"""One runner for direct commands, Git hooks, agent adapters and CI."""

from __future__ import annotations

import time
from pathlib import Path

from hard_eng import reports, tools
from hard_eng.common import GateError, Json, environment, run, source_files, write_file
from hard_eng.config import Check, Config, Package, affected


def required_documents(root: Path) -> None:
    missing = [
        name
        for name in ("PRODUCT.md", "DESIGN.md")
        if not (root / name).is_file() or not (root / name).read_text().strip()
    ]
    if missing:
        raise GateError(
            f"Missing or empty: {', '.join(missing)}. Study the repository and create these documents "
            "from evidence before continuing; follow the product/design guidance in skills/he/SKILL.md."
        )
    for name in ("PRODUCT.md", "DESIGN.md"):
        if "[TODO:" in (root / name).read_text():
            raise GateError(
                f"{name} contains unfilled template prompts; complete it from repository evidence"
            )


def source_checks(config: Config) -> None:
    extensions = set().union(*reports.EXTENSIONS.values()) | {".sh", ".bash"}
    exceptions = config.raw.get("file_size_exceptions", {})
    if not isinstance(exceptions, dict):
        raise GateError("File size exceptions must map exact paths to reason/evidence")
    for path in source_files(config.root):
        if (
            path.suffix not in extensions
            or reports.generated(path)
            or any(part in {"vendor", "node_modules", ".venv", ".hard-eng"} for part in path.parts)
        ):
            continue
        name = path.relative_to(config.root).as_posix()
        lines = len(path.read_text().splitlines())
        if lines > 700:
            exception = exceptions.get(name)
            if (
                not isinstance(exception, dict)
                or not exception.get("reason")
                or not exception.get("evidence")
            ):
                raise GateError(f"{name}: {lines} physical lines exceeds 700")
        if path.suffix in reports.EXTENSIONS["javascript"] and reports.focused_tests(path):
            raise GateError(f"{name}: focused test found")


def prepare_reports(check: Check) -> None:
    for path in reports.expected_reports(check):
        if path.is_symlink():
            raise GateError(f"{check.name}: report path is a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)


def execute(check: Check, package: Package | None, tool: tools.Tool | None) -> str:
    prepare_reports(check)
    command = list(tool.command if tool else ()) + list(check.command)
    env = environment(check.cwd)
    if check.tool == "zizmor":
        workflow_auth(check, env)
    result = run(command, check.cwd, check.timeout, env=env)
    if result.returncode:
        # Secret scanner output is never echoed; other commands provide their useful diagnostics.
        if not check.role.startswith("secrets"):
            print((result.stdout + result.stderr)[-12000:], end="")
        raise GateError(f"{check.name} failed (exit {result.returncode})")
    if check.report.get("type") == "dart-tests":
        write_file(reports.report_path(check, "tests"), result.stdout)
    elif check.report.get("stdout") is True:
        write_file(reports.report_path(check, "path"), result.stdout)
    return reports.validate(check, package)


def workflow_auth(check: Check, env: dict[str, str]) -> None:
    if any(flag in check.command for flag in ("--offline", "--no-online-audits")) or any(
        env.get(name, "").lower() not in {"", "0", "false", "no"}
        for name in ("ZIZMOR_OFFLINE", "ZIZMOR_NO_ONLINE_AUDITS")
    ):
        raise GateError("Zizmor online audits must not be disabled")
    if not any(env.get(name) for name in ("GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN")):
        token = run(["gh", "auth", "token"], check.cwd, 30)
        if token.returncode or not token.stdout.strip():
            raise GateError(
                "Authenticate GitHub CLI or provide GH_TOKEN for complete workflow security audits"
            )
        env["GH_TOKEN"] = token.stdout.strip()


def check_all(config: Config, *, changed: list[Path] | None = None) -> Json:
    required_documents(config.root)
    packages = affected(config, changed)
    checks = [check for package in packages for check in package.checks] + list(config.shared)
    source_checks(config)
    versions = {
        name: tools.resolve(config.root, name)
        for name in sorted({check.tool for check in checks if check.tool})
    }
    results: list[Json] = []
    failures: list[str] = []
    by_name = {package.name: package for package in packages}
    for check in checks:
        started = time.monotonic()
        try:
            detail = execute(check, by_name.get(check.package), versions.get(check.tool or ""))
            print(f"PASS {check.name}: {detail}")
            results.append(
                {"name": check.name, "seconds": round(time.monotonic() - started, 3), "detail": detail}
            )
        except GateError as error:
            failures.append(str(error))
            print(f"FAIL {error}")
    if failures:
        raise GateError(f"{len(failures)} required checks failed")
    return {"passed": True, "checks": results}
