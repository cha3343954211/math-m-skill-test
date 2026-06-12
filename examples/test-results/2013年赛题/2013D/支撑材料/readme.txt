# 支撑材料 - 2013D 公共自行车服务系统

## 数据说明
当前题目目录仅含 CUMCM2013D.doc 和 readme.doc，缺少附件1（20个Excel）和附件2站点图。本次交付采用固定随机种子生成的仿真样本完成完整建模流程；若补入真实附件，可复用 code/main_modeling.py 的同一口径重算。

## 目录
- papper/论文.tex, 论文.pdf：正式论文
- code/main_modeling.py：主建模代码
- data/：题面文档副本与本次使用数据 stations_used.csv, trips_used.csv
- tables/：最终结果表
- results/frozen_numbers.json：冻结数字
- quest1/ quest2/ quest3/：分问题输出与图表
- references/data_audit_and_method_notes.md：数据审计与方法记录

## 运行
python code/main_modeling.py
cd papper && xelatex -interaction=nonstopmode 论文.tex （运行3遍）
