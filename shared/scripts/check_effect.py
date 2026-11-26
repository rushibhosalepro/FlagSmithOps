#!/usr/bin/env python3
"""Check what a flag resolves to for specific identities, after a mitigation.

A successful CLI write does not prove the incident is resolved. This reports what
`flagsmith evaluate` returns for each identity you name, so an override that keeps the
feature on is visible.

  python check_effect.py --flag NAME --env ENV --identity affected-user --identity override-user

Exit codes: 0 all identities checked see the feature off (the incident is still NOT verified), 1 at least one still sees it on,
3 could not tell for at least one identity.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402


def flag_state(obj, flag):
    """True, False or None for `flag` in an evaluate response. None means not found."""

    def walk(o):
        if isinstance(o, dict):
            names = [o.get(k) for k in ("name", "feature_name", "key")]
            if isinstance(o.get("feature"), dict):
                names.append(o["feature"].get("name"))
            if flag in names and isinstance(o.get("enabled"), bool):
                return o["enabled"]
            for value in o.values():
                found = walk(value)
                if found is not None:
                    return found
        elif isinstance(o, list):
            for value in o:
                found = walk(value)
                if found is not None:
                    return found
        return None

    result = walk(obj)
    if result is None and isinstance(obj, dict) and isinstance(obj.get("enabled"), bool):
        return obj["enabled"]
    return result


def check(flag, identities, env=None, runner=None):
    """Evaluate `flag` for each identity in the named environment. Never reports the incident as resolved."""
    runner = runner or cli.run
    rows = []
    for identity in identities:
        args = ["evaluate", flag, "--identity", identity] + (["--environment", env] if env else [])
        reason = None
        try:
            response = runner(args)
            state, error = flag_state(response, flag), None
            if isinstance(response, dict) and isinstance(response.get("reason"), str):
                reason = response["reason"]  # observed values: STATIC. Others (for example targeting) are unverified.
        except cli.CliError as err:
            state, error = None, str(err)
        rows.append({"identity": identity, "enabled": state, "error": error, "reason": reason})
    still_on = [r["identity"] for r in rows if r["enabled"] is True]
    unknown = [r["identity"] for r in rows if r["enabled"] is None]
    if not env:
        result = "UNVERIFIED: no environment named, so the environment checked is unknown"
    elif not rows:
        result = "UNVERIFIED: no identities were checked"
    elif still_on:
        result = "PARTIAL: feature still on for " + ", ".join(still_on)
    elif unknown:
        result = "UNVERIFIED: could not read the flag for " + ", ".join(unknown)
    else:
        result = "FLAG OFF for the %d identity(ies) checked in %s" % (len(rows), env)
    return {
        "flag": flag,
        "environment": env,
        "rows": rows,
        "result": result,
        # Whether the symptom is gone cannot be seen from flag evaluation. A human must confirm it.
        "incident_status": "NOT VERIFIED: ask the user to confirm the symptom is gone",
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flag", required=True)
    parser.add_argument("--identity", action="append", required=True)
    parser.add_argument("--env", required=True, help="environment to evaluate (an SDK key may be required)")
    ns = parser.parse_args(argv)
    out = check(ns.flag, ns.identity, ns.env)
    for row in out["rows"]:
        shown = "unknown" if row["enabled"] is None else ("on" if row["enabled"] else "off")
        extra = "  (%s)" % row["error"] if row["error"] else ("  reason=%s" % row["reason"] if row["reason"] else "")
        print("%-24s %s%s" % (row["identity"], shown, extra))
    print(out["result"])
    print("Incident: " + out["incident_status"])
    if out["result"].startswith("PARTIAL"):
        return 1
    return 3 if out["result"].startswith("UNVERIFIED") else 0


if __name__ == "__main__":
    sys.exit(main())