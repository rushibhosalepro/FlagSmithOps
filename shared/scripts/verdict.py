#!/usr/bin/env python3
"""Decide PROCEED / APPROVAL REQUIRED / REFUSE for flag cleanup candidates.

Input: a JSON object or list of objects. Fields (all optional unless noted):
  flag (required), archived, tags[], permanent,
  evidence {state_read, code_searched},
  stale (true/false/null: whether staleness is established),
  multivariate,
  environments {name: {enabled: bool}}, production_environment,
  has_overrides (true/false/null),
  references {sdk_calls, other_literals, dynamic_call_sites, unsearched_languages[]},
  user {kept_behavior: "on"|"off"|<variant name>|null, other_usage: "none"|"unknown"|"in_use"}

PROCEED means eligible to be presented for approval. It never skips approval for a Flagsmith write.

  python verdict.py --input candidates.json [--table]
"""
import argparse
import json
import sys


def decide(c):
    refuse, approval, questions, unverified = [], [], [], []
    ev = c.get("evidence") or {}
    user = c.get("user") or {}
    refs = c.get("references") or {}
    tags = [str(t).lower() for t in c.get("tags") or []]

    if c.get("archived"):
        refuse.append("already archived; nothing to do")
    if c.get("permanent") or any("permanent" in t for t in tags):
        refuse.append("permanent tag: protected from cleanup")
    if not ev.get("state_read"):
        refuse.append("flag state could not be read")
    if not ev.get("code_searched"):
        refuse.append("code could not be searched")
    if user.get("other_usage") == "in_use":
        refuse.append("user says the flag is still in use elsewhere")

    if c.get("stale") is not True:
        approval.append("staleness not established" if c.get("stale") is None else "changed within the stale period")
    if refs.get("dynamic_call_sites", 0) > 0:
        approval.append("%d SDK call(s) use a non-literal flag name, so any flag may be read there" % refs["dynamic_call_sites"])
    if refs.get("other_literals", 0) > 0:
        approval.append("%d non-SDK mention(s) of the flag (config, tests, docs) need review" % refs["other_literals"])
    if refs.get("unsearched_languages"):
        approval.append("files in unsearched languages: %s" % ", ".join(refs["unsearched_languages"]))
    if c.get("has_overrides") is True:
        approval.append("segment or identity overrides exist")
    elif c.get("has_overrides") is None:
        unverified.append("segment and identity overrides not checked")

    envs = c.get("environments") or {}
    prod = c.get("production_environment")
    kept = user.get("kept_behavior")
    if prod not in envs:
        approval.append("production environment not identified")
    else:
        states = {name: bool(v.get("enabled")) for name, v in envs.items()}
        if len(set(states.values())) > 1:
            approval.append("environments differ: " + ", ".join("%s=%s" % (n, "on" if s else "off") for n, s in sorted(states.items())))
        prod_state = "on" if states[prod] else "off"
        if c.get("multivariate"):
            if not kept:
                approval.append("multivariate flag: variant to keep not named")
                questions.append("Which variant should the code keep for '%s'?" % c.get("flag"))
        elif kept is None:
            approval.append("production is %s; kept behaviour not confirmed" % prod_state)
            questions.append("'%s' is %s in %s. Keep the %s code path?" % (c.get("flag"), prod_state, prod, prod_state))
        elif kept != prod_state:
            approval.append("kept behaviour '%s' differs from production '%s'" % (kept, prod_state))

    gate = ["PR merged", "no references remain on the default branch of each repository searched", "flag state still matches the snapshot"]
    if user.get("other_usage") != "none":
        gate.append("user confirms no other repository, service or client uses the flag")
        unverified.append("usage outside the searched repositories not confirmed")

    if refuse:
        verdict, reasons = "REFUSE", refuse
    elif approval:
        verdict, reasons = "APPROVAL REQUIRED", approval
    else:
        verdict, reasons = "PROCEED", ["evidence supports removal; present the plan for approval"]
    return {
        "flag": c.get("flag"),
        "verdict": verdict,
        "reasons": reasons,
        "questions": questions,
        "unverified": unverified,
        "archive_gate": gate,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", help="JSON file (default: stdin)")
    parser.add_argument("--table", action="store_true", help="print a compact table instead of JSON")
    ns = parser.parse_args(argv)
    raw = open(ns.input, encoding="utf-8").read() if ns.input else sys.stdin.read()
    data = json.loads(raw)
    results = [decide(c) for c in (data if isinstance(data, list) else [data])]
    if ns.table:
        for r in results:
            print("%-28s %-18s %s" % (r["flag"], r["verdict"], "; ".join(r["reasons"])))
    else:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())