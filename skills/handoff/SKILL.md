---
name: handoff
description: Write or resume a terse, complete session handoff so a fresh session continues with zero missing context.
disable-model-invocation: true
argument-hint: "What should the next session focus on?"
---

# Handoff

## Contract

- Owner file = `HANDOFF.md` at repository root; no repository → current working directory; one file + overwrite; handoff history forbidden.
- Content = observed session facts only; invention/padding forbidden; unknown = recorded `Unknown`.
- Secrets/credentials/tokens = excluded; record storage location pointer instead.
- Handoff = context for the next session; current user message wins on conflict.

## Route

| State | Action | Completion |
|---|---|---|
| Active session with work to transfer | Write per [template.md](references/template.md) | Every section filled or explicit `None` + fresh-reader validation PASS + path reported |
| Fresh session + `HANDOFF.md` exists | Resume per [resume.md](references/resume.md) | Verified state summary reported + first Next step started |
| Fresh session + no `HANDOFF.md` | Report absence → ask for path or scope | User answer |

## Write

- Timing = before close/compaction; sending session writes; reconstruction from memory forbidden.
- Scan = full conversation + git state + task/plan state + verification receipts + unanswered user asks.
- Arguments = next-session focus; tailor Goal + Next to it.
- Terse = fact-dense bullets; narrative/history prose forbidden.
- Artifact-backed fact (brief | plan | ADR | issue | PR | commit | diff | doc) = pointer + one-line gist; duplication forbidden.
- Conversation-only fact (user ask | correction | constraint | preference | finding) = inlined in full; it dies with the session.
- Fresh-reader validation = re-read written file; any bullet needing conversation access to act on → rewrite; conversation-only shorthand/pronouns forbidden.
