# 2014D 储药柜的设计 支撑材料

## 主要结论
- 问题一：最少竖向隔板间距类型 3 类。
- 问题二：选定竖向隔板间距类型 14 类，总宽度冗余 1458.00 mm。
- 问题三：选定横向隔板间距类型 16 类，总平面冗余 2021.00 mm²。
- 问题四：总储药槽数 2457 个，估计最少储药柜 2 个。

## 目录说明
- papper/：论文 tex、pdf、md。
- quest1/quest2/quest3/：分问题代码、图表和输出。
- tables/：主要结果表 CSV。
- results/：冻结数字和敏感性分析图。
- references/：题意解析、建模路线和检索记录。
- data/：原始题目与附件备份。

## 复现方式
```bash
python quest1/codes/main_modeling.py
cd papper
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```
