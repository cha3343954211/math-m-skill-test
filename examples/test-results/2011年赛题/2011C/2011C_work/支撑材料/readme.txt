# 支撑材料说明

## 项目信息
- 题目：2011年C题 企业退休职工养老金制度的改革
- 生成日期：2026-05-29
- 说明：本材料由可复现 Python 代码生成，论文中的关键数字来自 results/frozen_numbers.json 与 tables/*.csv。

## 文件结构
- papper/：论文 LaTeX 源文件、Markdown说明和最终 PDF
- quest1/：问题一工资预测代码引用、图表和输出表
- quest2/：问题二缴费指数与替代率结果
- quest3/：问题三基金缺口和平衡年龄结果
- quest4/：问题四政策敏感性与改革措施结果
- tables/：所有最终结果 CSV 表格
- results/：冻结数字 frozen_numbers.json 与三层质量审计

## 运行说明
环境依赖：pandas、numpy、matplotlib、scipy、scikit-learn、xlrd。

核心代码：
```bash
python quest1/codes/main_modeling.py
```

编译论文：
```bash
cd papper
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```

## 主要结果
- 2035年山东省职工年平均工资预测：271148.30元。
- 30岁起缴、55/60/65岁退休替代率：31.24%、39.21%、50.16%。
- 40岁起缴、55/60/65岁退休替代率：18.21%、25.05%、34.19%。
- 30岁起缴并领取至75岁，55/60/65岁退休基金缺口：134.34万元、113.55万元、58.64万元。
- 收支平衡年龄：62.996岁、67.858岁、72.431岁。

## 质量审计
- L1 建模合理性：通过。
- L2 求解正确性：通过，已生成冻结数字。
- L3 论文质量：通过，PDF由 XeLaTeX 编译生成，共20页。
