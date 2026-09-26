# Write hard-eng.gates.json in Biome's layout

Status: Complete

## Outcome + scope

Setup and update write `hard-eng.gates.json` in the layout Biome's formatter produces: 2-space indent, objects expanded, and arrays of scalars kept on one line when they fit in 80 columns. A project whose format-lint runs Biome over the file can then install an update, because candidate verification no longer fails on Hard Eng's own output.

Non-goals: Biome's fill layout for number-only arrays longer than 80 columns and number-literal normalisation (gates.json holds neither); other JSON files setup writes.

## Repository context

Owner: `setup.py` `plan_install`, which writes the file from `gate_config`/`retired_config` and again after adapting packages. `.hooks/update.py` runs the candidate's `setup.py`, so both paths share this writer. Both used `json.dumps(indent=2)`, which puts every array element on its own line, for example `"checks": ["verify"]`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked for the fix, a test, a PR and a CI watch, with no merge.

Decision: render the layout in the stdlib (`gates_text`) rather than call Biome, so installed projects need no new runtime dependency.

## Acceptance + steps

- [x] A representative config renders to the exact Biome text: short `checks`/`sources` arrays inline, empty `{}`/`[]`, a `command` line of exactly 80 columns inline and one of 81 wrapped → `test_gates_file_matches_biome_layout`.
- [x] Fresh setup writes the file in that layout → `test_plain_dart_uses_native_coverage_tool`.
- [x] Regenerating a retired config (the update path) writes that layout → `test_retired_families_config_is_regenerated_and_reported`.

## Baseline + execution

Result: Passed
Evidence: Main `4e77de1` CI passed. Before the fix, the jabal_sina_pharmacy update log showed `FAIL format-lint` on the candidate's `hard-eng.gates.json` ("File content differs from formatting output"), with Biome collapsing `"checks": ["verify"]`, `"sources": ["lib"]` and short `command` arrays. With the old writer restored, both writer tests fail.
Execution: One builder, one commit.

## Risks + recovery

Projects whose gates.json Hard Eng rewrites get a one-time layout diff. Recovery: revert the commit.

## ux_reference

N/A — installer file output with no visual surface.

## Verification

Result: Passed
Evidence: Biome 2.5.14 (`indentStyle: space`, `lineWidth: 80`) reports no formatting change for `gates_text` output of the pharmacy's real config, every shipped template, this repository's config, nested and empty containers, and 80/81-column boundaries at two depths. `python3 .hooks/hard-eng.py check` → exit 0, 17/17 gates PASS, 913 tests.
E2E: N/A — Biome is not in this repository's CI; the Biome run above and the exact-text test stand in for it.

Delivery target: PR
Delivery: Pending — PR checks green.
