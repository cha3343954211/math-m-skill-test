import os, zipfile, json
from pathlib import Path
from datetime import datetime

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2011年赛题/2011B')
SUPPORT = ROOT / '支撑材料'
PDF = SUPPORT / 'papper' / '论文.pdf'
ZIP_SUPPORT = ROOT / '2011B_支撑材料.zip'
ZIP_ALL = ROOT / '2011B_论文PDF与支撑材料.zip'

assert PDF.exists(), f'PDF不存在: {PDF}'

def zip_dir(src, dst):
    if dst.exists(): dst.unlink()
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in src.rglob('*'):
            if p.is_file():
                if p.suffix.lower() in {'.aux','.log','.out','.toc'}:
                    continue
                z.write(p, p.relative_to(src).as_posix())

zip_dir(SUPPORT, ZIP_SUPPORT)
if ZIP_ALL.exists(): ZIP_ALL.unlink()
with zipfile.ZipFile(ZIP_ALL, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(PDF, '论文.pdf')
    z.write(ZIP_SUPPORT, ZIP_SUPPORT.name)

required = ['papper/论文.pdf','main_modeling.py','write_paper.py','results/frozen_numbers.json','results/quality_audit.md','tables/问题2_P32案发围堵方案.csv','readme.txt']
with zipfile.ZipFile(ZIP_SUPPORT) as z:
    names=set(z.namelist())
    check={r:(r in names) for r in required}

summary = {
    'generated_at': datetime.now().isoformat(timespec='seconds'),
    'pdf': str(PDF), 'pdf_size': PDF.stat().st_size,
    'support_zip': str(ZIP_SUPPORT), 'support_zip_size': ZIP_SUPPORT.stat().st_size,
    'all_zip': str(ZIP_ALL), 'all_zip_size': ZIP_ALL.stat().st_size,
    'required_check': check
}
(SUPPORT/'results'/'package_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
