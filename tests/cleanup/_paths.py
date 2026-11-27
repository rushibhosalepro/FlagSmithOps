import json
import os
import sys
import tempfile

# Isolation: never write into a real run's meter (FSOPS_METER_FILE may be set in the shell).
os.environ["FSOPS_METER_FILE"] = os.path.join(tempfile.mkdtemp(prefix="fsops-test-meter-"), "meter.jsonl")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "shared", "scripts")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load_json(*parts):
    """Load a JSON fixture from tests/fixtures."""
    with open(os.path.join(FIXTURES, *parts), encoding="utf-8") as handle:
        return json.load(handle)


def project_list(names):
    """What `flagsmith environment list --json` returns (ids by position). api_key is included like the real CLI."""
    return [{"id": i + 1, "name": n, "api_key": "key-%d" % (i + 1)} for i, n in enumerate(sorted(names))]


def env_aware(runner, names):
    """Wrap a fake flag runner so it also answers `environment list` for the given environment names."""
    def run(args):
        if list(args[:2]) == ["environment", "list"]:
            return project_list(names)
        return runner(args)
    return run


def make_snapshot(flag="obsolete_flag", states=None, overrides=0, project=None):
    """Write a real snapshot.py file for `flag` and return its path. states: {env: enabled}."""
    import snapshot
    states = states if states is not None else {"production": True, "staging": True}
    names = project if project is not None else list(states)

    def flag_get(args):
        env = args[args.index("--environment") + 1]
        raw = {"feature": flag, "type": "standard", "enabled": states[env]}
        if overrides is not None:
            raw.update(segment_overrides=overrides, identity_overrides=0)
        return raw

    snap = snapshot.capture(flag, list(states), runner=env_aware(flag_get, names))
    path = os.path.join(tempfile.mkdtemp(prefix="fsops-snap-"), "%s.snapshot.json" % flag)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(snap, handle)
    return path