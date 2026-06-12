# 2012D 机器人避障问题支撑材料

## 项目信息
- 题目：2012高教社杯全国大学生数学建模竞赛D题：机器人避障问题
- 完成内容：避障最短路径模型、O到A最短时间路径模型、论文PDF、代码、结果表、图表

## 文件结构
- `papper/论文.tex`：LaTeX论文源文件
- `papper/论文.pdf`：最终论文PDF
- `code/main_modeling.py`：主建模程序
- `tables/final_path_summary.csv`：主要路径结果汇总
- `tables/all_segments.csv`：全部路径段明细
- `quest1/figures/`：问题一各路径图
- `quest1/outputs/`：问题一路径段表
- `quest2/figures/`：问题二路径图与敏感性图
- `quest2/outputs/`：问题二路径段表与半径候选结果
- `results/frozen_numbers.json`：论文冻结数字
- `data/CUMCM_2012_D_Chinese.doc`：原题文件备份
- `references/problem_statement.txt`：题面文本提取
- `references/method_notes.md`：方法记录

## 运行说明
在本目录运行：
```bash
python code/main_modeling.py
cd papper
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```

## 主要结果
- O→A：可执行距离 461.51，总时间 92.30s
- O→B：可执行距离 866.47，总时间 173.29s
- O→C：可执行距离 932.38，总时间 189.17s
- O→A→B→C→O：可执行距离 2315.65，总时间 466.16s
- O→A最短时间候选：半径参数60，总距离431.68，总时间86.34s
