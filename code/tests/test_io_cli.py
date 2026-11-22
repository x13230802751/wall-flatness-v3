# 测试点云文件读取、命令行测量和输入错误处理。
import unittest,tempfile,zipfile,json,subprocess,sys
from pathlib import Path
import numpy as np
from wall_flatness.io import read_cloud

def pcd_bytes(mode='binary', count=3):
    header=f'VERSION 0.7\nFIELDS z x rgb y\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\nWIDTH {count}\nHEIGHT 1\nPOINTS {count}\nDATA {mode}\n'.encode()
    a=np.array([[3,1,0,2],[6,4,0,5],[9,7,0,8]],dtype='<f4')
    return header+(a.tobytes() if mode=='binary' else b'3 1 0 2\n6 4 0 5\n9 7 0 8\n')

class IOTests(unittest.TestCase):
    def test_pcd_formats_and_zip(self):
        with tempfile.TemporaryDirectory() as t:
            for mode in ['binary','ascii']:
                p=Path(t)/f'{mode}.pcd';p.write_bytes(pcd_bytes(mode))
                np.testing.assert_allclose(read_cloud(str(p)),[[1,2,3],[4,5,6],[7,8,9]])
            z=Path(t)/'data.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('room.pcd',pcd_bytes())
            np.testing.assert_allclose(read_cloud(str(z)+'::room.pcd'),read_cloud(str(Path(t)/'binary.pcd')))
    def test_bad_pcd(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad.pcd'
            for data in [pcd_bytes()[:-1],pcd_bytes(count=4),pcd_bytes('binary_compressed'),pcd_bytes().replace(b'FIELDS z x rgb y',b'FIELDS q x rgb y')]:
                p.write_bytes(data)
                with self.assertRaises(ValueError):read_cloud(str(p))
    def test_csv(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.csv';p.write_text('z,x,y\n3,1,2\n6,4,5\n')
            np.testing.assert_allclose(read_cloud(str(p)),[[1,2,3],[4,5,6]])

class CLITests(unittest.TestCase):
    def test_corrupt_zip_exit_two(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'bad.zip').write_bytes(b'not a zip');(root/'roi.json').write_text('{}')
            p=subprocess.run([sys.executable,'-m','wall_flatness','--cloud',str(root/'bad.zip')+'::r.pcd','--roi',str(root/'roi.json'),'--out',str(root/'out')],capture_output=True)
            self.assertEqual(p.returncode,2,p.stderr)
    def test_gt_requires_confirmation(self):
        from wall_flatness.__main__ import run
        with tempfile.TemporaryDirectory() as t:
            for gt,confirm in [(1,False),(None,True),(-1,True),(float('nan'),True)]:
                with self.subTest(gt=gt,confirm=confirm):
                    with self.assertRaises(ValueError):run('unused','unused',Path(t)/'out',gt,confirm)
    def test_gt_error_values(self):
        from wall_flatness.__main__ import run
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);x,y=np.meshgrid(np.linspace(-.9,.9,7),np.linspace(-.9,.9,7))
            p=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)];np.savetxt(root/'p.csv',p,delimiter=',',header='x,y,z',comments='')
            (root/'roi.json').write_text(json.dumps({'unit':'m','corners':[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]]}))
            r=run(str(root/'p.csv'),root/'roi.json',root/'out',1,True)
            self.assertEqual(r['abs_error_mm'],1);self.assertEqual(r['relative_error_pct'],100)
            z=run(str(root/'p.csv'),root/'roi.json',root/'zero',0,True)
            self.assertIsNone(z['relative_error_pct']);self.assertEqual(z['abs_error_mm'],0)
    def test_end_to_end_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);x,y=np.meshgrid(np.linspace(-.9,.9,11),np.linspace(-.9,.9,11));p=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)]
            np.savetxt(root/'p.csv',p,delimiter=',',header='x,y,z',comments='')
            cfg={'unit':'m','corners':[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]]};(root/'roi.json').write_text(json.dumps(cfg))
            cmd=[sys.executable,'-m','wall_flatness','--cloud',str(root/'p.csv'),'--roi',str(root/'roi.json'),'--out',str(root/'out')]
            a=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(a.returncode,0,a.stderr)
            result=json.loads((root/'out'/'result.json').read_text());self.assertAlmostEqual(result['rms_mm'],0);self.assertEqual(result['n_selected'],121)
            for name in ['summary.csv','distances.csv','roi_context.png','deviation_map.png','distance_histogram.png']:self.assertTrue((root/'out'/name).is_file(),name)
            self.assertEqual(len((root/'out'/'distances.csv').read_text().splitlines()),122)
            self.assertIsNone(result['gt_rms_mm']);self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)
    def test_missing_inputs_exit_two(self):
        p=subprocess.run([sys.executable,'-m','wall_flatness','--cloud','missing.pcd','--roi','missing.json','--out','unused'],capture_output=True)
        self.assertEqual(p.returncode,2)

if __name__=='__main__':unittest.main()
