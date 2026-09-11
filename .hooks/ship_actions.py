"""Guard the mutations following verified PR delivery."""

from pathlib import Path

from shipping import Shipment, gh, git, verify


def worktrees(root: Path) -> list[dict[str, str]]:
    records = git(root, "worktree", "list", "--porcelain", "-z")
    return [
        dict(field.partition(" ")[::2] for field in record.split("\0") if field)
        for record in records.split("\0\0")
        if record
    ]


def common_directory(root: Path) -> Path:
    return Path(
        git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    ).resolve()


def cleanup_guard(coordinator: Path, shipment: Shipment) -> None:
    target = shipment.root.resolve()
    if common_directory(coordinator) != common_directory(target):
        raise ValueError("Cleanup target is not in the coordinator's repository")
    if Path.cwd().resolve().is_relative_to(target):
        raise ValueError("Run cleanup outside the task's current worktree")
    records = worktrees(coordinator)
    if not records or Path(records[0]["worktree"]).resolve() == target:
        raise ValueError("The main worktree must be preserved")
    matches = [
        record for record in records if Path(record["worktree"]).resolve() == target
    ]
    if len(matches) != 1 or "locked" in matches[0] or "prunable" in matches[0]:
        raise ValueError("Cleanup needs one available, unlocked task worktree")
    branch = f"refs/heads/{shipment.branch}"
    if matches[0].get("branch") != branch:
        raise ValueError("Cleanup target no longer owns the verified task branch")
    if sum(record.get("branch") == branch for record in records) != 1:
        raise ValueError("Another worktree uses the task branch")
    if git(
        target, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"
    ).strip():
        raise ValueError("Cleanup preserves modified, untracked or ignored work")
    if git(target, "rev-parse", "HEAD").strip() != shipment.head_sha:
        raise ValueError("Cleanup preserves commits added after the verified PR")
    if shipment.branch == shipment.base or not shipment.merged_sha:
        raise ValueError("Cleanup requires a merged task branch, never the base")


def remote_branch(root: Path, remote: str, branch: str) -> str | None:
    lines = git(root, "ls-remote", "--heads", remote, f"refs/heads/{branch}")
    rows = [line.split() for line in lines.splitlines() if line.strip()]
    if not rows:
        return None
    if len(rows) != 1 or rows[0][1] != f"refs/heads/{branch}":
        raise ValueError("Task remote branch is ambiguous")
    return rows[0][0]


def cleanup(coordinator: Path, shipment: Shipment) -> None:
    cleanup_guard(coordinator, shipment)
    remote_head = remote_branch(shipment.root, shipment.remote, shipment.branch)
    if remote_head not in (None, shipment.head_sha):
        raise ValueError("Cleanup preserves a remote branch with additional work")
    if remote_head is not None:
        reference = f"refs/heads/{shipment.branch}"
        git(
            shipment.root,
            "push",
            f"--force-with-lease={reference}:{shipment.head_sha}",
            shipment.remote,
            f":{reference}",
        )
        if remote_branch(shipment.root, shipment.remote, shipment.branch) is not None:
            raise ValueError("Remote branch still exists; local worktree retained")
        print(f"Removed remote task branch {shipment.branch}", flush=True)
    cleanup_guard(coordinator, shipment)
    git(coordinator, "worktree", "remove", str(shipment.root))
    print(f"Removed task worktree {shipment.root}", flush=True)
    git(
        coordinator,
        "update-ref",
        "-d",
        f"refs/heads/{shipment.branch}",
        shipment.head_sha,
    )
    print(f"Removed local task branch {shipment.branch}", flush=True)


def run(
    coordinator: Path,
    plan: str,
    pr_url: str,
    stage: str,
    worktree: str | None,
    merge_method: str | None,
) -> int:
    target = Path(worktree).resolve() if worktree else coordinator.resolve()
    if common_directory(coordinator) != common_directory(target):
        raise ValueError("Shipping target belongs to a different repository")
    plan_path = (target / plan).resolve()
    if not plan_path.is_relative_to(target):
        raise ValueError("Use the selected task's plan inside its worktree")
    if stage == "merge" and merge_method is None:
        raise ValueError("Select the repository's merge method with --merge-method")
    proof_stage = "ready" if stage in {"ready", "merge"} else "delivered"
    shipment = verify(target, plan_path, pr_url, proof_stage)
    if stage == "merge":
        if shipment.delivery_target == "PR":
            raise ValueError("The plan authorizes PR delivery, not merging")
        gh(
            target,
            "pr",
            "merge",
            pr_url,
            f"--{merge_method}",
            "--match-head-commit",
            shipment.head_sha,
        )
        shipment = verify(target, plan_path, pr_url, "delivered")
    if stage == "cleanup":
        cleanup(coordinator, shipment)
    revision = shipment.merged_sha or shipment.head_sha
    print(f"PASS ship {stage}: {pr_url} at {revision}")
    return 0
