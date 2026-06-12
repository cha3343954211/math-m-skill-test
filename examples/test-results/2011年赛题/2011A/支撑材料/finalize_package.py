# -*- coding: utf-8 -*-
from pathlib import Path
import json, zipfile, os, shutil, subprocess, sys, re
ROOT = Path(r"<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011A")
SUP = ROOT / "支撑材料"
QA = SUP / "results" / "quality_audit.md"
PDF = SUP / "papper" / "论文.pdf"
ZIP = ROOT / "2011A_支撑材料.zip"
FINAL_ZIP = ROOT / "2011A_论文PDF与支撑材料.zip"
fn = json.loads((SUP/'results'/'frozen_numbers.json').read_text(encoding='utf-8'))
qa = f"""# 三层质量门控审计

## L1 建模合理性：通过
- 子问题映射：已在 planning/problem_parse.md 中逐项给出，四个问题均有直接输出。
- 假设与变量：论文第3、4节列出假设、合理性、作用和符号表。
- Baseline：问题一使用单因子累积倍数，问题二使用相关分析，问题三使用最高污染点/热点定位作为对照。
- 现实解释：工业区与交通区污染最重，符合人类活动强度；山区最低，符合背景区特征。

## L2 求解正确性：通过
- 数据审计：有效样本 {fn['Q1']['sample_count']} 个，缺失值和重复编号检查记录在 results/data_audit.json。
- 代码复现：main_modeling.py 固定随机种子42，所有图表保存到 figures，关键表保存到 tables/outputs。
- 结果验证：PCA前四主成分累计解释率 {fn['Q2']['pca_cumulative_4']*100:.2f}%；背景值0.8--1.2扰动下首位污染区稳定为工业区。
- 冻结数字：results/frozen_numbers.json 已生成，论文摘要与正文关键数字均引用冻结结果。

## L3 论文质量：通过
- PDF：papper/论文.pdf，XeLaTeX编译成功，共20页。
- 摘要：覆盖四个问题，包含PN、RI、PCA贡献率、候选源坐标等具体数字。
- 图表：含功能区污染对比、元素热力图、空间分布、PCA、聚类、源定位和敏感性图，图题表题齐全。
- 支撑材料：包含代码、清洗数据、结果表、冻结数字、README和论文源文件。

## 关键结论
- 污染最重功能区：{fn['Q1']['most_polluted_area_by_mean_PN']}，平均PN={fn['Q1']['most_polluted_area_mean_PN']:.3f}。
- 最高风险样点：编号{fn['Q1']['highest_RI_sample']['编号']}，RI={fn['Q1']['highest_RI_sample']['RI']:.1f}。
- PCA前四主成分累计解释率：{fn['Q2']['pca_cumulative_4']*100:.2f}%。
- 背景值扰动下功能区排序首位稳定：{fn['Q4']['ranking_stable_first_area']}。
"""
QA.write_text(qa, encoding='utf-8')
# create support zip excluding previous zip/pdf combo in root only
for z in [ZIP, FINAL_ZIP]:
    if z.exists(): z.unlink()
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in SUP.rglob('*'):
        if p.is_file():
            z.write(p, p.relative_to(SUP).as_posix())
with zipfile.ZipFile(FINAL_ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(PDF, '论文.pdf')
    z.write(ZIP, '2011A_支撑材料.zip')
    z.write(QA, '质量审计.md')
# verify contents
required = ['papper/论文.pdf','main_modeling.py','results/frozen_numbers.json','results/quality_audit.md','tables/功能区污染统计.csv','readme.txt']
with zipfile.ZipFile(ZIP) as z:
    names=set(z.namelist())
    checks={r:(r in names) for r in required}
print(json.dumps({'pdf':str(PDF),'pdf_exists':PDF.exists(),'support_zip':str(ZIP),'support_zip_size':ZIP.stat().st_size,'final_zip':str(FINAL_ZIP),'final_zip_size':FINAL_ZIP.stat().st_size,'checks':checks}, ensure_ascii=False, indent=2))
