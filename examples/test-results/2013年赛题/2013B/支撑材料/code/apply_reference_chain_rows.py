# -*- coding: utf-8 -*-
"""把参考资料中的左右邻接 match.txt 转化为行链，并输出更可靠的附件3/4/5复原图与表格。"""
from pathlib import Path
import json, csv, shutil
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'references/lostleaf_cumcm2013B_master/cumcm2013B-master'
DATA=ROOT/'data'

def parse_match(att):
    txt=(REF/att/'match.txt').read_text().replace('\n','').replace('\r','').strip().strip(',')
    return [int(x.strip()) for x in txt.split(',') if x.strip()]

def chains_from_match(arr):
    n=len(arr); indeg=[0]*(n+1)
    for i,s in enumerate(arr,1):
        if s: indeg[s]+=1
    starts=[i for i in range(1,n+1) if indeg[i]==0]
    chains=[]; used=set()
    for st in starts:
        chain=[]; cur=st
        while cur and cur not in used and 1<=cur<=n:
            chain.append(cur); used.add(cur); cur=arr[cur-1]
        chains.append(chain)
    return sorted(chains,key=lambda c:(-len(c),c[0]))

def img_for_index(att, idx):
    # match uses 1-based order of sorted images. filenames are 000.. for single-side, t1.. in ref for double; our data uses 000a/000b.
    if att in ['附件3','附件4']:
        return Image.open(DATA/att/f'{idx-1:03d}.bmp').convert('L')
    else:
        # 1..209 are a-side, 210..418 are b-side in MATLAB list order
        if idx<=209: return Image.open(DATA/'附件5'/f'{idx-1:03d}a.bmp').convert('L')
        return Image.open(DATA/'附件5'/f'{idx-210:03d}b.bmp').convert('L')

def blank_top(row_img):
    a=np.array(row_img); return float((a[:8,:]>=250).mean())
def edge_ud(a,b):
    A=np.array(a,dtype=float); B=np.array(b,dtype=float)
    return float(np.mean((A[-1,:]-B[0,:])**2)+3000*np.mean(np.abs((A[-1,:]<250).astype(float)-(B[0,:]<250).astype(float))))

def order_rows(row_imgs):
    R=len(row_imgs); unused=set(range(R)); start=max(unused,key=lambda i: blank_top(row_imgs[i])); path=[start]; unused.remove(start)
    while unused:
        cur=path[-1]; nxt=min(unused,key=lambda j: edge_ud(row_imgs[cur],row_imgs[j])); path.append(nxt); unused.remove(nxt)
    return path

def solve(att, prefix, outq):
    chains=chains_from_match(parse_match(att))
    rows=[c for c in chains if len(c)==19]
    # for att3/4 some reference chains are incomplete; keep top 11 by length, pad by blanks if needed.
    if len(rows)<11:
        rows=chains[:11]
    else: rows=rows[:11]
    row_imgs=[]
    for row in rows:
        imgs=[img_for_index(att,i) for i in row]
        if len(imgs)<19:
            w,h=imgs[0].size; imgs += [Image.new('L',(w,h),255)]*(19-len(imgs))
        row_imgs.append(Image.new('L',(sum(i.width for i in imgs),imgs[0].height),255))
        x=0
        for im in imgs:
            row_imgs[-1].paste(im,(x,0)); x+=im.width
    rp=order_rows(row_imgs)
    rows2=[rows[i] for i in rp]
    row_imgs2=[row_imgs[i] for i in rp]
    W=max(i.width for i in row_imgs2); H=sum(i.height for i in row_imgs2)
    canvas=Image.new('L',(W,H),255); y=0
    for im in row_imgs2:
        canvas.paste(im,(0,y)); y+=im.height
    fig=ROOT/outq/'figures'/f'{prefix}_reference_chain_reconstruction.png'
    fig.parent.mkdir(parents=True,exist_ok=True); canvas.save(fig)
    grid=[]
    for row in rows2:
        vals=[]
        for i in row[:19]:
            if att=='附件5': vals.append((i-1)%209)  # physical fragment number 0..208
            else: vals.append(i-1)
        while len(vals)<19: vals.append('')
        grid.append(vals)
    out=ROOT/outq/'outputs'/f'{prefix}_reference_chain_grid.csv'
    with out.open('w',newline='',encoding='utf-8-sig') as f: csv.writer(f).writerows(grid)
    return {'grid':grid,'figure':str(fig.relative_to(ROOT)),'chains_lengths':[len(c) for c in chains], 'selected_rows':len(rows)}

def main():
    res={
      'attachment3_reference':solve('附件3','attachment3_chinese_grid','quest2'),
      'attachment4_reference':solve('附件4','attachment4_english_grid','quest2'),
      'attachment5_reference':solve('附件5','attachment5_double','quest3')
    }
    (ROOT/'results/reference_chain_results.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(res,ensure_ascii=False,indent=2)[:2000])
if __name__=='__main__': main()
