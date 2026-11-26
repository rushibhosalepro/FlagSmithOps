# CLI conventions

Provisional until `docs/spike-results.md` is complete. Use only commands listed as verified in `.kiro/steering/tech.md`.

1. Always pass `--json`. Add `--jq '<expr>'` to return only the fields needed. Never print a full response when a few fields will do.
2. Pass `--no-input` so a command fails instead of prompting or opening a browser.
3. Name the project and environment explicitly (`--project`, `--environment`) or confirm `flagsmith config` shows the ones the user named.
4. Read before write. Reading works on any instance. Writes need Flagsmith 2.263.0 or newer.
5. Run one command at a time for writes. After each write, read fresh state.
6. On a non-zero exit code or an unexpected output shape, stop and show the exact message.
7. Never call `flagsmith feature delete`.
8. Never print `FLAGSMITH_API_KEY`, `FLAGSMITH_ENVIRONMENT_KEY`, or the output of `flagsmith auth token`.
9. Record every command (without secrets) in the evidence report.
10. Count the CLI calls and output size of each run for the benchmark.

## Field reference
To be filled from `docs/spike-results.md`: field names for `feature list`, `feature get`, `flag list`, `flag get`, and the `jq` expressions that return the minimum needed.
