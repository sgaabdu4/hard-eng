# Product Demo Video Workflow

1. Identify viewer, promise in first 5 seconds, duration, output path, privacy limits, and whether browser capture, VO, music, maps, generated images, or proof metrics are needed.
2. Write a short story brief and storyboard before recording.
3. Find project design SSOT: `DESIGN.md`, `design.md`, tokens/theme, CSS, assets, fonts, representative screens.
4. Install/use the standard pipeline: Playwright for capture, Remotion for composition/export, `@remotion/player` for preview, and ffmpeg/ffprobe for QA.
5. Capture real UI actions with stable viewport/video size and event metadata; do not manipulate app state unless the user wants a conceptual mock.
6. Scaffold Remotion with `node <skill-dir>/scripts/create-remotion-demo.mjs --out docs/demo/remotion`.
7. Compose cursor, click bloom, camera zooms, captions, frame/device chrome, background, audio, and chapter timing in Remotion.
8. Preview with Remotion Player. Render with Remotion.
9. QA final MP4 with `scripts/qa-remotion-demo.mjs`, ffprobe, sampled frames, and audio checks when relevant.
10. Return final video path and one-line description.
