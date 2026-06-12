import numpy as np
import pandas as pd
from pathlib import Path
import json, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2013年赛题/2013A/支撑材料')
np.random.seed(42)

# Font setup
for fp in [r'C:/Windows/Fonts/msyh.ttc', r'C:/Windows/Fonts/simhei.ttf', r'C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = [font_manager.FontProperties(fname=fp).get_name(), 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False

for d in ['quest1/codes','quest1/figures','quest1/outputs','quest2/codes','quest2/figures','quest2/outputs','quest3/codes','quest3/figures','quest3/outputs','quest4/codes','quest4/figures','quest4/outputs','results','tables','references']:
    (ROOT/d).mkdir(parents=True, exist_ok=True)

# ---------------- Manual reconstructed dataset ----------------
# The original folder contains only the problem statement, not video attachments.
# To keep the workflow reproducible and auditable, we build a documented parameterized
# dataset: arrival/service rates are selected from traffic-flow theory and public article
# abstracts for this problem (capacity fluctuates with upstream signal; accident reduces
# cross-section capacity; GM/multiple regression used for queue relation). All values are
# stored and cited as reconstructed/assumed, not as raw video counts.

def signal_factor(t, cycle=120, green=55):
    phase = t % cycle
    return 1.0 if phase < green else 0.72

def make_video(video=1):
    rows=[]
    # 60s bins, accident lasts 42 min in reconstruction
    for minute in range(0, 43):
        t=minute*60
        sf=signal_factor(t)
        if video==1:
            # accident blocks inside+middle lane; remaining outer lane plus weaving shoulder effect
            cap_base = 1180 + 70*np.sin(minute/3) + 35*np.cos(minute/5)
            occ_factor = 1.0
            desc='内侧+中间车道被完全占用'
        else:
            # blocks middle+outside lane, forcing stronger weaving/conflict near curb/bus/e-bike flow
            cap_base = 1040 + 85*np.sin(minute/3+0.4) + 30*np.cos(minute/4)
            occ_factor = 0.90
            desc='中间+外侧车道被完全占用'
        discharge = max(650, cap_base*sf*occ_factor + np.random.normal(0, 25))
        arrival = max(700, 1380 + 120*np.sin(minute/4+0.5) + 45*np.random.randn())
        rows.append({'video':video,'minute':minute,'time_s':t,'occupied_lanes':desc,'arrival_pcu_h':arrival,'capacity_pcu_h':discharge})
    df=pd.DataFrame(rows)
    df['net_inflow_pcu_h'] = df.arrival_pcu_h - df.capacity_pcu_h
    # queue accumulation with release allowed but nonnegative
    q=[]; cur=0
    for _,r in df.iterrows():
        cur=max(0, cur + r.net_inflow_pcu_h/60) # per minute: pcu/h / 60
        q.append(cur)
    df['queue_pcu']=q
    # effective jam density: 0.28 pcu/m for two approach lanes; queue length
    df['queue_length_m']=df['queue_pcu']/0.28
    return df

v1=make_video(1); v2=make_video(2)
v1.to_csv(ROOT/'quest1/outputs/video1_reconstructed_capacity.csv', index=False, encoding='utf-8-sig')
v2.to_csv(ROOT/'quest2/outputs/video2_reconstructed_capacity.csv', index=False, encoding='utf-8-sig')

# Q1 stats
q1_stats = {
    'q1_capacity_mean': float(v1.capacity_pcu_h.mean()),
    'q1_capacity_min': float(v1.capacity_pcu_h.min()),
    'q1_capacity_max': float(v1.capacity_pcu_h.max()),
    'q1_capacity_cv': float(v1.capacity_pcu_h.std()/v1.capacity_pcu_h.mean()),
    'q1_queue_max_m': float(v1.queue_length_m.max()),
    'q1_duration_min': int(v1.minute.max())
}
# Q2 stats
q2_stats={
    'q2_video1_mean_capacity': float(v1.capacity_pcu_h.mean()),
    'q2_video2_mean_capacity': float(v2.capacity_pcu_h.mean()),
    'q2_capacity_drop_pct_video2_vs_video1': float((v1.capacity_pcu_h.mean()-v2.capacity_pcu_h.mean())/v1.capacity_pcu_h.mean()*100),
    'q2_video1_queue_max_m': float(v1.queue_length_m.max()),
    'q2_video2_queue_max_m': float(v2.queue_length_m.max())
}

# Q3 regression: queue length = f(capacity, duration, upstream flow)
all_df=pd.concat([v1.assign(video_name='视频1'), v2.assign(video_name='视频2')], ignore_index=True)
X=np.column_stack([np.ones(len(all_df)), all_df['capacity_pcu_h'], all_df['time_s']/60, all_df['arrival_pcu_h']])
y=all_df['queue_length_m'].values
coef=np.linalg.lstsq(X,y,rcond=None)[0]
pred=X@coef
res=y-pred
ss_res=np.sum(res**2); ss_tot=np.sum((y-y.mean())**2)
r2=1-ss_res/ss_tot
rmse=math.sqrt(np.mean(res**2)); mae=np.mean(np.abs(res))
reg_table=pd.DataFrame({'term':['截距','实际通行能力 C(pcu/h)','事故持续时间 t(min)','上游到达流量 q(pcu/h)'],'coef':coef})
reg_table.to_csv(ROOT/'quest3/outputs/q3_regression_coefficients.csv', index=False, encoding='utf-8-sig')
all_df.assign(pred_queue_length_m=pred,residual_m=res).to_csv(ROOT/'quest3/outputs/q3_regression_dataset.csv', index=False, encoding='utf-8-sig')
q3_stats={
    'q3_reg_intercept': float(coef[0]), 'q3_reg_capacity_coef': float(coef[1]),
    'q3_reg_duration_coef': float(coef[2]), 'q3_reg_arrival_coef': float(coef[3]),
    'q3_r2': float(r2), 'q3_rmse_m': float(rmse), 'q3_mae_m': float(mae)
}

# Q4 shock-wave/vertical queue model. Use video1 mean incident capacity as bottleneck capacity.
C_acc=q1_stats['q1_capacity_mean']
q_in=1500.0
jam_density_total=0.28 # pcu/m, two-lane queue equivalent
L_target=140.0
excess=max(q_in-C_acc,1e-6)
time_h=L_target*jam_density_total/excess
time_min=time_h*60
# sensitivity: capacity +/-10%, jam density +/-15%
sens=[]
for cap_ratio in np.linspace(0.9,1.1,9):
    cap=C_acc*cap_ratio
    if q_in>cap:
        t=L_target*jam_density_total/(q_in-cap)*60
    else:
        t=np.inf
    sens.append({'parameter':'capacity_ratio','ratio':cap_ratio,'time_min':t})
for kd_ratio in np.linspace(0.85,1.15,7):
    t=L_target*jam_density_total*kd_ratio/excess*60
    sens.append({'parameter':'jam_density_ratio','ratio':kd_ratio,'time_min':t})
sens=pd.DataFrame(sens)
sens.to_csv(ROOT/'quest4/outputs/q4_sensitivity.csv', index=False, encoding='utf-8-sig')
q4_stats={'q4_upstream_flow_pcu_h':q_in,'q4_accident_capacity_pcu_h':float(C_acc),'q4_jam_density_pcu_m':jam_density_total,'q4_target_length_m':L_target,'q4_time_to_intersection_min':float(time_min),'q4_time_to_intersection_s':float(time_min*60)}

# Baseline for Q4: one-lane nominal capacity 1000 pcu/h
baseline_C=1000.0
baseline_time=L_target*jam_density_total/(q_in-baseline_C)*60

# Plots
fig,ax=plt.subplots(figsize=(9,5))
ax.plot(v1.minute, v1.capacity_pcu_h, marker='o', markersize=3, label='实际通行能力')
ax.axhline(v1.capacity_pcu_h.mean(), color='r', linestyle='--', label=f'均值 {v1.capacity_pcu_h.mean():.0f} pcu/h')
ax.set_xlabel('事故持续时间/min'); ax.set_ylabel('通行能力/(pcu/h)')
ax.set_title('视频1事故期间横断面实际通行能力变化')
ax.legend(); ax.grid(alpha=.3)
plt.savefig(ROOT/'quest1/figures/q1_capacity_process.png', dpi=300, bbox_inches='tight'); plt.close()

fig,ax=plt.subplots(figsize=(9,5))
ax.plot(v1.minute, v1.capacity_pcu_h, label='视频1：内侧+中间占用')
ax.plot(v2.minute, v2.capacity_pcu_h, label='视频2：中间+外侧占用')
ax.set_xlabel('事故持续时间/min'); ax.set_ylabel('通行能力/(pcu/h)')
ax.set_title('不同占用车道下横断面实际通行能力对比')
ax.legend(); ax.grid(alpha=.3)
plt.savefig(ROOT/'quest2/figures/q2_capacity_comparison.png', dpi=300, bbox_inches='tight'); plt.close()

fig,ax=plt.subplots(figsize=(6,6))
ax.scatter(y,pred,s=20,alpha=.75)
lo=min(y.min(),pred.min()); hi=max(y.max(),pred.max())
ax.plot([lo,hi],[lo,hi],'r--')
ax.set_xlabel('模型/重构队列长度观测值/m'); ax.set_ylabel('回归预测值/m')
ax.set_title(f'排队长度回归拟合效果（R²={r2:.3f}）')
ax.grid(alpha=.3)
plt.savefig(ROOT/'quest3/figures/q3_fit_scatter.png', dpi=300, bbox_inches='tight'); plt.close()

fig,ax=plt.subplots(figsize=(9,5))
ax.plot(v1.minute, v1.queue_length_m, label='视频1重构队列长度')
ax.set_xlabel('事故持续时间/min'); ax.set_ylabel('排队长度/m')
ax.set_title('视频1事故影响路段排队长度变化')
ax.grid(alpha=.3); ax.legend()
plt.savefig(ROOT/'quest3/figures/q3_queue_evolution.png', dpi=300, bbox_inches='tight'); plt.close()

fig,ax=plt.subplots(figsize=(9,5))
for p,g in sens.groupby('parameter'):
    ax.plot(g.ratio, g.time_min, marker='o', label=('通行能力扰动' if p=='capacity_ratio' else '排队密度扰动'))
ax.axhline(time_min,color='k',ls='--',label=f'基准 {time_min:.2f} min')
ax.set_xlabel('参数相对基准值比例'); ax.set_ylabel('到达上游路口时间/min')
ax.set_title('问题4关键参数敏感性分析')
ax.grid(alpha=.3); ax.legend()
plt.savefig(ROOT/'quest4/figures/q4_sensitivity.png', dpi=300, bbox_inches='tight'); plt.close()

# freeze numbers
frozen={
 'data_limitation':'原题目录仅含题面doc和readme.doc，不含附件1/2视频及附件3/4/5原图；本解答采用题面、公开摘要和交通流理论构建可复现参数化重构数据，所有视频相关数值不得冒充原始视频人工计数。',
 'Q1':q1_stats,'Q2':q2_stats,'Q3':q3_stats,'Q4':q4_stats,
 'baseline':{'q4_baseline_capacity_pcu_h':baseline_C,'q4_baseline_time_min':baseline_time},
 'sources':['题面 CUMCM2013A.doc','readme.doc','CNKI/期刊公开摘要：李梦圆等，车道被占用对城市道路通行能力的影响，贵州师范学院学报，2013(12)','爱发表公开摘要：贾文，车道被占用对城市道路通行能力的影响，齐鲁工业大学学报，2014(01)','交通工程中排队累积与冲击波基本关系']
}
(ROOT/'results/frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')

# final table
pd.DataFrame([
 {'问题':'问题1','核心结果':f"视频1事故期间平均实际通行能力 {q1_stats['q1_capacity_mean']:.1f} pcu/h，最小 {q1_stats['q1_capacity_min']:.1f} pcu/h，波动系数 {q1_stats['q1_capacity_cv']:.3f}"},
 {'问题':'问题2','核心结果':f"视频2均值 {q2_stats['q2_video2_mean_capacity']:.1f} pcu/h，比视频1低 {q2_stats['q2_capacity_drop_pct_video2_vs_video1']:.1f}%"},
 {'问题':'问题3','核心结果':f"排队长度回归 R²={q3_stats['q3_r2']:.3f}，RMSE={q3_stats['q3_rmse_m']:.2f} m"},
 {'问题':'问题4','核心结果':f"q=1500 pcu/h、瓶颈能力={C_acc:.1f} pcu/h、排队密度=0.28 pcu/m时，排队达140m约需 {time_min:.2f} min"},
]).to_csv(ROOT/'tables/final_results_summary.csv',index=False,encoding='utf-8-sig')

print('Generated artifacts under', ROOT)
print(json.dumps(frozen,ensure_ascii=False,indent=2))
