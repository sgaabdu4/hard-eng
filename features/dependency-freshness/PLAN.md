# Fail when a direct dependency misses a two-day-old release

Status: Complete

## Outcome + scope

A new `freshness` gate fails when a direct dependency (dev included) is older than its newest stable release published at least two days ago. Covers Bun, Dart/Flutter pub, uv and Poetry. Non-goals: Swift (no native listing; Xcode projects only), transitive dependencies, automatic upgrades.

## Repository context

Owners: gate roles and per-language templates in `.agents/skills/he/templates/hard-eng.*.json` and `.hooks/basic_mode.py`; role checks in `.hooks/gate_config.py` (`require_roles`, `selected_services`); scanner mapping and run loop in `.hooks/hard-eng.py` (`gate_scanner`, `run_limited_gate`); report parsers in `.hooks/reports.py`; gate docs in `.agents/skills/he/references/gates.md`. Issue: sgaabdu4/hard-eng#403 (asked 7 days; user set 2 on 2026-10-26 to match `features/tool-release-age/PLAN.md`).
Tool facts (verified 2026-10-26):
- Bun 1.4.3: `bun outdated --minimum-release-age=172800` (`-r` for workspaces) applies the wait itself; table output only; exit 0 when outdated. The flag beats a longer bunfig value. A row with `*` and Latest = Current is up to date.
- Dart 3.13.4: `dart pub outdated --json` has no wait; filter `kind` direct/dev; dates from `https://pub.dev/api/packages/<name>` `versions[].published`, skip retracted. Exit 69 when offline.
- uv 0.12.19: `uv tree --frozen --outdated --depth 1`; the CLI wait rewrites or ignores `uv.lock`, so dates come from PyPI `upload_time_iso_8601`. `--offline` passes silently, so never use it.
- Poetry 2.5.1: `POETRY_SOLVER_MIN_RELEASE_AGE=2 poetry show --outdated --top-level --format json` applies the wait itself.
- Every tool's "latest" ignores the declared range (new majors count) and skips prereleases. Exit codes never signal "outdated", so the gate parses output.
- No installed tool reports outdated packages (OSV-Scanner `update` lacks npm and PyPI).
Same cause: N/A — new check; no earlier fix.

## Decisions + authorization

Decided 2026-10-26: a broken release gets a hold in the gate file naming package, skipped version, reason and an end date at most 14 days away; it fails again after that date.
Decided 2026-10-26: two PRs. The "Update Hard Eng" PR never runs `freshness`, so it still merges by itself. Old dependencies found by any other check follow the existing [baseline repair](../../.agents/skills/he/references/gates.md#baseline-repair): a separate "Upgrade dependencies" PR merges first, then task branches rebase. The existing open-PR overlap rule in `workflow.md` already orders them; no new rule text.
Blockers: None.
Defaults (no question): new majors count; registry unreachable fails the gate; not part of `check --quick`.
Handoff: Approval
Authority: User asked on 2026-10-26 to plan #403 with a two-day window. Build waits for the user's go.

## Acceptance + steps

- [x] Bun: a direct dependency behind a release over two days old fails; only a newer release under two days passes → `tests/test_freshness.py::test_bun_fails_on_release_older_than_two_days`.
- [x] Dart: direct and dev dependencies judged on pub.dev dates; transitive and retracted versions ignored → `tests/test_freshness.py::test_dart_uses_pub_dates_for_direct_dependencies`.
- [x] uv: a direct dependency judged on PyPI upload dates → `tests/test_freshness.py::test_uv_uses_pypi_upload_dates`.
- [x] Poetry: output read with the two-day wait set → `tests/test_freshness.py::test_poetry_reads_outdated_with_wait`.
- [x] Registry failure or unreadable output fails with the tool's message → `tests/test_freshness.py::test_unreachable_registry_fails`.
- [x] A hold passes until its end date, then fails; a hold over 14 days or without a reason is rejected → `tests/test_freshness.py::test_hold_expires_and_needs_reason`.
- [x] A failure names the baseline-repair route and the native upgrade command → `tests/test_freshness.py::test_failure_names_upgrade_route`.
- [x] The Bun, Dart and Python templates carry the `freshness` role (basic mode reads no supported lockfile); a group without it is rejected → `tests/test_freshness.py::test_groups_require_freshness_role`.
- [x] An update PR that adds the gate to a project with old dependencies still passes → `tests/test_updates.py::test_update_pr_skips_freshness`.
- [x] A new web project starts on releases the check accepts, OpenNext's Next.js included → `tests/test_new_project.py::test_opennext_upgrades_next_like_every_other_package`.
- [x] Existing gates unchanged → N/A — no single test; the full `check --plan-stage Complete --base origin/main` passed.

## Baseline + execution

Result: Passed
Evidence: Reused the passed `hard-eng.yml` CI run 40073616726 on main at c567397f (`gh run list -b main --workflow hard-eng.yml`; conclusion success). Branch adds only Markdown before the build.
Execution: One builder (Sonnet), one slice per ecosystem in the order Bun, Dart, uv, Poetry; then a fresh reviewer (`challenge`).

## Risks + recovery

- Gate needs network in pre-push and CI. Offline push fails; recovery is to rerun online.
- The gate is time-based: an unchanged branch turns red once a release passes two days. Accepted by design.
- Registry APIs change shape. Parsers fail closed with the raw message.
- Dart dates come only from pub.dev, so a private pub server fails closed. Recovery: a hold, then extend the lookup when a project needs it.
- A branch that holds a verified Hard Eng update skips the check, even with other work in it. Task branches rebase after the update merges, so the skip ends there.

## ux_reference

N/A — command-line gate only; no visible UI.

## Verification

Result: Passed
Evidence: Focused runs pass: tests/test_freshness.py 14 passed; tests/test_setup.py + test_updates.py + test_verified_release.py + test_deployment_and_shell_gates.py + test_freshness.py 145 passed; test_package_discovery, test_basic_mode, test_adoption, test_affected_selection, test_ci_setup, test_swift, test_runner, test_quick_check, test_debt all pass. Local ruff, pyrefly, vulture, jscpd, deptry and semgrep on the changed files clean. Real smoke: uv and Dart outdated output checked against live PyPI and pub.dev. Review fixes: pub rows with no newer version are not looked up (test fails without the fix); uv hint raises lower bounds, since uv has no @latest. First full gate failed: 18 older tests built packages without the new role (fixed). New-project scaffolds checked in a scratch folder: Flutter had no old direct dependency; Next.js and Vite did, and `bun update --latest` already fixes them; OpenNext's pinned Next.js 16.4.1 did not, and 16.4.3 builds and serves HTTP 200 on its Worker, so the pin is gone. Full gate `check --plan-stage Complete --base origin/main`: 20 gates passed, tests 1954 passed, freshness passed on Hard Eng's own uv dependencies. Independent review (codex), round 1 at c7ba65af: Python post releases ignored, uv groups outside the defaults skipped, and two languages sharing a folder got one command and one report file; all three reproduced by a failing test, then fixed. Round 2 at cf53a862: that fix dropped workspace roots without a language field; reproduced and fixed.
E2E: N/A — gate behavior has no user journey; recorded registry responses prove each branch.
Delivery target: Merge
Delivery: Pending — main CI passes with the new gate.
