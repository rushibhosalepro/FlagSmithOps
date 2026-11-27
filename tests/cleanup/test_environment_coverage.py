"""Environment-completeness gate: capture, verdict and archive verification all fail closed.

Root cause covered here: coverage used to be self-reported (--known-envs typed by the agent), the verdict
trusted hand-built candidate fields, and verify only re-read the environments already in the snapshot.
"""
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import _paths
import cli
import snapshot
import verdict

RAW = {"feature": "f", "type": "standard", "enabled": True, "segment_overrides": 0, "identity_overrides": 0}


def runner(project, states=None, fail_list=False, list_value=None):
    """Fake CLI. project: env names in the project. states: {env: enabled} (missing env -> CliError)."""
    states = states if states is not None else {n: True for n in project}
    calls = []

    def run(args):
        calls.append(list(args))
        if list(args[:2]) == ["environment", "list"]:
            if fail_list:
                raise cli.CliError("flagsmith exited 1: Error: forbidden")
            return list_value if list_value is not None else _paths.project_list(project)
        env = args[args.index("--environment") + 1]
        if env not in states:
            raise cli.CliError('flagsmith exited 1: Error: environment "%s" not found' % env)
        raw = dict(RAW, enabled=states[env])
        if states[env] is None:
            raw.pop("enabled")
        return raw
    run.calls = calls
    return run


def save(snap):
    path = os.path.join(tempfile.mkdtemp(), "f.snapshot.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(snap, handle)
    return path


def candidate_for(snap_path, **overrides):
    with open(snap_path, encoding="utf-8") as handle:
        snap = json.load(handle)
    c = {
        "flag": "f", "archived": False, "tags": [], "stale": True, "multivariate": False,
        "evidence": {"state_read": True, "code_searched": True},
        "environments": {e: {"enabled": s["enabled"]} for e, s in snap["summary"].items()},
        "production_environment": "Production",
        "environments_complete": snap["environments_complete"],
        "has_overrides": snap["has_overrides"],
        "references": {"sdk_calls": 1, "other_literals": 0, "dynamic_call_sites": 0, "unsearched_languages": []},
        "user": {"kept_behavior": "on", "other_usage": "none"},
        "snapshot": snap_path,
    }
    c.update(overrides)
    return c


def verify_cli(path, run):
    buf = io.StringIO()
    with mock.patch.object(snapshot.cli, "run", side_effect=run), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = snapshot.main(["verify", "--file", path])
    return code, buf.getvalue()


BOTH = ["Development", "Production"]


class BaselineTest(unittest.TestCase):
    def test_complete_snapshot_proceeds_and_verifies(self):
        snap = snapshot.capture("f", None, runner=runner(BOTH))
        self.assertIs(snap["environments_complete"], True)
        self.assertEqual([e["name"] for e in snap["project_environments"]], BOTH)
        path = save(snap)
        self.assertEqual(verdict.decide(candidate_for(path))["verdict"], "PROCEED")
        self.assertEqual(verify_cli(path, runner(BOTH))[0], 0)

    def test_environment_keys_are_never_stored(self):
        self.assertNotIn("key-", json.dumps(snapshot.capture("f", None, runner=runner(BOTH))))


class OmittedEnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.snap = snapshot.capture("f", ["Production"], runner=runner(BOTH))

    def test_capture_reports_the_omission_from_the_cli_list(self):
        self.assertIs(self.snap["environments_complete"], False)
        self.assertEqual(self.snap["not_captured"], ["Development"])

    def test_self_reported_known_envs_cannot_hide_the_omission(self):
        snap = snapshot.capture("f", ["Production"], runner=runner(BOTH), known_envs=["Production"])
        self.assertIs(snap["environments_complete"], False)
        self.assertTrue(any("does not match the project's environment list" in p for p in snap["coverage_problems"]))

    def test_verdict_does_not_proceed(self):
        r = verdict.decide(candidate_for(save(self.snap)))
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertTrue(any("not captured: Development" in x for x in r["reasons"]))

    def test_hand_copied_complete_true_is_caught(self):
        r = verdict.decide(candidate_for(save(self.snap), environments_complete=True))
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("environments_complete does not match the snapshot", r["reasons"])


class UnknownEnvironmentListTest(unittest.TestCase):
    def test_failed_list_makes_coverage_unknown(self):
        snap = snapshot.capture("f", ["Production"], runner=runner(BOTH, fail_list=True))
        self.assertIsNone(snap["environments_complete"])
        self.assertIsNone(snap["project_environments"])
        self.assertNotEqual(verdict.decide(candidate_for(save(snap)))["verdict"], "PROCEED")

    def test_malformed_lists_are_unknown(self):
        for bad in ([], "x", [{"name": "Production"}], [{"id": "1", "name": "P"}], [{"id": 1, "name": ""}],
                    [{"id": 1, "name": "P"}, {"id": 2, "name": "P"}], [{"id": True, "name": "P"}], ["P"]):
            snap = snapshot.capture("f", ["Production"], runner=runner(BOTH, list_value=bad))
            self.assertIsNone(snap["environments_complete"], bad)

    def test_capture_without_env_and_without_list_refuses(self):
        with self.assertRaises(cli.CliError):
            snapshot.capture("f", None, runner=runner(BOTH, fail_list=True))

    def test_archive_verify_fails_when_the_current_list_cannot_be_read(self):
        path = save(snapshot.capture("f", None, runner=runner(BOTH)))
        code, text = verify_cli(path, runner(BOTH, fail_list=True))
        self.assertEqual(code, 1)
        self.assertIn("current environment list could not be read", text)

    def test_old_snapshot_without_a_project_list_fails_verify(self):
        snap = snapshot.capture("f", None, runner=runner(BOTH))
        del snap["project_environments"]
        code, text = verify_cli(save(snap), runner(BOTH))
        self.assertEqual(code, 1)
        self.assertIn("no project environment list", text)


class NewEnvironmentTest(unittest.TestCase):
    def test_environment_added_after_the_snapshot_blocks_the_archive(self):
        path = save(snapshot.capture("f", None, runner=runner(BOTH)))
        code, text = verify_cli(path, runner(BOTH + ["Staging"]))
        self.assertEqual(code, 1)
        self.assertIn("environment added since the snapshot: Staging (not covered)", text)

    def test_environment_removed_after_the_snapshot_is_reported_without_crashing(self):
        path = save(snapshot.capture("f", None, runner=runner(BOTH)))
        # Flagsmith ids are stable: Production keeps id 2 after Development (id 1) is deleted.
        run = runner(["Production"], states={"Production": True}, list_value=[{"id": 2, "name": "Production"}])
        code, text = verify_cli(path, run)
        self.assertEqual(code, 1)
        self.assertIn("environment removed since the snapshot: Development", text)
        self.assertFalse(any("Development" in c for c in run.calls if c[0] == "flag"))


class RenamedEnvironmentTest(unittest.TestCase):
    def test_rename_is_detected_by_id_and_blocks_the_archive(self):
        path = save(snapshot.capture("f", None, runner=runner(BOTH)))
        renamed = runner(["Dev", "Production"])                  # same ids (1, 2) as before; 1 is now "Dev"
        code, text = verify_cli(path, renamed)
        self.assertEqual(code, 1)
        self.assertIn("environment renamed since the snapshot: Development -> Dev", text)
        self.assertFalse(any("Development" in c for c in renamed.calls if c[0] == "flag"))


class MissingStateTest(unittest.TestCase):
    def test_missing_enabled_makes_the_snapshot_incomplete(self):
        snap = snapshot.capture("f", None, runner=runner(BOTH, states={"Development": None, "Production": True}))
        self.assertIs(snap["environments_complete"], False)
        self.assertIn("enabled state unknown for: Development", snap["coverage_problems"])

    def test_candidate_cannot_fill_in_a_state_the_snapshot_did_not_record(self):
        snap = snapshot.capture("f", None, runner=runner(BOTH, states={"Development": None, "Production": True}))
        c = candidate_for(save(snap), environments={"Development": {"enabled": True}, "Production": {"enabled": True}}, environments_complete=True)
        r = verdict.decide(c)
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertTrue(any("candidate environments do not match the snapshot" in x for x in r["reasons"]))


class IncompleteSnapshotThenArchiveTest(unittest.TestCase):
    def test_incomplete_snapshot_fails_archive_verification_even_if_nothing_changed(self):
        path = save(snapshot.capture("f", ["Production"], runner=runner(BOTH)))
        code, text = verify_cli(path, runner(BOTH))
        self.assertEqual(code, 1)
        self.assertIn("snapshot did not cover every environment", text)
        self.assertIn("Capture it again before archiving", text)

    def test_recapturing_every_environment_clears_the_gate(self):
        path = save(snapshot.capture("f", None, runner=runner(BOTH)))
        self.assertEqual(verify_cli(path, runner(BOTH))[0], 0)


class SnapshotLinkTest(unittest.TestCase):
    def test_no_snapshot_linked_never_proceeds(self):
        c = candidate_for(save(snapshot.capture("f", None, runner=runner(BOTH))))
        for bad in (None, "", 5, os.path.join(tempfile.mkdtemp(), "missing.json")):
            self.assertEqual(verdict.decide(dict(c, snapshot=bad))["verdict"], "APPROVAL REQUIRED", bad)
        del c["snapshot"]
        self.assertEqual(verdict.decide(c)["verdict"], "APPROVAL REQUIRED")

    def test_snapshot_for_another_flag_is_rejected(self):
        snap = snapshot.capture("other", None, runner=runner(BOTH))
        r = verdict.decide(candidate_for(save(snap)))
        self.assertTrue(any("snapshot is for a different flag" in x for x in r["reasons"]))

    def test_has_overrides_must_match_the_snapshot(self):
        path = save(snapshot.capture("f", None, runner=runner(BOTH)))
        r = verdict.decide(candidate_for(path, has_overrides=None, user={"kept_behavior": "on", "other_usage": "none", "accept_unchecked_overrides": True}))
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertTrue(any("has_overrides does not match" in x for x in r["reasons"]))

    def test_corrupt_snapshot_file_never_proceeds(self):
        path = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        c = candidate_for(save(snapshot.capture("f", None, runner=runner(BOTH))), snapshot=path)
        self.assertEqual(verdict.decide(c)["verdict"], "APPROVAL REQUIRED")


class UnreadableSnapshotFileTest(unittest.TestCase):
    """Found during the live check: a missing snapshot file crashed verify with exit 1 (the 'different' code)."""

    def run_main(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            return snapshot.main(list(argv)), err.getvalue()

    def test_missing_file_exits_2_with_a_message(self):
        code, err = self.run_main("verify", "--file", os.path.join(tempfile.mkdtemp(), "nope.json"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read snapshot", err)

    def test_corrupt_or_wrong_shape_file_exits_2(self):
        for text in ("{not json", "[]", '{"flag": "f"}'):
            path = os.path.join(tempfile.mkdtemp(), "s.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            self.assertEqual(self.run_main("verify", "--file", path)[0], 2, text)
            self.assertEqual(self.run_main("restore-commands", "--file", path, "--env", "p")[0], 2, text)

if __name__ == "__main__":
    unittest.main()