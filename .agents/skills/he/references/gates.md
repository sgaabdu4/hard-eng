# Adapt + repair checks

Apply when adapting or repairing project checks; use native diagnostics for enforced requirements.

| Agent decision | Required proof |
| --- | --- |
| Package/source coverage | Match actual production owners, nested packages + native workspaces. Review scan roots, generated/vendor attributes, ignored files and dynamic entry points; a clean report cannot prove omitted code was examined. |
| Import boundaries | Derive public/private interfaces + allowed dependencies from actual architecture. Prove allowed → pass, forbidden → fail, restored → pass, including relevant aliases, exports + test imports. Do not invent boundaries to satisfy a gate. |
| Performance | Choose representative workloads/environment + justified latency, memory, frame or operation budgets. Intentionally exceed each budget to prove failure. Flutter rendering needs profile-mode device measurements; debug unit tests are insufficient. See [Efficiency](efficiency.md) for bulk/async cases. |
| Security + dependencies | Review actual trust boundaries, native exclusions, extractor coverage + selected lockfiles/images. Confirm the scanned image is the intended build; scanner success does not establish exploitability or complete coverage. |
| Exceptions | Only proven false positives or intentional supported patterns; narrow native exception + adjacent reason/evidence. Keep the rule active elsewhere. |
| Parallelism | Opt in only independent commands with distinct outputs; account for child workers, memory + connections. Builds, generators and report cleaners may need ordering. |

Use existing [Python](../templates/hard-eng.python.json), [JavaScript](../templates/hard-eng.javascript.json) or [Dart/Flutter](../templates/hard-eng.dart.json) templates when adapting a new package. Do not copy a template over project-specific contracts.
