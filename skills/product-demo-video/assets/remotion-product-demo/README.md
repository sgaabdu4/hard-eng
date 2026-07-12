# Remotion Product Demo Template

This template is copied by `scripts/create-remotion-demo.mjs`.

## Contract

- `design.generated.ts` is generated from the nearest `DESIGN.md` or `design.md`
- Fonts come from `demoDesign.typography.uiStack` and `demoDesign.typography.displayStack`
- Do not hardcode a global skill font in the composition. If the project uses a committed font, load it in the project and expose it through `DESIGN.md`
- Camera zoom transforms the framed capture group: device/browser frame, chrome, and product content scale together
- Cursor events come from `createDemoDriver(..., {onEvent})` in `scripts/cursor-demo-harness.mjs`

## Files

- `ProductDemo.tsx`: final Remotion composition
- `Preview.tsx`: `@remotion/player` review surface
- `Root.tsx` and `index.ts`: Remotion render entry
- `story.sample.ts`: replace with the real product story
- `demo-types.ts`: shared props/events/design types

## Typical Use

1. Run the scaffold from the project root:
   ```bash
   node <skill-dir>/scripts/create-remotion-demo.mjs --out docs/demo/remotion
   ```
2. Put raw capture media under `public/capture/product-demo.webm` or update `captureSrc`.
3. Replace `story.sample.ts` with real scenes and captured events.
4. Preview with `@remotion/player`.
5. Render with `npx remotion render docs/demo/remotion/index.ts ProductDemo docs/demo/videos/product-demo.mp4`.
6. Check output with `scripts/qa-remotion-demo.mjs`.
