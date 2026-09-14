"""Exercise shared-cache exclusion through real gate subprocesses."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest


@pytest.mark.parametrize("executable", ["uv", "uvx"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_uv_gate_processes_do_not_share_cache_concurrently(
    runner: ModuleType, tmp_path: Path, executable: str, exit_code: int
) -> None:
    binary = tmp_path / executable
    binary.symlink_to(sys.executable)
    code = (
        "import pathlib,time,sys;"
        "cache=pathlib.Path('cache-write');"
        "cache.mkdir();time.sleep(0.1);cache.rmdir();"
        "pathlib.Path(sys.argv[1]).touch();sys.exit(int(sys.argv[2]))"
    )
    output_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                runner.run_gate,
                {"path": "."},
                {
                    "name": str(index),
                    "command": [str(binary), "-c", code, str(index), str(exit_code)],
                },
                5,
                output_lock,
            )
            for index in range(2)
        ]
        assert [future.result() for future in futures] == [bool(exit_code)] * 2
    assert all((tmp_path / str(index)).exists() for index in range(2))
