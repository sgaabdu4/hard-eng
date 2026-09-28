"""Run Codebase Memory from one per-user install so every client reaches its daemon."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGE = "codebase-memory-mcp"
VERSION = "0.11.0"
INSTALL = "--hard-eng-install"


def install_root() -> Path:
    data = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share"
    return Path(data) / "hard-eng" / PACKAGE / VERSION


def executable(root: Path) -> Path:
    return root / "node_modules" / PACKAGE / "bin" / PACKAGE


def install(root: Path) -> None:
    staging = Path(tempfile.mkdtemp(prefix=f".{VERSION}-", dir=root.parent))
    try:
        subprocess.run(
            ["pnpm", "add", "--dir", str(staging), "--ignore-scripts"]
            + [f"{PACKAGE}@{VERSION}"],
            check=True,
        )
        bin_js = staging / "node_modules" / PACKAGE / "bin.js"
        subprocess.run(["node", str(bin_js), "--version"], check=True)
        try:
            staging.rename(root)
        except OSError:
            if not executable(root).is_file():
                raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    root = install_root()
    if sys.argv[1:] == [INSTALL]:
        install(root)
        return
    if not executable(root).is_file():
        root.parent.mkdir(parents=True, exist_ok=True)
        log = root.parent / f"{VERSION}.log"
        with log.open("w") as output:
            # Own session and files: the install finishes after a host stops waiting.
            status = subprocess.run(
                [sys.executable, __file__, INSTALL],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
            ).returncode
        if status:
            sys.exit(f"Codebase Memory install failed; see {log}")
    binary = executable(root)
    os.execv(binary, [str(binary), *sys.argv[1:]])


if __name__ == "__main__":
    main()
