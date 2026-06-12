# 2013C 古塔的变形 支撑材料

## 文件结构
- papper/论文.tex, 论文.pdf：正式论文源文件和PDF。
- quest1/codes/main_modeling.py：完整建模、作图、结果冻结脚本。
- quest*/figures：各问题图表。
- tables：中心坐标、变形指标、趋势回归等结果表。
- results/frozen_numbers.json：论文使用的关键冻结数字。
- data：原始题面和附件。

## 运行方法
在支撑材料目录运行：
```bash
python quest1/codes/main_modeling.py
cd papper && xelatex -interaction=nonstopmode 论文.tex
```

## 数据审计
- 原始长表记录数：424。
- 年份：1986、1996、2009、2011。
- 缺测：1986/1996第13层5号点缺测；2009/2011塔尖仅给单点或未按多点观测，正式变形趋势分析到第13层。
- 圆拟合最大RMS：0.0774 m，中位RMS：0.0500 m。
