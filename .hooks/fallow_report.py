"""Validate native Fallow combined scans and audit metric enforcement."""

import json
import math
import shlex
from pathlib import Path

from gate_config import Gate, Group, JsonObject, Report


def owns_package_fallow(group: Group, gate: Gate, scripts: dict[str, str]) -> bool:
    """Keep the audit owner while allowing already-run coverage to be reused."""
    command = gate["command"]
    if gate.get("report", {}).get("type") != "fallow":
        return False
    if command[:3] == ["pnpm", "run", "check:fallow"]:
        return True
    if command[:2] != ["pnpm", "run"] or gate.get("parallel"):
        return False
    try:
        standalone = shlex.split(scripts.get("check:fallow", ""))
    except ValueError:
        return False
    for previous in group["checks"]:
        if previous is gate:
            break
        if (
            previous.get("role") == "tests"
            and not previous.get("parallel")
            and standalone == [*previous["command"], "&&", *command]
        ):
            return True
    return False


def native_fallow_command(arguments: list[str]) -> list[str] | None:
    if arguments[:2] in (["pnpm", "dlx"], ["pnpm", "exec"]):
        arguments = arguments[2:]
        while arguments and arguments[0].startswith(("--package=", "--allow-build=")):
            arguments = arguments[1:]
    if not arguments or Path(arguments[0]).name.split("@", 1)[0] != "fallow":
        return None
    return ["fallow", *arguments[1:]]


def validate_fallow_command(arguments: list[str], report: Report) -> None:
    invocation = native_fallow_command(arguments)
    if invocation is None:
        return
    for index, argument in enumerate(invocation):
        flag, separator, value = argument.partition("=")
        if flag == "--max-crap":
            value = (
                value
                if separator
                else next(iter(invocation[index + 1 : index + 2]), "")
            )
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(
                    "Fallow CRAP enforcement cannot be disabled; repair its coverage input"
                )
    if "audit" in invocation and report.get("type") != "fallow":
        raise ValueError(
            "Fallow audit gates require a native fallow report; exit status alone cannot prove enabled metrics"
        )


def fallow_report_path(arguments: list[str]) -> str | None:
    invocation = native_fallow_command(arguments) or []
    for index, argument in enumerate(invocation):
        flag, separator, value = argument.partition("=")
        if flag == "--output-file":
            output = (
                value
                if separator
                else next(iter(invocation[index + 1 : index + 2]), "")
            )
            if not output:
                raise ValueError("check:fallow --output-file needs a report path")
            return output
    return None


def validate_fallow_audit(report: JsonObject) -> None:
    if report["command"] != "audit" or report["verdict"] != "pass":
        raise ValueError("Fallow requires a passing native audit")
    complexity = report["complexity"]
    if not isinstance(complexity, dict) or complexity["findings"] != []:
        raise ValueError("Fallow audit reports missing complexity analysis or findings")
    summary = complexity["summary"]
    if not isinstance(summary, dict):
        raise TypeError("Fallow audit complexity summary must be an object")
    threshold = summary["max_crap_threshold"]
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not math.isfinite(threshold)
        or threshold <= 0
    ):
        raise ValueError("Fallow CRAP enforcement is disabled or invalid")
    for key in (
        "functions_above_threshold",
        "severity_critical_count",
        "severity_high_count",
        "severity_moderate_count",
    ):
        if type(summary[key]) is not int or summary[key] != 0:
            raise ValueError("Fallow audit reports complexity findings")
    for key in ("files_analyzed", "functions_analyzed"):
        count = summary[key]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("Fallow audit lacks a valid analysis scope")


def validate_fallow(path: Path) -> None:
    try:
        report = json.loads(path.read_text())
        audit = report["kind"] == "audit"
        if audit:
            validate_fallow_audit(report)
            report = {
                **report,
                "kind": "combined",
                "check": report["dead_code"],
                "dupes": report["duplication"],
            }
        check, dupes = report["check"], report["dupes"]
        stats = dupes["stats"]
        counts = [check["total_issues"], check["summary"]["total_issues"]]
        counts += [stats["clone_groups"], stats["duplication_percentage"]]
        counts += list(check["summary"].values())
        corpus = {"total_files", "total_lines", "total_tokens"}
        counts += [value for key, value in stats.items() if key not in corpus]
        clean = all(type(n) in (int, float) and n == 0 for n in counts)
        if report["kind"] != "combined" or not clean:
            raise ValueError("Fallow reports findings or skipped analysis")
        optional = {"boundaries-not-configured", "rule-packs-not-configured"}
        diagnostics = report.get("workspace_diagnostics", [])
        if not isinstance(diagnostics, list):
            raise TypeError("Fallow diagnostics must be a list")
        if (
            any(isinstance(value, list) and value for value in check.values())
            or dupes["clone_groups"] != []
            or any(
                not isinstance(item, dict) or item.get("kind") not in optional
                for item in diagnostics
            )
        ):
            raise ValueError("Fallow reports findings or analysis diagnostics")
        if diagnostics:
            print(
                "Fallow: optional boundary/policy detectors unconfigured; not verified"
            )
        scopes = [(check["entry_points"]["total"], 0 if audit else 1)]
        scopes += [(stats[key], 0) for key in corpus]
        for value, minimum in scopes:
            if type(value) is not int or value < minimum:
                raise ValueError("Fallow report lacks a valid analysis scope")
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Fallow report is incomplete") from error
