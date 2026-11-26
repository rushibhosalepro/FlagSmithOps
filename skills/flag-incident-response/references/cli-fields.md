# CLI fields (unverified assumptions)

These have not been confirmed against a live CLI. Check them once before relying on them.

## Field check (first run)
```
flagsmith feature list --jq '.[0] | keys'
flagsmith flag get <any-flag> --environment <env> --jq 'keys'
flagsmith evaluate <any-flag> --identity test --jq 'keys'
```
If a field is missing or named differently, tell the user, adapt the filters, and note it in the evidence. Do not guess a field.

## Assumed
| Command | Field | Used for |
|---|---|---|
| `feature list` | `name` | flag names for `candidates.py` |
| `flag get` | `enabled` | state per environment, restore command |
| `evaluate FLAG --identity ID` | `enabled`, with the flag name in `name` or `feature.name` | `check_effect.py` |

## Environment argument
The CLI documents `--environment` as the environment's client-side SDK key. Some commands may accept a name. If a command rejects a name, use the key and record that in the evidence. Unverified.

## Overrides
The CLI reads overrides only by segment id or identity id. Without ids, overrides cannot be listed. Say so in the report and ask the user which identities or segments to check.