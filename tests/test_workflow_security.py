"""Keep third-party CI actions on immutable source revisions."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkflowSecurityTests(unittest.TestCase):
    def test_external_actions_are_pinned_to_full_commit_sha(self):
        workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
        self.assertTrue(workflows)
        count = 0
        for path in workflows:
            text = path.read_text(encoding="utf-8")
            for value in re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", text, re.M):
                if value.startswith("./"):
                    continue
                count += 1
                with self.subTest(workflow=path.name, action=value):
                    self.assertRegex(value, r"^[^@]+@[0-9a-f]{40}$")
        self.assertGreater(count, 0)
