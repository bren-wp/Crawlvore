import unittest
from tools.verify_release_assets import ALL_FILES,verify_remote,validate_snapshots

class ReleaseMatrixTests(unittest.TestCase):
    def test_exact_remote_matrix(self):
        local={name:{'size':123,'digest':'sha256:'+'1'*64} for name in ALL_FILES}
        assets=[{'name':name,'state':'uploaded',**data} for name,data in local.items()]
        verify_remote(local,{'draft':True,'assets':assets})
        with self.assertRaises(ValueError):verify_remote(local,{'draft':True,'assets':assets[:-1]})
        with self.assertRaises(ValueError):verify_remote(local,{'draft':False,'assets':assets})
        assets[0]['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):verify_remote(local,{'draft':True,'assets':assets})

    def test_snapshot_manifest_counts_and_legacy_complete(self):
        categories={'subjekti':2,**{'category'+str(i):0 for i in range(35)}}
        hr={'scope':'all-status','category_count':36,'subjects':2,'rows':2,
            'categories':categories,'database_sha256':'a'*64}
        gb={'country':'GB','complete':True,'rows':3,'database_sha256':'b'*64}
        validate_snapshots(hr,gb)
        validate_snapshots({**hr,'complete':True},gb)
        for changes in ({'complete':False},{'complete':0},{'complete':'true'},
                        {'complete':None},{'progress':{}},{'completed_categories':36},
                        {'category_count':37},{'category_count':36.0},{'subjects':1},
                        {'subjects':True},{'rows':3},{'categories':{'subjekti':2}},
                        {'categories':{**categories,'category0':-1}},
                        {'categories':{**categories,'category0':False}},
                        {'database_sha256':None}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_snapshots({**hr,**changes},gb)
        for changes in ({'complete':1},{'rows':True},{'rows':'3'},
                        {'country':'HR'},{'database_sha256':42}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_snapshots(hr,{**gb,**changes})
