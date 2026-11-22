# 测试四点选区、平面拟合、RMS 计算及非法几何输入的处理。
import unittest
import numpy as np
from wall_flatness.geometry import measure

def fixture():
    x,y=np.meshgrid(np.linspace(-.9,.9,21),np.linspace(-.9,.9,21))
    p=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)]
    cfg={'unit':'m','corners':[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]]}
    return p,cfg

class GeometryTests(unittest.TestCase):
    def test_plane(self):
        p,c=fixture();r=measure(p,c)
        self.assertLess(r['rms_mm'],1e-10);self.assertEqual(r['n_selected'],len(p))
    def test_known_rms(self):
        p,c=fixture();p=np.repeat(p,2,axis=0);p[:,2]=np.tile([-.002,.002],len(p)//2)
        self.assertAlmostEqual(measure(p,c)['rms_mm'],2,places=9)
    def test_transform_invariance(self):
        p,c=fixture();p[:,2]=.002*np.cos(6*p[:,0]);r=measure(p,c)
        q,_=np.linalg.qr(np.random.default_rng(1).normal(size=(3,3)));shift=np.array([20,-8,4])
        c['corners']=(np.array(c['corners'])@q+shift).tolist()
        self.assertAlmostEqual(measure(p@q+shift,c)['rms_mm'],r['rms_mm'],places=8)
    def test_units(self):
        p,c=fixture();p[:,2]=.003*np.cos(5*p[:,1]);r=measure(p,c)
        c['unit']='mm';c['corners']=(np.array(c['corners'])*1000).tolist()
        self.assertAlmostEqual(measure(p*1000,c)['rms_mm'],r['rms_mm'],places=9)
    def test_reverse_order(self):
        p,c=fixture();p[:,2]=.002*np.sin(p[:,0]*4);a=measure(p,c);c['corners']=c['corners'][::-1];b=measure(p,c)
        self.assertAlmostEqual(a['rms_mm'],b['rms_mm']);np.testing.assert_array_equal(a['indices'],b['indices'])
    def test_bulge_preserved(self):
        p,c=fixture();p[220,2]=.03;r=measure(p,c)
        self.assertEqual(r['n_selected'],len(p));self.assertGreater(r['max_abs_mm'],25)
    def test_exclude_wrong_wall_and_outside_polygon(self):
        p,c=fixture();p=np.vstack([p,[[0,0,1],[1.2,0,0]]]);r=measure(p,c)
        self.assertEqual(r['n_selected'],441);self.assertEqual(r['n_slab_excluded'],1)
    def test_non_axis_aligned_polygon(self):
        p,c=fixture();c['corners']=[[0,-1,0],[1,0,0],[0,1,0],[-1,0,0]];r=measure(p,c)
        self.assertTrue(np.all(np.abs(p[r['indices'],:2]).sum(1)<=1+1e-9))
        self.assertLess(r['n_selected'],441)
    def test_boundary_included(self):
        p,c=fixture();p=np.vstack([p,c['corners']]);self.assertEqual(measure(p,c)['n_selected'],445)
    def test_invalid_points_preserve_indices(self):
        p,c=fixture();p=np.vstack([[np.nan,0,0],p]);r=measure(p,c)
        self.assertEqual(r['n_invalid'],1);self.assertEqual(r['indices'][0],1)
    def test_low_coverage(self):
        p,c=fixture();p=p[:50];r=measure(p,c);self.assertIn('LOW_COVERAGE',r['warnings'])
    def test_degenerate_corners(self):
        for corners in [[[0,0,0]]*4,[[i,0,0] for i in range(4)], [[-1,-1,0],[1,1,0],[1,-1,0],[-1,1,0]], [[-1,-1,0],[1,-1,0],[0,0,0],[-1,1,0]]]:
            with self.subTest(corners=corners):
                p,c=fixture();c['corners']=corners
                with self.assertRaises(ValueError):measure(p,c)
    def test_nonplanar_corners(self):
        p,c=fixture();c['corners'][0][2]=.2
        with self.assertRaises(ValueError):measure(p,c)
    def test_invalid_corner_shape_and_nonfinite(self):
        for corners in [[[0,0,0]]*3,[[float('nan'),0,0],[1,0,0],[1,1,0],[0,1,0]]]:
            p,c=fixture();c['corners']=corners
            with self.assertRaises(ValueError):measure(p,c)
    def test_invalid_corner_shape_and_nonfinite(self):
        for corners in [[[0,0,0]]*3,[[float('nan'),0,0],[1,0,0],[1,1,0],[0,1,0]]]:
            p,c=fixture();c['corners']=corners
            with self.assertRaises(ValueError):measure(p,c)
    def test_invalid_config(self):
        for key,value in [('unit','cm'),('slab_half_thickness_mm',0),('coverage_grid_mm',-1),('min_points',2),('min_points',30.5),('unexpected',1),('max_corner_deviation_mm',float('nan'))]:
            with self.subTest(key=key):
                p,c=fixture();c[key]=value
                with self.assertRaises(ValueError):measure(p,c)
    def test_empty_and_line(self):
        p,c=fixture()
        for bad in [np.empty((0,3)),np.ones((100,3))*9,np.c_[np.linspace(-.9,.9,100),np.zeros((100,2))]]:
            with self.assertRaises(ValueError):measure(bad,c)
    def test_slab_edge_warning(self):
        p,c=fixture();p[:,2]=.049
        self.assertIn('NEAR_SLAB_BOUNDARY',measure(p,c)['warnings'])

if __name__=='__main__':unittest.main()
