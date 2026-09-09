# Workflow

## Preconditions

- Explicit invocation = present.
- Active model family = known.
- Repository/provider data clearance = confirmed.
- Current CLI/model contract = `research` PASS when the recorded evidence is stale or the installed CLI changed.
- Prepared artifact = stable enough to challenge; reviewer must not invent missing implementation.

## Packet

- Format = JSON or terse Markdown.
- Include:
  - accepted outcome + user-visible behavior;
  - exact plan | diagnosis | diff | revision | proof under review;
  - constraints + exclusions + repository rules;
  - affected owners + callers + data/state transitions;
  - tests run + exact results + untested surfaces;
  - known risks + unknowns.
- Exclude:
  - secrets + regulated/customer data;
  - generator identity;
  - prior review verdicts + proposed rebuttals;
  - unrelated repository history.
- Evidence target = enough surrounding context to disprove claims, not a pasted whole repository.

## Challenge

- Reconstruct intended outcome before judging the proposed work.
- Try to prove each material claim wrong.
- Inspect neighboring repository context when needed.
- Check:
  - wrong requirement + hidden product decision;
  - wrong root cause + competing explanation;
  - wrong owner + missed caller/schema/route/config;
  - boundary/state/order/concurrency/retry/rollback failure;
  - auth/security/privacy/data-loss exposure;
  - weak or circular test + missing red-capable regression;
  - release/deploy/observability gap;
  - simpler existing owner or capability.
- Reject:
  - style preference + naming nit with no consequence;
  - duplicated finding;
  - claim without exact evidence or a named verification step;
  - confidence presented as fact.

## Severity

| Severity | Meaning |
|---|---|
| `Critical` | Security/data loss or the proposed work cannot deliver the accepted outcome |
| `Medium` | Material behavior, correctness, test, or delivery gap that should block build/ship |
| `Low` | Real bounded weakness with limited impact |
| `Info` | Useful observation with no required change |

## Adjudicate

For every reviewer finding:

1. Open cited files + inspect the actual owner/caller.
2. Reproduce or run the cheapest discriminating check when possible.
3. Verify current external contracts from primary sources when the claim depends on them.
4. Mark:
   - `Verified` = evidence proves the failure and impact;
   - `Rejected` = evidence disproves it;
   - `Unknown` = exact missing evidence + next check + owner.
5. Fold only verified gaps into the plan/change.

## Report

- Findings first, highest severity first.
- Each finding = title + severity + evidence + failure scenario + impact + verification + adjudication.
- Coverage = one verdict per named review area.
- No findings = say none; do not invent balance.
- Final status:
  - `FAIL` = verified Critical;
  - `CONCERNS` = verified Medium or material Unknown;
  - `PASS` = no verified Critical/Medium + coverage complete.

## External Contracts

- Claude CLI controls = [CLI reference](https://code.claude.com/docs/en/cli-reference).
- Fable effort + data handling = [effort](https://platform.claude.com/docs/en/build-with-claude/effort) + [Fable 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5).
- Codex controls = [developer commands](https://learn.chatgpt.com/docs/developer-commands#codex-exec) + [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) + [security](https://learn.chatgpt.com/docs/agent-approvals-security).
- GPT-5.6 Sol effort = [model reference](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
- Review method = [Google review guidance](https://google.github.io/eng-practices/review/reviewer/looking-for.html) + [OpenAI CriticGPT](https://openai.com/index/finding-gpt4s-mistakes-with-gpt-4/).
