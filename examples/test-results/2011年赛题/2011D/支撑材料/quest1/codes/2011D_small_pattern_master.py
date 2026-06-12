from pathlib import Path
from collections import defaultdict
import random,json,pandas as pd,pulp
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,[4,5]),'M':('7-13.5米规格',8,[7,8]),'S':('3-6.5米规格',0,[19,20])}
def pat(t,arr):
    v=[0]*46
    for i in arr: v[i]+=1
    return (t,tuple(v),sum(units[i] for i in arr),len(arr))
def gen_L():
    out=[]
    for k in [4,5]:
      def rec(start,rem,s,arr):
        if rem==0:
          if 177<=s<=179: out.append(pat('L',arr))
          return
        for i in range(start,46):
          ns=s+units[i]
          if ns+(rem-1)*units[i]>179: break
          if ns+(rem-1)*units[-1]<177: continue
          rec(i,rem-1,ns,arr+[i])
      rec(22,k,0,[])
    return out
def gen_random(t,N,seed):
    random.seed(seed); seen=set(); out=[]; min_i=SPECS[t][1]; ks=SPECS[t][2]
    if t=='M': bands=[(list(range(8,22)),1.0),(list(range(22,34)),0.25)]
    else: bands=[(list(range(0,8)),1.0),(list(range(8,14)),0.15),(list(range(14,22)),0.03)]
    tries=0
    while len(out)<N and tries<N*80:
        tries+=1; k=random.choice(ks); arr=[]
        for _ in range(k):
            r=random.random(); acc=0; chosen=bands[0][0]
            total=sum(w for _,w in bands)
            rr=random.random()*total; a=0
            for cand,w in bands:
                a+=w
                if rr<=a: chosen=cand; break
            weights=[counts[i] for i in chosen]
            arr.append(random.choices(chosen,weights,k=1)[0])
        s=sum(units[i] for i in arr)
        if 177<=s<=179:
            key=tuple(sorted(arr))
            if key not in seen:
                seen.add(key); out.append(pat(t,key))
    return out
def solve(pats):
    prob=pulp.LpProblem('small_master',pulp.LpMaximize)
    x=[pulp.LpVariable(f'x{j}',0,cat='Integer') for j in range(len(pats))]
    for i,c in enumerate(counts): prob += pulp.lpSum(x[j]*pats[j][1][i] for j in range(len(pats))) <= c
    prob += pulp.lpSum(x[j]*(1000000+(10000 if pats[j][0]=='L' else 100 if pats[j][0]=='M' else 0)) for j in range(len(pats)))
    st=prob.solve(pulp.PULP_CBC_CMD(msg=False,timeLimit=20,threads=8,gapRel=0.02))
    print('status',pulp.LpStatus[st], 'patterns',len(pats), flush=True)
    sol=[]
    for j,var in enumerate(x):
        q=int(round(var.value() or 0)); sol += [pats[j]]*q
    print('bundles',len(sol), {t:sum(1 for p in sol if p[0]==t) for t in 'LMS'}, flush=True)
    return sol
def write(sol):
    seen=defaultdict(int); rows=[]; used=[0]*46
    for t,v,s,k in sol:
        seen[t]+=1; pieces=[]
        for i,q in enumerate(v):
            pieces += [lengths[i]]*q; used[i]+=q
        rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(pieces),'total_length':round(sum(pieces),1),'pieces_text':'+'.join(str(int(z)) if z==int(z) else str(z) for z in sorted(pieces,reverse=True))})
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
    frozen={'solution_tag':'small_pattern_master_feasible','bundle_counts':{t:int(sum(1 for p in sol if p[0]==t)) for t in 'LMS'},'total_bundles':len(sol),'total_available_roots':roots,'total_available_length_m':round(total_len,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':bool(len(df)>0 and ((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused>=0).all()),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
    pats=gen_L()[:300]; print('L',len(pats),flush=True)
    pats+=gen_random('M',300,11); print('after M',len(pats),flush=True)
    pats+=gen_random('S',500,13); print('after S',len(pats),flush=True)
    sol=solve(pats); write(sol)
