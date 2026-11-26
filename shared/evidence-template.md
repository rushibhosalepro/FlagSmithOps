# Evidence report

Workflow: <flag-cleanup | flag-incident-response>
Date and time (UTC): <...>
Requested by: <user request, one line>
Flagsmith project: <name or id>
Environment(s): <names>
CLI version: <output of `flagsmith --version`>
Outcome: <COMPLETED | PARTIAL | REFUSED | STOPPED>

## Candidates and verdicts
| Flag | Verdict | Reason | Evidence (state, references, tags) |
|---|---|---|---|
| <name> | <PROCEED / APPROVAL REQUIRED / REFUSE> | <one line> | <short facts or file:line> |

## Approvals
| Action | Exact scope shown | Approved by | When |
|---|---|---|---|
| <PR / archive / disable / restore> | <flag, environment, change> | <user> | <time> |

## Commands run
List the commands. Do not include credentials.
1. `<command>` -> <exit code> <what it showed, one line>

## State before
Path to `snapshot.json`, plus a short summary per environment (enabled, value, variants and weights, overrides).

## State after
Fresh state read after the change, and the `evaluate` results for each identity checked.

## Verification
- Checked: <what>
- Not checked: <what, and why>
- Result: <matches expected | differs | could not verify>

## Restore
Command(s) to return to the original state:
```
<command>
```
Scope: environment default only. Overrides were not changed: <list>.

## Not verified
<anything the skill could not establish>
