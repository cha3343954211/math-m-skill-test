# -*- coding: utf-8 -*-
"""
CUMCM 2017B 拍照赚钱任务定价：数据审计、特征工程、模型、定价、打包与新项目方案。
Run from any directory. Outputs under 支撑材料/{tables,results,figures,quest*/...}.
"""
from __future__ import annotations

import json, math, warnings, os
from pathlib import Path
from dataclasses import dataclass
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression, LinearRegression, LassoCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss, brier_score_loss, confusion_matrix, classification_report, r2_score, mean_absolute_error
from sklearn.cluster import DBSCAN
from sklearn.inspection import permutation_importance
from scipy.spatial import cKDTree
from scipy.special import expit, logit

warnings.filterwarnings('ignore')

ROOT = Path(r"<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017B")
SUPPORT = ROOT / "支撑材料"
DATA = SUPPORT / "data"
TABLES = SUPPORT / "tables"
RESULTS = SUPPORT / "results"
FIGS = SUPPORT / "quest1" / "figures"
Q1OUT = SUPPORT / "quest1" / "outputs"
Q2OUT = SUPPORT / "quest2" / "outputs"
Q3OUT = SUPPORT / "quest3" / "outputs"
Q4OUT = SUPPORT / "quest4" / "outputs"
Q4FIG = SUPPORT / "quest4" / "figures"
ROB = SUPPORT / "robustness"
for d in [TABLES, RESULTS, FIGS, Q1OUT, Q2OUT, Q3OUT, Q4OUT, Q4FIG, ROB]:
    d.mkdir(parents=True, exist_ok=True)

R_EARTH = 6371.0088
np.random.seed(20260602)


def haversine_matrix(lat1, lon1, lat2, lon2):
    lat1 = np.radians(np.asarray(lat1))[:, None]
    lon1 = np.radians(np.asarray(lon1))[:, None]
    lat2 = np.radians(np.asarray(lat2))[None, :]
    lon2 = np.radians(np.asarray(lon2))[None, :]
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2*R_EARTH*np.arcsin(np.sqrt(np.maximum(a,0)))


def approx_xy(lat, lon, lat0=None):
    lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
    if lat0 is None: lat0 = np.nanmean(lat)
    x = R_EARTH * np.radians(lon) * np.cos(np.radians(lat0))
    y = R_EARTH * np.radians(lat)
    return np.column_stack([x, y])


def round_half(x):
    return np.round(np.asarray(x)*2)/2


def clip_round_price(x, low=65, high=90):
    return round_half(np.clip(x, low, high))


def parse_member_pos(s):
    a = str(s).replace(',', ' ').split()
    return float(a[0]), float(a[1])


def load_data():
    old = pd.read_excel(DATA / "附件一：已结束项目任务数据.xls")
    old = old.rename(columns={'任务gps 纬度':'lat','任务gps经度':'lon','任务标价':'price','任务执行情况':'done','任务号码':'task_id'})
    new = pd.read_excel(DATA / "附件三：新项目任务数据.xls")
    new = new.rename(columns={'任务GPS纬度':'lat','任务GPS经度':'lon','任务号码':'task_id'})
    mem = pd.read_excel(DATA / "附件二：会员信息数据.xlsx")
    mem = mem.rename(columns={'会员编号':'member_id','预订任务限额':'limit','预订任务开始时间':'start_time','信誉值':'credit','会员位置(GPS)':'pos'})
    pos = mem['pos'].apply(parse_member_pos)
    mem['lat'] = [p[0] for p in pos]
    mem['lon'] = [p[1] for p in pos]
    return old, mem, new


def build_features(tasks, members, task_universe=None, prefix=""):
    """Construct spatial supply-demand features. task_universe is old or new tasks for competition density."""
    df = tasks.copy().reset_index(drop=True)
    if task_universe is None: task_universe = tasks
    task_universe = task_universe.reset_index(drop=True)
    dm = haversine_matrix(df['lat'], df['lon'], members['lat'], members['lon'])
    dt = haversine_matrix(df['lat'], df['lon'], task_universe['lat'], task_universe['lon'])
    # if same data, remove self by ignoring very small distance for counts
    same = len(df)==len(task_universe) and np.allclose(df['lat'], task_universe['lat']) and np.allclose(df['lon'], task_universe['lon'])
    feats = pd.DataFrame(index=df.index)
    feats['lat'] = df['lat'].astype(float)
    feats['lon'] = df['lon'].astype(float)
    feats['nearest_member_km'] = dm.min(axis=1)
    feats['mean5_member_km'] = np.sort(dm, axis=1)[:, :5].mean(axis=1)
    feats['mean10_member_km'] = np.sort(dm, axis=1)[:, :10].mean(axis=1)
    for r in [1, 2, 3, 5, 10]:
        maskm = dm <= r
        count = maskm.sum(axis=1)
        feats[f'mem_cnt_{r}km'] = count
        feats[f'credit_sum_{r}km'] = maskm @ members['credit'].to_numpy(float)
        feats[f'credit_mean_{r}km'] = np.divide(feats[f'credit_sum_{r}km'], np.maximum(count,1))
        feats[f'limit_sum_{r}km'] = maskm @ members['limit'].to_numpy(float)
        feats[f'limit_mean_{r}km'] = np.divide(feats[f'limit_sum_{r}km'], np.maximum(count,1))
        task_count = (dt <= r).sum(axis=1)
        if same: task_count = task_count - 1
        feats[f'task_cnt_{r}km'] = task_count
        feats[f'supply_demand_{r}km'] = feats[f'limit_sum_{r}km'] / (task_count + 1)
        feats[f'member_task_ratio_{r}km'] = count / (task_count + 1)
    # coarse districts by coordinate bins
    feats['lat_centered'] = feats['lat'] - feats['lat'].mean()
    feats['lon_centered'] = feats['lon'] - feats['lon'].mean()
    return pd.concat([df[[c for c in df.columns if c not in feats.columns]], feats], axis=1)


def base_feature_cols(df):
    return [c for c in df.columns if c not in ['task_id','price','done','pos','start_time','member_id'] and pd.api.types.is_numeric_dtype(df[c])]


def cv_binary_models(X, y):
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=2026)
    models = {
        'Logistic': Pipeline([('scaler', StandardScaler()), ('clf', LogisticRegression(max_iter=3000, class_weight='balanced'))]),
        'RandomForest': RandomForestClassifier(n_estimators=500, random_state=2026, class_weight='balanced', max_depth=8, min_samples_leaf=8),
        'GBDT': GradientBoostingClassifier(n_estimators=220, max_depth=3, learning_rate=0.04, subsample=0.85, random_state=2026)
    }
    rows=[]; preds={}
    for name, model in models.items():
        proba = cross_val_predict(model, X, y, cv=cv, method='predict_proba')[:,1]
        pred = (proba >= 0.5).astype(int)
        rows.append({
            'model': name,
            'AUC': roc_auc_score(y, proba),
            'Accuracy': accuracy_score(y, pred),
            'LogLoss': log_loss(y, proba),
            'Brier': brier_score_loss(y, proba),
            'PredCompleteRate': proba.mean()
        })
        preds[name]=proba
    return pd.DataFrame(rows), preds, models


def price_regression(df, feature_cols):
    X=df[feature_cols]; y=df['price']
    regs={
        'Linear': Pipeline([('scaler', StandardScaler()), ('reg', LinearRegression())]),
        'Lasso': Pipeline([('scaler', StandardScaler()), ('reg', LassoCV(cv=5, random_state=2026))]),
        'RandomForestReg': RandomForestRegressor(n_estimators=400, max_depth=8, min_samples_leaf=6, random_state=2026),
        'GBDTReg': GradientBoostingRegressor(n_estimators=260, max_depth=3, learning_rate=0.04, random_state=2026)
    }
    rows=[]
    for name, reg in regs.items():
        # simple in-sample for explanatory fit plus CV-like out-of-fold by manual for rows
        from sklearn.model_selection import KFold, cross_val_predict
        cv = KFold(n_splits=5, shuffle=True, random_state=2026)
        pred = cross_val_predict(reg, X, y, cv=cv)
        rows.append({'model':name, 'CV_R2':r2_score(y,pred), 'CV_MAE':mean_absolute_error(y,pred)})
    return pd.DataFrame(rows)


def fit_logit_for_pricing(df, feature_cols):
    cols=['price'] + feature_cols
    X=df[cols]; y=df['done'].astype(int)
    pipe = Pipeline([('scaler', StandardScaler()), ('clf', LogisticRegression(max_iter=3000, class_weight='balanced'))])
    pipe.fit(X,y)
    # convert coefficient in scaled space to original-space coefficient
    scaler=pipe.named_steps['scaler']; clf=pipe.named_steps['clf']
    coef_orig = clf.coef_[0] / scaler.scale_
    intercept_orig = clf.intercept_[0] - np.sum(clf.coef_[0]*scaler.mean_/scaler.scale_)
    beta_price=coef_orig[0]
    return pipe, intercept_orig, coef_orig, beta_price, cols


def predict_prob_logit(intercept, coef, Xmat):
    return expit(intercept + np.asarray(Xmat) @ coef)


def optimize_prices_by_logit(df_features, intercept, coef, price_cols, tau=0.80, low=65, high=90):
    feature_cols_no_price = price_cols[1:]
    X_no = df_features[feature_cols_no_price].to_numpy(float)
    beta_p = coef[0]
    rest = intercept + X_no @ coef[1:]
    target_logit = logit(tau)
    if beta_p <= 1e-6:
        # fallback grid search
        grid=np.arange(low, high+0.001, 0.5)
        out=[]
        for r in rest:
            probs=expit(r+beta_p*grid)
            ok=np.where(probs>=tau)[0]
            out.append(grid[ok[0]] if len(ok) else high)
        p=np.array(out)
    else:
        p=(target_logit-rest)/beta_p
    p=clip_round_price(p, low, high)
    prob=expit(rest+beta_p*p)
    return p, prob


def spatial_smooth_prices(tasks, prices, radius=1.0, rho=0.20):
    xy=approx_xy(tasks['lat'], tasks['lon'])
    tree=cKDTree(xy)
    sm=[]
    prices=np.asarray(prices, float)
    for i, pt in enumerate(xy):
        idx=tree.query_ball_point(pt, radius)
        if len(idx)>1:
            sm.append((1-rho)*prices[i] + rho*np.mean(prices[idx]))
        else:
            sm.append(prices[i])
    return clip_round_price(sm)


def make_bundles(tasks, prices, probs, eps_km=1.0, max_size=3, eta=0.12):
    coords_rad=np.radians(tasks[['lat','lon']].to_numpy(float))
    labels=DBSCAN(eps=eps_km/R_EARTH, min_samples=2, metric='haversine').fit_predict(coords_rad)
    xy=approx_xy(tasks['lat'], tasks['lon'])
    used=set(); bundles=[]
    task_ids=tasks['task_id'].astype(str).to_list()
    for lab in sorted(set(labels)):
        if lab == -1: continue
        idx=np.where(labels==lab)[0].tolist()
        idx=[i for i in idx if i not in used]
        if len(idx)<2: continue
        # greedy seed nearest grouping
        tree=cKDTree(xy[idx])
        remaining=set(idx)
        while len(remaining)>=2:
            seed=next(iter(remaining))
            dists=[(np.linalg.norm(xy[seed]-xy[j]), j) for j in remaining]
            group=[j for _,j in sorted(dists)[:max_size]]
            if len(group)<2: break
            # ensure max pairwise <= 1.5*eps
            pdist=[]
            for a in range(len(group)):
                for b in range(a+1,len(group)):
                    pdist.append(np.linalg.norm(xy[group[a]]-xy[group[b]]))
            maxd=max(pdist) if pdist else 0
            avgd=np.mean(pdist) if pdist else 0
            if maxd <= 1.5*eps_km:
                for j in group: remaining.discard(j); used.add(j)
                sum_price=float(np.sum(prices[group]))
                discount = eta * (1/(1+avgd))
                bundle_price = round_half(sum_price * (1-discount))
                # Probability correction: compact packages reduce travel but add burden.
                p_single=float(np.mean(probs[group]))
                p_bundle=float(np.clip(p_single + 0.09*(1/(1+avgd)) - 0.025*(len(group)-1), 0.05, 0.98))
                # The package completes all tasks together, so expected completed tasks is size*P_G.
                # Accept when unit-cost expected completions improve and package probability is not materially worse.
                single_eff = float(np.sum(probs[group]) / sum_price)
                bundle_eff = float(len(group) * p_bundle / bundle_price)
                accept = (bundle_eff > single_eff) and (p_bundle >= 0.90 * p_single)
                bundles.append({
                    'bundle_id': f'G{len(bundles)+1:04d}',
                    'task_ids': ','.join([task_ids[j] for j in group]),
                    'size': len(group),
                    'center_lat': float(tasks.iloc[group]['lat'].mean()),
                    'center_lon': float(tasks.iloc[group]['lon'].mean()),
                    'avg_internal_km': float(avgd),
                    'max_internal_km': float(maxd),
                    'single_price_sum': sum_price,
                    'bundle_price': float(bundle_price),
                    'discount_rate': float((sum_price-bundle_price)/sum_price),
                    'mean_single_prob': p_single,
                    'bundle_prob': p_bundle,
                    'single_efficiency': single_eff,
                    'bundle_efficiency': bundle_eff,
                    'accepted': bool(accept)
                })
            else:
                remaining.discard(seed)
    return pd.DataFrame(bundles), used


def plot_all(oldf, newf, q2, q4, model_metrics, feat_imp):
    sns.set_theme(style='whitegrid')
    plt.rcParams['font.sans-serif'] = ['SimHei','Microsoft YaHei','Arial Unicode MS','DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    fig, ax=plt.subplots(1,2,figsize=(12,5),dpi=160)
    sns.histplot(oldf['price'], bins=25, ax=ax[0], color='#4c78a8')
    ax[0].set_title('历史任务标价分布'); ax[0].set_xlabel('标价/元')
    sns.boxplot(data=oldf, x='done', y='price', ax=ax[1], palette=['#f58518','#54a24b'])
    ax[1].set_title('完成与未完成任务标价比较'); ax[1].set_xlabel('是否完成(1=完成)')
    fig.tight_layout(); fig.savefig(FIGS/'fig1_price_distribution.png'); plt.close(fig)

    fig, ax=plt.subplots(figsize=(7,6),dpi=170)
    sc=ax.scatter(oldf['lon'], oldf['lat'], c=oldf['done'], s=28, cmap='RdYlGn', alpha=.82, edgecolors='none')
    ax.set_title('历史任务完成情况空间分布'); ax.set_xlabel('经度'); ax.set_ylabel('纬度')
    fig.colorbar(sc, ax=ax, label='完成情况')
    fig.tight_layout(); fig.savefig(FIGS/'fig2_old_spatial_done.png'); plt.close(fig)

    fig, ax=plt.subplots(figsize=(8,5),dpi=170)
    mm=model_metrics.set_index('model')[['AUC','Accuracy','Brier']]
    mm.plot(kind='bar', ax=ax, rot=0)
    ax.set_title('完成概率模型交叉验证指标'); ax.set_ylim(0,1)
    fig.tight_layout(); fig.savefig(FIGS/'fig3_model_metrics.png'); plt.close(fig)

    fig, ax=plt.subplots(figsize=(8,6),dpi=170)
    imp=feat_imp.head(15).iloc[::-1]
    ax.barh(imp['feature'], imp['importance'], color='#72b7b2')
    ax.set_title('GBDT 完成预测特征重要性（置换重要性）')
    fig.tight_layout(); fig.savefig(FIGS/'fig4_feature_importance.png'); plt.close(fig)

    fig, ax=plt.subplots(1,2,figsize=(12,5),dpi=170)
    sns.histplot(q2['new_price'], bins=25, ax=ax[0], color='#b279a2')
    ax[0].set_title('附件一新定价价格分布'); ax[0].set_xlabel('新标价/元')
    ax[1].scatter(q2['price'], q2['new_price'], s=18, alpha=.7)
    ax[1].plot([q2['price'].min(), q2['price'].max()],[q2['price'].min(), q2['price'].max()],'r--')
    ax[1].set_title('原价格与新价格比较'); ax[1].set_xlabel('原价格'); ax[1].set_ylabel('新价格')
    fig.tight_layout(); fig.savefig(SUPPORT/'quest2'/'figures'/'fig5_q2_price_compare.png'); plt.close(fig)

    fig, ax=plt.subplots(figsize=(7,6),dpi=170)
    sc=ax.scatter(newf['lon'], newf['lat'], c=q4['final_price'], s=16, cmap='viridis', alpha=.86)
    ax.set_title('附件三新项目最终定价空间分布'); ax.set_xlabel('经度'); ax.set_ylabel('纬度')
    fig.colorbar(sc, ax=ax, label='最终标价/元')
    fig.tight_layout(); fig.savefig(Q4FIG/'fig6_new_price_map.png'); plt.close(fig)

    fig, ax=plt.subplots(figsize=(8,5),dpi=170)
    sns.histplot(q4['final_price'], bins=35, ax=ax, color='#59a14f')
    ax.set_title('附件三新项目最终价格分布'); ax.set_xlabel('最终标价/元')
    fig.tight_layout(); fig.savefig(Q4FIG/'fig7_new_price_hist.png'); plt.close(fig)


def main():
    old, members, new = load_data()
    oldf = build_features(old, members, old)
    newf = build_features(new, members, new)
    feature_cols = base_feature_cols(oldf)
    # keep stable feature set, avoid too many highly collinear but okay for RF/GBDT/logit with scaler
    selected = ['lat','lon','nearest_member_km','mean5_member_km','mem_cnt_1km','mem_cnt_3km','mem_cnt_5km',
                'credit_sum_1km','credit_sum_3km','credit_sum_5km','limit_sum_1km','limit_sum_3km','limit_sum_5km',
                'task_cnt_1km','task_cnt_3km','task_cnt_5km','supply_demand_1km','supply_demand_3km','supply_demand_5km',
                'member_task_ratio_1km','member_task_ratio_3km','member_task_ratio_5km']
    selected = [c for c in selected if c in oldf.columns]
    Xcls = oldf[['price']+selected]
    y = oldf['done'].astype(int)
    model_metrics, oof_preds, models = cv_binary_models(Xcls, y)
    model_metrics.to_csv(TABLES/'table_model_metrics.csv', index=False, encoding='utf-8-sig')

    preg = price_regression(oldf, selected)
    preg.to_csv(TABLES/'table_original_price_regression.csv', index=False, encoding='utf-8-sig')

    # fit final models
    gbdt = GradientBoostingClassifier(n_estimators=220, max_depth=3, learning_rate=0.04, subsample=0.85, random_state=2026)
    gbdt.fit(Xcls, y)
    perm = permutation_importance(gbdt, Xcls, y, scoring='roc_auc', n_repeats=20, random_state=2026)
    feat_imp = pd.DataFrame({'feature':Xcls.columns, 'importance':perm.importances_mean, 'std':perm.importances_std}).sort_values('importance', ascending=False)
    feat_imp.to_csv(TABLES/'table_feature_importance.csv', index=False, encoding='utf-8-sig')

    logit_pipe, intercept, coef, beta_p, price_cols = fit_logit_for_pricing(oldf, selected)
    coef_table = pd.DataFrame({'feature':price_cols, 'coef_original_scale':coef})
    coef_table.loc[len(coef_table)] = ['intercept', intercept]
    coef_table.to_csv(TABLES/'table_logistic_coefficients.csv', index=False, encoding='utf-8-sig')

    old_pred_original_logit = predict_prob_logit(intercept, coef, oldf[price_cols].to_numpy(float))
    old_pred_original_gbdt = gbdt.predict_proba(Xcls)[:,1]
    q2_price, q2_prob = optimize_prices_by_logit(oldf, intercept, coef, price_cols, tau=0.80, low=65, high=90)
    q2_price_smooth = spatial_smooth_prices(oldf, q2_price, radius=1.0, rho=0.18)
    oldf_q2 = oldf.copy()
    oldf_q2['new_price'] = q2_price_smooth
    Xnewprice = oldf_q2[['new_price']+selected].rename(columns={'new_price':'price'})
    # final predicted prob by logit and GBDT, ensemble for reporting
    q2_prob_logit = predict_prob_logit(intercept, coef, pd.concat([oldf_q2['new_price'], oldf_q2[selected]], axis=1).to_numpy(float))
    q2_prob_gbdt = gbdt.predict_proba(Xnewprice)[:,1]
    q2_prob_ens = 0.65*q2_prob_logit + 0.35*q2_prob_gbdt
    q2_out = pd.DataFrame({
        '任务号码': oldf['task_id'], '纬度':oldf['lat'], '经度':oldf['lon'], '原标价':oldf['price'], '是否完成':oldf['done'],
        '新标价': q2_price_smooth, '原方案预测完成概率': 0.65*old_pred_original_logit+0.35*old_pred_original_gbdt,
        '新方案预测完成概率': q2_prob_ens,
        '价格变化': q2_price_smooth-oldf['price']
    })
    q2_out.to_csv(Q2OUT/'附件一新定价方案.csv', index=False, encoding='utf-8-sig')
    q2_out.to_excel(Q2OUT/'附件一新定价方案.xlsx', index=False)

    # Bundling for old q3
    q3_bundles, used_old = make_bundles(oldf, q2_price_smooth, q2_prob_ens, eps_km=1.0, max_size=3, eta=0.12)
    q3_bundles.to_csv(Q3OUT/'附件一打包方案.csv', index=False, encoding='utf-8-sig')
    q3_bundles.to_excel(Q3OUT/'附件一打包方案.xlsx', index=False)

    # New project pricing
    q4_base_price, q4_prob_logit = optimize_prices_by_logit(newf, intercept, coef, price_cols, tau=0.80, low=65, high=90)
    q4_smooth = spatial_smooth_prices(newf, q4_base_price, radius=1.0, rho=0.22)
    new_tmp = newf.copy(); new_tmp['price'] = q4_smooth
    q4_prob_logit = predict_prob_logit(intercept, coef, new_tmp[price_cols].to_numpy(float))
    q4_prob_gbdt = gbdt.predict_proba(new_tmp[['price']+selected])[:,1]
    q4_prob = 0.65*q4_prob_logit + 0.35*q4_prob_gbdt
    q4_single = pd.DataFrame({
        '任务号码': newf['task_id'], '纬度':newf['lat'], '经度':newf['lon'],
        '建议标价': q4_smooth, '预测完成概率': q4_prob,
        '附近会员数_3km': newf['mem_cnt_3km'], '附近任务数_3km': newf['task_cnt_3km'],
        '供需比_3km': newf['supply_demand_3km'], '最近会员距离_km': newf['nearest_member_km']
    })
    q4_bundles, used_new = make_bundles(newf, q4_smooth, q4_prob, eps_km=1.0, max_size=3, eta=0.12)
    # mark final: if in accepted bundles, keep single table but package table is implementation addendum
    q4_single['是否进入推荐任务包'] = q4_single['任务号码'].astype(str).isin(set(','.join(q4_bundles.loc[q4_bundles['accepted'],'task_ids'].astype(str)).split(',')) if len(q4_bundles) else set())
    q4_single = q4_single.rename(columns={'建议标价':'final_price'})
    q4_single.to_csv(Q4OUT/'附件三新项目单任务定价方案.csv', index=False, encoding='utf-8-sig')
    q4_single.to_excel(Q4OUT/'附件三新项目单任务定价方案.xlsx', index=False)
    q4_bundles.to_csv(Q4OUT/'附件三新项目打包建议.csv', index=False, encoding='utf-8-sig')
    q4_bundles.to_excel(Q4OUT/'附件三新项目打包建议.xlsx', index=False)

    # Summaries
    q1_summary = {
        'n_old_tasks': int(len(oldf)),
        'n_members': int(len(members)),
        'n_new_tasks': int(len(newf)),
        'original_complete_rate': float(oldf['done'].mean()),
        'original_price_mean': float(oldf['price'].mean()),
        'original_price_median': float(oldf['price'].median()),
        'original_price_min': float(oldf['price'].min()),
        'original_price_max': float(oldf['price'].max()),
        'completed_price_mean': float(oldf.loc[oldf['done']==1,'price'].mean()),
        'unfinished_price_mean': float(oldf.loc[oldf['done']==0,'price'].mean()),
        'price_done_corr': float(oldf['price'].corr(oldf['done'])),
        'beta_price_logit_original_scale': float(beta_p),
        'best_auc': float(model_metrics['AUC'].max())
    }
    q2_summary = {
        'old_total_price': float(oldf['price'].sum()),
        'new_total_price': float(q2_price_smooth.sum()),
        'old_mean_price': float(oldf['price'].mean()),
        'new_mean_price': float(q2_price_smooth.mean()),
        'old_pred_complete_rate_ensemble': float((0.65*old_pred_original_logit+0.35*old_pred_original_gbdt).mean()),
        'new_pred_complete_rate_ensemble': float(q2_prob_ens.mean()),
        'price_increase_rate': float(q2_price_smooth.sum()/oldf['price'].sum()-1),
        'high_risk_old_prob_lt_0_6': int(np.sum((0.65*old_pred_original_logit+0.35*old_pred_original_gbdt)<0.6)),
        'high_risk_new_prob_lt_0_6': int(np.sum(q2_prob_ens<0.6))
    }
    q3_summary = {
        'candidate_bundles': int(len(q3_bundles)),
        'accepted_bundles': int(q3_bundles['accepted'].sum()) if len(q3_bundles) else 0,
        'tasks_in_accepted_bundles': int(sum(q3_bundles.loc[q3_bundles['accepted'],'size'])) if len(q3_bundles) else 0,
        'bundle_total_single_price': float(q3_bundles.loc[q3_bundles['accepted'],'single_price_sum'].sum()) if len(q3_bundles) else 0,
        'bundle_total_package_price': float(q3_bundles.loc[q3_bundles['accepted'],'bundle_price'].sum()) if len(q3_bundles) else 0,
        'bundle_saving_rate_on_bundled_tasks': float(1-q3_bundles.loc[q3_bundles['accepted'],'bundle_price'].sum()/q3_bundles.loc[q3_bundles['accepted'],'single_price_sum'].sum()) if len(q3_bundles) and q3_bundles.loc[q3_bundles['accepted'],'single_price_sum'].sum()>0 else 0,
        'mean_bundle_prob': float(q3_bundles.loc[q3_bundles['accepted'],'bundle_prob'].mean()) if len(q3_bundles) and q3_bundles['accepted'].sum() else 0
    }
    q4_summary = {
        'n_new_tasks': int(len(q4_single)),
        'single_total_budget': float(q4_single['final_price'].sum()),
        'single_mean_price': float(q4_single['final_price'].mean()),
        'single_min_price': float(q4_single['final_price'].min()),
        'single_max_price': float(q4_single['final_price'].max()),
        'single_pred_complete_rate': float(q4_single['预测完成概率'].mean()),
        'high_risk_prob_lt_0_6': int((q4_single['预测完成概率']<0.6).sum()),
        'candidate_bundles': int(len(q4_bundles)),
        'accepted_bundles': int(q4_bundles['accepted'].sum()) if len(q4_bundles) else 0,
        'tasks_in_accepted_bundles': int(sum(q4_bundles.loc[q4_bundles['accepted'],'size'])) if len(q4_bundles) else 0,
        'accepted_bundle_saving_rate': float(1-q4_bundles.loc[q4_bundles['accepted'],'bundle_price'].sum()/q4_bundles.loc[q4_bundles['accepted'],'single_price_sum'].sum()) if len(q4_bundles) and q4_bundles.loc[q4_bundles['accepted'],'single_price_sum'].sum()>0 else 0
    }
    summary={'q1':q1_summary,'q2':q2_summary,'q3':q3_summary,'q4':q4_summary}
    (RESULTS/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    pd.DataFrame([q1_summary]).to_csv(TABLES/'table_q1_data_summary.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([q2_summary]).to_csv(TABLES/'table_q2_comparison.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([q3_summary]).to_csv(TABLES/'table_q3_bundle_summary.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([q4_summary]).to_csv(TABLES/'table_q4_new_project_summary.csv', index=False, encoding='utf-8-sig')

    plot_all(oldf, newf, oldf_q2.assign(price=oldf['price']), q4_single, model_metrics, feat_imp)
    # data audit
    audit=[]
    for name, df in [('old_tasks',old),('members',members),('new_tasks',new)]:
        audit.append({'dataset':name,'rows':len(df),'columns':len(df.columns),'missing_cells':int(df.isna().sum().sum()),'duplicate_rows':int(df.duplicated().sum())})
    pd.DataFrame(audit).to_csv(TABLES/'table_data_audit.csv', index=False, encoding='utf-8-sig')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
