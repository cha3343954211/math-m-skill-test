# 支撑材料 - CUMCM 2017 D题：巡检线路的排班

## 项目信息
- 题目：巡检线路的排班
- 赛事：2017年高教社杯全国大学生数学建模竞赛 D题
- 日期：2026年6月

## 文件结构
```
支撑材料/
├── data/raw/              # 原始附件
│   ├── CUMCM-2017-appendix-D.xlsx
│   └── CUMCM-2017-problem-D.docx
├── quest1/codes/          # 代码
│   ├── q1_main.py         # 三问完整求解主程序
│   └── visualization.py   # 可视化图表生成
├── figures/               # 生成的图表
│   ├── fig1_period_distribution.png
│   ├── fig2_workload_analysis.png
│   ├── fig3_network_topology.png
│   ├── fig4_workers_comparison.png
│   └── fig5_route_time_analysis.png
├── results/               # 冻结结果
│   └── frozen_numbers.json
├── papper/                # 论文
│   ├── 论文.tex           # LaTeX源文件
│   └── 论文.pdf           # 编译后的PDF（17页）
└── readme.txt             # 本文件
```

## 运行说明
### 环境要求
- Python 3.12+
- pip install numpy pandas openpyxl matplotlib
- MiKTeX 或 TeX Live（编译论文）

### 运行代码
```bash
cd 支撑材料/quest1/codes/
python q1_main.py          # 运行求解
python visualization.py    # 生成图表
```

### 编译论文
```bash
cd 支撑材料/papper/
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex  # 第二遍解决交叉引用
```

## 主要结果
### 问题一（固定班次，无休息）
- 每班最少需要：**17人**
- 三班共需：**51人**
- 设计14条巡检路线

### 问题二（含休息和进餐）
- 有效工作时间：427.5分钟
- 每班最少需要：**19人**
- 三班共需：**57人**

### 问题三（错时上班）
- 错时+无休息：17人/班，51人/三班
- 错时+有休息：19人/班，57人/三班
- 结论：错时上班在总人数上无显著节省，但能降低峰值人员密度
