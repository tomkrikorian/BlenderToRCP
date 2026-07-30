# The Apple platform contract: OpenUSD and MaterialX on OS 27 / RCP 3

Measured 2026-07-30 against: macOS 27.0 beta (Darwin 27.0), Reality Composer
Pro 3.0 build `80.0.1.500.1`, Xcode 27.0 beta (27A5228h) with the
macOS/iOS/xrOS 27.0 SDKs, Apple USD Tools 0.25.11 (`/usr/bin/usdchecker`).
Everything below is binary/filesystem measurement of those artifacts —
`strings`, `otool`, `plutil`, `diff`, nodedef-set arithmetic, and crate-header
probing — not Apple documentation. Claims another machine can re-derive cite
their evidence path. Re-verify after any OS, RCP, or Xcode update; the pinned
tests listed at the end fail loudly on the most important drift.

## The headline: one shared stack, no editor/runtime gap

The 27 generation collapsed the distinction that used to make targeting
RealityKit uncertain:

- **One USD library everywhere.** RCP 3, the RealityKit runtime on all
  platforms, `/usr/bin/usd*`, Xcode's `realitytool`, and the new public
  `USDKit.framework` all sit on Apple's own USD fork (project **USDLib**), on
  macOS the single image `/usr/lib/usd/libusd_ms.dylib` (24.1.7, C++ namespace
  `pxrInternal__aapl__pxrReserved__`). RCP still embeds a copy, but it is the
  same project six source-revisions apart — packaging, not divergence.
- **One MaterialX nodedef universe everywhere.** macOS 27 ships
  `ShaderGraph.framework` as a public OS SubFramework
  (`/System/Library/SubFrameworks/ShaderGraph.framework`), and its MaterialX
  library tree is **byte-identical** to the one inside RCP 3 (`diff -rq`
  clean). The Xcode platform `AssetRuntime` mirrors show the identical set on
  iOS/visionOS/tvOS 27. Shader-graph compilation is public runtime API
  (`ShaderGraphMaterial`, `Entity.precompileShaderGraphMaterials(from:)` in
  the 27 SDKs): ND_ resolution happens on-device at USDZ load, not only at
  RCP/realitytool compile time.
- **RCP's bundled "SystemFrameworks" are not a fork.** All 24 bundled
  frameworks (RealityKit, RealityFoundation, CoreRE, ShaderGraph, ...) have
  CFBundleVersions identical to the macOS 27 copies and are loaded via
  `LC_DYLD_ENVIRONMENT DYLD_VERSIONED_FRAMEWORK_PATH` — a back-deployment
  snapshot that only wins on hosts older than the build (min host 26.5). On
  a current OS, RCP previews with the shipping runtime.
- **What is genuinely RCP-only** lives in `Contents/Frameworks`: the
  CoreRealityTools / 107-plugin `libtm-*` editor engine (Our Machinery's
  "The Truth" data model — the owner of the `.import` format, see
  [RCP_IMPORT_EXPERIMENT.md](RCP_IMPORT_EXPERIMENT.md)), the Mosaic UI, and
  ML generation services. `.import` is editor infrastructure; **USDZ +
  MaterialX is the shared runtime contract.**

Consequence for this project: validating an export against RCP 3 and
`usdchecker` is a faithful proxy for the device runtime — same library, same
ceilings, same nodedef universe.

## OpenUSD: exactly what is supported

"USD version" is three different numbers. All three were measured.

### 1. Library feature set

Apple's USDLib declares base **OpenUSD 0.24.07**
(`RealityComposerPro.app/Contents/usr/OpenSourceVersions/USDLib.plist`) but
carries backports far past it. Symbols present in `libusd_ms.dylib` and the
RCP binaries: animation splines (`TsSpline`, upstream 24.11),
`UsdColorSpaceAPI` (25.02), `VtArrayEdit` and the `usdValidation` framework
(25.08+), `SdfPathExpression`, `SdfRelocates`, `UsdNamespaceEditor`,
`UsdGeomTetMesh`. Functional profile: **≈ OpenUSD 25.08–25.11** (a
late-2025 upstream snapshot). Nothing from upstream 26.x is present.

### 2. Binary crate format (`.usdc`, inside `.usdz`) — the number that decides whether a file opens

| | Version | Evidence |
|---|---|---|
| **Read ceiling** | **crate 0.14.0** | crate-header byte probe against `libusd_ms`: 0.14 accepted, 0.15/0.16 rejected ("Sdf crate file version mismatch"); RCP's binaries carry the same version-gate messages up to 0.14 (`VtArrayEdit`) |
| Write default | crate 0.8.0 | `PXR-USDC` header bytes of a `usdcat`-written file; RCP writes the same; env overrides exist (`USD_WRITE_NEW_USDC_FILES_AS_VERSION`) |

Crate versions are feature-gated: 0.10 pathExpressions, 0.11 relocates,
0.12–0.13 splines, 0.14 array edits. A writer only stamps a higher version
when the file actually uses such a feature; otherwise 0.8 is universal.

### 3. Text format (`.usda`)

Read ceiling **`#usda 1.2`** (1.3 rejected: "The maximum supported version is
'1.2'"); writes `#usda 1.0`.

### What this means for the exporter

Blender 5.2 embeds pxr **26.03** and the test venv uses usd-core **26.8** —
both newer than Apple's snapshot, and that is fine: upstream's write defaults
are still **crate 0.8.0 / `#usda 1.0`**, far below the ceilings. Every file
this exporter produces today opens in RCP 3 and on every OS 27 runtime.

The compatibility contract to target is **Apple's ceilings, not upstream's
release number**. The failure mode to watch is any future feature that forces
the writer past crate 0.14 / usda 1.2, or a post-25.11 schema Apple's
snapshot lacks — it would fail identically in RCP and on-device, so the
existing RCP + `usdchecker` validation lane catches it. Current headroom is
enormous; the nearest real features (splines at crate 0.12–0.13, array edits
at 0.14) still fit.

### USDKit (new public API in the 27 SDKs)

`USDKit.framework` (106.0.7, availability-gated `27.0` on every platform) is
a full public Swift USD API over the same USDLib: stages, layers, prims,
composition/list-ops, variants, ArResolver, plus
`USDStage.exportPackage(to:)` — a public on-device USDZ writer.
`_USDKit_RealityKit` adds `USDStageComponent` (a live USD stage attached to a
RealityKit `Entity`) and `USDPlayer`. Strategic reading: Apple is converging
on USD-native runtime loading, which strengthens USDZ as this project's
first-class deliverable and keeps `.import` a convenience lane for
RCP-centric workflows.

## MaterialX / ShaderGraph: exactly what is supported

### The nodedef universe

- The runtime tree (`/System/Library/SubFrameworks/ShaderGraph.framework/
  Versions/A/Resources/MaterialX`) is a MaterialX **1.38 + 1.39.4** hybrid:
  the vendored MaterialX-1.39.4 stdlib/bxdf, a 1.38 compatibility set, and
  Apple's own `Apple/apple_nodedefs*` trees (RealityKit surfaces, half-type
  variants, swizzle support for 1.39). Identical on RCP 3 and, by SDK
  evidence, on iOS/visionOS/tvOS 27.
- **Of this project's 928-nodedef manifest, 872 resolve at runtime; exactly
  56 do not** — and those are precisely the ids flagged
  `policy.editor_unresolvable` in `Plugin/manifest/rk_nodes_manifest.json`:
  the pbrlib closure domain (BSDF/EDF/VDF, displacement, `ND_surface`,
  `ND_volume`, `ND_light`, roughness helpers) and the stdlib `arrayappend`
  family. They exist in the OS only inside CoreRealityIO's USD *parsing*
  libraries — a USDZ referencing them parses but cannot be rendered by any
  Apple 27 runtime. The flag is therefore a runtime truth, not an RCP editor
  quirk; selection and preflight refuse these ids
  ([MATERIAL_TRANSLATION.md](MATERIAL_TRANSLATION.md)).
- Everything the exporter authors — `ND_realitykit_pbr_surfaceshader` (v1 and
  `_2_0`), `ND_realitykit_unlit_surfaceshader`, the `ND_image_*` family
  (including `uaddressmode`/`vaddressmode`/`filtertype`), `place2d`,
  `texcoord`, `normal_map_decode`, `normalmap`, `luminance_color3`, the
  swizzle chains — is signature-identical in the shipped libraries. No
  color3→float `convert` exists anywhere (the exporter's
  luminance + swizzle chain is the correct construction).
- The shipped surface beyond our manifest (~1,380 extra runtime ids) includes
  ~130 authorable 1.39.4 stdlib nodes the manifest does not know yet
  (`fract`, `safepower`, `distance`, `logical_*`, `round`, procedural
  patterns, `hextiledimage`, ...) — candidates for closing translation gaps,
  tracked as future work.

### Colour management

The engine (CoreRE) resolves textures through an alias table whose canonical
tokens are `srgb_texture`, `srgb_rec709_scene`, `lin_rec709`,
`lin_rec709_scene`, Display-P3/Rec.2020/ACEScg variants, and the data tokens
`raw`/`data`/`none`. Blender's OCIO name **`srgb_rec709_display` appears
nowhere in the stack** — its decode behaviour is undefined, which is why the
export postprocess renames it to `srgb_texture` and the preflight rejects it
(see MATERIAL_TRANSLATION.md, colour-space section).

### Spatial contract nuances (measured)

- `metersPerUnit` is **converted** on import by RCP, not rejected; `upAxis`
  is normalized on import. The exporter's preflight still enforces Y-up /
  metersPerUnit 1 because direct RealityKit loading has no such
  normalization pass and Apple's validators only check the metadata exists.
- `doubleSided` is honoured by the editor's renderer but absent from the
  RealityKit runtime surface — an asset relying on it looks right in RCP and
  wrong on device. The exporter forces `doubleSided = false` for exactly this
  reason.

## Drift detection

The load-bearing facts above are pinned by tests that run against the locally
installed artifacts and skip when absent:

- `tests/unit/test_manifest_matches_editor_libraries.py` — recomputes the
  56-id unresolvable set from the installed ShaderGraph libraries.
- `tests/unit/test_rcp_contract_matches_type_index.py` — holds the `.import`
  contract to RCP's shipped Truth schema (`__type_index.tm_meta`).
- `tests/unit/test_material_os27.py` — pins the manifest's RCP build
  (`80.0.1.500.1`) and the PBR2 surface contract.

After an OS/RCP/Xcode update, run those first; a failure there is the
earliest signal that this document needs re-measuring.
