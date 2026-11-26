"""Covers PR-08 (packaging) for flag-incident-response."""
import os
import re
import subprocess
import sys
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "shared"))
import validate_skill  # noqa: E402

SKILL = os.path.join(_paths.ROOT, "skills", "flag-incident-response")


class PackageTest(unittest.TestCase):
    def test_skill_md_is_valid(self):
        self.assertEqual(validate_skill.validate(SKILL), [])

    def test_skill_md_stays_short(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as handle:
            self.assertLess(len(handle.read().splitlines()), 100)

    def test_skill_scripts_match_shared(self):
        proc = subprocess.run([sys.executable, os.path.join(_paths.ROOT, "shared", "sync.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_every_script_mentioned_in_skill_exists(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        names = set(re.findall(r"scripts/(\w+\.py)", text))
        self.assertTrue(names)
        for name in names:
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "scripts", name)), name)

    def test_no_delete_or_archive_commands_in_skill(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("feature delete", text)
        self.assertNotIn("--archive", text)


if __name__ == "__main__":
    unittest.main()