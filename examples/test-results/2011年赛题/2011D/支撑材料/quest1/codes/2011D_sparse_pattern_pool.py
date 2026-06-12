from pathlib import Path
from collections import defaultdict
import random, json, time
import numpy as np, pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=np.array([3+0.5*i for i in range(46)], dtype=float)
units=(lengths*2).astype(int)
counts=np.array([43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1], dtype=int)
SPECS={'L':('14米以上规格',22,[4,5]),'M':('7-13.5米规格',8,[7,8]),'S':('3-6.5米规格',0,[19,20])}

def fmt(x): return str(int(x)) if float(x).is_integer() else str(float(x))

def pattern(t, arr):
    v=np.zeros(46, dtype=np.int16)
    for i in arr: v[i]+=1
    return t, tuple(int(z) for z in v)

def gen_patterns(t, target_n, seed=1):
    random.seed(seed)
    min_i=SPECS[t][1]; ks=SPECS[t][2]
    seen=set(); out=[]
    # band probabilities tuned to generate feasible sums quickly
    if t=='L':
        bands=[(list(range(22,46)),1.0)]
    elif t=='M':
        bands=[(list(range(8,22)),0.82),(list(range(22,34)),0.18)]
    else:
        bands=[(list(range(0,8)),0.86),(list(range(8,14)),0.12),(list(range(14,22)),0.02)]
    weights_by_band=[]
    for cand,w in bands:
        ww=[max(1,int(counts[i])) for i in cand]
        weights_by_band.append((cand,ww,w))
    tries=0
    while len(out)<target_n and tries<target_n*500:
        tries+=1
        k=random.choice(ks)
        arr=[]
        total_w=sum(w for _,_,w in weights_by_band)
        for _ in range(k):
            rr=random.random()*total_w; acc=0
            cand,ww,_w=weights_by_band[0]
            for cands,wws,w in weights_by_band:
                acc+=w
                if rr<=acc:
                    cand,ww=cands,wws; break
            arr.append(random.choices(cand, ww, k=1)[0])
        s=sum(units[i] for i in arr)
        if 177<=s<=179:
            key=(t,tuple(sorted(arr)))
            if key not in seen:
                seen.add(key); out.append(pattern(t,key[1]))
    print(t, 'patterns', len(out), 'tries', tries, flush=True)
    return out

def solve_once(nL=3000,nM=3000,nS=5000,tl=80):
    pats=[]
    pats += gen_patterns('L', nL, 101)
    pats += gen_patterns('M', nM, 202)
    pats += gen_patterns('S', nS, 303)
    P=len(pats)
    print('total patterns', P, flush=True)
    A=lil_matrix((46,P), dtype=float)
    c=np.zeros(P)
    for j,(t,v) in enumerate(pats):
        for i,q in enumerate(v):
            if q: A[i,j]=q
        c[j]=-(1_000_000 + (10_000 if t=='L' else 100 if t=='M' else 0))
    cons=LinearConstraint(A.tocsr(), np.zeros(46), counts.astype(float))
    res=milp(c, integrality=np.ones(P), bounds=Bounds(np.zeros(P), np.full(P, np.inf)), constraints=cons, options={'time_limit':tl, 'mip_rel_gap':0.02, 'disp': False})
    print('milp',res.success,res.message,'fun',res.fun, flush=True)
    if res.x is None:
        return []
    xs=np.rint(res.x).astype(int)
    sol=[]
    for j,q in enumerate(xs):
        if q>0:
            sol += [pats[j]]*int(q)
    print('solution',len(sol),{t:sum(1 for tt,_ in sol if tt==t) for t in 'LMS'}, flush=True)
    return sol

def write_solution(sol, tag):
    seen=defaultdict(int); rows=[]; used=np.zeros(46,dtype=int)
    for t,v in sol:
        seen[t]+=1; pieces=[]
        for i,q in enumerate(v):
            if q:
                pieces += [float(lengths[i])]*q; used[i]+=q
        rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(pieces),'total_length':round(sum(pieces),1),'pieces_text':'+'.join(fmt(x) for x in sorted(pieces, reverse=True))})
    df=pd.DataFrame(rows)
    (ROOT/'tables').mkdir(parents=True,exist_ok=True); (ROOT/'results').mkdir(parents=True,exist_ok=True)
    df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig')
    df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,cnt) in enumerate(zip(lengths,counts)):
        row={'length':float(l),'available':int(cnt)}; usedn=0
        for t in 'LMS':
            u=sum(v[i] for tt,v in sol if tt==t); row[f'used_{t}']=int(u); usedn+=u
        row['unused']=int(cnt-usedn); usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index()
    summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_len=float((lengths*counts).sum()); used_len=float((lengths*used).sum())
    frozen={'solution_tag':tag,'bundle_counts':{t:int(sum(1 for tt,_ in sol if tt==t)) for t in 'LMS'},'total_bundles':len(sol),'total_available_roots':int(counts.sum()),'total_available_length_m':round(total_len,1),'used_roots':int(used.sum()),'used_length_m':round(used_len,1),'unused_roots':int(counts.sum()-used.sum()),'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':bool(len(df)>0 and ((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused>=0).all()),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2), flush=True)

if __name__=='__main__':
    best=[]
    for scale in [(1200,1200,1800,35),(2500,2500,3500,60),(4000,4000,6000,90)]:
        sol=solve_once(*scale)
        if len(sol)>len(best):
            best=sol
            write_solution(best, f'sparse_pattern_pool_{scale[0]}_{scale[1]}_{scale[2]}')
        if len(best)>=180:
            break
