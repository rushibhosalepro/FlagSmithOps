"""Covers IR-02, IR-03: evidence-backed candidates, and a stop when they cannot be separated."""
import os
import subprocess
import tempfile
import unittest

import _paths
import candidates


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", repo] + list(args),
                   check=True, capture_output=True)


def make_repo(files):
    repo = tempfile.mkdtemp()
    git(repo, "init", "-q")
    for rel, text in files.items():
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


class CandidatesTest(unittest.TestCase):
    def test_one_clearly_identified_flag(self):
        repo = make_repo({
            "src/checkout.js": 'if (flagsmith.hasFeature("checkout_v2")) { go(); }\n',
            "src/profile.js": 'if (flagsmith.hasFeature("dark_mode")) { go(); }\n',
        })
        out = candidates.rank(repo, ["checkout_v2", "dark_mode"], ["checkout"])
        self.assertTrue(out["clear_winner"])
        self.assertEqual(out["winner"], "checkout_v2")
        self.assertEqual([c["flag"] for c in out["candidates"]], ["checkout_v2"])
        self.assertTrue(out["candidates"][0]["evidence"])

    def test_several_similar_flags_do_not_produce_a_winner(self):
        repo = make_repo({"src/a.js": 'hasFeature("checkout_v2"); hasFeature("checkout_banner");\n'})
        out = candidates.rank(repo, ["checkout_v2", "checkout_banner"], ["checkout"])
        self.assertEqual(len(out["candidates"]), 2)
        self.assertFalse(out["clear_winner"])
        self.assertIsNone(out["winner"])

    def test_no_evidence_means_no_candidates(self):
        repo = make_repo({"src/a.js": 'hasFeature("dark_mode");\n'})
        out = candidates.rank(repo, ["dark_mode"], ["payments"])
        self.assertEqual(out["candidates"], [])
        self.assertFalse(out["clear_winner"])

    def test_flag_used_only_in_another_service_is_still_a_candidate_by_name(self):
        repo = make_repo({"src/a.js": "// nothing\n"})
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"])
        self.assertEqual(out["candidates"][0]["flag"], "checkout_v2")
        self.assertTrue(out["clear_winner"])

    def test_recent_commit_adds_evidence_and_unavailable_git_is_reported(self):
        repo = make_repo({"src/a.js": 'hasFeature("checkout_v2");\n'})
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"])
        self.assertTrue(any("commit(s)" in e for e in out["candidates"][0]["evidence"]))
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"], git=lambda *a: None)
        self.assertTrue(any("git history unavailable" in e for e in out["candidates"][0]["evidence"]))

    def test_dynamic_calls_are_surfaced_as_a_warning(self):
        repo = make_repo({"src/a.js": "hasFeature(name);\n"})
        self.assertEqual(candidates.rank(repo, ["x"], ["x"])["dynamic_call_sites"], 1)


if __name__ == "__main__":
    unittest.main()