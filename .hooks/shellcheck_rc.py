"""A `.shellcheckrc` that turns a ShellCheck rule off hides findings from every shell gate."""

DISABLING = ("disable",)


def rc_hits(name: str, text: str) -> list[str]:
    return [
        f"{name}:{number} sets {line.strip()!r}, which turns ShellCheck rules off for every script near it; fix the scripts instead"
        for number, line in enumerate(text.splitlines(), 1)
        if not line.lstrip().startswith("#")
        and line.strip().partition("=")[0].strip() in DISABLING
    ]
