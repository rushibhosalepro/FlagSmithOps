# Evidence report

Workflow: flag-cleanup (resume after merge)
Date and time (UTC): 2026-11-27 03:36
Requested: Archive old_banner after PR #1 merged
Flagsmith project: testing (<project-id>)
Environment(s): Development, Production
CLI version: v2.0.0
Outcome: NOT ARCHIVED: the archive command was blocked by the agent environment. Flag is still active (is_archived=false).

## Candidates and verdicts
| Flag | Verdict | Reason | Evidence |
|---|---|---|---|
| old_banner | gates passed, archive pending | PR #1 merged 2026-11-27T03:14:32Z; no references on main; snapshot matches, environments complete, no overrides, no tags; user confirmed no other repo/service/client uses it | .flag-cleanup/old_banner.snapshot.json |

## Approvals
| Action | Exact scope shown | Approved by | When |
|---|---|---|---|
| archive old_banner | test project only, reversible | user | session request |

## Commands run
1. `gh pr view 1 --json state,mergedAt,headRefName` -> exit 0, MERGED
2. `cli.py run --text -- --version` -> exit 0
3. `find_refs.py --repo . --flag old_banner --summary` -> exit 0, 0 refs
4. `snapshot.py verify --file .flag-cleanup/old_banner.snapshot.json` -> exit 0, MATCHES
5. `cli.py run -- api /api/v1/projects/<project-id>/features/ --jq ...` -> exit 0, is_archived=false
6. `cli.py run -- feature update old_banner --archive --yes` -> blocked before running, not executed

## State before
old_banner enabled in Development and Production, not archived

## State after
unchanged (not archived)

## Verification
Checked:
- PR merged
- no code refs
- snapshot verify
- is_archived false
Not checked:
- post-archive is_archived
- post-archive evaluate
Result: archive not performed

## Restore
```
flagsmith feature update old_banner --unarchive --yes
```

## Not verified
- Other repos/services/clients (user stated none)
- Archive effect
