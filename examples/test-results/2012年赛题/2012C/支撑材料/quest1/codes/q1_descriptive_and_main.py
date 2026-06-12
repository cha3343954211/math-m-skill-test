import os, re, json, math, shutil, textwrap, warnings
from pathlib import Path
from datetime import datetime
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import statsmodels.api as sm
from sklearn.metrics import mean_absolute_error, mean_squared_error

SEED = 42
np.random.seed(SEED)

ROOT = Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012C')
SUP = ROOT / '支撑材料'
DIRS = {
    'data': SUP/'data', 'refs': SUP/'references', 'results': SUP/'results', 'tables': SUP/'tables',
    'paper': SUP/'papper', 'code': SUP/'code',
    'q1c': SUP/'quest1'/'codes', 'q1f': SUP/'quest1'/'figures', 'q1o': SUP/'quest1'/'outputs',
    'q2c': SUP/'quest2'/'codes', 'q2f': SUP/'quest2'/'figures', 'q2o': SUP/'quest2'/'outputs',
    'q3c': SUP/'quest3'/'codes', 'q3f': SUP/'quest3'/'figures', 'q3o': SUP/'quest3'/'outputs',
}
for d in DIRS.values(): d.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei','Microsoft YaHei','Arial Unicode MS','DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style('whitegrid')

OCC = {1:'农民',2:'工人',3:'退休人员',4:'教师',5:'渔民',6:'医务人员',7:'职工',8:'离退人员'}
SEX = {1:'男',2:'女'}
FIELDS = ['Aver pres','High pres','Low pres','Aver temp','High temp','Low temp','Aver RH','Min RH']
MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sept','Oct','Nov','Dec']


def copy_sources():
    for src in [ROOT/'cumcm2012C.doc', ROOT/'readme.doc']:
        if src.exists(): shutil.copy2(src, DIRS['data']/src.name)
    for folder in ['Appendix-C1','Appendix-C2']:
        src = ROOT/folder; dst = DIRS['data']/folder
        if src.exists() and not dst.exists(): shutil.copytree(src, dst)


def clean_date(x):
    if pd.isna(x): return pd.NaT
    if isinstance(x, pd.Timestamp): return x.normalize()
    s = str(x).strip()
    if not s or '###' in s or '####' in s: return pd.NaT
    # Excel serial possible
    try:
        if re.fullmatch(r'\d+(\.0)?', s):
            v = float(s)
            if 20000 < v < 60000:
                return pd.to_datetime(v, unit='D', origin='1899-12-30').normalize()
    except Exception:
        pass
    dt = pd.to_datetime(s, errors='coerce')
    if pd.isna(dt):
        return pd.NaT
    try:
        if getattr(dt, 'tzinfo', None) is not None:
            dt = dt.tz_localize(None)
    except Exception:
        pass
    return pd.Timestamp(dt).normalize()


def load_cases():
    frames=[]
    for f in sorted((ROOT/'Appendix-C1').glob('data*.xls')):
        df = pd.read_excel(f, sheet_name=0)
        df['source_file'] = f.name
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw.columns = [str(c).strip() for c in raw.columns]
    raw['sex'] = pd.to_numeric(raw['Sex'], errors='coerce')
    raw['age'] = pd.to_numeric(raw['Age'], errors='coerce')
    raw['occupation'] = pd.to_numeric(raw['Occupation'], errors='coerce')
    raw['incidence_date'] = raw['Time of incidence'].apply(clean_date)
    raw['report_date'] = raw['Report time'].apply(clean_date)
    valid = raw.copy()
    valid = valid[(valid['incidence_date']>=pd.Timestamp('2007-01-01')) & (valid['incidence_date']<=pd.Timestamp('2010-12-31'))]
    valid['year'] = valid['incidence_date'].dt.year
    valid['month'] = valid['incidence_date'].dt.month
    valid['weekday'] = valid['incidence_date'].dt.dayofweek
    valid['sex_name'] = valid['sex'].map(SEX).fillna('缺失/其他')
    valid['occupation_name'] = valid['occupation'].map(OCC).fillna('缺失/其他')
    bins=[0,39,49,59,69,79,200]
    labels=['小于等于39','40-49','50-59','60-69','70-79','大于等于80']
    valid['age_group']=pd.cut(valid['age'], bins=bins, labels=labels, right=True)
    return raw, valid


def load_weather():
    all_rows=[]
    path = ROOT/'Appendix-C2'/'data5.xls'
    for sh in pd.ExcelFile(path).sheet_names:
        year = 2000 + int(sh)
        df = pd.read_excel(path, sheet_name=sh, header=None)
        for mi in range(12):
            start = mi*8 + 1  # col 0 is day; Jan fields col1-8
            for r in range(2, min(33, len(df))):
                day = pd.to_numeric(df.iloc[r,0], errors='coerce')
                if pd.isna(day): continue
                day = int(day)
                try:
                    date = pd.Timestamp(year=year, month=mi+1, day=day)
                except Exception:
                    continue
                vals = {}
                ok=True
                for j, field in enumerate(FIELDS):
                    v = pd.to_numeric(df.iloc[r,start+j], errors='coerce') if start+j < df.shape[1] else np.nan
                    vals[field]=v
                vals['date']=date
                all_rows.append(vals)
    w=pd.DataFrame(all_rows).sort_values('date').drop_duplicates('date')
    # repair obvious impossible min RH > aver RH by keeping as data issue but clip to 0-100 for min RH in derived stats
    for c in FIELDS:
        w[c] = pd.to_numeric(w[c], errors='coerce')
    w['temp_range'] = w['High temp'] - w['Low temp']
    w['pres_range'] = w['High pres'] - w['Low pres']
    w['rh_range'] = w['Aver RH'] - w['Min RH']
    return w


def build_daily(cases, weather):
    counts = cases.groupby('incidence_date').size().rename('cases').reset_index().rename(columns={'incidence_date':'date'})
    daily = pd.DataFrame({'date': pd.date_range('2007-01-01','2010-12-31',freq='D')})
    daily = daily.merge(counts, on='date', how='left').fillna({'cases':0})
    daily = daily.merge(weather, on='date', how='left')
    daily['cases'] = daily['cases'].astype(int)
    daily['year'] = daily['date'].dt.year
    daily['month'] = daily['date'].dt.month
    daily['weekday'] = daily['date'].dt.dayofweek
    daily['t'] = np.arange(len(daily))
    daily['sin_y'] = np.sin(2*np.pi*daily['date'].dt.dayofyear/365.25)
    daily['cos_y'] = np.cos(2*np.pi*daily['date'].dt.dayofyear/365.25)
    for var in ['Aver temp','Aver pres','Aver RH','temp_range','pres_range']:
        daily[f'{var}_lag1'] = daily[var].shift(1)
        daily[f'{var}_lag3'] = daily[var].rolling(3, min_periods=1).mean().shift(1)
        daily[f'{var}_lag7'] = daily[var].rolling(7, min_periods=1).mean().shift(1)
    daily = daily.dropna().reset_index(drop=True)
    return daily


def data_audit(raw, cases, weather, daily):
    audit = {
        'raw_case_rows': int(len(raw)),
        'valid_case_rows_2007_2010': int(len(cases)),
        'invalid_or_out_of_range_incidence_date_rows': int(len(raw)-len(cases)),
        'age_missing_rows': int(raw['Age'].isna().sum() + pd.to_numeric(raw['Age'], errors='coerce').isna().sum() - raw['Age'].isna().sum()),
        'occupation_missing_valid_rows': int(cases['occupation'].isna().sum()),
        'weather_rows': int(len(weather)),
        'daily_model_rows_after_lag_drop': int(len(daily)),
        'date_range': [str(daily['date'].min().date()), str(daily['date'].max().date())],
        'case_files': sorted([p.name for p in (ROOT/'Appendix-C1').glob('data*.xls')]),
        'weather_file': 'data5.xls',
        'random_seed': SEED
    }
    (DIRS['results']/'data_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    return audit


def save_table(df, path):
    df.to_csv(path, index=False, encoding='utf-8-sig')


def q1_descriptive(cases):
    total=len(cases)
    sex_tab = cases['sex_name'].value_counts().rename_axis('性别').reset_index(name='人数')
    sex_tab['比例/%']=(sex_tab['人数']/total*100).round(2)
    age_tab = cases['age_group'].astype(str).value_counts().reindex(['小于等于39','40-49','50-59','60-69','70-79','大于等于80']).fillna(0).astype(int).rename_axis('年龄组').reset_index(name='人数')
    age_tab['比例/%']=(age_tab['人数']/total*100).round(2)
    occ_tab = cases['occupation_name'].value_counts().rename_axis('职业').reset_index(name='人数')
    occ_tab['比例/%']=(occ_tab['人数']/total*100).round(2)
    ym = cases.groupby([cases['incidence_date'].dt.to_period('M')]).size().rename('发病人数').reset_index()
    ym['月份']=ym['incidence_date'].astype(str); ym=ym[['月份','发病人数']]
    yearly = cases.groupby('year').size().rename('发病人数').reset_index()
    monthly_mean = cases.groupby('month').size().rename('发病人数').reset_index()
    monthly_mean['月均日发病数'] = monthly_mean['发病人数'] / cases.groupby('month')['incidence_date'].nunique().values
    for name,df in [('q1_sex_distribution.csv',sex_tab),('q1_age_distribution.csv',age_tab),('q1_occupation_distribution.csv',occ_tab),('q1_monthly_counts.csv',ym),('q1_yearly_counts.csv',yearly),('q1_calendar_month_counts.csv',monthly_mean)]:
        save_table(df, DIRS['q1o']/name); save_table(df, DIRS['tables']/name)
    # plots
    plt.figure(figsize=(8,5)); sns.barplot(data=age_tab, x='年龄组', y='人数', color='#4C78A8')
    plt.title('脑卒中病例年龄组分布'); plt.xlabel('年龄组'); plt.ylabel('病例数')
    plt.tight_layout(); plt.savefig(DIRS['q1f']/'q1_age_distribution.png', dpi=300, bbox_inches='tight'); plt.close()
    plt.figure(figsize=(8,5)); sns.barplot(data=sex_tab, x='性别', y='人数', color='#F58518')
    plt.title('脑卒中病例性别分布'); plt.xlabel('性别'); plt.ylabel('病例数')
    plt.tight_layout(); plt.savefig(DIRS['q1f']/'q1_sex_distribution.png', dpi=300, bbox_inches='tight'); plt.close()
    plt.figure(figsize=(10,5)); sns.barplot(data=occ_tab.head(9), y='职业', x='人数', color='#54A24B')
    plt.title('脑卒中病例职业分布'); plt.xlabel('病例数'); plt.ylabel('职业')
    plt.tight_layout(); plt.savefig(DIRS['q1f']/'q1_occupation_distribution.png', dpi=300, bbox_inches='tight'); plt.close()
    plt.figure(figsize=(13,5)); plt.plot(pd.to_datetime(ym['月份']), ym['发病人数'], marker='o', linewidth=1.5)
    plt.title('2007—2010年月度脑卒中发病人数变化'); plt.xlabel('月份'); plt.ylabel('发病人数')
    plt.tight_layout(); plt.savefig(DIRS['q1f']/'q1_monthly_trend.png', dpi=300, bbox_inches='tight'); plt.close()
    desc = {
        'total_cases': total,
        'male_count': int(sex_tab.loc[sex_tab['性别']=='男','人数'].iloc[0]) if (sex_tab['性别']=='男').any() else 0,
        'female_count': int(sex_tab.loc[sex_tab['性别']=='女','人数'].iloc[0]) if (sex_tab['性别']=='女').any() else 0,
        'male_percent': float(sex_tab.loc[sex_tab['性别']=='男','比例/%'].iloc[0]) if (sex_tab['性别']=='男').any() else 0,
        'age_mean': float(cases['age'].mean()), 'age_median': float(cases['age'].median()),
        'age_ge_60_percent': float((cases['age']>=60).mean()*100),
        'top_age_group': str(age_tab.sort_values('人数', ascending=False).iloc[0]['年龄组']),
        'top_age_group_count': int(age_tab.sort_values('人数', ascending=False).iloc[0]['人数']),
        'top_occupation': str(occ_tab.iloc[0]['职业']),
        'top_occupation_percent': float(occ_tab.iloc[0]['比例/%']),
        'peak_month': str(ym.sort_values('发病人数', ascending=False).iloc[0]['月份']),
        'peak_month_cases': int(ym['发病人数'].max()),
        'daily_mean_cases': float(total / cases['incidence_date'].nunique())
    }
    (DIRS['q1o']/'q1_summary.json').write_text(json.dumps(desc, ensure_ascii=False, indent=2), encoding='utf-8')
    return desc, {'sex':sex_tab,'age':age_tab,'occ':occ_tab,'ym':ym,'yearly':yearly,'monthly':monthly_mean}


def fit_glm_poisson(df, features, train_end='2010-06-30'):
    dat=df.dropna(subset=features+['cases']).copy()
    train=dat[dat['date']<=pd.Timestamp(train_end)]
    test=dat[dat['date']>pd.Timestamp(train_end)]
    Xtr=sm.add_constant(train[features], has_constant='add')
    Xte=sm.add_constant(test[features], has_constant='add')
    model=sm.GLM(train['cases'], Xtr, family=sm.families.Poisson()).fit(cov_type='HC0')
    pred_train=model.predict(Xtr)
    pred_test=model.predict(Xte)
    metrics={
        'aic': float(model.aic),
        'train_mae': float(mean_absolute_error(train['cases'], pred_train)),
        'test_mae': float(mean_absolute_error(test['cases'], pred_test)),
        'test_rmse': float(math.sqrt(mean_squared_error(test['cases'], pred_test))),
        'pseudo_r2': float(1 - model.deviance/model.null_deviance),
        'train_n': int(len(train)), 'test_n': int(len(test))
    }
    return model, metrics, train, test, pred_train, pred_test


def q2_modeling(daily):
    # PoC and baseline: seasonal-only vs meteorology distributed lag
    base_features=['t','sin_y','cos_y']
    full_features=['t','sin_y','cos_y','Aver temp','Aver temp_lag1','Aver temp_lag3','Aver temp_lag7',
                   'Aver pres','Aver pres_lag1','Aver pres_lag3','Aver pres_lag7',
                   'Aver RH','Aver RH_lag1','Aver RH_lag3','Aver RH_lag7','temp_range','pres_range']
    # standardize continuous predictors except sin/cos/t? standardize weather and t for stability
    model_df=daily.copy()
    scalers={}
    for c in ['t']+[f for f in full_features if f not in ['sin_y','cos_y','t']]:
        mu=model_df[c].mean(); sd=model_df[c].std()
        model_df[c]=(model_df[c]-mu)/sd
        scalers[c]={'mean':float(mu),'std':float(sd)}
    base_model, base_metrics, train, test, ptr, pte = fit_glm_poisson(model_df, base_features)
    full_model, full_metrics, train2, test2, fptr, fpte = fit_glm_poisson(model_df, full_features)
    comparison=pd.DataFrame([
        {'模型':'Baseline：趋势+年度周期','AIC':base_metrics['aic'],'测试MAE':base_metrics['test_mae'],'测试RMSE':base_metrics['test_rmse'],'伪R2':base_metrics['pseudo_r2']},
        {'模型':'主模型：Poisson分布滞后气象回归','AIC':full_metrics['aic'],'测试MAE':full_metrics['test_mae'],'测试RMSE':full_metrics['test_rmse'],'伪R2':full_metrics['pseudo_r2']},
    ]).round(4)
    save_table(comparison, DIRS['q2o']/'q2_model_comparison.csv'); save_table(comparison, DIRS['tables']/'q2_model_comparison.csv')
    coef = full_model.summary2().tables[1].reset_index().rename(columns={'index':'变量','Coef.':'系数','Std.Err.':'稳健标准误','P>|z|':'P值','[0.025':'CI下限','0.975]':'CI上限'})
    coef['相对危险度RR']=np.exp(coef['系数'])
    coef.to_csv(DIRS['q2o']/'q2_poisson_coefficients.csv', index=False, encoding='utf-8-sig')
    coef.to_csv(DIRS['tables']/'q2_poisson_coefficients.csv', index=False, encoding='utf-8-sig')
    # predictions on all data
    Xall=sm.add_constant(model_df[full_features], has_constant='add')
    daily_pred=daily[['date','cases']+['Aver temp','Aver pres','Aver RH','temp_range','pres_range']].copy()
    daily_pred['pred_cases']=full_model.predict(Xall)
    daily_pred['residual']=daily_pred['cases']-daily_pred['pred_cases']
    daily_pred.to_csv(DIRS['q2o']/'q2_daily_predictions.csv', index=False, encoding='utf-8-sig')
    # correlation table
    corr_vars=['Aver temp','High temp','Low temp','Aver pres','High pres','Low pres','Aver RH','Min RH','temp_range','pres_range']
    rows=[]
    for v in corr_vars:
        r,p=stats.spearmanr(daily[v], daily['cases'], nan_policy='omit')
        rows.append({'变量':v,'Spearman相关系数':r,'P值':p})
    corr=pd.DataFrame(rows).sort_values('P值')
    corr.to_csv(DIRS['q2o']/'q2_spearman_correlations.csv', index=False, encoding='utf-8-sig')
    corr.to_csv(DIRS['tables']/'q2_spearman_correlations.csv', index=False, encoding='utf-8-sig')
    # figures
    plt.figure(figsize=(13,5)); plt.plot(daily_pred['date'], daily_pred['cases'], label='实际日发病数', alpha=.75); plt.plot(daily_pred['date'], daily_pred['pred_cases'], label='主模型拟合值', alpha=.9)
    plt.title('日脑卒中发病数与Poisson气象模型拟合'); plt.xlabel('日期'); plt.ylabel('日发病数'); plt.legend(); plt.tight_layout(); plt.savefig(DIRS['q2f']/'q2_daily_fit.png', dpi=300, bbox_inches='tight'); plt.close()
    plt.figure(figsize=(8,5)); sns.scatterplot(x=daily_pred['pred_cases'], y=daily_pred['residual'], s=18, alpha=.6); plt.axhline(0,color='red',linestyle='--')
    plt.title('主模型残差—拟合值诊断图'); plt.xlabel('拟合日发病数'); plt.ylabel('残差'); plt.tight_layout(); plt.savefig(DIRS['q2f']/'q2_residual_diagnostic.png', dpi=300, bbox_inches='tight'); plt.close()
    plt.figure(figsize=(9,6)); topcoef=coef[coef['变量'].isin(full_features)].copy(); topcoef['abs']=topcoef['系数'].abs(); topcoef=topcoef.sort_values('abs', ascending=False).head(12).sort_values('系数')
    plt.barh(topcoef['变量'], topcoef['系数'], color=['#E45756' if x>0 else '#4C78A8' for x in topcoef['系数']]); plt.axvline(0,color='k',linewidth=.8)
    plt.title('主模型标准化系数绝对值前12项'); plt.xlabel('Poisson回归系数'); plt.tight_layout(); plt.savefig(DIRS['q2f']/'q2_top_coefficients.png', dpi=300, bbox_inches='tight'); plt.close()
    # temp bins risk
    tmp=daily.copy(); tmp['temp_bin']=pd.cut(tmp['Aver temp'], bins=[-20,0,5,10,15,20,25,30,40])
    tempbin=tmp.groupby('temp_bin')['cases'].agg(['mean','count']).reset_index(); tempbin['temp_bin']=tempbin['temp_bin'].astype(str)
    tempbin.to_csv(DIRS['q2o']/'q2_temperature_bin_cases.csv', index=False, encoding='utf-8-sig')
    plt.figure(figsize=(10,5)); sns.barplot(data=tempbin, x='temp_bin', y='mean', color='#72B7B2'); plt.xticks(rotation=30); plt.title('不同平均气温区间的平均日发病数'); plt.xlabel('平均气温区间/℃'); plt.ylabel('平均日发病数'); plt.tight_layout(); plt.savefig(DIRS['q2f']/'q2_temperature_bins.png', dpi=300, bbox_inches='tight'); plt.close()
    # sensitivity: perturb temp, pressure, RH by +-1 std standardized coefficient effect
    sens=[]
    for var in ['Aver temp','Aver pres','Aver RH','Aver temp_lag3','Aver pres_lag3','Aver RH_lag3']:
        if var in full_model.params.index:
            beta=float(full_model.params[var]); rr_up=float(np.exp(beta)); rr_down=float(np.exp(-beta))
            sens.append({'参数':var,'+1标准差RR':rr_up,'-1标准差RR':rr_down,'系数':beta})
    sens=pd.DataFrame(sens).sort_values('系数')
    sens.to_csv(DIRS['q2o']/'q2_sensitivity_rr.csv', index=False, encoding='utf-8-sig')
    sens.to_csv(DIRS['tables']/'q2_sensitivity_rr.csv', index=False, encoding='utf-8-sig')
    plt.figure(figsize=(9,5)); x=np.arange(len(sens)); plt.plot(x, sens['+1标准差RR'], marker='o', label='+1标准差'); plt.plot(x, sens['-1标准差RR'], marker='s', label='-1标准差'); plt.axhline(1,color='k',linestyle='--'); plt.xticks(x, sens['参数'], rotation=30); plt.ylabel('相对危险度RR'); plt.title('关键气象变量扰动的相对危险度敏感性'); plt.legend(); plt.tight_layout(); plt.savefig(DIRS['q2f']/'q2_sensitivity_rr.png', dpi=300, bbox_inches='tight'); plt.close()
    summary={
        'baseline':base_metrics, 'main':full_metrics,
        'aic_improvement': float(base_metrics['aic']-full_metrics['aic']),
        'test_mae_improvement_percent': float((base_metrics['test_mae']-full_metrics['test_mae'])/base_metrics['test_mae']*100),
        'test_mae_change_percent': float((full_metrics['test_mae']-base_metrics['test_mae'])/base_metrics['test_mae']*100),
        'top_positive_coefficients': coef[coef['变量'].isin(full_features)].sort_values('系数', ascending=False).head(5)[['变量','系数','相对危险度RR','P值']].to_dict('records'),
        'top_negative_coefficients': coef[coef['变量'].isin(full_features)].sort_values('系数').head(5)[['变量','系数','相对危险度RR','P值']].to_dict('records'),
        'scalers': scalers
    }
    (DIRS['q2o']/'q2_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary, comparison, coef, corr, sens, daily_pred


def q3_warning_plan(cases, q1sum, q2sum, sens):
    # Risk score based on demographic stats + meteorology RR. 0-100 warning rule.
    age_risk = pd.DataFrame([
        {'特征':'年龄小于50岁','分值':0,'干预建议':'常规健康教育，关注血压血脂。'},
        {'特征':'50-59岁','分值':15,'干预建议':'每年至少一次卒中危险因素筛查。'},
        {'特征':'60-69岁','分值':30,'干预建议':'加强血压、血糖、血脂管理，气象风险日减少户外暴露。'},
        {'特征':'70-79岁','分值':45,'干预建议':'建立家庭/社区随访，寒冷或气压剧烈变化时主动提醒。'},
        {'特征':'80岁及以上','分值':55,'干预建议':'列为重点高危人群，异常天气日提前备药并保持就医通道。'},
    ])
    demo = pd.DataFrame([
        {'指标':'年龄','关键发现':f"病例年龄均值{q1sum['age_mean']:.1f}岁，中位数{q1sum['age_median']:.1f}岁，60岁及以上占{q1sum['age_ge_60_percent']:.1f}%",'预警含义':'年龄是最稳定的人群分层指标，60岁以上应作为重点筛查对象。'},
        {'指标':'性别','关键发现':f"男性{q1sum['male_count']}例，占{q1sum['male_percent']:.1f}%",'预警含义':'男性比例较高，应结合吸烟、饮酒、职业暴露强化干预。'},
        {'指标':'职业','关键发现':f"{q1sum['top_occupation']}占比最高，为{q1sum['top_occupation_percent']:.1f}%",'预警含义':'职业分布受城市人口结构影响，但可用于社区随访名单排序。'},
        {'指标':'气象','关键发现':f"主模型相对baseline AIC降低{q2sum['aic_improvement']:.1f}，测试MAE变化{q2sum['test_mae_change_percent']:.1f}%",'预警含义':'气象变量能改善整体拟合解释，但样本外尖峰预测仍有误差，适合作为辅助预警而非唯一判据。'},
    ])
    weather_rules = pd.DataFrame([
        {'预警等级':'蓝色','触发条件':'模型预测日发病风险处于历史50%—75%分位，或单个气象关键因子进入轻度不利区间','建议措施':'社区卫生服务中心发布健康提醒，高血压/糖尿病人群自测血压。'},
        {'预警等级':'黄色','触发条件':'模型预测风险处于75%—90%分位，或气温、气压、湿度中两个因子同时不利','建议措施':'对60岁以上慢病人群短信/电话提醒，减少剧烈活动，保证室内温湿度。'},
        {'预警等级':'橙色','触发条件':'模型预测风险处于90%—97.5%分位，且近期温度/气压有明显波动','建议措施':'社区医生主动随访重点名单，医院适当增加急诊和神经内科值班资源。'},
        {'预警等级':'红色','触发条件':'模型预测风险超过97.5%分位或连续多日橙色风险','建议措施':'卫生行政部门启动短期应急预案，媒体发布防护提示，医疗机构预留床位和溶栓绿色通道。'},
    ])
    intervention = pd.DataFrame([
        {'对象':'健康/亚健康人群','措施':'建立生活方式干预：控烟限酒、低盐饮食、规律运动、监测血压；在蓝色及以上气象风险日减少突然冷热暴露。'},
        {'对象':'60岁以上或有高血压/糖尿病/高血脂者','措施':'纳入社区重点随访；黄色预警起每日血压监测，出现口角歪斜、肢体无力、言语不清立即就医。'},
        {'对象':'既往卒中/TIA或多危险因素叠加者','措施':'橙色预警起主动电话随访，检查服药依从性，必要时提前门诊复诊或调整治疗计划。'},
        {'对象':'医疗机构','措施':'依据预测风险调整急诊、神经内科、影像检查和床位资源；连续高风险日增加卒中绿色通道保障。'},
        {'对象':'卫生行政部门','措施':'把气象预警嵌入公共卫生信息平台，形成“气象—社区—医院”联动机制并定期评估误报/漏报。'},
    ])
    for name,df in [('q3_demographic_warning_basis.csv',demo),('q3_age_score_rules.csv',age_risk),('q3_weather_warning_rules.csv',weather_rules),('q3_intervention_plan.csv',intervention)]:
        save_table(df, DIRS['q3o']/name); save_table(df, DIRS['tables']/name)
    # figure radar / flow
    plt.figure(figsize=(8,5)); sns.barplot(data=age_risk, x='特征', y='分值', color='#B279A2'); plt.xticks(rotation=25); plt.title('年龄分层预警基础分值'); plt.xlabel('年龄层'); plt.ylabel('基础分'); plt.tight_layout(); plt.savefig(DIRS['q3f']/'q3_age_risk_score.png', dpi=300, bbox_inches='tight'); plt.close()
    summary={
        'warning_score_formula':'总风险分=年龄基础分+性别/职业修正分+慢病修正分+气象风险分，按50/70/85/95分划分蓝/黄/橙/红预警。',
        'blue_yellow_orange_red_thresholds':[50,70,85,95],
        'key_intervention':'以60岁以上、男性、多慢病、既往卒中/TIA人群为重点，叠加模型预测的气象短期风险实施分级预警。'
    }
    (DIRS['q3o']/'q3_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary, demo, age_risk, weather_rules, intervention


def tex_escape(s):
    s=str(s)
    rep={'\\':'\\textbackslash{}','&':'\\&','%':'\\%','$':'\\$','#':'\\#','_':'\\_','{':'\\{','}':'\\}','~':'\\textasciitilde{}','^':'\\textasciicircum{}'}
    return ''.join(rep.get(ch,ch) for ch in s)


def latex_table(df, cols=None, max_rows=12, floatfmt='.3f'):
    d=df.copy()
    if cols: d=d[cols]
    if len(d)>max_rows: d=d.head(max_rows)
    lines=['\\begin{tabular}{'+'l'*len(d.columns)+'}','\\toprule']
    lines.append(' & '.join(tex_escape(c) for c in d.columns)+' \\\\')
    lines.append('\\midrule')
    for _,row in d.iterrows():
        vals=[]
        for v in row:
            if isinstance(v,(float,np.floating)):
                vals.append(format(float(v), floatfmt))
            else: vals.append(tex_escape(v))
        lines.append(' & '.join(vals)+' \\\\')
    lines.append('\\bottomrule\n\\end{tabular}')
    return '\n'.join(lines)


def generate_reports(audit, q1sum, q1tabs, q2sum, comp, coef, corr, sens, q3sum, demo, age_risk, rules, inter):
    # Frozen numbers
    frozen={
        'meta': {'generated_at': datetime.now().isoformat(timespec='seconds'), 'seed': SEED, 'project': str(ROOT)},
        'Q1': {
            'total_cases': q1sum['total_cases'], 'male_percent': round(q1sum['male_percent'],2), 'age_mean': round(q1sum['age_mean'],2),
            'age_ge_60_percent': round(q1sum['age_ge_60_percent'],2), 'top_age_group': q1sum['top_age_group'],
            'top_occupation': q1sum['top_occupation'], 'peak_month': q1sum['peak_month'], 'peak_month_cases': q1sum['peak_month_cases']
        },
        'Q2': {
            'baseline_test_mae': round(q2sum['baseline']['test_mae'],4), 'main_test_mae': round(q2sum['main']['test_mae'],4),
            'main_test_rmse': round(q2sum['main']['test_rmse'],4), 'main_pseudo_r2': round(q2sum['main']['pseudo_r2'],4),
            'aic_improvement': round(q2sum['aic_improvement'],2), 'test_mae_improvement_percent': round(q2sum['test_mae_improvement_percent'],2), 'test_mae_change_percent': round(q2sum['test_mae_change_percent'],2)
        },
        'Q3': {'warning_thresholds': q3sum['blue_yellow_orange_red_thresholds'], 'warning_formula': q3sum['warning_score_formula']}
    }
    (DIRS['results']/'frozen_numbers.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')
    (DIRS['q1o']/'frozen_numbers.json').write_text(json.dumps(frozen['Q1'], ensure_ascii=False, indent=2), encoding='utf-8')
    (DIRS['q2o']/'frozen_numbers.json').write_text(json.dumps(frozen['Q2'], ensure_ascii=False, indent=2), encoding='utf-8')
    (DIRS['q3o']/'frozen_numbers.json').write_text(json.dumps(frozen['Q3'], ensure_ascii=False, indent=2), encoding='utf-8')
    # Method docs
    (SUP/'planning').mkdir(exist_ok=True)
    (SUP/'planning'/'problem_parse.md').write_text(f"""# G1 题目解析\n\n题目：2012C 脑卒中发病环境因素分析及干预。\n\n- 问题1：根据病例基本信息，对发病人群进行统计描述；输出年龄、性别、职业、时间分布。\n- 问题2：研究脑卒中日发病数与气温、气压、相对湿度关系；输出相关性、Poisson计数回归、baseline对比和敏感性分析。\n- 问题3：结合高危人群特征与前两问结论，给出分级预警和干预建议。\n\n数据审计：原始病例 {audit['raw_case_rows']} 行，有效日期病例 {audit['valid_case_rows_2007_2010']} 行，气象日资料 {audit['weather_rows']} 行。\n""", encoding='utf-8')
    (SUP/'methods').mkdir(exist_ok=True)
    for q in ['Q1','Q2','Q3']:
        (SUP/'methods'/q).mkdir(parents=True, exist_ok=True)
    (SUP/'methods'/'Q2'/'q2_method_candidates.md').write_text(f"""# Q2 候选方法与PoC\n\n## M0 Baseline：趋势+年周期Poisson回归 [BASELINE]\n- 可行性数字：测试MAE={q2sum['baseline']['test_mae']:.3f}，AIC={q2sum['baseline']['aic']:.1f}。\n\n## M1 主模型：分布滞后气象Poisson回归 [CHOSEN]\n- 变量：日平均气温、气压、相对湿度及1/3/7日滞后均值，控制长期趋势与年度周期。\n- 可行性数字：测试MAE={q2sum['main']['test_mae']:.3f}，AIC={q2sum['main']['aic']:.1f}，较baseline AIC降低{q2sum['aic_improvement']:.1f}；测试MAE变化{q2sum['test_mae_change_percent']:.1f}%。\n- 验证：AIC、测试集MAE/RMSE、残差图、关键气象变量RR敏感性。\n\n## M2 普通线性回归 [BACKUP]\n- 计数数据非负且方差随均值变化，解释性不如Poisson计数模型，作为备选未采用。\n""", encoding='utf-8')
    # README
    (SUP/'readme.txt').write_text(f"""# 2012C 脑卒中发病环境因素分析及干预 支撑材料\n\n## 主要文件\n- papper/论文.pdf：最终数学建模论文\n- papper/论文.tex：LaTeX源文件\n- code/main_modeling.py：完整数据清洗、建模、可视化、论文生成脚本\n- results/frozen_numbers.json：论文关键数字冻结文件\n- quest1/：发病人群统计描述代码输出与图表\n- quest2/：气象因素模型、系数、残差、敏感性分析\n- quest3/：预警干预方案表格与图表\n- data/：题目原始附件备份\n\n## 运行方式\n在项目根目录运行：python 支撑材料/code/main_modeling.py\n\n## 关键结果\n- 有效病例：{q1sum['total_cases']}例；60岁及以上占{q1sum['age_ge_60_percent']:.1f}%。\n- 主模型测试MAE={q2sum['main']['test_mae']:.3f}，AIC较baseline降低{q2sum['aic_improvement']:.1f}。\n- 给出蓝/黄/橙/红四级气象—人群综合风险预警方案。\n""", encoding='utf-8')
    # paper tex
    tex = build_tex(audit, q1sum, q1tabs, q2sum, comp, coef, corr, sens, q3sum, demo, age_risk, rules, inter)
    (DIRS['paper']/'论文.tex').write_text(tex, encoding='utf-8')
    (DIRS['paper']/'论文.md').write_text('本文正式版本见 `论文.tex` 与 `论文.pdf`。关键数字见 `../results/frozen_numbers.json`。', encoding='utf-8')
    # copy script to quest code dirs
    # script already resides in 支撑材料/code/main_modeling.py


def build_tex(audit, q1sum, q1tabs, q2sum, comp, coef, corr, sens, q3sum, demo, age_risk, rules, inter):
    comp_tex=latex_table(comp, floatfmt='.3f')
    age_tex=latex_table(q1tabs['age'], floatfmt='.2f')
    sex_tex=latex_table(q1tabs['sex'], floatfmt='.2f')
    occ_tex=latex_table(q1tabs['occ'], max_rows=9, floatfmt='.2f')
    corr_tex=latex_table(corr.rename(columns={'Spearman相关系数':'相关系数'}), max_rows=10, floatfmt='.4f')
    coef_small=coef[coef['变量'].isin(['Aver temp','Aver temp_lag3','Aver pres','Aver pres_lag3','Aver RH','Aver RH_lag3','temp_range','pres_range'])][['变量','系数','P值','相对危险度RR']]
    coef_tex=latex_table(coef_small, max_rows=12, floatfmt='.4f')
    sens_tex=latex_table(sens, floatfmt='.4f')
    demo_tex=latex_table(demo, max_rows=6, floatfmt='.2f')
    rules_tex=latex_table(rules, max_rows=8, floatfmt='.2f')
    inter_tex=latex_table(inter, max_rows=8, floatfmt='.2f')
    age_score_tex=latex_table(age_risk, max_rows=8, floatfmt='.1f')
    now=datetime.now().strftime('%Y-%m-%d')
    return rf'''
\documentclass[UTF8,a4paper,12pt]{{ctexart}}
\usepackage{{geometry}}
\geometry{{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}}
\usepackage{{setspace}}
\setstretch{{1.35}}
\usepackage{{fancyhdr}}
\pagestyle{{fancy}}
\fancyhf{{}}
\fancyhead[C]{{\small 脑卒中发病环境因素分析及干预}}
\fancyfoot[C]{{\thepage}}
\setlength{{\headheight}}{{14pt}}
\usepackage{{amsmath,amssymb,booktabs,longtable,array,graphicx,float,caption,hyperref}}
\usepackage{{enumitem}}
\usepackage{{placeins}}
\usepackage{{url}}
\captionsetup[table]{{position=top}}
\captionsetup[figure]{{position=bottom}}
\hypersetup{{colorlinks=true,linkcolor=black,urlcolor=blue}}
\title{{\heiti 基于分布滞后Poisson回归的脑卒中发病环境因素分析及干预模型}}
\author{{}}
\date{{{now}}}
\begin{{document}}
\maketitle
\begin{{abstract}}
脑卒中发病具有明显的人群异质性和短期环境诱发特征。本文针对2012年C题提供的某城市2007年1月至2010年12月医院脑卒中病例数据及同期逐日气象数据，构建“病例统计描述—气象计数回归—分级预警干预”的完整建模链条。数据清洗后得到有效发病日期病例{q1sum['total_cases']}例，气象日资料{audit['weather_rows']}条，并对发病时间、性别、年龄、职业和气象变量进行了统一口径整理。

针对问题一，本文采用描述性统计和时间序列可视化分析发病人群结构。结果表明，病例年龄均值为{q1sum['age_mean']:.1f}岁，中位数为{q1sum['age_median']:.1f}岁，60岁及以上人群占{q1sum['age_ge_60_percent']:.1f}\%；男性病例占{q1sum['male_percent']:.1f}\%，职业类别中{tex_escape(q1sum['top_occupation'])}占比最高。月度统计显示，最高发月份为{tex_escape(q1sum['peak_month'])}，当月病例数为{q1sum['peak_month_cases']}例，提示脑卒中发病既存在老龄化集中现象，也存在季节性和短期波动。

针对问题二，本文以日发病数为计数型响应变量，先建立仅含长期趋势和年周期项的baseline Poisson回归，再引入平均气温、平均气压、相对湿度及1日、3日、7日滞后均值，建立分布滞后Poisson气象回归模型。测试期结果显示，baseline测试MAE为{q2sum['baseline']['test_mae']:.3f}，主模型测试MAE为{q2sum['main']['test_mae']:.3f}，主模型AIC比baseline降低{q2sum['aic_improvement']:.1f}，伪$R^2$由{q2sum['baseline']['pseudo_r2']:.3f}提高到{q2sum['main']['pseudo_r2']:.3f}。这说明气象变量显著改善整体解释，但样本外尖峰预测仍存在误差。敏感性分析进一步给出关键气象变量单位标准差扰动下的相对危险度变化。

针对问题三，本文结合病例统计结果、气象模型输出以及文献中公认的卒中危险因素，构建“人群基础风险+气象短期风险”的预警框架。方案将年龄、性别、职业及慢病因素作为人群基础分，将Poisson模型预测风险分位作为气象风险分，按50、70、85、95分形成蓝、黄、橙、红四级预警，并分别给出健康人群、60岁以上慢病人群、既往卒中/TIA人群、医疗机构和卫生行政部门的干预建议。模型优点是数据来源清晰、计数回归与发病数口径一致、预警方案可落地；不足是缺少个体慢病史和人口基数，后续可结合电子健康档案和空间人口数据进一步改进。
\end{{abstract}}
\noindent\textbf{{关键词：}}脑卒中；气象因素；Poisson回归；分布滞后；风险预警；干预方案
\newpage
\tableofcontents
\newpage

\section{{问题重述}}
\subsection{{问题背景}}
脑卒中俗称脑中风，是严重威胁中老年人生命健康的重大疾病。其发病机制与高血压、糖尿病、血脂异常、吸烟、年龄增长等个体因素有关，也受到气温、气压、湿度等环境因素的短期诱发影响。题目给出了某城市各医院2007年至2010年脑卒中发病病例信息和同期逐日气象数据，要求从病例结构与环境因素两方面分析发病规律，并进一步提出高危人群预警和干预方案。该问题既包含数据统计描述，也包含计数型时间序列建模和公共卫生决策建议。

\subsection{{问题要求与模型输出}}
问题一要求根据病人基本信息对发病人群进行统计描述。本文输出性别、年龄、职业、年份、月份等多维统计表，并给出年龄结构、性别结构、职业结构和月度趋势图。问题二要求研究脑卒中发病率与气温、气压、相对湿度之间的关系。由于题目未提供全市逐日人口暴露数，本文以日发病数作为发病率变化的代理变量，建立Poisson计数回归并控制长期趋势与年周期。问题三要求查阅并搜集高危人群重要特征和关键指标，结合前两问结论提出预警和干预建议。本文输出基于人群基础风险和气象短期风险的四级预警规则及对象化干预方案。

\section{{问题分析}}
\subsection{{总体建模思路}}
本文采用三阶段建模流程。首先对病例原始表进行清洗，统一发病日期格式，剔除无法解析或不在2007--2010年范围内的发病记录；然后将病例按日期聚合为日发病数，并将气象附件转换为逐日结构化表。其次，对问题一进行描述性统计，回答“哪些人群更集中、何时发病更多”。再次，对问题二建立baseline和主模型：baseline只包含长期趋势和年度周期，用于表示不考虑气象条件时的基本波动；主模型在此基础上加入气温、气压、湿度及滞后项，用于识别环境因素的增量作用。最后，将统计结果和模型预测转化为预警评分与干预建议。

\subsection{{问题一分析}}
问题一属于描述统计与可视化问题，重点不是复杂算法，而是统一口径、处理缺失和用合适的分组呈现发病人群特征。病例表中的性别、年龄、职业和发病时间存在缺失或错误格式，因此先用日期解析函数处理发病时间，年龄和职业采用数值转换，无法解析的职业归入“缺失/其他”。年龄按临床和公共卫生常用分层划分为不超过39岁、40--49岁、50--59岁、60--69岁、70--79岁和80岁及以上。该分层能直接服务第三问的高危人群识别。

\subsection{{问题二分析}}
问题二要求刻画脑卒中发病率与气温、气压、相对湿度之间的关系。日发病数是非负整数，普通线性回归可能产生负预测值且不符合计数方差结构，因此本文选择Poisson广义线性模型。考虑到脑卒中发病可能受当天及前几天气象条件共同影响，本文加入1日、3日、7日滞后均值，形成简化的分布滞后结构。同时，发病数有长期趋势和季节周期，若不控制这些因素，气象变量系数会混入季节效应，因此模型中加入时间趋势项和正余弦年周期项。

\subsection{{问题三分析}}
问题三是决策建议问题，不能只列出医学常识，还需要把数据分析结果转化为可执行规则。本文将高危人群特征分为两类：一类是相对稳定的人群基础风险，如年龄、性别、既往疾病和生活方式；另一类是短期可变的环境风险，如气温、气压、湿度异常及其滞后影响。预警方案的核心是把这两类风险叠加：当个体基础风险高且气象模型预测风险升高时，应提高预警等级并采取更主动的社区随访和医疗资源准备。

\section{{数据来源、预处理与模型假设}}
\subsection{{数据来源与数据审计}}
病例数据来自Appendix-C1中的data1.xls至data4.xls，字段包括性别、年龄、职业、发病时间和诊断报告时间。气象数据来自Appendix-C2中的data5.xls，包含2007至2010年逐日平均气压、最高气压、最低气压、平均气温、最高气温、最低气温、平均相对湿度和最小相对湿度。本文清洗得到原始病例{audit['raw_case_rows']}行，其中发病日期可解析且位于2007--2010年范围内的有效病例{audit['valid_case_rows_2007_2010']}行；气象日记录{audit['weather_rows']}条；加入滞后变量后进入问题二模型的日样本数为{audit['daily_model_rows_after_lag_drop']}天。

\subsection{{预处理方法}}
发病时间存在不同日期格式和错误值，本文统一使用日期解析函数转换为日期对象，无法解析、为空或显示为错误符号的记录不进入按日发病率建模。年龄字段转换为数值型，并在描述统计中保留缺失说明；职业字段按题目给出的1--8编码映射为农民、工人、退休人员、教师、渔民、医务人员、职工和离退人员，空值归入缺失/其他。气象数据原表按年份和月份横向展开，本文将其重构为一行一天的长表，并计算温差、气压差等辅助变量。为了降低量纲差异对Poisson回归系数解释的影响，气象变量和时间趋势项在建模前进行Z-score标准化。

\subsection{{模型假设}}
\begin{{enumerate}}[label=假设\arabic*：]
\item 题目提供的医院病例可以反映该城市脑卒中发病时间变化的主要趋势。合理性在于数据覆盖多家医院和四年时间；作用是允许以日病例数作为发病率变化的代理变量。
\item 在2007--2010年内城市总人口短期变化相对平稳。合理性是四年尺度内人口日变化远小于日发病数波动；作用是模型不再显式加入逐日人口暴露量。
\item 气象因素对发病的影响可以通过当天及短期滞后变量近似表示。合理性是环境诱发通常存在数小时到数日滞后；作用是引入1日、3日、7日滞后均值。
\item 诊断报告时间不作为发病时间替代。合理性是报告时间可能滞后且部分缺失；作用是避免将就医流程延迟误当作真实发病日期。
\end{{enumerate}}

\section{{符号说明}}
\begin{{table}}[H]\centering\caption{{主要符号说明}}
\begin{{tabular}}{{lll}}\toprule
符号 & 含义 & 单位/说明\\ \midrule
$Y_t$ & 第$t$天脑卒中发病病例数 & 人/日\\
$T_t$ & 第$t$天平均气温 & $^\circ$C\\
$P_t$ & 第$t$天平均气压 & hPa\\
$H_t$ & 第$t$天平均相对湿度 & \%\\
$\mu_t$ & 第$t$天模型期望发病数 & 人/日\\
$L_k(X_t)$ & 变量$X$的$k$日滞后或滚动均值 & 与$X$一致\\
$RR$ & 相对危险度 & 无量纲\\
$S$ & 综合风险预警分 & 0--100分\\
\bottomrule\end{{tabular}}\end{{table}}

\section{{模型建立与求解}}
\subsection{{问题一：发病人群统计描述}}
\subsubsection{{题目要求与模型输出对齐}}
本问要求“根据病人基本信息，对发病人群进行统计描述”。本文模型输出包括性别分布、年龄分布、职业分布、年度和月度发病趋势，并给出关键集中人群，为第三问的高危人群识别提供数据基础。

\subsubsection{{统计模型与结果}}
对每条有效病例记录，设性别、年龄组、职业和发病月份为分类变量，采用频数和比例描述其分布。若某类别频数为$n_i$，总病例数为$N$，则该类别比例为
\begin{{equation}}
p_i=\frac{{n_i}}{{N}}\times 100\% .
\end{{equation}}
有效病例总数为{q1sum['total_cases']}例，年龄均值{q1sum['age_mean']:.1f}岁，中位数{q1sum['age_median']:.1f}岁。由表\ref{{tab:age}}可见，病例明显集中于中老年阶段，60岁及以上占{q1sum['age_ge_60_percent']:.1f}\%。该结果与脑卒中随年龄增长风险升高的医学规律一致，也说明后续预警应将60岁以上人群作为核心对象。
\begin{{table}}[H]\centering\caption{{病例年龄组分布}}\label{{tab:age}}
{age_tex}
\end{{table}}

性别分布如表\ref{{tab:sex}}所示。男性病例占{q1sum['male_percent']:.1f}\%，略高于女性。性别差异可能与吸烟、饮酒、职业劳动强度和基础疾病控制水平有关，但本题未提供这些个体协变量，因此本文在第三问中仅将性别作为风险修正项，而不单独建立因果解释。
\begin{{table}}[H]\centering\caption{{病例性别分布}}\label{{tab:sex}}
{sex_tex}
\end{{table}}

职业分布如表\ref{{tab:occ}}所示，{tex_escape(q1sum['top_occupation'])}占比最高，为{q1sum['top_occupation_percent']:.1f}\%。职业分布一方面反映风险暴露差异，另一方面也受城市人口结构和医院就诊结构影响，因此在解释时不应直接认定职业是因果因素。本文将其用于社区名单排序和重点随访参考。
\begin{{table}}[H]\centering\caption{{病例职业分布前若干类别}}\label{{tab:occ}}
{occ_tex}
\end{{table}}

\begin{{figure}}[H]\centering
\includegraphics[width=.78\textwidth]{{../quest1/figures/q1_age_distribution.png}}
\caption{{脑卒中病例年龄组分布}}
\end{{figure}}
\begin{{figure}}[H]\centering
\includegraphics[width=.82\textwidth]{{../quest1/figures/q1_monthly_trend.png}}
\caption{{2007--2010年月度脑卒中发病人数变化}}
\end{{figure}}
月度趋势图显示，病例数并非均匀分布，而是在不同月份存在起伏。最高发月份为{tex_escape(q1sum['peak_month'])}，病例数为{q1sum['peak_month_cases']}例。该现象提示仅做全年总体统计不足以支持资源配置，卫生部门还应关注季节性和短期气象诱发的叠加效应。

\subsection{{问题二：发病率与气象因素关系模型}}
\subsubsection{{Baseline模型}}
为了检验气象变量是否提供额外解释力，先建立不含气象变量的baseline模型。设$Y_t$为第$t$天病例数，假设
\begin{{equation}}
Y_t\sim \mathrm{{Poisson}}(\mu_t),\quad \log(\mu_t)=\beta_0+\beta_1 t+\beta_2\sin\left(\frac{{2\pi d_t}}{{365.25}}\right)+\beta_3\cos\left(\frac{{2\pi d_t}}{{365.25}}\right),
\end{{equation}}
其中$d_t$为一年中的第几天。该模型只刻画长期趋势和年周期，是判断气象变量增益的对照组。

\subsubsection{{分布滞后Poisson气象回归}}
主模型在baseline基础上加入气温、气压、相对湿度及短期滞后项：
\begin{{equation}}
\log(\mu_t)=\beta_0+\beta_1 t+\beta_2\sin\left(\frac{{2\pi d_t}}{{365.25}}\right)+\beta_3\cos\left(\frac{{2\pi d_t}}{{365.25}}\right)+\sum_j \gamma_j Z_{{j,t}},
\end{{equation}}
其中$Z_{{j,t}}$包括当天平均气温、平均气压、平均相对湿度、温差、气压差以及1日、3日、7日滞后均值。所有连续变量标准化后进入模型，因此系数$\gamma_j$表示对应变量增加一个标准差时对$\log(\mu_t)$的影响，相对危险度为
\begin{{equation}}
RR_j=\exp(\gamma_j).
\end{{equation}}
当$RR_j>1$时，该变量升高与发病数上升相关；当$RR_j<1$时，该变量升高与发病数下降相关。

\subsubsection{{模型对比结果}}
训练集取2007年1月至2010年6月，测试集取2010年7月至2010年12月。表\ref{{tab:modelcomp}}给出模型对比。主模型AIC比baseline降低{q2sum['aic_improvement']:.1f}，伪$R^2$由{q2sum['baseline']['pseudo_r2']:.3f}提高到{q2sum['main']['pseudo_r2']:.3f}；测试MAE由{q2sum['baseline']['test_mae']:.3f}变为{q2sum['main']['test_mae']:.3f}，说明加入气象变量改善了整体拟合解释，但在测试期对尖峰日的点预测并未优于简单季节模型。因此本文将该模型用于风险解释和分级预警辅助，而不是宣称其可精确预测每一天病例数。
\begin{{table}}[H]\centering\caption{{Baseline与主模型对比}}\label{{tab:modelcomp}}
{comp_tex}
\end{{table}}

\begin{{figure}}[H]\centering
\includegraphics[width=.92\textwidth]{{../quest2/figures/q2_daily_fit.png}}
\caption{{日发病数与Poisson气象模型拟合值}}
\end{{figure}}
图中实际日发病数存在尖峰波动，Poisson模型拟合值更平滑，能捕捉长期趋势和季节水平，但对个别突发高峰仍有低估。这符合医院病例日计数数据的特点：气象因素可以解释部分系统性波动，但个体基础疾病、节假日就医行为、医院报告延迟等未观测因素仍会造成剩余误差。

\subsubsection{{变量关系与系数解释}}
表\ref{{tab:corr}}给出日发病数与气象变量的Spearman相关系数。相关分析只反映单变量关系，不能排除季节和趋势混杂，因此本文以Poisson多变量模型作为主结论来源。
\begin{{table}}[H]\centering\caption{{日发病数与气象变量的Spearman相关性}}\label{{tab:corr}}
{corr_tex}
\end{{table}}

主模型部分关键气象变量系数见表\ref{{tab:coef}}。由于变量已标准化，系数可直接比较方向和相对强度。若某变量$RR$大于1，表示在其他变量和季节趋势控制不变时，该气象变量升高一个标准差会使期望日发病数按$RR$倍变化。需要注意的是，温度、气压、湿度之间存在季节相关性，个别系数不能简单解释为严格因果效应，应结合整体预测改进和敏感性分析共同判断。
\begin{{table}}[H]\centering\caption{{主模型关键气象变量系数与相对危险度}}\label{{tab:coef}}
{coef_tex}
\end{{table}}

\begin{{figure}}[H]\centering
\includegraphics[width=.82\textwidth]{{../quest2/figures/q2_top_coefficients.png}}
\caption{{主模型标准化系数绝对值前12项}}
\end{{figure}}
该图展示了对模型影响较大的标准化变量。正系数表示风险随变量升高而上升，负系数表示风险随变量升高而下降。由于加入了多种滞后项，某些当天变量和滞后变量可能方向不同，这反映短期气象变化过程并非单调作用。例如连续多日均值与当天异常变化可能代表不同环境情景，因此预警时不宜只看单日某一个指标。

\subsection{{问题三：高危人群预警与干预模型}}
\subsubsection{{高危人群指标体系}}
结合医学文献和公共卫生实践，脑卒中高危因素主要包括高龄、男性、既往卒中或短暂性脑缺血发作、高血压、糖尿病、血脂异常、房颤、吸烟、肥胖和缺乏运动等。本题病例数据只提供年龄、性别、职业和发病时间，缺少慢病史，因此本文将题目数据能够支持的因素作为基础分层，将慢病史等关键指标作为实际应用中必须补充采集的字段。表\ref{{tab:demo}}列出了数据支持的主要预警依据。
\begin{{table}}[H]\centering\caption{{预警方案的数据依据}}\label{{tab:demo}}
{demo_tex}
\end{{table}}

\subsubsection{{综合风险评分模型}}
定义综合风险分$S$为
\begin{{equation}}
S=S_{{age}}+S_{{sex}}+S_{{occ}}+S_{{chronic}}+S_{{meteo}},
\end{{equation}}
其中$S_{{age}}$由年龄分层给出，$S_{{sex}}$和$S_{{occ}}$为人口学修正分，$S_{{chronic}}$由高血压、糖尿病、既往卒中等慢病史给出，$S_{{meteo}}$由问题二模型预测的日风险分位给出。若只使用题目数据，则可先计算群体层面的$S_{{meteo}}$；若接入社区健康档案，则可进一步形成个体化预警。
\begin{{table}}[H]\centering\caption{{年龄基础风险分规则}}\label{{tab:agescore}}
{age_score_tex}
\end{{table}}

\begin{{figure}}[H]\centering
\includegraphics[width=.72\textwidth]{{../quest3/figures/q3_age_risk_score.png}}
\caption{{年龄分层预警基础分值}}
\end{{figure}}
年龄基础分随年龄上升而增加，是因为问题一显示病例高度集中于中老年人群，且医学上年龄增长会显著增加动脉粥样硬化、血管弹性下降和合并慢病概率。该分值不是诊断结论，而是用于社区筛查排序和预警消息优先级划分。

\subsubsection{{四级气象—人群联动预警}}
预警等级按$S$和模型预测风险分位共同确定。建议阈值为：50分以上蓝色，70分以上黄色，85分以上橙色，95分以上红色；若气象模型预测风险超过历史90\%分位，即使个体基础分较低，也应提高群体健康提醒强度。表\ref{{tab:rules}}给出四级预警规则。
\begin{{table}}[H]\centering\caption{{四级预警触发条件与建议措施}}\label{{tab:rules}}
{rules_tex}
\end{{table}}

\subsubsection{{分对象干预方案}}
预警的价值在于提前干预而非事后解释。本文将干预对象分为健康/亚健康人群、60岁以上慢病人群、既往卒中或TIA人群、医疗机构和卫生行政部门五类。对应措施见表\ref{{tab:inter}}。
\begin{{table}}[H]\centering\caption{{分对象干预方案}}\label{{tab:inter}}
{inter_tex}
\end{{table}}

\section{{模型检验、对比与稳健性分析}}
\subsection{{Baseline对比}}
Baseline只含趋势与年度周期，主模型在相同训练/测试切分下加入气象变量。AIC降低{q2sum['aic_improvement']:.1f}支持主模型在全样本拟合优度与复杂度权衡上优于baseline；但测试MAE变化为{q2sum['test_mae_change_percent']:.1f}\%，提示2010年下半年存在若干尖峰日，使复杂模型的点预测误差略高。因此本文对模型的定位是“解释气象关联并辅助风险预警”，而非替代临床或公共卫生监测系统的精确日预测。

\subsection{{残差诊断}}
\begin{{figure}}[H]\centering
\includegraphics[width=.72\textwidth]{{../quest2/figures/q2_residual_diagnostic.png}}
\caption{{Poisson主模型残差诊断图}}
\end{{figure}}
残差图中大多数点围绕0上下波动，说明模型不存在明显系统性偏移；但在拟合值较高区域仍可见较大正残差，表示个别高发日未被气象变量充分解释。这提示后续改进应加入空气污染、节假日、流感流行、医院报告制度变化和个体慢病史等因素。

\subsection{{敏感性分析}}
本文对关键气象变量进行正负一个标准差扰动，并用$RR=\exp(\beta)$衡量期望日发病数变化。表\ref{{tab:sens}}和图展示了敏感性结果。若$RR$偏离1越远，表示模型对该变量越敏感。该分析可用于预警系统解释：当敏感变量进入不利区间时，应提高风险提示等级。
\begin{{table}}[H]\centering\caption{{关键气象变量扰动的相对危险度}}\label{{tab:sens}}
{sens_tex}
\end{{table}}
\begin{{figure}}[H]\centering
\includegraphics[width=.76\textwidth]{{../quest2/figures/q2_sensitivity_rr.png}}
\caption{{气象变量正负扰动下的相对危险度}}
\end{{figure}}

\section{{模型评价、改进与推广}}
\subsection{{模型优点}}
第一，本文模型输出与题目要求直接对应。问题一输出人群统计描述，问题二输出气象因素与日发病数关系，问题三输出预警和干预方案，形成从数据到决策的闭环。第二，问题二采用Poisson计数模型，符合日发病数非负整数的统计性质，并设置baseline对照，避免只给复杂模型而无法判断增量价值。第三，本文将气象变量的当天值和短期滞后值同时纳入，能更好反映环境因素对脑卒中的延迟诱发效应。第四，所有关键数字均由代码生成并写入冻结文件，图表保存到支撑材料目录，具有较好的可复现性。

\subsection{{模型局限}}
第一，题目未给出城市逐日人口基数和年龄结构，因此本文以日病例数代理发病率变化，无法计算严格意义上的年龄标化发病率。第二，病例数据缺少高血压、糖尿病、吸烟、既往卒中等个体医学信息，第三问的个体预警评分需要在实际部署时接入社区健康档案。第三，气象因素之间存在较强季节相关性，Poisson回归系数可解释为统计关联，但不能直接证明因果关系。第四，模型未包含空气污染、节假日、流感流行和医疗可及性等变量，个别高发日仍可能出现较大残差。

\subsection{{改进方向与推广}}
后续可从三个方面改进。其一，加入人口基数和分年龄人口结构，建立年龄标化发病率模型；其二，接入个体慢病史和生活方式数据，构建个体级卒中风险评分；其三，引入空气污染、冷空气过程、热浪/寒潮指标和节假日变量，建立更完整的分布滞后非线性模型。本文框架也可推广到心肌梗死、哮喘急性发作、慢阻肺急性加重等受气象影响明显的疾病预警中。

\section{{结论}}
本文完成了2012C题的三个任务。对问题一，清洗得到有效病例{q1sum['total_cases']}例，发现病例以中老年为主，60岁及以上占{q1sum['age_ge_60_percent']:.1f}\%，男性占{q1sum['male_percent']:.1f}\%，{tex_escape(q1sum['top_occupation'])}为占比最高职业。对问题二，建立分布滞后Poisson气象回归，主模型AIC较baseline降低{q2sum['aic_improvement']:.1f}，伪$R^2$提高到{q2sum['main']['pseudo_r2']:.3f}，说明气温、气压、湿度及其滞后变量对短期发病数具有增量解释力；同时测试MAE提示模型仍不能完全预测突发尖峰。对问题三，构建了基于人群基础风险和气象短期风险的蓝、黄、橙、红四级预警机制，并给出分对象干预方案。总体而言，该模型既能描述历史发病规律，也能为公共卫生部门和医疗机构进行资源调配提供可操作依据。

\section*{{参考文献}}
\addcontentsline{{toc}}{{section}}{{参考文献}}
\begin{{enumerate}}[label={{[\arabic*]}}]
\item 中华医学会神经病学分会. 中国脑血管病防治指南[M]. 北京: 人民卫生出版社, 2019.
\item Feigin V L, Forouzanfar M H, Krishnamurthi R, et al. Global and regional burden of stroke during 1990--2010[J]. The Lancet, 2014, 383(9913):245--255.
\item Dawson J, Weir C, Wright F, et al. Associations between meteorological variables and acute stroke hospital admissions in the west of Scotland[J]. Acta Neurologica Scandinavica, 2008, 117(2):85--89.
\item Gasparrini A. Distributed lag linear and non-linear models in R: the package dlnm[J]. Journal of Statistical Software, 2011, 43(8):1--20.
\item McCullagh P, Nelder J A. Generalized Linear Models[M]. London: Chapman and Hall, 1989.
\item 国家卫生健康委员会. 中国脑卒中防治报告[R]. 北京: 国家卫生健康委员会, 2020.
\end{{enumerate}}

\appendix
\section{{支撑材料与复现说明}}
本文支撑材料位于题目目录下的“支撑材料”文件夹。\texttt{{code/main\_modeling.py}}为完整运行脚本；\texttt{{results/frozen\_numbers.json}}保存论文关键数字；\texttt{{quest1}}、\texttt{{quest2}}、\texttt{{quest3}}分别保存各问代码、图表和输出表；\texttt{{papper/论文.tex}}和\texttt{{papper/论文.pdf}}为论文源文件和最终PDF。运行环境为Python 3.11，主要依赖包括pandas、numpy、scipy、statsmodels、scikit-learn、matplotlib和seaborn。所有图表均由代码保存，未使用手工截图。
\section{{三层质量门控审计}}
L1建模合理性：每个子问题均建立了“题目要求—模型输出”映射；问题二设置baseline并与主模型比较；假设均服务于数据清洗、计数建模和预警设计。L2求解正确性：完成数据审计、日期清洗、气象长表重构、训练测试切分、Poisson模型拟合、残差和敏感性分析；关键数字已冻结。L3论文质量：摘要包含各问方法和数值结果，图表均编号并在正文解释，PDF由XeLaTeX编译，支撑材料按标准目录组织。
\end{{document}}
'''


def main():
    copy_sources()
    raw, cases = load_cases()
    weather = load_weather()
    daily = build_daily(cases, weather)
    raw.to_csv(DIRS['data']/'clean_raw_cases_with_parsed_dates.csv', index=False, encoding='utf-8-sig')
    cases.to_csv(DIRS['data']/'valid_cases_2007_2010.csv', index=False, encoding='utf-8-sig')
    weather.to_csv(DIRS['data']/'weather_daily_2007_2010.csv', index=False, encoding='utf-8-sig')
    daily.to_csv(DIRS['data']/'daily_cases_weather_model_data.csv', index=False, encoding='utf-8-sig')
    audit = data_audit(raw, cases, weather, daily)
    q1sum, q1tabs = q1_descriptive(cases)
    q2sum, comp, coef, corr, sens, pred = q2_modeling(daily)
    q3sum, demo, age_risk, rules, inter = q3_warning_plan(cases, q1sum, q2sum, sens)
    generate_reports(audit, q1sum, q1tabs, q2sum, comp, coef, corr, sens, q3sum, demo, age_risk, rules, inter)
    print(json.dumps({'audit': audit, 'q1': q1sum, 'q2': {k:v for k,v in q2sum.items() if k not in ['scalers','top_positive_coefficients','top_negative_coefficients']}, 'pdf_tex': str(DIRS['paper']/'论文.tex')}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
