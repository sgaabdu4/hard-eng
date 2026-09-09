---
name: e2e
description: Prove real user journeys across browser, mobile, desktop, API and CLI surfaces using the project's existing test tools. Use for end-to-end verification, runtime UI review or requested visual proof.
---

# E2E

## Route by the surface under test

| Surface | Execution owner |
|---|---|
| Web UI, including React, Next.js and Vue | Existing browser E2E runner and conventions. Use available browser control to explore; preserve durable regressions in the project's tests. |
| Requested polished web walkthrough video | [Product Walkthrough](../product-walkthrough-video/SKILL.md) owns recording, pacing, review and MP4 delivery. |
| Flutter with Riverpod | [Building Flutter Apps](../building-flutter-apps/SKILL.md) owns device execution, Dart MCP, optional Marionette, native boundaries and lifecycle proof. |
| Other Flutter stacks | Existing Flutter integration tests and device tooling; use the project's compatible runtime tools without importing Riverpod architecture rules. |
| Native mobile, React Native or desktop UI | Existing platform/device automation and test runner. Verify OS-owned dialogs through platform control, not just the app tree. |
| API, backend, worker or CLI, including pure Dart | Existing integration tests through the real request, event or command boundary; assert response/exit behavior and durable effects. A browser or Flutter runtime is needed only when the journey includes it. |

Select by actual surface, not implementation language. Follow explicit browser/device requirements. Use installed compatible tools first; if no usable runner or connection exists, identify the missing capability before proposing setup. Do not introduce a framework or wrapper just to follow this skill.

## Prove the journey

- Establish requested behavior, environment/build, actors, permissions and starting data. Exercise the real user path with stable semantic selectors and observable state waits.
- Choose the smallest cases covering the changed behavior and meaningful failures. Shared state needs independent writer/observer proof; persisted changes need source-of-truth readback. Cover denied/revoked access, retries or relaunch when the requirement depends on them.
- Keep cases isolated and repeatable using existing fixtures and cleanup. Do not substitute a mock, direct API mutation or test-only shortcut for the interaction being proved.
- Assert the visible result and relevant durable effects. A completed click, successful request, clean log or zero exit alone is insufficient. Investigate unexpected app/native/network errors and retries that only pass intermittently.
- On failure, preserve the reproduction and useful evidence. With fix authorization, correct the owner, rerun the original case and affected downstream cases, and retain a meaningful regression in the existing suite.

## Visual proof and completion

- Capture the smallest useful evidence set. Ordinary regression work does not require video. When screenshots or video are requested or needed, inspect the actual delivered media and confirm its subject, required steps and final state.
- A walkthrough's pointer and pacing can explain a real journey. Recording effects cannot prove raw rendering or timing that they alter. A polished video does not replace backend readback or repeatable regression assertions.
- Reuse Product Walkthrough's review pipeline for its videos; add no second receipt schema, validator or review runner. Other captures use the project's existing artifacts and direct media inspection.
- Keep secrets and personal data out of artifacts. Show requested evidence to the user; treat test artifacts as local unless their inclusion as repository assets is authorized.
- Report tested surfaces, outcomes and exact gaps separately. Assertions, persisted state, deployment identity and visual evidence prove different things. An unavailable device, account or unreviewed artifact remains unproven.
