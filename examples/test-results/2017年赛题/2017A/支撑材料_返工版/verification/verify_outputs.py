from pathlib import Path
import json, pandas as pd
root=Path(__file__).resolve().parents[1]
assert (root/'paper'/'论文.pdf').exists()
for f in ['results/problem2.xls','results/problem3.xls','results/frozen_numbers_rework.json']:
    assert (root/f).exists(), f
for f in ['results/problem2.xlsx','results/problem3.xlsx']:
    df=pd.read_excel(root/f,header=None); assert df.shape==(256,256), df.shape
print('VERIFY_OK')
