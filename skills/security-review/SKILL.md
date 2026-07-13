---
name: security-review
description: Review owned code or proposed changes for auth, data, secret, dependency, injection, or LLM security risks.
---

# Security Review

## Contract

- Scope = defensive review of user-owned/authorized code, config, artifact, URL, or design only.
- Finding = exact source/flow + preconditions + affected asset/data + realistic impact + simpler fix + verification + confidence.
- Focused trace = input → validation → identity/tenant policy → privileged sink/data/tool → observable impact.
- Mask secret values; report type + location + exposure path. Current advisory claim requires version-aware evidence.
- Review request = read/execute only; remediation requires explicit fix authority.

## Route

| Need | Load/action |
|---|---|
| Focused auth/data/injection/upload/secret/LLM path | Apply focused trace + report contract |
| Broad application/repository review | [broad.md](references/broad.md) |
| Dependency/advisory exposure | [dependencies.md](references/dependencies.md) + `$research` |
| Branch/PR/WIP security review | `$code-review` owns final axes/verdict; this skill supplies security evidence |
| Existing scanners/audits/CI | `$deterministic-checks` owns commands/results |

## Result

| Status | Boundary |
|---|---|
| `FAIL` | Confirmed exploitable risk, exposed secret/data, broken trust boundary, or required evidence/gate failure |
| `CONCERNS` | Material surface unverified, plausible path lacks decisive proof, or current dependency evidence unavailable |
| `PASS` | Every scoped surface checked/`N/A`; no unresolved finding |

- Separate required findings from hardening/info; missing coverage remains explicit.
- Remediation = root owner + affected blast radius + `$test-quality` + `$deterministic-checks`; never suppress evidence.
