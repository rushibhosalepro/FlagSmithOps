"""Covers FC-03, FC-04 (code search, dynamic references, unsearched languages)."""
import os
import unittest

import _paths
import find_refs

REPO = os.path.join(_paths.FIXTURES, "repo_basic")
FLAGS = ["new_checkout", "old_banner", "py_flag", "config_flag", "multi_a", "multi_b", "absent_flag", "go_flag"]


class FindRefsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = find_refs.scan([REPO], FLAGS)

    def summary(self, flag):
        return self.result["flags"][flag]["summary"]

    def test_double_and_single_quoted_sdk_calls(self):
        self.assertEqual(self.summary("new_checkout"), {"sdk_calls": 1, "other_literals": 0})
        self.assertEqual(self.summary("old_banner")["sdk_calls"], 1)

    def test_python_sdk_call(self):
        self.assertEqual(self.summary("py_flag")["sdk_calls"], 1)

    def test_non_sdk_literal_is_reported_separately(self):
        self.assertEqual(self.summary("config_flag"), {"sdk_calls": 0, "other_literals": 1})

    def test_array_argument_lists_every_flag(self):
        self.assertEqual(self.summary("multi_a")["sdk_calls"], 1)
        self.assertEqual(self.summary("multi_b")["sdk_calls"], 1)

    def test_unreferenced_flag_has_no_references(self):
        self.assertEqual(self.result["flags"]["absent_flag"]["references"], [])

    def test_node_modules_is_skipped(self):
        files = [r["file"] for r in self.result["flags"]["new_checkout"]["references"]]
        self.assertFalse(any("node_modules" in f for f in files))

    def test_dynamic_call_sites_found(self):
        self.assertEqual(self.result["dynamic_call_sites_count"], 2)
        self.assertTrue(all("dynamic.js" in s["file"] for s in self.result["dynamic_call_sites"]))

    def test_unsupported_language_reported_not_searched(self):
        self.assertEqual(self.result["unsearched_languages"], [".go"])
        self.assertEqual(self.summary("go_flag"), {"sdk_calls": 0, "other_literals": 0})

    def test_reference_has_file_and_line(self):
        ref = self.result["flags"]["py_flag"]["references"][0]
        self.assertTrue(ref["file"].endswith("src/app.py"))
        self.assertEqual(ref["line"], 2)

    def test_summary_text_is_compact(self):
        text = find_refs.summary_text(self.result)
        self.assertIn("new_checkout: sdk_calls=1 other_literals=0", text)
        self.assertIn("dynamic call sites: 2", text)
        self.assertIn("unsearched languages: .go", text)
        self.assertLess(len(text), 1500)

    def test_missing_repo_exits_with_error(self):
        self.assertEqual(find_refs.main(["--repo", os.path.join(REPO, "nope"), "--flag", "x"]), 2)


if __name__ == "__main__":
    unittest.main()