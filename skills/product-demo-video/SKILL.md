---
name: product-demo-video
description: Use only when product video, demo recording, walkthrough, explainer, onboarding reel, or launch clip is explicit.
---

# Product Demo Video

Use only when video is an explicit deliverable. Build the real product story first; then capture/compose/render/QA.

## Modes

- Browser product demo: real local/web app capture with Playwright, composed in Remotion
- Narrative/investor explainer: script/deck/docs/assets -> Remotion scenes, voiceover/music, data-viz, maps, proof frames
- Hybrid pitch: product footage/screenshots plus narrative beats and proof

## Core Flow

1. Identify viewer, promise in first 5 seconds, duration, output path, privacy limits, and whether browser capture, VO, music, maps, generated images, or proof metrics are needed.
2. Write a short story brief and storyboard before recording.
3. Find project design SSOT: `DESIGN.md`, `design.md`, tokens/theme, CSS, assets, fonts, representative screens.
4. Install/use the standard pipeline: Playwright for capture, Remotion for composition/export, `@remotion/player` for preview, ffmpeg/ffprobe for QA.
5. Capture real UI actions with stable viewport/video size and event metadata; do not manipulate app state unless the user wants a conceptual mock.
6. Scaffold Remotion:

```bash
node <skill-dir>/scripts/create-remotion-demo.mjs --out docs/demo/remotion
```

7. Compose cursor, click bloom, camera zooms, captions, frame/device chrome, background, audio, and chapter timing in Remotion.
8. Preview with Remotion Player. Render with Remotion.
9. QA final MP4 with `scripts/qa-remotion-demo.mjs`, ffprobe, sampled frames, and audio checks when relevant.
10. Return final video path and one-line description.

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
