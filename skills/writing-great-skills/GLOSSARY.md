# Writing Great Skills Glossary

Definitions = runtime vocabulary for [writing-great-skills](SKILL.md).

## Objective

- **Predictability** = same process across runs; valid outputs may vary.
- **Branch** = one materially distinct way the skill is used.
- **Granularity** = where one skill ends + another begins.

## Invocation

- **Implicit invocation** = model may select the skill from its description.
- **Explicit-only invocation** = human selects `$skill`; Codex policy blocks implicit selection.
- **Description** = always-visible trigger contract: purpose + unique branch triggers.
- **Context load** = tokens + attention spent on always-visible skill metadata.
- **Cognitive load** = skills + trigger conditions the human must remember.
- **Router skill** = one explicit skill mapping needs → other explicit skills.
- **Leading concept** = pretrained word/idea anchoring invocation + execution with few tokens.

## Information Hierarchy

- **Step** = ordered action ending on a completion criterion.
- **Reference** = knowledge consulted by some, not all, valid invocations.
- **Context pointer** = branch condition + target for loading disclosed material.
- **Information hierarchy** = step → inline universal reference → disclosed conditional reference.
- **Progressive disclosure** = move branch-specific reference behind a precise pointer.
- **Co-location** = definition + rules + caveats under one owner.
- **Resource** = script + reference + asset used by the skill.

## Steering

- **Completion criterion** = observable boundary separating complete from partial.
- **Legwork** = investigation/execution required inside a criterion.
- **Post-completion steps** = later actions visible while the current action is unfinished.
- **Premature completion** = fuzzy criterion + later-step pull → current action ends early.
- **Positive steering** = state the target action; hard prohibition → pair with replacement action.
- **Sequence split** = context boundary hiding later steps after sharper criteria fail.

## Pruning

- **SSOT** = one authoritative owner per meaning.
- **Duplication** = one meaning with multiple owners.
- **Relevance** = line still affects the skill's current job.
- **No-op** = instruction does not change model behavior.
- **Sediment** = stale content retained because deletion feels risky.
- **Sprawl** = live but excessive content weakening attention.
- **Context pointer failure** = required material exists but pointer does not reliably load it.

## Tests

- **No-op test** = remove line → behavior unchanged ⇒ delete line.
- **Branch test** = same actions + same proof ⇒ merge branches.
- **Disclosure test** = name one valid run that skips each reference; none ⇒ inline/delete.
- **Split test** = no independent trigger + no observed rush ⇒ keep together.
- **Predictability test** = representative prompts follow intended branch + gates repeatedly.
