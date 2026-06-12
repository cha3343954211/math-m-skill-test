from pathlib import Path
import csv
from ortools.sat.python import cp_model
ROOT=Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(x*2) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
comp=(134,44,15); specs=['L']*comp[0]+['M']*comp[1]+['S']*comp[2]
minu={'L':28,'M':14,'S':6}; std={'L':5,'M':8,'S':20}
model=cp_model.CpModel(); x={}; used=[]
for b,t in enumerate(specs):
 for i,u in enumerate(units):
  if u>=minu[t]: x[b,i]=model.NewIntVar(0,min(counts[i],std[t]),f'x_{b}_{i}')
for i,c in enumerate(counts):
 ui=model.NewIntVar(0,c,f'used_{i}'); used.append(ui); model.Add(ui==sum(x.get((b,i),0) for b in range(len(specs)))); model.Add(ui<=c)
for b,t in enumerate(specs):
 roots=sum(x.get((b,i),0) for i in range(46)); su=sum(units[i]*x.get((b,i),0) for i in range(46))
 model.Add(roots>=std[t]-1); model.Add(roots<=std[t]); model.Add(su>=177); model.Add(su<=179)
for b in range(len(specs)-1):
 if specs[b]==specs[b+1]:
  model.Add(sum(units[i]*x.get((b,i),0) for i in range(46)) <= sum(units[i]*x.get((b+1,i),0) for i in range(46)))
model.Maximize(sum(units[i]*used[i] for i in range(46)))
solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=300; solver.parameters.num_search_workers=16; solver.parameters.log_search_progress=False
st=solver.Solve(model); print('STATUS',solver.StatusName(st),'obj',solver.ObjectiveValue()/2,'bound',solver.BestObjectiveBound()/2,'time',solver.WallTime(),flush=True)
if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): raise SystemExit(1)
def fmt(v): return str(int(v)) if abs(v-int(v))<1e-9 else str(v)
seq={'L':0,'M':0,'S':0}; rows=[]
for b,t in enumerate(specs):
 pieces=[]
 for i,l in enumerate(lengths): pieces += [l]*solver.Value(x.get((b,i),0))
 seq[t]+=1; rows.append([f'{t}{seq[t]:03d}',t,len(pieces),fmt(sum(pieces)),'+'.join(fmt(z) for z in sorted(pieces,reverse=True))])
out=ROOT/'tables/final_matching_plan_193.csv'
with out.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f); w.writerow(['bundle_id','spec','roots','total_length','pieces_text']); w.writerows(rows)
print('WROTE',out,seq,flush=True)
