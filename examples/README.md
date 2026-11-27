# Examples

| Example | What it shows |
|---|---|
| [`demo-shop/`](demo-shop/) | A tiny shop with a broken checkout (`new_checkout`) and an obsolete banner (`old_banner`). Rerun the incident and cleanup drills, and the safety drills, against your own disposable Flagsmith project, then compare with the recorded live runs. |

The recorded runs these examples reproduce:
- [`docs/reports/logs/`](../docs/reports/logs/): scripted runs with exact commands and outputs (cleanup through a merged PR, incident, and a live gate disable and restore).
- [`docs/reports/kiro-final/`](../docs/reports/kiro-final/): fresh Kiro sessions, including refusals (delete, gate bypass, archive before merge), with instrumentation counts and agent-written evidence.
- [`docs/reports/VALIDATION-REPORT.md`](../docs/reports/VALIDATION-REPORT.md): what is verified, partial and not tested.
