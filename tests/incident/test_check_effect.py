"""Covers IR-08: verify behaviour, and report a partial mitigation when an override keeps it on."""
import unittest

import _paths
import check_effect
import cli


def runner_for(states):
    def run(args):
        identity = args[args.index("--identity") + 1]
        state = states[identity]
        if isinstance(state, Exception):
            raise state
        return {"feature": {"name": "f"}, "enabled": state}
    return run


class CheckEffectTest(unittest.TestCase):
    def test_all_off_is_mitigated_but_not_claimed_resolved(self):
        out = check_effect.check("f", ["a", "b"], runner=runner_for({"a": False, "b": False}))
        self.assertTrue(out["result"].startswith("MITIGATED"))
        self.assertIn("not proven resolved", out["result"])

    def test_override_keeping_feature_on_is_partial(self):
        out = check_effect.check("f", ["a", "vip"], runner=runner_for({"a": False, "vip": True}))
        self.assertEqual(out["result"], "PARTIAL: feature still on for vip")

    def test_cli_failure_is_unverified_not_success(self):
        out = check_effect.check("f", ["a", "b"], runner=runner_for({"a": False, "b": cli.CliError("exit 1: boom")}))
        self.assertTrue(out["result"].startswith("UNVERIFIED"))
        self.assertIn("boom", out["rows"][1]["error"])

    def test_partial_outranks_unverified(self):
        out = check_effect.check("f", ["a", "b"], runner=runner_for({"a": True, "b": cli.CliError("x")}))
        self.assertTrue(out["result"].startswith("PARTIAL"))

    def test_flag_state_finds_the_named_flag_in_a_list(self):
        data = {"flags": [{"name": "other", "enabled": True}, {"name": "f", "enabled": False}]}
        self.assertIs(check_effect.flag_state(data, "f"), False)

    def test_flag_state_unknown_when_shape_is_unrecognised(self):
        self.assertIsNone(check_effect.flag_state({"weird": 1}, "f"))

    def test_environment_is_passed_through(self):
        seen = []
        check_effect.check("f", ["a"], env="KEY", runner=lambda args: seen.append(args) or {"enabled": False})
        self.assertIn("--environment", seen[0])


if __name__ == "__main__":
    unittest.main()