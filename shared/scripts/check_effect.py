#!/usr/bin/env python3
"""Check what a flag resolves to for specific identities, after a mitigation.

A successful CLI write does not prove the incident is resolved. This reports what
`flagsmith evaluate` returns for each identity you name, so an override that keeps the
feature on is visible.

  python check_effect.py --flag NAME --identity affected-user --identity override-user [--env KEY]

Exit codes: 0 all identities see the feature off, 1 at least one still sees it on,
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
    runner = runner or cli.run
    rows = []
    for identity in identities:
        args = ["evaluate", flag, "--identity", identity] + (["--environment", env] if env else [])
        try:
            state, error = flag_state(runner(args), flag), None
        except cli.CliError as err:
            state, error = None, str(err)
        rows.append({"identity": identity, "enabled": state, "error": error})
    still_on = [r["identity"] for r in rows if r["enabled"] is True]
    unknown = [r["identity"] for r in rows if r["enabled"] is None]
    if still_on:
        result = "PARTIAL: feature still on for " + ", ".join(still_on)
    elif unknown:
        result = "UNVERIFIED: could not read the flag for " + ", ".join(unknown)
    else:
        result = "MITIGATED for the identities checked (the incident itself is not proven resolved)"
    return {"flag": flag, "rows": rows, "result": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flag", required=True)
    parser.add_argument("--identity", action="append", required=True)
    parser.add_argument("--env", help="value for --environment (an SDK key may be required)")
    ns = parser.parse_args(argv)
    out = check(ns.flag, ns.identity, ns.env)
    for row in out["rows"]:
        shown = "unknown" if row["enabled"] is None else ("on" if row["enabled"] else "off")
        print("%-24s %s%s" % (row["identity"], shown, "  (%s)" % row["error"] if row["error"] else ""))
    print(out["result"])
    if out["result"].startswith("PARTIAL"):
        return 1
    return 3 if out["result"].startswith("UNVERIFIED") else 0


if __name__ == "__main__":
    sys.exit(main())