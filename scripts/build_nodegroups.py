"""
Build the RealityKit NodeGroup library (`Plugin/assets/nodegroups.blend`) for BlenderToRCP.

Run in Blender:

  blender --background --python scripts/build_nodegroups.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy  # noqa: F401  (Blender provides this)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    from Plugin.nodes import nodegroups as rk_nodegroups

    asset_path = repo_root / "Plugin" / "assets" / "nodegroups.blend"
    rk_nodegroups.save_nodegroup_library(asset_path)
    print(f"Saved node group library: {asset_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

