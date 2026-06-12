from pathlib import Path
from ortools.sat.python import cp_model
import pandas as pd, json
from collections import defaultdict
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,5),'M':('7-13.5米规格',8,8),'S':('3-6.5米规格',0,20)}
def fmt(x): return str(int(x)) if x==int(x) else str(x)
def solve(total=190, tl=300):
    maxL=min(140,total); maxM=min(80,total)
    model=cp_model.CpModel()
    y={(b,t):model.NewBoolVar(f'y_{b}_{t}') for b in range(total) for t in 'LMS'}
    for b in range(total): model.Add(sum(y[b,t] for t in 'LMS')==1)
    x={}
    for b in range(total):
        for i in range(46):
            if counts[i]>0: x[b,i]=model.NewIntVar(0,min(counts[i],20),f'x_{b}_{i}')
    used=[]
    for i,c in enumerate(counts):
        ui=model.NewIntVar(0,c,f'used_{i}'); used.append(ui); model.Add(ui==sum(x.get((b,i),0) for b in range(total)))
    for b in range(total):
        roots=sum(x.get((b,i),0) for i in range(46)); su=sum(units[i]*x.get((b,i),0) for i in range(46))
        model.Add(su>=177); model.Add(su<=179)
        # root conditional via linear bounds
        model.Add(roots >= 4*y[b,'L'] + 7*y[b,'M'] + 19*y[b,'S'])
        model.Add(roots <= 5*y[b,'L'] + 8*y[b,'M'] + 20*y[b,'S'])
        # forbidden low lengths for L/M
        for i in range(22): model.Add(x.get((b,i),0) <= 20*(1-y[b,'L']))
        for i in range(8): model.Add(x.get((b,i),0) <= 20*(1-y[b,'M']))
    # Objective fixed total: maximize L, then M, then used length/roots
    model.Maximize(1000000*sum(y[b,'L'] for b in range(total)) + 10000*sum(y[b,'M'] for b in range(total)) + 10*sum(units[i]*used[i] for i in range(46)) + sum(used))
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=tl; solver.parameters.num_search_workers=16
    st=solver.Solve(model); print('STATUS',solver.StatusName(st),'obj',solver.ObjectiveValue(),flush=True)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    bundles=[]
    for b in range(total):
        t=max('LMS', key=lambda tt: solver.Value(y[b,tt])); p=[]
        for i,l in enumerate(lengths): var=x.get((b,i)); p += [l]*(solver.Value(var) if var is not None else 0)
        bundles.append((t,sorted(p,reverse=True)))
    return bundles

def write(bundles):
    seen=defaultdict(int); rows=[]
    for t,p in bundles:
        seen[t]+=1; rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(p),'total_length':round(sum(p),1),'pieces_text':'+'.join(fmt(x) for x in p)})
    df=pd.DataFrame(rows); df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; usedn=0
        for t in 'LMS':
            u=sum(p.count(l) for tt,p in bundles if tt==t); row[f'used_{t}']=u; usedn+=u
        row['unused']=c-usedn; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index(); summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_len=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(sum(p) for _,p in bundles); roots=sum(counts); used_roots=sum(len(p) for _,p in bundles)
    frozen={'problem':'CUMCM2011D 天然肠衣搭配问题','bundle_counts':{t:int(sum(1 for tt,_ in bundles if tt==t)) for t in 'LMS'},'total_bundles':len(bundles),'total_available_roots':roots,'total_available_length_m':round(total_len,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':bool(((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused>=0).all()),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
    for total in [194,193,192,191,190,188,185,180]:
        sol=solve(total,120)
        if sol: write(sol); break
