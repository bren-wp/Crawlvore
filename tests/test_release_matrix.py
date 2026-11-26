import unittest
from tools.verify_release_assets import ALL_FILES,verify_remote

class ReleaseMatrixTests(unittest.TestCase):
    def test_exact_remote_matrix(self):
        local={name:{'size':123,'digest':'sha256:'+'1'*64} for name in ALL_FILES}
        assets=[{'name':name,'state':'uploaded',**data} for name,data in local.items()]
        verify_remote(local,{'draft':True,'assets':assets})
        with self.assertRaises(ValueError):verify_remote(local,{'draft':True,'assets':assets[:-1]})
        with self.assertRaises(ValueError):verify_remote(local,{'draft':False,'assets':assets})
        assets[0]['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):verify_remote(local,{'draft':True,'assets':assets})
