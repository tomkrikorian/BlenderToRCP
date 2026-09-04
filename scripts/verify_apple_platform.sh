#!/usr/bin/env bash
# Apple 27 platform verification, run by hand on a Mac.
#
#   scripts/verify_apple_platform.sh [OUTPUT_DIR]
#
# This was a GitHub Actions workflow targeting a self-hosted runner labelled
# macos-27 / xcode-27 / reality-composer-pro-3 / blender-5.2. No such runner is
# registered, so the job never ran: its last attempt sat queued for 24 hours and
# was cancelled. A workflow that cannot fire still has to be maintained, and its
# assertions rot unnoticed - two of them were wrong for a week before anyone
# looked. Run it here instead, where the machine actually exists.
#
# Needs: macOS 27, Xcode 27 (xcrun usdchecker, realitytool), Blender 5.2, and a
# Python with pytest, usd-core and numpy.
#
# What it does NOT do: prove anything renders. Every check here is a syntax,
# packaging or load check. Only importing the evaluation scenes into Reality
# Composer Pro and looking at them does that - see
# References/Blender/TEST_SCENES.md.

set -uo pipefail

cd "$(dirname "$0")/.."
OUT="${1:-/tmp/blendertorcp-apple-verify}"

: "${BLENDERTORCP_BLENDER:=/Applications/Blender.app/Contents/MacOS/Blender}"
export BLENDERTORCP_BLENDER

failures=0
step() { printf '\n=== %s\n' "$1"; }
check() {
  if "$@"; then
    printf '  ok    %s\n' "$*"
  else
    printf '  FAIL  %s\n' "$*"
    failures=$((failures + 1))
  fi
}

command -v xcrun >/dev/null || { echo "xcrun not found - Xcode 27 required" >&2; exit 1; }
[ -x "$BLENDERTORCP_BLENDER" ] || { echo "Blender not found at $BLENDERTORCP_BLENDER" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT/exports" "$OUT/compiled"
echo "workspace: $OUT"

# ---------------------------------------------------------------------------
step "Integration tests on Apple Silicon"
# ---------------------------------------------------------------------------
check python3 -m pytest -q tests/integration

# ---------------------------------------------------------------------------
step "Export the fixtures"
# ---------------------------------------------------------------------------
export_fixture() {  # name blend [overrides...]
  local name="$1" blend="$2"; shift 2
  mkdir -p "$OUT/exports/$name"
  python3 Plugin --blender "$BLENDERTORCP_BLENDER" --timeout 900 \
    export "$blend" "$@" \
    -o "$OUT/exports/$name/$name.usdc" --format USDC --diagnostics \
    > "$OUT/exports/$name/export-usdc.json"
}

check export_fixture t22_red_cube References/Blender/t22_red_cube.blend
check export_fixture t23_cube_with_4_animations References/Blender/t23_cube_with_4_animations.blend \
  export-animation=true author-animation-library=true
check export_fixture t12_skinned_limb References/Blender/t12_skinned_limb.blend \
  export-animation=true author-animation-library=true

mkdir -p "$OUT/exports/t22_red_cube"
check python3 Plugin --blender "$BLENDERTORCP_BLENDER" --timeout 900 \
  export References/Blender/t22_red_cube.blend \
  -o "$OUT/exports/t22_red_cube/t22_red_cube.usdz" --format USDZ --diagnostics

# ---------------------------------------------------------------------------
step "The Specular Tint refusal"
# ---------------------------------------------------------------------------
# The refusal comes from the material, so the whole scene must be exported. A
# --selected-only run yields NO_EXPORTABLE_OBJECTS instead, which is not what
# this proves.
mkdir -p "$OUT/exports/t21_specular_tint_refusal"
set +e
python3 Plugin --blender "$BLENDERTORCP_BLENDER" --json --timeout 900 \
  export References/Blender/t21_specular_tint_refusal.blend \
  -o "$OUT/exports/t21_specular_tint_refusal/t21_specular_tint_refusal.usdc" --format USDC --diagnostics \
  > "$OUT/exports/t21_specular_tint_refusal/expected-portable-rejection.json"
tint_status=$?
set -e
if [[ "$tint_status" -eq 0 ]]; then
  echo "  FAIL  Specular Tint export unexpectedly succeeded"
  failures=$((failures + 1))
else
  TINT_REPORT="$OUT/exports/t21_specular_tint_refusal/expected-portable-rejection.json" python3 - <<'PY'
import json, os, sys
report = json.load(open(os.environ["TINT_REPORT"]))
error = report.get("error") or {}
assert error.get("code") == "UNSUPPORTED_MATERIAL_NODES", error.get("code")
details = error.get("details") or []
assert any("Specular Tint" in d.get("message", "") for d in details), details
assert any("RealityKit Portable" in d.get("message", "") for d in details), details
print("  ok    refused with UNSUPPORTED_MATERIAL_NODES naming Specular Tint")
PY
  [ $? -eq 0 ] || failures=$((failures + 1))
  check test ! -e "$OUT/exports/t21_specular_tint_refusal/t21_specular_tint_refusal.usdc"
fi

# ---------------------------------------------------------------------------
step "usdchecker, strict and ARKit-strict"
# ---------------------------------------------------------------------------
for asset in \
  "$OUT/exports/t22_red_cube/t22_red_cube.usdc" \
  "$OUT/exports/t23_cube_with_4_animations/t23_cube_with_4_animations.usdc" \
  "$OUT/exports/t12_skinned_limb/t12_skinned_limb.usdc" \
  "$OUT/exports/t22_red_cube/t22_red_cube.usdz"
do
  [ -e "$asset" ] || continue
  check xcrun usdchecker --strict "$asset"
  check xcrun usdchecker --arkit --strict "$asset"
done

# ---------------------------------------------------------------------------
step "The shipping profile is PBR Surface 2, and OpenPBR stays out of it"
# ---------------------------------------------------------------------------
# PBR Surface 2 is the default and is verified by import. OpenPBR is not a
# separate shading model on RealityKit - the editor funnels it into PBR
# Surface 2 and discards sheen, anisotropy, coat colour, transmission and thin
# film - so a default export must never author it.
if [ -e "$OUT/exports/t22_red_cube/t22_red_cube.usdc" ]; then
  profile="$OUT/t22_red_cube-material-profile.usda"
  xcrun usdcat "$OUT/exports/t22_red_cube/t22_red_cube.usdc" --out "$profile"
  check grep -Fq 'realitykit_pbr2' "$profile"
  check grep -Fq 'ND_realitykit_pbr_surfaceshader_2_0"' "$profile"
  if grep -Fq 'ND_open_pbr_surface_surfaceshader' "$profile"; then
    echo "  FAIL  OpenPBR escaped into the default export"
    failures=$((failures + 1))
  else
    echo "  ok    the default export authors PBR Surface 2 and no OpenPBR"
  fi
fi

# ---------------------------------------------------------------------------
step "Compile for every Apple 27 platform"
# ---------------------------------------------------------------------------
for platform in xros xrsimulator macosx iphoneos iphonesimulator appletvos appletvsimulator; do
  for name in t22_red_cube t23_cube_with_4_animations t12_skinned_limb; do
    asset="$OUT/exports/$name/$name.usdc"
    [ -e "$asset" ] || continue
    check python3 scripts/validate_exports.py \
      --input "$asset" \
      --output "$OUT/compiled/$platform/$name" \
      --platform "$platform" \
      --deployment-target 27.0
  done
done

# ---------------------------------------------------------------------------
step "ShaderGraph nodes against RealityKit 27"
# ---------------------------------------------------------------------------
for platform in xros macosx; do
  check "$BLENDERTORCP_BLENDER" --background --factory-startup --python-exit-code 1 \
    --python scripts/validate_nodes.py -- \
    --output "$OUT/nodes-$platform" --platform "$platform" --deployment-target 27.0
done

# ---------------------------------------------------------------------------
printf '\n'
if [ "$failures" -eq 0 ]; then
  echo "All Apple 27 checks passed. Evidence in $OUT"
  echo
  echo "This proves the files parse, package and load. It does not prove they"
  echo "render. Import References/Blender/t*.usdz into Reality Composer Pro and"
  echo "check them against References/Blender/TEST_SCENES.md before releasing."
  exit 0
fi
echo "$failures check(s) failed. Evidence in $OUT"
exit 1
