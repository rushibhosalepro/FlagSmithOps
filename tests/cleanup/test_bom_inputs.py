"""Windows PowerShell 5 writes a byte-order mark with `Set-Content -Encoding utf8`.
Every script that reads a file an agent may have written must tolerate it.
Found by running the incident drill on the demo project."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import _paths
import candidates
import evidence
import snapshot
import verdict

BOM = "\ufeff"


def write_bom(text, name):
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(BOM + text)
    return path


class BomTest(unittest.TestCase):
    def test_flags_file_first_name_is_not_corrupted(self):
        repo = tempfile.mkdtemp()
        with open(os.path.join(repo, "checkout.js"), "w", encoding="utf-8") as handle:
            handle.write('hasFeature("new_checkout");\n')
        flags = write_bom("new_checkout\nold_banner\n", "flags.txt")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(candidates.main(["--repo", repo, "--keyword", "checkout", "--flags-file", flags]), 0)
        names = [c["flag"] for c in json.loads(buf.getvalue())["candidates"]]
        self.assertEqual(names, ["new_checkout"])
        self.assertNotIn(BOM, buf.getvalue().replace("\\ufeff", "X"))

    def test_verdict_input_file_with_bom(self):
        data = _paths.load_json("verdict_inputs", "unknown_overrides.json")
        path = write_bom(json.dumps(data), "c.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(verdict.main(["--input", path]), 0)
        self.assertEqual(json.loads(buf.getvalue())[0]["verdict"], "APPROVAL REQUIRED")

    def test_verdict_stdin_with_bom(self):
        data = _paths.load_json("verdict_inputs", "unknown_overrides.json")
        buf = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(BOM + json.dumps(data))), contextlib.redirect_stdout(buf):
            self.assertEqual(verdict.main([]), 0)
        self.assertEqual(json.loads(buf.getvalue())[0]["flag"], "unknown_overrides_flag")

    def test_evidence_input_with_bom(self):
        path = write_bom(json.dumps({"workflow": "flag-cleanup", "outcome": "REFUSED"}), "run.json")
        out = os.path.join(tempfile.mkdtemp(), "evidence.md")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evidence.main(["--input", path, "--out", out]), 0)
        with open(out, encoding="utf-8") as handle:
            self.assertIn("REFUSED", handle.read())

    def test_snapshot_file_with_bom(self):
        snap = snapshot.capture("f", ["Production"], runner=lambda a: _paths.load_json("recorded", "flag_get_production.json"))
        path = write_bom(json.dumps(snap), "snap.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(snapshot.main(["restore-commands", "--file", path, "--env", "Production"]), 0)
        self.assertIn("enable", buf.getvalue())


if __name__ == "__main__":
    unittest.main()