#!/usr/bin/env bash
set -euo pipefail

# Safe, local release preflight. This only writes versioned artifacts under
# dist/; it never creates tags, pushes commits, or publishes a release.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec bash "${REPO_ROOT}/scripts/build_archive.sh" --check "$@"
