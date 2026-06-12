# -*- coding: utf-8 -*-
"""
2011年CUMCM A题：城市表层土壤重金属污染分析
生成支撑材料、表格、图表和冻结数字。
"""
from __future__ import annotations
import json, math, os, shutil, warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import seaborn as sns
from scipy.interpolate import griddata
from scipy.spatial import cKDTree
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score

warnings.filterwarnings('ignore')
np.random.seed(42)

ROOT = Path(r"<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011A")
OUT = ROOT / "支撑材料"
DATA_FILE = ROOT / "cumcm2011A附件_数据.xls"
RAW_DIR = OUT / "data_raw"
CLEAN_DIR = OUT / "data_clean"
TABLE_DIR = OUT / "tables"
RESULT_DIR = OUT / "results"
PAPER_DIR = OUT / "papper"
QUEST_DIRS = {i: OUT / f"quest{i}" for i in range(1,5)}
for d in [OUT, RAW_DIR, CLEAN_DIR, TABLE_DIR, RESULT_DIR, PAPER_DIR]: d.mkdir(parents=True, exist_ok=True)
for q,d in QUEST_DIRS.items():
    for sub in ["codes","figures","outputs"]: (d/sub).mkdir(parents=True, exist_ok=True)

# font
plt.rcParams['font.sans-serif'] = ['SimHei','Microsoft YaHei','SimSun']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style('whitegrid', {'font.sans-serif':['SimHei','Microsoft YaHei','SimSun']})

ELEMENTS = ['As','Cd','Cr','Cu','Hg','Ni','Pb','Zn']
UNIT = {'As':'μg/g','Cd':'ng/g','Cr':'μg/g','Cu':'μg/g','Hg':'ng/g','Ni':'μg/g','Pb':'μg/g','Zn':'μg/g'}
AREA_NAMES = {1:'生活区',2:'工业区',3:'山区',4:'交通区',5:'公园绿地区'}
# Hakanson toxic response coefficients, common literature values
TOX = {'As':10,'Cd':30,'Cr':2,'Cu':5,'Hg':40,'Ni':5,'Pb':5,'Zn':1}


def read_data():
    loc = pd.read_excel(DATA_FILE, sheet_name='附件1', header=2, usecols=[0,1,2,3,4])
    loc.columns = ['编号','x','y','海拔','功能区']
    loc = loc.dropna(subset=['编号']).copy()
    loc['编号'] = loc['编号'].astype(int)
    for c in ['x','y','海拔','功能区']: loc[c]=pd.to_numeric(loc[c], errors='coerce')
    loc['功能区'] = loc['功能区'].astype(int)
    loc['功能区名称'] = loc['功能区'].map(AREA_NAMES)

    conc = pd.read_excel(DATA_FILE, sheet_name='附件2', header=2, usecols=list(range(9)))
    conc.columns = ['编号'] + ELEMENTS
    conc = conc.dropna(subset=['编号']).copy(); conc['编号']=conc['编号'].astype(int)
    for e in ELEMENTS: conc[e]=pd.to_numeric(conc[e], errors='coerce')

    bg = pd.read_excel(DATA_FILE, sheet_name='附件3', header=2, usecols=[0,1,2,3])
    bg.columns = ['元素原名','背景均值','背景标准差','范围']
    bg = bg.dropna(subset=['元素原名']).copy()
    bg['元素'] = ELEMENTS
    bg['背景均值'] = pd.to_numeric(bg['背景均值'], errors='coerce')
    bg['背景标准差'] = pd.to_numeric(bg['背景标准差'], errors='coerce')
    bg = bg[['元素','背景均值','背景标准差','范围']]
    df = loc.merge(conc, on='编号', how='inner')
    return df, bg


def pollution_indices(df, bg):
    bg_mean = dict(zip(bg['元素'], bg['背景均值']))
    out = df.copy()
    cf_cols=[]; igeo_cols=[]; er_cols=[]
    for e in ELEMENTS:
        cf = f'{e}_Cf'; ig=f'{e}_Igeo'; er=f'{e}_Er'
        out[cf] = out[e] / bg_mean[e]
        out[ig] = np.log2(out[e] / (1.5 * bg_mean[e]))
        out[er] = TOX[e] * out[cf]
        cf_cols.append(cf); igeo_cols.append(ig); er_cols.append(er)
    out['综合污染指数PN'] = np.sqrt((out[cf_cols].mean(axis=1)**2 + out[cf_cols].max(axis=1)**2)/2)
    out['潜在生态风险RI'] = out[er_cols].sum(axis=1)
    def pn_level(v):
        if v <= 0.7: return '安全'
        if v <= 1: return '警戒线'
        if v <= 2: return '轻度污染'
        if v <= 3: return '中度污染'
        return '重度污染'
    def ri_level(v):
        if v < 150: return '低风险'
        if v < 300: return '中等风险'
        if v < 600: return '较强风险'
        return '很强风险'
    out['PN等级'] = out['综合污染指数PN'].map(pn_level)
    out['RI等级'] = out['潜在生态风险RI'].map(ri_level)
    return out


def idw_grid(x, y, z, nx=180, ny=180, power=2):
    xi = np.linspace(min(x), max(x), nx); yi = np.linspace(min(y), max(y), ny)
    xx, yy = np.meshgrid(xi, yi)
    pts = np.c_[x,y]
    tree = cKDTree(pts)
    q = np.c_[xx.ravel(), yy.ravel()]
    k = min(12, len(pts))
    dist, idx = tree.query(q, k=k)
    dist = np.asarray(dist); idx=np.asarray(idx)
    if k == 1: dist=dist[:,None]; idx=idx[:,None]
    weights = 1 / np.maximum(dist, 1e-6)**power
    zz = np.sum(weights * np.asarray(z)[idx], axis=1) / np.sum(weights, axis=1)
    return xx, yy, zz.reshape(xx.shape)


def save_spatial_maps(df):
    # 8 element spatial maps, using pollution factor Cf for comparability
    for e in ELEMENTS:
        xx, yy, zz = idw_grid(df['x'].values, df['y'].values, df[f'{e}_Cf'].values)
        fig, ax = plt.subplots(figsize=(8,6.5))
        cs = ax.contourf(xx, yy, zz, levels=18, cmap='YlOrRd')
        sc = ax.scatter(df['x'], df['y'], c=df[f'{e}_Cf'], s=12, cmap='YlOrRd', edgecolor='k', linewidth=0.15)
        ax.set_title(f'{e}污染累积倍数空间分布（相对背景值）')
        ax.set_xlabel('x/m'); ax.set_ylabel('y/m')
        fig.colorbar(cs, ax=ax, label='Cf=实测浓度/背景值')
        fig.tight_layout()
        fig.savefig(QUEST_DIRS[1]/'figures'/f'问题1_{e}_空间分布.png', dpi=300, bbox_inches='tight')
        plt.close(fig)
    # comprehensive PN map
    xx, yy, zz = idw_grid(df['x'].values, df['y'].values, df['综合污染指数PN'].values)
    fig, ax = plt.subplots(figsize=(8,6.5))
    cs = ax.contourf(xx, yy, zz, levels=20, cmap='Reds')
    ax.scatter(df['x'], df['y'], c=df['综合污染指数PN'], s=13, cmap='Reds', edgecolor='k', linewidth=0.15)
    ax.set_title('综合污染指数PN空间分布')
    ax.set_xlabel('x/m'); ax.set_ylabel('y/m')
    fig.colorbar(cs, ax=ax, label='Nemerow综合污染指数')
    fig.tight_layout(); fig.savefig(QUEST_DIRS[1]/'figures'/'问题1_综合污染指数空间分布.png', dpi=300, bbox_inches='tight'); plt.close(fig)


def area_stats(df, bg):
    cf_cols=[f'{e}_Cf' for e in ELEMENTS]
    er_cols=[f'{e}_Er' for e in ELEMENTS]
    agg = df.groupby(['功能区','功能区名称']).agg(
        样本数=('编号','count'), 平均PN=('综合污染指数PN','mean'), 最大PN=('综合污染指数PN','max'),
        平均RI=('潜在生态风险RI','mean'), 最大RI=('潜在生态风险RI','max')
    ).reset_index()
    for e in ELEMENTS:
        agg[f'{e}均值'] = df.groupby(['功能区','功能区名称'])[e].mean().values
        agg[f'{e}累积倍数'] = df.groupby(['功能区','功能区名称'])[f'{e}_Cf'].mean().values
    agg = agg.sort_values('平均PN', ascending=False)
    agg.to_csv(TABLE_DIR/'功能区污染统计.csv', index=False, encoding='utf-8-sig')
    agg.to_csv(QUEST_DIRS[1]/'outputs'/'功能区污染统计.csv', index=False, encoding='utf-8-sig')
    # plots
    fig, axes = plt.subplots(1,2,figsize=(13,5))
    order=agg['功能区名称']
    sns.barplot(data=agg, x='功能区名称', y='平均PN', ax=axes[0], order=order, palette='Reds_r')
    axes[0].set_title('不同功能区平均综合污染指数PN'); axes[0].set_xlabel(''); axes[0].set_ylabel('平均PN')
    sns.barplot(data=agg, x='功能区名称', y='平均RI', ax=axes[1], order=order, palette='Oranges_r')
    axes[1].set_title('不同功能区平均潜在生态风险RI'); axes[1].set_xlabel(''); axes[1].set_ylabel('平均RI')
    for ax in axes: ax.tick_params(axis='x', rotation=20)
    fig.tight_layout(); fig.savefig(QUEST_DIRS[1]/'figures'/'问题1_功能区污染程度对比.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    # heatmap of enrichment by area
    mat = agg.set_index('功能区名称')[[f'{e}累积倍数' for e in ELEMENTS]]
    fig, ax = plt.subplots(figsize=(10,5.5))
    sns.heatmap(mat, annot=True, fmt='.1f', cmap='YlOrRd', ax=ax, cbar_kws={'label':'平均累积倍数'})
    ax.set_title('各功能区8种重金属相对背景值累积倍数')
    fig.tight_layout(); fig.savefig(QUEST_DIRS[1]/'figures'/'问题1_功能区元素累积热力图.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    return agg


def source_analysis(df):
    X = np.log1p(df[ELEMENTS].values)
    scaler = StandardScaler(); Xs = scaler.fit_transform(X)
    corr = pd.DataFrame(Xs, columns=ELEMENTS).corr()
    corr.to_csv(TABLE_DIR/'元素相关系数矩阵.csv', encoding='utf-8-sig')
    fig, ax = plt.subplots(figsize=(8,6.5)); sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0, ax=ax)
    ax.set_title('重金属元素浓度相关系数矩阵（log1p标准化前相关）')
    fig.tight_layout(); fig.savefig(QUEST_DIRS[2]/'figures'/'问题2_元素相关系数热力图.png', dpi=300, bbox_inches='tight'); plt.close(fig)

    pca = PCA(n_components=4, random_state=42).fit(Xs)
    scores = pca.transform(Xs)
    loadings = pd.DataFrame(pca.components_.T, index=ELEMENTS, columns=[f'PC{i+1}' for i in range(4)])
    evr = pd.DataFrame({'主成分':[f'PC{i+1}' for i in range(4)], '方差贡献率':pca.explained_variance_ratio_, '累计贡献率':np.cumsum(pca.explained_variance_ratio_)})
    loadings.to_csv(TABLE_DIR/'PCA载荷矩阵.csv', encoding='utf-8-sig')
    evr.to_csv(TABLE_DIR/'PCA方差贡献率.csv', index=False, encoding='utf-8-sig')
    loadings.to_csv(QUEST_DIRS[2]/'outputs'/'PCA载荷矩阵.csv', encoding='utf-8-sig')
    evr.to_csv(QUEST_DIRS[2]/'outputs'/'PCA方差贡献率.csv', index=False, encoding='utf-8-sig')
    fig, axes = plt.subplots(1,2,figsize=(13,5))
    sns.barplot(data=evr, x='主成分', y='方差贡献率', ax=axes[0], palette='Blues')
    axes[0].set_title('主成分方差贡献率')
    sns.heatmap(loadings, annot=True, fmt='.2f', cmap='coolwarm', center=0, ax=axes[1])
    axes[1].set_title('主成分载荷矩阵')
    fig.tight_layout(); fig.savefig(QUEST_DIRS[2]/'figures'/'问题2_PCA贡献率与载荷.png', dpi=300, bbox_inches='tight'); plt.close(fig)

    # KMeans cluster in concentration profile
    best=[]
    for k in range(2,7):
        lab=KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(Xs)
        best.append((k, silhouette_score(Xs, lab)))
    best_df=pd.DataFrame(best, columns=['K','轮廓系数']); best_df.to_csv(TABLE_DIR/'KMeans轮廓系数.csv', index=False, encoding='utf-8-sig')
    k=int(best_df.sort_values('轮廓系数', ascending=False).iloc[0]['K'])
    labels=KMeans(n_clusters=k, random_state=42, n_init=30).fit_predict(Xs)
    df_cluster=df[['编号','x','y','功能区名称']+ELEMENTS+['综合污染指数PN','潜在生态风险RI']].copy(); df_cluster['污染谱聚类']=labels+1
    profile=df_cluster.groupby('污染谱聚类')[ELEMENTS+['综合污染指数PN','潜在生态风险RI']].mean()
    profile.to_csv(TABLE_DIR/'污染谱聚类中心.csv', encoding='utf-8-sig')
    df_cluster.to_csv(QUEST_DIRS[2]/'outputs'/'污染谱聚类结果.csv', index=False, encoding='utf-8-sig')
    fig, ax=plt.subplots(figsize=(8,6.5))
    sns.scatterplot(data=df_cluster, x='x', y='y', hue='污染谱聚类', style='功能区名称', palette='tab10', ax=ax, s=45)
    ax.set_title(f'采样点污染谱KMeans聚类空间分布（K={k}）')
    ax.set_xlabel('x/m'); ax.set_ylabel('y/m'); ax.legend(bbox_to_anchor=(1.02,1), loc='upper left', fontsize=8)
    fig.tight_layout(); fig.savefig(QUEST_DIRS[2]/'figures'/'问题2_污染谱聚类空间分布.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    return pca, scores, loadings, evr, best_df, k, profile


def identify_sources(df, scores, loadings):
    # Interpret factors by positive loading elements and locate maxima of IDW score field
    sources=[]
    for pc in range(min(4, scores.shape[1])):
        sc = scores[:,pc]
        if np.abs(sc).max() == 0: continue
        # orient so sum of top positive loadings is positive; use raw high scores for high concentration pattern
        xx, yy, zz = idw_grid(df['x'].values, df['y'].values, sc)
        # top grid maxima (separated)
        flat_idx=np.argsort(zz.ravel())[::-1]
        chosen=[]
        for idx in flat_idx:
            x=float(xx.ravel()[idx]); y=float(yy.ravel()[idx]); val=float(zz.ravel()[idx])
            if len(chosen)==0 or all(((x-a)**2+(y-b)**2)**0.5>800 for a,b,_ in chosen):
                chosen.append((x,y,val))
            if len(chosen)>=3: break
        pos = loadings[f'PC{pc+1}'].sort_values(ascending=False)
        neg = loadings[f'PC{pc+1}'].sort_values()
        dominant = ','.join(pos.head(3).index.tolist())
        for rank,(x,y,val) in enumerate(chosen, start=1):
            near=df.assign(dist=((df['x']-x)**2+(df['y']-y)**2)**0.5).sort_values('dist').head(8)
            main_area=near['功能区名称'].mode().iloc[0]
            sources.append({'因子':f'PC{pc+1}','候选源序号':rank,'x':round(x,1),'y':round(y,1),'因子场强度':round(val,3),'主导元素':dominant,'邻近主要功能区':main_area,'邻近样点编号':','.join(map(str,near['编号'].head(5).tolist()))})
        fig, ax = plt.subplots(figsize=(8,6.5))
        cs=ax.contourf(xx, yy, zz, levels=18, cmap='coolwarm')
        ax.scatter(df['x'], df['y'], c=sc, cmap='coolwarm', edgecolor='k', linewidth=0.15, s=13)
        for rank,(x,y,val) in enumerate(chosen, start=1):
            ax.scatter([x],[y], marker='*', c='yellow', edgecolor='black', s=220)
            ax.text(x+60,y+60,f'S{pc+1}-{rank}', fontsize=9, weight='bold')
        ax.set_title(f'污染因子PC{pc+1}空间场与候选污染源位置')
        ax.set_xlabel('x/m'); ax.set_ylabel('y/m'); fig.colorbar(cs, ax=ax, label='PCA因子得分(IDW)')
        fig.tight_layout(); fig.savefig(QUEST_DIRS[3]/'figures'/f'问题3_PC{pc+1}_污染源定位.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    src=pd.DataFrame(sources)
    src.to_csv(TABLE_DIR/'候选污染源位置.csv', index=False, encoding='utf-8-sig')
    src.to_csv(QUEST_DIRS[3]/'outputs'/'候选污染源位置.csv', index=False, encoding='utf-8-sig')

    # hotspot DBSCAN on high RI/Cf points
    high=df[(df['潜在生态风险RI']>=df['潜在生态风险RI'].quantile(0.85)) | (df['综合污染指数PN']>=df['综合污染指数PN'].quantile(0.85))].copy()
    coords=high[['x','y']].values
    if len(high)>5:
        lab=DBSCAN(eps=850, min_samples=2).fit_predict(coords)
        high['热点簇']=lab
        centers=[]
        for labv in sorted(set(lab)):
            if labv==-1: continue
            sub=high[high['热点簇']==labv]
            w=sub['潜在生态风险RI'].values
            centers.append({'热点簇':int(labv+1),'x':round(np.average(sub['x'],weights=w),1),'y':round(np.average(sub['y'],weights=w),1),'样点数':len(sub),'平均RI':round(sub['潜在生态风险RI'].mean(),1),'主要功能区':sub['功能区名称'].mode().iloc[0],'代表样点':','.join(map(str,sub.sort_values('潜在生态风险RI',ascending=False)['编号'].head(5).tolist()))})
        centers=pd.DataFrame(centers).sort_values('平均RI', ascending=False)
    else:
        centers=pd.DataFrame()
    centers.to_csv(TABLE_DIR/'高风险热点簇中心.csv', index=False, encoding='utf-8-sig')
    high.to_csv(QUEST_DIRS[3]/'outputs'/'高风险热点样点.csv', index=False, encoding='utf-8-sig')
    fig, ax=plt.subplots(figsize=(8,6.5))
    ax.scatter(df['x'], df['y'], c='lightgray', s=12, label='普通样点')
    sc=ax.scatter(high['x'], high['y'], c=high['潜在生态风险RI'], cmap='Reds', s=55, edgecolor='k', label='高风险样点')
    if len(centers)>0:
        for _,r in centers.iterrows():
            ax.scatter([r['x']],[r['y']], marker='*', s=260, c='cyan', edgecolor='black')
            ax.text(r['x']+60,r['y']+60,f"H{int(r['热点簇'])}", weight='bold')
    fig.colorbar(sc, ax=ax, label='RI')
    ax.set_title('高污染样点DBSCAN热点簇与候选源中心')
    ax.set_xlabel('x/m'); ax.set_ylabel('y/m'); ax.legend(loc='best')
    fig.tight_layout(); fig.savefig(QUEST_DIRS[3]/'figures'/'问题3_高风险热点簇定位.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    return src, centers


def robustness(df, bg):
    # Background sensitivity: multiply background by 0.8..1.2 and compare area ranking / top hotspots
    bg_mean = dict(zip(bg['元素'], bg['背景均值']))
    rows=[]
    for ratio in np.linspace(0.8,1.2,9):
        temp=df.copy()
        cf_cols=[]; er_cols=[]
        for e in ELEMENTS:
            temp[f'{e}_Cf_s']=temp[e]/(bg_mean[e]*ratio)
            temp[f'{e}_Er_s']=TOX[e]*temp[f'{e}_Cf_s']
            cf_cols.append(f'{e}_Cf_s'); er_cols.append(f'{e}_Er_s')
        temp['PN_s']=np.sqrt((temp[cf_cols].mean(axis=1)**2+temp[cf_cols].max(axis=1)**2)/2)
        temp['RI_s']=temp[er_cols].sum(axis=1)
        rank=temp.groupby('功能区名称')['PN_s'].mean().sort_values(ascending=False).index.tolist()
        rows.append({'背景值扰动系数':round(float(ratio),2),'第一污染区':rank[0],'第二污染区':rank[1],'平均PN':round(float(temp['PN_s'].mean()),3),'平均RI':round(float(temp['RI_s'].mean()),1),'高风险点数RI>600':int((temp['RI_s']>=600).sum())})
    sens=pd.DataFrame(rows); sens.to_csv(TABLE_DIR/'背景值敏感性分析.csv', index=False, encoding='utf-8-sig')
    sens.to_csv(QUEST_DIRS[4]/'outputs'/'背景值敏感性分析.csv', index=False, encoding='utf-8-sig')
    fig, ax1=plt.subplots(figsize=(8,5))
    ax1.plot(sens['背景值扰动系数'], sens['平均PN'], marker='o', label='平均PN')
    ax1.set_xlabel('背景值统一扰动系数'); ax1.set_ylabel('平均PN')
    ax2=ax1.twinx(); ax2.plot(sens['背景值扰动系数'], sens['高风险点数RI>600'], marker='s', c='orange', label='RI>600点数')
    ax2.set_ylabel('高风险点数')
    ax1.set_title('背景值扰动对综合污染评价的敏感性')
    fig.tight_layout(); fig.savefig(QUEST_DIRS[4]/'figures'/'问题4_背景值敏感性分析.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    return sens


def write_docs(df, bg, area, pca, scores, loadings, evr, kbest, k, profile, sources, centers, sens):
    df.to_csv(CLEAN_DIR/'merged_clean_indices.csv', index=False, encoding='utf-8-sig')
    bg.to_csv(CLEAN_DIR/'background_values.csv', index=False, encoding='utf-8-sig')
    shutil.copy2(DATA_FILE, RAW_DIR/DATA_FILE.name)
    # data audit
    audit = {
        'data_source': str(DATA_FILE),
        'samples': int(len(df)), 'fields': list(df.columns),
        'missing_total': int(df.isna().sum().sum()),
        'duplicate_id_count': int(df['编号'].duplicated().sum()),
        'area_counts': df['功能区名称'].value_counts().to_dict(),
        'element_units': UNIT,
        'background_values': dict(zip(bg['元素'], bg['背景均值'])),
        'generated_at': datetime.now().isoformat(timespec='seconds')
    }
    (RESULT_DIR/'data_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

    top_area=area.iloc[0]
    top_ri=df.sort_values('潜在生态风险RI', ascending=False).iloc[0]
    top_pn=df.sort_values('综合污染指数PN', ascending=False).iloc[0]
    max_cf={e: float(df[f'{e}_Cf'].max()) for e in ELEMENTS}
    mean_cf={e: float(df[f'{e}_Cf'].mean()) for e in ELEMENTS}
    pc1=float(evr.loc[0,'方差贡献率']); pc2=float(evr.loc[1,'方差贡献率']); pc3=float(evr.loc[2,'方差贡献率']); pc4=float(evr.loc[3,'方差贡献率'])
    cum4=float(evr.loc[3,'累计贡献率'])
    frozen={
        'metadata': {'problem':'CUMCM 2011 A 城市表层土壤重金属污染分析','generated_at':datetime.now().isoformat(timespec='seconds'),'random_seed':42},
        'Q1': {
            'sample_count': int(len(df)),
            'area_pollution_rank_by_mean_PN': area[['功能区名称','平均PN','平均RI','样本数']].round(3).to_dict(orient='records'),
            'most_polluted_area_by_mean_PN': str(top_area['功能区名称']),
            'most_polluted_area_mean_PN': round(float(top_area['平均PN']),3),
            'highest_PN_sample': {'编号':int(top_pn['编号']),'x':float(top_pn['x']),'y':float(top_pn['y']),'PN':round(float(top_pn['综合污染指数PN']),3),'RI':round(float(top_pn['潜在生态风险RI']),1),'功能区':str(top_pn['功能区名称'])},
            'highest_RI_sample': {'编号':int(top_ri['编号']),'x':float(top_ri['x']),'y':float(top_ri['y']),'PN':round(float(top_ri['综合污染指数PN']),3),'RI':round(float(top_ri['潜在生态风险RI']),1),'功能区':str(top_ri['功能区名称'])},
            'mean_enrichment_factor': {e:round(mean_cf[e],3) for e in ELEMENTS},
            'max_enrichment_factor': {e:round(max_cf[e],3) for e in ELEMENTS},
        },
        'Q2': {
            'pca_variance_ratio': evr.round(4).to_dict(orient='records'),
            'pca_cumulative_4': round(cum4,4),
            'pc1_top_elements': loadings['PC1'].abs().sort_values(ascending=False).head(3).index.tolist(),
            'pc2_top_elements': loadings['PC2'].abs().sort_values(ascending=False).head(3).index.tolist(),
            'kmeans_best_k': k,
            'kmeans_best_silhouette': round(float(kbest.sort_values('轮廓系数', ascending=False).iloc[0]['轮廓系数']),3)
        },
        'Q3': {
            'factor_source_candidates': sources.head(12).to_dict(orient='records'),
            'hotspot_centers': centers.to_dict(orient='records') if len(centers)>0 else []
        },
        'Q4': {
            'background_sensitivity': sens.to_dict(orient='records'),
            'ranking_stable_first_area': bool((sens['第一污染区']==sens['第一污染区'].iloc[len(sens)//2]).all())
        }
    }
    (RESULT_DIR/'frozen_numbers.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')
    (QUEST_DIRS[4]/'outputs'/'frozen_numbers.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')

    # gate files
    planning=OUT/'planning'; planning.mkdir(exist_ok=True)
    (planning/'problem_parse.md').write_text(f"""# G1 题目解析

## 子问题映射
1. 问题一：题目要求给出8种重金属空间分布并分析不同功能区污染程度；模型输出为8张元素累积倍数IDW分布图、综合污染指数PN图、功能区PN/RI统计排序。
2. 问题二：题目要求说明污染主要原因；模型输出为元素相关矩阵、PCA载荷、污染谱聚类，并据元素组合解释工业、交通、生活/绿地等来源。
3. 问题三：题目要求分析传播特征并确定污染源位置；模型输出为PCA因子空间场极值点和高风险DBSCAN热点簇中心。
4. 问题四：题目要求评价模型并提出补充信息与后续模型；输出为敏感性分析、模型优缺点和演变模型框架。

## 数据清单
- 附件1：{len(df)}个采样点位置、海拔和功能区；
- 附件2：8种重金属浓度；
- 附件3：8种元素背景均值、标准差与范围。
""", encoding='utf-8')
    (OUT/'readme.txt').write_text(f"""# 2011A 支撑材料说明

## 项目信息
- 题目：城市表层土壤重金属污染分析（2011年高教社杯A题）
- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 样本量：{len(df)} 个采样点，8 种重金属元素

## 文件结构
- papper/：论文Markdown、LaTeX源文件、PDF
- quest1/：空间分布与功能区污染评价代码、图表、输出
- quest2/：污染原因识别（相关/PCA/聚类）代码、图表、输出
- quest3/：传播特征与污染源定位图表、输出
- quest4/：模型评价、敏感性分析与改进材料
- tables/：论文表格CSV
- results/：数据审计、冻结数字frozen_numbers.json
- data_raw/ 与 data_clean/：原始附件和清洗后数据

## 运行说明
Python依赖：numpy pandas scipy scikit-learn matplotlib seaborn xlrd。
从本目录上一级运行：python 支撑材料/main_modeling.py
论文编译：cd 支撑材料/papper && xelatex 论文.tex 运行3遍。

## 主要结果摘要
- 平均PN最高功能区：{top_area['功能区名称']}，平均PN={float(top_area['平均PN']):.3f}。
- 最高RI采样点：编号{int(top_ri['编号'])}，位置({float(top_ri['x']):.0f}, {float(top_ri['y']):.0f})，RI={float(top_ri['潜在生态风险RI']):.1f}。
- 前4个PCA主成分累计解释率：{cum4*100:.2f}%。
- KMeans污染谱最佳K={k}，轮廓系数={float(kbest.sort_values('轮廓系数', ascending=False).iloc[0]['轮廓系数']):.3f}。
""", encoding='utf-8')
    return frozen


def main():
    df0,bg=read_data()
    df=pollution_indices(df0,bg)
    save_spatial_maps(df)
    area=area_stats(df,bg)
    pca,scores,loadings,evr,kbest,k,profile=source_analysis(df)
    sources,centers=identify_sources(df,scores,loadings)
    sens=robustness(df,bg)
    frozen=write_docs(df,bg,area,pca,scores,loadings,evr,kbest,k,profile,sources,centers,sens)
    print(json.dumps({
        'status':'ok','out':str(OUT),'sample_count':len(df),
        'most_polluted_area':frozen['Q1']['most_polluted_area_by_mean_PN'],
        'paper_inputs_ready':True
    }, ensure_ascii=False, indent=2))

if __name__=='__main__':
    main()
