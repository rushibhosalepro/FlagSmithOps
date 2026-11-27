# FlagSmithOps

Two Agent Skills that guide a coding agent through complete [Flagsmith](https://www.flagsmith.com) jobs with the Flagsmith CLI.

| Skill | What it does |
|---|---|
| [`flag-cleanup`](skills/flag-cleanup) | Finds obsolete flags, removes their code in a pull request, and archives the flags after the PR merges. |
| [`flag-incident-response`](skills/flag-incident-response) | Traces a broken feature to its flag, disables it in one environment after you approve, checks the effect for specific users, and restores on request. |

Both skills follow one safety contract. Every Flagsmith write needs your explicit approval for that exact action. Missing information is never treated as safe. Flags are archived, never deleted. The original state is captured first, and every run produces an evidence report.

## Requirements
- A coding agent that supports [Agent Skills](https://agentskills.io) (for example Kiro or Claude Code).
- [Flagsmith CLI](https://docs.flagsmith.com/integrating-with-flagsmith/CLI) v2 or later. Changing flags needs Flagsmith 2.263.0 or newer.
- Python 3 (standard library only).
- `git`, and the [`gh` CLI](https://cli.github.com) for `flag-cleanup`.

## Install

### 1. Install the Flagsmith CLI and log in
```
# macOS / Linux
brew install Flagsmith/tap/flagsmith        # or: curl -fsSL https://get.flagsmith.com | sh

# Windows (PowerShell)
irm https://raw.githubusercontent.com/Flagsmith/flagsmith-cli/main/install.ps1 | iex
```
Then run `flagsmith login`, or in CI set `FLAGSMITH_API_KEY`. Check with `flagsmith auth status`.

### 2. Install the skills with npx
Needs Node.js 22.20 or later.
```
# both skills, then pick your agents
npx skills add rushibhosalepro/FlagSmithOps

# one skill, one agent
npx skills add rushibhosalepro/FlagSmithOps --skill flag-cleanup -a kiro-cli
npx skills add rushibhosalepro/FlagSmithOps --skill flag-incident-response -a claude-code
```
Skills install into the current project. Add `-g` to install for all projects. `kiro-cli` installs to `.kiro/skills/`, which Kiro IDE also reads. Other agent names (`cursor`, `codex`, `github-copilot` and more) are listed in the [`skills` CLI docs](https://github.com/vercel-labs/skills/blob/main/docs/agents.md).

Manage them later with `npx skills list`, `npx skills update` and `npx skills remove`. The `skills` CLI sends anonymous usage data. Set `DISABLE_TELEMETRY=1` to turn that off.

### 3. Or copy the folders by hand
Clone this repository, then copy the skill folders into your agent. Each skill folder is self-contained, so you do not need the rest of the repository.
**Kiro**, for one project, copy into `.kiro/skills/`:
```
# macOS / Linux
mkdir -p .kiro/skills && cp -r skills/flag-cleanup skills/flag-incident-response .kiro/skills/

# Windows (PowerShell)
New-Item -ItemType Directory -Force .kiro\skills | Out-Null
Copy-Item -Recurse skills\flag-cleanup, skills\flag-incident-response .kiro\skills\
```
For all projects, copy into `~/.kiro/skills/` instead. You can also use Kiro's Agent Steering & Skills panel: **+ > Import a skill > Import skill from a folder**.

**Claude Code**, for one project, copy into `.claude/skills/`. For all projects, copy into `~/.claude/skills/`:
```
# macOS / Linux
mkdir -p ~/.claude/skills && cp -r skills/flag-cleanup skills/flag-incident-response ~/.claude/skills/

# Windows (PowerShell)
New-Item -ItemType Directory -Force $HOME\.claude\skills | Out-Null
Copy-Item -Recurse skills\flag-cleanup, skills\flag-incident-response $HOME\.claude\skills\
```

**Other agents:** copy the two folders into that agent's skills directory. See its documentation.

### 4. Check it loaded
Start a new agent session and type `/`. You should see `flag-cleanup` and `flag-incident-response`. The agent also loads a skill on its own when your request matches its description.

## Use

Say what you want. The skill asks for what it needs (project, environments, which one is production, repositories to search).

```
Clean up the obsolete feature flags in this repo.
```
```
Checkout is failing in production. I think it is behind a feature flag. Find it and turn it off.
```
You can also invoke a skill directly: `/flag-cleanup` or `/flag-incident-response`.

**What to expect**
- `flag-cleanup` shows a table: each flag, its verdict (PROCEED, APPROVAL REQUIRED or REFUSE), and why. It asks which code path to keep, then asks before opening the PR. After the PR merges, run it again. It re-checks live state and asks before archiving each flag.
- `flag-incident-response` shows the flag it found and the evidence. It stops and asks if several flags could be responsible. It shows the exact change and the restore command before it disables anything, then reports what the flag resolves to for the users you name.

Evidence reports are written to `evidence.md` (incident) and `.flag-cleanup/` (cleanup). They never contain credentials.

## Limits you should know
- Code search covers JavaScript, TypeScript and Python. Other languages are reported as not searched.
- The skills cannot see other repositories or services. Before archiving a flag, `flag-cleanup` asks you to confirm nothing else uses it.
- Restore covers the environment default only (enabled state and a simple value). Multivariate variants and weights are not restored, and segment and identity overrides are reported but never changed. Snapshot verification shows any difference.
- Environment coverage is checked, not assumed. Snapshots read the project's environment list from Flagsmith. The cleanup verdict and the archive gate refuse to proceed if any environment was missed, unreadable, or added, removed or renamed since the snapshot.
- Unknown is never treated as safe. If a flag's state, tags, overrides or code search results are missing, the skill asks you instead of proceeding.
- A successful CLI command does not prove an incident is over. The incident skill checks specific users and asks you to confirm the symptom is gone.
- Change requests and scheduled changes (paid Flagsmith plans) are not supported.

## Status
The scripts pass unit tests. The CLI's read-only output (flag state, override counts, evaluation, the Management API) was checked against a live Flagsmith Cloud project with CLI v2.0.0, and the results are in `docs/spike-results.md`. A write drill on disposable flags also passed: disable and restore, and archive and unarchive, each matched their snapshot. Both full workflows have since been run against live Flagsmith, including a merged PR and runs by fresh Kiro agents. See `docs/reports/VALIDATION-REPORT.md` for what is verified, what is partial, and what is not tested. Token savings are not measured.

## Develop
```
python -m unittest discover -s tests/cleanup
python -m unittest discover -s tests/incident
python shared/sync.py                                   # copy shared/scripts into each skill
python shared/validate_skill.py skills/flag-cleanup     # check the Agent Skills format
```
Edit scripts in `shared/scripts/`, then run `sync.py`. On macOS and Linux use `python3` if `python` is not available.

## Layout
```
skills/        the two skills (SKILL.md, scripts/, references/)
shared/        shared scripts, evidence template, safety contract, sync and validation
tests/         unit tests, fixtures
benchmarks/    benchmark method and results
docs/          notes on what the CLI actually does
```