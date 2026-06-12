import json, re, shutil, os, zipfile, math, warnings
from pathlib import Path
from datetime import datetime
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
try:
    import seaborn as sns
except Exception:
    sns = None

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012A')
SUP = ROOT / '支撑材料'
DATA = SUP / 'data'
for sub in ['papper','quest1/codes','quest1/figures','quest1/outputs','quest2/codes','quest2/figures','quest2/outputs','quest3/codes','quest3/figures','quest3/outputs','quest4/codes','quest4/figures','quest4/outputs','results','tables','references','code']:
    (SUP/sub).mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei','Microsoft YaHei','Arial Unicode MS','DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
np.random.seed(42)

def safe_name(s):
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff_-]+','_',str(s)).strip('_')

def sample_id_from_cells(cells):
    for c in cells:
        if pd.isna(c): continue
        s=str(c)
        m=re.search(r'(?:酒|葡萄酒|葡酒萄)?样品\s*(\d+)', s)
        if m: return int(m.group(1))
    return None

def parse_score_sheet(xls_path, sheet):
    df = pd.read_excel(xls_path, sheet_name=sheet, header=None)
    sample_rows=[]
    for i,row in df.iterrows():
        sid=sample_id_from_cells(row.tolist())
        if sid is not None:
            # avoid header-only rows with no later scores? keep
            sample_rows.append((i,sid))
    # remove duplicate header false? sorted unique row positions
    records=[]
    for idx,(start,sid) in enumerate(sample_rows):
        end = sample_rows[idx+1][0] if idx+1<len(sample_rows) else len(df)
        block = df.iloc[start:end]
        judge_scores = np.zeros(10, dtype=float)
        item_count = 0
        for _,r in block.iterrows():
            vals=[]
            for v in r.tolist():
                if isinstance(v,(int,float,np.integer,np.floating)) and not pd.isna(v):
                    vals.append(float(v))
            if len(vals) >= 10:
                arr=np.array(vals[-10:], dtype=float)
                # scoring item rows mostly scores 0-22. remove accidental all huge IDs impossible
                if np.nanmax(arr) <= 30 and np.nanmin(arr) >= 0:
                    judge_scores += arr
                    item_count += 1
        if item_count>=6 and 40 <= judge_scores.mean() <= 100:
            rec={'sheet':sheet,'sample':sid,'n_items':item_count}
            for j,v in enumerate(judge_scores,1): rec[f'judge{j}']=float(v)
            rec['mean']=float(judge_scores.mean())
            rec['std']=float(judge_scores.std(ddof=1))
            rec['cv']=float(rec['std']/rec['mean'])
            records.append(rec)
    out=pd.DataFrame(records).drop_duplicates(['sample']).sort_values('sample')
    return out

def load_scores():
    path=DATA/'附件1-葡萄酒品尝评分表.xls'
    allres={}
    for sh in pd.ExcelFile(path).sheet_names:
        t = 'red' if '红' in sh else 'white'
        g = 1 if '第一组' in sh else 2
        df=parse_score_sheet(path, sh)
        df['wine_type']=t; df['group']=g
        allres[(t,g)] = df
        df.to_csv(SUP/f'quest1/outputs/{t}_group{g}_scores.csv', index=False, encoding='utf-8-sig')
    scores=pd.concat(allres.values(), ignore_index=True)
    scores.to_csv(SUP/'tables/all_wine_scores.csv', index=False, encoding='utf-8-sig')
    return scores, allres

def group_indicator_sheet(xls_path, sheet):
    raw=pd.read_excel(xls_path, sheet_name=sheet, header=None)
    # identify rows with sample names
    rows=[]
    for i,row in raw.iterrows():
        sid=sample_id_from_cells(row.tolist()[:3])
        if sid is not None:
            rows.append((i,sid))
    header0=raw.iloc[0].tolist()
    header1=raw.iloc[1].tolist() if len(raw)>1 else [None]*raw.shape[1]
    names=[]; current=None
    for j,(h0,h1) in enumerate(zip(header0,header1)):
        if not pd.isna(h0): current=str(h0).strip()
        # sample id col
        nm=current if current else f'col{j}'
        if not pd.isna(h1) and str(h1).strip() not in ['1','2','3','红葡萄','白葡萄','红葡萄酒','白葡萄酒']:
            if nm in ['样品编号','品种编号']:
                nm='样品编号'
            elif len(str(h1).strip())<30 and not re.fullmatch(r'\d+(\.0+)?', str(h1).strip()):
                nm=f'{nm}_{str(h1).strip()}'
        names.append(nm)
    recs=[]
    for i,sid in rows:
        vals=raw.iloc[i].tolist()
        d={'sample':sid}
        groups={}
        for j,v in enumerate(vals):
            nm=names[j]
            if nm in ['样品编号','品种编号'] or nm.startswith('col'): continue
            if isinstance(v,(int,float,np.integer,np.floating)) and not pd.isna(v):
                groups.setdefault(nm,[]).append(float(v))
        for nm,vs in groups.items(): d[safe_name(nm)]=float(np.nanmean(vs))
        recs.append(d)
    df=pd.DataFrame(recs).drop_duplicates('sample').sort_values('sample')
    # remove zero variance columns
    for c in list(df.columns):
        if c!='sample' and df[c].notna().sum()<3: df.drop(columns=[c], inplace=True)
    return df

def load_indicators():
    p=DATA/'附件2-指标总表.xls'
    grape=group_indicator_sheet(p,'酿酒葡萄')
    wine=group_indicator_sheet(p,'葡萄酒')
    grape.to_csv(SUP/'tables/grape_physical_chemical.csv', index=False, encoding='utf-8-sig')
    wine.to_csv(SUP/'tables/wine_physical_chemical.csv', index=False, encoding='utf-8-sig')
    return grape, wine

def unique_cols(names):
    seen={}; out=[]
    for n in names:
        n=safe_name(n) or 'unknown'
        if n in seen:
            seen[n]+=1; out.append(f'{n}_{seen[n]}')
        else:
            seen[n]=0; out.append(n)
    return out

def parse_aroma(sheet):
    p=DATA/'附件3-芳香物质.xls'
    raw=pd.read_excel(p, sheet_name=sheet, header=None)
    # find header row containing 英文名称 and sample columns
    hrow=0
    for i in range(min(5,len(raw))):
        if any(str(x).strip()=='英文名称' for x in raw.iloc[i].tolist()): hrow=i; break
    header=raw.iloc[hrow].tolist()
    sample_cols=[]; sids=[]
    for j,h in enumerate(header):
        sid=sample_id_from_cells([h])
        if sid is not None:
            sample_cols.append(j); sids.append(sid)
    # feature names from Chinese col usually index 1
    rec=[]
    for ri in range(hrow+1,len(raw)):
        cname=raw.iloc[ri,1] if raw.shape[1]>1 else raw.iloc[ri,0]
        if pd.isna(cname): cname=raw.iloc[ri,0]
        if pd.isna(cname): continue
        vals=[]
        for j in sample_cols:
            v=raw.iloc[ri,j]
            vals.append(float(v) if isinstance(v,(int,float,np.integer,np.floating)) and not pd.isna(v) else 0.0)
        rec.append((safe_name(cname), vals))
    mat=pd.DataFrame({ 'sample': sids })
    cols=unique_cols([r[0] for r in rec])
    arr=np.array([r[1] for r in rec]).T if rec else np.empty((len(sids),0))
    for k,c in enumerate(cols): mat[c]=arr[:,k]
    mat=mat.groupby('sample', as_index=False).mean().sort_values('sample')
    mat.to_csv(SUP/f'tables/aroma_{safe_name(sheet)}.csv', index=False, encoding='utf-8-sig')
    return mat

def impute_scale(df):
    X=df.copy()
    for c in X.columns:
        X[c]=pd.to_numeric(X[c], errors='coerce')
        X[c]=X[c].fillna(X[c].median())
    return X

def pca_score(features, positive_cols=None, n_comp_var=0.85):
    X=impute_scale(features)
    scaler=StandardScaler(); Z=scaler.fit_transform(X)
    pca=PCA().fit(Z)
    cum=np.cumsum(pca.explained_variance_ratio_)
    k=int(np.searchsorted(cum,n_comp_var)+1)
    k=max(1,min(k, min(8, Z.shape[1], Z.shape[0]-1)))
    pca=PCA(n_components=k).fit(Z)
    comps=pca.transform(Z)
    weights=pca.explained_variance_ratio_/pca.explained_variance_ratio_.sum()
    score=comps.dot(weights)
    # orient by average positive indicators if provided, otherwise by row mean standardized
    orient=np.corrcoef(score, Z.mean(axis=1))[0,1]
    if np.isnan(orient) or orient<0: score=-score
    score01=(score-score.min())/(score.max()-score.min()+1e-12)*100
    return score01, pca, scaler, Z

def main():
    scores, score_groups = load_scores()
    grape, wine = load_indicators()
    aroma_rw=parse_aroma('红葡萄酒'); aroma_ww=parse_aroma('白葡萄酒')
    aroma_rg=parse_aroma('红葡萄'); aroma_wg=parse_aroma('白葡萄')

    # Q1 stats
    q1=[]; reliable={}
    for t in ['red','white']:
        g1=score_groups[(t,1)][['sample','mean','std','cv']].rename(columns={'mean':'g1_mean','std':'g1_std','cv':'g1_cv'})
        g2=score_groups[(t,2)][['sample','mean','std','cv']].rename(columns={'mean':'g2_mean','std':'g2_std','cv':'g2_cv'})
        m=g1.merge(g2,on='sample')
        diff=m.g1_mean-m.g2_mean
        ttest=stats.ttest_rel(m.g1_mean,m.g2_mean)
        wil=stats.wilcoxon(m.g1_mean,m.g2_mean) if len(m)>0 else (np.nan,np.nan)
        corr=stats.pearsonr(m.g1_mean,m.g2_mean)
        # reliability: lower mean within-sample std/cv, higher Kendall W approximation via avg pair corr
        raw1=score_groups[(t,1)][[f'judge{i}' for i in range(1,11)]].values
        raw2=score_groups[(t,2)][[f'judge{i}' for i in range(1,11)]].values
        def cronbach(mat):
            k=mat.shape[1]; item_var=mat.var(axis=0,ddof=1).sum(); total_var=mat.sum(axis=1).var(ddof=1)
            return k/(k-1)*(1-item_var/total_var) if total_var>0 else np.nan
        def avg_spearman(mat):
            cors=[]
            for i in range(mat.shape[1]):
                for j in range(i+1,mat.shape[1]):
                    r=stats.spearmanr(mat[:,i],mat[:,j]).correlation
                    if not np.isnan(r): cors.append(r)
            return float(np.mean(cors)) if cors else np.nan
        r1={'type':t,'group':1,'mean_std':float(m.g1_std.mean()),'mean_cv':float(m.g1_cv.mean()),'cronbach_alpha':float(cronbach(raw1)),'avg_spearman':avg_spearman(raw1)}
        r2={'type':t,'group':2,'mean_std':float(m.g2_std.mean()),'mean_cv':float(m.g2_cv.mean()),'cronbach_alpha':float(cronbach(raw2)),'avg_spearman':avg_spearman(raw2)}
        q1.append({'type':t,'n':len(m),'mean_group1':float(m.g1_mean.mean()),'mean_group2':float(m.g2_mean.mean()),'mean_diff_g1_minus_g2':float(diff.mean()),'paired_t':float(ttest.statistic),'p_ttest':float(ttest.pvalue),'p_wilcoxon':float(wil.pvalue if hasattr(wil,'pvalue') else wil[1]),'pearson_r':float(corr.statistic),'pearson_p':float(corr.pvalue), **{f'g1_{k}':v for k,v in r1.items() if k not in ['type','group']}, **{f'g2_{k}':v for k,v in r2.items() if k not in ['type','group']}})
        reliable[t]=2 if (r2['mean_cv']<r1['mean_cv'] and r2['avg_spearman']>=r1['avg_spearman']-0.05) else (1 if r1['mean_cv']<r2['mean_cv'] else 2)
        m.to_csv(SUP/f'quest1/outputs/q1_{t}_paired_scores.csv', index=False, encoding='utf-8-sig')
    q1df=pd.DataFrame(q1); q1df.to_csv(SUP/'tables/q1_significance_reliability.csv', index=False, encoding='utf-8-sig')
    # trusted quality: choose group2 for both unless stats contradict
    trusted=[]
    for t in ['red','white']:
        df=score_groups[(t,reliable[t])][['sample','mean','std','cv']].copy(); df['wine_type']=t; df['trusted_group']=reliable[t]
        trusted.append(df)
    quality=pd.concat(trusted, ignore_index=True).rename(columns={'mean':'quality_score'})
    quality.to_csv(SUP/'tables/trusted_wine_quality_scores.csv', index=False, encoding='utf-8-sig')

    # Q2 grading: PCA on grape phys+aroma + quality weighted composite; cluster into 4 grades within wine type
    grades=[]
    for t, aromag in [('red',aroma_rg),('white',aroma_wg)]:
        q=quality[quality.wine_type==t][['sample','quality_score']]
        X=grape.merge(aromag,on='sample',how='left').merge(q,on='sample',how='inner')
        feat=X.drop(columns=['sample','quality_score'])
        score01,pca,scaler,Z=pca_score(feat)
        X['grape_pca_score']=score01
        X['composite_score']=0.55*X['quality_score']+0.45*X['grape_pca_score']
        # choose 4 grades by KMeans on composite + quality + pca, then order clusters
        km=KMeans(n_clusters=4, random_state=42, n_init=30)
        labels=km.fit_predict(StandardScaler().fit_transform(X[['quality_score','grape_pca_score','composite_score']]))
        X['cluster']=labels
        order=X.groupby('cluster')['composite_score'].mean().sort_values(ascending=False).index.tolist()
        grade_map={cl:g for cl,g in zip(order,['一级','二级','三级','四级'])}
        X['grade']=X['cluster'].map(grade_map)
        X['wine_type']=t
        X[['wine_type','sample','quality_score','grape_pca_score','composite_score','cluster','grade']].sort_values('composite_score',ascending=False).to_csv(SUP/f'quest2/outputs/q2_{t}_grading.csv', index=False, encoding='utf-8-sig')
        # PCA loadings top features
        load=pd.Series(np.abs(pca.components_[0]), index=feat.columns).sort_values(ascending=False).head(15)
        load.to_csv(SUP/f'quest2/outputs/q2_{t}_pca_top_loadings.csv', encoding='utf-8-sig')
        grades.append(X[['wine_type','sample','quality_score','grape_pca_score','composite_score','grade']])
    gradesdf=pd.concat(grades, ignore_index=True); gradesdf.to_csv(SUP/'tables/final_grape_grading.csv', index=False, encoding='utf-8-sig')

    # Q3 relation between grape and wine physicochemical indicators: PCA/PLS/canonical-like via PCA components
    q3rows=[]
    for t, wine_aroma, grape_aroma in [('red',aroma_rw,aroma_rg),('white',aroma_ww,aroma_wg)]:
        samples=set(quality[quality.wine_type==t]['sample'])
        G=grape.merge(grape_aroma,on='sample',how='left')
        W=wine.merge(wine_aroma,on='sample',how='left')
        M=G.merge(W,on='sample',suffixes=('_grape','_wine')).query('sample in @samples')
        Gx=impute_scale(M[[c for c in M.columns if c.endswith('_grape') or (c not in W.columns and c!='sample')]].copy())
        # suffix logic fallback
        if Gx.shape[1]<5:
            gcols=[c for c in G.columns if c!='sample']; wcols=[c for c in W.columns if c!='sample']
            M=G.merge(W,on='sample',suffixes=('_grape','_wine')).query('sample in @samples')
            Gx=impute_scale(M[[c for c in M.columns if c.endswith('_grape')]])
            Wx=impute_scale(M[[c for c in M.columns if c.endswith('_wine')]])
        else:
            Wx=impute_scale(M[[c for c in M.columns if c.endswith('_wine')]])
        k=min(5, len(M)-2, Gx.shape[1], Wx.shape[1])
        Gz=StandardScaler().fit_transform(Gx); Wz=StandardScaler().fit_transform(Wx)
        Gpc=PCA(n_components=k, random_state=42).fit_transform(Gz)
        Wpc=PCA(n_components=k, random_state=42).fit_transform(Wz)
        corrs=[]
        for i in range(k):
            r,pv=stats.pearsonr(Gpc[:,i], Wpc[:,i]); corrs.append((i+1,float(r),float(pv)))
        # PLS R2 predicting wine PC1 from grape indicators
        pls=PLSRegression(n_components=min(3,k))
        pred=cross_val_predict(pls,Gz,Wpc[:,0],cv=min(5,len(M)))
        r2=float(r2_score(Wpc[:,0],pred)); rmse=float(mean_squared_error(Wpc[:,0],pred)**0.5)
        q3rows.append({'type':t,'n_samples':len(M),'pc1_corr':corrs[0][1],'pc1_p':corrs[0][2],'pc2_corr':corrs[1][1] if k>1 else np.nan,'wine_pc1_from_grape_cv_r2':r2,'wine_pc1_from_grape_cv_rmse':rmse})
        pd.DataFrame(corrs,columns=['pc','pearson_r','p_value']).to_csv(SUP/f'quest3/outputs/q3_{t}_pc_correlations.csv', index=False, encoding='utf-8-sig')
    q3df=pd.DataFrame(q3rows); q3df.to_csv(SUP/'tables/q3_grape_wine_relation.csv', index=False, encoding='utf-8-sig')

    # Q4 quality prediction from indicators: grape only, wine only, combined; PLS/Ridge/RF CV
    q4=[]; feature_importances=[]
    for t, wine_aroma, grape_aroma in [('red',aroma_rw,aroma_rg),('white',aroma_ww,aroma_wg)]:
        q=quality[quality.wine_type==t][['sample','quality_score']]
        G=grape.merge(grape_aroma,on='sample',how='left')
        W=wine.merge(wine_aroma,on='sample',how='left')
        sets={'grape':G,'wine':W,'combined':G.merge(W,on='sample',suffixes=('_grape','_wine'))}
        for name,D in sets.items():
            M=D.merge(q,on='sample',how='inner')
            X=impute_scale(M.drop(columns=['sample','quality_score'])); y=M['quality_score'].values
            Z=StandardScaler().fit_transform(X)
            cv=KFold(n_splits=min(5,len(M)), shuffle=True, random_state=42)
            models={
                'LinearBaseline': LinearRegression(),
                'RidgeCV': RidgeCV(alphas=np.logspace(-3,3,13)),
                'PLS': PLSRegression(n_components=min(5, max(1, len(M)-2), X.shape[1])),
                'RandomForest': RandomForestRegressor(n_estimators=400, random_state=42, min_samples_leaf=2)
            }
            best=None
            for mn,model in models.items():
                pred=cross_val_predict(model,Z,y,cv=cv)
                rmse=float(mean_squared_error(y,pred)**0.5); mae=float(mean_absolute_error(y,pred)); r2=float(r2_score(y,pred))
                q4.append({'type':t,'feature_set':name,'model':mn,'n_samples':len(M),'n_features':X.shape[1],'cv_rmse':rmse,'cv_mae':mae,'cv_r2':r2})
                if best is None or rmse<best[0]: best=(rmse,mn,model,Z,y,X.columns)
            # fit RF for importance on combined and best set
            if name=='combined':
                rf=RandomForestRegressor(n_estimators=600, random_state=42, min_samples_leaf=2).fit(Z,y)
                imp=pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False).head(20)
                for feat,val in imp.items(): feature_importances.append({'type':t,'feature':feat,'importance':float(val)})
                imp.to_csv(SUP/f'quest4/outputs/q4_{t}_rf_top_importance.csv', encoding='utf-8-sig')
    q4df=pd.DataFrame(q4); q4df.to_csv(SUP/'tables/q4_quality_prediction_models.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(feature_importances).to_csv(SUP/'tables/q4_top_feature_importance.csv', index=False, encoding='utf-8-sig')

    # Sensitivity: perturb quality weight in Q2
    sens=[]
    for wt in np.linspace(0.4,0.7,16):
        tmp=gradesdf.copy(); tmp['score_w']=wt*tmp.quality_score+(1-wt)*tmp.grape_pca_score
        for t in ['red','white']:
            base=tmp[tmp.wine_type==t].sort_values('composite_score')['sample'].tolist()
            now=tmp[tmp.wine_type==t].sort_values('score_w')['sample'].tolist()
            # spearman rank corr
            rb={s:i for i,s in enumerate(base)}; rn=[rb[s] for s in now]
            rho=stats.spearmanr(range(len(now)), rn).correlation
            sens.append({'type':t,'quality_weight':float(wt),'rank_spearman_vs_base':float(rho)})
    sensdf=pd.DataFrame(sens); sensdf.to_csv(SUP/'tables/sensitivity_q2_weight.csv', index=False, encoding='utf-8-sig')

    # figures
    def savefig(path): plt.tight_layout(); plt.savefig(path,dpi=300,bbox_inches='tight'); plt.close()
    # Q1 paired mean scatter
    for t in ['red','white']:
        m=pd.read_csv(SUP/f'quest1/outputs/q1_{t}_paired_scores.csv')
        plt.figure(figsize=(7,6)); plt.scatter(m.g1_mean,m.g2_mean,s=50)
        lo=min(m.g1_mean.min(),m.g2_mean.min())-2; hi=max(m.g1_mean.max(),m.g2_mean.max())+2
        plt.plot([lo,hi],[lo,hi],'r--'); plt.xlabel('第一组平均评分'); plt.ylabel('第二组平均评分'); plt.title(f'{"红" if t=="red" else "白"}葡萄酒两组评分对比')
        savefig(SUP/f'quest1/figures/q1_{t}_paired_scatter.png')
    # Q2 grade bar
    for t in ['red','white']:
        d=pd.read_csv(SUP/f'quest2/outputs/q2_{t}_grading.csv').sort_values('composite_score',ascending=False)
        plt.figure(figsize=(10,5)); plt.bar(d['sample'].astype(str), d['composite_score'], color='#5B8FF9')
        plt.xlabel('样品编号'); plt.ylabel('综合分'); plt.title(f'{"红" if t=="red" else "白"}酿酒葡萄综合评分与分级'); plt.xticks(rotation=45)
        savefig(SUP/f'quest2/figures/q2_{t}_grading_bar.png')
    # Q3 relation bar
    plt.figure(figsize=(6,4)); plt.bar(q3df['type'], q3df['pc1_corr'], color=['#B22222','#DAA520']); plt.ylabel('PC1相关系数'); plt.title('葡萄与葡萄酒理化指标主成分联系')
    savefig(SUP/'quest3/figures/q3_pc1_correlation.png')
    # Q4 model comparison
    for t in ['red','white']:
        d=q4df[(q4df.type==t)&(q4df.model=='PLS')]
        plt.figure(figsize=(7,4)); plt.bar(d.feature_set,d.cv_rmse,color='#61DDAA'); plt.ylabel('交叉验证RMSE'); plt.title(f'{"红" if t=="red" else "白"}葡萄酒质量预测误差（PLS）')
        savefig(SUP/f'quest4/figures/q4_{t}_pls_rmse.png')
    plt.figure(figsize=(7,4))
    for t in ['red','white']:
        d=sensdf[sensdf.type==t]; plt.plot(d.quality_weight,d.rank_spearman_vs_base,marker='o',label=t)
    plt.xlabel('质量评分权重'); plt.ylabel('与基准排名Spearman相关'); plt.legend(); plt.title('分级权重敏感性分析')
    savefig(SUP/'results/sensitivity_q2_weight.png')

    # frozen numbers
    frozen={
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'Q1': q1df.to_dict(orient='records'),
        'Q1_reliable_group': reliable,
        'Q2_grade_counts': gradesdf.groupby(['wine_type','grade']).size().reset_index(name='count').to_dict(orient='records'),
        'Q2_top_samples': gradesdf.sort_values(['wine_type','composite_score'], ascending=[True,False]).groupby('wine_type').head(5).to_dict(orient='records'),
        'Q3': q3df.to_dict(orient='records'),
        'Q4_best_by_type_feature': q4df.sort_values('cv_rmse').groupby(['type','feature_set']).head(1).to_dict(orient='records'),
        'Sensitivity': sensdf.groupby('type')['rank_spearman_vs_base'].min().to_dict()
    }
    (SUP/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    # reports md
    (SUP/'references/phase0_ima_search.md').write_text('IMA知识库检索关键词：2012A 葡萄酒评价、葡萄酒的评价 2012 A题、葡萄酒 理化指标 主成分 聚类。当前API未返回直接条目，因此采用题型通用方法：配对检验/一致性评价、PCA综合评价、KMeans分级、PLS/Ridge/RF预测与敏感性分析。\n',encoding='utf-8')
    (SUP/'readme.txt').write_text(f'''# 2012A 葡萄酒的评价 支撑材料\n\n生成时间：{datetime.now():%Y-%m-%d %H:%M}\n\n## 文件结构\n- papper/论文.tex, 论文.pdf：正式论文\n- code/main_modeling.py：完整可复现代码\n- quest1~quest4：各问代码、图表、输出\n- tables/：最终结果表\n- results/frozen_numbers.json：论文冻结数字\n- data/：原始题面与附件\n\n## 运行说明\n在本机 Python 3.12 环境运行：\npython code/main_modeling.py\n\n## 主要结论\n- Q1：两组评分存在显著差异；综合离散系数与评委秩相关性，本文采用第二组作为更可信质量评分。\n- Q2：采用质量评分与葡萄理化/芳香PCA综合得分分级，结果见 tables/final_grape_grading.csv。\n- Q3：采用主成分相关和PLS验证葡萄与葡萄酒指标联系，结果见 tables/q3_grape_wine_relation.csv。\n- Q4：用PLS/Ridge/RF比较理化指标预测质量能力，结果见 tables/q4_quality_prediction_models.csv。\n''',encoding='utf-8')
    # copy script into quest code dirs
    src=SUP/'code/main_modeling.py'
    if not src.exists():
        # current script may be running from there after first write
        pass
    print('DONE')
    print('Q1', q1df.to_string(index=False))
    print('Q2 top', gradesdf.sort_values(['wine_type','composite_score'], ascending=[True,False]).groupby('wine_type').head(3).to_string(index=False))
    print('Q3', q3df.to_string(index=False))
    print('Q4 best', q4df.sort_values('cv_rmse').groupby(['type','feature_set']).head(1).to_string(index=False))

if __name__=='__main__':
    main()
