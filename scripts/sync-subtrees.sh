#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Subtree skills migrated to submodules. Updating submodules from upstream instead."
exec "$ROOT/scripts/update-submodules.sh" --remote
