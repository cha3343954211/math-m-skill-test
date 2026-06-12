# 2015A 太阳影子定位支撑材料

## 项目信息
- 题目：2015高教社杯全国大学生数学建模竞赛A题——太阳影子定位
- 完成内容：问题分析、太阳位置模型、地点/日期反演代码、图表、结果表、正式论文PDF、质量门控报告

## 目录结构
- `数据/`：题面与附件1-3原始Excel、附件4下载说明
- `代码/2015A_shadow_modeling.py`：完整可运行求解脚本
- `图表/`：论文中使用的所有PNG图表
- `tables/`：影长曲线、拟合轨迹、候选解、敏感性与汇总CSV
- `results/frozen_numbers.json`：论文引用的冻结数字
- `contracts/`：题意、模型路线、指标与结果契约
- `qa/`：预检、证据门禁和格式门禁报告
- `论文/论文.tex`、`论文/论文.pdf`：正式论文源文件与PDF

## 运行说明
在本目录下运行：

```bash
python 代码/2015A_shadow_modeling.py
```

依赖：numpy、pandas、scipy、matplotlib、xlrd。

## 编译论文
```bash
cd 论文
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
xelatex -interaction=nonstopmode 论文.tex
```

## 主要结果
- 问题1：天安门3m直杆在2015-10-22 11:58影长最短，为3.8411m。
- 问题2：附件1主要地点候选为北纬18.3361°、东经109.7018°，RMSE=0.000251m。
- 问题3：附件2优先候选为2015-05-23、北纬39.7296°、东经78.8739°；附件3优先候选为2015-11-16、北纬30.4121°、东经106.5854°。
- 问题4：视频文件缺失，未伪造结果；论文给出可执行视频反演模型。
