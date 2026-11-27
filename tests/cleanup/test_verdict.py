"""Covers FC-04, FC-05, FC-06 for the eight cleanup fixtures plus edge cases."""
import copy
import json
import os
import unittest

import _paths
import verdict

BASE = {
    "flag": "obsolete_flag",
    "archived": False,
    "tags": [{"label": "cleanup-candidate", "is_permanent": False}],
    "environments_complete": True,
    "stale": True,
    "multivariate": False,
    "evidence": {"state_read": True, "code_searched": True},
    "environments": {"production": {"enabled": True}, "staging": {"enabled": True}},
    "production_environment": "production",
    "has_overrides": False,
    "references": {"sdk_calls": 2, "other_literals": 0, "dynamic_call_sites": 0, "unsearched_languages": []},
    "user": {"kept_behavior": "on", "other_usage": "none"},
    "snapshot": _paths.make_snapshot(),
}
UNKNOWN_OVERRIDES_SNAPSHOT = _paths.make_snapshot(overrides=None)


def make(**changes):
    c = copy.deepcopy(BASE)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(c.get(key), dict):
            c[key].update(value)
        else:
            c[key] = value
    return verdict.decide(c)


class VerdictTest(unittest.TestCase):
    def test_1_obsolete_flag_proceeds(self):
        r = make()
        self.assertEqual(r["verdict"], "PROCEED")
        self.assertEqual(r["questions"], [])

    def test_2_flag_user_says_is_in_use_is_refused(self):
        self.assertEqual(make(user={"other_usage": "in_use"})["verdict"], "REFUSE")

    def test_3_permanent_tag_is_refused(self):
        self.assertEqual(make(tags=["Stale", "Permanent"])["verdict"], "REFUSE")
        self.assertEqual(make(permanent=True)["verdict"], "REFUSE")

    def test_4_enabled_in_production_needs_confirmation(self):
        r = make(user={"kept_behavior": None})
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("Keep the on code path?", r["questions"][0])

    def test_5_dynamic_references_need_approval(self):
        r = make(references={"dynamic_call_sites": 1})
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")

    def test_6_missing_evidence_is_refused_not_proceeded(self):
        self.assertEqual(make(evidence={"state_read": False})["verdict"], "REFUSE")
        self.assertEqual(make(evidence={"code_searched": False})["verdict"], "REFUSE")

    def test_7_multivariate_needs_named_variant(self):
        self.assertEqual(make(multivariate=True, user={"kept_behavior": None})["verdict"], "APPROVAL REQUIRED")
        self.assertEqual(make(multivariate=True, user={"kept_behavior": "variant_b"})["verdict"], "PROCEED")

    def test_8_other_usage_unknown_gates_the_archive(self):
        r = make(user={"other_usage": "unknown"})
        self.assertEqual(r["verdict"], "PROCEED")
        self.assertTrue(any("other repository" in g for g in r["archive_gate"]))
        self.assertTrue(r["unverified"])

    def test_none_usage_does_not_add_other_usage_gate(self):
        self.assertFalse(any("other repository" in g for g in make()["archive_gate"]))

    def test_staleness_unknown_or_false_needs_approval(self):
        self.assertEqual(make(stale=None)["verdict"], "APPROVAL REQUIRED")
        self.assertEqual(make(stale=False)["verdict"], "APPROVAL REQUIRED")

    def test_stale_tag_alone_does_not_proceed(self):
        r = make(user={"kept_behavior": None, "other_usage": "unknown"})
        self.assertNotEqual(r["verdict"], "PROCEED")

    def test_non_sdk_mentions_need_review(self):
        self.assertEqual(make(references={"other_literals": 1})["verdict"], "APPROVAL REQUIRED")

    def test_unsearched_languages_need_approval(self):
        self.assertEqual(make(references={"unsearched_languages": [".go"]})["verdict"], "APPROVAL REQUIRED")

    def test_kept_behaviour_must_match_production(self):
        self.assertEqual(make(user={"kept_behavior": "off"})["verdict"], "APPROVAL REQUIRED")

    def test_overrides_true_needs_approval(self):
        self.assertEqual(make(has_overrides=True)["verdict"], "APPROVAL REQUIRED")

    def test_unknown_overrides_do_not_proceed(self):
        r = make(has_overrides=None)
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("segment and identity overrides not checked", r["unverified"])
        self.assertTrue(any("Overrides" in q for q in r["questions"]))
        self.assertTrue(any("overrides checked" in g for g in r["archive_gate"]))

    def test_unknown_overrides_explicitly_accepted_can_proceed_but_stay_unverified(self):
        r = make(has_overrides=None, user={"accept_unchecked_overrides": True}, snapshot=UNKNOWN_OVERRIDES_SNAPSHOT)
        self.assertEqual(r["verdict"], "PROCEED")
        self.assertIn("segment and identity overrides not checked", r["unverified"])
        self.assertTrue(any("overrides checked" in g for g in r["archive_gate"]))

    def test_checked_overrides_add_no_archive_gate(self):
        self.assertFalse(any("overrides checked" in g for g in make(has_overrides=False)["archive_gate"]))

    def test_missing_enabled_state_is_not_treated_as_off(self):
        r = make(environments={"production": {}, "staging": {"enabled": True}}, user={"kept_behavior": "off"})
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertTrue(any("enabled state unknown for: production" in x for x in r["reasons"]))
        self.assertFalse(any("differs from production" in x for x in r["reasons"]))

    def test_null_or_non_boolean_enabled_is_unknown(self):
        for bad in (None, "true", 1, 0):
            r = make(environments={"production": {"enabled": bad}})
            self.assertEqual(r["verdict"], "APPROVAL REQUIRED", bad)
            self.assertTrue(any("enabled state unknown" in x for x in r["reasons"]), bad)

    def test_unknown_state_in_other_environment_blocks_proceed(self):
        r = make(environments={"production": {"enabled": True}, "staging": {"enabled": None}})
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")

    def test_missing_state_never_creates_a_false_environment_difference(self):
        r = make(environments={"production": {"enabled": False}, "staging": {}}, user={"kept_behavior": "off"})
        self.assertFalse(any("environments differ" in x for x in r["reasons"]))

    def test_missing_environment_value_object_is_unknown(self):
        r = make(environments={"production": None})
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")

    def test_missing_code_search_results_are_not_zero_references(self):
        r = make(references=None)
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("code search results missing or incomplete", r["reasons"])

    def test_unread_tags_cannot_proceed(self):
        r = make(tags=None)
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("permanent status is unknown", " ".join(r["reasons"]))

    def test_already_archived_is_refused(self):
        self.assertEqual(make(archived=True)["verdict"], "REFUSE")

    def test_unknown_production_environment_needs_approval(self):
        self.assertEqual(make(production_environment="prod")["verdict"], "APPROVAL REQUIRED")

    def test_environment_difference_is_reported(self):
        r = make(environments={"staging": {"enabled": False}})
        self.assertTrue(any("environments differ" in x for x in r["reasons"]))

    def test_refuse_outranks_approval(self):
        r = make(tags=["permanent"], stale=None)
        self.assertEqual(r["verdict"], "REFUSE")


class VerdictFixtureFilesTest(unittest.TestCase):
    """Runs verdict.py end to end on fixture files, the way the skill does."""

    def run_file(self, name):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = verdict.main(["--input", os.path.join(_paths.FIXTURES, "verdict_inputs", name)])
        self.assertEqual(code, 0)
        return json.loads(buf.getvalue())[0]

    def test_missing_enabled_field_in_production(self):
        r = self.run_file("missing_enabled.json")
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("enabled state unknown for: production", r["reasons"])

    def test_null_enabled_field_in_production(self):
        r = self.run_file("null_enabled.json")
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("enabled state unknown for: production", r["reasons"])

    def test_unknown_overrides_from_file(self):
        r = self.run_file("unknown_overrides.json")
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertIn("segment and identity overrides not checked", r["unverified"])

    def test_multiple_environment_configurations_need_a_decision(self):
        r = self.run_file("multi_environment.json")
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertTrue(any("environments differ" in x and "staging=off" in x for x in r["reasons"]))


if __name__ == "__main__":
    unittest.main()