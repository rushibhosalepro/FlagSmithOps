#!/usr/bin/env python3
"""Capture, verify and diff flag state across environments.

The CLI's JSON field names are unverified, so snapshots keep the raw CLI output.
Restore commands are derived only when an `enabled` field can be found.

  python snapshot.py capture --flag NAME --env production --env staging --out snapshot.json
  python snapshot.py verify  --file snapshot.json
  python snapshot.py restore-commands --file snapshot.json --env production
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402

IGNORE_DEFAULT = {"updated_at", "created_at"}


def capture(flag, envs, segment_ids=(), runner=None):
    runner = runner or cli.run
    snap = {
        "flag": flag,
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "environments": {},
        "notes": [],
    }
    for env in envs:
        entry = {"default": runner(["flag", "get", flag, "--environment", env]), "segment_overrides": {}}
        for sid in segment_ids:
            try:
                entry["segment_overrides"][str(sid)] = runner(
                    ["flag", "get", flag, "--environment", env, "--segment", str(sid)]
                )
            except cli.CliError as err:
                entry["segment_overrides"][str(sid)] = {"error": str(err)}
        snap["environments"][env] = entry
    if not segment_ids:
        snap["notes"].append(
            "Segment and identity overrides were not captured. The CLI reads them only by segment or identity id."
        )
    return snap


def _strip(obj, ignore):
    if isinstance(obj, dict):
        return {k: _strip(v, ignore) for k, v in obj.items() if k not in ignore}
    if isinstance(obj, list):
        return [_strip(v, ignore) for v in obj]
    return obj


def diff(a, b, ignore=IGNORE_DEFAULT, path=""):
    """Return a list of 'path: before != after' strings. Empty list means equal."""
    a, b = _strip(a, ignore), _strip(b, ignore)
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            sub = "%s.%s" % (path, key) if path else key
            if key not in a:
                out.append("%s: <missing> != %r" % (sub, b[key]))
            elif key not in b:
                out.append("%s: %r != <missing>" % (sub, a[key]))
            else:
                out.extend(diff(a[key], b[key], ignore, sub))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff(x, y, ignore, "%s[%d]" % (path, i)))
    elif a != b:
        out.append("%s: %r != %r" % (path or "<root>", a, b))
    return out


def _find(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj:
                return True, obj[key]
        for value in obj.values():
            found, result = _find(value, keys)
            if found:
                return True, result
    elif isinstance(obj, list):
        for value in obj:
            found, result = _find(value, keys)
            if found:
                return True, result
    return False, None


def restore_commands(snap, env):
    """Commands that return the environment default to the snapshot. Best effort."""
    raw = snap["environments"][env]["default"]
    flag = snap["flag"]
    cmds, notes = [], []
    found, enabled = _find(raw, ["enabled"])
    if found and isinstance(enabled, bool):
        cmds.append(["flagsmith", "flag", "enable" if enabled else "disable", flag, "--environment", env])
    else:
        notes.append("Could not find an 'enabled' field in the snapshot. Restore by hand from the raw state.")
    found, value = _find(raw, ["feature_state_value", "value"])
    if found and value is not None and not isinstance(value, (dict, list)):
        cmds.append(["flagsmith", "flag", "update", flag, "--environment", env, "--value", str(value)])
        notes.append("Value restore assumes the flag value type is unchanged.")
    return {"commands": cmds, "notes": notes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--flag", required=True)
    cap.add_argument("--env", action="append", required=True)
    cap.add_argument("--segment-ids", default="")
    cap.add_argument("--out", required=True)
    ver = sub.add_parser("verify", help="re-read live state and compare with a snapshot file")
    ver.add_argument("--file", required=True)
    rc = sub.add_parser("restore-commands")
    rc.add_argument("--file", required=True)
    rc.add_argument("--env", required=True)
    ns = parser.parse_args(argv)
    try:
        if ns.command == "capture":
            ids = [s for s in ns.segment_ids.split(",") if s]
            snap = capture(ns.flag, ns.env, ids)
            with open(ns.out, "w", encoding="utf-8") as handle:
                json.dump(snap, handle, indent=2)
            print("saved %s" % ns.out)
            for env, entry in snap["environments"].items():
                found, enabled = _find(entry["default"], ["enabled"])
                print("  %s: enabled=%s" % (env, enabled if found else "unknown (field not found)"))
            for note in snap["notes"]:
                print("  note: " + note)
            return 0
        with open(ns.file, encoding="utf-8") as handle:
            saved = json.load(handle)
        if ns.command == "restore-commands":
            print(json.dumps(restore_commands(saved, ns.env), indent=2))
            return 0
        seg_ids = sorted({sid for e in saved["environments"].values() for sid in e["segment_overrides"]})
        fresh = capture(saved["flag"], list(saved["environments"]), seg_ids)
        problems = diff(saved["environments"], fresh["environments"])
        if problems:
            print(