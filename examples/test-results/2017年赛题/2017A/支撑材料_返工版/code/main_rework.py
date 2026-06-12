#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2017A 返工版：CT系统参数标定与成像重建。

运行位置不限；脚本自动定位题目根目录，输出到 支撑材料_返工版/。
"""
from __future__ import annotations
import json, shutil, math, zipfile, os
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import optimize, ndimage
from skimage.transform import radon, iradon, resize
from skimage.metrics import structural_similarity as ssim
from skimage.filters import threshold_otsu
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]  # .../2017A
DATA = ROOT / 'A题附件.xls'
SUP = ROOT / '支撑材料_返工版'
for d in ['paper','data','references','results','tables','code','quest1/figures','quest1/outputs','quest2/figures','quest2/outputs','quest3/figures','quest3/outputs','quest4/figures','verification']:
    (SUP/d).mkdir(parents=True, exist_ok=True)
for f in ROOT.glob('*'):
    if f.is_file() and f.suffix.lower() in ['.xls','.xlsx','.docx','.doc','.pdf']:
        dst=SUP/'data'/f.name
        if not dst.exists(): shutil.copy2(f,dst)

# fonts
for fp in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif']=[font_manager.FontProperties(fname=fp).get_name(),'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus']=False
np.random.seed(2017)

# load
img = pd.read_excel(DATA, sheet_name='附件1', header=None).values.astype(float)
sino2_raw = pd.read_excel(DATA, sheet_name='附件2', header=None).values.astype(float)
sino3_raw = pd.read_excel(DATA, sheet_name='附件3', header=None).values.astype(float)
points = pd.read_excel(DATA, sheet_name='附件4', header=None).values.astype(float)
sino5_raw = pd.read_excel(DATA, sheet_name='附件5', header=None).values.astype(float)
N=img.shape[0]; pixel_mm=100/N
L = radon(img, theta=[0.0], circle=False).shape[0]
x_rad = np.arange(L)-(L-1)/2
x_cell = np.arange(512)-(512-1)/2

# helpers
def corr(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float)
    a=a-a.mean(); b=b-b.mean(); den=np.linalg.norm(a)*np.linalg.norm(b)
    return float(a.dot(b)/den) if den>1e-12 else 0.0

def simulate_profile(prof, scale, shift_cell, n=512):
    xi=(x_cell-shift_cell)/scale
    return np.interp(xi, x_rad, prof, left=0, right=0)

def best_shift_corr(obs, prof, scale, max_shift=90):
    base=simulate_profile(prof, scale, 0)
    aa=(obs-obs.mean())/(obs.std()+1e-12); bb=(base-base.mean())/(base.std()+1e-12)
    cc=np.correlate(aa,bb,mode='full')/len(aa)
    lags=np.arange(-len(aa)+1,len(aa))
    mask=(lags>=-max_shift)&(lags<=max_shift)
    lag=int(lags[mask][np.argmax(cc[mask])])
    best=(-9,0.0)
    for sh in np.linspace(lag-2, lag+2, 17):
        c=corr(obs, simulate_profile(prof, scale, sh))
        if c>best[0]: best=(c,float(sh))
    return best[1], best[0]

def mean_match_score(params, js=None, return_detail=False):
    theta0, step, scale=params
    if js is None: js=np.arange(180)
    rad=radon(img, theta=(theta0+step*js)%180, circle=False)
    vals=[]; details=[]
    for idx,j in enumerate(js):
        sh,c=best_shift_corr(sino2_raw[:,j], rad[:,idx], scale)
        vals.append(c); details.append([int(j), float((theta0+step*j)%180), float(scale), float(sh), float(c)])
    return (float(np.mean(vals)), details) if return_detail else -float(np.mean(vals))

# calibration: coarse + refine
js_coarse=np.arange(0,180,3)
coarse=[]
for scale in np.linspace(1.25,1.55,13):
    for theta0 in np.linspace(20,38,37):
        sc=-mean_match_score((theta0,1.0,scale), js_coarse)
        coarse.append((sc,theta0,1.0,scale))
coarse=sorted(coarse, reverse=True)[:6]
def obj(p):
    th,st,sc=p
    if not (15<=th<=45 and 0.96<=st<=1.03 and 1.1<=sc<=1.7): return 9
    return mean_match_score((th,st,sc), js_coarse)
best=None
for _,th,st,sc in coarse[:4]:
    res=optimize.minimize(obj,[th,st,sc],method='Nelder-Mead',options={'maxiter':180,'xatol':5e-4,'fatol':1e-6})
    cand=(-res.fun,*res.x)
    if best is None or cand[0]>best[0]: best=cand
match_mean, details = mean_match_score(best[1:], np.arange(180), True)
match_df=pd.DataFrame(details,columns=['projection_index','theta_deg','scale_cell_per_radon_pixel','shift_cell','corr'])
theta0, step, scale = float(best[1]), float(best[2]), float(best[3])
angles=(theta0+step*np.arange(180))%180
match_df.to_csv(SUP/'tables/calibration_profile_matching.csv',index=False,encoding='utf-8-sig')

# detector correction
def correct_sinogram(raw, shifts):
    out=np.zeros((L, raw.shape[1]))
    for j in range(raw.shape[1]):
        cell_pos=scale*x_rad + shifts[j]
        out[:,j]=np.interp(cell_pos, x_cell, raw[:,j], left=0, right=0)
    return out
shifts=match_df.shift_cell.values
sino2_corr=correct_sinogram(sino2_raw, shifts)
sino3_corr=correct_sinogram(sino3_raw, shifts)
sino5_corr=correct_sinogram(sino5_raw, shifts)
for name,arr in [('template_corrected_sinogram.csv',sino2_corr),('problem2_corrected_sinogram.csv',sino3_corr),('problem3_corrected_sinogram.csv',sino5_corr)]:
    pd.DataFrame(arr).to_csv(SUP/'results'/name,index=False,header=False,float_format='%.6f')

# reconstruction candidates and metrics
def fit_amp(rec, target=img):
    A=np.column_stack([rec.ravel(), np.ones(rec.size)])
    ab,*_=np.linalg.lstsq(A,target.ravel(),rcond=None)
    return float(ab[0]), float(ab[1])
def image_metrics(rec, name):
    a,b=fit_amp(rec,img); rr=a*rec+b; rr_clip=np.clip(rr,0,1)
    return {'name':name,'amp_a':a,'amp_b':b,'mae':float(np.mean(np.abs(rr-img))),'rmse':float(np.sqrt(np.mean((rr-img)**2))),'ssim':float(ssim(img,rr_clip,data_range=1)),'min':float(rr.min()),'max':float(rr.max())}, rr
metrics=[]; recs={}
# baselines raw
for filt in ['ramp','shepp-logan','hann']:
    rec=iradon(sino2_raw, theta=np.arange(180), output_size=256, filter_name=filt, circle=False)
    m,rr=image_metrics(rec,'baseline_raw512_'+filt); metrics.append(m); recs[m['name']]=rr
# corrected
for filt in ['ramp','shepp-logan','hann']:
    rec=iradon(sino2_corr, theta=angles, output_size=256, filter_name=filt, circle=False)
    m,rr=image_metrics(rec,'main_corrected_'+filt); metrics.append(m); recs[m['name']]=rr
metrics_df=pd.DataFrame(metrics).sort_values('rmse')
metrics_df.to_csv(SUP/'tables/template_reconstruction_metrics.csv',index=False,encoding='utf-8-sig')
main_method='main_corrected_shepp-logan'
amp_a=float(metrics_df[metrics_df.name==main_method].iloc[0].amp_a)
amp_b=float(metrics_df[metrics_df.name==main_method].iloc[0].amp_b)
rec_template=recs[main_method]

# projection back metrics raw coordinate
def raw_forward_from_image(im, shifts):
    rad=radon(im, theta=angles, circle=False)
    raw=np.zeros_like(sino2_raw)
    for j in range(raw.shape[1]):
        xi=(x_cell-shifts[j])/scale
        raw[:,j]=np.interp(xi, x_rad, rad[:,j], left=0, right=0)
    return raw
def proj_metric(im, raw, shifts, name):
    pred=raw_forward_from_image(im, shifts)
    A=np.column_stack([pred.ravel(), np.ones(pred.size)])
    ab,*_=np.linalg.lstsq(A, raw.ravel(), rcond=None)
    pp=ab[0]*pred+ab[1]
    return {'name':name,'proj_rmse':float(np.sqrt(np.mean((pp-raw)**2))),'proj_mae':float(np.mean(np.abs(pp-raw))),'proj_corr':corr(pp.ravel(), raw.ravel()),'proj_scale':float(ab[0]),'proj_offset':float(ab[1])}
proj_rows=[]
for nm in metrics_df.name:
    if nm in recs:
        use_shifts=shifts if 'corrected' in nm else np.zeros(180)
        proj_rows.append(proj_metric(recs[nm], sino2_raw, use_shifts, nm))
proj_df=pd.DataFrame(proj_rows).sort_values('proj_rmse')
proj_df.to_csv(SUP/'tables/projection_back_metrics.csv',index=False,encoding='utf-8-sig')

# unknown recon using corrected sinograms and main filter, same amplitude calibration
rec2_raw=iradon(sino3_corr, theta=angles, output_size=256, filter_name='shepp-logan', circle=False)
rec3_raw=iradon(sino5_corr, theta=angles, output_size=256, filter_name='shepp-logan', circle=False)
rec2=np.clip(amp_a*rec2_raw+amp_b,0,None)
rec3=np.clip(amp_a*rec3_raw+amp_b,0,None)
# no upper quantile capping

def save_true_xls(path, arr):
    import xlwt
    wb=xlwt.Workbook(); ws=wb.add_sheet('Sheet1')
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ws.write(i,j,float(round(arr[i,j],4)))
    wb.save(str(path))
for base,arr in [('problem2',rec2),('problem3',rec3)]:
    pd.DataFrame(np.round(arr,4)).to_excel(ROOT/f'{base}_rework.xlsx',header=False,index=False)
    pd.DataFrame(np.round(arr,4)).to_excel(SUP/'results'/f'{base}.xlsx',header=False,index=False)
    save_true_xls(ROOT/f'{base}_rework.xls', np.round(arr,4))
    save_true_xls(SUP/'results'/f'{base}.xls', np.round(arr,4))

# points
def sample_points(rec, pts):
    vals=[]
    for x,y in pts:
        col=x/pixel_mm-0.5; row=255.5-y/pixel_mm
        vals.append(float(ndimage.map_coordinates(rec, [[row],[col]], order=1, mode='nearest')[0]))
    return vals
vals2=sample_points(rec2,points); vals3=sample_points(rec3,points)
pt_df=pd.DataFrame({'序号':np.arange(1,11),'x/mm':points[:,0],'y/mm':points[:,1],'问题2吸收率':vals2,'问题3吸收率':vals3})
pt_df.round(4).to_csv(SUP/'tables/ten_point_absorption_rework.csv',index=False,encoding='utf-8-sig')

# geometry components
def geom_info(rec, min_area=20):
    thr=max(float(threshold_otsu(rec)), float(np.percentile(rec,70))) if rec.max()>0 else 0
    bw=ndimage.binary_opening(rec>thr, iterations=1)
    lab,n=ndimage.label(bw)
    rows=[]
    for i in range(1,n+1):
        coords=np.argwhere(lab==i)
        if len(coords)*pixel_mm**2<min_area: continue
        vals=rec[lab==i]; rr,cc=coords[:,0],coords[:,1]
        x=(cc+0.5)*pixel_mm; y=(255.5-rr)*pixel_mm
        rows.append({'area_mm2':float(len(coords)*pixel_mm**2),'centroid_x_mm':float(x.mean()),'centroid_y_mm':float(y.mean()),'mean_absorption':float(vals.mean()),'max_absorption':float(vals.max()),'bbox_xmin_mm':float(x.min()),'bbox_xmax_mm':float(x.max()),'bbox_ymin_mm':float(y.min()),'bbox_ymax_mm':float(y.max())})
    return thr, sorted(rows,key=lambda r:r['area_mm2'], reverse=True)
thr2,geo2=geom_info(rec2); thr3,geo3=geom_info(rec3)
pd.DataFrame(geo2).round(4).to_csv(SUP/'tables/problem2_geometry_components_rework.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(geo3).round(4).to_csv(SUP/'tables/problem3_geometry_components_rework.csv',index=False,encoding='utf-8-sig')

# unknown projection back consistency (compare reconstructed image to its own raw projection)
unk_proj=pd.DataFrame([proj_metric(rec2, sino3_raw, shifts, 'problem2_rework'), proj_metric(rec3, sino5_raw, shifts, 'problem3_rework')])
unk_proj.to_csv(SUP/'tables/unknown_projection_back_metrics.csv',index=False,encoding='utf-8-sig')

# sensitivity around theta0/scale: recompute corrected template for perturbations but same shifts approximate? use shift rematch for fair subsets expensive; do full correction with same shifts for local sensitivity.
sens=[]
for dt in [-0.5,-0.25,0,0.25,0.5]:
    ang=(theta0+dt+step*np.arange(180))%180
    rec=iradon(sino2_corr, theta=ang, output_size=256, filter_name='shepp-logan', circle=False)
    m,_=image_metrics(rec,f'theta0{dt:+.2f}')
    sens.append({'参数':'初始角/度','扰动':dt,'RMSE':m['rmse'],'SSIM':m['ssim']})
for ds in [-0.04,-0.02,0,0.02,0.04]:
    oldscale=scale; sc=scale*(1+ds)
    out=np.zeros_like(sino2_corr)
    for j in range(180):
        out[:,j]=np.interp(sc*x_rad+shifts[j], x_cell, sino2_raw[:,j], left=0, right=0)
    rec=iradon(out, theta=angles, output_size=256, filter_name='shepp-logan', circle=False)
    m,_=image_metrics(rec,f'scale{ds:+.2f}')
    sens.append({'参数':'探测器尺度相对扰动','扰动':ds,'RMSE':m['rmse'],'SSIM':m['ssim']})
sens_df=pd.DataFrame(sens); sens_df.round(5).to_csv(SUP/'tables/sensitivity_analysis_rework.csv',index=False,encoding='utf-8-sig')

# new template simulation: asymmetric multi-feature template, compare min pairwise profile distance vs original
newT=np.zeros_like(img)
yy,xx=np.mgrid[0:N,0:N]
def add_disk(cx,cy,r,val):
    newT[((xx-cx)**2+(yy-cy)**2)<=r*r]=val
def add_rect(x1,x2,y1,y2,val):
    newT[y1:y2,x1:x2]=val
add_disk(70,80,22,1.0); add_disk(165,70,12,0.65); add_disk(185,175,28,0.8)
# ring
rr=np.sqrt((xx-88)**2+(yy-178)**2); newT[(rr>=15)&(rr<=19)]=1.2
add_rect(35,205,130,138,0.55)
# diagonal stripe
mask_diag=(np.abs((yy-40)-0.45*(xx-30))<3)&(xx>30)&(xx<220)&(yy>40)&(yy<150); newT[mask_diag]=0.9
add_rect(25,60,25,55,0.3); add_rect(60,95,25,55,0.6); add_rect(95,130,25,55,0.9)
rad_orig=radon(img, theta=np.arange(180), circle=False); rad_new=radon(newT, theta=np.arange(180), circle=False)
def min_pair_dist(radmat):
    prof=(radmat-radmat.mean(axis=0))/(radmat.std(axis=0)+1e-12)
    vals=[]
    for i in range(180):
        for j in range(i+1,180): vals.append(np.linalg.norm(prof[:,i]-prof[:,j]))
    return float(np.min(vals)), float(np.percentile(vals,5)), float(np.mean(vals))
tmpl_cmp=pd.DataFrame([{'模板':'原模板','最小角度剖面距离':min_pair_dist(rad_orig)[0],'5%分位距离':min_pair_dist(rad_orig)[1],'平均距离':min_pair_dist(rad_orig)[2]}, {'模板':'新设计模板','最小角度剖面距离':min_pair_dist(rad_new)[0],'5%分位距离':min_pair_dist(rad_new)[1],'平均距离':min_pair_dist(rad_new)[2]}])
tmpl_cmp.round(4).to_csv(SUP/'tables/new_template_identifiability.csv',index=False,encoding='utf-8-sig')

# figures
def imfig(arr,path,title,cmap='viridis'):
    plt.figure(figsize=(6,5)); plt.imshow(arr,cmap=cmap,origin='lower',extent=[0,100,0,100]); plt.colorbar(label='吸收率'); plt.xlabel('x/mm'); plt.ylabel('y/mm'); plt.title(title); plt.tight_layout(); plt.savefig(path,dpi=300,bbox_inches='tight'); plt.close()
imfig(img,SUP/'quest1/figures/template_original.png','附件1标定模板')
imfig(rec_template,SUP/'quest1/figures/template_reconstruction_rework.png','返工版模板回代重建')
imfig(rec2,SUP/'quest2/figures/problem2_reconstruction_rework.png','返工版问题2重建')
imfig(rec3,SUP/'quest3/figures/problem3_reconstruction_rework.png','返工版问题3重建')
imfig(newT,SUP/'quest4/figures/new_template_design.png','问题4新模板设计示意')
plt.figure(figsize=(9,4)); plt.plot(match_df.projection_index, match_df.theta_deg,label='标定方向'); plt.xlabel('投影序号'); plt.ylabel('角度/°'); plt.title('返工版射线方向标定'); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(SUP/'quest1/figures/angle_sequence_rework.png',dpi=300,bbox_inches='tight'); plt.close()
plt.figure(figsize=(9,4)); plt.plot(match_df.projection_index, match_df.shift_cell,label='逐投影shift'); plt.xlabel('投影序号'); plt.ylabel('探测器偏移/cell'); plt.title('逐投影探测器中心校正序列'); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(SUP/'quest1/figures/detector_shift_sequence.png',dpi=300,bbox_inches='tight'); plt.close()
plt.figure(figsize=(8,4)); x=np.arange(len(metrics_df)); plt.bar(x,metrics_df.rmse); plt.xticks(x,metrics_df.name,rotation=30,ha='right',fontsize=8); plt.ylabel('模板RMSE'); plt.title('Baseline与返工主模型模板重建误差对比'); plt.tight_layout(); plt.savefig(SUP/'quest1/figures/baseline_comparison_rmse.png',dpi=300,bbox_inches='tight'); plt.close()
plt.figure(figsize=(8,4));
for k,g in sens_df.groupby('参数'):
    plt.plot(g['扰动'],g['RMSE'],'o-',label=k)
plt.xlabel('扰动量'); plt.ylabel('模板RMSE'); plt.title('返工版参数灵敏度分析'); plt.legend(); plt.tight_layout(); plt.savefig(SUP/'quest4/figures/sensitivity_rework.png',dpi=300,bbox_inches='tight'); plt.close()

# frozen numbers
best_img=metrics_df[metrics_df.name==main_method].iloc[0].to_dict()
baseline=metrics_df[metrics_df.name=='baseline_raw512_shepp-logan'].iloc[0].to_dict()
best_proj=proj_df[proj_df.name==main_method].iloc[0].to_dict()
frozen={
 'data_audit':{'template_shape':'256x256','sinogram_shape':'512x180','radon_detector_len':int(L),'point_count':10,'pixel_mm':pixel_mm},
 'calibration':{'theta0_deg':theta0,'angle_step_deg':step,'scale_cell_per_radon_pixel':scale,'detector_spacing_pixel_per_cell':1/scale,'detector_spacing_mm_per_cell':(1/scale)*pixel_mm,'mean_profile_corr':match_mean,'shift_mean_cell':float(np.mean(shifts)),'shift_std_cell':float(np.std(shifts)),'shift_min_cell':float(np.min(shifts)),'shift_max_cell':float(np.max(shifts))},
 'template_validation':{'baseline_raw512_shepp_logan':{k:float(baseline[k]) if isinstance(baseline[k],(int,float,np.floating)) else baseline[k] for k in baseline},'main_corrected_shepp_logan':{k:float(best_img[k]) if isinstance(best_img[k],(int,float,np.floating)) else best_img[k] for k in best_img},'projection_back_main':{k:float(best_proj[k]) if isinstance(best_proj[k],(int,float,np.floating)) else best_proj[k] for k in best_proj}},
 'problem2':{'point_absorption':[round(float(x),4) for x in vals2], 'geometry_top5':geo2[:5], 'projection_back':unk_proj.iloc[0].to_dict()},
 'problem3':{'point_absorption':[round(float(x),4) for x in vals3], 'geometry_top5':geo3[:5], 'projection_back':unk_proj.iloc[1].to_dict()},
 'new_template':tmpl_cmp.round(4).to_dict(orient='records')
}
(SUP/'results/frozen_numbers_rework.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
# requirements, run_all, verify
(SUP/'requirements.txt').write_text('numpy\npandas\nscipy\nscikit-image\nmatplotlib\nopenpyxl\nxlwt\n',encoding='utf-8')
(SUP/'run_all.py').write_text("""from pathlib import Path\nimport subprocess, sys\nroot=Path(__file__).resolve().parents[0]\nsubprocess.check_call([sys.executable, str(root/'code'/'main_rework.py')])\n""",encoding='utf-8')
(SUP/'verification/verify_outputs.py').write_text("""from pathlib import Path\nimport json, pandas as pd\nroot=Path(__file__).resolve().parents[1]\nassert (root/'paper'/'论文.pdf').exists()\nfor f in ['results/problem2.xls','results/problem3.xls','results/frozen_numbers_rework.json']:\n    assert (root/f).exists(), f\nfor f in ['results/problem2.xlsx','results/problem3.xlsx']:\n    df=pd.read_excel(root/f,header=None); assert df.shape==(256,256), df.shape\nprint('VERIFY_OK')\n""",encoding='utf-8')
# notes
(SUP/'references/method_route_rework.md').write_text('返工版采用模板Radon剖面联合标定 theta0/step/scale，并对每列投影使用 matched-shift 校正后再FBP重建。标定参数真实进入 corrected sinogram 和未知介质重建链。',encoding='utf-8')
print(json.dumps(frozen,ensure_ascii=False,indent=2)[:4000])
