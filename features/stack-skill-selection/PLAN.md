# Install stack skills only where the stack is used

Status: Complete

## Outcome + scope

Setup installs `appwrite-backend` only when the project imports Appwrite, and `building-flutter-apps` only when it has Dart/Flutter code. Every other skill stays universal. Updates delete an unedited copy of a stack skill the project does not use, remove its `.claude/skills` link, and refuse to delete an edited copy. Folders emptied by an update deletion are removed, and a rejected update commit restores them. A project that later adopts the stack receives the skill on its next update. README states the rule. Non-goals: new detection rules, per-project skill configuration, rewording distributed guidance.

## Repository context

Owners: `setup.py` (`scaffold_changes`, `prepare_skill_links`), `.hooks/update.py` (`update_plan`), existing detection `agent_hooks.integrated_services`; tests in `tests/test_setup.py` and `tests/test_updates.py`. Evidence: a Flutter package without Appwrite received the full Appwrite skill (39 files) when migrating to current Hard Eng, because every skill directory was copied and linked unconditionally, and updates only removed skills deleted from the source.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to implement and test this; commit and delivery need separate approval.

## Acceptance + steps

- [x] Fresh install into a project without Appwrite or Dart → neither stack skill copied nor linked; universal skills installed → updated install test passes.
- [x] Fresh install into a project importing Appwrite → Appwrite skill linked, Flutter skill absent; fresh Dart install → Flutter skill linked, Appwrite skill absent → extended tests pass.
- [x] Update of an installation carrying an unedited unused stack skill → its files, folders and link deleted in the update commit; a rejected commit restores them → new test passes.
- [x] Update with an edited copy of an unused stack skill → refused, edit preserved, revision unchanged → new test passes.
- [x] Sandbox update of a real consumer installation from a local stand-in release → project checks pass and only the unused Appwrite skill and its link are removed.
- [x] Sandbox fresh install of a project without Appwrite, then an update after it imports Appwrite → skill absent, then added with its link.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `dcda0bb` + this plan → 16/17 gates PASS; `tests` failed only `test_native_dart_declarations_and_runtime_controls`, which passes alone (63 s). The host load average was 120–200 on 16 cores from other processes; with the parser timeout temporarily raised the test took 445 s and the whole suite passed (799). Unrelated to this change.
Execution: One builder.

## Risks + recovery

A project that starts using a stack between Hard Eng releases gets its skill only at the next release. Distributed guidance links to stack skills (`he/references/integrations.md` Appwrite row, `he-plan` new Flutter app line) resolve exactly when the stack is present. `scaffold_files` stays unfiltered so scaffold-only update detection still recognises deletion commits.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: New/extended assertions in `tests/test_setup.py` (pnpm install omits both stack skills; Dart install links the Flutter skill only), `tests/test_mcp_setup.py` (Appwrite import installs the Appwrite skill and its MCP guide, not the Flutter skill) and `tests/test_updates.py::test_update_removes_unused_stack_skill_unless_edited` (unedited copy: update commit deletes exactly the installed files and link; edited copy: `Local scaffold edit` refusal, edit and revision kept) all pass, and all five fail with detection forced off. The folder assertion fails without pruning; the rejected-commit case fails without the rollback folder restore. Dry `update_plan` of a real installed Flutter package without Appwrite: 38 Appwrite files + its link removed, no Flutter skill path touched; the only other planned files match the unchanged updater's plan plus the new `update.py` and marker.
Sandbox: the real `update.update` against a clone of an installed Flutter package, with the release lookup pointed at a local stand-in upstream, ran all its project checks and committed deletion of the 38 Appwrite files and link; `.agents/skills` then held no `appwrite-backend` folder and kept `building-flutter-apps`. (An earlier run under host load 100+ refused the update when the project's stream timing check failed; that check passes alone in 3 s.) A fresh install into a new Python project omitted both stack skills; after the project imported Appwrite, the next update committed the Appwrite skill and link.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` at host load ~18 → exit 0, 17/17 PASS, 800 tests passed (including the Dart parser test that timed out under load).
E2E: N/A — installer/updater transformation; proof is fixture tests, the sandbox runs and the gate.

Delivery target: Merge
Delivery: Pending — needs user approval.
