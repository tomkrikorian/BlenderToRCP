# RCPPreview — RealityKit / Spatial preview companion (macOS)

`RCPPreview.app` is the macOS companion for the BlenderToRCP add-on. It renders
the current Blender scene in **RealityKit** on the desktop and streams it to a
connected **Apple Vision Pro** via the macOS 27 **SpatialPreview** framework.

It is driven entirely by files written by the Blender add-on's live-export
engine — there is no socket protocol.

## Requirements

- macOS 27+ and Xcode 27+ selected (`xcode-select -p` → Xcode-beta).
- [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`).
- For Vision Pro streaming: a Vision Pro connected to this Mac through
  **Mac Virtual Display** (no app is installed on the headset — it uses the
  built-in system viewer).

## Build

```bash
./build_app.sh            # generates the Xcode project, builds, registers with LaunchServices
```

The app is built to `build/Build/Products/Debug/RCPPreview.app` and registered
so the Blender add-on can launch it by bundle id
(`com.studiomeije.blendertorcp.preview`). Move it to `/Applications` to make the
registration permanent, or set the *RealityKit Preview App* path in the
BlenderToRCP add-on preferences.

## How it works

The add-on launches the app with `--session <dir>`, where `<dir>` is under
`~/Library/Caches/com.studiomeije.blendertorcp/live/<pid>/`. The app polls that
directory:

| File | Writer | Contents |
| --- | --- | --- |
| `control.json` | Blender | `{ "desktop": Bool, "stream": Bool }` — which features are active |
| `latest.json` | Blender | `{ "rev": Int, "artifacts": { "desktop": "vNNN/scene.usdc", "stream": "vNNN/scene.usdz" } }` |
| `status.json` | RCPPreview | `{ "rev", "loaded_rev", "streaming", "endpoint", "message", "error" }` — surfaced back in Blender's panel |

- **Desktop (Feature 1):** `USDStage.open()` + `USDStageComponent` in a
  `RealityView` with `.realityViewCameraControls(.orbit)`. Reloads on every new
  revision.
- **Stream (Feature 2):** `DocumentPreviewSession` to a
  `SpatialPreviewEndpoint` discovered via `ConnectedSpatialEndpointObserver`
  (falling back to `SpatialPreviewDevicePicker`). New revisions are pushed with
  `updateContents(url:)`.

## Manual test without Blender

```bash
mkdir -p /tmp/sess/v0001
blendertorcp bake-export some.blend -o /tmp/sess/v0001/scene.usdz   # or copy any usdc/usdz
printf '{"desktop":true,"stream":false}' > /tmp/sess/control.json
printf '{"rev":1,"artifacts":{"desktop":"v0001/scene.usdc"}}' > /tmp/sess/latest.json
open -n build/Build/Products/Debug/RCPPreview.app --args --session /tmp/sess
```

> Beta note: SpatialPreview, USDKit and `USDStageComponent` are macOS 27 beta
> APIs; symbol names may change before release. Streaming is gated behind the
> overlay frameworks `_SpatialPreview_USDKit` / `_SpatialPreview_SwiftUI`.
