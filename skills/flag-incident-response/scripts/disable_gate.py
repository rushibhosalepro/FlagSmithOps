#!/usr/bin/env python3
"""Pre-write gate for the incident mitigation. The only supported way to disable a flag.

Validates the snapshot, re-checks live state, and only then disables the environment default.
Any failed condition stops before the write. There are no warnings: a problem is a stop.

  python disable_gate.py --flag NAME --env ENV --snapshot .fsops/NAME.snapshot.json            # check only
  python disable_gate.py --flag NAME --env ENV --snapshot .fsops/NAME.snapshot.json --execute  # after approval

Policy (incident workflow): the snapshot must be for this flag, cover every environment of the project
(environments_complete true, with an environment list), include ENV with a boolean enabled state that is
currently on, and live state must still match it. ENV must still exist under the same id.

Exit codes: 0 valid (check) or disabled (execute), 3 blocked by the gate (no write), 2 CLI or file error.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import snapshot  # noqa: E402


def _load(path):
    try:
        data = json.loads(cli.read_text(path))
    except (OSError, ValueError) as err:
        return None, "snapshot missing or unreadable: %s (%s)" % (path, err.__class__.__name__)
    if not isinstance(data, dict):
        return None, "snapshot has an unexpected shape"
    return data, None


def check_snapshot(snap, flag, env):
    """Problems found in the snapshot alone (no CLI calls)."""
    problems = []
    if snap.get("flag") != flag:
        problems.append("snapshot is for flag %r, not %r" % (snap.get("flag"), flag))
    if snap.get("environments_complete") is not True:
        detail = "; ".join(str(p) for p in snap.get("coverage_problems") or []) or "coverage unknown"
        problems.append("snapshot does not cover every environment (%s). Capture again with no --env." % detail)
    project = snap.get("project_environments")
    if not isinstance(project, list) or not project:
        problems.append("snapshot has no project environment list")
    elif env not in [e.get("name") for e in project if isinstance(e, dict)]:
        problems.append("environment %r is not in the project's environment list in the snapshot" % env)
    envs = snap.get("environments") if isinstance(snap.get("environments"), dict) else {}
    # Recompute coverage from the contents, so an edited environments_complete flag cannot hide a gap.
    if isinstance(project, list):
        listed = [e.get("name") for e in project if isinstance(e, dict)]
        missing = sorted(n for n in listed if n not in envs)
        if missing:
            problems.append("snapshot is missing environments from its own list: " + ", ".join(str(m) for m in missing))
        unknown = sorted(n for n in listed if n in envs and snapshot.enabled_state(
            envs[n].get("default") if isinstance(envs[n], dict) else None) is None)
        if unknown:
            problems.append("enabled state unknown in the snapshot for: " + ", ".join(unknown))
    if env not in envs:
        problems.append("environment %r is not in the snapshot" % env)
        return problems
    state = snapshot.enabled_state(envs[env].get("default") if isinstance(envs[env], dict) else None)
    if state is None:
        problems.append("enabled state of %r in %r is unknown in the snapshot" % (flag, env))
    elif state is False:
        problems.append("%r is already disabled in %r according to the snapshot; nothing to disable" % (flag, env))
    return problems


def check_live(snap, flag, env, runner):
    """Problems found by re-reading Flagsmith (read-only)."""
    problems = []
    current, error = snapshot.discover_environments(runner)
    if current is None:
        return ["current " + error]
    saved_ids = {e.get("name"): e.get("id") for e in snap.get("project_environments") or [] if isinstance(e, dict)}
    now = {e["name"]: e["id"] for e in current}
    if env not in now:
        problems.append("environment %r no longer exists (or was renamed)" % env)
        return problems
    if saved_ids.get(env) != now[env]:
        problems.append("environment %r has a different id than in the snapshot" % env)
    if set(now) != set(saved_ids):
        problems.append("environment list changed since the snapshot (now: %s). Capture again." % ", ".join(sorted(now)))
    live = snapshot.enabled_state(runner(["flag", "get", flag, "--environment", env]))
    expected = snapshot.enabled_state(snap["environments"][env]["default"])
    if live is None:
        problems.append("current enabled state of %r in %r could not be read" % (flag, env))
    elif live != expected:
        problems.append("state changed since the snapshot (snapshot: %s, now: %s). Capture again." % (expected, live))
    return problems


def validate(flag, env, snapshot_path, runner=None):
    """Return (problems, snapshot). Empty problems means the disable may be executed after approval."""
    runner = runner or cli.run
    if not isinstance(env, str) or not env.strip():
        return ["no environment named"], None
    snap, error = _load(snapshot_path)
    if error:
        return [error], None
    problems = check_snapshot(snap, flag, env)
    if problems:
        return problems, snap
    try:
        problems = check_live(snap, flag, env, runner)
    except cli.CliError as err:
        problems = ["live check failed: %s" % err]
    return problems, snap


def disable(flag, env, snapshot_path, runner=None):
    """Validate, then disable. Returns (status, problems, new_state). status: 'disabled' or 'blocked'."""
    runner = runner or cli.run
    problems, _ = validate(flag, env, snapshot_path, runner)
    if problems:
        return "blocked", problems, None
    runner(["flag", "disable", flag, "--environment", env, "--yes"], gate=True)
    after = snapshot.enabled_state(runner(["flag", "get", flag, "--environment", env]))
    return "disabled", [], after


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flag", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--execute", action="store_true", help="disable after validation. Use only after the user approved this exact action")
    ns = parser.parse_args(argv)
    try:
        if not ns.execute:
            problems, _ = validate(ns.flag, ns.env, ns.snapshot)
            if problems:
                print("BLOCKED: disable %s in %s would not be allowed" % (ns.flag, ns.env))
                print("\n".join("- " + p for p in problems))
                return 3
            print("VALID: %s can be disabled in %s after approval" % (ns.flag, ns.env))
            return 0
        status, problems, after = disable(ns.flag, ns.env, ns.snapshot)
    except cli.CliError as err:
        sys.stderr.write(str(err) + "\n")
        return 2
    if status == "blocked":
        print("BLOCKED: nothing was written")
        print("\n".join("- " + p for p in problems))
        return 3
    print("DISABLED %s in %s. enabled now: %s" % (ns.flag, ns.env, "unknown" if after is None else after))
    return 0 if after is False else 2


if __name__ == "__main__":
    sys.exit(main())