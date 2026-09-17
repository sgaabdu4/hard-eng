# Review and release skill packages

Status: Complete

## Outcome + scope

Review all 14 distributed skills against Writing Great Skills; correct proven documentation, routing and metadata defects, publish canonical Appwrite/Flutter patch releases and adopt their verified revisions. Preserve substantive rules; no new enforcement framework or unrelated stack migration.

## Repository context

Owners: `.agents/skills`, canonical `sgaabdu4/appwrite-backend` and `sgaabdu4/building-flutter-apps`, their existing release metadata, README and submodule pins.

## Decisions + authorization

Blockers: None
Authority: Autonomous corrections, Terra research/review, canonical version publication and Hard Eng main delivery are explicitly authorized.

## Acceptance + steps

- [x] All 14 packages reviewed for triggers, disclosure, ownership, references/resources and metadata; each important moved rule retains a reachable owner.
- [x] Incorrect installed commands, metadata and stale docs corrected at canonical owners; representative valid/invalid cases verified.
- [x] Changed skill behavior exercised through relevant agent cases; structural checks remain distinct from behavioral proof.
- [x] Canonical versions agree across existing release surfaces; tests and independent reviews pass before publication.
- [x] Hard Eng adopts published, verified canonical revisions; native checks and installation preserve the complete skill packages.

## Baseline + execution

Result: Passed
Evidence: Starting revision f186f2a; `uv run --no-project --with pyyaml python .hooks/hard-eng.py check --plan-stage Draft` passed all 17 checks, 739 tests and four performance cases.
Execution: Terra researched both canonical packages and independently reviewed all 12 other packages; coordinator owns integration and publication. Cross-review found no remaining substantive rule loss or unnecessary machinery.

### Package review coverage

| Skill | Review and preservation scope |
| --- | --- |
| appwrite-backend | Canonical scripts, all service/safety references, portable command and API examples; Terra owner. |
| building-flutter-apps | Canonical rule map, references, assets, hooks, metadata and existing evals; Terra owner. |
| code-review | Diff/base selection, independent challenge and shared test-quality owner. |
| codebase-design | Structure, UI and domain routes; preserve simple-CRUD/YAGNI boundaries. |
| e2e | Native journey, persistence, multi-actor, failed-proof and media boundaries. |
| he | All workflow, gate, efficiency, testing, integration routes and copied templates. |
| he-plan | Draft proposal vs Ready, UX, Wayfinder and conditional baseline recovery. |
| he-build | Authorized scope, shared-state isolation, integrated proof and Complete handoff. |
| he-ship | Native CLI contract, privacy, media attachment, remote proof and guarded cleanup. |
| he-learn | Recurrence proof, smallest prevention owner, ADR authority/retrieval and no-op route. |
| product-walkthrough-video | Recorder/review resources and output contract; generated guidance must distinguish WebM proof from MP4 delivery. |
| research | All five routes; source applicability, counterevidence and truthful unknowns. |
| security-review | Real enforcing boundaries, permission-preserving proof and limits of scan results. |
| writing-great-skills | Whole-package authoring guidance, invocation policies and validator compatibility. |

Preserved moves: HE Plan baseline-repair diagram/rules → existing HE gate reference; participation table/caveat → existing HE workflow reference. Content comparison confirms identical rules apart from rebased links. Entry routes remain direct, including HE Build/Ship recovery links.

## Risks + recovery

Moving guidance can hide a constraint or change task selection. Retain rule-to-owner mapping and exercise affected routes. Preserve existing implicit/explicit invocation policy and unrelated work. Host behavior and external service correctness remain separate proof boundaries.

## ux_reference

N/A — documentation, skill routing and metadata changes have no application UI.

## Verification

Result: Passed
Evidence: Focused installer/handoff checks: 18 passed. Appwrite: 59 native tests, Biome formatting and independent review passed; v2.1.4 published from merged revision 893da2a after green master CI. Flutter: full native quality gate passed (28 drift fixtures, 13 rules, 50 smoke checks, routing metadata, Markdown examples and upstream drift); independent review passed; v5.10.3 published from merged revision 1c82462 after green main Windows installer CI. Both released revisions are pinned in Hard Eng. The native video scaffold generates the two distinct output routes with strict configuration intact; an initial probe had an incorrect expected phrase and was corrected, with no script change needed. Final Terra audit of all 14 released packages: 111 Markdown files, 426 local links and 86 section anchors resolve; external URLs and fenced examples are excluded from these counts. All frontmatters and six optional Codex metadata files agree with their invocation policy. All 13 owned JavaScript resources and JSON templates parse. Canonical final checks passed; the integrated Complete gate is the final local release check.

Research: current [Codex skill metadata](https://developers.openai.com/codex/skills/), [Claude skill fields](https://code.claude.com/docs/en/skills), [Copilot skill fields](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), [GitHub attachment CLI](https://cli.github.com/manual/gh_pr_create) and [Playwright screencast](https://playwright.dev/docs/api/class-screencast) agree with retained contracts. Native GitHub CLI help independently confirms attachments. The bundled generic skill validator accepts 12 packages and rejects the supported `disable-model-invocation` extension on two; their boolean metadata and matching Codex policy were checked separately. No global validator or invocation policy was changed.
E2E: Passed — the real Appwrite guard accepted valid schema and rejected destructive omissions through documented commands in canonical and Hard Eng layouts, including spaced paths. The real installer preserved complete skill packages and project customizations. Native Terra probes kept unresolved proposal choices in Draft Approval, continued an approved Ready plan without re-asking, and blocked feature work until baseline repairs were delivered and a fresh baseline passed. Flutter routing cases 4, 7, 21, 38, 43, 44 and 45 matched their final expectations individually. The earlier full 45-case run scored 41/45: two prompts/routes needed clarification and two expectations were investigated; the deep-link expectation was restored after its output confirmed the original route, while the telemetry case was narrowed to its explicit scope. No final all-45 rerun or universal compliance claim; Flutter probe evidence is console output, not a persisted aggregate report.

Delivery target: Merge
Delivery: Pending — canonical [Appwrite v2.1.4](https://github.com/sgaabdu4/appwrite-backend/releases/tag/v2.1.4) and [Flutter v5.10.3](https://github.com/sgaabdu4/building-flutter-apps/releases/tag/v5.10.3) are published after passing merged CI. Hard Eng PR and verified main CI remain required.
