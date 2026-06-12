import json, os, shutil, textwrap, math, re, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy import ndimage, stats
from skimage.transform import iradon, radon, resize
from skimage.filters import threshold_otsu
from skimage.metrics import structural_similarity as ssim
from scipy.optimize import linear_sum_assignment

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017A')
SUP = ROOT / '支撑材料'
DATA = ROOT / 'A题附件.xls'
DIRS = [SUP/'papper',SUP/'data',SUP/'references',SUP/'results',SUP/'tables',SUP/'code']
for q in range(1,5):
    DIRS += [SUP/f'quest{q}/codes',SUP/f'quest{q}/figures',SUP/f'quest{q}/outputs']
for d in DIRS: d.mkdir(parents=True, exist_ok=True)
for f in ROOT.glob('*'):
    if f.is_file() and f.suffix.lower() in ['.xls','.xlsx','.docx','.doc','.pdf']:
        dst=SUP/'data'/f.name
        if not dst.exists(): shutil.copy2(f,dst)

# Chinese font
for fp in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False
np.random.seed(2026)

# ---------- load data ----------
img = pd.read_excel(DATA, sheet_name='附件1', header=None).values.astype(float)
sino2 = pd.read_excel(DATA, sheet_name='附件2', header=None).values.astype(float)
sino3 = pd.read_excel(DATA, sheet_name='附件3', header=None).values.astype(float)
points = pd.read_excel(DATA, sheet_name='附件4', header=None).values.astype(float)
sino5 = pd.read_excel(DATA, sheet_name='附件5', header=None).values.astype(float)

# ---------- calibration ----------
def norm(a):
    a=np.asarray(a,float); s=a.std()
    return (a-a.mean())/s if s>1e-12 else a*0

def resample_profile(prof, n=512, scale=1.4, shift=0.0):
    m=len(prof); x=np.arange(m)-(m-1)/2
    xi=(np.arange(n)-(n-1)/2-shift)/scale
    return np.interp(xi, x, prof, left=0, right=0)

def best_match_for_projection(obs, rad, scales=np.linspace(1.25,1.52,10)):
    a=norm(obs)
    best=(-9,0,1.4,0)
    for k in range(rad.shape[1]):
        prof=rad[:,k]
        for sc in scales:
            pr=resample_profile(prof, 512, sc, 0)
            b=norm(pr)
            corr=np.correlate(a,b,mode='full')/len(a)
            idx=int(np.argmax(corr)); sh=idx-(len(a)-1); val=float(corr[idx])
            if val>best[0]: best=(val,k,sc,sh)
    return best

theta_grid=np.arange(180,dtype=float)
rad=radon(img, theta=theta_grid, circle=False)
# exhaustive matching of every third angle, then infer linear sequence; full matching saved for evidence.
matches=[]
for j in range(180):
    val,k,sc,sh=best_match_for_projection(sino2[:,j],rad)
    matches.append([j,k,sc,sh,val])
match_df=pd.DataFrame(matches,columns=['projection_index','matched_theta_deg','scale_pixel_per_cell','center_shift_cell','corr'])
match_df.to_csv(SUP/'tables/calibration_projection_matching.csv',index=False,encoding='utf-8-sig')
# robust initial angle: first 60 projections are distinctive and monotone; median of k-j
first=match_df.iloc[:60]
theta0=float(np.median(((first.matched_theta_deg-first.projection_index+90)%180)-90))
angle_step=1.0
angles=(theta0 + np.arange(180)*angle_step)%180
scale=float(np.median(first.scale_pixel_per_cell))
# fit center offset using shift vs theta: shift_cell ≈ scale*(dx cosθ + dy sinθ)
valid=match_df[(match_df['corr']>0.975) & (match_df['projection_index']<100)].copy()
if len(valid)<20: valid=first.copy()
T=np.deg2rad(theta0+valid.projection_index.values)
A=np.column_stack([np.cos(T), np.sin(T), np.ones_like(T)])*np.array([scale,scale,1.0])
coef, *_ = np.linalg.lstsq(A, valid.center_shift_cell.values, rcond=None)
dx_pix, dy_pix, c0 = [float(x) for x in coef]
center_pixel=[127.5+dx_pix,127.5+dy_pix]
pixel_mm=100/256
detector_spacing_pixel=1/scale
detector_spacing_mm=detector_spacing_pixel*pixel_mm
center_mm=[(center_pixel[0]+0.5)*pixel_mm, (255.5-center_pixel[1])*pixel_mm]

# reconstruct template to estimate amplitude scale and validation metrics
def reconstruct(sino, angles, output_size=256):
    # FBP; clip weak numerical negative values
    rec=iradon(sino, theta=angles, output_size=output_size, filter_name='ramp', circle=False)
    return rec
rec_template_raw=reconstruct(sino2, angles)
# linear amplitude correction using pixels where template support nonzero or rec high
mask=(img>0.05) | (rec_template_raw>np.percentile(rec_template_raw,85))
a=float(np.sum(rec_template_raw[mask]*img[mask])/(np.sum(rec_template_raw[mask]**2)+1e-12))
rec_template=np.clip(rec_template_raw*a,0,None)
mae=float(np.mean(np.abs(rec_template-img)))
rmse=float(np.sqrt(np.mean((rec_template-img)**2)))
ss=float(ssim(img, np.clip(rec_template,0,1), data_range=1))

# unknown reconstructions
rec2=np.clip(reconstruct(sino3, angles)*a,0,None)
rec3=np.clip(reconstruct(sino5, angles)*a,0,None)
# normalize lightly: preserve absorption scale but cap extreme ringing
for arr in [rec2,rec3]:
    q=np.percentile(arr,99.8)
    if q>0: arr[arr>q]=q

# coordinates: problem points in mm with tray origin lower-left; convert to pixel row/col
def sample_points(rec, pts):
    vals=[]
    for x,y in pts:
        col=x/pixel_mm-0.5
        row=255.5-y/pixel_mm
        vals.append(float(ndimage.map_coordinates(rec, [[row],[col]], order=1, mode='nearest')[0]))
    return vals
vals2=sample_points(rec2,points)
vals3=sample_points(rec3,points)
pt_df=pd.DataFrame({'序号':np.arange(1,11),'x/mm':points[:,0],'y/mm':points[:,1],'问题2吸收率':vals2,'问题3吸收率':vals3})
pt_df.to_csv(SUP/'tables/ten_point_absorption.csv',index=False,encoding='utf-8-sig')

# geometry descriptors
def geom_info(rec):
    positive=rec[rec>np.percentile(rec,70)]
    thr=float(max(threshold_otsu(rec), np.percentile(rec,75)*0.6)) if rec.max()>0 else 0
    bw=ndimage.binary_opening(rec>thr, iterations=1)
    lab,n=ndimage.label(bw)
    objs=[]
    for i in range(1,n+1):
        coords=np.argwhere(lab==i)
        if len(coords)<20: continue
        vals=rec[lab==i]
        rows,cols=coords[:,0],coords[:,1]
        x=(cols+0.5)*pixel_mm; y=(255.5-rows)*pixel_mm
        objs.append({'area_mm2':float(len(coords)*pixel_mm**2),'centroid_x_mm':float(x.mean()),'centroid_y_mm':float(y.mean()),'mean_absorption':float(vals.mean()),'max_absorption':float(vals.max()),'bbox_xmin_mm':float(x.min()),'bbox_xmax_mm':float(x.max()),'bbox_ymin_mm':float(y.min()),'bbox_ymax_mm':float(y.max())})
    objs=sorted(objs,key=lambda d:d['area_mm2'],reverse=True)[:10]
    return thr, objs
thr2, objs2=geom_info(rec2); thr3, objs3=geom_info(rec3)
pd.DataFrame(objs2).to_csv(SUP/'tables/problem2_geometry_components.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(objs3).to_csv(SUP/'tables/problem3_geometry_components.csv',index=False,encoding='utf-8-sig')

# save reconstructed matrices; .xlsx plus tab-separated .xls-compatible files
for name,arr in [('problem2',rec2),('problem3',rec3)]:
    df=pd.DataFrame(np.round(arr,4))
    df.to_excel(ROOT/f'{name}.xlsx', header=False, index=False)
    df.to_csv(ROOT/f'{name}.xls', sep='\t', header=False, index=False, float_format='%.4f')
    df.to_excel(SUP/'results'/f'{name}.xlsx', header=False, index=False)
    df.to_csv(SUP/'results'/f'{name}.xls', sep='\t', header=False, index=False, float_format='%.4f')

# figures
def save_img(arr, path, title, cmap='viridis'):
    plt.figure(figsize=(6,5))
    plt.imshow(arr, cmap=cmap, extent=[0,100,0,100], origin='lower')
    plt.colorbar(label='吸收率')
    plt.xlabel('x/mm'); plt.ylabel('y/mm'); plt.title(title)
    plt.tight_layout(); plt.savefig(path,dpi=300,bbox_inches='tight'); plt.close()
save_img(img, SUP/'quest1/figures/template_absorption.png','标定模板吸收率分布')
save_img(rec_template, SUP/'quest1/figures/template_reconstruction_validation.png','模板反投影重建验证')
save_img(rec2, SUP/'quest2/figures/problem2_reconstruction.png','问题2未知介质重建吸收率')
save_img(rec3, SUP/'quest3/figures/problem3_reconstruction.png','问题3未知介质重建吸收率')
plt.figure(figsize=(9,4)); plt.plot(match_df.projection_index, match_df.matched_theta_deg,'.',ms=3,label='轮廓匹配角'); plt.plot(np.arange(180),angles,'-',lw=1,label='拟合射线方向'); plt.xlabel('投影序号'); plt.ylabel('角度/°'); plt.title('180个射线方向标定'); plt.legend(); plt.tight_layout(); plt.savefig(SUP/'quest1/figures/calibrated_angles.png',dpi=300,bbox_inches='tight'); plt.close()
plt.figure(figsize=(8,4)); plt.plot(match_df.projection_index, match_df.center_shift_cell,'.-',ms=3); plt.xlabel('投影序号'); plt.ylabel('探测器中心偏移/单元'); plt.title('中心偏移匹配结果'); plt.tight_layout(); plt.savefig(SUP/'quest1/figures/center_shift_fit.png',dpi=300,bbox_inches='tight'); plt.close()
# sensitivity: perturb theta0 and scale
sens=[]
for dt in [-0.5,-0.25,0,0.25,0.5]:
    rec=np.clip(reconstruct(sino2, (angles+dt)%180)*a,0,None)
    sens.append({'参数':'初始角扰动/°','扰动':dt,'RMSE':float(np.sqrt(np.mean((rec-img)**2))),'SSIM':float(ssim(img,np.clip(rec,0,1),data_range=1))})
for ds in [-0.04,-0.02,0,0.02,0.04]:
    # detector spacing perturb approximated by sinogram vertical zoom before FBP
    zoomed=ndimage.zoom(sino2, (1+ds,1), order=1)
    if zoomed.shape[0]>512:
        start=(zoomed.shape[0]-512)//2; z=zoomed[start:start+512]
    else:
        z=np.zeros_like(sino2); start=(512-zoomed.shape[0])//2; z[start:start+zoomed.shape[0]]=zoomed
    rec=np.clip(reconstruct(z, angles)*a,0,None)
    sens.append({'参数':'探测器间距相对扰动','扰动':ds,'RMSE':float(np.sqrt(np.mean((rec-img)**2))),'SSIM':float(ssim(img,np.clip(rec,0,1),data_range=1))})
sens_df=pd.DataFrame(sens); sens_df.to_csv(SUP/'tables/sensitivity_analysis.csv',index=False,encoding='utf-8-sig')
plt.figure(figsize=(8,4))
for key,g in sens_df.groupby('参数'):
    plt.plot(g['扰动'],g['RMSE'],'o-',label=key)
plt.xlabel('扰动量'); plt.ylabel('模板重建RMSE'); plt.title('标定参数灵敏度分析'); plt.legend(); plt.tight_layout(); plt.savefig(SUP/'quest4/figures/sensitivity_rmse.png',dpi=300,bbox_inches='tight'); plt.close()

# frozen numbers
frozen={
 'data_audit':{'template_shape':'256x256','sinogram_shape':'512x180','point_count':10,'template_min':float(img.min()),'template_max':float(img.max())},
 'calibration':{'rotation_center_pixel_x':round(center_pixel[0],4),'rotation_center_pixel_y':round(center_pixel[1],4),'rotation_center_mm_x':round(center_mm[0],4),'rotation_center_mm_y':round(center_mm[1],4),'detector_spacing_pixel':round(detector_spacing_pixel,4),'detector_spacing_mm':round(detector_spacing_mm,4),'initial_angle_deg':round(theta0,4),'angle_step_deg':round(angle_step,4),'mean_matching_corr':round(float(match_df['corr'].mean()),4),'template_reconstruction_MAE':round(mae,4),'template_reconstruction_RMSE':round(rmse,4),'template_reconstruction_SSIM':round(ss,4)},
 'problem2':{'point_absorption':[round(x,4) for x in vals2],'threshold':round(thr2,4),'component_count_reported':len(objs2),'main_components':objs2[:5]},
 'problem3':{'point_absorption':[round(x,4) for x in vals3],'threshold':round(thr3,4),'component_count_reported':len(objs3),'main_components':objs3[:5]},
 'sensitivity':sens_df.round(4).to_dict(orient='records')
}
(SUP/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
# route and analysis notes
(SUP/'references/model_route.json').write_text(json.dumps({'baseline':'直接以等角度FBP重建作为基线','main_model':'模板轮廓匹配标定 + 滤波反投影重建 + 组件阈值分割 + 参数扰动灵敏度','chosen_reason':'标定模板已知，Radon投影可直接与附件2轮廓匹配；FBP可解释、可复现，并能输出256x256吸收率矩阵。'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(frozen,ensure_ascii=False,indent=2)[:3000])
