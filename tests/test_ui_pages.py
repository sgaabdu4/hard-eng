"""The measures on saved public pages and fixtures, the patterns table, and the Stop path imports."""

import shutil
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from ui_capture import WIDTHS, capture

FIXTURES = Path(__file__).parent / "fixtures/ui_quality"
UI_MODULES = (
    "ui_measure",
    "ui_proof",
    "look",
    "merge_guard",
    "ship_record",
    "plan_controls",
)


LAYOUT_RULES = {
    "competing-buttons",
    "accent-colours",
    "overflow",
    "shared-edge",
    "field-control",
    "extra-text",
}


GOV_SEARCH_REASON = (
    "its search field has no icon inside, with one submit button beside it; "
    "the search row of ux.md is the user's decision, so the finding stays and "
    "this one element is left out (see the fixture README)"
)
KNOWN_DIFFERENCES = {"govuk-home": ('input[name="keywords"]', GOV_SEARCH_REASON)}


@pytest.mark.parametrize(
    ("name", "edge_widths"),
    [("govuk-home", ()), ("govuk-buttons", ()), ("pushed-right", (390, 768))],
)
def test_saved_public_pages_have_no_layout_misfires(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    name: str,
    edge_widths: tuple[int, ...],
) -> None:
    shutil.copy(FIXTURES / f"public/{name}.html", tmp_path / f"pages/{name}.html")
    skip = KNOWN_DIFFERENCES.get(name, ("", ""))[:1]
    found = capture(browser, tmp_path, site, name, skip)
    for width in WIDTHS:
        layout = {rule for rule in found[width] if rule in LAYOUT_RULES}
        assert layout == ({"shared-edge"} if width in edge_widths else set()), (
            name,
            width,
            found[width],
        )


@pytest.mark.parametrize(
    ("name", "rule", "red_count"),
    [("fields", "field-control", 3), ("text", "extra-text", 2)],
)
def test_red_then_fixed_standard_fields_and_extra_text(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    name: str,
    rule: str,
    red_count: int,
) -> None:
    for variant, expected in (
        ("red", Counter({rule: red_count})),
        ("fixed", Counter()),
    ):
        page = f"{name}-{variant}"
        shutil.copy(FIXTURES / f"{page}.html", tmp_path / f"pages/{page}.html")
        found = capture(browser, tmp_path, site, page)
        for width in WIDTHS:
            assert found[width] == expected, (page, width, found[width])


def test_standard_patterns_state_behaviour_and_placement_only() -> None:
    reference = (
        FIXTURES.parents[2] / ".agents/skills/he-plan/references/ux.md"
    ).read_text()
    rows = [
        line
        for line in reference.split("- Standard patterns =")[1]
        .split("- Brief =")[0]
        .splitlines()
        if line.startswith("| ")
    ][2:]
    assert 8 <= len(rows) <= 12
    for row in rows:
        assert len(row.split("|")[1:-1]) == 2, row
        lowered = row.lower()
        for word in ("colour", "color", "font", "px", "pt ", "pixel", "bold", "round"):
            assert word not in lowered, (word, row)


def test_a_plan_check_of_a_plan_without_a_visible_change_loads_no_ui_proof(
    tmp_path: Path, completed_plan: str
) -> None:
    import subprocess
    import sys

    from conftest import SOURCE

    plan = tmp_path / "PLAN.md"
    plan.write_text(completed_plan)
    code = (
        "import sys, pathlib; sys.path.insert(0, sys.argv[1]); import plans; "
        "plans.validate_plan(pathlib.Path(sys.argv[2])); "
        "print(sorted(m for m in sys.argv[3:] if m in sys.modules))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code, str(SOURCE / ".hooks"), str(plan), *UI_MODULES],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == "[]"


def test_the_stop_path_plan_check_of_a_visible_plan_loads_no_ui_proof(
    tmp_path: Path, visual_plan: str
) -> None:
    import subprocess
    import sys

    from conftest import SOURCE, commit, init

    project = tmp_path / "project"
    init(project)
    (project / "hard-eng.gates.json").write_text('{"packages": [], "shared": {}}')
    (project / "src/ui").mkdir(parents=True)
    (project / "src/ui/Field.tsx").write_text("export {};\n")
    commit(project, "first")
    plan = project / "features/x/PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        visual_plan.replace(
            "Controls: None — the fixture changes only wording.",
            "Controls: Field — reuses `src/ui/Field.tsx`",
        )
    )
    code = (
        "import sys, pathlib; sys.path.insert(0, sys.argv[1]); import plans; "
        "root = pathlib.Path(sys.argv[2]); "
        "plans.validate_plan(root / 'features/x/PLAN.md'); "
        "plans.validate_plans(root, 'HEAD', 'Complete'); "
        "print(sorted(m for m in sys.argv[3:] if m in sys.modules))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code, str(SOURCE / ".hooks"), str(project), *UI_MODULES],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "['plan_controls']"
