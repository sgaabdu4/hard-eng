---
name: lavish
description: Use only for UI option comparison and UI decision collection in Hard Eng planning. Not for generic reports, plans, diagrams, or non-UI artifacts.
---

# Lavish

Hard Eng uses Lavish narrowly: compare UI options, collect the user's decision,
and save the UI decision receipt before `/he:plan` can pass.

Read upstream reference when needed:
`vendor/skill-upstreams/lavish-axi/skills/lavish/SKILL.md`

## Contract

- Use only when Grill Me mapped `ui-flow` or `visual-design` to `run` or `brief`
- Do not use Lavish for generic plans, reports, diagrams, non-UI review, or stage management
- First inspect the app's design SSOT: `PRODUCT.md`, `DESIGN.md`, tokens, fonts, shared components, and representative screens
- Open a localhost mock flow that uses the current design system and shared components
- Show 2-4 concrete UI options, not vague pros/cons
- Run `npx -y lavish-axi <html-file>` to open the decision artifact
- Before every poll, the artifact itself must visibly show the current Grill Me
  question/options, and `--agent-reply` must tell the user what to answer next
- Run `npx -y lavish-axi poll <html-file>` with no timeout and rerun it if interrupted
- If a poll answer advances Grill Me to the next Q, update `session_state.md`,
  `plan_draft.md`, and the Lavish artifact before polling again
- Do not ask the next Grill Me question only in chat while a Lavish session is
  active; either update Lavish to that exact Q or end the session first
- Use native form controls for choices; custom controls need an explicit submit
  that calls `window.lavish.queuePrompt()` and `sendQueuedPrompts()`
- Direct Impeccable Live pages must not claim `Sent to Lavish` unless
  `window.lavish` exists and the queue/send call actually runs
- If a user answers from a direct Live page, record a manual browser-read receipt
  or reopen Lavish for capture; do not count the direct button as a poll receipt
- Do not rely on browser `localStorage`/`sessionStorage` for review state;
  persist decisions in repo files and `he-state.json`
- Save `optionsPath`, `pollReceiptPath`, `savedChoicesPath`, `savedComponentsPath`, selected option, rejected options, chosen components, and user decision in `he-state.json`
- If the user is not aligned, keep asking one question at a time; do not mark Plan ready
