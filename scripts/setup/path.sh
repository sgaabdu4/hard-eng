#!/bin/bash
set -eu

START_MARKER='# >>> hard-eng managed PATH >>>'
END_MARKER='# <<< hard-eng managed PATH <<<'

fail() {
  printf 'setup:path: %s\n' "$1" >&2
  exit 1
}

selected_shell() {
  shell_name=${SHELL:-}
  shell_name=${shell_name##*/}
  case "$shell_name" in
    zsh|bash|fish) printf '%s\n' "$shell_name" ;;
    *) fail "unsupported shell: ${SHELL:-unset}" ;;
  esac
}

profile_path() {
  shell_name=$(selected_shell)
  case "$shell_name" in
    zsh) printf '%s/.zshrc\n' "$HOME" ;;
    bash) printf '%s/.bashrc\n' "$HOME" ;;
    fish)
      config_home=${XDG_CONFIG_HOME:-$HOME/.config}
      case "$config_home" in
        /*) ;;
        *) fail "XDG_CONFIG_HOME must be absolute: $config_home" ;;
      esac
      [ "$config_home" = / ] || config_home=${config_home%/}
      printf '%s/fish/config.fish\n' "$config_home"
      ;;
  esac
}

render_profile() {
  profile=$1
  destination=$2
  mode=$3
  snapshot=$4
  shell_kind=$(selected_shell)
  PROFILE_PATH=$profile DESTINATION_PATH=$destination SNAPSHOT_PATH=$snapshot SETUP_PATH_MODE=$mode \
    START_MARKER=$START_MARKER END_MARKER=$END_MARKER SHELL_KIND=$shell_kind python3 - <<'PY'
import hashlib
import os
import stat
from pathlib import Path

profile = Path(os.environ["PROFILE_PATH"])
destination = Path(os.environ["DESTINATION_PATH"])
snapshot = Path(os.environ["SNAPSHOT_PATH"])
mode = os.environ["SETUP_PATH_MODE"]
start = os.environ["START_MARKER"]
end = os.environ["END_MARKER"]
if os.environ["SHELL_KIND"] == "fish":
    block = (
        f"{start}\n"
        'set -gx PATH "$HOME/.local/bin" '
        '(string match -v -- "$HOME/.local/bin" $PATH)\n'
        f"{end}\n"
    )
else:
    block = (
        f"{start}\n"
        'case ":${PATH}:" in\n'
        '  ":${HOME}/.local/bin:"*) ;;\n'
        '  *) export PATH="${HOME}/.local/bin:${PATH}" ;;\n'
        "esac\n"
        f"{end}\n"
    )

if os.path.lexists(profile):
    metadata = os.lstat(profile)
    if not stat.S_ISREG(metadata.st_mode):
        raise SystemExit("setup:path: profile is not a regular file; refusing to replace it")
    raw = profile.read_bytes()
    try:
        current = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise SystemExit("setup:path: profile is not valid UTF-8; refusing to replace it")
    signature = f"file:{hashlib.sha256(raw).hexdigest()}"
    target_mode = stat.S_IMODE(metadata.st_mode)
else:
    current = ""
    signature = "absent"
    target_mode = 0o600

lines = current.splitlines(keepends=True)
starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == start]
ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == end]
if not starts and not ends:
    prefix = current
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += "\n"
    if prefix:
        prefix += "\n"
    updated = prefix + block
elif len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0]:
    updated = "".join(lines[: starts[0]]) + block + "".join(lines[ends[0] + 1 :])
else:
    raise SystemExit("setup:path: malformed or duplicate managed PATH markers")

if updated == current:
    raise SystemExit(3)
if mode == "check":
    raise SystemExit(4)

snapshot.write_text(signature, encoding="ascii")
with destination.open("wb") as handle:
    handle.write(updated.encode("utf-8"))
    handle.flush()
    os.fsync(handle.fileno())
os.chmod(destination, target_mode)
PY
}

verify_profile_snapshot() {
  profile=$1
  snapshot=$2
  PROFILE_PATH=$profile SNAPSHOT_PATH=$snapshot python3 - <<'PY'
import hashlib
import os
import stat
from pathlib import Path

profile = Path(os.environ["PROFILE_PATH"])
snapshot = Path(os.environ["SNAPSHOT_PATH"])
expected = snapshot.read_text(encoding="ascii")
if os.path.lexists(profile):
    metadata = os.lstat(profile)
    if not stat.S_ISREG(metadata.st_mode):
        raise SystemExit("setup:path: profile changed type during convergence")
    actual = f"file:{hashlib.sha256(profile.read_bytes()).hexdigest()}"
else:
    actual = "absent"
if actual != expected:
    raise SystemExit("setup:path: profile changed during convergence; leaving the user edit untouched")
PY
}

install_path() {
  command -v python3 >/dev/null 2>&1 || fail "missing required command: python3"
  profile=$(profile_path)
  profile_dir=$(dirname "$profile")
  mkdir -p "$profile_dir"
  lock=$profile_dir/.hard-eng-path.lock
  mkdir "$lock" 2>/dev/null || fail "another PATH convergence is active: $lock"
  temporary=
  backup=
  trap 'rm -f "$temporary"; [ -z "$backup" ] || rm -f "$backup"; [ -z "$lock" ] || rmdir "$lock" 2>/dev/null || true' EXIT HUP INT TERM
  temporary=$(mktemp "$profile_dir/.hard-eng-path.XXXXXX")
  snapshot=$temporary.snapshot
  trap 'rm -f "$temporary" "$snapshot"; [ -z "$backup" ] || rm -f "$backup"; [ -z "$lock" ] || rmdir "$lock" 2>/dev/null || true' EXIT HUP INT TERM

  set +e
  render_profile "$profile" "$temporary" install "$snapshot"
  status=$?
  set -e
  case "$status" in
    0) ;;
    3)
      printf 'setup:path: PASS unchanged (%s)\n' "$profile"
      return
      ;;
    *) return "$status" ;;
  esac

  verify_profile_snapshot "$profile" "$snapshot"
  if [ -e "$profile" ]; then
    backup_dir=$HOME/.local/share/hard-eng/backups/shell
    (umask 077 && mkdir -p "$backup_dir")
    [ -d "$backup_dir" ] && [ ! -L "$backup_dir" ] || fail "backup owner is not a regular directory: $backup_dir"
    chmod 700 "$backup_dir"
    backup=$backup_dir/$(basename "$profile").$(date +%Y%m%dT%H%M%S).$$.bak
    cp -p "$profile" "$backup"
    chmod 600 "$backup"
  fi
  verify_profile_snapshot "$profile" "$snapshot"
  mv "$temporary" "$profile"
  temporary=
  rm -f "$snapshot"
  snapshot=
  rmdir "$lock"
  lock=
  trap - EXIT HUP INT TERM
  printf 'setup:path: PASS installed (%s)\n' "$profile"
}

check_path() {
  command -v python3 >/dev/null 2>&1 || fail "missing required command: python3"
  profile=$(profile_path)
  temporary=$(mktemp "${TMPDIR:-/tmp}/hard-eng-path-check.XXXXXX")
  trap 'rm -f "$temporary"' EXIT HUP INT TERM
  set +e
  render_profile "$profile" "$temporary" check "$temporary.snapshot"
  status=$?
  set -e
  case "$status" in
    3)
      printf 'setup:path: PASS (%s)\n' "$profile"
      ;;
    4) fail "managed PATH block missing or stale: $profile" ;;
    *) return "$status" ;;
  esac
}

case "${1:-install}" in
  preflight) profile_path >/dev/null ;;
  install) install_path ;;
  check) check_path ;;
  *) fail "usage: $0 [preflight|install|check]" ;;
esac
