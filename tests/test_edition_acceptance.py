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
