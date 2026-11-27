"""Regression gates for narrow, deliberately exposed desktop boundaries."""
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SecuritySurfaceTests(unittest.TestCase):
    def test_native_webview_exposes_no_global_tauri_or_capabilities(self):
        config=json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
        self.assertIs(config['app']['withGlobalTauri'],False)
        self.assertEqual(config['app']['security']['capabilities'],[])
        self.assertEqual(list((ROOT/'desktop/src-tauri/capabilities').glob('*.json')),[])

    def test_frontend_has_no_known_raw_html_or_browser_secret_storage_sinks(self):
        patterns=(r'\binnerHTML\b',r'\bouterHTML\b',r'\binsertAdjacentHTML\b',
                  r'\bdocument\.write\s*\(',r'\beval\s*\(',
                  r'\bnew\s+Function\s*\(',r'\blocalStorage\b',r'\bsessionStorage\b')
        for path in sorted((ROOT/'frontend').glob('*.ts')):
            content=path.read_text(encoding='utf-8')
            for pattern in patterns:
                with self.subTest(path=path.name,pattern=pattern):
                    self.assertIsNone(re.search(pattern,content))
