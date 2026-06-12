from pathlib import Path
from collections import defaultdict
import json, pandas as pd
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]; counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':('14米以上规格',22,5),'M':('7-13.5米规格',8,8),'S':('3-6.5米规格',0,20)}
def fmt(x): return str(int(x)) if x==int(x) else str(x)
def greedy_one(inv,min_i,std):
    candidates=[]
    for k in [std,std-1]:
        arr=[]; s=0
        # repeatedly choose piece bringing average close to remaining target 89
        for r in range(k,0,-1):
            best=None
            for i in range(min_i,46):
                if inv[i]<=0: continue
                ns=s+lengths[i]
                rem=r-1
                if rem==0:
                    score=abs(ns-89) if 88.5<=ns<=89.5 else 999
                else:
                    avg=(89-ns)/rem
                    # require possible min/max rough
                    avail=[j for j in range(min_i,46) if inv[j]-(1 if j==i else 0)>0]
                    if not avail: continue
                    if ns+rem*lengths[min(avail)]>89.5 or ns+rem*lengths[max(avail)]<88.5: continue
                    score=abs(lengths[i]-avg)+0.01*i
                if best is None or score<best[0]: best=(score,i)
            if best is None: break
            i=best[1]; inv[i]-=1; arr.append(i); s+=lengths[i]
        if len(arr)==k and 88.5<=s<=89.5:
            v=[0]*46
            for i in arr: v[i]+=1
            return v
        for i in arr: inv[i]+=1
    return None
def build(order, limits):
    inv=counts[:]; bundles=[]
    for t in order:
        for _ in range(limits[t]):
            v=greedy_one(inv,SPECS[t][1],SPECS[t][2])
            if not v: return bundles,inv
            bundles.append((t,v))
    return bundles,inv
def validate(bundles):
    used=[0]*46; bad=[]
    for idx,(t,v) in enumerate(bundles,1):
        roots=sum(v); s=sum(lengths[i]*v[i] for i in range(46)); min_i=SPECS[t][1]; std=SPECS[t][2]
        if not (88.5<=s<=89.5 and roots in (std,std-1) and all(v[i]==0 for i in range(min_i))): bad.append((idx,t,roots,s))
        for i,q in enumerate(v): used[i]+=q
    over=[i for i in range(46) if used[i]>counts[i]]
    return bad,over,used
def write(bundles,tag):
    bad,over,used=validate(bundles); assert not bad and not over
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
if __name__=='__main__':
    best=[]; besttag=''
    for order in [('S','M','L'),('M','S','L'),('L','M','S'),('M','L','S'),('S','L','M'),('L','S','M')]:
      for lim in [{'L':140,'M':70,'S':70},{'L':130,'M':50,'S':30},{'L':120,'M':60,'S':40}]:
        b,inv=build(order,lim); print(order,lim,len(b),{t:sum(1 for tt,_ in b if tt==t) for t in 'LMS'})
        if len(b)>len(best): best=b; besttag=str(order)+str(lim)
    write(best,'greedy_baseline_'+besttag)
