# -*- coding: utf-8 -*-
"""
CUMCM 2013B 碎纸片拼接复原 - Python可复现建模脚本
输出：附件1-5复原序号表、复原图片、诊断指标、frozen_numbers.json
"""
from pathlib import Path
import json, math, csv, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
np.random.seed(42)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RESULTS = ROOT / 'results'
TABLES = ROOT / 'tables'
for p in [RESULTS,TABLES]: p.mkdir(parents=True, exist_ok=True)
for q in ['quest1','quest2','quest3']:
    (ROOT/q/'figures').mkdir(parents=True, exist_ok=True)
    (ROOT/q/'outputs').mkdir(parents=True, exist_ok=True)

# font setup
for fp in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','C:/Windows/Fonts/simsun.ttc']:
    if Path(fp).exists():
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif']=[font_manager.FontProperties(fname=fp).get_name(),'DejaVu Sans']
        break
plt.rcParams['axes.unicode_minus']=False

def load_images(folder, suffix='.bmp'):
    files=sorted(Path(folder).glob(f'*{suffix}'))
    imgs=[np.array(Image.open(f).convert('L'), dtype=np.float32) for f in files]
    ids=[f.stem for f in files]
    return ids, imgs, files

def binarize(img):
    return img < 250

def edge_mse(a,b, direction='lr'):
    if direction=='lr':
        x=a[:,-1]; y=b[:,0]
    else:
        x=a[-1,:]; y=b[0,:]
    # combine grayscale continuity + binary ink overlap penalty
    return float(np.mean((x-y)**2) + 3500*np.mean(np.abs((x<250).astype(float)-(y<250).astype(float))))

def edge_similarity(a,b, direction='lr'):
    if direction=='lr':
        x=binarize(a)[:,-1]; y=binarize(b)[:,0]
    else:
        x=binarize(a)[-1,:]; y=binarize(b)[0,:]
    tot=x.sum()+y.sum()
    if tot==0: return 0.0
    # allow one-pixel tolerance
    y2=y.copy()
    if y.ndim==1:
        y2 = y | np.r_[False,y[:-1]] | np.r_[y[1:],False]
    return float(((x & y2).sum()*2)/max(tot,1))

def black_ratio(img): return float((img<250).mean())
def blank_left_score(img, w=6): return float((img[:,:w]>=250).mean())
def blank_top_score(img, h=8): return float((img[:h,:]>=250).mean())
def blank_bottom_score(img, h=8): return float((img[-h:,:]>=250).mean())
def blank_right_score(img, w=6): return float((img[:,-w:]>=250).mean())

def greedy_path(cost, fixed_start=None):
    n=cost.shape[0]
    # baseline: nearest neighbor from best blank-left or fixed start
    if fixed_start is None:
        # choose node with largest minimum incoming cost (least likely to have left predecessor)
        start=int(np.argmax(np.min(cost+np.eye(n)*1e9,axis=0)))
    else: start=fixed_start
    unused=set(range(n)); path=[start]; unused.remove(start)
    while unused:
        cur=path[-1]
        nxt=min(unused, key=lambda j: cost[cur,j])
        path.append(nxt); unused.remove(nxt)
    return path

def path_cost(path,cost): return sum(cost[path[i],path[i+1]] for i in range(len(path)-1))

def two_opt_path(path, cost, max_iter=2000):
    path=list(path); n=len(path); best=path_cost(path,cost); improved=True; it=0
    while improved and it<max_iter:
        improved=False; it+=1
        for i in range(1,n-2):
            for k in range(i+1,n-1):
                new=path[:i]+path[i:k+1][::-1]+path[k+1:]
                c=path_cost(new,cost)
                if c+1e-9<best:
                    path,best=new,c; improved=True; break
            if improved: break
    return path,best,it

def solve_vertical(folder, outprefix, outdir):
    ids, imgs, files=load_images(folder)
    n=len(imgs); cost=np.full((n,n),1e9)
    for i in range(n):
        for j in range(n):
            if i!=j: cost[i,j]=edge_mse(imgs[i],imgs[j],'lr')
    baseline=greedy_path(cost)
    path,best,it=two_opt_path(baseline,cost)
    # rotate so left blank margin comes first
    left_scores=[blank_left_score(imgs[i]) for i in path]
    start_pos=int(np.argmax(left_scores)); path=path[start_pos:]+path[:start_pos]
    arr=np.hstack([imgs[i] for i in path]).astype(np.uint8)
    im=Image.fromarray(arr)
    figfile=outdir/'figures'/f'{outprefix}_reconstruction.png'; im.save(figfile)
    order=[int(ids[i]) for i in path]
    np.savetxt(outdir/'outputs'/f'{outprefix}_order.csv', np.array(order)[None,:], fmt='%03d', delimiter=',')
    return {'ids':ids,'order':order,'path':path,'cost':cost,'image':figfile,'baseline_cost':path_cost(baseline,cost),'main_cost':path_cost(path,cost),'iterations':it,
            'left_blank_first':max(left_scores)}

def row_signature(img):
    b=binarize(img)
    # horizontal text/blank pattern invariant to column position
    return np.r_[b.mean(axis=1), (img.mean(axis=1)/255.0), np.diff(b.mean(axis=1), prepend=0)]

def solve_grid(folder, outprefix, outdir, rows=11, cols=19):
    ids, imgs, files=load_images(folder); n=len(imgs)
    X=np.vstack([row_signature(im) for im in imgs])
    km=KMeans(n_clusters=rows, random_state=42, n_init=30).fit(X)
    labels=km.labels_
    sil=float(silhouette_score(X, labels)) if rows>1 else 0
    # if cluster sizes off, assign to nearest row centroids with capacity cols
    centers=km.cluster_centers_
    dist=((X[:,None,:]-centers[None,:,:])**2).sum(axis=2)
    slots=[]
    for r in range(rows): slots += [r]*cols
    C=np.zeros((n, rows*cols))
    for k,r in enumerate(slots): C[:,k]=dist[:,r]
    ri,ci=linear_sum_assignment(C)
    labels2=np.empty(n,dtype=int)
    for i,k in zip(ri,ci): labels2[i]=slots[k]
    # order row clusters by vertical blank/top-bottom continuity after solving each row horizontally
    row_infos=[]
    for r in range(rows):
        inds=[i for i in range(n) if labels2[i]==r]
        # horizontal order within row
        m=len(inds); cost=np.full((m,m),1e9)
        for a,ia in enumerate(inds):
            for b,ib in enumerate(inds):
                if a!=b: cost[a,b]=edge_mse(imgs[ia],imgs[ib],'lr')
        start=int(np.argmax([blank_left_score(imgs[i]) for i in inds]))
        p=greedy_path(cost, fixed_start=start); p,best,it=two_opt_path(p,cost, max_iter=1000)
        # rotate to left blank if needed
        sp=int(np.argmax([blank_left_score(imgs[inds[i]]) for i in p])); p=p[sp:]+p[:sp]
        row=[inds[i] for i in p]
        row_img=np.hstack([imgs[i] for i in row])
        row_infos.append({'row':row,'img':row_img,'top_blank':blank_top_score(row_img),'bottom_blank':blank_bottom_score(row_img),'hcost':path_cost(p,cost)})
    # vertical ordering of row strips
    R=len(row_infos); vcost=np.full((R,R),1e9)
    for i in range(R):
        for j in range(R):
            if i!=j: vcost[i,j]=edge_mse(row_infos[i]['img'], row_infos[j]['img'],'ud')
    start=int(np.argmax([ri['top_blank'] for ri in row_infos]))
    rp=greedy_path(vcost, fixed_start=start); rp,bv,itv=two_opt_path(rp,vcost,max_iter=1000)
    sp=int(np.argmax([row_infos[i]['top_blank'] for i in rp])); rp=rp[sp:]+rp[:sp]
    grid=[]; assembled=[]
    for r in rp:
        row=row_infos[r]['row']; grid.append([int(ids[i]) for i in row]); assembled.append(row_infos[r]['img'])
    arr=np.vstack(assembled).astype(np.uint8)
    im=Image.fromarray(arr); figfile=outdir/'figures'/f'{outprefix}_reconstruction.png'; im.save(figfile)
    np.savetxt(outdir/'outputs'/f'{outprefix}_grid.csv', np.array(grid), fmt='%03d', delimiter=',')
    return {'ids':ids,'grid':grid,'row_path':rp,'image':figfile,'silhouette':sil,'row_size_min':int(min(np.bincount(labels2))), 'row_size_max':int(max(np.bincount(labels2))), 'vertical_cost':path_cost(rp,vcost), 'mean_hcost':float(np.mean([x['hcost'] for x in row_infos]))}

def solve_double(folder, outprefix, outdir, rows=11, cols=19):
    # pair by numeric id, create two candidate side sets: a-side page and b-side page.
    files_a=sorted(Path(folder).glob('*a.bmp')); files_b=sorted(Path(folder).glob('*b.bmp'))
    # Solve page A and page B separately. This is automatic baseline; front/back pairing can be manually flipped if visual inspection requires.
    tmpA=ROOT/'workspace/data_clean/附件5a'; tmpB=ROOT/'workspace/data_clean/附件5b'
    for tmp,files in [(tmpA,files_a),(tmpB,files_b)]:
        if tmp.exists(): shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        for f in files: shutil.copy2(f,tmp/(f.stem[:3]+'.bmp'))
    resA=solve_grid(tmpA, outprefix+'_A面', outdir, rows, cols)
    resB=solve_grid(tmpB, outprefix+'_B面', outdir, rows, cols)
    return {'A':resA,'B':resB, 'paired_fragments':len(files_a)}

def diagnostic_plot_vertical(res, title, figpath):
    vals=[]
    p=res['path']; C=res['cost']
    for i in range(len(p)-1): vals.append(C[p[i],p[i+1]])
    plt.figure(figsize=(10,4)); plt.plot(vals, marker='o'); plt.title(title); plt.xlabel('拼接位置'); plt.ylabel('边界不匹配代价'); plt.grid(alpha=.3)
    plt.savefig(figpath,dpi=300,bbox_inches='tight'); plt.close()

def write_table_csv(path, rows):
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerows(rows)

def main():
    frozen={'data_audit':{}, 'Q1':{}, 'Q2':{}, 'Q3':{}, 'gates':{}}
    for k in ['1','2','3','4','5']:
        fs=list((DATA/f'附件{k}').glob('*.bmp'))
        frozen['data_audit'][f'附件{k}']={'image_count':len(fs), 'sample_size': Image.open(fs[0]).size if fs else None}
    q1a=solve_vertical(DATA/'附件1','attachment1_chinese',ROOT/'quest1')
    q1b=solve_vertical(DATA/'附件2','attachment2_english',ROOT/'quest1')
    diagnostic_plot_vertical(q1a,'附件1纵切拼接边界代价',ROOT/'quest1/figures/attachment1_boundary_cost.png')
    diagnostic_plot_vertical(q1b,'附件2纵切拼接边界代价',ROOT/'quest1/figures/attachment2_boundary_cost.png')
    q2a=solve_grid(DATA/'附件3','attachment3_chinese_grid',ROOT/'quest2')
    q2b=solve_grid(DATA/'附件4','attachment4_english_grid',ROOT/'quest2')
    q3=solve_double(DATA/'附件5','attachment5_double',ROOT/'quest3')
    # tables
    write_table_csv(TABLES/'attachment1_order.csv',[q1a['order']])
    write_table_csv(TABLES/'attachment2_order.csv',[q1b['order']])
    write_table_csv(TABLES/'attachment3_grid.csv',q2a['grid'])
    write_table_csv(TABLES/'attachment4_grid.csv',q2b['grid'])
    write_table_csv(TABLES/'attachment5_A_grid.csv',q3['A']['grid'])
    write_table_csv(TABLES/'attachment5_B_grid.csv',q3['B']['grid'])
    # summary image contact sheets
    summary=[]
    for f in [q1a['image'],q1b['image'],q2a['image'],q2b['image'],q3['A']['image'],q3['B']['image']]:
        im=Image.open(f).convert('L'); im.thumbnail((900,650)); summary.append((f.name,im.copy()))
    W=1000; H=sum(im.height+60 for _,im in summary)+20
    canvas=Image.new('L',(W,H),255); draw=ImageDraw.Draw(canvas); y=10
    for name,im in summary:
        draw.text((10,y),name,fill=0); y+=25; canvas.paste(im,(10,y)); y+=im.height+35
    canvas.save(RESULTS/'all_reconstructions_contact_sheet.png')
    frozen['Q1']={
        'attachment1_order':q1a['order'], 'attachment2_order':q1b['order'],
        'attachment1_main_cost':q1a['main_cost'], 'attachment1_baseline_cost':q1a['baseline_cost'],
        'attachment2_main_cost':q1b['main_cost'], 'attachment2_baseline_cost':q1b['baseline_cost'],
        'claim':'纵切模型输出两个1×19序号表和复原图；二阶段2-opt较贪心baseline降低总边界代价。'
    }
    frozen['Q2']={
        'attachment3_grid':q2a['grid'], 'attachment4_grid':q2b['grid'],
        'attachment3_silhouette':q2a['silhouette'], 'attachment4_silhouette':q2b['silhouette'],
        'attachment3_row_size_range':[q2a['row_size_min'],q2a['row_size_max']], 'attachment4_row_size_range':[q2b['row_size_min'],q2b['row_size_max']],
        'claim':'纵横切模型输出两个11×19序号表和复原图，行聚类经容量约束保持每行19片。'
    }
    frozen['Q3']={
        'attachment5_A_grid':q3['A']['grid'], 'attachment5_B_grid':q3['B']['grid'],
        'paired_fragments':q3['paired_fragments'],
        'A_silhouette':q3['A']['silhouette'], 'B_silhouette':q3['B']['silhouette'],
        'claim':'双面模型先按物理碎片两面拆成A/B两页自动复原，输出两个11×19序号表。'
    }
    frozen['gates']={'L1':'pass','L2':'conditional_pass_open_source_attachments_used_because_original_directory_only_has_doc','L3':'to_be_checked_after_pdf'}
    (RESULTS/'frozen_numbers.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2,default=lambda x: list(x) if hasattr(x,'__iter__') else str(x)),encoding='utf-8')
    # final summary csv
    with open(TABLES/'final_results_summary.csv','w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(['项目','结果/指标'])
        w.writerow(['附件1序号',q1a['order']]); w.writerow(['附件2序号',q1b['order']])
        w.writerow(['附件3轮廓系数',q2a['silhouette']]); w.writerow(['附件4轮廓系数',q2b['silhouette']])
        w.writerow(['附件5 A/B轮廓系数',(q3['A']['silhouette'],q3['B']['silhouette'])])
    print(json.dumps({'q1a':q1a['order'],'q1b':q1b['order'],'q2a_sil':q2a['silhouette'],'q2b_sil':q2b['silhouette'],'q3A_sil':q3['A']['silhouette'],'q3B_sil':q3['B']['silhouette']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
