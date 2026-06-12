# 2011A 支撑材料说明

## 项目信息
- 题目：城市表层土壤重金属污染分析（2011年高教社杯A题）
- 生成时间：2026-05-29 14:54:44
- 样本量：319 个采样点，8 种重金属元素

## 文件结构
- papper/：论文Markdown、LaTeX源文件、PDF
- quest1/：空间分布与功能区污染评价代码、图表、输出
- quest2/：污染原因识别（相关/PCA/聚类）代码、图表、输出
- quest3/：传播特征与污染源定位图表、输出
- quest4/：模型评价、敏感性分析与改进材料
- tables/：论文表格CSV
- results/：数据审计、冻结数字frozen_numbers.json
- data_raw/ 与 data_clean/：原始附件和清洗后数据

## 运行说明
Python依赖：numpy pandas scipy scikit-learn matplotlib seaborn xlrd。
从本目录上一级运行：python 支撑材料/main_modeling.py
论文编译：cd 支撑材料/papper && xelatex 论文.tex 运行3遍。

## 主要结果摘要
- 平均PN最高功能区：工业区，平均PN=14.682。
- 最高RI采样点：编号9，位置(2708, 2295)，RI=18680.5。
- 前4个PCA主成分累计解释率：89.36%。
- KMeans污染谱最佳K=2，轮廓系数=0.335。
