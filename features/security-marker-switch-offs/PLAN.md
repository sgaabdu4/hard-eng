# Security marker switch-offs

Status: Complete

## Outcome + scope

`check` fails a change that adds a Semgrep or Gitleaks inline ignore marker in any file, or an entry in `.gitleaksignore` or `.semgrepignore`, because each hides a security scanner finding. Non-goals: markers of scanners Hard Eng does not run (`nosec`), and other tools' ignore files.

## Repository context

Owners: `validate_suppressions` in `.hooks/comments.py` owns HE-NO-SWITCH-OFF; its rule text lives in `.agents/skills/he/references/requirements.md`. `DIRECTIVE` allowed both markers as comments, and no `*_OFF` pattern matched them; files outside five languages were never scanned. Semgrep honors its inline marker, and Gitleaks honors its marker in every file. Setup writes `.semgrepignore` with a comment line only, which stays allowed.
Same cause: one cause, the switch-off scan covered only language suppressions; the new scan covers every changed file for the two security scanners.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, gate bugs first, with every decision made by the agent. Decided: leave out `nosec`, because no Hard Eng gate honors it.

## Acceptance + steps

- [x] An added marker or ignore entry fails and names file, line and text → `tests/test_comments.py::test_added_switch_off_fails_naming_file_line_and_pattern`.
- [x] A marker that was already there is not flagged → `tests/test_comments.py::test_switch_off_already_in_the_project_is_not_flagged`.
- [x] Ignore-file comments and ordinary words pass → `tests/test_comments.py::test_scaffold_paths_and_ordinary_words_are_not_flagged`.

## Baseline + execution

Result: Passed
Evidence: `develop` 648a210: the six new marker rows failed, because `check` accepted them; the full suite had only the 8 known environment failures.
Execution: One builder; failing rows, then the scan.

## Risks + recovery

A project that adds a real `.semgrepignore` path entry now fails `check`; recovery is to fix the finding or narrow the rule in the Semgrep config, which the reviewer sees.

## ux_reference

N/A — gate change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1813 passed, the same 8 environment failures as `develop`; `tests/test_comments.py` 151 passed. Ruff format and lint, Pyrefly (0 errors), Vulture, jscpd (0 clones) and deptry pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the tests run the real check against real Git repositories.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
