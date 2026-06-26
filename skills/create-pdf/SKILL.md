---
name: create-pdf
description: Use for visual PDFs: create, polish, export, verify decks, reports, proposals, one-pagers, or HTML-to-PDF.
---

# Create PDF

Make finished visual PDFs. Never deliver until the exported PDF has been rendered back to images and inspected.

## Flow

1. Identify artifact type, page size/aspect ratio, audience, source assets, and required output path.
2. If designing or polishing, read `references/pdf-design-checklist.md`.
3. Use existing brand/design sources first. If none, default to Urbanist `400/500/600`, restrained palette, image-led pages, and short proof-heavy copy.
4. Build meaningful visuals before layout: screenshots, photos, diagrams, charts, maps, timelines, QR codes, or generated bitmap scenes.
5. Lock dimensions. For HTML decks use fixed page elements such as `.slide { width: 1280px; height: 720px; overflow: hidden; }`.
6. Audit HTML before export with `scripts/audit-fixed-html.mjs`; require custom fonts when typography matters.
7. Export fixed HTML/decks with `scripts/export-html-deck.mjs`; prefer exact element screenshots assembled into image-based PDFs over browser print for complex decks.
8. Render the final PDF to page images, make/contact-sheet inspect, then iterate until clean.
9. Return final PDF path plus terse QA result.

## Script Paths

Use the skill root from the triggered skill path, or:

```bash
CREATE_PDF_SKILL_ROOT="${CREATE_PDF_SKILL_ROOT:-$HOME/.agents/skills/create-pdf}"
```

Useful commands:

```bash
node "$CREATE_PDF_SKILL_ROOT/scripts/audit-fixed-html.mjs" --url <url> --selector .slide --width 1280 --height 720 --require-font Urbanist --font-weights 400,500,600
node "$CREATE_PDF_SKILL_ROOT/scripts/export-html-deck.mjs" --url <url> --out output.pdf --selector .slide --width 1280 --height 720 --require-font Urbanist --font-weights 400,500,600
python3 "$CREATE_PDF_SKILL_ROOT/scripts/render-pdf-contact-sheet.py" output.pdf
```

If workspace dependency helpers expose Node, Python, Poppler, or Chrome paths, use those paths. If not, use `node`, `python3`, `pdftoppm`, and installed Chrome/Playwright from `PATH`.

## Quality Bar

- PDF feels designed, not printed
- Text is readable, aligned, unclipped, and high contrast
- Required fonts are loaded, not silently replaced
- Images reveal the subject and are intentionally cropped
- Numbers, charts, maps, QR codes, and links work at final PDF scale
- No stale placeholders, broken assets, low-res screenshots, overlap, or wrong page order
