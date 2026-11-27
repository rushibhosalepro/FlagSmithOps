# What the wrapper does and does not protect

`scripts/cli.py` is a guard rail for an agent that follows the skill. It is **not a security boundary**. It cannot stop an agent, a user or a script that decides to go around it.

## What it blocks
Calls made through `cli.run()`, which includes `python scripts/cli.py run -- ...` and every FlagSmithOps script:

| Blocked | How |
|---|---|
| `* delete` (feature, flag override, segment, environment, project, organisation) | refused before the CLI starts, even with `gate=True` |
| `api` with any method other than GET, or with a body (`-F`, `-f`, `--field`, `--raw-field`, `--input`) | refused before the CLI starts |
| `flag disable`, and `flag update ... --disable` | refused unless the call carries `gate=True`. Only `disable_gate.py` passes it, after its checks |

Blocked calls are recorded in the meter with `"blocked": true`. Tests check that the CLI process is never started for them.

## What it cannot block
- **Direct CLI use.** `flagsmith flag disable ...`, `flagsmith feature delete ...` or `flagsmith api ... -X DELETE` run in a shell never touch the wrapper.
- **Direct Python use.** `gate=True` is an ordinary keyword argument, not a secret. `python -c "import cli; cli.run([...], gate=True)"` disables without any check. Editing or deleting the scripts also removes every check.
- **Other writes through the wrapper.** These run without any FlagSmithOps check: `flag enable`, `flag update --enable`, `--value`, `--weight`, `flag update --identifier/--segment` (except `--disable`), `feature update --archive/--unarchive`, `feature create`, `segment create/update`, `environment create/clone`, and `evaluate --persist`.
- **The Flagsmith dashboard, other API keys and other tools.**

## What relies on the agent following the skill
- Asking for approval before each write, and using an approval only for the exact action shown.
- Running every CLI call through the wrapper instead of `flagsmith` directly.
- Disabling only through `disable_gate.py`, and treating BLOCKED as a stop.
- Archiving only after the cleanup gates pass (PR merged, no references, `snapshot.py verify` matches, other usage confirmed).
- Restoring with the commands generated from the snapshot.
- Not changing overrides, variants or weights.

The real permission boundary is the Flagsmith credential. Give the agent a key or role that can only do what the workflow needs. Change requests on paid Flagsmith plans add a second approval inside Flagsmith itself.