#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$root/.venv-mutation"
[ -x "$venv/bin/python" ] || python3 -m venv "$venv"
"$venv/bin/python" -m pip install --quiet --disable-pip-version-check --requirement "$root/requirements-mutation.txt"
"$venv/bin/python" -m pip show mutmut | sed -n "s/^Version: /mutmut /p"
