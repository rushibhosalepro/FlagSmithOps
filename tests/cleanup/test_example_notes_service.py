"""The notes-service example's README states these cleanup results. Keep them true."""
import json
import os
import tempfile
import unittest

import _paths
import find_refs
import snapshot
import verdict

REPO = os.path.join(_paths.ROOT, "examples", "notes-service")
FLAGS = ["search_v2", "legacy_export", "pdf_preview", "worker_batching"]
ENVS = [{"id": 1, "name": "Development"}, {"id": 2, "name": "Production"}]


def runner_for(states, calls=None):
    """Fake CLI matching the README's setup. states: {env: enabled}. Disables change the state."""
    states = dict(states)

    def run(args, gate=False):
        args = [str(a) for a in args]
        if calls is not None:
            calls.append(args)
        if args[:2] == ["environment", "list"]:
            return [dict(e) for e in ENVS]
        env = args[args.index("--environment") + 1]
        if args[:2] == ["flag", "disable"]:
            states[env] = False
        return {"type": "standard", "enabled": states[env], "value": None, "segment_overrides": 0, "identity_overrides": 0}
    return run

# Cleanup phase: after the search fix shipped and search_v2 was turned on everywhere.
STATES = {
    "search_v2": {"Development": True, "Production": True},
    "legacy_export": {"Development": True, "Production": True},
    "pdf_preview": {"Development": True, "Production": False},
    "worker_batching": {"Development": True, "Production": True},
}


class NotesServiceCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = find_refs.scan([REPO], FLAGS)

    def summary(self, flag):
        return self.refs["flags"][flag]["summary"]

    def decide(self, flag, kept=None, other_usage="none"):
        snap = snapshot.capture(flag, None, runner=runner_for(STATES[flag]))
        path = os.path.join(tempfile.mkdtemp(), flag + ".json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(snap, handle)
        s = self.summary(flag)
        return verdict.decide({
            "flag": flag, "archived": False, "tags": [], "stale": True, "multivariate": False,
            "evidence": {"state_read": True, "code_searched": True},
            "environments": {e: {"enabled": v["enabled"]} for e, v in snap["summary"].items()},
            "production_environment": "Production", "environments_complete": snap["environments_complete"],
            "has_overrides": snap["has_overrides"],
            "references": {"sdk_calls": s["sdk_calls"], "other_literals": s["other_literals"],
                           "dynamic_call_sites": self.refs["dynamic_call_sites_count"],
                           "unsearched_languages": self.refs["unsearched_languages"]},
            "user": {"kept_behavior": kept, "other_usage": other_usage}, "snapshot": path})

    def test_code_search_results(self):
        self.assertEqual(self.summary("search_v2"), {"sdk_calls": 1, "other_literals": 2})
        self.assertEqual(self.summary("legacy_export"), {"sdk_calls": 2, "other_literals": 1})
        self.assertEqual(self.summary("pdf_preview"), {"sdk_calls": 0, "other_literals": 2})
        self.assertEqual(self.summary("worker_batching"), {"sdk_calls": 0, "other_literals": 0})
        self.assertEqual(self.refs["dynamic_call_sites_count"], 1)
        self.assertTrue(self.refs["dynamic_call_sites"][0]["file"].endswith("src/features.js"))
        self.assertEqual(self.refs["unsearched_languages"], [".go"])

    def test_references_span_javascript_and_python(self):
        files = {r["file"].split(":", 1)[1] for r in self.refs["flags"]["legacy_export"]["references"]}
        self.assertIn("src/export.js", files)
        self.assertIn("scripts/export_notes.py", files)

    def test_no_candidate_proceeds_without_human_review(self):
        for flag, kept in (("search_v2", "on"), ("legacy_export", "on"), ("pdf_preview", None), ("worker_batching", None)):
            self.assertEqual(self.decide(flag, kept)["verdict"], "APPROVAL REQUIRED", flag)

    def test_worker_batching_is_not_called_unused_because_go_was_not_searched(self):
        r = self.decide("worker_batching", kept="on")
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("files in unsearched languages: .go", r["reasons"])

    def test_pdf_preview_shows_the_wrapper_and_the_environment_difference(self):
        reasons = " ".join(self.decide("pdf_preview")["reasons"])
        self.assertIn("non-literal flag name", reasons)
        self.assertIn("environments differ: Development=on, Production=off", reasons)

    def test_legacy_export_reasons_are_review_items_not_blockers(self):
        r = self.decide("legacy_export", kept="on")
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertFalse(any("kept behaviour" in x or "environments differ" in x for x in r["reasons"]))


if __name__ == "__main__":
    unittest.main()