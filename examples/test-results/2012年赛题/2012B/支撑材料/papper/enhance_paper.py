# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd, json
root=Path(r'<LOCAL_MATH_MODELING_TEST_ROOT>/2012年赛题/2012B')
sup=root/'支撑材料'; pap=sup/'papper'; tex=pap/'论文.tex'
text=tex.read_text(encoding='utf-8')
if 'setspace' not in text:
    text=text.replace('\\usepackage{geometry,graphicx,booktabs,longtable,array,amsmath,amssymb,float,fancyhdr,lastpage,caption,subcaption,xcolor,enumitem}', '\\usepackage{geometry,graphicx,booktabs,longtable,array,amsmath,amssymb,float,fancyhdr,lastpage,caption,subcaption,xcolor,enumitem,setspace}')
if '\\setstretch{1.32}' not in text:
    text=text.replace('\\renewcommand{\\arraystretch}{1.18}', '\\renewcommand{\\arraystretch}{1.18}\n\\setstretch{1.32}\n\\setlength{\\parskip}{0.25em}')

def esc(s):
    return str(s).replace('\\','/').replace('&','\\&').replace('%','\\%').replace('_','\\_').replace('#','\\#')
def fmt(v):
    try:
        f=float(v)
        if abs(f)>=100: return f'{f:.1f}'
        return f'{f:.3f}'.rstrip('0').rstrip('.')
    except Exception:
        return esc(v)

def simple_longtable(filename, cols, caption, label):
    df=pd.read_csv(sup/'tables'/filename)
    spec='l'+'r'*(len(cols)-1)
    out=['\\begin{center}\\small', f'\\begin{{longtable}}{{{spec}}}', f'\\caption{{{caption}}}\\label{{{label}}}\\\\', '\\toprule']
    out.append(' & '.join(esc(c) for c in cols)+'\\\\\\midrule')
    out.append('\\endfirsthead')
    out.append('\\toprule')
    out.append(' & '.join(esc(c) for c in cols)+'\\\\\\midrule')
    out.append('\\endhead')
    for _,r in df.iterrows():
        out.append(' & '.join(fmt(r[c]) for c in cols)+'\\\\')
    out += ['\\bottomrule', '\\end{longtable}\\end{center}']
    return '\n'.join(out)

fn=json.loads((sup/'results'/'frozen_numbers.json').read_text(encoding='utf-8'))
extra_data='''
\\subsection{数据清洗与候选集构造}
为避免模型建立阶段出现口径混乱，本文首先将附件3和附件5整理为结构化表格。附件3中组件价格按类型给出：A类单晶硅14.9元/Wp，B类多晶硅12.5元/Wp，C类薄膜4.8元/Wp。尺寸字段统一由毫米换算为平方米，开路电压和额定功率保留原单位。附件5中逆变器输入电压范围、额定功率、效率和价格被整理为约束表。清洗后的候选组件见表\\ref{tab:pvclean}，逆变器约束见表\\ref{tab:invclean}。这些表的作用不是简单展示数据，而是为后续整数规划提供面积、成本、功率、电压和启动阈值参数。
'''
extra_data += simple_longtable('光伏组件参数清洗表.csv',['型号','类型','功率W','面积m2','开路电压V','效率','价格元每Wp','启动阈值'],'光伏组件参数清洗与候选集','tab:pvclean')
extra_data += '\n' + simple_longtable('逆变器参数整理表.csv',['型号','下限V','上限V','额定功率kW','效率','价格元'],'逆变器参数整理与约束范围','tab:invclean')
extra_data += '''
由表中可以看出，晶硅组件的效率和单位面积功率普遍高于薄膜组件，但价格也显著更高；C类薄膜组件功率密度低，却具有较低启动阈值和较低价格。因此，如果目标只看年发电量，晶硅组件更容易入选；如果目标同时考虑全寿命单位电量费用，薄膜组件具有明显竞争力。这也解释了后文 baseline 与主模型的差异：baseline偏向高功率密度，而主模型偏向全寿命经济性。
'''
if '数据清洗与候选集构造' not in text:
    text=text.replace('\\subsection{模型假设}', extra_data+'\n\\subsection{模型假设}')

# area constraint table
rows=[]
for q in ['问题1','问题2','问题3']:
    df=pd.read_csv(sup/'tables'/f'{q}_铺设分组与逆变器.csv')
    house=fn['given_house'] if q in ['问题1','问题2'] else fn['designed_house']
    for surf,g in df.groupby('surface'):
        area=float((g['area']*g['数量']).sum()); usable=float(house['surfaces'][surf]['usable'])
        rows.append((q,surf,area,usable,usable-area,100*area/usable))
constraint='''\\begin{table}[H]\\centering\\caption{各方案表面面积约束核验}\\label{tab:areacheck}\\small
\\begin{tabular}{llrrrr}\\toprule
问题 & 表面 & 已铺面积/$m^2$ & 可铺面积/$m^2$ & 余量/$m^2$ & 利用率/\\%\\\\\\midrule
'''
for r in rows:
    constraint += f'{r[0]} & {r[1]} & {r[2]:.2f} & {r[3]:.2f} & {r[4]:.2f} & {r[5]:.1f}\\\\\n'
constraint += '\\bottomrule\\end{tabular}\\end{table}'
extra_model=f'''
\\subsection{{算法步骤与可复现流程}}
为使求解过程可审计，本文将模型实现拆为以下步骤。第一步，读取8760小时气象数据并按东、南、西、北和水平面方向统计逐时辐射强度；第二步，读取组件表并计算单块面积、单块投资和启动阈值；第三步，对每个“表面--组件”组合计算单块年发电量和35年边际净收益；第四步，在每个表面的可铺面积约束下求解整数规划，得到各表面各型号组件数量；第五步，枚举同型号组件的串联数和并联串数，检查串电压是否落入逆变器输入电压范围，并选择满足额定功率约束且价格最低的逆变器；第六步，删除在计入逆变器固定成本后净收益为负的零散分组；第七步，输出最终铺设表、图示、敏感性分析表和冻结数字文件。

该流程对应的伪代码如下：
\\begin{{enumerate}}[leftmargin=2em]
\\item 对每个表面$i$和组件$j$，根据逐时辐射$G_i(t)$计算$E_{{ij}}$；
\\item 计算边际净收益$b_{{ij}}=0.5TE_{{ij}}-C_j$；
\\item 求解$\\max\\sum b_{{ij}}x_{{ij}}$，约束为$\\sum_j a_jx_{{ij}}\\le A_i$且$x_{{ij}}$为非负整数；
\\item 对每个非零$x_{{ij}}$，枚举串联数$s$和并联数$p$，使$sV_j$满足逆变器输入范围，$spP_j$不超过逆变器容量；
\\item 计算总投资、35年发电量、收益、单位电量费用和回收期；
\\item 改变辐射强度扰动系数，重新计算经济指标并输出敏感性结果。
\\end{{enumerate}}

\\subsection{{面积、容量与连接约束核验}}
优化类问题不能只报告目标值，还必须检验方案是否满足现实约束。表\\ref{{tab:areacheck}}给出了各方案的表面面积使用情况。可以看到所有表面均满足已铺面积不超过可铺面积，且南墙和屋顶通常利用率较高，说明模型倾向优先使用辐射条件较好的南向表面。东西墙由于辐射峰值分别集中在上午和下午，模型在经济性允许时也会配置一定数量组件，以平衡日内发电分布。
{constraint}

逆变器约束方面，表中的“串联数、并联串数、串电压、组容量、逆变器型号”共同构成可实施连接方案。工程实施时可根据具体逆变器产品将大串进一步拆分为多个同电压子阵列，本文表格给出的是满足题目抽象约束的分组计算口径。
'''
if '算法步骤与可复现流程' not in text:
    text=text.replace('\\subsection{问题一：贴附安装求解结果}', extra_model+'\n\\subsection{问题一：贴附安装求解结果}')

full_tables='''
\\subsection{完整分组阵列结果}
正文前文给出了主要分组结果。为便于复核，下面列出三个问题的完整可执行分组表。表中每一行对应一个表面上的一个组件型号分组，包含数量、串并联方式、串电压、组容量、逆变器型号和年发电量。完整CSV文件同时保存在支撑材料\\verb|tables/|目录下。
'''
full_tables += simple_longtable('问题1_铺设分组与逆变器.csv',['surface','model','数量','串联数','并联串数','串电压V','组容量kW','逆变器','年发电量kWh'],'问题一完整分组阵列与逆变器结果','tab:q1full')
full_tables += simple_longtable('问题2_铺设分组与逆变器.csv',['surface','model','数量','串联数','并联串数','串电压V','组容量kW','逆变器','年发电量kWh'],'问题二完整分组阵列与逆变器结果','tab:q2full')
full_tables += simple_longtable('问题3_铺设分组与逆变器.csv',['surface','model','数量','串联数','并联串数','串电压V','组容量kW','逆变器','年发电量kWh'],'问题三完整分组阵列与逆变器结果','tab:q3full')
full_tables += '''
这些完整分组表显示，最终方案并未机械铺满所有边角面积，而是优先保留在计入逆变器成本后仍有正全寿命净收益的分组。若强行加入少量边角组件，虽然名义装机容量增加，但会因新增逆变器固定成本导致单位电量费用上升，因此不符合题目“单位发电量费用尽可能小”的要求。
'''
if '完整分组阵列结果' not in text:
    text=text.replace('\\section{补充计算表与实施说明}', full_tables+'\n\\section{补充计算表与实施说明}')

more_eval='''
\\subsection{参数来源与误差来源讨论}
本文经济性结果主要受三类参数影响。第一类是辐射数据。附件4为典型气象年，能够反映大同地区一般气候条件，但不能代表每一年的真实天气，因此本文用$\\pm20\\%$辐射扰动分析外推风险。第二类是组件性能。题目给出的额定功率是在标准测试条件下测得，实际运行会受到温度、灰尘、遮挡、线损和逆变器效率影响；本文用0.92线损修正和逆变器效率进行折减，但未引入逐时温度模型。第三类是价格和电价。组件价格、逆变器价格和0.5元/kWh电价均按题目静态值计算，未考虑折现率、设备维护费和逆变器中途更换成本，因此回收期属于静态回收期。

从误差传播角度看，辐射强度和线损系数会近似按比例影响年发电量，进而影响35年收益和回收期；组件价格和逆变器价格则直接影响总投资，对单位电量费用影响较大。由于最终方案大量采用低成本C类组件，组件价格扰动对净收益的影响相对可控；但如果未来薄膜组件价格上升或晶硅组件价格下降，最优型号可能发生变化。因此本文的方案更适合作为在题目给定价格体系下的最优设计，而不是对所有市场情景的永久结论。

\\subsection{与题目目标的对应关系}
题目同时提出“全年发电总量尽可能大”和“单位发电量费用尽可能小”。二者存在冲突：高效率晶硅组件能显著增加发电量，但投资额也更高；薄膜组件发电量相对较低，但单位成本低、启动阈值低，具有较好经济性。本文没有把问题简化成单目标最大大发电量，而是通过baseline对比说明：单纯追求发电量的baseline年发电量更高，但单位电量费用也更高；主模型发电量较低，但单位电量费用下降明显，且净收益更优。这样的结果更符合题目对双目标的综合要求。
'''
if '参数来源与误差来源讨论' not in text:
    text=text.replace('\\section{模型评价、改进与推广}', more_eval+'\n\\section{模型评价、改进与推广}')

tex.write_text(text,encoding='utf-8')
print('enhanced tex lines',len(text.splitlines()))
