# Runtime Seam Ladder

## Setup

1. Ledger = every reporter failure + constraint + requested platform/artifact/state + rejected remedy.
2. Identity = Git revision + dirty-state fingerprint + dependency versions + flavor/entrypoint + build mode + package/bundle ID + version/build + artifact hash + installed version/update time.
3. Environment = physical/simulator device + OS/API + account/session + backend endpoint/project/region/tenant + provider + network state.
4. Reproduction = exact user action + expected result + observed result + timestamp/run ID + logs/screenshot/readback.
5. Matrix = one row per requested integration × permission state × app lifecycle state × artifact format.

## Ladder

| # | Seam | `PASS` evidence |
|---|---|---|
| 0 | Public behavior | Original violation reproduces red on the requested device/state; later the same proof turns green. |
| 1 | Artifact identity | Built bytes + installed bytes resolve to the same revision/flavor/package/version/build; AAB proof uses APKs generated from that bundle or the exact distributed track artifact. |
| 2 | Native declaration | Required manifest/Info.plist/entitlement/capability/resource exists in the packaged artifact, not only source. |
| 3 | Runtime permission | OS-owned grant readback matches the exact capability/data type; denied/revoked recovery is observable and usable. |
| 4 | Plugin boundary | Initialization + smallest token/read/schedule call terminate under a bounded deadline with value or exact error. |
| 5 | App owner | Startup, handler, datasource, state mapping, UI, and failure path are each wired; startup cannot wait forever on optional integration readiness. |
| 6 | Remote registration | Current app-instance token/installation generation maps to the expected authenticated user and current backend target. |
| 7 | Provider | Correct project/tenant provider is enabled; credentials/config are current; one unique direct-target probe is accepted. |
| 8 | Transport | Backend message/execution state + provider result/error are read back; accepted/sent is not inferred as device display. |
| 9 | OS receipt | Target-native logs/system state show receipt, suppression, or exact rejection at the OS boundary. |
| 10 | Lifecycle behavior | Foreground + background + terminated + tap/deep-link rows requested by the user each pass independently. |
| 11 | Source of truth | Remote/local durable state matches UI and contains no duplicate/stale generation after retry or reinstall. |
| 12 | Release observability | Controlled failure from exact installed artifact reaches expected telemetry project/environment/release/dist with symbolicated app frames. |

- Stop at first red/unknown seam → record prediction + discriminating check + result.
- Later seam cannot explain an earlier red seam.
- Rerun downstream seams only after the failed prerequisite changes.
- Full E2E = final proof, never first diagnostic.

## Notification + Push Branch

1. Classify payload = notification + data | notification-only | data-only.
2. Prove OS notification permission + Android channel + packaged small icon + Apple presentation capability as applicable.
3. Prove current FCM/APNs token → token refresh handling → backend target → correct provider.
4. Send one unique direct-target probe; record message ID + target ID + token-generation fingerprint without exposing the token.
5. Separate transport from presentation:
   - Foreground notification = app handler + explicit presentation path where the platform does not show it automatically.
   - Background/terminated notification = OS receipt/display + app-open handling.
   - Data-only = registered background entrypoint + platform execution constraints + app-owned presentation/state change.
6. Test tap from background + terminated with `onMessageOpenedApp`/initial-message equivalent.
7. Reinstall or clear-data → discard old token/target evidence → reopen app → re-register → repeat from seam 3.

## Health + Steps Branch

1. Prove platform service availability + packaged capability/manifest declarations.
2. Request the minimum capability set needed by the feature; read granted permissions back per data type.
3. Treat request completion, aggregate bool, null, partial grant, and actual read access as distinct states.
4. Read the exact requested type and time interval; prove raw sample/aggregate count before blaming mapping or UI.
5. Trace platform record → datasource → domain kind → aggregate → widget; close every exhaustive mapping for a newly supported metric.
6. Remote sync claim → independent backend readback with current user/source/range; UI alone is insufficient.
7. Denied/revoked path → clear explanation + direct settings/permission recovery + retry after foreground resume.

## Reminder Branch

1. Prove notification permission + scheduling capability + current clock/timezone.
2. Device path = schedule → pending-notification readback → fire on device.
3. Push fallback = local failure/timeout classified → one backend intent/target → provider/OS delivery.
4. Assert one delivery owner per reminder; local + push duplicate delivery = `FAIL`.
5. Bound plugin/token/function observations; timeout = unresolved seam, not silent success.

## Sentry + Release Branch

1. Route Flutter wiring through `building-flutter-apps`; route runtime issue/release readback through `sentry`.
2. Prove one centralized fail-open SDK boundary + PII-disabled/scrubbed configuration.
3. Bind release + dist to exact package version/build and artifact revision.
4. Retain/upload matching symbols for each obfuscated/native artifact; APK success does not prove AAB-derived artifact identity.
5. Upload receipt = wiring only; controlled event readback with exact release/dist + symbolicated app frame = runtime `PASS`.
6. Keep `SENTRY_AUTH_TOKEN` build-only; never print/store it in source, runtime config, logs, or evidence.

## Failure Controls

| Weak signal | Required replacement |
|---|---|
| Package installed | Runtime init + smallest compatible call |
| Permission requested | OS grant readback + actual capability/data operation |
| Device connected | Exact target identity + installed artifact + app state |
| Appwrite message `success` | Provider result + OS receipt + requested presentation state |
| Widget/unit test green | Compatible native device/runtime proof |
| Reinstall and retry | Name the invalidated identities + rebuild registration evidence |
| No error in logs | Positive value/state/readback assertion |
| Symbol upload succeeded | Exact-release controlled event + symbolicated frame |
| Long spinner/poll | Bounded terminal observation + first non-completing seam |

## Closure Matrix

| Item | Identity/state | Red proof | First red seam | Evidence after correction | Result |
|---|---|---|---|---|---|
| User-reported failure | exact | required | required | required | open/pass/blocker |
| Permission denied/revoked | exact | required | required | required | open/pass/blocker |
| Foreground | exact | when requested | required | required | open/pass/blocker |
| Background | exact | when requested | required | required | open/pass/blocker |
| Terminated/tap | exact | when requested | required | required | open/pass/blocker |
| APK | exact | when requested | required | required | open/pass/blocker |
| AAB-derived/distributed | exact | when requested | required | required | open/pass/blocker |
| Backend/source of truth | exact | when applicable | required | required | open/pass/blocker |
| Sentry release/symbols | exact | when required | required | required | open/pass/blocker |

## Current Primary Sources

- Firebase Flutter receive states + foreground/background handlers: <https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages>
- Firebase Flutter registration token + refresh: <https://firebase.google.com/docs/cloud-messaging/flutter/get-started>
- Android notification runtime permission: <https://developer.android.com/develop/ui/compose/notifications/notification-permission>
- Android Health Connect setup/permissions: <https://developer.android.com/health-and-fitness/health-connect/get-started>
- Android Health Connect permission UX: <https://developer.android.com/health-and-fitness/health-connect/ui/permissions>
- Flutter `health` package contract: <https://pub.dev/packages/health>
- Appwrite targets: <https://appwrite.io/docs/products/messaging/targets>
- Appwrite providers: <https://appwrite.io/docs/products/messaging/providers>
- Appwrite messages/status: <https://appwrite.io/docs/products/messaging/messages>
- Sentry Dart build plugin: <https://pub.dev/packages/sentry_dart_plugin>

Before relying on platform/provider semantics = `research` current primary-source `PASS` + local installed-version binding.
