# Supported code patterns

`scripts/find_refs.py` searches JavaScript, TypeScript (`.js .jsx .ts .tsx .mjs .cjs`) and Python (`.py`). It skips `.git`, `node_modules`, `venv`, `dist`, `build` and similar folders, and files over 1 MB.

## What counts as an SDK reference
The flag name as the first literal argument of: `hasFeature`, `isFeatureEnabled`, `getValue`, `getFeatureValue`, `getFlag`, `useFlags` (array of names), `has_feature`, `is_feature_enabled`, `get_feature_value`, `get_flag`, `get_value`.

## What is reported separately
- Other literal: the exact flag name in a string anywhere else (config, tests, docs). Needs human review.
- Dynamic call site: one of the calls above whose argument is a variable, template string or expression. It may read any flag, so the candidate needs approval.
- Unsearched language: files in Go, Java, Kotlin, Ruby, PHP, C#, Swift, Dart, Rust, Scala or Elixir. They are counted, not searched.

## Not covered
- Wrappers around the SDK with their own names (for example `useFeature(name)`). Search for them by hand and tell the user.
- Flag names assembled from parts, read from config or environment variables, or generated.
- Usage in other repositories, services, mobile apps or dashboards. Always ask the user (step 8).
- Multi-line calls where the name is on a later line.