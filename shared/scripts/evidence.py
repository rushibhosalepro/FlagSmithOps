#!/usr/bin/env python3
"""Render evidence.md from a JSON description of a run. Credentials are redacted.

  python evidence.py --input run.json --out evidence.md

Input fields: workflow, requested, project, environments[], cli_version, outcome,
candidates[{flag, verdict, reasons[], evidence}], approvals[{action, scope, approved_by, when}],
commands[{command, result}], state_before, state_after, verification{checked[], not_checked[], result},
restore[], not_verified[]
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import read_text, redact  # noqa: E402


def _list(items, empty="none"):
    return "\n".join("- %s" % i for i in items) if items else "- %s" % empty


def render(d):
    out = ["# Evidence report", ""]
    out += [
        "Workflow: %s" % d.get("workflow", ""),
        "Date and time (UTC): %s" % d.get("when", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")),
        "Requested: %s" % d.get("requested", ""),
        "Flagsmith project: %s" % d.get("project", ""),
        "Environment(s): %s" % ", ".join(d.get("environments", [])),
        "CLI version: %s" % d.get("cli_version", "unknown"),
        "Outcome: %s" % d.get("outcome", ""),
        "",
        "## Candidates and verdicts",
        "| Flag | Verdict | Reason | Evidence |",
        "|---|---|---|---|",
    ]
    for c in d.get("candidates", []):
        out.append("| %s | %s | %s | %s |" % (c.get("flag"), c.get("verdict"), "; ".join(c.get("reasons", [])), c.get("evidence", "")))
    out += ["", "## Approvals", "| Action | Exact scope shown | Approved by | When |", "|---|---|---|---|"]
    for a in d.get("approvals", []):
        out.append("| %s | %s | %s | %s |" % (a.get("action"), a.get("scope"), a.get("approved_by"), a.get("when")))
    out += ["", "## Commands run"]
    out += ["%d. `%s` -> %s" % (i, c.get("command"), c.get("result")) for i, c in enumerate(d.get("commands", []), 1)] or ["none"]
    out += ["", "## State before", str(d.get("state_before", "")), "", "## State after", str(d.get("state_after", ""))]
    v = d.get("verification", {})
    out += ["", "## Verification", "Checked:", _list(v.get("checked")), "Not checked:", _list(v.get("not_checked")), "Result: %s" % v.get("result", "")]
    out += ["", "## Restore", "```", "\n".join(d.get("restore", [])) or "none", "```"]
    out += ["", "## Not verified", _list(d.get("not_verified"))]
    return redact("\n".join(out) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    ns = parser.parse_args(argv)
    text = render(json.loads(read_text(ns.input)))
    with open(ns.out, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("wrote %s" % ns.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())