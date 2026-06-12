import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import interp1d
from scipy.optimize import minimize
from skimage.transform import radon, iradon, resize
from skimage.filters import threshold_otsu
from scipy import ndimage

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017A')
SUP = ROOT / '支撑材料'
DATA = ROOT / 'A题附件.xls'
OUT = SUP / 'results'
TAB = SUP / 'tables'
FIG = SUP / 'quest1' / 'figures'
for p in [OUT,TAB,FIG]: p.mkdir(parents=True, exist_ok=True)

img = pd.read_excel(DATA, sheet_name='附件1', header=None).values.astype(float)
y = pd.read_excel(DATA, sheet_name='附件2', header=None).values.astype(float)
print('img', img.shape, img.min(), img.max(), 'sino', y.shape, y.min(), y.max())
# Radon library uses rows as y; theta degrees counter-clockwise from vertical projection convention.
thetas = np.linspace(0,179,180,endpoint=True)
r = radon(img, theta=thetas, circle=False)
print('radon', r.shape, r.min(), r.max())

def norm(v):
    v=np.asarray(v,float)
    s=v.std()
    if s<1e-9: return v*0
    return (v-v.mean())/s
# resample radon profile to 512, centered
def resample_profile(prof, n=512, scale=1.0, shift=0.0):
    m=len(prof)
    x=np.arange(m)-(m-1)/2
    xi=(np.arange(n)-(n-1)/2-shift)/scale
    return np.interp(xi, x, prof, left=0, right=0)
# coarse best angle and shift using normalized correlation over scale candidates
scales=np.linspace(1.0,1.6,13)
best=[]
for j in range(180):
    obs=y[:,j]
    if obs.std()<1e-9:
        best.append((j,0,1,0,0)); continue
    best_tuple=(-9,None,None,None)
    for k,th in enumerate(thetas):
        prof=r[:,k]
        for sc in scales:
            pr=resample_profile(prof,512,scale=sc,shift=0)
            # align by cross-correlation small shifts
            a=norm(obs); b=norm(pr)
            corr=np.correlate(a,b,mode='full')/len(a)
            idx=int(np.argmax(corr)); sh=idx-(len(a)-1)
            val=corr[idx]
            if val>best_tuple[0]: best_tuple=(val,th,sc,sh)
    best.append((j,best_tuple[1],best_tuple[2],best_tuple[3],best_tuple[0]))
    if j%30==0: print('j',j,best[-1])
cal=pd.DataFrame(best, columns=['projection_index','theta_deg','detector_scale_pixel_per_unit','center_shift_detector_cells','corr'])
cal.to_csv(TAB/'calibration_angle_matching.csv',index=False,encoding='utf-8-sig')
print(cal.describe())
print(cal.head(20))
# Fit angle sequence theta = theta0 + step*j mod 180 to matched theta values via circular doubling.
angles=np.deg2rad(cal.theta_deg.values*2)
j=np.arange(180)
# unwrap doubled angles sorted by j
unw=np.unwrap(angles)/2*180/np.pi
coef=np.polyfit(j,unw,1)
print('linear coef',coef)
# use matched angles directly if sequence poor; otherwise fitted monotone mod180
fit=(coef[0]*j+coef[1])%180
# detector params median
scale=float(np.median(cal.detector_scale_pixel_per_unit)); shift=float(np.median(cal.center_shift_detector_cells))
print('scale med',scale,'shift med',shift,'corr mean',cal.corr.mean())
# save parameters
import json
params={'rotation_center_pixel':[127.5+shift/scale,127.5], 'detector_spacing_pixel':1/scale, 'detector_scale_pixel_per_cell':scale, 'median_center_shift_detector_cells':shift, 'angle0_deg':float(fit[0]), 'angle_step_deg':float(coef[0]), 'angles_deg':[float(x) for x in fit], 'mean_profile_correlation':float(cal.corr.mean())}
(OUT/'calibration_parameters.json').write_text(json.dumps(params,ensure_ascii=False,indent=2),encoding='utf-8')
PYTHON='done'
print(PYTHON)
