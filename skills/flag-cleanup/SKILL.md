---
name: flag-cleanup
description: Finds obsolete Flagsmith feature flags, removes their code in a pull request, and archives the flags after the PR merges, using the Flagsmith CLI. Refuses protected or still-used flags and asks for approval before every write. Use when the user wants to clean up, remove, retire or archive stale feature flags, or reduce flag debt.
compatibility: Requires the flagsmith CLI v2 (logged in, or FLAGSMITH_API_KEY set), git, the gh CLI, and Python 3.
---

# Flag cleanup

Take a flag from "probably obsolete" to "code removed, PR merged, flag archived", without surprises.

## Rules
- Read before write. Missing information is never evidence of safety.
- Never run `flagsmith feature delete`. Archive only.
- Ask for explicit approval, separately, before: opening the PR, and archiving each flag. An approval covers only the exact action shown.
- If a command fails or its output is not what you expect, stop and show the exact error. Do not work around it.
- Never print or commit API keys. Use `--json` with `--jq` and keep output small.
- Scripts live in `scripts/`. They do exact work. You decide, ask and explain.

## Workflow

**0. Preflight.** Run `flagsmith --version`, `flagsmith auth status`, `flagsmith config`. Ask the user to confirm: the Flagsmith project, the environments, which one is production, and which repositories are in scope. First time only: check the CLI fields against `references/cli-fields.md`. If the CLI is not logged in, stop and tell the user.

**1. Candidates.** List features with `flagsmith feature list` and a `--jq` filter that returns only name, tags and archived status (see `references/cli-fields.md`). Skip archived features and say so. If the user named flags, use only those.

**2. Inspect.** For each candidate list environment names with `flagsmith environment list`, then run `python scripts/snapshot.py capture --flag NAME --env ENV [--env ENV2] --known-envs ENV,ENV2,... --out .flag-cleanup/NAME.snapshot.json`. It reads the flag in every environment and prints one line each (enabled=unknown means the state could not be read). Tell the user about any WARNING for environments not captured. Note whether the flag is multivariate.

**3. Search code.** Run `python scripts/find_refs.py --repo . [--repo OTHER] --flag NAME --summary`. It reports SDK calls, other mentions, dynamic calls that could read any flag, and languages it did not search (`references/patterns.md`).

**4. Decide.** Write one JSON object per candidate to `.fsops/candidates.json` (fields in `scripts/verdict.py`), then run `python scripts/verdict.py --input .fsops/candidates.json --table`. Show the user the table. Ask the questions it returns, for example which code path to keep. Re-run with their answers in `user.kept_behavior` and `user.other_usage`.
- REFUSE: stop for that flag and explain why.
- APPROVAL REQUIRED: resolve the reasons with the user. Do not guess.
- PROCEED: eligible. Still present the plan for approval (step 5).
- Unknown is not safe: an unreadable environment state, unchecked overrides, missing tags or missing search results never produce PROCEED. Ask the user to resolve them, or to accept the risk explicitly.

**5. Plan and approve.** Show: flags, files and lines to change, which path is kept, the tests you will run, and the rollback. Wait for a clear yes (`references/approvals.md`).

**6. Change code.** Create branch `chore/remove-flag-NAME`. Remove only the verified references and anything left unused as a direct result. Keep the path the user confirmed. Run the repository's tests. If they fail or none exist, stop and tell the user.

**7. Evidence and PR.** Write the run to `.fsops/run.json`, then `python scripts/evidence.py --input .fsops/run.json --out .flag-cleanup/evidence.md`. Commit the code, `.flag-cleanup/evidence.md` and the snapshot files. After approval, open the PR with `gh pr create`, using the evidence as the body. Stop here until the PR merges. Tell the user to run this skill again after the merge.

**8. After the merge (resume).** In a new session, read `.flag-cleanup/` on the default branch to find flags awaiting archive. Do not trust the files. Re-check live:
- `gh pr view --json state,mergedAt` shows merged. If not, block the archive.
- `python scripts/find_refs.py` on the default branch shows no references left.
- `python scripts/snapshot.py verify --file .flag-cleanup/NAME.snapshot.json` matches.
- Ask the user to confirm no other repository, service or client uses the flag. If they cannot, block the archive.

**9. Archive.** After approval for each flag: `flagsmith feature update NAME --archive`. Read the fresh state, then `flagsmith evaluate NAME --identity cleanup-check` and report what you see. Say so if archiving changes how the flag evaluates (this is not confirmed yet). Restore command: `flagsmith feature update NAME --unarchive`.

**10. Report.** Update the evidence report. Run `python scripts/cli.py meter` and give the user the call count and output size. State anything you could not verify.

## Output
Be brief. Use compact tables. Never paste raw JSON from the CLI.

## References
- `references/cli-fields.md`: the field names this skill assumes, and how to check them.
- `references/patterns.md`: supported languages and call patterns, and what is not covered.
- `references/approvals.md`: wording for approval requests.