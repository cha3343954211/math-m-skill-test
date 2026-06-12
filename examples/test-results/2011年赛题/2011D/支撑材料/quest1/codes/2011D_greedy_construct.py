from pathlib import Path
from collections import defaultdict
import json, math, time
import pandas as pd
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]
units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,5),'M':('7-13.5米规格',8,8),'S':('3-6.5米规格',0,20)}

def fmt(x): return str(int(x)) if abs(x-int(x))<1e-9 else str(x)

def make_pieces(inv):
    p=[]
    for i,c in enumerate(inv): p += [lengths[i]]*c
    return sorted(p, reverse=True)

def greedy_fill(inv, min_i, k, target=178):
    # choose k items from inv[min_i:] with sum units in [177,179], close to target
    # DP maps (cnt,sum)-> predecessor, maximize use of scarce shorter bins by deterministic scan
    states={(0,0): None}
    pred={}
    for i in range(min_i,46):
        c=inv[i]
        if c<=0: continue
        new=dict(states)
        max_take=min(c,k)
        for (cnt,s) in list(states.keys()):
            for q in range(1,max_take+1):
                nc=cnt+q; ns=s+q*units[i]
                if nc>k or ns>179: break
                # lower-bound prune not needed
                key=(nc,ns)
                if key not in new:
                    new[key]=((cnt,s),i,q); pred[key]=((cnt,s),i,q)
        states=new
    candidates=[s for (cnt,s) in states if cnt==k and 177<=s<=179]
    if not candidates: return None
    # prefer 178 exactly, then lower length to save material
    best=min(candidates, key=lambda s:(abs(s-target), s))
    key=(k,best); use=[0]*46
    while key!=(0,0):
        prev,i,q=states[key]
        use[i]+=q; key=prev
    for i,q in enumerate(use): inv[i]-=q
    return use

def build(nL,nM,nS):
    inv=counts[:]; bundles=[]
    # Build L first with 5 roots where possible, then 4 roots for long scarcity balance
    for _ in range(nL):
        u=greedy_fill(inv,22,5) or greedy_fill(inv,22,4)
        if u is None: return None
        bundles.append(('L',u))
    for _ in range(nM):
        u=greedy_fill(inv,8,8) or greedy_fill(inv,8,7)
        if u is None: return None
        bundles.append(('M',u))
    for _ in range(nS):
        u=greedy_fill(inv,0,20) or greedy_fill(inv,0,19)
        if u is None: return None
        bundles.append(('S',u))
    return bundles,inv

def validate(bundles, inv):
    used=[0]*46
    bad=[]
    for idx,(t,u) in enumerate(bundles,1):
        roots=sum(u); su=sum(units[i]*u[i] for i in range(46))
        min_i=SPECS[t][1]; std=SPECS[t][2]
        if not (177<=su<=179 and roots in (std,std-1) and all(u[i]==0 for i in range(min_i))): bad.append((idx,t,roots,su/2))
        for i,q in enumerate(u): used[i]+=q
    over=[(lengths[i],used[i],counts[i]) for i in range(46) if used[i]>counts[i]]
    return bad,over

def write(bundles, inv, tag):
    seen=defaultdict(int); rows=[]
    for t,u in bundles:
        seen[t]+=1; p=make_pieces(u)
        rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(p),'total_length':round(sum(p),1),'pieces_text':'+'.join(fmt(x) for x in p)})
    df=pd.DataFrame(rows); (ROOT/'tables').mkdir(exist_ok=True)
    df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; usedn=0
        for t in 'LMS':
            u=sum(bu[i] for tt,bu in bundles if tt==t); row[f'used_{t}']=u; usedn+=u
        row['unused']=c-usedn; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index(); summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_len=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(sum(lengths[i]*u[i] for i in range(46)) for _,u in bundles); roots=sum(counts); used_roots=sum(sum(u) for _,u in bundles)
    frozen={'solution_tag':tag,'bundle_counts':{t:int(sum(1 for tt,_ in bundles if tt==t)) for t in 'LMS'},'total_bundles':len(bundles),'total_available_roots':roots,'total_available_length_m':round(total_len,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':True,'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results').mkdir(exist_ok=True); (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2))

def main():
    # heuristic composition search: high L first, feasible total descending
    for total in range(194,179,-1):
      for nL in range(min(140,total), max(0,total-80)-1, -1):
        for nM in range(min(70,total-nL), -1, -1):
          nS=total-nL-nM
          if nS<0: continue
          sol=build(nL,nM,nS)
          if not sol: continue
          bad,over=validate(*sol)
          print('TRY',nL,nM,nS,'bad',len(bad),'over',len(over),flush=True)
          if not bad and not over:
            write(sol[0],sol[1],f'greedy_{nL}_{nM}_{nS}')
            return
    print('NO SOL')
if __name__=='__main__': main()
