# 2017A CT系统参数标定及成像应用 支撑材料

## 运行环境
Python 3.11，依赖 numpy pandas scipy scikit-image matplotlib openpyxl reportlab。

## 主要文件
- papper/论文.pdf：正式论文。
- code/main_modeling.py：完整建模求解脚本。
- code/build_pdf_report.py：PDF生成脚本。
- results/frozen_numbers.json：冻结关键数字。
- results/problem2.xls, results/problem3.xls：题目要求的256×256重建矩阵。
- tables/*.csv：标定、几何、10点吸收率、灵敏度分析结果。
- quest*/figures/*.png：论文图表。

## 复现方式
在任意简单工作目录运行：
python "<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017A/支撑材料/code/main_modeling.py"
python "<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017A/支撑材料/code/build_pdf_report.py"
