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

    def test_release_zip_rejects_traversal_aliases_and_symlinks(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from tools.verify_release_assets import validate_zip
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"source.zip"
            for bad in ("Crawlvora/../secret","Crawlvora/..\\secret",
                        "Crawlvora/version","Crawlvora/dir//file",
                        "Crawlvora/file:stream"):
                with zipfile.ZipFile(path,"w") as archive:
                    archive.writestr("Crawlvora/VERSION","8.1.4")
                    archive.writestr("Crawlvora/package.json","{}")
                    archive.writestr(bad,"bad")
                with self.subTest(bad=bad),self.assertRaises(ValueError):
                    validate_zip(path)
            with zipfile.ZipFile(path,"w") as archive:
                archive.writestr("Crawlvora/VERSION","8.1.4")
                archive.writestr("Crawlvora/package.json","{}")
                info=zipfile.ZipInfo("Crawlvora/link")
                info.create_system=3
                info.external_attr=0o120777<<16
                archive.writestr(info,"../secret")
            with self.assertRaises(ValueError):validate_zip(path)
            with zipfile.ZipFile(path,"w") as archive:
                archive.writestr("Crawlvora/VERSION","8.1.4")
                archive.writestr("Crawlvora/package.json","{}")
            validate_zip(path)

    def test_wordpress_package_allowlist(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from tools.package_wordpress import build
        from tools.verify_release_assets import validate_zip
        with tempfile.TemporaryDirectory() as tmp:
            path=build(Path(tmp)/"plugin.zip")
            validate_zip(path,wordpress=True)
            with zipfile.ZipFile(path,"a") as archive:
                archive.writestr("crawlvora-business-directory/private.json","{}")
            with self.assertRaises(ValueError):validate_zip(path,wordpress=True)
