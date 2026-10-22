"""Create a new project from its stack's official scaffold plus Hard Eng's starter files."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

SOURCE = Path(__file__).resolve().parent
SCAFFOLDS = {
    "flutter": ["flutter", "create", "--empty", "--project-name", "app", "."],
    "nextjs": [
        *("bun", "x", "create-next-app@16.4.0", ".", "--ts", "--app", "--use-bun"),
        *("--biome", "--tailwind", "--no-src-dir", "--import-alias", "@/*"),
        *("--disable-git", "--no-agent-feedback", "--yes"),
    ],
    "opennext": [
        *("bun", "x", "create-cloudflare@2.73.3", "."),
        "--template=github:opennextjs/opennextjs-cloudflare/create-cloudflare/next#2c37a8a4e0679e442dc5232c8b2a58bdbf8189c2",
        *("--no-deploy", "--no-git", "--no-agents", "--no-auto-update"),
    ],
    "vite": ["bun", "x", "create-vite@9.2.1", ".", "--template", "react-ts"],
}
REMOVED = {"opennext": ["eslint.config.mjs"], "vite": [".oxlintrc.json"]}
SCAFFOLD_VERSIONS = {"opennext": ["next"]}
GENERATED = {"opennext": [["bun", "run", "cf-typegen"]]}
EMPTY_REPOSITORY = (
    "No supported project manifest found. New project: ask the user which type to create "
    "(Python, Flutter, Next.js, OpenNext on Cloudflare or React + Vite) unless their request says. "
    "For a web app, never default to Next.js: suggest it only for public pages that need "
    "search ranking or fast first load, and React + Vite for apps behind a login, internal "
    "tools and apps with a separate backend. Then rerun the setup command with "
    "`sh -s -- --new STACK` (flutter, nextjs, opennext or vite): it creates the project with "
    "the official scaffold, adds starter tests and checks, pins each package to the newest "
    "release minimumReleaseAge allows, commits, and installs Hard Eng. A Python project: "
    "`uv init` and `uv lock`, then rerun setup."
)


def run(root: Path, command: list[str]) -> None:
    subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, check=True)


def merged_package(text: str, starter: dict[str, dict[str, str | None]]) -> str:
    """Add the starter's scripts and devDependencies; a null value removes the key."""
    manifest = json.loads(text)
    for section, values in starter.items():
        current = manifest.setdefault(section, {})
        for key, value in values.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
    return json.dumps(manifest, indent=2) + "\n"


def scaffold_versions(root: Path, names: list[str]) -> list[str]:
    """The scaffold's own pins for packages that newer releases break."""
    if not names:
        return []
    manifest = json.loads((root / "package.json").read_text())
    versions = {
        **manifest.get("dependencies", {}),
        **manifest.get("devDependencies", {}),
    }
    return [f"{name}@{versions[name]}" for name in names]


def pinned_pubspec(text: str, lock: dict[str, dict[str, dict[str, str]]]) -> str:
    """Replace each `any` constraint with the version pub resolved."""
    packages = lock["packages"]
    return re.sub(
        r"^(  ([a-z0-9_]+)): any$",
        lambda match: f"{match[1]}: {packages[match[2]]['version']}",
        text,
        flags=re.MULTILINE,
    )


def copy_starter(root: Path, stack: str) -> None:
    starter = SOURCE / ".agents/starters" / stack
    for path in sorted(starter.rglob("*")):
        if not path.is_file():
            continue
        target = root / path.relative_to(starter)
        text = path.read_text()
        if path.name == "package.json":
            text = merged_package(target.read_text(), json.loads(text))
        elif path.name == "pubspec.yaml":
            sdk = re.search(r"^  sdk: (\S+)$", target.read_text(), re.MULTILINE)
            text = text.replace("sdk: SDK", f"sdk: {sdk[1] if sdk else 'SDK'}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


def titled_svgs(root: Path) -> None:
    """Give each scaffold image the title Biome's accessibility rule requires."""
    for path in sorted((root / "public").glob("*.svg")):
        text = path.read_text()
        if "<title>" not in text:
            start = text.index(">", text.index("<svg")) + 1
            path.write_text(f"{text[:start]}<title>{path.stem}</title>{text[start:]}")


def finish_web(root: Path, kept: list[str]) -> None:
    run(root, ["bun", "update", "--latest", "--exact"])
    if kept:
        run(root, ["bun", "add", "--exact", *kept])
    if (root / "biome.json").is_file():
        titled_svgs(root)
        # The scaffold's config targets the Biome it shipped; the update installs a newer one.
        run(root, ["bun", "x", "biome", "migrate", "--write"])
        run(root, ["bun", "x", "biome", "format", "--write", "."])


def finish_flutter(root: Path) -> None:
    skill = SOURCE / ".agents/skills/building-flutter-apps/references"
    shutil.copyfile(skill / "analysis_options.yaml", root / "analysis_options.yaml")
    run(root, ["flutter", "pub", "get"])
    lock = yaml.safe_load((root / "pubspec.lock").read_text())
    pubspec = root / "pubspec.yaml"
    pubspec.write_text(pinned_pubspec(pubspec.read_text(), lock))
    run(root, ["flutter", "pub", "get"])
    run(root, ["dart", "run", "build_runner", "build", "--delete-conflicting-outputs"])
    run(root, ["dart", "format", "lib", "test"])


def create(root: Path, stack: str) -> None:
    if not (root / ".git").exists():
        raise ValueError(f"--new must run at the Git repository root, not {root}")
    present = sorted(path.name for path in root.iterdir() if path.name != ".git")
    if present:
        raise ValueError(
            f"--new needs an empty repository; it holds {', '.join(present)}"
        )
    run(root, SCAFFOLDS[stack])
    for name in REMOVED.get(stack, []):
        (root / name).unlink()
    kept = scaffold_versions(root, SCAFFOLD_VERSIONS.get(stack, []))
    copy_starter(root, stack)
    if stack == "flutter":
        finish_flutter(root)
    else:
        finish_web(root, kept)
    for command in GENERATED.get(stack, []):
        run(root, command)
    run(root, ["git", "add", "--all"])
    run(root, ["git", "commit", "--quiet", "-m", f"Create the {stack} project"])
