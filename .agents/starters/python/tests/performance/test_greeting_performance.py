import time

import main


def run_seconds() -> float:
    start = time.perf_counter()
    for index in range(100_000):
        main.greeting(str(index))
    return time.perf_counter() - start


def test_greeting_builds_100k_messages_within_budget() -> None:
    # Fastest of 5 runs, so a busy shared runner's pause does not fail a fast build.
    assert min(run_seconds() for _ in range(5)) < 1.0
