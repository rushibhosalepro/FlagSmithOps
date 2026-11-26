"""Covers FC-04, FC-05, FC-06 for the eight cleanup fixtures plus edge cases."""
import copy
import unittest

import _paths
import verdict

BASE = {
    "flag": "obsolete_flag",
    "tags": ["Stale"],
    "stale": True,
    "multivariate": False,
    "evidence": {"state_read": True, "code_searched": True},
    "environments": {"production": {"enabled": True}, "staging": {"enabled": True}},
    "production_environment": "production",
    "has_overrides": False,
    "references": {"sdk_calls": 2, "other_literals": 0, "dynamic_call_sites": 0, "unsearched_languages": []},
    "user": {"kept_behavior": "on", "other_usage": "none"},
}


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

    def test_overrides_true_needs_approval_and_none_is_unverified(self):
        self.assertEqual(make(has_overrides=True)["verdict"], "APPROVAL REQUIRED")
        r = make(has_overrides=None)
        self.assertEqual(r["verdict"], "PROCEED")
        self.assertIn("segment and identity overrides not checked", r["unverified"])

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


if __name__ == "__main__":
    unittest.main()