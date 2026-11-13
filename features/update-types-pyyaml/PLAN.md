# Update types-pyyaml to clear the freshness gate

Status: Complete

## Outcome + scope

The dev dependency `types-pyyaml` moves to 6.0.12.20261111, so the `freshness` gate passes again. Non-goals: other dependencies, code changes.

## Repository context

Owners: `pyproject.toml` dev group and `uv.lock`; the `freshness` gate named the command `uv add --group dev 'types-pyyaml>=6.0.12.20261111'`.
Same cause: N/A — a new upstream release passed the 2-day minimum release age; no other direct dependency is outdated. The update of 1 November to 6.0.12.20261030 used this same plan.
Single source: N/A — the floor has one owner, the dev group of `pyproject.toml`; `uv.lock` is generated from it.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. Baseline repair: the gate blocks the delivery check of a merged repair and the release that the maintainer asked for.

## Acceptance + steps

- [x] `freshness` reports no outdated direct dependency → N/A — no test can prove an upstream release; the command of the `freshness` gate passed on this branch.
- [x] Type checks still pass with the new stubs → N/A — the `types` gate is the proof; its command passed on this branch.

## Baseline + execution

Result: Passed
Evidence: develop 52923585: the checks job of the newest Hard Eng CI run failed only `freshness`, for this release; its 18 other gates passed. The Hard Eng CI run for the push of that commit passed.
Execution: One builder, this session.

## Risks + recovery

N/A — type stubs only; no runtime code uses them.

## ux_reference

N/A — dependency only; no visible UI.

## Verification

Result: Passed
Evidence: on this branch the command of the `freshness` gate reported no outdated direct dependency (exit 0), and the command of the `types` gate reported 0 diagnostics (exit 0). The lock file changed for this one package only.
E2E: N/A — no user journey changes.
Retro: (1) The push refused the change without a plan, because a change of `pyproject.toml` always needs one → None — the refusal named the step, and this plan is reused for each new release of the package. (2) An upstream release failed the gate on the base branch → None — outside cause; the gate worked as designed.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
