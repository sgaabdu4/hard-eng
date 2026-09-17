# Strict scanner gates with mandatory repair

Status: Complete

## Outcome + scope

Every scaffolded repository fails its scanner gates on any finding, and no finding may be tolerated, baselined or suppressed: it is repaired in code and that repair is committed before the task's own work continues, even when the finding is unrelated to the task. Concretely: the Dart template and the Dart boundary adapter run `dart-decimate check ... --strict`; the React Doctor gate runs with `--no-respect-inline-disables` so inline lint disables no longer hide diagnostics; gate validation requires `--strict` on `dart-decimate check`, `--blocking warning --no-respect-inline-disables` on React Doctor, `--fail-on-issues` on fallow scans and `--gate all` on `fallow audit`, and rejects debt-tolerating flags (`--regression-baseline`, `--fail-on-regression`, `--tolerance` for dart-decimate; `--baseline`, `--save-baseline`, `--dead-code-baseline`, `--health-baseline`, `--dupes-baseline` for fallow) with a message that says to repair the findings; the strict Dart boundary command still has its project rules validated; the gates reference, the installed `AGENTS.md` rule and `DECISION.md` state the rule. No suppression-comment grep gate, no runtime rewriting of installed configurations.

## Repository context

Owners: `.agents/skills/he/templates/hard-eng.dart.json` (both dart-decimate commands), `.hooks/project_setup.py` `adapt_boundaries` (Dart boundary command) and `adapt_javascript` (react-doctor command), `validate_command_output` (already rejects Node warning suppression, then the fallow command validator), `.hooks/gate_config.py` `validate_dart_boundaries` (exact command match, file at the 700-line limit), `.hooks/fallow_report.py` (fallow command validator, generalised to `validate_scanner_command`; `tool_setup.managed_scanner_command` reuses its scanner detection), `.agents/skills/he/references/gates.md` (Exceptions row, Baseline repair), source `AGENTS.md` Verification rule (installed into projects by `configure_instructions`), `DECISION.md` items 89, 160, 166, 168. Already strict and unchanged: semgrep `--error --strict`, zizmor `--strict-collection`, biome `--error-on-warnings`, jscpd `--threshold 0`, pyrefly `--min-severity info`, fallow scan `--fail-on-issues`, react-doctor `--blocking warning` (its maximum failing level), and the report validators, which already fail on any finding. Verified flags: `dart-decimate check --strict` ("Fail when any finding is reported, including warnings") works with `--boundary-violations` and with `--threshold 0 --format json`; `react-doctor --no-respect-inline-disables` works with `--json --json-out`; `fallow audit --gate all` fails on every finding in changed files where the default gates only new ones; fallow rejects `--baseline` on `audit`. The provisioned dart-decimate 0.0.44 produced identical results on three consecutive runs over a client Flutter monorepo (verdict pass, zero findings, 795 files), so a strict gate is not flaky.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for strict mode on dart-decimate, fallow, react-doctor and any other scanner, no violations in scaffolded repositories, no suppression, and repair of every finding committed before the rest of the work continues. Commit and PR need a separate go-ahead. Assumptions stated in the report: existing installs keep their gate commands (validation flags the audit gate; the report names the manual edits), and "no suppression" is enforced through tool flags plus the rule text, not a suppression-comment grep.

## Acceptance + steps

- [x] Dart template and `adapt_boundaries` emit `--strict`; the strict boundary command still has its project rules validated → updated pins in `tests/test_setup.py` and `tests/test_tool_execution.py`.
- [x] React Doctor gate carries `--no-respect-inline-disables` → updated scanner pin in `tests/test_tool_execution.py`.
- [x] `validate_scanner_command` rejects the tolerance flags before execution and requires `--strict`, the React Doctor flags and `--gate all` → red/green tests in `tests/test_tool_execution.py`; `tests/test_reports.py` fixture gains `--gate all`.
- [x] gates.md Exceptions row forbids baselines, tolerances, ignore lists and inline disables of findings; Baseline repair covers findings unrelated to the task and findings surfaced by a tool release; `AGENTS.md` Verification rule and `DECISION.md` state the rule.
- [x] Full check passes on the final tree.

## Baseline + execution

Result: Passed
Evidence: main at e45b0cd, CI run 35221637420 success; local full check on that tree earlier today passed with 745 tests. Rebased onto main c9d526a (CI run 35249775864 success) without conflicts before delivery.
Execution: Single session, sequential edits; validation code first, then templates, then docs.

## Risks + recovery

Installed projects keep their current gate commands, so a dart-decimate, React Doctor or fallow audit gate without the strict flags fails validation on the next check with a message naming the flag to add; the report validators already failed on any finding, so no previously passing repository gains findings from this change. Recovery is reverting the branch.

## ux_reference

N/A — hook, template and documentation changes.

## Verification

Result: Passed
Evidence: Red before the hook changes: `test_gate_rejects_disabled_fallow_metric_before_execution` failed at the new `add --gate all` expectation (DID NOT RAISE) with the tests updated and the hooks unmodified. Red for the new tests against the stashed hook files: the ten rejection cases failed with DID NOT RAISE and the four accepted commands passed. Green after: `tests/test_tool_execution.py`, `tests/test_setup.py`, `tests/test_reports.py` 258 passed, covering eleven rejected commands (a fallow scan without `--fail-on-issues` was added after review) (missing `--strict`, `--tolerance`, `--regression-baseline=`, `--fail-on-regression` behind `pnpm dlx`, React Doctor without the inline-disable flag or with `--blocking error` or no `--blocking`, fallow baseline flags on scan and audit, `fallow audit --gate new`) and four accepted strict commands, plus the updated scanner, boundary and delegated-fallow pins. Ruff format and check clean; `project_setup.py` 697 and `gate_config.py` 700 lines. Full check evidence is in the delivery line.
E2E: Passed — the provisioned dart-decimate 0.0.44 ran `check lib --threshold 0 --strict --format json` three times on a client Flutter monorepo with identical output (verdict pass, zero findings, 795 files), `dart-decimate check . --boundary-violations --strict` passed on the same tree earlier today, `react-doctor 0.9.14 --help` confirms `--blocking` defaults to error and documents `--no-respect-inline-disables`, and `fallow 3.27.0 audit --help` states that audit always analyses only changed files, that `--gate all` fails on every finding there, and that `--baseline` is rejected on audit; dart-decimate 0.0.43 rejects `--strict` as an unexpected argument, so the flag needs 0.0.44, which `npm:dart-decimate@latest` provisions.

Delivery target: PR
Delivery: Pending — full `hard-eng.py check --base origin/main` on the final tree passed: exit 0, 764 tests in 185 s, every native check passed. The first two runs failed on this repository's own gates (the test file exceeded 700 lines; the validator exceeded complexity 10) and were repaired by moving and compressing the tests and splitting the validator per tool.
