#!/usr/bin/env python3
"""Decide PROCEED / APPROVAL REQUIRED / REFUSE for flag cleanup candidates.

Input: a JSON object or list of objects. Unknown is never safe: a field that is missing,
null, or not the exact type expected counts as UNKNOWN, and unknown never produces PROCEED.
Only real JSON booleans are accepted as booleans ("false" and 0 are not False).

Fields:
  flag (required)
  archived                  bool           (from the API field is_archived)
  multivariate              bool
  stale                     bool or null   (null = not established)
  tags                      list or null   items: {"label": str, "is_permanent": bool} or a plain label string.
                                           A plain label cannot show permanence (only a label containing "permanent" is refused).
  permanent                 bool           (true refuses)
  evidence                  {state_read: bool, code_searched: bool}
  environments              {name: {enabled: bool}}
  production_environment    str
  environments_complete     bool           (snapshot.py: true only if every environment of the project was captured)
  environments_not_captured list           (names, optional, for the message)
  has_overrides             bool or null
  references                {sdk_calls: int, other_literals: int, dynamic_call_sites: int, unsearched_languages: list}
  user                      {kept_behavior: "on"|"off"|<variant>|null, other_usage: "none"|"unknown"|"in_use",
                             accept_unchecked_overrides: true to accept unknown overrides explicitly}

PROCEED means eligible to be presented for approval. It never skips approval for a Flagsmith write.

  python verdict.py --input candidates.json [--table]
"""
import argparse
import json
import sys


def _bool(value):
    """True or False only for a real boolean, else None (unknown)."""
    return value if isinstance(value, bool) else None


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _dict(value):
    return value if isinstance(value, dict) else {}


def _tag_status(tags):
    """Return (permanent, unknown) from the tags field."""
    if not isinstance(tags, list):
        return False, True
    permanent, unknown = False, False
    for tag in tags:
        if isinstance(tag, dict):
            flag = _bool(tag.get("is_permanent"))
            if flag is True:
                permanent = True
            elif flag is None:
                unknown = True
        elif isinstance(tag, str):
            if "permanent" in tag.lower():
                permanent = True
            else:
                unknown = True  # a label alone cannot show whether the tag is permanent
        else:
            unknown = True
    return permanent, unknown


def decide(c):
    if not isinstance(c, dict):
        return {"flag": None, "verdict": "REFUSE", "reasons": ["candidate is not a JSON object"],
                "questions": [], "unverified": [], "archive_gate": []}
    refuse, approval, questions, unverified = [], [], [], []
    ev, user = _dict(c.get("evidence")), _dict(c.get("user"))
    name = c.get("flag")

    if not isinstance(name, str) or not name.strip():
        refuse.append("flag name missing")

    # --- hard stops -------------------------------------------------------------
    archived = _bool(c.get("archived"))
    if archived is True:
        refuse.append("already archived; nothing to do")
    elif archived is None:
        approval.append("archived status unknown")
    permanent, tags_unknown = _tag_status(c.get("tags"))
    if permanent or c.get("permanent") is True:
        refuse.append("permanent tag: protected from cleanup")
    elif tags_unknown or c.get("permanent") not in (None, False):
        approval.append("tags not read or permanence unknown, so permanent status is unknown")
    if ev.get("state_read") is not True:
        refuse.append("flag state could not be read")
    if ev.get("code_searched") is not True:
        refuse.append("code could not be searched")
    if user.get("other_usage") == "in_use":
        refuse.append("user says the flag is still in use elsewhere")

    # --- things that need a human ----------------------------------------------
    stale = _bool(c.get("stale"))
    if stale is not True:
        approval.append("staleness not established" if stale is None else "changed within the stale period")

    refs = c.get("references")
    sdk, other, dyn = (_count(_dict(refs).get(k)) for k in ("sdk_calls", "other_literals", "dynamic_call_sites"))
    langs = _dict(refs).get("unsearched_languages")
    if not isinstance(refs, dict) or None in (sdk, other, dyn) or not isinstance(langs, list):
        approval.append("code search results missing or incomplete")
    else:
        if dyn > 0:
            approval.append("%d SDK call(s) use a non-literal flag name, so any flag may be read there" % dyn)
        if other > 0:
            approval.append("%d non-SDK mention(s) of the flag (config, tests, docs) need review" % other)
        if langs:
            approval.append("files in unsearched languages: %s" % ", ".join(str(x) for x in langs))

    overrides = _bool(c.get("has_overrides"))
    if overrides is True:
        approval.append("segment or identity overrides exist")
    elif overrides is None:
        unverified.append("segment and identity overrides not checked")
        if user.get("accept_unchecked_overrides") is not True:
            approval.append("overrides not checked; check them or explicitly accept the risk")
            questions.append("Overrides for '%s' were not checked. Check them, or accept that they are unknown?" % name)

    complete = _bool(c.get("environments_complete"))
    if complete is not True:
        missing = c.get("environments_not_captured")
        detail = (": " + ", ".join(str(m) for m in missing)) if isinstance(missing, list) and missing else ""
        approval.append(("not every environment was read" + detail) if complete is False
                        else "environment coverage not established (the project's environment list was not checked)")

    mv = _bool(c.get("multivariate"))
    envs = _dict(c.get("environments"))
    prod = c.get("production_environment")
    kept = user.get("kept_behavior")
    if mv is None:
        approval.append("multivariate status unknown")
    if not isinstance(prod, str) or prod not in envs:
        approval.append("production environment not identified")
    else:
        raw = {n: _bool(_dict(v).get("enabled")) for n, v in envs.items()}
        unknown = sorted(n for n, s in raw.items() if s is None)
        if unknown:
            approval.append("enabled state unknown for: " + ", ".join(unknown))
        states = {n: s for n, s in raw.items() if s is not None}
        if len(set(states.values())) > 1:
            approval.append("environments differ: " + ", ".join("%s=%s" % (n, "on" if s else "off") for n, s in sorted(states.items())))
        if mv is True:
            if not isinstance(kept, str) or not kept:
                approval.append("multivariate flag: variant to keep not named")
                questions.append("Which variant should the code keep for '%s'?" % name)
        elif mv is False and prod in states:
            prod_state = "on" if states[prod] else "off"
            if kept is None:
                approval.append("production is %s; kept behaviour not confirmed" % prod_state)
                questions.append("'%s' is %s in %s. Keep the %s code path?" % (name, prod_state, prod, prod_state))
            elif kept != prod_state:
                approval.append("kept behaviour '%s' differs from production '%s'" % (kept, prod_state))

    gate = ["PR merged", "no references remain on the default branch of each repository searched", "flag state still matches the snapshot"]
    if overrides is not False:
        gate.append("overrides checked, or the risk explicitly accepted")
    if user.get("other_usage") != "none":
        gate.append("user confirms no other repository, service or client uses the flag")
        unverified.append("usage outside the searched repositories not confirmed")

    if refuse:
        verdict, reasons = "REFUSE", refuse + approval
    elif approval:
        verdict, reasons = "APPROVAL REQUIRED", approval
    else:
        verdict, reasons = "PROCEED", ["evidence supports removal; present the plan for approval"]
    return {"flag": name, "verdict": verdict, "reasons": reasons, "questions": questions,
            "unverified": unverified, "archive_gate": gate}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", help="JSON file (default: stdin)")
    parser.add_argument("--table", action="store_true", help="print a compact table instead of JSON")
    ns = parser.parse_args(argv)
    raw = open(ns.input, encoding="utf-8-sig").read() if ns.input else sys.stdin.read().lstrip("\ufeff")
    try:
        data = json.loads(raw)
    except ValueError as err:
        sys.stderr.write("input is not valid JSON: %s\n" % err)
        return 2
    results = [decide(c) for c in (data if isinstance(data, list) else [data])]
    if ns.table:
        for r in results:
            print("%-28s %-18s %s" % (r["flag"], r["verdict"], "; ".join(r["reasons"])))
    else:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())