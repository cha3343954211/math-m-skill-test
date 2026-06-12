from pathlib import Path
import json, pandas as pd
from collections import defaultdict
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,5),'M':('7-13.5米规格',8,8),'S':('3-6.5米规格',0,20)}
def fmt(x): return str(int(x)) if x==int(x) else str(x)
def take_bundle(inv,min_i,k):
    # DP exact one bundle from current inventory, prefer low total 88.5/89 and preserve scarce long by scanning near avg
    states={(0,0): [0]*46}
    for i in range(min_i,46):
        c=min(inv[i],k)
        if c<=0: continue
        items=list(states.items())
        for (cnt,s),vec in items:
            for q in range(1,c+1):
                nc=cnt+q; ns=s+q*units[i]
                if nc>k or ns>179: break
                key=(nc,ns)
                if key not in states:
                    nv=vec.copy(); nv[i]+=q; states[key]=nv
    cand=[]
    for target in [177,178,179]:
        key=(k,target)
        if key in states: cand.append((abs(target-178),target,states[key]))
    if not cand: return None
    cand.sort()
    v=cand[0][2]
    for i,q in enumerate(v): inv[i]-=q
    return v

def construct(nL,nM,nS,order):
    inv=counts[:]; bundles=[]
    for t in order:
        n={'L':nL,'M':nM,'S':nS}[t]; min_i=SPECS[t][1]; std=SPECS[t][2]
        for _ in range(n):
            v=take_bundle(inv,min_i,std) or take_bundle(inv,min_i,std-1)
            if v is None: return None
            bundles.append((t,v))
    return bundles

def validate(bundles):
    used=[0]*46; bad=[]
    for idx,(t,v) in enumerate(bundles,1):
        roots=sum(v); su=sum(units[i]*v[i] for i in range(46)); min_i=SPECS[t][1]; std=SPECS[t][2]
        if not (177<=su<=179 and roots in (std,std-1) and all(v[i]==0 for i in range(min_i))): bad.append((idx,t,roots,su/2))
        for i,q in enumerate(v): used[i]+=q
    over=[(i,used[i],counts[i]) for i in range(46) if used[i]>counts[i]]
    return bad,over,used

def write(bundles,tag):
    bad,over,used=validate(bundles); assert not bad and not over,(bad[:3],over[:3])
    seen=defaultdict(int); rows=[]
    for t,v in bundles:
        seen[t]+=1; p=[]
        for i,q in enumerate(v): p += [lengths[i]]*q
        rows.append({'bundle_id':f'{t}{seen[t]:03d}','spec':t,'spec_name':SPECS[t][0],'roots':len(p),'total_length':round(sum(p),1),'pieces_text':'+'.join(fmt(x) for x in sorted(p,reverse=True))})
    df=pd.DataFrame(rows); (ROOT/'tables').mkdir(exist_ok=True); (ROOT/'results').mkdir(exist_ok=True)
    df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for i,(l,c) in enumerate(zip(lengths,counts)):
        row={'length':l,'available':c}; usedn=0
        for t in 'LMS':
            u=sum(v[i] for tt,v in bundles if tt==t); row[f'used_{t}']=u; usedn+=u
        row['unused']=c-usedn; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['spec','spec_name']).agg(bundles=('bundle_id','count'),avg_roots=('roots','mean'),avg_total_length=('total_length','mean'),min_total_length=('total_length','min'),max_total_length=('total_length','max')).reset_index(); summary.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_len=sum(l*c for l,c in zip(lengths,counts)); used_len=sum(lengths[i]*used[i] for i in range(46)); roots=sum(counts); used_roots=sum(used)
    frozen={'solution_tag':tag,'bundle_counts':{t:int(sum(1 for tt,_ in bundles if tt==t)) for t in 'LMS'},'total_bundles':len(bundles),'total_available_roots':roots,'total_available_length_m':round(total_len,1),'used_roots':used_roots,'used_length_m':round(used_len,1),'unused_roots':roots-used_roots,'unused_length_m':round(total_len-used_len,1),'upper_bound_by_length':int(total_len//88.5),'all_bundles_feasible':True,'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())]}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(frozen,ensure_ascii=False,indent=2))

def main():
    orders=[('S','M','L'),('S','L','M'),('M','S','L'),('L','M','S'),('L','S','M'),('M','L','S')]
    for total in range(194,179,-1):
      for nL in range(min(140,total),-1,-1):
        for nM in range(min(80,total-nL),-1,-1):
          nS=total-nL-nM
          if nS<0: continue
          # rough length lower checks
          for order in orders:
            b=construct(nL,nM,nS,order)
            if b:
              bad,over,_=validate(b)
              print('TRY',total,nL,nM,nS,order,'bad',len(bad),'over',len(over),flush=True)
              if not bad and not over: write(b,f'dpseq_{nL}_{nM}_{nS}_{"".join(order)}'); return
    print('NO SOL')
if __name__=='__main__': main()
