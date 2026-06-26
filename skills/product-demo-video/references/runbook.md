# Product Demo Video Runbook

## Story

For every video, capture:

- viewer and promise
- 3-5 product beats
- proof/end screen
- privacy limits
- source assets/data
- device/viewport truth

Investor/narrative videos also need problem, solution, proof, market, moat/distribution, close, voiceover, and scene timecodes.

## Capture

Use Playwright only for real product behavior. Set viewport and video size explicitly. Drive real clicks, typing, waits, scrolls, and success states. Record cursor/click event metadata so Remotion can draw the final pointer layer.

## Composition

Remotion owns editorial output: frame/device chrome, captured surface group, camera zoom, cursor, click bloom, captions, chapter cards, backgrounds, trims, audio, and export. Remotion Player owns frame-accurate local review.

The camera transform should scale the captured surface group around the target. Avoid iframe-only zoom, layout resizing, or decorative-frame-only growth.

## Narrative / Investor

1. Read script/deck/docs and extract scene table.
2. Critique for unclear product mechanism, missing proof, weak moat/market, consent risk, or slide-recap drift.
3. Map each scene to time range, voiceover, visual action, on-screen text, and source/proof.
4. Use project/deck assets first, then consented user assets, generated raster images, then SVG/data-viz.
5. For maps, use sourced map/GeoJSON data; never place geography by eye.
6. For generated images, inspect for bad text/logos/anatomy/cliches and copy accepted assets into the project.
7. Use animated SVG/data-viz for routes, pins, count-ups, dials, cards, stamps, and product-flow arrows when motion explains something.

## Audio

Read keys from env or hidden prompts only. Save raw and fitted VO. Probe durations. Use ffmpeg `atempo` conservatively. Keep music under voice and verify with `volumedetect`. Use licensed/user-provided/generated audio only.

## Motion

- Cursor glides; click bloom is brief
- Text enters after scene stabilizes
- Captions never cover clicked controls
- Long forms scroll deliberately: top/title, pause, interact, scroll, save/proof
- Process connectors stay in owned gaps/SVG viewBoxes and never cross content, faces, labels, or unrelated cards

## QA

Run the smallest useful checks:

```bash
node <skill-dir>/scripts/qa-remotion-demo.mjs docs/demo/videos/product-demo.mp4 --events docs/demo/videos/product-demo-events.json
ffprobe <video>
```

Sample final MP4 frames for:

- opening promise
- first narrative scene
- every click/zoom
- process flow with lines/arrows/dots/cards
- map/data-viz/proof metric
- long-scroll/form interaction
- role or device-frame switch
- dashboard/report proof
- end card

Check for blank frames, clipped text, wrong crop, caption overlap, loading states, wrong device claim, detached map pins, decorative connectors, secrets, and banned visual patterns.
