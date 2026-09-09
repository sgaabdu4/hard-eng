# Hard Eng interface

Hard Eng has a command-line interface and no visual application.

- `setup.sh` installs into the current Git repository.
- `bin/hard-eng` runs source-checkout commands; installed projects use `.agents/hard-eng/bin/hard-eng`.
- `hard-eng.gates.json` holds native check commands and report locations.
- `.hooks/hard-eng.py` is the shared hook entry point; client files only register calls.
- Output identifies passing checks, failures and incomplete verification in plain text. Failures retain a nonzero exit status.

Preserve existing instructions and configuration. Use native package managers and tool reports; add no dashboard, result cache or alternative workflow.
