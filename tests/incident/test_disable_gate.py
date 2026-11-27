"""Incident pre-write gate: an invalid snapshot or a changed live state never reaches `flag disable`.

Every test records the CLI calls and asserts the number of write calls.
"""
import contextlib
import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths
import cli
import disable_gate
import snapshot

FLAG, ENV = "new_checkout", "Production"
PROJECT = ["Development", "Production"]
WRITES = ("disable", "enable", "--archive", "--unarchive", "--weight", "--disable", "--enable")


class FakeFlagsmith:
    """Fake CLI with mutable state. Records every call; writes change the state."""

    def __init__(self, states=None, project=None, list_error=False, list_value=None):
        self.states = dict(states if states is not None else {"Development": False, "Production": True})
        self.project = project if project is not None else list(PROJECT)
        self.list_error, self.list_value = list_error, list_value
        self.calls = []

    def __call__(self, args, gate=False):
        args = [str(a) for a in args]
        self.calls.append((args, gate))
        if args[:2] == ["environment", "list"]:
            if self.list_error:
                raise cli.CliError("flagsmith exited 1: Error: forbidden")
            return self.list_value if self.list_value is not None else _paths.project_list(self.project)
        env = args[args.index("--environment") + 1]
        if env not in self.states:
            raise cli.CliError('flagsmith exited 1: Error: environment "%s" not found' % env)
        if args[:2] == ["flag", "disable"]:
            self.states[env] = False
        raw = {"feature": FLAG, "type": "standard", "enabled": self.states[env], "value": None,
               "segment_overrides": 0, "identity_overrides": 0}
        if self.states[env] is None:
            del raw["enabled"]
        return raw

    def writes(self):
        return [a for a, _ in self.calls if any(w in a for w in WRITES)]


def save(data, raw=False):
    path = os.path.join(tempfile.mkdtemp(), "%s.snapshot.json" % FLAG)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(data if raw else json.dumps(data))
    return path


def complete_snapshot(fake=None, flag=FLAG, envs=None):
    return snapshot.capture(flag, envs, runner=fake or FakeFlagsmith())


class GateTest(unittest.TestCase):
    def assert_blocked(self, fake, path, phrase, env=ENV, flag=FLAG):
        status, problems, after = disable_gate.disable(flag, env, path, runner=fake)
        self.assertEqual(status, "blocked")
        self.assertTrue(any(phrase in p for p in problems), problems)
        self.assertEqual(fake.writes(), [], "a blocked gate made a write call")
        self.assertIsNone(after)
        return problems

    # --- the eight required cases -------------------------------------------
    def test_missing_snapshot(self):
        self.assert_blocked(FakeFlagsmith(), os.path.join(tempfile.mkdtemp(), "none.json"), "snapshot missing or unreadable")

    def test_corrupt_snapshot(self):
        for text in ("{not json", "", "[]", '"x"'):
            fake = FakeFlagsmith()
            status, problems, _ = disable_gate.disable(FLAG, ENV, save(text, raw=True), runner=fake)
            self.assertEqual(status, "blocked", text)
            self.assertEqual(fake.writes(), [], text)

    def test_wrong_flag(self):
        path = save(complete_snapshot(flag="old_banner"))
        self.assert_blocked(FakeFlagsmith(), path, "snapshot is for flag 'old_banner'")

    def test_wrong_environment(self):
        path = save(complete_snapshot())
        self.assert_blocked(FakeFlagsmith(), path, "is not in the snapshot", env="Prodution")

    def test_unknown_target_state(self):
        fake = FakeFlagsmith(states={"Development": False, "Production": None})
        snap = complete_snapshot(fake)
        self.assert_blocked(FakeFlagsmith(), save(snap), "enabled state of 'new_checkout' in 'Production' is unknown")

    def test_unknown_target_state_even_if_coverage_were_claimed(self):
        snap = complete_snapshot()
        snap["environments"][ENV]["default"]["enabled"] = "false"     # hand-edited, not a boolean
        self.assert_blocked(FakeFlagsmith(), save(snap), "is unknown in the snapshot")

    def test_incomplete_environment_coverage(self):
        snap = complete_snapshot(envs=[ENV])                          # Development omitted
        self.assertIs(snap["environments_complete"], False)
        self.assert_blocked(FakeFlagsmith(), save(snap), "does not cover every environment")

    def test_incomplete_coverage_is_never_accepted_by_editing_the_flag(self):
        snap = complete_snapshot(envs=[ENV])
        snap["environments_complete"] = True                          # hand-edited to look complete
        snap["coverage_problems"] = []
        self.assert_blocked(FakeFlagsmith(), save(snap), "missing environments from its own list: Development")

    def test_unknown_state_in_another_environment_is_not_hidden_by_editing(self):
        snap = complete_snapshot(FakeFlagsmith(states={"Development": None, "Production": True}))
        snap["environments_complete"], snap["coverage_problems"] = True, []
        self.assert_blocked(FakeFlagsmith(), save(snap), "enabled state unknown in the snapshot for: Development")

    def test_unknown_environment_list(self):
        snap = snapshot.capture(FLAG, [ENV], runner=FakeFlagsmith(list_error=True))
        self.assertIsNone(snap["environments_complete"])
        self.assert_blocked(FakeFlagsmith(), save(snap), "does not cover every environment")

    def test_unknown_current_environment_list_blocks_the_live_check(self):
        self.assert_blocked(FakeFlagsmith(list_error=True), save(complete_snapshot()), "current environment list could not be read")

    def test_complete_snapshot_with_valid_target_state_disables_once(self):
        fake = FakeFlagsmith()
        path = save(complete_snapshot(fake))
        fake.calls.clear()
        status, problems, after = disable_gate.disable(FLAG, ENV, path, runner=fake)
        self.assertEqual((status, problems, after), ("disabled", [], False))
        writes = fake.writes()
        self.assertEqual(writes, [["flag", "disable", FLAG, "--environment", ENV, "--yes"]])
        self.assertIs(fake.states["Development"], False)              # other environment untouched
        write_call = next(c for c in fake.calls if c[0][:2] == ["flag", "disable"])
        self.assertTrue(write_call[1], "the write must be made through the gate")
        reads_before = [a for a, _ in fake.calls[:fake.calls.index(write_call)]]
        self.assertIn(["environment", "list"], reads_before)
        self.assertIn(["flag", "get", FLAG, "--environment", ENV], reads_before)

    # --- live-state changes since the snapshot ---------------------------------
    def test_state_changed_since_the_snapshot(self):
        path = save(complete_snapshot())
        self.assert_blocked(FakeFlagsmith(states={"Development": False, "Production": False}), path, "state changed since the snapshot")

    def test_already_disabled_per_snapshot(self):
        fake = FakeFlagsmith(states={"Development": False, "Production": False})
        self.assert_blocked(fake, save(complete_snapshot(fake)), "already disabled")

    def test_environment_added_since_the_snapshot(self):
        path = save(complete_snapshot())
        self.assert_blocked(FakeFlagsmith(project=PROJECT + ["Staging"]), path, "environment 'Staging' was added since the snapshot")

    def test_environment_renamed_since_the_snapshot(self):
        path = save(complete_snapshot())
        fake = FakeFlagsmith(list_value=[{"id": 1, "name": "Development"}, {"id": 2, "name": "Prod"}])
        self.assert_blocked(fake, path, "no longer exists (or was renamed)")

    def test_environment_id_changed(self):
        path = save(complete_snapshot())
        fake = FakeFlagsmith(list_value=[{"id": 1, "name": "Development"}, {"id": 9, "name": "Production"}])
        self.assert_blocked(fake, path, "different id")

    def test_live_read_failure_blocks(self):
        path = save(complete_snapshot())
        fake = FakeFlagsmith()

        def failing(args, gate=False):
            if args[:2] == ["flag", "get"]:
                raise cli.CliError("flagsmith exited 1: boom")
            return fake(args, gate)
        status, problems, _ = disable_gate.disable(FLAG, ENV, path, runner=failing)
        self.assertEqual(status, "blocked")
        self.assertTrue(any("live check failed" in p for p in problems))
        self.assertEqual(fake.writes(), [])

    def test_empty_environment_name(self):
        for env in ("", "  ", None):
            self.assertEqual(disable_gate.validate(FLAG, env, save(complete_snapshot()), runner=FakeFlagsmith())[0], ["no environment named"])


class EnvironmentMappingTest(unittest.TestCase):
    """The live check compares the full saved and current name-to-id mapping, not just the target."""

    def setUp(self):
        self.path = save(complete_snapshot())            # Development=1, Production=2

    def run_gate(self, list_value):
        fake = FakeFlagsmith(list_value=list_value)
        status, problems, _ = disable_gate.disable(FLAG, ENV, self.path, runner=fake)
        return status, problems, fake

    def test_non_target_environment_id_changed(self):
        status, problems, fake = self.run_gate([{"id": 7, "name": "Development"}, {"id": 2, "name": "Production"}])
        self.assertEqual(status, "blocked")
        self.assertTrue(any("'Development' has a different id than in the snapshot (1, now 7)" in p for p in problems), problems)
        self.assertEqual(fake.writes(), [])

    def test_environment_deleted_and_recreated_with_the_same_name(self):
        # Same names as before; Development was deleted and recreated, so Flagsmith gave it a new id.
        status, problems, fake = self.run_gate([{"id": 2, "name": "Production"}, {"id": 31, "name": "Development"}])
        self.assertEqual(status, "blocked")
        self.assertTrue(any("deleted and recreated" in p for p in problems), problems)
        self.assertEqual(fake.writes(), [])

    def test_multiple_environment_ids_changed(self):
        status, problems, fake = self.run_gate([{"id": 11, "name": "Development"}, {"id": 12, "name": "Production"}])
        self.assertEqual(status, "blocked")
        changed = [p for p in problems if "has a different id" in p]
        self.assertEqual(len(changed), 2, problems)
        self.assertEqual(fake.writes(), [])

    def test_no_state_is_read_once_the_mapping_differs(self):
        _, _, fake = self.run_gate([{"id": 7, "name": "Development"}, {"id": 2, "name": "Production"}])
        self.assertFalse(any(a[:2] == ["flag", "get"] for a, _ in fake.calls))

    def test_unchanged_complete_mapping_is_allowed(self):
        status, problems, fake = self.run_gate([{"id": 1, "name": "Development"}, {"id": 2, "name": "Production"}])
        self.assertEqual((status, problems), ("disabled", []))
        self.assertEqual(len(fake.writes()), 1)

    def test_compare_environments_directly(self):
        saved = [{"id": 1, "name": "Development"}, {"id": 2, "name": "Production"}]
        self.assertEqual(disable_gate.compare_environments(saved, [{"id": 1, "name": "Development"}, {"id": 2, "name": "Production"}]), [])
        self.assertTrue(disable_gate.compare_environments(saved, [{"id": 2, "name": "Production"}]))
        self.assertTrue(disable_gate.compare_environments(None, [{"id": 1, "name": "Development"}]))
        self.assertTrue(disable_gate.compare_environments(["x"], [{"id": 1, "name": "Development"}]))


class CheckModeTest(unittest.TestCase):
    def run_main(self, fake, *argv):
        buf = io.StringIO()
        with mock.patch.object(disable_gate.cli, "run", side_effect=fake), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            return disable_gate.main(list(argv)), buf.getvalue()

    def test_check_mode_never_writes_even_when_valid(self):
        fake = FakeFlagsmith()
        path = save(complete_snapshot(FakeFlagsmith()))
        code, text = self.run_main(fake, "--flag", FLAG, "--env", ENV, "--snapshot", path)
        self.assertEqual(code, 0)
        self.assertIn("VALID", text)
        self.assertEqual(fake.writes(), [])

    def test_blocked_exits_3_with_no_write(self):
        fake = FakeFlagsmith()
        code, text = self.run_main(fake, "--flag", FLAG, "--env", ENV, "--snapshot", os.path.join(tempfile.mkdtemp(), "x.json"), "--execute")
        self.assertEqual(code, 3)
        self.assertIn("BLOCKED: nothing was written", text)
        self.assertEqual(fake.writes(), [])

    def test_execute_disables_and_reports_the_new_state(self):
        fake = FakeFlagsmith()
        path = save(complete_snapshot(FakeFlagsmith()))
        code, text = self.run_main(fake, "--flag", FLAG, "--env", ENV, "--snapshot", path, "--execute")
        self.assertEqual(code, 0)
        self.assertIn("DISABLED new_checkout in Production. enabled now: False", text)
        self.assertEqual(len(fake.writes()), 1)


class WrapperBlocksUngatedDisablesTest(unittest.TestCase):
    """The agent-facing wrapper refuses disables, so the gate cannot be skipped through it."""

    def test_wrapper_refuses_flag_disable_and_update_disable_without_starting_the_cli(self):
        for argv in (["run", "--", "flag", "disable", FLAG, "--environment", ENV, "--yes"],
                     ["run", "--", "-e", ENV, "flag", "disable", FLAG, "--yes"],
                     ["run", "--", "flag", "update", FLAG, "--disable", "--environment", ENV, "--yes"]):
            err = io.StringIO()
            with mock.patch("subprocess.run") as sp, contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(argv), 2, argv)
            sp.assert_not_called()
            self.assertIn("disable_gate.py", err.getvalue())

    def test_python_api_without_the_gate_flag_is_refused_too(self):
        with mock.patch("subprocess.run") as sp:
            with self.assertRaises(cli.CliError):
                cli.run(["flag", "disable", FLAG, "--environment", ENV, "--yes"])
        sp.assert_not_called()

    def test_gate_flag_allows_the_write_and_reads_are_unaffected(self):
        done = subprocess.CompletedProcess([], 0, stdout='{"enabled": false}', stderr="")
        with mock.patch("subprocess.run", return_value=done) as sp:
            cli.run(["flag", "disable", FLAG, "--environment", ENV, "--yes"], gate=True)
            cli.run(["flag", "get", FLAG, "--environment", ENV])
            cli.run(["flag", "enable", FLAG, "--environment", ENV, "--yes"])   # restore stays available
        self.assertEqual(sp.call_count, 3)

    def test_the_gate_cannot_be_used_to_delete(self):
        with mock.patch("subprocess.run") as sp:
            with self.assertRaises(cli.CliError):
                cli.run(["feature", "delete", FLAG], gate=True)
        sp.assert_not_called()


if __name__ == "__main__":
    unittest.main()