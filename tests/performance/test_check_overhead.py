"""Keep a check's own child processes constant as the repository grows."""

import sys
from pathlib import Path
from types import ModuleType

from conftest import configure, gate

STARTED: list[str] = []
COUNTING: list[bool] = []


def record(event: str, arguments: tuple[object, ...]) -> None:
    if COUNTING and event == "subprocess.Popen":
        STARTED.append(Path(str(arguments[0])).name)


sys.addaudithook(record)


def test_check_starts_the_same_processes_for_ten_or_four_hundred_files(
    runner: ModuleType, tmp_path: Path
) -> None:
    configure(tmp_path, [gate("suite", "pass")])
    (tmp_path / "notes").mkdir()
    counts = []
    for total in (10, 400):
        for index in range(total):
            (tmp_path / "notes" / f"{index}.txt").write_text(f"note {index}\n")
        STARTED.clear()
        COUNTING.append(True)
        try:
            assert runner.check(timeout=120) == 0
        finally:
            COUNTING.clear()
        counts.append(sorted(STARTED))
    assert counts[0] == counts[1]
    assert "git" in counts[0]
