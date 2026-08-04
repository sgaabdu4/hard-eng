#!/usr/bin/env python3
"""Reusable ElevenLabs narration, FFmpeg render, and mechanical QA actor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from media_common import approval_receipt, credential_preflight, failure_receipt
from media_manifest import MediaContractError, read_json, require, validate_manifest
from media_narration import narration
from media_render import qa, render

sys.dont_write_bytecode = True


def preflight(context: dict[str, Any], phase: str, approval_path: Path | None) -> None:
    if phase == "narration":
        require(
            approval_path is not None,
            "narration.preflight",
            "narration preflight requires approval",
        )
        approval_receipt(approval_path, context)
        credential_preflight(context)
        require(
            not (context["artifact_root"] / "narration.json").exists(),
            "narration.preflight",
            "narration output already exists",
        )
    elif phase == "render":
        receipt = read_json(
            context["artifact_root"] / "narration.json", "render.preflight"
        )
        require(
            receipt.get("job_sha256") == context["job_sha256"],
            "render.preflight",
            "narration receipt is stale",
        )
        require(
            not (context["artifact_root"] / "render.json").exists(),
            "render.preflight",
            "render output already exists",
        )
    elif phase == "qa":
        receipt = read_json(context["artifact_root"] / "render.json", "qa.preflight")
        require(
            receipt.get("job_sha256") == context["job_sha256"],
            "qa.preflight",
            "render receipt is stale",
        )
        require(
            not (context["artifact_root"] / "qa-mechanical.json").exists(),
            "qa.preflight",
            "QA output already exists",
        )
    else:
        raise MediaContractError(
            "media.preflight", "phase must be narration, render, or qa"
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "command", choices=("validate", "preflight", "narration", "render", "qa")
    )
    result.add_argument("--job", required=True, type=Path)
    result.add_argument("--phase", choices=("narration", "render", "qa"))
    result.add_argument("--approval", type=Path)
    return result


def main() -> int:
    arguments = parser().parse_args()
    context: dict[str, Any] | None = None
    phase = arguments.command
    try:
        context = validate_manifest(arguments.job.resolve())
        if arguments.command == "validate":
            print(
                f"media-pipeline: PASS | chapters={len(context['chapters'])} "
                f"| characters={context['characters']}"
            )
        elif arguments.command == "preflight":
            require(
                arguments.phase is not None,
                "media.preflight",
                "preflight requires --phase",
            )
            preflight(
                context,
                arguments.phase,
                arguments.approval.resolve() if arguments.approval else None,
            )
            print(f"media-pipeline: PREFLIGHT PASS | phase={arguments.phase}")
        elif arguments.command == "narration":
            require(
                arguments.approval is not None,
                "narration.preflight",
                "narration requires --approval",
            )
            narration(context, arguments.approval.resolve())
        elif arguments.command == "render":
            render(context)
        else:
            qa(context)
        return 0
    except MediaContractError as exc:
        if context is not None:
            failure_receipt(context, phase, exc)
        print(f"media-pipeline: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
