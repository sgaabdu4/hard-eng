# Prototype Shared Rules

## Rules

- **Throwaway from day one**: place it near the real module or page, name it clearly as a prototype, and follow existing routing conventions
- **One command to run**: use the project runner, such as `pnpm <name>`, `python <path>`, or `bun <path>`
- **No persistence by default**: keep state in memory unless persistence is the question
- **Scratch persistence only**: if a database or file is required, mark it `PROTOTYPE - wipe me`
- **Skip polish**: no tests, abstractions, or error handling beyond runnable proof
- **Surface the state**: print or render relevant state after each action or variant switch
- **Delete or absorb**: once answered, delete the prototype or fold the decision into real code

## Durable Answer

Capture the answer and original question in a commit message, ADR, issue, or nearby `NOTES.md` before deleting the prototype.
