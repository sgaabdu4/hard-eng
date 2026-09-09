import subprocess


def unsafe(expression: str) -> object:
    # ruleid: hard-eng.python.dynamic-eval
    return eval(expression)


def unsafe_shell(command: str) -> subprocess.CompletedProcess[str]:
    # ruleid: hard-eng.python.shell-execution
    return subprocess.run(command, shell=True, text=True)


def safe_argument(value: str) -> subprocess.CompletedProcess[str]:
    # ok: hard-eng.python.shell-execution
    return subprocess.run(["printf", "%s", value], shell=False, text=True)
