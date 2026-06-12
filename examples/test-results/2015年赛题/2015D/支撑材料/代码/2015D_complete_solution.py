# -*- coding: utf-8 -*-
"""
2015D 众筹筑屋规划方案设计 - 完整建模求解脚本
生成：方案I核算、方案II优化、投资回报率调整、图表、冻结数字与契约文件。
"""
from pathlib import Path
import json, math, warnings
import numpy as np
import pandas as pd

def clean_json(obj):
    """Convert numpy/pandas scalar values to plain JSON-serializable Python values."""
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if pd.isna(obj) if isinstance(obj, (float, np.floating)) else False:
        return None
    return obj
from scipy.optimize import milp, LinearConstraint, Bounds
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
warnings.filterwarnings('ignore')
np.random.seed(42)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'; FIG = ROOT / '图表'; TAB = ROOT / 'tables'; CON = ROOT / 'contracts'; QA = ROOT / 'qa'; REF = ROOT / 'references'
for p in [OUT, FIG, TAB, CON, QA, REF]: p.mkdir(parents=True, exist_ok=True)
# 中文字体
for fp in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif']=[font_manager.FontProperties(fname=fp).get_name(),'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus']=False

LAND_AREA = 102077.6
LAND_COST = 777_179_627.0
MAX_FAR = 2.28
TRANSFER_TAX_RATE = 0.0565
ROI_THRESHOLD = 0.25
# 土地增值税超率累进税率：速算扣除系数
LVAT_BRACKETS = [(0.5,0.30,0.00),(1.0,0.40,0.05),(2.0,0.50,0.15),(float('inf'),0.60,0.35)]

housing = pd.DataFrame({
    'type_id': list(range(1,12)),
    'name': [f'房型{i}' for i in range(1,12)],
    'category': ['普通住宅','普通住宅','普通住宅','非普通住宅','非普通住宅','非普通住宅','非普通住宅','非普通住宅','其他','其他','非普通住宅'],
    'far_included': [1,1,1,1,1,1,1,1,0,0,0],
    'cost_deductible': [1,1,0,1,1,1,1,0,1,1,0],
    'area': [77,98,117,145,156,167,178,126,103,129,133],
    'plan1_units': [250,250,150,250,250,250,250,75,150,150,75],
    'unit_cost': [4263,4323,4532,5288,5268,5533,5685,4323,2663,2791,2982],
    'price': [12000,10800,11200,12800,12800,13600,14000,10400,6400,6800,7200],
    'min_units': [50,50,50,150,100,150,50,100,50,50,50],
    'max_units': [450,500,300,500,550,350,450,250,350,400,250],
    'satisfaction': [0.4,0.6,0.5,0.6,0.7,0.8,0.9,0.6,0.2,0.3,0.4]
})
# 参筹意愿比例归一化为结构偏好：题给为逐房型满意比例，不能直接当总和为1的份额
housing['pref_share'] = housing['satisfaction'] / housing['satisfaction'].sum()
housing['revenue_per_unit'] = housing.area * housing.price
housing['build_cost_per_unit'] = housing.area * housing.unit_cost
housing['profit_before_tax_per_unit'] = housing.revenue_per_unit - housing.build_cost_per_unit
housing.to_csv(TAB/'input_housing_data.csv', index=False, encoding='utf-8-sig')

def lvat_tax(income, deductible, surcharge=True):
    """土地增值税。deductible含土地、开发成本、开发费用、税金、加计扣除等准予扣除项。"""
    increment = max(0.0, income - deductible)
    if deductible <= 1e-9 or increment <= 0:
        return 0.0, increment, 0.0, 0.0
    ratio = increment / deductible
    for ub, rate, quick in LVAT_BRACKETS:
        if ratio <= ub:
            tax = increment * rate - deductible * quick
            return max(0.0, tax), increment, ratio, rate
    raise RuntimeError('unreachable')

def allocate_other(values, ordinary_area, nonordinary_area):
    total = ordinary_area + nonordinary_area
    if total <= 0: return 0.0,0.0
    return values * ordinary_area/total, values * nonordinary_area/total

def evaluate(units, label='方案'):
    df = housing.copy(); df['units'] = np.array(units, dtype=float)
    df['total_area'] = df.area * df.units
    df['far_area'] = df.total_area * df.far_included
    df['income'] = df.revenue_per_unit * df.units
    df['build_cost'] = df.build_cost_per_unit * df.units
    df['deductible_build_cost_raw'] = df.build_cost * df.cost_deductible
    total_income = df.income.sum(); total_build_cost = df.build_cost.sum(); total_area = df.total_area.sum()
    far = df.far_area.sum()/LAND_AREA
    transfer_tax = total_income * TRANSFER_TAX_RATE
    # 开发费用：按取得土地金额与开发成本之和的10%估算；房地产企业加计扣除20%。
    ordinary = df.category.eq('普通住宅'); nonordinary = df.category.eq('非普通住宅'); other = df.category.eq('其他')
    ordinary_area = df.loc[ordinary,'total_area'].sum(); nonordinary_area = df.loc[nonordinary,'total_area'].sum()
    # 土地、税金按收入比例分摊；其他类别按普通/非普通建筑面积比分摊。
    group_rows=[]; total_lvat=0
    for cat, mask in [('普通住宅', ordinary), ('非普通住宅', nonordinary)]:
        inc_direct = df.loc[mask,'income'].sum(); cost_direct = df.loc[mask,'deductible_build_cost_raw'].sum()
        other_inc, other_cost = allocate_other(df.loc[other,'income'].sum(), ordinary_area, nonordinary_area) if cat=='普通住宅' else allocate_other(df.loc[other,'income'].sum(), ordinary_area, nonordinary_area)[1], allocate_other(df.loc[other,'deductible_build_cost_raw'].sum(), ordinary_area, nonordinary_area)[1]
        if cat=='普通住宅':
            other_inc, other_cost = allocate_other(df.loc[other,'income'].sum(), ordinary_area, nonordinary_area)[0], allocate_other(df.loc[other,'deductible_build_cost_raw'].sum(), ordinary_area, nonordinary_area)[0]
        income = inc_direct + other_inc
        build_cost_deductible = cost_direct + other_cost
        income_share = income/total_income if total_income>0 else 0
        land = LAND_COST * income_share
        tr_tax = transfer_tax * income_share
        dev_fee = 0.10*(land + build_cost_deductible)
        add_deduct = 0.20*(land + build_cost_deductible)
        deductible = land + build_cost_deductible + dev_fee + tr_tax + add_deduct
        tax, increment, ratio, rate = lvat_tax(income, deductible)
        total_lvat += tax
        group_rows.append(dict(label=label, group=cat, income=income, direct_income=inc_direct, allocated_other_income=other_inc,
                               deductible_build_cost=build_cost_deductible, land_cost=land, transfer_tax=tr_tax,
                               dev_fee=dev_fee, add_deduct=add_deduct, deductible=deductible, increment=increment,
                               increment_ratio=ratio, tax_rate=rate, lvat=tax))
    total_cost = total_build_cost + LAND_COST + transfer_tax + total_lvat
    net_profit = total_income - total_cost
    roi = net_profit / total_cost if total_cost else -999
    # 满意度匹配：供应结构与偏好结构的L1偏差、加权满意率
    supply_share = df.units/df.units.sum()
    match_l1 = float(np.abs(supply_share - df.pref_share).sum())
    satisfaction_score = float((supply_share * df.satisfaction).sum())
    summary = dict(label=label, total_units=float(df.units.sum()), total_area=float(total_area), far=float(far),
                   total_income=float(total_income), build_cost=float(total_build_cost), land_cost=float(LAND_COST),
                   transfer_tax=float(transfer_tax), lvat=float(total_lvat), total_cost=float(total_cost),
                   net_profit=float(net_profit), roi=float(roi), match_l1=match_l1,
                   satisfaction_score=satisfaction_score, feasible_far=far<=MAX_FAR+1e-6,
                   roi_success=roi>=ROI_THRESHOLD)
    return summary, df, pd.DataFrame(group_rows)

# 方案I
s1, df1, tax1 = evaluate(housing.plan1_units.values, '方案I')

# baseline：按偏好比例分配到方案I总套数，再投影到上下界并用贪心补齐/削减容积率
TOTAL_UNITS = int(s1['total_units'])
def project_units(raw, target_total=TOTAL_UNITS):
    x = np.rint(raw).astype(int)
    x = np.maximum(x, housing.min_units.values); x = np.minimum(x, housing.max_units.values)
    # 调整总套数，优先按偏好不足/过剩调整，同时控制容积率
    for _ in range(10000):
        diff = target_total - x.sum()
        far_area = np.dot(x, housing.area.values*housing.far_included.values)
        if diff==0 and far_area <= MAX_FAR*LAND_AREA+1e-6: break
        if diff>0:
            candidates=[i for i in range(11) if x[i] < housing.max_units.iloc[i] and far_area + housing.area.iloc[i]*housing.far_included.iloc[i] <= MAX_FAR*LAND_AREA+1e-6]
            if not candidates: break
            desired=target_total*housing.pref_share.values - x
            i=max(candidates, key=lambda j:(desired[j], housing.profit_before_tax_per_unit.iloc[j]/10000))
            x[i]+=1
        else:
            candidates=[i for i in range(11) if x[i] > housing.min_units.iloc[i]]
            if not candidates: break
            excess=x-target_total*housing.pref_share.values
            i=max(candidates, key=lambda j:(excess[j], housing.area.iloc[j]*housing.far_included.iloc[j]))
            x[i]-=1
    return x
baseline_units = project_units(TOTAL_UNITS*housing.pref_share.values, TOTAL_UNITS)
sb, dfb, taxb = evaluate(baseline_units, '偏好比例baseline')

# 方案II：整数多目标。先最大化税前单位利润与满意度，同时约束总套数为方案I规模、容积率、上下限。
# 为满足ROI，税后核算非线性，采用若干满意度偏差上限下的线性利润优化，再精确核算选ROI最高且匹配较好的方案。
area_far = (housing.area*housing.far_included).values.astype(float)
profit = housing.profit_before_tax_per_unit.values.astype(float)
sat = housing.satisfaction.values.astype(float)
pref = housing.pref_share.values.astype(float)
mins = housing.min_units.values.astype(float); maxs = housing.max_units.values.astype(float)

candidates=[]
# variables: x(11), u_abs(11) for |x/total - pref| <= u, maximize profit + alpha satisfaction, penalize u
n=11
for lam in [0, 2e5, 5e5, 1e6, 2e6, 5e6, 1e7, 2e7, 5e7]:
    c = np.r_[-profit - lam*sat, np.ones(n)*2e6]  # minimize negative objective + L1 penalty
    integrality = np.r_[np.ones(n), np.zeros(n)]
    lb=np.r_[mins, np.zeros(n)]; ub=np.r_[maxs, np.ones(n)]
    constraints=[]; lows=[]; highs=[]
    # total units equal baseline/方案I规模
    constraints.append(np.r_[np.ones(n), np.zeros(n)]); lows.append(TOTAL_UNITS); highs.append(TOTAL_UNITS)
    # FAR <= max
    constraints.append(np.r_[area_far, np.zeros(n)]); lows.append(-np.inf); highs.append(MAX_FAR*LAND_AREA)
    # abs constraints: x/T - pref <= u ; -(x/T-pref)<=u
    for i in range(n):
        row=np.zeros(2*n); row[i]=1/TOTAL_UNITS; row[n+i]=-1
        constraints.append(row); lows.append(-np.inf); highs.append(pref[i])
        row=np.zeros(2*n); row[i]=-1/TOTAL_UNITS; row[n+i]=-1
        constraints.append(row); lows.append(-np.inf); highs.append(-pref[i])
    res=milp(c=c, integrality=integrality, bounds=Bounds(lb,ub), constraints=LinearConstraint(np.vstack(constraints), np.array(lows), np.array(highs)), options={'time_limit':60, 'mip_rel_gap':1e-6})
    if res.success:
        x=np.rint(res.x[:n]).astype(int)
        summ, dfx, taxx = evaluate(x, f'候选II_lam_{lam:g}')
        summ['lambda']=lam; summ['units_vector']=x.tolist()
        candidates.append((summ, dfx, taxx))
if not candidates:
    raise RuntimeError('MILP failed for all candidates')
# 选择：ROI优先达标，其次满意匹配好；若均达标则取match_l1较低且ROI高
cand_df=pd.DataFrame([c[0] for c in candidates]).sort_values(['roi_success','match_l1','roi'], ascending=[False, True, False])
best_label=cand_df.iloc[0]['label']
s2, df2, tax2 = next(c for c in candidates if c[0]['label']==best_label)
s2['label']='方案II'; df2['label']='方案II'; tax2['label']='方案II'

# 如果方案II未达25%，寻找价格/成本调整情景；如果已达，也做安全裕度与调整阈值分析。
def evaluate_adjusted(price_factor=1.0, cost_factor=1.0, units=None, label='调整'):
    global housing
    old=housing.copy()
    housing['price']=old['price']*price_factor
    housing['unit_cost']=old['unit_cost']*cost_factor
    housing['revenue_per_unit']=housing.area*housing.price
    housing['build_cost_per_unit']=housing.area*housing.unit_cost
    housing['profit_before_tax_per_unit']=housing.revenue_per_unit-housing.build_cost_per_unit
    res=evaluate(df2.units.values if units is None else units, label)
    housing=old
    return res
scenarios=[]
for pf in np.linspace(0.92,1.12,41):
    summ,_,_=evaluate_adjusted(price_factor=float(pf), label=f'售价系数{pf:.3f}')
    scenarios.append(dict(type='price_factor', factor=float(pf), roi=summ['roi'], net_profit=summ['net_profit'], success=summ['roi_success']))
for cf in np.linspace(0.88,1.08,41):
    summ,_,_=evaluate_adjusted(cost_factor=float(cf), label=f'成本系数{cf:.3f}')
    scenarios.append(dict(type='cost_factor', factor=float(cf), roi=summ['roi'], net_profit=summ['net_profit'], success=summ['roi_success']))
scen=pd.DataFrame(scenarios)
price_need=scen[(scen.type=='price_factor') & (scen.success)].factor.min() if any((scen.type=='price_factor') & (scen.success)) else np.nan
cost_need=scen[(scen.type=='cost_factor') & (scen.success)].factor.max() if any((scen.type=='cost_factor') & (scen.success)) else np.nan

# 输出表格
summary_df=pd.DataFrame([s1, sb, s2])
summary_df.to_csv(TAB/'方案核算汇总.csv', index=False, encoding='utf-8-sig')
df1.to_csv(TAB/'方案I_房型明细.csv', index=False, encoding='utf-8-sig')
dfb.to_csv(TAB/'baseline_房型明细.csv', index=False, encoding='utf-8-sig')
df2.to_csv(TAB/'方案II_房型明细.csv', index=False, encoding='utf-8-sig')
pd.concat([tax1,taxb,tax2]).to_csv(TAB/'土地增值税分组核算.csv', index=False, encoding='utf-8-sig')
cand_df.to_csv(TAB/'方案II候选比较.csv', index=False, encoding='utf-8-sig')
scen.to_csv(TAB/'投资回报率敏感性.csv', index=False, encoding='utf-8-sig')

# 图表
plt.figure(figsize=(10,5))
x=np.arange(n); width=0.25
plt.bar(x-width, df1.units, width, label='方案I')
plt.bar(x, baseline_units, width, label='偏好baseline')
plt.bar(x+width, df2.units, width, label='方案II')
plt.xticks(x, housing.name, rotation=45); plt.ylabel('套数'); plt.title('各方案房型套数对比'); plt.legend(); plt.tight_layout()
plt.savefig(FIG/'问题2_房型套数对比.png', dpi=300, bbox_inches='tight'); plt.close()

plt.figure(figsize=(8,5))
vals=[s1['far'], sb['far'], s2['far']]
plt.bar(['方案I','baseline','方案II'], vals, color=['#779ECB','#F4B183','#82C91E'])
plt.axhline(MAX_FAR, color='r', linestyle='--', label=f'容积率上限{MAX_FAR}')
plt.ylabel('容积率'); plt.title('容积率核算与约束检验'); plt.legend(); plt.tight_layout()
plt.savefig(FIG/'问题1_容积率核算.png', dpi=300, bbox_inches='tight'); plt.close()

plt.figure(figsize=(8,5))
plt.bar(['方案I','baseline','方案II'], [s1['roi']*100, sb['roi']*100, s2['roi']*100], color=['#779ECB','#F4B183','#82C91E'])
plt.axhline(25, color='r', linestyle='--', label='成功阈值25%')
plt.ylabel('投资回报率(%)'); plt.title('投资回报率对比'); plt.legend(); plt.tight_layout()
plt.savefig(FIG/'问题3_投资回报率对比.png', dpi=300, bbox_inches='tight'); plt.close()

plt.figure(figsize=(8,5))
for typ, lab in [('price_factor','售价调整'),('cost_factor','成本调整')]:
    tmp=scen[scen.type==typ]
    plt.plot(tmp.factor, tmp.roi*100, marker='o', markersize=3, label=lab)
plt.axhline(25,color='r',linestyle='--',label='25%阈值')
plt.xlabel('调整系数'); plt.ylabel('投资回报率(%)'); plt.title('投资回报率敏感性分析'); plt.legend(); plt.tight_layout()
plt.savefig(FIG/'问题3_ROI敏感性分析.png', dpi=300, bbox_inches='tight'); plt.close()

plt.figure(figsize=(9,5))
plt.plot(housing.name, housing.pref_share, marker='o', label='参筹偏好归一化份额')
plt.plot(housing.name, df1.units/df1.units.sum(), marker='s', label='方案I供应份额')
plt.plot(housing.name, df2.units/df2.units.sum(), marker='^', label='方案II供应份额')
plt.xticks(rotation=45); plt.ylabel('份额'); plt.title('供应结构与购买意愿匹配'); plt.legend(); plt.tight_layout()
plt.savefig(FIG/'问题2_意愿匹配曲线.png', dpi=300, bbox_inches='tight'); plt.close()

# contracts & frozen numbers
frozen = {
    'schema_version':'1.0','generated_by':'2015D_complete_solution.py',
    'constants': {'land_area':LAND_AREA,'land_cost':LAND_COST,'max_far':MAX_FAR,'transfer_tax_rate':TRANSFER_TAX_RATE,'roi_threshold':ROI_THRESHOLD},
    'plan1': s1, 'baseline': sb, 'plan2': s2,
    'plan2_units': {housing.name.iloc[i]: int(df2.units.iloc[i]) for i in range(n)},
    'tax': {'plan1': tax1.to_dict(orient='records'), 'plan2': tax2.to_dict(orient='records')},
    'adjustment': {'price_factor_min_to_25pct_roi': None if pd.isna(price_need) else float(price_need),
                   'cost_factor_max_for_25pct_roi': None if pd.isna(cost_need) else float(cost_need),
                   'plan2_already_success': bool(s2['roi_success'])},
    'sources': {'tables_dir':'tables','figures_dir':'图表','code':'代码/2015D_complete_solution.py'}
}
(OUT/'frozen_numbers.json').write_text(json.dumps(clean_json(frozen), ensure_ascii=False, indent=2), encoding='utf-8')
(CON/'model_results.json').write_text(json.dumps(clean_json({'summary':summary_df.to_dict(orient='records'),'plan2_units':frozen['plan2_units']}), ensure_ascii=False, indent=2), encoding='utf-8')
(CON/'metrics.json').write_text(json.dumps(clean_json({'roi':[{'label':r['label'],'roi':r['roi']} for _,r in summary_df.iterrows()], 'match_l1':[{'label':r['label'],'match_l1':r['match_l1']} for _,r in summary_df.iterrows()]}), ensure_ascii=False, indent=2), encoding='utf-8')
(CON/'conclusions.json').write_text(json.dumps({
    'Q1': f"方案I容积率{s1['far']:.4f}，土地增值税{s1['lvat']/1e8:.4f}亿元，ROI={s1['roi']*100:.2f}%", 
    'Q2': f"方案II套数向高满意房型倾斜，L1偏差由方案I的{s1['match_l1']:.4f}降至{s2['match_l1']:.4f}，ROI={s2['roi']*100:.2f}%", 
    'Q3': f"方案II{'达到' if s2['roi_success'] else '未达到'}25%成功阈值；售价阈值系数{price_need}，成本阈值系数{cost_need}"}, ensure_ascii=False, indent=2), encoding='utf-8')
(CON/'problem_analysis.json').write_text(json.dumps({'schema_version':'1.0','questions':[
    {'id':'Q1','task':'核算方案I成本收益、容积率和土地增值税','type':'会计核算/评价'},
    {'id':'Q2','task':'按参筹者意愿重新设计方案II并核算','type':'整数规划/多目标优化'},
    {'id':'Q3','task':'判断ROI是否达到25%，必要时调整','type':'敏感性与情景分析'}]}, ensure_ascii=False, indent=2), encoding='utf-8')
(CON/'model_route.json').write_text(json.dumps({'schema_version':'1.0','route':{
    'Q1':'按房型收入、建安成本、容积率面积、两类土地增值税累进税率核算',
    'Q2':'偏好比例投影baseline + 整数线性规划，多目标平衡税前利润、满意度和偏好L1偏差，精确税后核算筛选',
    'Q3':'以25% ROI为门槛，对售价和成本系数做单因素敏感性分析'}}, ensure_ascii=False, indent=2), encoding='utf-8')
# QA preflight/reference notes
(QA/'preflight_report.md').write_text(f"""# 输入资产预检报告\n\n- 题目目录：{ROOT.parent}\n- 原始文件：题面DOC、附件1 DOC、附件2 PDF、附件3 PDF均已复制到 `支撑材料/数据/`。\n- 题面可读性：antiword/pdftotext 已提取文本到 `references/extracted_text/`。\n- 附件分类：附件1为原始数据；附件2/3为税收政策说明；未发现结果模板。\n- 旧产物：本次新建 `支撑材料/`，结果以本目录内 contracts/results/tables 为准。\n""", encoding='utf-8')
(REF/'external_resource_notes.md').write_text("""# 外部与知识库参考记录\n\n- IMA 数学建模2026知识库检索：`2015D 众筹筑屋 规划 方案 土地增值税`、`土地增值税 优化 房型`、`房地产 投资回报率 规划 优化`、`众筹筑屋`、`2015 D题`，返回结果为空。\n- 本题采用附件2《中华人民共和国土地增值税暂行条例》中的四级超率累进税率，结合附件1房型、成本、售价、约束与满意比例建立模型。\n- 方法参考来自通用整数规划、房地产土地增值税核算规则和数模论文门控流程，未使用 SkillHub。\n""", encoding='utf-8')
# readme
(ROOT/'README.md').write_text(f"""# 2015D 众筹筑屋规划方案设计支撑材料\n\n## 运行说明\n\n```bash\ncd '{ROOT.as_posix()}'\npython 代码/2015D_complete_solution.py\ncd 论文 && xelatex -interaction=nonstopmode 论文.tex\n```\n\n## 主要输出\n- `论文/论文.pdf`：正式论文\n- `results/frozen_numbers.json`：冻结数字\n- `tables/`：方案核算与优化结果表\n- `图表/`：论文图表\n- `contracts/`：题意、模型路线、结果与结论契约\n""", encoding='utf-8')
print('方案I', s1)
print('baseline', sb)
print('方案II', s2)
print('方案II units', frozen['plan2_units'])
print('price_need', price_need, 'cost_need', cost_need)
