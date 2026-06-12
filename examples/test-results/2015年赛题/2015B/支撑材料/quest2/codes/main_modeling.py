# -*- coding: utf-8 -*-
"""2015B “互联网+”时代的出租车资源配置 数学建模全过程代码。"""
from pathlib import Path
import json, math, random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.optimize import differential_evolution
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

SEED = 42
random.seed(SEED); np.random.seed(SEED)
ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2015年赛题/2015B/支撑材料')
FIGS = ROOT/'results'/'figures'; TABLES = ROOT/'tables'; OUT = ROOT/'results'; CONTRACTS=ROOT/'contracts'
for p in [FIGS, TABLES, OUT, CONTRACTS]: p.mkdir(parents=True, exist_ok=True)
for q in ['quest1','quest2','quest3']:
    for sub in ['figures','outputs']:
        (ROOT/q/sub).mkdir(parents=True, exist_ok=True)
for fp in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False

zones = pd.DataFrame({
    'zone_id': range(1,9),
    'zone': ['火车站/机场','CBD商务区','高校园区','居住新区','老城商业区','工业园区','景区医院','远郊组团'],
    'type': ['枢纽','商务','教育','居住','商业','工业','公共服务','远郊'],
    'poi_index': [1.00,0.92,0.55,0.62,0.78,0.45,0.70,0.28],
    'base_demand': [320,285,150,210,245,130,190,80],
    'base_supply': [250,230,145,170,190,120,150,55],
})
periods = pd.DataFrame({'period_id': range(1,7),'period':['早高峰','上午平峰','午间','晚高峰','夜间','深夜'],'demand_factor':[1.55,0.82,1.00,1.75,1.18,0.42],'supply_factor':[1.05,0.95,0.92,1.10,0.82,0.45]})
weather = pd.DataFrame({'weather':['晴','雨','极端天气'], 'demand_mult':[1.00,1.18,1.35], 'supply_mult':[1.00,0.88,0.72]})
rows=[]
for _,z in zones.iterrows():
  for _,t in periods.iterrows():
    for _,w0 in weather.iterrows():
      lam_d = z.base_demand*t.demand_factor*w0.demand_mult*(0.92+0.18*np.random.rand())
      lam_s = z.base_supply*t.supply_factor*w0.supply_mult*(0.90+0.20*np.random.rand())
      demand=max(1, int(np.random.normal(lam_d, max(6, 0.08*lam_d))))
      supply=max(1, int(np.random.normal(lam_s, max(5, 0.07*lam_s))))
      gap=demand-supply; ratio=supply/demand
      success=min(0.99, max(0.30, 0.52+0.42*min(ratio,1.2)-0.06*(w0.weather!='晴')+np.random.normal(0,0.025)))
      wait=max(1.2, 4+18*max(0,1-ratio)+3*(w0.weather=='雨')+6*(w0.weather=='极端天气')+np.random.normal(0,1.1))
      empty=max(0.03, min(0.55, 0.32-0.18*min(demand/supply,1.6)+0.04*(z.type=='远郊')+np.random.normal(0,0.025)))
      rows.append([z.zone_id,z.zone,z.type,t.period_id,t.period,w0.weather,demand,supply,gap,ratio,success,wait,empty])
df=pd.DataFrame(rows, columns=['zone_id','zone','type','period_id','period','weather','demand','supply','gap','supply_demand_ratio','success_rate','avg_wait_min','empty_rate'])
(ROOT/'data').mkdir(exist_ok=True)
df.to_csv(ROOT/'data'/'taxi_spatiotemporal_estimated_data.csv', index=False, encoding='utf-8-sig')

def entropy_weight(X):
    X=np.asarray(X, dtype=float); X=(X-X.min(axis=0))/(X.max(axis=0)-X.min(axis=0)+1e-12)
    P=X/(X.sum(axis=0)+1e-12); E=-(P*np.log(P+1e-12)).sum(axis=0)/np.log(X.shape[0]); D=1-E
    return D/D.sum()

eval_df=df.copy(); eval_df['ratio_closeness']=1/(1+abs(eval_df['supply_demand_ratio']-1)); eval_df['gap_abs']=eval_df['gap'].abs()
raw=eval_df[['success_rate','ratio_closeness','avg_wait_min','gap_abs','empty_rate']].copy()
mat=pd.DataFrame({'success_rate':raw.success_rate,'ratio_closeness':raw.ratio_closeness})
for c in ['avg_wait_min','gap_abs','empty_rate']: mat[c]=raw[c].max()-raw[c]
w=entropy_weight(mat.values); X=(mat-mat.min())/(mat.max()-mat.min()+1e-12)
Dpos=np.sqrt(((X-X.max())**2*w).sum(axis=1)); Dneg=np.sqrt(((X-X.min())**2*w).sum(axis=1))
eval_df['match_index']=Dneg/(Dpos+Dneg); eval_df['match_level']=pd.cut(eval_df['match_index'], bins=[-0.01,0.35,0.50,0.65,1.01], labels=['严重失衡','偏紧张','基本匹配','匹配良好'])
eval_df.to_csv(TABLES/'q1_spatiotemporal_match_results.csv', index=False, encoding='utf-8-sig')
summary_zone=eval_df.groupby('zone').agg(match_index=('match_index','mean'), success_rate=('success_rate','mean'), avg_wait_min=('avg_wait_min','mean'), supply_demand_ratio=('supply_demand_ratio','mean'), gap=('gap','mean')).sort_values('match_index')
summary_period=eval_df.groupby('period').agg(match_index=('match_index','mean'), avg_wait_min=('avg_wait_min','mean'), gap=('gap','mean')).sort_values('match_index')
summary_zone.to_csv(TABLES/'q1_zone_summary.csv', encoding='utf-8-sig'); summary_period.to_csv(TABLES/'q1_period_summary.csv', encoding='utf-8-sig')
baseline_score=X.values.mean(axis=1); baseline_corr=float(np.corrcoef(baseline_score, eval_df['match_index'])[0,1])
plt.figure(figsize=(10,5)); summary_zone['match_index'].plot(kind='barh', color='#4976B7'); plt.xlabel('供求匹配指数'); plt.title('各区域出租车供求匹配指数（越高越匹配）'); plt.tight_layout(); plt.savefig(FIGS/'q1_zone_match_index.png', dpi=300, bbox_inches='tight'); plt.close()
pivot=eval_df.pivot_table(index='period', columns='zone', values='match_index', aggfunc='mean').loc[periods.period]
plt.figure(figsize=(11,5.5)); plt.imshow(pivot.values, cmap='RdYlGn', aspect='auto', vmin=0.25, vmax=0.8); plt.colorbar(label='匹配指数'); plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=35, ha='right'); plt.yticks(range(len(pivot.index)), pivot.index); plt.title('不同时空供求匹配热力图'); plt.tight_layout(); plt.savefig(FIGS/'q1_match_heatmap.png', dpi=300, bbox_inches='tight'); plt.close()

companies=['A平台','B平台','C平台']; panel=[]
for company in companies:
  for day in range(1,31):
    post=1 if day>=16 else 0
    for _,base in df.sample(30, random_state=SEED+day).iterrows():
      shortage=max(0, base.demand-base.supply)/base.demand
      if company=='A平台': ps, ds = (7.5,2.0) if post else (0,0)
      elif company=='B平台': ps, ds = (3.0,6.0) if post else (0,0)
      else: ps, ds = (1.5,1.5) if post else (0,0)
      demand2=base.demand*(1+0.018*ps-0.006*ds)+np.random.normal(0,8); supply2=base.supply*(1+0.012*ps+0.030*ds*(1+0.6*shortage))+np.random.normal(0,7)
      ratio=supply2/max(demand2,1); succ=min(0.99,max(0.25,0.50+0.43*min(ratio,1.25)-0.025*(base.weather!='晴')+np.random.normal(0,0.018)))
      wait=max(1, 4+17*max(0,1-ratio)+2.2*(base.weather=='雨')+5*(base.weather=='极端天气')+np.random.normal(0,0.85)); cost=max(0, demand2*succ*ps + supply2*ds*0.42)
      panel.append([company,day,post,base.zone,base.period,base.weather,ps,ds,demand2,supply2,ratio,succ,wait,cost,shortage])
panel=pd.DataFrame(panel, columns=['company','day','post','zone','period','weather','passenger_subsidy','driver_subsidy','demand','supply','ratio','success_rate','avg_wait_min','cost','shortage'])
panel.to_csv(TABLES/'q2_subsidy_panel.csv', index=False, encoding='utf-8-sig')
D=pd.get_dummies(panel[['company','period','weather']], drop_first=True)
X2=pd.concat([panel[['post','passenger_subsidy','driver_subsidy','shortage']],D], axis=1).astype(float); y=panel['success_rate']
reg=LinearRegression().fit(X2,y); pred=reg.predict(X2)
metrics={'mae':float(mean_absolute_error(y,pred)), 'rmse':float(math.sqrt(mean_squared_error(y,pred))), 'r2':float(reg.score(X2,y))}; coef=dict(zip(X2.columns, reg.coef_)); coef['intercept']=reg.intercept_
q2_summary=panel.groupby(['company','post']).agg(success_rate=('success_rate','mean'), avg_wait_min=('avg_wait_min','mean'), cost=('cost','mean'), ratio=('ratio','mean')).reset_index(); q2_delta=[]
for c in companies:
    pre=q2_summary[(q2_summary.company==c)&(q2_summary.post==0)].iloc[0]; po=q2_summary[(q2_summary.company==c)&(q2_summary.post==1)].iloc[0]
    q2_delta.append({'company':c,'success_rate_delta':po.success_rate-pre.success_rate,'wait_delta_min':po.avg_wait_min-pre.avg_wait_min,'cost_per_order':po.cost/max(panel[(panel.company==c)&(panel.post==1)].eval('demand*success_rate').mean(),1),'ratio_delta':po.ratio-pre.ratio})
q2_delta=pd.DataFrame(q2_delta); q2_summary.to_csv(TABLES/'q2_before_after_summary.csv', index=False, encoding='utf-8-sig'); q2_delta.to_csv(TABLES/'q2_subsidy_effect_delta.csv', index=False, encoding='utf-8-sig')
plt.figure(figsize=(8,5))
for c in companies:
    tmp=q2_summary[q2_summary.company==c]; plt.plot(['补贴前','补贴后'], tmp['success_rate'], marker='o', label=c)
plt.ylabel('订单成功率'); plt.title('不同平台补贴前后订单成功率变化'); plt.legend(); plt.tight_layout(); plt.savefig(FIGS/'q2_success_before_after.png', dpi=300, bbox_inches='tight'); plt.close()
plt.figure(figsize=(8,5)); plt.bar(q2_delta.company, q2_delta.wait_delta_min, color='#D65F5F'); plt.axhline(0,color='k',lw=0.8); plt.ylabel('平均等待时间变化（分钟）'); plt.title('补贴后等待时间变化（负值表示缓解打车难）'); plt.tight_layout(); plt.savefig(FIGS/'q2_wait_delta.png', dpi=300, bbox_inches='tight'); plt.close()

def simulate_policy(params, data):
    a,b,c,d=params; Dv=data['demand'].values.astype(float); Sv=data['supply'].values.astype(float); m=np.maximum(0,Dv-Sv)/Dv
    ps=np.clip(a*m+b,0,10); ds=np.clip(c*m+d,0,12); D2=Dv*(1+0.014*ps-0.005*ds); S2=Sv*(1+0.010*ps+0.035*ds*(1+0.7*m))
    ratio=S2/D2; success=np.clip(0.51+0.43*np.minimum(ratio,1.25)-0.02*(data['weather'].values!='晴'),0.25,0.99)
    wait=np.maximum(1.0,4+17*np.maximum(0,1-ratio)+2*(data['weather'].values=='雨')+5*(data['weather'].values=='极端天气'))
    cost=(D2*success*ps + S2*ds*0.42)/(D2*success+1e-9); match=0.45*success + 0.25/(1+np.abs(ratio-1)) + 0.20*(1/(1+wait/10)) + 0.10*(1-np.clip(cost/12,0,1))
    return match.mean(), success.mean(), wait.mean(), cost.mean(), ps.mean(), ds.mean()
def objective(params):
    match,succ,wait,cost,ps,ds=simulate_policy(params, df); penalty=max(0,cost-8.0)**2
    return -(match + 0.03*succ - 0.004*wait - 0.01*penalty)
res=differential_evolution(objective, bounds=[(0,12),(0,3),(0,14),(0,3)], seed=SEED, tol=1e-7, polish=True); opt_params=res.x
base_policy=simulate_policy([0,0,0,0], df); flat_policy=simulate_policy([0,3,0,3], df); opt_policy=simulate_policy(opt_params, df)
q3=pd.DataFrame([{'policy':'无补贴基线','match_index':base_policy[0],'success_rate':base_policy[1],'avg_wait_min':base_policy[2],'cost_per_order':base_policy[3],'avg_passenger_subsidy':base_policy[4],'avg_driver_subsidy':base_policy[5]},{'policy':'固定双边补贴(3,3)','match_index':flat_policy[0],'success_rate':flat_policy[1],'avg_wait_min':flat_policy[2],'cost_per_order':flat_policy[3],'avg_passenger_subsidy':flat_policy[4],'avg_driver_subsidy':flat_policy[5]},{'policy':'动态错配补贴优化','match_index':opt_policy[0],'success_rate':opt_policy[1],'avg_wait_min':opt_policy[2],'cost_per_order':opt_policy[3],'avg_passenger_subsidy':opt_policy[4],'avg_driver_subsidy':opt_policy[5]}])
q3.to_csv(TABLES/'q3_policy_comparison.csv', index=False, encoding='utf-8-sig')
sens=[]
for mult in np.linspace(0.7,1.3,13):
    p=opt_params.copy(); p[[0,2]]*=mult; r=simulate_policy(p, df); sens.append({'subsidy_intensity_ratio':mult,'match_index':r[0],'success_rate':r[1],'avg_wait_min':r[2],'cost_per_order':r[3]})
sens=pd.DataFrame(sens); sens.to_csv(TABLES/'q3_sensitivity.csv', index=False, encoding='utf-8-sig')
plt.figure(figsize=(8,5)); plt.plot(sens.subsidy_intensity_ratio, sens.match_index, marker='o'); plt.xlabel('补贴强度倍数'); plt.ylabel('匹配指数'); plt.title('动态补贴强度敏感性分析'); plt.tight_layout(); plt.savefig(FIGS/'q3_sensitivity.png', dpi=300, bbox_inches='tight'); plt.close()
plt.figure(figsize=(8,5)); x=np.arange(len(q3)); plt.bar(x-0.2,q3.success_rate,width=0.4,label='成功率'); plt.bar(x+0.2,1/(1+q3.avg_wait_min/10),width=0.4,label='等待时间转化得分'); plt.xticks(x,q3.policy,rotation=15,ha='right'); plt.title('新平台补贴方案与基线对比'); plt.legend(); plt.tight_layout(); plt.savefig(FIGS/'q3_policy_comparison.png', dpi=300, bbox_inches='tight'); plt.close()

worst=summary_zone.iloc[0]; best=summary_zone.iloc[-1]; worst_period=summary_period.iloc[0]; best_company=q2_delta.sort_values('wait_delta_min').iloc[0]; optrow=q3[q3.policy=='动态错配补贴优化'].iloc[0]
frozen={'Q1':{'entropy_weights':dict(zip(['订单成功率','供需比接近度','平均等待时间','绝对缺口','空驶率'], [round(float(x),4) for x in w])),'baseline_corr_equal_weight':round(baseline_corr,4),'worst_zone':str(worst.name),'worst_zone_match_index':round(float(worst.match_index),4),'worst_zone_wait_min':round(float(worst.avg_wait_min),2),'best_zone':str(best.name),'best_zone_match_index':round(float(best.match_index),4),'worst_period':str(worst_period.name),'worst_period_match_index':round(float(worst_period.match_index),4)},'Q2':{'regression_metrics':{k:round(v,4) for k,v in metrics.items()},'driver_subsidy_coef':round(float(coef.get('driver_subsidy',0)),4),'passenger_subsidy_coef':round(float(coef.get('passenger_subsidy',0)),4),'best_company_for_relief':str(best_company.company),'best_company_success_delta_pct':round(float(best_company.success_rate_delta*100),2),'best_company_wait_delta_min':round(float(best_company.wait_delta_min),2),'all_company_delta': q2_delta.round(4).to_dict(orient='records')},'Q3':{'optimal_params_a_b_c_d':[round(float(x),4) for x in opt_params],'optimal_policy_match_index':round(float(optrow.match_index),4),'optimal_policy_success_rate_pct':round(float(optrow.success_rate*100),2),'optimal_policy_wait_min':round(float(optrow.avg_wait_min),2),'optimal_policy_cost_per_order':round(float(optrow.cost_per_order),2),'optimal_avg_passenger_subsidy':round(float(optrow.avg_passenger_subsidy),2),'optimal_avg_driver_subsidy':round(float(optrow.avg_driver_subsidy),2),'match_improvement_vs_no_subsidy_pct':round(float((optrow.match_index/q3.iloc[0].match_index-1)*100),2),'wait_reduction_vs_no_subsidy_pct':round(float((1-optrow.avg_wait_min/q3.iloc[0].avg_wait_min)*100),2)},'execution':{'seed':SEED,'data_rows':int(len(df)),'panel_rows':int(len(panel))}}
(OUT/'frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
(CONTRACTS/'problem_analysis.json').write_text(json.dumps({'schema_version':'1.0','generated_by':'main_modeling.py','question':'2015B “互联网+”时代的出租车资源配置','subquestions':[{'id':'Q1','requirement':'建立指标并分析不同时空出租车供求匹配程度','type':'评价/时空分析','output':'供求匹配指数、等级、区域与时段排序'},{'id':'Q2','requirement':'分析补贴方案是否缓解打车难','type':'政策评估/回归对比','output':'补贴前后订单成功率、等待时间、回归系数与成本效率'},{'id':'Q3','requirement':'设计新打车平台补贴方案并论证合理性','type':'约束优化/敏感性分析','output':'动态双边补贴函数、最优参数、成本与效果对比'}],'data_assets':['题目无附件，本文构造可复现实证口径：8类城市区域×6时段×3天气的供需估计表；补贴评估面板由政策情景模型生成，全部代码可重跑。']},ensure_ascii=False,indent=2),encoding='utf-8')
(CONTRACTS/'model_route.json').write_text(json.dumps({'schema_version':'1.0','generated_by':'main_modeling.py','routes':[{'question_id':'Q1','baseline':'等权综合评分','main_model':'熵权-TOPSIS供求匹配评价','validation':'与等权baseline相关性、时空热力图、指标权重审计'},{'question_id':'Q2','baseline':'补贴前均值对比','main_model':'补贴前后面板回归 + 平台对比','validation':'R2/RMSE、成功率与等待时间变化、单均成本'},{'question_id':'Q3','baseline':'无补贴、固定双边补贴','main_model':'错配驱动动态双边补贴优化','validation':'与baseline对比、补贴强度敏感性'}]},ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'readme.txt').write_text('# 2015B “互联网+”时代的出租车资源配置 支撑材料\n\n运行：python quest1/codes/main_modeling.py\n\n主要文件：papper/论文.pdf；results/frozen_numbers.json；tables/*.csv；results/figures/*.png。\n', encoding='utf-8')
print(json.dumps(frozen,ensure_ascii=False,indent=2))
