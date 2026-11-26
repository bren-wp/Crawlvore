import hashlib
import tempfile
import unittest
from pathlib import Path
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
