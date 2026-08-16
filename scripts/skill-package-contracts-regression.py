#!/usr/bin/env python3
"""Red-capable fixtures for the repository-owned skill package validator."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load():
    path = ROOT / "scripts/skill-package-contracts.py"
    spec = importlib.util.spec_from_file_location("skill_package_contracts", path)
    if spec is None or spec.loader is None:
        raise SystemExit("skill-package-regressions: FAIL: validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(root: Path) -> Path:
    (root / ".skill-lock.json").write_text('{"version":3,"skills":{}}\n', encoding="utf-8")
    skill = root / "skills/example-skill"
    (skill / "agents").mkdir(parents=True)
    (skill / "references").mkdir()
    (skill / "SKILL.md").write_text(
        """---
name: example-skill
description: >-
  Validate example skill packages and resources.
metadata:
  version: "1.0"
---

# Example Skill

Use [workflow.md](references/workflow.md).
""",
        encoding="utf-8",
    )
    (skill / "references/workflow.md").write_text("# Workflow\n\n1. Finish.\n", encoding="utf-8")
    (skill / "agents/openai.yaml").write_text(
        """interface:
  display_name: "Example Skill"
  short_description: "Validate example skill package files"
  default_prompt: "Use example-skill to validate this package."
policy:
  allow_implicit_invocation: true
""",
        encoding="utf-8",
    )
    return skill


def expect_invalid(module, mutate: Callable[[Path], object], expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-skill-package-") as temporary:
        root = Path(temporary)
        skill = fixture(root)
        mutate(skill)
        try:
            module.validate_repository(root)
        except module.ContractError as exc:
            if expected not in str(exc):
                raise SystemExit(
                    f"skill-package-regressions: FAIL: expected {expected!r}, got {exc!r}"
                )
        else:
            raise SystemExit(f"skill-package-regressions: FAIL: accepted {expected}")


def check_markdown_grammar(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-skill-markdown-") as temporary:
        root = Path(temporary)
        skill = fixture(root)
        (skill / "SKILL.md").write_text(
            """---
name: example-skill
description: Validate example skill packages and resources.
---

# Example Skill

Use [the workflow][workflow].
<a href="references/workflow.md">HTML workflow</a>

```md
[not a resource](references/missing.md)
```

[workflow]: references/workflow.md
""",
            encoding="utf-8",
        )
        if module.validate_repository(root) != (1, 1):
            raise SystemExit("skill-package-regressions: FAIL: valid Markdown grammar rejected")


def check_managed_reachability(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-managed-skill-") as temporary:
        root = Path(temporary)
        skill = fixture(root)
        (root / ".skill-lock.json").write_text(
            '{"version":3,"skills":{"example-skill":{}}}\n', encoding="utf-8"
        )
        (skill / "agents/openai.yaml").unlink()
        if module.validate_repository(root) != (1, 0):
            raise SystemExit("skill-package-regressions: FAIL: valid managed package rejected")
        (skill / "references/orphan.md").write_text("# Orphan\n", encoding="utf-8")
        try:
            module.validate_repository(root)
        except module.ContractError as error:
            if "orphan reference files" not in str(error):
                raise SystemExit(f"skill-package-regressions: FAIL: {error}")
        else:
            raise SystemExit("skill-package-regressions: FAIL: managed orphan accepted")


def main() -> int:
    module = load()
    with tempfile.TemporaryDirectory(prefix="hard-eng-skill-package-valid-") as temporary:
        root = Path(temporary)
        fixture(root)
        if module.validate_repository(root) != (1, 1):
            raise SystemExit("skill-package-regressions: FAIL: valid package rejected")
    check_markdown_grammar(module)
    check_managed_reachability(module)

    expect_invalid(
        module,
        lambda skill: (skill / "SKILL.md").write_text(
            (skill / "SKILL.md").read_text(encoding="utf-8").replace(
                "name: example-skill", "name: wrong-name"
            ),
            encoding="utf-8",
        ),
        "name must match parent directory",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "SKILL.md").write_text(
            (skill / "SKILL.md").read_text(encoding="utf-8").replace(
                "metadata:", "unsupported:"
            ),
            encoding="utf-8",
        ),
        "unsupported frontmatter keys",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "SKILL.md").write_text(
            (skill / "SKILL.md").read_text(encoding="utf-8").replace(
                "description: >-\n  Validate example skill packages and resources.",
                "description: Use when: YAML is malformed.",
            ),
            encoding="utf-8",
        ),
        "Nested mappings",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "SKILL.md").write_text(
            """---
name: example-skill
description: &shared "Validate example skill packages and resources."
metadata:
  version: *shared
---

# Example Skill

Use [workflow.md](references/workflow.md).
""",
            encoding="utf-8",
        ),
        "aliases, anchors",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "SKILL.md").write_text(
            (skill / "SKILL.md").read_text(encoding="utf-8").replace(
                'version: "1.0"', "version:\n    nested: value"
            ),
            encoding="utf-8",
        ),
        "metadata must map string keys to string values",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "references/workflow.md").unlink(),
        "references missing resource",
    )
    expect_invalid(
        module,
        lambda skill: (
            (skill / "references/workflow.md").unlink(),
            (skill / "references/workflow.md").symlink_to(skill / "SKILL.md"),
        ),
        "contains a symlink",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "references/orphan.md").write_text("# Orphan\n", encoding="utf-8"),
        "orphan reference files",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "agents/openai.yaml").write_text(
            (skill / "agents/openai.yaml").read_text(encoding="utf-8").replace(
                "example-skill", "example-skill-extra"
            ),
            encoding="utf-8",
        ),
        "interface.default_prompt must mention",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "agents/openai.yaml").write_text(
            (skill / "agents/openai.yaml").read_text(encoding="utf-8").replace(
                "Use example-skill",
                f"Use {chr(36)}example-skill",
            ),
            encoding="utf-8",
        ),
        "without a runtime sigil",
    )
    expect_invalid(
        module,
        lambda skill: (skill / "agents/openai.yaml").write_text(
            (skill / "agents/openai.yaml").read_text(encoding="utf-8").replace(
                "Validate example skill package files", "Too short"
            ),
            encoding="utf-8",
        ),
        "interface.short_description must be 25-64 characters",
    )

    print("skill-package-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
