2011B 交巡警服务平台的设置与调度——支撑材料

运行方法：
1. python main_modeling.py  生成数据、模型结果、图表和 frozen_numbers.json
2. python write_paper.py    生成 LaTeX 论文
3. 在 papper 目录运行 xelatex 论文.tex 三次生成 PDF

主要结果：
- A区现状3分钟未覆盖节点：6，最大到达时间：5.70 min。
- A区建议新增平台数：4，位置节点：[28, 40, 48, 87]。
- 全市现状3分钟未覆盖节点：138，最薄弱区域：F区。
- P32围堵最小安全裕度：13.26 min，风险最高出口：202。
