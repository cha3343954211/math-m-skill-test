# 2014A 嫦娥三号软着陆轨道设计与控制策略支撑材料

## 目录说明
- `data/`：原始赛题与附件，含题面 doc 与两个 DEM tif。
- `code/main_modeling.py`：完整可复现建模代码，生成轨道、避障、控制、误差与敏感性结果。
- `tables/`：关键结果 CSV 表。
- `results/frozen_numbers.json`：论文引用的冻结数字。
- `results/figures/`：论文图表。
- `papper/论文.tex`、`papper/论文.pdf`：论文源文件和最终 PDF。

## 运行方式
在 Hermes/Windows bash 环境下运行：
```bash
python "<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014A/支撑材料/code/main_modeling.py"
cd "<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014A/支撑材料/papper"
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```

## 主要结果摘要
- 着陆准备轨道近月点半径 1749.372 km，远月点半径 1834.372 km；近月点速度 1694.056 m/s，远月点速度 1615.558 m/s。
- DEM 安全评分得到推荐着陆点相对预定中心总偏移约 1179.55 m。
- 分段三次轨迹与推力约束控制策略总动力下降时间 990.00 s，燃料消耗约 1404.95 kg，最大等效推力约 5400.69 N，满足 1500--7500 N 可调范围。
- 末端 4 m 自由落体阶段考虑测量误差后，95% 触地速度约 3.68 m/s。

## 质量门控
- L1 建模合理性：通过。逐问给出轨道位置/速度、六阶段轨迹控制、误差敏感性。
- L2 求解正确性：通过。代码固定随机种子，图表保存，关键数字冻结到 JSON。
- L3 论文质量：通过。LaTeX 正式排版，摘要含数字，图表/公式/表格均有解释。
