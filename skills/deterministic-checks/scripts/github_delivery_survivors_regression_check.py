#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of github_delivery.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dart_decimate_gate_survivors_regression_check import run_main as run_main_for
from github_delivery_regression_check import fixtures as base_fixtures
from regression_fixture import checker

fail, require = checker("github-delivery-survivors")

VERIFIER_MODULE_NAME = "skills.deterministic-checks.scripts.github_delivery"
SHA = "a" * 40
REUSABLE_SHA = "c" * 40


def load_verifier() -> Any:
    try:
        return importlib.import_module(VERIFIER_MODULE_NAME)
    except ImportError as error:
        fail(f"verifier could not be loaded: {error}")


def expect_error(module: Any, func: Any, *args: Any, expected: str, **kwargs: Any) -> None:
    try:
        func(*args, **kwargs)
    except module.DeliveryError as error:
        require(str(error) == expected, f"unexpected message: {error!r} != {expected!r}")
        return
    fail(f"expected DeliveryError: {expected}")


def check_require_mapping(module: Any) -> None:
    expect_error(module, module.require_mapping, 123, "workflow run", expected="workflow run was invalid")
    require(module.require_mapping({"a": 1}, "x") == {"a": 1}, "require_mapping lost a valid mapping")


def check_require_success(module: Any) -> None:
    expect_error(
        module,
        module.require_success,
        {"status": "completed", "conclusion": "failure"},
        "workflow",
        expected="required workflow did not complete successfully",
    )
    module.require_success({"status": "completed", "conclusion": "success"}, "workflow")


def check_require_exact(module: Any) -> None:
    expect_error(
        module, module.require_exact, [], "quality", "job", expected="required job was missing or ambiguous: quality"
    )
    item = module.require_exact([{"name": "quality"}], "quality", "job")
    require(item == {"name": "quality"}, "require_exact did not return the exact match")


def check_parse_step(module: Any) -> None:
    require(module.parse_step("deploy::Deploy production") == ("deploy", "Deploy production"), "parse_step misparsed")
    expected = "required step must use '<job>::<step>'"
    expect_error(module, module.parse_step, "badspec", expected=expected)
    expect_error(module, module.parse_step, "::step", expected=expected)
    expect_error(module, module.parse_step, "job::step::extra", expected=expected)


def check_parse_reusable(module: Any) -> None:
    sha = "d" * 40
    require(module.parse_reusable(f"path::{sha}") == ("path", sha, None), "parse_reusable dropped optional ref")
    require(module.parse_reusable(f"path::{sha}::") == ("path", sha, None), "parse_reusable mishandled empty ref")
    require(
        module.parse_reusable(f"path::{sha}::refs/tags/v1") == ("path", sha, "refs/tags/v1"),
        "parse_reusable lost its ref",
    )
    expected = "reusable workflow must use '<path>::<sha>[::<ref>]'"
    expect_error(module, module.parse_reusable, f"a::b::c::{sha}", expected=expected)
    expect_error(module, module.parse_reusable, "onlyone", expected=expected)


def check_reusable_identity(module: Any) -> None:
    valid_sha = "e" * 40
    require(
        module.reusable_identity({"path": "p", "sha": valid_sha, "ref": "main"}) == ("p", valid_sha, "main"),
        "reusable_identity lost its ref",
    )
    require(
        module.reusable_identity({"path": "p", "sha": valid_sha}) == ("p", valid_sha, None),
        "reusable_identity treated a missing ref as required",
    )
    expect_error(module, module.reusable_identity, 123, expected="referenced workflow was invalid")
    invalid = "referenced workflow identity was invalid"
    expect_error(module, module.reusable_identity, {"path": "p", "sha": "not-a-sha"}, expected=invalid)
    expect_error(module, module.reusable_identity, {"path": "p", "sha": None}, expected=invalid)
    expect_error(module, module.reusable_identity, {"path": "", "sha": valid_sha}, expected=invalid)
    expect_error(module, module.reusable_identity, {"path": 123, "sha": valid_sha}, expected=invalid)
    expect_error(module, module.reusable_identity, {"path": "p", "sha": valid_sha, "ref": 123}, expected=invalid)


def base_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    run, jobs = base_fixtures()
    jobs["jobs"][0]["steps"] = jobs["jobs"][0]["steps"][:1]
    return run, jobs


def call_verify(module: Any, run: Any, jobs: Any, **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "repository": "owner/repository",
        "run_id": 123,
        "sha": SHA,
        "workflow": "Production",
        "workflow_id": 77,
        "workflow_path": ".github/workflows/production.yml@main",
        "event": "workflow_dispatch",
        "ref": "main",
        "run_attempt": 2,
        "check_suite_id": 456,
        "reusable_workflows": (f"owner/reusable/.github/workflows/deploy.yml@v1::{REUSABLE_SHA}::refs/tags/v1",),
        "required_jobs": ("quality",),
        "required_steps": ("deploy::Deploy production",),
    }
    kwargs.update(overrides)
    return module.verify_delivery(run, jobs, **kwargs)


def expect_verify_error(module: Any, run: Any, jobs: Any, expected: str, **overrides: Any) -> None:
    try:
        call_verify(module, run, jobs, **overrides)
    except module.DeliveryError as error:
        require(str(error) == expected, f"unexpected verify_delivery message: {error!r} != {expected!r}")
        return
    fail(f"verify_delivery did not fail as expected: {expected}")


def check_verify_delivery(module: Any) -> None:
    run, jobs = base_fixture()
    receipt = call_verify(module, run, jobs)
    require(
        receipt
        == {
            "run_id": 123,
            "repository": "owner/repository",
            "workflow_id": 77,
            "workflow_path": ".github/workflows/production.yml@main",
            "run_attempt": 2,
            "check_suite_id": 456,
            "required_jobs": 2,
            "required_steps": 1,
            "sha": SHA,
            "workflow": "Production",
        },
        "verify_delivery receipt drifted from the exact contract",
    )

    _run_a, jobs_a = base_fixture()
    expect_verify_error(module, "not-a-mapping", jobs_a, "workflow run was invalid")
    run_b, _jobs_b = base_fixture()
    expect_verify_error(module, run_b, "not-a-mapping", "workflow jobs was invalid")

    run_c, jobs_c = base_fixture()
    jobs_c["total_count"] = 3
    expect_verify_error(module, run_c, jobs_c, "workflow jobs were incomplete")
    expect_verify_error(module, run_c, {"total_count": 2, "jobs": "ab"}, "workflow jobs were incomplete")

    run_d, jobs_d = base_fixture()
    run_d["repository"] = "not-a-mapping"
    expect_verify_error(module, run_d, jobs_d, "workflow repository was invalid")
    run_e, jobs_e = base_fixture()
    run_e["repository"] = {"full_name": "lookalike/repository"}
    expect_verify_error(module, run_e, jobs_e, "workflow repository identity did not match")

    run_f, jobs_f = base_fixture()
    run_f["id"] = "123"
    expect_verify_error(module, run_f, jobs_f, "workflow run ID did not match")
    run_g, jobs_g = base_fixture()
    run_g["id"] = 124
    expect_verify_error(module, run_g, jobs_g, "workflow run ID did not match")
    run_h, jobs_h = base_fixture()
    run_h["id"] = True
    expect_verify_error(module, run_h, jobs_h, "workflow run ID did not match", run_id=1)

    run_i, jobs_i = base_fixture()
    run_i["head_sha"] = "b" * 40
    expect_verify_error(module, run_i, jobs_i, "workflow run SHA did not match delivery SHA")

    run_j, jobs_j = base_fixture()
    run_j["name"] = "Other"
    expect_verify_error(module, run_j, jobs_j, "workflow run name did not match")

    for field, bad_value in (
        ("workflow_id", 78),
        ("path", ".github/workflows/lookalike.yml@main"),
        ("event", "push"),
        ("head_branch", "release"),
        ("run_attempt", 1),
        ("check_suite_id", 999),
    ):
        run_k, jobs_k = base_fixture()
        run_k[field] = bad_value
        expect_verify_error(module, run_k, jobs_k, f"workflow run {field} did not match")

    run_l, jobs_l = base_fixture()
    run_l["check_suite_id"] = 456.0
    expect_verify_error(module, run_l, jobs_l, "workflow run check_suite_id did not match")

    run_l2, jobs_l2 = base_fixture()
    run_l2["run_attempt"] = True
    expect_verify_error(module, run_l2, jobs_l2, "workflow run run_attempt did not match", run_attempt=1)

    run_m, jobs_m = base_fixture()
    del run_m["referenced_workflows"]
    receipt_m = call_verify(module, run_m, jobs_m, reusable_workflows=())
    require(receipt_m["sha"] == SHA, "verify_delivery rejected an empty referenced-workflow set correctly matching")

    run_n, jobs_n = base_fixture()
    run_n["referenced_workflows"] = "not-a-list"
    expect_verify_error(module, run_n, jobs_n, "referenced workflow identity was invalid")

    run_o, jobs_o = base_fixture()
    run_o["referenced_workflows"] = run_o["referenced_workflows"] * 2
    expect_verify_error(module, run_o, jobs_o, "referenced workflow identity was ambiguous")

    run_p, jobs_p = base_fixture()
    dup_spec = f"owner/reusable/.github/workflows/deploy.yml@v1::{REUSABLE_SHA}::refs/tags/v1"
    expect_verify_error(
        module,
        run_p,
        jobs_p,
        "expected referenced workflow identity was ambiguous",
        reusable_workflows=(dup_spec, dup_spec),
    )

    run_q, jobs_q = base_fixture()
    run_q["conclusion"] = "failure"
    expect_verify_error(module, run_q, jobs_q, "required workflow did not complete successfully")

    run_r, jobs_r = base_fixture()
    jobs_r["jobs"] = jobs_r["jobs"][:1]
    jobs_r["total_count"] = 1
    expect_verify_error(module, run_r, jobs_r, "required job was missing or ambiguous: quality")

    run_s, jobs_s = base_fixture()
    jobs_s["jobs"].append(dict(jobs_s["jobs"][0]))
    jobs_s["total_count"] = 3
    expect_verify_error(module, run_s, jobs_s, "required job was missing or ambiguous: deploy")

    run_t, jobs_t = base_fixture()
    jobs_t["jobs"][0]["head_sha"] = "b" * 40
    expect_verify_error(module, run_t, jobs_t, "required job SHA did not match: deploy")

    run_u, jobs_u = base_fixture()
    jobs_u["jobs"][0]["conclusion"] = "failure"
    expect_verify_error(module, run_u, jobs_u, "required job: deploy did not complete successfully")

    run_v, jobs_v = base_fixture()
    del jobs_v["jobs"][1]["steps"]
    expect_verify_error(
        module, run_v, jobs_v, "required job had no steps: quality", required_steps=("quality::Some step",)
    )

    run_w, jobs_w = base_fixture()
    expect_verify_error(
        module,
        run_w,
        jobs_w,
        "required step was missing or ambiguous: Missing step",
        required_steps=("deploy::Missing step",),
    )

    run_x, jobs_x = base_fixture()
    jobs_x["jobs"][0]["steps"][0]["conclusion"] = "skipped"
    expect_verify_error(module, run_x, jobs_x, "required step: deploy::Deploy production did not complete successfully")

    run_y, jobs_y = base_fixture()
    run_y["referenced_workflows"] = [
        {"path": "owner/reusable/.github/workflows/other.yml@v1", "sha": REUSABLE_SHA, "ref": "refs/tags/v1"}
    ]
    expect_verify_error(module, run_y, jobs_y, "referenced workflow identity did not match")


class _OneShotMatchJob(dict):
    """A job dict whose name only matches once, exposing whether a caller re-looked it up."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._matched = False

    def get(self, key: Any, default: Any = None) -> Any:
        if key == "name":
            if self._matched:
                return None
            self._matched = True
        return dict.get(self, key, default)


def check_verify_delivery_job_cache(module: Any) -> None:
    run, jobs = base_fixture()
    jobs["jobs"][0] = _OneShotMatchJob(jobs["jobs"][0])
    try:
        receipt = call_verify(module, run, jobs, required_jobs=("deploy", "deploy", "quality"), required_steps=())
    except module.DeliveryError as error:
        fail(f"resolve_job re-looked up an already-resolved job instead of using its cache: {error}")
    require(receipt["required_jobs"] == 2, "verify_delivery receipt drifted for a duplicated required job")


def check_load_json(module: Any) -> None:
    class FakePath:
        def __init__(self, content: str) -> None:
            self.content = content
            self.seen_encoding: str | None = None

        def read_text(self, encoding: str | None = None) -> str:
            self.seen_encoding = encoding
            return self.content

        def __str__(self) -> str:
            return "fake-path"

    fake = FakePath('{"a": 1}')
    require(module.load_json(fake) == {"a": 1}, "load_json did not parse valid JSON")
    require(fake.seen_encoding == "utf-8", f"load_json passed the wrong encoding: {fake.seen_encoding!r}")

    with tempfile.TemporaryDirectory(prefix="github-delivery-survivors-") as temporary:
        missing = Path(temporary) / "missing.json"
        expect_error(module, module.load_json, missing, expected=f"invalid JSON fixture: {missing}")


def check_inputs(module: Any) -> None:
    class Args:
        def __init__(self, **kwargs: Any) -> None:
            self.repo = kwargs.get("repo")
            self.run_id = kwargs.get("run_id")
            self.run_json = kwargs.get("run_json")
            self.jobs_json = kwargs.get("jobs_json")

    choose_message = "choose live GitHub input or JSON fixtures"
    fixtures_message = "both JSON fixtures are required"

    calls: list[tuple[Any, Any]] = []

    def fake_fetch_live(repo: Any, run_id: Any) -> tuple[str, str]:
        calls.append((repo, run_id))
        return ("LIVE_RUN", "LIVE_JOBS")

    original_fetch_live = module.fetch_live
    module.fetch_live = fake_fetch_live
    try:
        expect_error(module, module.inputs, Args(), expected=choose_message)

        with tempfile.TemporaryDirectory(prefix="github-delivery-inputs-") as temporary:
            run_path = Path(temporary) / "run.json"
            jobs_path = Path(temporary) / "jobs.json"
            run_path.write_text(json.dumps({"r": 1}), encoding="utf-8")
            jobs_path.write_text(json.dumps({"j": 1}), encoding="utf-8")

            expect_error(module, module.inputs, Args(run_json=run_path), expected=fixtures_message)
            expect_error(module, module.inputs, Args(jobs_json=jobs_path), expected=fixtures_message)
            expect_error(
                module, module.inputs, Args(run_json=run_path, jobs_json="not-a-path"), expected=fixtures_message
            )

            result = module.inputs(Args(run_json=run_path, jobs_json=jobs_path))
            require(result == ({"r": 1}, {"j": 1}), "inputs did not load both JSON fixtures correctly")

        expect_error(module, module.inputs, Args(repo="not a repo"), expected="live GitHub input is invalid")
        require(calls == [], f"a rejected repository pattern must never reach fetch_live: {calls}")

        result = module.inputs(Args(repo="owner/repository", run_id=42))
        require(result == ("LIVE_RUN", "LIVE_JOBS"), "inputs did not return the live fetch result")
        require(calls == [("owner/repository", 42)], f"fetch_live was called with the wrong arguments: {calls}")
    finally:
        module.fetch_live = original_fetch_live


REQUIRED_FLAGS = (
    "--run-id",
    "--sha",
    "--workflow",
    "--expected-repository",
    "--workflow-id",
    "--workflow-path",
    "--event",
    "--ref",
    "--run-attempt",
    "--check-suite-id",
)


def common_pairs() -> list[tuple[str, str]]:
    return [
        ("--run-id", "123"),
        ("--sha", SHA),
        ("--workflow", "Production"),
        ("--expected-repository", "owner/repository"),
        ("--workflow-id", "77"),
        ("--workflow-path", ".github/workflows/production.yml@main"),
        ("--event", "workflow_dispatch"),
        ("--ref", "main"),
        ("--run-attempt", "2"),
        ("--check-suite-id", "456"),
    ]


def full_pairs_for_parser() -> list[tuple[str, str]]:
    return [("--run-json", "run.json"), ("--jobs-json", "jobs.json"), *common_pairs()]


def build_argv(
    pairs: list[tuple[str, str]], *, omit: tuple[str, ...] = (), overrides: dict[str, str] | None = None
) -> list[str]:
    overrides = overrides or {}
    argv: list[str] = []
    for flag, value in pairs:
        if flag in omit:
            continue
        argv.extend([flag, overrides.get(flag, value)])
    return argv


def check_parser(module: Any) -> None:
    require(module.parser().description == module.__doc__, "parser lost its description")
    pairs = full_pairs_for_parser()
    for flag in REQUIRED_FLAGS:
        argv = build_argv(pairs, omit=(flag,))
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                module.parser().parse_args(argv)
        except SystemExit as exc:
            require(exc.code == 2, f"missing {flag} exited with {exc.code}, not 2")
        else:
            fail(f"{flag} stopped being required by the parser")

    parsed = module.parser().parse_args(build_argv(pairs))
    require(parsed.require_job == [], "require-job default drifted from an empty list")
    require(parsed.require_step == [], "require-step default drifted from an empty list")
    require(parsed.reusable_workflow == [], "reusable-workflow default drifted from an empty list")


def write_fixture(directory: Path, name: str, payload: dict[str, Any]) -> Path:
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_main(module: Any, argv: list[str]) -> tuple[int, str, str]:
    return run_main_for(module, argv, "github_delivery.py")


def check_main(module: Any) -> None:
    with tempfile.TemporaryDirectory(prefix="github-delivery-main-") as temporary:
        directory = Path(temporary)
        run, jobs = base_fixture()
        run_path = write_fixture(directory, "run.json", run)
        jobs_path = write_fixture(directory, "jobs.json", jobs)

        pairs = [
            ("--run-json", str(run_path)),
            ("--jobs-json", str(jobs_path)),
            *common_pairs(),
            ("--reusable-workflow", f"owner/reusable/.github/workflows/deploy.yml@v1::{REUSABLE_SHA}::refs/tags/v1"),
            ("--require-job", "quality"),
            ("--require-step", "deploy::Deploy production"),
        ]

        code, out, err = run_main(module, build_argv(pairs))
        require(code == 0, f"the fully valid CLI fixture did not pass: {err}")
        expected_pass = (
            "github-delivery: PASS"
            f" sha={SHA}"
            " workflow=Production"
            " workflow_id=77"
            " attempt=2"
            " run_id=123"
            " required_jobs=2"
            " required_steps=1"
        )
        require(out.strip() == expected_pass, f"PASS line drifted: {out.strip()!r}")

        code, _out, err = run_main(module, build_argv(pairs, overrides={"--sha": "not-a-sha"}))
        require(code == 1, "an invalid SHA did not fail the CLI")
        require(
            err.strip() == "github-delivery: FAIL delivery SHA must be a full lowercase SHA-1",
            f"unexpected SHA failure message: {err.strip()!r}",
        )

        code, _out, err = run_main(module, build_argv(pairs, overrides={"--expected-repository": "bad repo"}))
        require(code == 1, "an invalid expected repository did not fail the CLI")
        require(
            err.strip() == "github-delivery: FAIL expected repository identity is invalid",
            f"unexpected repository failure message: {err.strip()!r}",
        )

        contract_message = "github-delivery: FAIL workflow and required job/step contract are required"
        for overrides in (
            {"--workflow": ""},
            {"--workflow-path": "bad/path.yml"},
            {"--event": ""},
            {"--ref": ""},
            {"--run-id": "0"},
        ):
            code, _out, err = run_main(module, build_argv(pairs, overrides=overrides))
            require(code == 1, f"contract violation {overrides} did not fail the CLI")
            require(err.strip() == contract_message, f"unexpected contract failure for {overrides}: {err.strip()!r}")

        code, _out, err = run_main(module, build_argv(pairs, omit=("--require-job", "--require-step")))
        require(code == 1, "dropping both require-job and require-step did not fail the CLI")
        require(err.strip() == contract_message, f"unexpected message with no requirements: {err.strip()!r}")

        code, _out, err = run_main(module, build_argv(pairs, omit=("--require-step",)))
        require(code == 0, f"a job-only requirement should still pass: {err}")

        code, _out, err = run_main(module, build_argv(pairs, omit=("--require-job",)))
        require(code == 0, f"a step-only requirement should still pass: {err}")

        boundary_run = dict(run)
        boundary_run.update(
            {"id": 1, "workflow_id": 1, "run_attempt": 1, "check_suite_id": 1, "referenced_workflows": []}
        )
        boundary_run_path = write_fixture(directory, "boundary_run.json", boundary_run)
        boundary_pairs = [
            (flag, value)
            for flag, value in pairs
            if flag
            not in {
                "--run-json",
                "--run-id",
                "--workflow-id",
                "--run-attempt",
                "--check-suite-id",
                "--reusable-workflow",
            }
        ]
        boundary_pairs = [("--run-json", str(boundary_run_path)), *boundary_pairs]
        boundary_pairs.extend(
            [("--run-id", "1"), ("--workflow-id", "1"), ("--run-attempt", "1"), ("--check-suite-id", "1")]
        )
        code, _out, err = run_main(module, [token for pair in boundary_pairs for token in pair])
        require(code == 0, f"the minimum-boundary ids of 1 should still pass: {err}")


def main() -> int:
    module = load_verifier()
    check_require_mapping(module)
    check_require_success(module)
    check_require_exact(module)
    check_parse_step(module)
    check_parse_reusable(module)
    check_reusable_identity(module)
    check_verify_delivery(module)
    check_verify_delivery_job_cache(module)
    check_load_json(module)
    check_inputs(module)
    check_parser(module)
    check_main(module)
    print("github-delivery-survivors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
