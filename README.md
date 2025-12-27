# BlenderToRCP

Blender add-on to export USD/USDZ and rewrite Blender materials into Reality Composer Pro compatible MaterialX ShaderGraph graphs.

## Key features
- Export `.usda`, `.usdc`, or `.usdz` from Blender with a Reality Composer Pro friendly pipeline.
- Strict material validation: unsupported nodes fail export with copy/pasteable errors (no silent fallbacks).
- RealityKit material rewrite: converts supported Blender shader graphs into MaterialX graphs that Reality Composer Pro can edit.
- Portable exports: stages texture/assets next to the USD and rewrites all asset paths to be relative.
- Animation compatibility: concatenates actions for export and can author Reality Composer Pro animation clips.
- Bake & Export (background): bakes textures and exports an Unlit material workflow without blocking Blender's UI.

## Important note
This is the first version of BlenderToRCP and node/graph support is intentionally limited.
Many Blender shader graphs (and some scene setups) will not export correctly yet. The exporter runs in a
strict mode by default and will fail with errors when it encounters unsupported nodes or patterns. But even if it does export, it might not export correctly.
In both cases, please report the issue so we can improve the exporter.

--------------------------------

This repo supports two workflows:
- Install the Blender add-on (end users)
- Contribute to the add-on (developers)

## Install the Blender add-on
1) Download the release asset `BlenderToRCP.zip` from GitHub Releases.

2) In Blender:
- **Edit > Preferences > Extensions > Add-ons > Install from Disk...** (recommended for Blender extensions)
- If you're using the classic add-on flow: **Edit > Preferences > Add-ons > Install...**

3) Select `BlenderToRCP.zip`, then enable **BlenderToRCP** in the add-ons list.

## Contribute to the Blender add-on
### Requirements
- Blender 5.0 (target version)
- Python 3 (for developer scripts)
- Git LFS (this repo stores `.png` and `.usda` via LFS)
- OpenUSD Python bindings (pxr) available in Blender (default builds include it)
- Reality Composer Pro (for validation/testing)

### Setup the repo locally
1) Clone the repo and pull LFS assets:

```bash
git lfs install
git lfs pull
```

2) Ensure Blender's user extension repository exists (macOS example):

```bash
mkdir -p ~/Library/Application\ Support/Blender/5.0/extensions/user_default
```

3) Option A (recommended): symlink into Blender's `user_default` extensions repo:

```bash
ln -s "<path-to-this-repo>/Plugin" \
  "$HOME/Library/Application Support/Blender/5.0/extensions/user_default/BlenderToRCP"
```

4) Option B (custom local repo): create a folder and add it as a repository in Blender:
- Create a directory (example): `~/blender-local-addons`
- In Blender: **Edit > Preferences > Extensions > Add-ons** -> **Options** -> **New Repository**
- Symlink `Plugin` into that repository as `BlenderToRCP`

5) Enable the add-on:
- **Edit > Preferences > Extensions > Add-ons**
- Search for **BlenderToRCP**
- Enable it

### Dev loop
- After code changes: **Blender > System > Reload Scripts** (F8) or restart Blender.
- Build the installable zip (matches CI release asset):
  ```bash
  bash scripts/build_archive.sh
  ```

## Developer Tools
- Rebuild MaterialX manifest:
  ```bash
  python3 scripts/build_materialx_manifest.py
  ```
- Build nodegroup previews (optional):
  ```bash
  blender --background --python scripts/build_nodegroups.py
  ```

## Architecture
See `docs/ARCHITECTURE.MD`.
