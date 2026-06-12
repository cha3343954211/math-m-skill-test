import csv, time
from pathlib import Path
from collections import defaultdict
import pulp

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
lengths=[3+0.5*i for i in range(46)]
units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':{'min_unit':28,'roots':[4,5],'target':134}, 'M':{'min_unit':14,'roots':[7,8],'target':44}, 'S':{'min_unit':6,'roots':[19,20],'target':16}}

def gen_patterns(spec):
    min_u=SPECS[spec]['min_unit']; roots_opts=SPECS[spec]['roots']
    start=next(i for i,u in enumerate(units) if u>=min_u)
    elig=list(range(start,46)); pats=[]; cur=[]
    def rec(last_pos, rem_r, rem_s, chosen):
        if rem_r==0:
            if rem_s==0:
                vec=[0]*46
                for i in chosen: vec[i]+=1
                pats.append(tuple(vec))
            return
        # nondecreasing indices. Min all remaining at current; max all remaining at highest.
        if last_pos>=len(elig): return
        if rem_s < rem_r*units[elig[last_pos]] or rem_s > rem_r*units[elig[-1]]: return
        for pos in range(last_pos, len(elig)):
            i=elig[pos]; u=units[i]
            # after choosing u, remaining can be from pos..end
            if rem_s-u < (rem_r-1)*u: break
            if rem_s-u > (rem_r-1)*units[elig[-1]]: continue
            rec(pos, rem_r-1, rem_s-u, chosen+[i])
    for r in roots_opts:
        for s in (177,178,179):
            rec(0,r,s,[])
    return pats

def main():
    allp=[]
    for spec in ['L','M','S']:
        t=time.time(); pats=gen_patterns(spec)
        print(spec, len(pats), 'patterns', 'time', round(time.time()-t,2), flush=True)
        allp += [(spec,p) for p in pats]
    prob=pulp.LpProblem('casing_patterns', pulp.LpMinimize)
    y=[pulp.LpVariable(f'y_{sp}_{j}', lowBound=0, cat='Integer') for j,(sp,p) in enumerate(allp)]
    for spec in ['L','M','S']:
        prob += pulp.lpSum(y[j] for j,(sp,p) in enumerate(allp) if sp==spec) == SPECS[spec]['target']
    for i,c in enumerate(counts):
        prob += pulp.lpSum(y[j]*p[i] for j,(sp,p) in enumerate(allp)) == c
    prob += 0
    status=prob.solve(pulp.PULP_CBC_CMD(msg=True, timeLimit=600, threads=8))
    print('status', pulp.LpStatus[status], flush=True)
    if pulp.LpStatus[status] not in ('Optimal','Feasible'):
        raise SystemExit(2)
    bundles=[]; seq=defaultdict(int)
    for j,(spec,p) in enumerate(allp):
        val=round(y[j].value() or 0)
        for _ in range(val):
            seq[spec]+=1; pieces=[]
            for i,k in enumerate(p): pieces += [lengths[i]]*k
            bundles.append((f'{spec}{seq[spec]:03d}', spec, len(pieces), sum(pieces), pieces))
    def fmt(x): return str(int(x)) if abs(x-int(x))<1e-9 else str(x)
    out=ROOT/'tables/final_matching_plan.csv'
    with out.open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(['bundle_id','spec','roots','total_length','pieces_text'])
        for bid,s,r,tot,pieces in bundles:
            w.writerow([bid,s,r,fmt(tot), '+'.join(fmt(x) for x in sorted(pieces, reverse=True))])
    usage=[0]*46
    for *_,pieces in bundles:
        for x in pieces: usage[int(round((x-3)*2))]+=1
    print('bundles', len(bundles), dict(seq), 'usage ok', usage==counts, 'path', out, flush=True)
    print('length minmax', min(b[3] for b in bundles), max(b[3] for b in bundles), 'roots minmax', min(b[2] for b in bundles), max(b[2] for b in bundles), flush=True)
if __name__=='__main__': main()
