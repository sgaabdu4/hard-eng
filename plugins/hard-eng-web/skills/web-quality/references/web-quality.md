# Web quality

Start with the changed behavior, framework/version, existing components and
tokens, data/render boundary, bundle owner, accessibility contract, and
repository scripts. Use Codebase Memory for ownership and callers.

If Fallow or React Doctor is already project-owned or installed, use its
read-only/changed-code mode first and reduce output through Context Mode. Never
network-install it automatically. Treat dead-code, duplicate, architecture,
style-drift, security, and bundle findings as candidates until verified; no
semantic auto-fix.

For React/Next work, avoid serial data waterfalls, unnecessary client
boundaries, duplicate fetches, unstable effect dependencies, derived-state
effects, and broad imports that inflate bundles. Prefer parallel server data,
small serializable client props, dynamic loading for heavy optional UI,
existing design-system owners, semantic HTML, keyboard/focus support, and
measured performance evidence. Run project lint/type/test/build plus real UI
and accessibility proof required by the change.
