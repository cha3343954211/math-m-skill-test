from pathlib import Path
from collections import defaultdict
import json
import pandas as pd
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,5),'M':('7-13.5米规格',8,8),'S':('3-6.5米规格',0,20)}
def fmt(x): return str(int(x)) if x==int(x) else str(x)
def find_bundle(inv,min_i,k,target=178,prefer='balanced'):
    # DFS over descending lengths with pruning; returns use vector
    idxs=[i for i in range(45,min_i-1,-1) if inv[i]>0]
    # try around average target/k; sort by closeness for speed
    avg=target/k
    idxs.sort(key=lambda i:(abs(units[i]-avg), -units[i]))
    use=[0]*46
    suffix=[]
    # simple recursive choose one by one, nondecreasing position to allow repeats
    best=None
    def rec(pos,start,remk,rems):
        nonlocal best
        if remk==0:
            if 177<=rems<=179: best=use[:]; return True
            return False
        if rems + remk*min(units[i] for i in idxs if inv[i]>use[i]) >179 if any(inv[i]>use[i] for i in idxs) else True: return False
        # candidate bins with stock, enforce combination order via start index in sorted idxs
        for jj in range(start,len(idxs)):
            i=idxs[jj]
            if use[i]>=inv[i]: continue
            ns=rems+units[i]
            if ns>179: continue
            # lower/upper bound with available remaining rough
            use[i]+=1
            if rec(pos+1,jj,remk-1,ns): return True
            use[i]-=1
        return False
    ok=rec(0,0,k,0)
    if not ok: return None
    for i,q in enumerate(best): inv[i]-=q
    return best

def build(nL,nM,nS):
    inv=counts[:]; bundles=[]
    # interleave S first to preserve short exact combinations, then M, then L
    for t,n,min_i,ks in [('S',nS,0,[20,19]),('M',nM,8,[8,7]),('L',nL,22,[5,4])]:
        for _ in range(n):
            u=None
            for k in ks:
                u=find_bundle(inv,min_i,k)
                if u: break
            if u is None: return None
            bundles.append((t,u))
    return bundles,inv

def validate(bundles):
    used=[0]*46; bad=[]
    for idx,(t,u) in enumerate(bundles,1):
        roots=sum(u); su=sum(units[i]*u[i] for i in range(46)); min_i=SPECS[t][1]; std=SPECS[t][2]
        if not (177<=su<=179 and roots in (std,std-1) and all(u[i]==0 for i in range(min_i))): bad.append((idx,t,roots,su/2))
        for i,q in enumerate(u): used[i]+=q
    over=[i for i in range(46) if used[i]>counts[i]]
    return bad,over,used

def write(bundles,tag):
    seen=defaultdict(int); rows=[]
    for t,u in bundles:
        seen[t]+=1; p=[]
        for i,q in enumerate(u): p += [lengths[i]]*q
        p=sorted(p,reverse=True)
        rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(p),'total_length':round(sum(p),1),'pieces_text':'+'.join(fmt(x) for x in p)})
    df=pd.DataFrame(rows); (ROOT/'tables').mkdir(exist_ok=True)
    df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    _,_,used=validate(bundles); usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; usedn=0
        for t in 'LMS':
            u=sum(bu[i] for tt,bu in bundles if tt==t); row[f'used_{t}']=u; usedn+=u
        row['unused']=c-usedn; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index(); summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_len=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(lengths[i]*used[i] for i in range(46)); roots=sum(counts); used_roots=sum(used)
    frozen={'solution_tag':tag,'bundle_counts':{t:int(sum(1 for tt,_ in bundles if tt==t)) for t in 'LMS'},'total_bundles':len(bundles),'total_available_roots':roots,'total_available_length_m':round(total_len,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':True,'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results').mkdir(exist_ok=True); (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2))

def main():
    candidates=[]
    for total in range(194,179,-1):
      for nS in range(0,min(80,total)+1):
        for nM in range(0,min(80,total-nS)+1):
          nL=total-nS-nM
          if nL<0: continue
          candidates.append((total,-nL,-nM,nL,nM,nS))
    for _,_,_,nL,nM,nS in candidates:
      sol=build(nL,nM,nS)
      if sol:
        bad,over,_=validate(sol[0]); print('FOUND?',nL,nM,nS,'bad',bad[:1],'over',over[:3],flush=True)
        if not bad and not over: write(sol[0],f'dfs_{nL}_{nM}_{nS}'); return
    print('NO SOL')
if __name__=='__main__': main()
