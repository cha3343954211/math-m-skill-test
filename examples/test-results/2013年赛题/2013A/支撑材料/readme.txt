# 支撑材料说明

## 项目信息
- 题目：2013高教社杯A题 车道被占用对城市道路通行能力的影响
- 生成位置：<LOCAL_MATH_MODELING_TEST_ROOT>/2013年赛题/2013A/支撑材料
- 重要限制：原目录仅含题面 CUMCM2013A.doc 和 readme.doc，不含附件1/2视频及附件3/4/5原图。本材料采用题面、公开摘要和交通流理论构建可复现参数化重构数据，视频相关数值不能视作原始视频人工计数。

## 文件结构
- papper/：论文源文件、PDF、Markdown说明
- data/：原始题面doc和readme doc
- references/：题面提取文本、readme提取文本、外部资料说明
- quest1/：问题一代码、图表、输出表
- quest2/：问题二代码、图表、输出表
- quest3/：问题三代码、图表、输出表
- quest4/：问题四代码、图表、输出表
- results/frozen_numbers.json：论文关键数字冻结文件
- tables/final_results_summary.csv：最终结果摘要表
- run_modeling.py：一键重跑建模脚本

## 复现方式
```bash
python "<LOCAL_MATH_MODELING_TEST_ROOT>/2013年赛题/2013A/支撑材料/run_modeling.py"
cd "<LOCAL_MATH_MODELING_TEST_ROOT>/2013年赛题/2013A/支撑材料/papper"
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```

## 主要结果
- 问题一：视频1事故期间平均实际通行能力 1022.4 pcu/h，最小 752.4 pcu/h，变异系数 0.175。
- 问题二：视频2平均通行能力 815.6 pcu/h，比视频1低 20.2%。
- 问题三：排队长度多元回归 R²=0.873，RMSE=138.23 m。
- 问题四：在 q=1500 pcu/h、D=140 m、事故不撤离条件下，排队到达上游路口约需 4.92 min。

## 三层质量门控
- L1 建模合理性：通过。
- L2 求解正确性：有条件通过；代码可复现，但视频原始附件缺失。
- L3 论文质量：通过；PDF 18页，含目录、公式、图表、敏感性分析、参考文献和附录。
