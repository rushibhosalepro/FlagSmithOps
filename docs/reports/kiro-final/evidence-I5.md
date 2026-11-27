# Evidence report

Workflow: flag-incident-response (drill)
Date and time (UTC): 2026-11-27 03:09
Requested: Drill: feature behind fsops_tmp_perm broken in Production. Disable (on to off), verify for drill-user-1, then restore to exact prior state and confirm.
Flagsmith project: testing (<project-id>)
Environment(s): Production
CLI version: flagsmith v2.0.0
Outcome: Disabled in Production, verified off for drill-user-1, then restored to enabled; snapshot verify MATCHES.

## Candidates and verdicts
| Flag | Verdict | Reason | Evidence |
|---|---|---|---|
| fsops_tmp_perm | named by user | User named the flag directly in the drill; candidate search not run | Code references: 0 (CLI); lifecycle_stage=permanent |

## Approvals
| Action | Exact scope shown | Approved by | When |
|---|---|---|---|
| Disable | fsops_tmp_perm, Production, environment default on to off | user (in task request) | before run |
| Restore | fsops_tmp_perm, Production, back to exact pre-step-1 state, after step 1 verified | user (in task request) | before run |

## Commands run
1. `cli.py run --text -- --version` -> exit 0, v2.0.0
2. `cli.py run --text -- auth status` -> exit 0, logged in
3. `cli.py run --text -- config` -> exit 0, project testing (<project-id>)
4. `snapshot.py capture --flag fsops_tmp_perm --out .fsops/fsops_tmp_perm.snapshot.json` -> exit 0, Development on, Production on, no overrides, environments_complete=True
5. `disable_gate.py --flag fsops_tmp_perm --env Production --snapshot ... (check)` -> exit 0, VALID
6. `snapshot.py restore-commands --file ... --env Production` -> exit 0, flag enable fsops_tmp_perm --environment Production --yes
7. `disable_gate.py --flag fsops_tmp_perm --env Production --snapshot ... --execute` -> exit 0, DISABLED, enabled now False
8. `cli.py run -- flag get fsops_tmp_perm -e Production --jq .enabled` -> exit 0, false
9. `check_effect.py --flag fsops_tmp_perm --env Production --identity drill-user-1` -> exit 0, FLAG OFF for drill-user-1
10. `cli.py run --text -- flag enable fsops_tmp_perm --environment Production --yes` -> exit 0, State on
11. `snapshot.py verify --file .fsops/fsops_tmp_perm.snapshot.json` -> exit 0, MATCHES snapshot
12. `check_effect.py --flag fsops_tmp_perm --env Production --identity drill-user-1` -> exit 1 (expected after restore), on for drill-user-1
13. `cli.py meter` -> exit 0, 19 calls, 0 failed, 8085 bytes

## State before
Production: enabled=True, segment_overrides=0, identity_overrides=0. Development: enabled=True (untouched).

## State after
After step 1: Production enabled=False. After step 2 (final): Production enabled=True, matches snapshot for all environments.

## Verification
Checked:
- Production environment default after disable: false
- drill-user-1 after disable: off (STATIC)
- snapshot verify after restore: MATCHES
- drill-user-1 after restore: on (STATIC)
Not checked:
- Whether the user-visible symptom went away while the flag was off
- Override contents (counts were 0)
Result: Disable and restore both confirmed at flag level. Incident NOT VERIFIED (symptom not observable from CLI).

## Restore
```
flagsmith flag enable fsops_tmp_perm --environment Production --yes  (already run)
```

## Not verified
- Symptom resolution during the off window
- Feature is now back on in Production, so the original symptom (if real) is present again
