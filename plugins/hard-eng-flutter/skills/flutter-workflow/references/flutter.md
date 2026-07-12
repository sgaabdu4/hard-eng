# Flutter

Confirm the app actually uses Riverpod before applying these rules. Read its
`pubspec.yaml`, `build.yaml`, analysis options, routing owner, generated-file
policy, architecture, and tests. Never edit generated Dart; change annotations
or builders and run the repository-owned generation command.

Prefer code-generated providers, immutable domain state, typed repository and
datasource seams, pure-Dart domain objects, and widgets that render/dispatch
rather than own business state. Guard async gaps with the stack’s mounted
checks. Preserve localization, semantics, keyboard/focus, responsive layout,
deep-link, offline, permission, and restoration behavior when applicable.

Use project-locked SDK/package versions and current official Flutter/package
documentation. Do not install or upgrade packages automatically. Prove touched
packages with package-root `dart analyze`, focused tests, required codegen
currentness, and real device/browser E2E for observable flows. Realtime/shared
state requires writer-plus-observer proof without manual refresh.
