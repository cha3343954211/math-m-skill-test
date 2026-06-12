# -*- coding: utf-8 -*-
"""CUMCM 2015C 月上柳梢头：天文位置模型、2016城市判定、图表与冻结数字生成。"""
from __future__ import annotations
import json, math
from pathlib import Path
from datetime import datetime, timedelta, timezone, date
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib import font_manager
from skyfield.api import load, wgs84
from lunardate import LunarDate

ROOT = Path(r"<LOCAL_MATH_MODELING_TEST_ROOT>/2015年赛题/2015C")
SUP = ROOT / "支撑材料"; FIG = SUP/"results/figures"; TAB=SUP/"tables"; CON=SUP/"contracts"; DATA=SUP/"data"
for p in [FIG,TAB,CON, SUP/'papper', SUP/'code'] + [SUP/f'quest{i}/outputs' for i in range(1,5)]: p.mkdir(parents=True, exist_ok=True)
for fp in [r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/simhei.ttf", r"C:/Windows/Fonts/simsun.ttc"]:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp); plt.rcParams['font.sans-serif']=[font_manager.FontProperties(fname=fp).get_name(),'DejaVu Sans']; break
plt.rcParams['axes.unicode_minus']=False

ts=load.timescale(); eph=load('de421.bsp'); earth,sun,moon=eph['earth'],eph['sun'],eph['moon']; CST=timezone(timedelta(hours=8))
CITIES={'北京':(39.9042,116.4074),'哈尔滨':(45.8038,126.5349),'上海':(31.2304,121.4737),'广州':(23.1291,113.2644),'昆明':(25.0389,102.7183),'成都':(30.5728,104.0668),'乌鲁木齐':(43.8256,87.6168)}
PARAMS={'willow_alt_low':8.0,'willow_alt_high':15.0,'dusk_sun_low':-12.0,'dusk_sun_high':-6.0,'illum_min':0.80}

def make_times(d:date, step_min=1):
    start=datetime(d.year,d.month,d.day,15,0,tzinfo=CST); n=int(10*60/step_min)+1
    dts=[start+timedelta(minutes=i*step_min) for i in range(n)]
    utc=[x.astimezone(timezone.utc) for x in dts]
    t=ts.utc([u.year for u in utc],[u.month for u in utc],[u.day for u in utc],[u.hour for u in utc],[u.minute for u in utc],[u.second for u in utc])
    return dts,t

def scan_day(city,d,step_min=1,params=PARAMS):
    dts,t=make_times(d,step_min); lat,lon=CITIES[city]; loc=earth+wgs84.latlon(lat,lon)
    obs=loc.at(t)
    sun_alt=obs.observe(sun).apparent().altaz()[0].degrees
    mapp=obs.observe(moon).apparent(); moon_alt,moon_az,_=mapp.altaz()
    phase=mapp.phase_angle(sun).degrees; illum=(1+np.cos(np.radians(phase)))/2
    df=pd.DataFrame({'datetime':dts,'sun_alt':sun_alt,'moon_alt':moon_alt.degrees,'moon_az':moon_az.degrees,'illum':illum})
    df['match']=(df.sun_alt.between(params['dusk_sun_low'],params['dusk_sun_high']) & df.moon_alt.between(params['willow_alt_low'],params['willow_alt_high']) & (df.illum>=params['illum_min']))
    return df

def summarize_matches(city, dates, params=PARAMS):
    all_rows=[]; intervals=[]
    for d in dates:
        df=scan_day(city,d,1,params); df['city']=city; df['date']=d.isoformat(); all_rows.append(df)
        idx=np.flatnonzero(df['match'].to_numpy())
        if len(idx):
            for g in np.split(idx, np.where(np.diff(idx)>1)[0]+1):
                seg=df.iloc[g]; mid=seg.iloc[len(seg)//2]
                intervals.append({'城市':city,'日期':d.isoformat(),'开始时间':seg.iloc[0].datetime.strftime('%H:%M'),'结束时间':seg.iloc[-1].datetime.strftime('%H:%M'),'代表时间':mid.datetime.strftime('%H:%M'),'太阳高度角(°)':round(float(mid.sun_alt),2),'月亮高度角(°)':round(float(mid.moon_alt),2),'月亮方位角(°)':round(float(mid.moon_az),2),'月面照明比例':round(float(mid.illum),3),'持续分钟':int((seg.iloc[-1].datetime-seg.iloc[0].datetime).total_seconds()/60)+1})
    return pd.concat(all_rows,ignore_index=True), pd.DataFrame(intervals)

def lunar_date(y,m,d): return LunarDate(y,m,d).toSolarDate()
def date_window(center,days=3): return [center+timedelta(days=i) for i in range(-days,days+1)]

def choose(ints, center):
    out=[]
    for city,g in ints.groupby('城市'):
        gg=g.copy(); gg['距正月十五天数']=gg['日期'].map(lambda s: abs((date.fromisoformat(s)-center).days)); gg=gg.sort_values(['距正月十五天数','持续分钟'],ascending=[True,False]); out.append(gg.iloc[0])
    return pd.DataFrame(out).drop(columns=['距正月十五天数']).sort_values('城市') if out else pd.DataFrame()

center2015=lunar_date(2015,1,15); center2016=lunar_date(2016,1,15)
rows2015,int2015=summarize_matches('北京',date_window(center2015,3)); rows2016bj,int2016bj=summarize_matches('北京',date_window(center2016,3))
city_rows=[]; city_int=[]
for c in CITIES:
    r,i=summarize_matches(c,date_window(center2016,3)); city_rows.append(r); city_int.append(i)
city_rows=pd.concat(city_rows,ignore_index=True); city_intervals=pd.concat(city_int,ignore_index=True); chosen=choose(city_intervals,center2016)
# baseline
baseline=[]
for city in CITIES:
    for d in date_window(center2016,1):
        df=scan_day(city,d,5); r=df.loc[(df.sun_alt+6).abs().idxmin()]
        baseline.append({'城市':city,'日期':d.isoformat(),'基准时间(太阳-6°)':r.datetime.strftime('%H:%M'),'月亮高度角(°)':round(float(r.moon_alt),2),'是否在8-15°':bool(8<=r.moon_alt<=15)})
baseline=pd.DataFrame(baseline)
# sensitivity with coarser scan for speed
sens=[]
def count_for_params(p):
    ints=[]
    for city in CITIES:
        _,it=summarize_matches(city,date_window(center2016,3),p)
        if not it.empty: ints.append(it)
    if not ints: return 0,0
    x=pd.concat(ints); return int(x['城市'].nunique()), float(x.groupby('城市')['持续分钟'].max().mean())
for delta in [-2,-1,0,1,2]:
    p=PARAMS.copy(); p['willow_alt_low']=8+delta; p['willow_alt_high']=15+delta; c,avg=count_for_params(p); sens.append({'扰动参数':'月亮高度角整体平移','扰动值':delta,'可发生城市数':c,'平均最长持续分钟':round(avg,1)})
for delta in [-2,-1,0,1,2]:
    p=PARAMS.copy(); p['dusk_sun_low']=-12+delta; p['dusk_sun_high']=-6+delta; c,avg=count_for_params(p); sens.append({'扰动参数':'黄昏太阳高度角整体平移','扰动值':delta,'可发生城市数':c,'平均最长持续分钟':round(avg,1)})
sens=pd.DataFrame(sens)
# save
for name,df in [('beijing_2015_scan.csv',rows2015),('beijing_2015_intervals.csv',int2015),('beijing_2016_scan.csv',rows2016bj),('beijing_2016_intervals.csv',int2016bj),('city_2016_scan.csv',city_rows),('city_2016_all_intervals.csv',city_intervals),('city_2016_chosen_results.csv',chosen),('baseline_lunar15_sunset.csv',baseline),('sensitivity_results.csv',sens)]: df.to_csv(TAB/name,index=False,encoding='utf-8-sig')
# figures
fig,ax=plt.subplots(figsize=(10,5.5)); df=scan_day('北京',center2016,2); xs=df.datetime.dt.strftime('%H:%M')
ax.plot(xs,df.sun_alt,label='太阳高度角',color='#f39c12'); ax.plot(xs,df.moon_alt,label='月亮高度角',color='#2e86de'); ax.axhspan(-12,-6,color='#f39c12',alpha=.12,label='黄昏后判定区间'); ax.axhspan(8,15,color='#2e86de',alpha=.10,label='月上柳梢头高度区间')
ids=np.linspace(0,len(df)-1,9,dtype=int); ax.set_xticks(ids); ax.set_xticklabels(xs.iloc[ids]); ax.set_ylabel('高度角 / °'); ax.set_title('北京2016正月十五太阳与月亮高度角变化'); ax.legend(ncol=2); ax.grid(alpha=.25); plt.tight_layout(); plt.savefig(FIG/'fig1_beijing_2016_altitude.png',dpi=300,bbox_inches='tight'); plt.close()
fig,ax=plt.subplots(figsize=(10,5.8)); plot_df=chosen.sort_values('持续分钟',ascending=False); ax.bar(plot_df['城市'],plot_df['持续分钟'],color='#5470c6')
for i,r in enumerate(plot_df.itertuples()): ax.text(i,r.持续分钟+1,f"{r.代表时间}\n{r.日期[5:]}",ha='center',va='bottom',fontsize=9)
ax.set_ylabel('满足情景持续时间 / 分钟'); ax.set_title('2016年各城市代表窗口'); ax.grid(axis='y',alpha=.25); plt.tight_layout(); plt.savefig(FIG/'fig2_city_windows.png',dpi=300,bbox_inches='tight'); plt.close()
fig,ax=plt.subplots(figsize=(10,5.5)); bg=baseline[baseline['日期']==center2016.isoformat()].sort_values('城市'); ax.bar(bg['城市'],bg['月亮高度角(°)'],color=['#91cc75' if x else '#ee6666' for x in bg['是否在8-15°']]); ax.axhspan(8,15,color='#5470c6',alpha=.12,label='目标高度区间'); ax.set_ylabel('太阳-6°时月亮高度角 / °'); ax.set_title('基线：正月十五民用暮光结束时月亮高度'); ax.legend(); ax.grid(axis='y',alpha=.25); plt.tight_layout(); plt.savefig(FIG/'fig3_baseline_compare.png',dpi=300,bbox_inches='tight'); plt.close()
fig,ax=plt.subplots(figsize=(9,5.2));
for key,g in sens.groupby('扰动参数'): ax.plot(g['扰动值'],g['平均最长持续分钟'],marker='o',label=key)
ax.set_xlabel('角度阈值扰动 / °'); ax.set_ylabel('平均最长持续时间 / 分钟'); ax.set_title('关键角度阈值敏感性分析'); ax.grid(alpha=.25); ax.legend(); plt.tight_layout(); plt.savefig(FIG/'fig4_sensitivity.png',dpi=300,bbox_inches='tight'); plt.close()
# json contracts
frozen={'model_parameters':PARAMS,'beijing_2015_lantern_festival':center2015.isoformat(),'beijing_2015_best_interval':int2015.to_dict('records'),'beijing_2016_lantern_festival':center2016.isoformat(),'beijing_2016_intervals':int2016bj.to_dict('records'),'city_2016_chosen_results':chosen.to_dict('records'),'baseline_summary':{'cities_pass_at_sun_minus6_on_lunar15':int(bg['是否在8-15°'].sum()),'total_cities':len(bg)},'sensitivity':sens.to_dict('records'),'data_audit':{'source':'题目无附件；使用Skyfield de421.bsp星历和城市经纬度进行可复现实算','scan_step_minutes':1,'date_window':'农历正月十五前后3天','timezone':'北京时间 UTC+8','random_seed':'无随机主模型；敏感性为确定性扰动'}}
(CON/'frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
(CON/'problem_analysis.json').write_text(json.dumps({'题目':'2015C 月上柳梢头','子问题':[{'id':'Q1','要求':'定义月上柳梢头和黄昏后，建立天文模型并验证','输出':'角度阈值、时间阈值、北京2015元宵验证窗口'},{'id':'Q2','要求':'分析2016北京发生日期时间','输出':'北京2016代表日期、开始/结束/代表时间'},{'id':'Q3','要求':'判断六城市是否发生并给日期时间/原因','输出':'哈尔滨、上海、广州、昆明、成都、乌鲁木齐代表窗口'},{'id':'Q4','要求':'模型合理性检验','输出':'baseline对比、星历验证、敏感性分析'}]},ensure_ascii=False,indent=2),encoding='utf-8')
(CON/'model_route.json').write_text(json.dumps({'baseline':'农历正月十五附近 + 民用暮光结束时月亮高度是否落入8-15度','main_model':'Skyfield星历计算太阳/月亮地平坐标，逐分钟扫描黄昏太阳高度[-12,-6]与月亮高度[8,15]交集','validation':['北京2015元宵附近回代','baseline对比','阈值敏感性分析','城市经度导致本地代表时间差异解释']},ensure_ascii=False,indent=2),encoding='utf-8')
(SUP/'readme.txt').write_text(f"""# 2015C 月上柳梢头 支撑材料\n\n## 复现\npython 支撑材料/code/main_modeling.py\n\n## 文件\n- papper/: 论文源文件和PDF\n- code/main_modeling.py: 主模型脚本\n- tables/: 最终结果表\n- results/figures/: 图表\n- contracts/frozen_numbers.json: 冻结数字\n- data/problem_statement.txt: 题面文本\n\n核心结果详见 tables/city_2016_chosen_results.csv。\n""",encoding='utf-8')
print('DONE')
print('2015',center2015); print(int2015.to_string(index=False))
print('2016 chosen'); print(chosen.to_string(index=False))
print('baseline pass', frozen['baseline_summary'])
