# Question format module

Use before asking any user-facing interview question.

## Delivery

- Default to the markdown `Visible question block`; `grill-me` choices need
  visible context.
- Do not use `request_user_input` for `grill-me` interview prompts that need
  `Meaning`, `Why it matters`, `Suggested default`, or `Options`. That rich
  context belongs in the markdown block.
- Use `request_user_input` only for simple, low-risk choices where a one-line
  question and short option labels are enough. One call, one question, 2-3
  exclusive options; recommended option first with `(Recommended)`.
- In a `request_user_input` call, the tool `question` string is only the short
  question. Options must be self-contained. Descriptions are optional and
  non-critical because the built-in UI may hide them.
- Omit `autoResolutionMs` for blocking/high-risk choices; use it only when a
  default can safely continue. Persist the exact markdown block or tool
  question/options before replying/calling.

## Visible question block

Visible format:

```text
Q<N>: <plain question>

Meaning: <what this decides; include one example if useful>
Why it matters: <what changes based on the answer>
Suggested default: <A/B/C> - <one clear reason>

Options:
A) <plain option>
B) <plain option>
C) <plain option or "Not sure - use the default">

Reply: A/B/C, "use default", "not sure", "skip for now", or your own answer.
```

## Rules

- Clarity beats terseness. Normal prompt target: 8-14 lines; max 160 words
- Markdown replies use one `text` code fence containing the plain question
  block; no prose outside it during interview.
- Before replying, persist the exact block in `session_state.md`
- Do not use box drawing, table borders, vertical bars, horizontal rules, or
  decorative lines.
- Use blank lines between sections; keep option lists compact
- Wrap lines around 72 chars
- Explain enough for a nontechnical reader to answer without guessing: plain
  meaning + why it matters + one concrete example when helpful. No essay.
- Use complete sentences in the visible card. Do not compress with terse
  abbreviations or arrow shorthand.
- Avoid jargon in visible prompts. Replace `success metric` with `main pass/fail
  check`; replace `MVP gate` with `what must work before real staff use it`.
- Do not show `Stage`, `Definitions`, `Acceptance criteria`,
  `Verification`, `Evidence`, or `Scenario` blocks in the visible prompt.
- Put definitions/evidence/acceptance criteria/verification/scenarios in the
  handoff/final plan only.
- Add `Details (optional)` only when needed; max 2 bullets
- Options must be directly selectable. Avoid multi-clause options
- If the user seems unsure, offer `Not sure - use the default`
- If the user says `all`, `both`, or `all important`, accept it when feasible;
  record all as required and move to the next concrete behavior. Do not force a
  primary ranking unless scope truly breaks.

## Example

```text
Q3: What must work before real staff try v1?

Meaning: Pick the test that decides "ready for real work";
other checks can still be required.
Why it matters: This tells us what to test first.
Suggested default: A - it proves the core flow works.

Options:
A) Task reaches the right person with deadline + notification.
B) Any age user can create/delegate without training.
C) Malayalam voice becomes usable English task text.

Reply: A/B/C, "all", "not sure", "skip for now", or edit it.
```

## Internal record

Keep this out of the visible prompt. Use it for handoff/final-plan synthesis
only when needed.

```md
Question ID: <N>
Question: <plain question>
Stage: <intake | product | ui-flow | visual-design | prototype-tech-stack | prototype | backend-tech-stack | vertical-slices | final>
User-facing prompt: <exact visible prompt>
Suggested default: <clear choice + why>
Internal details:
- Definitions: <term = meaning | n/a>
- Domain docs: <CONTEXT/ADR/glossary impact or conflict | n/a>
- Options: <A/B/C + tradeoffs>
- Evidence: <code/docs/user quote | unknown>
- Why: <dependency unlocked>
- Acceptance criteria: <happy/fail/edge pass/fail checks | unknown>
- Verification: <test/prototype/manual/rubric | unknown>
- Scenario: <edge case | n/a>
```

## Internal rules

- Never batch Qs
- Do not rely on chat memory for the last or next Q; use `session_state.md`
- Always list 2-3 directly selectable options in the visible prompt and
  internal record.
- If only one option works, visible option C is `Not sure - use the default`
  and internal notes explain why.
- In internal records, every `Suggested default:` starts with `Pick <option>` or
  `Use <choice>` and one clear reason.
- Define new/product/domain/tech terms in internal `Definitions`; expose only
  unavoidable definitions in `Details (optional)`.
- If domain docs matter, load `modules/domain-docs.md`; capture canonical terms,
  avoided synonyms, and ADR candidates internally, not in the visible prompt.
- Avoid vague words; name exact screen, entity, state, runtime, data source, or
  constraint.
