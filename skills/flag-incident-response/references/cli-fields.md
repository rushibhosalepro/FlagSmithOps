# CLI fields

Observed with flagsmith CLI v2.0.0 on Flagsmith Cloud, using read-only commands. Anything not listed under "Observed" is unverified. Confirm the shape once at the start of a session. If a field is missing or different, tell the user and do not guess.

## Observed
| Command | Fields |
|---|---|
| `feature list --json` | `id`, `name`, `description`, `type`, `default_value`, `enabled` |
| `flag get FLAG -e ENV --json` | `feature`, `type`, `description`, `enabled` (boolean), `value`, `segment_overrides` (count), `identity_overrides` (count), `code_references` (count), `lifecycle_stage` |
| `evaluate FLAG --identity ID -e ENV --json` | `name`, `enabled`, `value`, `reason` (seen: `STATIC`) |
| `environment list --json` | per environment: `id`, `name`, `api_key` (the client-side SDK key), `project` and more |

Rules that follow:
- `-e` accepts the environment name (tested with `Production`) or its SDK key. With no `-e`, the CLI stops with "no environment". Always pass `-e`, and pass the one the user named.
- `enabled` in `feature list` and `feature get` is **not** an environment state. It was `false` while the environment was `true`. Only `flag get -e ENV` gives the environment state.
- `evaluate` resolves for the identity, with overrides applied. `check_effect.py` uses it. Its `reason` field is shown in the output. Seen: `STATIC`, and `TARGETING_MATCH; segment=identity_overrides` when an identity override applies.

## Override case (verified)
With the environment default disabled and an identity override enabling the flag, `evaluate` returned `enabled: true` with `reason: TARGETING_MATCH; segment=identity_overrides` for that identity. `check_effect.py` reports this as PARTIAL.

## Overrides
`flag get` returns `segment_overrides` and `identity_overrides` as counts. `snapshot.py capture` reads them and sets `has_overrides`. Counts do not say which identities are affected. To check an identity, run `check_effect.py` for it.

## Observed by running writes (disposable test flags)
- Writes with --no-input need --yes: without it the command exits 2 with "pass --yes to confirm" and changes nothing.
- Failures exit 1 with a clear message.
- lag disable returns the new flag state. Disable then lag enable returned state identical to the snapshot (snapshot.py verify).
- evaluate showed the flag off for the identities checked right after the disable.

## Pre-write gate (`scripts/disable_gate.py`)
Run with `--snapshot` in check mode before asking for approval, then with `--execute` after approval. It stops (exit 3, no write) unless every condition holds:
1. The snapshot exists, is readable JSON, and is for the requested flag.
2. It covers every environment. `environments_complete` must be true, it must have the project's environment list, and every listed environment must be captured with a boolean `enabled`. The gate recomputes this from the contents, so editing the flag does not help.
3. The requested environment is in that list and in the snapshot, with a boolean `enabled` that is `true` (already off means there is nothing to disable).
4. Live check (read-only): the current environment list matches the snapshot (same names and ids), and the flag's current state in the target environment equals the snapshot.

Only then does it run `flag disable NAME --environment ENV --yes` and read the new state back. `cli.py` refuses `flag disable` and `flag update --disable` from any other caller, including `python scripts/cli.py run`. Exit codes: 0 valid or disabled, 3 blocked, 2 CLI or file error.

## Still unverified
Behaviour of disable and restore when overrides exist, and for multivariate flags. Segment overrides (only identity overrides were tested). How quickly the SDK API reflects a change (evaluated seconds after the write here).