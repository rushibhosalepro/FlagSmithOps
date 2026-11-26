"""Safety audit: unknown information must never silently become a safe state.

Covers: missing and malformed state, unknown and existing overrides, multivariate flags, incomplete environment
coverage, permanent-tag detection, strict typing, CLI delete guard and failed CLI operations.
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

CLEAN = {
    "flag": "obsolete_flag",
    "archived": False,
    "tags": [{"label": "cleanup-candidate", "is_permanent": False}],
    "stale": True,
    "multivariate": False,
    "evidence": {"state_read": True, "code_searched": True},
    "environments": {"production": {"enabled": True}, "staging": {"enabled": True}},
    "production_environment": "production",
    "environments_complete": True,
    "has_overrides": False,
    "references": {"sdk_calls": 2, "other_literals": 0, "dynamic_call_sites": 0, "unsearched_languages": []},
    "user": {"kept_behavior": "on", "other_usage": "none"},
}


def make(**changes):
    c = copy.deepcopy(CLEAN)
    for key, value in changes.items():
        if value is DELETE:
            c.pop(key, None)
        else:
            c[key] = value
    return verdict.decide(c)


DELETE = object()
BAD_VALUES = [None, "x", "true", "false", 0, 1, [], {}, -1, 1.5]


class BaselineTest(unittest.TestCase):
    def test_the_clean_candidate_proceeds(self):
        self.assertEqual(make()["verdict"], "PROCEED")


def _same(a, b):
    """Equal and of the same type (so 0 is not False)."""
    return type(a) is type(b) and a == b


def _is_legitimate(path, original, value):
    """Values that are valid inputs, so PROCEED is the correct answer for them."""
    if path == ("user", "other_usage"):
        return True                             # gates the archive instead of the PR. Asserted in its own test.
    if value is DELETE:
        return False
    if _same(value, original):
        return True
    if path == ("references", "sdk_calls"):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0   # any real count is valid
    if path == ("flag",):
        return isinstance(value, str) and bool(value.strip())
    if path == ("tags",):
        return value == []                      # no tags at all is a known state
    return False


class MutationTest(unittest.TestCase):
    """Take a candidate that proceeds, break one field at a time. Nothing may still PROCEED unless the value is valid."""

    PATHS = [(k,) for k in CLEAN] + [
        ("evidence", "state_read"), ("evidence", "code_searched"),
        ("environments", "production", "enabled"), ("environments", "staging", "enabled"),
        ("references", "sdk_calls"), ("references", "other_literals"),
        ("references", "dynamic_call_sites"), ("references", "unsearched_languages"),
        ("user", "kept_behavior"), ("user", "other_usage"),
    ]

    def mutate(self, path, value):
        c = copy.deepcopy(CLEAN)
        node = c
        for part in path[:-1]:
            node = node[part]
        original = node[path[-1]]
        if value is DELETE:
            del node[path[-1]]
        else:
            node[path[-1]] = copy.deepcopy(value)
        return c, original

    def test_every_deletion_and_wrong_value_never_proceeds(self):
        leaks = []
        for path in self.PATHS:
            for value in BAD_VALUES + [DELETE, "x", "obsolete-name"]:
                c, original = self.mutate(path, value)
                if _is_legitimate(path, original, value):
                    continue
                r = verdict.decide(c)
                if r["verdict"] == "PROCEED":
                    leaks.append("%s = %r" % (".".join(path), "<deleted>" if value is DELETE else value))
        self.assertEqual(leaks, [], "these mutations still PROCEED (unknown became safe): %s" % leaks)

    def test_an_unconfirmed_other_usage_is_gated_not_silently_ignored(self):
        for value in BAD_VALUES + [DELETE, "unknown", "x"]:
            c, _ = self.mutate(("user", "other_usage"), value)
            r = verdict.decide(c)
            if value == "in_use":
                self.assertEqual(r["verdict"], "REFUSE")
            else:
                self.assertTrue(any("other repository" in g for g in r["archive_gate"]), value)
                self.assertIn("usage outside the searched repositories not confirmed", r["unverified"], value)

    def test_the_legitimate_exemptions_really_do_proceed(self):
        for path, value in ((("flag",), "some_other_name"), (("tags",), []), (("references", "unsearched_languages"), []),
                            (("references", "other_literals"), 0), (("user", "other_usage"), "none")):
            c, _ = self.mutate(path, value)
            self.assertEqual(verdict.decide(c)["verdict"], "PROCEED", path)

class StrictBooleanTest(unittest.TestCase):
    def test_string_false_is_not_false(self):
        for field, bad in (("has_overrides", "false"), ("archived", "false"), ("multivariate", "false"), ("environments_complete", "true")):
            self.assertNotEqual(make(**{field: bad})["verdict"], "PROCEED", field)

    def test_string_true_does_not_satisfy_evidence(self):
        self.assertEqual(make(evidence={"state_read": "true", "code_searched": True})["verdict"], "REFUSE")
        self.assertEqual(make(evidence={"state_read": True, "code_searched": "yes"})["verdict"], "REFUSE")

    def test_only_a_real_true_accepts_unchecked_overrides(self):
        for bad in ("true", "yes", 1, "false", [], {}):
            r = make(has_overrides=None, user={"kept_behavior": "on", "other_usage": "none", "accept_unchecked_overrides": bad})
            self.assertEqual(r["verdict"], "APPROVAL REQUIRED", bad)
        r = make(has_overrides=None, user={"kept_behavior": "on", "other_usage": "none", "accept_unchecked_overrides": True})
        self.assertEqual(r["verdict"], "PROCEED")
        self.assertIn("segment and identity overrides not checked", r["unverified"])

    def test_malformed_enabled_values_are_unknown_never_off(self):
        for bad in (None, "false", "true", 0, 1, [], {}):
            r = make(environments={"production": {"enabled": bad}, "staging": {"enabled": True}}, user={"kept_behavior": "off", "other_usage": "none"})
            self.assertEqual(r["verdict"], "APPROVAL REQUIRED", bad)
            self.assertFalse(any("differs from production" in x for x in r["reasons"]), bad)


class OverridesTest(unittest.TestCase):
    def test_existing_overrides_need_approval(self):
        self.assertEqual(make(has_overrides=True)["verdict"], "APPROVAL REQUIRED")

    def test_unknown_overrides_need_approval_and_block_the_archive(self):
        r = make(has_overrides=None)
        self.assertEqual(r["verdict"], "APPROVAL REQUIRED")
        self.assertTrue(any("overrides checked" in g for g in r["archive_gate"]))


class MultivariateTest(unittest.TestCase):
    def test_unknown_multivariate_status_never_proceeds(self):
        self.assertEqual(make(multivariate=None)["verdict"], "APPROVAL REQUIRED")
        self.assertEqual(make(multivariate=DELETE)["verdict"], "APPROVAL REQUIRED")

    def test_multivariate_needs_a_named_variant(self):
        for kept in (None, "", 0, True, ["a"]):
            self.assertEqual(make(multivariate=True, user={"kept_behavior": kept, "other_usage": "none"})["verdict"], "APPROVAL REQUIRED", kept)
        self.assertEqual(make(multivariate=True, user={"kept_behavior": "variant_b", "other_usage": "none"})["verdict"], "PROCEED")

    def test_snapshot_does_not_restore_the_value_of_a_non_standard_flag(self):
        for type_value in ("multivariate", "MULTIVARIATE", "something_new"):
            raw = {"enabled": True, "value": "control", "type": type_value, "segment_overrides": 0, "identity_overrides": 0}
            snap = snapshot.capture("f", ["prod"], runner=lambda a, raw=raw: raw)
            res = snapshot.restore_commands(snap, "prod")
            self.assertTrue(res["multivariate_detected"], type_value)
            self.assertFalse(any("--value" in c for c in res["commands"]), type_value)

    def test_value_is_restored_only_for_an_explicit_standard_type(self):
        for raw, expect in (({"enabled": True, "value": "x", "type": "standard"}, True),
                            ({"enabled": True, "value": "x"}, False),
                            ({"enabled": True, "value": "x", "type": None}, False),
                            ({"enabled": True, "value": "x", "type": 5}, False)):
            snap = {"flag": "f", "environments": {"prod": {"default": raw, "segment_overrides": {}}}}
            res = snapshot.restore_commands(snap, "prod")
            self.assertEqual(any("--value" in c for c in res["commands"]), expect, raw)
        # the enable/disable command is still produced, because `enabled` applies to every type
        snap = {"flag": "f", "environments": {"prod": {"default": {"enabled": False, "type": "multivariate"}, "segment_overrides": {}}}}
        self.assertEqual(snapshot.restore_commands(snap, "prod")["commands"][0][2], "disable")


class EnvironmentCoverageTest(unittest.TestCase):
    def runner(self, args):
        return {"enabled": True, "type": "standard", "segment_overrides": 0, "identity_overrides": 0}

    def test_complete_only_when_the_project_list_was_checked_and_nothing_is_missing(self):
        s = snapshot.capture("f", ["a", "b"], runner=self.runner, known_envs=["a", "b"])
        self.assertIs(s["environments_complete"], True)

    def test_missing_environment_makes_it_incomplete(self):
        s = snapshot.capture("f", ["a"], runner=self.runner, known_envs=["a", "b", "c"])
        self.assertIs(s["environments_complete"], False)
        self.assertEqual(s["not_captured"], ["b", "c"])

    def test_unchecked_environment_list_is_unknown_not_complete(self):
        s = snapshot.capture("f", ["a", "b"], runner=self.runner)
        self.assertIsNone(s["environments_complete"])

    def test_verdict_blocks_proceed_for_unknown_or_incomplete_coverage(self):
        for value in (None, False, DELETE, "true"):
            self.assertEqual(make(environments_complete=value)["verdict"], "APPROVAL REQUIRED", value)
        r = make(environments_complete=False, environments_not_captured=["Development"])
        self.assertTrue(any("Development" in x for x in r["reasons"]))


class PermanentTagTest(unittest.TestCase):
    def tags(self, tags):
        return make(tags=tags)

    def test_permanent_attribute_refuses_whatever_the_label(self):
        self.assertEqual(self.tags([{"label": "x", "is_permanent": True}])["verdict"], "REFUSE")
        self.assertEqual(self.tags([{"label": "cleanup", "is_permanent": False}, {"label": "kill-switch", "is_permanent": True}])["verdict"], "REFUSE")

    def test_permanent_attribute_false_overrides_a_misleading_label(self):
        self.assertEqual(self.tags([{"label": "not-permanent-yet", "is_permanent": False}])["verdict"], "PROCEED")

    def test_plain_labels_cannot_show_permanence(self):
        self.assertEqual(self.tags(["Stale"])["verdict"], "APPROVAL REQUIRED")
        self.assertEqual(self.tags(["Permanent"])["verdict"], "REFUSE")
        self.assertEqual(self.tags(["long-lived permanent config"])["verdict"], "REFUSE")

    def test_missing_or_invalid_permanence_is_unknown(self):
        for tag in ({"label": "x"}, {"label": "x", "is_permanent": None}, {"label": "x", "is_permanent": "true"}, {"label": "x", "is_permanent": 1}, 5, None):
            self.assertEqual(self.tags([tag])["verdict"], "APPROVAL REQUIRED", tag)

    def test_unread_tags_are_unknown_and_empty_tags_are_known(self):
        self.assertEqual(self.tags(None)["verdict"], "APPROVAL REQUIRED")
        self.assertEqual(self.tags("Permanent")["verdict"], "APPROVAL REQUIRED")
        self.assertEqual(self.tags([])["verdict"], "PROCEED")

    def test_permanent_flag_field(self):
        self.assertEqual(make(permanent=True)["verdict"], "REFUSE")
        self.assertEqual(make(permanent="yes")["verdict"], "APPROVAL REQUIRED")


class MalformedInputTest(unittest.TestCase):
    def test_non_object_candidates_are_refused_not_crashed(self):
        for bad in ("x", 5, None, [], ["a"]):
            self.assertEqual(verdict.decide(bad)["verdict"], "REFUSE", bad)

    def test_a_candidate_without_a_name_is_refused(self):
        for bad in (DELETE, None, "", "  ", 5):
            self.assertEqual(make(flag=bad)["verdict"], "REFUSE", bad)

    def test_wrong_container_types_do_not_crash(self):
        r = make(evidence="x", user=[], references="x", environments="x")
        self.assertIn(r["verdict"], ("REFUSE", "APPROVAL REQUIRED"))

    def test_invalid_json_input_exits_2(self):
        path = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(verdict.main(["--input", path]), 2)
        self.assertIn("not valid JSON", err.getvalue())

    def test_reasons_never_hide_a_refusal(self):
        r = make(tags=[{"label": "x", "is_permanent": True}], stale=None)
        self.assertEqual(r["verdict"], "REFUSE")
        self.assertTrue(any("staleness" in x for x in r["reasons"]))


class DeleteGuardTest(unittest.TestCase):
    def blocked(self, *args):
        return cli.blocked_reason(list(args))

    def test_delete_subcommands_are_blocked(self):
        for args in (("feature", "delete", "x"), ("project", "delete", "1"), ("environment", "delete", "e"), ("env", "delete", "e"),
                     ("organisation", "delete", "o"), ("org", "delete", "o"), ("segment", "delete", "s"), ("flag", "delete", "f", "--segment", "1")):
            self.assertIsNotNone(self.blocked(*args), args)

    def test_delete_is_blocked_even_with_global_flags_first(self):
        self.assertIsNotNone(self.blocked("--yes", "-p", "123", "feature", "delete", "x"))
        self.assertIsNotNone(self.blocked("-e", "Production", "--jq", ".", "feature", "delete", "x"))

    def test_api_writes_are_blocked(self):
        for args in (("api", "/api/v1/projects/1/", "-X", "DELETE"), ("api", "/x", "--method", "delete"), ("api", "/x", "-XDELETE"),
                     ("api", "/x", "--method=PATCH"), ("api", "/x", "-X", "POST"), ("api", "/x", "-F", "name=x"),
                     ("api", "/x", "--field", "a=b"), ("api", "/x", "-f", "a=b"), ("api", "/x", "--input", "body.json"),
                     ("api", "/x", "-X", "")):
            self.assertIsNotNone(self.blocked(*args), args)

    def test_reads_and_the_allowed_writes_are_not_blocked(self):
        for args in (("api", "/api/v1/projects/1/features/"), ("api", "/x", "-X", "GET"), ("api", "/x", "--jq", ".results"),
                     ("feature", "list"), ("flag", "get", "delete"), ("flag", "disable", "f", "--yes"),
                     ("feature", "update", "f", "--archive", "--yes"), ("feature", "update", "f", "--unarchive", "--yes"),
                     ("evaluate", "f", "--identity", "u")):
            self.assertIsNone(self.blocked(*args), args)

    def test_run_refuses_before_calling_the_cli_and_records_it(self):
        meter = os.path.join(tempfile.mkdtemp(), "m.jsonl")
        with mock.patch("subprocess.run") as sp:
            with self.assertRaises(cli.CliError) as ctx:
                cli.run(["feature", "delete", "x"], meter_file=meter)
        sp.assert_not_called()
        self.assertIn("never deletes", str(ctx.exception))
        self.assertEqual(cli.meter_summary(meter)["failed"], 1)

    def test_the_wrapper_entry_point_exits_2_for_a_blocked_call(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(["run", "--", "feature", "delete", "x"]), 2)
        self.assertIn("blocked", err.getvalue())


class FailedCliTest(unittest.TestCase):
    def test_failed_capture_leaves_no_snapshot(self):
        target = os.path.join(tempfile.mkdtemp(), "s.json")
        with mock.patch.object(snapshot.cli, "run", side_effect=cli.CliError("exit 1: boom")):
            self.assertEqual(snapshot.main(["capture", "--flag", "f", "--env", "p", "--out", target]), 2)
        self.assertFalse(os.path.exists(target))

    def test_failed_verify_is_never_a_match(self):
        snap = snapshot.capture("f", ["p"], runner=lambda a: {"enabled": True, "type": "standard"})
        with self.assertRaises(cli.CliError):
            snapshot.verify(snap, runner=mock.Mock(side_effect=cli.CliError("exit 1: boom")))


class OutputFolderTest(unittest.TestCase):
    """Found in the live cleanup run: SKILL.md writes to .flag-cleanup/ before that folder exists."""

    def test_snapshot_capture_creates_the_output_folder(self):
        target = os.path.join(tempfile.mkdtemp(), ".flag-cleanup", "nested", "f.snapshot.json")
        raw = {"enabled": True, "type": "standard", "segment_overrides": 0, "identity_overrides": 0}
        with mock.patch.object(snapshot.cli, "run", return_value=raw), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(snapshot.main(["capture", "--flag", "f", "--env", "p", "--out", target]), 0)
        self.assertTrue(os.path.isfile(target))

    def test_evidence_creates_the_output_folder(self):
        import evidence
        src = os.path.join(tempfile.mkdtemp(), "run.json")
        with open(src, "w", encoding="utf-8") as handle:
            json.dump({"outcome": "COMPLETED"}, handle)
        target = os.path.join(tempfile.mkdtemp(), ".flag-cleanup", "evidence.md")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evidence.main(["--input", src, "--out", target]), 0)
        self.assertTrue(os.path.isfile(target))

class MeterIsolationTest(unittest.TestCase):
    def test_the_suite_never_writes_to_a_meter_set_outside_the_tests(self):
        self.assertIn("fsops-test-meter-", os.environ["FSOPS_METER_FILE"])

if __name__ == "__main__":
    unittest.main()