# Hard Eng Repository

- Product = Hard Eng.
- Canonical source = this repository.
- Skill owner = `skills/`.
- Runtime target = OpenAI Codex.
- Delivery = native Codex; plugin packaging = none.
- Cross-harness compatibility layers = none.
- Global behavioral rules = `AGENTS.md`; repository facts stay here.

## Skill ownership

- Canonical path = `skills/<name>/`.
- Ownership = lock key → managed vendor; absent from lock → local authored.
- Managed skill folders + lock metadata = immutable vendor copies; agent/manual edits = forbidden.
- Local skill folders = repository-owned; normal edits allowed.
- Only pinned `npx skills@1.5.16` add/update may write them; routine updates use `scripts/update-managed-skills.sh`.
- Before commit/push = `python3 scripts/check-skill-contracts.py` + `node skills/deterministic-checks/scripts/check-design-md.js` + `node scripts/check-managed-skills.js`; failure = stop.
- Content change → upstream source → `scripts/update-managed-skills.sh`.
- Update scope = locked paths only; local paths + discovery + unlisted install = forbidden.
- Skill add/remove/source replacement = explicit user approval.
- Daily CI = model-free → `03:30 UTC` → direct default-branch commit when changed.
- Scheduled exception = locked-skill update only; no model, eval, subagent, or new skill.
