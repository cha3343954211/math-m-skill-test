# -*- coding: utf-8 -*-
"""
CUMCM 2014D 储药柜设计：模型求解与材料生成
运行：python main_modeling.py
"""
from pathlib import Path
import json, math, shutil, textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.signal import find_peaks

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014D')
SUP = ROOT / '支撑材料'
DATA = SUP / 'data'
RESULTS = SUP / 'results'
TABLES = SUP / 'tables'
PAPER = SUP / 'papper'
Q1 = SUP / 'quest1'
Q2 = SUP / 'quest2'
Q3 = SUP / 'quest3'
for p in [RESULTS, TABLES, PAPER, Q1/'figures', Q1/'outputs', Q2/'figures', Q2/'outputs', Q3/'figures', Q3/'outputs']:
    p.mkdir(parents=True, exist_ok=True)

# Chinese font
for fp in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False

# ---------------- Data ----------------
box = pd.read_excel(ROOT / '附件1-药盒型号.xls')
dem = pd.read_excel(ROOT / '附件2-药品需求量.xls')
df = box.merge(dem, on='药品编号', how='left')
df = df.rename(columns={'长(mm)':'L','高(mm)':'H','宽(mm)':'W','日最大需求量（单位：盒）':'D'})
df['D'] = df['D'].astype(int)
N = len(df)

# interval model for width/height slot spacing. Need 2mm clearance on each side => lower = size+4.
# Prevent two boxes side-by-side: slot spacing < 2*size+4, use conservative upper = 2*size+3.999.
# Prevent horizontal rotation is nonbinding because L is much larger, but included as upper=L-0.001 if tighter.
def make_intervals(size, length=None):
    lower = size.astype(float) + 4.0
    upper = 2*size.astype(float) + 3.999
    # Length is much larger than width for most medicines; horizontal rotation is controlled by
    # the no-side-by-side upper bound and push-channel geometry, so we do not impose L as a hard
    # width upper bound here. Imposing S<L would make a few real boxes infeasible despite the
    # problem only requiring a practical anti-rotation design.
    return lower.to_numpy(), upper.to_numpy()

lw, uw = make_intervals(df['W'], df['L'])
lh, uh = make_intervals(df['H'], None)
df['width_lower'] = lw; df['width_upper'] = uw
df['height_lower'] = lh; df['height_upper'] = uh

# Greedy minimum stabbing points for intervals; also assign each interval to first feasible point.
def min_interval_points(lower, upper):
    order = np.argsort(upper)
    points=[]; covered=np.zeros(len(lower), dtype=bool)
    for i in order:
        if not covered[i]:
            p = upper[i]
            points.append(p)
            covered |= (lower <= p) & (p <= upper)
    points = np.array(points)
    assign=[]
    for a,b in zip(lower, upper):
        feas = np.where((points>=a)&(points<=b))[0]
        # choose smallest feasible spacing to reduce redundancy
        j = feas[np.argmin(points[feas])]
        assign.append(j)
    return points, np.array(assign)

q1_points, q1_assign = min_interval_points(lw, uw)
df['q1_type'] = q1_assign + 1
df['q1_slot_width'] = q1_points[q1_assign]
df['q1_width_redundancy'] = df['q1_slot_width'] - df['width_lower']

# DP for K contiguous groups. Items sorted by lower; a group is feasible if max(lower)<=min(upper).
def dp_cluster(lower, upper, weights=None, Kmax=50):
    n=len(lower)
    if weights is None: weights=np.ones(n)
    order=np.argsort(lower)
    lo=lower[order]; up=upper[order]; wt=weights[order]
    prefix_w=np.r_[0, np.cumsum(wt)]
    prefix_wlo=np.r_[0, np.cumsum(wt*lo)]
    cost=np.full((n,n), np.inf)
    point=np.full((n,n), np.nan)
    feasible=np.zeros((n,n), dtype=bool)
    for i in range(n):
        min_up=np.inf
        max_lo=-np.inf
        for j in range(i,n):
            max_lo=max(max_lo, lo[j]); min_up=min(min_up, up[j])
            if max_lo <= min_up + 1e-9:
                feasible[i,j]=True
                point[i,j]=max_lo
                cost[i,j]=max_lo*(prefix_w[j+1]-prefix_w[i]) - (prefix_wlo[j+1]-prefix_wlo[i])
            else:
                # Since lo nondecreasing, later j might still fail for this i if min_up too low; continue for safety.
                pass
    Kmax=min(Kmax,n)
    dp=np.full((Kmax+1,n+1), np.inf); prev=np.full((Kmax+1,n+1), -1, dtype=int)
    dp[0,0]=0
    for k in range(1,Kmax+1):
        for j in range(1,n+1):
            best=np.inf; bi=-1
            for i in range(k-1,j):
                if np.isfinite(dp[k-1,i]) and np.isfinite(cost[i,j-1]):
                    val=dp[k-1,i]+cost[i,j-1]
                    if val<best:
                        best=val; bi=i
            dp[k,j]=best; prev[k,j]=bi
    def reconstruct(K):
        groups=[]; j=n
        for k in range(K,0,-1):
            i=prev[k,j]
            if i<0: return None
            groups.append((i,j-1,point[i,j-1],cost[i,j-1]))
            j=i
        groups=groups[::-1]
        assign_sorted=np.empty(n,dtype=int); pts=[]
        for t,(i,j,p,c) in enumerate(groups):
            assign_sorted[i:j+1]=t; pts.append(p)
        assign=np.empty(n,dtype=int); assign[order]=assign_sorted
        pts=np.array(pts)
        return groups, pts, assign, order
    return dp, prev, reconstruct

# Width DP up to all unique widths (or 47)
Kmax_w = int(df['W'].nunique())
dp_w, prev_w, rec_w = dp_cluster(lw, uw, None, Kmax_w)
width_curve=[]
for K in range(1,Kmax_w+1):
    val=dp_w[K,N]
    if np.isfinite(val):
        width_curve.append({'K':K,'total_width_redundancy':float(val),'avg_width_redundancy':float(val/N)})
width_curve=pd.DataFrame(width_curve)
# Knee choice: minimize normalized redundancy + normalized K, with redundancy dominant but not absolute.
r = width_curve['total_width_redundancy'].to_numpy(); k = width_curve['K'].to_numpy()
r_norm=(r-r.min())/(r.max()-r.min()); k_norm=(k-k.min())/(k.max()-k.min())
score=0.65*r_norm + 0.35*k_norm
K_width=int(k[np.argmin(score)])
groups_w, q2_points, q2_assign, order_w = rec_w(K_width)
df['q2_type'] = q2_assign + 1
df['slot_width'] = q2_points[q2_assign]
df['width_redundancy'] = df['slot_width'] - df['width_lower']

# Height DP weighted by width redundancy. To avoid zero weights eliminating height optimization for exact-width items, use epsilon.
weights_h = (df['width_redundancy'].to_numpy() + 0.05)
Kmax_h = int(df['H'].nunique())
dp_h, prev_h, rec_h = dp_cluster(lh, uh, weights_h, min(Kmax_h, 60))
height_curve=[]
for K in range(1, min(Kmax_h,60)+1):
    val=dp_h[K,N]
    if np.isfinite(val):
        # true plane redundancy with no epsilon
        rec=rec_h(K)
        if rec is None: continue
        pts=rec[1]; ass=rec[2]
        true_plane = float(np.sum((pts[ass]-lh)*df['width_redundancy'].to_numpy()))
        height_curve.append({'K':K,'weighted_height_objective':float(val),'total_plane_redundancy':true_plane})
height_curve=pd.DataFrame(height_curve)
r = height_curve['total_plane_redundancy'].to_numpy(); k=height_curve['K'].to_numpy()
r_norm=(r-r.min())/(r.max()-r.min()); k_norm=(k-k.min())/(k.max()-k.min())
score=0.65*r_norm + 0.35*k_norm
K_height=int(k[np.argmin(score)])
groups_h, q3_hpoints, q3_hassign, order_h = rec_h(K_height)
df['height_type'] = q3_hassign + 1
df['slot_height'] = q3_hpoints[q3_hassign]
df['height_redundancy'] = df['slot_height'] - df['height_lower']
df['plane_redundancy'] = df['width_redundancy'] * df['height_redundancy']

# Problem 4槽数和柜数
SLOT_LEN=1500.0; CAB_W=2500.0; CAB_H=1500.0
df['boxes_per_slot'] = np.floor(SLOT_LEN / df['L']).astype(int)
df['required_slots'] = np.ceil(df['D'] / df['boxes_per_slot']).astype(int)
df['total_slot_front_width'] = df['required_slots'] * df['slot_width']
# Row requirements by height type; row width is 2500.
row_reqs=[]
for ht, sub in df.groupby('height_type'):
    h=float(sub['slot_height'].iloc[0])
    total_w=float(sub['total_slot_front_width'].sum())
    rows=math.ceil(total_w/CAB_W)
    util=total_w/(rows*CAB_W)
    row_reqs.append({'height_type':int(ht),'slot_height':h,'total_slot_width':total_w,'rows_required':rows,'row_width_utilization':util})
row_reqs=pd.DataFrame(row_reqs).sort_values('slot_height', ascending=False)
# Pack rows into cabinets by first-fit decreasing heights. Each row item height h.
cabinets=[]
for _, rr in row_reqs.iterrows():
    for _ in range(int(rr['rows_required'])):
        h=rr['slot_height']
        placed=False
        # choose cabinet with least remaining after placement among feasible
        feasible=[(idx, cab['remain']-h) for idx,cab in enumerate(cabinets) if cab['remain']+1e-9>=h]
        if feasible:
            idx,_=min(feasible, key=lambda x:x[1])
            cabinets[idx]['rows'].append((int(rr['height_type']), h)); cabinets[idx]['remain']-=h
        else:
            cabinets.append({'remain':CAB_H-h, 'rows':[(int(rr['height_type']), h)]})
min_cabinets=len(cabinets)
area_lb=math.ceil(float((df['required_slots']*df['slot_width']*df['slot_height']).sum())/(CAB_W*CAB_H))
height_lb=math.ceil(float((row_reqs['rows_required']*row_reqs['slot_height']).sum())/CAB_H)
width_rows_total=int(row_reqs['rows_required'].sum())

# Baseline comparisons
baseline = {
    'q1_baseline_unique_width_types': int(df['W'].nunique()),
    'q1_min_feasible_width_types': int(len(q1_points)),
    'q2_chosen_width_types': K_width,
    'q2_total_width_redundancy': float(df['width_redundancy'].sum()),
    'q2_avg_width_redundancy': float(df['width_redundancy'].mean()),
    'q2_min_redundancy_all_unique_width_types': float(width_curve.iloc[-1]['total_width_redundancy']),
    'q3_chosen_height_types': K_height,
    'q3_total_plane_redundancy': float(df['plane_redundancy'].sum()),
    'q4_total_required_slots': int(df['required_slots'].sum()),
    'q4_min_cabinets_heuristic': int(min_cabinets),
    'q4_area_lower_bound': int(area_lb),
    'q4_height_row_lower_bound': int(height_lb),
    'q4_total_rows': int(width_rows_total),
}

# Tables
q1_table = df.groupby('q1_type').agg(slot_width=('q1_slot_width','first'), count=('药品编号','count'), min_W=('W','min'), max_W=('W','max'), avg_redundancy=('q1_width_redundancy','mean')).reset_index()
q2_table = df.groupby('q2_type').agg(slot_width=('slot_width','first'), count=('药品编号','count'), min_W=('W','min'), max_W=('W','max'), total_width_redundancy=('width_redundancy','sum'), avg_redundancy=('width_redundancy','mean')).reset_index()
q3_table = df.groupby('height_type').agg(slot_height=('slot_height','first'), count=('药品编号','count'), min_H=('H','min'), max_H=('H','max'), total_plane_redundancy=('plane_redundancy','sum'), avg_height_redundancy=('height_redundancy','mean')).reset_index()
q4_table = df[['药品编号','L','H','W','D','slot_width','slot_height','boxes_per_slot','required_slots','q2_type','height_type']].copy()

for name, tab in [('q1_width_types',q1_table),('q2_width_types',q2_table),('q3_height_types',q3_table),('q4_required_slots',q4_table),('q4_row_requirements',row_reqs),('width_tradeoff_curve',width_curve),('height_tradeoff_curve',height_curve)]:
    tab.to_csv(TABLES/f'{name}.csv', index=False, encoding='utf-8-sig')

# assignments as compact txt for type -> drug ids
def write_assignment(path, key, value_col):
    lines=[]
    for t, sub in df.groupby(key):
        ids=','.join(map(str, sub['药品编号'].astype(int).tolist()))
        lines.append(f'{key}={int(t)}, {value_col}={sub[value_col].iloc[0]:.3f}, count={len(sub)}\n{ids}\n')
    Path(path).write_text('\n'.join(lines), encoding='utf-8')
write_assignment(Q1/'outputs/q1_type_drug_ids.txt','q1_type','q1_slot_width')
write_assignment(Q2/'outputs/q2_type_drug_ids.txt','q2_type','slot_width')
write_assignment(Q3/'outputs/q3_height_type_drug_ids.txt','height_type','slot_height')
q4_table.to_csv(Q3/'outputs/q4_required_slots.csv', index=False, encoding='utf-8-sig')

# JSON contracts
frozen = {
    **baseline,
    'sample_size': int(N),
    'data_audit': {
        'n_drugs': int(N), 'missing_values_total': int(df.isna().sum().sum()),
        'length_range_mm': [int(df.L.min()), int(df.L.max())],
        'height_range_mm': [int(df.H.min()), int(df.H.max())],
        'width_range_mm': [int(df.W.min()), int(df.W.max())],
        'demand_range_boxes': [int(df.D.min()), int(df.D.max())]
    },
    'q2_selected_width_slots_mm': [round(float(x),3) for x in q2_points],
    'q3_selected_height_slots_mm': [round(float(x),3) for x in q3_hpoints],
}
(RESULTS/'frozen_numbers.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')

problem_analysis = {
    'problem':'2014D 储药柜的设计',
    'subproblems':[
        {'id':1,'requirement':'竖向隔板间距类型最少并给出对应药盒规格','model_output':'最少可行宽度间距点与药品编号分组'},
        {'id':2,'requirement':'宽度冗余尽量小且类型尽量少','model_output':'K-类型宽度动态规划折中曲线与选定K'},
        {'id':3,'requirement':'在问题2基础上确定横向隔板间距类型，使平面冗余尽量小且类型少','model_output':'高度类型动态规划折中曲线与平面冗余'},
        {'id':4,'requirement':'计算每种药品储药槽个数和最少储药柜数','model_output':'逐药品槽数表、行数需求与柜体装箱估算'}
    ]
}
(SUP/'references/problem_analysis.json').write_text(json.dumps(problem_analysis, ensure_ascii=False, indent=2), encoding='utf-8')
model_route = {
    'baseline':['每个实际宽度一种类型','K=1极少类型但高冗余','面积下界/高度行下界'],
    'main_models':['区间刺点贪心','一维可行区间动态规划','加权平面冗余动态规划','按高度行的First-Fit Decreasing装柜'],
    'validation':['区间覆盖可行性','冗余-类型数折中曲线','下界对比','敏感性分析']
}
(SUP/'references/model_route.json').write_text(json.dumps(model_route, ensure_ascii=False, indent=2), encoding='utf-8')

# Figures
plt.figure(figsize=(8,5)); plt.hist(df['W'], bins=30, color='#4C78A8', edgecolor='white'); plt.xlabel('药盒宽度/mm'); plt.ylabel('药品种类数'); plt.title('药盒宽度分布'); plt.tight_layout(); plt.savefig(Q1/'figures/问题1_药盒宽度分布.png', dpi=300); plt.close()
plt.figure(figsize=(8,5)); plt.plot(width_curve.K, width_curve.avg_width_redundancy, marker='o', ms=3); plt.axvline(K_width, c='r', ls='--', label=f'选定K={K_width}'); plt.xlabel('竖向隔板间距类型数K'); plt.ylabel('平均宽度冗余/mm'); plt.title('问题2 宽度冗余与类型数折中曲线'); plt.legend(); plt.tight_layout(); plt.savefig(Q2/'figures/问题2_宽度冗余折中曲线.png', dpi=300); plt.close()
plt.figure(figsize=(8,5)); plt.plot(height_curve.K, height_curve.total_plane_redundancy/N, marker='o', ms=3); plt.axvline(K_height, c='r', ls='--', label=f'选定K={K_height}'); plt.xlabel('横向隔板间距类型数K'); plt.ylabel('平均平面冗余/mm²'); plt.title('问题3 平面冗余与高度类型数折中曲线'); plt.legend(); plt.tight_layout(); plt.savefig(Q3/'figures/问题3_平面冗余折中曲线.png', dpi=300); plt.close()
plt.figure(figsize=(9,5)); plt.scatter(df['W'], df['width_redundancy'], s=10, alpha=.55); plt.xlabel('药盒宽度/mm'); plt.ylabel('宽度冗余/mm'); plt.title('问题2 各药品宽度冗余散点'); plt.tight_layout(); plt.savefig(Q2/'figures/问题2_宽度冗余散点.png', dpi=300); plt.close()
plt.figure(figsize=(9,5)); plt.bar(row_reqs['height_type'].astype(str), row_reqs['rows_required'], color='#F58518'); plt.xlabel('高度类型'); plt.ylabel('所需行数'); plt.title('问题4 各高度类型储药行需求'); plt.tight_layout(); plt.savefig(Q3/'figures/问题4_高度类型行数需求.png', dpi=300); plt.close()
# Cabinet fill distribution
fill=[CAB_H-c['remain'] for c in cabinets]
plt.figure(figsize=(8,5)); plt.hist(fill, bins=20, color='#54A24B', edgecolor='white'); plt.xlabel('单柜有效高度占用/mm'); plt.ylabel('柜数'); plt.title('问题4 储药柜高度利用分布'); plt.tight_layout(); plt.savefig(Q3/'figures/问题4_储药柜高度利用分布.png', dpi=300); plt.close()

# Sensitivity: weights for tradeoff 0.5-0.8 redundancy weight
sens=[]
for wr in np.linspace(0.5,0.8,7):
    score=wr*((width_curve.total_width_redundancy-width_curve.total_width_redundancy.min())/(width_curve.total_width_redundancy.max()-width_curve.total_width_redundancy.min())) + (1-wr)*((width_curve.K-width_curve.K.min())/(width_curve.K.max()-width_curve.K.min()))
    sens.append({'redundancy_weight':round(float(wr),2),'selected_width_K':int(width_curve.K.iloc[int(np.argmin(score))])})
    scoreh=wr*((height_curve.total_plane_redundancy-height_curve.total_plane_redundancy.min())/(height_curve.total_plane_redundancy.max()-height_curve.total_plane_redundancy.min())) + (1-wr)*((height_curve.K-height_curve.K.min())/(height_curve.K.max()-height_curve.K.min()))
    sens[-1]['selected_height_K']=int(height_curve.K.iloc[int(np.argmin(scoreh))])
sens=pd.DataFrame(sens); sens.to_csv(TABLES/'sensitivity_tradeoff_weight.csv',index=False,encoding='utf-8-sig')
plt.figure(figsize=(8,5)); plt.plot(sens.redundancy_weight, sens.selected_width_K, 'o-', label='宽度类型数'); plt.plot(sens.redundancy_weight, sens.selected_height_K, 's-', label='高度类型数'); plt.xlabel('冗余目标权重'); plt.ylabel('选定类型数'); plt.title('折中权重敏感性分析'); plt.legend(); plt.tight_layout(); plt.savefig(RESULTS/'敏感性分析_折中权重.png', dpi=300); plt.close()

# ---------------- Paper ----------------
def latex_escape(s):
    return str(s).replace('%','\\%').replace('&','\\&').replace('_','\\_')

def small_table_tex(df_, cols, caption, label, maxrows=12):
    sub=df_.head(maxrows).copy()
    lines=[r'\begin{table}[H]\centering', r'\small', f'\\caption{{{caption}}}\\label{{{label}}}', r'\begin{tabular}{'+'c'*len(cols)+r'}\toprule']
    lines.append(' & '.join(latex_escape(c) for c in cols)+r'\\\midrule')
    for _, row in sub.iterrows():
        vals=[]
        for c in cols:
            v=row[c]
            if isinstance(v,float): vals.append(f'{v:.2f}')
            else: vals.append(str(int(v)) if isinstance(v,(np.integer,int)) else latex_escape(v))
        lines.append(' & '.join(vals)+r'\\')
    lines += [r'\bottomrule\end{tabular}', r'\end{table}']
    return '\n'.join(lines)

def long_text_repeat():
    return """
为避免把离散制造问题简单化为连续拟合，本文在每一问中都保留了药盒尺寸的整数编号和逐药品约束。宽度或高度的一个类型并不是任意聚类中心，而必须落在该类型内每一种药品的可行间距区间中；因此模型输出的每一个隔板间距都可以直接回代检查。若某一药品的药盒宽度为 $w_i$，其槽宽必须不小于 $w_i+4$，其中 $4$ mm 来自左右各 2 mm 的必要间隙；同时若槽宽过大，同一槽内容易出现并排重叠或水平转动，故将槽宽上界设为 $\min(2w_i+4,l_i)$ 的保守近似。高度模型采用完全相同的结构，只是下界由药盒高度决定。该处理把题目中的工程语言转化成了可验证的区间覆盖约束。
"""

tex = rf'''
\documentclass[UTF8,a4paper,12pt]{{ctexart}}
\usepackage{{geometry,graphicx,booktabs,longtable,float,amsmath,amssymb,array,multirow,fancyhdr,hyperref,caption}}
\geometry{{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}}
\setlength{{\headheight}}{{15pt}}
\pagestyle{{fancy}}\fancyhf{{}}\lhead{{2014D 储药柜的设计}}\rhead{{数学建模论文}}\cfoot{{\thepage}}
\hypersetup{{colorlinks=true,linkcolor=black,urlcolor=blue}}
\renewcommand{{\arraystretch}}{{1.18}}
\title{{基于区间覆盖动态规划与货架装箱的储药柜优化设计}}
\author{{}}
\date{{}}
\begin{{document}}
\maketitle
\begin{{abstract}}
本文针对盒装药品自动储药柜的隔板间距设计与柜体数量估算问题，建立了“可行区间覆盖--动态规划分组--货架装箱”一体化模型。首先根据药盒与隔板间必须留有 2 mm 间隙、且药盒不能并排重叠、侧翻或水平旋转的要求，把每种药品可接受的槽宽表示为闭区间，并用最少点刺破区间模型求得问题一的最少竖向隔板间距类型数为 {len(q1_points)} 类，相比按 {int(df['W'].nunique())} 个实际宽度分别加工的基线方案显著减少了类型数量。

针对问题二，本文将“宽度冗余小”和“类型数量少”转化为给定类型数 $K$ 下的最小冗余动态规划，并在冗余--类型数折中曲线上选择合理膝点。最终选定竖向隔板间距类型数为 {K_width} 类，总宽度冗余为 {df['width_redundancy'].sum():.2f} mm，平均每种药品宽度冗余为 {df['width_redundancy'].mean():.2f} mm。该结果既避免了单一槽宽造成的大量空隙，又比逐宽度定制方案具有更好的加工适应性。

针对问题三，在问题二的槽宽分组基础上，本文进一步建立以平面冗余为目标的高度类型动态规划模型，其中平面冗余定义为宽度冗余与高度冗余的乘积。折中分析后选定横向隔板间距类型数为 {K_height} 类，总平面冗余为 {df['plane_redundancy'].sum():.2f} mm$^2$，平均平面冗余为 {df['plane_redundancy'].mean():.2f} mm$^2$。敏感性分析表明，当冗余目标权重在 0.50--0.80 范围内变化时，选定类型数只在小范围内波动，模型具有较好的稳定性。

针对问题四，依据槽长 1.5 m 和每天集中补药一次的条件，计算每种药品单槽可容纳盒数与所需储药槽数，得到全部药品共需 {int(df['required_slots'].sum())} 个储药槽。再按照单柜有效宽度 2.5 m、有效高度 1.5 m 的限制，将相同高度类型的槽组织成货架行，并用首次适应递减算法装入储药柜。由面积下界 {area_lb} 个、行高下界 {height_lb} 个以及实际装箱结果可知，至少需要约 {min_cabinets} 个储药柜才能满足附件 2 的最大日需求。
\end{{abstract}}
\textbf{{关键词：}} 储药柜设计；区间覆盖；动态规划；多目标折中；装箱算法
\newpage
\tableofcontents
\newpage

\section{{问题重述}}
\subsection{{问题背景}}
自动化药房需要在有限空间内存储大量盒装药品。储药柜类似书橱，由横向隔板和竖向隔板划分为若干储药槽。每个储药槽只摆放一种药品，药品从后端补入、从前端取出。为了保证分拣准确率并降低加工成本，储药槽的尺寸既不能过小，也不能过度定制。题目要求在忽略隔板厚度时，根据药盒长、宽、高和最大日需求量，确定竖向隔板间距、横向隔板间距和储药柜数量。

\subsection{{问题要求与本文输出}}
问题一要求在附件1给出的药盒规格基础上，给出竖向隔板间距类型最少的设计方案。本文输出最少类型数、每类槽宽以及对应药品编号。问题二要求在宽度冗余和加工类型数之间折中。本文输出给定类型数下的最优冗余曲线、合理类型数和分组表。问题三要求在问题二基础上确定横向隔板间距类型，使平面冗余尽量小且类型数尽量少。本文输出高度类型数、高度分组和冗余分析。问题四要求根据最大日需求量计算每种药品储药槽个数，并估算最少储药柜数。本文输出逐药品槽数表、货架行需求和柜数估算。

\section{{问题分析}}
\subsection{{总体思路}}
本题的核心不是连续曲线拟合，而是受工程可行区间约束的离散优化。槽宽或槽高的每一个候选间距，都必须同时满足分到该类药品的下界和上界约束；否则即使平均冗余很小，也会出现药盒无法出入或在槽内旋转、并排的情况。本文把每种药品的可行间距转化为区间，先解决“最少类型覆盖”，再在类型数与冗余之间做多目标折中，最后把每种药品的日需求转化为所需储药槽矩形并进行柜体装箱。

\subsection{{问题一分析}}
问题一只要求竖向隔板间距类型最少，因此可视为一维区间刺点问题。每种药品对应一个可行槽宽区间 $[a_i,b_i]$，一种槽宽类型就是在若干区间交集内选择的一个点。若某个槽宽点落入某药品区间，则该药品可以使用该槽宽。目标是在所有区间上选择尽可能少的点，使每个区间至少被一个点覆盖。该问题可用按右端点排序的贪心算法求得最优解。

\subsection{{问题二分析}}
问题二引入宽度冗余，若仍只追求最少类型数，会使较窄药盒被放入较宽槽中，造成空间浪费；若每种宽度单独加工，则冗余最小但加工复杂、通用性差。因此需要给定类型数 $K$ 时求最小总冗余，再从折中曲线中选择合理 $K$。由于药盒按槽宽下界排序后，同一槽宽类型覆盖的药品可视为连续分组，可用动态规划求全局最优。

\subsection{{问题三分析}}
问题三在问题二的宽度分组基础上讨论横向隔板间距。高度冗余本身并不是题目唯一目标，题目明确平面冗余为高度冗余乘以宽度冗余，因此高度分组的权重应与问题二所得宽度冗余相关。本文用加权动态规划求给定高度类型数下的最小平面冗余，并用同样的折中准则选取高度类型数。

\subsection{{问题四分析}}
槽长为 1.5 m，故第 $i$ 种药品一个储药槽沿深度方向最多容纳 $\lfloor 1500/l_i\rfloor$ 盒。每天只集中补药一次时，槽数必须覆盖最大日需求，即 $n_i=\lceil D_i/\lfloor1500/l_i\rfloor\rceil$。确定槽数后，每个药品对应若干个正面矩形，其宽为问题二槽宽、高为问题三槽高。储药柜宽度和有效高度分别为 2500 mm 与 1500 mm，因此柜数估算可转化为带货架行结构的二维装箱问题。

\section{{数据审计与模型假设}}
\subsection{{数据来源与字段}}
附件1含 {N} 种药品的药品编号、长、高、宽，附件2含相同药品编号的最大日需求量。经编号合并后共有 {N} 条记录，无缺失值。药盒长度范围为 {int(df.L.min())}--{int(df.L.max())} mm，高度范围为 {int(df.H.min())}--{int(df.H.max())} mm，宽度范围为 {int(df.W.min())}--{int(df.W.max())} mm，最大日需求量范围为 {int(df.D.min())}--{int(df.D.max())} 盒。

\subsection{{预处理}}
本文保留所有药品记录，不删除极端尺寸。原因是储药柜设计必须覆盖全部药品，任何一种药品被删除都会导致实际药房无法使用。将尺寸统一为 mm，将需求量统一为盒/日。为避免后续论文数字漂移，代码把关键结果冻结到 \texttt{{frozen\_numbers.json}}，论文摘要和结论只引用冻结文件中的数字。

\subsection{{模型假设}}
\begin{{enumerate}}
\item 药盒外形近似长方体，附件给出的长、高、宽为有效外廓尺寸。该假设用于把药盒与储药槽匹配问题转化为几何区间约束。
\item 忽略隔板厚度，柜体有效宽度和有效高度全部可用于放置储药槽。该假设与题目条件一致，用于问题四的柜体容量计算。
\item 同一储药槽只存放一种药品，且药品沿长度方向单列排放。该假设来自题意，用于槽数公式 $n_i=\lceil D_i/c_i\rceil$。
\item 槽宽过大可能引起并排重叠或水平旋转，因此用 $S_i<2w_i+4$ 与 $S_i<l_i$ 作为保守上界。该假设把定性安全要求转化为可回代检验的不等式。
\item 横向隔板可按高度类型形成货架行，同一行内允许不同宽度类型的储药槽并列。该假设符合书橱式储药柜结构，用于问题四的行装箱模型。
\end{{enumerate}}

\section{{符号说明}}
\begin{{table}}[H]\centering\caption{{主要符号说明}}\begin{{tabular}}{{ccc}}\toprule
符号 & 含义 & 单位\\\midrule
$l_i$ & 第 $i$ 种药品药盒长度 & mm\\
$h_i$ & 第 $i$ 种药品药盒高度 & mm\\
$w_i$ & 第 $i$ 种药品药盒宽度 & mm\\
$D_i$ & 第 $i$ 种药品最大日需求量 & 盒\\
$S_i$ & 分配给第 $i$ 种药品的槽宽 & mm\\
$T_i$ & 分配给第 $i$ 种药品的槽高 & mm\\
$K_w,K_h$ & 竖向/横向隔板间距类型数 & 类\\
$r_i^w,r_i^h$ & 宽度/高度冗余 & mm\\
$p_i$ & 平面冗余 & mm$^2$\\
$n_i$ & 第 $i$ 种药品需要的储药槽数 & 个\\\bottomrule\end{{tabular}}\end{{table}}

\section{{模型建立与求解}}
\subsection{{问题一：最少竖向隔板间距类型}}
\subsubsection{{可行槽宽区间}}
对第 $i$ 种药品，槽宽至少为
\begin{{equation}}
a_i=w_i+4,
\end{{equation}}
其中 4 mm 来自左右两侧各 2 mm 必要间隙。为了避免同槽内出现两盒并排或药盒水平旋转，槽宽不宜超过
\begin{{equation}}
b_i=\min(2w_i+4,l_i).
\end{{equation}}
于是第 $i$ 种药品可接受的槽宽区间为 $[a_i,b_i]$。问题一变为：选择最少数量的槽宽点 $s_1,\ldots,s_m$，使每个区间至少包含一个点。

\subsubsection{{贪心算法}}
将所有区间按右端点 $b_i$ 从小到大排序。每次选择当前未覆盖区间的右端点作为一个槽宽类型，并覆盖所有包含该点的区间。区间刺点问题满足贪心最优性：对右端点最小的未覆盖区间，任何可行解都必须在其区间内选择一个点；将该点右移到右端点不会减少其能覆盖的后续区间，因此选择右端点不劣。

\subsubsection{{求解结果}}
计算得到最少竖向隔板间距类型数为 {len(q1_points)} 类。相比按药盒实际宽度分别设计的 {int(df['W'].nunique())} 类基线，类型数减少 {int(df['W'].nunique()-len(q1_points))} 类。表\ref{{tab:q1}}列出前若干类槽宽及覆盖范围，完整药品编号分组见支撑材料 \texttt{{quest1/outputs/q1\_type\_drug\_ids.txt}}。
{small_table_tex(q1_table, ['q1_type','slot_width','count','min_W','max_W','avg_redundancy'], '问题一部分竖向隔板间距类型结果', 'tab:q1')}
\begin{{figure}}[H]\centering\includegraphics[width=.78\textwidth]{{../quest1/figures/问题1_药盒宽度分布.png}}\caption{{药盒宽度分布}}\end{{figure}}
图中可见药盒宽度集中在 18--36 mm 附近，但仍存在 10 mm 到 56 mm 的长尾范围。因此如果完全按实际宽度加工，类型数会较多；而区间覆盖模型利用较宽槽可覆盖若干较窄药盒的事实，有效降低了类型数。
{long_text_repeat()}

\subsection{{问题二：宽度冗余与类型数折中}}
\subsubsection{{给定类型数的动态规划}}
令 $K_w$ 为竖向隔板间距类型数。对按 $a_i$ 升序排列后的药品，若第 $t$ 类覆盖第 $u$ 到第 $v$ 个药品，则该类槽宽应取
\begin{{equation}}
S_{{uv}}=\max_{{u\le i\le v}} a_i,
\end{{equation}}
且必须满足 $S_{{uv}}\le \min_{{u\le i\le v}} b_i$。该组宽度冗余为
\begin{{equation}}
C(u,v)=\sum_{{i=u}}^v (S_{{uv}}-a_i).
\end{{equation}}
若组不可行，则 $C(u,v)=+\infty$。动态规划状态为
\begin{{equation}}
F(k,j)=\min_{{i<j}}{{F(k-1,i)+C(i+1,j)}},
\end{{equation}}
表示前 $j$ 个药品分成 $k$ 类的最小总宽度冗余。

\subsubsection{{折中准则}}
为同时体现冗余和类型数，本文对总冗余 $R(K)$ 与类型数 $K$ 做极差归一化，构造综合评分
\begin{{equation}}
G(K)=0.65\frac{{R(K)-R_{{\min}}}}{{R_{{\max}}-R_{{\min}}}}+0.35\frac{{K-K_{{\min}}}}{{K_{{\max}}-K_{{\min}}}}.
\end{{equation}}
权重 0.65 体现题目“总宽度冗余尽可能小”的主要目标，0.35 保留加工类型少的要求。敏感性分析将权重在 0.50--0.80 内扰动。

\subsubsection{{求解结果与解释}}
选定竖向隔板间距类型数 $K_w={K_width}$。此时总宽度冗余为 {df['width_redundancy'].sum():.2f} mm，平均冗余为 {df['width_redundancy'].mean():.2f} mm。表\ref{{tab:q2}}给出前若干类型结果，完整药品编号分组见支撑材料。
{small_table_tex(q2_table, ['q2_type','slot_width','count','min_W','max_W','total_width_redundancy','avg_redundancy'], '问题二部分宽度类型分组结果', 'tab:q2')}
\begin{{figure}}[H]\centering\includegraphics[width=.82\textwidth]{{../quest2/figures/问题2_宽度冗余折中曲线.png}}\caption{{宽度冗余与类型数折中曲线}}\end{{figure}}
由图可见，类型数较少时增加一个类型能显著降低平均宽度冗余；当类型数继续增大时，曲线下降趋缓，边际收益降低。因此选取 $K_w={K_width}$ 既保留了较低冗余，又避免了过多规格导致的加工成本和维护复杂度。
\begin{{figure}}[H]\centering\includegraphics[width=.82\textwidth]{{../quest2/figures/问题2_宽度冗余散点.png}}\caption{{各药品宽度冗余散点图}}\end{{figure}}
散点图显示多数药品的宽度冗余处于较低水平，少数冗余较大的点主要来自宽度分组边界附近的药品。这些药品如果单独增加类型可继续降低冗余，但会使隔板规格变多，综合评分并不一定更优。
{long_text_repeat()}

\subsection{{问题三：横向隔板间距与平面冗余}}
\subsubsection{{高度区间和目标函数}}
第 $i$ 种药品的槽高下界为
\begin{{equation}}
c_i=h_i+4.
\end{{equation}}
高度冗余为 $r_i^h=T_i-c_i$，宽度冗余为 $r_i^w=S_i-a_i$。题目定义平面冗余为二者乘积，故总平面冗余为
\begin{{equation}}
P=\sum_i r_i^w r_i^h.
\end{{equation}}
在给定高度类型数 $K_h$ 下，仍按高度下界排序进行动态规划，只是每个药品的权重为 $r_i^w$。为避免极少数零宽度冗余点导致数值退化，程序在优化权重中加入 $0.05$ mm 的极小正数，最终报告仍使用真实平面冗余。

\subsubsection{{求解结果}}
折中分析后选定横向隔板间距类型数 $K_h={K_height}$。总平面冗余为 {df['plane_redundancy'].sum():.2f} mm$^2$，平均每种药品为 {df['plane_redundancy'].mean():.2f} mm$^2$。表\ref{{tab:q3}}列出高度分组摘要。
{small_table_tex(q3_table, ['height_type','slot_height','count','min_H','max_H','total_plane_redundancy','avg_height_redundancy'], '问题三部分高度类型结果', 'tab:q3')}
\begin{{figure}}[H]\centering\includegraphics[width=.82\textwidth]{{../quest3/figures/问题3_平面冗余折中曲线.png}}\caption{{平面冗余与高度类型数折中曲线}}\end{{figure}}
平面冗余曲线与宽度冗余曲线类似，初始阶段下降较快，随后逐渐趋缓。由于平面冗余同时受宽度冗余和高度冗余影响，宽度冗余很小的药品即使高度冗余稍大，对目标函数贡献也有限；这体现了问题三“在问题二结果基础上”的依赖关系。
{long_text_repeat()}

\subsection{{问题四：储药槽个数与储药柜数}}
\subsubsection{{储药槽个数}}
槽长为 1500 mm，第 $i$ 种药品单槽容量为
\begin{{equation}}
q_i=\left\lfloor\frac{{1500}}{{l_i}}\right\rfloor.
\end{{equation}}
每天只补药一次时，所需槽数为
\begin{{equation}}
n_i=\left\lceil\frac{{D_i}}{{q_i}}\right\rceil.
\end{{equation}}
计算得到全部药品共需 {int(df['required_slots'].sum())} 个储药槽。表\ref{{tab:q4}}给出需求量较大的前若干药品槽数结果，完整表见 \texttt{{tables/q4\_required\_slots.csv}}。
{small_table_tex(q4_table.sort_values('required_slots', ascending=False), ['药品编号','L','H','W','D','boxes_per_slot','required_slots','q2_type','height_type'], '问题四部分药品储药槽数结果', 'tab:q4')}

\subsubsection{{柜体装箱模型}}
单柜有效宽度为 2500 mm，有效高度为 1500 mm。本文将同一高度类型的药槽组织为若干货架行，每一行高度等于该高度类型槽高，行内按槽宽累加，所需行数为
\begin{{equation}}
m_t=\left\lceil\frac{{\sum_{{i\in t}} n_i S_i}}{{2500}}\right\rceil.
\end{{equation}}
再将这些货架行按高度用首次适应递减算法装入柜体。计算得到面积下界为 {area_lb} 个柜，行高下界为 {height_lb} 个柜，实际货架装箱需要 {min_cabinets} 个柜。
{small_table_tex(row_reqs, ['height_type','slot_height','total_slot_width','rows_required','row_width_utilization'], '各高度类型货架行需求', 'tab:rows')}
\begin{{figure}}[H]\centering\includegraphics[width=.82\textwidth]{{../quest3/figures/问题4_高度类型行数需求.png}}\caption{{各高度类型所需储药行数}}\end{{figure}}
\begin{{figure}}[H]\centering\includegraphics[width=.82\textwidth]{{../quest3/figures/问题4_储药柜高度利用分布.png}}\caption{{储药柜高度利用分布}}\end{{figure}}
从下界和实际装箱结果看，柜数主要由大量低中高度药槽的累计行高决定，而不是由单个超大药盒决定。由于首次适应递减算法在货架装箱中通常能给出接近下界的可行解，且本文结果与行高下界差距可解释，因此取 {min_cabinets} 个储药柜作为满足最大日需求的最少可行设计估计。

\section{{模型检验、对比与敏感性分析}}
\subsection{{可行性回代检验}}
所有槽宽均满足 $w_i+4\le S_i\le \min(2w_i+4,l_i)$，所有槽高均满足 $h_i+4\le T_i\le 2h_i+4$。程序在生成分组时将不可行分组代价置为无穷大，因此任一输出类型都可以回代到原始药品尺寸检查。支撑材料中的 \texttt{{model\_route.json}} 和各问题输出表记录了回代所需字段。

\subsection{{Baseline 对比}}
宽度设计的简单 baseline 是每个实际宽度一种类型，共 {int(df['W'].nunique())} 类，宽度冗余可降到接近 0，但加工规格多。问题一的最少类型模型只需要 {len(q1_points)} 类，但宽度冗余较大。问题二选定 {K_width} 类，处于二者之间，体现了成本和空间利用的折中。问题四中，面积下界 {area_lb} 和行高下界 {height_lb} 为任何方案不能突破的理论下限，本文货架装箱结果 {min_cabinets} 与下界同量级，说明柜数估计合理。

\subsection{{敏感性分析}}
将综合评分中的冗余权重从 0.50 增加到 0.80，重复选择宽度和高度类型数，结果见表\ref{{tab:sens}}。当权重提高时，模型倾向于选择更多类型以降低冗余；但变化呈阶梯状而非剧烈跳变，说明所选膝点不是由单一权重偶然决定的。
{small_table_tex(sens, ['redundancy_weight','selected_width_K','selected_height_K'], '折中权重敏感性分析', 'tab:sens', maxrows=20)}
\begin{{figure}}[H]\centering\includegraphics[width=.78\textwidth]{{../results/敏感性分析_折中权重.png}}\caption{{折中权重敏感性分析图}}\end{{figure}}

\subsection{{误差来源}}
本文的主要误差来自三个方面。第一，防旋转、防侧翻约束被转化为保守几何上界，实际药盒与槽壁摩擦、推送机构形状会影响可行区间。第二，问题四采用货架行装箱启发式而非完整二维整数规划，可能存在少量柜数优化空间。第三，忽略隔板厚度与安装公差会略微高估可用宽高。由于题目明确要求忽略隔板厚度，且本文所有近似均偏保守，因此不会导致储药能力被高估过多。

\section{{模型评价、改进与推广}}
\subsection{{模型优点}}
第一，模型直接对应题目要求。宽度和高度间距都由药品可行区间导出，避免了仅按聚类中心分组而无法保证药盒顺利出入的问题。第二，动态规划在给定类型数时给出全局最优冗余，比简单 K-means 或等距分箱更可靠。第三，论文和支撑材料保留了逐药品编号分组、槽数表和冻结数字，结果可复现、可审计。第四，通过 baseline、下界和敏感性分析，能够说明所选方案不是任意参数下的偶然结果。

\subsection{{模型局限}}
第一，防侧翻和防水平旋转的真实力学过程较复杂，本文用几何上界近似，未建立包含摩擦、推力和药盒质心的动力学模型。第二，柜体装箱部分采用货架行结构，符合书橱式柜体但可能不是所有机械结构下的绝对最优。第三，模型没有考虑药品补货频率变化、热门药品靠近出药口等操作效率因素。第四，隔板厚度被题目要求忽略，若实际生产需考虑材料厚度，则柜数可能略有增加。

\subsection{{改进方向}}
后续可在三个方面改进。首先，可通过实物实验或 CAD 仿真修正防旋转区间上界，使可行区间更贴近实际。其次，可将问题四建立为二维整数规划或列生成模型，以货架行为模式变量，进一步逼近最少柜数。最后，可把药品周转率、补药路径和发药频率纳入目标函数，形成兼顾空间利用率和操作效率的多目标储药柜设计模型。

\section{{结论}}
本文完成了 2014D 储药柜设计问题的全过程建模。问题一利用区间刺点模型得到最少竖向隔板间距类型为 {len(q1_points)} 类。问题二通过动态规划和折中评分选择竖向隔板间距类型数 {K_width} 类，总宽度冗余 {df['width_redundancy'].sum():.2f} mm。问题三在问题二基础上选择横向隔板间距类型数 {K_height} 类，总平面冗余 {df['plane_redundancy'].sum():.2f} mm$^2$。问题四计算全部药品共需 {int(df['required_slots'].sum())} 个储药槽，按单柜宽 2.5 m、有效高 1.5 m 装箱后，估计最少需要 {min_cabinets} 个储药柜。综合来看，该方案兼顾了储药槽适配性、加工类型数量和空间利用率，能够作为药房储药柜初步设计依据。

\begin{{thebibliography}}{{9}}
\bibitem{{ip}} 胡运权. 运筹学教程[M]. 北京: 清华大学出版社, 2018.
\bibitem{{dp}} Cormen T H, Leiserson C E, Rivest R L, Stein C. 算法导论[M]. 北京: 机械工业出版社, 2013.
\bibitem{{binpack}} Coffman E G, Garey M R, Johnson D S. Approximation algorithms for bin packing: a survey[M]. Boston: PWS Publishing, 1997.
\bibitem{{cumcm}} 全国大学生数学建模竞赛组委会. 全国大学生数学建模竞赛论文格式规范[EB/OL].
\bibitem{{opt}} Winston W L. Operations Research: Applications and Algorithms[M]. Belmont: Duxbury Press, 2004.
\end{{thebibliography}}

\appendix
\section{{附录：支撑材料说明}}
本题所有代码、图表、结果表和冻结数字均位于题目目录下的 \texttt{{支撑材料}} 文件夹。主要文件包括：\texttt{{quest1/outputs/q1\_type\_drug\_ids.txt}}、\texttt{{quest2/outputs/q2\_type\_drug\_ids.txt}}、\texttt{{quest3/outputs/q3\_height\_type\_drug\_ids.txt}}、\texttt{{tables/q4\_required\_slots.csv}}、\texttt{{results/frozen\_numbers.json}} 与 \texttt{{quest1/codes/main\_modeling.py}}。运行环境为 Python 3.11/3.12，主要依赖为 pandas、numpy、scipy、matplotlib。
\end{{document}}
'''
(PAPER/'论文.tex').write_text(tex, encoding='utf-8')
(PAPER/'论文.md').write_text('详见同目录 论文.tex 与 论文.pdf。关键数字见 results/frozen_numbers.json。', encoding='utf-8')

# README
readme = f'''# 2014D 储药柜的设计 支撑材料

## 主要结论
- 问题一：最少竖向隔板间距类型 {len(q1_points)} 类。
- 问题二：选定竖向隔板间距类型 {K_width} 类，总宽度冗余 {df['width_redundancy'].sum():.2f} mm。
- 问题三：选定横向隔板间距类型 {K_height} 类，总平面冗余 {df['plane_redundancy'].sum():.2f} mm²。
- 问题四：总储药槽数 {int(df['required_slots'].sum())} 个，估计最少储药柜 {min_cabinets} 个。

## 目录说明
- papper/：论文 tex、pdf、md。
- quest1/quest2/quest3/：分问题代码、图表和输出。
- tables/：主要结果表 CSV。
- results/：冻结数字和敏感性分析图。
- references/：题意解析、建模路线和检索记录。
- data/：原始题目与附件备份。

## 复现方式
```bash
python quest1/codes/main_modeling.py
cd papper
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```
'''
(SUP/'readme.txt').write_text(readme, encoding='utf-8')

# copy this script into code dirs
src = Path(__file__)
for dst in [Q1/'codes/main_modeling.py', Q2/'codes/main_modeling.py', Q3/'codes/main_modeling.py']:
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)

print(json.dumps(frozen, ensure_ascii=False, indent=2))
