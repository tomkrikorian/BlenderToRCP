---
name: "blendertorcp-setup"
description: "Use when a user wants to set up the BlenderToRCP CLI tool; locate the Blender executable and plugin install path, verify connectivity, and configure a shell alias. Also use to troubleshoot CLI errors like 'Blender not found' or 'Plugin not loaded'."
---

# BlenderToRCP CLI Setup

Configure the BlenderToRCP CLI so the agent can export scenes, bake textures, validate materials, and manage settings from the terminal.

## Prerequisites

- Blender 5.2+ installed
- BlenderToRCP addon installed and enabled in Blender's preferences
- Python 3 available as `python3`

For manual installs, install `BlenderToRCP-<version>.zip` in Blender via `Edit > Preferences > Extensions > Add-ons > Install from Disk...`, then enable `BlenderToRCP`. Blender installs the package under its manifest ID, `blender_to_rcp`. For development installs, symlink `<repo>/Plugin` to the Blender `extensions/user_default/blender_to_rcp` path.

## Inputs

- `blender-path` (optional): explicit path to the Blender binary

## Workflow

### 1. Locate the Blender binary

If the user supplied a path, verify it exists. Otherwise probe common locations:

```bash
# macOS
test -x /Applications/Blender.app/Contents/MacOS/Blender && echo "found"

# Linux
command -v blender >/dev/null 2>&1 && echo "found"
which blender
```

If nothing is found, ask the user for the path before proceeding.

### 2. Locate the extension root

The addon ships the CLI directly in the extension root. Check Blender's extensions paths:

```bash
# macOS
find ~/Library/Application\ Support/Blender \
  \( -path "*/extensions/*/blender_to_rcp/cli/__main__.py" -o \
     -path "*/extensions/*/BlenderToRCP/cli/__main__.py" \) 2>/dev/null

# Linux
find ~/.config/blender \
  \( -path "*/extensions/*/blender_to_rcp/cli/__main__.py" -o \
     -path "*/extensions/*/BlenderToRCP/cli/__main__.py" \) 2>/dev/null
```

Treat `blender_to_rcp` as canonical because it is the manifest ID. The uppercase
`BlenderToRCP` search is only a legacy development-symlink fallback. For
development installs, the CLI directory is `<repo>/Plugin/`, and the dev symlink
normally points `.../extensions/user_default/blender_to_rcp` there.

Verify the install by confirming both `cli/__main__.py` and `api/runner.py` exist in the resolved extension root. In a repo checkout, those files live under `Plugin/`.

### 3. Test the connection

Run these checks to confirm Blender, Python, and the addon are all wired up:

```bash
# Installed extension root
BLENDERTORCP_BLENDER=/path/to/blender python3 /path/to/blender_to_rcp version
BLENDERTORCP_BLENDER=/path/to/blender python3 /path/to/blender_to_rcp preferences get
BLENDERTORCP_BLENDER=/path/to/blender python3 /path/to/blender_to_rcp settings list

# Development checkout
python3 /path/to/repo/Plugin --blender /path/to/blender version
python3 /path/to/repo/Plugin --blender /path/to/blender preferences get
python3 /path/to/repo/Plugin --blender /path/to/blender settings list
```

`version` proves Blender launches. `preferences get` and `settings list` also prove the addon registered correctly. If this fails:

| Error | Exit Code | Cause | Fix |
|-------|-----------|-------|-----|
| `Blender not found` | 2 | Wrong binary path | Correct `BLENDERTORCP_BLENDER` or use `--blender <path>` |
| `No output from Blender` | 1 | Blender crashed on startup | Re-run with `--verbose`, save stderr, then create a support bundle if a scene is involved |
| `Failed to import command registry` | 3 | Plugin path is wrong, addon not enabled, or files are missing | Enable BlenderToRCP in Blender preferences and re-check the install path |
| `BlenderToRCP addon preferences not available.` | 1 | Add-on is not enabled, or the path points at the wrong directory | Enable the add-on, then re-run `preferences get` against the resolved extension root |
| `'Scene' object has no attribute 'blender_to_rcp_export_settings'` | 1 | Add-on did not register its scene properties | Enable the add-on, then re-run `settings list` or `settings get` |

With `--json`, add-on load failures and export failures are emitted as structured JSON with `ok`, `schema_version`, `command`, `error`, `context`, `artifacts`, and optional `process_output`; without `--json`, the CLI prints a shorter stderr message plus diagnostics/support hints when available.

For support captures:

```bash
blendertorcp --verbose export scene.blend -o output.usdz \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
blendertorcp support-bundle scene.blend -o output.usdz --diagnostics output.diagnostics.json
# For UI background bake/export failures, also pass the job directory:
blendertorcp support-bundle scene.blend -o output.usdz \
  --job-dir output/.blendertorcp_jobs/bake_export_YYYYMMDD_HHMMSS_abcd
```

### 4. Configure the shell

Add to the user's shell profile (`~/.zshrc`, `~/.bashrc`, or equivalent):

```bash
export BLENDERTORCP_BLENDER="/path/to/blender"
alias blendertorcp="python3 /path/to/blender_to_rcp"
# Or for a repository checkout:
# alias blendertorcp="python3 /path/to/repo/Plugin"
```

After sourcing the profile, confirm the alias works:

```bash
blendertorcp version
blendertorcp preferences get
blendertorcp settings list
```

### 5. Report result

Print the resolved paths and confirm the setup is complete:
- Blender binary path
- Extension root or repo `Plugin/` path
- Shell alias configured (yes/no)
- CLI verification output
