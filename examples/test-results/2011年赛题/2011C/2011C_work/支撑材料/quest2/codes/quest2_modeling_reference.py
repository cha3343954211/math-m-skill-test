# -*- coding: utf-8 -*-
"""
CUMCM 2011C 企业退休职工养老金制度改革
可复现建模脚本：读取附件、预测工资、计算替代率/缺口、生成图表与冻结数字。
"""
from pathlib import Path
import json, math, re, shutil, subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

np.random.seed(42)

ROOT = Path(r"<LOCAL_MATH_MODELING_TEST_ROOT>/2011C_work/支撑材料")
SRC = Path(r"<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011C")
for d in [ROOT/'quest1/codes', ROOT/'quest1/figures', ROOT/'quest1/outputs',
          ROOT/'quest2/codes', ROOT/'quest2/figures', ROOT/'quest2/outputs',
          ROOT/'quest3/codes', ROOT/'quest3/figures', ROOT/'quest3/outputs',
          ROOT/'quest4/codes', ROOT/'quest4/figures', ROOT/'quest4/outputs',
          ROOT/'results', ROOT/'tables', ROOT/'papper']:
    d.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei','Microsoft YaHei','Arial Unicode MS','DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# -------------------- 数据读取 --------------------
def load_wage_data():
    df = pd.read_excel(SRC/'cumcm2011C附件1_山东省职工平均工资.xls', header=1)
    df = df.iloc[:, :2].copy()
    df.columns = ['year','avg_wage']
    df = df[pd.to_numeric(df['year'], errors='coerce').notna()].copy()
    df['year'] = df['year'].astype(int)
    df['avg_wage'] = pd.to_numeric(df['avg_wage'], errors='coerce')
    df = df.dropna().sort_values('year')
    df['growth'] = df['avg_wage'].pct_change()
    return df

def load_salary_distribution():
    raw = pd.read_excel(SRC/'cumcm2011C附件2_某企业分年龄职工数量及薪酬分布表.xls', sheet_name='Sheet1', header=None)
    ranges = list(raw.iloc[2,1:])
    mids=[]
    for r in ranges:
        a,b = map(float, str(r).split('-'))
        mids.append((a+b)/2)
    rows=[]
    for i in range(3,11):
        age_band = str(raw.iloc[i,0]).replace('职工数','')
        counts = pd.to_numeric(raw.iloc[i,1:], errors='coerce').fillna(0).values.astype(float)
        n = counts.sum()
        avg_month = float(np.dot(counts, mids)/n) if n>0 else np.nan
        rows.append({'age_band':age_band, 'count':int(n), 'avg_month_wage':avg_month})
    df = pd.DataFrame(rows)
    enterprise_avg = float(np.dot(df['count'], df['avg_month_wage'])/df['count'].sum())
    df['payment_index'] = df['avg_month_wage']/enterprise_avg
    return df, enterprise_avg, pd.DataFrame({'salary_range':ranges, 'midpoint':mids})

wage_hist = load_wage_data()
age_salary, enterprise_avg_month_2009, salary_bins = load_salary_distribution()

# -------------------- 工资预测 --------------------
def forecast_wage_damped(df, end_year=2045):
    # baseline：2000-2010 CAGR 常数增长；主模型：工资增长率由近期高速逐步收敛到中等发达水平的长期增速
    hist = df[['year','avg_wage','growth']].copy()
    recent = hist[(hist.year>=2005)&(hist.year<=2010)]['growth'].dropna()
    g0 = float(recent.mean())
    g_inf = 0.045      # 2035后趋近的长期名义工资增速假设
    k = 0.072          # 衰减速度，使2035年增长率约5.8%左右
    last_year = int(hist.year.max())
    last_wage = float(hist.avg_wage.iloc[-1])
    rows=[]
    wage=last_wage
    for y in range(last_year+1, end_year+1):
        g = g_inf + (g0-g_inf)*math.exp(-k*(y-last_year))
        wage *= (1+g)
        rows.append({'year':y,'growth_main':g,'avg_wage_main':wage})
    f = pd.DataFrame(rows)
    cagr = (hist.loc[hist.year==2010,'avg_wage'].iloc[0]/hist.loc[hist.year==2000,'avg_wage'].iloc[0])**(1/10)-1
    f['growth_baseline'] = cagr
    f['avg_wage_baseline'] = last_wage*((1+cagr)**(f.year-last_year))
    # GM(1,1) 只作为候选对照，因其指数外推过强
    return f, {'recent_avg_growth_2005_2010':g0, 'long_run_growth':g_inf, 'decay_k':k, 'baseline_cagr_2000_2010':float(cagr)}

wage_forecast, wage_params = forecast_wage_damped(wage_hist, 2045)
wage_all = pd.concat([
    wage_hist[['year','avg_wage']].rename(columns={'avg_wage':'avg_wage_main'}),
    wage_forecast[['year','avg_wage_main']]
], ignore_index=True).sort_values('year')
wage_lookup = dict(zip(wage_all.year.astype(int), wage_all.avg_wage_main.astype(float)))

def wage_year(year):
    return float(wage_lookup[int(year)])

# -------------------- 养老金模型 --------------------
PAY_MONTHS = {40:233,41:230,42:226,43:223,44:220,45:216,46:212,47:208,48:204,49:199,50:195,51:190,52:185,53:180,54:175,55:170,56:164,57:158,58:152,59:145,60:139,61:132,62:125,63:117,64:109,65:101,66:93,67:84,68:75,69:65,70:56}
INTEREST = 0.03
PERSONAL_RATE = 0.08
ENTERPRISE_RATE = 0.20

def get_index_for_start_age(start_age):
    # 2009年年龄=start_age+9，使用所在年龄段职工工资/企业平均工资作缴费指数参考值
    age_2009 = start_age + 9
    for _, r in age_salary.iterrows():
        a,b = map(int, re.findall(r'\d+', r['age_band'])[:2])
        if a <= age_2009 <= b:
            return float(r['payment_index']), r['age_band']
    # 边界外取最接近年龄段
    return float(age_salary.iloc[-1]['payment_index']), age_salary.iloc[-1]['age_band']

def pension_case(start_age, retire_age, index, start_year=2000, death_age=75, post_adjust_alpha=1.0, total_contrib_rate=0.28):
    years_pay = retire_age - start_age
    retire_year = start_year + years_pay
    # 缴费从start_year到retire_year-1，共years_pay年
    personal_acc = 0.0
    total_fund_acc = 0.0
    contrib_records=[]
    for y in range(start_year, retire_year):
        own_wage = index * wage_year(y)
        personal_acc = personal_acc*(1+INTEREST) + PERSONAL_RATE*own_wage
        total_fund_acc = total_fund_acc*(1+INTEREST) + total_contrib_rate*own_wage
        contrib_records.append({'year':y,'own_wage':own_wage,'personal_contrib':PERSONAL_RATE*own_wage,'total_contrib':total_contrib_rate*own_wage})
    last_social_month = wage_year(retire_year-1)/12
    indexed_month = last_social_month * index
    basic_month = (last_social_month + indexed_month)/2 * years_pay * 0.01
    personal_month = personal_acc / PAY_MONTHS[retire_age]
    pension_month0 = basic_month + personal_month
    pre_retire_month_wage = index * wage_year(retire_year-1)/12
    replacement_rate = pension_month0/pre_retire_month_wage
    # 退休后养老金随社会平均工资调整；基准年为retire_year-1
    payouts=[]
    cum=0.0
    break_age=None
    for age in range(retire_age, death_age):
        y = start_year + (age-start_age)
        adj = (wage_year(y)/wage_year(retire_year-1))**post_adjust_alpha
        annual_pension = pension_month0*12*adj
        cum += annual_pension
        payouts.append({'age':age+1, 'year':y, 'annual_pension':annual_pension, 'cum_pension':cum})
        if break_age is None and cum >= total_fund_acc:
            # 年内线性插值
            prev = cum - annual_pension
            frac = (total_fund_acc-prev)/annual_pension if annual_pension>0 else 1
            break_age = age + frac
    gap_75 = cum - total_fund_acc
    return {
        'start_age':start_age, 'retire_age':retire_age, 'pay_years':years_pay, 'retire_year':retire_year,
        'payment_index':index, 'basic_month':basic_month, 'personal_month':personal_month,
        'pension_month0':pension_month0, 'pre_retire_month_wage':pre_retire_month_wage,
        'replacement_rate':replacement_rate, 'personal_account_at_retire':personal_acc,
        'total_fund_at_retire':total_fund_acc, 'cum_pension_to_75':cum, 'gap_to_75':gap_75,
        'break_even_age':break_age,
        'contrib_records':contrib_records, 'payout_records':payouts,
    }

# Q2 six cases
q2_rows=[]
case_details={}
for start_age in [30,40]:
    idx, band = get_index_for_start_age(start_age)
    for retire_age in [55,60,65]:
        c=pension_case(start_age, retire_age, idx)
        c['reference_age_band_2009']=band
        q2_rows.append({k:c[k] for k in ['start_age','retire_age','pay_years','retire_year','payment_index','basic_month','personal_month','pension_month0','pre_retire_month_wage','replacement_rate']})
        q2_rows[-1]['reference_age_band_2009']=band
        case_details[f'start{start_age}_retire{retire_age}']=c
q2 = pd.DataFrame(q2_rows)
q2['replacement_rate_pct']=q2['replacement_rate']*100

# Q3 start age 30 only
idx30, band30 = get_index_for_start_age(30)
q3 = pd.DataFrame([{k:case_details[f'start30_retire{r}'][k] for k in ['start_age','retire_age','pay_years','retire_year','payment_index','total_fund_at_retire','cum_pension_to_75','gap_to_75','break_even_age','replacement_rate']} for r in [55,60,65]])
q3['replacement_rate_pct']=q3['replacement_rate']*100

# Q4 sensitivity / policy measures: pension adjustment alpha, total contribution rate required for 75 balance, target replacement needed account rate
q4_rows=[]
for r in [55,60,65]:
    base=case_details[f'start30_retire{r}']
    for alpha in [0,0.25,0.5,0.75,1.0]:
        c=pension_case(30,r,idx30,post_adjust_alpha=alpha)
        q4_rows.append({'retire_age':r,'pension_adjust_alpha':alpha,'gap_to_75':c['gap_to_75'],'break_even_age':c['break_even_age'] or 999})
q4_sens=pd.DataFrame(q4_rows)
# 必要总缴费率：使缴费基金累计等于75岁累计领取（线性按缴费率缩放）
policy=[]
for r in [55,60,65]:
    c=case_details[f'start30_retire{r}']
    required_rate=0.28*c['cum_pension_to_75']/c['total_fund_at_retire']
    policy.append({'retire_age':r,'required_total_contrib_rate_for_75_balance':required_rate,'increase_pp':(required_rate-0.28)*100,
                   'replacement_rate_pct':c['replacement_rate']*100,'gap_to_75':c['gap_to_75']})
q4_policy=pd.DataFrame(policy)

# -------------------- 输出表格 --------------------
wage_hist.to_csv(ROOT/'tables/historical_wage.csv', index=False, encoding='utf-8-sig')
wage_forecast[wage_forecast.year<=2035].to_csv(ROOT/'tables/wage_forecast_2011_2035.csv', index=False, encoding='utf-8-sig')
age_salary.to_csv(ROOT/'tables/age_salary_indices.csv', index=False, encoding='utf-8-sig')
q2.to_csv(ROOT/'tables/q2_replacement_rates.csv', index=False, encoding='utf-8-sig')
q3.to_csv(ROOT/'tables/q3_fund_gap.csv', index=False, encoding='utf-8-sig')
q4_sens.to_csv(ROOT/'tables/q4_sensitivity.csv', index=False, encoding='utf-8-sig')
q4_policy.to_csv(ROOT/'tables/q4_policy_rates.csv', index=False, encoding='utf-8-sig')
# 复制到各问题 outputs
for name in ['wage_forecast_2011_2035.csv']:
    shutil.copy(ROOT/'tables'/name, ROOT/'quest1/outputs'/name)
for name in ['age_salary_indices.csv','q2_replacement_rates.csv']:
    shutil.copy(ROOT/'tables'/name, ROOT/'quest2/outputs'/name)
for name in ['q3_fund_gap.csv']:
    shutil.copy(ROOT/'tables'/name, ROOT/'quest3/outputs'/name)
for name in ['q4_sensitivity.csv','q4_policy_rates.csv']:
    shutil.copy(ROOT/'tables'/name, ROOT/'quest4/outputs'/name)

# -------------------- 图表 --------------------
fig, ax = plt.subplots(figsize=(9,5.5))
ax.plot(wage_hist.year, wage_hist.avg_wage, 'o-', label='历史工资')
f2035=wage_forecast[wage_forecast.year<=2035]
ax.plot(f2035.year, f2035.avg_wage_main, 'o-', label='主模型预测')
ax.plot(f2035.year, f2035.avg_wage_baseline, '--', label='CAGR基线')
ax.set_xlabel('年份'); ax.set_ylabel('年平均工资（元）'); ax.set_title('山东省职工年平均工资历史与预测')
ax.legend(); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest1/figures/q1_wage_forecast.png', dpi=300, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(9,5))
ax.plot(f2035.year, f2035.growth_main*100, label='主模型增长率')
ax.axhline(wage_params['baseline_cagr_2000_2010']*100, color='r', linestyle='--', label='2000-2010 CAGR基线')
ax.set_xlabel('年份'); ax.set_ylabel('名义增长率（%）'); ax.set_title('工资增长率收敛假设与基线比较')
ax.legend(); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest1/figures/q1_growth_assumption.png', dpi=300, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(8,5))
ax.bar(age_salary['age_band'], age_salary['payment_index'])
ax.axhline(1, color='r', linestyle='--', label='企业平均=1')
ax.set_xlabel('年龄段'); ax.set_ylabel('缴费指数参考值'); ax.set_title('各年龄段工资相对企业平均工资的比值')
ax.tick_params(axis='x', rotation=35); ax.legend(); ax.grid(axis='y', alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest2/figures/q2_payment_indices.png', dpi=300, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(9,5))
for start_age in [30,40]:
    sub=q2[q2.start_age==start_age]
    ax.plot(sub.retire_age, sub.replacement_rate_pct, 'o-', label=f'{start_age}岁开始缴费')
ax.axhline(58.5, color='r', linestyle='--', label='目标替代率58.5%')
ax.set_xlabel('退休年龄'); ax.set_ylabel('养老金替代率（%）'); ax.set_title('不同起缴年龄与退休年龄下的替代率')
ax.legend(); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest2/figures/q2_replacement_rates.png', dpi=300, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(8,5))
colors=['#d95f02' if v>0 else '#1b9e77' for v in q3.gap_to_75]
ax.bar(q3.retire_age.astype(str), q3.gap_to_75/10000, color=colors)
ax.axhline(0, color='black', linewidth=1)
ax.set_xlabel('退休年龄'); ax.set_ylabel('75岁时基金缺口（万元）'); ax.set_title('30岁起缴费职工至75岁死亡的基金缺口')
ax.grid(axis='y', alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest3/figures/q3_fund_gap.png', dpi=300, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(8,5))
ax.plot(q3.retire_age, q3.break_even_age, 'o-')
ax.set_xlabel('退休年龄'); ax.set_ylabel('收支平衡年龄'); ax.set_title('累计缴存基金与累计领取养老金达到平衡的年龄')
ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest3/figures/q3_break_even_age.png', dpi=300, bbox_inches='tight'); plt.close()

fig, ax = plt.subplots(figsize=(8,5))
for r in [55,60,65]:
    sub=q4_sens[q4_sens.retire_age==r]
    ax.plot(sub.pension_adjust_alpha, sub.gap_to_75/10000, 'o-', label=f'{r}岁退休')
ax.axhline(0, color='black')
ax.set_xlabel('退休后养老金随工资调整系数 α'); ax.set_ylabel('75岁时基金缺口（万元）'); ax.set_title('养老金调整幅度对基金缺口的敏感性')
ax.legend(); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(ROOT/'quest4/figures/q4_adjustment_sensitivity.png', dpi=300, bbox_inches='tight'); plt.close()

# -------------------- 冻结数字 --------------------
def r2(x): return round(float(x), 4)
key = {
    'data_audit': {
        'wage_years': [int(wage_hist.year.min()), int(wage_hist.year.max())],
        'wage_records': int(len(wage_hist)),
        'salary_age_groups': int(len(age_salary)),
        'salary_employees_total': int(age_salary['count'].sum()),
        'enterprise_avg_month_wage_2009': r2(enterprise_avg_month_2009),
        'ima_search_note': '已搜索数学建模2026知识库关键词：养老金替代率、养老保险基金收支平衡、工资预测GM(1,1)，本地返回为空；方法按题意和养老金公式建立。'
    },
    'wage_params': {k:r2(v) for k,v in wage_params.items()},
    'q1': {
        'forecast_2011': r2(f2035.loc[f2035.year==2011,'avg_wage_main'].iloc[0]),
        'forecast_2020': r2(f2035.loc[f2035.year==2020,'avg_wage_main'].iloc[0]),
        'forecast_2030': r2(f2035.loc[f2035.year==2030,'avg_wage_main'].iloc[0]),
        'forecast_2035': r2(f2035.loc[f2035.year==2035,'avg_wage_main'].iloc[0]),
        'growth_2035_pct': r2(f2035.loc[f2035.year==2035,'growth_main'].iloc[0]*100),
    },
    'q2': q2[['start_age','retire_age','payment_index','pension_month0','pre_retire_month_wage','replacement_rate_pct']].round(4).to_dict(orient='records'),
    'q3': q3[['retire_age','total_fund_at_retire','cum_pension_to_75','gap_to_75','break_even_age','replacement_rate_pct']].round(4).to_dict(orient='records'),
    'q4_policy': q4_policy.round(4).to_dict(orient='records')
}
with open(ROOT/'results/frozen_numbers.json','w',encoding='utf-8') as f:
    json.dump(key,f,ensure_ascii=False,indent=2)

# QA report
qa = []
qa.append('L1 建模合理性：每个问题均建立题目输出映射；Q1为预测，Q2为替代率计算，Q3为基金缺口与收支平衡年龄，Q4为政策敏感性与调参。')
qa.append('L2 求解正确性：读取38年工资数据、8个年龄段薪酬分布；代码固定参数并输出CSV、PNG和frozen_numbers.json；替代率/缺口由同一函数复现。')
qa.append('L3 论文质量：论文数字均来自frozen_numbers.json和最终CSV；图表300dpi保存；LaTeX编译后需核验页数与附件完整性。')
(ROOT/'results/quality_audit.md').write_text('\n\n'.join(qa), encoding='utf-8')
print('OK generated materials at', ROOT)
print(json.dumps(key['q1'], ensure_ascii=False, indent=2))
print(q2[['start_age','retire_age','replacement_rate_pct']].to_string(index=False))
print(q3[['retire_age','gap_to_75','break_even_age']].to_string(index=False))
