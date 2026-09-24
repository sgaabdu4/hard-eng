# Keep test fixture manifests out of package discovery

Status: Complete

## Outcome + scope

Fixes #153. Package discovery skips a manifest under a test directory when it has no lockfile of its own and no enclosing workspace declares it, so setup generates no impossible standalone group for a fixture and `check` does not demand one. A fixture with its own lockfile, a declared workspace member, and every manifest outside test directories keep full package checks. Non-goals: ignoring all nested manifests or changing gate templates.

## Repository context

Owner: `package_manifests` in `.hooks/gate_config.py`, used by `setup.py:gate_config` to generate groups and by `validate_manifest_groups` to require them. `mcp_setup.marionette_server` already skips nonproduction `pubspec.yaml` files with `nonproduction_source`. Lockfiles per language match `dependency_command`: `pubspec.lock`, `pnpm-lock.yaml`, `uv.lock` or `poetry.lock`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix the open Hard Eng issues.

## Acceptance + steps

- [x] Lockfile-less `tests/fixtures/example/pubspec.yaml` → not discovered; with `pubspec.lock` or declared as a workspace member → discovered.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `b5a5d31` → 17/17 gates PASS, 802 tests passed.
Execution: One builder; filter at the single discovery owner.

## Risks + recovery

A real package under a test directory that relies on an unlisted lockfile location would lose its group; add its lockfile or declare it as a workspace member.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_package_discovery.py::test_fixture_manifest_ownership` passes; its first assertion fails on `b5a5d31`, which discovered the fixture. Synthetic repository with root `package.json` + `pnpm-lock.yaml` and lockfile-less `tests/fixtures/example/pubspec.yaml` → `setup.gate_config` generates only the root JavaScript group and `validate_manifest_groups` accepts it. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 803 tests passed.
E2E: N/A — discovery change; the focused test exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
