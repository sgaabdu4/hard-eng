# Hard Eng Design

## Experience

Hard Eng should feel like a serious engineering control surface: clear order,
compact evidence, explicit decisions, visible blockers, and calm status color.
The interface favors inspectability over decoration and never hides a gate
behind animation, jargon, or an opaque agent action.

## Design source of truth

Token owner: `assets/readme/tokens.css`.

Use semantic tokens rather than raw colors in diagrams, HTML prototypes, README
media, and any future status UI. Update this file and the token owner together
when visual behavior changes.

The current vocabulary is:

- background, panel, ink, muted text, and divider;
- pass, ready, concern, fail, blocked, and publication status;
- terminal background, foreground, border, bar, and code emphasis;
- brand wordmark, proof-return, and verification-notch colors;
- system sans and system monospace stacks.

Use OKLCH colors for interactive surfaces, compact type, 8px radii, accessible
contrast, visible focus, and wrapping code labels. README workflow media uses
the token owner's compatibility hex values: warm ivory, near-black, restrained
teal, professional green, and quiet tan borders. Avoid nested cards, decorative
gradients, invented status colors, negative letter spacing, or dense
screenshots that cannot be read at their delivered size.

## Lifecycle presentation

Every lifecycle surface makes these facts visible:

- accepted outcome or direct contract;
- current phase and Build substep;
- current vertical slice;
- fresh proof and candidate identity;
- blockers and admitted findings;
- exact next action and owner;
- whether user approval is required.

`assets/readme/hard-eng-hero.png` is the approved README hero. It preserves the
five original anime character scenes, including the hijabi planner, while
grouping Implement and Verify inside one `he-build` frame with a visible return
loop. It is the only README flow visual.

## Brand mark

The approved direction is **Verified Return**:

- `assets/readme/hard-eng-wordmark.svg` is the primary outlined wordmark; the
  terminal `g` returns left as a proof arrow.
- `assets/readme/hard-eng.svg` is the compact transparent mark; a broken
  charcoal return loop forms the `g`, and one restrained teal notch represents
  verification.
- Both marks use the standalone compatibility values owned by
  `--brand-wordmark` and `--brand-verification`; neither uses a background
  card, shadow, gradient, status dot, or generated text.
- The compact mark must remain recognizable at 32px. The wordmark must render
  without an installed font because its letters are vector outlines.

## UI Decision Lab

For user-visible work, Plan first discovers the project's actual tokens,
components, layout, copy, interaction, and accessibility owners.

- Existing interfaces use their real design system and capture a reproducible
  baseline when possible.
- Greenfield or radical visual work may offer two or three distinct Imagegen
  direction boards only after explicit call-budget approval.
- A selected direction becomes code-native tokens plus an interactive
  prototype with realistic sanitized mock data and happy, loading, empty,
  validation, permission, error, retry, and recovery states.
- Web concepts use HTML/CSS. Existing non-web products prefer their native
  preview/component environment when HTML would misrepresent behavior.
- Generated pixels are exploration, never the implementation or accessibility
  proof.

The user approves the direction before Build. Build presents comparable
real-app evidence at the selected cadence. Ship presents the final accepted
candidate with before/after screenshots and sequence video when the flow,
motion, navigation, responsiveness, or reproduced UI bug requires it.

## Documentation and media

Architecture diagrams should be code-native Mermaid or SVG. Terminal captures
use deterministic sanitized fixtures. Media contains no personal paths,
repository names, task IDs, credentials, private UI, or fabricated results.

A raster README hero requires explicit generation approval. Product proof uses
real deterministic artifacts, not marketing polish.

## Change rule

Any UI, visual, component, token, prototype, status, diagram, or media change
updates this file and `assets/readme/tokens.css`. Any product behavior or
positioning change updates `PRODUCT.md`.
