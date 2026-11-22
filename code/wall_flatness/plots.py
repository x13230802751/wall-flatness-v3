# 绘制四点选区预览、墙面偏差色图和点到平面距离直方图。
"""Diagnostic figures; visualization sampling never changes metric computation."""
import os,tempfile
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'civl7023-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def save_plots(points,r,out):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130})
    fig=plt.figure(figsize=(11,7));ax=fig.add_subplot(111,projection='3d')
    p=points*(1 if r['config']['unit']=='m' else .001);p=p[np.isfinite(p).all(1)]
    bg=p[np.linspace(0,len(p)-1,min(len(p),18000),dtype=int)]
    ax.scatter(*bg.T,s=1,c='#8495a7',alpha=.35,rasterized=True)
    s=r['selected_xyz_m'];show=s[np.linspace(0,len(s)-1,min(len(s),18000),dtype=int)]
    ax.scatter(*show.T,s=1,c='#177aa6',alpha=.75)
    corners=r['corners_m'];closed=np.vstack([corners,corners[0]])
    ax.plot(*closed.T,c='#e44339',linewidth=2.5)
    for i,q in enumerate(corners):ax.text(*q,f' Q{i+1}',color='#a5231b',fontsize=11)
    ax.set(xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)',title=f"{r['config'].get('room_id','Room')} | ROI context (display sampled)\nBlue: evaluated original points; red: supplied corners")
    ax.set_box_aspect(np.maximum(np.ptp(p,axis=0),.01));ax.view_init(elev=22,azim=38)
    fig.tight_layout();fig.savefig(out/'roi_context.png');plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,7));uv=r['uv_m'];d=r['abs_mm']
    vmax=max(float(np.percentile(d,99)),.001)
    scatter=ax.scatter(uv[:,0],uv[:,1],c=d,s=3,cmap='viridis',vmin=0,vmax=vmax,rasterized=True)
    poly=r['polygon_uv_m'];poly=np.vstack([poly,poly[0]]);ax.plot(poly[:,0],poly[:,1],c='#df4039',lw=1.5)
    for i,q in enumerate(r['polygon_uv_m']):ax.annotate(f'Q{i+1}',q,xytext=(5,5),textcoords='offset points',color='#ad211c')
    cb=fig.colorbar(scatter,ax=ax,extend='max' if d.max()>vmax else 'neither');cb.set_label('Absolute distance to fitted plane (mm)')
    cov=r['coverage_fraction'];coverage_text=f'{cov:.1%}' if cov is not None else 'undefined'
    ax.set(xlabel='ROI local u (m)',ylabel='ROI local v (m)',title=f"RMS = {r['rms_mm']:.3f} mm | N = {len(d):,} | grid coverage = {coverage_text}\nColor capped at P99 ({vmax:.3f} mm); max = {d.max():.3f} mm; gaps not interpolated")
    ax.set_aspect('equal');ax.grid(alpha=.15);fig.tight_layout();fig.savefig(out/'deviation_map.png');plt.close(fig)

    fig,ax=plt.subplots(figsize=(9,5));ax.hist(r['signed_mm'],bins=70,color='#167da6',edgecolor='white',linewidth=.3)
    ax.axvline(0,color='#d94b41',lw=1);ax.set(xlabel='Signed point-to-plane distance (mm)',ylabel='Point count',title=f"Deviation distribution | RMS {r['rms_mm']:.3f} mm\nSign follows reference normal; not automatically inward/outward")
    fig.tight_layout();fig.savefig(out/'distance_histogram.png');plt.close(fig)
