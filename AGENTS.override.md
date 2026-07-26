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
- Runtime targets = OpenAI Codex + Claude Code.
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
- Only pinned `npx skills@1.5.16` add/update may write them; routine updates use `scripts/update-managed-skills.sh`.
- Before commit/push = `python3 skills/deterministic-checks/scripts/worktree.py --repo . --intent publish` + `python3 skills/deterministic-checks/scripts/bounded_run.py --timeout 600 -- python3 scripts/check-skill-contracts.py` + `node skills/deterministic-checks/scripts/check-design-md.js` + `node scripts/check-managed-skills.js`; failure = stop.
- Gate enforcement = `scripts/git-hooks/publish-gate.sh` via global dispatcher; pre-commit = managed-skills + design; pre-push = full contracts; `--no-verify` = explicit user approval only.
- Content change → upstream source → `scripts/update-managed-skills.sh`.
- Update scope = locked paths only; local paths + discovery + unlisted install = forbidden.
- Skill add/remove/source replacement = explicit user approval.
- Daily CI = model-free → `03:30 UTC` → direct default-branch commit when changed.
- Scheduled exception = locked-skill update only; no model, eval, subagent, or new skill.
