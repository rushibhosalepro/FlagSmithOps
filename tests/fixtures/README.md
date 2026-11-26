# Test fixtures

`cli_outputs/` holds SYNTHETIC examples of `flagsmith flag get --json` output. The real field names are
unverified, so these only exercise how our scripts behave when a field is present, missing, null or nested.
Replace them with recorded real output after the live check.

`verdict_inputs/` holds candidate objects for `verdict.py`.