#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
YES="${HARD_ENG_UNINSTALL_YES:-0}"
source "$ROOT/scripts/no-mistakes-wrapper-install.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/uninstall.sh --yes [--dry-run]

Removes Hard Eng-managed links, skills, hooks, cron blocks, shell PATH block,
watchdog LaunchAgent, managed Codex bin files, and Hard Eng caches.
Shared prerequisites such as Homebrew, Git, Node, Dart, Flutter, Treehouse, and
no-mistakes are not removed because they may be used outside this repo.
If Hard Eng installed the `no-mistakes` command wrapper, uninstall restores the
normal symlink to the shared `no-mistakes` binary.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --yes) YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if [[ "$YES" != "1" ]]; then
  echo "Refusing uninstall without --yes." >&2
  exit 2
fi

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'dry-run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

remove_if_symlink_to() {
  local target="$1"
  local prefix="$2"
  [[ -L "$target" ]] || return 0
  case "$(readlink "$target")" in
    "$prefix"|"$prefix"/*) run rm -f "$target" ;;
  esac
}

remove_exact_stub() {
  local target="$1"
  [[ -f "$target" ]] || return 0
  if [[ "$(cat "$target")" == "@AGENTS.md" ]]; then
    run rm -f "$target"
  fi
}

remove_managed_file() {
  local target="$1"
  [[ -f "$target" ]] || return 0
  if grep -q 'Managed by hard-eng installer' "$target" 2>/dev/null; then
    run rm -f "$target"
  fi
}

restore_no_mistakes_link() {
  local nm_home="${NO_MISTAKES_HOME:-$HOME/.no-mistakes}"
  local link_dir="${NO_MISTAKES_LINK_DIR:-$HOME/.local/bin}"
  local link_path="$link_dir/no-mistakes"
  local real_binary="$nm_home/bin/no-mistakes"
  local embedded_real_binary

  [[ -f "$link_path" ]] || return 0
  if ! is_managed_no_mistakes_wrapper "$link_path"; then
    return 0
  fi
  if embedded_real_binary="$(read_no_mistakes_wrapper_assignment "$link_path" HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN)" &&
    [[ -x "$embedded_real_binary" ]]; then
    real_binary="$embedded_real_binary"
  fi
  if [[ ! -x "$real_binary" ]]; then
    echo "Preserving managed no-mistakes wrapper because upstream binary is missing: $real_binary" >&2
    return 0
  fi
  run rm -f "$link_path"
  run ln -s "$real_binary" "$link_path"
}

remove_shell_block() {
  local target="${HARD_ENG_SHELL_ENV_FILE:-$HOME/.zshenv}"
  local tmp
  [[ -f "$target" ]] || return 0
  tmp="${target}.hard-eng-uninstall.$$"
  awk \
    -v begin="# BEGIN hard-eng bootstrap path" \
    -v end="# END hard-eng bootstrap path" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$target" >"$tmp"
  if [[ "$DRY_RUN" == "1" ]]; then
    run mv "$tmp" "$target"
    rm -f "$tmp"
  else
    mv "$tmp" "$target"
  fi
}

remove_cron_blocks() {
  command -v crontab >/dev/null 2>&1 || return 0
  local current tmp
  current="$(crontab -l 2>/dev/null || true)"
  tmp="$(mktemp)"
  printf '%s\n' "$current" | awk \
    -v begin="# BEGIN hard-eng auto-sync" \
    -v end="# END hard-eng auto-sync" \
    -v stack_begin="# BEGIN hard-eng codex-stack-update" \
    -v stack_end="# END hard-eng codex-stack-update" '
      $0 == begin || $0 == stack_begin { skip = 1; next }
      $0 == end || $0 == stack_end { skip = 0; next }
      !skip { print }
    ' >"$tmp"
  run crontab "$tmp"
  rm -f "$tmp"
}

remove_launch_agent() {
  [[ "$(uname -s)" == "Darwin" ]] || return 0
  local label plist
  if command -v launchctl >/dev/null 2>&1; then
    label="dev.hard-eng.codex-watchdog"
    run launchctl bootout "gui/$(id -u)/$label" >/dev/null 2>&1 || true
    run launchctl disable "gui/$(id -u)/$label" >/dev/null 2>&1 || true
  fi
  label="dev.hard-eng.codex-watchdog"
  plist="$HOME/Library/LaunchAgents/${label}.plist"
  [[ -e "$plist" ]] && run rm -f "$plist"
  return 0
}

remove_hooks() {
  git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || return 0
  local hooks_dir hook
  hooks_dir="$(git -C "$ROOT" rev-parse --git-path hooks)"
  [[ "$hooks_dir" == /* ]] || hooks_dir="$ROOT/$hooks_dir"
  for hook in post-merge post-rewrite pre-commit pre-push; do
    remove_managed_file "$hooks_dir/$hook"
  done
}

remove_codex_config_entries() {
  local target="$HOME/.codex/config.toml"
  [[ -f "$target" ]] || return 0
  if [[ "$DRY_RUN" == "1" ]]; then
    run printf '%s\n' "would remove Hard Eng Codex config entries from $target"
    return 0
  fi
  python3 - "$target" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
lines = path.read_text().splitlines()
section_re = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
managed_mcp_section_prefixes = (
    "mcp_servers.codebase-memory-mcp",
    "mcp_servers.context-mode",
    "mcp_servers.dart",
)
def is_managed_mcp_section(section):
    return any(section == prefix or section.startswith(f"{prefix}.") for prefix in managed_mcp_section_prefixes)
drop_sections = {
    match.group(1).strip()
    for line in lines
    if (match := section_re.match(line)) and is_managed_mcp_section(match.group(1).strip())
}
drop_top = {
    'approval_policy = "never"',
    'sandbox_mode = "danger-full-access"',
}
drop_features = {
    'hooks = true',
    'default_mode_request_user_input = true',
}
out = []
index = 0
while index < len(lines):
    match = section_re.match(lines[index])
    if not match:
        if lines[index].strip() not in drop_top:
            out.append(lines[index])
        index += 1
        continue
    section = match.group(1).strip()
    block = [lines[index]]
    index += 1
    while index < len(lines) and not section_re.match(lines[index]):
        block.append(lines[index])
        index += 1
    if section in drop_sections:
        continue
    if section == "features":
        kept = [block[0], *[line for line in block[1:] if line.strip() not in drop_features]]
        if any(line.strip() for line in kept[1:]):
            out.extend(kept)
        continue
    out.extend(block)
text = "\n".join(out).strip()
if text:
    path.write_text(text + "\n")
else:
    path.unlink()
PY
}

remove_context_mode_permissions() {
  local settings_path
  for settings_path in "$HOME/.codex/settings.json" "$HOME/.copilot/settings.json"; do
    [[ -f "$settings_path" ]] || continue
    if [[ "$DRY_RUN" == "1" ]]; then
      run printf '%s\n' "would remove Hard Eng permission entries from $settings_path"
      continue
    fi
    SETTINGS_PATH="$settings_path" AGENTS_ROOT="$ROOT" python3 <<'PY'
from pathlib import Path
import json
import os

path = Path(os.environ["SETTINGS_PATH"])
root = Path(os.environ["AGENTS_ROOT"])
home = Path.home()
data = json.loads(path.read_text())
allow = data.get("permissions", {}).get("allow")
if isinstance(allow, list):
    def variants(path):
        values = {str(path), str(path.resolve())}
        return values | {item.replace("/private/var/", "/var/") for item in values} | {item.replace("/var/", "/private/var/", 1) for item in values if item.startswith("/var/")}
    homes = variants(home)
    roots = variants(root)
    managed = {
        *(f"Read({item}/.codex/skills/**)" for item in homes),
        *(f"Read({item}/skills/**)" for item in roots),
        *(f"Read({item}/vendor/skill-upstreams/**)" for item in roots),
    }
    data["permissions"]["allow"] = [entry for entry in allow if entry not in managed]
path.write_text(json.dumps(data, indent=2) + "\n")
PY
  done
  return 0
}

for target in \
  "$HOME/.codex/AGENTS.md" "$HOME/.codex/mcp-config.json" "$HOME/.codex/hooks.json" \
  "$HOME/.claude/AGENTS.md" "$HOME/.copilot/AGENTS.md" "$HOME/.pi/AGENTS.md" "$HOME/.pi/agent/AGENTS.md"; do
  remove_if_symlink_to "$target" "$ROOT"
done
remove_exact_stub "$HOME/.claude/CLAUDE.md"

HARD_ENG_DRY_RUN="$DRY_RUN" node "$ROOT/scripts/manage-skills.mjs" remove

for name in codex-watchdog codex-health codex-context-mode-health codex-cleanup codex-update-stack; do
  remove_managed_file "$HOME/.codex/bin/$name"
done

remove_hooks
restore_no_mistakes_link
remove_launch_agent
remove_cron_blocks
remove_shell_block
remove_codex_config_entries
remove_context_mode_permissions
run rm -f "${HARD_ENG_SKILL_CONFIG:-$HOME/.config/hard-eng/skills.json}"
run rm -rf "$HOME/.cache/hard-eng"

echo "Hard Eng uninstall complete."
