from pathlib import Path
import pandas as pd, json
ROOT=Path('<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011D/支撑材料')
SPECS={'L':(14.0,4,5),'M':(7.0,7,8),'S':(3.0,19,20)}
def parse_pieces(s): return [float(x) for x in str(s).split('+') if x]
df=pd.read_csv(ROOT/'tables/final_matching_plan.csv')
udf=pd.read_csv(ROOT/'tables/material_usage_by_length.csv')
errors=[]
for _,r in df.iterrows():
    pieces=parse_pieces(r['pieces_text']); spec=r['spec']; min_len,min_roots,max_roots=SPECS[spec]
    if len(pieces)!=int(r['roots']): errors.append((r.bundle_id,'roots_mismatch'))
    if abs(sum(pieces)-float(r['total_length']))>1e-6: errors.append((r.bundle_id,'length_mismatch'))
    if not (88.5<=sum(pieces)<=89.5): errors.append((r.bundle_id,'length_range',sum(pieces)))
    if not (min_roots<=len(pieces)<=max_roots): errors.append((r.bundle_id,'root_range',len(pieces)))
    if any(x<min_len-1e-9 for x in pieces): errors.append((r.bundle_id,'spec_min_piece',min(pieces)))
if (udf['unused']<0).any(): errors.append(('usage','negative_unused'))
summary={
 'rows':len(df),
 'by_spec':df.groupby('spec').size().to_dict(),
 'total_used_roots':int(df['roots'].sum()),
 'total_used_length':float(df['total_length'].sum()),
 'min_bundle_length':float(df['total_length'].min()),
 'max_bundle_length':float(df['total_length'].max()),
 'min_roots':int(df['roots'].min()),
 'max_roots':int(df['roots'].max()),
 'unused_roots':int(udf['unused'].sum()),
 'unused_length':float((udf['length']*udf['unused']).sum()),
 'errors':errors[:20],
 'passed':len(errors)==0
}
(ROOT/'results/validation_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
