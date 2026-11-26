"""Covers IR-08: verify behaviour, report partial mitigation, never claim the incident is resolved."""
import contextlib
import io
import unittest
from unittest import mock

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


def run_main(states, identities, env="prod"):
    argv = ["--flag", "f", "--env", env] + [x for i in identities for x in ("--identity", i)]
    buf = io.StringIO()
    with mock.patch.object(check_effect.cli, "run", side_effect=runner_for(states)), contextlib.redirect_stdout(buf):
        code = check_effect.main(argv)
    return code, buf.getvalue()


class ResultTest(unittest.TestCase):
    def check(self, states, identities=None, env="prod"):
        return check_effect.check("f", identities or list(states), env=env, runner=runner_for(states))

    def test_flag_off_for_everyone_checked_still_does_not_claim_the_incident_is_resolved(self):
        out = self.check({"a": False, "b": False})
        self.assertTrue(out["result"].startswith("FLAG OFF"))
        self.assertTrue(out["incident_status"].startswith("NOT VERIFIED"))
        for text in (out["result"], out["incident_status"]):
            self.assertNotIn("RESOLVED", text.upper().replace("NOT VERIFIED", ""))

    def test_override_keeping_the_feature_on_is_partial(self):
        out = self.check({"a": False, "vip": True})
        self.assertEqual(out["result"], "PARTIAL: feature still on for vip")
        self.assertTrue(out["incident_status"].startswith("NOT VERIFIED"))

    def test_unknown_evaluation_result_is_unverified(self):
        out = check_effect.check("f", ["a"], env="prod", runner=lambda args: {"weird": 1})
        self.assertTrue(out["result"].startswith("UNVERIFIED"))
        self.assertIsNone(out["rows"][0]["enabled"])

    def test_failed_cli_call_is_unverified_not_success(self):
        out = self.check({"a": False, "b": cli.CliError("exit 1: boom")})
        self.assertTrue(out["result"].startswith("UNVERIFIED"))
        self.assertIn("boom", out["rows"][1]["error"])

    def test_partial_outranks_unverified(self):
        out = self.check({"a": True, "b": cli.CliError("x")})
        self.assertTrue(out["result"].startswith("PARTIAL"))

    def test_no_identities_is_unverified(self):
        out = check_effect.check("f", [], env="prod", runner=runner_for({}))
        self.assertTrue(out["result"].startswith("UNVERIFIED"))

    def test_no_environment_is_unverified_even_if_everything_looks_off(self):
        out = check_effect.check("f", ["a"], env=None, runner=runner_for({"a": False}))
        self.assertTrue(out["result"].startswith("UNVERIFIED"))
        self.assertIn("environment", out["result"])

    def test_environment_is_passed_to_every_evaluation(self):
        seen = []
        check_effect.check("f", ["a", "b"], env="KEY", runner=lambda args: seen.append(args) or {"enabled": False})
        self.assertEqual(len(seen), 2)
        for args in seen:
            self.assertEqual(args[args.index("--environment") + 1], "KEY")


class FlagStateTest(unittest.TestCase):
    def test_finds_the_named_flag_in_a_list(self):
        data = {"flags": [{"name": "other", "enabled": True}, {"name": "f", "enabled": False}]}
        self.assertIs(check_effect.flag_state(data, "f"), False)

    def test_nested_feature_name_form(self):
        self.assertIs(check_effect.flag_state({"feature": {"name": "f"}, "enabled": True}, "f"), True)

    def test_another_flags_state_is_never_used(self):
        self.assertIsNone(check_effect.flag_state({"flags": [{"name": "other", "enabled": True}]}, "f"))

    def test_non_boolean_enabled_is_unknown(self):
        self.assertIsNone(check_effect.flag_state({"feature": {"name": "f"}, "enabled": "false"}, "f"))

    def test_unrecognised_shape_is_unknown(self):
        self.assertIsNone(check_effect.flag_state({"weird": 1}, "f"))


class MainTest(unittest.TestCase):
    def test_flag_off_exits_0_but_still_says_incident_not_verified(self):
        code, text = run_main({"a": False}, ["a"])
        self.assertEqual(code, 0)
        self.assertIn("Incident: NOT VERIFIED", text)

    def test_partial_exits_1(self):
        code, text = run_main({"a": False, "vip": True}, ["a", "vip"])
        self.assertEqual(code, 1)
        self.assertIn("PARTIAL", text)
        self.assertIn("Incident: NOT VERIFIED", text)

    def test_cli_failure_exits_3(self):
        code, text = run_main({"a": cli.CliError("exit 1: boom")}, ["a"])
        self.assertEqual(code, 3)
        self.assertIn("boom", text)

    def test_environment_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                check_effect.main(["--flag", "f", "--identity", "a"])


if __name__ == "__main__":
    unittest.main()