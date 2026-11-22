# 生成已知参考值的合成场景，评测四点选区方法的 RMS 准确性。
"""Frozen synthetic RMS accuracy benchmark; production geometry is unmodified.

Ground truth uses constructed orthogonal height fields, never production output.
Observed-wall reference uses a separate covariance eigensolver and known labels.
"""
from pathlib import Path
import sys,os,json,csv,time,hashlib,platform
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from wall_flatness.geometry import measure
OUT=ROOT/'outputs'/'rms_accuracy_benchmark'

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def oracle(x):
    q=x-x.mean(0);return float(1000*np.sqrt(max(0,np.linalg.eigvalsh(q.T@q/len(q))[0])))
def pose(k):
    a=[0,.37,1.12][k];b=[np.pi/2,1.31,.76][k]
    rz=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]])
    rx=np.array([[1,0,0],[0,np.cos(b),-np.sin(b)],[0,np.sin(b),np.cos(b)]])
    return rz@rx,np.array([[0,0,0],[4,-3,2],[1000,-500,200]][k],dtype=float)
def surface(kind,A):
    u,v=np.meshgrid(np.linspace(-.99,.99,101),np.linspace(-.74,.74,81));u=u.ravel();v=v.ravel()
    if kind=='wave':f=np.cos(2*np.pi*u)*np.cos(2*np.pi*v)
    elif kind=='bowl':f=u*u+.7*v*v
    else:f=np.exp(-(u*u+v*v)/(2*(.04 if kind=='narrow' else .22)**2))
    # Remove constant and both linear components using independent least squares.
    X=np.c_[np.ones(len(u)),u,v];g=f-X@np.linalg.lstsq(X,f,rcond=None)[0]
    z=g/np.sqrt(np.mean(g*g))*A/1000
    wall=np.c_[u,v,z]
    cov=(wall-wall.mean(0)).T@(wall-wall.mean(0))/len(wall)
    assert np.max(np.abs(cov[:2,2]))<1e-12
    assert np.linalg.eigvalsh(cov[:2,:2]).min()>cov[2,2]
    assert abs(np.sqrt(np.mean(z*z))*1000-A)<1e-10
    return wall
def scenarios():
    cases=[]
    def add(group,**kw):cases.append({**dict(group=group,profile='wave',A=1.8,pose=1,unit='m',seed=702300+len(cases)),**kw})
    for profile in ['wave','bowl','bump']:
        for A in [0,.5,1,1.8,3,5]:
            for k in range(3):add('clean',profile=profile,A=A,pose=k,unit='mm' if k==2 else 'm')
    for A in [.5,1.8,5]:
        for sigma in [.2,.5,1.0]:
            for rep in range(20):add('noise',A=A,sigma=sigma,rep=rep)
    for fraction in [.5,.1,.02]:
        for rep in range(20):add('sampling',profile='bump',fraction=fraction,rep=rep)
    for profile in ['wave','bowl','bump']:add('occlusion',profile=profile)
    for fraction in [.01,.05,.1]:
        for rep in range(10):add('clutter',fraction=fraction,rep=rep)
    for half in [20,50,150]:add('slab_clipping',profile='narrow',A=5,half=half)
    for name in ['left','right','down','up','shrink']:add('roi_change',profile='bump',roi_change=name)
    return cases

def main():
    if OUT.exists():raise ValueError('Benchmark directory exists; preserve recorded evidence')
    OUT.mkdir();(OUT/'inputs').mkdir();(OUT/'examples').mkdir()
    cases=scenarios()
    protocol=dict(date='2026-11-22',target='Point-weighted RMS to the best-fit orthogonal plane on a fixed finite point set',
        truth='Constructed zero-mean height field orthogonal to u and v, normalized to exact RMS A; height variance is smallest covariance eigenvalue',
        exact_input_units='m except pose 2 clean cases use mm for both cloud and corners',
        numeric_gate_mm=1e-6,proposed_practical_gate_mm=.2,
        gate_note='0.2 mm is a project working target, not course requirement or engineering standard; not a clean-numerics threshold',
        noise_model='Independent Gaussian displacement along nominal wall normal only; no scanner or registration realism claimed',
        repeat_definition='Monte Carlo inputs with different seeds; not independent physical walls',
        failure_policy='Keep all cases, exceptions and warning states; no parameter optimization',
        scenarios=cases,production_sha256=hashlib.sha256((ROOT/'wall_flatness'/'geometry.py').read_bytes()).hexdigest(),
        python=platform.python_version(),numpy=np.__version__)
    dump(OUT/'protocol.json',protocol) # Before first production measurement.
    records=[];picked=set();start=time.perf_counter()
    for i,case in enumerate(cases):
        rng=np.random.default_rng(case['seed']);base=surface(case['profile'],case['A']);n_full=len(base)
        keep=np.ones(n_full,dtype=bool)
        if case['group']=='sampling':keep=rng.random(n_full)<case['fraction']
        if case['group']=='occlusion':keep=np.linalg.norm(base[:,:2],axis=1)>.35
        wall=base[keep].copy()
        if case['group']=='noise':wall[:,2]+=rng.normal(0,case['sigma']/1000,len(wall))
        nwall=len(wall);corners=np.array([[-1,-.75,0],[1,-.75,0],[1,.75,0],[-1,.75,0.]])
        if case.get('roi_change'):
            shift={'left':[-.1,0,0],'right':[.1,0,0],'down':[0,-.1,0],'up':[0,.1,0],'shrink':[0,0,0]}[case['roi_change']]
            corners=corners*.9 if case['roi_change']=='shrink' else corners+shift
        # Semantic GT membership: rectangular bounds only, NOT slab residual or fitted plane.
        good=(wall[:,0]>=corners[:,0].min()-1e-12)&(wall[:,0]<=corners[:,0].max()+1e-12)&(wall[:,1]>=corners[:,1].min()-1e-12)&(wall[:,1]<=corners[:,1].max()+1e-12)
        counterpart=wall.copy();counterpart[:,2]=3
        side=wall[::4].copy();side[:,0]=1.3;side[:,2]=np.linspace(-.5,2.5,len(side))
        front=np.empty((0,3))
        if case['group']=='clutter':
            n=int(round(nwall*case['fraction']));front=np.c_[rng.uniform(-.2,.2,n),rng.uniform(-.2,.2,n),np.full(n,.03)]
        local=np.vstack([wall,counterpart,side,front]);R,t=pose(case['pose']);cloud=local@R.T+t
        q=corners@R.T+t;scale=1000 if case['unit']=='mm' else 1
        cfg=dict(unit=case['unit'],corners=(q*scale).tolist(),slab_half_thickness_mm=case.get('half',50),room_id='synthetic',roi_id=f'{i:03d}_{case["group"]}')
        labels=np.zeros(len(local),dtype=bool);labels[:nwall]=good
        caseid=f'{i:03d}_{case["group"]}'
        np.savez_compressed(OUT/'inputs'/f'{caseid}.npz',points=cloud*scale,wall_roi_mask=labels,clean_wall_full_m=base)
        dump(OUT/'inputs'/f'{caseid}.json',dict(case=case,config=cfg))
        target=case['A'];ref=oracle(wall[good]);rec=dict(id=caseid,**case,true_full_rms_mm=target,visible_wall_oracle_mm=ref,
            n_full=n_full,n_visible_wall=int(good.sum()),status='error',rms_mm=None,error_full_mm=None,error_visible_mm=None,
            precision=None,recall=None,coverage=None,warnings=[],within_working_target=False)
        try:
            result=measure(cloud*scale,cfg);ids=result['indices'];tp=int(labels[ids].sum())
            rec.update(status=result['status'],rms_mm=result['rms_mm'],error_full_mm=result['rms_mm']-target,
                error_visible_mm=result['rms_mm']-ref,precision=tp/len(ids),recall=tp/int(labels.sum()),
                coverage=result['coverage_fraction'],warnings=result['warnings'],within_working_target=abs(result['rms_mm']-target)<=.2)
            if case['group'] not in picked:
                picked.add(case['group'])
                np.savetxt(OUT/'examples'/f'{case["group"]}_distances.csv',np.c_[ids,result['signed_mm']],delimiter=',',header='point_index,signed_mm',comments='')
        except (ValueError,np.linalg.LinAlgError) as exc:rec['exception']=str(exc)
        records.append(rec)
        if (i+1)%50==0:print('Completed',i+1,'/',len(cases),flush=True)
    dump(OUT/'records.json',records)
    fields=['id','group','profile','A','seed','pose','unit','sigma','fraction','half','roi_change','rep','true_full_rms_mm','visible_wall_oracle_mm','n_full','n_visible_wall','status','rms_mm','error_full_mm','error_visible_mm','precision','recall','coverage','warnings','within_working_target','exception']
    with (OUT/'records.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    groups={}
    for g in dict.fromkeys(r['group'] for r in records):
        rr=[r for r in records if r['group']==g];ok=[r for r in rr if r['rms_mm'] is not None];err=np.array([r['error_full_mm'] for r in ok])
        groups[g]=dict(n=len(rr),n_success=len(ok),n_warning=sum(r['status']=='warning' for r in rr),
            bias_mm=float(np.mean(err)),mae_mm=float(np.mean(np.abs(err))),rmse_mm=float(np.sqrt(np.mean(err**2))),max_ae_mm=float(np.max(np.abs(err))),
            pass_rate=sum(r['within_working_target'] for r in rr)/len(rr),max_visible_ae_mm=max(abs(r['error_visible_mm']) for r in ok))
    clean=[r for r in records if r['group']=='clean']
    gate=all(r['rms_mm'] is not None and abs(r['error_full_mm'])<=1e-6 and r['precision']==1 and r['recall']==1 for r in clean)
    summary=dict(groups=groups,clean_numeric_gate_passed=gate,total_cases=len(cases),elapsed_seconds=time.perf_counter()-start)
    dump(OUT/'summary.json',summary)
    make_plots(records)
    manifest={str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.rglob('*')) if f.is_file()}
    dump(OUT/'manifest_sha256.json',manifest)
    print(json.dumps(summary,indent=2),flush=True)

def make_plots(records):
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT.parent/'_mplcache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,3,figsize=(12,3.7))
    for ax,kind in zip(axs,['wave','bowl','bump']):
        w=surface(kind,1.8);im=ax.scatter(w[:,0],w[:,1],c=w[:,2]*1000,s=2,cmap='coolwarm');ax.set_aspect('equal');ax.set_title(kind+'; exact RMS = 1.8 mm');ax.set_xlabel('u (m)');ax.set_ylabel('v (m)');fig.colorbar(im,ax=ax,label='signed height (mm)')
    fig.tight_layout();fig.savefig(OUT/'known_walls.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    for A in [.5,1.8,5]:
        xs=[];ys=[];sd=[]
        for sigma in [.2,.5,1]:
            rr=[r['error_full_mm'] for r in records if r['group']=='noise' and r['A']==A and r['sigma']==sigma]
            xs.append(sigma);ys.append(np.mean(rr));sd.append(np.std(rr,ddof=1))
        ax.errorbar(xs,ys,yerr=sd,marker='o',capsize=4,label=f'True RMS {A} mm')
    ax.axhline(.2,c='gray',ls='--',label='Working target +0.2 mm');ax.set_xlabel('Normal noise sigma (mm)');ax.set_ylabel('Mean signed error vs clean wall (mm)');ax.legend();ax.set_title('20 realizations; error bars are sample SD, not CI');fig.tight_layout();fig.savefig(OUT/'noise_bias.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for ax,g,param in [(axs[0],'clutter','fraction'),(axs[1],'slab_clipping','half')]:
        rr=[r for r in records if r['group']==g];xx=sorted(set(r[param] for r in rr));yy=[np.mean([r['rms_mm'] for r in rr if r[param]==x]) for x in xx]
        ax.plot(xx,yy,'o-');ax.axhline(rr[0]['A'],ls='--',c='black',label='Known true wall RMS');ax.set_title(g);ax.set_xlabel('Object count / wall count' if g=='clutter' else 'Slab half thickness (mm)');ax.set_ylabel('Predicted RMS (mm)');ax.legend()
    fig.tight_layout();fig.savefig(OUT/'failure_modes.png',dpi=180);plt.close(fig)
if __name__=='__main__':main()
