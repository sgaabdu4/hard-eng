#!/usr/bin/env python3
"""Read and validate the canonical setup dependency manifest."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import NoReturn


MANIFEST_PATH = Path(__file__).with_name("manifest.json")
PLATFORMS = {"macos-arm64", "macos-amd64", "linux-arm64", "linux-amd64"}
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
HEX_128 = re.compile(r"^[0-9a-f]{128}$")
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
RELATIVE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
EXPECTED_NPM_NAMES = {"codebase-memory-mcp", "context-mode", "ctx7"}
BINARY_SOURCES = {
    "codebase-memory-mcp": "https://github.com/DeusData/codebase-memory-mcp/",
    "jq": "https://github.com/jqlang/jq/",
    "rtk": "https://github.com/rtk-ai/rtk/",
}


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup:manifest: {message}")


def load_manifest() -> dict:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read manifest: {error}")
    if not isinstance(value, dict):
        fail("root must be an object")
    return value


def validate(manifest: dict) -> None:
    if set(manifest) != {
        "schema_version",
        "requirements",
        "codex",
        "copilot",
        "npm_runtime",
        "binaries",
    }:
        fail("top-level keys mismatch")
    if manifest.get("schema_version") != 1:
        fail("unsupported schema_version")
    requirements = manifest.get("requirements")
    if not isinstance(requirements, dict) or set(requirements) != {"node_min"}:
        fail("requirements keys mismatch")
    node_min = requirements.get("node_min")
    if not isinstance(node_min, str) or not VERSION.fullmatch(node_min):
        fail("requirements.node_min must be a semantic version")

    codex = manifest.get("codex")
    if not isinstance(codex, dict) or set(codex) != {"context_mode"}:
        fail("codex keys mismatch")
    context_mode = codex.get("context_mode")
    if not isinstance(context_mode, dict):
        fail("codex.context_mode must be an object")
    expected_context_keys = {
        "marketplace_repo",
        "marketplace_name",
        "marketplace_source",
        "marketplace_ref",
        "marketplace_commit",
        "plugin_id",
        "version",
    }
    if set(context_mode) != expected_context_keys:
        fail("codex.context_mode keys mismatch")
    context_version = context_mode.get("version")
    if (
        context_mode.get("marketplace_repo") != "mksglu/context-mode"
        or context_mode.get("marketplace_name") != "context-mode"
        or context_mode.get("marketplace_source")
        != "https://github.com/mksglu/context-mode.git"
        or context_mode.get("plugin_id") != "context-mode@context-mode"
        or not isinstance(context_version, str)
        or not VERSION.fullmatch(context_version)
        or context_mode.get("marketplace_ref") != f"v{context_version}"
        or not isinstance(context_mode.get("marketplace_commit"), str)
        or not HEX_40.fullmatch(context_mode["marketplace_commit"])
    ):
        fail("invalid Codex Context Mode contract")

    copilot = manifest.get("copilot")
    if not isinstance(copilot, dict) or set(copilot) != {"context_mode"}:
        fail("copilot keys mismatch")
    copilot_context = copilot.get("context_mode")
    if not isinstance(copilot_context, dict) or set(copilot_context) != {
        "plugin_name",
        "plugin_source_subdir",
    }:
        fail("copilot.context_mode keys mismatch")
    plugin_name = copilot_context.get("plugin_name")
    plugin_source_subdir = copilot_context.get("plugin_source_subdir")
    if (
        not isinstance(plugin_name, str)
        or not isinstance(plugin_source_subdir, str)
        or plugin_name != context_mode.get("plugin_id", "").split("@", 1)[0]
        or plugin_source_subdir != "configs/copilot-cli"
        or not RELATIVE_PATH.fullmatch(plugin_source_subdir)
    ):
        fail("invalid Copilot Context Mode contract")

    npm_runtime = manifest.get("npm_runtime")
    if (
        not isinstance(npm_runtime, dict)
        or set(npm_runtime) != {"packages", "remove_paths"}
    ):
        fail("npm_runtime keys mismatch")
    packages = npm_runtime.get("packages")
    if not isinstance(packages, list) or not packages:
        fail("npm_runtime.packages must be a non-empty list")
    names: set[str] = set()
    for package in packages:
        if not isinstance(package, dict):
            fail("npm package entry must be an object")
        if set(package) != {"name", "version", "sha512", "tree_exclusions"}:
            fail("npm package keys mismatch")
        name = package.get("name")
        version = package.get("version")
        checksum = package.get("sha512")
        exclusions = package.get("tree_exclusions")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            fail(f"invalid or duplicate npm package: {name!r}")
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            fail(f"invalid npm version: {name}")
        if not isinstance(checksum, str) or not HEX_128.fullmatch(checksum):
            fail(f"invalid npm sha512: {name}")
        if not isinstance(exclusions, list) or not all(
            isinstance(item, str)
            and item
            and RELATIVE_PATH.fullmatch(item)
            and ".." not in Path(item).parts
            for item in exclusions
        ):
            fail(f"invalid npm tree exclusions: {name}")
        names.add(name)
    if names != EXPECTED_NPM_NAMES:
        fail("npm package ownership set mismatch")
    npm_context_version = next(
        package["version"] for package in packages if package["name"] == "context-mode"
    )
    if npm_context_version != context_version:
        fail("Context Mode plugin and shared CLI versions differ")

    remove_paths = npm_runtime.get("remove_paths")
    if not isinstance(remove_paths, list) or not all(
        isinstance(item, str)
        and item
        and RELATIVE_PATH.fullmatch(item)
        and ".." not in Path(item).parts
        for item in remove_paths
    ):
        fail("invalid npm runtime remove_paths")

    binaries = manifest.get("binaries")
    if not isinstance(binaries, dict) or not binaries:
        fail("binaries must be a non-empty object")
    if set(binaries) != set(BINARY_SOURCES):
        fail("binary ownership set mismatch")
    for name, binary in binaries.items():
        if not NAME.fullmatch(name) or not isinstance(binary, dict):
            fail(f"binary entry must be an object: {name}")
        if set(binary) != {"version", "assets"}:
            fail(f"binary keys mismatch: {name}")
        version = binary.get("version")
        assets = binary.get("assets")
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            fail(f"invalid binary version: {name}")
        if not isinstance(assets, dict) or set(assets) != PLATFORMS:
            fail(f"binary platform coverage mismatch: {name}")
        for platform, asset in assets.items():
            if not isinstance(asset, dict):
                fail(f"asset must be an object: {name}/{platform}")
            if set(asset) != {"file", "sha256", "url", "kind"}:
                fail(f"asset keys mismatch: {name}/{platform}")
            filename = asset.get("file")
            checksum = asset.get("sha256")
            url = asset.get("url")
            kind = asset.get("kind")
            if not isinstance(filename, str) or not NAME.fullmatch(filename):
                fail(f"invalid asset filename: {name}/{platform}")
            if not isinstance(checksum, str) or not HEX_64.fullmatch(checksum):
                fail(f"invalid asset sha256: {name}/{platform}")
            if (
                not isinstance(url, str)
                or not url.startswith(BINARY_SOURCES[name])
                or "|" in url
                or any(character.isspace() for character in url)
            ):
                fail(f"invalid asset URL: {name}/{platform}")
            if kind not in {"file", "tar.gz"}:
                fail(f"invalid asset kind: {name}/{platform}")


def get_value(manifest: dict, dotted_path: str):
    value = manifest
    for segment in dotted_path.split("."):
        if not isinstance(value, dict) or segment not in value:
            fail(f"unknown manifest path: {dotted_path}")
        value = value[segment]
    if isinstance(value, (dict, list)):
        fail(f"manifest path is not scalar: {dotted_path}")
    return value


def main(argv: list[str]) -> int:
    manifest = load_manifest()
    validate(manifest)
    command = argv[1] if len(argv) > 1 else "validate"
    if command == "validate":
        print("setup:manifest: PASS")
        return 0
    if command == "get" and len(argv) == 3:
        print(get_value(manifest, argv[2]))
        return 0
    if command == "npm-specs" and len(argv) == 2:
        print(" ".join(
            f"{package['name']}@{package['version']}"
            for package in manifest["npm_runtime"]["packages"]
        ))
        return 0
    if command == "npm-sha512" and len(argv) == 3:
        for package in manifest["npm_runtime"]["packages"]:
            if f"{package['name']}@{package['version']}" == argv[2]:
                print(package["sha512"])
                return 0
        fail(f"unknown npm package: {argv[2]}")
    if command == "npm-exclusions" and len(argv) == 3:
        for package in manifest["npm_runtime"]["packages"]:
            if package["name"] == argv[2]:
                print(" ".join(package["tree_exclusions"]))
                return 0
        fail(f"unknown npm package: {argv[2]}")
    if command == "npm-remove-paths" and len(argv) == 2:
        print(" ".join(manifest["npm_runtime"]["remove_paths"]))
        return 0
    if command == "asset" and len(argv) == 4:
        name, platform = argv[2:]
        binary = manifest.get("binaries", {}).get(name)
        if not isinstance(binary, dict) or platform not in binary["assets"]:
            fail(f"unknown binary asset: {name}/{platform}")
        asset = binary["assets"][platform]
        print("|".join((
            binary["version"],
            asset["file"],
            asset["sha256"],
            asset["url"],
            asset["kind"],
        )))
        return 0
    fail(
        "usage: manifest.py "
        "[validate|get <path>|npm-specs|npm-sha512 <spec>|"
        "npm-exclusions <name>|npm-remove-paths|asset <name> <platform>]"
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
