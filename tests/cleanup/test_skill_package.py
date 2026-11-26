"""Covers PR-08 (packaging): the skill validates and its scripts are in sync."""
import os
import subprocess
import sys
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "shared"))
import validate_skill  # noqa: E402

SKILL = os.path.join(_paths.ROOT, "skills", "flag-cleanup")


class PackageTest(unittest.TestCase):
    def test_skill_md_is_valid(self):
        self.assertEqual(validate_skill.validate(SKILL), [])

    def test_skill_md_stays_short(self):
        lines = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read().splitlines()
        self.assertLess(len(lines), 100)

    def test_skill_scripts_match_shared(self):
        proc = subprocess.run([sys.executable, os.path.join(_paths.ROOT, "shared", "sync.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_every_script_mentioned_in_skill_exists(self):
        text = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
        for name in set(__import__("re").findall(r"scripts/(\w+\.py)", text)):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "scripts", name)), name)


if __name__ == "__main__":
    unittest.main()