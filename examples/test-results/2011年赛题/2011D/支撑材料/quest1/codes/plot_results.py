from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
figdir=ROOT/'quest1/figures'; figdir.mkdir(parents=True,exist_ok=True)
plt.rcParams['font.sans-serif']=['SimHei','Microsoft YaHei','Arial Unicode MS']
plt.rcParams['axes.unicode_minus']=False
raw=pd.read_csv(ROOT/'tables/raw_material_counts.csv')
usage=pd.read_csv(ROOT/'tables/material_usage_by_length.csv')
summary=pd.read_csv(ROOT/'tables/summary_by_spec.csv')
plan=pd.read_csv(ROOT/'tables/final_matching_plan.csv')
# 图1 原料分布
fig,ax=plt.subplots(figsize=(12,5))
ax.bar(raw['length'], raw['available'], width=0.42, color='#4C78A8')
ax.set_xlabel('原料长度档/m'); ax.set_ylabel('根数'); ax.set_title('表2原料长度分布')
ax.grid(axis='y',alpha=.25)
plt.tight_layout(); plt.savefig(figdir/'fig1_raw_material_distribution.png',dpi=300,bbox_inches='tight'); plt.close()
# 图2 各规格捆数
fig,ax=plt.subplots(figsize=(7,5))
order=['L','M','S']; vals=[int((plan['spec']==s).sum()) for s in order]
labels=['14米以上规格','7-13.5米规格','3-6.5米规格']
ax.bar(labels, vals, color=['#2F5597','#70AD47','#FFC000'])
for i,v in enumerate(vals): ax.text(i,v+1,str(v),ha='center')
ax.set_ylabel('成品捆数'); ax.set_title('最终方案各规格成品数量')
plt.xticks(rotation=12); plt.tight_layout(); plt.savefig(figdir/'fig2_bundle_counts_by_spec.png',dpi=300,bbox_inches='tight'); plt.close()
# 图3 使用与剩余堆叠
fig,ax=plt.subplots(figsize=(12,5))
used=usage[['used_L','used_M','used_S']].sum(axis=1)
ax.bar(usage['length'], used, width=.42, label='已使用', color='#70AD47')
ax.bar(usage['length'], usage['unused'], bottom=used, width=.42, label='剩余', color='#D9D9D9')
ax.set_xlabel('原料长度档/m'); ax.set_ylabel('根数'); ax.set_title('各长度档原料使用与剩余情况')
ax.legend(); ax.grid(axis='y',alpha=.25)
plt.tight_layout(); plt.savefig(figdir/'fig3_usage_vs_unused_by_length.png',dpi=300,bbox_inches='tight'); plt.close()
# 图4 单捆长度分布
fig,ax=plt.subplots(figsize=(8,5))
plan['total_length'].hist(ax=ax,bins=[88.45,88.75,89.25,89.55],color='#5B9BD5',edgecolor='white')
ax.set_xlabel('单捆总长度/m'); ax.set_ylabel('捆数'); ax.set_title('单捆总长度分布（均满足88.5-89.5m）')
plt.tight_layout(); plt.savefig(figdir/'fig4_bundle_length_distribution.png',dpi=300,bbox_inches='tight'); plt.close()
print('figures saved', figdir)
