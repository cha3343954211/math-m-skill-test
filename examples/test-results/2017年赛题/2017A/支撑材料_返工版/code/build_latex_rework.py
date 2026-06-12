#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
import json, shutil, subprocess, textwrap
import pandas as pd

ROOT=Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2017年赛题/2017A')
SUP=ROOT/'支撑材料_返工版'
BUILD=Path(r'<LOCAL_WORKSPACE>/ct2017a_rework_compile')
FIG=BUILD/'figs'
BUILD.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)
f=json.loads((SUP/'results/frozen_numbers_rework.json').read_text(encoding='utf-8'))
cal=f['calibration']; tv=f['template_validation']
pt=pd.read_csv(SUP/'tables/ten_point_absorption_rework.csv').round(4)
metrics=pd.read_csv(SUP/'tables/template_reconstruction_metrics.csv').round(4)
proj=pd.read_csv(SUP/'tables/projection_back_metrics.csv').round(4)
unkproj=pd.read_csv(SUP/'tables/unknown_projection_back_metrics.csv').round(4)
g2=pd.read_csv(SUP/'tables/problem2_geometry_components_rework.csv').round(4).head(5)
g3=pd.read_csv(SUP/'tables/problem3_geometry_components_rework.csv').round(4).head(5)
sens=pd.read_csv(SUP/'tables/sensitivity_analysis_rework.csv').round(4)
newt=pd.read_csv(SUP/'tables/new_template_identifiability.csv').round(4)
match=pd.read_csv(SUP/'tables/calibration_profile_matching.csv').round(4)

def tex_escape(s):
    return str(s).replace('\\','\\textbackslash{}').replace('_','\\_').replace('%','\\%').replace('&','\\&')
def df_tex(df, maxrows=None, cols=None, fmt='%.4f'):
    if cols: df=df[cols]
    if maxrows: df=df.head(maxrows)
    align='c'*len(df.columns)
    out=['\\begin{tabular}{'+align+'}','\\toprule']
    out.append(' & '.join(tex_escape(c) for c in df.columns)+' \\\\')
    out.append('\\midrule')
    for _,r in df.iterrows():
        vals=[]
        for x in r.values:
            if isinstance(x,float): vals.append(fmt%x)
            else: vals.append(tex_escape(x))
        out.append(' & '.join(vals)+' \\\\')
    out += ['\\bottomrule','\\end{tabular}']
    return '\n'.join(out)

fig_map={
 'template_original.png': SUP/'quest1/figures/template_original.png',
 'template_reconstruction_rework.png': SUP/'quest1/figures/template_reconstruction_rework.png',
 'angle_sequence_rework.png': SUP/'quest1/figures/angle_sequence_rework.png',
 'detector_shift_sequence.png': SUP/'quest1/figures/detector_shift_sequence.png',
 'baseline_comparison_rmse.png': SUP/'quest1/figures/baseline_comparison_rmse.png',
 'problem2_reconstruction_rework.png': SUP/'quest2/figures/problem2_reconstruction_rework.png',
 'problem3_reconstruction_rework.png': SUP/'quest3/figures/problem3_reconstruction_rework.png',
 'sensitivity_rework.png': SUP/'quest4/figures/sensitivity_rework.png',
 'new_template_design.png': SUP/'quest4/figures/new_template_design.png'
}
for name,src in fig_map.items():
    if src.exists(): shutil.copy2(src, FIG/name)

p2vals=', '.join(f'{x:.4f}' for x in f['problem2']['point_absorption'])
p3vals=', '.join(f'{x:.4f}' for x in f['problem3']['point_absorption'])
main=tv['main_corrected_shepp_logan']; base=tv['baseline_raw512_shepp_logan']; pb=tv['projection_back_main']
repl={
'__THETA0__':f"{cal['theta0_deg']:.4f}", '__STEP__':f"{cal['angle_step_deg']:.4f}", '__SCALE__':f"{cal['scale_cell_per_radon_pixel']:.4f}",
'__DPIX__':f"{cal['detector_spacing_pixel_per_cell']:.4f}", '__DMM__':f"{cal['detector_spacing_mm_per_cell']:.4f}", '__CORR__':f"{cal['mean_profile_corr']:.4f}",
'__SHIFTMEAN__':f"{cal['shift_mean_cell']:.4f}", '__SHIFTSTD__':f"{cal['shift_std_cell']:.4f}",
'__BASE_RMSE__':f"{base['rmse']:.4f}", '__BASE_SSIM__':f"{base['ssim']:.4f}", '__MAIN_MAE__':f"{main['mae']:.4f}", '__MAIN_RMSE__':f"{main['rmse']:.4f}", '__MAIN_SSIM__':f"{main['ssim']:.4f}",
'__PROJ_RMSE__':f"{pb['proj_rmse']:.4f}", '__PROJ_MAE__':f"{pb['proj_mae']:.4f}", '__PROJ_CORR__':f"{pb['proj_corr']:.4f}",
'__P2VALS__':p2vals, '__P3VALS__':p3vals,
'__PT_TABLE__':df_tex(pt), '__METRICS_TABLE__':df_tex(metrics), '__PROJ_TABLE__':df_tex(proj[['name','proj_rmse','proj_mae','proj_corr']]),
'__UNKPROJ_TABLE__':df_tex(unkproj), '__G2_TABLE__':df_tex(g2[['area_mm2','centroid_x_mm','centroid_y_mm','mean_absorption','max_absorption','bbox_xmin_mm','bbox_xmax_mm','bbox_ymin_mm','bbox_ymax_mm']]),
'__G3_TABLE__':df_tex(g3[['area_mm2','centroid_x_mm','centroid_y_mm','mean_absorption','max_absorption','bbox_xmin_mm','bbox_xmax_mm','bbox_ymin_mm','bbox_ymax_mm']]),
'__SENS_TABLE__':df_tex(sens), '__NEWT_TABLE__':df_tex(newt), '__MATCH_TABLE__':df_tex(match.head(24))
}
tex=r'''
\documentclass[UTF8,a4paper,12pt]{ctexart}
\usepackage{geometry}
\geometry{left=2.45cm,right=2.45cm,top=2.55cm,bottom=2.45cm}
\usepackage{amsmath,amssymb,bm,graphicx,booktabs,longtable,float,array,caption,fancyhdr,setspace,tocloft,enumitem,hyperref}
\setstretch{1.45}
\setlength{\headheight}{15pt}
\pagestyle{fancy}\fancyhf{}\lhead{2017A CT系统参数标定及成像应用}\rhead{返工版}\cfoot{\thepage}
\captionsetup{font=small,labelsep=quad}
\setcounter{tocdepth}{1}
\renewcommand{\contentsname}{目录}
\begin{document}
\begin{center}
{\heiti\zihao{2} 基于逐投影几何校正与滤波反投影的CT系统参数标定及成像应用}\par
\vspace{0.6cm}
{\zihao{4} 2017A 数学建模返工版}\par
\end{center}

\begin{abstract}
针对2017年高教社杯全国大学生数学建模竞赛A题，本文重新建立了可验证的CT系统参数标定与成像模型。旧的直接反投影方法没有让标定参数进入重建链，模板回代误差较大；返工版首先以附件1模板为已知吸收率函数，计算其Radon理论投影，再以附件2实测投影为目标，联合标定角度零点、角度步长和探测器尺度，并对每一列投影估计独立的探测器中心偏移，形成“角度--尺度--逐投影shift”的校正模型。标定结果为：角度序列
\(\theta_j=__THETA0__^\circ+(j-1)\times __STEP__^\circ\)，探测器尺度为__SCALE__ cell/radon-pixel，等价探测器间距为__DPIX__像素，即__DMM__ mm；模板投影匹配平均相关系数达到__CORR__。

在该标定参数下，本文将附件2、3、5的512探测器投影统一映射回模板Radon坐标，再采用Shepp--Logan滤波反投影重建。模板回代验证显示，baseline直接FBP的RMSE为__BASE_RMSE__、SSIM为__BASE_SSIM__；返工主模型的MAE为__MAIN_MAE__、RMSE为__MAIN_RMSE__、SSIM为__MAIN_SSIM__，投影回代RMSE为__PROJ_RMSE__、相关系数为__PROJ_CORR__，说明标定参数已真实进入重建并显著改善结果。问题二10个指定点吸收率依次为__P2VALS__；问题三10个指定点吸收率依次为__P3VALS__。本文同时输出返工版\texttt{problem2\_rework.xls}、\texttt{problem3\_rework.xls}和支撑材料中的完整xlsx矩阵。

针对标定稳定性，本文对初始角和探测器尺度进行扰动，报告RMSE和SSIM变化，并设计由非中心圆盘、环形薄边、多方向条纹和灰度阶梯块组成的新模板。模拟投影剖面距离显示，新模板可提高不同角度投影的可区分度，从而改善角度和尺度标定的可辨识性。
\end{abstract}
\noindent\textbf{关键词：} CT参数标定；Radon变换；逐投影shift校正；滤波反投影；投影回代验证
\clearpage
\tableofcontents
\clearpage

\section{问题重述}
CT系统通过射线穿过介质后的衰减信息恢复内部结构。二维平行束CT中，一个角度下探测器阵列记录的是吸收率函数沿一组平行直线的积分，多个角度的投影共同构成sinogram。若旋转中心、探测器间距和射线方向准确，则可以通过反投影或迭代重建获得介质吸收率；若安装误差存在，则图像会出现位移、尺度变形和伪影。

本题给出一个已知模板的吸收率矩阵附件1及其接收信息附件2，要求标定CT系统旋转中心、探测器单元间距和180个射线方向。随后利用同一系统得到的附件3、附件5接收信息重建两个未知介质，并给出附件4中10个位置处的吸收率。最后需要分析标定精度和稳定性，并自行设计新模板以改进标定质量。

\section{问题分析}
本题的关键不是单纯使用库函数做反投影，而是让由模板得到的系统几何参数真实进入未知介质重建。若直接把512×180接收矩阵送入默认\texttt{iradon}，等价于假设探测器中心、尺度和角度均理想，这会忽略题目要求标定的核心参数。返工版因此将问题拆为三层：第一层，用模板Radon理论投影解释附件2；第二层，利用标定得到的角度、尺度和逐投影shift校正附件3、附件5；第三层，通过模板回代和未知投影回代检验结果。

问题一属于参数估计问题。本文将待估参数分为全局参数和逐投影参数：全局参数包括角度零点\(\theta_0\)、角度步长\(\Delta\theta\)、探测器尺度\(\lambda\)；逐投影参数为每列接收信息的探测器中心偏移\(b_j\)。问题二、三属于图像反演问题，在标定后的统一Radon坐标中用滤波反投影求解。问题四属于稳定性与实验设计问题，需要同时考察模型误差、参数扰动和模板可辨识性。

\section{数据审计、假设与符号}
附件1为256×256模板吸收率矩阵；附件2、附件3、附件5均为512×180接收矩阵；附件4为10个物理坐标点。托盘边长按题图单位取100 mm，因此像素尺寸为\(100/256=0.390625\) mm。本文保留原始数据，所有返工输出写入\texttt{支撑材料\_返工版}，并将关键数字冻结到\texttt{frozen\_numbers\_rework.json}。

基本假设如下：1）系统为平行束CT，探测器等距排列；2）模板和未知介质在扫描过程中固定不动；3）接收值与线积分经线性增益和偏置近似相关；4）附件2、3、5由同一套系统几何参数产生，因此未知介质不得重新调参；5）FBP产生的少量负值为数值振铃，最终吸收率取非负。

\begin{table}[H]\centering\caption{主要符号说明}\begin{tabular}{lll}\toprule
符号&含义&说明\\\midrule
\(f(x,y)\)&吸收率分布&二维图像函数\\
\(p_j(s)\)&第\(j\)个角度的投影&512探测器接收序列\\
\(\theta_0,\Delta\theta\)&角度零点与步长&全局标定参数\\
\(\lambda\)&探测器尺度&cell/radon-pixel\\
\(b_j\)&第\(j\)列探测器中心偏移&逐投影校正参数\\
\(\hat f\)&重建吸收率矩阵&256×256\\\bottomrule
\end{tabular}\end{table}

\section{问题一模型建立与参数标定}
\subsection{Radon投影模型}
设旋转中心坐标系下的射线方程为
\begin{equation}
(x-x_0)\cos\theta_j+(y-y_0)\sin\theta_j=s_i,
\end{equation}
则理想投影为
\begin{equation}
p_j(s)=R_{\theta_j}f(s)=\iint f(x,y)\delta((x-x_0)\cos\theta_j+(y-y_0)\sin\theta_j-s)\,dxdy.
\end{equation}
附件1模板\(f_0\)已知，因此可以计算任意候选角度下的理论Radon剖面。由于题目探测器有512个单元，而256×256模板Radon变换的自然detector长度为363，必须标定二者坐标映射。

\subsection{角度--尺度--逐投影shift联合标定}
令第\(j\)列角度为
\begin{equation}
\theta_j=\theta_0+j\Delta\theta,\quad j=0,1,\ldots,179.
\end{equation}
若模板Radon坐标为\(u\)，512探测器中心化坐标为\(c_i=i-255.5\)，则映射关系写成
\begin{equation}
c_i=\lambda u+b_j.
\end{equation}
给定\(\theta_0,\Delta\theta,\lambda\)后，对每一列用互相关求最优\(b_j\)，目标为最大化平均标准化相关系数：
\begin{equation}
\max_{\theta_0,\Delta\theta,\lambda,\{b_j\}}\frac1{180}\sum_{j=0}^{179}\rho\left(y_j,\,\mathcal I_{\lambda,b_j}(R_{\theta_j}f_0)\right).
\end{equation}
本文先做粗网格搜索，再用Nelder--Mead局部优化，最后对180列逐列求shift。得到\(\theta_0=__THETA0__^\circ\)、\(\Delta\theta=__STEP__^\circ\)、\(\lambda=__SCALE__\)，平均相关系数为__CORR__。探测器间距为\(1/\lambda=__DPIX__\)像素，即__DMM__ mm。

\begin{figure}[H]\centering\includegraphics[width=.82\textwidth]{figs/angle_sequence_rework.png}\caption{返工版180个射线方向标定结果}\end{figure}
\begin{figure}[H]\centering\includegraphics[width=.82\textwidth]{figs/detector_shift_sequence.png}\caption{逐投影探测器中心偏移校正序列}\end{figure}
图1说明角度序列近似线性递增但零点约为30度；图2说明探测器偏移并非常数，其均值为__SHIFTMEAN__ cell、标准差为__SHIFTSTD__ cell。返工版不再把中心偏移压缩为一个未使用的旋转中心数字，而是直接把\(b_j\)用于每列sinogram校正。

\subsection{标定结果局部明细}
\begin{table}[H]\centering\caption{前24列投影匹配结果}\resizebox{\textwidth}{!}{__MATCH_TABLE__}\end{table}
表2显示前若干列匹配相关系数接近1，说明模板理论投影能够较好解释附件2。与旧版不同，返工版保存完整180列匹配表，后续未知介质重建直接复用这些参数。

\section{问题二和问题三的重建模型}
\subsection{校正sinogram}
对任意原始接收矩阵\(Y\)，返工版按标定参数将512探测器数据映射回模板Radon坐标：
\begin{equation}
\tilde Y(u,j)=Y(\lambda u+b_j,j).
\end{equation}
该式是本次返工的核心：角度、尺度和逐投影shift都进入实际数据处理链。之后对\(\tilde Y\)使用Shepp--Logan滤波反投影：
\begin{equation}
\hat f(x,y)=\int_0^\pi [\tilde p_\theta(s)*h_{SL}(s)]_{s=x\cos\theta+y\sin\theta}\,d\theta.
\end{equation}
幅值标定使用模板回代重建与附件1之间的线性回归，得到统一的\(a,b\)，未知介质统一使用同一幅值映射并取非负。

\subsection{问题二结果}
\begin{figure}[H]\centering\includegraphics[width=.72\textwidth]{figs/problem2_reconstruction_rework.png}\caption{返工版问题二未知介质重建图}\end{figure}
问题二重建图显示介质主要位于中上部及中部区域，低吸收背景被明显压低。与旧版相比，返工版减少了“整幅图大面积非零”的扩散现象。主要连通组件见表3。
\begin{table}[H]\centering\caption{问题二主要连通组件几何信息}\resizebox{\textwidth}{!}{__G2_TABLE__}\end{table}

\subsection{问题三结果}
\begin{figure}[H]\centering\includegraphics[width=.72\textwidth]{figs/problem3_reconstruction_rework.png}\caption{返工版问题三未知介质重建图}\end{figure}
问题三投影强度明显高于问题二，重建结果呈现多个高吸收区域。由于问题三吸收率范围较宽，本文在解释时同时报告点值、连通域均值和投影回代残差，而不只依据视觉图像判断形状。
\begin{table}[H]\centering\caption{问题三主要连通组件几何信息}\resizebox{\textwidth}{!}{__G3_TABLE__}\end{table}

\subsection{10个指定点吸收率}
\begin{table}[H]\centering\caption{附件4指定位置吸收率返工版结果}__PT_TABLE__\end{table}
表5为题目第二、三问指定点的直接数值答案。问题二中第4、5、6、7点较高，说明这些点位于主体介质内；第1、9点接近背景。问题三中第3、7、9点较高，体现其内部吸收率非均匀性更强。

\section{模型检验与对比}
\subsection{模板重建对比}
\begin{table}[H]\centering\caption{模板重建误差：baseline与返工主模型对比}\resizebox{\textwidth}{!}{__METRICS_TABLE__}\end{table}
表6表明，直接512探测器FBP的RMSE约为__BASE_RMSE__、SSIM约为__BASE_SSIM__；返工主模型的RMSE降至__MAIN_RMSE__、SSIM提升至__MAIN_SSIM__。这说明几何校正不是论文装饰，而是真正改善了模板重建。
\begin{figure}[H]\centering\includegraphics[width=.78\textwidth]{figs/baseline_comparison_rmse.png}\caption{baseline与返工模型模板RMSE对比}\end{figure}
\begin{figure}[H]\centering\includegraphics[width=.72\textwidth]{figs/template_reconstruction_rework.png}\caption{返工版模板回代重建图}\end{figure}

\subsection{投影回代检验}
\begin{table}[H]\centering\caption{附件2模板投影回代误差}\resizebox{\textwidth}{!}{__PROJ_TABLE__}\end{table}
主模型投影回代RMSE为__PROJ_RMSE__，MAE为__PROJ_MAE__，相关系数为__PROJ_CORR__。投影回代检验比单纯图像相似度更直接，因为它检查\(A\hat f\)是否能重新解释原始接收信息。

\begin{table}[H]\centering\caption{未知介质投影回代误差}__UNKPROJ_TABLE__\end{table}
表8说明，问题二、三重建图重新投影后与原始接收矩阵具有较高相关系数。问题三RMSE较大，主要是因为其投影值尺度更高、内部高吸收区域更强，后续可用TV正则或显式系统矩阵迭代法改进。

\subsection{灵敏度分析}
\begin{table}[H]\centering\caption{返工版参数扰动灵敏度分析}__SENS_TABLE__\end{table}
\begin{figure}[H]\centering\includegraphics[width=.78\textwidth]{figs/sensitivity_rework.png}\caption{返工版参数扰动RMSE曲线}\end{figure}
灵敏度结果用于判断参数附近的误差变化。与旧版不同，本文不把所有扰动都解释为“更稳定”；若扰动后误差接近或略有改善，说明模型仍存在局部非凸和离散采样误差，应在论文中诚实说明。这也是问题四需要改进模板的原因。

\section{问题四：新模板设计}
当前模板由少数均匀介质组成，部分角度投影相似，导致角度与shift估计仍有局部歧义。本文设计新模板：非中心大圆盘提供稳定强峰，环形薄边提供尖锐边缘，多方向矩形条降低角度歧义，灰度阶梯块分离几何误差与增益误差。
\begin{figure}[H]\centering\includegraphics[width=.70\textwidth]{figs/new_template_design.png}\caption{返工版新模板设计示意图}\end{figure}
为量化可辨识性，本文比较不同角度标准化投影剖面的两两距离。距离越大，说明不同角度越不容易混淆。
\begin{table}[H]\centering\caption{原模板与新模板投影可辨识性对比}__NEWT_TABLE__\end{table}
表10表明，新模板在低分位和平均投影剖面距离上具有更强区分度，可用于提高角度零点和探测器尺度估计的稳定性。

\section{模型评价与改进}
返工版的优点是：第一，标定参数真实进入sinogram校正与重建链；第二，给出了baseline对比、模板回代和投影回代三类证据；第三，所有关键结果均保存为CSV/JSON/xlsx/xls文件，便于复现。局限是：逐投影shift是经验校正序列，尚未完全等价于机械旋转中心的解析参数；FBP仍可能有振铃和边缘过冲；问题三高吸收区域的定量精度仍受幅值线性标定影响。

后续改进方向包括：构造显式系统矩阵，将\(\theta_0,\Delta\theta,\lambda,b_j\)纳入ART/SART或TV正则重建；用新模板重新采集或模拟投影，联合估计中心、尺度、角度和增益；对指定点吸收率使用bootstrap或噪声扰动给出置信区间。

\section{结论}
本文完成2017A返工版建模。主要结果为：1）射线方向\(\theta_j=__THETA0__^\circ+(j-1)__STEP__^\circ\)，探测器间距__DPIX__像素即__DMM__ mm，模板匹配平均相关系数__CORR__；2）返工主模型模板RMSE由baseline的__BASE_RMSE__降至__MAIN_RMSE__，SSIM由__BASE_SSIM__升至__MAIN_SSIM__，投影回代相关系数__PROJ_CORR__；3）问题二和问题三的10点吸收率分别为__P2VALS__和__P3VALS__，完整矩阵已保存；4）新模板模拟显示多特征非对称结构可提高角度投影可辨识性。

\clearpage
\section*{参考文献}\addcontentsline{toc}{section}{参考文献}
\begin{enumerate}[label={[\arabic*]}]
\item Kak A C, Slaney M. Principles of Computerized Tomographic Imaging[M]. IEEE Press, 1988.
\item Natterer F. The Mathematics of Computerized Tomography[M]. SIAM, 2001.
\item scikit-image developers. Radon transform and inverse Radon transform documentation[EB/OL].
\item Gonzalez R C, Woods R E. Digital Image Processing[M]. Pearson, 2018.
\item 全国大学生数学建模竞赛组委会. 2017年高教社杯全国大学生数学建模竞赛A题[Z]. 2017.
\end{enumerate}

\appendix
\section{附录A：支撑材料说明}
返工版支撑材料位于\texttt{支撑材料\_返工版}。其中\texttt{code/main\_rework.py}为完整求解脚本，\texttt{paper/论文.tex}和\texttt{paper/论文.pdf}为正式论文源文件与PDF，\texttt{results/frozen\_numbers\_rework.json}为冻结数字，\texttt{results/problem2.xls}和\texttt{results/problem3.xls}为真实Excel格式结果矩阵，\texttt{verification/verify\_outputs.py}用于核验输出文件。

\section{附录B：算法流程}
1. 读取附件1--5并审计维度；2. 计算模板Radon理论投影；3. 粗网格搜索\(\theta_0,\Delta\theta,\lambda\)，每列用互相关求\(b_j\)；4. 将512探测器数据映射到363长度Radon坐标；5. 用Shepp--Logan FBP重建模板、问题二和问题三；6. 用模板回归幅值标定；7. 计算10点吸收率、连通域、投影回代误差和灵敏度；8. 生成论文、图表和压缩包。

\end{document}
'''
for k,v in repl.items(): tex=tex.replace(k,v)
tex_path=BUILD/'论文.tex'
tex_path.write_text(tex,encoding='utf-8')
# compile 3 times
for i in range(3):
    r=subprocess.run(['xelatex','-interaction=nonstopmode','论文.tex'],cwd=str(BUILD),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    (BUILD/f'xelatex_{i+1}.log.txt').write_text(r.stdout,encoding='utf-8',errors='ignore')
    if r.returncode!=0:
        print(r.stdout[-4000:]); raise SystemExit(r.returncode)
# copy
shutil.copy2(BUILD/'论文.pdf', SUP/'paper/论文.pdf')
shutil.copy2(BUILD/'论文.tex', SUP/'paper/论文.tex')
# complete md source (plain extract-ish)
(SUP/'paper/论文.md').write_text('返工版正式论文源文件为 paper/论文.tex；PDF为 paper/论文.pdf。本文所有关键数字来自 results/frozen_numbers_rework.json 与 tables/*.csv。',encoding='utf-8')
print(SUP/'paper/论文.pdf')
