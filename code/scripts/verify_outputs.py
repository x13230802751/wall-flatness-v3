# 独立核对已保存结果中的点索引、距离、拟合平面和输出文件。
"""Independent checks of stored distances, indices, plane equations and artifacts."""
from pathlib import Path
import sys,json,re,hashlib,platform,importlib.metadata
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from wall_flatness.io import read_cloud

def main():
    out=ROOT/'outputs';summary=json.loads((out/'experiment_summary.json').read_text(encoding='utf-8'));checks=[]
    for record in summary['records']:
        name=record['case'];folder=out/name;r=json.loads((folder/'result.json').read_text(encoding='utf-8'))
        a=np.genfromtxt(folder/'distances.csv',names=True,delimiter=',');idx=a['point_index'].astype(int)
        xyz=np.c_[a['x_m'],a['y_m'],a['z_m']];cloud=read_cloud(r['cloud_source']);scale=1 if r['config']['unit']=='m' else .001
        assert len(a)==r['n_selected'] and len(np.unique(idx))==len(idx)
        np.testing.assert_allclose(xyz,cloud[idx]*scale,atol=1e-12,rtol=0)
        signed=(xyz-np.array(r['plane_center_m']))@np.array(r['plane_normal'])*1000
        np.testing.assert_allclose(signed,a['signed_distance_mm'],atol=1e-9)
        rms=float(np.sqrt(np.mean(signed**2)));assert abs(rms-r['rms_mm'])<1e-9
        centered=xyz-xyz.mean(0);eigenvalues=np.linalg.eigvalsh(centered.T@centered/len(xyz))
        covariance_rms=float(np.sqrt(max(eigenvalues[0],0))*1000)
        assert abs(covariance_rms-rms)<1e-6
        assert r['gt_rms_mm'] is None and r['abs_error_mm'] is None
        for filename in ['roi_context.png','deviation_map.png','distance_histogram.png']:
            with Image.open(folder/filename) as im:assert im.width>=1000 and im.height>=600
        checks.append(dict(case=name,n_points=len(a),csv_rms_mm=rms,covariance_rms_mm=covariance_rms,passed=True))
    test_log=(out/'test_results.txt').read_text(encoding='utf-8-sig');match=re.search(r'Ran (\d+) tests',test_log)
    assert match and test_log.strip().endswith('OK')
    cli=json.loads((out/'cli_verified'/'result.json').read_text(encoding='utf-8'));base=json.loads((out/'M04_demo'/'result.json').read_text(encoding='utf-8'));assert cli['rms_mm']==base['rms_mm']
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'wall_flatness').glob('*.py'))}
    report=dict(tests_passed=int(match[1]),independent_artifact_checks=checks,local_powershell_launcher_matches=True,python=platform.python_version(),packages={x:importlib.metadata.version(x) for x in ['numpy','matplotlib','pillow']},source_sha256=source_hashes)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
