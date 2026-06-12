import json
import math
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / '附件1.xls'
OUT_RESULTS = ROOT / 'results'
TABLES = ROOT / 'tables'
PAPER = ROOT / 'papper'
QUEST_DIRS = {i: ROOT / f'quest{i}' for i in [1,2,3]}
for p in [OUT_RESULTS, TABLES, PAPER] + [d/'outputs' for d in QUEST_DIRS.values()] + [d/'figures' for d in QUEST_DIRS.values()]:
    p.mkdir(parents=True, exist_ok=True)

# Chinese font setup
for fp in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False

YEARS = [1986, 1996, 2009, 2011]
BLOCKS = {1986:0, 1996:6, 2009:12, 2011:18}


def load_raw():
    df = pd.read_excel(DATA, header=None)
    recs = []
    for year, c in BLOCKS.items():
        block = df.iloc[3:, c:c+5].copy()
        block.columns = ['layer', 'point', 'x', 'y', 'z']
        block['layer'] = block['layer'].ffill()
        for col in ['point','x','y','z']:
            block[col] = pd.to_numeric(block[col], errors='coerce')
        block = block.dropna(subset=['x','y','z']).copy()
        block['year'] = year
        recs.append(block[['year','layer','point','x','y','z']])
    raw = pd.concat(recs, ignore_index=True)
    raw['layer_label'] = raw['layer'].astype(str)
    return raw


def fit_circle(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    # Algebraic LS: x^2+y^2 + D x + E y + F = 0
    A = np.column_stack([x, y, np.ones_like(x)])
    b = -(x*x + y*y)
    D, E, F = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = -D/2, -E/2
    r2 = cx*cx + cy*cy - F
    r = math.sqrt(max(r2, 0))
    residual = np.sqrt((x-cx)**2 + (y-cy)**2) - r
    return cx, cy, r, residual


def compute_centers(raw):
    rows = []
    for (year, layer), g in raw.groupby(['year','layer'], sort=False):
        if str(layer) == '塔尖':
            cx, cy, z = g['x'].mean(), g['y'].mean(), g['z'].mean()
            r, rms, maxabs, n = 0.0, 0.0, 0.0, len(g)
        else:
            cx, cy, r, res = fit_circle(g['x'], g['y'])
            z = g['z'].mean()
            rms = float(np.sqrt(np.mean(res**2)))
            maxabs = float(np.max(np.abs(res)))
            n = len(g)
        rows.append(dict(year=year, layer=str(layer), layer_num=14 if str(layer)=='塔尖' else int(layer),
                         cx=cx, cy=cy, z=z, radius=r, n_points=n, circle_rms=rms, circle_max_abs=maxabs))
    centers = pd.DataFrame(rows).sort_values(['year','layer_num'])
    # Reference base center per year: layer 1, so inter-year datum translations do not pollute deformation.
    base = centers[centers.layer_num==1][['year','cx','cy','z']].rename(columns={'cx':'base_x','cy':'base_y','z':'base_z'})
    centers = centers.merge(base, on='year', how='left')
    centers['dx'] = centers['cx'] - centers['base_x']
    centers['dy'] = centers['cy'] - centers['base_y']
    centers['dz'] = centers['z'] - centers['base_z']
    centers['offset'] = np.sqrt(centers.dx**2 + centers.dy**2)
    centers['azimuth_deg'] = (np.degrees(np.arctan2(centers.dy, centers.dx)) + 360) % 360
    centers['inclination_ratio'] = centers['offset'] / centers['dz'].replace(0, np.nan)
    centers['inclination_deg'] = np.degrees(np.arctan(centers['inclination_ratio']))
    return centers


def line_fit_deformation(centers):
    rows=[]
    for year, g0 in centers[centers.layer_num<=13].groupby('year'):
        g=g0.sort_values('z')
        z = g['dz'].values
        X = np.column_stack([np.ones(len(z)), z])
        ax,bx = np.linalg.lstsq(X, g['dx'].values, rcond=None)[0]
        ay,by = np.linalg.lstsq(X, g['dy'].values, rcond=None)[0]
        predx = ax + bx*z; predy = ay + by*z
        bend = np.sqrt((g['dx'].values-predx)**2 + (g['dy'].values-predy)**2)
        for i, (_, row) in enumerate(g.iterrows()):
            rows.append(dict(year=year, layer=row.layer, layer_num=row.layer_num,
                             straight_x=predx[i], straight_y=predy[i], bending=bend[i]))
    bend_df=pd.DataFrame(rows)
    summary=[]
    for year, g in bend_df.groupby('year'):
        top = centers[(centers.year==year)&(centers.layer_num==13)].iloc[0]
        summary.append(dict(year=year,
            top_offset=float(top.offset), top_dx=float(top.dx), top_dy=float(top.dy),
            top_azimuth_deg=float(top.azimuth_deg), top_inclination_deg=float(top.inclination_deg),
            top_inclination_ratio=float(top.inclination_ratio),
            max_bending=float(g.bending.max()), max_bending_layer=str(g.loc[g.bending.idxmax(),'layer']),
            mean_bending=float(g.bending.mean()),
            axis_slope_x=float(np.linalg.lstsq(np.column_stack([np.ones(len(centers[(centers.year==year)&(centers.layer_num<=13)])), centers[(centers.year==year)&(centers.layer_num<=13)].dz.values]), centers[(centers.year==year)&(centers.layer_num<=13)].dx.values, rcond=None)[0][1]),
            axis_slope_y=float(np.linalg.lstsq(np.column_stack([np.ones(len(centers[(centers.year==year)&(centers.layer_num<=13)])), centers[(centers.year==year)&(centers.layer_num<=13)].dz.values]), centers[(centers.year==year)&(centers.layer_num<=13)].dy.values, rcond=None)[0][1])
        ))
    return bend_df, pd.DataFrame(summary)


def compute_twist(raw, centers):
    # twist: mean unwrapped polar angle of labeled wall points after subtracting each layer center.
    rows=[]
    center_map = centers.set_index(['year','layer'])[['cx','cy']].to_dict('index')
    for (year, layer), g0 in raw[raw.layer_label!='塔尖'].groupby(['year','layer_label']):
        g=g0.dropna(subset=['point']).sort_values('point')
        if len(g)<4: continue
        c=center_map[(year, layer)]
        angles = np.degrees(np.arctan2(g['y'].values-c['cy'], g['x'].values-c['cx']))
        # adjust each point angle relative to 1986 layer1 physical label convention? Store mean orientation only.
        # Circular mean of residual angle relative to ideal 45-degree spacing identifies layer rotation.
        ideal = angles[0] + (g['point'].values-g['point'].values[0])*45.0
        residual = (angles - ideal + 180) % 360 - 180
        orientation = (angles[0] - (g['point'].values[0]-1)*45.0 + 360) % 360
        rows.append(dict(year=year, layer=layer, layer_num=int(float(layer)), orientation_deg=orientation,
                         angle_residual_rms=float(np.sqrt(np.mean(residual**2)))))
    tw=pd.DataFrame(rows).sort_values(['year','layer_num'])
    base=tw[tw.layer_num==1][['year','orientation_deg']].rename(columns={'orientation_deg':'base_orientation'})
    tw=tw.merge(base,on='year',how='left')
    tw['twist_deg'] = ((tw['orientation_deg']-tw['base_orientation']+180)%360)-180
    return tw


def trend_analysis(centers, summary):
    rows=[]
    t=np.array(YEARS,dtype=float)
    for layer in range(1,14):
        g=centers[centers.layer_num==layer].sort_values('year')
        if len(g)!=4: continue
        tt=t-t[0]
        for var in ['dx','dy','offset']:
            y=g[var].values
            coef=np.polyfit(tt,y,1)
            pred=np.polyval(coef,tt)
            ss_res=np.sum((y-pred)**2); ss_tot=np.sum((y-y.mean())**2)
            r2=1-ss_res/ss_tot if ss_tot>1e-12 else np.nan
            rows.append(dict(layer=layer, variable=var, slope_per_year=float(coef[0]), intercept_1986=float(coef[1]), r2=float(r2), pred_2021=float(np.polyval(coef,2021-1986)), pred_2030=float(np.polyval(coef,2030-1986))))
    trend=pd.DataFrame(rows)
    # top-layer vector prediction using dx/dy slopes.
    top=trend[(trend.layer==13)&(trend.variable.isin(['dx','dy']))]
    pred={}
    for year in [2021,2030]:
        px=float(top[top.variable=='dx'][f'pred_{year}'].iloc[0]); py=float(top[top.variable=='dy'][f'pred_{year}'].iloc[0])
        pred[f'top_offset_{year}']=math.hypot(px,py)
        pred[f'top_azimuth_{year}']=(math.degrees(math.atan2(py,px))+360)%360
    return trend, pred


def make_figures(centers, bend_df, twist, trend):
    # centerline by year
    fig, ax = plt.subplots(figsize=(7,7))
    for year, g in centers[centers.layer_num<=13].groupby('year'):
        ax.plot(g.dx, g.dy, marker='o', label=str(year))
        for _, r in g.iterrows():
            if r.layer_num in [1,5,9,13]: ax.text(r.dx, r.dy, str(int(r.layer_num)), fontsize=8)
    ax.axhline(0,color='gray',lw=.8); ax.axvline(0,color='gray',lw=.8)
    ax.set_xlabel('相对底层中心x位移 / m'); ax.set_ylabel('相对底层中心y位移 / m')
    ax.set_title('各年塔身中心线水平投影')
    ax.legend(); ax.axis('equal'); ax.grid(alpha=.3)
    plt.savefig(QUEST_DIRS[2]/'figures'/'问题2_中心线水平投影.png', dpi=300, bbox_inches='tight'); plt.close()

    fig, ax = plt.subplots(figsize=(7,6))
    for year, g in centers[centers.layer_num<=13].groupby('year'):
        ax.plot(g.offset, g.z, marker='o', label=str(year))
    ax.set_xlabel('相对底层中心偏移量 / m'); ax.set_ylabel('高程 z / m')
    ax.set_title('各层中心偏移量随高度变化')
    ax.legend(); ax.grid(alpha=.3)
    plt.savefig(QUEST_DIRS[2]/'figures'/'问题2_偏移高度曲线.png', dpi=300, bbox_inches='tight'); plt.close()

    fig, ax = plt.subplots(figsize=(8,5))
    for year, g in bend_df.groupby('year'):
        ax.plot(g.layer_num, g.bending*1000, marker='o', label=str(year))
    ax.set_xlabel('塔层'); ax.set_ylabel('相对最佳直线轴弯曲残差 / mm')
    ax.set_title('塔身弯曲残差分布')
    ax.legend(); ax.grid(alpha=.3)
    plt.savefig(QUEST_DIRS[2]/'figures'/'问题2_弯曲残差.png', dpi=300, bbox_inches='tight'); plt.close()

    fig, ax = plt.subplots(figsize=(8,5))
    for year, g in twist.groupby('year'):
        ax.plot(g.layer_num, g.twist_deg, marker='o', label=str(year))
    ax.set_xlabel('塔层'); ax.set_ylabel('相对底层扭转角 / 度')
    ax.set_title('各层相对底层扭转角')
    ax.legend(); ax.grid(alpha=.3)
    plt.savefig(QUEST_DIRS[2]/'figures'/'问题2_扭转角.png', dpi=300, bbox_inches='tight'); plt.close()

    top=centers[centers.layer_num==13].sort_values('year')
    fig, ax = plt.subplots(figsize=(8,5))
    ax.plot(top.year, top.offset*1000, marker='o', label='实测顶层偏移')
    tr=trend[(trend.layer==13)&(trend.variable=='offset')].iloc[0]
    years=np.arange(1986,2031)
    pred=tr.intercept_1986 + tr.slope_per_year*(years-1986)
    ax.plot(years, pred*1000, '--', label='线性趋势')
    ax.set_xlabel('年份'); ax.set_ylabel('第13层偏移量 / mm')
    ax.set_title('塔顶变形趋势')
    ax.legend(); ax.grid(alpha=.3)
    plt.savefig(QUEST_DIRS[3]/'figures'/'问题3_塔顶偏移趋势.png', dpi=300, bbox_inches='tight'); plt.close()


def save_tables(raw, centers, bend_df, summary, twist, trend, pred):
    raw.to_csv(TABLES/'raw_long.csv', index=False, encoding='utf-8-sig')
    centers.to_csv(TABLES/'centers_by_year_layer.csv', index=False, encoding='utf-8-sig')
    centers[['year','layer','cx','cy','z','radius','circle_rms','dx','dy','offset','azimuth_deg','inclination_deg']].to_excel(TABLES/'各次测量各层中心坐标.xlsx', index=False)
    bend_df.to_csv(TABLES/'bending_by_year_layer.csv', index=False, encoding='utf-8-sig')
    summary.to_csv(TABLES/'deformation_summary.csv', index=False, encoding='utf-8-sig')
    twist.to_csv(TABLES/'twist_by_year_layer.csv', index=False, encoding='utf-8-sig')
    trend.to_csv(TABLES/'trend_linear_by_layer.csv', index=False, encoding='utf-8-sig')
    # frozen numbers
    freeze = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'data_audit': {
            'raw_records': int(len(raw)), 'years': YEARS,
            'layers_modeled': '1-13 layers; tower tip separately averaged when available',
            'missing_note': '1986/1996第13层5号点缺测；圆拟合使用其余7点。2009/2011塔尖未给多点，仅分析至第13层。'
        },
        'circle_fit': {
            'max_rms_m': float(centers.circle_rms.max()),
            'median_rms_m': float(centers.circle_rms.median())
        },
        'deformation_summary': summary.to_dict(orient='records'),
        'trend_prediction': pred,
        'top_layer_trend': trend[trend.layer==13].to_dict(orient='records')
    }
    (OUT_RESULTS/'frozen_numbers.json').write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding='utf-8')
    return freeze


def write_docs(raw, centers, bend_df, summary, twist, trend, freeze):
    ref = ROOT/'references'/'external_resource_notes.md'
    ref.write_text('''# 外部/知识库资料记录\n\n- IMA 检索词：`古塔的变形`、`古塔 变形`、`倾斜 弯曲 扭曲`、`圆拟合 中心 坐标`、`2013 C题`。本次知识库返回空列表，因此未直接引用同题案例。\n- 方法依据：采用测量数据自身的几何结构建立模型。中心定位使用最小二乘圆拟合；倾斜用各层中心相对底层中心的水平位移与高度比；弯曲用中心线相对最佳空间直线轴的水平残差；扭曲用同层标志点相对中心的极角变化；趋势用基于相对底层坐标的线性回归，避免不同年度坐标基准平移影响。\n- 风险控制：所有年度先转为“相对底层中心”的局部坐标，再做变形比较；缺测点不插值伪造，圆拟合直接用可用观测点。\n''', encoding='utf-8')
    readme = ROOT/'readme.txt'
    readme.write_text(f'''# 2013C 古塔的变形 支撑材料\n\n## 文件结构\n- papper/论文.tex, 论文.pdf：正式论文源文件和PDF。\n- quest1/codes/main_modeling.py：完整建模、作图、结果冻结脚本。\n- quest*/figures：各问题图表。\n- tables：中心坐标、变形指标、趋势回归等结果表。\n- results/frozen_numbers.json：论文使用的关键冻结数字。\n- data：原始题面和附件。\n\n## 运行方法\n在支撑材料目录运行：\n```bash\npython quest1/codes/main_modeling.py\ncd papper && xelatex -interaction=nonstopmode 论文.tex\n```\n\n## 数据审计\n- 原始长表记录数：{len(raw)}。\n- 年份：1986、1996、2009、2011。\n- 缺测：1986/1996第13层5号点缺测；2009/2011塔尖仅给单点或未按多点观测，正式变形趋势分析到第13层。\n- 圆拟合最大RMS：{freeze['circle_fit']['max_rms_m']:.4f} m，中位RMS：{freeze['circle_fit']['median_rms_m']:.4f} m。\n''', encoding='utf-8')


def main():
    raw = load_raw()
    centers = compute_centers(raw)
    bend_df, summary = line_fit_deformation(centers)
    twist = compute_twist(raw, centers)
    trend, pred = trend_analysis(centers, summary)
    make_figures(centers, bend_df, twist, trend)
    freeze = save_tables(raw, centers, bend_df, summary, twist, trend, pred)
    write_docs(raw, centers, bend_df, summary, twist, trend, freeze)
    print('OK')
    print('records', len(raw))
    print(summary.to_string(index=False))
    print('pred', pred)

if __name__ == '__main__':
    main()
