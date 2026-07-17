"""Command-line router for the Hard Eng PLAN state owner."""

from __future__ import annotations

import argparse


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--repo", default=".")
    inspect.add_argument("--plan")
    initialize = commands.add_parser("init")
    initialize.add_argument("--repo", default=".")
    initialize.add_argument("--feature-slug", required=True)
    initialize.add_argument("--plan-id")
    transfer = commands.add_parser("transfer")
    transfer.add_argument("--repo", default=".")
    transfer.add_argument("--to-repo", required=True)
    transfer.add_argument("--plan", required=True)
    transfer.add_argument("--expect-token", required=True)
    transfer.add_argument("--include", action="append", default=[])
    for name in ("reconcile-head", "reconcile-build-head"):
        reconcile = commands.add_parser(name)
        reconcile.add_argument("--repo", default=".")
        reconcile.add_argument("--plan", required=True)
        reconcile.add_argument("--expect-token", required=True)
    migrate = commands.add_parser("migrate-state")
    migrate.add_argument("--repo", default=".")
    migrate.add_argument("--plan", required=True)
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("--repo", default=".")
    checkpoint.add_argument("--plan", required=True)
    checkpoint.add_argument("--expect-token", required=True)
    checkpoint.add_argument("--set", dest="updates", action="append", default=[])
    checkpoint.add_argument(
        "--add-item", action="append", nargs=5,
        metavar=("TYPE", "EVIDENCE", "IMPACT", "OWNER", "NEXT_ACTION"), default=[],
    )
    checkpoint.add_argument(
        "--update-item", action="append", nargs=3,
        metavar=("ID", "FIELD", "VALUE"), default=[],
    )
    checkpoint.add_argument("--close-item", action="append", default=[])
    checkpoint.add_argument(
        "--add-learning", action="append", nargs=6,
        metavar=("TRIGGER", "SOURCE", "EVIDENCE", "CAUSE", "OWNER", "REQUIRED_PROOF"),
        default=[],
    )
    checkpoint.add_argument(
        "--resolve-learning", action="append", nargs=2,
        metavar=("ID", "RESOLUTION"), default=[],
    )
    checkpoint.add_argument(
        "--transfer-learning", action="append", nargs=3,
        metavar=("ID", "DESTINATION_PLAN", "DESTINATION_ID"), default=[],
    )
    checkpoint.add_argument(
        "--refresh-learning", action="append", nargs=2,
        metavar=("ID", "RESOLUTION"), default=[],
    )
    checkpoint.add_argument("--prune-closed", action="store_true")
    complete = commands.add_parser("complete-slice")
    complete.add_argument("--repo", default=".")
    complete.add_argument("--plan", required=True)
    complete.add_argument("--expect-token", required=True)
    return root


def run(owner) -> int:
    args = parser().parse_args()
    if args.command == "init":
        return owner["initialize"](args.repo, args.feature_slug, args.plan_id)
    if args.command == "transfer":
        return owner["transfer"](
            args.repo, args.to_repo, args.plan, args.expect_token, args.include
        )
    if args.command == "reconcile-head":
        return owner["reconcile_head"](args.repo, args.plan, args.expect_token)
    if args.command == "reconcile-build-head":
        return owner["reconcile_build_head"](args.repo, args.plan, args.expect_token)
    if args.command == "migrate-state":
        return owner["migrate_state"](args.repo, args.plan)
    if args.command == "checkpoint":
        return owner["checkpoint"](
            args.repo, args.plan, args.expect_token, args.updates, args.add_item,
            args.update_item, args.close_item, args.add_learning,
            args.resolve_learning, args.transfer_learning, args.prune_closed,
            args.refresh_learning,
        )
    if args.command == "complete-slice":
        return owner["complete_active_slice"](args.repo, args.plan, args.expect_token)
    return owner["inspect"](args.repo, args.plan)
