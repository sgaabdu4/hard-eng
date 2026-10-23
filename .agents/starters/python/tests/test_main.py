import io
import runpy
from contextlib import redirect_stdout

import main


def test_greeting_names_the_caller() -> None:
    assert main.greeting("app") == "Hello from app!"


def test_running_the_module_prints_the_greeting() -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        runpy.run_module("main", run_name="__main__")
    assert output.getvalue() == "Hello from app!\n"
