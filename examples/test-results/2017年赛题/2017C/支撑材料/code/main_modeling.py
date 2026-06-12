import os
import re
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy import stats
from sklearn.model_selection import LeaveOneOut, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.decomposition import PCA
from sklearn.inspection import permutation_importance

np.random.seed(42)

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017C')
SUPPORT = ROOT / '支撑材料'
DATA_DIR = SUPPORT / 'data'
RESULTS_DIR = SUPPORT / 'results'
TABLES_DIR = SUPPORT / 'tables'
REF_DIR = SUPPORT / 'references'
CODE_DIR = SUPPORT / 'code'
for d in [DATA_DIR, RESULTS_DIR, TABLES_DIR, REF_DIR, CODE_DIR,
          SUPPORT/'quest1/figures', SUPPORT/'quest1/outputs', SUPPORT/'quest2/figures', SUPPORT/'quest2/outputs', SUPPORT/'quest3/figures', SUPPORT/'quest3/outputs']:
    d.mkdir(parents=True, exist_ok=True)

# Chinese font
for fp in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 130


def is_num(x):
    return isinstance(x, (int, float, np.integer, np.floating)) and not pd.isna(x)


def parse_data1(path):
    raw = pd.read_excel(path, header=None)
    rows=[]
    substance=None
    concentration=None
    # Based on headers: col0 item, col1 concentration, col2-6 B,G,R,H,S
    for _, r in raw.iterrows():
        c0, c1 = r.iloc[0], r.iloc[1]
        if isinstance(c0, str) and c0 not in ['项目']:
            # new substance or water label in row after item in col0
            if is_num(c1) or c1 == '水':
                substance = c0
                concentration = 0.0 if c1 == '水' else float(c1)
                vals = r.iloc[2:7].tolist()
            else:
                continue
        elif is_num(c0) or c0 == '水':
            concentration = 0.0 if c0 == '水' else float(c0)
            vals = r.iloc[1:6].tolist()
        elif pd.isna(c0) and (is_num(c1) or c1 == '水'):
            concentration = 0.0 if c1 == '水' else float(c1)
            vals = r.iloc[2:7].tolist()
        elif pd.isna(c0) and pd.isna(c1) and concentration is not None:
            vals = r.iloc[1:6].tolist()
        else:
            continue
        if substance is None or len(vals)<5 or not all(is_num(v) for v in vals[:5]):
            continue
        rows.append({'substance':substance,'concentration':float(concentration),
                     'B':float(vals[0]),'G':float(vals[1]),'R':float(vals[2]),'H':float(vals[3]),'S':float(vals[4])})
    return pd.DataFrame(rows)


def parse_data2(path):
    raw = pd.read_excel(path, header=None)
    rows=[]
    concentration=None
    # header: col1 concentration, col2-6 R,G,B,S,H but row continuation shifts to col1-5
    for _, r in raw.iterrows():
        c0, c1 = r.iloc[0], r.iloc[1]
        if c0 == '二氧化硫' or c1 == '浓度（ppm）':
            continue
        if c1 == '水':
            concentration=0.0; vals=r.iloc[2:7].tolist()
        elif is_num(c1) and all(is_num(v) for v in r.iloc[2:7].tolist()):
            concentration=float(c1); vals=r.iloc[2:7].tolist()
        elif pd.isna(c1) and all(is_num(v) for v in r.iloc[2:7].tolist()):
            vals=r.iloc[2:7].tolist()
        elif is_num(c1) and all(is_num(v) for v in r.iloc[1:6].tolist()):
            vals=r.iloc[1:6].tolist()
        else:
            continue
        if concentration is None or not all(is_num(v) for v in vals[:5]):
            continue
        rows.append({'substance':'二氧化硫','concentration':float(concentration),
                     'R':float(vals[0]),'G':float(vals[1]),'B':float(vals[2]),'S':float(vals[3]),'H':float(vals[4])})
    return pd.DataFrame(rows)


def color_distance_to_blank(df, features):
    blank = df[df.concentration==0][features].mean().values
    return np.linalg.norm(df[features].values - blank, axis=1)


def loo_eval(model, X, y):
    loo=LeaveOneOut(); preds=np.zeros(len(y))
    for train,test in loo.split(X):
        m = model
        # recreate simple models via deepcopy
        import copy
        m = copy.deepcopy(model)
        m.fit(X[train], y[train])
        preds[test] = m.predict(X[test]).reshape(-1)
    return preds


def metrics(y_true, y_pred):
    y_true=np.asarray(y_true); y_pred=np.asarray(y_pred)
    rmse=float(np.sqrt(mean_squared_error(y_true,y_pred)))
    mae=float(mean_absolute_error(y_true,y_pred))
    r2=float(r2_score(y_true,y_pred)) if len(np.unique(y_true))>1 else np.nan
    nonzero=y_true>0
    mape=float(np.mean(np.abs((y_true[nonzero]-y_pred[nonzero])/y_true[nonzero]))*100) if nonzero.any() else np.nan
    return {'RMSE':rmse,'MAE':mae,'MAPE_percent':mape,'R2':r2}


def adjacent_separation(df, features):
    levels=sorted(df.concentration.unique())
    means=[]; sds=[]
    for c in levels:
        X=df[df.concentration==c][features].values
        means.append(X.mean(axis=0))
        if len(X)>1:
            sds.append(np.mean(np.linalg.norm(X-X.mean(axis=0), axis=1)))
        else:
            sds.append(0.0)
    ratios=[]
    for i in range(len(levels)-1):
        d=np.linalg.norm(means[i+1]-means[i])
        denom=sds[i]+sds[i+1]+1e-9
        ratios.append(d/denom)
    return float(np.mean(ratios)) if ratios else np.nan, float(np.min(ratios)) if ratios else np.nan


def analyze_data1(df1):
    records=[]
    features=['B','G','R','H','S']
    for sub,g in df1.groupby('substance'):
        g=g.copy()
        g['D0']=color_distance_to_blank(g, features)
        # concentration monotonic with each feature and distance; Spearman abs max and mean
        cors=[]
        for f in features+['D0']:
            if len(g[f].unique())>1 and len(g.concentration.unique())>1:
                rho,p=stats.spearmanr(g[f], g.concentration)
                cors.append((f, float(rho), float(p), abs(float(rho))))
        best=max(cors, key=lambda x:x[3])
        mean_abs=float(np.mean([c[3] for c in cors]))
        sep_mean, sep_min=adjacent_separation(g, features)
        # repeatability: within concentration avg CV in 5D distance
        rep=[]
        for c,gg in g.groupby('concentration'):
            if len(gg)>1:
                X=gg[features].values
                rep.append(np.mean(np.linalg.norm(X-X.mean(axis=0),axis=1)))
        repeat=float(np.mean(rep)) if rep else 0.0
        # baseline linear log1p from D0 and multivariate ridge CV LOO on log1p
        y=np.log1p(g.concentration.values)
        Xd=g[['D0']].values
        Xm=g[features].values
        lin=Pipeline([('scaler',StandardScaler()),('lr',LinearRegression())])
        ridge=Pipeline([('scaler',StandardScaler()),('ridge',RidgeCV(alphas=np.logspace(-3,3,25)))])
        pred_d=np.expm1(loo_eval(lin, Xd, y)); pred_m=np.expm1(loo_eval(ridge, Xm, y))
        pred_d=np.clip(pred_d,0,None); pred_m=np.clip(pred_m,0,None)
        md=metrics(g.concentration.values, pred_d); mm=metrics(g.concentration.values, pred_m)
        # composite higher better, normalize rough: monotonic + sep - relative noise - mape
        score= 35*best[3] + 25*np.tanh(sep_mean/2) + 25*max(0,1-min(mm['MAPE_percent'],100)/100) + 15*max(0,1-repeat/15)
        records.append({'物质':sub,'样本数':len(g),'浓度档数':g.concentration.nunique(),
                        '最佳单调指标':best[0],'最佳Spearman_abs':best[3],'最佳Spearman':best[1],
                        '平均单调性':mean_abs,'相邻可分性均值':sep_mean,'相邻可分性最小值':sep_min,
                        '重复测量平均波动':repeat,
                        '一维距离LOO_RMSE':md['RMSE'],'一维距离LOO_MAPE%':md['MAPE_percent'],
                        '五维Ridge_LOO_RMSE':mm['RMSE'],'五维Ridge_LOO_MAPE%':mm['MAPE_percent'],
                        '综合质量分':score})
    out=pd.DataFrame(records).sort_values('综合质量分', ascending=False)
    out.to_csv(TABLES_DIR/'data1_quality_evaluation.csv', index=False, encoding='utf-8-sig')
    # plots
    fig,ax=plt.subplots(figsize=(10,5))
    ax.bar(out['物质'], out['综合质量分'], color='#4C78A8')
    ax.set_ylabel('综合质量分')
    ax.set_title('Data1 五组数据质量综合评价')
    ax.grid(axis='y',alpha=.25)
    plt.xticks(rotation=20)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest1/figures/问题1_五组数据质量评分.png', dpi=300, bbox_inches='tight'); plt.close()
    fig,axes=plt.subplots(2,3,figsize=(13,7)); axes=axes.ravel()
    for ax,(sub,g) in zip(axes,df1.groupby('substance')):
        gg=g.copy(); gg['D0']=color_distance_to_blank(gg, features)
        ax.scatter(gg.concentration, gg['D0'], s=35)
        ax.set_title(sub); ax.set_xlabel('浓度(ppm)'); ax.set_ylabel('相对白板色差D0')
        ax.grid(alpha=.25)
    axes[-1].axis('off')
    plt.tight_layout(); plt.savefig(SUPPORT/'quest1/figures/问题1_色差浓度关系散点图.png', dpi=300, bbox_inches='tight'); plt.close()
    return out


def analyze_data2(df2):
    features=['R','G','B','S','H']
    df=df2.copy()
    df['D0']=color_distance_to_blank(df, features)
    y=df.concentration.values
    ylog=np.log1p(y)
    X5=df[features].values
    X3=df[['R','G','B']].values
    Xh=df[['S','H']].values
    Xd=df[['D0']].values
    models={
        'Baseline_D0_Linear': (Pipeline([('scaler',StandardScaler()),('lr',LinearRegression())]), Xd),
        'RGB_Ridge': (Pipeline([('scaler',StandardScaler()),('ridge',RidgeCV(alphas=np.logspace(-3,3,31)))]), X3),
        'HSV_Ridge': (Pipeline([('scaler',StandardScaler()),('ridge',RidgeCV(alphas=np.logspace(-3,3,31)))]), Xh),
        'FiveDim_Ridge': (Pipeline([('scaler',StandardScaler()),('ridge',RidgeCV(alphas=np.logspace(-3,3,31)))]), X5),
        'FiveDim_Poly2_Ridge': (Pipeline([('scaler',StandardScaler()),('poly',PolynomialFeatures(2, include_bias=False)),('ridge',RidgeCV(alphas=np.logspace(-2,4,31)))]), X5),
        'PLS_2comp': (Pipeline([('scaler',StandardScaler()),('pls',PLSRegression(n_components=2))]), X5),
    }
    rows=[]; preds={}
    for name,(model,X) in models.items():
        plog=loo_eval(model,X,ylog)
        p=np.clip(np.expm1(plog),0,None)
        preds[name]=p
        m=metrics(y,p); m['模型']=name; rows.append(m)
    met=pd.DataFrame(rows).sort_values('RMSE')
    met.to_csv(TABLES_DIR/'data2_model_comparison.csv', index=False, encoding='utf-8-sig')
    best_name=met.iloc[0]['模型']; best_model=models[best_name][0]; best_X=models[best_name][1]
    best_pred=preds[best_name]
    # Fit final model full data
    best_model.fit(best_X,ylog)
    fitted=np.clip(np.expm1(best_model.predict(best_X).reshape(-1)),0,None)
    residual=y-best_pred
    pred_df=df.copy(); pred_df['LOO预测浓度']=best_pred; pred_df['全样本拟合浓度']=fitted; pred_df['LOO残差']=residual; pred_df['绝对误差']=np.abs(residual)
    pred_df.to_csv(TABLES_DIR/'data2_predictions_residuals.csv', index=False, encoding='utf-8-sig')
    # concentration-level summaries
    level=pred_df.groupby('concentration').agg(样本数=('concentration','size'), R均值=('R','mean'),G均值=('G','mean'),B均值=('B','mean'),S均值=('S','mean'),H均值=('H','mean'),预测均值=('LOO预测浓度','mean'),预测标准差=('LOO预测浓度','std'),MAE=('绝对误差','mean')).reset_index()
    level.to_csv(TABLES_DIR/'data2_level_summary.csv', index=False, encoding='utf-8-sig')
    # Feature importance for five-dim ridge/poly not straightforward; use RF permutation and correlations
    rf=RandomForestRegressor(n_estimators=400, random_state=42, min_samples_leaf=2)
    rf.fit(X5,y)
    imp=permutation_importance(rf,X5,y,n_repeats=80,random_state=42)
    imps=pd.DataFrame({'维度':features,'置换重要性均值':imp.importances_mean,'置换重要性标准差':imp.importances_std})
    corrs=[]
    for f in features+['D0']:
        rho,p=stats.spearmanr(df[f],y)
        corrs.append({'维度':f,'Spearman相关系数':rho,'p值':p})
    corrdf=pd.DataFrame(corrs)
    imps.to_csv(TABLES_DIR/'dimension_importance.csv', index=False, encoding='utf-8-sig')
    corrdf.to_csv(TABLES_DIR/'dimension_spearman.csv', index=False, encoding='utf-8-sig')
    # sample size/dimension influence via repeated CV subsets
    rng=np.random.default_rng(42)
    infl=[]
    dims={'D0':[ 'D0'], 'RGB':['R','G','B'], 'HSV':['S','H'], 'RGBSH':['R','G','B','S','H']}
    for dim_name,cols in dims.items():
        for frac in [0.35,0.5,0.7,0.9,1.0]:
            rmses=[]
            n=min(len(df), max(8,int(len(df)*frac)))
            reps=40 if frac<1 else 1
            for _ in range(reps):
                idx=np.arange(len(df)) if frac==1 else rng.choice(len(df),n,replace=False)
                X=df.iloc[idx][cols].values; yy=np.log1p(df.iloc[idx].concentration.values); yraw=df.iloc[idx].concentration.values
                model=Pipeline([('scaler',StandardScaler()),('ridge',RidgeCV(alphas=np.logspace(-3,3,25)))])
                pp=np.clip(np.expm1(loo_eval(model,X,yy)),0,None)
                rmses.append(np.sqrt(mean_squared_error(yraw,pp)))
            infl.append({'颜色维度':dim_name,'样本比例':frac,'样本数':n,'LOO_RMSE均值':float(np.mean(rmses)),'LOO_RMSE标准差':float(np.std(rmses))})
    infl_df=pd.DataFrame(infl)
    infl_df.to_csv(TABLES_DIR/'sample_dimension_influence.csv', index=False, encoding='utf-8-sig')
    # sensitivity: noise added
    sens=[]
    for sigma in [0,1,2,3,5,8]:
        rmses=[]
        for _ in range(50 if sigma else 1):
            Xn=X5+rng.normal(0,sigma,X5.shape)
            model=Pipeline([('scaler',StandardScaler()),('ridge',RidgeCV(alphas=np.logspace(-3,3,25)))])
            pp=np.clip(np.expm1(loo_eval(model,Xn,ylog)),0,None)
            rmses.append(np.sqrt(mean_squared_error(y,pp)))
        sens.append({'颜色读数噪声标准差':sigma,'RMSE均值':float(np.mean(rmses)),'RMSE标准差':float(np.std(rmses))})
    sens_df=pd.DataFrame(sens)
    sens_df.to_csv(TABLES_DIR/'noise_sensitivity.csv', index=False, encoding='utf-8-sig')
    # plots
    fig,ax=plt.subplots(figsize=(7,6))
    ax.scatter(y,best_pred,c='#F58518',s=50,label='留一预测')
    lim=[-5,max(y.max(),best_pred.max())*1.05]
    ax.plot(lim,lim,'k--',label='理想线')
    ax.set_xlabel('真实浓度(ppm)'); ax.set_ylabel('预测浓度(ppm)')
    ax.set_title(f'Data2 最优模型 {best_name} 留一交叉验证')
    ax.legend(); ax.grid(alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest2/figures/问题2_真实预测对比.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(9,4.8))
    ax.bar(met['模型'], met['RMSE'], color='#54A24B')
    ax.set_ylabel('LOO RMSE(ppm)'); ax.set_title('不同模型误差对比')
    plt.xticks(rotation=30,ha='right'); ax.grid(axis='y',alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest2/figures/问题2_模型误差对比.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(8,4.5))
    ax.scatter(best_pred,residual,c='#E45756',s=45)
    ax.axhline(0,color='k',ls='--')
    ax.set_xlabel('预测浓度(ppm)'); ax.set_ylabel('残差=真实-预测(ppm)')
    ax.set_title('Data2 留一预测残差图')
    ax.grid(alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest2/figures/问题2_残差图.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(8,4.8))
    ax.plot(level['concentration'], level['R均值'], marker='o', label='R')
    ax.plot(level['concentration'], level['G均值'], marker='o', label='G')
    ax.plot(level['concentration'], level['B均值'], marker='o', label='B')
    ax.plot(level['concentration'], level['S均值'], marker='o', label='S')
    ax.plot(level['concentration'], level['H均值'], marker='o', label='H')
    ax.set_xlabel('浓度(ppm)'); ax.set_ylabel('颜色读数均值')
    ax.set_title('二氧化硫不同浓度下颜色读数变化')
    ax.legend(ncol=5); ax.grid(alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest2/figures/问题2_颜色维度随浓度变化.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(8,5))
    for dim in infl_df['颜色维度'].unique():
        g=infl_df[infl_df['颜色维度']==dim]
        ax.errorbar(g['样本数'],g['LOO_RMSE均值'],yerr=g['LOO_RMSE标准差'],marker='o',label=dim,capsize=3)
    ax.set_xlabel('参与建模样本数'); ax.set_ylabel('LOO RMSE(ppm)')
    ax.set_title('数据量与颜色维度对预测误差的影响')
    ax.legend(); ax.grid(alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest3/figures/问题3_数据量颜色维度影响.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(7,4.5))
    ax.errorbar(sens_df['颜色读数噪声标准差'], sens_df['RMSE均值'], yerr=sens_df['RMSE标准差'], marker='o', capsize=3)
    ax.set_xlabel('颜色读数附加噪声标准差'); ax.set_ylabel('RMSE(ppm)')
    ax.set_title('颜色读数噪声敏感性分析')
    ax.grid(alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest3/figures/问题3_颜色噪声敏感性.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(7,4.5))
    ax.bar(imps['维度'], imps['置换重要性均值'], yerr=imps['置换重要性标准差'], color='#B279A2', capsize=3)
    ax.set_ylabel('置换重要性'); ax.set_title('颜色维度贡献度分析')
    ax.grid(axis='y',alpha=.25)
    plt.tight_layout(); plt.savefig(SUPPORT/'quest3/figures/问题3_颜色维度贡献度.png',dpi=300,bbox_inches='tight'); plt.close()
    return met, pred_df, level, imps, corrdf, infl_df, sens_df, best_name


def write_refs():
    text = '''# 外部/知识库资料侦察记录\n\n## IMA 数学建模2026知识库\n- 检索关键词：`2017C 颜色 物质浓度 辨识 比色法`、`颜色 浓度 回归 主成分`。\n- 检索结果：未返回直接同题资料。\n- 转化为建模动作：按数据分析/回归题型自行建立 baseline（相对白板色差一元线性回归）、主模型（多维颜色读数的正则化回归/PLS/二次岭回归）、验证（留一交叉验证、残差分析、噪声敏感性、维度消融）。\n\n## 方法参考\n- 颜色空间建模通常需处理 RGB/HSV 维度、白板校正、维度冗余与颜色噪声。\n- 小样本回归避免复杂黑箱模型，优先采用留一交叉验证、Ridge/PLS 等正则化方法，并用 baseline 验证收益。\n- 质量评价从单调性、重复性、可分性、可预测性四个方面衡量。\n'''
    (REF_DIR/'external_resource_notes.md').write_text(text, encoding='utf-8')


def main():
    for fn in ['CUMCM-2017-problem-C.docx','Data1.xls','Data2.xls','readme.txt']:
        src=ROOT/fn
        if src.exists(): shutil.copy2(src, DATA_DIR/fn)
    df1=parse_data1(ROOT/'Data1.xls')
    df2=parse_data2(ROOT/'Data2.xls')
    df1.to_csv(TABLES_DIR/'data1_cleaned.csv', index=False, encoding='utf-8-sig')
    df2.to_csv(TABLES_DIR/'data2_cleaned.csv', index=False, encoding='utf-8-sig')
    q1=analyze_data1(df1)
    met,pred,level,imps,corrdf,infl,sens,best=analyze_data2(df2)
    write_refs()
    final={
        'data_audit': {
            'Data1_samples': int(len(df1)), 'Data1_substances': int(df1.substance.nunique()),
            'Data2_samples': int(len(df2)), 'Data2_levels': [float(x) for x in sorted(df2.concentration.unique())],
            'missing_after_parse': int(df1.isna().sum().sum()+df2.isna().sum().sum())
        },
        'question1': {
            'best_quality_substance': str(q1.iloc[0]['物质']),
            'worst_quality_substance': str(q1.iloc[-1]['物质']),
            'quality_scores': {str(r['物质']): float(r['综合质量分']) for _,r in q1.iterrows()},
            'criteria': ['单调性(Spearman)', '相邻浓度可分性', '重复测量稳定性', '留一预测误差']
        },
        'question2': {
            'best_model': str(best),
            'best_LOO_RMSE': float(met.iloc[0]['RMSE']),
            'best_LOO_MAE': float(met.iloc[0]['MAE']),
            'best_LOO_MAPE_percent': float(met.iloc[0]['MAPE_percent']),
            'best_LOO_R2': float(met.iloc[0]['R2']),
            'baseline_RMSE': float(met[met['模型']=='Baseline_D0_Linear'].iloc[0]['RMSE']),
            'residual_mean': float(pred['LOO残差'].mean()),
            'residual_std': float(pred['LOO残差'].std()),
            'max_abs_error': float(pred['绝对误差'].max())
        },
        'question3': {
            'dimension_best_full_rmse': str(infl[infl['样本比例']==1.0].sort_values('LOO_RMSE均值').iloc[0]['颜色维度']),
            'full_sample_dimension_rmse': {str(r['颜色维度']): float(r['LOO_RMSE均值']) for _,r in infl[infl['样本比例']==1.0].iterrows()},
            'noise_rmse_sigma0': float(sens[sens['颜色读数噪声标准差']==0].iloc[0]['RMSE均值']),
            'noise_rmse_sigma5': float(sens[sens['颜色读数噪声标准差']==5].iloc[0]['RMSE均值']),
            'top_dimension_by_importance': str(imps.sort_values('置换重要性均值', ascending=False).iloc[0]['维度'])
        }
    }
    (RESULTS_DIR/'frozen_numbers.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    (SUPPORT/'quest1/outputs/frozen_numbers.json').write_text(json.dumps(final['question1'], ensure_ascii=False, indent=2), encoding='utf-8')
    (SUPPORT/'quest2/outputs/frozen_numbers.json').write_text(json.dumps(final['question2'], ensure_ascii=False, indent=2), encoding='utf-8')
    (SUPPORT/'quest3/outputs/frozen_numbers.json').write_text(json.dumps(final['question3'], ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(final, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
