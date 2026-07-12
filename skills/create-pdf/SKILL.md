---
name: create-pdf
description: Use for visual PDFs: create, polish, export, verify decks, reports, proposals, one-pagers, or HTML-to-PDF.
---

# Create PDF

Make finished visual PDFs. Never deliver until the exported PDF has been rendered back to images and inspected.

## Flow

Read `references/workflow.md` before creating or polishing a PDF.

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
