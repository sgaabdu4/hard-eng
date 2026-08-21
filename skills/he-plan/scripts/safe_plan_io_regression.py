#!/usr/bin/env python3
"""Focused descriptor/CAS/artifact proof for PLAN lifecycle storage."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

STATE_SCRIPTS = Path(__file__).resolve().parents[2] / "he/scripts"
GIT_ENV_SCRIPTS = Path(__file__).resolve().parents[2] / "deterministic-checks/scripts"
for _path in (STATE_SCRIPTS, GIT_ENV_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import plan_state
import safe_plan_io
import setup_state
from git_env import scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())

STATE_PATH = STATE_SCRIPTS / "plan_state.py"

Failure = Callable[[str], NoReturn]


def _fail(message: str) -> NoReturn:
    raise SystemExit(message)


def check_ancestor_swap(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve() / "repo"
        original_parent = repo / "features/loop"
        moved_parent = repo / "features/loop-original"
        outside_parent = Path(directory).resolve() / "outside"
        original_parent.mkdir(parents=True)
        outside_parent.mkdir()
        plan = original_parent / "PLAN.md"
        outside = outside_parent / "PLAN.md"
        plan.write_bytes(b"expected")
        outside.write_bytes(b"outside")
        original_read = safe_plan_io._read_at
        swapped = False

        def swapping_read(parent, name):
            nonlocal swapped
            result = original_read(parent, name)
            if not swapped:
                swapped = True
                os.rename(original_parent, moved_parent)
                original_parent.symlink_to(outside_parent, target_is_directory=True)
            return result

        safe_plan_io._read_at = swapping_read
        try:
            safe_plan_io.replace_if_unchanged(repo, Path("features/loop/PLAN.md"), b"expected", 0o644, b"replacement")
        finally:
            safe_plan_io._read_at = original_read
        if outside.read_bytes() != b"outside":
            fail("ancestor swap redirected PLAN replacement outside repository")
        if (moved_parent / "PLAN.md").read_bytes() != b"replacement":
            fail("descriptor-relative replacement lost the opened PLAN owner")


def check_init_preimage(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        setup_state.seed_receipt_for_fixture(repo)
        initialized = subprocess.run(
            [sys.executable, str(STATE_PATH), "init", "--repo", str(repo), "--feature-slug", "fresh-loop"],
            check=False,
            capture_output=True,
            text=True,
        )
        relative = Path("features/fresh-loop/PLAN.md")
        plan = repo / relative
        if initialized.returncode != 0 or not plan.is_file():
            fail(f"init did not create no-follow parents: {initialized.stderr}")
        before, mode = safe_plan_io.read_snapshot(repo, relative)
        for expected, expected_mode in ((before, mode ^ 0o100), (before + b"editor-drift", mode)):
            try:
                safe_plan_io.replace_if_unchanged(repo, relative, expected, expected_mode, b"replacement")
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("byte/mode preimage drift did not fail")
            if plan.read_bytes() != before:
                fail("preimage failure mutated PLAN")


def check_exchange_editor_save(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        relative = Path("features/loop/PLAN.md")
        plan = repo / relative
        plan.parent.mkdir(parents=True)
        plan.write_bytes(b"expected")
        original_exchange = safe_plan_io._exchange
        injected = False

        def editor_then_exchange(parent, left, right):
            nonlocal injected
            if not injected:
                injected = True
                descriptor = os.open(right, os.O_WRONLY | os.O_TRUNC, dir_fd=parent)
                try:
                    os.write(descriptor, b"editor-save")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            original_exchange(parent, left, right)

        safe_plan_io._exchange = editor_then_exchange
        try:
            try:
                safe_plan_io.replace_if_unchanged(repo, relative, b"expected", 0o644, b"replacement")
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("editor save immediately before exchange was overwritten")
        finally:
            safe_plan_io._exchange = original_exchange
        if plan.read_bytes() != b"editor-save":
            fail("atomic rollback did not preserve editor bytes")
        if tuple(plan.parent.glob(".hard-eng-*")):
            fail("rejected exchange leaked hidden replacement")


def check_rollback_failure_recovery(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        relative = Path("features/loop/PLAN.md")
        plan = repo / relative
        plan.parent.mkdir(parents=True)
        plan.write_bytes(b"expected")
        original_exchange = safe_plan_io._exchange
        calls = 0

        def editor_then_failed_rollback(parent, left, right):
            nonlocal calls
            calls += 1
            if calls == 1:
                descriptor = os.open(right, os.O_WRONLY | os.O_TRUNC, dir_fd=parent)
                try:
                    os.write(descriptor, b"editor-save")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                original_exchange(parent, left, right)
            else:
                raise OSError("injected rollback failure")

        safe_plan_io._exchange = editor_then_failed_rollback
        try:
            try:
                safe_plan_io.replace_if_unchanged(repo, relative, b"expected", 0o644, b"replacement")
            except safe_plan_io.SafePlanIOError as error:
                marker = "recover concurrent PLAN bytes from sibling "
                if marker not in str(error):
                    fail("rollback failure omitted recovery location")
                recovery = plan.parent / str(error).split(marker, 1)[1]
            else:
                fail("injected rollback failure unexpectedly succeeded")
        finally:
            safe_plan_io._exchange = original_exchange
        if plan.read_bytes() != b"replacement":
            fail("rollback-failure target state was not explicit")
        if not recovery.is_file() or recovery.read_bytes() != b"editor-save":
            fail("rollback failure destroyed concurrent editor bytes")
        if recovery.stat().st_mode & 0o077:
            fail("rollback recovery sibling was not private")
        recovery.unlink()


def check_write_failure_cleanup(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        original_write = safe_plan_io.os.write
        safe_plan_io.os.write = lambda *_: (_ for _ in ()).throw(OSError("injected"))
        try:
            try:
                safe_plan_io.create_new(repo, Path("features/loop/PLAN.md"), b"content", 0o644)
            except OSError:
                pass
            else:
                fail("injected write failure unexpectedly succeeded")
        finally:
            safe_plan_io.os.write = original_write
        if tuple(repo.rglob(".hard-eng-*")):
            fail("write failure leaked hidden temporary")


def check_gitlinks(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        repo, child = root / "repo", root / "child"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "init", "-q", str(child)], check=True)
        tracked = child / "tracked.txt"
        tracked.write_text("clean", encoding="utf-8")
        subprocess.run(["git", "-C", str(child), "add", "tracked.txt"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(child),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "initial",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "protocol.file.allow=always",
                "-C",
                str(repo),
                "submodule",
                "add",
                "-q",
                str(child),
                "linked",
            ],
            check=True,
        )
        clean = safe_plan_io.repository_artifact(repo)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qam",
                "add gitlink",
            ],
            check=True,
        )
        if safe_plan_io.delivered_head_artifact(repo, clean) != clean:
            fail("committed clean gitlink is incompatible with green")
        linked_file = repo / "linked/tracked.txt"
        linked_file.write_text("dirty", encoding="utf-8")
        try:
            safe_plan_io.repository_artifact(repo)
        except safe_plan_io.SafePlanIOError:
            pass
        else:
            fail("dirty gitlink content received green artifact")
        subprocess.run(["git", "-C", str(repo / "linked"), "checkout", "-q", "--", "tracked.txt"], check=True)
        linked_file.write_text("new-head", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo / "linked"), "add", "tracked.txt"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo / "linked"),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "advance",
            ],
            check=True,
        )
        try:
            safe_plan_io.repository_artifact(repo)
        except safe_plan_io.SafePlanIOError:
            pass
        else:
            fail("gitlink HEAD/index mismatch received green artifact")


def check_ambiguous_and_special_entries(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        conflict = repo / "conflict.txt"
        conflict.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "conflict.txt"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "base",
            ],
            check=True,
        )
        blobs = []
        for value in (b"ours\n", b"theirs\n"):
            result = subprocess.run(
                ["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input=value, capture_output=True, check=True
            )
            blobs.append(result.stdout.strip().decode("ascii"))
        subprocess.run(["git", "-C", str(repo), "update-index", "--force-remove", "conflict.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "update-index", "--index-info"],
            input=(f"100644 {blobs[0]} 2\tconflict.txt\n100644 {blobs[1]} 3\tconflict.txt\n"),
            text=True,
            check=True,
        )
        try:
            safe_plan_io.repository_artifact(repo)
        except safe_plan_io.SafePlanIOError:
            pass
        else:
            fail("multi-stage index entry received a green artifact")

    if hasattr(os, "mkfifo"):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            special = repo / "special"
            special.write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "special"], check=True)
            special.unlink()
            os.mkfifo(special)
            try:
                safe_plan_io.repository_artifact(repo)
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("special worktree entry received a green artifact")


def check_plan_lock(state, fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        plan = root / "features/lean-loop/PLAN.md"
        marker = root / "acquired"
        plan.parent.mkdir(parents=True)
        plan.write_text("fixture", encoding="utf-8")
        code = (
            "import pathlib,sys;"
            f"sys.path.insert(0,{str(STATE_PATH.parent)!r});"
            "import plan_state;"
            f"r=pathlib.Path({str(root)!r});p=pathlib.Path({str(plan)!r});"
            f"m=pathlib.Path({str(marker)!r});"
            "\nwith plan_state.plan_lock(r,p): m.write_text('yes',encoding='utf-8')"
        )
        with state.plan_lock(root, plan):
            process = subprocess.Popen(
                [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            time.sleep(0.2)
            if process.poll() is not None or marker.exists():
                fail("per-plan lock did not serialize a concurrent writer")
        _, error = process.communicate(timeout=5)
        if process.returncode != 0 or marker.read_text(encoding="utf-8") != "yes":
            fail(f"serialized writer did not resume: {error}")


def check_plan_collection(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        first = repo / "features/first/PLAN.md"
        second = repo / "features/second/PLAN.md"
        first.parent.mkdir(parents=True)
        second.parent.mkdir(parents=True)
        first.write_text(plan_state.template("first", "first-00000000"), encoding="utf-8")
        second.write_text(plan_state.template("second", "second-00000000"), encoding="utf-8")
        try:
            plan_state.resolve_plan(repo, None)
        except plan_state.PlanError as error:
            if "multiple active" not in str(error) or "first" not in str(error) or "second" not in str(error):
                fail(f"multiple-plan error omitted paths: {error}")
        else:
            fail("implicit resolution accepted multiple active Feature Briefs")
        try:
            selected = plan_state.resolve_plan(repo, str(first))
        except plan_state.PlanError as error:
            fail(f"explicit PLAN path did not disambiguate multiple active Feature Briefs: {error}")
        else:
            if selected != first.resolve():
                fail(f"explicit PLAN path resolved to the wrong plan: {selected}")
        second.write_text(
            second.read_text(encoding="utf-8").replace(
                "- lifecycle_status = planning", "- lifecycle_status = cancelled"
            ),
            encoding="utf-8",
        )
        extra = first.parent / "notes/detail.md"
        extra.parent.mkdir()
        extra.write_text("extra\n", encoding="utf-8")
        try:
            plan_state.resolve_plan(repo, str(first))
        except plan_state.PlanError as error:
            if "detail.md" not in str(error):
                fail(f"extra-Markdown error omitted path: {error}")
        else:
            fail("active feature accepted a second Markdown document")


def check_index_transition_stability(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        baseline = repo / "README.md"
        baseline.write_text("baseline\n", encoding="utf-8")
        attributes = repo / ".gitattributes"
        attributes.write_text("*.txt text eol=lf\n", encoding="utf-8")
        filtered = repo / "filtered.txt"
        filtered.write_bytes(b"filtered\r\n")
        delivery = repo / "delivery.txt"
        delivery.write_text("A\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "README.md", ".gitattributes", "filtered.txt", "delivery.txt"], check=True
        )
        commit = [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
        ]
        subprocess.run([*commit, "baseline"], check=True)
        filtered.write_bytes(b"filtered\r\n")
        filtered_green = safe_plan_io.repository_artifact(repo)
        if safe_plan_io.delivered_head_artifact(repo, filtered_green) != filtered_green:
            fail("Git clean-filtered working bytes are incompatible with HEAD")

        lifecycle = repo / "features/loop/PLAN.md"
        lifecycle.parent.mkdir(parents=True)
        lifecycle.write_text("canonical lifecycle state\n", encoding="utf-8")
        if safe_plan_io.repository_artifact(repo) != filtered_green:
            fail("canonical PLAN changed the product artifact")
        proof_media = repo.parent / "visualizations/ux-reference.png"
        proof_media.parent.mkdir()
        proof_media.write_bytes(b"local visual proof\n")
        if safe_plan_io.repository_artifact(repo) != filtered_green:
            fail("outside-repository lifecycle media changed the product artifact")
        if safe_plan_io.delivered_head_artifact(repo, filtered_green) != filtered_green:
            fail("outside-repository lifecycle media was treated as delivery content")
        misplaced_media = lifecycle.with_name("ux-reference.png")
        misplaced_media.write_bytes(b"misplaced visual proof\n")
        if safe_plan_io.repository_artifact(repo) == filtered_green:
            fail("repository-local feature media was hidden from the product artifact")
        misplaced_media.unlink()
        product_media = repo / "public/product.png"
        product_media.parent.mkdir()
        product_media.write_bytes(b"product asset\n")
        if safe_plan_io.repository_artifact(repo) == filtered_green:
            fail("product media was excluded from the product artifact")
        product_media.unlink()
        product_media.parent.rmdir()
        proof_media.unlink()
        proof_media.parent.rmdir()
        lifecycle.unlink()

        delivery.write_text("C\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "delivery.txt"], check=True)
        delivery.write_text("B\n", encoding="utf-8")
        green = safe_plan_io.repository_artifact(repo)
        subprocess.run([*commit, "partial staged delivery"], check=True)
        if safe_plan_io.repository_artifact(repo) != green:
            fail("partial commit repro did not preserve green worktree artifact")
        try:
            safe_plan_io.delivered_head_artifact(repo, green)
        except safe_plan_io.SafePlanIOError:
            pass
        else:
            fail("partial-stage commit passed delivered HEAD assertion")
        original_artifact = safe_plan_io.repository_artifact

        def save_stale_head_after_green_hash(target):
            result = original_artifact(target)
            delivery.write_text("C\n", encoding="utf-8")
            return result

        safe_plan_io.repository_artifact = save_stale_head_after_green_hash
        try:
            try:
                safe_plan_io.delivered_head_artifact(repo, green)
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("inter-call save back to stale HEAD bypassed delivered assertion")
        finally:
            safe_plan_io.repository_artifact = original_artifact
        delivery.write_text("B\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "delivery.txt"], check=True)
        subprocess.run([*commit, "complete delivery"], check=True)
        if safe_plan_io.delivered_head_artifact(repo, green) != green:
            fail("complete commit did not match green artifact")

        executable = repo / "new-tool"
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        executable.chmod(0o755)
        link = repo / "new-tool-link"
        link.symlink_to("new-tool")
        untracked = safe_plan_io.repository_artifact(repo)
        subprocess.run(["git", "-C", str(repo), "add", "new-tool", "new-tool-link"], check=True)
        if safe_plan_io.repository_artifact(repo) != untracked:
            fail("staging unchanged new files changed the green artifact")
        subprocess.run([*commit, "add unchanged files"], check=True)
        if safe_plan_io.repository_artifact(repo) != untracked:
            fail("committing unchanged new files changed the green artifact")
        if safe_plan_io.delivered_head_artifact(repo, untracked) != untracked:
            fail("committed mode/symlink artifact is incompatible with green")

        executable.unlink()
        link.unlink()
        deleted = safe_plan_io.repository_artifact(repo)
        subprocess.run(["git", "-C", str(repo), "add", "-u"], check=True)
        if safe_plan_io.repository_artifact(repo) != deleted:
            fail("staging unchanged deletions changed the green artifact")
        subprocess.run([*commit, "delete unchanged files"], check=True)
        if safe_plan_io.repository_artifact(repo) != deleted:
            fail("committing unchanged deletions changed the green artifact")
        if safe_plan_io.delivered_head_artifact(repo, deleted) != deleted:
            fail("committed deletion artifact is incompatible with green")


def check_clean_index_blob_reuse(fail: Failure) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        for index in range(32):
            (repo / f"clean-{index}.txt").write_text(f"clean {index}\n", encoding="utf-8")
        (repo / "clean-\nname.txt").write_text("newline path\n", encoding="utf-8")
        (repo / "clean-link").symlink_to("clean-0.txt")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "baseline",
            ],
            check=True,
        )
        original_blob_id = safe_plan_io._git_blob_id
        calls = []

        def counting_blob_id(*args, **kwargs):
            calls.append((args, kwargs))
            return original_blob_id(*args, **kwargs)

        safe_plan_io._git_blob_id = counting_blob_id
        try:
            safe_plan_io.repository_artifact(repo)
            if calls:
                fail("clean tracked files launched per-file Git hashing")
            (repo / "clean-0.txt").write_text("modified\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            safe_plan_io.repository_artifact(repo)
            if len(calls) != 2:
                fail(f"artifact hashing did not scale with changed files: expected 2 Git hashes, got {len(calls)}")
            calls.clear()
            subprocess.run(["git", "-C", str(repo), "update-index", "--assume-unchanged", "clean-1.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "update-index", "--skip-worktree", "clean-2.txt"], check=True)
            (repo / "clean-1.txt").write_text("assumed\n", encoding="utf-8")
            (repo / "clean-2.txt").write_text("skipped\n", encoding="utf-8")
            safe_plan_io.repository_artifact(repo)
            if len(calls) != 4:
                fail(f"artifact hashing trusted hidden index flags: expected 4 Git hashes, got {len(calls)}")
        finally:
            safe_plan_io._git_blob_id = original_blob_id


if __name__ == "__main__":
    check_ancestor_swap(_fail)
    check_init_preimage(_fail)
    check_exchange_editor_save(_fail)
    check_rollback_failure_recovery(_fail)
    check_write_failure_cleanup(_fail)
    check_gitlinks(_fail)
    check_ambiguous_and_special_entries(_fail)
    check_plan_collection(_fail)
    check_index_transition_stability(_fail)
    check_clean_index_blob_reuse(_fail)
    print("safe-plan-io-regression: PASS")
