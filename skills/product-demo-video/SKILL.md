---
name: product-demo-video
description: Use only when the user explicitly requests a product demo video, walkthrough, explainer, onboarding reel, or launch clip; ordinary E2E screenshots and verification recordings do not trigger it.
---

# Product Demo Video

Use only when video is an explicit deliverable. Build the real product story first; then capture/compose/render/QA.

## Modes

- Browser product demo: real local/web app capture with Playwright, composed in Remotion
- Narrative/investor explainer: script/deck/docs/assets -> Remotion scenes, voiceover/music, data-viz, maps, proof frames
- Hybrid pitch: product footage/screenshots plus narrative beats and proof

## Core Flow

Read `references/workflow.md` before scripting, capturing, composing, or rendering.

## Non-Negotiables

- Product/design system drives typography, color, radius, logos, and stage surfaces
- Cursor is a small black pointer with click bloom, not a debug dot
- Zoom the captured frame/chrome/content group together; product text/control must visibly enlarge
- On-screen text is chapter copy, not internal QA narration
- Do not invent metrics, maps, customer data, testimonials, or proof
- Use real/safe data; avoid private data unless explicitly approved
- Final MP4 frames, not only source stills, are the QA artifact

## Details

Read `references/runbook.md` for narrative workflows, asset rules, maps, audio, capture script shape, composition ownership, motion guardrails, and QA frame list. Use bundled `assets/remotion-product-demo/` and scripts before writing custom scaffolding.
