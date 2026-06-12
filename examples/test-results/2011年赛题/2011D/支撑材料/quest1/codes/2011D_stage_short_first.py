from pathlib import Path
from ortools.sat.python import cp_model
import pandas as pd, json
from collections import defaultdict
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,5),'M':('7-13.5米规格',8,8),'S':('3-6.5米规格',0,20)}
def fmt(x): return str(int(x)) if x==int(x) else str(x)
def solve_stage(spec,n,avail,force_low=False,tl=120):
    name,min_i,std=SPECS[spec]; model=cp_model.CpModel(); x={}
    max_i=7 if force_low else 45
    for b in range(n):
        for i in range(min_i,max_i+1):
            if avail[i]>0: x[b,i]=model.NewIntVar(0,min(avail[i],std),f'x_{b}_{i}')
    for i,c in enumerate(avail):
        if min_i<=i<=max_i: model.Add(sum(x.get((b,i),0) for b in range(n)) <= c)
    if force_low:
        for i in range(0,8): model.Add(sum(x.get((b,i),0) for b in range(n)) == avail[i])
    for b in range(n):
        roots=sum(x.get((b,i),0) for i in range(46)); su=sum(units[i]*x.get((b,i),0) for i in range(46))
        model.Add(roots>=std-1); model.Add(roots<=std); model.Add(su>=177); model.Add(su<=179)
    model.Maximize(sum(units[i]*x.get((b,i),0) for b in range(n) for i in range(46)))
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=tl; solver.parameters.num_search_workers=16
    st=solver.Solve(model); print(spec,n,solver.StatusName(st),flush=True)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None
    bundles=[]; used=[0]*46
    for b in range(n):
        p=[]
        for i,l in enumerate(lengths):
            val=solver.Value(x.get((b,i),0)); p += [l]*val; used[i]+=val
        bundles.append((spec,sorted(p,reverse=True)))
    return bundles,used

def write(bundles):
    seen=defaultdict(int); rows=[]
    for t,p in bundles:
        seen[t]+=1; rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(p),'total_length':round(sum(p),1),'pieces_text':'+'.join(fmt(x) for x in p)})
    df=pd.DataFrame(rows); df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; used=0
        for t in 'LMS':
            u=sum(p.count(l) for tt,p in bundles if tt==t); row[f'used_{t}']=u; used+=u
        row['unused']=c-used; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index(); summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(sum(p) for _,p in bundles); roots=sum(counts); used_roots=sum(len(p) for _,p in bundles)
    frozen={'problem':'CUMCM2011D 天然肠衣搭配问题','bundle_counts':{t:int(sum(1 for tt,_ in bundles if tt==t)) for t in 'LMS'},'total_bundles':len(bundles),'total_available_roots':roots,'total_available_length_m':round(total,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total-used_len,1),'upper_bound_by_length':int(total//88.5),'all_bundles_feasible':bool(((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused>=0).all()),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
    avail=counts.copy(); allb=[]
    # First consume all short raw materials into S bundles, then optimize remaining M/L.
    res=solve_stage('S',16,avail,force_low=True,tl=120)
    if not res: raise SystemExit(1)
    b,u=res; allb+=b; avail=[a-v for a,v in zip(avail,u)]
    for spec,n in [('L',120),('M',50)]:
        res=solve_stage(spec,n,avail,False,120)
        if not res: raise SystemExit(1)
        b,u=res; allb+=b; avail=[a-v for a,v in zip(avail,u)]
    write(allb)
