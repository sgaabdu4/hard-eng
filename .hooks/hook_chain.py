"""Keep a project's own pre-push hook running ahead of Hard Eng's."""

import shutil
import subprocess
from pathlib import Path

PYTHON_LAUNCHER = """#!/usr/bin/env python3
import subprocess
import sys

root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
sys.exit(subprocess.call([sys.executable, root + "/.hooks/hard-eng.py", "pre-push"]))
"""
SHELL_LAUNCHER = '#!/usr/bin/env sh\nexec python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py" pre-push\n'
CHAINED_LAUNCHER = """#!/usr/bin/env sh
original="$0.project"
input=$(mktemp) || exit 1
trap 'rm -f "$input"' EXIT
cat > "$input"
if [ -x "$original" ]; then
  "$original" "$@" < "$input" || exit $?
fi
python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py" pre-push < "$input"
"""
LAUNCHERS = {PYTHON_LAUNCHER, SHELL_LAUNCHER, CHAINED_LAUNCHER}
KEPT = "Kept your existing pre-push hook; it runs before Hard Eng's checks. Compare its checks with Hard Eng's (he references: adopting existing checks)."
RESTORE = "Hard Eng's pre-push hook is missing or was replaced (another tool may have reinstalled its own), so pushes are not checked. Rerun setup to restore it: curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/setup.sh | sh"


def locate(root: Path) -> tuple[Path, Path]:
    from agent_hooks import project_pre_push

    hook = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-path", "hooks/pre-push"], cwd=root, text=True
        ).strip()
    )
    hook = hook if hook.is_absolute() else root / hook
    return hook, project_pre_push(root, hook)


def project_copy(hook: Path) -> Path:
    return hook.with_name(hook.name + ".project")


def is_own(root: Path, hook: Path) -> bool:
    if hook.is_symlink():
        return hook.resolve() == root / ".hooks/hard-eng.py"
    return hook.is_file() and hook.read_text(errors="replace") in LAUNCHERS


def foreign_hook(root: Path, hook: Path) -> bool:
    return (hook.exists() or hook.is_symlink()) and not is_own(root, hook)


def kept_copy_matches(hook: Path) -> bool:
    copy = project_copy(hook)
    return copy.exists() and copy.read_bytes() == hook.read_bytes()


def check_free(root: Path, hook: Path) -> None:
    copy = project_copy(hook)
    if foreign_hook(root, hook) and copy.exists() and not kept_copy_matches(hook):
        raise ValueError(
            f"{hook.name} was replaced while {copy.name} holds another project hook; merge them into {copy.name} and rerun setup"
        )


def preserve(root: Path, hook: Path) -> bool:
    check_free(root, hook)
    if not foreign_hook(root, hook):
        return False
    if not project_copy(hook).exists():
        shutil.copy2(hook, project_copy(hook))
    return True


def restore_note(root: Path) -> str:
    from update import SOURCE_FILE

    if not (root / SOURCE_FILE).exists():
        return ""
    try:
        target = locate(root)[1]
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    return "" if is_own(root, target) else RESTORE
