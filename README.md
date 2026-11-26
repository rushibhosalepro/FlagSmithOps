# FlagSmithOps

Two Agent Skills that guide a coding agent through complete Flagsmith jobs with the Flagsmith CLI. Built for Toggle Wars (WeMakeDevs x Flagsmith), Track 04: Flagsmith Agent Skills.

| Skill | Job |
|---|---|
| `flag-cleanup` | Find obsolete flags, remove their code, open a PR, archive the flags after the PR merges. |
| `flag-incident-response` | Trace a broken feature to its flag, disable it after approval, verify, and restore on request. |

Both skills follow one safety contract: PROCEED, APPROVAL REQUIRED or REFUSE, approval for every Flagsmith write, original state captured, flags archived and never deleted, and an evidence report for every run.

Status: planning. Specs and steering are written. The technical spike has not been run. Nothing in `skills/` is implemented yet.

## Where things are
- `.kiro/steering/`: product, safety contract, technical context, hackathon rules, structure.
- `.kiro/specs/flagsmithops-project/`: shared requirements, design and tasks (start here).
- `.kiro/specs/flag-cleanup/` and `flag-incident-response/`: skill requirements. Design and tasks follow the spike.
- `docs/spike-results.md`: what the CLI really does. Fill this in first.
- `benchmarks/methodology.md`: how token and time results are measured.

## Next step
Run the Phase 0 spike (`.kiro/specs/flagsmithops-project/tasks.md`) against a non-production Flagsmith Cloud project, then update the specs from `docs/spike-results.md`.

## Setup, usage and Flagsmith usage
To be written in Phase 6, from what is built and tested.
