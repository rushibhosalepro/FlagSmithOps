"""Covers PR-03: state capture, restore commands, verification, and honesty about what is not restored.

Fixtures in tests/fixtures/cli_outputs are SYNTHETIC. The real CLI field names are unverified.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import _paths
import cli
import snapshot


def out(name):
    return _paths.load_json("cli_outputs", name)


def runner_from(table, project=None):
    """table maps (flag env) -> fixture name or Exception. Segment reads raise unless listed under (env, segment)."""
    names = project if project is not None else sorted({k if isinstance(k, str) else k[0] for k in table})

    def run(args):
        if list(args[:2]) == ["environment", "list"]:
            return _paths.project_list(names)
        env = args[args.index("--environment") + 1]
        key = (env, args[args.index("--segment") + 1]) if "--segment" in args else env
        value = table[key]
        if isinstance(value, Exception):
            raise value
        return out(value) if isinstance(value, str) else value
    return run


class CaptureTest(unittest.TestCase):
    def test_every_named_environment_is_captured_with_raw_state(self):
        snap = snapshot.capture("f", ["production", "staging"],
                                runner=runner_from({"production": "flag_get_enabled.json", "staging": "flag_get_disabled.json"}))
        self.assertEqual(set(snap["environments"]), {"production", "staging"})
        self.assertIs(snap["environments"]["production"]["default"]["enabled"], True)
        self.assertIs(snap["environments"]["staging"]["default"]["enabled"], False)

    def test_environments_left_out_are_reported_not_silently_skipped(self):
        snap = snapshot.capture("f", ["production"], runner=runner_from({"production": "flag_get_enabled.json"}, project=["dev", "production", "staging"]))
        self.assertEqual(snap["not_captured"], ["dev", "staging"])
        self.assertIs(snap["environments_complete"], False)
        self.assertTrue(any("not captured: dev, staging" in n for n in snap["notes"]))

    def test_without_a_readable_environment_list_coverage_is_unknown(self):
        def run(args):
            if list(args[:2]) == ["environment", "list"]:
                raise cli.CliError("exit 1: forbidden")
            return out("flag_get_enabled.json")
        snap = snapshot.capture("f", ["production"], runner=run)
        self.assertIsNone(snap["environments_complete"])
        self.assertTrue(any("environment list could not be read" in n for n in snap["notes"]))

    def test_overrides_not_captured_is_explicit(self):
        snap = snapshot.capture("f", ["production"], runner=runner_from({"production": "flag_get_enabled.json"}))
        self.assertTrue(any("Override counts were not found" in n and "were not captured" in n for n in snap["notes"]))
        self.assertIsNone(snap["has_overrides"])

    def test_captured_segment_overrides_are_marked_reference_only(self):
        runner = runner_from({"production": "flag_get_enabled.json", ("production", "7"): {"enabled": False}})
        snap = snapshot.capture("f", ["production"], segment_ids=[7], runner=runner)
        self.assertEqual(snap["environments"]["production"]["segment_overrides"]["7"], {"enabled": False})
        self.assertTrue(any("never restored" in n for n in snap["notes"]))

    def test_segment_read_error_is_recorded_not_raised(self):
        runner = runner_from({"production": "flag_get_enabled.json", ("production", "7"): cli.CliError("exit 1: none")})
        snap = snapshot.capture("f", ["production"], segment_ids=[7], runner=runner)
        self.assertIn("error", snap["environments"]["production"]["segment_overrides"]["7"])

    def test_failed_read_of_a_default_raises_so_no_partial_snapshot_is_used(self):
        runner = runner_from({"production": "flag_get_enabled.json", "staging": cli.CliError("exit 1: boom")})
        with self.assertRaises(cli.CliError):
            snapshot.capture("f", ["production", "staging"], runner=runner)

    def test_cli_capture_failure_exits_2_and_writes_no_file(self):
        target = os.path.join(tempfile.mkdtemp(), "snap.json")
        with mock.patch.object(snapshot.cli, "run", side_effect=cli.CliError("exit 1: boom")):
            code = snapshot.main(["capture", "--flag", "f", "--env", "production", "--out", target])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(target))


class EnabledStateTest(unittest.TestCase):
    def test_only_real_booleans_are_known(self):
        self.assertIs(snapshot.enabled_state(out("flag_get_enabled.json")), True)
        self.assertIs(snapshot.enabled_state(out("flag_get_disabled.json")), False)

    def test_missing_null_and_invalid_are_unknown_never_false(self):
        self.assertIsNone(snapshot.enabled_state(out("flag_get_missing_enabled.json")))
        self.assertIsNone(snapshot.enabled_state(out("flag_get_null_enabled.json")))
        for bad in ("true", 1, 0, [], {}):
            self.assertIsNone(snapshot.enabled_state({"enabled": bad}), bad)
        self.assertIsNone(snapshot.enabled_state("not a dict"))

    def test_a_nested_enabled_is_not_the_environment_default(self):
        self.assertIsNone(snapshot.enabled_state(out("flag_get_nested_enabled_only.json")))


def snap_of(name_by_env):
    return snapshot.capture("f", list(name_by_env), runner=runner_from(name_by_env))


class RestoreCommandsTest(unittest.TestCase):
    def cmds(self, snap, env):
        return snapshot.restore_commands(snap, env)

    def test_enabled_and_disabled_defaults_get_the_matching_command(self):
        snap = snap_of({"production": "flag_get_enabled.json", "staging": "flag_get_disabled.json"})
        self.assertEqual(self.cmds(snap, "production")["commands"][0][:4], ["flagsmith", "flag", "enable", "f"])
        self.assertEqual(self.cmds(snap, "staging")["commands"][0][:4], ["flagsmith", "flag", "disable", "f"])

    def test_multiple_environments_each_restore_to_their_own_state(self):
        snap = snap_of({"production": "flag_get_enabled.json", "staging": "flag_get_disabled.json", "dev": "flag_get_enabled.json"})
        verbs = {env: self.cmds(snap, env)["commands"][0][2] for env in snap["environments"]}
        self.assertEqual(verbs, {"production": "enable", "staging": "disable", "dev": "enable"})
        for env, verb in verbs.items():
            self.assertIn(env, self.cmds(snap, env)["commands"][0])

    def test_every_generated_write_carries_yes_and_the_notes_say_to_run_only_after_approval(self):
        res = self.cmds(snap_of({"production": "flag_get_enabled.json"}), "production")
        self.assertTrue(res["commands"])
        for command in res["commands"]:
            self.assertEqual(command[-1], "--yes")
        self.assertTrue(any("only after the user approves" in n for n in res["notes"]))

    def test_scalar_value_is_restored_for_a_plain_flag(self):
        cmds = self.cmds(snap_of({"production": "flag_get_enabled.json"}), "production")["commands"]
        self.assertIn("--value", cmds[1])
        self.assertIn("blue", cmds[1])

    def test_missing_enabled_generates_no_enable_or_disable_command(self):
        res = self.cmds(snap_of({"production": "flag_get_missing_enabled.json"}), "production")
        self.assertFalse(any(c[2] in ("enable", "disable") for c in res["commands"]))
        self.assertTrue(any("No boolean top-level 'enabled'" in n for n in res["notes"]))

    def test_null_enabled_generates_no_enable_or_disable_command(self):
        res = self.cmds(snap_of({"production": "flag_get_null_enabled.json"}), "production")
        self.assertFalse(any(c[2] in ("enable", "disable") for c in res["commands"]))

    def test_nested_enabled_never_becomes_a_production_command(self):
        res = self.cmds(snap_of({"production": "flag_get_nested_enabled_only.json"}), "production")
        self.assertFalse(any(c[2] in ("enable", "disable") for c in res["commands"]))

    def test_multivariate_flag_is_detected_and_value_not_restored(self):
        res = self.cmds(snap_of({"production": "flag_get_multivariate.json"}), "production")
        self.assertTrue(res["multivariate_detected"])
        self.assertFalse(any("--value" in c for c in res["commands"]))
        self.assertTrue(any("multivariate" in n for n in res["notes"]))

    def test_variant_values_are_never_used_as_the_flag_value(self):
        res = self.cmds(snap_of({"production": "flag_get_multivariate.json"}), "production")
        flat = json.dumps(res["commands"])
        self.assertNotIn("variant_a", flat)
        self.assertNotIn("variant_b", flat)

    def test_notes_always_say_what_is_not_restored(self):
        for name in ("flag_get_enabled.json", "flag_get_multivariate.json", "flag_get_missing_enabled.json"):
            notes = " ".join(self.cmds(snap_of({"production": name}), "production")["notes"])
            for phrase in ("Variants", "weights", "segment overrides", "identity overrides", "not restored"):
                self.assertIn(phrase, notes, name)


class VerifyTest(unittest.TestCase):
    def saved(self, name="flag_get_enabled.json"):
        return snap_of({"production": name})

    def test_identical_state_matches(self):
        self.assertEqual(snapshot.verify(self.saved(), runner=runner_from({"production": "flag_get_enabled.json"})), [])

    def test_timestamps_alone_do_not_cause_a_mismatch(self):
        live = dict(out("flag_get_enabled.json"), updated_at="t2")
        self.assertEqual(snapshot.verify(self.saved(), runner=runner_from({"production": live})), [])

    def test_restoration_mismatch_is_reported(self):
        problems = snapshot.verify(self.saved(), runner=runner_from({"production": "flag_get_disabled.json"}))
        self.assertTrue(any("enabled" in p for p in problems))

    def test_value_mismatch_is_reported(self):
        live = dict(out("flag_get_enabled.json"), feature_state_value="green")
        self.assertTrue(snapshot.verify(self.saved(), runner=runner_from({"production": live})))

    def test_multivariate_weight_change_is_reported_even_though_restore_cannot_fix_it(self):
        problems = snapshot.verify(self.saved("flag_get_multivariate.json"),
                                   runner=runner_from({"production": "flag_get_multivariate_reweighted.json"}))
        self.assertTrue(any("percentage_allocation" in p for p in problems))

    def test_mismatch_in_one_of_several_environments_is_reported(self):
        saved = snap_of({"production": "flag_get_enabled.json", "staging": "flag_get_disabled.json"})
        problems = snapshot.verify(saved, runner=runner_from({"production": "flag_get_enabled.json", "staging": "flag_get_enabled.json"}))
        self.assertTrue(problems)
        self.assertTrue(all(p.startswith("staging") for p in problems))

    def test_failed_read_during_verify_raises_instead_of_claiming_a_match(self):
        with self.assertRaises(cli.CliError):
            snapshot.verify(self.saved(), runner=runner_from({"production": cli.CliError("exit 1: boom")}))

    def test_cli_verify_exit_codes(self):
        path = os.path.join(tempfile.mkdtemp(), "snap.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.saved(), handle)
        with mock.patch.object(snapshot.cli, "run", side_effect=runner_from({"production": "flag_get_enabled.json"})):
            self.assertEqual(snapshot.main(["verify", "--file", path]), 0)
        with mock.patch.object(snapshot.cli, "run", side_effect=runner_from({"production": "flag_get_disabled.json"})):
            self.assertEqual(snapshot.main(["verify", "--file", path]), 1)
        with mock.patch.object(snapshot.cli, "run", side_effect=cli.CliError("exit 1: boom")):
            self.assertEqual(snapshot.main(["verify", "--file", path]), 2)


class DiffTest(unittest.TestCase):
    def test_ignores_timestamps_and_finds_real_changes(self):
        a = {"enabled": True, "updated_at": "t1"}
        self.assertEqual(snapshot.diff(a, {"enabled": True, "updated_at": "t2"}), [])
        self.assertEqual(len(snapshot.diff(a, {"enabled": False, "updated_at": "t1"})), 1)

    def test_reports_missing_keys_and_nested_paths(self):
        self.assertEqual(len(snapshot.diff({"x": {"y": 1}}, {"x": {"z": 1}})), 2)

    def test_list_length_change_is_reported(self):
        self.assertTrue(snapshot.diff({"v": [1, 2]}, {"v": [1]}))


if __name__ == "__main__":
    unittest.main()