# Spike results

What the Flagsmith CLI actually does, from running it. Only read-only commands have been run so far. Nothing has been changed in Flagsmith yet.

## Environment
| Item | Value |
|---|---|
| Date | 2026-11-26 |
| CLI version | `flagsmith version v2.0.0` |
| OS | Windows (PowerShell) |
| Flagsmith | Cloud (free or unknown plan; the test project has no tags) |
| Test project | one project with two environments (`Development`, `Production`) and two flags, `new_checkout` and `old_banner` |
| Auth | browser login, credentials in the OS keychain (`flagsmith auth status`) |

Environment keys, project ids and account details are deliberately not recorded here.

## Findings
| # | Question | Command run | Observed | Status |
|---|---|---|---|---|
| 1 | Fields of `feature list --json` | `feature list --include-archived` | `id, name, description, type, default_value, enabled`. No tags, no archived flag. | VERIFIED |
| 2 | Fields of `feature get --json` | `feature get new_checkout` | Same as above. `enabled` was `false` while the Production state was `true`, so it is not an environment state. | VERIFIED |
| 3 | Fields of `flag list --json` | `flag list -e Production` | Array of objects with the same shape as `flag get`. | VERIFIED |
| 4 | Fields of `flag get --json` | `flag get new_checkout -e Production` | `feature, type, description, enabled (bool), value, segment_overrides (count), identity_overrides (count), code_references (count), lifecycle_stage`. | VERIFIED |
| 5 | Does `-e` take a name or an SDK key? | `flag get ... -e Production`, and with the key | Both work. | VERIFIED |
| 6 | What happens with no `-e`? | `flag get new_checkout` | `Error: no environment. Pass -e, set FLAGSMITH_ENVIRONMENT, or run flagsmith init`. It does not guess. | VERIFIED |
| 7 | `evaluate` output | `evaluate new_checkout --identity X -e Production` | `{name, enabled, value, reason}`. `reason` was `STATIC`. | VERIFIED |
| 8 | Can overrides be detected? | `flag get` | Yes, as counts: `segment_overrides`, `identity_overrides`. | VERIFIED |
| 9 | Tags, archived, variants, last modified | `api /api/v1/projects/ID/features/` | Present: `tags` (ids), `is_archived`, `multivariate_options`, `last_modified_in_any_environment`, `code_references_counts`, `owners`. Paginated. | VERIFIED |
| 10 | API path form | `api /projects/ID/features/` | 404. Needs the `/api/v1/` prefix. | VERIFIED |
| 11 | Does `--jq` work with `api`? | `api ... --jq '[...]'` | Yes. 1,815 bytes became 226 bytes (88% smaller). Bytes are not model tokens. | VERIFIED |
| 12 | Segments in the project | `segment list` | None. | VERIFIED |
| 13 | Field name for a permanent tag | `api /api/v1/projects/ID/tags/` | The project has no tags (`count: 0`), so the field is unseen. | UNVERIFIED |
| 14 | Does the `Stale` tag appear? | docs | Needs Scale-up or Enterprise, so it will not appear on a free plan. | DOCS ONLY |
| 15 | Values of `lifecycle_stage` | `flag get` | Only `new` seen. Others unknown. | UNVERIFIED |
| 16 | Archive then unarchive round trip | | Not run (writes). | UNVERIFIED |
| 17 | Does an archived flag still evaluate? | | Not run (writes). | UNVERIFIED |
| 18 | Disable then restore: identical state? | | Not run (writes). | UNVERIFIED |
| 19 | Override effect on `evaluate` | | No overrides exist to test. | UNVERIFIED |
| 20 | Multivariate `flag get` / `feature get` shape | | No multivariate flag in the test project. | UNVERIFIED |
| 21 | Exit codes on failure | | Not captured by the test harness. | UNVERIFIED |
| 22 | Does `--no-input` need `--yes` for confirmations? | | Not run (writes). | UNVERIFIED |

## Changes the findings caused
| Finding | Change |
|---|---|
| 1, 2, 9: `feature list` has no tags or archived flag | The cleanup skill reads candidates through `flagsmith api /api/v1/projects/ID/features/`. |
| 2: feature-level `enabled` is not an environment state | Documented in both skills' `cli-fields.md`. Environment state comes only from `flag get -e`. |
| 8: override counts exist | `snapshot.py` records them and sets `has_overrides`. Unknown still needs approval. |
| 7: `evaluate` has a `reason` | `check_effect.py` prints it. |
| 4: `value` and `enabled` are top level | Restore reads only top-level fields, which matches the real output. |
| Real recorded outputs | Added to `tests/fixtures/recorded/` and used in tests. |

## Next
Writes need approval for each exact action. Planned drill, on the test project only: disable `new_checkout` in Production and restore it, then archive `old_banner` and unarchive it, checking `flag get` before and after each step.