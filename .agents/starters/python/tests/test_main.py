import io
from contextlib import redirect_stdout

import main


def test_greeting_names_the_caller() -> None:
    assert main.greeting("app") == "Hello from app!"


def test_main_prints_the_greeting() -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        main.main()
    assert output.getvalue() == "Hello from app!\n"
