# Skill reference files stay under the Codex tool output cut

Status: Complete

## Outcome + scope

A test fails any reference document in a Hard Eng skill that is over 36,000 bytes, and `he/references/gates.md` (39,476 bytes) is split so that it passes. Non-goals: no new rule text for agents, no exception list, no size rule for non-Markdown files or for skills that a submodule owns.

## Repository context

Owners: `tests/test_skill_links.py` (`size_failures`), `.agents/skills/he/references/gates.md`, new `.agents/skills/he/references/plan-checks.md`, and its route in `.agents/skills/he/SKILL.md`.
Evidence: Codex 0.166 session logs on the maintainer's machine show single tool outputs cut near 40,000 bytes, with a `tokens truncated` marker in place of the middle. A reference repository measured the same cut on the same Codex version and holds its skill files to 36,000 bytes. `gates.md` was the only Hard Eng reference document over that size. The plan, build and ship skills link only its `Plan checks` and `Baseline repair` sections, which are about 7,100 bytes together with the `E2E:` rule they depend on.
Same cause: the 8,000-byte `SKILL.md` limit in the same test (`SKILL_BYTES`) covers the other Codex cut. Searched all Markdown files under `.agents/skills` by size; no other file in a Hard Eng owned skill is over 36,000 bytes.
Single source: the size limits have one owner, `tests/test_skill_links.py`. The moved sections have one owner, `plan-checks.md`; `gates.md` keeps no copy. Searched `.agents/skills`, `.hooks`, `tests`, `README.md` and `AGENTS.md` for `gates.md#plan-checks` and `gates.md#baseline-repair`; every link now points to the new file.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous weekly reference review. The maintainer asked for adapt items as small PRs into `develop` with merge and release, and on 2026-11-09 said to skip the Codex adversarial review for this item while Codex is at its usage limit.

## Acceptance + steps

- [x] A reference document over 36,000 bytes in a Hard Eng owned skill fails; one at the limit and one in a submodule skill pass → `tests/test_skill_links.py::test_an_oversized_reference_fails_unless_a_submodule_owns_it`.
- [x] Every distributed skill document is inside its limit after the split → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.
- [x] Every link to the moved sections resolves to the new file → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

## Baseline + execution

Result: Passed
Evidence: On 2026-11-09 `python3 .hooks/hard-eng.py check` on develop 2218082d passed every check; the test stage reported 2363 passed.
Execution: This session, one builder. First slice: the guard test, which fails on `gates.md` before the split.

## Risks + recovery

- An installed project keeps old links to `gates.md#plan-checks` in its own plans. Those links are in project files that the update does not own; the section text is in the same folder. Recovery: revert the commit.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: On 2026-11-09 the guard test failed first with `he: references/gates.md has 39476 bytes; Codex may cut it at 36000`. After the split `uv run --with pytest pytest -q tests/test_skill_links.py` reported 10 passed; `gates.md` is 32,434 bytes and `plan-checks.md` is 7,098 bytes. A reader that did not write the change compared old and new text: the moved text is word for word the same. Limit: no Codex session read the split files, because Codex was at its usage limit; the Codex adversarial review was skipped at the maintainer's request.
E2E: N/A — a size test and a document split with no user journey.
Retro: A reader found the `E2E:` rule left in `gates.md` with no user there, and no route to the new file → fixed in this change; prevention is the existing Reader step in `.agents/skills/writing-great-skills/SKILL.md`, which found both. The first Complete check failed lint on an unwrapped two-part string in the new test → wrapped; prevention is HE Build's focused checks step, which this build skipped for lint.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release to `main`.
