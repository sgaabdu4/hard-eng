# Create PDF Workflow

1. Identify artifact type, page size/aspect ratio, audience, source assets, and required output path.
2. If designing or polishing, read `references/pdf-design-checklist.md`.
3. Use existing brand/design sources first. If none, default to Urbanist `400/500/600`, restrained palette, image-led pages, and short proof-heavy copy.
4. Build meaningful visuals before layout: screenshots, photos, diagrams, charts, maps, timelines, QR codes, or generated bitmap scenes.
5. Lock dimensions. For HTML decks use fixed page elements such as `.slide { width: 1280px; height: 720px; overflow: hidden; }`.
6. Audit HTML before export with `scripts/audit-fixed-html.mjs`; require custom fonts when typography matters.
7. Export fixed HTML/decks with `scripts/export-html-deck.mjs`; prefer exact element screenshots assembled into image-based PDFs over browser print for complex decks.
8. Render the final PDF to page images, make/contact-sheet inspect, then iterate until clean.
9. Return final PDF path plus terse QA result.
