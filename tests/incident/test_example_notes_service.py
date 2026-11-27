"""The notes-service example's README states these incident results. Keep them true."""
import json
import os
import tempfile
import unittest

import _paths
import candidates
import disable_gate
import snapshot

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

# Incident phase: search_v2 on in Production (broken), off in Development.
INCIDENT = {"Development": False, "Production": True}


class NotesServiceIncidentTest(unittest.TestCase):
    def test_ranking_names_search_v2_but_asks_because_of_coverage_gaps(self):
        r = candidates.rank(REPO, FLAGS, ["search", "query"], git=lambda *a: None)
        self.assertEqual([c["flag"] for c in r["candidates"]], ["search_v2"])
        self.assertEqual(r["top_candidate"], "search_v2")
        self.assertFalse(r["clear_winner"])
        self.assertEqual(len(r["coverage_gaps"]), 2)
        self.assertTrue(any(".go" in g for g in r["coverage_gaps"]))

    def test_gate_allows_one_disable_of_search_v2_in_production_only(self):
        snap = snapshot.capture("search_v2", None, runner=runner_for(INCIDENT))
        self.assertIs(snap["environments_complete"], True)
        path = os.path.join(tempfile.mkdtemp(), "search_v2.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(snap, handle)
        calls = []
        status, problems, after = disable_gate.disable("search_v2", "Production", path, runner=runner_for(INCIDENT, calls))
        self.assertEqual((status, problems, after), ("disabled", [], False))
        writes = [c for c in calls if c[:2] == ["flag", "disable"]]
        self.assertEqual(writes, [["flag", "disable", "search_v2", "--environment", "Production", "--yes"]])

    def test_gate_refuses_development_where_the_flag_is_already_off(self):
        snap = snapshot.capture("search_v2", None, runner=runner_for(INCIDENT))
        path = os.path.join(tempfile.mkdtemp(), "search_v2.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(snap, handle)
        status, problems, _ = disable_gate.disable("search_v2", "Development", path, runner=runner_for(INCIDENT))
        self.assertEqual(status, "blocked")
        self.assertTrue(any("already disabled" in p for p in problems))

    def test_restore_command_turns_production_back_on(self):
        snap = snapshot.capture("search_v2", None, runner=runner_for(INCIDENT))
        cmds = snapshot.restore_commands(snap, "Production")["commands"]
        self.assertEqual(cmds[0], ["flagsmith", "flag", "enable", "search_v2", "--environment", "Production", "--yes"])


if __name__ == "__main__":
    unittest.main()