#!/usr/bin/env python3
"""Regression checks for the global affected-full gate contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REQUIRED = {
    "AGENTS.md": (
        "Gate scope = affected-full",
        "or uncertainty → full repository",
        "Gate concurrency = independent affected owners parallel",
    ),
    "PRODUCT.md": (
        "runs affected-full gates",
        "shared behavior = agent-agnostic canonical skills",
    ),
    "skills/deterministic-checks/SKILL.md": (
        "[Affected-full gates](references/affected-full.md)",
        "proven non-impacted scope may skip",
    ),
    "skills/deterministic-checks/references/affected-full.md": (
        "Affected-full = universal gates always + full applicable gate row per impacted owner.",
        "global/shared/toolchain/CI/classifier change → full repository",
        "external mutation serial via one release actor",
        "Skip = only scope the classifier proved non-impacted.",
    ),
    "skills/deterministic-checks/references/hooks.md": (
        "`pre-push` = affected-full",
        "CI = same classifier + gate commands",
        "one always-run aggregate",
    ),
    "skills/he-ship/references/workflow.md": (
        "affected-full classifier",
    ),
}


def validate(contents: dict[str, str]) -> tuple[str, ...]:
    findings: list[str] = []
    for relative, anchors in REQUIRED.items():
        text = contents.get(relative)
        if text is None:
            findings.append(f"missing owner: {relative}")
            continue
        for anchor in anchors:
            if anchor not in text:
                findings.append(f"{relative}: missing {anchor}")
    return tuple(findings)


def live_contents() -> dict[str, str]:
    contents: dict[str, str] = {}
    for relative in REQUIRED:
        path = ROOT / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


def check_sensitivity(contents: dict[str, str]) -> None:
    for relative, anchors in REQUIRED.items():
        for anchor in anchors:
            mutated = dict(contents)
            mutated[relative] = contents[relative].replace(anchor, "", 1)
            expected = f"{relative}: missing {anchor}"
            if expected not in validate(mutated):
                raise SystemExit(
                    "affected-full-contracts: FAIL | "
                    f"mutation survived: {relative} -> {anchor}"
                )


def main() -> int:
    contents = live_contents()
    findings = validate(contents)
    if findings:
        raise SystemExit(
            "affected-full-contracts: FAIL | " + " | ".join(findings)
        )
    check_sensitivity(contents)
    print("affected-full-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
