# Human Writing Guide

Use this when creating or editing text meant to be read outside the chat: GitHub issues, PR descriptions, docs, COO/executive notes, specs, emails, release notes, user-facing copy, rewrites, and long explanations.

## Goal

Write like a clear human operator: direct, specific, calm, and compact. Terse still applies, but readability beats compression.

Do not run a full visible draft/audit/final loop unless the user asks for it. Usually do a quiet compact pass and return the final.

## Voice

- Match the audience
- For technical docs, be plain and exact
- For executive notes, lead with decision, risk, impact, and next action
- For GitHub issues, state problem, evidence, expected behavior, actual behavior, scope, and acceptance criteria
- For user-facing copy, use ordinary words and avoid internal implementation detail
- If the user provides a writing sample, match its sentence length, word choice, paragraph starts, punctuation, and transitions
- Add personality only for opinion, blog, personal, or persuasive writing. Keep technical, legal, reference, and executive writing plain

## Compact Humanizer Pass

Scan for clusters of these tells, not one-off false positives. Fix what improves clarity or voice.

- Hard blockers in final artifacts: remove these even when they appear once:
  - "not just X, but Y", "not only X, but also Y", and "more than just X". Rewrite as a direct claim: "X does Y" or "X also does Y"
  - Grand contrast frames such as "AI is not merely a tool" or "this is not about X, it is about Y". Say the plain point directly
  - Client-facing claims that sound impressive but do not explain the operating mechanism. Replace them with "how it works" plus the concrete evidence

- Inflated significance: "pivotal", "testament", "underscores", "broader landscape", "sets the stage"
- Promotional tone: "boasts", "vibrant", "rich", "breathtaking", "renowned", "must-visit", "groundbreaking"
- Fake-depth -ing clauses: "highlighting", "underscoring", "showcasing", "reflecting", "fostering", "ensuring"
- Vague attribution: "experts say", "industry reports", "observers note", "some critics argue" without a named source
- Formula sections: generic "Challenges", "Future Outlook", or upbeat conclusions that add no fact
- AI vocabulary piles: "additionally", "align with", "crucial", "delve", "enhance", "interplay", "key", "landscape", "valuable"
- Copula avoidance: replace "serves as", "stands as", "features", "offers" with "is", "has", or a specific verb
- Negative parallelism: avoid "not just X, but Y" and clipped endings like "no guessing"
- Rule of three padding: do not force three items when one or two are enough
- Synonym cycling: keep one clear term instead of rotating labels
- False ranges: avoid "from X to Y" unless X and Y are a real scale
- Passive voice: use active voice when it makes the actor clearer
- Em/en dashes: avoid in final artifacts. Use a period, comma, colon, or parentheses
- Bold-label lists: avoid bold labels on every bullet unless the format truly needs them
- Title-case headings: prefer sentence case for docs and notes
- Emojis: omit unless the target voice uses them
- Curly quotes: use straight quotes unless the target format requires curly quotes
- Chatbot residue: remove "of course", "great question", "here is", "I hope this helps", "let me know"
- Cutoff/speculation: do not write around missing info. Say "unknown" briefly or omit
- Sycophancy: acknowledge the point without praise
- Filler/hedging: replace "in order to", "due to the fact that", "at this point in time", "it is important to note", "could potentially possibly"
- Generic positive endings: end on a fact, decision, risk, or next action
- Hyphenation: keep attributive compounds when useful, but drop predicate hyphens where natural
- Persuasive tropes: avoid "the real question", "at its core", "what really matters", "the heart of the matter"
- Signposting: skip "let's dive in", "let's break this down", "here's what you need to know"
- Fragmented headers: do not add a one-line warmup that repeats the heading
- Diff-anchored prose: durable docs describe the current system, not what changed in the last commit

Before returning any paste-ready artifact, do a literal final scan for: `not just`, `not only`, `more than just`, `not merely`, `serves as`, `stands as`, `leverage`, `delve`, `pivotal`, `seamless`, `robust`, and `groundbreaking`. Rewrite matches unless they are quoted source text.

## Preserve

- Specific details, real quotes, dates, paths, examples, and odd-but-true facts
- Mixed feelings or uncertainty when the source actually has them
- The user's voice, including casual wording, sentence rhythm, and defensible quirks
- Neutral plainness for technical, legal, reference, and executive writing

## Full Rewrite Mode

Use only when the user asks to humanize, rewrite, or audit text:

1. Preserve meaning and coverage.
2. Match the target voice or the user's sample.
3. Quietly check "what still sounds AI-generated?"
4. Return the final rewrite, plus a short change note if useful.
