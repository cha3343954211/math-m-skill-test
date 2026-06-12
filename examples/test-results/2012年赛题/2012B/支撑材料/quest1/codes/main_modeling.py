# -*- coding: utf-8 -*-
"""CUMCM 2012B 太阳能小屋建模求解主程序。"""
from pathlib import Path
import re, json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from scipy.optimize import milp, LinearConstraint, Bounds

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012B')
SUP = ROOT/'支撑材料'; RES=SUP/'results'; TABLES=SUP/'tables'
for p in [RES,TABLES]: p.mkdir(parents=True, exist_ok=True)
for q in ['quest1','quest2','quest3']:
    for sub in ['figures','outputs','codes']:
        (SUP/q/sub).mkdir(parents=True, exist_ok=True)
np.random.seed(42)
plt.rcParams['font.sans-serif']=['SimHei','Microsoft YaHei','Arial Unicode MS','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
PV_FILE = ROOT/'cumcm2012B_附件3_三种类型的光伏电池(A单晶硅B多晶硅C非晶硅薄膜)组件设计参数和市场价格.xls'
MET_FILE = ROOT/'cumcm2012B附件4_山西大同典型气象年逐时参数及各方向辐射强度.xls'

GIVEN_HOUSE={'投影长m':10.0,'投影宽m':6.0,'北檐高m':3.0,'南檐高m':5.0,'roof_tilt_deg':math.degrees(math.atan2(2.0,6.0)),'surfaces':{
 '南墙':{'area':42.0,'usable':31.0,'orientation':'南','tilt':90,'irr':'南向总辐射强度'},
 '北墙':{'area':30.0,'usable':24.0,'orientation':'北','tilt':90,'irr':'北向总辐射强度'},
 '东墙':{'area':40.0,'usable':30.0,'orientation':'东','tilt':90,'irr':'东向总辐射强度'},
 '西墙':{'area':40.0,'usable':30.0,'orientation':'西','tilt':90,'irr':'西向总辐射强度'},
 '屋顶':{'area':67.1,'usable':60.0,'orientation':'南倾屋顶','tilt':26.565,'irr':'南向总辐射强度'}}}
DESIGNED_HOUSE={'投影长m':12.0,'投影宽m':6.0,'北檐高m':2.8,'南檐高m':5.4,'roof_tilt_deg':math.degrees(math.atan2(2.6,6.0)),'surfaces':{
 '南墙':{'area':49.2,'usable':36.5,'orientation':'南','tilt':90,'irr':'南向总辐射强度'},
 '北墙':{'area':33.6,'usable':27.0,'orientation':'北','tilt':90,'irr':'北向总辐射强度'},
 '东墙':{'area':49.2,'usable':37.0,'orientation':'东','tilt':90,'irr':'东向总辐射强度'},
 '西墙':{'area':49.2,'usable':37.0,'orientation':'西','tilt':90,'irr':'西向总辐射强度'},
 '屋顶':{'area':78.5,'usable':70.0,'orientation':'南倾屋顶','tilt':23.429,'irr':'南向总辐射强度'}}}

def parse_pv():
    raw=pd.read_excel(PV_FILE, header=None); rows=[]; price_map={'A':14.9,'B':12.5,'C':4.8}
    for _,r in raw.iloc[2:26].iterrows():
        model=str(r[1]).strip() if pd.notna(r[1]) else ''
        if not re.match(r'^[ABC]\d+$', model): continue
        nums=[float(x) for x in re.findall(r'\d+(?:\.\d+)?', str(r[3]))]
        L,W=nums[0]/1000, nums[1]/1000; t=model[0]
        power=float(r[2]); price=price_map[t]
        rows.append(dict(型号=model,类型=t,功率W=power,长m=L,宽m=W,面积m2=L*W,开路电压V=float(r[4]),效率=float(r[6]),价格元每Wp=price,单价元=power*price,启动阈值=80 if t in 'AB' else 30))
    df=pd.DataFrame(rows); df['功率面积比W每m2']=df['功率W']/df['面积m2']; return df

def parse_meteo():
    df=pd.read_excel(MET_FILE, sheet_name='逐时气象参数', header=1).rename(columns=lambda x:str(x).strip())
    df=df.dropna(subset=['日期']).copy(); df['日期']=pd.to_datetime(df['日期']); df['月']=df['日期'].dt.month
    for c in ['水平面总辐射强度','水平面散射辐射强度','法向直射辐射强度','东向总辐射强度','南向总辐射强度','西向总辐射强度','北向总辐射强度']:
        df[c]=pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

def annual_kwh_per_kwp(met, irr_col, threshold=80, mode='attached', tilt_deg=90):
    factor=1.0
    if mode=='elevated': factor=1.14 if (irr_col=='南向总辐射强度' and tilt_deg<60) else (1.05 if irr_col in ['东向总辐射强度','西向总辐射强度'] else 1.03)
    irr=met[irr_col].to_numpy(float)*factor; return float(irr[irr>=threshold].sum()/1000.0)

def inverter_table():
    data=[('SN1',24,21,32,0.4,0.84,2900),('SN2',24,21,32,0.8,0.84,4500),('SN3',48,42,64,0.8,0.86,4500),('SN4',48,42,64,1.6,0.86,6900),('SN5',48,42,64,2.4,0.86,10200),('SN6',48,42,64,4.0,0.90,15000),('SN7',110,99,150,2.4,0.90,10200),('SN8',110,99,150,4.0,0.90,15300),('SN9',110,99,150,8.0,0.92,35000),('SN10',110,99,150,16.0,0.92,63800),('SN11',220,180,300,0.8,0.94,4500),('SN12',220,180,300,1.6,0.94,6900),('SN13',220,180,300,2.4,0.94,10300),('SN14',220,180,300,4.0,0.94,15300),('SN15',220,180,300,6.0,0.94,22000),('SN16',220,180,300,8.0,0.94,35000),('SN17',650,250,800,10.0,0.973,43750),('SN18',650,330,800,12.0,0.973,54700)]
    return pd.DataFrame(data, columns=['型号','额定电压V','下限V','上限V','额定功率kW','效率','价格元'])

def choose_inverter(cap_kw, voltage):
    inv=inverter_table(); f=inv[(inv['额定功率kW']>=cap_kw)&(voltage>=inv['下限V'])&(voltage<=inv['上限V'])]
    if f.empty: f=inv[inv['额定功率kW']>=cap_kw]
    return None if f.empty else f.sort_values(['价格元','额定功率kW']).iloc[0].to_dict()

def string_design(m,n):
    best=None
    for s in range(1,n+1):
        p=math.ceil(n/s); voltage=s*m['开路电压V']; cap=s*p*m['功率W']/1000; inv=choose_inverter(cap,voltage)
        if inv is None: continue
        score=(s*p-n)*m['单价元']+inv['价格元']
        if best is None or score<best[0]: best=(score,s,p,voltage,cap,inv)
    if best is None: return dict(串联数=n,并联串数=1,串电压V=round(n*m['开路电压V'],2),组容量kW=round(n*m['功率W']/1000,3),逆变器='定制',逆变器价格元=0,逆变器效率=0.9)
    _,s,p,voltage,cap,inv=best
    return dict(串联数=int(s),并联串数=int(p),串电压V=round(voltage,2),组容量kW=round(cap,3),逆变器=inv['型号'],逆变器价格元=float(inv['价格元']),逆变器效率=float(inv['效率']))

def optimize(house,mode,qname):
    pv=parse_pv(); met=parse_meteo(); candidates=[]
    for surf,info in house['surfaces'].items():
        for _,m in pv.iterrows():
            maxn=int(info['usable']//m['面积m2'])
            if maxn<=0: continue
            kwh_kwp=annual_kwh_per_kwp(met,info['irr'],m['启动阈值'],mode,info['tilt'])
            annual=m['功率W']/1000*kwh_kwp*0.92; cost=m['单价元']; net=annual*31.5*0.5-cost
            candidates.append(dict(surface=surf,model=m['型号'],type=m['类型'],maxn=maxn,area=m['面积m2'],power=m['功率W'],cost=cost,annual_kwh=annual,net35=net,unit_cost=cost/(annual*31.5+1e-9)))
    cand=pd.DataFrame(candidates); c=-(cand['net35'].to_numpy()); A=[]; lower=[]; upper=[]
    for surf,info in house['surfaces'].items():
        row=np.zeros(len(c)); idx=cand.index[cand.surface==surf].tolist(); row[idx]=cand.loc[idx,'area']; A.append(row); lower.append(0); upper.append(info['usable'])
    res=milp(c=c,integrality=np.ones(len(c)),bounds=Bounds(np.zeros(len(c)),cand['maxn'].to_numpy(float)),constraints=LinearConstraint(np.array(A),np.array(lower),np.array(upper)),options={'time_limit':20})
    x=np.rint(res.x).astype(int) if res.success else np.zeros(len(c),int); sol=cand.copy(); sol['数量']=x; sol=sol[sol['数量']>0].copy()
    if sol['数量'].sum()<10:
        rows=[]
        for surf,info in house['surfaces'].items():
            r=cand[cand.surface==surf].sort_values(['unit_cost','annual_kwh'],ascending=[True,False]).iloc[0].copy(); r['数量']=int(info['usable']//r['area']); rows.append(r)
        sol=pd.DataFrame(rows)
    out=[]
    for _,r in sol.iterrows():
        m=pv[pv['型号']==r['model']].iloc[0]; sd=string_design(m,int(r['数量']))
        annual=float(r['annual_kwh']*r['数量']*sd['逆变器效率']); cap=float(r['power']*r['数量']/1000); total=float(r['cost']*r['数量']+sd['逆变器价格元']); life=annual*31.5; revenue=life*0.5
        out.append({**r.to_dict(),**sd,'装机容量kW':cap,'年发电量kWh':annual,'35年等效发电量kWh':life,'总投资元':total,'35年收益元':revenue,'净收益元':revenue-total,'回收年限':total/(annual*0.5),'单位电量费用元每kWh':total/life})
    ans=pd.DataFrame(out).sort_values('年发电量kWh',ascending=False)
    # 逆变器是固定成本。MILP阶段只按组件边际收益筛选，可能为少量零散小组件单独配置逆变器，
    # 导致该分组全寿命净收益为负；后处理删除这些经济性不可接受的分组，保留可执行主方案。
    pos=ans[ans['净收益元']>=0].copy()
    if not pos.empty:
        ans=pos.sort_values('年发电量kWh',ascending=False)
    ans.to_csv(TABLES/f'{qname}_铺设分组与逆变器.csv',index=False,encoding='utf-8-sig')
    summary={'组件块数':int(ans['数量'].sum()),'装机容量kW':round(float(ans['装机容量kW'].sum()),3),'年发电量kWh':round(float(ans['年发电量kWh'].sum()),1),'35年等效发电量kWh':round(float(ans['35年等效发电量kWh'].sum()),1),'总投资元':round(float(ans['总投资元'].sum()),1),'35年收益元':round(float(ans['35年收益元'].sum()),1),'净收益元':round(float(ans['净收益元'].sum()),1),'平均单位电量费用元每kWh':round(float(ans['总投资元'].sum()/ans['35年等效发电量kWh'].sum()),3),'静态回收年限':round(float(ans['总投资元'].sum()/(ans['年发电量kWh'].sum()*0.5)),2)}
    base=[]
    for surf,info in house['surfaces'].items():
        sub=cand[cand.surface==surf].copy(); sub['area_yield']=sub['annual_kwh']/sub['area']; r=sub.sort_values('area_yield',ascending=False).iloc[0]; n=int(info['usable']//r['area']); base.append((r,n))
    base_cost=sum(r['cost']*n for r,n in base); base_annual=sum(r['annual_kwh']*n*0.92 for r,n in base)
    return ans,summary,{'年发电量kWh':round(float(base_annual),1),'总投资元':round(float(base_cost),1),'单位电量费用元每kWh':round(float(base_cost/(base_annual*31.5)),3)}

def plot_solution(ans,house,qname):
    fig,ax=plt.subplots(figsize=(12,7)); ax.set_title(f'{qname} 光伏组件铺设与分组阵列示意图'); y=0; colors={'A':'#4C78A8','B':'#F58518','C':'#54A24B'}
    for surf,info in house['surfaces'].items():
        ax.add_patch(Rectangle((0,y),info['usable']/5,0.8,fill=False,lw=1.5)); ax.text(-0.2,y+0.4,surf,ha='right',va='center'); x=0
        for _,r in ans[ans['surface']==surf].iterrows():
            w=max(0.25,(r['area']*r['数量'])/5); ax.add_patch(Rectangle((x,y),w,0.8,color=colors.get(r['type'],'gray'),alpha=0.75)); ax.text(x+w/2,y+0.4,f"{r['model']}×{int(r['数量'])}\n{int(r['串联数'])}串×{int(r['并联串数'])}并\n{r['逆变器']}",ha='center',va='center',fontsize=7); x+=w
        y+=1.2
    ax.set_xlim(-1,max(v['usable'] for v in house['surfaces'].values())/5+1); ax.set_ylim(-.2,y); ax.axis('off')
    qdir={'问题1':'quest1','问题2':'quest2','问题3':'quest3'}[qname]; plt.savefig(SUP/qdir/'figures'/f'{qname}_铺设示意图.png',dpi=300,bbox_inches='tight'); plt.close()

def plots_and_sens(ans,qname):
    ratios=np.linspace(0.8,1.2,9); base_a=ans['年发电量kWh'].sum(); base_c=ans['总投资元'].sum(); rows=[]
    for rr in ratios: rows.append({'辐射扰动系数':rr,'年发电量kWh':base_a*rr,'回收年限':base_c/(base_a*rr*0.5),'单位电量费用元每kWh':base_c/(base_a*rr*31.5)})
    df=pd.DataFrame(rows); df.to_csv(TABLES/f'{qname}_敏感性分析.csv',index=False,encoding='utf-8-sig')
    fig,ax=plt.subplots(figsize=(7,4)); ax.plot(df['辐射扰动系数'],df['回收年限'],'o-'); ax.set_xlabel('辐射强度扰动系数'); ax.set_ylabel('静态回收年限/年'); ax.set_title(f'{qname} 敏感性分析')
    qdir={'问题1':'quest1','问题2':'quest2','问题3':'quest3'}[qname]; plt.savefig(SUP/qdir/'figures'/f'{qname}_敏感性分析.png',dpi=300,bbox_inches='tight'); plt.close()

def main():
    (SUP/'references'/'phase0_knowledge_search.md').write_text('# Phase 0 检索记录\n\nIMA 检索“2012B 太阳能小屋 光伏 优化”等关键词返回空结果。本文依据题目附件和 math-modeling 优化题门控流程，采用 baseline + 整数规划 + 逆变器后处理。附件2目录为空，按题面建筑约束作几何重构并在论文中说明。\n',encoding='utf-8')
    pv=parse_pv(); met=parse_meteo(); inv=inverter_table(); pv.to_csv(TABLES/'光伏组件参数清洗表.csv',index=False,encoding='utf-8-sig'); inv.to_csv(TABLES/'逆变器参数整理表.csv',index=False,encoding='utf-8-sig')
    monthly=met.groupby('月')[['东向总辐射强度','南向总辐射强度','西向总辐射强度','北向总辐射强度','水平面总辐射强度']].sum()/1000; monthly.to_csv(TABLES/'月度各方向辐射量.csv',encoding='utf-8-sig'); monthly.plot(figsize=(10,5),marker='o'); plt.title('大同典型气象年各方向月辐射量'); plt.ylabel('kWh/m²'); plt.savefig(RES/'月度辐射量.png',dpi=300,bbox_inches='tight'); plt.close()
    results={}; baselines={}
    for q,house,mode in [('问题1',GIVEN_HOUSE,'attached'),('问题2',GIVEN_HOUSE,'elevated'),('问题3',DESIGNED_HOUSE,'elevated')]:
        ans,s,b=optimize(house,mode,q); results[q]=s; baselines[q]=b; plot_solution(ans,house,q); plots_and_sens(ans,q)
    labels=list(results); fig,ax1=plt.subplots(figsize=(9,5)); ax1.bar(labels,[results[k]['年发电量kWh'] for k in labels],color='#4C78A8'); ax1.set_ylabel('年发电量/kWh'); ax2=ax1.twinx(); ax2.plot(labels,[results[k]['平均单位电量费用元每kWh'] for k in labels],'o-',color='#E45756'); ax2.set_ylabel('单位电量费用/(元/kWh)'); plt.title('三种方案对比'); plt.savefig(RES/'三方案对比.png',dpi=300,bbox_inches='tight'); plt.close()
    audit={'气象记录数':int(len(met)),'气象字段数':int(met.shape[1]),'辐射缺失值数':int(met[['东向总辐射强度','南向总辐射强度','西向总辐射强度','北向总辐射强度']].isna().sum().sum()),'光伏组件型号数':int(len(pv)),'逆变器型号数':int(len(inv)),'附件2状态':'原目录为空，采用几何重构并声明假设'}
    frozen={'题目':'CUMCM2012B 太阳能小屋的设计','results':results,'baselines':baselines,'data_audit':audit,'given_house':GIVEN_HOUSE,'designed_house':DESIGNED_HOUSE}
    (RES/'frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 最终结果分析与论文写作包\n']
    for q,s in results.items(): lines.append(f"## {q}\n- 组件块数：{s['组件块数']}；装机容量：{s['装机容量kW']} kW；年发电量：{s['年发电量kWh']} kWh；35年等效发电量：{s['35年等效发电量kWh']} kWh。\n- 总投资：{s['总投资元']} 元；35年收益：{s['35年收益元']} 元；净收益：{s['净收益元']} 元；单位电量费用：{s['平均单位电量费用元每kWh']} 元/kWh；静态回收期：{s['静态回收年限']} 年。\n- baseline：年发电量 {baselines[q]['年发电量kWh']} kWh，总投资 {baselines[q]['总投资元']} 元，单位费用 {baselines[q]['单位电量费用元每kWh']} 元/kWh。\n")
    (RES/'q_solution_package_for_writer.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
