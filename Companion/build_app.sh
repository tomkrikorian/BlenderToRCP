#!/bin/bash
# Build RCPPreview.app and register it with LaunchServices so the Blender
# add-on can launch it by bundle id (`open -b com.studiomeije.blendertorcp.preview`).
#
# Requires: Xcode 27+ selected (`xcode-select -p`), XcodeGen (`brew install xcodegen`).
set -euo pipefail
cd "$(dirname "$0")"

CONFIG="${1:-Debug}"

echo "==> Generating Xcode project"
xcodegen generate

echo "==> Building ($CONFIG)"
xcodebuild \
  -project RCPPreview.xcodeproj \
  -scheme RCPPreview \
  -configuration "$CONFIG" \
  -derivedDataPath build \
  CODE_SIGN_IDENTITY="-" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=YES \
  build

APP="build/Build/Products/$CONFIG/RCPPreview.app"
echo "==> Built: $APP"

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ -x "$LSREGISTER" ]; then
  "$LSREGISTER" -f "$APP" && echo "==> Registered with LaunchServices"
fi

echo
echo "Done. Install by moving it to /Applications, or set the 'RealityKit"
echo "Preview App' path in the BlenderToRCP add-on preferences to:"
echo "  $(pwd)/$APP"
