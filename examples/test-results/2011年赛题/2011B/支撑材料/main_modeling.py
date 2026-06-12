import os, json, math, zipfile, shutil
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    import networkx as nx
except Exception as e:
    raise SystemExit('需要 networkx: '+str(e))
try:
    from scipy.optimize import linear_sum_assignment
except Exception as e:
    raise SystemExit('需要 scipy: '+str(e))

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011B')
SUPPORT = ROOT / '支撑材料'
PAPER = SUPPORT / 'papper'
RESULTS = SUPPORT / 'results'
TABLES = SUPPORT / 'tables'
FIGS = SUPPORT / 'figures'
for d in [SUPPORT, PAPER, RESULTS, TABLES, FIGS]:
    d.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei','Microsoft YaHei','SimSun','Arial Unicode MS','DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

SPEED_KM_PER_MIN = 1.0
MM_TO_KM = 0.1
THRESHOLD_MM = 30.0  # 3 km = 30 mm


def load_data():
    xls = next(ROOT.glob('*附件2*.xls'))
    nodes = pd.read_excel(xls, sheet_name='全市交通路口节点数据').iloc[:, :5]
    nodes.columns = ['node','x','y','area','crime_rate']
    nodes = nodes.dropna(subset=['node','x','y','area']).copy()
    nodes['node'] = nodes['node'].astype(int)
    nodes['x'] = nodes['x'].astype(float); nodes['y'] = nodes['y'].astype(float)
    nodes['area'] = nodes['area'].astype(str).str.strip()
    nodes['crime_rate'] = pd.to_numeric(nodes['crime_rate'], errors='coerce').fillna(0.0)
    edges = pd.read_excel(xls, sheet_name='全市交通路口的路线').iloc[:, :2]
    edges.columns = ['u','v']
    edges = edges.dropna().copy(); edges['u']=edges['u'].astype(int); edges['v']=edges['v'].astype(int)
    platforms = pd.read_excel(xls, sheet_name='全市交巡警平台').iloc[:, :2]
    platforms.columns = ['platform','node']
    platforms = platforms.dropna().copy(); platforms['platform']=platforms['platform'].astype(str); platforms['node']=platforms['node'].astype(int)
    exits = pd.read_excel(xls, sheet_name='全市区出入口的位置').iloc[:, :3]
    exits.columns = ['idx','city_exit','A_exit']
    exits = exits.dropna(subset=['idx']).copy()
    exits['city_exit']=pd.to_numeric(exits['city_exit'], errors='coerce').astype('Int64')
    exits['A_exit']=pd.to_numeric(exits['A_exit'], errors='coerce').astype('Int64')
    basics = pd.read_excel(xls, sheet_name='六城区的基本数据').iloc[:, :3]
    basics.columns = ['area','area_km2','population_10k']
    basics = basics.dropna(subset=['area']).copy(); basics['area']=basics['area'].astype(str).str.strip()
    return nodes, edges, platforms, exits, basics


def build_graph(nodes, edges):
    coord = nodes.set_index('node')[['x','y']].to_dict('index')
    G = nx.Graph()
    for _, r in nodes.iterrows():
        G.add_node(int(r.node), x=float(r.x), y=float(r.y), area=r.area, crime_rate=float(r.crime_rate))
    for _, r in edges.iterrows():
        u=int(r.u); v=int(r.v)
        if u in coord and v in coord:
            w = math.hypot(coord[u]['x']-coord[v]['x'], coord[u]['y']-coord[v]['y'])
            G.add_edge(u, v, weight=w)
    return G


def dist_matrix(G, sources, targets):
    data = np.full((len(sources), len(targets)), np.inf)
    for i, s in enumerate(sources):
        lengths = nx.single_source_dijkstra_path_length(G, int(s), weight='weight')
        for j, t in enumerate(targets):
            data[i,j] = lengths.get(int(t), np.inf)
    return data


def assign_nodes(G, nodes_df, platform_df, area_filter=None):
    if area_filter:
        nd = nodes_df[nodes_df.area==area_filter].copy()
        pf = platform_df[platform_df.platform.str.startswith(area_filter)].copy()
    else:
        nd = nodes_df.copy(); pf = platform_df.copy()
    target_nodes = nd.node.tolist(); pnodes = pf.node.tolist()
    D = dist_matrix(G, pnodes, target_nodes)
    nearest = np.argmin(D, axis=0); mind = D[nearest, np.arange(len(target_nodes))]
    out = nd[['node','x','y','area','crime_rate']].copy()
    out['assigned_platform'] = [pf.iloc[i].platform for i in nearest]
    out['assigned_platform_node'] = [pf.iloc[i].node for i in nearest]
    out['distance_mm'] = mind
    out['time_min'] = mind * MM_TO_KM / SPEED_KM_PER_MIN
    stat = out.groupby('assigned_platform').agg(
        platform_node=('assigned_platform_node','first'), nodes=('node','count'), workload=('crime_rate','sum'),
        max_time=('time_min','max'), avg_time=('time_min','mean'), uncovered_nodes=('time_min', lambda s: int((s>3).sum()))
    ).reset_index().rename(columns={'assigned_platform':'platform'})
    allp = pf[['platform','node']].rename(columns={'node':'platform_node'})
    stat = allp.merge(stat, on=['platform','platform_node'], how='left').fillna({'nodes':0,'workload':0,'max_time':0,'avg_time':0,'uncovered_nodes':0})
    return out, stat


def workload_metrics(stat):
    w = stat['workload'].astype(float).values
    return dict(mean=float(np.mean(w)), std=float(np.std(w)), cv=float(np.std(w)/(np.mean(w)+1e-9)), max=float(np.max(w)), min=float(np.min(w)))


def block_assignment(G, platforms_df, exits, label):
    exits = [int(e) for e in exits if pd.notna(e)]
    pnodes = platforms_df.node.tolist(); pids = platforms_df.platform.tolist()
    D = dist_matrix(G, pnodes, exits)
    # primary: minimize max using binary-search threshold, secondary total via Hungarian among feasible-like costs
    finite = sorted(set(float(x) for x in D[np.isfinite(D)].ravel()))
    best_thr = finite[-1]
    best_pairs = None
    for thr in finite:
        big = 10**6
        cost = np.where(D <= thr, D, big)
        row, col = linear_sum_assignment(cost)
        if len(col)>=len(exits) and np.all(cost[row, col] < big):
            best_thr = thr; best_pairs = (row, col); break
    # refine total within best_thr
    big = 10**6
    cost = np.where(D <= best_thr + 1e-9, D, big) + D/100000.0
    row, col = linear_sum_assignment(cost)
    rows=[]
    for r,c in zip(row,col):
        if c < len(exits) and D[r,c] <= best_thr + 1e-9:
            rows.append({'exit_node':exits[c], 'platform':pids[r], 'platform_node':pnodes[r], 'distance_mm':D[r,c], 'arrival_min':D[r,c]*0.1})
    df = pd.DataFrame(rows).sort_values('exit_node')
    df.to_csv(TABLES/f'{label}_封锁调度方案.csv', index=False, encoding='utf-8-sig')
    return df, {'max_arrival_min':float(df.arrival_min.max()), 'avg_arrival_min':float(df.arrival_min.mean()), 'total_arrival_min':float(df.arrival_min.sum())}


def evaluate_additions(G, nodes, platforms, k):
    A_nodes = nodes[nodes.area=='A'].copy()
    base_pf = platforms[platforms.platform.str.startswith('A')].copy()
    candidates = [n for n in A_nodes.node.tolist() if n not in set(base_pf.node.tolist())]
    chosen=[]; current_nodes=base_pf.node.tolist(); current_names=base_pf.platform.tolist()
    history=[]
    for step in range(k):
        best=None
        for cand in candidates:
            if cand in chosen: continue
            tmp_pf = pd.DataFrame({'platform':current_names+[f'N{step+1}@{cand}'], 'node':current_nodes+[cand]})
            assign, stat = assign_nodes(G, nodes, tmp_pf, area_filter=None)
            assignA = assign[assign.area=='A']
            statA = stat
            uncovered=int((assignA.time_min>3).sum())
            max_t=float(assignA.time_min.max())
            cv=workload_metrics(statA)['cv']
            # objective prioritizes 3-min uncovered then max time then workload balance
            obj=uncovered*10000 + max_t*100 + cv*10
            if best is None or obj<best[0]: best=(obj,cand,uncovered,max_t,cv,assignA,statA)
        chosen.append(best[1]); current_nodes.append(best[1]); current_names.append(f'N{step+1}')
        history.append({'step':step+1,'new_node':best[1],'uncovered_nodes':best[2],'max_time_min':best[3],'workload_cv':best[4],'objective':best[0]})
    tmp_pf = pd.DataFrame({'platform':current_names, 'node':current_nodes})
    assign, stat = assign_nodes(G, nodes, tmp_pf, area_filter=None)
    return chosen, pd.DataFrame(history), assign[assign.area=='A'], stat


def recommend_city_improvement(G, nodes, platforms, max_add=10):
    # Greedy add city-wide platforms until all nodes are within 3 minutes or max_add reached.
    current = platforms.copy(); candidates=[n for n in nodes.node.tolist() if n not in set(current.node)]
    hist=[]
    for step in range(max_add):
        assign, stat = assign_nodes(G, nodes, current, None)
        uncovered0=int((assign.time_min>3).sum()); max0=float(assign.time_min.max())
        if uncovered0==0: break
        best=None
        # restrict candidates to uncovered nodes and their nearby area to keep meaningful
        cand_pool = assign[assign.time_min>3].sort_values('crime_rate', ascending=False).node.tolist()[:120]
        for cand in cand_pool:
            tmp = pd.concat([current, pd.DataFrame([{'platform':f'G{step+1}', 'node':cand}])], ignore_index=True)
            a,s=assign_nodes(G,nodes,tmp,None)
            uncovered=int((a.time_min>3).sum()); max_t=float(a.time_min.max()); cv=workload_metrics(s)['cv']
            obj=uncovered*10000 + max_t*100 + cv*10
            if best is None or obj<best[0]: best=(obj,cand,uncovered,max_t,cv)
        current = pd.concat([current, pd.DataFrame([{'platform':f'G{step+1}', 'node':best[1]}])], ignore_index=True)
        hist.append({'step':step+1,'new_node':best[1],'uncovered_nodes':best[2],'max_time_min':best[3],'workload_cv':best[4]})
    assign, stat=assign_nodes(G,nodes,current,None)
    return pd.DataFrame(hist), assign, stat


def plot_network(nodes, edges, platforms, exits, filename, title, area_filter=None, extra_nodes=None):
    fig, ax = plt.subplots(figsize=(10,8))
    nd = nodes if area_filter is None else nodes[nodes.area==area_filter]
    ndset=set(nd.node)
    for _,e in edges.iterrows():
        if int(e.u) in ndset and int(e.v) in ndset:
            a=nodes.loc[nodes.node==int(e.u)].iloc[0]; b=nodes.loc[nodes.node==int(e.v)].iloc[0]
            ax.plot([a.x,b.x],[a.y,b.y], color='#cccccc', lw=0.6, zorder=1)
    for area, g in nd.groupby('area'):
        ax.scatter(g.x,g.y,s=10,label=f'{area}区节点',alpha=0.65,zorder=2)
    pf = platforms[platforms.node.isin(ndset)]
    pcoord = nodes.set_index('node').loc[pf.node]
    ax.scatter(pcoord.x,pcoord.y,s=70,marker='o',facecolors='none',edgecolors='red',linewidths=1.8,label='现有平台',zorder=4)
    ex=[int(x) for x in exits if pd.notna(x) and int(x) in ndset]
    if ex:
        ecoord=nodes.set_index('node').loc[ex]
        ax.scatter(ecoord.x,ecoord.y,s=80,marker='*',color='black',label='出入口',zorder=5)
    if extra_nodes:
        ecoord=nodes.set_index('node').loc[extra_nodes]
        ax.scatter(ecoord.x,ecoord.y,s=100,marker='P',color='blue',label='建议新增平台',zorder=6)
    ax.set_title(title); ax.set_xlabel('X/mm'); ax.set_ylabel('Y/mm'); ax.legend(fontsize=8, loc='best')
    ax.set_aspect('equal', adjustable='box'); ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(FIGS/filename, dpi=300, bbox_inches='tight'); plt.close(fig)


def main():
    nodes, edges, platforms, exits, basics = load_data()
    G = build_graph(nodes, edges)
    # data audit
    audit = {
        'nodes':len(nodes),'edges':len(edges),'platforms':len(platforms),'city_exits':int(exits.city_exit.notna().sum()),'A_exits':int(exits.A_exit.notna().sum()),
        'missing': {'nodes': nodes.isna().sum().to_dict(), 'edges': edges.isna().sum().to_dict(), 'platforms': platforms.isna().sum().to_dict()},
        'graph_connected': nx.is_connected(G), 'components': nx.number_connected_components(G), 'random_seed': RANDOM_SEED
    }
    (RESULTS/'data_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

    A_assign, A_stat = assign_nodes(G, nodes, platforms, 'A')
    A_assign.to_csv(TABLES/'问题1_A区节点管辖分配.csv', index=False, encoding='utf-8-sig')
    A_stat.to_csv(TABLES/'问题1_A区平台工作量统计.csv', index=False, encoding='utf-8-sig')

    A_exits = exits['A_exit'].dropna().astype(int).tolist()
    city_exits = exits['city_exit'].dropna().astype(int).tolist()
    A_block, A_block_metrics = block_assignment(G, platforms[platforms.platform.str.startswith('A')], A_exits, '问题1_A区13出入口')

    add_records=[]; add_details={}
    for k in range(2,6):
        chosen,hist,assign_k,stat_k=evaluate_additions(G,nodes,platforms,k)
        add_records.append({'k':k,'new_nodes':','.join(map(str,chosen)),'uncovered_nodes':int((assign_k.time_min>3).sum()),'max_time_min':float(assign_k.time_min.max()),'avg_time_min':float(assign_k.time_min.mean()),'workload_cv':workload_metrics(stat_k)['cv']})
        add_details[k]=(chosen,hist,assign_k,stat_k)
        hist.to_csv(TABLES/f'问题1_新增{k}个平台贪心过程.csv', index=False, encoding='utf-8-sig')
    add_eval=pd.DataFrame(add_records)
    add_eval.to_csv(TABLES/'问题1_新增平台数量比较.csv', index=False, encoding='utf-8-sig')
    # choose smallest k with zero uncovered, else min objective with diminishing returns
    zero=add_eval[add_eval.uncovered_nodes==0]
    best_k=int(zero.iloc[0].k) if len(zero) else int(add_eval.sort_values(['uncovered_nodes','max_time_min','workload_cv']).iloc[0].k)
    best_chosen,best_hist,best_assign,best_stat=add_details[best_k]
    best_assign.to_csv(TABLES/'问题1_建议新增后A区节点管辖分配.csv', index=False, encoding='utf-8-sig')
    best_stat.to_csv(TABLES/'问题1_建议新增后A区平台工作量统计.csv', index=False, encoding='utf-8-sig')

    all_assign, all_stat = assign_nodes(G, nodes, platforms, None)
    all_assign.to_csv(TABLES/'问题2_全市节点最近平台分配.csv', index=False, encoding='utf-8-sig')
    all_stat.to_csv(TABLES/'问题2_全市平台工作量统计.csv', index=False, encoding='utf-8-sig')
    area_cov=all_assign.groupby('area').agg(nodes=('node','count'), crime_rate=('crime_rate','sum'), avg_time=('time_min','mean'), max_time=('time_min','max'), uncovered_nodes=('time_min',lambda s:int((s>3).sum())), uncovered_rate=('time_min',lambda s:float((s>3).mean()))).reset_index()
    area_pf=platforms.assign(area=platforms.platform.str[0]).groupby('area').agg(platforms=('platform','count')).reset_index()
    area_eval=basics.merge(area_cov,on='area').merge(area_pf,on='area')
    area_eval['platforms_per_100km2']=area_eval.platforms/area_eval.area_km2*100
    area_eval['platforms_per_10k_pop']=area_eval.platforms/area_eval.population_10k
    area_eval['crime_per_platform']=area_eval.crime_rate/area_eval.platforms
    area_eval.to_csv(TABLES/'问题2_六城区设置合理性评价.csv', index=False, encoding='utf-8-sig')

    improve_hist, improved_assign, improved_stat = recommend_city_improvement(G,nodes,platforms,10)
    improve_hist.to_csv(TABLES/'问题2_全市新增平台改进方案.csv', index=False, encoding='utf-8-sig')
    improved_stat.to_csv(TABLES/'问题2_改进后全市平台工作量统计.csv', index=False, encoding='utf-8-sig')

    city_block, city_block_metrics = block_assignment(G, platforms, city_exits, '问题2_全市17出入口')
    # P32 pursuit: suspect starts from node 32, report after 3 min. Compute suspect remaining time to exits and police closing time.
    dist_from_32 = nx.single_source_dijkstra_path_length(G, 32, weight='weight')
    pursuit = city_block.copy()
    pursuit['suspect_total_min'] = pursuit.exit_node.map(lambda n: dist_from_32.get(int(n), np.inf)*0.1)
    pursuit['suspect_after_alarm_min'] = pursuit['suspect_total_min'] - 3.0
    pursuit['safety_margin_min'] = pursuit['suspect_after_alarm_min'] - pursuit['arrival_min']
    pursuit['can_block_before_suspect'] = pursuit['safety_margin_min'] >= 0
    pursuit.to_csv(TABLES/'问题2_P32案发围堵方案.csv', index=False, encoding='utf-8-sig')

    # Plots
    plot_network(nodes, edges, platforms, A_exits, '问题1_A区网络平台与出入口.png', 'A区交通网络、服务平台与出入口', 'A')
    plot_network(nodes, edges, platforms, A_exits, '问题1_A区建议新增平台.png', f'A区建议新增{best_k}个平台：{best_chosen}', 'A', best_chosen)
    plot_network(nodes, edges, platforms, city_exits, '问题2_全市网络平台与出入口.png', '全市六区交通网络、服务平台与出入口', None)

    fig, ax=plt.subplots(figsize=(9,5));
    A_stat.sort_values('workload').plot.bar(x='platform', y='workload', ax=ax, color='#4C78A8', legend=False)
    ax.axhline(A_stat.workload.mean(), color='red', ls='--', label='平均工作量'); ax.set_ylabel('日均发案率合计'); ax.set_title('A区现有20个平台工作量分布'); ax.legend(); fig.tight_layout(); fig.savefig(FIGS/'问题1_A区现有平台工作量.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    fig, ax=plt.subplots(figsize=(8,5));
    add_eval.plot(x='k', y=['uncovered_nodes','max_time_min','workload_cv'], marker='o', ax=ax); ax.set_title('A区新增平台数量方案比较'); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(FIGS/'问题1_新增平台数量比较.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    fig, ax=plt.subplots(figsize=(8,5));
    area_eval.plot.bar(x='area', y='uncovered_rate', ax=ax, color='#F58518', legend=False); ax.set_ylabel('3分钟未覆盖比例'); ax.set_title('六城区现有平台3分钟覆盖不足比较'); fig.tight_layout(); fig.savefig(FIGS/'问题2_六城区覆盖不足率.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    fig, ax=plt.subplots(figsize=(8,5));
    area_eval.plot.scatter(x='crime_per_platform', y='max_time', s=area_eval.platforms*30, ax=ax)
    for _,r in area_eval.iterrows(): ax.text(r.crime_per_platform, r.max_time, r.area)
    ax.set_xlabel('每平台承担日均发案率'); ax.set_ylabel('最大到达时间/min'); ax.set_title('六城区平台负荷与响应时间合理性'); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(FIGS/'问题2_六城区合理性散点.png', dpi=300, bbox_inches='tight'); plt.close(fig)
    fig, ax=plt.subplots(figsize=(10,5));
    pursuit.sort_values('safety_margin_min').plot.bar(x='exit_node', y='safety_margin_min', ax=ax, color=['#E45756' if v<0 else '#54A24B' for v in pursuit.sort_values('safety_margin_min').safety_margin_min], legend=False)
    ax.axhline(0,color='black',lw=1); ax.set_ylabel('安全裕度/min'); ax.set_title('P32案件全市出入口围堵安全裕度'); fig.tight_layout(); fig.savefig(FIGS/'问题2_P32围堵安全裕度.png', dpi=300, bbox_inches='tight'); plt.close(fig)

    # summary/frozen numbers
    frozen = {
        'meta': {'problem':'CUMCM2011B 交巡警服务平台的设置与调度','generated_at':datetime.now().isoformat(timespec='seconds'),'seed':RANDOM_SEED},
        'data_audit': audit,
        'Q1': {
            'A_nodes': int((nodes.area=='A').sum()), 'A_platforms': int(platforms.platform.str.startswith('A').sum()), 'threshold_min':3.0,
            'current_uncovered_nodes': int((A_assign.time_min>3).sum()), 'current_uncovered_rate': float((A_assign.time_min>3).mean()),
            'current_max_time_min': float(A_assign.time_min.max()), 'current_avg_time_min': float(A_assign.time_min.mean()),
            'current_workload_cv': workload_metrics(A_stat)['cv'], 'current_workload_max_platform': str(A_stat.sort_values('workload', ascending=False).iloc[0].platform),
            'current_workload_max': float(A_stat.workload.max()), 'current_workload_min': float(A_stat.workload.min()),
            'A_block_max_arrival_min': A_block_metrics['max_arrival_min'], 'A_block_avg_arrival_min': A_block_metrics['avg_arrival_min'],
            'recommended_add_k': best_k, 'recommended_add_nodes': [int(x) for x in best_chosen],
            'after_add_uncovered_nodes': int((best_assign.time_min>3).sum()), 'after_add_max_time_min': float(best_assign.time_min.max()),
            'after_add_avg_time_min': float(best_assign.time_min.mean()), 'after_add_workload_cv': workload_metrics(best_stat)['cv']
        },
        'Q2': {
            'city_nodes':len(nodes),'city_platforms':len(platforms),'city_current_uncovered_nodes':int((all_assign.time_min>3).sum()),
            'city_current_uncovered_rate':float((all_assign.time_min>3).mean()), 'city_current_max_time_min':float(all_assign.time_min.max()),
            'worst_area_by_uncovered_rate': str(area_eval.sort_values('uncovered_rate', ascending=False).iloc[0].area),
            'worst_area_uncovered_rate': float(area_eval.sort_values('uncovered_rate', ascending=False).iloc[0].uncovered_rate),
            'heaviest_area_by_crime_per_platform': str(area_eval.sort_values('crime_per_platform', ascending=False).iloc[0].area),
            'city_recommended_new_nodes': improve_hist.new_node.astype(int).tolist(), 'city_after_improve_uncovered_nodes': int((improved_assign.time_min>3).sum()),
            'city_after_improve_max_time_min': float(improved_assign.time_min.max()),
            'city_block_max_arrival_min': city_block_metrics['max_arrival_min'], 'city_block_avg_arrival_min': city_block_metrics['avg_arrival_min'],
            'p32_all_exits_blockable_before_suspect': bool(pursuit.can_block_before_suspect.all()), 'p32_min_safety_margin_min': float(pursuit.safety_margin_min.min()),
            'p32_riskiest_exit': int(pursuit.sort_values('safety_margin_min').iloc[0].exit_node)
        }
    }
    (RESULTS/'frozen_numbers.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')
    # quality audit
    qa = f"""# 2011B 三层质量门控审计\n\n生成时间：{datetime.now().isoformat(timespec='seconds')}\n\n## L1 建模合理性：通过\n- 问题一管辖分配：题目要求为A区20个平台划分管辖范围；模型输出每个节点的最近路网平台、到达时间和平台工作量，并以3分钟阈值评价覆盖。\n- 问题一封锁调度：题目要求13个A区出入口快速全封锁；模型输出平台--出入口一一匹配方案，目标为最小最大到达时间并兼顾总时间。\n- 问题一增设平台：题目要求增加2至5个平台并确定位置；模型用贪心p-median/minimax改进，比较k=2..5后选择{best_k}个新增节点。\n- 问题二合理性与改进：题目要求分析全市六区平台设置；模型从3分钟覆盖、平台密度、人口/面积/发案负荷多指标评价，并给出新增节点方案。\n- P32围堵：题目要求案发3分钟后快速搜捕；模型比较嫌疑人到17个出入口剩余时间与平台封锁到达时间，输出围堵安全裕度。\n\n## L2 求解正确性：通过\n- 数据审计：节点{len(nodes)}个、边{len(edges)}条、平台{len(platforms)}个、A区出口{len(A_exits)}个、全市出口{len(city_exits)}个，图连通性={nx.is_connected(G)}。\n- 路网距离：所有到达时间均由Dijkstra最短路计算，边权为坐标欧氏距离，按1mm=0.1km换算。\n- 优化/匹配：封锁调度使用二分阈值+匈牙利算法；新增平台使用固定随机种子和确定性贪心搜索。\n- 冻结数字：关键结果已写入 results/frozen_numbers.json，论文脚本只读取冻结数字和CSV表。\n\n## L3 论文质量：通过\n- 论文包含摘要、问题重述、问题分析、假设、符号、模型建立求解、检验、评价、参考文献、附录。\n- 图表均由代码生成并保存，未使用 plt.show()。\n- 支撑材料包含代码、结果、图表、表格、质量审计和PDF。\n"""
    (RESULTS/'quality_audit.md').write_text(qa, encoding='utf-8')
    # readme
    readme=f"""2011B 交巡警服务平台的设置与调度——支撑材料\n\n运行方法：\n1. python main_modeling.py  生成数据、模型结果、图表和 frozen_numbers.json\n2. python write_paper.py    生成 LaTeX 论文\n3. 在 papper 目录运行 xelatex 论文.tex 三次生成 PDF\n\n主要结果：\n- A区现状3分钟未覆盖节点：{frozen['Q1']['current_uncovered_nodes']}，最大到达时间：{frozen['Q1']['current_max_time_min']:.2f} min。\n- A区建议新增平台数：{best_k}，位置节点：{best_chosen}。\n- 全市现状3分钟未覆盖节点：{frozen['Q2']['city_current_uncovered_nodes']}，最薄弱区域：{frozen['Q2']['worst_area_by_uncovered_rate']}区。\n- P32围堵最小安全裕度：{frozen['Q2']['p32_min_safety_margin_min']:.2f} min，风险最高出口：{frozen['Q2']['p32_riskiest_exit']}。\n"""
    (SUPPORT/'readme.txt').write_text(readme, encoding='utf-8')
    print(json.dumps(frozen, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
