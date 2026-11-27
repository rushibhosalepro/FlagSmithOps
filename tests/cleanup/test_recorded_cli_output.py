"""Tests against REAL output recorded from flagsmith CLI v2.0.0 (tests/fixtures/recorded).

Covers: override counts, enabled state, and the feature-level `enabled` trap.
"""
import copy
import unittest

import _paths
import snapshot


def recorded(name):
    return _paths.load_json("recorded", name)


def capture_with(raw_by_env):
    return snapshot.capture("new_checkout", list(raw_by_env), runner=_paths.env_aware(lambda a: copy.deepcopy(raw_by_env[a[a.index("--environment") + 1]]), list(raw_by_env)))


class RecordedFlagGetTest(unittest.TestCase):
    def setUp(self):
        self.snap = capture_with({"Production": recorded("flag_get_production.json")})

    def test_real_output_has_a_top_level_boolean_enabled(self):
        self.assertIs(snapshot.enabled_state(recorded("flag_get_production.json")), True)
        self.assertIs(self.snap["summary"]["Production"]["enabled"], True)

    def test_zero_override_counts_mean_no_overrides(self):
        self.assertEqual(self.snap["summary"]["Production"]["segment_overrides"], 0)
        self.assertIs(self.snap["has_overrides"], False)

    def test_lifecycle_stage_and_code_references_are_recorded_as_is(self):
        s = self.snap["summary"]["Production"]
        self.assertEqual(s["lifecycle_stage"], "new")
        self.assertEqual(s["code_references"], 0)

    def test_restore_enables_production_and_skips_the_null_value(self):
        res = snapshot.restore_commands(self.snap, "Production")
        self.assertEqual(res["commands"], [["flagsmith", "flag", "enable", "new_checkout", "--environment", "Production", "--yes"]])

    def test_note_says_overrides_are_counts_only(self):
        self.assertTrue(any("Override counts come from the CLI" in n for n in self.snap["notes"]))

    def test_feature_level_enabled_is_not_the_environment_state(self):
        # `feature list` and `feature get` report enabled=false for this flag while Production is enabled=true.
        self.assertIs(recorded("feature_list_item.json")["enabled"], False)
        self.assertIs(recorded("flag_get_production.json")["enabled"], True)


class OverrideCountTest(unittest.TestCase):
    def snap(self, **fields):
        raw = dict(recorded("flag_get_production.json"), **fields)
        return capture_with({"Production": raw})

    def test_segment_overrides_present(self):
        s = self.snap(segment_overrides=2)
        self.assertIs(s["has_overrides"], True)
        notes = snapshot.restore_commands(s, "Production")["notes"]
        self.assertTrue(any("2 segment and 0 identity override(s) exist" in n for n in notes))

    def test_identity_overrides_present(self):
        self.assertIs(self.snap(identity_overrides=1)["has_overrides"], True)

    def test_missing_counts_are_unknown_not_zero(self):
        raw = recorded("flag_get_production.json")
        del raw["segment_overrides"], raw["identity_overrides"]
        s = capture_with({"Production": raw})
        self.assertIsNone(s["has_overrides"])
        self.assertTrue(any("Override counts were not found" in n for n in s["notes"]))

    def test_invalid_counts_are_unknown(self):
        for bad in ("0", None, -1, 1.5, True, [], {}):
            self.assertIsNone(self.snap(segment_overrides=bad, identity_overrides=bad)["has_overrides"], bad)

    def test_one_unknown_count_keeps_the_answer_unknown(self):
        self.assertIsNone(self.snap(identity_overrides=None)["has_overrides"])

    def test_a_known_positive_count_wins_over_an_unknown_one(self):
        self.assertIs(self.snap(segment_overrides=3, identity_overrides=None)["has_overrides"], True)

    def test_overrides_in_any_environment_count(self):
        prod = recorded("flag_get_production.json")
        dev = dict(prod, identity_overrides=4)
        s = capture_with({"Production": prod, "Development": dev})
        self.assertIs(s["has_overrides"], True)

    def test_zero_everywhere_is_false_only_when_every_count_is_known(self):
        prod = recorded("flag_get_production.json")
        dev = dict(prod)
        del dev["identity_overrides"]
        self.assertIsNone(capture_with({"Production": prod, "Development": dev})["has_overrides"])


if __name__ == "__main__":
    unittest.main()