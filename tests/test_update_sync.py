import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Store,Collector
from registry import Registry
from automation import Queue

class UpgradeSyncTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/"db.sqlite")
        self.bot=Collector(self.store)
        self.registry=Registry(self.store)
        self.allowed=True
        with self.store.db() as c:self.store.upsert(c,{"title":"Existing company","mbs":"000000001"})
    def queue(self,version="8.1.7"):
        return Queue(self.store,self.bot,self.registry,lambda:("fixture","fixture"),app_version=version,authorized=lambda:self.allowed)
    def test_explicit_opt_in_once_per_version(self):
        q=self.queue()
        with patch("automation.start_registry") as start:
            q.tick();start.assert_not_called()
            with self.assertRaises(ValueError):q.update_policy(True,False)
            q.update_policy(True,True);q.tick()
            self.assertTrue(start.call_args.kwargs["allow_full_refresh"])
            self.bot.update(status="completed");q.tick();q.tick()
            self.assertEqual(start.call_count,1)
            q=self.queue();q.tick()
            self.assertEqual(start.call_count,1)
            q=self.queue("8.1.8");q.tick()
            self.assertEqual(start.call_count,2)
            self.assertEqual(self.store.stats()["total"],1)
    def test_revoked_authorization_and_downgrade(self):
        q=self.queue();q.update_policy(True,True)
        self.allowed=False
        with patch("automation.start_registry") as start:
            q.tick();start.assert_not_called()
            self.allowed=True;q.tick()
            self.bot.update(status="completed");q.tick()
            q=self.queue("8.1.6");q.tick()
            self.assertEqual(start.call_count,1)
    def test_interrupted_update_job_resumes_and_disable_cancels(self):
        q=self.queue();q.update_policy(True,True)
        with patch("automation.start_registry") as start:
            q.tick();self.assertEqual(start.call_count,1)
            q=self.queue();q.tick();self.assertEqual(start.call_count,2)
            q=self.queue();q.update_policy(False);q.tick()
            self.assertEqual(start.call_count,2)
            self.assertEqual(q.summary()["jobs"][0]["state"],"cancelled")
