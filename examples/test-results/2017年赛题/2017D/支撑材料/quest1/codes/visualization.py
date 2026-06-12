"""
CUMCM 2017 D - 可视化图表
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path
import os
import json

# 中文字体
_FONT_CANDIDATES = [
    r'C:/Windows/Fonts/msyh.ttc',
    r'C:/Windows/Fonts/simhei.ttf',
    r'C:/Windows/Fonts/NotoSansSC-VF.ttf',
    r'C:/Windows/Fonts/simsun.ttc',
]
for fp in _FONT_CANDIDATES:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        fn = font_manager.FontProperties(fname=fp).get_name()
        plt.rcParams['font.sans-serif'] = [fn, 'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus'] = False

os.chdir('<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017D')

# 数据
points_data = [
    (1,35,3),(2,50,2),(3,35,3),(4,35,2),(5,720,2),(6,35,3),(7,80,2),
    (8,35,3),(9,35,4),(10,120,2),(11,35,3),(12,35,2),(13,80,5),(14,35,3),
    (15,35,2),(16,35,3),(17,480,2),(18,35,2),(19,35,2),(20,35,3),(21,80,3),
    (22,35,2),(23,35,3),(24,35,2),(25,120,2),(26,35,2)
]

edges_data = [
    (1,2,2),(2,3,1),(2,4,3),(2,19,5),(3,5,1),(3,6,1),(4,21,1),
    (4,23,4),(5,7,2),(6,8,2),(6,14,1),(6,10,5),(8,17,1),(9,24,2),
    (9,25,3),(10,11,2),(10,12,6),(11,13,2),(11,15,7),(12,15,2),
    (13,16,2),(15,18,2),(15,26,6),(16,18,3),(17,25,1),(19,20,2),
    (20,22,2),(21,22,2),(22,23,1),(23,24,1),(25,26,3)
]

# ===== 图1：巡检周期分布 =====
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

periods = [p[1] for p in points_data]
period_labels = ['35min', '50min', '80min', '120min', '480min', '720min']
period_counts = [periods.count(35), periods.count(50), periods.count(80), 
                 periods.count(120), periods.count(480), periods.count(720)]

colors = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#F44336', '#607D8B']
axes[0].bar(period_labels, period_counts, color=colors, edgecolor='white', linewidth=1.5)
axes[0].set_xlabel('巡检周期', fontsize=12)
axes[0].set_ylabel('巡检点数量', fontsize=12)
axes[0].set_title('各周期巡检点数量分布', fontsize=14, fontweight='bold')
for i, v in enumerate(period_counts):
    axes[0].text(i, v + 0.2, str(v), ha='center', fontsize=11, fontweight='bold')

# 巡检耗时分布
durations = [p[2] for p in points_data]
dur_labels = ['2min', '3min', '4min', '5min']
dur_counts = [durations.count(2), durations.count(3), durations.count(4), durations.count(5)]
axes[1].pie(dur_counts, labels=dur_labels, autopct='%1.1f%%', 
            colors=['#2196F3', '#4CAF50', '#FF9800', '#F44336'],
            startangle=90, textprops={'fontsize': 12})
axes[1].set_title('各巡检耗时分布', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig('支撑材料/figures/fig1_period_distribution.png', dpi=300, bbox_inches='tight')
plt.close()

# ===== 图2：工作量分析 =====
fig, ax = plt.subplots(figsize=(12, 6))

shift = 480
visits = [int(np.ceil(shift / p[1])) for p in points_data]
inspect_time = [v * p[2] for v, p in zip(visits, points_data)]
point_ids = [f'XJ-{p[0]:04d}' for p in points_data]

x = np.arange(len(point_ids))
width = 0.4

bars1 = ax.bar(x - width/2, visits, width, label='每班巡检次数', color='#2196F3', alpha=0.8)
ax2 = ax.twinx()
bars2 = ax2.bar(x + width/2, inspect_time, width, label='每班巡检总时间(min)', color='#FF9800', alpha=0.8)

ax.set_xlabel('巡检点编号', fontsize=12)
ax.set_ylabel('巡检次数', fontsize=12, color='#2196F3')
ax2.set_ylabel('巡检总时间(min)', fontsize=12, color='#FF9800')
ax.set_title('各巡检点每班工作量', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(point_ids, rotation=45, ha='right', fontsize=9)

lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

plt.tight_layout()
plt.savefig('支撑材料/figures/fig2_workload_analysis.png', dpi=300, bbox_inches='tight')
plt.close()

# ===== 图3：网络拓扑图 =====
fig, ax = plt.subplots(figsize=(12, 10))

# 手动布局（基于连通关系）
pos = {
    1: (1, 8), 2: (3, 8), 3: (5, 9), 4: (6, 7), 5: (7, 10), 6: (7, 8),
    7: (9, 10), 8: (9, 7), 9: (12, 6), 10: (10, 5), 11: (12, 5),
    12: (11, 3), 13: (14, 5), 14: (8, 7), 15: (13, 3), 16: (15, 5),
    17: (10, 8), 18: (14, 3), 19: (4, 6), 20: (4, 4), 21: (7, 5),
    22: (5, 4), 23: (6, 5), 24: (11, 6), 25: (12, 7), 26: (15, 2)
}

# 画边
for e in edges_data:
    x1, y1 = pos[e[0]]
    x2, y2 = pos[e[1]]
    ax.plot([x1, x2], [y1, y2], 'gray', linewidth=0.8, alpha=0.5)
    mx, my = (x1+x2)/2, (y1+y2)/2
    ax.text(mx, my, str(e[2]), fontsize=7, ha='center', va='center', 
            color='gray', bbox=dict(boxstyle='round,pad=0.1', facecolor='white', alpha=0.7))

# 画节点
period_colors = {35: '#2196F3', 50: '#4CAF50', 80: '#FF9800', 
                 120: '#9C27B0', 480: '#F44336', 720: '#607D8B'}

for p in points_data:
    x, y = pos[p[0]]
    c = period_colors[p[1]]
    size = 200 if p[0] != 22 else 400
    marker = 's' if p[0] == 22 else 'o'
    ax.scatter(x, y, s=size, c=c, marker=marker, edgecolors='black', linewidth=1, zorder=5)
    ax.annotate(f'XJ-{p[0]:04d}\n({p[1]}min)', (x, y), textcoords="offset points",
                xytext=(0, 12), ha='center', fontsize=7, fontweight='bold')

# 图例
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=c, label=f'{per}min') for per, c in period_colors.items()]
ax.legend(handles=legend_elements, loc='lower left', fontsize=9, title='巡检周期')
ax.set_title('化工厂巡检网络拓扑图', fontsize=14, fontweight='bold')
ax.set_xlabel('相对位置X', fontsize=11)
ax.set_ylabel('相对位置Y', fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('支撑材料/figures/fig3_network_topology.png', dpi=300, bbox_inches='tight')
plt.close()

# ===== 图4：Q1 vs Q2 人员对比 =====
fig, ax = plt.subplots(figsize=(8, 5))

categories = ['Q1固定班\n(无休息)', 'Q2固定班\n(有休息)', 'Q3错时\n(无休息)', 'Q3错时\n(有休息)']
workers = [17, 19, 17, 19]
total = [51, 57, 51, 57]

x = np.arange(len(categories))
width = 0.35

bars1 = ax.bar(x - width/2, workers, width, label='每班人数', color='#2196F3', edgecolor='white')
bars2 = ax.bar(x + width/2, total, width, label='三班总人数', color='#FF9800', edgecolor='white')

for bar in bars1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, 
            str(int(bar.get_height())), ha='center', fontsize=11, fontweight='bold')
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, 
            str(int(bar.get_height())), ha='center', fontsize=11, fontweight='bold')

ax.set_ylabel('人数', fontsize=12)
ax.set_title('各方案人员需求对比', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=10)
ax.legend(fontsize=11)
ax.set_ylim(0, 65)

plt.tight_layout()
plt.savefig('支撑材料/figures/fig4_workers_comparison.png', dpi=300, bbox_inches='tight')
plt.close()

# ===== 图5：路线时间分布 =====
fig, ax = plt.subplots(figsize=(12, 6))

# Q1路线数据
routes_q1 = [
    ('R1: 22-23-24-9-20-19', 35, 32, 1),
    ('R2: 4-3-6-14', 35, 29, 1),
    ('R3: 1-8', 35, 29, 1),
    ('R4: 26', 35, 22, 1),
    ('R5: 11', 35, 33, 1),
    ('R6: 15', 35, 34, 1),
    ('R7: 12', 35, 38, 2),
    ('R8: 18', 35, 38, 2),
    ('R9: 16', 35, 41, 2),
    ('R10: 2', 50, 14, 1),
    ('R11: 21-7-13', 80, 50, 1),
    ('R12: 25-10', 120, 33, 1),
    ('R13: 17', 480, 18, 1),
    ('R14: 5', 720, 18, 1),
]

route_names = [r[0] for r in routes_q1]
route_times = [r[2] for r in routes_q1]
route_periods = [r[1] for r in routes_q1]
route_workers = [r[3] for r in routes_q1]

colors = ['#2196F3' if w == 1 else '#F44336' for w in route_workers]
bars = ax.barh(range(len(route_names)), route_times, color=colors, edgecolor='white', height=0.6)

# 标注周期线
for i, (rt, rp) in enumerate(zip(route_times, route_periods)):
    ax.plot([rp, rp], [i-0.4, i+0.4], 'k--', linewidth=1, alpha=0.5)

ax.set_yticks(range(len(route_names)))
ax.set_yticklabels(route_names, fontsize=9)
ax.set_xlabel('时间 (min)', fontsize=12)
ax.set_title('Q1各路线耗时与周期约束对比', fontsize=14, fontweight='bold')
ax.invert_yaxis()

# 图例
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor='#2196F3', label='1人路线'),
                   Patch(facecolor='#F44336', label='需增员路线'),
                   plt.Line2D([0], [0], color='k', linestyle='--', label='周期约束线')]
ax.legend(handles=legend_elements, loc='lower right', fontsize=10)

plt.tight_layout()
plt.savefig('支撑材料/figures/fig5_route_time_analysis.png', dpi=300, bbox_inches='tight')
plt.close()

print("所有图表已生成:")
print("  fig1_period_distribution.png - 巡检周期分布")
print("  fig2_workload_analysis.png - 工作量分析")
print("  fig3_network_topology.png - 网络拓扑图")
print("  fig4_workers_comparison.png - 人员对比")
print("  fig5_route_time_analysis.png - 路线时间分析")
