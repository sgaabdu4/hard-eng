import time

import main


def test_greeting_builds_100k_messages_within_budget() -> None:
    start = time.perf_counter()
    for index in range(100_000):
        main.greeting(str(index))
    assert time.perf_counter() - start < 1.0
