# UX Stage

## Decide

| Area | Required decision |
|---|---|
| Surface | entry points + screens + hierarchy + navigation + terminology/content/actions |
| State | form/validation + loading/empty/error/permission + feedback/confirm/cancel |
| Adaptation | responsive + keyboard + focus + labels/errors + contrast/reflow/motion/touch targets |
| Components | reuse/modify/new-shared/feature-specific; new shared owner requires reuse-gap evidence |
| Proof | mock contracts/data + happy/alternate/error paths + assets/prototype/screenshots/video when material |

## Method

| Need | Use |
|---|---|
| Structure/layout before production stack exists | HTML/CSS interactive prototype |
| Existing app, design system, or component-state fidelity | Real-component isolated prototype |
| Aesthetic direction, illustration, mood, or visual comparison | Imagegen after explicit approval |
| Shared designer handoff/review requires editable design source | Figma when available |
| No observable UI/interaction change | Skip proposal |

## Route

1. Compare accepted UX intent against root `DESIGN.md` → record no-delta or invoke `$atomic-ui` DESIGN update + explicit approval.
2. Route no-UI case through Method → approve `Visual surface = none` declaration → propose feature UX skip.
3. Existing UI → inventory production owners + exact reuse/change gaps.
4. New UI/product → research product/design constraints + target users + platform conventions before proposing direction.
5. Material visual/interaction choice → present 2–3 distinct evidence-backed options; otherwise recommend the single owner-preserving path.
6. Apply Method → obtain required user selection/approval → create only the selected proof artifact.
7. Exercise mock-data happy + alternate + loading/empty/error/permission + responsive/a11y flows; iterate until selected behavior is represented.
8. Capture screenshots/video only when decision-useful → record `$atomic-ui` production-owner evidence + prototype/assets paths.

- Imagegen = aesthetic proof only; never exact layout/interaction/tokens.
- HTML/CSS/real components = exact layout/interaction proof; production wiring = forbidden.

## Complete

- Root `DESIGN.md` exists + validates + reflects approved intended visual/no-visual truth.
- Selected method + reason + paths + decisions + trade-offs = recorded.
- Complete relevant flow is inspectable with mock data; non-happy states included.
- `$atomic-ui` ownership evidence + accessibility/responsive behavior = explicit.
