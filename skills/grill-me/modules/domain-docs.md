# Domain docs module

Load for code/doc-backed grilling, fuzzy terms, ADR candidates/conflicts, or
final synthesis touching docs.

## Read pass

- If repo/docs exploration is already needed, silently check for
  `CONTEXT-MAP.md`, `CONTEXT.md`, relevant `docs/adr/`, and context-local ADRs
  near the touched area. Missing docs are not a blocker; do not ask to create
  them up front.
- Treat `plan.md`, decision docs, PRDs, and open-question docs as evidence; do
  not re-ask answered product/domain Qs.
- Docs close only covered stages. "No remaining product questions" accepts
  product plan only unless screen flow/look + review status are documented.
- Use glossary vocabulary in questions, plans, titles, tests, and artifacts
  Respect `_Avoid_` synonyms.
- If user claims, code, glossary, or ADRs conflict, surface the conflict with
  evidence. Ask one Q only when the conflict blocks the next decision.

## Active refinement

- Treat fuzzy terms as product/code risk. Capture the canonical term, tight
  definition, avoided synonyms, and boundary.
- Use confirmed terms in code, tests, issues, and plans
- Stress relationships with scenarios: cardinality, lifecycle, empty state,
  delete/archive, ownership, permissions, and handoff.
- Cross-check user statements against code/docs before asking for evidence
- For naming, ownership, lifecycle, permission, data, or migration decisions,
  classify as glossary, ADR candidate, or both.

## Capture

During interview, do not edit `CONTEXT.md` or ADRs unless asked. Record terms
and ADR candidates in the active state, draft, handoff, or final plan.

Use this compact format:

```md
Domain term: <Term> - <tight project-specific meaning>
Avoid: <synonyms to avoid | none>
ADR: <title> - hard to reverse: <yes/no>; surprising: <yes/no>;
tradeoff: <yes/no>; decision: <decision>
```

## Synthesis

- `CONTEXT.md` is a glossary only. Keep definitions tight and free of
  implementation decisions.
- Write or update glossary terms only when confirmed by the user or evidence
- Offer/create an ADR only when all are true: hard to reverse, surprising
  without context, and a real tradeoff.
- Keep ADRs short: title plus one to three sentences of context, decision, and
  reason. Add options/consequences only when useful.
- Use confirmed terms in PRDs, issues, tests, and plans
