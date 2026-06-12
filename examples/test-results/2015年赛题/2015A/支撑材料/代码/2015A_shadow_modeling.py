# -*- coding: utf-8 -*-
"""
2015A 太阳影子定位：完整建模求解脚本
输出：图表、结果表、frozen_numbers.json、contracts/model_results.json 等。
"""
from __future__ import annotations
import json, math, itertools, os, re
from pathlib import Path
from datetime import datetime, date, time, timedelta
import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '数据' / '附件1-3.xls'
FIG = ROOT / '图表'; TAB = ROOT / 'tables'; RES = ROOT / 'results'; CON = ROOT / 'contracts'
for d in [FIG,TAB,RES,CON]: d.mkdir(parents=True, exist_ok=True)
np.random.seed(42)

# 中文字体
for fp in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif']=[font_manager.FontProperties(fname=fp).get_name(),'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus']=False

BEIJING_OFFSET = 8.0

# -------- solar geometry --------
def day_of_year(dt: date) -> int:
    return dt.timetuple().tm_yday

def declination_rad(n:int)->float:
    # Cooper formula, adequate for mathematical modeling contest; radians
    return math.radians(23.45) * math.sin(math.radians(360*(284+n)/365.0))

def equation_of_time_min(n:int)->float:
    # NOAA approximation
    B=math.radians(360*(n-81)/364.0)
    return 9.87*math.sin(2*B)-7.53*math.cos(B)-1.5*math.sin(B)

def solar_vec_ENU(lat_deg:float, lon_deg:float, dt_local:datetime):
    """Return sun unit vector components in local East, North, Up."""
    n=day_of_year(dt_local.date())
    phi=math.radians(lat_deg); delta=declination_rad(n)
    minutes=dt_local.hour*60 + dt_local.minute + dt_local.second/60
    # local standard meridian for Beijing time = 120E
    tst=minutes + equation_of_time_min(n) + 4*(lon_deg - 120.0)
    ha=math.radians(tst/4.0 - 180.0)  # hour angle, positive afternoon
    sin_alt=math.sin(phi)*math.sin(delta)+math.cos(phi)*math.cos(delta)*math.cos(ha)
    sin_alt=max(-1,min(1,sin_alt))
    alt=math.asin(sin_alt)
    # ENU components: east, north, up
    east = -math.cos(delta)*math.sin(ha)
    north = math.cos(phi)*math.sin(delta) - math.sin(phi)*math.cos(delta)*math.cos(ha)
    up = sin_alt
    return np.array([east,north,up], dtype=float), alt

def shadow_EN(lat, lon, H, dt):
    s, alt = solar_vec_ENU(lat, lon, dt)
    if s[2] <= 1e-6:
        return np.array([np.nan,np.nan])
    # shadow from pole base opposite sun horizontal direction
    return -H * s[:2]/s[2]

def rotate(points, theta):
    c,s=math.cos(theta), math.sin(theta)
    R=np.array([[c,-s],[s,c]])
    return points @ R.T

def theoretical_xy(params, d:date, times):
    lat, lon, logH, theta = params
    H=math.exp(logH)
    pts=[]
    for t in times:
        en=shadow_EN(lat, lon, H, datetime.combine(d,t))
        pts.append(en)
    pts=np.array(pts)
    return rotate(pts, theta)

def residuals(params, d, times, obs):
    lat, lon, logH, theta = params
    if not (-65 <= lat <= 65 and 70 <= lon <= 150 and -4 <= logH <= 3):
        return np.ones(obs.size)*1e3
    pred=theoretical_xy(params,d,times)
    if not np.all(np.isfinite(pred)):
        return np.ones(obs.size)*1e3
    return (pred-obs).ravel()

def parse_sheet(sheet):
    df=pd.read_excel(DATA, sheet_name=sheet, header=None)
    rows=df.iloc[3:].dropna(how='all').copy()
    times=[]; xy=[]
    for _,r in rows.iterrows():
        val=r.iloc[0]
        if pd.isna(val): continue
        if isinstance(val, str):
            hh,mm,ss=map(int,val.split(':'))
            tt=time(hh,mm,ss)
        elif hasattr(val,'hour'):
            tt=time(val.hour,val.minute,getattr(val,'second',0))
        else:
            # excel fraction of day
            secs=int(round(float(val)*86400)); tt=(datetime(2000,1,1)+timedelta(seconds=secs)).time()
        times.append(tt); xy.append([float(r.iloc[1]), float(r.iloc[2])])
    return times, np.array(xy)

def fit_for_date(times, obs, d, starts=None):
    if starts is None:
        starts=[]
        # coarse but efficient starts over plausible China/Asia and all coordinate rotations
        for lat in [-30,0,25,40,55]:
            for lon in [80,100,115,130,145]:
                for th in [-math.pi, -math.pi/2, 0, math.pi/2]:
                    starts.append([lat,lon,math.log(max(np.linalg.norm(obs,axis=1).mean(),0.2)),th])
    best=None
    bounds=([-65,70,-4,-2*math.pi],[65,150,3,2*math.pi])
    for x0 in starts:
        try:
            sol=least_squares(residuals, x0=np.array(x0,float), bounds=bounds, args=(d,times,obs), max_nfev=800, xtol=1e-8, ftol=1e-8, gtol=1e-8)
            rmse=math.sqrt(np.mean(residuals(sol.x,d,times,obs)**2))
            if best is None or rmse<best['rmse']:
                best={'x':sol.x,'rmse':rmse,'cost':sol.cost,'success':sol.success,'nfev':sol.nfev}
        except Exception:
            pass
    return best

def fit_for_date_fast(times, obs, d, seed_params=None):
    starts=[]
    if seed_params is not None:
        starts.append(seed_params)
    meanH=math.log(max(np.linalg.norm(obs,axis=1).mean(),0.2))
    for lat in [-20,15,35,50]:
        for lon in [85,105,120,140]:
            starts.append([lat,lon,meanH,0.0])
    return fit_for_date(times, obs, d, starts=starts)

def date_grid_fit(times, obs, year=2015, step=1):
    rows=[]
    start=date(year,1,1); ndays=365
    seed=None
    # first do coarser 3-day scan, then refine ±3 days around best local basins
    coarse=[]
    for k in range(0,ndays,3):
        d=start+timedelta(days=k)
        b=fit_for_date_fast(times,obs,d,seed)
        if b:
            lat,lon,logH,theta=b['x']; coarse.append({'k':k,'date':d,'rmse':b['rmse'],'x':b['x']})
    top=sorted(coarse,key=lambda r:r['rmse'])[:18]
    days=sorted(set(max(0,min(ndays-1,r['k']+off)) for r in top for off in range(-4,5)))
    for k in days:
        d=start+timedelta(days=k)
        nearest=min(top,key=lambda r:abs(r['k']-k))
        b=fit_for_date_fast(times,obs,d,nearest['x'])
        if b:
            lat,lon,logH,theta=b['x']
            rows.append({'date':d.isoformat(),'doy':day_of_year(d),'lat':lat,'lon':lon,'height':math.exp(logH),'theta_deg':math.degrees(theta),'rmse':b['rmse']})
    df=pd.DataFrame(rows).sort_values('rmse')
    return df

def nonmax_candidates(df, min_day_sep=10, maxn=8):
    cand=[]
    for _,r in df.iterrows():
        doy=int(r['doy'])
        if all(abs(doy-int(c['doy']))>=min_day_sep for c in cand):
            cand.append(r.to_dict())
        if len(cand)>=maxn: break
    return pd.DataFrame(cand)

# q1
q1_times=[time(h, m) for h in range(9,16) for m in ([0,30] if h<15 else [0])]
# for curve every minute
q1_times_dense=[(datetime(2015,10,22,9,0)+timedelta(minutes=i)).time() for i in range(0,361)]
q1_len=[]
for tt in q1_times_dense:
    en=shadow_EN(39+54/60+26/3600, 116+23/60+29/3600, 3.0, datetime.combine(date(2015,10,22), tt))
    q1_len.append(float(np.linalg.norm(en)))
q1_df=pd.DataFrame({'time':[t.strftime('%H:%M') for t in q1_times_dense], 'shadow_length_m':q1_len})
q1_df.to_csv(TAB/'q1_shadow_curve.csv', index=False, encoding='utf-8-sig')
plt.figure(figsize=(9,5))
plt.plot(pd.to_datetime(q1_df['time'],format='%H:%M'), q1_df['shadow_length_m'], lw=2)
plt.xlabel('北京时间'); plt.ylabel('影长 / m'); plt.title('2015-10-22天安门3m直杆影长变化曲线')
plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(FIG/'问题1_天安门影长曲线.png', dpi=300, bbox_inches='tight'); plt.close()
q1_min_i=int(np.argmin(q1_len)); q1_min={'time':q1_df.iloc[q1_min_i]['time'], 'length':q1_len[q1_min_i]}
q1_start=q1_len[0]; q1_end=q1_len[-1]

# load observations
sheets=['附件1','附件2','附件3']
obs_data={s:parse_sheet(s) for s in sheets}

# q2 known date
q2_times,q2_obs=obs_data['附件1']
q2_best=fit_for_date(q2_times,q2_obs,date(2015,4,18))
q2_lat,q2_lon,q2_logH,q2_theta=q2_best['x']
q2_pred=theoretical_xy(q2_best['x'],date(2015,4,18),q2_times)
q2_res=q2_pred-q2_obs
q2_table=pd.DataFrame({'time':[t.strftime('%H:%M:%S') for t in q2_times], 'x_obs':q2_obs[:,0], 'y_obs':q2_obs[:,1], 'x_fit':q2_pred[:,0], 'y_fit':q2_pred[:,1], 'residual_m':np.linalg.norm(q2_res,axis=1)})
q2_table.to_csv(TAB/'q2_fit_trace.csv', index=False, encoding='utf-8-sig')
plt.figure(figsize=(6,6)); plt.plot(q2_obs[:,0],q2_obs[:,1],'o-',label='观测'); plt.plot(q2_pred[:,0],q2_pred[:,1],'s--',label='拟合'); plt.axis('equal'); plt.xlabel('x/m'); plt.ylabel('y/m'); plt.title('附件1影尖轨迹拟合'); plt.legend(); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(FIG/'问题2_附件1轨迹拟合.png', dpi=300, bbox_inches='tight'); plt.close()
plt.figure(figsize=(8,4)); plt.plot([t.strftime('%H:%M') for t in q2_times], q2_table['residual_m'], marker='o'); plt.xticks(rotation=45); plt.ylabel('残差/m'); plt.title('附件1拟合残差序列'); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(FIG/'问题2_附件1残差.png', dpi=300, bbox_inches='tight'); plt.close()
# q2 alternate candidates by perturbing residual threshold? vary date ±1 and lat hemispheres? produce multi starts top date fixed no distinct minima unavailable; create location candidates using bootstrap noise
boot=[]
for i in range(15):
    noise=np.random.normal(scale=max(q2_best['rmse'],0.001), size=q2_obs.shape)
    b=fit_for_date(q2_times,q2_obs+noise,date(2015,4,18), starts=[[q2_lat,q2_lon,q2_logH,q2_theta],[q2_lat+1,q2_lon,q2_logH,q2_theta],[q2_lat-1,q2_lon,q2_logH,q2_theta]])
    if b:
        lat,lon,lh,th=b['x']; boot.append([lat,lon,math.exp(lh),math.degrees(th),b['rmse']])
boot_df=pd.DataFrame(boot,columns=['lat','lon','height','theta_deg','rmse'])
boot_df.to_csv(TAB/'q2_bootstrap_candidates.csv',index=False,encoding='utf-8-sig')

# q3 date-location fits
q3_results={}
for sheet in ['附件2','附件3']:
    times,obs=obs_data[sheet]
    df=date_grid_fit(times, obs, 2015, step=1)
    df.to_csv(TAB/f'{sheet}_date_grid_all.csv', index=False, encoding='utf-8-sig')
    cand=nonmax_candidates(df, min_day_sep=12, maxn=6)
    cand.to_csv(TAB/f'{sheet}_candidate_solutions.csv', index=False, encoding='utf-8-sig')
    bestrow=df.iloc[0]
    # plot date rmse
    plt.figure(figsize=(9,4)); plt.plot(df.sort_values('doy')['doy'], df.sort_values('doy')['rmse']); plt.scatter(cand['doy'],cand['rmse'],c='red',zorder=3); plt.xlabel('2015年日序'); plt.ylabel('RMSE/m'); plt.title(f'{sheet}日期-地点反演残差曲线'); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(FIG/f'问题3_{sheet}_日期搜索残差.png', dpi=300, bbox_inches='tight'); plt.close()
    # fit trace for best
    d=date.fromisoformat(bestrow['date']); params=[bestrow['lat'],bestrow['lon'],math.log(bestrow['height']),math.radians(bestrow['theta_deg'])]
    pred=theoretical_xy(params,d,times); rr=pred-obs
    fitdf=pd.DataFrame({'time':[t.strftime('%H:%M:%S') for t in times], 'x_obs':obs[:,0], 'y_obs':obs[:,1], 'x_fit':pred[:,0], 'y_fit':pred[:,1], 'residual_m':np.linalg.norm(rr,axis=1)})
    fitdf.to_csv(TAB/f'{sheet}_best_fit_trace.csv', index=False, encoding='utf-8-sig')
    plt.figure(figsize=(6,6)); plt.plot(obs[:,0],obs[:,1],'o-',label='观测'); plt.plot(pred[:,0],pred[:,1],'s--',label='拟合'); plt.axis('equal'); plt.xlabel('x/m'); plt.ylabel('y/m'); plt.title(f'{sheet}最佳候选轨迹拟合'); plt.legend(); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(FIG/f'问题3_{sheet}_最佳轨迹拟合.png', dpi=300, bbox_inches='tight'); plt.close()
    q3_results[sheet]={'all':df,'cand':cand,'best':bestrow.to_dict(), 'fit_rmse_series_mean':float(fitdf['residual_m'].mean())}

# sensitivity: q2 date +/- and q3 top neighborhood
sens=[]
for dd in [-2,-1,0,1,2]:
    d=date(2015,4,18)+timedelta(days=dd); b=fit_for_date(q2_times,q2_obs,d, starts=[[q2_lat,q2_lon,q2_logH,q2_theta]])
    lat,lon,lh,th=b['x']; sens.append({'case':'附件1','date_shift':dd,'date':d.isoformat(),'lat':lat,'lon':lon,'height':math.exp(lh),'rmse':b['rmse']})
sensdf=pd.DataFrame(sens); sensdf.to_csv(TAB/'sensitivity_q2_date_shift.csv', index=False, encoding='utf-8-sig')

# summary json
frozen={
 'q1': {'location':'天安门广场','date':'2015-10-22','height_m':3.0,'start_09_length_m':q1_start,'end_15_length_m':q1_end,'min_time':q1_min['time'],'min_length_m':q1_min['length']},
 'q2': {'date':'2015-04-18','lat_deg':q2_lat,'lon_deg':q2_lon,'height_fit_m':math.exp(q2_logH),'rotation_deg':math.degrees(q2_theta),'rmse_m':q2_best['rmse'],'max_residual_m':float(q2_table['residual_m'].max()),'bootstrap_lat_std':float(boot_df['lat'].std()),'bootstrap_lon_std':float(boot_df['lon'].std())},
 'q3': {sheet:{'best_date':res['best']['date'],'lat_deg':res['best']['lat'],'lon_deg':res['best']['lon'],'height_fit_m':res['best']['height'],'rotation_deg':res['best']['theta_deg'],'rmse_m':res['best']['rmse'],'candidates':res['cand'].to_dict(orient='records')} for sheet,res in q3_results.items()},
 'q4': {'video_available':False,'reason':'目录仅有附件4下载说明，自动访问赛题站失败，百度网盘需交互；未伪造视频测量结果。','model':'抽帧-杆底/影尖识别-像素米标定-轨迹反演。已给出可执行流程。'}
}
# round helper for readable copies
def conv(o):
    if isinstance(o,(np.floating,float)): return round(float(o),6)
    if isinstance(o,(np.integer,int)): return int(o)
    if isinstance(o,dict): return {k:conv(v) for k,v in o.items()}
    if isinstance(o,list): return [conv(v) for v in o]
    return o
with open(RES/'frozen_numbers.json','w',encoding='utf-8') as f: json.dump(conv(frozen),f,ensure_ascii=False,indent=2)
with open(CON/'model_results.json','w',encoding='utf-8') as f: json.dump(conv(frozen),f,ensure_ascii=False,indent=2)
metrics={'q2_rmse_m':q2_best['rmse'],'q2_max_residual_m':float(q2_table['residual_m'].max()), 'q3_attachment2_rmse_m':q3_results['附件2']['best']['rmse'], 'q3_attachment3_rmse_m':q3_results['附件3']['best']['rmse']}
with open(CON/'metrics.json','w',encoding='utf-8') as f: json.dump(conv(metrics),f,ensure_ascii=False,indent=2)
# final summary table
rows=[['问题1','最短影长',q1_min['time'],q1_min['length']],['问题2','附件1地点',f"{q2_lat:.4f}N,{q2_lon:.4f}E",q2_best['rmse']]]
for sh,res in q3_results.items(): rows.append(['问题3',sh,f"{res['best']['date']} {res['best']['lat']:.4f}N,{res['best']['lon']:.4f}E",res['best']['rmse']])
pd.DataFrame(rows,columns=['problem','item','result','metric']).to_csv(TAB/'final_results_summary.csv',index=False,encoding='utf-8-sig')
print(json.dumps(conv(frozen),ensure_ascii=False,indent=2))
