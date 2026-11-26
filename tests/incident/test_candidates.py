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
    def test_no_matching_flag(self):
        repo = make_repo({"src/a.js": 'hasFeature("dark_mode");\n'})
        out = candidates.rank(repo, ["dark_mode"], ["payments"])
        self.assertEqual(out["candidates"], [])
        self.assertFalse(out["clear_winner"])
        self.assertIsNone(out["winner"])
        self.assertIsNone(out["top_candidate"])

    def test_no_flags_at_all(self):
        out = candidates.rank(make_repo({"src/a.js": "x\n"}), [], ["checkout"])
        self.assertEqual(out["candidates"], [])
        self.assertFalse(out["clear_winner"])

    def test_one_correct_candidate_with_two_kinds_of_evidence(self):
        repo = make_repo({
            "src/checkout.js": 'if (flagsmith.hasFeature("checkout_v2")) { go(); }\n',
            "src/profile.js": 'if (flagsmith.hasFeature("dark_mode")) { go(); }\n',
        })
        out = candidates.rank(repo, ["checkout_v2", "dark_mode"], ["checkout"])
        self.assertTrue(out["clear_winner"])
        self.assertEqual(out["winner"], "checkout_v2")
        self.assertEqual([c["flag"] for c in out["candidates"]], ["checkout_v2"])
        self.assertGreaterEqual(out["candidates"][0]["evidence_kinds"], 2)

    def test_the_ranking_is_always_marked_as_needing_confirmation(self):
        repo = make_repo({"src/checkout.js": 'hasFeature("checkout_v2");\n'})
        self.assertTrue(candidates.rank(repo, ["checkout_v2"], ["checkout"])["confirm_with_user"])
        self.assertTrue(candidates.rank(repo, ["checkout_v2"], ["nothing"])["confirm_with_user"])

    def test_multiple_plausible_candidates_do_not_produce_a_winner(self):
        repo = make_repo({"src/checkout.js": 'hasFeature("checkout_v2"); hasFeature("checkout_banner");\n'})
        out = candidates.rank(repo, ["checkout_v2", "checkout_banner"], ["checkout"])
        self.assertEqual(len(out["candidates"]), 2)
        self.assertFalse(out["clear_winner"])
        self.assertIsNone(out["winner"])
        self.assertIsNotNone(out["top_candidate"])

    def test_name_match_alone_is_not_enough_for_a_winner(self):
        repo = make_repo({"src/a.js": "// nothing\n"})
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"])
        self.assertEqual(out["candidates"][0]["flag"], "checkout_v2")
        self.assertFalse(out["clear_winner"])

    def test_incorrect_ranking_is_not_presented_as_certain(self):
        # The flag with the misleading name and a recent commit outscores the flag whose code is actually in the
        # checkout path. The lead is too small, so the skill must ask a human instead of choosing.
        repo = make_repo({
            "src/misc.js": 'hasFeature("checkout_banner");\n',
            "src/checkout/pricing.js": 'hasFeature("pricing_engine");\n',
        })
        out = candidates.rank(repo, ["checkout_banner", "pricing_engine"], ["checkout"])
        names = [c["flag"] for c in out["candidates"]]
        self.assertEqual(set(names), {"checkout_banner", "pricing_engine"})
        self.assertFalse(out["clear_winner"])
        self.assertIsNone(out["winner"])

    def test_a_flags_own_name_is_not_counted_as_code_evidence(self):
        repo = make_repo({"src/a.js": 'hasFeature("checkout_banner");\n'})
        evidence = candidates.rank(repo, ["checkout_banner"], ["checkout"])["candidates"][0]["evidence"]
        self.assertFalse(any(e.startswith("code mentions") for e in evidence))

    def test_another_flags_name_on_the_same_line_is_not_credited(self):
        repo = make_repo({"src/a.js": 'hasFeature("checkout_banner"); hasFeature("pricing_engine_v2");\n'})
        out = candidates.rank(repo, ["checkout_banner", "pricing_engine_v2"], ["checkout"])
        self.assertEqual([c["flag"] for c in out["candidates"]], ["checkout_banner"])

    def test_dynamic_sdk_calls_prevent_a_winner_and_are_reported(self):
        repo = make_repo({
            "src/checkout.js": 'hasFeature("checkout_v2");\n',
            "src/wrapper.js": "hasFeature(name);\n",
        })
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"])
        self.assertEqual(out["dynamic_call_sites"], 1)
        self.assertFalse(out["clear_winner"])
        self.assertTrue(any("non-literal flag name" in g for g in out["coverage_gaps"]))
        self.assertEqual(out["top_candidate"], "checkout_v2")

    def test_unsearched_languages_prevent_a_winner(self):
        repo = make_repo({
            "src/checkout.js": 'hasFeature("checkout_v2");\n',
            "svc/main.go": "package main\n",
        })
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"])
        self.assertFalse(out["clear_winner"])
        self.assertTrue(any(".go" in g for g in out["coverage_gaps"]))

    def test_recent_commit_adds_evidence_and_unavailable_git_is_reported(self):
        repo = make_repo({"src/checkout.js": 'hasFeature("checkout_v2");\n'})
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"])
        self.assertTrue(any("commit(s)" in e for e in out["candidates"][0]["evidence"]))
        out = candidates.rank(repo, ["checkout_v2"], ["checkout"], git=lambda *a: None)
        self.assertTrue(any("git history unavailable" in e for e in out["candidates"][0]["evidence"]))

    def test_repository_folder_name_is_not_code_evidence(self):
        # Found in the live run: repo folder "fsops_demo_shop" gave every referenced flag a code match for "fsops".
        import shutil
        base = tempfile.mkdtemp()
        repo = os.path.join(base, "checkout-service")
        shutil.copytree(make_repo({"src/a.js": 'hasFeature("dark_mode");\n'}), repo)
        out = candidates.rank(repo, ["dark_mode"], ["checkout"])
        self.assertEqual(out["candidates"], [])

    def test_a_folder_inside_the_repo_still_counts(self):
        repo = make_repo({"src/checkout/pay.js": 'hasFeature("dark_mode");\n'})
        evidence = candidates.rank(repo, ["dark_mode"], ["checkout"])["candidates"][0]["evidence"]
        self.assertTrue(any(e.startswith("code mentions: checkout") for e in evidence))

    def test_recent_change_alone_never_creates_a_candidate(self):
        repo = make_repo({"src/a.js": 'hasFeature("dark_mode");\n'})
        self.assertEqual(candidates.rank(repo, ["dark_mode"], ["payments"])["candidates"], [])


if __name__ == "__main__":
    unittest.main()