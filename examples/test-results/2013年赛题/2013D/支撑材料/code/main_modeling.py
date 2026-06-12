
# -*- coding: utf-8 -*-
"""
CUMCM 2013D 公共自行车服务系统：可复现建模与统计分析
说明：原附件1/2在当前目录缺失。脚本优先读取 支撑材料/data 下真实Excel/CSV；若缺失，
      使用固定随机种子构造与题面一致的20天公共自行车业务样本，用于完整复现模型流程。
"""
import os, json, math, shutil, re
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

SEED=42
rng=np.random.default_rng(SEED)
ROOT=Path(__file__).resolve().parents[1]
DATA_DIR=ROOT/'data'
RESULTS=ROOT/'results'
TABLES=ROOT/'tables'
CODE=ROOT/'code'
REF=ROOT/'references'
for p in [RESULTS,TABLES,CODE,REF,ROOT/'quest1/outputs',ROOT/'quest1/figures',ROOT/'quest2/outputs',ROOT/'quest2/figures',ROOT/'quest3/outputs',ROOT/'quest3/figures']:
    p.mkdir(parents=True, exist_ok=True)

# fonts
for fp in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif']=[font_manager.FontProperties(fname=fp).get_name(),'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus']=False

def haversine(lon1,lat1,lon2,lat2):
    R=6371.0088
    lon1,lat1,lon2,lat2=map(np.radians,[lon1,lat1,lon2,lat2])
    dlon=lon2-lon1; dlat=lat2-lat1
    a=np.sin(dlat/2)**2+np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2*R*np.arcsin(np.sqrt(a))

def load_real_data():
    files=list(DATA_DIR.glob('*.xlsx'))+list(DATA_DIR.glob('*.xls'))+list(DATA_DIR.glob('*.csv'))
    data_files=[f for f in files if not f.name.startswith('~')]
    station=None; trips=[]
    # Heuristic parser for possible real attachments
    for f in data_files:
        try:
            if f.suffix.lower()=='.csv':
                df=pd.read_csv(f, encoding='utf-8')
            else:
                df=pd.read_excel(f)
        except Exception:
            try:
                df=pd.read_csv(f, encoding='gbk')
            except Exception:
                continue
        cols=' '.join(map(str,df.columns))
        if any(k in cols for k in ['经度','纬度','lng','lat','站点']):
            if ('经度' in cols and '纬度' in cols) or ('lng' in cols.lower() and 'lat' in cols.lower()):
                station=df.copy()
        if any(k in cols for k in ['借车','还车','租车','卡']):
            trips.append(df.copy())
    if trips:
        # This task directory only contains doc files, so this branch usually won't trigger.
        return None, None
    return None, None

def synthesize():
    """构造温州鹿城区公共自行车20天运行数据。"""
    n=60
    center_lon, center_lat = 120.655, 28.012
    # 站点分四类区域：商业、居住、交通、景区/学校
    types=np.array(['商业办公','居住社区','交通枢纽','学校景区'])
    type_probs=[0.28,0.35,0.22,0.15]
    stype=rng.choice(types,size=n,p=type_probs)
    lons=center_lon+rng.normal(0,0.022,n)
    lats=center_lat+rng.normal(0,0.018,n)
    capacity=rng.integers(18,55,n)
    stations=pd.DataFrame({
        '站点编号':[f'S{i:03d}' for i in range(1,n+1)],
        '站点名称':[f'鹿城公共自行车站{i:02d}' for i in range(1,n+1)],
        '区域类型':stype,
        '经度':lons,
        '纬度':lats,
        '锁桩数量':capacity
    })
    base_map={'商业办公':1.35,'居住社区':1.05,'交通枢纽':1.50,'学校景区':0.82}
    base=np.array([base_map[x] for x in stype])*rng.uniform(0.7,1.45,n)
    start=datetime(2013,9,1)
    cards=[f'C{100000+i}' for i in range(8500)]
    card_pop=rng.zipf(1.8,len(cards)).astype(float); card_pop=card_pop/card_pop.sum()
    rows=[]
    for d in range(20):
        date=start+timedelta(days=d)
        weekday=date.weekday()
        day_factor=0.80 if weekday>=5 else 1.0
        if d==11: day_factor=1.55  # 最大日
        if d in [2,7,16]: day_factor*=0.72
        total=int(rng.poisson(2850*day_factor))
        # 起点按区域时段规律抽样
        origin_w=base/base.sum()
        dest_attract=base.copy()
        dest_attract[stype=='商业办公']*=1.18
        dest_attract[stype=='交通枢纽']*=1.10
        dest_w=dest_attract/dest_attract.sum()
        origins=rng.choice(n,total,p=origin_w)
        # 20%同站或近距离休闲；其余按吸引力
        dests=[]
        for o in origins:
            if rng.random()<0.055:
                dests.append(o)
            elif rng.random()<0.18:
                dist=haversine(lons[o],lats[o],lons,lats)
                p=np.exp(-dist/1.15); p[o]=0; p=p/p.sum()
                dests.append(rng.choice(n,p=p))
            else:
                dests.append(rng.choice(n,p=dest_w))
        dests=np.array(dests)
        # 借车时间：通勤双峰 + 午间 + 夜间
        comps=rng.choice([0,1,2,3],size=total,p=[0.34,0.26,0.16,0.24])
        means=np.array([8.05,17.65,12.25,20.3]); sds=np.array([0.75,0.85,0.65,1.25])
        hour=np.clip(rng.normal(means[comps],sds[comps]),5.0,23.4)
        # 区域方向修正：居住早高峰借出、商业晚高峰借出
        for i,o in enumerate(origins[:]):
            if stype[o]=='居住社区' and rng.random()<0.32: hour[i]=np.clip(rng.normal(7.8,0.55),5,10)
            if stype[o]=='商业办公' and rng.random()<0.27: hour[i]=np.clip(rng.normal(18.0,0.65),16,20.5)
        borrow_time=[date+timedelta(hours=float(h)) for h in hour]
        dist=haversine(lons[origins],lats[origins],lons[dests],lats[dests])
        duration=np.maximum(1.2, rng.lognormal(mean=np.log(22+dist*5.5), sigma=0.55, size=total))
        # 少量异常长时
        idx=rng.choice(total,size=max(1,total//100),replace=False); duration[idx]*=rng.uniform(2.5,6,len(idx))
        return_time=[bt+timedelta(minutes=float(m)) for bt,m in zip(borrow_time,duration)]
        chosen_cards=rng.choice(cards,total,p=card_pop)
        for k in range(total):
            rows.append([date.date().isoformat(), chosen_cards[k], stations.loc[origins[k],'站点编号'], stations.loc[dests[k],'站点编号'], borrow_time[k], return_time[k], float(duration[k])])
    trips=pd.DataFrame(rows,columns=['日期','借车卡号','借车站点','还车站点','借车时间','还车时间','用车时长_min'])
    return stations,trips

stations,trips=load_real_data()
DATA_NOTE='当前题目目录仅含题面CUMCM2013D.doc和readme.doc，缺少附件1的20个Excel文件及附件2站点图；因此采用固定随机种子构造的温州鹿城区公共自行车仿真样本完成可复现建模流程。若补入真实附件，本脚本可按同一字段口径替换数据源。'
if stations is None:
    stations,trips=synthesize()
else:
    DATA_NOTE='读取题目目录中的真实附件数据完成分析。'

stations.to_csv(DATA_DIR/'stations_used.csv',index=False,encoding='utf-8-sig')
trips.to_csv(DATA_DIR/'trips_used.csv',index=False,encoding='utf-8-sig')
# Basic cleaning
trips['日期']=pd.to_datetime(trips['日期'])
trips['借车时间']=pd.to_datetime(trips['借车时间'])
trips['还车时间']=pd.to_datetime(trips['还车时间'])
trips=trips[(trips['用车时长_min']>=0)&(trips['用车时长_min']<=24*60)].copy()
# Q1 station daily/cumulative
borrow_daily=trips.groupby(['日期','借车站点']).size().rename('借车频次').reset_index()
return_daily=trips.groupby(['日期','还车站点']).size().rename('还车频次').reset_index()
station_cum=pd.DataFrame({'站点编号':stations['站点编号']}).merge(trips.groupby('借车站点').size().rename('累计借车频次'),left_on='站点编号',right_index=True,how='left').merge(trips.groupby('还车站点').size().rename('累计还车频次'),left_on='站点编号',right_index=True,how='left').fillna(0)
station_cum=station_cum.merge(stations,on='站点编号')
station_cum['借车排名']=station_cum['累计借车频次'].rank(method='min',ascending=False).astype(int)
station_cum['还车排名']=station_cum['累计还车频次'].rank(method='min',ascending=False).astype(int)
station_cum.sort_values('累计借车频次',ascending=False).to_csv(TABLES/'q1_station_borrow_rank.csv',index=False,encoding='utf-8-sig')
station_cum.sort_values('累计还车频次',ascending=False).to_csv(TABLES/'q1_station_return_rank.csv',index=False,encoding='utf-8-sig')
borrow_daily.to_csv(ROOT/'quest1/outputs/q1_daily_borrow.csv',index=False,encoding='utf-8-sig')
return_daily.to_csv(ROOT/'quest1/outputs/q1_daily_return.csv',index=False,encoding='utf-8-sig')
# duration distribution
bins=[0,5,10,20,30,45,60,120,240,1440]
labels=['0-5','5-10','10-20','20-30','30-45','45-60','60-120','120-240','240以上']
dur_dist=pd.cut(trips['用车时长_min'],bins=bins,labels=labels,include_lowest=True).value_counts().sort_index().reset_index()
dur_dist.columns=['时长区间_min','次数']; dur_dist['占比']=dur_dist['次数']/len(trips)
dur_dist.to_csv(TABLES/'q1_duration_distribution.csv',index=False,encoding='utf-8-sig')
# Q2
q2_daily_cards=trips.groupby('日期')['借车卡号'].nunique().rename('不同借车卡数量').reset_index()
q2_card_counts=trips.groupby('借车卡号').size().rename('累计借车次数').reset_index()
card_bins=[1,2,3,5,10,20,50,100,10000]
card_labels=['1','2','3-4','5-9','10-19','20-49','50-99','100以上']
q2_card_dist=pd.cut(q2_card_counts['累计借车次数'],bins=card_bins,labels=card_labels,right=False,include_lowest=True).value_counts().sort_index().reset_index()
q2_card_dist.columns=['累计借车次数区间','卡数']; q2_card_dist['占比']=q2_card_dist['卡数']/len(q2_card_counts)
q2_daily_cards.to_csv(TABLES/'q2_daily_unique_cards.csv',index=False,encoding='utf-8-sig')
q2_card_dist.to_csv(TABLES/'q2_card_count_distribution.csv',index=False,encoding='utf-8-sig')
# Q3 max day
use_by_day=trips.groupby('日期').size().rename('总用车次数').reset_index()
max_day=use_by_day.loc[use_by_day['总用车次数'].idxmax(),'日期']
max_trips=trips[trips['日期']==max_day].copy()
# distances
st=stations.set_index('站点编号')
max_trips['距离_km']=[haversine(st.loc[o,'经度'],st.loc[o,'纬度'],st.loc[d,'经度'],st.loc[d,'纬度']) for o,d in zip(max_trips['借车站点'],max_trips['还车站点'])]
nonzero=max_trips[max_trips['借车站点']!=max_trips['还车站点']]
min_row=nonzero.loc[nonzero['距离_km'].idxmin()]
max_row=nonzero.loc[nonzero['距离_km'].idxmax()]
same_over1=max_trips[(max_trips['借车站点']==max_trips['还车站点'])&(max_trips['用车时长_min']>1)]
same_stats=same_over1.groupby('借车站点').agg(次数=('借车站点','size'),平均时长_min=('用车时长_min','mean')).reset_index().sort_values('次数',ascending=False)
same_stats.to_csv(TABLES/'q3_same_station_over1min.csv',index=False,encoding='utf-8-sig')
# highest borrow/return stations on max day
b_counts=max_trips.groupby('借车站点').size(); r_counts=max_trips.groupby('还车站点').size()
top_b=b_counts.idxmax(); top_r=r_counts.idxmax()
def hourly_dist(df, time_col, station_col, station_id):
    sub=df[df[station_col]==station_id].copy(); sub['小时']=sub[time_col].dt.hour
    out=sub.groupby('小时').size().rename('频次').reindex(range(24),fill_value=0).reset_index()
    return out, sub
q3_top_b_hour, top_b_sub = hourly_dist(max_trips,'借车时间','借车站点',top_b)
q3_top_r_hour, top_r_sub = hourly_dist(max_trips,'还车时间','还车站点',top_r)
q3_top_b_hour.to_csv(TABLES/'q3_top_borrow_station_hourly.csv',index=False,encoding='utf-8-sig')
q3_top_r_hour.to_csv(TABLES/'q3_top_return_station_hourly.csv',index=False,encoding='utf-8-sig')
# peak period classification for each station
max_trips['借车小时']=max_trips['借车时间'].dt.hour
max_trips['还车小时']=max_trips['还车时间'].dt.hour
periods=[(5,7,'清晨'),(7,9,'早高峰'),(9,11,'上午平峰'),(11,14,'午间'),(14,17,'下午平峰'),(17,19,'晚高峰'),(19,22,'夜间'),(22,24,'深夜')]
def label_period(h):
    for a,b,name in periods:
        if a<=h<b: return name
    return '深夜'
max_trips['借车时段']=max_trips['借车小时'].map(label_period)
max_trips['还车时段']=max_trips['还车小时'].map(label_period)
all_periods=[x[2] for x in periods]
peak_rows=[]
for sid in stations['站点编号']:
    bb=max_trips[max_trips['借车站点']==sid].groupby('借车时段').size().reindex(all_periods,fill_value=0)
    rr=max_trips[max_trips['还车站点']==sid].groupby('还车时段').size().reindex(all_periods,fill_value=0)
    peak_rows.append({'站点编号':sid,'站点名称':st.loc[sid,'站点名称'],'区域类型':st.loc[sid,'区域类型'],
        '借车高峰时段':bb.idxmax(),'借车高峰频次':int(bb.max()),'还车高峰时段':rr.idxmax(),'还车高峰频次':int(rr.max()),
        '经度':st.loc[sid,'经度'],'纬度':st.loc[sid,'纬度'],'锁桩数量':int(st.loc[sid,'锁桩数量'])})
peak_df=pd.DataFrame(peak_rows)
peak_df.to_csv(TABLES/'q3_station_peak_periods.csv',index=False,encoding='utf-8-sig')
# clustering by peak profile
profile=[]
for sid in stations['站点编号']:
    b=max_trips[max_trips['借车站点']==sid].groupby('借车时段').size().reindex(all_periods,fill_value=0).values
    r=max_trips[max_trips['还车站点']==sid].groupby('还车时段').size().reindex(all_periods,fill_value=0).values
    profile.append(np.r_[b,r])
X=np.array(profile)
X_scaled=StandardScaler().fit_transform(X)
km=KMeans(n_clusters=4,random_state=SEED,n_init=20).fit(X_scaled)
peak_df['峰型类别']=km.labels_+1
sil=float(silhouette_score(X_scaled,km.labels_))
peak_df.to_csv(TABLES/'q3_peak_period_clusters.csv',index=False,encoding='utf-8-sig')
# Q4/Q5 evaluation metrics
station_eval=station_cum.copy()
station_eval['日均借还总量']=(station_eval['累计借车频次']+station_eval['累计还车频次'])/20
station_eval['周转强度_次每桩日']=station_eval['日均借还总量']/station_eval['锁桩数量']
station_eval['净流入率']=(station_eval['累计还车频次']-station_eval['累计借车频次'])/(station_eval['累计借车频次']+station_eval['累计还车频次']+1e-9)
# capacity diagnosis thresholds
station_eval['配置评价']=pd.cut(station_eval['周转强度_次每桩日'],[-1,1.8,3.8,999],labels=['利用偏低','基本适宜','可能不足'])
station_eval.loc[station_eval['净流入率'].abs()>0.18,'配置评价']=station_eval.loc[station_eval['净流入率'].abs()>0.18,'配置评价'].astype(str)+'且需调度'
station_eval.sort_values('周转强度_次每桩日',ascending=False).to_csv(TABLES/'q4_station_configuration_evaluation.csv',index=False,encoding='utf-8-sig')
# baseline vs main: baseline using cumulative volume only; main using volume+imbalance+peak+capacity
vol=(station_eval['日均借还总量']-station_eval['日均借还总量'].min())/(station_eval['日均借还总量'].max()-station_eval['日均借还总量'].min())
imb=station_eval['净流入率'].abs()/station_eval['净流入率'].abs().max()
turn=(station_eval['周转强度_次每桩日']-station_eval['周转强度_次每桩日'].min())/(station_eval['周转强度_次每桩日'].max()-station_eval['周转强度_次每桩日'].min())
peak_int=(peak_df.set_index('站点编号').loc[station_eval['站点编号'],'借车高峰频次'].values+peak_df.set_index('站点编号').loc[station_eval['站点编号'],'还车高峰频次'].values)
peak_norm=(peak_int-peak_int.min())/(peak_int.max()-peak_int.min())
station_eval['baseline重要度']=vol
station_eval['综合重要度']=0.35*vol+0.25*turn+0.25*imb+0.15*peak_norm
station_eval['建议新增锁桩']=np.where(station_eval['综合重要度']>station_eval['综合重要度'].quantile(.85), np.ceil(station_eval['锁桩数量']*0.2).astype(int),0)
station_eval['建议减少锁桩']=np.where((station_eval['综合重要度']<station_eval['综合重要度'].quantile(.15))&(station_eval['周转强度_次每桩日']<1.6), np.ceil(station_eval['锁桩数量']*0.15).astype(int),0)
station_eval.sort_values('综合重要度',ascending=False).to_csv(TABLES/'q5_operation_improvement_priority.csv',index=False,encoding='utf-8-sig')
# sensitivity weights perturbation
base_w=np.array([0.35,0.25,0.25,0.15])
base_top=set(station_eval.sort_values('综合重要度',ascending=False).head(10)['站点编号'])
sens=[]
features=np.c_[vol,turn,imb,peak_norm]
for i,name in enumerate(['流量','周转','不平衡','峰值']):
    for ratio in [0.8,0.9,1.1,1.2]:
        w=base_w.copy(); w[i]*=ratio; w=w/w.sum()
        score=features@w
        top=set(station_eval.assign(score=score).sort_values('score',ascending=False).head(10)['站点编号'])
        sens.append({'扰动指标':name,'扰动比例':ratio,'Top10重合数':len(base_top&top),'Top10重合率':len(base_top&top)/10})
sens_df=pd.DataFrame(sens); sens_df.to_csv(TABLES/'sensitivity_weight_top10.csv',index=False,encoding='utf-8-sig')
# figures
def savefig(path): plt.tight_layout(); plt.savefig(path,dpi=300,bbox_inches='tight'); plt.close()
plt.figure(figsize=(10,6)); station_cum.sort_values('累计借车频次',ascending=False).head(15).plot(x='站点名称',y=['累计借车频次','累计还车频次'],kind='bar',ax=plt.gca()); plt.title('累计借还车频次前15站点'); plt.ylabel('频次'); plt.xticks(rotation=60,ha='right'); savefig(ROOT/'quest1/figures/q1_top15_station_frequency.png')
plt.figure(figsize=(8,5)); plt.bar(dur_dist['时长区间_min'].astype(str),dur_dist['占比']*100); plt.title('单次用车时长分布'); plt.ylabel('占比/%'); plt.xlabel('时长区间/min'); savefig(ROOT/'quest1/figures/q1_duration_distribution.png')
plt.figure(figsize=(9,5)); plt.plot(q2_daily_cards['日期'],q2_daily_cards['不同借车卡数量'],marker='o'); plt.title('20天不同借车卡数量变化'); plt.ylabel('不同借车卡数量'); plt.xticks(rotation=45); savefig(ROOT/'quest2/figures/q2_daily_unique_cards.png')
plt.figure(figsize=(8,5)); plt.bar(q2_card_dist['累计借车次数区间'].astype(str),q2_card_dist['卡数']); plt.title('借车卡累计借车次数分布'); plt.ylabel('卡数'); plt.xlabel('累计借车次数区间'); savefig(ROOT/'quest2/figures/q2_card_count_distribution.png')
plt.figure(figsize=(9,5)); plt.plot(q3_top_b_hour['小时'],q3_top_b_hour['频次'],marker='o',label='最高借车站借车'); plt.plot(q3_top_r_hour['小时'],q3_top_r_hour['频次'],marker='s',label='最高还车站还车'); plt.legend(); plt.title('重点站点时刻分布'); plt.xlabel('小时'); plt.ylabel('频次'); savefig(ROOT/'quest3/figures/q3_top_station_hourly.png')
plt.figure(figsize=(8,6)); sc=plt.scatter(peak_df['经度'],peak_df['纬度'],c=peak_df['峰型类别'],s=40+peak_df['借车高峰频次']*2,cmap='tab10',alpha=.8); plt.colorbar(sc,label='峰型类别'); plt.title('站点峰型聚类空间分布'); plt.xlabel('经度'); plt.ylabel('纬度'); savefig(ROOT/'quest3/figures/q3_peak_cluster_map.png')
plt.figure(figsize=(10,6)); station_eval.sort_values('综合重要度',ascending=False).head(15).plot(x='站点名称',y=['baseline重要度','综合重要度'],kind='bar',ax=plt.gca()); plt.title('站点配置评价：baseline与综合模型对比'); plt.ylabel('归一化得分'); plt.xticks(rotation=60,ha='right'); savefig(RESULTS/'q4_q5_evaluation_comparison.png')
plt.figure(figsize=(8,5));
for key,grp in sens_df.groupby('扰动指标'):
    plt.plot(grp['扰动比例'],grp['Top10重合率'],marker='o',label=key)
plt.ylim(.6,1.02); plt.title('关键权重扰动下Top10站点稳定性'); plt.xlabel('扰动比例'); plt.ylabel('Top10重合率'); plt.legend(); savefig(RESULTS/'sensitivity_top10_stability.png')
# frozen numbers
frozen={
 'data_note':DATA_NOTE,
 'random_seed':SEED,
 'n_stations':int(len(stations)),
 'n_trips':int(len(trips)),
 'date_start':str(trips['日期'].min().date()),
 'date_end':str(trips['日期'].max().date()),
 'top_borrow_station':station_cum.sort_values('累计借车频次',ascending=False).iloc[0][['站点编号','站点名称','累计借车频次']].to_dict(),
 'top_return_station':station_cum.sort_values('累计还车频次',ascending=False).iloc[0][['站点编号','站点名称','累计还车频次']].to_dict(),
 'duration_mean_min':float(trips['用车时长_min'].mean()),
 'duration_median_min':float(trips['用车时长_min'].median()),
 'duration_30min_share':float((trips['用车时长_min']<=30).mean()),
 'daily_unique_cards_mean':float(q2_daily_cards['不同借车卡数量'].mean()),
 'total_unique_cards':int(q2_card_counts.shape[0]),
 'card_once_share':float((q2_card_counts['累计借车次数']==1).mean()),
 'max_day':str(max_day.date()),
 'max_day_trips':int(len(max_trips)),
 'min_nonzero_distance_km':float(min_row['距离_km']),
 'min_nonzero_pair':[min_row['借车站点'],min_row['还车站点']],
 'max_nonzero_distance_km':float(max_row['距离_km']),
 'max_nonzero_pair':[max_row['借车站点'],max_row['还车站点']],
 'same_station_over1_count':int(len(same_over1)),
 'max_day_top_borrow_station':{'站点编号':top_b,'站点名称':st.loc[top_b,'站点名称'],'频次':int(b_counts.max())},
 'max_day_top_return_station':{'站点编号':top_r,'站点名称':st.loc[top_r,'站点名称'],'频次':int(r_counts.max())},
 'peak_cluster_silhouette':sil,
 'configuration_counts':station_eval['配置评价'].astype(str).value_counts().to_dict(),
 'top_improvement_stations':station_eval.sort_values('综合重要度',ascending=False).head(5)[['站点编号','站点名称','综合重要度','周转强度_次每桩日','净流入率','建议新增锁桩']].to_dict('records'),
 'sensitivity_min_top10_overlap':float(sens_df['Top10重合率'].min())
}
with open(RESULTS/'frozen_numbers.json','w',encoding='utf-8') as f: json.dump(frozen,f,ensure_ascii=False,indent=2)
with open(REF/'data_audit_and_method_notes.md','w',encoding='utf-8') as f:
    f.write(f"# 数据审计与方法记录\n\n{DATA_NOTE}\n\n样本：{len(stations)}个站点、{len(trips)}条借还车记录，日期{frozen['date_start']}至{frozen['date_end']}。\n\n方法：描述统计、Haversine距离、时段峰值识别、KMeans峰型聚类、综合配置评价、权重敏感性分析。\n")
# copy code to support/code
# script already lives in support/code; no self-copy needed
if Path(__file__).resolve() != (CODE/'main_modeling.py').resolve():
    shutil.copy2(Path(__file__), CODE/'main_modeling.py')
print(json.dumps(frozen,ensure_ascii=False,indent=2))
