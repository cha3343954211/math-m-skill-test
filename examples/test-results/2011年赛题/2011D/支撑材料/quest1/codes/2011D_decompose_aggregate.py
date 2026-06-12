from pathlib import Path
from ortools.sat.python import cp_model
import json
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
data=json.loads((ROOT/'quest1/outputs/aggregate_solution.json').read_text(encoding='utf-8'))
def solve_spec(t, tl=120):
    arr=data['alloc'][t]; n=data['n'][t]; min_i={'L':22,'M':8,'S':0}[t]; std={'L':5,'M':8,'S':20}[t]
    model=cp_model.CpModel(); x={}
    for b in range(n):
        for i,c in enumerate(arr):
            if c: x[b,i]=model.NewIntVar(0,min(c,std),f'x_{b}_{i}')
    for i,c in enumerate(arr):
        if c: model.Add(sum(x.get((b,i),0) for b in range(n))==c)
    for b in range(n):
        roots=sum(x.get((b,i),0) for i in range(46)); su=sum(units[i]*x.get((b,i),0) for i in range(46))
        model.Add(roots>=std-1); model.Add(roots<=std); model.Add(su>=177); model.Add(su<=179)
        for i in range(min_i):
            if (b,i) in x: model.Add(x[b,i]==0)
    # symmetry: nonincreasing first long count rough for speed? skip
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=tl; solver.parameters.num_search_workers=16; solver.parameters.log_search_progress=False
    st=solver.Solve(model); print(t,n,solver.StatusName(st),solver.WallTime(),flush=True)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    bundles=[]
    for b in range(n): bundles.append([solver.Value(x.get((b,i),0)) for i in range(46)])
    (ROOT/f'quest1/outputs/decompose_{t}.json').write_text(json.dumps(bundles),encoding='utf-8')
    return bundles
if __name__=='__main__':
    for t in 'LMS': solve_spec(t,180)
