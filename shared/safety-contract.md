<!-- Copy of .kiro/steering/safety-contract.md. Keep in sync. -->
# Shared safety contract

Both skills follow this contract. Do not weaken it in a skill. If a skill needs an exception, change this file first and note why.

## Principles
1. The Flagsmith CLI is the primary interface for flag operations.
2. Read before write.
3. Missing information is not evidence of safety.
4. Consequential Flagsmith writes need explicit human approval.
5. Capture the original state before changing anything.
6. Verify every consequential change using fresh state, not the CLI exit code alone.
7. Never permanently delete a flag. Archive instead.
8. Write an evidence report for every completed or refused workflow.
9. Use `--json` and `--jq` to keep CLI output small.
10. Stop when an operation fails or safety cannot be established. Show the exact error. Do not work around it.

## Verdicts
A verdict classifies the next operation.

| Verdict | Meaning | Agent behaviour |
|---|---|---|
| PROCEED | Evidence supports the next operation | Read-only and local operations continue without asking. A Flagsmith write is presented for approval first. |
| APPROVAL REQUIRED | Evidence is incomplete or the impact is meaningful | Show the planned action, the evidence and the rollback. Wait for explicit authorization. |
| REFUSE | The operation is unsafe or unsupported | Stop, explain why, and record it in the evidence report. |

PROCEED never skips approval for a Flagsmith write. It means the write is eligible to be presented.

## Approval rules
- An approval covers only the exact action shown (flag, environment, change).
- A previous approval does not cover a different flag, environment or operation.
- Approval is requested separately for: opening a PR, archiving a flag, and disabling or restoring a flag.
- Silence, ambiguity, or "looks fine" without a clear yes is not approval.

## State capture and restore
- Before any write, save a snapshot of the affected flag in every environment: enabled state, value, variants and weights, and a list of segment and identity overrides.
- Restore scope: environment default (enabled state and value) only. Overrides are reported, never changed automatically.
- Every write has a documented restore command stored in the evidence report.

## Stop conditions
Stop and report when any of these happens:
- A CLI command fails or returns an unexpected shape.
- The project or environment is not the one the user named.
- The Flagsmith version, plan or permissions do not support the operation (for example a 403 or 409 from enforced change requests).
- More than one candidate flag matches an incident and the evidence cannot separate them.
- Fresh verification disagrees with the expected result.

## Evidence report
Every run produces `evidence.md` from `shared/evidence-template.md`. It records:
- The request, project, environment and CLI version.
- Each candidate and its verdict, with the evidence.
- The commands run (not secrets) and what changed.
- The before and after state, and the restore command.
- Anything not verified.

## Secrets
Never print, log, commit or copy API keys or `flagsmith.env` contents. `flagsmith.json` holds no secrets and may be committed.

