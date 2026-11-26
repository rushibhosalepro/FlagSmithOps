"""Stand-in for the flagsmith CLI, used by tests. Behaviour depends on the flag name."""
import json
import sys

args = sys.argv[1:]
if "fail_flag" in args:
    sys.stderr.write("boom: FLAGSMITH_API_KEY=secret123\n")
    sys.exit(1)
if "bad_flag" in args:
    print("this is not json")
    sys.exit(0)
print(json.dumps({"args": args, "enabled": "off_flag" not in args, "feature_state_value": None}))