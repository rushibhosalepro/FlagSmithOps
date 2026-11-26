import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "shared", "scripts")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load_json(*parts):
    """Load a JSON fixture from tests/fixtures."""
    with open(os.path.join(FIXTURES, *parts), encoding="utf-8") as handle:
        return json.load(handle)