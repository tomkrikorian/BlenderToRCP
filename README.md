# BlenderToRCP

Blender add-on to export USD/USDZ and rewrite Blender materials into Reality Composer Pro compatible MaterialX ShaderGraph graphs.

## Key features

- **CLI remote control**: export, bake, validate, and manage settings from the terminal — no Blender UI needed.
- Export `.usda`, `.usdc`, or `.usdz` from Blender with a Reality Composer Pro friendly pipeline.
- Strict material validation: unsupported nodes fail export with copy/pasteable errors instead of silently degrading.
- RealityKit material rewrite: supported Blender shader graphs are rewritten into MaterialX graphs that Reality Composer Pro can edit.
- Portable exports: textures and auxiliary assets are staged next to the USD and rewritten to relative paths.
- Animation compatibility: actions can be concatenated for export; Reality Composer Pro clip-library metadata is opt-in for editor workflows.
- Profile-driven texture baking: the single Blender Export button runs baking in a second process when the selected material type requires it, writes status/log files, and keeps the UI responsive.
- Experimental, build-pinned Reality Composer Pro 3 `.import` generation for the validated one-mesh static, transform-animation, and skeletal subsets. Baked base-color/opacity and roughness texture payloads are supported within that same strict one-mesh boundary.
- Shader authoring helpers: insert RealityKit PBR or Unlit node groups, browse a generated RealityKit node menu, and validate active materials in the Shader Editor.

## Important note
This is still a strict, compatibility-first exporter. Node coverage and graph translation are intentionally limited, and some Blender materials or scene setups will fail export until explicit support is added. When export succeeds, validate the result in Reality Composer Pro or with the repo validation scripts before relying on it in production.

Release 2.x deliberately targets the Blender 5.2 API. Blender 5.1 and earlier are unsupported, and the codebase does not carry compatibility branches for them. The extension manifest enforces a minimum of Blender 5.2.0; later Blender releases still need to pass this repository's Blender integration suite before they can be treated as supported.

The Apple validation baseline is Reality Composer Pro 3 with the version-27 Apple SDKs and deployment targets. Automated validation checks fresh USD/USDZ exports, compiles generated ShaderGraph and `.rkassets` fixtures with `realitytool`, exercises the Blender CLI, and loads fresh source plus compiled assets through RealityKit on macOS 27. Interactive import/save/reopen testing in Reality Composer Pro 3, visual acceptance in Reality Composer Pro or Quick Look/Spatial Preview, and physical-device testing remain manual release checks.

`References/RealityComposerProProject` contains the disposable RCP3 research
corpus used to measure the private `.import` format. `.import` generation is
experimental and pinned to RCP 3.0 build `80.0.1.500.1`; it is not an Apple
published interchange format. See
[`docs/RCP_IMPORT_EXPERIMENT.md`](docs/RCP_IMPORT_EXPERIMENT.md) for its exact
acceptance status and fail-closed boundaries.

The shipping material profile is `realitykit_portable`, which authors the established RealityKit PBR v1 surface and is the mandatory CI path. `realitykit_pbr2` and `openpbr_1_1` are explicit experimental profiles for OS 27 investigation; they are not production compatibility claims or release gates.

This repo supports three workflows:
- Install the Blender add-on.
- Use the CLI to control exports from the terminal or an AI agent.
- Contribute to the add-on.

## Where to find it in Blender
- `3D View > Sidebar > RCP Exporter`: main export UI, advanced USD export settings, bake settings, job monitor, and diagnostics access.
- `Shader Editor > Sidebar > RCP Exporter > RealityKit Compatibility`: validate the active material and select offending nodes.
- `Shader Editor > Sidebar > RCP Exporter > RealityKit Authoring`: insert RealityKit PBR or Unlit node groups.
- `Shader Editor > Add > RealityKit Nodes`: insert generated RealityKit node groups from the bundled node catalog.

## Install the Blender add-on
1. Download the release asset `BlenderToRCP-<version>.zip` from GitHub Releases. The matching `.zip.sha256` asset can be used to verify the download.
2. On macOS, verify both downloads from their containing directory:

```bash
shasum -a 256 -c BlenderToRCP-<version>.zip.sha256
```

3. In Blender, open `Edit > Preferences > Extensions > Add-ons > Install from Disk...`.
4. Select `BlenderToRCP-<version>.zip`.
5. Enable `BlenderToRCP` in the add-ons list.

## CLI

BlenderToRCP includes a command-line interface that can export, bake, validate, and manage settings without opening the Blender UI. Every command spawns `blender --background` and returns JSON to stdout on success. For failures, use `--json` when callers need the structured error envelope on stdout; without `--json`, the CLI prints a short human-readable error and support hints to stderr.

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

# Experimental: bake and generate an adjacent USDA plus RCP3 .import directory
blendertorcp bake-export scene.blend -o output.import \
  --format RCP_IMPORT --bake-mode LIT_IBL --resolution 2048

# Read and modify settings
blendertorcp settings get scene.blend --group bake
blendertorcp settings get scene.blend --group texture
blendertorcp settings set scene.blend export_format=USDZ --dry-run
```

For the full command reference see [`docs/CLI.md`](docs/CLI.md).

## AI agent skills

This repo ships two [OpenAI-format skills](https://skills.sh) that let AI agents (Claude, ChatGPT, Copilot, etc.) drive BlenderToRCP from natural language.

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

Once installed, an agent can respond to prompts like "export my Blender scene to USDZ" or "bake and export Robot.blend at 4K resolution" by invoking the CLI commands automatically.

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
python3 -m pip install pytest==9.1.1 usd-core==26.8
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
- `scripts/validate_exports.py` validates exported USD, USDZ, or `.rkassets` inputs with strict `usdchecker`, nodedef/path lint, and optional `realitytool` compilation. `--compiled-output-dir` retains collision-safe, deterministic `.reality` outputs for the runtime gate instead of compiling throwaway artifacts.
- `scripts/run_realitykit_runtime_smoke.sh` builds the public-API RealityKit probe with Xcode 27 and recursively verifies model, ShaderGraph material, animation-library/clip, and required component-type expectations while loading source and compiled assets on macOS 27.

## Add-on preferences and persisted state
The add-on preferences expose:
- `USDZ Packager Path`: optional path to `usdzip`. If empty, the add-on uses the built-in Python packager.
- `MaterialX Library Path`: optional override for MaterialX definitions. If empty, the add-on uses the bundled references.
- `Default Export Format`

The add-on also persists the last-used export settings and remembers export paths per `.blend` file. That state lives in Blender preferences, not in the repository.

## Export workflow
The Blender panel has one Export button. Choose `RealityKit PBR` or `RealityKit Unlit`; the profile options determine whether compatible materials are translated directly or baked before export. Direct PBR export validates every scene material in strict mode before writing USD. Export settings are stored on the scene and expose a focused subset of Blender USD export controls, including:
- Root prim naming, selection-only export, animation export, and custom property authoring.
- Name, Unicode, and transform-op controls.
- Geometry and rigging controls such as triangulation, subdivision, armatures, deform bones, and shape keys.
- `USD Export: Texture` can be enabled to resize textures or transcode them to AVIF/PNG during `Export Scene`; when disabled, the exporter keeps Apple-compatible AVIF, PNG, JPEG, and OpenEXR inputs in their source encoding and transcodes other LDR image formats to PNG. OpenEXR is always preserved byte-for-byte and ignores resize/format overrides to protect float/HDR data. Radiance HDR (`.hdr`) fails with guidance to convert it to OpenEXR.
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
- `Material Color Only - Lit PBR` (`LIT_ALBEDO`): bakes the same light-independent material color but authors Lit PBR materials so Reality Composer Pro or RealityKit lights the baked color. Blender shadows are not baked. The `Roughness` option under `Advanced Bake Options` chooses between a baked per-texel roughness map and a single averaged roughness value.
- `Lighting & Shadows` (`LIT_IBL`, default): bakes the appearance under the selected lighting source, then still exports the final materials as RealityKit Unlit materials with lighting and shadows encoded into textures. Use this when the USDZ should match the Blender preview.
- `Isolate Meshes for Shadows`: hides non-target meshes during lighting-and-shadows bakes to avoid cross-mesh shadow contribution.
- `USD Export: Texture`: opt in to applying the shared texture resolution, image format, and bake margin settings. For `Export Scene`, `Original` keeps Apple-compatible AVIF, PNG, JPEG, and OpenEXR encodings and `Keep Original` leaves source dimensions untouched; unsupported LDR inputs are normalized to PNG. OpenEXR always bypasses overrides, while Radiance HDR must be converted to OpenEXR first. AVIF textures are written natively by Blender.

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

For a PBR Surface 2 visual comparison of direct, clamp-only, and experimental `specularWeight` redistribution strategies, generate the research fixture described in [`References/SpecularTintResearch/README.md`](References/SpecularTintResearch/README.md). Weight redistribution is deliberately not used by production exports.

## Troubleshooting and support capture
For CLI failures, capture stdout and stderr separately:

```bash
blendertorcp --verbose export scene.blend -o output.usdz --format USDZ \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

Attach `blendertorcp-result.json`, `blendertorcp-stderr.log`, the exact command, `blendertorcp version`, `blendertorcp preferences get`, the returned `.diagnostics.json`, and a redacted support bundle. For background bake/export, also include `<export_dir>/.blendertorcp_jobs/<job_id>/settings.json`, `status.json`, and `log.txt` or use the support bundle action.
Use `--json` for automated support capture so load failures, validation failures, diagnostics paths, support-bundle hints, and process-output tails stay in a machine-readable JSON envelope.

## Release and packaging flow
Release metadata has one source of truth: `Plugin/blender_manifest.toml`. The runtime version, versioned archive name, release tag check, and checksum sidecar all derive from it.

The workflows divide the gates by trust and toolchain:

| Event | Automated gates |
|---|---|
| Pull request | `.github/workflows/ci.yml`: compile check, unit tests, archive build/validation/installed-extension smoke, and Blender 5.2 integration tests on GitHub-hosted Linux. The protected Apple runner is not exposed to pull requests. |
| Push to `dev` | Portable CI always runs. `.github/workflows/apple-platform-validation.yml` also runs on the labelled Apple 27 self-hosted runner when its configured `Plugin`, `References`, `scripts`, `tests`, or workflow paths change. |
| Push to `main` | Portable CI. The release candidate must first pass the protected Apple validation through `dev`; the Apple workflow cannot be dispatched directly from `main`. |
| Manual workflow dispatch | The release workflow accepts dry runs only from trusted `dev`; the protected Apple workflow has no direct manual entry point. Dry runs never publish a GitHub release. |
| Push of a bare `X.Y.Z` tag | `.github/workflows/build-archive.yml` first requires the tagged commit to be reachable from `origin/dev`, then calls both reusable validation workflows, verifies that the tag exactly matches the manifest version, builds one deterministic versioned archive and checksum, and publishes only after every gate succeeds. |

The Apple job requires a self-hosted runner carrying all of these labels:

```text
self-hosted, macOS, ARM64, macos-27, xcode-27,
reality-composer-pro-3, blender-5.2
```

The runner must have Blender 5.2, Xcode 27, the version-27 SDKs, Reality Composer Pro 3, `usdchecker`, `usdcat`, and `realitytool` installed. `scripts/check_apple27_toolchain.sh` fails before validation when that contract is not met.

The Apple gate retains every platform-specific `.reality` file, then loads the fresh and macOS-compiled RedCube, animated-cube, and rigged-character fixtures with public RealityKit APIs. It requires model and ShaderGraph material evidence for every asset, plus animation evidence and the exact expected clip-library keys for the animated fixtures. The runtime JSON report, runtime log, fresh exports, and compiled artifacts are uploaded as release evidence.

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

## Architecture
See `docs/ARCHITECTURE.MD`.
