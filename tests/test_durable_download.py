import tempfile
import unittest
from pathlib import Path
from durable_download import transfer

class Reply:
    def __init__(self,status,headers,blocks):
        self.status_code=status;self.headers=headers;self.blocks=blocks
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,size):
        for chunk in self.blocks:
            if isinstance(chunk,Exception):raise chunk
            yield chunk

class Session:
    def __init__(self,*replies):self.replies=list(replies);self.headers=[]
    def get(self,url,**kw):
        self.headers.append(kw['headers']);return self.replies.pop(0)

class DurableDownloadTests(unittest.TestCase):
    def test_resume_across_restart_and_reuse_complete_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);name='snapshot.zip'
            a=Session(Reply(200,{'Content-Length':'8','ETag':'"one"'},[b'abcd',OSError('lost network')]))
            with self.assertRaises(OSError):transfer(a,'https://example.test',root,name,lambda:None,lambda **kw:None)
            self.assertEqual(next(root.glob('transfer-*/snapshot.zip')).read_bytes(),b'abcd')
            b=Session(Reply(206,{'Content-Length':'4','ETag':'"one"','Content-Range':'bytes 4-7/8'},[b'efgh']))
            path=transfer(b,'https://example.test',root,name,lambda:None,lambda **kw:None)
            self.assertEqual(b.headers[0]['Range'],'bytes=4-')
            self.assertEqual(b.headers[0]['If-Range'],'"one"')
            self.assertEqual(path.read_bytes(),b'abcdefgh')
            self.assertEqual(transfer(Session(),'https://example.test',root,name,lambda:None,lambda **kw:None),path)

    def test_changed_identity_never_overwrites_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);name='snapshot.zip'
            a=Session(Reply(200,{'Content-Length':'8','ETag':'"one"'},[b'abcd',OSError('closed')]))
            with self.assertRaises(OSError):transfer(a,'https://example.test',root,name,lambda:None,lambda **kw:None)
            old=next(root.glob('transfer-*/snapshot.zip'))
            b=Session(Reply(206,{'Content-Length':'4','ETag':'"two"','Content-Range':'bytes 4-7/8'},[b'xxxx']))
            with self.assertRaises(ValueError):transfer(b,'https://example.test',root,name,lambda:None,lambda **kw:None)
            self.assertEqual(old.read_bytes(),b'abcd')
            c=Session(Reply(200,{'Content-Length':'8','ETag':'"two"'},[b'12345678']))
            new=transfer(c,'https://example.test',root,name,lambda:None,lambda **kw:None)
            self.assertNotEqual(old,new);self.assertEqual(old.read_bytes(),b'abcd');self.assertEqual(new.read_bytes(),b'12345678')
