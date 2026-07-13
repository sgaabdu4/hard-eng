#!/bin/bash
set -u

NULL_REF=0000000000000000000000000000000000000000

fail() {
  printf 'worktree-env: %s\n' "$1" >&2
  return 1
}

[[ "${1:-}" == "$NULL_REF" && "${3:-}" == "1" ]] || exit 0

target=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
target=$(cd "$target" && pwd -P) || exit 1
main=
while IFS= read -r -d '' record; do
  case "$record" in
    "worktree "*) main=${record#worktree }; break ;;
  esac
done < <(git worktree list --porcelain -z 2>/dev/null)

[[ -n "$main" ]] || exit 0
main=$(cd "$main" && pwd -P) || exit 1
[[ "$target" != "$main" ]] || exit 0

manifest="$target/.worktreeinclude"
[[ -f "$manifest" && ! -L "$manifest" ]] || exit 0
git -C "$target" ls-files --error-unmatch -- .worktreeinclude >/dev/null 2>&1 ||
  fail '.worktreeinclude must be tracked' || exit 1

status=0
while IFS= read -r path || [[ -n "$path" ]]; do
  path=${path%$'\r'}
  case "$path" in
    ''|'#'*) continue ;;
    '!'*|'/'*|'./'*|*'/./'*|*'/.') continue ;;
    '..'|'../'*|*'/../'*|*'/..') continue ;;
  esac

  name=${path##*/}
  case "$name" in
    .env|.env.*) ;;
    *) continue ;;
  esac
  case "$path" in
    *'*'*|*'?'*|*'['*)
      fail "literal .env path required: $path"
      status=1
      continue
      ;;
  esac

  source_path="$main/$path"
  target_path="$target/$path"

  if [[ ! -f "$source_path" || -L "$source_path" ]]; then
    fail "missing regular source: $path"
    status=1
    continue
  fi
  source_real=$(/bin/realpath "$source_path") || {
    fail "cannot resolve source: $path"
    status=1
    continue
  }
  if [[ "$source_real" != "$source_path" ]]; then
    fail "symlinked source path forbidden: $path"
    status=1
    continue
  fi
  if ! git -C "$main" check-ignore -q -- "$path"; then
    fail "source is not ignored: $path"
    status=1
    continue
  fi
  if git -C "$main" ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
    fail "source is tracked: $path"
    status=1
    continue
  fi
  [[ ! -e "$target_path" && ! -L "$target_path" ]] || continue

  unsafe_parent=0
  parent="$target/${path%/*}"
  [[ "$path" == */* ]] || parent=$target
  cursor=$target
  relative_parent=${parent#"$target"/}
  if [[ "$parent" != "$target" ]]; then
    old_ifs=$IFS
    IFS=/
    for part in $relative_parent; do
      cursor="$cursor/$part"
      if [[ -L "$cursor" || ( -e "$cursor" && ! -d "$cursor" ) ]]; then
        fail "unsafe target parent: $path"
        status=1
        unsafe_parent=1
        break
      fi
    done
    IFS=$old_ifs
  fi
  [[ "$unsafe_parent" -eq 0 ]] || continue

  mkdir -p "$parent"
  if ! /usr/bin/install -m 600 "$source_path" "$target_path"; then
    fail "copy failed: $path"
    status=1
  fi
done < "$manifest"

exit "$status"
