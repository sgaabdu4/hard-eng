"""Local Complete-stage UI proof checks: fast file-record verification before ship, skipped in CI and --quick."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import local_ui_proof
import look
import pytest
import ui_measure
from comments import validate_rules
from conftest import SOURCE, commit, git
from plans import usability_rules
from test_push_text_checks import push_check
from test_shipping import _fixture
from test_ui_quality import (
    GUIDELINE_TEST,
    NO_UX,
    REAL_UX,
    UNCHANGED_UX,
    WIDTHS,
    write_look,
    write_pair,
)
from tool_setup import TOOL_OWNER


def clear_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)


def web_change_repo(
    tmp_path: Path,
    *,
    ux: str = REAL_UX,
    design: str = "",
    commit_work: bool = True,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture = _fixture(tmp_path, ui_paths=["src/**", "app/**"])
    root = fixture.root
    if design:
        (root / "DESIGN.md").write_text(design)
    (root / ".git/info/exclude").write_text(".hard-eng/\n")
    (root / "src").mkdir()
    (root / "src/App.tsx").write_text("export const App = () => <p>Old</p>;\n")
    commit(root, "base")
    git(root, "branch", "-f", "main", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", git(root, "rev-parse", "main"))
    (root / "src/App.tsx").write_text("export const App = () => <p>New</p>;\n")
    plan_text = (root / "PLAN.md").read_text().replace(NO_UX, ux) + "\n"
    (root / "PLAN.md").write_text(plan_text)
    if commit_work:
        commit(root, "ui work")
    return root


def write_clean_browser(
    root: Path,
    *,
    name: str = "after",
    route: str = "/account",
    findings: list[dict[str, object]] | None = None,
    widths: tuple[int, ...] = WIDTHS,
    dirty_override: bool | None = None,
) -> bytes:
    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True, exist_ok=True)
    for width in widths:
        image = folder / f"{name}-{width}.png"
        image.write_bytes(f"{name}-{width}".encode())
        record_path = ui_measure.write_record(root, image, width, findings or [], route)
        if dirty_override is not None:
            data = json.loads(record_path.read_text())
            data["dirty"] = dirty_override
            record_path.write_text(json.dumps(data))
    return f"{name}-390".encode()


def test_local_complete_check_refuses_missing_browser_and_look_then_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, design="# Design\n\n## Overview\nNavy primary.\n")
    head = git(root, "rev-parse", "HEAD").strip()

    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "browser capture" in problem

    after = write_clean_browser(root, findings=[{"rule": "tap-size", "at": "btn"}])
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "tap-size" in problem

    after = write_clean_browser(root, route="/other")
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "/account" in problem

    after = write_clean_browser(root, route="/account")
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "Look review" in problem

    write_look(root, head, after)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "current DESIGN.md" in problem

    na_rules = [
        f"{name}: {'N/A — skipped' if name == 'Design system' else 'Pass — looked at it'}"
        for name, _ in usability_rules()
    ]
    write_look(root, head, after, design_doc=look.design_hash(root), rules=na_rules)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "Design system cannot be N/A" in problem

    write_look(root, head, after, design_doc=look.design_hash(root))
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None
    validate_rules(root, "origin/main", screens=True, full=True, stage="Complete")


def test_local_complete_check_refuses_na_ux_reference_on_visible_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, ux=NO_UX)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "ux_reference says N/A" in problem


def touch_after_capture(root: Path, rel: str = "src/App.tsx") -> None:
    future = (
        root / ".hard-eng/browser/after-390.json"
    ).stat().st_mtime_ns + 5_000_000_000
    os.utime(root / rel, ns=(future, future))


def _assert_reverted_and_untracked_dirty_ui(tmp_path: Path) -> None:
    reverted_root = web_change_repo(tmp_path / "rev", commit_work=False)
    (reverted_root / "src/Other.tsx").write_text("export const O = () => <p>v1</p>;\n")
    commit(reverted_root, "both components")
    rev_head = git(reverted_root, "rev-parse", "HEAD").strip()
    (reverted_root / "src/App.tsx").write_text("export const App = () => <p>D1</p>;\n")
    (reverted_root / "src/Other.tsx").write_text("export const O = () => <p>tmp</p>;\n")
    rev_after = write_clean_browser(reverted_root, route="/account")
    write_look(reverted_root, rev_head, rev_after)
    assert local_ui_proof.local_ui_proof_problem(reverted_root, "origin/main") is None
    git(reverted_root, "checkout", "--", "src/Other.tsx")
    touch_after_capture(reverted_root, "src/Other.tsx")
    problem = local_ui_proof.local_ui_proof_problem(reverted_root, "origin/main")
    assert problem is not None and "predates the latest UI edit" in problem

    (tmp_path / "udir").mkdir()
    untracked_dir_root = _fixture(tmp_path / "udir", ui_paths=["src/**/*.tsx"]).root
    (untracked_dir_root / ".git/info/exclude").write_text(".hard-eng/\n")
    (untracked_dir_root / "src").mkdir()
    (untracked_dir_root / "src/App.tsx").write_text(
        "export const App = () => <p>A</p>;\n"
    )
    commit(untracked_dir_root, "base")
    git(untracked_dir_root, "branch", "-f", "main", "HEAD")
    git(
        untracked_dir_root,
        "update-ref",
        "refs/remotes/origin/main",
        git(untracked_dir_root, "rev-parse", "main"),
    )
    (untracked_dir_root / "PLAN.md").write_text(
        (untracked_dir_root / "PLAN.md").read_text().replace(NO_UX, REAL_UX)
    )
    (untracked_dir_root / "src/widgets").mkdir()
    (untracked_dir_root / "src/widgets/Card.tsx").write_text(
        "export const Card = () => <p>New</p>;\n"
    )
    udir_head = git(untracked_dir_root, "rev-parse", "HEAD").strip()
    udir_after = write_clean_browser(untracked_dir_root, route="/account")
    write_look(untracked_dir_root, udir_head, udir_after)
    assert (
        local_ui_proof.local_ui_proof_problem(untracked_dir_root, "origin/main") is None
    )


def test_local_complete_check_supports_dirty_build_and_rejects_stale_and_deleted_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, commit_work=False)
    head = git(root, "rev-parse", "HEAD").strip()
    after = write_clean_browser(root, route="/account")
    write_look(root, head, after)
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None

    touch_after_capture(root)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "predates the latest UI edit" in problem

    deleted_root = web_change_repo(tmp_path / "del", commit_work=True)
    del_head = git(deleted_root, "rev-parse", "HEAD").strip()
    del_after = write_clean_browser(deleted_root, route="/account")
    write_look(deleted_root, del_head, del_after)
    old_ns = (
        deleted_root / ".hard-eng/browser/after-390.json"
    ).stat().st_mtime_ns - 5_000_000_000
    for path in (deleted_root / ".hard-eng/browser").glob("*.json"):
        os.utime(path, ns=(old_ns, old_ns))
    (deleted_root / "src/App.tsx").unlink()
    problem = local_ui_proof.local_ui_proof_problem(deleted_root, "origin/main")
    assert problem is not None and "predates the latest UI edit" in problem

    legacy_root = web_change_repo(tmp_path / "legacy", commit_work=True)
    (legacy_root / "src/legacy").mkdir()
    (legacy_root / "src/legacy/Hero.tsx").write_text(
        "export const H = () => <p>H</p>;\n"
    )
    commit(legacy_root, "add legacy hero")
    (legacy_root / "src/legacy/Hero.tsx").unlink()
    commit(legacy_root, "delete legacy hero")
    leg_head = git(legacy_root, "rev-parse", "HEAD").strip()
    (legacy_root / "src/App.tsx").write_text("export const App = () => <p>Edit</p>;\n")
    leg_after = write_clean_browser(legacy_root, route="/account")
    write_look(legacy_root, leg_head, leg_after)
    readme = legacy_root / "src/legacy/README.md"
    readme.write_text("# Notes\n")
    future_ns = (
        legacy_root / ".hard-eng/browser/after-390.json"
    ).stat().st_mtime_ns + 5_000_000_000
    os.utime(legacy_root / "src/legacy", ns=(future_ns, future_ns))
    assert local_ui_proof.local_ui_proof_problem(legacy_root, "origin/main") is None
    _assert_reverted_and_untracked_dirty_ui(tmp_path)


def test_local_complete_check_reads_owner_evidence_inside_pre_push_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    owner = web_change_repo(tmp_path / "owner")
    head = git(owner, "rev-parse", "HEAD").strip()
    after = write_clean_browser(owner, route="/account")
    write_look(owner, head, after)

    snapshot = tmp_path / "snap"
    git(owner, "worktree", "add", "--detach", str(snapshot), head)
    try:
        assert (
            local_ui_proof.local_ui_proof_problem(snapshot, "origin/main") is not None
        )
        monkeypatch.setenv(
            TOOL_OWNER, os.pathsep.join([str(snapshot.resolve()), str(owner.resolve())])
        )
        assert local_ui_proof.local_ui_proof_problem(snapshot, "origin/main") is None
    finally:
        git(owner, "worktree", "remove", "--force", str(snapshot))


def test_local_complete_check_validates_unchanged_pair_when_dirty_and_skips_in_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, ux=UNCHANGED_UX)
    base = git(root, "rev-parse", "origin/main").strip()
    head = git(root, "rev-parse", "HEAD").strip()
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is not None

    (root / "PLAN.md").write_text((root / "PLAN.md").read_text() + "\n")
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is not None

    for var in ("GITHUB_ACTIONS", "CI"):
        monkeypatch.setenv(var, "true")
        assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None
        monkeypatch.delenv(var)

    write_pair(root, base, head)
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None

    for side in ("before", "after"):
        write_pair(root, base, head)
        for path in (root / ".hard-eng/browser").glob(f"{side}-*.json"):
            data = json.loads(path.read_text())
            data["findings"] = [{"rule": "tap-size", "at": "btn"}]
            path.write_text(json.dumps(data))
        problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
        assert problem is not None and "tap-size" in problem

    write_pair(root, base, head, after_dirty=True)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "uncommitted changes" in problem

    (root / "src/App.tsx").write_text("export const App = () => <p>Dirty</p>;\n")
    write_pair(root, base, head, after_dirty=True)
    touch_after_capture(root)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "predates the latest UI edit" in problem


def test_local_complete_check_rejects_discarded_dirty_capture_and_allows_staged_plan_after_committed_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path)
    (root / "src/Gone.tsx").write_text("export const Gone = () => <p>Gone</p>;\n")
    commit(root, "add gone")
    (root / "src/Gone.tsx").unlink()
    commit(root, "delete gone")
    head = git(root, "rev-parse", "HEAD").strip()

    dirty_after = write_clean_browser(root, route="/account", dirty_override=True)
    write_look(root, head, dirty_after)
    (root / "PLAN.md").write_text((root / "PLAN.md").read_text() + "\n")
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "clean tree" in problem

    clean_after = write_clean_browser(root, route="/account", dirty_override=False)
    write_look(root, head, clean_after)
    git(root, "add", "PLAN.md")
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None


def _assert_unchanged_routes_and_owners(root: Path, base_plan: str) -> None:
    (root / "features/ui-b/PLAN.md").write_text(
        base_plan.replace(
            REAL_UX, UNCHANGED_UX.replace("the card at rest", "home route `/`")
        )
    )
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "names /" in problem

    for desc, expected in (
        ("/settings/ screen", "/settings/"),
        ("/settings?tab=security screen", "/settings"),
        ("/ signed out", "/"),
        ("Settings at desktop / mobile sizes", ""),
    ):
        plan_body = base_plan.replace(
            REAL_UX, UNCHANGED_UX.replace("the card at rest", desc)
        )
        assert (
            local_ui_proof._unchanged_route(
                plan_body, local_ui_proof.reference_section(plan_body)
            )
            == expected
        )

    (root / "src/settings").mkdir()
    (root / "src/settings/Card.tsx").write_text(
        "export const Card = () => <p>New</p>;\n"
    )
    for owner in ("src/settings/", "src/"):
        (root / "features/ui-b/PLAN.md").write_text(
            base_plan.replace(REAL_UX, NO_UX) + f"\nOwners: {owner}\n"
        )
        problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
        assert problem is not None and "ux_reference says N/A" in problem


def test_local_complete_check_handles_multi_plan_siblings_and_multiple_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path)
    base_plan = (root / "PLAN.md").read_text()
    (root / "PLAN.md").unlink()
    (root / "features/api").mkdir(parents=True)
    (root / "features/ui-a").mkdir(parents=True)
    (root / "features/ui-b").mkdir(parents=True)
    (root / "features/api/PLAN.md").write_text(base_plan.replace(REAL_UX, NO_UX))
    (root / "features/ui-a/PLAN.md").write_text(base_plan)
    (root / "features/ui-b/PLAN.md").write_text(
        base_plan.replace("/account", "/settings")
    )
    commit(root, "multi plan")
    base = git(root, "rev-parse", "origin/main").strip()
    head = git(root, "rev-parse", "HEAD").strip()

    first = write_clean_browser(root, name="account", route="/account")
    write_look(root, head, first)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "/settings" in problem

    second = write_clean_browser(root, name="settings", route="/settings")
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "every changed route" in problem

    write_look(root, head, second)
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None

    (root / "features/ui-b/PLAN.md").write_text(
        base_plan.replace(
            REAL_UX, UNCHANGED_UX.replace("the card at rest", "/settings screen")
        )
    )
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "unchanged pair" in problem

    write_pair(root, base, head)
    for path in (root / ".hard-eng/browser").glob("after-*.json"):
        data = json.loads(path.read_text())
        data["route"] = "/pricing"
        path.write_text(json.dumps(data))
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "/settings" in problem

    for path in (root / ".hard-eng/browser").glob("after-*.json"):
        data = json.loads(path.read_text())
        data["route"] = "/settings"
        path.write_text(json.dumps(data))
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "Before capture" in problem

    for path in (root / ".hard-eng/browser").glob("before-*.json"):
        data = json.loads(path.read_text())
        data["route"] = "/settings"
        path.write_text(json.dumps(data))
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None
    _assert_unchanged_routes_and_owners(root, base_plan)


def test_local_complete_check_detects_quoted_binary_ui_asset_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    fixture = _fixture(tmp_path, ui_paths=["src/**"])
    root = fixture.root
    (root / "src").mkdir()
    asset = root / 'src/logo"1.png'
    asset.write_bytes(b"\x89PNG\r\n\x1a\nold")
    commit(root, "base")
    git(root, "branch", "-f", "main", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", git(root, "rev-parse", "main"))
    asset.write_bytes(b"\x89PNG\r\n\x1a\nnew")
    (root / "PLAN.md").write_text(
        (root / "PLAN.md").read_text().replace(NO_UX, REAL_UX)
    )
    commit(root, "quoted binary asset")
    with pytest.raises(ValueError, match="UI evidence"):
        validate_rules(root, "origin/main", screens=True, full=True, stage="Complete")


def flutter_app_root(tmp_path: Path) -> Path:
    """A repository with one Flutter package whose screen file is not yet committed."""
    root = _fixture(tmp_path, ui_paths=["app/**"]).root
    gates = json.loads((root / "hard-eng.gates.json").read_text())
    gates["packages"] = [
        {"name": "shop", "path": "app", "language": "dart", "checks": []}
    ]
    (root / "hard-eng.gates.json").write_text(json.dumps(gates))
    (root / "app/lib/ui").mkdir(parents=True)
    (root / "app/test").mkdir(parents=True)
    (root / "app/pubspec.yaml").write_text(
        "name: shop\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    (root / "app/lib/ui/card.dart").write_text("Widget card() => Text('Old');\n")
    return root


def test_local_complete_check_validates_native_flutter_guideline_and_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = flutter_app_root(tmp_path)
    commit(root, "base")
    git(root, "branch", "-f", "main", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", git(root, "rev-parse", "main"))
    (root / "app/lib/ui/card.dart").write_text("Widget card() => Text('New');\n")
    (root / "PLAN.md").write_text(
        (root / "PLAN.md").read_text().replace(NO_UX, REAL_UX)
    )
    commit(root, "native change")
    head = git(root, "rev-parse", "HEAD").strip()

    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "meetsGuideline" in problem

    (root / "app/test/card_test.dart").write_text(GUIDELINE_TEST)
    commit(root, "guideline test")
    head = git(root, "rev-parse", "HEAD").strip()
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "Look review" in problem

    write_look(root, head, b"native-shot")
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None


def test_local_complete_check_fast_path_and_quick_import_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path)
    start = time.perf_counter()
    assert (
        local_ui_proof.local_ui_proof_problem(
            root, "origin/main", {"README.md", "src/App.test.tsx"}
        )
        is None
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50

    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "import comments\n"
        f"comments.validate_rules(__import__('pathlib').Path({str(root)!r}), 'origin/main', screens=True, full=False, stage='Complete')\n"
        "print('local_ui_proof' in sys.modules)\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    assert done.stdout.strip() == "False"


def test_push_text_checks_refuses_missing_local_ui_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import gate_runner

    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path)
    assert push_check(gate_runner, root, monkeypatch) == 1
    assert "UI evidence" in capsys.readouterr().out


DESIGN = "# Design\n\n## Overview\nNavy primary.\n"
LISTED_SURFACES = [
    "/other, /account and /c/[id]",
    "/other, /account, and /c/[id]",
    "/other, /account, /c/[id]",
]


def surface_ux(surface: str) -> str:
    return REAL_UX.replace("Existing — /account,", f"Existing — {surface},")


@pytest.mark.parametrize("surface", LISTED_SURFACES)
def test_local_complete_check_accepts_a_capture_of_any_listed_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, ux=surface_ux(surface), design=DESIGN)
    head = git(root, "rev-parse", "HEAD").strip()
    after = write_clean_browser(root, route="/account")
    write_look(root, head, after, design_doc=look.design_hash(root))
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None


def test_local_complete_check_names_every_listed_route_for_an_unlisted_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, ux=surface_ux("/one, /two and /c/[id]"))
    write_clean_browser(root, route="/account")
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "/account" in problem
    assert all(route in problem for route in ("/one", "/two", "/c/[id]"))


def test_local_complete_check_refuses_a_one_route_surface_capture_of_another_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, ux=surface_ux("/one"))
    write_clean_browser(root, route="/account")
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "names /one;" in problem


def test_local_complete_check_refuses_a_looked_at_capture_of_an_unlisted_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = web_change_repo(tmp_path, design=DESIGN)
    head = git(root, "rev-parse", "HEAD").strip()
    listed = write_clean_browser(root, name="after", route="/account")
    stray = write_clean_browser(root, name="stray", route="/other")
    write_look(root, head, listed, design_doc=look.design_hash(root))
    assert local_ui_proof.local_ui_proof_problem(root, "origin/main") is None
    write_look(root, head, stray, design_doc=look.design_hash(root))
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "stray-390.png" in problem
    assert "capture the changed screen" in problem
