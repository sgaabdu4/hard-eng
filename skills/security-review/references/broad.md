# Broad Security Review

1. Fix scope + revision/environment + trust boundaries + entry points + identities/roles/tenants + sensitive assets.
2. Inspect auth/session/recovery + authorization/data isolation + secrets/logs/debug + uploads/files + injection/SSRF/XSS/RCE + dependencies/supply chain + LLM/tool actions.
3. Distributable binary/container/archive → preflight source defaults + resolved config + build arguments + generated/extracted artifact for embedded credentials/tokens/private endpoints/debug data before first delivery attempt.
4. Trace suspicious input to validation + policy + sink; verify tests/config/runtime evidence and counterexamples.
5. Classify confirmed findings by exploitability + asset sensitivity + blast radius; preference-only hardening stays separate.
6. Report findings first, then checked/`N/A`/unknown surfaces + residual risk + exact next proof.

| Surface | Reject when |
|---|---|
| Identity | Client controls subject/role/tenant; session/token/recovery invariant fails |
| Data | Object/property/list/export access lacks same-owner/tenant policy |
| Boundary | Debug/default/log/CORS/CSRF/header/rate-limit behavior fails open or exposes data |
| Input | User-controlled query/markup/URL/archive/parser/process/tool reaches unsafe sink |
| Files | Type/content/name/size/storage/serving/processing boundary is untrusted |
| Artifact | Packaged output embeds a secret/private default or lacks extracted-artifact inspection before delivery. |
| LLM/tool | Model selects privileged IDs/URLs/files/SQL/shell/payment/admin action without external authz/validation/approval |

- Missing authorization/runtime evidence → unknown, not safe inference.
- Formal standard requested → `research` current OWASP ASVS → cite versioned requirement IDs; coverage ≠ certification.
