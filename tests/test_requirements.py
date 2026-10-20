"""Each rule has one registry definition that code, tests and docs reference by ID."""

from pathlib import Path

import pytest
from conftest import init
from plans import requirement_tests, validate_requirements

# Fixture IDs are built so this file names no real registry ID.
HE, REQ = "HE", "REQ"
COVERAGE_ID = f"{HE}-COVERAGE-MIN"
STYLE_ID = f"{HE}-OUTPUT-STYLE"
REGISTRY = ".agents/skills/he/references/requirements.md"
COVERAGE = (
    f"## {COVERAGE_ID} — Line coverage minimum\n\n"
    "Tests must cover at least seventy percent of executable lines in every package.\n\n"
    "Proof: check\n"
)
STYLE = f"## {STYLE_ID} — Plain output\n\nReplies use plain words.\n\nProof: guidance\n"
ENFORCER = f'raise ValueError("Coverage is too low ({COVERAGE_ID})")\n'
PYTHON_TEST = f'def test_low_coverage_fails() -> None:\n    """{COVERAGE_ID}: low coverage fails."""\n'


def project(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "project"
    init(root)
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content)
    return root


def proven(tmp_path: Path, registry: str = COVERAGE + STYLE, **extra: str) -> Path:
    return project(
        tmp_path,
        {
            REGISTRY: registry,
            "setup.py": "",
            ".hooks/coverage.py": ENFORCER,
            "tests/test_coverage.py": PYTHON_TEST,
            ".agents/skills/he/SKILL.md": f"Write plainly; see {STYLE_ID}.\n",
            **extra,
        },
    )


def test_proven_registry_passes(tmp_path: Path) -> None:
    validate_requirements(proven(tmp_path))


def test_project_without_registry_is_not_checked(tmp_path: Path) -> None:
    validate_requirements(project(tmp_path, {"README.md": f"See {HE}-UNKNOWN-RULE.\n"}))


def test_repeated_id_fails(tmp_path: Path) -> None:
    root = proven(tmp_path, registry=COVERAGE + STYLE + COVERAGE)
    with pytest.raises(ValueError, match=f"{COVERAGE_ID} is defined more than once"):
        validate_requirements(root)


def test_entry_without_proof_line_fails(tmp_path: Path) -> None:
    root = proven(
        tmp_path, registry=COVERAGE + STYLE + f"## {HE}-NEW-RULE — New\n\nText.\n"
    )
    with pytest.raises(ValueError, match=f"{HE}-NEW-RULE needs a definition and a"):
        validate_requirements(root)


def test_reference_to_unknown_id_fails(tmp_path: Path) -> None:
    """HE-REQUIREMENT-REGISTRY: a reference to an unregistered ID fails."""
    root = proven(tmp_path, **{"README.md": f"Coverage: {COVERAGE_ID}IMUM.\n"})
    with pytest.raises(
        ValueError, match=f"README.md:1 names unknown {COVERAGE_ID}IMUM"
    ):
        validate_requirements(root)


def test_reference_to_retired_id_fails(tmp_path: Path) -> None:
    retired = f"## {HE}-OLD-RULE — Old\n\nStatus: Retired — use {COVERAGE_ID}\n"
    root = proven(
        tmp_path,
        registry=COVERAGE + STYLE + retired,
        **{"README.md": f"{HE}-OLD-RULE\n"},
    )
    with pytest.raises(ValueError, match=f"README.md:1 names retired {HE}-OLD-RULE"):
        validate_requirements(root)


def test_check_rule_without_test_fails(tmp_path: Path) -> None:
    root = proven(tmp_path, **{"tests/test_coverage.py": "def test_x() -> None:\n"})
    with pytest.raises(ValueError, match=f"{COVERAGE_ID} has no test"):
        validate_requirements(root)


def test_check_rule_without_enforcer_fails(tmp_path: Path) -> None:
    root = proven(tmp_path, **{".hooks/coverage.py": "x = 1\n"})
    with pytest.raises(ValueError, match=f"{COVERAGE_ID} has no enforcing source"):
        validate_requirements(root)


def test_guidance_rule_without_skill_link_fails(tmp_path: Path) -> None:
    root = proven(tmp_path, **{".agents/skills/he/SKILL.md": "Write.\n"})
    with pytest.raises(ValueError, match=f"{STYLE_ID} has no skill"):
        validate_requirements(root)


def test_copied_rule_sentence_fails(tmp_path: Path) -> None:
    copy = "Rules:\n\n- tests must cover at least seventy percent of executable\n  lines in every package.\n"
    root = proven(tmp_path, **{"README.md": copy})
    with pytest.raises(ValueError, match=f"README.md copies {COVERAGE_ID}"):
        validate_requirements(root)


@pytest.mark.parametrize(
    "marker",
    [".hooks/hard-eng-source.json", "pyproject.toml"],
    ids=["marker", "no-setup"],
)
def test_installed_project_does_not_need_hard_eng_tests(
    tmp_path: Path, marker: str
) -> None:
    files = {REGISTRY: COVERAGE + STYLE, "AGENTS.md": f"Coverage: {COVERAGE_ID}.\n"}
    validate_requirements(project(tmp_path, {**files, marker: "{}\n"}))


def test_project_rule_needs_its_own_test(tmp_path: Path) -> None:
    own = f"## {REQ}-PAY-LIMIT — Payment limit\n\nPayments stop at the daily limit.\n\nProof: check\n"
    root = project(
        tmp_path,
        {
            REGISTRY: COVERAGE + STYLE,
            ".hooks/hard-eng-source.json": "{}\n",
            "docs/requirements.md": own,
            "src/pay.ts": f'throw new Error("{REQ}-PAY-LIMIT")\n',
        },
    )
    with pytest.raises(ValueError, match=f"{REQ}-PAY-LIMIT has no test"):
        validate_requirements(root)


def test_requirement_tests_name_each_covering_test(tmp_path: Path) -> None:
    named = f"it('{COVERAGE_ID}: low coverage fails', () => {{}})\n"
    root = proven(tmp_path, **{"src/coverage.test.ts": named})
    assert requirement_tests(root) == {
        COVERAGE_ID: [
            ("src/coverage.test.ts", 1, f"{COVERAGE_ID}: low coverage fails"),
            ("tests/test_coverage.py", 2, "test_low_coverage_fails"),
        ]
    }
