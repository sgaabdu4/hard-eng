"""Focused UX-reference target and linked-worktree regression checks."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env


def png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


VALID_PNG = png_bytes(640, 360, (30, 90, 70))
BASELINE_PNG = png_bytes(640, 360, (245, 245, 240))
SMALL_PNG = png_bytes(1, 1, (30, 90, 70))
AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."
APPROVAL_CONTEXT = ("--allowed-action", "build-and-verify")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_static_preview_receipt(
    repo: Path,
    target: Path,
    baseline: Path,
    *,
    source_paths: tuple[str, ...] = ("DESIGN.md", "src/theme.css"),
    provenance_route: str = "/admin/example",
    width: int = 640,
    height: int = 360,
) -> Path:
    target_digest = digest(target)
    baseline_digest = digest(baseline)
    binding = {
        "revision": "fixture-revision",
        "environment": "local-preview",
        "scenario_id": "ux-reference",
        "run_id": "fixture-run",
        "attempt_id": "fixture-attempt",
    }
    source_bindings = [{"path": value, "sha256": digest(repo / value)} for value in source_paths]
    receipt = {
        "schema_version": 4,
        "field_source_class": "caller_asserted",
        "proof_target": {
            "id": "ux-reference-screen",
            "surface": "/admin/example",
            "visible_claims": {"preview-screen": "The proposed change is visible on the real app screen."},
            "forbidden_visible_states": ["invented standalone dashboard"],
        },
        "accepted_requirements": {
            "source": "fixture:user-request",
            "items": {"preview-screen": "The proposed change is visible on the real app screen."},
        },
        "prototype": {
            "surface_kind": "existing",
            "production_sources": source_bindings,
            "render_provenance": {
                "kind": "running-product-static-preview",
                "presentation_label": "static preview on current app screen",
                "route": provenance_route,
            },
            "reference_artifacts": [
                {
                    "kind": "screenshot",
                    "path": str(baseline),
                    "sha256": baseline_digest,
                    "environment": "production",
                    "revision": "baseline-revision",
                    "surface": "/admin/example",
                    "dimensions": {"width": 640, "height": 360},
                    "review": {
                        "field_source_class": "independently_measured",
                        "method": "actual-media-inspection",
                        "conclusion": "PASS",
                        "observed_subject": "the current app screen before the proposed change",
                    },
                }
            ],
        },
        "binding": binding,
        "evidence": {
            "automated": {"field_source_class": "caller_asserted", "required": False, "status": "N/A"},
            "persisted_state": {"field_source_class": "caller_asserted", "required": False, "status": "N/A"},
            "deployment": {"field_source_class": "caller_asserted", "required": False, "status": "N/A"},
            "visual": {
                "field_source_class": "independently_measured",
                "purpose": "existing-ui-static-preview",
                "required": True,
                "requested": True,
                "produced": True,
                "status": "PASS",
                "delivery_artifact_sha256s": [target_digest],
                "artifacts": [
                    {
                        **binding,
                        "proof_target_id": "ux-reference-screen",
                        "successful_test_attempt": True,
                        "successful_test_attempt_source": "trusted_system_readback",
                        "kind": "screenshot",
                        "path": str(target),
                        "sha256": target_digest,
                        "dimensions": {"width": width, "height": height},
                        "viewport": {"width": width, "height": height},
                        "device": "desktop",
                        "required_step_ids": ["preview-screen"],
                    }
                ],
                "review": {
                    "field_source_class": "independently_measured",
                    "method": "actual-media-inspection",
                    "conclusion": "PASS",
                    "artifacts": [
                        {
                            "field_source_class": "independently_measured",
                            "artifact_sha256": target_digest,
                            "proof_target_id": "ux-reference-screen",
                            "conclusion": "PASS",
                            "subject_match": True,
                            "observed_subject": "the proposed change on the current app screen",
                            "requirements_match": True,
                            "reference_match": True,
                            "reference_sha256s": [baseline_digest],
                            "preserved_reference_anchors": ["page shell", "navigation", "existing form"],
                            "presentation_label": "static preview on current app screen",
                            "required_steps": [
                                {"id": "preview-screen", "artifact_sha256": target_digest, "frame": "full image"}
                            ],
                            "observed_start_state": "current app screen",
                            "observed_final_state": "current app screen with proposed static data",
                            "authentication_or_error_screens": [],
                            "irrelevant_or_stalled_sections": [],
                            "layout_findings": {"overflow": [], "clipping": [], "spacing": [], "responsive": []},
                        }
                    ],
                },
            },
        },
        "overall_status": "PASS",
    }
    receipt_path = Path(f"{target}.visual-review.json")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path


def check_targets(state, git_repo: Callable[[Path], None], fail: Callable[[str], None]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        repo = root / "project"
        git_repo(repo)
        media = root / "visualizations"
        media.mkdir()
        (media / "mock.txt").write_text("not an image", encoding="utf-8")
        (media / "fake-mock.png").write_bytes(b"\x89PNG mock")
        (media / "real-mock.png").write_bytes(VALID_PNG)
        (media / "baseline.png").write_bytes(BASELINE_PNG)
        (media / "unreviewed.png").write_bytes(VALID_PNG)
        (media / "small.png").write_bytes(SMALL_PNG)
        (media / "wrong-route.png").write_bytes(VALID_PNG)
        (media / "source-mismatch.png").write_bytes(VALID_PNG)
        (media / "existing-as-new.png").write_bytes(VALID_PNG)
        (media / "safe.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360"><rect width="640" height="360" fill="#000"/></svg>',
            encoding="utf-8",
        )
        (media / "script.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8"
        )
        (media / "external.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.invalid/pixel.png"/></svg>',
            encoding="utf-8",
        )
        (media / "event.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', encoding="utf-8"
        )
        (media / "style.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(https://example.invalid/fill.svg)"/></svg>',
            encoding="utf-8",
        )
        (media / "paint.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(https://example.invalid/fill.svg)"/></svg>',
            encoding="utf-8",
        )
        (media / "local-paint.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">'
            '<defs><linearGradient id="paint"><stop offset="0" stop-color="#000"/>'
            '<stop offset="1" stop-color="#fff"/></linearGradient></defs>'
            '<rect width="640" height="360" fill="url(#paint)"/></svg>',
            encoding="utf-8",
        )
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        base = _filled(state.template("lean-loop", "lean-loop-test"))
        (repo / "docs").mkdir()
        (repo / "src").mkdir()
        (repo / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (repo / "src/theme.css").write_text(":root { --surface: white; }\n", encoding="utf-8")
        (repo / "src/other.css").write_text(":root { --surface: ivory; }\n", encoding="utf-8")
        (repo / "docs/real-mock.png").write_bytes(VALID_PNG)
        baseline = media / "baseline.png"
        for name in ("real-mock.png",):
            write_static_preview_receipt(repo, media / name, baseline)
        write_static_preview_receipt(repo, media / "small.png", baseline, width=1, height=1)
        write_static_preview_receipt(
            repo, media / "wrong-route.png", baseline, provenance_route="/invented-combined-dashboard"
        )
        write_static_preview_receipt(repo, media / "source-mismatch.png", baseline)
        mislabeled_receipt = write_static_preview_receipt(repo, media / "existing-as-new.png", baseline)
        mislabeled = json.loads(mislabeled_receipt.read_text(encoding="utf-8"))
        mislabeled["evidence"]["visual"]["purpose"] = "new-ui-concept"
        mislabeled_receipt.write_text(json.dumps(mislabeled), encoding="utf-8")
        cases = (
            ("docs/mock.png", "DESIGN.md + src/theme.css", False),
            ("accepted modal layout per chat", "DESIGN.md + src/theme.css", False),
            ("docs/mock.txt", "DESIGN.md + src/theme.css", False),
            ("docs/fake-mock.png", "DESIGN.md + src/theme.css", False),
            ("https://example.invalid/mock", "DESIGN.md + src/theme.css", False),
            ("https://example.invalid/mock.png", "DESIGN.md + src/theme.css", False),
            (str(media / "real-mock.png"), "n/a", False),
            (str(media / "real-mock.png"), "DESIGN.md", False),
            (str(media / "real-mock.png"), f"DESIGN.md + {repo / 'src/theme.css'}", False),
            ("docs/real-mock.png", "DESIGN.md + docs/real-mock.png", False),
            (str(media / "real-mock.png"), "DESIGN.md + src/missing.css", False),
            (str(media / "mock.txt"), "DESIGN.md + src/theme.css", False),
            (str(media / "fake-mock.png"), "DESIGN.md + src/theme.css", False),
            (str(media / "unreviewed.png"), "DESIGN.md + src/theme.css", False),
            (str(media / "small.png"), "DESIGN.md + src/theme.css", False),
            (str(media / "wrong-route.png"), "DESIGN.md + src/theme.css", False),
            (str(media / "source-mismatch.png"), "DESIGN.md + src/other.css", False),
            (str(media / "existing-as-new.png"), "DESIGN.md + src/theme.css", False),
            (str(media / "script.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "external.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "event.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "style.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "paint.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "local-paint.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "safe.svg"), "DESIGN.md + src/theme.css", False),
            (str(media / "real-mock.png"), "DESIGN.md + src/theme.css", True),
        )
        for value, sources, expected in cases:
            text = base.replace("- ux_reference = n/a", f"- ux_reference = {value}").replace(
                "- ux_reference_sources = n/a", f"- ux_reference_sources = {sources}"
            )
            plan.write_text(text, encoding="utf-8")
            approved = subprocess.run(
                [
                    sys.executable,
                    str(STATE_PATH),
                    "approve",
                    "--repo",
                    str(repo),
                    "--plan",
                    str(plan),
                    "--expect-token",
                    state.token_for(text),
                    "--approval-reply",
                    AUTONOMOUS_DIRECTIVE,
                    *APPROVAL_CONTEXT,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if (approved.returncode == 0) != expected:
                fail(f"ux_reference target rule failed for: {value} from {sources}: {approved.stderr}")
            if not expected and not approved.stderr:
                fail(f"ux_reference rejection lacks guidance: {value}")


def check_linked_worktree(state, git_repo: Callable[[Path], None], fail: Callable[[str], None]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        repo = root / "project"
        worktree = root / "project-worktree"
        media = root / "visualizations/ux-reference.png"
        media.parent.mkdir()
        media.write_bytes(VALID_PNG)
        baseline = root / "visualizations/baseline.png"
        baseline.write_bytes(BASELINE_PNG)
        git_repo(repo)
        (repo / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src/theme.css").write_text(":root { --surface: white; }\n", encoding="utf-8")
        write_static_preview_receipt(repo, media, baseline)
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        brief = (
            _filled(state.template("lean-loop", "linked-worktree-test"))
            .replace("- ux_reference = n/a", f"- ux_reference = {media}")
            .replace("- ux_reference_sources = n/a", "- ux_reference_sources = DESIGN.md + src/theme.css")
        )
        plan.write_text(brief, encoding="utf-8")
        subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), "add", "."], check=True, env=git_env()
        )
        subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
            env=git_env(),
        )
        subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-qb",
                "fixture/ux-reference",
                str(worktree),
            ],
            check=True,
            env=git_env(),
        )
        worktree_plan = worktree / "features/lean-loop/PLAN.md"
        validated = subprocess.run(
            [sys.executable, str(STATE_PATH), "validate", "--repo", str(worktree), "--plan", str(worktree_plan)],
            check=False,
            capture_output=True,
            text=True,
        )
        expected_markdown = f"ux_reference_markdown=![UX reference](<{media}>)"
        if validated.returncode != 0 or expected_markdown not in validated.stdout:
            fail(
                "fresh linked-worktree validation did not emit renderable absolute "
                f"Markdown: {validated.stdout} {validated.stderr}"
            )
        worktree_alias = root / "project-worktree-alias"
        worktree_alias.symlink_to(worktree, target_is_directory=True)
        aliased = subprocess.run(
            [
                sys.executable,
                str(STATE_PATH),
                "validate",
                "--repo",
                str(worktree_alias),
                "--plan",
                str(worktree_alias / "features/lean-loop/PLAN.md"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if aliased.returncode != 0:
            fail(f"aliased worktree root rejected its absolute PLAN path: {aliased.stderr}")
        approved = subprocess.run(
            [
                sys.executable,
                str(STATE_PATH),
                "approve",
                "--repo",
                str(worktree),
                "--plan",
                str(worktree_plan),
                "--expect-token",
                state.token_for(brief),
                "--approval-reply",
                AUTONOMOUS_DIRECTIVE,
                *APPROVAL_CONTEXT,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if approved.returncode != 0:
            fail(f"fresh linked-worktree approval failed: {approved.stderr}")


def _filled(text: str) -> str:
    replacements = {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": ("## Material decisions\n- Existing policy remains canonical."),
        "- ux_reference = TBD": "- ux_reference = n/a",
        "- ux_reference_sources = TBD": "- ux_reference_sources = n/a",
        "## Acceptance examples\n- TBD": (
            "## Acceptance examples\n- Given an eligible user, when they act, then the result is visible."
        ),
        "## Affected canonical areas\n- TBD": ("## Affected canonical areas\n- Existing command owner and route."),
        "- rollback = TBD": "- rollback = disable the route and preserve stored state.",
        "## Vertical slices\n- S-1 = TBD; depends_on = none\n- proof = TBD": (
            "## Vertical slices\n"
            "- S-1 = command to stored result to visible response.\n"
            "- proof = focused behavior test."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text
