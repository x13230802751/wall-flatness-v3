# 核查已有实验记录，汇总 RMS 的有符号误差、绝对误差和相对误差。
"""Audit existing immutable experiments, then produce explicit error tables.

This does not rerun or tune the measurement method. It verifies recorded evidence
and adds signed/absolute/relative error with zero-reference handling.
"""
from pathlib import Path
import csv,json,hashlib,math
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'outputs'/'rms_accuracy_benchmark'
F=ROOT/'outputs'/'official_evaluation'
O=ROOT/'outputs'/'rms_error_evaluation'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def table(name,rows):
    dump(O/(name+'.json'),rows)
    with (O/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def metrics(pred,ref):
    if pred is None:return None,None,None
    e=pred-ref;return e,abs(e),None if ref==0 else 100*abs(e)/abs(ref)
def summary(rows):
    ok=[r for r in rows if r['predicted_rms_mm'] is not None]
    e=[r['signed_error_full_mm'] for r in ok]
    return dict(n=len(rows),n_success=len(ok),n_failure=len(rows)-len(ok),n_warning=sum(r['status']=='warning' for r in rows),
        bias_mm=sum(e)/len(e),mae_mm=sum(abs(x) for x in e)/len(e),
        rmse_mm=math.sqrt(sum(x*x for x in e)/len(e)),max_ae_mm=max(abs(x) for x in e),
        max_visible_ae_mm=max(r['abs_error_visible_mm'] for r in ok),
        within_0p2mm_count=sum(abs(x)<=.2 for x in e),working_target_note='Proposed project target only; not engineering acceptance or overall accuracy')
def condition(r):
    g=r['group'];parts=[g,r['profile'],f'A={r["A"]}mm']
    for k in ['sigma','fraction','half','roi_change']:
        if k in r:parts.append(f'{k}={r[k]}')
    return ';'.join(parts)
def main():
    if O.exists():raise ValueError('Output exists; preserve prior evidence')
    O.mkdir()
    # Audit both previously generated evidence manifests, not just summary files.
    hash_count=0
    for folder in [B,F]:
        for name,digest in read(folder/'manifest_sha256.json').items():
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,str(folder/name)
            hash_count+=1
    protocol=read(B/'protocol.json');verification=read(B/'verification.json')
    assert hashlib.sha256((ROOT/'wall_flatness'/'geometry.py').read_bytes()).hexdigest()==protocol['production_sha256']
    raw=read(B/'records.json');assert len(raw)==335==verification['n_inputs_replayed']
    scored=[]
    for r in raw:
        assert (B/'inputs'/f'{r["id"]}.npz').is_file()
        cfg=read(B/'inputs'/f'{r["id"]}.json')['config']
        assert cfg['unit']==r['unit'] and len(cfg['corners'])==4
        e,a,re=metrics(r['rms_mm'],r['true_full_rms_mm'])
        ev,av,rv=metrics(r['rms_mm'],r['visible_wall_oracle_mm'])
        if e is not None:
            assert abs(e-r['error_full_mm'])<1e-12
            assert abs(ev-r['error_visible_mm'])<1e-12
        scored.append(dict(id=r['id'],group=r['group'],condition=condition(r),profile=r['profile'],seed=r['seed'],
            reference_type='constructed_exact_full_wall',full_truth_rms_mm=r['true_full_rms_mm'],predicted_rms_mm=r['rms_mm'],
            signed_error_full_mm=e,abs_error_full_mm=a,relative_error_full_pct=re,
            relative_error_status='undefined_zero_reference' if r['true_full_rms_mm']==0 else 'defined',
            visible_wall_reference_rms_mm=r['visible_wall_oracle_mm'],signed_error_visible_mm=ev,abs_error_visible_mm=av,
            precision=r['precision'],recall=r['recall'],coverage=r['coverage'],status=r['status'],warnings=';'.join(r['warnings']),
            exact_full_truth_available=True,comparison_scope='numerical_correctness' if r['group']=='clean' else 'controlled_input_or_scope_effect',
            input_npz=str(B/'inputs'/f'{r["id"]}.npz'),roi_json=str(B/'inputs'/f'{r["id"]}.json')))
    table('synthetic_errors',scored)
    conditions=defaultdict(list);groups=defaultdict(list)
    for r in scored:conditions[r['condition']].append(r);groups[r['group']].append(r)
    table('condition_metrics',[dict(condition=k,**summary(v)) for k,v in conditions.items()])
    table('group_diagnostics',[dict(group=k,**summary(v)) for k,v in groups.items()])
    # Cross-check newly calculated aggregations with original records' summaries.
    old=read(B/'summary.json')['groups']
    for g,rr in groups.items():
        ss=summary(rr)
        for k in ['bias_mm','mae_mm','rmse_mm','max_ae_mm']:assert abs(ss[k]-old[g][k])<1e-10
    official=[]
    for r in read(F/'comparison.json'):
        m=read(F/f'{r["room"]}_{r["roi"]}'/'result.json')
        assert not m['gt_same_roi_confirmed'] and m['gt_rms_mm'] is None
        e,a,re=metrics(m['rms_mm'],r['reference_mm'])
        assert abs(a-r['absolute_difference_mm'])<1e-12
        official.append(dict(room=r['room'],roi=r['roi'],predicted_rms_mm=m['rms_mm'],official_reference_mm=r['reference_mm'],
            signed_reference_difference_mm=e,abs_reference_difference_mm=a,relative_reference_difference_pct=re,
            same_roi_confirmed=False,wall_status=r['wall_status'],accuracy_validation_status='pending_matching_reference_protocol',
            roi_json=str(F/f'{r["room"]}_{r["roi"]}_roi.json'),evidence_directory=str(F/f'{r["room"]}_{r["roi"]}')))
    table('official_reference_differences',official)
    clean=groups['clean'];zero=[r for r in scored if r['full_truth_rms_mm']==0]
    assert all(r['relative_error_full_pct'] is None for r in zero)
    assert all(r['abs_error_full_mm']<=1e-6 and r['precision']==1 and r['recall']==1 for r in clean)
    audit=dict(date='2026-11-22',operation='Audit and score existing runs; no remeasurement or parameter tuning',
        hashed_evidence_files=hash_count,synthetic_rows=len(scored),condition_rows=len(conditions),official_rows=len(official),
        zero_reference_rows=len(zero),undefined_relative_errors_correct=True,clean_numeric_gate_passed=True,
        production_unchanged=True,summary_crosschecks_passed=True,
        formal_real_wall_validation_complete=False,
        missing_real_reference=['Exact manual ROI or full-wall scope','Manual sampling and point weights','Reference-plane and RMS method','Reference measurement uncertainty','M04 official location image provenance'])
    dump(O/'audit.json',audit)
    manifest={str(f.relative_to(O)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(O.rglob('*')) if f.is_file()}
    dump(O/'manifest_sha256.json',manifest)
    print(json.dumps(audit,indent=2),flush=True)
if __name__=='__main__':main()
