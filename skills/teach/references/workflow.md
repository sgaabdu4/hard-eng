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

Keep knowledge limited to what the target skill needs. For knowledge acquisition, reduce difficulty so working memory goes to understanding.

## Skill Practice

Use difficulty deliberately for skill acquisition:

- retrieval practice
- spacing
- interleaving for related skills
- tight feedback loops
- quizzes or real-world actions when useful

For quizzes, avoid answer-shape clues. Keep options comparable in length where possible.

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

Open the lesson file when useful.

## Assets

Reusable CSS, quiz widgets, simulators, and diagram helpers live in `assets/`.

Create a shared stylesheet early. Add new components only when a later lesson can reuse them.

## References

Create reference documents when a lesson produces durable compressed knowledge:

- syntax and code snippets
- algorithms and flowcharts
- poses, exercises, routines, or processes
- glossaries

Once a glossary exists, use its vocabulary in future lessons.

## Wisdom

For questions that need real-world judgment, answer as far as evidence allows and recommend high-reputation communities, classes, forums, or practitioners when useful.

Respect the user's preference if they do not want community involvement.
