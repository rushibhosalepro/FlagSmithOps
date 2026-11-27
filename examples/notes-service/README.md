# Notes service: both skills, one flag's whole life

A small notes service written in JavaScript, Python and Go. It walks one flag through both skills in order:

1. **Incident** (`flag-incident-response`): the new search behind `search_v2` crashes in production. Find the flag, switch it off, verify, and keep a restore path.
2. **Fix**: the bug is fixed, and `search_v2` is turned back on and rolled out everywhere.
3. **Cleanup** (`flag-cleanup`): `search_v2` and the long-finished `legacy_export` are now obsolete. Remove their code in a PR and archive them after the merge, without touching the flags that are still in use.

It also includes the cases the [demo shop](../demo-shop/) does not cover, where the skills must ask instead of guessing:

| Flag | Where it is read | Why it matters |
|---|---|---|
| `search_v2` | `src/search.js` | The incident flag, then a cleanup candidate after the fix |
| `legacy_export` | `src/export.js` **and** `scripts/export_notes.py` | References in two languages, removed in one PR |
| `pdf_preview` | `src/preview.js`, through the `featureOn()` wrapper in `src/features.js` | Still rolling out (on in Development only). The wrapper is a non-literal SDK call, so the search cannot tell which flags it reads |
| `worker_batching` | `worker/main.go` only | The code search does not read Go. It finds **0 references**, but the flag is in use, so the skill must not treat it as unused |

The expected results below were produced by running the skill scripts on this code with these flag states. They are checked by `tests/cleanup/test_example_notes_service.py` and `tests/incident/test_example_notes_service.py`. **This example has not yet been run end to end against live Flagsmith or with an agent.** The same scripts were run live on the [demo shop](../demo-shop/) (see [`docs/reports/`](../../docs/reports/)).

```
npm test                                     # 5 tests
node src/app.js                              # all flags off: v1 search, JSON export
FLAGS="search_v2,legacy_export" node src/app.js   # search "" FAILED, CSV export
```
On Windows PowerShell: `$env:FLAGS = "search_v2,legacy_export"; node src/app.js`.

## Setup
Use a **disposable** Flagsmith project with `Development` and `Production` environments. Copy this folder out of the FlagSmithOps repository, make it a git repository with a disposable GitHub remote, and bind it:
```
git init -b main && git add -A && git commit -m "Notes service"
gh repo create my-notes-demo --private --source . --remote origin --push
flagsmith init
```
Create the flags in their incident-time state (these are setup commands, run by you, not skill steps):
```
flagsmith feature create search_v2 --description "Demo: ranked search (crashes on empty query)" --enabled --yes
flagsmith flag disable search_v2 -e Development --yes
flagsmith feature create legacy_export --description "Demo: CSV export, fully rolled out" --enabled --yes
flagsmith feature create pdf_preview --description "Demo: PDF preview, rolling out" --yes
flagsmith flag enable pdf_preview -e Development --yes
flagsmith feature create worker_batching --description "Demo: indexer batching, read in Go" --enabled --yes
```
Then install the skills in the folder: `npx skills add rushibhosalepro/FlagSmithOps -a kiro-cli` (or `-a claude-code`).

| Flag | Development | Production |
|---|---|---|
| `search_v2` | off | **on** (broken) |
| `legacy_export` | on | on |
| `pdf_preview` | on | off |
| `worker_batching` | on | on |

## Phase 1: incident (`flag-incident-response`)

**Say:** "Searching with an empty query fails in production. I think it is behind a feature flag. Environment: Production. Affected user: notes-user-1."

**Expected:**
- `candidates.py` (keywords such as `search` and `query`) returns one candidate, `search_v2`, with evidence that its name and code mention search. It is **not** a clear winner, because of two coverage gaps: a non-literal SDK call in `src/features.js`, and Go files that were not searched. The skill shows the evidence and asks you to confirm the flag.
- After you confirm: a snapshot of every environment, then the gate in check mode (VALID), then the approval request.

**Say:** "Yes, search_v2. Approved: disable it in Production only."

**Expected:**
- `disable_gate.py --execute` makes exactly one write, `flag disable search_v2 --environment Production --yes`. Development stays off.
- `check_effect.py --identity notes-user-1` shows FLAG OFF, and the skill says the incident itself is not verified.
- With the flag off, `node src/app.js` (with `FLAGS` empty) shows the empty search working again.
- Asking it to disable `search_v2` in **Development** is refused, because it is already off there.

## Phase 2: fix and roll out (you)
Fix the bug in `src/search.js`, for example return `[]` for an empty query in `searchV2`, and commit. Then ask the incident skill to restore Production ("Fixed. Approved: restore search_v2 in Production"). The restore command comes from the snapshot (`flag enable search_v2 --environment Production --yes`), and `snapshot.py verify` should print `MATCHES snapshot`. Finally, roll out to Development yourself:
```
flagsmith flag enable search_v2 -e Development --yes
```
`search_v2` is now on everywhere and ready to remove.

## Phase 3: cleanup (`flag-cleanup`)

**Say:** "Clean up the obsolete feature flags in this repo. Production is production. Only this repository uses these flags."

**Expected code search** (`find_refs.py`, 7 files searched):

| Flag | SDK calls | Other mentions | Note |
|---|---|---|---|
| `search_v2` | 1 (`src/search.js`) | 2 (tests) | |
| `legacy_export` | 2 (`src/export.js`, `scripts/export_notes.py`) | 1 (tests) | JavaScript and Python |
| `pdf_preview` | 0 | 2 (`src/preview.js`, tests) | read through the wrapper |
| `worker_batching` | 0 | 0 | only in Go, which is not searched |

Repo-wide: 1 dynamic call site (`src/features.js`) and unsearched language `.go`.

**Expected verdicts:** all four are **APPROVAL REQUIRED**. None proceeds on its own, because the dynamic call and the Go files mean the search cannot be complete. The reasons differ:

| Flag | Main reasons | What you decide |
|---|---|---|
| `search_v2` | dynamic call, 2 test mentions, `.go` not searched | Obsolete; keep the ON path |
| `legacy_export` | dynamic call, 1 test mention, `.go` not searched | Obsolete; keep the ON path (CSV) |
| `pdf_preview` | same, plus environments differ (Development on, Production off) and kept behaviour not confirmed | **Not obsolete**, still rolling out. Leave it |
| `worker_batching` | dynamic call, `.go` not searched, kept behaviour not confirmed | **Not obsolete**, used by the Go worker. Leave it |

The point of `worker_batching`: 0 references found is not evidence that a flag is unused.

**Say:** "Remove search_v2 and legacy_export, keep their ON paths. The wrapper in src/features.js only reads pdf_preview, and the Go worker only reads worker_batching. Leave pdf_preview and worker_batching alone. Approved: change the code on a branch, run the tests, and open the PR."

**Expected:** one branch removing the `search_v2` branch in `src/search.js` (keeping v2), the flag check in `src/export.js` and `scripts/export_notes.py` (keeping CSV), and the related tests. `npm test` passes. `.flag-cleanup/` holds snapshots and evidence, and a PR is opened. Your agent's sandbox may block `git push` and `gh pr create`; then you push.

**Then:**
- "Archive them now" **before** you merge: blocked, because the PR is not merged.
- Merge, then "PR merged, nothing else uses them. Approved: archive search_v2 and legacy_export": re-checks the merge, finds 0 references left on `main`, `snapshot.py verify` matches with complete environment coverage, then archives each flag after its own approval and confirms `is_archived: true`.

## Reset
```
flagsmith feature update search_v2 --unarchive --yes
flagsmith feature update legacy_export --unarchive --yes
```
Or delete the disposable project in the dashboard. The skills never delete.

## Limits
- Not yet run live with an agent. The expected results come from the scripts and the tests named above.
- Your agent's wording and command order will vary. The gates should not.
- The Go worker and the `featureOn()` wrapper are deliberate blind spots. The skill reports them; it cannot see through them.
- See [`docs/wrapper-limits.md`](../../docs/wrapper-limits.md) for what the wrapper does not block.
