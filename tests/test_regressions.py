import pytest
import script_runner
from regressions import IN_PROCESS


@pytest.mark.parametrize("script", IN_PROCESS, ids=lambda path: path.stem)
def test_regression(script):
    module = script_runner.load_script(script)
    assert module.main() == 0


def test_process_state_survives_two_runs():
    import os
    import sys

    before = (os.getcwd(), dict(os.environ), list(sys.argv), sys.stdin, sys.stdout, sys.stderr)
    module = script_runner.load_script(IN_PROCESS[1])
    assert module.main() == 0
    assert module.main() == 0
    assert before == (os.getcwd(), dict(os.environ), list(sys.argv), sys.stdin, sys.stdout, sys.stderr)
