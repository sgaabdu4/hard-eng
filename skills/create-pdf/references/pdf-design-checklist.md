# PDF Design Checklist

Use this before export and again after rendering the PDF back to images.

## Content And Structure

- One main idea per slide/page whenever possible
- Preserve all required content, but split crowded content across pages
- Prefer specific claims over generic copy
- Keep labels short and concrete
- Remove redundant labels when the object is self-explanatory, such as a QR code

## Visual Assets

- New decks and visual PDFs should include real or generated imagery
- Use actual product, client, venue, founder, map, chart, or workflow imagery where possible
- Generate or build custom visuals for abstract ideas instead of using filler panels
- If a page is only headings plus rectangular text boxes, redesign it around a stronger visual: full-bleed image, large crop, workflow graphic, before/after proof, chart, annotated screenshot, or generated bitmap
- Covers and section breaks should feel cinematic and specific: image-led, high-contrast, and immediately tied to the subject
- Download remote thumbnails/images locally and optimize them. Do not depend on hotlinks
- Use WebP/JPEG for photos, SVG for QR/icons/logos, and PNG only when transparency or screenshots require it

## Fixed Layout

- Pick page dimensions before composing
- For decks, 16:9 fixed pages work best: `1280x720` HTML or `16in x 9in` PDF
- Lock major boxes with explicit width/height, grid columns, and media aspect ratios
- Leave at least 24px between unrelated content groups on a 1280x720 slide
- Keep footer/page number areas clear
- Use exact element screenshots for HTML decks; viewport scroll screenshots can drift

## Typography And Readability

- Use one brand font family unless the existing design system says otherwise
- If no font is specified, default to Urbanist with weights 400, 500, and 600
- Verify required fonts through browser-computed styles and loaded `document.fonts`; do not accept silent system fallback
- Avoid bold body copy unless the brand system uses it
- Body text must be readable against its background
- Do not place small text on busy images. Add a solid/tinted panel or crop differently
- Check all long labels for wrapping, clipping, and line-height collisions

## Investor Deck Bar

- One clear message per slide, readable in a skim
- Large headline, restrained supporting copy, and proof through numbers or visuals
- Avoid paragraph blocks. Use labels, metrics, diagrams, screenshots, and captions
- Keep page numbers and footer metadata clear of content
- Use repeated structure across related pages, but vary compositions enough that the deck does not feel templated

## Image-Based PDF Export

- For complex browser designs, export each fixed page as a high-resolution image, then assemble the PDF
- Preserve source anchors as PDF link annotations for digital-review PDFs
- Recommended capture: 1280x720 page, device scale factor 2, JPEG quality 90-94
- Render-back QA is mandatory because the PDF is the real deliverable

## QA Checklist

- Page count is correct
- Page size/aspect ratio is correct
- Every page is aligned and complete
- No clipped or missing content
- No broken image placeholders
- No stale values or old terminology
- Clickable links work when expected
- QR codes scan from rendered PDF
- Contact sheet looks consistent at a glance
- File size is reasonable for sharing
