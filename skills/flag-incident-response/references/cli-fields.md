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
- `evaluate` resolves for the identity, with overrides applied. `check_effect.py` uses it. Its `reason` field is shown in the output. Only `STATIC` has been seen. Other values are unverified.

## Overrides
`flag get` returns `segment_overrides` and `identity_overrides` as counts. `snapshot.py capture` reads them and sets `has_overrides`. Counts do not say which identities are affected. To check an identity, run `check_effect.py` for it.

## Still unverified
Multivariate output shape. Whether `flag disable` and the restore commands return state exactly. Whether `--no-input` makes a command that asks for confirmation fail unless `--yes` is passed. CLI exit codes. How an override shows up in `evaluate` (`reason`).