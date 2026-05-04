#!/usr/bin/env python3
"""
Entry point for running BlenderToRCP as a CLI tool.

Usage::

    python3 /path/to/Plugin <command> [options]
    python3 -m Plugin.cli <command> [options]

This allows the installed Blender addon to double as a CLI tool
without any additional installation.
"""

import sys
from pathlib import Path
import importlib.util

# When invoked as ``python3 /path/to/Plugin``, Python sets __name__ to
# "__main__" and the package isn't on sys.path.  Add the parent directory
# so ``from Plugin.cli…`` resolves correctly. If the installed extension folder
# is named BlenderToRCP, alias that folder to ``Plugin`` for CLI compatibility.
_plugin_dir = Path(__file__).resolve().parent
_parent_path = _plugin_dir.parent
_parent = str(_parent_path)
if _parent not in sys.path:
    sys.path.insert(0, _parent)
if not (_parent_path / "Plugin" / "__init__.py").exists() and "Plugin" not in sys.modules:
    _init_path = _plugin_dir / "__init__.py"
    _spec = importlib.util.spec_from_file_location(
        "Plugin",
        _init_path,
        submodule_search_locations=[str(_plugin_dir)],
    )
    if _spec is not None and _spec.loader is not None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules["Plugin"] = _module
        _spec.loader.exec_module(_module)

from Plugin.cli.__main__ import main  # noqa: E402

sys.exit(main())
