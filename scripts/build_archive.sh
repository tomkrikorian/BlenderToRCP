#!/usr/bin/env bash
set -euo pipefail

# Builds a Blender extension archive (.zip) that can be installed via:
# Blender -> Edit -> Preferences -> Extensions -> Add-ons -> Install from Disk
#
# Archive structure:
#   BlenderToRCP/              (plugin content folder)
#     __init__.py
#     blender_manifest.toml
#     ...

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUT_DIR="${REPO_ROOT}/dist"
OUT_ZIP="${OUT_DIR}/BlenderToRCP.zip"

CONTENT_FOLDER_NAME="BlenderToRCP"
SOURCE_CONTENT_DIR="${REPO_ROOT}/Plugin"

if [[ ! -d "${SOURCE_CONTENT_DIR}" ]]; then
  echo "ERROR: Missing ${SOURCE_CONTENT_DIR}" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is required to build the archive (install rsync)" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "ERROR: zip is required to build the archive (install zip)" >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGING_DIR}"' EXIT

mkdir -p "${STAGING_DIR}/${CONTENT_FOLDER_NAME}"

# Copy plugin contents (but not the outer folder name) into the archive content folder.
# Exclude caches and Finder metadata.
rsync -a --delete \
  --exclude=".DS_Store" \
  --exclude="__pycache__" \
  --exclude="*.py[cod]" \
  "${SOURCE_CONTENT_DIR}/" \
  "${STAGING_DIR}/${CONTENT_FOLDER_NAME}/"

mkdir -p "${OUT_DIR}"
rm -f "${OUT_ZIP}"

(cd "${STAGING_DIR}" && zip -r "${OUT_ZIP}" "${CONTENT_FOLDER_NAME}" -x "*/.DS_Store" "*.DS_Store" >/dev/null)

echo "Built: ${OUT_ZIP}"
