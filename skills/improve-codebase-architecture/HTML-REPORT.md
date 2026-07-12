# HTML Report Format

Render the architectural review as one offline HTML file. Put all styles in an
inline CSS token layer and render diagrams as static inline SVG or semantic HTML.
The report makes no network requests and runs no scripts, so private source names
stay inside the local artifact.

## Scaffold

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Architecture review — {{repo name}}</title>
    <style>
      :root {
        --bg: oklch(0.98 0 0);
        --surface: oklch(1 0 0);
        --ink: oklch(0.22 0.02 255);
        --muted: oklch(0.48 0.02 255);
        --line: oklch(0.86 0.01 255);
        --accent: oklch(0.52 0.16 260);
        --leak: oklch(0.55 0.2 25);
        --warning: oklch(0.7 0.14 75);
        --radius: 8px;
        --space-1: 0.5rem;
        --space-2: 1rem;
        --space-3: 1.5rem;
        --space-4: 2.5rem;
      }
      * { box-sizing: border-box; }
      body { margin: 0; background: var(--bg); color: var(--ink); font-family: system-ui, sans-serif; }
      main { width: min(72rem, calc(100% - 2rem)); margin: 0 auto; padding: var(--space-4) 0; }
      .candidates { display: grid; gap: var(--space-4); }
      .candidate { border-top: 1px solid var(--line); padding-top: var(--space-3); }
      .comparison { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
      .diagram { min-height: 20rem; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: var(--space-2); }
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: var(--leak); }
      @media (max-width: 48rem) { .comparison { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <main>
      <header>...</header>
      <section class="candidates" id="candidates">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

Resolve reusable colors, spacing, radii, and typography through the inline token
layer. When the target repo has compatible design tokens, copy their resolved
values into these semantic roles instead of inventing a second visual system.

## Header

Show repo name, date, and a compact legend: solid box = module, dashed line =
seam, red arrow = leakage, thick dark box = deep module. Start with candidates,
not an introduction paragraph.

## Candidate

Each candidate is one `<article>` with:

- short title naming the deepening
- recommendation strength and dependency category
- monospaced file list
- side-by-side before/after diagram
- one-sentence problem and solution
- wins of six words or fewer
- one-line ADR callout when needed

The diagram carries the explanation. Redraw any diagram that needs a paragraph.

## Static diagram patterns

Use static inline SVG for dependencies, call flow, or sequence. Give every SVG a
`<title>`, keep source order meaningful, use arrow markers defined inside the
same SVG, and label leakage without relying on color alone.

```html
<svg class="diagram" viewBox="0 0 640 320" role="img" aria-labelledby="before-title">
  <title id="before-title">Before: pricing leaks across the repository seam</title>
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0 0 L8 4 L0 8 Z" fill="context-stroke" />
    </marker>
  </defs>
  <rect x="24" y="120" width="150" height="56" rx="8" />
  <text x="99" y="153" text-anchor="middle">OrderHandler</text>
  <rect x="244" y="120" width="150" height="56" rx="8" />
  <text x="319" y="153" text-anchor="middle">OrderRepo</text>
  <rect x="464" y="120" width="150" height="56" rx="8" />
  <text x="539" y="153" text-anchor="middle">PricingClient</text>
  <line x1="174" y1="148" x2="244" y2="148" marker-end="url(#arrow)" />
  <line class="leak seam" x1="394" y1="148" x2="464" y2="148" marker-end="url(#arrow)" />
  <text x="429" y="132" text-anchor="middle">leak</text>
</svg>
```

Use semantic HTML boxes with static inline SVG arrows when manual placement makes
the comparison clearer. Other useful shapes are cross-sections for shallow
layers, mass diagrams for interface-to-implementation depth, and call-graph
collapse for behavior moved behind one interface.

## Style

- Lean, dense, and editorial; use generous whitespace without dashboard chrome
- Restrained neutral surfaces with one accent, warning, and leakage role
- Flat sections; avoid nested cards and decorative shadows
- Keep diagrams near 320px tall and stack comparisons on narrow screens
- Use compact system typography and readable labels
- Preserve meaning in monochrome and at 200% zoom
- Keep the artifact static: inline CSS and static inline SVG only

## Top recommendation

Use one larger section with the candidate name, one sentence explaining why, and
an anchor link to its candidate.

## Language

Use the `codebase-design` glossary terms exactly: module, interface,
implementation, depth, deep, shallow, seam, adapter, leverage, and locality.

Suitable phrasing:

- "Order intake module is shallow — interface nearly matches implementation."
- "Pricing leaks across the seam."
- "Deepen: one interface, one place to test."
- "Two adapters justify the seam: HTTP in prod, in-memory in tests."

Wins name the architectural gain, such as "locality: bugs concentrate" or
"interface shrinks; implementation absorbs behavior."
