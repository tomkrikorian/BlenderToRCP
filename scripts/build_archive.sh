#!/usr/bin/env bash
set -euo pipefail

# Build and verify the installable Blender extension archive. The Python helper
# owns the archive format so local and CI builds produce identical bytes.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_PYTHON="${BLENDERTORCP_RELEASE_PYTHON:-python3}"

if ! command -v "${RELEASE_PYTHON}" >/dev/null 2>&1; then
  echo "ERROR: Python 3.9 or newer is required (${RELEASE_PYTHON} not found)" >&2
  exit 1
fi

exec "${RELEASE_PYTHON}" \
  "${REPO_ROOT}/scripts/release_archive.py" \
  --repo-root "${REPO_ROOT}" \
  "$@"
