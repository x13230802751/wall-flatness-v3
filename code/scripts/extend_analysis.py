# 改变 M26 的测量区域，分析局部异常和附属构件对 RMS 的影响。
"""Explicit ROI change after observing M26 high-deviation fixtures; no residual deletion."""
from pathlib import Path
import sys,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from wall_flatness.geometry import roi_frame,measure
from wall_flatness.io import read_cloud
from wall_flatness.__main__ import run
from wall_flatness.plots import save_plots

def main():
    out=ROOT/'outputs';summary=json.loads((out/'experiment_summary.json').read_text(encoding='utf-8'))
    cfg=json.loads((ROOT/'examples'/'M26_demo.json').read_text())
    c,n,u,v,poly,_=roi_frame(np.array(cfg['corners']),.01)
    # The inspected original deviation image has a high-deviation feature at v~-0.5 m.
    # A new upper rectangle, explicitly documented, avoids that entire spatial area.
    uv=np.array([[-.60,0],[.60,0],[.60,.70],[-.60,.70]])
    cfg.update(roi_id='upper_patch_after_visual_review',corners=(c+uv[:,0,None]*u+uv[:,1,None]*v).tolist(),description='Separate upper spatial ROI selected after inspecting demo map; no residual filtering; not official GT ROI')
    roi=ROOT/'examples'/'M26_upper.json';roi.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    source=str(ROOT.parent/'data'/'Point_Cloud_Data.zip')+'::M26.pcd'
    r=run(source,roi,out/'M26_upper');p=read_cloud(source)
    checks=[]
    for half in [20,50,100]:
        rr=measure(p,{**cfg,'slab_half_thickness_mm':half});checks.append((half,rr['rms_mm'],rr['n_selected']))
    summary['records'].append(dict(case='M26_upper',rms_mm=r['rms_mm'],n_selected=r['n_selected'],coverage=r['coverage_fraction'],warnings=r['warnings']))
    a=np.genfromtxt(out/'M26_upper'/'distances.csv',names=True,delimiter=',');check=float(np.sqrt(np.mean(a['signed_distance_mm']**2)))
    summary['max_csv_recompute_difference_mm']=max(summary['max_csv_recompute_difference_mm'],abs(check-r['rms_mm']))
    summary['report_paragraphs'].append(f'M26 空间选区对照：原演示图下部有三个相邻高偏差块，外观类似墙面附属构件，未凭图像直接确认其类别。原区域随半厚度 20→50→100 mm 的 RMS 为 1.416→4.347→7.220 mm，说明它对厚度筛选高度敏感，不能将原结果直接解释为纯墙面粗糙度。程序没有自动删除这些点。')
    summary['report_paragraphs'].append(f'据此另建上部独立矩形 ROI，角点保存在 M26_upper.json，范围为原局部坐标 u=[−0.60,0.60] m、v=[0,0.70] m。新区域 RMS={r["rms_mm"]:.6f} mm，N={r["n_selected"]}；半厚度 20/50/100 mm 对照为 {checks}。这是改变空间测量范围的诊断实验，不能宣称“优化后官方误差降低”，也不能用新值替代原 ROI 结果。')
    summary['figures'].append(dict(title='M26 避开局部异常后的独立空间选区',path='outputs/M26_upper/deviation_map.png',caption=f'上部矩形为另一个已保存的四点输入；RMS={r["rms_mm"]:.4f} mm。比较体现选区定义对结果的影响，不是删除原选区中的高残差点。'))
    summary['upper_patch_sensitivity']=[{'half_thickness_mm':h,'rms_mm':x,'n_selected':n} for h,x,n in checks]
    (out/'experiment_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    # Regenerate all diagnostic images using current plotting code, retaining metrics.
    for rec in summary['records']:
        name=rec['case'];roi_name=name+'.json'
        if name.endswith('_demo'):cloud=str(ROOT.parent/'data'/'Point_Cloud_Data.zip')+f'::{name[:3]}.pcd'
        elif name=='M26_upper':cloud=source
        else:cloud=str(ROOT/'examples'/f'{name}.csv')
        cfg=json.loads((ROOT/'examples'/roi_name).read_text(encoding='utf-8'));p=read_cloud(cloud);rr=measure(p,cfg);save_plots(p,rr,out/name)
    print(json.dumps({'M26_upper_rms_mm':r['rms_mm'],'checks':checks}))

if __name__=='__main__':main()
