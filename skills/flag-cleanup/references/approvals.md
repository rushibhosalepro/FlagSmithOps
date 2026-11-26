# Approval requests

An approval covers only the action shown. Accept a clear yes. Silence, "maybe" or "looks fine" is not approval.

## Open the PR
```
Plan for flag `NAME`:
- Remove N references in these files: ...
- Keep the <on/off/variant> code path (production is <state>).
- Tests: <command>, result <pass>.
- Rollback: revert the PR. Flag state is unchanged until you approve the archive.
Open the PR? (yes / no)
```

## Archive
```
Archive flag `NAME`?
- PR #N is merged. No references remain on <branch> in: <repos>.
- You confirmed no other service uses it: <yes/not confirmed>.
- Environments: <env: state, ...>.
- Command: flagsmith feature update NAME --archive
- Restore: flagsmith feature update NAME --unarchive
Archive? (yes / no)
```

## Refusal
```
Not touching `NAME`: <reason>. Evidence: <one line>.
What would change this: <what the user can confirm or fix>.
```