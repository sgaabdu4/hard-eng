# Dependency Exposure

1. Enumerate resolved dependency/artifact versions from lockfile/SBOM/image/runtime; manifest range alone = insufficient.
2. Use existing ecosystem audit/SCA through `$deterministic-checks`; missing tool/install/change requires user-approved project owner.
3. Use `$research` → verify advisory ID + ecosystem/package + affected range + fixed version + current primary source.
4. Classify direct/transitive + prod/dev/build/container/OS + reachable/used/unknown; scanner hit alone ≠ exploitable path.
5. Report confirmed match, conflicting evidence, or unknown + exact next proof; never confirm from package-name/CVE keyword search.

- Evidence = command/tool version + resolved package version + advisory source/date + affected/fixed range + project usage.
- Source conflict → preserve both + `CONCERNS`; severity never exceeds proven project impact.
