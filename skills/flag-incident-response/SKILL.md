---
name: flag-incident-response
description: Traces a production incident to the responsible Flagsmith feature flag, disables it in one named environment after explicit approval, verifies the effect for specific users, and gives a tested restore command. Use when a feature is broken in production and may be behind a flag, or when the user asks for a kill switch or to turn a feature off quickly and safely.
compatibility: Requires the flagsmith CLI v2 (logged in, or FLAGSMITH_API_KEY set), git, and Python 3.
---

# Flag incident response

Find the flag behind a broken feature, switch it off safely, prove what changed, and leave a way back.

## Rules
- Never write before the user approves the exact action: which flag, which environment, from what to what.
- Change one flag in one named environment. Never disable several flags "to be safe".
- Disable only through `scripts/disable_gate.py`. A BLOCKED result is a stop, not a warning. Incomplete environment coverage is never accepted.
- If more than one flag could be responsible and the evidence cannot separate them, stop and ask.
- Never delete or archive a flag. Disabling the environment default is the only mitigation.
- A successful command does not prove the incident is over. Verify, and say what you could not verify.
- If a command fails or its output is not what you expect, stop and show the exact error.
- Never print or commit API keys. Keep CLI output small with `--json --jq`.
- Read an environment's state only with `flag get NAME -e ENV` (or `snapshot.py`). `feature get` and `feature list` show a project-level default, not the environment state, so never use them as evidence of a change.
- Run every Flagsmith command through `python scripts/cli.py run -- <args>` (add `--text` for plain output). The wrapper blocks deletes and API writes, hides keys, adds `--no-input`, and counts calls for the report. Do not call `flagsmith` directly.

## Workflow

**0. Preflight.** Run `python scripts/cli.py run --text -- --version`, then `... -- auth status` and `... -- config` (if your agent blocks these, say so and continue; the user confirms the project instead). Get from the user: the affected feature and symptoms, the project, the environment to mitigate (must be named, not assumed), and an identity affected by the problem. First time only: check the CLI fields in `references/cli-fields.md`.

**1. Find candidates.** Save the flag names to `.fsops/flags.txt` with `python scripts/cli.py run -- feature list --jq ".[].name"`. Run `python scripts/candidates.py --repo . --keyword WORD [--keyword WORD2] --flags-file .fsops/flags.txt`. Keywords come from the user's description (feature, page, service names).

**2. Resolve.** The ranking is a heuristic. Even when `clear_winner` is true, show the flag and its evidence and get the user to confirm it. If `clear_winner` is false, show the top candidates and ask the user to choose. Stop until they do. If there are no candidates, say so and stop. A winner is never named when `coverage_gaps` is not empty (dynamic SDK calls, unsearched languages): tell the user the cause may not be in the search.

**3. Capture original state.** Run `python scripts/snapshot.py capture --flag NAME --out .fsops/NAME.snapshot.json`. It reads the project's environment list itself and captures every environment, so you can show the others are untouched. If it prints a WARNING about coverage, tell the user. If the project uses segments, ask the user which ones could matter and pass `--segment-ids`.

**4. Prepare.** Check mitigation is safe. REFUSE and explain if disabling could cause harm (for example the flag guards a data migration or a payment path with no fallback), or if the state could not be read. Otherwise show: flag, environment, change (on to off), expected effect, who may still see the feature (overrides), and the restore commands from `python scripts/snapshot.py restore-commands --file .fsops/NAME.snapshot.json --env ENV`. Then run the gate in check mode: `python scripts/disable_gate.py --flag NAME --env ENV --snapshot .fsops/NAME.snapshot.json`. If it prints BLOCKED (exit 3), stop: show the reasons, fix them (usually capture again), and do not ask for approval until it prints VALID.

**5. Approve.** Use the wording in `references/approvals.md`. Wait for a clear yes.

**6. Apply.** `python scripts/disable_gate.py --flag NAME --env ENV --snapshot .fsops/NAME.snapshot.json --execute`. Disable only this way. The wrapper refuses `flag disable` made through it, but it cannot stop a direct `flagsmith` call, so never make one. The gate re-checks the snapshot and live state, then disables. BLOCKED (exit 3) means nothing was written: stop and report the reasons. Do not retry another way, and do not ask the user to accept the gap.

**7. Verify.** Read the new state with `python scripts/cli.py run -- flag get NAME -e ENV --jq .enabled`. Then run `python scripts/check_effect.py --flag NAME --env ENV --identity AFFECTED [--identity OVERRIDE_USER]`. `--env` is required, so you never check the wrong environment. Include an identity covered by each override you know of. FLAG OFF means only that those identities see the flag off. PARTIAL means someone still sees the feature: name them. UNVERIFIED means you could not tell. The script always prints `Incident: NOT VERIFIED`. Never tell the user the incident is resolved. Ask them to confirm the symptom is gone, because you cannot see that from the CLI.

**8. Restore (when asked).** Ask for approval. Run the restore commands (they include `--yes`). Confirm with `python scripts/snapshot.py verify --file .fsops/NAME.snapshot.json`. Report if the state differs or if environments were added, removed or renamed since the snapshot. Restore covers the environment default only (enabled state and a simple value). Variants, weights and overrides are not restored. Report any difference `verify` finds.

**9. Evidence.** Always do this after a mitigation, a restore or a refusal. It is a local file, so it needs no approval. Write the run to `.fsops/run.json` and run `python scripts/evidence.py --input .fsops/run.json --out evidence.md`. Include candidates, the action or the refusal, the verification result, the restore command and anything not verified. Run `python scripts/cli.py meter` and report calls and output size.

## Output
Be brief. During an incident the user is under pressure. Lead with the decision needed, then the evidence. No raw JSON.

## References
- `references/cli-fields.md`: assumed fields and the first-run check.
- `references/approvals.md`: wording for approval, partial result and refusal.