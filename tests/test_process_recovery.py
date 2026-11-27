"""Actual process-death tests, isolated from live databases and credentials."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from core import Store, Collector
from registry import Registry
from test_registry import Fake

ROOT=Path(__file__).resolve().parents[1]
CHILD=Path(__file__).resolve()

def child(mode,root):
    if mode=='registry':
        store=Store(root/'companies.sqlite3')
        class Crash(Fake):
            def get(self,name,q=None):
                if name=='subjekti' and q['offset']==1:os._exit(73)
                return super().get(name,q)
        Registry(store).sync(Collector(store),Crash(),1)
    raise RuntimeError('Crash injection was not reached')

class ProcessRecoveryTests(unittest.TestCase):
    def kill_at_checkpoint(self,mode,root):
        env=dict(os.environ,PYTHONPATH=os.pathsep.join((str(ROOT),str(ROOT/'src'),str(ROOT/'tests'))))
        process=subprocess.run([sys.executable,str(CHILD),mode,str(root)],env=env,capture_output=True,timeout=60)
        self.assertEqual(process.returncode,73,process.stderr.decode(errors='replace'))

    def test_process_death_preserves_registry_page_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.kill_at_checkpoint('registry',root)
            store=Store(root/'companies.sqlite3');registry=Registry(store)
            with store.db() as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute("SELECT next_offset FROM registry_progress WHERE category='subjekti'").fetchone()[0],1)
            self.assertEqual(registry.browse('21','subjekti')['total'],1)
            client=Fake();registry.sync(Collector(store),client,1)
            self.assertNotIn(('subjekti',{'snapshot_id':'21','offset':0,'limit':1}),client.calls)
            self.assertEqual(registry.browse('21','subjekti')['total'],2)
            self.assertEqual(store.stats()['total'],2)

if __name__=='__main__':
    child(sys.argv[1],Path(sys.argv[2]))
