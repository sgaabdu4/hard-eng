#!/usr/bin/env python3
"""Focused descriptor/CAS/artifact proof for PLAN lifecycle storage."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


STATE_SCRIPTS = Path(__file__).resolve().parents[2] / "he/scripts"
if str(STATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(STATE_SCRIPTS))

import safe_plan_io

STATE_PATH = STATE_SCRIPTS / "plan_state.py"


def check_ancestor_swap(fail) -> None:
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
            safe_plan_io.replace_if_unchanged(
                repo, Path("features/loop/PLAN.md"), b"expected", 0o644, b"replacement"
            )
        finally:
            safe_plan_io._read_at = original_read
        if outside.read_bytes() != b"outside":
            fail("ancestor swap redirected PLAN replacement outside repository")
        if (moved_parent / "PLAN.md").read_bytes() != b"replacement":
            fail("descriptor-relative replacement lost the opened PLAN owner")


def check_init_preimage(fail) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        initialized = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "init", "--repo", str(repo),
                "--feature-slug", "fresh-loop",
            ],
            check=False, capture_output=True, text=True,
        )
        relative = Path("features/fresh-loop/PLAN.md")
        plan = repo / relative
        if initialized.returncode != 0 or not plan.is_file():
            fail(f"init did not create no-follow parents: {initialized.stderr}")
        before, mode = safe_plan_io.read_snapshot(repo, relative)
        for expected, expected_mode in (
            (before, mode ^ 0o100),
            (before + b"editor-drift", mode),
        ):
            try:
                safe_plan_io.replace_if_unchanged(
                    repo, relative, expected, expected_mode, b"replacement"
                )
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("byte/mode preimage drift did not fail")
            if plan.read_bytes() != before:
                fail("preimage failure mutated PLAN")


def check_exchange_editor_save(fail) -> None:
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
                safe_plan_io.replace_if_unchanged(
                    repo, relative, b"expected", 0o644, b"replacement"
                )
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


def check_rollback_failure_recovery(fail) -> None:
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
                safe_plan_io.replace_if_unchanged(
                    repo, relative, b"expected", 0o644, b"replacement"
                )
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
        recovery.unlink()


def check_archive_cas_race(fail) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        relative = Path("features/loop/PLAN.md")
        plan = repo / relative
        plan.parent.mkdir(parents=True)
        plan.write_bytes(b"expected")
        archive_name = "PLAN.legacy-v4.fixture.md"
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
                safe_plan_io.archive_then_replace(
                    repo, relative, b"expected", 0o644, archive_name, b"replacement"
                )
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("archive migration race unexpectedly succeeded")
        finally:
            safe_plan_io._exchange = original_exchange
        if plan.read_bytes() != b"editor-save":
            fail("archive race did not preserve concurrent PLAN")
        if (plan.parent / archive_name).exists():
            fail("failed migration retained invocation-created archive")

        plan.write_bytes(b"expected")
        archive = plan.parent / archive_name
        archive.write_bytes(b"expected")
        safe_plan_io._exchange = editor_then_exchange
        injected = False
        try:
            try:
                safe_plan_io.archive_then_replace(
                    repo, relative, b"expected", 0o644, archive_name, b"replacement"
                )
            except safe_plan_io.SafePlanIOError:
                pass
            else:
                fail("pre-existing archive race unexpectedly succeeded")
        finally:
            safe_plan_io._exchange = original_exchange
        if archive.read_bytes() != b"expected":
            fail("failed migration removed pre-existing retry archive")

        archive.unlink()
        plan.write_bytes(b"expected")
        injected = False
        original_rename = safe_plan_io.os.rename
        replaced_archive = False

        def concurrent_archive_then_rename(source, destination, *args, **kwargs):
            nonlocal replaced_archive
            if source == archive_name and not replaced_archive:
                replaced_archive = True
                parent = kwargs["src_dir_fd"]
                concurrent = ".concurrent-archive"
                descriptor = os.open(
                    concurrent, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644,
                    dir_fd=parent,
                )
                try:
                    os.write(descriptor, b"concurrent-archive")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                os.replace(
                    concurrent, archive_name,
                    src_dir_fd=parent, dst_dir_fd=parent,
                )
            return original_rename(source, destination, *args, **kwargs)

        safe_plan_io._exchange = editor_then_exchange
        safe_plan_io.os.rename = concurrent_archive_then_rename
        try:
            try:
                safe_plan_io.archive_then_replace(
                    repo, relative, b"expected", 0o644, archive_name, b"replacement"
                )
            except safe_plan_io.SafePlanIOError as error:
                marker = "concurrent migration archive preserved at sibling "
                if marker not in str(error):
                    fail("archive race omitted recovery location")
                recovery = plan.parent / str(error).split(marker, 1)[1]
            else:
                fail("concurrent archive replacement unexpectedly succeeded")
        finally:
            safe_plan_io._exchange = original_exchange
            safe_plan_io.os.rename = original_rename
        if plan.read_bytes() != b"editor-save":
            fail("concurrent archive race lost editor PLAN")
        if not recovery.is_file() or recovery.read_bytes() != b"concurrent-archive":
            fail("concurrent archive bytes were not preserved at recovery location")
        recovery.unlink()

        plan.write_bytes(b"expected")
        injected = False
        original_link = safe_plan_io.os.link
        replaced_after_link = False

        def replace_archive_after_link(source, destination, *args, **kwargs):
            nonlocal replaced_after_link
            result = original_link(source, destination, *args, **kwargs)
            if destination == archive_name and not replaced_after_link:
                replaced_after_link = True
                parent = kwargs["dst_dir_fd"]
                concurrent = ".concurrent-after-link"
                descriptor = os.open(
                    concurrent, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644,
                    dir_fd=parent,
                )
                try:
                    os.write(descriptor, b"concurrent-after-link")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                os.replace(
                    concurrent, archive_name,
                    src_dir_fd=parent, dst_dir_fd=parent,
                )
            return result

        safe_plan_io._exchange = editor_then_exchange
        safe_plan_io.os.link = replace_archive_after_link
        try:
            try:
                safe_plan_io.archive_then_replace(
                    repo, relative, b"expected", 0o644, archive_name, b"replacement"
                )
            except safe_plan_io.SafePlanIOError as error:
                marker = "concurrent migration archive preserved at sibling "
                if marker not in str(error):
                    fail("post-link archive replacement omitted recovery location")
                recovery = plan.parent / str(error).split(marker, 1)[1]
            else:
                fail("post-link archive replacement unexpectedly succeeded")
        finally:
            safe_plan_io._exchange = original_exchange
            safe_plan_io.os.link = original_link
        if plan.read_bytes() != b"editor-save":
            fail("post-link archive replacement lost editor PLAN")
        if not recovery.is_file() or recovery.read_bytes() != b"concurrent-after-link":
            fail("post-link concurrent archive was misclassified or deleted")
        recovery.unlink()

        plan.write_bytes(b"expected")
        replaced_after_link = False
        safe_plan_io.os.link = replace_archive_after_link
        try:
            try:
                safe_plan_io.archive_then_replace(
                    repo, relative, b"expected", 0o644, archive_name, b"replacement"
                )
            except safe_plan_io.SafePlanIOError as error:
                marker = "legacy source preserved at sibling "
                if marker not in str(error) or "; PLAN restored" not in str(error):
                    fail("successful PLAN race omitted recovery and rollback state")
                recovery = plan.parent / str(error).split(marker, 1)[1].split(";", 1)[0]
            else:
                fail("post-link success-path archive replacement was accepted")
        finally:
            safe_plan_io.os.link = original_link
        if plan.read_bytes() != b"expected":
            fail("success-path archive race did not restore legacy PLAN")
        if archive.read_bytes() != b"concurrent-after-link":
            fail("success-path archive race lost concurrent archive")
        if not recovery.is_file() or recovery.read_bytes() != b"expected":
            fail("success-path archive race lost legacy recovery evidence")
        archive.unlink()
        recovery.unlink()


def check_write_failure_cleanup(fail) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        original_write = safe_plan_io.os.write
        safe_plan_io.os.write = lambda *_: (_ for _ in ()).throw(OSError("injected"))
        try:
            try:
                safe_plan_io.create_new(
                    repo, Path("features/loop/PLAN.md"), b"content", 0o644
                )
            except OSError:
                pass
            else:
                fail("injected write failure unexpectedly succeeded")
        finally:
            safe_plan_io.os.write = original_write
        if tuple(repo.rglob(".hard-eng-*")):
            fail("write failure leaked hidden temporary")


def check_gitlinks(fail) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        repo, child = root / "repo", root / "child"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "init", "-q", str(child)], check=True)
        tracked = child / "tracked.txt"
        tracked.write_text("clean", encoding="utf-8")
        subprocess.run(["git", "-C", str(child), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(child), "-c", "user.name=Test", "-c",
             "user.email=test@example.invalid", "commit", "-qm", "initial"],
            check=True,
        )
        subprocess.run(
            ["git", "-c", "protocol.file.allow=always", "-C", str(repo),
             "submodule", "add", "-q", str(child), "linked"],
            check=True,
        )
        clean = safe_plan_io.repository_artifact(repo)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Test", "-c",
             "user.email=test@example.invalid", "commit", "-qam", "add gitlink"],
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
        subprocess.run(
            ["git", "-C", str(repo / "linked"), "checkout", "-q", "--", "tracked.txt"],
            check=True,
        )
        linked_file.write_text("new-head", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo / "linked"), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo / "linked"), "-c", "user.name=Test", "-c",
             "user.email=test@example.invalid", "commit", "-qm", "advance"],
            check=True,
        )
        try:
            safe_plan_io.repository_artifact(repo)
        except safe_plan_io.SafePlanIOError:
            pass
        else:
            fail("gitlink HEAD/index mismatch received green artifact")


def check_plan_lock(state, fail) -> None:
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
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.2)
            if process.poll() is not None or marker.exists():
                fail("per-plan lock did not serialize a concurrent writer")
        _, error = process.communicate(timeout=5)
        if process.returncode != 0 or marker.read_text(encoding="utf-8") != "yes":
            fail(f"serialized writer did not resume: {error}")


def check_index_transition_stability(fail) -> None:
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
            ["git", "-C", str(repo), "add", "README.md", ".gitattributes",
             "filtered.txt", "delivery.txt"], check=True
        )
        commit = [
            "git", "-C", str(repo), "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid", "commit", "-qm",
        ]
        subprocess.run([*commit, "baseline"], check=True)
        filtered.write_bytes(b"filtered\r\n")
        filtered_green = safe_plan_io.repository_artifact(repo)
        if safe_plan_io.delivered_head_artifact(repo, filtered_green) != filtered_green:
            fail("Git clean-filtered working bytes are incompatible with HEAD")

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
        subprocess.run(
            ["git", "-C", str(repo), "add", "new-tool", "new-tool-link"], check=True
        )
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


if __name__ == "__main__":
    check_ancestor_swap(lambda message: (_ for _ in ()).throw(SystemExit(message)))
    check_init_preimage(lambda message: (_ for _ in ()).throw(SystemExit(message)))
    check_exchange_editor_save(lambda message: (_ for _ in ()).throw(SystemExit(message)))
    check_rollback_failure_recovery(
        lambda message: (_ for _ in ()).throw(SystemExit(message))
    )
    check_archive_cas_race(lambda message: (_ for _ in ()).throw(SystemExit(message)))
    check_write_failure_cleanup(lambda message: (_ for _ in ()).throw(SystemExit(message)))
    check_gitlinks(lambda message: (_ for _ in ()).throw(SystemExit(message)))
    check_index_transition_stability(
        lambda message: (_ for _ in ()).throw(SystemExit(message))
    )
    print("safe-plan-io-regression: PASS")
