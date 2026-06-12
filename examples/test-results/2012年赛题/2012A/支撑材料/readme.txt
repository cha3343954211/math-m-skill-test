# 2012A 葡萄酒的评价 支撑材料

生成时间：2026-05-30 10:38

## 文件结构
- papper/论文.tex, 论文.pdf：正式论文
- code/main_modeling.py：完整可复现代码
- quest1~quest4：各问代码、图表、输出
- tables/：最终结果表
- results/frozen_numbers.json：论文冻结数字
- data/：原始题面与附件

## 运行说明
在本机 Python 3.12 环境运行：
python code/main_modeling.py

## 主要结论
- Q1：两组评分存在显著差异；综合离散系数与评委秩相关性，本文采用第二组作为更可信质量评分。
- Q2：采用质量评分与葡萄理化/芳香PCA综合得分分级，结果见 tables/final_grape_grading.csv。
- Q3：采用主成分相关和PLS验证葡萄与葡萄酒指标联系，结果见 tables/q3_grape_wine_relation.csv。
- Q4：用PLS/Ridge/RF比较理化指标预测质量能力，结果见 tables/q4_quality_prediction_models.csv。
