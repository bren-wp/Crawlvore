import json
from pathlib import Path
import tempfile
import unittest
from tools.edition_acceptance import EDITIONS, names, record, verify

class EditionAcceptanceTests(unittest.TestCase):
    def test_exact_source_snapshot_and_asset_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source='a'*40
            manifest={'HR':{'database_sha256':'b'*64}}
            for edition,countries in EDITIONS.items():
                for name in names(edition):(root/name).write_bytes(name.encode())
                record(root,edition,source,'b'*64 if 'HR' in countries else '')
            verify(root,source,manifest)
            with self.assertRaisesRegex(ValueError,'mismatch'):verify(root,'d'*40,manifest)
            with self.assertRaisesRegex(ValueError,'mismatch'):verify(root,source,{'HR':{'database_sha256':'e'*64}})
            (root/'Setup-HR.exe').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'mismatch'):verify(root,source,manifest)

    def test_unexpected_database_in_online_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Unexpected snapshot'):
                record(Path(tmp),'Online','a'*40,'b'*64)

    def test_linux_receipts_bind_both_packages_to_same_commit_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source='a'*40
            manifest={'HR':{'database_sha256':'b'*64}}
            linux=root/'linux'
            for edition,countries in EDITIONS.items():
                hr='b'*64 if countries else ''
                for name in names(edition):(root/name).write_bytes(name.encode())
                record(root,edition,source,hr)
                directory=linux/edition;directory.mkdir(parents=True)
                for name in names(edition,'Linux'):(directory/name).write_bytes((edition+name).encode())
                record(directory,edition,source,hr,'Linux')
            verify(root,source,manifest,linux)
            receipt=linux/'Online'/'acceptance-Linux-Online.json'
            original=receipt.read_bytes()
            receipt.unlink()
            with self.assertRaisesRegex(ValueError,'Missing'):verify(root,source,manifest,linux)
            receipt.write_bytes(original)
            package=linux/'HR'/'Crawlvora-Linux-amd64.deb'
            package.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'mismatch'):verify(root,source,manifest,linux)

    def test_linux_online_rejects_bundled_snapshot_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Unexpected snapshot'):
                record(Path(tmp),'Online','a'*40,'b'*64,'Linux')
