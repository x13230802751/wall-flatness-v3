# 测量官方点云的预设墙面区域，并记录与官方参考值的差异。
"""Same-wall reference comparison. Exact manual GT footprints are unavailable.

ROIs are fixed from RGB geometry, never optimized against the GT value.
Run inspect_official_walls.py first. Main ROI measurements use unchanged code.
"""
from pathlib import Path
import sys,json,csv,hashlib
import numpy as np
from inspect_official_walls import load,OUT,ROOT
sys.path.insert(0,str(ROOT))
from wall_flatness.geometry import measure
from wall_flatness.__main__ import run
import matplotlib.pyplot as plt

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

# Local axis0 limits, absolute Z limits. Chosen from RGB before measurement.
PROTOCOL={
 'M26':dict(wall='W10',axis1_side=0,main=[-1.70,1.45,-12.20,-10.95],
            extended=[-1.70,1.45,-13.22,-10.95],gt=1.0,
            wall_status='identified_from_door_opposite_wall',
            reason='W11 has a floor-connected door; W10 is opposite. Upper band avoids the visible electrical fitting at Z about -12.5 m.'),
 'M04':dict(wall='W11',axis1_side=1,main=[-1.08,1.47,-4.85,-3.05],
            extended=[-1.08,1.47,-5.28,-2.67],gt=1.8,
            wall_status='photo_based_candidate_official_image_provenance_unconfirmed',
            reason='Photo looks toward W00 door; right wall is W11. Central seam and bottom fitting match RGB. Source image provenance and exact footprint remain unconfirmed.')}

def config(room,basis,d,rect,name):
    x0,x1,z0,z1=rect
    local=np.array([[x0,d,z0],[x1,d,z0],[x1,d,z1],[x0,d,z1]])
    return dict(unit='m',room_id=room,roi_id=name,corners=(local@basis.T).tolist(),
                slab_half_thickness_mm=50.,description=PROTOCOL[room]['reason'])

def main():
    if (OUT/'comparison.json').exists():raise ValueError('Completed evaluation exists; preserve evidence and use a fresh output root')
    dump(OUT/'evaluation_protocol.json',dict(protocol=PROTOCOL,scope='same-wall descriptive reference differences; NOT exact-ROI accuracy validation',
        primary_metric='absolute difference in mm; relative difference is secondary',
        no_target_based_roi_selection=True,sensitivity='half thickness 20/50/100 mm; translate ROI +-100 mm horizontally/vertically; shrink sides by 10%; no optimization',
        exact_manual_roi_available=False,gt_instrument_uncertainty_available=False))
    records=[];sens=[];checks=[]
    for room,pr in PROTOCOL.items():
        p,col=load(room);frame=json.loads((OUT/f'{room}_frame.json').read_text())
        basis=np.array(frame['basis_columns']);d=frame['wall_coordinate_bounds_m'][1][pr['axis1_side']]
        for kind in ['main','extended']:
            cfg=config(room,basis,d,pr[kind],f'{room}_{kind}');roi=OUT/f'{room}_{kind}_roi.json';dump(roi,cfg)
            result=run(str(ROOT.parent/'data'/'Point_Cloud_Data.zip')+f'::{room}.pcd',roi,OUT/f'{room}_{kind}')
            # Do not turn on exact-ROI confirmation. Report external descriptive differences separately.
            diff=result['rms_mm']-pr['gt']
            rec=dict(room=room,roi=kind,wall=pr['wall'],wall_status=pr['wall_status'],rms_mm=result['rms_mm'],reference_mm=pr['gt'],
                     signed_difference_mm=diff,absolute_difference_mm=abs(diff),relative_difference_pct=abs(diff)/pr['gt']*100,
                     n_selected=result['n_selected'],coverage_fraction=result['coverage_fraction'],
                     same_roi_confirmed=False,comparison_class='descriptive_only',warnings=result['warnings'])
            records.append(rec);print(json.dumps(rec),flush=True)
            # Independent saved-XYZ covariance eigensolution, no geometry.fit_plane call.
            saved=np.genfromtxt(OUT/f'{room}_{kind}'/'distances.csv',delimiter=',',names=True)
            xyz=np.c_[saved['x_m'],saved['y_m'],saved['z_m']];centered=xyz-xyz.mean(0)
            eigen=float(np.sqrt(max(0,np.linalg.eigvalsh(centered.T@centered/len(xyz))[0]))*1000)
            csv_rms=float(np.sqrt(np.mean(saved['signed_distance_mm']**2)))
            err=max(abs(csv_rms-result['rms_mm']),abs(eigen-result['rms_mm']))
            if err>1e-5:raise AssertionError('Independent RMS check failed')
            checks.append(dict(room=room,roi=kind,eigen_rms_mm=eigen,csv_rms_mm=csv_rms,max_difference_mm=err))
            if kind=='main':
                r=measure(p,cfg);a=p@basis
                fig,ax=plt.subplots(figsize=(8,6));sel=np.abs(a[:,1]-d)<.08
                ax.scatter(a[sel,0],a[sel,2],c=col[sel],s=1)
                corners=np.array(cfg['corners'])@basis;loop=np.r_[corners,corners[:1]]
                ax.plot(loop[:,0],loop[:,2],'r-',lw=2)
                for i,q in enumerate(corners):ax.text(q[0],q[2],f'Q{i+1}',color='red',fontsize=11)
                ax.set_aspect('equal');ax.set_xlabel('local axis0 (m)');ax.set_ylabel('Z (m)')
                ax.set_title(f'{room} {pr["wall"]}: selected ROI (red)\nOriginal RGB, no residual-based point rejection')
                fig.tight_layout();fig.savefig(OUT/f'{room}_selected_rgb.png',dpi=180);plt.close(fig)
                variants=[]
                for thick in [20,50,100]:variants.append((f'half_thickness_{thick}mm',{**cfg,'slab_half_thickness_mm':thick}))
                for axis in [0,2]:
                    for sign in [-1,1]:
                        q=np.array(cfg['corners'])+sign*.1*basis[:,axis]
                        variants.append((f'shift_axis{axis}_{sign*100}mm',{**cfg,'corners':q.tolist()}))
                q=np.array(cfg['corners']);q=q.mean(0)+.9*(q-q.mean(0))
                variants.append(('shrink_linear_90pct',{**cfg,'corners':q.tolist()}))
                for name,c in variants:
                    rr=measure(p,c);sens.append(dict(room=room,variant=name,rms_mm=rr['rms_mm'],n_selected=rr['n_selected'],
                        coverage_fraction=rr['coverage_fraction'],change_from_main_mm=rr['rms_mm']-result['rms_mm']))
    for name,rows in [('comparison',records),('sensitivity',sens),('independent_checks',checks)]:
        dump(OUT/f'{name}.json',rows)
        with (OUT/f'{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    manifest={str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.rglob('*')) if f.is_file()}
    dump(OUT/'manifest_sha256.json',manifest)
    print('Independent checks passed',checks,flush=True)
if __name__=='__main__':main()
