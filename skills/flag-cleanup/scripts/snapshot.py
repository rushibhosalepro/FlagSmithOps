#!/usr/bin/env python3
"""Capture, verify and diff flag state across environments.

The CLI's JSON field names are unverified, so a snapshot keeps the raw CLI output.
Restore commands are derived only from TOP-LEVEL fields of that output. A value found in
a nested object (a segment override, a variant) is never used, because it may describe
something other than the environment default.

  python snapshot.py capture --flag NAME --env production --env staging --out snapshot.json [--known-envs production,staging,dev]
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


def capture(flag, envs, segment_ids=(), runner=None, known_envs=None):
    """Read the flag in every named environment. Raises CliError if any read fails."""
    runner = runner or cli.run
    snap = {
        "flag": flag,
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "environments": {},
        "not_captured": sorted(set(known_envs or []) - set(envs)),
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
    snap["summary"] = {env: _summarise(entry["default"]) for env, entry in snap["environments"].items()}
    snap["has_overrides"] = overrides_exist(snap["summary"])
    if known_envs is None:
        snap["notes"].append("Environments not named were not captured, and the full environment list was not checked.")
    if snap["not_captured"]:
        snap["notes"].append("NOT captured: " + ", ".join(snap["not_captured"]))
    if segment_ids:
        snap["notes"].append("Segment overrides were captured for reference only. They are never restored.")
    elif snap["has_overrides"] is None:
        snap["notes"].append(
            "Override counts were not found in the CLI output, and the overrides themselves were not captured."
        )
    else:
        snap["notes"].append(
            "Override counts come from the CLI (segment_overrides, identity_overrides). The overrides themselves were not captured and are never restored."
        )
    return snap


def _count(raw, key):
    """A non-negative integer field of the top-level object, else None (unknown)."""
    value = raw.get(key) if isinstance(raw, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _summarise(raw):
    stage = raw.get("lifecycle_stage") if isinstance(raw, dict) else None
    return {
        "enabled": enabled_state(raw),
        "segment_overrides": _count(raw, "segment_overrides"),
        "identity_overrides": _count(raw, "identity_overrides"),
        "code_references": _count(raw, "code_references"),
        "lifecycle_stage": stage if isinstance(stage, str) else None,
    }


def overrides_exist(summary):
    """True if any environment reports an override, False only if every count is known and zero, else None."""
    counts = [s[k] for s in summary.values() for k in ("segment_overrides", "identity_overrides")]
    if any(c for c in counts if c is not None):
        return True
    if counts and all(c == 0 for c in counts):
        return False
    return None


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


def _top(raw, keys):
    """(found, value) for the first of `keys` that is a top-level field of a dict. Never searches nested data."""
    if isinstance(raw, dict):
        for key in keys:
            if key in raw:
                return True, raw[key]
    return False, None


def enabled_state(raw):
    """True or False when the top-level `enabled` is a real boolean, else None (unknown)."""
    found, value = _top(raw, ["enabled"])
    return value if found and isinstance(value, bool) else None


def _has_variants(raw):
    if not isinstance(raw, dict):
        return False
    return any(("multivariate" in k.lower() or "variant" in k.lower()) and v for k, v in raw.items())


def restore_commands(snap, env):
    """Commands that return the environment DEFAULT to the snapshot. Best effort, honest about gaps."""
    raw = snap["environments"][env]["default"]
    flag = snap["flag"]
    cmds = []
    notes = [
        "Restores the environment default only (enabled state, and a plain value where one can be read).",
        "Variants, weights, segment overrides and identity overrides are not restored. Run `snapshot.py verify` and report any difference.",
        "The commands include --yes, which the CLI requires for writes without a terminal. Run them only after the user approves.",
    ]
    state = enabled_state(raw)
    if state is None:
        notes.append("No boolean top-level 'enabled' field in the snapshot, so no enable/disable command was generated. Restore by hand from the raw state.")
    else:
        cmds.append(["flagsmith", "flag", "enable" if state else "disable", flag, "--environment", env, "--yes"])
    counts = snap.get("summary", {}).get(env, {})
    if counts.get("segment_overrides") or counts.get("identity_overrides"):
        notes.append("%s segment and %s identity override(s) exist in %s. They are not restored." % (counts.get("segment_overrides") or 0, counts.get("identity_overrides") or 0, env))
    if _has_variants(raw):
        notes.append("This flag appears to be multivariate. Its value was not restored.")
    else:
        found, value = _top(raw, ["feature_state_value", "value"])
        if found and value is not None and not isinstance(value, (dict, list)):
            cmds.append(["flagsmith", "flag", "update", flag, "--environment", env, "--value", str(value), "--yes"])
            notes.append("Value restore assumes the value type is unchanged.")
    return {"commands": cmds, "notes": notes, "multivariate_detected": _has_variants(raw)}


def verify(saved, runner=None):
    """Re-read live state and compare it with a snapshot. Returns a list of differences (empty = identical)."""
    seg_ids = sorted({sid for e in saved["environments"].values() for sid in e["segment_overrides"]})
    fresh = capture(saved["flag"], list(saved["environments"]), seg_ids, runner=runner)
    return diff(saved["environments"], fresh["environments"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--flag", required=True)
    cap.add_argument("--env", action="append", required=True)
    cap.add_argument("--known-envs", default="", help="comma-separated names from `environment list`, to detect omissions")
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
            known = [s for s in ns.known_envs.split(",") if s] or None
            snap = capture(ns.flag, ns.env, ids, known_envs=known)
            with open(ns.out, "w", encoding="utf-8") as handle:
                json.dump(snap, handle, indent=2)
            print("saved %s" % ns.out)
            for env, s in snap["summary"].items():
                shown = lambda v: "unknown" if v is None else v  # noqa: E731
                print("  %s: enabled=%s segment_overrides=%s identity_overrides=%s lifecycle_stage=%s"
                      % (env, shown(s["enabled"]), shown(s["segment_overrides"]), shown(s["identity_overrides"]), shown(s["lifecycle_stage"])))
            print("  has_overrides=%s" % ("unknown" if snap["has_overrides"] is None else snap["has_overrides"]))
            if snap["not_captured"]:
                print("  WARNING: not captured: " + ", ".join(snap["not_captured"]))
            for note in snap["notes"]:
                print("  note: " + note)
            return 0
        with open(ns.file, encoding="utf-8-sig") as handle:
            saved = json.load(handle)
        if ns.command == "restore-commands":
            print(json.dumps(restore_commands(saved, ns.env), indent=2))
            return 0
        problems = verify(saved)
        if problems:
            print("DIFFERENT")
            print("\n".join(problems))
            return 1
        print("MATCHES snapshot")
        return 0
    except cli.CliError as err:
        sys.stderr.write(str(err) + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())