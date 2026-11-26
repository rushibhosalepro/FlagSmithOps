"""Covers PR-02 (CLI conventions, stop on failure, no secrets) and PR-04 (evidence)."""
import json
import os
import sys
import tempfile
import unittest

import _paths
import cli
import evidence

FAKE = [sys.executable, os.path.join(_paths.FIXTURES, "fake_flagsmith.py")]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.meter = os.path.join(tempfile.mkdtemp(), "meter.jsonl")

    def call(self, *args, **kw):
        return cli.run(list(args), binary=FAKE, meter_file=self.meter, **kw)

    def test_adds_no_input_and_json(self):
        out = self.call("flag", "get", "x")
        self.assertIn("--no-input", out["args"])
        self.assertIn("--json", out["args"])

    def test_jq_call_does_not_add_json(self):
        out = self.call("flag", "get", "x", "--jq", ".")
        self.assertNotIn("--json", out["args"])

    def test_failure_raises_with_exact_message_and_redacts_secrets(self):
        with self.assertRaises(cli.CliError) as ctx:
            self.call("flag", "get", "fail_flag")
        self.assertIn("boom", str(ctx.exception))
        self.assertNotIn("secret123", str(ctx.exception))
        self.assertEqual(ctx.exception.returncode, 1)

    def test_non_json_output_is_an_error(self):
        with self.assertRaises(cli.CliError):
            self.call("flag", "get", "bad_flag")

    def test_missing_binary_is_a_clear_error(self):
        with self.assertRaises(cli.CliError) as ctx:
            cli.run(["x"], binary=["definitely-not-a-real-binary"], meter_file=self.meter)
        self.assertIn("not found", str(ctx.exception))

    def test_meter_counts_calls_failures_and_bytes(self):
        self.call("flag", "get", "x")
        with self.assertRaises(cli.CliError):
            self.call("flag", "get", "fail_flag")
        s = cli.meter_summary(self.meter)
        self.assertEqual((s["calls"], s["failed"]), (2, 1))
        self.assertGreater(s["output_bytes"], 0)

    def test_cli_run_failure_exits_2_and_shows_the_error_without_secrets(self):
        import io
        import contextlib
        from unittest import mock
        err = io.StringIO()
        boom = cli.CliError("flagsmith exited 1: boom FLAGSMITH_API_KEY=[REDACTED]", ["flag", "get"], 1)
        with mock.patch.object(cli, "run", side_effect=boom), contextlib.redirect_stderr(err):
            code = cli.main(["run", "--", "flag", "get", "x"])
        self.assertEqual(code, 2)
        self.assertIn("boom", err.getvalue())
        self.assertNotIn("secret123", err.getvalue())

    def test_redact(self):
        self.assertNotIn("abc123", cli.redact("FLAGSMITH_API_KEY=abc123 and Bearer tok999"))
        self.assertNotIn("tok999", cli.redact("Authorization: Bearer tok999"))


class EvidenceTest(unittest.TestCase):
    DATA = {
        "workflow": "flag-cleanup", "requested": "clean up", "project": "demo", "environments": ["production"],
        "cli_version": "v2.0.0", "outcome": "COMPLETED",
        "candidates": [{"flag": "obsolete_flag", "verdict": "PROCEED", "reasons": ["ok"], "evidence": "2 refs"}],
        "approvals": [{"action": "archive", "scope": "obsolete_flag in production", "approved_by": "user", "when": "t"}],
        "commands": [{"command": "FLAGSMITH_API_KEY=abc123 flagsmith feature list", "result": "exit 0"}],
        "restore": ["flagsmith feature update obsolete_flag --unarchive"],
        "verification": {"checked": ["fresh state"], "not_checked": [], "result": "matches expected"},
        "not_verified": ["usage outside searched repositories"],
    }

    def test_renders_required_sections(self):
        text = evidence.render(self.DATA)
        for section in ("## Candidates and verdicts", "## Approvals", "## Commands run", "## Restore", "## Not verified"):
            self.assertIn(section, text)
        self.assertIn("| obsolete_flag | PROCEED | ok | 2 refs |", text)

    def test_redacts_credentials(self):
        self.assertNotIn("abc123", evidence.render(self.DATA))

    def test_cli_writes_file(self):
        d = tempfile.mkdtemp()
        src, dst = os.path.join(d, "run.json"), os.path.join(d, "evidence.md")
        with open(src, "w", encoding="utf-8") as h:
            json.dump(self.DATA, h)
        self.assertEqual(evidence.main(["--input", src, "--out", dst]), 0)
        self.assertTrue(os.path.getsize(dst) > 0)


if __name__ == "__main__":
    unittest.main()