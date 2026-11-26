# CLI fields (unverified assumptions)

These field names have not been confirmed against a live CLI. Check them once before relying on them.

## Field check (first run)
```
flagsmith feature list --jq '.[0] | keys'
flagsmith flag get <any-flag> --environment <env> --jq 'keys'
```
Compare with the list below. If a field is missing or named differently, tell the user, adapt the `--jq` filters, and note it in the evidence report. Do not guess a field.

## Assumed
| Command | Field | Used for |
|---|---|---|
| `feature list` | `name` | candidate name |
| `feature list` | `tags` | permanent and stale tags. May be ids, not names. |
| `feature list` | archived status (for example `is_archived`) | skip archived |
| `feature list` | variants or multivariate options | multivariate detection |
| `flag get` | `enabled` | environment state, restore command |
| `flag get` | `feature_state_value` or `value` | value restore |

## Tags
If tags come back as ids, resolve them to names before applying the permanent-tag rule. If you cannot read tag names, pass `tags: null` to `verdict.py`. It will not allow PROCEED, because permanent status is unknown.

## Stale
Staleness comes from the `Stale` tag or from the user. Whether the tag appears in CLI output is unverified. Pass `stale: null` when it is not established.

## Overrides
The CLI reads overrides only per segment or identity id. `snapshot.py capture` records them only when given `--segment-ids`. Otherwise pass `has_overrides: null`. The verdict is then APPROVAL REQUIRED, and the archive stays blocked until overrides are checked or the user explicitly accepts the risk (`user.accept_unchecked_overrides`). The report lists them as not checked either way.