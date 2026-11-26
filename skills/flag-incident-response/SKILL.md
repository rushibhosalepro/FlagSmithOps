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
- If more than one flag could be responsible and the evidence cannot separate them, stop and ask.
- Never delete or archive a flag. Disabling the environment default is the only mitigation.
- A successful command does not prove the incident is over. Verify, and say what you could not verify.
- If a command fails or its output is not what you expect, stop and show the exact error.
- Never print or commit API keys. Keep CLI output small with `--json --jq`.

## Workflow

**0. Preflight.** Run `flagsmith --version`, `flagsmith auth status`, `flagsmith config`. Get from the user: the affected feature and symptoms, the project, the environment to mitigate (must be named, not assumed), and an identity affected by the problem. First time only: check the CLI fields in `references/cli-fields.md`.

**1. Find candidates.** Save the flag names to `.fsops/flags.txt` (`flagsmith feature list` with a `--jq` that returns names only). Run `python scripts/candidates.py --repo . --keyword WORD [--keyword WORD2] --flags-file .fsops/flags.txt`. Keywords come from the user's description (feature, page, service names).

**2. Resolve.** If `clear_winner` is false, show the top candidates with their evidence and ask the user to choose. Stop until they do. If there are no candidates, or the flag is not clearly the cause, say so and stop. Mention `dynamic_call_sites` and `unsearched_languages` when non-zero, since they can hide a flag.

**3. Capture original state.** Run `python scripts/snapshot.py capture --flag NAME --env ENV [--env OTHER] --out .fsops/NAME.snapshot.json`. Capture every environment so you can show the others are untouched. If the project uses segments, ask the user which ones could matter and pass `--segment-ids`.

**4. Prepare.** Check mitigation is safe. REFUSE and explain if disabling could cause harm (for example the flag guards a data migration or a payment path with no fallback), or if the state could not be read. Otherwise show: flag, environment, change (on to off), expected effect, who may still see the feature (overrides), and the restore commands from `python scripts/snapshot.py restore-commands --file .fsops/NAME.snapshot.json --env ENV`.

**5. Approve.** Use the wording in `references/approvals.md`. Wait for a clear yes.

**6. Apply.** `python scripts/cli.py run -- flag disable NAME --environment ENV`. On any failure, stop and show the error. Do not retry with other options.

**7. Verify.** Run `python scripts/check_effect.py --flag NAME --identity AFFECTED [--identity OVERRIDE_USER]`. Include an identity covered by each override you know of. If the result is PARTIAL, say the mitigation is partial and name who still sees the feature. Then ask the user to confirm the symptom is gone. You cannot see that from the CLI.

**8. Restore (when asked).** Ask for approval. Run the restore commands. Confirm with `python scripts/snapshot.py verify --file .fsops/NAME.snapshot.json`. Report if the state differs. Restore covers the environment default only. Overrides are reported, never changed.

**9. Evidence.** Write the run to `.fsops/run.json` and run `python scripts/evidence.py --input .fsops/run.json --out evidence.md`. Include candidates, the action or the refusal, the verification result, the restore command and anything not verified. Run `python scripts/cli.py meter` and report calls and output size.

## Output
Be brief. During an incident the user is under pressure. Lead with the decision needed, then the evidence. No raw JSON.

## References
- `references/cli-fields.md`: assumed fields and the first-run check.
- `references/approvals.md`: wording for approval, partial result and refusal.