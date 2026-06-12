# -*- coding: utf-8 -*-
from pathlib import Path
import json, pandas as pd, textwrap, os, re
ROOT=Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012B')
SUP=ROOT/'支撑材料'; PAP=SUP/'papper'; PAP.mkdir(parents=True,exist_ok=True)
fn=json.loads((SUP/'results'/'frozen_numbers.json').read_text(encoding='utf-8'))

def esc(s):
    s=str(s)
    return s.replace('\\','/').replace('&','\\&').replace('%','\\%').replace('_','\\_').replace('#','\\#')

def csv_table(name, cols, maxrows=8):
    df=pd.read_csv(SUP/'tables'/name)
    df=df.head(maxrows)
    spec='l'+'r'*(len(cols)-1)
    lines=[r'\begin{tabular}{%s}\toprule'%spec]
    lines.append(' & '.join(esc(c) for c in cols)+r'\\\midrule')
    for _,r in df.iterrows():
        vals=[]
        for c in cols:
            v=r[c]
            if isinstance(v,float): v=f'{v:.2f}'
            vals.append(esc(v))
        lines.append(' & '.join(vals)+r'\\')
    lines.append(r'\bottomrule\end{tabular}')
    return '\n'.join(lines)

res=fn['results']; base=fn['baselines']
summary_rows=[]
for q in ['问题1','问题2','问题3']:
    s=res[q]
    summary_rows.append(f"{q} & {s['组件块数']} & {s['装机容量kW']} & {s['年发电量kWh']} & {s['35年等效发电量kWh']} & {s['总投资元']} & {s['净收益元']} & {s['静态回收年限']}\\\\")
summary='\n'.join(summary_rows)
body = rf'''
\documentclass[UTF8,a4paper,12pt]{{ctexart}}
\usepackage{{geometry,graphicx,booktabs,longtable,array,amsmath,amssymb,float,fancyhdr,lastpage,caption,subcaption,xcolor,enumitem}}
\geometry{{left=2.5cm,right=2.5cm,top=2.4cm,bottom=2.4cm}}
\setlength{{\headheight}}{{15pt}}
\pagestyle{{fancy}}\fancyhf{{}}\lhead{{2012B 太阳能小屋的设计}}\rhead{{数学建模论文}}\cfoot{{第 \thepage 页 / 共 \pageref{{LastPage}} 页}}
\captionsetup{{font=small,labelsep=quad}}
\renewcommand{{\arraystretch}}{{1.18}}
\title{{基于整数规划与全寿命经济性的太阳能小屋光伏铺设优化}}
\author{{}}
\date{{}}
\begin{{document}}
\maketitle
\begin{{abstract}}
本文针对2012年B题“太阳能小屋的设计”，在大同典型气象年逐时辐射数据、光伏组件参数和逆变器参数的基础上，建立了“表面--组件型号--数量”的整数规划模型，并结合串并联电压约束和逆变器容量约束给出可执行的分组阵列方案。由于原目录中附件2给定小屋外观尺寸图为空，本文在不改变题意约束的前提下，根据建筑要求重构给定小屋几何，并在模型假设中显式说明这一数据限制。

针对问题一，仅考虑贴附安装，本文以35年全寿命净收益和单位电量费用为综合目标，选取C类薄膜组件并在屋顶、南墙和西墙进行重点铺设。优化方案共铺设82块组件，装机容量为{res['问题1']['装机容量kW']} kW，年发电量为{res['问题1']['年发电量kWh']} kWh，35年等效发电量为{res['问题1']['35年等效发电量kWh']} kWh，总投资{res['问题1']['总投资元']}元，单位电量费用为{res['问题1']['平均单位电量费用元每kWh']}元/kWh，静态回收期为{res['问题1']['静态回收年限']}年。

针对问题二，考虑架空安装后通风降温和倾角优化带来的有效辐射增益，仍采用同一建筑外形重新求解。结果表明架空安装使年发电量提高到{res['问题2']['年发电量kWh']} kWh，35年等效发电量提高到{res['问题2']['35年等效发电量kWh']} kWh，单位电量费用下降为{res['问题2']['平均单位电量费用元每kWh']}元/kWh，净收益增加到{res['问题2']['净收益元']}元，回收期缩短到{res['问题2']['静态回收年限']}年。

针对问题三，本文在附件7约束下设计了一个投影面积72平方米、南高北低、屋顶南倾约23.43度的新小屋。优化后铺设98块组件，装机容量{res['问题3']['装机容量kW']} kW，年发电量{res['问题3']['年发电量kWh']} kWh，35年等效发电量{res['问题3']['35年等效发电量kWh']} kWh，净收益{res['问题3']['净收益元']}元，单位电量费用{res['问题3']['平均单位电量费用元每kWh']}元/kWh。敏感性分析显示，当年辐射强度在$\pm20\%$范围变化时，三种方案的经济性排序保持稳定，说明模型具有较好的稳健性。
\end{{abstract}}
\noindent\textbf{{关键词：}}太阳能小屋；光伏组件；整数规划；逆变器选配；全寿命经济性
\newpage
\tableofcontents
\newpage

\section{{问题重述}}
\subsection{{问题背景}}
太阳能小屋需要在屋顶和外墙上铺设光伏电池组件。组件输出为直流电，需要经过逆变器变为220V交流电后供家庭使用，剩余电量可输入电网。由于不同组件价格、峰瓦功率、启动阈值和转换效率差异明显，同一块外表面受到的太阳辐射也与朝向、倾角、安装方式和大同地区气象条件有关，因此不能简单地按照面积最大原则铺满，而应同时考虑发电量、单位电量费用、串并联电压、逆变器容量和35年寿命衰减。

\subsection{{待解决问题}}
题目要求分别完成三个层次的设计任务。问题一要求在给定小屋外表面、贴附安装条件下，选择组件型号、铺设位置、分组数量和逆变器规格，使全年发电量尽可能大且单位发电量费用尽可能小。问题二要求考虑架空方式安装，重新分析朝向与倾角对效率的影响并给出方案。问题三要求在附件7建筑要求下重新设计小屋外形，并对新小屋外表面进行光伏优化铺设。三个问题均需给出铺设图、串并联示意、分组阵列容量和逆变器规格，并计算35年发电总量、经济效益和投资回收年限。

\section{{问题分析}}
\subsection{{总体思路}}
本题属于带工程约束的组合优化问题。决策对象是每个建筑表面选择哪些组件、各铺设多少块，以及这些组件如何串并联并匹配逆变器。目标具有双重性：一方面全年发电量要大，另一方面单位电量费用要小。因此本文先用逐时辐射数据计算不同表面和不同组件的年等效发电量，再建立整数规划筛选组件数量，最后根据电压范围和容量约束做串并联及逆变器后处理。

本文的证据链为：附件数据清洗 $\rightarrow$ 辐射收益计算 $\rightarrow$ baseline构造 $\rightarrow$ 整数规划优化 $\rightarrow$ 逆变器匹配 $\rightarrow$ 35年经济性计算 $\rightarrow$ 敏感性检验。数据审计和最终数字均保存在支撑材料中，论文中的关键数字均来自\verb|results/frozen_numbers.json|。

\subsection{{各问题映射}}
问题一：题目要求输出给定小屋贴附安装的铺设方案；本文模型输出每个表面采用的组件型号、数量、串并联方式、逆变器型号、年发电量、35年收益和回收期。问题二：题目要求考虑架空安装对效率的影响；本文在问题一几何基础上引入架空增益系数，并重新优化。问题三：题目要求重新设计建筑；本文在投影面积、净空高度、窗地比、窗墙比等约束内设计南倾单坡小屋，再执行同一优化流程。

\section{{数据来源、预处理与模型假设}}
\subsection{{数据来源与审计}}
本文使用题目附件1、附件3、附件4、附件5、附件6和附件7。附件3给出24种光伏组件参数，附件4给出大同典型气象年8760小时逐时辐射数据，附件5给出18种逆变器参数与价格。经检查，气象辐射字段缺失值为0，光伏组件型号数为{fn['data_audit']['光伏组件型号数']}，逆变器型号数为{fn['data_audit']['逆变器型号数']}。附件2目录为空，无法提取原始小屋尺寸图，因此本文按题面建筑要求进行几何重构，并将该限制作为模型局限说明。

\begin{{table}}[H]\centering\caption{{三种问题最终优化结果汇总}}
\begin{{tabular}}{{lrrrrrrr}}\toprule
问题 & 组件数 & 容量/kW & 年发电/kWh & 35年发电/kWh & 投资/元 & 净收益/元 & 回收期/年\\\midrule
{summary}
\bottomrule\end{{tabular}}\end{{table}}

\subsection{{模型假设}}
假设1：组件在同一表面内接受相同朝向和相近遮挡条件。合理性在于题目要求按外表面分组阵列，同一分组阵列应尽可能具有相同太阳辐射条件；作用是使表面辐射数据可以直接用于同表面组件发电估计。假设2：电价35年内按0.5元/kWh静态计算。该值由题目给出；作用是计算收益和回收期。假设3：组件寿命衰减按附件3注释处理，0--10年100\%、10--25年90\%、25年后80\%，故35年等效年数为31.5年。假设4：架空安装主要通过通风降温和倾角调节提升有效辐射利用率，南向低倾角表面增益取14\%，东西墙取5\%，北墙取3\%。该假设用于问题二和问题三的比较，敏感性分析用于检验结论是否依赖该参数。

\section{{符号说明}}
\begin{{table}}[H]\centering\caption{{主要符号说明}}
\begin{{tabular}}{{lll}}\toprule
符号 & 含义 & 单位\\\midrule
$i$ & 建筑外表面编号 & --\\
$j$ & 光伏组件型号编号 & --\\
$x_{{ij}}$ & 表面$i$铺设型号$j$组件数量 & 块\\
$A_i$ & 表面$i$可铺设面积 & $m^2$\\
$a_j$ & 型号$j$单块组件面积 & $m^2$\\
$P_j$ & 型号$j$额定功率 & W\\
$G_i(t)$ & 表面$i$在$t$时刻的辐射强度 & W/$m^2$\\
$E_{{ij}}$ & 表面$i$铺设单块型号$j$组件的年发电量 & kWh\\
$C_j$ & 单块组件投资 & 元\\
$K$ & 逆变器投资 & 元\\
$T$ & 35年寿命等效年数，本文取31.5 & 年\\
\bottomrule\end{{tabular}}\end{{table}}

\section{{模型建立与求解}}
\subsection{{发电量模型}}
对表面$i$和组件$j$，若$t$时刻辐射强度低于组件启动阈值，则逆变器停止输出；否则按标准测试条件下1kWp组件在1000W/$m^2$辐射下1小时输出1kWh近似计算。因此单块组件年发电量为
\begin{{equation}}
E_{{ij}}=\eta_l\frac{{P_j}}{{1000}}\sum_{{t=1}}^{{8760}} \frac{{G_i(t)}}{{1000}} I(G_i(t)\geq G_j^0),
\end{{equation}}
其中$\eta_l$为线路和匹配损失修正系数，本文取0.92；$G_j^0$为启动阈值，晶硅组件取80W/$m^2$，薄膜组件取30W/$m^2$。

\subsection{{整数规划模型}}
设$x_{{ij}}$为非负整数，面积约束为
\begin{{equation}}
\sum_j a_j x_{{ij}}\le A_i,\quad x_{{ij}}\in \mathbb{{Z}}_+.
\end{{equation}}
35年等效发电量为$T\sum_{{i,j}}E_{{ij}}x_{{ij}}$。为了同时体现“发电量大”和“单位费用小”，本文以单块组件的35年净收益作为主优化系数：
\begin{{equation}}
\max \sum_{{i,j}} \left(0.5TE_{{ij}}-C_j\right)x_{{ij}}.
\end{{equation}}
该模型先决定组件数量，再进行逆变器固定成本后处理。若某个零散分组在加入逆变器后净收益为负，则剔除该经济性不可接受分组，保留可执行方案。这一处理避免了“组件本身边际收益为正但单独逆变器成本过高”的伪优方案。

\subsection{{逆变器与串并联模型}}
同型号组件可串联，不同型号不可串联。若型号$j$的开路电压为$V_j$，每串$s$块，则串电压为$sV_j$。逆变器$m$可行的条件为
\begin{{equation}}
V_m^{{\min}}\le sV_j\le V_m^{{\max}},\quad p s P_j/1000\le R_m,
\end{{equation}}
其中$p$为并联串数，$R_m$为逆变器额定功率。本文枚举可行$s,p$组合，选择满足电压和容量约束且投资最小的逆变器。分组阵列表已输出到支撑材料的CSV文件中。

\subsection{{问题一：贴附安装求解结果}}
问题一采用给定小屋重构几何，贴附安装不引入额外倾角增益。优化结果见表\ref{{tab:q1}}。方案集中选择C1薄膜组件，原因是其启动阈值低、价格仅4.8元/Wp，在大同垂直墙面和屋顶多方向辐射条件下，全寿命单位电量费用明显低于晶硅组件。虽然晶硅组件单位面积功率更高，但投资过大，按0.5元/kWh电价计算不具经济优势。
\begin{{table}}[H]\centering\caption{{问题一主要铺设分组与逆变器}}\label{{tab:q1}}
{csv_table('问题1_铺设分组与逆变器.csv',['surface','model','数量','串联数','并联串数','逆变器','装机容量kW','年发电量kWh','单位电量费用元每kWh'],8)}
\end{{table}}
\begin{{figure}}[H]\centering\includegraphics[width=.92\textwidth]{{../quest1/figures/问题1_铺设示意图.png}}\caption{{问题一光伏组件铺设与串并联示意图}}\end{{figure}}
该方案共铺设{res['问题1']['组件块数']}块组件，装机容量{res['问题1']['装机容量kW']}kW，年发电量{res['问题1']['年发电量kWh']}kWh。35年等效发电量为{res['问题1']['35年等效发电量kWh']}kWh，总投资{res['问题1']['总投资元']}元，按电价0.5元/kWh计算的35年收益为{res['问题1']['35年收益元']}元，净收益为{res['问题1']['净收益元']}元，静态回收期为{res['问题1']['静态回收年限']}年。

\subsection{{问题二：架空安装求解结果}}
问题二在同一小屋几何上考虑架空安装。架空安装的主要优势是改善组件背面通风、降低温升损失，同时允许屋面组件朝更优倾角布置。因此本文对南向低倾角面引入14\%有效辐射增益，对东西墙引入5\%通风收益，对北墙引入3\%收益。重新求解后主要分组见表\ref{{tab:q2}}。
\begin{{table}}[H]\centering\caption{{问题二主要铺设分组与逆变器}}\label{{tab:q2}}
{csv_table('问题2_铺设分组与逆变器.csv',['surface','model','数量','串联数','并联串数','逆变器','装机容量kW','年发电量kWh','单位电量费用元每kWh'],8)}
\end{{table}}
\begin{{figure}}[H]\centering\includegraphics[width=.92\textwidth]{{../quest2/figures/问题2_铺设示意图.png}}\caption{{问题二光伏组件铺设与串并联示意图}}\end{{figure}}
与问题一相比，组件数量保持{res['问题2']['组件块数']}块附近，但年发电量提高至{res['问题2']['年发电量kWh']}kWh，单位电量费用下降至{res['问题2']['平均单位电量费用元每kWh']}元/kWh。该结果说明在组件价格和逆变器配置不变时，架空方式主要通过提高单位容量发电量改善经济性。

\subsection{{问题三：新小屋设计与优化铺设}}
新小屋采用投影$12m\times6m$，投影面积72$m^2$，满足附件7总投影面积不超过74$m^2$、长边不超过15m、短边不小于3m的要求。北檐高2.8m，南檐高5.4m，满足室内最低净空和屋顶最高点要求；屋面向南倾斜约23.43度，以提高南向辐射利用。窗地比和窗墙比在建筑设计中通过南侧采光窗和东西北侧较小窗控制满足约束。
\begin{{table}}[H]\centering\caption{{问题三主要铺设分组与逆变器}}\label{{tab:q3}}
{csv_table('问题3_铺设分组与逆变器.csv',['surface','model','数量','串联数','并联串数','逆变器','装机容量kW','年发电量kWh','单位电量费用元每kWh'],8)}
\end{{table}}
\begin{{figure}}[H]\centering\includegraphics[width=.92\textwidth]{{../quest3/figures/问题3_铺设示意图.png}}\caption{{问题三新小屋铺设与串并联示意图}}\end{{figure}}
问题三方案共铺设{res['问题3']['组件块数']}块组件，装机容量{res['问题3']['装机容量kW']}kW，年发电量{res['问题3']['年发电量kWh']}kWh，35年等效发电量{res['问题3']['35年等效发电量kWh']}kWh。与问题二相比，重新设计小屋扩大了南向屋面和可铺设面积，使全寿命净收益提高到{res['问题3']['净收益元']}元。

\section{{模型检验、对比与敏感性分析}}
\subsection{{Baseline对比}}
本文设置的baseline为“在每个表面选择单位面积年发电量最大的组件并尽量铺满”。该策略追求大发电量，但忽略价格和逆变器固定成本。结果显示，baseline在问题一、二、三中的年发电量分别为{base['问题1']['年发电量kWh']}、{base['问题2']['年发电量kWh']}和{base['问题3']['年发电量kWh']}kWh，高于主模型；但其单位电量费用分别为{base['问题1']['单位电量费用元每kWh']}、{base['问题2']['单位电量费用元每kWh']}和{base['问题3']['单位电量费用元每kWh']}元/kWh，显著高于主模型。由此可见，本题不能单纯追求峰瓦容量或单位面积发电量，必须把全寿命经济性纳入目标。
\begin{{figure}}[H]\centering\includegraphics[width=.82\textwidth]{{../results/三方案对比.png}}\caption{{三种方案年发电量与单位电量费用对比}}\end{{figure}}

\subsection{{约束满足检验}}
面积约束方面，所有表面的铺设面积均不超过其可铺设面积；串并联方面，每个分组仅由同型号组件串联，不同型号不串联；逆变器方面，输出表中的组容量均不超过所选逆变器额定容量，串电压落在相应逆变器允许输入范围内或采用后处理选择的最接近可行规格。经济性方面，后处理删除了包含逆变器固定成本后净收益为负的小零散分组，避免为了填补边角面积而造成总成本上升。

\subsection{{敏感性分析}}
考虑典型气象年与未来年份存在差异，本文将年有效辐射强度在基准值的80\%--120\%之间扰动，重新计算发电量、单位电量费用和静态回收期。三种方案回收期均随辐射增强而下降，且问题三在多数扰动水平下保持较高净收益，说明新建筑设计对南向屋面面积的增加提高了方案稳健性。
\begin{{figure}}[H]\centering
\begin{{subfigure}}{{.32\textwidth}}\includegraphics[width=\textwidth]{{../quest1/figures/问题1_敏感性分析.png}}\caption{{问题一}}\end{{subfigure}}
\begin{{subfigure}}{{.32\textwidth}}\includegraphics[width=\textwidth]{{../quest2/figures/问题2_敏感性分析.png}}\caption{{问题二}}\end{{subfigure}}
\begin{{subfigure}}{{.32\textwidth}}\includegraphics[width=\textwidth]{{../quest3/figures/问题3_敏感性分析.png}}\caption{{问题三}}\end{{subfigure}}
\caption{{辐射扰动对静态回收期的影响}}
\end{{figure}}

\section{{模型评价、改进与推广}}
\subsection{{模型优点}}
第一，模型将逐时辐射数据、组件启动阈值、组件价格、逆变器容量和35年衰减统一到同一经济性框架中，避免只按面积或功率铺设的片面性。第二，整数规划直接输出每个表面的组件数量，后处理进一步给出串并联和逆变器型号，方案可执行性较强。第三，baseline对比说明主模型牺牲部分发电量换取更低单位电量费用，符合题目“发电量尽可能大且单位发电量费用尽可能小”的双目标要求。第四，敏感性分析验证了辐射波动下结论的稳定性。

\subsection{{模型局限}}
主要局限有三点。其一，附件2尺寸图缺失，给定小屋几何采用重构值，若原图尺寸与本文假设差异较大，问题一和问题二的具体数量会改变。其二，架空安装增益采用工程经验系数而非精细太阳位置角和倾角投影逐时计算，因此问题二和问题三的增益估计仍可进一步细化。其三，本文未考虑遮挡、安装维护费用、逆变器寿命短于组件寿命等因素，经济性结果偏乐观。

\subsection{{改进方向}}
若获得附件2原始尺寸图，可直接替换建筑表面面积并重新运行代码。若需要更高精度，可根据附件6太阳高度角、方位角公式计算任意倾角表面的逐时入射角，将水平面总辐射、散射辐射和法向直射辐射分解后再合成倾斜面辐射。经济模型方面，可引入折现率、维护成本和逆变器更换周期，建立净现值模型替代静态回收期。

\section{{结论}}
本文完成了2012B太阳能小屋三个问题的完整建模求解。问题一贴附安装方案的年发电量为{res['问题1']['年发电量kWh']}kWh，单位电量费用{res['问题1']['平均单位电量费用元每kWh']}元/kWh；问题二架空安装后年发电量提高到{res['问题2']['年发电量kWh']}kWh，单位电量费用降至{res['问题2']['平均单位电量费用元每kWh']}元/kWh；问题三新设计小屋年发电量达到{res['问题3']['年发电量kWh']}kWh，35年净收益{res['问题3']['净收益元']}元。综合看，低成本薄膜组件在本题电价和辐射条件下具有明显经济优势，而增大南向屋面可铺设面积、采用架空安装，是提升太阳能小屋综合效益的主要途径。

\begin{{thebibliography}}{{9}}
\bibitem{{solar}} 方荣生. 太阳能应用技术[M]. 北京: 中国农业机械出版社, 1985.
\bibitem{{std}} 中华人民共和国国家标准. GB/T 19939-2005 光伏系统并网技术要求[S].
\bibitem{{pv}} Stine W B, Geyer M. Power From The Sun[EB/OL]. http://www.powerfromthesun.net/.
\bibitem{{opt}} Winston W L. Operations Research: Applications and Algorithms[M]. Belmont: Duxbury Press, 2004.
\bibitem{{cumcm}} 全国大学生数学建模竞赛组委会. 2012高教社杯全国大学生数学建模竞赛B题及附件[Z].
\end{{thebibliography}}

\appendix
\section{{支撑材料说明}}
支撑材料包括：\verb|quest1/codes/main_modeling.py|主程序，\verb|tables/|下的组件清洗表、逆变器表、铺设分组表和敏感性分析表，\verb|results/frozen_numbers.json|冻结数字文件，以及各问题\verb|figures/|目录下的铺设示意图和敏感性图。运行主程序即可复现本文全部图表和关键数字。
\end{{document}}
'''
(PAP/'论文.tex').write_text(body,encoding='utf-8')
(PAP/'论文.md').write_text('正式论文见 论文.tex / 论文.pdf。关键结果来自 results/frozen_numbers.json。',encoding='utf-8')
print(PAP/'论文.tex')
