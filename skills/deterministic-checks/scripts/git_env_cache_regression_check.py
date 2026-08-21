#!/usr/bin/env python3
"""Behavioral fixture for the stripped-variable disk cache.

git-env-hygiene: exempt - the fixture drives the sanitizer itself and must be
able to observe an unsanitized fork.

The cache exists because the agent guard is a fresh interpreter on every tool
call and was forking `git rev-parse --local-env-vars` each time. A cache in that
position is only safe while three things hold: it agrees with the fork, a
different git misses it, and a failed fork never gets written. Each case below
goes red if its guarantee is removed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

LABEL = "git-env-cache-regressions"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"{LABEL}: FAIL: {message}")


def load(cache: Path, path_override: str | None = None) -> tuple[frozenset[str], str]:
    """One fresh interpreter, so the in-process memo cannot hide a cache miss.

    Returns the variable set and whatever the child printed about forking.
    """
    program = (
        "import json, sys;"
        "sys.path.insert(0, sys.argv[1]);"
        "import git_env;"
        "real = git_env.run_captured;"
        "forked = [];"
        "git_env.run_captured = lambda *a, **k: (forked.append(a[0]), real(*a, **k))[1];"
        "names = sorted(git_env.stripped_variables());"
        "print(json.dumps({'names': names, 'forked': [list(c) for c in forked]}))"
    )
    env = dict(os.environ)
    env["HARD_ENG_GIT_ENV_CACHE"] = str(cache)
    if path_override is not None:
        env["PATH"] = path_override
    result = subprocess.run(
        [sys.executable, "-c", program, str(Path(__file__).resolve().parent)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if result.returncode != 0:
        fail(f"probe failed: {result.stderr.strip()[-300:]}")
    try:
        answer = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        fail(f"probe printed no verdict: {result.stdout!r}")
    return frozenset(answer["names"]), json.dumps(answer["forked"])


def main() -> int:
    with tempfile.TemporaryDirectory() as workspace:
        area = Path(workspace)
        cache = area / "local-env-vars.json"

        # 1. The first call forks and the second does not, and both answer the same.
        first, first_calls = load(cache)
        if "rev-parse" not in first_calls:
            fail("the first call did not consult git at all")
        if not cache.is_file():
            fail("a clean fork was not remembered")
        second, second_calls = load(cache)
        if "rev-parse" in second_calls:
            fail("a warm cache still forked git")
        if first != second:
            fail(f"cache disagrees with the fork: {sorted(first ^ second)}")
        if not first:
            fail("the sanitizer answered with no variables at all")

        # 2. The cache is private, because it is written into a shared user cache.
        mode = cache.stat().st_mode & 0o777
        if mode != 0o600:
            fail(f"cache mode is {oct(mode)}, expected 0o600")

        # 3. A different git binary must miss. This is the whole reason the fork
        #    exists — the variable list drifts between versions, and a cache that
        #    survived an upgrade would silently sanitize against the old list.
        record = json.loads(cache.read_text(encoding="utf-8"))
        record["fingerprint"] = "/nowhere/git:1:1"
        cache.write_text(json.dumps(record), encoding="utf-8")
        _, drift_calls = load(cache)
        if "rev-parse" not in drift_calls:
            fail("a cache written by a different git was trusted")

        # 4. A git that resolves but answers badly is never remembered, or one bad
        #    moment would blind every later process until the binary changed. The
        #    shim has to exist and be executable: with no git on PATH at all the
        #    fingerprint is already None, and that guard would mask this one.
        shim = area / "bin"
        shim.mkdir()
        (shim / "git").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (shim / "git").chmod(0o755)
        broken = area / "broken.json"
        names, broken_calls = load(broken, path_override=str(shim))
        if "rev-parse" not in broken_calls:
            fail("the failing-git probe never reached the fork")
        if broken.exists():
            fail("a failed lookup was written to the cache")
        if not names:
            fail("a failed lookup returned nothing; the static list is the floor")

        # 5. No git on PATH at all is a different path, and must also stay silent.
        empty = area / "empty"
        empty.mkdir()
        blank = area / "blank.json"
        absent, _ = load(blank, path_override=str(empty))
        if blank.exists():
            fail("a lookup with no git at all was written to the cache")
        if not absent:
            fail("a lookup with no git returned nothing; the static list is the floor")

        # 6. The static list is the floor on every path, hit or miss.
        import git_env

        floor: frozenset[str] = frozenset(git_env.LOCAL_ENV_VARS)
        for label, answer in (("fork", first), ("cache", second), ("failure", names), ("absent", absent)):
            if not floor <= answer:
                fail(f"{label} answer dropped {sorted(floor - answer)}")

    print(f"{LABEL}: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
