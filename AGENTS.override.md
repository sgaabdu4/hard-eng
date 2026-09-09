# Hard Eng Repository

## Instruction ownership

- `AGENTS.md` = cross-repository behavior only.
- `AGENTS.override.md` = Hard Eng repository facts + maintenance + delivery rules.
- Global admission = applies unchanged to unrelated repositories; otherwise keep it here.
- Hard Eng owner replacement = one canonical path + superseded alias/compatibility/dual-path deletion.

## Repository

- Product = Hard Eng.
- Canonical source = this repository.
- Skill owner = `skills/`.
- Runtime targets = OpenAI Codex + Claude Code + GitHub Copilot CLI.
- Delivery = native per-agent wiring (symlink/import) from this canonical repository; plugin packaging = none.
- Duplicated per-agent instruction/skill copies forbidden; canonical file + symlink/import only.
- checkout_policy = primary-only
- Primary-only = agent/Git worktree creation + use forbidden.

## Skill ownership

- Canonical path = `skills/<name>/`.
- Ownership = lock key → managed vendor; absent from lock → local authored.
- Managed skill folders + lock metadata = immutable vendor copies; agent/manual edits = forbidden.
- Managed vendor aggregate file (e.g. `skills/vercel-react-best-practices/AGENTS.md`) = global file-size rule exempt; exemption reason = vendor-generated + lock-verified immutable.
- Local skill folders = repository-owned; normal edits allowed.
- Only pinned `npx skills@1.5.22` add/update may write them; routine updates use `scripts/update-managed-skills.sh`.
- Before commit/push = `scripts/git-hooks/publish-gate.sh commit|push` respectively; failure = stop.
- Gate enforcement = global dispatcher + same-Git-common-dir checkout gate; pre-tool = irreversible destructive-loss block only; planning records research + authorization receipts without blocking recoverable tool access; pre-commit = worktree + one staged format/lint scan + complete named enforcement owner/proof coverage; pre-push = typecheck + format + lint + tests + Fallow + Python types + Python format/lint + full contracts + managed-skills + design + secrets scan + enforcement coverage; `--no-verify` = explicit user approval only.
- Content change → upstream source → `scripts/update-managed-skills.sh`.
- Update scope = locked paths only; local paths + discovery + unlisted install = forbidden.
- Skill add/remove/source replacement = explicit user approval.
- Daily CI = model-free → `03:30 UTC` → direct default-branch commit when changed.
- Scheduled exception = locked-skill update + nightly mutation ledger (`02:17 UTC`, public repository only, pull request for survivors); no model, eval, subagent, or new skill.
