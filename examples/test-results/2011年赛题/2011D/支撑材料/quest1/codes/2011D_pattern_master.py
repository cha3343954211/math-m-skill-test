from pathlib import Path
from itertools import combinations_with_replacement
from collections import Counter,defaultdict
import random,json,time
import pandas as pd
import pulp
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,[4,5]),'M':('7-13.5米规格',8,[7,8]),'S':('3-6.5米规格',0,[19,20])}
def pat_from_idxs(idxs,t):
    v=[0]*46
    for i in idxs: v[i]+=1
    return (t,tuple(v),sum(units[i] for i in idxs),len(idxs))
def gen_exact(t, limit=None):
    name,min_i,ks=SPECS[t]; pats=[]
    for k in ks:
        def rec(start,rem,s,arr):
            if rem==0:
                if 177<=s<=179: pats.append(pat_from_idxs(arr,t))
                return
            for i in range(start,46):
                ns=s+units[i]
                if ns+(rem-1)*units[i]>179: break
                if ns+(rem-1)*units[-1]<177: continue
                rec(i,rem-1,ns,arr+[i])
        rec(min_i,k,0,[])
    return pats
def gen_random_M(N=20000,seed=5):
    random.seed(seed); seen=set(); pats=[]
    for _ in range(N):
        k=8 if random.random()<0.8 else 7
        arr=[]
        for j in range(k):
            # medium products mostly use 8-13.5m, sometimes long downgrade
            if random.random()<0.9:
                cand=list(range(8,22)); ww=[counts[i] for i in cand]
            else:
                cand=list(range(22,30)); ww=[max(1,counts[i]//3) for i in cand]
            arr.append(random.choices(cand,ww,k=1)[0])
        s=sum(units[i] for i in arr)
        if 177<=s<=179:
            key=tuple(sorted(arr))
            if key not in seen:
                seen.add(key); pats.append(pat_from_idxs(key,'M'))
    return pats

def gen_random_S(N=20000,seed=7):
    random.seed(seed); seen=set(); pats=[]
    weights=[counts[i] if i<22 else max(1,counts[i]//5) for i in range(46)]
    pop=list(range(46))
    for _ in range(N):
        k=20 if random.random()<0.75 else 19
        # biased around avg 4.5 with occasional medium downgrade
        arr=[]
        for j in range(k):
            if random.random()<0.88:
                cand=list(range(0,8)); ww=[counts[i] for i in cand]
            else:
                cand=list(range(8,16)); ww=[counts[i] for i in cand]
            arr.append(random.choices(cand,ww,k=1)[0])
        s=sum(units[i] for i in arr)
        if 177<=s<=179:
            key=tuple(sorted(arr))
            if key not in seen:
                seen.add(key); pats.append(pat_from_idxs(key,'S'))
    # add deterministic simple S patterns around 4-5m
    for k in [19,20]:
      def rec(start,rem,s,arr):
        if len(pats)>25000: return
        if rem==0:
          if 177<=s<=179:
            key=tuple(arr)
            if key not in seen: seen.add(key); pats.append(pat_from_idxs(arr,'S'))
          return
        for i in range(start,10):
          ns=s+units[i]
          if ns+(rem-1)*units[i]>179: break
          if ns+(rem-1)*units[13]<177: continue
          rec(i,rem-1,ns,arr+[i])
      rec(0,k,0,[])
    return pats
def solve(pats, tl=180):
    prob=pulp.LpProblem('casing_master',pulp.LpMaximize)
    xs=[pulp.LpVariable(f'x_{j}',0,cat='Integer') for j in range(len(pats))]
    for i,c in enumerate(counts): prob += pulp.lpSum(xs[j]*pats[j][1][i] for j in range(len(pats))) <= c
    prob += pulp.lpSum(xs[j]*(1_000_000 + (10_000 if pats[j][0]=='L' else 100 if pats[j][0]=='M' else 0)) for j in range(len(pats)))
    solver=pulp.PULP_CBC_CMD(msg=False,timeLimit=tl,threads=8,gapRel=0.01)
    st=prob.solve(solver); print('STATUS',pulp.LpStatus[st], 'OBJ', pulp.value(prob.objective), flush=True)
    sol=[]
    for j,x in enumerate(xs):
        q=int(round(x.value() or 0))
        sol += [pats[j]]*q
    return sol
def write(sol):
    seen=defaultdict(int); rows=[]; used=[0]*46
    for t,v,s,k in sol:
        seen[t]+=1
        p=[]
        for i,q in enumerate(v): p += [lengths[i]]*q; used[i]+=q
        rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(p),'total_length':round(sum(p),1),'pieces_text':'+'.join(str(int(x)) if x==int(x) else str(x) for x in sorted(p,reverse=True))})
    df=pd.DataFrame(rows); (ROOT/'tables').mkdir(exist_ok=True); (ROOT/'results').mkdir(exist_ok=True)
    df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; usedn=0
        for t in 'LMS':
            u=sum(p[1][i] for p in sol if p[0]==t); row[f'used_{t}']=u; usedn+=u
        row['unused']=c-usedn; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index(); summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_len=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(lengths[i]*used[i] for i in range(46)); roots=sum(counts); used_roots=sum(used)
    frozen={'solution_tag':'pattern_master_lms','bundle_counts':{t:int(sum(1 for p in sol if p[0]==t)) for t in 'LMS'},'total_bundles':len(sol),'total_available_roots':roots,'total_available_length_m':round(total_len,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':bool(((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused>=0).all()),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
    pats=[]
    for t in ['L']:
        p=gen_exact(t); print(t,len(p),flush=True); pats+=p
    p=gen_random_M(); print('M',len(p),flush=True); pats+=p
    s=gen_random_S(); print('S',len(s),flush=True); pats+=s
    sol=solve(pats,60); write(sol)
