"""All version-bearing build metadata must match the release version."""
import json
from pathlib import Path
import re
import tomllib
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ReleaseVersionTests(unittest.TestCase):
    def test_build_metadata_matches_version(self):
        version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
        self.assertRegex(version,r'^\d+\.\d+\.\d+$')
        for path in ('package.json','desktop/src-tauri/tauri.conf.json'):
            self.assertEqual(json.loads((ROOT/path).read_text(encoding='utf-8'))['version'],version)
        lock=json.loads((ROOT/'package-lock.json').read_text(encoding='utf-8'))
        self.assertEqual(lock['version'],version)
        self.assertEqual(lock['packages']['']['version'],version)
        cargo=tomllib.loads((ROOT/'desktop/src-tauri/Cargo.toml').read_text(encoding='utf-8'))
        self.assertEqual(cargo['package']['version'],version)
        rustlock=tomllib.loads((ROOT/'desktop/src-tauri/Cargo.lock').read_text(encoding='utf-8'))
        self.assertEqual([p['version'] for p in rustlock['package'] if p['name']==cargo['package']['name']],[version])
        self.assertRegex((ROOT/'CHANGELOG.md').read_text(encoding='utf-8'),r'(?m)^## '+re.escape(version)+r'\b')
