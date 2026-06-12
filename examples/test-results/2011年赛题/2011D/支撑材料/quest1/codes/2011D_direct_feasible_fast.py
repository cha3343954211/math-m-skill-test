from pathlib import Path
from ortools.sat.python import cp_model
import json
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
def feasible(nL,nM,nS,tl=30):
    n=nL+nM+nS; types=['L']*nL+['M']*nM+['S']*nS
    model=cp_model.CpModel(); x={}
    for b,t in enumerate(types):
        min_i={'L':22,'M':8,'S':0}[t]; std={'L':5,'M':8,'S':20}[t]
        for i,c in enumerate(counts):
            if c and i>=min_i: x[b,i]=model.NewIntVar(0,min(c,std),f'x_{b}_{i}')
    for i,c in enumerate(counts):
        if c: model.Add(sum(x.get((b,i),0) for b in range(n))<=c)
    for b,t in enumerate(types):
        std={'L':5,'M':8,'S':20}[t]
        roots=sum(x.get((b,i),0) for i in range(46)); su=sum(units[i]*x.get((b,i),0) for i in range(46))
        model.Add(roots>=std-1); model.Add(roots<=std); model.Add(su>=177); model.Add(su<=179)
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=tl; solver.parameters.num_search_workers=16; solver.parameters.random_seed=123
    st=solver.Solve(model); print((nL,nM,nS),solver.StatusName(st),solver.WallTime(),flush=True)
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        bundles=[]
        for b,t in enumerate(types): bundles.append((t,[solver.Value(x.get((b,i),0)) for i in range(46)]))
        (ROOT/'quest1/outputs/direct_feasible.json').write_text(json.dumps({'composition':[nL,nM,nS],'bundles':bundles},ensure_ascii=False),encoding='utf-8')
        return True
    return False
if __name__=='__main__':
    comps=[]
    for total in range(194,184,-1):
      for nL in range(min(134,total), max(0,total-80)-1, -1):
        for nM in range(min(70,total-nL), -1, -1):
          nS=total-nL-nM
          if nS<0: continue
          comps.append((total,-nL,-nM,nL,nM,nS))
    # prioritize around known aggregate upper neighborhoods
    priority=[(133,45,16),(133,44,17),(132,46,16),(132,45,17),(131,48,16),(130,49,16),(130,48,17),(129,50,17)]
    seen=set()
    for c in priority:
        seen.add(c)
        if feasible(*c,tl=60): break
    else:
      for _,_,_,a,b,c in comps:
        if (a,b,c) in seen: continue
        if feasible(a,b,c,tl=10): break
