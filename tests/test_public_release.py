import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from tools.public_release import ALL_FILES,FILES,no_catalog,online_tar,validate,verify_remote
from tools.edition_acceptance import file_info


class PublicReleaseTests(unittest.TestCase):
    def test_catalog_members_rejected(self):
        for name in ("worker/_internal/tvrtk_output.csv","worker/registry-seed.json",
                     "opt/crawlvora/national-data/GB/manifest.json","workspace.sqlite3","db.sqlite3.gz"):
            with self.subTest(name=name),self.assertRaises(ValueError):
                no_catalog(name)
        no_catalog("worker/_internal/libsqlite3.so.0")

    def test_online_archive_identity(self):
        for payload,valid in (({"edition":"Online"},True),({"edition":"Full"},False)):
            data=json.dumps(payload).encode()
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode="w") as archive:
                info=tarfile.TarInfo("worker/_internal/edition.json")
                info.size=len(data)
                archive.addfile(info,io.BytesIO(data))
            buffer.seek(0)
            with tarfile.open(fileobj=buffer,mode="r") as archive:
                if valid:online_tar(archive)
                else:
                    with self.assertRaises(ValueError):online_tar(archive)

    def test_exact_remote_and_local_asset_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in FILES:(root/name).write_bytes(name.encode())
            (root/"SHA256SUMS.txt").write_text("".join(file_info(root/name)["sha256"]+"  "+name+"\n" for name in sorted(FILES)),encoding="ascii")
            data=validate(root)
            assets=[{"name":name,"state":"uploaded","size":info["size"],"digest":"sha256:"+info["sha256"]} for name,info in data.items()]
            self.assertEqual(set(data),ALL_FILES)
            verify_remote(root,{"draft":True,"assets":assets})
            with self.assertRaises(ValueError):verify_remote(root,{"draft":True,"assets":assets[:-1]})
            with self.assertRaises(ValueError):verify_remote(root,{"draft":False,"assets":assets})
            assets[0]["digest"]="sha256:"+"0"*64
            with self.assertRaises(ValueError):verify_remote(root,{"draft":True,"assets":assets})
