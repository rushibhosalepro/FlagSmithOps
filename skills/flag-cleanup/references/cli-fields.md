# CLI fields

Observed with flagsmith CLI v2.0.0 on Flagsmith Cloud, using read-only commands. Anything not listed under "Observed" is unverified. Confirm the shape once at the start of a session. If a field is missing or different, tell the user and do not guess.

## Observed
| Command | Fields |
|---|---|
| `flag get FLAG -e ENV --json` | `feature`, `type`, `description`, `enabled` (boolean), `value`, `segment_overrides` (count), `identity_overrides` (count), `code_references` (count), `lifecycle_stage` (string, seen: `new`) |
| `feature list --json`, `feature get FLAG --json` | `id`, `name`, `description`, `type`, `default_value`, `enabled`. **No tags. No archived flag.** |
| `api /api/v1/projects/ID/features/` | paginated (`count`, `next`, `previous`, `results`). Each result has `name`, `tags` (ids), `is_archived`, `multivariate_options`, `last_modified_in_any_environment`, `num_segment_overrides`, `num_identity_overrides`, `owners`, `code_references_counts` and more |
| `api /api/v1/projects/ID/tags/` | paginated list of project tags |
| `evaluate FLAG --identity ID -e ENV --json` | `name`, `enabled`, `value`, `reason` (seen: `STATIC`) |

Rules that follow:
- `-e` accepts the environment name (tested with `Production`) or its client-side SDK key. With no `-e`, the CLI stops with "no environment". Always pass `-e`.
- `enabled` in `feature list` and `feature get` is **not** an environment state. It was `false` while the environment was `true`. Only `flag get -e ENV` gives the environment state.
- API paths need the `/api/v1/` prefix. Without it the call returns 404.

## Reading candidates
Use the Management API, because `feature list` has no tags or archived flag:
```
flagsmith api /api/v1/projects/PROJECT_ID/features/ --jq '[.results[] | {name, tags, is_archived, variants: (.multivariate_options | length), modified: .last_modified_in_any_environment}]'
```
Results are paginated. If `next` is not null, read the next page. This filter cut a 1,815-byte response to 226 bytes.

## Tags and permanent flags
`tags` holds ids. Resolve them with `flagsmith api /api/v1/projects/PROJECT_ID/tags/`. The docs say a tag is permanent when "Is permanent?" is set. The field name is unverified, because the test project has no tags. If you cannot tell whether a tag is permanent, pass `tags: null` to `verdict.py`. It will not allow PROCEED.

## Stale
The `Stale` tag needs a Scale-up or Enterprise plan, so it will not exist on the free plan. Use `last_modified_in_any_environment` and what the user tells you. Pass `stale: null` when staleness is not established. `lifecycle_stage` is recorded, but its possible values are unknown, so do not base a decision on it.

## Overrides
`snapshot.py capture` reads `segment_overrides` and `identity_overrides` (counts) and sets `has_overrides`. Use that value. If the counts are missing it is `null`, the verdict needs approval, and the archive stays blocked until overrides are checked or the user accepts the risk.

## Observed by running writes (disposable test flags)
- Writes with --no-input need --yes: without it the command exits 2 with "pass --yes to confirm" and changes nothing.
- Failures exit 1 with a clear message (unknown flag, unknown environment, no environment).
- eature update FLAG --archive sets is_archived true. --unarchive sets it false. Both returned the feature object.
- An archived flag still evaluates (evaluate returned the same state) and lag get still works. The default eature list hides archived features. --include-archived shows them.
- Archive then unarchive, and disable then enable, returned state identical to the snapshot (snapshot.py verify).

## Still unverified
Permanent-tag field name. `lifecycle_stage` values. Multivariate output shape. How long an archived flag keeps evaluating (it was checked right after archiving). Behaviour with overrides and multivariate flags.