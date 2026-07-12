# Teach Workflow

## Workspace Files

- `MISSION.md`: why the topic matters; use `MISSION-FORMAT.md`
- `RESOURCES.md`: trusted resources; use `RESOURCES-FORMAT.md`
- `learning-records/*.md`: durable insights; use `LEARNING-RECORD-FORMAT.md`
- `lessons/*.html`: self-contained lesson artifacts
- `reference/*.html`: compressed quick-reference artifacts
- `assets/*`: reusable lesson components
- `NOTES.md`: user preferences and working notes

## Mission

Every lesson ties back to `MISSION.md`.

If the mission is missing or unclear, ask why the user wants to learn the topic before writing lessons.

Confirm before changing the mission, then add a learning record for the change.

## Knowledge

Gather knowledge from trusted resources first. Use `RESOURCES.md` to track sources and cite claims in lessons.

Prefer primary sources, recognized experts, peer-reviewed work, and strongly
moderated communities. Do not rely on parametric memory alone. Annotate why
each source is useful, record genuine gaps, and prune sources that prove wrong,
shallow, or off-mission.

Keep knowledge limited to what the target skill needs. For knowledge acquisition, reduce difficulty so working memory goes to understanding.

## Skill Practice

Use difficulty deliberately for skill acquisition:

- retrieval practice
- spacing
- interleaving for related skills
- tight feedback loops
- quizzes or real-world actions when useful

For quizzes, avoid answer-shape clues. Keep options comparable in length where possible.

Separate momentary fluency from durable storage strength. A correct answer in
the moment is not mastery; revisit important knowledge through spaced,
effortful retrieval and varied application.

## Zone Of Proximal Development

If the user names an exact lesson target, teach that target. Otherwise infer the next useful lesson from:

- `MISSION.md`
- existing `learning-records/`
- user preferences in `NOTES.md`
- gaps in trusted resources

The lesson should feel challenging enough without overwhelming the learner.

## Lessons

Each lesson is one short HTML file under `lessons/`, named `0001-<dash-case-name>.html`.

A lesson should:

- teach one tightly scoped thing
- give the user one tangible win
- cite a primary source
- link to related lessons and references
- invite follow-up questions
- use existing `assets/` first

Lessons must be accessible, clean, readable, and print-friendly, with restrained
typography and enough whitespace for quick review. Link lessons and reference
documents with ordinary HTML anchors. Open the finished lesson for the user
when the environment supports it.

Open the lesson file when useful.

## Assets

Reusable CSS, quiz widgets, simulators, and diagram helpers live in `assets/`.

Create a shared stylesheet early. Add new components only when a later lesson can reuse them.

Reuse is the default: do not inline a stylesheet, quiz, simulator, or diagram
helper that belongs in the shared component library.

## References

Create reference documents when a lesson produces durable compressed knowledge:

- syntax and code snippets
- algorithms and flowcharts
- poses, exercises, routines, or processes
- glossaries

Once a glossary exists, use its vocabulary in future lessons.

Reference documents are the compressed artifacts the learner should revisit;
lessons may be transient. Keep glossaries opinionated, concise, and updated as
understanding changes.

## Wisdom

For questions that need real-world judgment, answer as far as evidence allows and recommend high-reputation communities, classes, forums, or practitioners when useful.

Respect the user's preference if they do not want community involvement.

Use `NOTES.md` for durable teaching preferences or working constraints so later
sessions do not repeatedly ask or recommend something the user has declined.
