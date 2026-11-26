# Spike results

Purpose: record what the Flagsmith CLI actually does, so specs rely on observed behaviour. Fill this in during Phase 0 (see `.kiro/specs/flagsmithops-project/tasks.md`). Until a row is filled in, treat it as unverified.

## Environment
| Item | Value |
|---|---|
| Date | |
| CLI version (`flagsmith --version`) | |
| OS | Windows |
| Flagsmith | Cloud (plan: ) |
| Project and environments | |
| Auth method | |

## Findings
| # | Question | Command run | Observed result | Status |
|---|---|---|---|---|
| 1 | Fields returned by `feature list --json` | | | unverified |
| 2 | Fields returned by `feature get --json` | | | unverified |
| 3 | Fields returned by `flag list --json` | | | unverified |
| 4 | Fields returned by `flag get --json` per environment | | | unverified |
| 5 | Does the `Stale` tag appear in JSON? Is feature versioning needed? | | | unverified |
| 6 | Archive then unarchive: state identical? | | | unverified |
| 7 | Does an archived flag still evaluate? | | | unverified |
| 8 | Disable then restore: state identical (incl. multivariate weights)? | | | unverified |
| 9 | Segment override: `evaluate` result when default is disabled | | | unverified |
| 10 | Identity override: `evaluate` result when default is disabled | | | unverified |
| 11 | Exit codes and error text with `--no-input` (bad flag, wrong env, no auth) | | | unverified |
| 12 | Code references or flag analytics via `flagsmith api` | | | unverified |
| 13 | Anything blocked by the free plan | | | unverified |

## Output size
| Command | Full bytes | With `--jq` bytes | `jq` expression |
|---|---|---|---|
| | | | |

## Decisions and spec changes caused by the spike
| Finding | Spec or steering file changed | Change |
|---|---|---|
| | | |

## Open items
