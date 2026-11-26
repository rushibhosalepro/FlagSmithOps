"""Covers PR-03 (state capture, restore commands, comparison)."""
import unittest

import _paths
import cli
import snapshot


def fake_runner(args):
    flag, env = args[2], args[args.index("--environment") + 1]
    if "--segment" in args:
        raise cli.CliError("exit 1: no override")
    return {"feature": flag, "environment": env, "enabled": env == "production", "updated_at": "t1",
            "feature_state_value": "blue"}


class SnapshotTest(unittest.TestCase):
    def test_capture_keeps_raw_state_for_every_environment(self):
        snap = snapshot.capture("f", ["production", "staging"], runner=fake_runner)
        self.assertEqual(set(snap["environments"]), {"production", "staging"})
        self.assertTrue(snap["environments"]["production"]["default"]["enabled"])

    def test_capture_without_segments_notes_overrides_not_captured(self):
        snap = snapshot.capture("f", ["production"], runner=fake_runner)
        self.assertTrue(any("overrides were not captured" in n for n in snap["notes"]))

    def test_segment_errors_are_recorded_not_raised(self):
        snap = snapshot.capture("f", ["production"], segment_ids=[7], runner=fake_runner)
        self.assertIn("error", snap["environments"]["production"]["segment_overrides"]["7"])

    def test_diff_ignores_timestamps_and_finds_real_changes(self):
        a = {"enabled": True, "updated_at": "t1"}
        self.assertEqual(snapshot.diff(a, {"enabled": True, "updated_at": "t2"}), [])
        self.assertEqual(len(snapshot.diff(a, {"enabled": False, "updated_at": "t1"})), 1)

    def test_diff_reports_missing_keys_and_nested_paths(self):
        out = snapshot.diff({"x": {"y": 1}}, {"x": {"z": 1}})
        self.assertEqual(len(out), 2)

    def test_restore_commands_from_enabled_flag(self):
        snap = snapshot.capture("f", ["production", "staging"], runner=fake_runner)
        on = snapshot.restore_commands(snap, "production")["commands"]
        off = snapshot.restore_commands(snap, "staging")["commands"]
        self.assertEqual(on[0][:4], ["flagsmith", "flag", "enable", "f"])
        self.assertEqual(off[0][:4], ["flagsmith", "flag", "disable", "f"])
        self.assertIn("--value", on[1])

    def test_restore_always_warns_that_variants_and_weights_are_not_restored(self):
        snap = snapshot.capture("f", ["production"], runner=fake_runner)
        notes = snapshot.restore_commands(snap, "production")["notes"]
        self.assertTrue(any("variants and weights are not restored" in n for n in notes))

    def test_restore_without_enabled_field_says_so(self):
        snap = {"flag": "f", "environments": {"production": {"default": {"weird": 1}}}}
        res = snapshot.restore_commands(snap, "production")
        self.assertEqual(res["commands"], [])
        self.assertTrue(res["notes"])


if __name__ == "__main__":
    unittest.main()