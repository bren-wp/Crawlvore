import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os
from tools.pack_portable import pack

class PortablePackingTests(unittest.TestCase):
    def test_payload_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);host=p/'host.exe';worker=p/'worker.exe';dest=p/'portable.exe'
            host.write_bytes(b'launcher');worker.write_bytes(b'payload')
            digest=hashlib.sha256(worker.read_bytes()).hexdigest()
            with self.assertRaises(ValueError): pack(host,worker,dest,'0'*64,7)
            self.assertFalse(dest.exists())
            pack(host,worker,dest,digest,7)
            self.assertEqual(dest.read_bytes(),b'launcherpayload')
            with self.assertRaises(FileExistsError): pack(host,worker,dest,digest,7)

    def test_existing_partial_is_not_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);host=p/'host.exe';worker=p/'worker.exe';dest=p/'portable.exe'
            host.write_bytes(b'launcher');worker.write_bytes(b'payload')
            previous=dest.with_suffix('.exe.incomplete');previous.write_bytes(b'older build')
            digest=hashlib.sha256(worker.read_bytes()).hexdigest()
            pack(host,worker,dest,digest,7)
            self.assertEqual(previous.read_bytes(),b'older build')
            self.assertEqual(dest.read_bytes(),b'launcherpayload')

    def test_concurrent_publication_preserves_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);host=p/'host.exe';worker=p/'worker.exe';dest=p/'portable.exe'
            host.write_bytes(b'launcher');worker.write_bytes(b'payload')
            digest=hashlib.sha256(worker.read_bytes()).hexdigest()
            link=os.link
            def race(source,target):
                Path(target).write_bytes(b'other verified artifact')
                link(source,target)
            with patch('tools.pack_portable.os.link',side_effect=race):
                with self.assertRaises(FileExistsError):pack(host,worker,dest,digest,7)
            self.assertEqual(dest.read_bytes(),b'other verified artifact')
            self.assertEqual(list(p.glob('portable.exe.*.incomplete')),[])

    def test_low_disk_space_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            from collections import namedtuple
            p=Path(tmp);host=p/'host.exe';worker=p/'worker.exe';dest=p/'portable.exe'
            host.write_bytes(b'launcher');worker.write_bytes(b'payload')
            usage=namedtuple('Usage','total used free')
            digest=hashlib.sha256(worker.read_bytes()).hexdigest()
            with patch('tools.pack_portable.shutil.disk_usage',return_value=usage(1,1,0)):
                with self.assertRaisesRegex(ValueError,'Insufficient free space'):pack(host,worker,dest,digest,7)
            self.assertFalse(dest.exists())
            self.assertEqual(host.read_bytes(),b'launcher')
            self.assertEqual(worker.read_bytes(),b'payload')
