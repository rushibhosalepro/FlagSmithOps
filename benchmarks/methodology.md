# Benchmark methodology

Requirement: PR-07. Goal: show the measured difference between a general coding agent and the same agent using the skill. Report what we measure, including results that do not favour the skill.

## Conditions
- Baseline: same agent, same task, no skill installed.
- Treatment: same agent, same task, skill installed.

## Hold constant
Model and version, agent and version, fixture repository commit, Flagsmith project and permissions, user request text, CLI version, success conditions.

## Tasks
1. Cleanup: the `flag-cleanup` fixture repo with the eight fixture flags. Request: "Clean up the obsolete flags in this repo."
2. Incident: the incident fixture. Request: a fixed incident description.

## Runs
At least 5 runs per task per condition. Reset the fixture repo and Flagsmith project to the same state before each run. Report the median and the range.

## Metrics
| Metric | Source |
|---|---|
| Input tokens | Agent usage report |
| Output tokens | Agent usage report |
| Total tokens | Agent usage report |
| CLI calls | `meter.py` |
| CLI output bytes | `meter.py` |
| Failed commands | `meter.py` |
| Completion time | Wall clock, start of request to final state |
| Correct decisions | Verdict per fixture compared with the expected verdict |
| Unsafe actions | Any write without approval, deletion, or change outside the named environment |

Rules:
- Keep CLI output bytes and model tokens separate. Do not convert one into the other.
- If actual token usage is unavailable, label any estimate as an estimate and say how it was made.
- Do not set a target multiple in advance.
- Record the agent's number of turns and whether the run completed the whole job.

## Output
`benchmarks/results/<date>-<task>.md` with the table of runs, the median and range per metric, and notes on failures. The demo table is copied from these files.

## Also measure
- Output size with and without `--jq` for the main read commands.
- `SKILL.md` size in tokens (estimate), since it loads on activation.
