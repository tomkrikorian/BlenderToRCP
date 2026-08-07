#!/usr/bin/env bash
# Export every evaluation scene to the Reality Composer Pro project's Export
# folder, one directory per scene. Import them into the project yourself.
#
#   scripts/export_test_scenes.sh [FORMAT]      # FORMAT defaults to USDZ
set -uo pipefail

cd "$(dirname "$0")/.."
FORMAT="${1:-USDZ}"
EXT=$(echo "$FORMAT" | tr '[:upper:]' '[:lower:]')
SCENES="References/Blender"
OUT="References/RealityComposerProProject/Export"

: "${BLENDERTORCP_BLENDER:=/Applications/Blender.app/Contents/MacOS/Blender}"
export BLENDERTORCP_BLENDER

failures=0
for blend in "$SCENES"/t*.blend; do
  name=$(basename "$blend" .blend)
  mkdir -p "$OUT/$name"
  if python3 Plugin export "$blend" -o "$OUT/$name/$name.$EXT" --format "$FORMAT" >/dev/null 2>&1; then
    size=$(wc -c < "$OUT/$name/$name.$EXT" | tr -d ' ')
    printf "  %-30s ok    %6s bytes\n" "$name" "$size"
  else
    # A refusal is the expected result for some scenes; see TEST_SCENES.md.
    printf "  %-30s refused\n" "$name"
    failures=$((failures + 1))
  fi
done
echo
echo "$failures scene(s) refused — check TEST_SCENES.md for which are meant to."
