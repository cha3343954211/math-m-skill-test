# 2012C 脑卒中发病环境因素分析及干预 支撑材料

## 主要文件
- papper/论文.pdf：最终数学建模论文
- papper/论文.tex：LaTeX源文件
- code/main_modeling.py：完整数据清洗、建模、可视化、论文生成脚本
- results/frozen_numbers.json：论文关键数字冻结文件
- quest1/：发病人群统计描述代码输出与图表
- quest2/：气象因素模型、系数、残差、敏感性分析
- quest3/：预警干预方案表格与图表
- data/：题目原始附件备份

## 运行方式
在项目根目录运行：python 支撑材料/code/main_modeling.py

## 关键结果
- 有效病例：61851例；60岁及以上占80.5%。
- 主模型测试MAE=16.412，AIC较baseline降低451.3。
- 给出蓝/黄/橙/红四级气象—人群综合风险预警方案。
