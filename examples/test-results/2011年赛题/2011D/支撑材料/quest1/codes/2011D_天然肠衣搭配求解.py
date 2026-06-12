import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ortools.sat.python import cp_model

ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
for d in ['quest1/codes','quest1/figures','quest1/outputs','quest2/figures','quest2/outputs','quest3/outputs','results','tables']:(ROOT/d).mkdir(parents=True,exist_ok=True)
lengths=[3+0.5*i for i in range(46)]
units=[int(round(x*2)) for x in lengths]
counts=[43,59,39,41,27,28,34,21,24,24,20,25,21,23,21,18,31,23,22,59,18,25,35,29,30,42,28,42,45,49,50,64,52,63,49,35,27,16,12,2,0,6,0,0,0,1]
SPECS={'L':{'name':'14米以上规格','min_unit':28,'std_roots':5},'M':{'name':'7-13.5米规格','min_unit':14,'std_roots':8},'S':{'name':'3-6.5米规格','min_unit':6,'std_roots':20}}

def fmt_len(x): return str(int(x)) if abs(x-int(x))<1e-9 else str(x)
def band(x): return f"{fmt_len(x)}-{fmt_len(x+0.4)}"

def solve_cp(comp=(134,44,16)):
    nL,nM,nS=comp; specs=['L']*nL+['M']*nM+['S']*nS; B=len(specs)
    model=cp_model.CpModel(); x={}
    for b,t in enumerate(specs):
        for i,u in enumerate(units):
            if u>=SPECS[t]['min_unit']:
                x[(b,i)]=model.NewIntVar(0,min(counts[i],SPECS[t]['std_roots']),f'x_{b}_{i}')
    for i,c in enumerate(counts): model.Add(sum(x.get((b,i),0) for b in range(B))==c)
    for b,t in enumerate(specs):
        std=SPECS[t]['std_roots']; roots=sum(x.get((b,i),0) for i in range(len(units))); su=sum(units[i]*x.get((b,i),0) for i in range(len(units)))
        model.Add(roots>=std-1); model.Add(roots<=std); model.Add(su>=177); model.Add(su<=179)
    # symmetry breaking: within same spec, nondecreasing total half-meter units; reduces search
    for b in range(B-1):
        if specs[b]==specs[b+1]:
            su1=sum(units[i]*x.get((b,i),0) for i in range(len(units))); su2=sum(units[i]*x.get((b+1,i),0) for i in range(len(units)))
            model.Add(su1<=su2)
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=600; solver.parameters.num_search_workers=8; solver.parameters.log_search_progress=True
    status=solver.Solve(model); print('status',solver.StatusName(status),flush=True)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE): raise RuntimeError('no feasible for comp')
    bundles=[]
    for b,t in enumerate(specs):
        pieces=[]
        for i,l in enumerate(lengths):
            var=x.get((b,i))
            if var is not None: pieces += [l]*solver.Value(var)
        bundles.append({'spec':t,'pieces':sorted(pieces,reverse=True),'roots':len(pieces),'total_length':round(sum(pieces),1)})
    return bundles,comp

def write_outputs(bundles, comp):
    seen=defaultdict(int)
    for b in bundles:
        seen[b['spec']]+=1; b['bundle_id']=f"{b['spec']}{seen[b['spec']]:03d}"; b['spec_name']=SPECS[b['spec']]['name']
    df=pd.DataFrame(bundles); df['pieces_text']=df['pieces'].apply(lambda xs:'+'.join(fmt_len(x) for x in xs)); df=df[['bundle_id','spec','spec_name','roots','total_length','pieces_text']]
    df.to_csv(ROOT/'tables/final_matching_plan.csv',index=False,encoding='utf-8-sig'); df.to_excel(ROOT/'tables/final_matching_plan.xlsx',index=False)
    usage=[]
    for l,c in zip(lengths,counts):
        row={'length':l,'band':band(l),'available':c}; used=0
        for t in SPECS:
            u=sum(b['pieces'].count(l) for b in bundles if b['spec']==t); row[f'used_{t}']=u; used+=u
        row['unused']=c-used; usage.append(row)
    udf=pd.DataFrame(usage); udf.to_csv(ROOT/'tables/material_usage_by_length.csv',index=False,encoding='utf-8-sig')
    summary=[]
    for t,s in SPECS.items():
        sub=df[df.spec==t]; summary.append({'spec':t,'spec_name':s['name'],'bundles':len(sub),'avg_roots':round(float(sub.roots.mean()) if len(sub) else 0,3),'avg_total_length':round(float(sub.total_length.mean()) if len(sub) else 0,3),'min_total_length':float(sub.total_length.min()) if len(sub) else None,'max_total_length':float(sub.total_length.max()) if len(sub) else None})
    sdf=pd.DataFrame(summary); sdf.to_csv(ROOT/'tables/summary_by_spec.csv',index=False,encoding='utf-8-sig')
    total_available=sum(l*c for l,c in zip(lengths,counts)); roots_available=sum(counts); used_length=sum(b['total_length'] for b in bundles); used_roots=sum(b['roots'] for b in bundles)
    frozen={'problem':'CUMCM2011D 天然肠衣搭配问题','bundle_counts':{'L':comp[0],'M':comp[1],'S':comp[2]},'total_bundles':len(bundles),'long_spec_bundles':comp[0],'middle_spec_bundles':comp[1],'short_spec_bundles':comp[2],'total_available_roots':roots_available,'total_available_length_m':round(total_available,1),'used_roots':used_roots,'used_length_m':round(used_length,1),'unused_roots':roots_available-used_roots,'unused_length_m':round(total_available-used_length,1),'upper_bound_by_length':int(total_available//88.5),'length_error_range_m':[round(float(df.total_length.min()-89),3),round(float(df.total_length.max()-89),3)],'root_count_range':[int(df.roots.min()),int(df.roots.max())],'all_bundles_feasible':bool(((df.total_length>=88.5)&(df.total_length<=89.5)).all() and (udf.unused==0).all()),'source_files':['tables/final_matching_plan.csv','tables/material_usage_by_length.csv','tables/summary_by_spec.csv']}
    (ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    plt.rcParams['font.sans-serif']=['SimHei','Microsoft YaHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
    fig,ax=plt.subplots(figsize=(8,5)); ax.bar(sdf.spec_name,sdf.bundles,color=['#4C78A8','#F58518','#54A24B']); ax.set_ylabel('成品捆数'); ax.set_title('各规格成品捆数');
    for i,v in enumerate(sdf.bundles): ax.text(i,v+0.5,str(int(v)),ha='center')
    plt.xticks(rotation=15); plt.tight_layout(); plt.savefig(ROOT/'quest1/figures/问题1_各规格成品捆数.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(12,5)); ax.bar(udf.length,udf.available,width=.38,label='原料根数',alpha=.65); ax.bar(udf.length,udf.available-udf.unused,width=.25,label='已使用根数',alpha=.95); ax.set_xlabel('折算长度/m'); ax.set_ylabel('根数'); ax.set_title('原料使用情况'); ax.legend(); plt.tight_layout(); plt.savefig(ROOT/'quest2/figures/问题2_原料使用情况.png',dpi=300,bbox_inches='tight'); plt.close()
    fig,ax=plt.subplots(figsize=(8,5));
    for t in SPECS: ax.hist(df[df.spec==t].total_length,bins=np.arange(88.45,89.56,.1),alpha=.55,label=t)
    ax.axvline(89,color='k',ls='--',lw=1); ax.set_xlabel('每捆总长度/m'); ax.set_ylabel('捆数'); ax.set_title('成品总长度误差分布'); ax.legend(); plt.tight_layout(); plt.savefig(ROOT/'quest2/figures/问题2_总长度误差分布.png',dpi=300,bbox_inches='tight'); plt.close()
    (ROOT/'quest1/outputs/q1_final_result_analysis.md').write_text(f"# 最终结果分析\n\n最终得到 {len(bundles)} 捆，其中 14米以上规格 {comp[0]} 捆，7-13.5米规格 {comp[1]} 捆，3-6.5米规格 {comp[2]} 捆。总长度上界为 {frozen['upper_bound_by_length']} 捆，因此总捆数达到理论上界。所有原料全部使用；所有成品总长度均在 88.5--89.5 m，根数满足标准根数或少 1 根。\n",encoding='utf-8')
    (ROOT/'quest3/outputs/q3_solution_package_for_writer.md').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(frozen,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': bundles,comp=solve_cp(); write_outputs(bundles,comp)
