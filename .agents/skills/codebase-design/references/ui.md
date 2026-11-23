# UI ownership

Every screen comes from one source in five layers: (1) Fixed UX rules; (2) `DESIGN.md`, whose front matter holds the design tokens; (3) Token files, derived from it and compared with it by the full check; (4) Library, the shared parts of the `ui_library` folders, which use only tokens and are listed in `UI-LIBRARY.md`; (5) Screens, which use only library parts. The look is free inside `DESIGN.md`. Atomic folder names may stay inside the library; they are not the main structure.

Use the existing design system + actual consumers to locate the decision's owner.

| Decision                            | Closest owner                   |
| ----------------------------------- | ------------------------------- |
| Reusable visual value               | Existing token/theme            |
| Basic control behavior              | Primitive / atom                |
| Repeated interaction or composition | Component / molecule / organism |
| Page arrangement                    | Layout / template / page        |
- These are responsibilities, not required folders or extraction targets. Keep a true one-off constraint inside the library part that needs it; component extraction must remove repeated visual/interaction knowledge or establish a meaningful composed contract.
- Check existing variants before adding props or another component. Reuse styling without merging components whose behavior and semantics differ.
- Consolidate touched consumers at the chosen owner; avoid parallel editable values in documentation, theme and components, except the token values of `DESIGN.md` and its token files, which the full check compares. Follow the project's existing token mechanism rather than introducing generation or synchronization tooling.
- Exercise affected responsive, loading, empty, error, disabled + focus states as applicable. Verify semantic names/roles, keyboard behavior and visual output; component reuse alone proves none of these.
- The library holds one part for each fixed control: `PasswordField` (label, autocomplete, error, a reveal icon with a screen-reader label), `SearchField` (screen-reader label, search icon, no text button), `EmptyState` (image, title, one action), `ErrorMessage` (set through the field's error input, tied to the field) and `ConfirmDialog` (a title that says what will happen, a confirm button with that verb, focus on Cancel). The empty state, password field and search field have no description or subtitle slot. `UI-LIBRARY.md` lists each part with a use line; `ui-library --write` keeps it current.
