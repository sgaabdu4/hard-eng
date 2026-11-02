#!/usr/bin/env bash
set -u
label=$1
shift
nproc
uv sync --locked
mkdir -p coverage
semgrep_start=$(date +%s.%N)
(
  uvx semgrep@latest scan --config p/python --jobs 2 --error --strict --time --json --output coverage/semgrep.json setup.py new_project.py release_canary.py .hooks tests > coverage/semgrep.log 2>&1
  echo "SEMGREP_SECONDS $(echo "$(date +%s.%N) - $semgrep_start" | bc)"
) &
start=$(date +%s.%N)
uv run --no-sync --with pytest --upgrade-package pytest --with pytest-cov --upgrade-package pytest-cov --with pytest-xdist --upgrade-package pytest-xdist --with pyyaml pytest "$@" --durations=60 --durations-min=0 --cov --cov-report=json:coverage/coverage.json --junitxml=coverage/junit.xml
rc=$?
echo "PYTEST_WALL $label $(echo "$(date +%s.%N) - $start" | bc) exit=$rc"
wait
