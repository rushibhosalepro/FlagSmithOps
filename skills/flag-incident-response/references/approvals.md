# Approval and report wording

An approval covers only the action shown. Accept a clear yes. Silence or "maybe" is not approval.

## Disable
```
Disable `NAME` in `ENV`?
- Evidence: <one line>.
- Change: enabled -> disabled (environment default only).
- Other environments are not touched: <list>.
- Not affected by this change: <overrides, if any>.
- Restore: <command, with --yes>
Go ahead? (yes / no)
```

## Partial result
```
Partial. `NAME` is off by default in ENV, but still on for: <identities>.
Cause: <override>. I will not change overrides. Options: ask a human to review them, or tell me which to check.
```

## Verified vs not
```
Checked: flag state in ENV, evaluation for <identities>.
Not checked: whether the symptom is gone (please confirm), <anything else>.
```

## Refusal
```
Not changing `NAME`: <reason>.
What would help: <the human decision or missing information>.
```