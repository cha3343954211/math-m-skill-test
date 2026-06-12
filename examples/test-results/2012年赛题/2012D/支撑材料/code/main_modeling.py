import json, math, heapq, os, csv
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
# 强制指定 Windows 中文字体，避免图题/坐标轴中文显示为方框
_FONT_CANDIDATES = [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/NotoSansSC-VF.ttf']
for _font in _FONT_CANDIDATES:
    if Path(_font).exists():
        font_manager.fontManager.addfont(_font)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=_font).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results'
TABLES = ROOT/'tables'
FIGS1 = ROOT/'quest1'/'figures'
FIGS2 = ROOT/'quest2'/'figures'
for d in [OUT,TABLES,FIGS1,FIGS2,ROOT/'quest1/outputs',ROOT/'quest2/outputs']:
    d.mkdir(parents=True, exist_ok=True)

# 题面参数：若Word公式对象不可抽取，按竞赛常见侧翻约束采用 v_line=5, v_turn=sqrt(10r)
V_LINE = 5.0
MIN_R = 10.0
ACC_LIMIT = 10.0
SAFE = 10.0
WORLD = box(0,0,800,800)
POINTS = {'O':(0.0,0.0), 'A':(300.0,300.0), 'B':(100.0,700.0), 'C':(700.0,640.0)}

def obstacle_geoms():
    obs=[]
    obs.append(('1 正方形', Polygon([(300,400),(500,400),(500,600),(300,600)])))
    obs.append(('2 圆形', Point(550,450).buffer(70, resolution=96)))
    obs.append(('3 平行四边形', Polygon([(360,240),(500,240),(540,330),(400,330)])))
    obs.append(('4 三角形', Polygon([(280,100),(345,210),(410,100)])))
    obs.append(('5 正方形', Polygon([(80,60),(230,60),(230,210),(80,210)])))
    obs.append(('6 三角形', Polygon([(60,300),(150,435),(235,300)])))
    obs.append(('7 长方形', Polygon([(0,470),(220,470),(220,530),(0,530)])))
    obs.append(('8 平行四边形', Polygon([(150,600),(240,600),(270,680),(180,680)])))
    obs.append(('9 长方形', Polygon([(370,680),(430,680),(430,800),(370,800)])))
    obs.append(('10 正方形', Polygon([(540,600),(670,600),(670,730),(540,730)])))
    obs.append(('11 正方形', Polygon([(640,520),(720,520),(720,600),(640,600)])))
    obs.append(('12 长方形', Polygon([(500,140),(800,140),(800,200),(500,200)])))
    return obs

OBS = obstacle_geoms()

def union_inflated(clearance=SAFE, resolution=24):
    return unary_union([g.buffer(clearance, resolution=resolution, join_style=2) for _,g in OBS])

def sample_poly_vertices(geom):
    pts=[]
    if geom.geom_type == 'Polygon':
        coords=list(geom.exterior.coords)[:-1]
        pts.extend(coords)
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            pts.extend(list(poly.exterior.coords)[:-1])
    return [(float(x),float(y)) for x,y in pts if -1e-6<=x<=800+1e-6 and -1e-6<=y<=800+1e-6]

def valid_segment(p,q, forbidden, eps=1e-7):
    line=LineString([p,q])
    if not WORLD.buffer(1e-6).covers(line): return False
    # 不穿越安全膨胀区内部；允许与边界相切
    return not line.crosses(forbidden) and line.difference(forbidden.buffer(-1e-8)).length > 1e-6

def build_graph(start, goal, clearance=SAFE, extra_points=None):
    forbidden=union_inflated(clearance)
    nodes=[start,goal]
    nodes += sample_poly_vertices(forbidden)
    if extra_points: nodes += extra_points
    # 去重
    uniq=[]; seen=set()
    for x,y in nodes:
        key=(round(x,5),round(y,5))
        if key not in seen and WORLD.covers(Point(x,y)) and not forbidden.buffer(-1e-7).contains(Point(x,y)):
            seen.add(key); uniq.append((float(x),float(y)))
    n=len(uniq)
    adj=[[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1,n):
            if valid_segment(uniq[i], uniq[j], forbidden):
                w=math.dist(uniq[i], uniq[j])
                adj[i].append((j,w)); adj[j].append((i,w))
    return uniq, adj, forbidden

def dijkstra(nodes, adj):
    n=len(nodes); dist=[float('inf')]*n; prev=[None]*n
    dist[0]=0; pq=[(0,0)]
    while pq:
        d,u=heapq.heappop(pq)
        if d!=dist[u]: continue
        if u==1: break
        for v,w in adj[u]:
            nd=d+w
            if nd<dist[v]: dist[v]=nd; prev[v]=u; heapq.heappush(pq,(nd,v))
    if not math.isfinite(dist[1]): return None, float('inf')
    path=[]; u=1
    while u is not None:
        path.append(nodes[u]); u=prev[u]
    return path[::-1], dist[1]

def shortest_polyline(a,b,clearance=SAFE):
    nodes,adj,forbidden=build_graph(POINTS[a], POINTS[b], clearance)
    path,dist=dijkstra(nodes,adj)
    return path, dist, forbidden

def angle_between(u,v):
    nu=math.hypot(*u); nv=math.hypot(*v)
    c=max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/(nu*nv)))
    return math.acos(c)

def rounded_segments(poly, r=MIN_R):
    # 返回 line/arc 段；按局部几何用半径r圆角，若相邻边太短则自动缩小半径
    segs=[]
    if len(poly)<2: return segs
    cur=poly[0]
    for i in range(1,len(poly)-1):
        p0=np.array(poly[i-1],float); p=np.array(poly[i],float); p1=np.array(poly[i+1],float)
        u=(p0-p); v=(p1-p)
        L1=np.linalg.norm(u); L2=np.linalg.norm(v)
        if L1<1e-9 or L2<1e-9: continue
        u=u/L1; v=v/L2
        phi=angle_between(u,v)  # 两条射线夹角
        if phi<1e-4 or abs(math.pi-phi)<1e-4:
            segs.append({'type':'line','start':tuple(cur),'end':tuple(p)})
            cur=tuple(p); continue
        rr=min(r, 0.45*min(L1,L2)/max(1e-6, math.tan(phi/2)))
        d=rr*math.tan(phi/2)
        t1=p+u*d; t2=p+v*d
        # 角平分线方向，圆心在内角方向，距离 r/sin(phi/2)
        bis=u+v; bis=bis/np.linalg.norm(bis)
        center=p+bis*(rr/math.sin(phi/2))
        # 方向
        a1=math.atan2(t1[1]-center[1], t1[0]-center[0]); a2=math.atan2(t2[1]-center[1], t2[0]-center[0])
        cross=(t1[0]-center[0])*(t2[1]-center[1])-(t1[1]-center[1])*(t2[0]-center[0])
        direction='ccw' if cross>0 else 'cw'
        if math.dist(cur, tuple(t1))>1e-6:
            segs.append({'type':'line','start':tuple(cur),'end':tuple(t1)})
        segs.append({'type':'arc','start':tuple(t1),'end':tuple(t2),'center':tuple(center),'radius':rr,'direction':direction,
                     'angle': abs((a2-a1+math.pi)%(2*math.pi)-math.pi)})
        cur=tuple(t2)
    if math.dist(cur, poly[-1])>1e-6:
        segs.append({'type':'line','start':tuple(cur),'end':tuple(poly[-1])})
    return segs

def seg_length(s):
    if s['type']=='line': return math.dist(s['start'],s['end'])
    return s['radius']*s['angle']

def seg_time(s):
    if s['type']=='line': return seg_length(s)/V_LINE
    v=min(V_LINE, math.sqrt(ACC_LIMIT*s['radius']))
    return seg_length(s)/v

def segments_summary(segs):
    return sum(seg_length(s) for s in segs), sum(seg_time(s) for s in segs)

def path_valid(poly, clearance=SAFE):
    forbidden=union_inflated(clearance)
    line=LineString(poly)
    return WORLD.covers(line) and not line.crosses(forbidden) and not forbidden.buffer(-1e-8).contains(line)

def plot_path(path, title, outpath, segs=None):
    fig,ax=plt.subplots(figsize=(8,8))
    for name,g in OBS:
        x,y=g.exterior.xy; ax.fill(x,y, color='#999999', alpha=.45, edgecolor='black', linewidth=.8)
        cx,cy=g.centroid.x,g.centroid.y; ax.text(cx,cy,name.split()[0],ha='center',va='center',fontsize=8)
    forbidden=union_inflated(SAFE)
    geoms=[forbidden] if forbidden.geom_type=='Polygon' else list(forbidden.geoms)
    for g in geoms:
        x,y=g.exterior.xy; ax.plot(x,y,'r--',lw=.5,alpha=.5)
    if path:
        xs=[p[0] for p in path]; ys=[p[1] for p in path]
        ax.plot(xs,ys,'b-o',lw=2,ms=3,label='折线骨架')
    if segs:
        for s in segs:
            if s['type']=='line':
                ax.plot([s['start'][0],s['end'][0]],[s['start'][1],s['end'][1]],color='green',lw=2)
            else:
                c=s['center']; r=s['radius']
                a1=math.atan2(s['start'][1]-c[1],s['start'][0]-c[0]); a2=math.atan2(s['end'][1]-c[1],s['end'][0]-c[0])
                if s['direction']=='ccw':
                    if a2<a1: a2+=2*math.pi
                    th=np.linspace(a1,a2,50)
                else:
                    if a1<a2: a1+=2*math.pi
                    th=np.linspace(a1,a2,50)
                ax.plot(c[0]+r*np.cos(th), c[1]+r*np.sin(th), color='green', lw=2)
    for k,p in POINTS.items(): ax.scatter(*p,c='red'); ax.text(p[0]+6,p[1]+6,k,fontsize=12)
    ax.set_xlim(0,800); ax.set_ylim(0,800); ax.set_aspect('equal'); ax.grid(True,alpha=.25)
    ax.set_title(title); ax.set_xlabel('x'); ax.set_ylabel('y')
    fig.tight_layout(); fig.savefig(outpath,dpi=300,bbox_inches='tight'); plt.close(fig)

def fmt(p): return f"({p[0]:.2f},{p[1]:.2f})"

def export_segments(label,segs,outcsv):
    rows=[]
    for i,s in enumerate(segs,1):
        row={'路径':label,'段号':i,'类型':'直线' if s['type']=='line' else '圆弧','起点':fmt(s['start']),'终点':fmt(s['end']),
             '圆心':'' if s['type']=='line' else fmt(s['center']),'半径':'' if s['type']=='line' else f"{s['radius']:.2f}",
             '方向':'' if s['type']=='line' else s['direction'], '长度':seg_length(s),'时间':seg_time(s)}
        rows.append(row)
    pd.DataFrame(rows).to_csv(outcsv,index=False,encoding='utf-8-sig')
    return rows

def main():
    route_pairs=[('O','A'),('O','B'),('O','C')]
    all_results={}
    summary=[]; all_segment_rows=[]
    for a,b in route_pairs:
        path,dist,_=shortest_polyline(a,b,clearance=SAFE)
        # 用安全裕度20生成圆角可行路线，避免圆角侵入10单位安全区
        safe_path,safe_dist,_=shortest_polyline(a,b,clearance=20.0)
        segs=rounded_segments(safe_path, MIN_R)
        length,time=segments_summary(segs)
        label=f'{a}-{b}'
        all_results[label]={'polyline_clearance10':path,'polyline_length_clearance10':dist,'rounded_path_clearance20':safe_path,
                            'rounded_length':length,'rounded_time':time,'valid_skeleton_10':path_valid(path,SAFE),'valid_skeleton_20':path_valid(safe_path,20.0)}
        summary.append({'路径':label,'10单位安全折线最短距离':dist,'圆角可行路线总距离':length,'按速度约束总时间':time,'骨架节点数':len(path),'圆角段数':len(segs)})
        rows=export_segments(label,segs,ROOT/'quest1/outputs'/f'{label}_segments.csv'); all_segment_rows+=rows
        plot_path(safe_path,f'{label} 避障最短路径（圆角化）',FIGS1/f'{label}_path.png',segs)
    # O-A-B-C-O 组合
    combo=[('O','A'),('A','B'),('B','C'),('C','O')]
    combo_path=[]; combo_segs=[]; combo_dist10=0
    for a,b in combo:
        p,d,_=shortest_polyline(a,b,SAFE); combo_dist10+=d
        sp,sd,_=shortest_polyline(a,b,20.0)
        if combo_path: combo_path += sp[1:]
        else: combo_path += sp
        combo_segs += rounded_segments(sp,MIN_R)
    combo_len,combo_time=segments_summary(combo_segs)
    all_results['O-A-B-C-O']={'polyline_length_clearance10':combo_dist10,'rounded_path_clearance20':combo_path,'rounded_length':combo_len,'rounded_time':combo_time}
    summary.append({'路径':'O-A-B-C-O','10单位安全折线最短距离':combo_dist10,'圆角可行路线总距离':combo_len,'按速度约束总时间':combo_time,'骨架节点数':len(combo_path),'圆角段数':len(combo_segs)})
    all_segment_rows += export_segments('O-A-B-C-O',combo_segs,ROOT/'quest1/outputs'/'O-A-B-C-O_segments.csv')
    plot_path(combo_path,'O-A-B-C-O 连续巡回避障路径',FIGS1/'O-A-B-C-O_path.png',combo_segs)

    # 问题2：O到A最短时间。速度函数下若转弯半径>=2.5则弧线速度不低于直线速度(上限取V_LINE)，故用尽量短且满足r>=10的圆角路线即时间最短近似。
    oa_path = all_results['O-A']['rounded_path_clearance20']
    candidates=[]
    for r in [10,15,20,30,40,60,80]:
        segs=rounded_segments(oa_path,r); L,T=segments_summary(segs)
        candidates.append({'半径参数':r,'总距离':L,'总时间':T,'段数':len(segs)})
    cand_df=pd.DataFrame(candidates)
    cand_df.to_csv(ROOT/'quest2/outputs/time_radius_candidates.csv',index=False,encoding='utf-8-sig')
    best_r=float(cand_df.loc[cand_df['总时间'].idxmin(),'半径参数'])
    best_segs=rounded_segments(oa_path,best_r); best_len,best_time=segments_summary(best_segs)
    export_segments('O-A最短时间',best_segs,ROOT/'quest2/outputs/O-A_time_segments.csv')
    plot_path(oa_path,'O-A 最短时间路径',FIGS2/'O-A_time_path.png',best_segs)
    fig,ax=plt.subplots(figsize=(6,4)); ax.plot(cand_df['半径参数'],cand_df['总时间'],'o-'); ax.set_xlabel('圆角半径参数'); ax.set_ylabel('总时间/s'); ax.set_title('O-A路径转弯半径敏感性'); ax.grid(True,alpha=.3); fig.tight_layout(); fig.savefig(FIGS2/'time_sensitivity_radius.png',dpi=300,bbox_inches='tight'); plt.close(fig)

    pd.DataFrame(summary).to_csv(TABLES/'final_path_summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(all_segment_rows).to_csv(TABLES/'all_segments.csv',index=False,encoding='utf-8-sig')
    frozen={
        'parameters':{'safe_distance':SAFE,'min_turn_radius':MIN_R,'line_speed':V_LINE,'turn_speed_formula':'min(V_line, sqrt(10*r))'},
        'summary':summary,
        'time_candidates':candidates,
        'q2_best':{'radius':best_r,'length':best_len,'time':best_time},
        'paths':all_results
    }
    (OUT/'frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'summary':summary,'q2_best':frozen['q2_best']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
