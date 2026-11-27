import unittest
from unittest.mock import patch, Mock
from native_progress import sync_progress
from registry import start_registry
from core import Collector

class NativeProgressTests(unittest.TestCase):
    def test_only_committed_completion_reaches_100(self):
        for status,expected in [
            ({"status":"running","phase":"projection","projected":10,"projection_total":10},99),
            ({"status":"running","phase":"finalizing"},99),
            ({"status":"completed","phase":"complete"},100),
            ({"status":"completed","update_available":"22"},0),
            ({"status":"failed","phase":"complete"},0),
        ]:
            self.assertEqual(sync_progress(status,[])[0],expected)
    def test_counts_only_current_snapshot(self):
        categories=[{"snapshot":"21","done":1},{"snapshot":"22","done":1},{"snapshot":"22","done":0}]
        self.assertEqual(sync_progress({"status":"running","phase":"download","snapshot_id":"22","last":2},categories)[0],42.5)
    def test_thread_forwards_refresh_policy(self):
        bot=Collector(None)
        registry=Mock()
        registry.sync.return_value=False
        with patch("registry.Client") as client, patch("registry.threading.Thread") as thread:
            thread.side_effect=lambda target,daemon:Mock(start=target)
            start_registry(bot,registry,("test","test"),allow_full_refresh=False)
            registry.sync.assert_called_once_with(bot,client.return_value,500,pinned_snapshot=None,allow_full_refresh=False)
            self.assertEqual(bot.snapshot()["status"],"completed")
            self.assertNotIn("Sinkronizacija završena."," ".join(bot.snapshot()["logs"]))
