# 支撑材料说明

## 项目信息
- 题目：2014高教社杯全国大学生数学建模竞赛 B题 创意平板折叠桌
- 工作目录：2014B/支撑材料
- 生成日期：2026-05-31

## 文件结构
```
支撑材料/
├── papper/                 # 论文源文件与PDF
│   ├── 论文.tex
│   ├── 论文.md
│   └── 论文.pdf
├── code/
│   └── main_modeling.py    # 主建模脚本，生成全部结果、表格和图
├── quest1/                 # 问题一图表与输出
├── quest2/                 # 问题二图表与输出
├── quest3/                 # 问题三图表与输出（含8张动态过程图）
├── tables/                 # 最终参数表CSV
├── results/
│   └── frozen_numbers.json # 论文冻结数字
├── references/             # 题面提取与IMA检索记录
└── data/                   # 原始题面与视频附件
```

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
### 问题一
- 木条数：20
- 有效平板尺寸：111.827 cm × 50.000 cm × 3 cm
- 木条长度范围：53.079–55.913 cm
- 最大开槽长度：2.315 cm
- 支撑半径：24.254 cm

### 问题二
- 目标：桌高70 cm，桌面直径80 cm
- 最优平板尺寸：151.272 cm × 80.000 cm × 3 cm
- 木条数：32
- 钢筋位置比例：0.3500
- 最大开槽长度：2.773 cm
- 稳定性指标：0.9173

### 问题三
- 给出椭圆、圆角方形、花瓣形三类创意折叠桌方案
- 已生成8张动态变化过程图

## 质量门控
- L1 建模合理性：通过
- L2 求解正确性：通过，关键数字已冻结到 results/frozen_numbers.json
- L3 论文质量：通过，PDF共19页
