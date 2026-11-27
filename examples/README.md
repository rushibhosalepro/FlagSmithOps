# Examples

| Example | What it shows |
|---|---|
| [`demo-shop/`](demo-shop/) | A tiny shop with a broken checkout (`new_checkout`) and an obsolete banner (`old_banner`). Rerun the incident and cleanup drills, and the safety drills, against your own disposable Flagsmith project, then compare with the recorded live runs. |
| [`notes-service/`](notes-service/) | Both skills on one flag's whole life: an incident on `search_v2`, the fix, then a cleanup of `search_v2` and `legacy_export`. Adds JavaScript and Python references, an SDK wrapper the search cannot see through, and a flag read only in Go. Expected results come from the scripts and are checked by tests. It has not yet been run live. |

The recorded runs these examples reproduce:
- [`docs/reports/logs/`](../docs/reports/logs/): scripted runs with exact commands and outputs (cleanup through a merged PR, incident, and a live gate disable and restore).
- [`docs/reports/kiro-final/`](../docs/reports/kiro-final/): fresh Kiro sessions, including refusals (delete, gate bypass, archive before merge), with instrumentation counts and agent-written evidence.
- [`docs/reports/VALIDATION-REPORT.md`](../docs/reports/VALIDATION-REPORT.md): what is verified, partial and not tested.
