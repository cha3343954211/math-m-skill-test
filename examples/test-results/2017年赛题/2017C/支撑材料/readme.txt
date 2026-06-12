# 2017C 颜色与物质浓度辨识 支撑材料

## 文件结构
- papper/论文.tex、论文.pdf：正式论文
- code/main_modeling.py：完整建模代码
- data/：原始题面与附件备份
- tables/：清洗数据、模型比较、预测残差、敏感性分析表
- results/frozen_numbers.json：论文引用的冻结数字
- quest1/ quest2/ quest3/：各小问图表和输出

## 运行方法
1. python code/main_modeling.py
2. cd papper && xelatex -interaction=nonstopmode 论文.tex （运行三遍）

## 主要结果
- 问题一最佳数据：溴酸钾；最差数据：奶中尿素。
- 问题二最优模型：FiveDim_Poly2_Ridge，LOO RMSE=10.25 ppm。
- 问题三完整样本最佳维度组合：RGBSH。
