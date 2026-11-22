# 生成官方点云的彩色墙面投影图，辅助查看墙面和确定测量区域。
"""Create RGB wall elevations before selecting evaluation ROIs. No GT used."""
from pathlib import Path
import os,sys,json,zipfile
import numpy as np
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'_mplcache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'official_evaluation'
OUT.mkdir(exist_ok=True)

def load(room):
    with zipfile.ZipFile(ROOT.parent/'data'/'Point_Cloud_Data.zip') as z:
        raw=z.read(room+'.pcd')
    marker=b'DATA binary\n';start=raw.index(marker)+len(marker)
    a=np.frombuffer(raw[start:],dtype='<f4').reshape(-1,7)
    rgb=a[:,6].copy().view('<u4')
    colors=np.c_[(rgb>>16)&255,(rgb>>8)&255,rgb&255]/255
    return a[:,:3].astype(float),colors

def main():
    for room in ['M26','M04']:
        p,col=load(room)
        cfg=json.loads((ROOT/'examples'/f'{room}_demo.json').read_text(encoding='utf-8'))
        q=np.array(cfg['corners']);u=q[1]-q[0];u[2]=0;u/=np.linalg.norm(u)
        v=np.array([-u[1],u[0],0.]);basis=np.stack([u,v,[0,0,1]],axis=1)
        a=p@basis
        bounds=[]
        fig,axs=plt.subplots(1,2,figsize=(11,4))
        for k in range(2):
            h,e=np.histogram(a[:,k],bins=np.arange(a[:,k].min(),a[:,k].max()+.005,.005))
            mid=(e[:-1]+e[1:])/2
            # Highest peak in each half of the room: location only, not final inlier set.
            split=np.median(a[:,k]);lo=mid[np.argmax(np.where(mid<split,h,0))];hi=mid[np.argmax(np.where(mid>split,h,0))]
            bounds.append([float(lo),float(hi)])
            axs[k].plot(mid,h);axs[k].set_title(f'{room} axis {k}: {lo:.3f}, {hi:.3f} m')
        fig.tight_layout();fig.savefig(OUT/f'{room}_coordinate_histograms.png',dpi=150);plt.close(fig)
        fig,axs=plt.subplots(2,2,figsize=(12,10))
        for k in range(2):
            for side in range(2):
                ax=axs[k,side];d=bounds[k][side];sel=np.abs(a[:,k]-d)<.08
                j=1-k;ax.scatter(a[sel,j],a[sel,2],c=col[sel],s=.6,rasterized=True)
                ax.set_title(f'{room} W{k}{side}: axis{k}={d:.3f} m; N={sel.sum()}')
                ax.set_xlabel(f'axis{j} (m)');ax.set_ylabel('Z (m)');ax.set_aspect('equal')
        fig.tight_layout();fig.savefig(OUT/f'{room}_wall_elevations.png',dpi=180);plt.close(fig)
        fig,ax=plt.subplots(figsize=(8,7));sel=(a[:,2]>np.quantile(a[:,2],.1))&(a[:,2]<np.quantile(a[:,2],.9));idx=np.flatnonzero(sel)[::3]
        ax.scatter(a[idx,0],a[idx,1],c=col[idx],s=.6)
        for k in range(2):
            for side in range(2):
                d=bounds[k][side]
                if k==0:ax.axvline(d,c='red',lw=.8);ax.text(d,np.mean(bounds[1]),f'W{k}{side}')
                else:ax.axhline(d,c='red',lw=.8);ax.text(np.mean(bounds[0]),d,f'W{k}{side}')
        ax.set_aspect('equal');ax.set_xlabel('axis0 (m)');ax.set_ylabel('axis1 (m)');ax.set_title(room+' horizontal overview')
        fig.tight_layout();fig.savefig(OUT/f'{room}_plan.png',dpi=180);plt.close(fig)
        metadata={'basis_columns':basis.tolist(),'wall_coordinate_bounds_m':bounds,'z_quantiles_m':np.quantile(a[:,2],[.01,.05,.5,.95,.99]).tolist()}
        (OUT/f'{room}_frame.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print(room,metadata,flush=True)
if __name__=='__main__':main()
