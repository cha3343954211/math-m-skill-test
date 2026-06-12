from pathlib import Path
import numpy as np, json
from scipy.optimize import milp, LinearConstraint, Bounds
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=np.array([3+0.5*i for i in range(46)]); units=(lengths*2).astype(int)
counts=np.array([43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1])
# var order: nL,nM,nS, then u_i_L,u_i_M,u_i_S
N=3+46*3
c=np.zeros(N); c[:3]=[-1010000,-1000100,-1000000]
lb=np.zeros(N); ub=np.full(N,np.inf); ub[:3]=300
for i,cnt in enumerate(counts):
    for ti in range(3): ub[3+i*3+ti]=cnt
# ineligible upper =0
for i in range(22): ub[3+i*3+0]=0
for i in range(8): ub[3+i*3+1]=0
constraints=[]; lows=[]; highs=[]
# stock per i
for i,cnt in enumerate(counts):
    row=np.zeros(N); row[3+i*3:3+i*3+3]=1
    constraints.append(row); lows.append(0); highs.append(cnt)
# roots and lengths per spec
for ti,t in enumerate('LMS'):
    std={'L':5,'M':8,'S':20}[t]; minr=std-1
    row=np.zeros(N); row[ti]=minr
    for i in range(46): row[3+i*3+ti]-=1
    constraints.append(row); lows.append(-np.inf); highs.append(0) # minr*n <= roots
    row=np.zeros(N); row[ti]=-std
    for i in range(46): row[3+i*3+ti]+=1
    constraints.append(row); lows.append(-np.inf); highs.append(0) # roots <= std*n
    row=np.zeros(N); row[ti]=177
    for i in range(46): row[3+i*3+ti]-=units[i]
    constraints.append(row); lows.append(-np.inf); highs.append(0)
    row=np.zeros(N); row[ti]=-179
    for i in range(46): row[3+i*3+ti]+=units[i]
    constraints.append(row); lows.append(-np.inf); highs.append(0)
res=milp(c, integrality=np.ones(N), bounds=Bounds(lb,ub), constraints=LinearConstraint(np.array(constraints), np.array(lows), np.array(highs)), options={'time_limit':60,'mip_rel_gap':0})
print(res.success,res.message,res.fun)
x=np.rint(res.x).astype(int)
out={'n':dict(zip('LMS',x[:3].tolist())),'alloc':{}}
for ti,t in enumerate('LMS'):
    arr=[int(x[3+i*3+ti]) for i in range(46)]; out['alloc'][t]=arr
print(json.dumps(out['n'],ensure_ascii=False))
for t in 'LMS':
    arr=np.array(out['alloc'][t]); n=out['n'][t]
    print(t,'roots',int(arr.sum()),'len',float((arr*lengths).sum()),'avg roots',arr.sum()/max(1,n),'avg len',(arr*lengths).sum()/max(1,n))
(ROOT/'quest1/outputs').mkdir(parents=True,exist_ok=True)
(ROOT/'quest1/outputs/aggregate_solution.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
