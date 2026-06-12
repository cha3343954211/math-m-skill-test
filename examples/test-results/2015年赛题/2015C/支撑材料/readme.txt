# 2015C 月上柳梢头 支撑材料

## 目录
- papper/: 论文 LaTeX 源文件与 PDF
- code/main_modeling.py: 主模型、图表、表格和冻结数字生成脚本
- tables/: 最终结果表、baseline、敏感性分析
- results/figures/: 论文图表
- contracts/frozen_numbers.json: 论文关键数字唯一来源
- data/problem_statement.txt: 题面文本

## 复现
在项目根目录运行：
python 支撑材料/code/main_modeling.py

依赖：numpy pandas matplotlib skyfield lunardate scipy。

## 核心结果
2016年北京农历正月十五为 2016-02-22。主模型用太阳高度[-12,-6]度定义黄昏后，用月亮高度[8,15]度定义月上柳梢头，并要求月面照明比例不低于0.80。详见 tables/city_2016_chosen_results.csv。
