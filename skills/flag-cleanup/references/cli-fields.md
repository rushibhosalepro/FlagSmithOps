# CLI fields

Observed with flagsmith CLI v2.0.0 on Flagsmith Cloud, using read-only commands. Anything not listed under "Observed" is unverified. Confirm the shape once at the start of a session. If a field is missing or different, tell the user and do not guess.

## Observed
| Command | Fields |
|---|---|
| `flag get FLAG -e ENV --json` | `feature`, `type`, `description`, `enabled` (boolean), `value`, `segment_overrides` (count), `identity_overrides` (count), `code_references` (count), `lifecycle_stage` (string, seen: `new`) |
| `feature list --json`, `feature get FLAG --json` | `id`, `name`, `description`, `type`, `default_value`, `enabled`. **No tags. No archived flag.** |
| `api /api/v1/projects/ID/features/` | paginated (`count`, `next`, `previous`, `results`). Each result has `name`, `tags` (ids), `is_archived`, `multivariate_options`, `last_modified_in_any_environment`, `num_segment_overrides`, `num_identity_overrides`, `owners`, `code_references_counts` and more |
| `api /api/v1/projects/ID/tags/` | paginated list of project tags |
| `evaluate FLAG --identity ID -e ENV --json` | `name`, `enabled`, `value`, `reason` (seen: `STATIC`, and `TARGETING_MATCH; segment=identity_overrides` for an identity override) |

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
`tags` holds ids. Resolve them and build the objects `verdict.py` expects:
```
flagsmith api /api/v1/projects/PROJECT_ID/tags/ --jq '[.results[] | {id, label, is_permanent}]'
```
Each tag has `is_permanent` (boolean, verified). A tag is permanent because of that attribute, not its label. Pass each tag as `{"label": ..., "is_permanent": ...}`. A permanent tag makes the verdict REFUSE. If you cannot resolve a tag id, pass the id as it is, or pass `tags: null`. `verdict.py` then treats permanence as unknown and will not allow PROCEED.

## Multivariate flags
`flag get` returns `type` (`standard` or `multivariate`, verified) and, for a multivariate flag, `variants` (each with `id`, `key`, `value`, `weight`). The features API shows the same as `multivariate_options`. Pass `multivariate: true` when `type` is not `standard`. Snapshots keep the weights, so `snapshot.py verify` reports any weight change. Restore commands do not restore variants or weights. The CLI can set weights with `flag update FLAG --weight key=pct`, but the skill does not do it for you.

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

## Environment coverage gate
`snapshot.py capture` reads `environment list` itself and records `project_environments` (ids and names only, never keys). With no `--env` it captures every environment. `environments_complete` is:
- `true` only if the list was read, every listed environment was captured, and each has a boolean `enabled`;
- `false` if an environment is missing, a captured name is not in the list, `--known-envs` disagrees with the list, or a state is unreadable (`coverage_problems` says which);
- `null` if the list could not be read or had an unexpected shape.

`verdict.py` needs `snapshot` (the file path) to PROCEED. It loads it and requires `environments_complete: true`, and the candidate's `environments`, `environments_complete` and `has_overrides` must match it exactly.

`snapshot.py verify` fails (exit 1) if the snapshot is incomplete or has no environment list, if the current list cannot be read, or if an environment was added, removed or renamed since the snapshot (detected by environment id). The cleanup archive gate uses it, so any of these blocks the archive.

## Still unverified
`lifecycle_stage` values. Segment overrides (only identity overrides were tested). How long an archived flag keeps evaluating (it was checked right after archiving). Behaviour with overrides and multivariate flags.