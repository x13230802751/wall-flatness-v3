# 运行合成场景和真实房间的四点选区示例，保存测量及参数敏感性结果。
"""Reproduce synthetic and real demonstration runs; never calibrate against GT."""
from pathlib import Path
import sys,json,csv,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from wall_flatness.io import read_cloud
from wall_flatness.geometry import measure,fit_plane
from wall_flatness.__main__ import run

def write_json(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def discover_example(points):
    # Candidate plane discovery is ONLY for reproducible example coordinates.
    # Final measurement reselects from the ENTIRE room, not RANSAC inliers.
    rng=np.random.default_rng(7023);sample=points[rng.choice(len(points),min(20000,len(points)),replace=False)]
    best=None;score=0
    for _ in range(400):
        a,b,c=sample[rng.choice(len(sample),3,replace=False)];n=np.cross(b-a,c-a)
        if np.linalg.norm(n)<1e-9:continue
        n/=np.linalg.norm(n)
        if abs(n[2])>.35:continue
        mask=np.abs((sample-a)@n)<.01
        if mask.sum()>score:best=sample[mask];score=int(mask.sum())
    if best is None:raise ValueError('No suitable demo plane')
    center,n,_=fit_plane(best)
    if n[np.argmax(np.abs(n))]<0:n=-n
    v=np.array([0.,0.,1.]);v-=n*(v@n);v/=np.linalg.norm(v);u=np.cross(v,n)
    uv=np.c_[(best-center)@u,(best-center)@v]
    low,high=np.quantile(uv,[.2,.8],axis=0);mid=(low+high)/2;half=np.minimum((high-low)/2,[.65,.75])
    poly=np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*half+mid
    return (center+poly[:,0,None]*u+poly[:,1,None]*v).tolist()

def main():
    examples=ROOT/'examples';examples.mkdir(exist_ok=True)
    out=ROOT/'outputs';out.mkdir(exist_ok=True)
    summary_path=out/'experiment_summary.json'
    if summary_path.exists():raise ValueError('Experiments already exist; use a fresh copy/output location to preserve evidence')
    records=[];figures=[];rng=np.random.default_rng(7023)
    x,y=np.meshgrid(np.linspace(-1,1,151),np.linspace(-1,1,151));flat=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)]
    corners=[[-.9,-.9,0],[.9,-.9,0],[.9,.9,0],[-.9,.9,0]]
    for name in ['plane_noise','bulge','contamination','sparse']:
        p=flat.copy();p[:,2]=rng.normal(0,.0005,len(p))
        if name=='plane_noise':p[:,2]=rng.normal(0,.002,len(p))
        if name=='bulge':p[:,2]+=.02*np.exp(-np.sum(p[:,:2]**2,axis=1)/(.22**2))
        if name=='contamination':p[(np.abs(p[:,0])<.18)&(np.abs(p[:,1])<.18),2]+=.025
        if name=='sparse':p=p[p[:,0]<-.7]
        background=flat.copy();background[:,2]=2.5;p=np.vstack([p,background])
        cloud=examples/f'{name}.csv';np.savetxt(cloud,p,delimiter=',',header='x,y,z',comments='',fmt='%.9g')
        cfg={'unit':'m','room_id':'synthetic','roi_id':name,'corners':corners,'description':'Synthetic controlled example; not real measurements'}
        roi=examples/f'{name}.json';write_json(roi,cfg);r=run(str(cloud),roi,out/name)
        records.append({'case':name,'rms_mm':r['rms_mm'],'n_selected':r['n_selected'],'coverage':r['coverage_fraction'],'warnings':r['warnings']})
        print(name,r['rms_mm'],r['n_selected'],flush=True)
        if name in ('bulge','contamination'):
            figures.append({'title':f'模拟实验 {name}','path':f'outputs/{name}/deviation_map.png','caption':'使用原始选区点计算；中心高偏差保留在统计中。色标为点到最佳拟合平面的绝对距离，空白不插值。'})
    sensitivity=[]
    for room in ['M26','M04']:
        source=str(ROOT.parent/'data'/'Point_Cloud_Data.zip')+f'::{room}.pcd';p=read_cloud(source)
        cfg={'unit':'m','room_id':room,'roi_id':'geometric_demo','corners':discover_example(p),'description':'Algorithm-selected demo ROI; not confirmed as official GT wall or photo rectangle'}
        roi=examples/f'{room}_demo.json';write_json(roi,cfg);r=run(source,roi,out/f'{room}_demo')
        records.append({'case':room+'_demo','rms_mm':r['rms_mm'],'n_selected':r['n_selected'],'coverage':r['coverage_fraction'],'warnings':r['warnings']})
        print(room,r['rms_mm'],r['n_selected'],flush=True)
        for width in [20,50,100]:
            rs=measure(p,{**cfg,'slab_half_thickness_mm':width});sensitivity.append({'room':room,'variant':f'half_thickness_{width}mm','rms_mm':rs['rms_mm'],'n_selected':rs['n_selected'],'coverage':rs['coverage_fraction']})
        q=np.array(cfg['corners']);q=q.mean(0)+.8*(q-q.mean(0));rs=measure(p,{**cfg,'corners':q.tolist()});sensitivity.append({'room':room,'variant':'ROI_80pct_linear_size','rms_mm':rs['rms_mm'],'n_selected':rs['n_selected'],'coverage':rs['coverage_fraction']})
        figures.extend([{'title':f'{room} 房间与四点演示选区','path':f'outputs/{room}_demo/roi_context.png','caption':f'{room} 完整房间背景仅为显示抽样；蓝色为实际评价区域。红色 Q1 至 Q4 是保存在 examples/{room}_demo.json 的输入角点。该区域不是已确认的官方真值区域。'},
                        {'title':f'{room} 墙面偏差图','path':f'outputs/{room}_demo/deviation_map.png','caption':f'本次演示区域 RMS={r["rms_mm"]:.4f} mm，N={r["n_selected"]}。颜色上限为第 99 百分位，超过上限的点仍完整计入 RMS。没有依据此图判定工程合格。'}])
    with (out/'sensitivity.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(sensitivity[0]));w.writeheader();w.writerows(sensitivity)
    # Independent recomputation from saved distances, not just the in-memory result.
    diffs=[]
    for rec in records:
        a=np.genfromtxt(out/rec['case']/'distances.csv',names=True,delimiter=',');check=float(np.sqrt(np.mean(a['signed_distance_mm']**2)))
        diffs.append(abs(check-rec['rms_mm']))
    paragraphs=['执行范围：4 个模拟场景和 M26、M04 两个真实房间演示区域。模拟随机种子 7023；真实角点由固定种子的几何候选面生成后保存。测量始终重新从整个房间按四点和厚度筛选，未使用 RANSAC 内点作为最终评价点集。']
    for rec in records:paragraphs.append(f'{rec["case"]}：RMS={rec["rms_mm"]:.6f} mm，评价点数={rec["n_selected"]}，50 mm 网格覆盖率={rec["coverage"]:.1%}，提示={rec["warnings"] or "无自动提示"}。')
    paragraphs.append(f'逐点 CSV 独立复算与 result.json 的最大 RMS 差为 {max(diffs):.3g} mm，证明保存的逐点数据与摘要一致。')
    paragraphs.append('模拟结果解释：plane_noise 的 2 mm 是加入点的噪声标准差设定，有限样本且拟合后结果应接近而不必等于 2 mm；bulge 中的 20 mm 是峰值设定，不是整片 RMS，不能期望整体 RMS 等于 20 mm。contamination 表明未分离的前景物体可以显著改变 RMS；sparse 表明点数足够仍可能只覆盖很少的墙面。')
    for room in ['M26','M04']:
        rows=[r for r in sensitivity if r['room']==room];s='；'.join(f'{r["variant"]}: {r["rms_mm"]:.4f} mm / {r["n_selected"]} 点' for r in rows)
        paragraphs.append(f'{room} 敏感性实验：{s}。厚度改变影响候选点，ROI 缩小改变测量范围；数值变小不直接代表算法更准。')
    paragraphs.append('官方精度验证状态：未进行。M26 的 1.0 mm 与 M04 的 1.8 mm 是 README 指定墙面的人工参考，本演示 ROI 未确认与其同墙同范围同基准；所有真实结果的 GT 与误差字段保持 null。附图仅提供红框意图，无法从图片恢复三维角点，因此没有声称本例复现照片红框。')
    paragraphs.append('当前边界：四点和半厚度可以限制空间区域，但不能可靠区分同一区域内的插座、线槽、门框和墙体；输入选区需要人工或上游语义模块复核。噪声、遮挡、采样密度和参考面定义都会影响 RMS。本项目输出点加权 RMS，不是面积加权 RMS，也不是直尺或最小区域平整度。')
    write_json(summary_path,dict(records=records,sensitivity=sensitivity,max_csv_recompute_difference_mm=max(diffs),report_paragraphs=paragraphs,figures=figures))

if __name__=='__main__':main()
