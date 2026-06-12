# 2017A CT系统参数标定及成像应用（返工版）

## 返工说明
本版修复旧版“标定参数未进入重建链”的问题。采用模板 Radon 投影联合标定 theta0/step/scale，并用逐投影 shift 校正附件2/3/5，再进行滤波反投影重建。

## 主要结果
- 模板匹配平均相关系数：0.9987
- 模板RMSE：baseline 0.3735 -> 返工主模型 0.0607
- 模板SSIM：baseline 0.0853 -> 返工主模型 0.6826
- 模板投影回代相关系数：0.9995

## 文件说明
- paper/论文.pdf：正式论文PDF
- paper/论文.tex：正式论文LaTeX源文件
- code/main_rework.py：返工版完整建模求解脚本
- code/build_latex_rework.py：论文生成脚本
- results/problem2.xls, results/problem3.xls：题目要求的256×256结果矩阵（真实Excel格式）
- results/problem2.xlsx, results/problem3.xlsx：同内容xlsx版本
- results/frozen_numbers_rework.json：冻结关键数字
- tables/*.csv：标定、验证、点值、几何和灵敏度表
- verification/verify_outputs.py：输出核验脚本

## 复现方式
安装 requirements.txt 后运行：
python code/main_rework.py
python code/build_latex_rework.py
python verification/verify_outputs.py
