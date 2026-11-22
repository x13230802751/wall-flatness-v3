# 提供命令行入口，读取点云和四点配置并保存区域 RMS 测量结果。
import argparse,csv,json,sys,time,platform,hashlib,zipfile
from pathlib import Path
import numpy as np
from . import __version__
from .io import read_cloud
from .geometry import measure

ARRAY_FIELDS={'indices','selected_xyz_m','signed_mm','abs_mm','uv_m','polygon_uv_m','corners_m','roi_center_m'}

def run(cloud,roi,out,gt=None,confirmed=False):
    start=time.perf_counter();out=Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):raise ValueError('Output directory must be absent or empty; choose a new directory')
    if (gt is not None)!=bool(confirmed):raise ValueError('--gt-rms-mm and --gt-confirmed must be supplied together after checking the same wall/ROI/reference')
    if gt is not None and (not np.isfinite(gt) or gt<0):raise ValueError('GT must be finite and nonnegative')
    config=json.loads(Path(roi).read_text(encoding='utf-8-sig'))
    if not isinstance(config,dict):raise ValueError('ROI JSON must be an object')
    points,digest=read_cloud(cloud,with_hash=True);r=measure(points,config)
    from .plots import save_plots
    out.mkdir(parents=True,exist_ok=True)
    values=np.c_[r['indices'],r['selected_xyz_m'],r['signed_mm'],r['abs_mm']]
    np.savetxt(out/'distances.csv',values,delimiter=',',header='point_index,x_m,y_m,z_m,signed_distance_mm,abs_distance_mm',comments='',fmt=['%d']+['%.17g']*5)
    save_plots(points,r,out)
    result={k:v for k,v in r.items() if k not in ARRAY_FIELDS}
    result.update(schema_version=1,software_version=__version__,python_version=platform.python_version(),numpy_version=np.__version__,
                  cloud_source=str(cloud),cloud_payload_sha256=digest,roi_sha256=hashlib.sha256(Path(roi).read_bytes()).hexdigest(),
                  gt_rms_mm=gt,gt_same_roi_confirmed=bool(confirmed),abs_error_mm=None if gt is None else abs(r['rms_mm']-gt),
                  relative_error_pct=None if gt is None or gt==0 else abs(r['rms_mm']-gt)/gt*100,
                  runtime_seconds=time.perf_counter()-start,
                  measurement_definition='Point-weighted RMS to best-fit plane of all selected original points; no residual rejection',
                  sign_convention='Aligned to SVD normal of supplied corners; not guaranteed toward room interior')
    (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    fields=['room_id','roi_id','status','rms_mm','n_selected','coverage_fraction','p95_abs_mm','max_abs_mm','gt_rms_mm','abs_error_mm','relative_error_pct','runtime_seconds']
    with (out/'summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow({k:result['config'].get(k,'') if k in ('room_id','roi_id') else result[k] for k in fields})
    return result

def main():
    parser=argparse.ArgumentParser(description='Whole-room point cloud + four cyclic 3D ROI corners -> wall RMS (mm).')
    parser.add_argument('--cloud',required=True,help='PCD/CSV or archive.zip::member.pcd')
    parser.add_argument('--roi',required=True,help='JSON with unit and four cyclic corners')
    parser.add_argument('--out',required=True,help='New or empty output directory')
    parser.add_argument('--gt-rms-mm',type=float);parser.add_argument('--gt-confirmed',action='store_true')
    args=parser.parse_args()
    try:
        r=run(args.cloud,args.roi,args.out,args.gt_rms_mm,args.gt_confirmed)
    except (ValueError,OSError,KeyError,ImportError,zipfile.BadZipFile,np.linalg.LinAlgError) as e:
        print(f'ERROR: {e}',file=sys.stderr);return 2
    print(json.dumps({k:r[k] for k in ['status','rms_mm','n_selected','warnings']},ensure_ascii=True));return 0

if __name__=='__main__':sys.exit(main())
