# React Doctor

1. Manifest argv = `npx --yes react-doctor@latest . --scope full --blocking warning --no-respect-inline-disables --no-telemetry --json -y` → every gate executes the manifest family through `project_gate.py`.
2. Default parallel workers stay enabled; one full scan replaces staged + changed + full repeats.
3. Staged/changed/files/lines/base/project/category/time-budget narrowing = forbidden.
4. Diagnose-only, never gate proof → no concurrent gate + latest command + `why <file:line>`; rule → latest command + `rules explain <rule> --json`.
5. Nonzero/finding/incomplete/skipped = `FAIL`; fix root cause + rerun full scan.
6. Project-local install/wrapper/runtime copy = forbidden.
7. Execution = `project_gate.py` exclusive source lock because audit mode may temporarily neutralize inline directives on disk; restore + exact-tree fingerprint precede unlock.
8. Interrupted/non-restored audit = Git-private quarantine + no later gate command; exact manual worktree restoration clears quarantine + automatic checkout/overwrite forbidden.
