# Open Hard Eng issues 489, 528, 529

Status: Complete

## Outcome + scope

Fix three open issues; 469 needs no change. 528: the UI evidence check survives GitHub timing out its ranged request, and names the failing attachment. 529: the missing-evidence message names the upload command. 489: the efficiency guide shows the helper body that passes unused-parameter checks. 469: no code change. Checks stay on Bun; the project holds the broken plugin release with a freshness hold (`gates.md` freshness), which the gate rechecks within 14 days and for every newer release. Non-goals: running tools on Node, retry loops.

## Repository context

Owners: `.hooks/shipping.py` (`_check_attachment`), `.hooks/ship_evidence.py` (`attachment_urls`), `.agents/skills/he/references/efficiency.md`.
Evidence: on 2026-11-08 GitHub returned 504 for several release and attachment downloads while other requests returned 200. The checker already accepts `void reason;` and `void _reason;` bodies since 2026-11-05; only the guide was missing. Bun 1.4.4 is still the newest release and its undici fix PR is still open.
Same cause: N/A — separate reports.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer asked on 2026-11-08 to check the open issues and add their fixes to this PR.

## Acceptance + steps

- [x] A ranged request that fails falls back to a plain GET; a plain GET failure names the attachment → `tests/test_shipping_ui_evidence.py::test_ui_evidence_falls_back_to_a_plain_get_when_the_ranged_request_fails`.
- [x] Missing UI evidence names `gh pr edit … --attach` → `tests/test_shipping_ui_evidence.py::test_missing_ui_evidence_names_the_upload_command`.
- [x] The `void reason;` helper body passes the await-in-loop rule → `tests/test_hot_paths.py::test_exact_reported_inputs_keep_all_expected_findings`.

## Baseline + execution

Result: Passed
Evidence: develop 921d8ce8 passed required CI; this branch's earlier commit passed the full pre-push check on 2026-11-08.
Execution: This session, one builder, in the open staging PR at the maintainer's request.

## Risks + recovery

- A plain GET downloads the whole attachment once, only after the ranged request fails. Recovery: revert the commit.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: On 2026-11-08 `uv run pytest -q tests/test_shipping.py tests/test_tool_setup.py` and the evidence tests: 127 passed; the new tests failed before the fixes.
E2E: N/A — command-line checks with no user journey.
Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release; close the issues after release.
