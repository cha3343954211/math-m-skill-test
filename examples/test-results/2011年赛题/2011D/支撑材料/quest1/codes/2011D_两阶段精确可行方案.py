from pathlib import Path
from ortools.sat.python import cp_model
import json, pandas as pd, numpy as np
from collections import defaultdict
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]

def solve_S(nS=16):
    model=cp_model.CpModel(); x={}
    for b in range(nS):
        for i in range(22): # up to 13.5 only for S downgrades; low all forced
            if counts[i]>0: x[b,i]=model.NewIntVar(0,min(counts[i],20),f'x_{b}_{i}')
    for i,c in enumerate(counts[:8]): model.Add(sum(x.get((b,i),0) for b in range(nS))==c)
    for i,c in enumerate(counts[8:22], start=8): model.Add(sum(x.get((b,i),0) for b in range(nS))<=c)
    for b in range(nS):
        roots=sum(x.get((b,i),0) for i in range(22)); su=sum(units[i]*x.get((b,i),0) for i in range(22))
        model.Add(roots>=19); model.Add(roots<=20); model.Add(su>=177); model.Add(su<=179)
    # symmetry by sum
    for b in range(nS-1): model.Add(sum(units[i]*x.get((b,i),0) for i in range(22)) <= sum(units[i]*x.get((b+1,i),0) for i in range(22)))
    # minimize mid length used to leave more for M
    model.Minimize(sum(units[i]*x.get((b,i),0) for b in range(nS) for i in range(8,22)))
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=120; solver.parameters.num_search_workers=8
    st=solver.Solve(model); print('S', solver.StatusName(st), solver.ObjectiveValue()/2, flush=True)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    bundles=[]; used=[0]*46
    for b in range(nS):
        pieces=[]
        for i in range(22):
            val=solver.Value(x.get((b,i),0)); pieces += [lengths[i]]*val; used[i]+=val
        bundles.append(('S',pieces))
    return bundles,used

def solve_LM(avail,nL=134,nM=44):
    # solve L first using >=14; then M using >=7. Try exact remaining all >=7 used.
    model=cp_model.CpModel(); specs=['L']*nL+['M']*nM; x={}; B=len(specs)
    for b,t in enumerate(specs):
        min_i=22 if t=='L' else 8; std=5 if t=='L' else 8
        for i in range(min_i,46):
            if avail[i]>0: x[b,i]=model.NewIntVar(0,min(avail[i],std),f'x_{b}_{i}')
    for i,c in enumerate(avail):
        if i>=8: model.Add(sum(x.get((b,i),0) for b in range(B))==c)
    for b,t in enumerate(specs):
        std=5 if t=='L' else 8
        roots=sum(x.get((b,i),0) for i in range(46)); su=sum(units[i]*x.get((b,i),0) for i in range(46))
        model.Add(roots>=std-1); model.Add(roots<=std); model.Add(su>=177); model.Add(su<=179)
    # symmetry within L and M
    for b in range(B-1):
        if specs[b]==specs[b+1]: model.Add(sum(units[i]*x.get((b,i),0) for i in range(46)) <= sum(units[i]*x.get((b+1,i),0) for i in range(46)))
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=300; solver.parameters.num_search_workers=8
    st=solver.Solve(model); print('LM',nL,nM,solver.StatusName(st), flush=True)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    bundles=[]; used=[0]*46
    for b,t in enumerate(specs):
        pieces=[]
        for i in range(46):
            val=solver.Value(x.get((b,i),0)); pieces += [lengths[i]]*val; used[i]+=val
        bundles.append((t,pieces))
    return bundles,used

def write_plan(bundles):
    specs={'L':'14米以上规格','M':'7-13.5米规格','S':'3-6.5米规格'}
    seen=defaultdict(int); rows=[]
    for t,pieces in bundles:
        seen[t]+=1; rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':specs[t],'roots':len(pieces),'total_length':round(sum(pieces),1),'pieces_text':'+'.join(str(int(x)) if x==int(x) else str(x) for x in sorted(pieces,reverse=True))})
    df=pd.DataFrame(rows); df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; used=0
        for t in 'LMS':
            u=sum(p.count(l) for tt,p in bundles if tt==t); row[f'used_{t}']=u; used+=u
        row['unused']=c-used; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index()
    summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(sum(p) for _,p in bundles); roots=sum(counts); used_roots=sum(len(p) for _,p in bundles)
    frozen={'problem':'CUMCM2011D 天然肠衣搭配问题','bundle_counts':{t:int(sum(1 for tt,_ in bundles if tt==t)) for t in 'LMS'},'total_bundles':len(bundles),'total_available_roots':roots,'total_available_length_m':round(total,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total-used_len,1),'upper_bound_by_length':int(total//88.5),'all_bundles_feasible':bool(((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused==0).all()),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    s=solve_S(16)
    if not s: raise SystemExit(1)
    sb, su=s; avail=[c-u for c,u in zip(counts,su)]
    # Try lexicographic nL/nM around aggregate
    for nL,nM in [(134,44),(133,45),(132,46),(131,47),(130,48),(129,49),(128,50),(127,51),(126,52),(125,53),(124,54),(123,55),(122,56),(121,57),(120,58)]:
        lm=solve_LM(avail,nL,nM)
        if lm:
            lb,lu=lm
            write_plan(lb+sb)
            break
    else:
        raise SystemExit('no LM')
