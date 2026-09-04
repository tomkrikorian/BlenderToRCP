# BlenderToRCP

BlenderToRCP is a Blender add-on that exports scenes to `.usda`, `.usdc`, or
`.usdz` and rewrites Blender materials into MaterialX ShaderGraph graphs that
Reality Composer Pro can open and edit. It includes a command-line interface,
so you can also drive exports from a terminal or an AI agent without opening
the Blender UI.

## Who it's for

- Blender artists who want scenes and materials to arrive intact in Reality
  Composer Pro and RealityKit.
- Developers and AI agents who control exports from the terminal through the
  [CLI](#cli).
- Contributors who want to extend the add-on. Start with
  [Contribute to the Blender add-on](#contribute-to-the-blender-add-on).

## Key features

- **USD and USDZ export**: write `.usda`, `.usdc`, or `.usdz` through a
  Reality Composer Pro friendly pipeline
  ([docs/EXPORT_PIPELINE.md](docs/EXPORT_PIPELINE.md)).
- **CLI remote control**: export, bake, validate, and manage settings from the
  terminal — no Blender UI needed ([docs/CLI.md](docs/CLI.md)).
- **Strict material validation**: unsupported nodes fail export with
  copy/pasteable errors instead of silently degrading
  ([docs/MATERIAL_TRANSLATION.md](docs/MATERIAL_TRANSLATION.md)).
- **RealityKit material rewrite**: supported Blender shader graphs become
  MaterialX graphs that Reality Composer Pro can edit
  ([docs/MATERIAL_TRANSLATION.md](docs/MATERIAL_TRANSLATION.md)).
- **Portable exports**: textures and auxiliary assets are staged next to the
  exported USD and rewritten to relative paths
  ([docs/EXPORT_PIPELINE.md](docs/EXPORT_PIPELINE.md)).
- **Animation export**: actions can be concatenated for export. Reality
  Composer Pro clip-library metadata is experimental and opt-in; RCP 3 build
  `80.0.1.500.1` flattens authored named clip definitions to the aggregate
  animation during supported USD import
  ([docs/EXPORT_PIPELINE.md](docs/EXPORT_PIPELINE.md)).
- **Profile-driven texture baking**: when the selected material type requires
  a bake, the single Export button runs it in a second Blender process and
  keeps the UI responsive ([docs/BAKING.md](docs/BAKING.md)).
- **Shader authoring helpers**: insert RealityKit PBR or Unlit node groups,
  browse a generated RealityKit node menu, and validate active materials in
  the Shader Editor.

## Requirements

- Blender 5.2.x. Release 2.x deliberately targets the Blender 5.2 API, and
  the extension manifest enforces a minimum of Blender 5.2.0. Blender 5.1 and
  earlier are unsupported, and the codebase does not carry compatibility
  branches for them. Later Blender releases still need to pass this
  repository's Blender integration suite before they can be treated as
  supported.

Contributor requirements are listed under
[Contribute to the Blender add-on](#contribute-to-the-blender-add-on).

## Quick start

1. Download the release asset `BlenderToRCP-<version>.zip` from GitHub
   Releases. Use the matching `.zip.sha256` asset to verify the download.
2. On macOS, verify both downloads from their containing directory:

```bash
shasum -a 256 -c BlenderToRCP-<version>.zip.sha256
```

3. In Blender, open `Edit > Preferences > Extensions > Add-ons > Install from Disk...`.
4. Select `BlenderToRCP-<version>.zip`.
5. Enable `BlenderToRCP` in the add-ons list.

The export panel appears in the 3D View sidebar under `RCP Exporter`; see
[Where to find it in Blender](#where-to-find-it-in-blender). To drive exports
from the terminal instead, see [CLI](#cli).

## Documentation

Full documentation index: [`docs/README.md`](docs/README.md).

| Document | Covers |
|---|---|
| [`docs/ARCHITECTURE.MD`](docs/ARCHITECTURE.MD) | Codebase layout and module responsibilities |
| [`docs/CLI.md`](docs/CLI.md) | Every command, flag, exit code, and the JSON envelope |
| [`docs/SETTINGS.md`](docs/SETTINGS.md) | What every toggle changes, and which settings override each other |
| [`docs/FEATURE_SUPPORT.md`](docs/FEATURE_SUPPORT.md) | Which Blender features survive an export, and which are refused or dropped |
| [`docs/MATERIAL_TRANSLATION.md`](docs/MATERIAL_TRANSLATION.md) | Blender shader graph to RealityKit MaterialX ShaderGraph |
| [`docs/BAKING.md`](docs/BAKING.md) | When a bake runs, what each mode captures, what scene state it overrides |
| [`docs/EXPORT_PIPELINE.md`](docs/EXPORT_PIPELINE.md) | Geometry, units, animation, staging, USDZ packaging |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed in every release, and what breaks on upgrade |

The three pipeline documents each carry a section on the decisions the exporter
makes **on your behalf**, and whether it tells you it made them. Start there if
an export came out differently than you expected.

Upgrading from 1.3.0 is not a drop-in: 2.0.0 removes several settings and
refuses some materials it used to export. The breaking changes are listed first
in [`CHANGELOG.md`](CHANGELOG.md).

Open defects are tracked in
[GitHub Issues](https://github.com/tomkrikorian/BlenderToRCP/issues).

## A compatibility-first exporter

BlenderToRCP is strict by design. Node coverage and graph translation are
intentionally limited, and some Blender materials or scene setups will fail
export until explicit support is added. When export succeeds, validate the
result in Reality Composer Pro or with the repository validation scripts
before relying on it in production.

The default material profile is `realitykit_portable`, which authors the
RealityKit PBR v1 surface and is the mandatory CI path. `realitykit_pbr2`
authors the 30-input PBR Surface 2, verified by import into Reality Composer
Pro 3, and carries every Principled control the portable profile refuses.
`openpbr_1_1` is expanded by Reality Composer Pro into PBR Surface 2 and
loses inputs on the way; the export says which.

### How releases are validated

The Apple validation baseline is Reality Composer Pro 3 with the version-27
Apple SDKs and deployment targets. Automated validation checks fresh USD/USDZ
exports, compiles generated ShaderGraph and `.rkassets` fixtures with
`realitytool`, exercises the Blender CLI, and loads fresh source plus compiled
assets through RealityKit on macOS 27. Interactive import/save/reopen testing
in Reality Composer Pro 3, visual acceptance in Reality Composer Pro or
Quick Look/Spatial Preview, and physical-device testing remain manual release
checks.

## Where to find it in Blender

- `3D View > Sidebar > RCP Exporter`: main export UI, advanced USD export settings, bake settings, job monitor, and diagnostics access.
- `Shader Editor > Sidebar > RCP Exporter > RealityKit Compatibility`: validate the active material and select offending nodes.
- `Shader Editor > Sidebar > RCP Exporter > RealityKit Authoring`: insert RealityKit PBR or Unlit node groups.
- `Shader Editor > Add > RealityKit Nodes`: insert generated RealityKit node groups from the bundled node catalog.

## CLI

BlenderToRCP includes a command-line interface that exports, bakes, validates,
and manages settings without opening the Blender UI. Every command spawns
`blender --background` and returns JSON to stdout on success. For failures,
use `--json` when callers need the structured error envelope on stdout;
without `--json`, the CLI prints a short human-readable error and support
hints to stderr.

### Quick start

```bash
# Set the Blender path (add to ~/.zshrc or ~/.bashrc)
export BLENDERTORCP_BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

# Create an alias for convenience.
# Installed extension (the directory uses the manifest ID):
alias blendertorcp="python3 /path/to/blender_to_rcp"
# Or, for a development checkout:
# alias blendertorcp="python3 /path/to/repo/Plugin"

# Test the connection
blendertorcp version
blendertorcp preferences get
blendertorcp settings list
```

### Usage examples

```bash
# Scene inspection
blendertorcp info scene.blend
blendertorcp list-objects scene.blend --type MESH
blendertorcp list-materials scene.blend

# Validate materials with the same policy used by export
blendertorcp validate scene.blend

# Export to USDZ
blendertorcp export scene.blend -o output.usdz --format USDZ

# Bake textures and export
blendertorcp bake-export scene.blend -o output.usdz --resolution 2048

# Read and modify settings
blendertorcp settings get scene.blend --group bake
blendertorcp settings get scene.blend --group texture
blendertorcp settings set scene.blend export_format=USDZ --dry-run
```

For the full command reference see [`docs/CLI.md`](docs/CLI.md).

## AI agent skills

This repo ships two [Agent Skills](https://skills.sh) — `SKILL.md` files with YAML frontmatter — that let AI agents (Claude, ChatGPT, Copilot, etc.) drive BlenderToRCP from natural language.

### Install skills

```bash
npx skills add tomkrikorian/BlenderToRCP
```

Browse and discover skills at [skills.sh](https://skills.sh).

### Available skills

| Skill | Description |
|-------|-------------|
| `blendertorcp-cli` | Export scenes, bake textures, validate materials, and manage settings via the CLI. |
| `blendertorcp-setup` | Set up the CLI — locate Blender, verify the plugin, configure the shell alias. Also covers troubleshooting. |

Once installed, an agent can respond to prompts like "export my Blender scene to USDZ" or "bake and export my scene at 4K resolution" by invoking the CLI commands automatically.

## Add-on preferences and persisted state

The add-on preferences expose:
- `USDZ Packager Path`: optional path to `usdzip`. If empty, the add-on uses the built-in Python packager.

The add-on also persists the last-used export settings and remembers export paths per `.blend` file. That state lives in Blender preferences, not in the repository.

## Export workflow

The Blender panel has one Export button. Choose `RealityKit PBR` or `RealityKit Unlit`; the profile options determine whether compatible materials are translated directly or baked before export. Direct PBR export validates every scene material in strict mode before writing USD. Export settings are stored on the scene and expose a focused subset of Blender USD export controls, including:
- Root prim naming, selection-only export, animation export, and custom property authoring.
- Name, Unicode, and transform-op controls.
- Geometry and rigging controls such as triangulation, subdivision, armatures, deform bones, and shape keys.
- `Optimization > Optimize Source Textures` can be enabled to resize textures or transcode them to AVIF/PNG during direct PBR export; when disabled, the exporter keeps Apple-compatible AVIF, PNG, JPEG, and OpenEXR inputs in their source encoding and transcodes other LDR image formats to PNG. OpenEXR is always preserved byte-for-byte and ignores resize/format overrides to protect float/HDR data. Radiance HDR (`.hdr`) fails with guidance to convert it to OpenEXR.
- Material validation fails closed by default. `Normalize Unsupported Values` is an explicit export-only exception for one safe case: an unlinked, constant, achromatic Principled `Specular Tint` above `1` is clamped to white. Colored or linked values still stop export. The source material and `.blend` are never modified; diagnostics record the source and exported values.
- Failed exports always write `<output>.diagnostics.json`. `Keep Success Diagnostics` retains the same report after successful exports.

Release 2.x enforces a non-configurable Apple spatial contract: Blender's native orientation conversion, `-Z` forward, `Y` up, meters at scale `1.0`, relative dependencies, and mesh/UV/normal export. Raw cameras, lights, Blender World dome lights, curves, point clouds, volumes, and hair cannot be enabled. One ordinary Blender 5.2 USD camera imported as `PerspectiveCameraComponent` in a macOS 27 smoke, but ordinary `UsdGeom.Camera` has no cross-platform RealityKit renderer guarantee and is therefore rejected by the portable profile. Author cameras and lighting in Reality Composer Pro 3 or RealityKit, and convert unsupported geometry to polygon meshes before export.

Every failed export writes support-oriented diagnostics as `<output>.diagnostics.json`. Successful exports retain that sidecar only when `Keep Success Diagnostics` is enabled. The Diagnostics panel exposes the latest available report and support-bundle actions.

## Profile-driven background baking

When the selected profile requires baking, the single Export button launches a second Blender process, bakes textures, runs the same USD export pipeline, and updates live job status in the panel.

Which option should I choose?

| Goal | Use |
|------|-----|
| Translate compatible materials directly | `RealityKit PBR` → `Translate Materials` |
| Bake complex materials but keep dynamic RealityKit lighting | `RealityKit PBR` → `Bake Materials` |
| Export material color that ignores scene lighting | `RealityKit Unlit` → `Material Color Only` |
| Preserve Blender lighting and shadows | `RealityKit Unlit` → `Lighting & Shadows` |

Operational details:
- The `.blend` file must be saved before starting a background bake.
- Only one background bake/export job can run at a time.
- Job state lives under `<export_dir>/.blendertorcp_jobs/<job_id>/`.
- Each job writes `settings.json`, `status.json`, and `log.txt`; status also records the diagnostics path when available.
- The panel shows progress, output path, log path, diagnostics path, and the current step, and supports cancel, clear, log open, diagnostics open, and support bundle actions.
- The optional per-step watchdog remains available through the CLI and persisted plugin settings. It is disabled by default and intentionally omitted from the Blender panel.
- Bake/export preflights external image files used by exported objects. Missing, unpacked textures fail early with an actionable pack-or-relink error.
- Baked exports do not validate the source material graph. Unsupported Blender node groups are expected to be resolved by baking; strict graph validation applies to `RealityKit PBR` → `Translate Materials`.

Bake modes:
- `Material Color Only - Unlit` (`UNLIT_ALBEDO`): bakes light-independent material color and rewrites the exported materials as RealityKit Unlit materials, shown as-is and ignoring scene lighting. Blender shadows are not baked.
- `Material Color Only - Lit PBR` (`LIT_ALBEDO`): bakes the same light-independent material color but authors Lit PBR materials so Reality Composer Pro or RealityKit lights the baked color. Blender shadows are not baked. When `RealityKit PBR > Bake Materials` is selected, the `Roughness` option in `Material Settings` chooses between a baked per-texel roughness map and a single averaged roughness value.
- `Lighting & Shadows` (`LIT_IBL`, default): bakes the appearance under the selected lighting source, then still exports the final materials as RealityKit Unlit materials with lighting and shadows encoded into textures. Use this when the USDZ should match the Blender preview.
- `Isolate Meshes for Shadows`: hides non-target meshes during lighting-and-shadows bakes to avoid cross-mesh shadow contribution.
- `Optimization`: sets bake resolution, image format, and margin for baked routes. For direct PBR export, `Optimize Source Textures` enables maximum-resolution and format overrides; `Original` keeps Apple-compatible AVIF, PNG, JPEG, and OpenEXR encodings and `Keep Original` leaves source dimensions untouched. Unsupported LDR inputs are normalized to PNG. OpenEXR always bypasses overrides, while Radiance HDR must be converted to OpenEXR first. AVIF textures are written natively by Blender.

## Material authoring and diagnostics

BlenderToRCP is not export-only. The Shader Editor integration also supports:
- Validating the active material against the current RealityKit compatibility rules.
- Selecting offending nodes after validation.
- Inserting bundled RealityKit PBR and Unlit node groups.
- Browsing the generated RealityKit node catalog through `Add > RealityKit Nodes`.

Diagnostics workflow:
- Export failures always write diagnostics; `Keep Success Diagnostics` controls successful-export sidecars.
- The diagnostics dialog summarizes converted and failed materials, copied and converted textures, fallback nodes, KTX-required nodes, omitted nodes, and truncated warning/error lists.
- Diagnostics JSON can be inspected directly or opened in Blender's Text Editor for troubleshooting.
- Support bundles are redacted ZIP files created from the Blender UI or with `blendertorcp support-bundle scene.blend -o output.usdz --diagnostics output.diagnostics.json`.
- Support bundles include environment, scene/settings, asset dependency diagnostics, and export diagnostics. They include material validation only for non-baked exports. Background job files are included by the UI action for the active job or by passing `--job-dir` to the CLI. Source `.blend` files and exported assets are opt-in.
- Redaction covers absolute paths in plain text and JSON-escaped Windows path strings; `--no-redact` disables that protection.


## Troubleshooting and support capture

For CLI failures, capture stdout and stderr separately:

```bash
blendertorcp --verbose export scene.blend -o output.usdz --format USDZ \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

Attach `blendertorcp-result.json`, `blendertorcp-stderr.log`, the exact command, `blendertorcp version`, `blendertorcp preferences get`, the returned `.diagnostics.json`, and a redacted support bundle. For background bake/export, also include `<export_dir>/.blendertorcp_jobs/<job_id>/settings.json`, `status.json`, and `log.txt` or use the support bundle action.
Use `--json` for automated support capture so load failures, validation failures, diagnostics paths, support-bundle hints, and process-output tails stay in a machine-readable JSON envelope.

## Contribute to the Blender add-on

### Requirements
- Blender 5.2.x. Release 2.x targets the 5.2 API and does not support earlier Blender versions.
- Python 3.13 for parity with CI and Blender 5.2. The standalone release packager supports Python 3.9 or newer.
- Git LFS. This repo stores `.png` and `.usda` via LFS.
- `pytest` for the test suites. The release packager itself uses the Python 3.9+ standard library.
- OpenUSD Python bindings (`pxr`) in Blender for material rewriting and validation helpers.

The Apple 27 validation lane additionally requires an Apple-silicon host running macOS 27, Xcode 27 selected with `DEVELOPER_DIR` or `xcode-select`, Reality Composer Pro 3 installed, and these command-line tools:

- `usdchecker`
- `usdcat`
- `xcrun realitytool`

### Local setup
1. Clone the repo and pull LFS assets:

```bash
git lfs install
git lfs pull
```

2. Ensure Blender's user extension repository exists on macOS.
Replace `<version>` with your installed Blender major.minor version, for example `5.2`:

```bash
mkdir -p ~/Library/Application\ Support/Blender/<version>/extensions/user_default
```

3. Symlink the add-on into Blender's extension repository:

```bash
ln -s "<path-to-this-repo>/Plugin" \
  "$HOME/Library/Application Support/Blender/<version>/extensions/user_default/blender_to_rcp"
```

4. Enable the add-on in Blender.

5. Verify the CLI against the checkout:

```bash
python3 "<path-to-this-repo>/Plugin" --blender /Applications/Blender.app/Contents/MacOS/Blender version
python3 "<path-to-this-repo>/Plugin" --blender /Applications/Blender.app/Contents/MacOS/Blender preferences get
python3 "<path-to-this-repo>/Plugin" --blender /Applications/Blender.app/Contents/MacOS/Blender settings list
```

### Contributor quick start
Run the portable checks from the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install pytest==9.1.1 usd-core==26.8 numpy==2.3.4 PyYAML==6.0.3 pillow==12.3.0
python3 -m compileall -q Plugin scripts tests
git diff --check
bash tests/test_check_apple27_toolchain.sh
python3 scripts/tests/test_release_archive.py -q

python3 scripts/build_materialx_manifest.py
git diff --exit-code -- Plugin/manifest/rk_nodes_manifest.json

python3 -m pytest -q tests/unit \
  -k "not test_cli_entrypoint_works_when_extension_folder_is_named_blendertorcp"

# Build twice and verify manifest metadata, archive contents, determinism,
# filename, and SHA-256 sidecar.
bash scripts/check_release.sh

# Equivalent packaging entry point.
bash scripts/build_archive.sh --check
```

Then run the Blender lane against Blender 5.2:

```bash
export BLENDERTORCP_BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
python3 -m pytest -q \
  tests/integration \
  tests/unit/test_cli_parser.py::test_cli_entrypoint_works_when_extension_folder_is_named_blendertorcp

# Fail if the shipped binary differs semantically from a fresh Blender 5.2
# build (catalog, interfaces, metadata, preview nodes, and topology).
"$BLENDERTORCP_BLENDER" \
  --background \
  --factory-startup \
  --python-exit-code 1 \
  --python scripts/check_nodegroup_parity.py

archive="$(find dist -maxdepth 1 -type f -name 'BlenderToRCP-*.zip' -print -quit)"
test -n "$archive"
python3 scripts/smoke_extension_archive.py \
  --archive "$archive" \
  --blender "$BLENDERTORCP_BLENDER"
```

On a machine provisioned for the Apple 27 lane, use a clean Python environment and install only pytest. Do not install PyPI `usd-core` into this environment: the Apple lane must resolve `usdchecker` and `usdcat` from the selected Xcode 27 toolchain.

```bash
apple27_env="$(mktemp -d /tmp/blendertorcp-apple27.XXXXXX)"
python3 -m venv "$apple27_env/venv"
source "$apple27_env/venv/bin/activate"
python -m pip install pytest==9.1.1

bash scripts/check_apple27_toolchain.sh

"$BLENDERTORCP_BLENDER" \
  --background \
  --factory-startup \
  --python scripts/validate_nodes.py \
  -- \
  --output tests/node_validation \
  --platform xros \
  --deployment-target 27.0

python scripts/validate_exports.py \
  --input <export-dir-or-usd> \
  --platform macosx \
  --deployment-target 27.0 \
  --use-metal \
  --compiled-output-dir "$apple27_env/compiled" \
  --output <validation-report.json>

# Load the fresh USDC/USDZ and the exact .reality file retained by the
# validation command. Add the fixture-specific animation-key expectations used
# by the protected workflow for animated assets.
scripts/run_realitykit_runtime_smoke.sh \
  --asset <fresh-export.usdc> --expect-model --expect-shader-graph \
  --asset <fresh-export.usdz> --expect-model --expect-shader-graph \
  --asset <compiled-output.reality> --expect-model --expect-shader-graph \
  --output "$apple27_env/realitykit-runtime.json"

```

Regenerate checked-in material assets only when their sources change:

```bash
python3 scripts/build_materialx_manifest.py
"$BLENDERTORCP_BLENDER" \
  --background \
  --factory-startup \
  --python-exit-code 1 \
  --python scripts/build_nodegroups.py
```

Notes:
- `scripts/check_release.sh` is the local release gate. It uses only Python 3.9+ standard-library modules plus the shell entry point, and does not create tags or GitHub releases.
- A successful check writes `dist/BlenderToRCP-<version>.zip` and `dist/BlenderToRCP-<version>.zip.sha256`, where `<version>` comes from `Plugin/blender_manifest.toml`.
- For a tag build, `bash scripts/check_release.sh --expected-tag 2.0.0` additionally requires the exact bare-semver tag to match the manifest version.
- `scripts/smoke_extension_archive.py` installs the built ZIP into isolated Blender user resources and tests the installed extension rather than the checkout. It requires the canonical `bl_ext.user_default.blender_to_rcp` module, registered scene settings, no duplicate `Plugin.*` modules, the packaged Blender 5.2 node-group interfaces and clean on-demand asset loading, bundled license/notices, and working installed `version` and `settings list` commands. It also exports a tiny default-material scene to USDC and USDZ through the installed CLI, opens both with Blender's USD runtime to verify geometry, binding, and the portable RealityKit ShaderGraph, enforces the packaged USDZ contract, runs strict `usdchecker` when available, conditionally compiles both assets with Xcode 27 `realitytool`, and exercises the background bake runner's controlled empty-scene preflight.
- `scripts/build_materialx_manifest.py` rebuilds `Plugin/manifest/rk_nodes_manifest.json` from `References/MaterialX-definitions`.
- `scripts/build_nodegroups.py` regenerates `Plugin/assets/nodegroups.blend`; `scripts/check_nodegroup_parity.py` independently rebuilds the library with Blender 5.2 and fails if its semantic signature differs from the shipped binary.
- `scripts/validate_nodes.py` writes generated bundles and reports under `tests/node_validation` by default and can compile each fixture with `realitytool`.
- `scripts/validate_exports.py` validates exported USD, USDZ, or `.rkassets` inputs with strict `usdchecker`, nodedef/path lint, and optional `realitytool` compilation. USDZ inputs are safely expanded into the temporary `.rkassets` compile staging because nesting a USDZ file can make `realitytool` 27 exit successfully while emitting a runtime-unloadable artifact. `--compiled-output-dir` retains collision-safe, deterministic `.reality` outputs for the runtime gate instead of compiling throwaway artifacts.
- `scripts/run_realitykit_runtime_smoke.sh` builds the public-API RealityKit probe with Xcode 27 and recursively verifies model, ShaderGraph material, animation-library/clip, and required component-type expectations while loading source and compiled assets on macOS 27.

## Release and packaging flow

Release metadata has one source of truth: `Plugin/blender_manifest.toml`. The runtime version, versioned archive name, release tag check, and checksum sidecar all derive from it.

The workflows divide the gates by trust and toolchain:

| Event | Automated gates |
|---|---|
| Pull request | `.github/workflows/ci.yml`: compile check, unit tests, archive build/validation/installed-extension smoke, and Blender 5.2 integration tests on GitHub-hosted Linux. The protected Apple runner is not exposed to pull requests. |
| Push to `dev` | Portable CI. Apple 27 verification is manual: run `scripts/verify_apple_platform.sh` on a Mac. |
| Push to `main` | Portable CI. Run `scripts/verify_apple_platform.sh` on a Mac before promoting a release candidate. |
| Manual workflow dispatch | The release workflow accepts dry runs only from trusted `dev`. Dry runs never publish a GitHub release. |
| Push of a bare `X.Y.Z` tag | `.github/workflows/build-archive.yml` first requires the tagged commit to be reachable from `origin/dev`, then calls the portable validation workflow, verifies that the tag exactly matches the manifest version, builds one deterministic versioned archive and checksum, and publishes only after every gate succeeds. |

Apple 27 verification is not automated. There is no self-hosted runner, and the
workflow that assumed one was removed — it never ran, and its assertions rotted
unnoticed. Run it yourself on a Mac carrying Blender 5.2, Xcode 27, the
version-27 SDKs and Reality Composer Pro 3:

```bash
scripts/verify_apple_platform.sh
```

It runs the integration suite, exports the fixtures, checks the expected
Specular Tint refusal, runs `usdchecker` strict and ARKit-strict, guards the
shipping profile against an experimental surface, and compiles for all seven
Apple 27 platforms. `scripts/check_apple27_toolchain.sh` fails first when the
toolchain contract is not met.

None of that proves an asset **renders**. Only importing the evaluation scenes
into Reality Composer Pro does — see
[`References/Blender/TEST_SCENES.md`](References/Blender/TEST_SCENES.md).

Before pushing a release tag:

1. Merge a pull request only after portable CI passes.
2. Confirm the intended release commit is already on `origin/dev`, passed the Apple 27 workflow, and passed the manual Reality Composer Pro/device checks described above.
3. Set `version` in `Plugin/blender_manifest.toml` to the intended bare-semver version.
4. Run `bash scripts/check_release.sh --expected-tag <version>` locally.
5. Push the matching `<version>` tag. The release workflow, not a local command, publishes the ZIP and `.sha256` assets after its own gates pass.

## License

BlenderToRCP has one project license: [GNU GPL version 3 or later](LICENSE), as
declared by `SPDX:GPL-3.0-or-later` in the Blender extension manifest.

The files under `THIRD_PARTY_LICENSES/` and [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)
cover only the Apple, MaterialX, and OpenPBR material redistributed by this
repository. They preserve the upstream MIT and Apache-2.0 notices and do not
make BlenderToRCP a dual-licensed project.
