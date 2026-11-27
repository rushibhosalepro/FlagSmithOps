"""Tests built on REAL output recorded during the live audit (CLI v2.0.0, Flagsmith Cloud, disposable flags)."""
import copy
import unittest

import _paths
import snapshot
import verdict


def rec(name):
    return _paths.load_json("recorded", name)


def capture(raw):
    return snapshot.capture(raw.get("feature", "f"), ["Production"], runner=_paths.env_aware(lambda a: copy.deepcopy(raw), ["Production"]))


class RealMultivariateTest(unittest.TestCase):
    def test_real_type_string_is_multivariate_and_is_detected(self):
        self.assertEqual(rec("flag_get_multivariate.json")["type"], "multivariate")
        res = snapshot.restore_commands(capture(rec("flag_get_multivariate.json")), "Production")
        self.assertTrue(res["multivariate_detected"])
        self.assertFalse(any("--value" in c for c in res["commands"]))

    def test_real_variant_weight_change_is_reported_by_verify(self):
        snap = capture(rec("flag_get_multivariate.json"))
        changed = rec("flag_get_multivariate.json")
        changed["variants"][1]["weight"] = 40
        problems = snapshot.verify(snap, runner=_paths.env_aware(lambda a: copy.deepcopy(changed), ["Production"]))
        self.assertEqual(problems, ["Production.default.variants[1].weight: 30 != 40"])

    def test_restore_does_not_claim_to_restore_weights(self):
        notes = " ".join(snapshot.restore_commands(capture(rec("flag_get_multivariate.json")), "Production")["notes"])
        self.assertIn("weights", notes)
        self.assertIn("not restored", notes)


class RealOverrideTest(unittest.TestCase):
    def test_identity_override_count_sets_has_overrides(self):
        snap = capture(rec("flag_get_identity_override.json"))
        self.assertIs(snap["has_overrides"], True)
        self.assertEqual(snap["summary"]["Production"]["identity_overrides"], 1)
        notes = " ".join(snapshot.restore_commands(snap, "Production")["notes"])
        self.assertIn("1 identity override(s) exist", notes)

    def test_real_targeting_reason_is_carried_into_the_check(self):
        import check_effect
        real = rec("evaluate_identity_override.json")
        out = check_effect.check("fsops_tmp_override", ["vip-user"], env="Production", runner=lambda a: real)
        self.assertTrue(out["result"].startswith("PARTIAL"))
        self.assertEqual(out["rows"][0]["reason"], "TARGETING_MATCH; segment=identity_overrides")


class RealPermanentTagTest(unittest.TestCase):
    def resolve(self, feature_name):
        tags = {t["id"]: t for t in rec("tags_list.json")}
        feature = next(f for f in rec("features_api_list.json") if f["name"] == feature_name)
        return [{"label": tags[i]["label"], "is_permanent": tags[i]["is_permanent"]} if i in tags else i for i in feature["tags"]]

    def candidate(self, tags):
        return {"flag": "x", "archived": False, "tags": tags, "stale": True, "multivariate": False,
                "evidence": {"state_read": True, "code_searched": True},
                "environments": {"Production": {"enabled": True}}, "production_environment": "Production",
                "environments_complete": True, "has_overrides": False,
                "references": {"sdk_calls": 1, "other_literals": 0, "dynamic_call_sites": 0, "unsearched_languages": []},
                "user": {"kept_behavior": "on", "other_usage": "none"},
                "snapshot": _paths.make_snapshot(flag="x", states={"Production": True})}

    def test_the_real_tag_object_has_is_permanent(self):
        self.assertIs(rec("tags_list.json")[0]["is_permanent"], True)

    def test_permanent_tagged_flag_is_refused(self):
        self.assertEqual(verdict.decide(self.candidate(self.resolve("fsops_tmp_perm")))["verdict"], "REFUSE")

    def test_unresolved_tag_ids_are_unknown_not_safe(self):
        feature = next(f for f in rec("features_api_list.json") if f["name"] == "fsops_tmp_perm")
        self.assertEqual(verdict.decide(self.candidate(feature["tags"]))["verdict"], "APPROVAL REQUIRED")

    def test_flag_with_no_tags_is_not_refused(self):
        self.assertEqual(verdict.decide(self.candidate(self.resolve("fsops_tmp_mv")))["verdict"], "PROCEED")


if __name__ == "__main__":
    unittest.main()