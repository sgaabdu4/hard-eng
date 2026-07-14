---
version: alpha
name: Hard Eng
description: Professional warm-neutral lifecycle identity with teal planning/build and green delivery accents.
colors:
  ink: "#151A20"
  canvas: "#FBF8F3"
  panel: "#F3E8DA"
  primary: "#0E777C"
  verify: "#58B8C1"
  ship: "#5C963F"
  on-dark: "#FFFFFF"
typography:
  display:
    fontFamily: "system-ui, sans-serif"
    fontSize: 64px
    fontWeight: 700
    lineHeight: 1
    letterSpacing: -0.03em
  heading:
    fontFamily: "system-ui, sans-serif"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.15
  body:
    fontFamily: "system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: 8px
  card: 16px
  pill: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
components:
  lifecycle-plan:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-dark}"
    rounded: "{rounded.card}"
    padding: 24px
  lifecycle-build:
    backgroundColor: "{colors.verify}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: 24px
  lifecycle-ship:
    backgroundColor: "{colors.ship}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: 24px
  learning-signal:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: 24px
  lifecycle-canvas:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: 24px
---

# Hard Eng Design

## Overview

- Visual identity = professional + calm + rigorous + human.
- Canonical reference = `assets/readme/hard-eng-hero.png` SHA-256 `8a34dffd7dfa754de486f26152b0659dca385836425e6d26f124e7f508652a10`.
- Hierarchy = bold wordmark → concise promise → explicit lifecycle cards.
- People = inclusive anime-style collaborators; retain approved characters when lifecycle art changes.
- Lifecycle = Plan → Build (Implement ⇄ Verify) → Ship; learning evidence spans every boundary.

## Colors

- Ink = near-black authority for wordmark, headings, and primary text.
- Canvas = warm off-white; pure clinical white is not the dominant surface.
- Plan/build = restrained teal; use for state, arrows, and verification loop.
- Ship = natural green; learning signal = warm panel + restrained dashed return path.
- Border/panel = warm neutrals; preserve calm separation without heavy chrome.

## Typography

- Wordmark/display = heavy system sans + tight tracking + lowercase product name.
- Stage heading = bold system sans + compact line height.
- Body = readable system sans; clarity outranks decorative character.

## Layout

- Lifecycle visual = horizontal on wide surfaces + readable stacked adaptation on narrow surfaces.
- Build = one grouped owner containing Implement ⇄ Verify; never render them as independent lifecycle stages.
- Spacing = generous outer canvas + consistent card gaps + clear arrow lanes.

## Elevation & Depth

- Depth = warm border + subtle tonal panel separation.
- Heavy shadows + glossy effects + neon glow = forbidden.

## Shapes

- Cards = softly rounded rectangles.
- Status = compact pills.
- Flow = simple arrows; verify loop remains visibly bidirectional.

## Components

- Wordmark = `hard-eng`; no alternate logo text.
- Lifecycle card = stage name + approved character/art + state accent.
- Build group = Implement card + Verify card + loop arrows inside one boundary.
- Learning signal = candidate marker + dashed return to owning stage; never a lifecycle card.

## Do's and Don'ts

- Do = preserve approved lifecycle order + character continuity + warm professional palette.
- Do = keep arrows aligned, unobstructed, and semantically correct.
- Do = verify contrast + reflow + readable labels.
- Do not = introduce plugins/harness logos + extra lifecycle stages + decorative complexity.
- Do not = replace the approved hijabi planner or other approved people without explicit approval.
- Do not = treat Imagegen output as exact layout/token proof; use code/vector owners for geometry.
