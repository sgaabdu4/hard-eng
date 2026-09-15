# Explain Hard Eng clearly to a new reader

Status: Complete

## Outcome + scope

Rewrite the README for a solo developer building with agents. Explain the alpha status, purpose, setup, components, security and enforcement, with Mermaid diagrams for human-led and autonomous work and meaningful setup/failure cases. Keep important technical details accessible through verified links.

## Repository context

README.md is the public entry point. Existing stage skills, gate configuration, installer and DECISION.md own the detailed behavior; describe and link to them without introducing another contract.

## Decisions + authorization

Blockers: None
The user requested the rewrite and diagrams. Reuse README.md and Mermaid's native Markdown support; no new dependency or runtime component. This small plan is required by the existing engineering workflow. Public documentation must contain no private project examples or identifiers.

## Baseline + execution

Result: Passed
Evidence: Main b77e811 passed the full source gate and hosted CI. Documentation claims will be checked against the current installer, hooks, skills and gate contracts.

## Acceptance + steps

- [x] A new reader can understand purpose, installation and the plan/build/ship flow.
- [x] Security and enforcement claims distinguish mechanical checks from agent and human judgment.
- [x] Diagrams render; links resolve; documentation remains concise and accurate.

## ux_reference

N/A — repository documentation, with rendered Mermaid verification.

## Risks + recovery

Documentation could overstate hook activation or security coverage. Verify each claim against executable owners and retain alpha limitations; inspect the rendered diagrams for readability.

## Verification

Result: Passed
Evidence: The official Mermaid CLI rendered all eight diagrams successfully; visual inspection led to vertical layouts for readable labels. All 31 local links resolve. Whitespace and public-text checks pass. The stack gate matrix was checked against required roles and report validators; a duplicated overview table was removed. Source runtime code is unchanged. Native pre-push and hosted CI remain required before delivery.
E2E: Passed — rendered and inspected all eight native Mermaid diagrams and verified documented commands and links against the repository.

Delivery target: Merge
Delivery: Pending
