from pathlib import Path
import pulp, json
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
# aggregate allocation MILP: find upper-bound composition and length allocations by spec
prob=pulp.LpProblem('agg',pulp.LpMaximize)
n={t:pulp.LpVariable(f'n_{t}',0,cat='Integer') for t in 'LMS'}
u={(i,t):pulp.LpVariable(f'u_{i}_{t}',0,cat='Integer') for i in range(46) for t in 'LMS'}
for i,c in enumerate(counts): prob += sum(u[i,t] for t in 'LMS') <= c
# eligibility: L only 14+, M only 7+, S all
for i in range(22): prob += u[i,'L']==0
for i in range(8): prob += u[i,'M']==0
# roots constraints
prob += sum(u[i,'L'] for i in range(46)) >= 4*n['L']; prob += sum(u[i,'L'] for i in range(46)) <= 5*n['L']
prob += sum(u[i,'M'] for i in range(46)) >= 7*n['M']; prob += sum(u[i,'M'] for i in range(46)) <= 8*n['M']
prob += sum(u[i,'S'] for i in range(46)) >= 19*n['S']; prob += sum(u[i,'S'] for i in range(46)) <= 20*n['S']
for t in 'LMS':
    prob += sum(units[i]*u[i,t] for i in range(46)) >= 177*n[t]
    prob += sum(units[i]*u[i,t] for i in range(46)) <= 179*n[t]
prob += 1000000*sum(n.values()) + 10000*n['L'] + 100*n['M']
prob.solve(pulp.PULP_CBC_CMD(msg=False,timeLimit=60,threads=8,gapRel=0))
print('status',pulp.LpStatus[prob.status], 'obj',pulp.value(prob.objective))
res={'n':{t:int(round(n[t].value() or 0)) for t in 'LMS'},'alloc':{t:[int(round(u[i,t].value() or 0)) for i in range(46)] for t in 'LMS'}}
print(json.dumps(res['n'],ensure_ascii=False))
for t in 'LMS':
    roots=sum(res['alloc'][t]); length=sum(lengths[i]*res['alloc'][t][i] for i in range(46))
    print(t, roots, length, 'avg roots', roots/max(1,res['n'][t]), 'avg len', length/max(1,res['n'][t]))
(ROOT/'quest1/outputs').mkdir(parents=True,exist_ok=True)
(ROOT/'quest1/outputs/aggregate_solution.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
