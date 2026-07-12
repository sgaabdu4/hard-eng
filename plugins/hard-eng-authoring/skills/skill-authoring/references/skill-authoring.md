# Skill authoring

Define the job, positive triggers, exclusions, observable outputs, and failure
cases before writing. Keep `SKILL.md` a short entry/routing contract; move
multi-step workflows and variants into focused references or scripts. Reuse
templates/assets and avoid duplicate skills with overlapping descriptions.

Test manifest/YAML validity, trigger precision, non-trigger exclusions,
reference reachability, line/description/context budgets, path safety, and the
real public behavior. Model evaluations are release-only, explicitly approved,
bounded, and never a substitute for deterministic contracts.
