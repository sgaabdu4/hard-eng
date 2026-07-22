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

copy_path() {
  path=$1
  source_path="$main/$path"
  target_path="$target/$path"

  if [[ ! -f "$source_path" || -L "$source_path" ]]; then
    fail "missing regular source: $path"
    return 1
  fi
  source_real=$(/bin/realpath "$source_path") || {
    fail "cannot resolve source: $path"
    return 1
  }
  if [[ "$source_real" != "$source_path" ]]; then
    fail "symlinked source path forbidden: $path"
    return 1
  fi
  if ! git -C "$main" check-ignore -q -- "$path"; then
    fail "source is not ignored: $path"
    return 1
  fi
  if git -C "$main" ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
    fail "source is tracked: $path"
    return 1
  fi
  [[ ! -e "$target_path" && ! -L "$target_path" ]] || return 0

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
        unsafe_parent=1
        break
      fi
    done
    IFS=$old_ifs
  fi
  [[ "$unsafe_parent" -eq 0 ]] || return 1

  mkdir -p "$parent"
  /usr/bin/install -m 600 "$source_path" "$target_path" || {
    fail "copy failed: $path"
    return 1
  }
}

status=0
while IFS= read -r pattern || [[ -n "$pattern" ]]; do
  pattern=${pattern%$'\r'}
  case "$pattern" in
    ''|'#'*) continue ;;
    '*'|'**'|'/*'|'/**'|'**/*'|'/**/*')
      fail "broad manifest entry forbidden: $pattern"
      status=1
      continue
      ;;
    '!'*|'/'*|'./'*|*'/./'*|*'/.') continue ;;
    '..'|'../'*|*'/../'*|*'/..') continue ;;
  esac
  matched=0
  while IFS= read -r -d '' path; do
    matched=1
    copy_path "$path" || status=1
  done < <(git -C "$main" ls-files -z --others --ignored --exclude-standard -- "$pattern")
  if [[ "$matched" -eq 0 ]]; then
    fail "manifest entry matched no ignored files: $pattern"
    status=1
  fi
done < "$manifest"

exit "$status"
