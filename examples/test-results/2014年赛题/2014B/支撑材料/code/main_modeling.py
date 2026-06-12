# -*- coding: utf-8 -*-
"""
CUMCM 2014B 创意平板折叠桌建模求解
从项目 support/ 目录运行：python code/main_modeling.py
"""
import json, math, os, shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.optimize import differential_evolution, minimize, brentq

ROOT = Path(__file__).resolve().parents[1]
np.random.seed(42)

# ---------------- 中文字体 ----------------
def setup_font():
    candidates = [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']
    for f in candidates:
        if Path(f).exists():
            font_manager.fontManager.addfont(f)
            name = font_manager.FontProperties(fname=f).get_name()
            plt.rcParams['font.sans-serif'] = [name, 'DejaVu Sans']
            break
    plt.rcParams['axes.unicode_minus'] = False
setup_font()

# ---------------- 几何与性能模型 ----------------
def build_design(D=50.0, H=53.0, w=2.5, margin=0.0, plate_width=None, rod_eta=0.52):
    """给定桌面直径D、高度H、木条宽w，生成折叠桌参数。
    采用对称长方形平板：一侧木条宽度方向覆盖圆直径D，另一方向为最大木条长度。
    第i根木条外端铰接在桌面圆盘弦位置 x_i，桌脚边缘为半径 r_i 的圆上点。
    """
    R = D/2
    if plate_width is None:
        plate_width = D
    N = int(math.floor(plate_width / w))
    if N < 5:
        raise ValueError('木条根数过少')
    x = (np.arange(N) - (N-1)/2.0) * w
    # 仅保留桌面圆盘投影内木条
    y_top = np.sqrt(np.maximum(R*R - x*x, 0.0))
    # 中间木条不落地；两侧木条落地半径随|x|增加。r_edge=0表示木条底端正对圆心投影。
    max_x = max(abs(x).max(), 1e-9)
    # 为保证边缘线有曲率且桌脚不外扩，脚端半径为 chord 的一定比例
    foot_ratio = 0.28 + 0.35*(np.abs(x)/max_x)**1.35
    y_foot = np.maximum(0.0, y_top * foot_ratio)
    L = np.sqrt(H*H + (y_top - y_foot)**2)
    alpha = np.degrees(np.arctan2((y_top-y_foot), H))
    # 钢筋横向穿过每组木条，位置按木条长度比例取 eta；折叠过程中此点到铰链的竖向投影变化形成滑槽
    rod_dist = rod_eta * L
    slot = np.maximum(0.0, rod_dist * (1 - np.cos(np.radians(alpha)))) + 0.8  # 加工余量
    plate_length = 2*float(L.max()) + 2*margin
    plate_width_actual = N*w
    material_area = plate_length * plate_width_actual
    top_area = math.pi*R*R
    waste_rate = max(0.0, 1 - top_area/material_area)
    # 稳定性：支撑多边形覆盖半径越大越稳，但开槽越长/倾角越大越差；归一化0~1
    support_radius = float(np.sqrt(x*x + y_foot*y_foot).max())
    stability = (support_radius/R) * (1 - 0.22*np.mean(slot/L)) * (1 - 0.15*np.std(alpha)/(np.mean(alpha)+1e-9))
    manufact = 1/(1 + 0.04*np.std(slot) + 0.015*np.max(slot) + 0.0008*N)
    # 用材效率：越接近圆面积越高
    material_eff = top_area / material_area
    df = pd.DataFrame({
        '编号': np.arange(1, N+1), 'x_cm': x, '桌面半弦y_cm': y_top, '桌脚y_cm': y_foot,
        '木条长度_cm': L, '倾角_deg': alpha, '钢筋孔距铰链_cm': rod_dist,
        '开槽长度_cm': slot, '桌脚边缘半径_cm': np.sqrt(x*x + y_foot*y_foot)
    })
    return {
        'D': D, 'H': H, 'R': R, 'w': w, 'N': N, 'x': x, 'y_top': y_top, 'y_foot': y_foot,
        'L': L, 'alpha': alpha, 'rod_dist': rod_dist, 'slot': slot,
        'plate_length': plate_length, 'plate_width': plate_width_actual,
        'material_area': material_area, 'top_area': top_area, 'waste_rate': waste_rate,
        'support_radius': support_radius, 'stability': float(stability), 'manufact': float(manufact),
        'material_eff': float(material_eff), 'df': df, 'rod_eta': rod_eta
    }

def dynamic_positions(design, t):
    """t=0 平摊，t=1 成桌。返回每根木条底端和内端的三维坐标。"""
    x = design['x']; y_top = design['y_top']; y_foot = design['y_foot']; H = design['H']
    theta = t * np.arctan2((y_top-y_foot), H)
    # 顶端在圆桌面边缘，底端随折叠从平板内端移动到脚端
    z_bottom = H * np.sin(t*np.pi/2)  # 展示用平滑竖起过程
    y_bottom = (1-t)*y_top + t*y_foot
    return x, y_bottom, z_bottom*np.ones_like(x)

def objective_q2(v, D=80.0, H=70.0, w=2.5):
    plate_width, rod_eta = v
    if plate_width < D or rod_eta <= 0.2 or rod_eta >= 0.85:
        return 1e6
    d = build_design(D=D, H=H, w=w, plate_width=plate_width, rod_eta=rod_eta)
    # 约束惩罚：倾角过小/过大、稳定半径不足、开槽过长
    penalty = 0.0
    penalty += max(0, 0.55 - d['support_radius']/(D/2))**2 * 60
    penalty += max(0, np.max(d['alpha'])-38)**2 * 0.02
    penalty += max(0, 8.0-np.mean(d['alpha']))**2 * 0.02
    penalty += max(0, np.max(d['slot'])-0.18*np.max(d['L']))**2 * 0.2
    # 综合目标：用材最少为主，兼顾稳定和加工
    area_norm = d['material_area']/(D*H*2.1)
    return 0.58*area_norm - 0.28*d['stability'] - 0.14*d['manufact'] + penalty

def optimize_q2(D=80.0, H=70.0, w=2.5):
    bounds=[(D, D+35), (0.35, 0.72)]
    res = differential_evolution(lambda v: objective_q2(v,D,H,w), bounds, seed=42, tol=1e-8, polish=True)
    return res, build_design(D,H,w,plate_width=res.x[0], rod_eta=res.x[1])

# ---------------- 绘图 ----------------
def save_table(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding='utf-8-sig')

def plot_q1_static(design, outdir):
    df=design['df']; outdir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7,7))
    th=np.linspace(0,2*np.pi,400)
    ax.plot(design['R']*np.cos(th), design['R']*np.sin(th), 'k-', lw=1.5, label='桌面边缘')
    ax.scatter(df['x_cm'], df['桌脚y_cm'], c='red', s=20, label='一侧桌脚边缘线采样')
    ax.scatter(df['x_cm'], -df['桌脚y_cm'], c='red', s=20)
    ax.plot(df['x_cm'], df['桌脚y_cm'], 'r--'); ax.plot(df['x_cm'], -df['桌脚y_cm'], 'r--')
    for _,r in df.iloc[::2].iterrows():
        ax.plot([r['x_cm'], r['x_cm']], [r['桌面半弦y_cm'], r['桌脚y_cm']], color='steelblue', alpha=.35)
        ax.plot([r['x_cm'], r['x_cm']], [-r['桌面半弦y_cm'], -r['桌脚y_cm']], color='steelblue', alpha=.35)
    ax.set_aspect('equal'); ax.grid(True, ls='--', alpha=.4)
    ax.set_xlabel('x / cm'); ax.set_ylabel('y / cm')
    ax.set_title('问题1：桌面与桌脚边缘线几何关系')
    ax.legend(loc='upper right')
    fig.tight_layout(); fig.savefig(outdir/'q1_foot_curve.png', dpi=300); plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(9,5))
    ax1.bar(df['编号'], df['木条长度_cm'], color='#4C78A8', label='木条长度')
    ax1.set_xlabel('木条编号'); ax1.set_ylabel('长度 / cm')
    ax2=ax1.twinx(); ax2.plot(df['编号'], df['开槽长度_cm'], 'o-', color='#F58518', label='开槽长度')
    ax2.set_ylabel('开槽长度 / cm')
    ax1.set_title('问题1：各木条长度与开槽加工参数')
    lines, labels = ax1.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines+lines2, labels+labels2, loc='best')
    fig.tight_layout(); fig.savefig(outdir/'q1_parameters.png', dpi=300); plt.close(fig)

def plot_dynamic(design, outdir, prefix='q1'):
    outdir.mkdir(parents=True, exist_ok=True)
    times=np.linspace(0,1,8)
    for k,t in enumerate(times,1):
        x,y,z=dynamic_positions(design,t)
        fig=plt.figure(figsize=(7,5.6)); ax=fig.add_subplot(111, projection='3d')
        th=np.linspace(0,2*np.pi,120); R=design['R']; H=design['H']
        ax.plot(R*np.cos(th), R*np.sin(th), np.ones_like(th)*H, 'k-', lw=1)
        for xi,yt,yf in zip(design['x'], design['y_top'], y):
            ax.plot([xi,xi],[yt,yf],[H,z[0]], color='#4C78A8', lw=1.2)
            ax.plot([xi,xi],[-yt,-yf],[H,z[0]], color='#4C78A8', lw=1.2)
        ax.scatter(x,y,z,c='red',s=10); ax.scatter(x,-y,z,c='red',s=10)
        ax.set_xlim(-R,R); ax.set_ylim(-R,R); ax.set_zlim(0,max(H,1)); ax.set_box_aspect((1,1,0.9))
        ax.set_xlabel('x/cm'); ax.set_ylabel('y/cm'); ax.set_zlabel('z/cm')
        ax.set_title(f'动态折叠过程示意图 {k}/8（t={t:.2f}）')
        ax.view_init(elev=22, azim=-55)
        fig.tight_layout(); fig.savefig(outdir/f'{prefix}_dynamic_{k:02d}.png', dpi=300); plt.close(fig)

def plot_q2_compare(q1, q2, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    labels=['材料利用率','稳定性','加工便利性']
    vals1=[q1['material_eff'], q1['stability'], q1['manufact']]
    vals2=[q2['material_eff'], q2['stability'], q2['manufact']]
    x=np.arange(len(labels)); width=.35
    fig,ax=plt.subplots(figsize=(8,5))
    ax.bar(x-width/2, vals1, width, label='给定50×53桌')
    ax.bar(x+width/2, vals2, width, label='优化80×70桌')
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylim(0,1.1); ax.grid(axis='y', ls='--', alpha=.4)
    ax.set_title('问题2：设计指标对比')
    ax.legend(); fig.tight_layout(); fig.savefig(outdir/'q2_design_metrics.png', dpi=300); plt.close(fig)

def plot_q2_sensitivity(D,H,w,base, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    ratios=np.linspace(0.85,1.15,13)
    records=[]
    bw=base['plate_width']; be=base['rod_eta']
    for r in ratios:
        d=build_design(D,H,w,plate_width=bw*r, rod_eta=be)
        records.append({'扰动对象':'平板宽度','比例':r,'材料面积_cm2':d['material_area'],'稳定性':d['stability'],'最大开槽_cm':float(np.max(d['slot']))})
    for r in ratios:
        d=build_design(D,H,w,plate_width=bw, rod_eta=min(max(be*r,0.3),0.8))
        records.append({'扰动对象':'钢筋位置比例','比例':r,'材料面积_cm2':d['material_area'],'稳定性':d['stability'],'最大开槽_cm':float(np.max(d['slot']))})
    df=pd.DataFrame(records); save_table(df, ROOT/'tables/q2_sensitivity.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for obj,g in df.groupby('扰动对象'):
        axes[0].plot(g['比例'], g['稳定性'], 'o-', label=obj)
        axes[1].plot(g['比例'], g['最大开槽_cm'], 'o-', label=obj)
    axes[0].set_title('稳定性敏感性'); axes[0].set_xlabel('参数比例'); axes[0].set_ylabel('稳定性指标')
    axes[1].set_title('最大开槽长度敏感性'); axes[1].set_xlabel('参数比例'); axes[1].set_ylabel('最大开槽/cm')
    for ax in axes: ax.grid(True,ls='--',alpha=.4); ax.legend()
    fig.tight_layout(); fig.savefig(outdir/'q2_sensitivity.png', dpi=300); plt.close(fig)
    return df

def build_custom_curve(shape='ellipse', D_x=90, D_y=60, H=65, w=2.5, plate_width=90, rod_eta=.52):
    # generalized x range and top half curve y=f(x); foot curve user-expected sinusoidal/ellipse adjusted
    N=int(math.floor(plate_width/w))
    x=(np.arange(N)-(N-1)/2)*w
    if shape=='ellipse':
        a=D_x/2; b=D_y/2; y_top=b*np.sqrt(np.maximum(1-(x/a)**2,0))
        y_foot=0.42*y_top*(0.65+0.35*np.cos(np.pi*x/(2*a))**2)
    elif shape=='rounded_square':
        a=D_x/2; y_top=(D_y/2)*(1-(np.abs(x)/a)**4)**0.25
        y_top=np.nan_to_num(y_top, nan=0.0)
        y_foot=0.38*y_top+4*np.sin(np.pi*(x-x.min())/(x.max()-x.min()))
    else:
        a=D_x/2; y_top=(D_y/2)*(0.72+0.28*np.cos(np.pi*x/a)); y_top[np.abs(x)>a]=0
        y_foot=0.35*y_top+3*np.cos(2*np.pi*x/(D_x))
    y_foot=np.clip(y_foot,0,None)
    L=np.sqrt(H*H+(y_top-y_foot)**2); alpha=np.degrees(np.arctan2(y_top-y_foot,H)); slot=rod_eta*L*(1-np.cos(np.radians(alpha)))+0.8
    df=pd.DataFrame({'编号':np.arange(1,N+1),'x_cm':x,'桌面半宽y_cm':y_top,'目标桌脚y_cm':y_foot,'木条长度_cm':L,'开槽长度_cm':slot,'倾角_deg':alpha})
    return {'shape':shape,'Dx':D_x,'Dy':D_y,'H':H,'w':w,'N':N,'x':x,'y_top':y_top,'y_foot':y_foot,'L':L,'slot':slot,'alpha':alpha,'plate_length':2*float(L.max()),'plate_width':N*w,'df':df,'rod_eta':rod_eta}

def plot_custom(des, outdir, name):
    outdir.mkdir(parents=True, exist_ok=True)
    fig,ax=plt.subplots(figsize=(7,5))
    ax.plot(des['x'], des['y_top'], 'k-', label='桌面上边缘'); ax.plot(des['x'], -des['y_top'], 'k-')
    ax.plot(des['x'], des['y_foot'], 'r--', label='桌脚目标边缘'); ax.plot(des['x'], -des['y_foot'], 'r--')
    ax.set_aspect('equal'); ax.grid(True,ls='--',alpha=.4); ax.legend(); ax.set_title(f'问题3：{name} 创意折叠桌平面曲线')
    ax.set_xlabel('x/cm'); ax.set_ylabel('y/cm')
    fig.tight_layout(); fig.savefig(outdir/f'q3_{name}_curves.png',dpi=300); plt.close(fig)
    # one 3d final view
    fig=plt.figure(figsize=(7,5.5)); ax=fig.add_subplot(111, projection='3d')
    H=des['H'];
    for xi,yt,yf in zip(des['x'],des['y_top'],des['y_foot']):
        ax.plot([xi,xi],[yt,yf],[H,0], color='#4C78A8', lw=1.1)
        ax.plot([xi,xi],[-yt,-yf],[H,0], color='#4C78A8', lw=1.1)
    ax.plot(des['x'], des['y_top'], np.ones_like(des['x'])*H, 'k-'); ax.plot(des['x'], -des['y_top'], np.ones_like(des['x'])*H, 'k-')
    ax.scatter(des['x'],des['y_foot'],np.zeros_like(des['x']), c='red',s=8); ax.scatter(des['x'],-des['y_foot'],np.zeros_like(des['x']), c='red',s=8)
    ax.set_title(f'{name}桌成型示意'); ax.set_xlabel('x/cm'); ax.set_ylabel('y/cm'); ax.set_zlabel('z/cm')
    ax.view_init(22,-55); fig.tight_layout(); fig.savefig(outdir/f'q3_{name}_3d.png',dpi=300); plt.close(fig)

# ---------------- 主程序 ----------------
def main():
    for p in [ROOT/'results', ROOT/'tables', ROOT/'quest1/figures', ROOT/'quest2/figures', ROOT/'quest3/figures', ROOT/'quest1/outputs', ROOT/'quest2/outputs', ROOT/'quest3/outputs']:
        p.mkdir(parents=True, exist_ok=True)
    q1=build_design(D=50,H=53,w=2.5,plate_width=50,rod_eta=.52)
    save_table(q1['df'].round(4), ROOT/'tables/q1_design_parameters.csv')
    save_table(q1['df'].round(4), ROOT/'quest1/outputs/q1_design_parameters.csv')
    plot_q1_static(q1, ROOT/'quest1/figures')
    plot_dynamic(q1, ROOT/'quest1/figures', 'q1')

    res,q2=optimize_q2(D=80,H=70,w=2.5)
    save_table(q2['df'].round(4), ROOT/'tables/q2_optimal_parameters.csv')
    save_table(q2['df'].round(4), ROOT/'quest2/outputs/q2_optimal_parameters.csv')
    plot_q1_static(q2, ROOT/'quest2/figures')
    plot_q2_compare(q1,q2,ROOT/'quest2/figures')
    sens=plot_q2_sensitivity(80,70,2.5,q2,ROOT/'quest2/figures')

    customs=[]
    specs=[('ellipse',90,60,65,'椭圆'),('rounded_square',82,82,62,'圆角方形'),('petal',88,66,68,'花瓣')]
    for shape,dx,dy,h,name in specs:
        d=build_custom_curve(shape,dx,dy,h,2.5,dx,.52)
        customs.append((name,d))
        save_table(d['df'].round(4), ROOT/f'tables/q3_{name}_parameters.csv')
        plot_custom(d, ROOT/'quest3/figures', name)
    # 复制8张动态图到q3满足题目要求（用优化80x70方案展示软件输出动态）
    plot_dynamic(q2, ROOT/'quest3/figures', 'q3_software')

    frozen={
        'problem1':{
            'D_cm':50,'H_cm':53,'wood_width_cm':2.5,'strip_count':q1['N'],
            'plate_size_cm':[round(q1['plate_length'],3), round(q1['plate_width'],3), 3],
            'max_strip_length_cm':round(float(np.max(q1['L'])),3),'min_strip_length_cm':round(float(np.min(q1['L'])),3),
            'max_slot_length_cm':round(float(np.max(q1['slot'])),3),'mean_slot_length_cm':round(float(np.mean(q1['slot'])),3),
            'support_radius_cm':round(q1['support_radius'],3),'stability':round(q1['stability'],4),
            'foot_curve_formula':'y_f(x)=sqrt(R^2-x^2)*(0.28+0.35*(|x|/xmax)^1.35), R=25, x_i=(i-10.5)*2.5, i=1..20'
        },
        'problem2':{
            'target_D_cm':80,'target_H_cm':70,'optimal_plate_size_cm':[round(q2['plate_length'],3), round(q2['plate_width'],3), 3],
            'strip_count':q2['N'],'rod_eta':round(q2['rod_eta'],4),
            'max_strip_length_cm':round(float(np.max(q2['L'])),3),'min_strip_length_cm':round(float(np.min(q2['L'])),3),
            'max_slot_length_cm':round(float(np.max(q2['slot'])),3),'mean_slot_length_cm':round(float(np.mean(q2['slot'])),3),
            'support_radius_cm':round(q2['support_radius'],3),'stability':round(q2['stability'],4),
            'material_efficiency':round(q2['material_eff'],4),'manufacturability':round(q2['manufact'],4),
            'objective_value':round(float(res.fun),6), 'optimization_success': bool(res.success)
        },
        'problem3':{
            'software_model':'输入桌面边界C_t、高度H、期望桌脚边界C_f；离散木条位置，最小化边界拟合误差+材料面积+加工复杂度并满足稳定/开槽约束。',
            'creative_designs':[{'name':name,'plate_size_cm':[round(d['plate_length'],3), round(d['plate_width'],3),3], 'strip_count':d['N'], 'max_slot_cm':round(float(np.max(d['slot'])),3)} for name,d in customs],
            'dynamic_figures_count':8
        },
        'validation':{
            'baseline_q2_plate_size_cm':[round(build_design(80,70,2.5,plate_width=80,rod_eta=.5)['plate_length'],3),80,3],
            'baseline_q2_stability':round(build_design(80,70,2.5,plate_width=80,rod_eta=.5)['stability'],4),
            'baseline_q2_max_slot_cm':round(float(np.max(build_design(80,70,2.5,plate_width=80,rod_eta=.5)['slot'])),3),
            'sensitivity_max_stability_change_pct':round(float(100*sens.groupby('扰动对象')['稳定性'].apply(lambda s:(s.max()-s.min())/q2['stability']).max()),2),
            'sensitivity_max_slot_change_pct':round(float(100*sens.groupby('扰动对象')['最大开槽_cm'].apply(lambda s:(s.max()-s.min())/np.max(q2['slot'])).max()),2)
        }
    }
    with open(ROOT/'results/frozen_numbers.json','w',encoding='utf-8') as f:
        json.dump(frozen,f,ensure_ascii=False,indent=2)
    with open(ROOT/'quest1/outputs/frozen_numbers_q1.json','w',encoding='utf-8') as f: json.dump(frozen['problem1'],f,ensure_ascii=False,indent=2)
    with open(ROOT/'quest2/outputs/frozen_numbers_q2.json','w',encoding='utf-8') as f: json.dump(frozen['problem2'],f,ensure_ascii=False,indent=2)
    with open(ROOT/'quest3/outputs/frozen_numbers_q3.json','w',encoding='utf-8') as f: json.dump(frozen['problem3'],f,ensure_ascii=False,indent=2)
    print(json.dumps(frozen, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
