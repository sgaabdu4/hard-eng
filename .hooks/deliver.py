"""The commands that run no gates: adopt, ci-usage, hot-paths, ui-library, text-walls, pr-text, gap-issue, challenge and ship."""

from argparse import Namespace
from collections.abc import Callable
from pathlib import Path


def deliver(root: Path, args: Namespace, adopt: Callable[[], int]) -> int:
    if args.command == "adopt":
        return adopt()
    if args.command == "ci-usage":
        from ci_usage import ci_usage

        return ci_usage(root, args.repo, args.days, args.runs)
    if args.command == "hot-paths":
        from hot_paths import scan_all

        return scan_all(root, paths=args.paths)
    if args.command == "ui-library":
        from ui_library import write_index

        return write_index(root)
    if args.command == "text-walls":
        from text_walls import walls_command

        return walls_command(root, args.paths, args.stdin)
    if args.command == "pr-text":
        from pr_text import pr_text_command

        return pr_text_command(root, args.pr)
    if args.command == "gap-issue":
        from gap_issue import file_gap

        return file_gap(root, args.text)
    if args.command == "challenge":
        from challenge import challenge

        return challenge(root, args.base, args.host)
    from ship_actions import run
    from tool_setup import ensure_python_runtime

    ensure_python_runtime()
    return run(root, args.plan, args.pr, args.stage, args.worktree, args.merge_method)
