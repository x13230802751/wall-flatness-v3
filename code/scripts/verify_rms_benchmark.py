# 重新读取合成基准输入，核查参考值、测量结果和实验记录。
"""Re-read every saved benchmark input and audit results and analytic truth."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from wall_flatness.geometry import measure
O=ROOT/'outputs'/'rms_accuracy_benchmark'
def main():
    records=json.loads((O/'records.json').read_text(encoding='utf-8'))
    proto=json.loads((O/'protocol.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT/'wall_flatness'/'geometry.py').read_bytes()).hexdigest()==proto['production_sha256']
    for name,digest in json.loads((O/'manifest_sha256.json').read_text(encoding='utf-8')).items():
        assert hashlib.sha256((O/name).read_bytes()).hexdigest()==digest,name
    differences=[];truth_errors=[]
    for rec in records:
        inp=np.load(O/'inputs'/f'{rec["id"]}.npz');cfg=json.loads((O/'inputs'/f'{rec["id"]}.json').read_text(encoding='utf-8'))['config']
        base=inp['clean_wall_full_m'];z=base[:,2];A=rec['true_full_rms_mm']
        cov=(base-base.mean(0)).T@(base-base.mean(0))/len(base)
        assert abs(z.mean())<1e-12 and np.max(np.abs(cov[:2,2]))<1e-12
        assert np.linalg.eigvalsh(cov[:2,:2]).min()>cov[2,2]
        te=abs(np.sqrt(np.mean(z*z))*1000-A);assert te<1e-10;truth_errors.append(te)
        result=measure(inp['points'],cfg);de=abs(result['rms_mm']-rec['rms_mm']);assert de<1e-10;differences.append(de)
        labels=inp['wall_roi_mask'];tp=labels[result['indices']].sum()
        assert abs(tp/len(result['indices'])-rec['precision'])<1e-12
        assert abs(tp/labels.sum()-rec['recall'])<1e-12
        assert result['warnings']==rec['warnings']
    answer=dict(n_inputs_replayed=len(records),max_replay_difference_mm=max(differences),max_analytic_truth_error_mm=max(truth_errors),
                labels_and_warnings_verified=True,production_code_hash_verified=True,input_hashes_verified=True)
    (O/'verification.json').write_text(json.dumps(answer,indent=2),encoding='utf-8');print(json.dumps(answer,indent=2))
if __name__=='__main__':main()
