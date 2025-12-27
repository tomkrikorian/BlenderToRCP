"""
MaterialX nodedef manifest loader + selectors.

`rk_nodes_manifest.json` is a prebuilt index of all MaterialX nodedefs we can
target (RealityKit + stdlib/pbrlib). It is generated from Apple's `.mtlx`
definition files by a repo script (see `scripts/build_materialx_manifest.py`).

Important: the Blender add-on does not rebuild this manifest at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.paths import manifest_path as _manifest_path


MANIFEST_SCHEMA_VERSION = "2.0.0"


class ManifestError(RuntimeError):
    pass


def get_manifest_path() -> Path:
    """Return the path to the bundled manifest JSON."""
    return _manifest_path()


def load_manifest() -> Dict[str, Any]:
    """Load the bundled manifest JSON (no rebuild)."""
    manifest_path = get_manifest_path()
    if not manifest_path.exists():
        raise ManifestError(
            f"MaterialX manifest missing: {manifest_path}. "
            f"Run `python3 scripts/build_materialx_manifest.py` to generate it."
        )

    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:
        raise ManifestError(f"Failed to parse MaterialX manifest: {manifest_path}: {exc}") from exc

    _validate_manifest(manifest, manifest_path)
    return manifest


def get_node_def(manifest: Dict[str, Any], nodedef_name: str) -> Optional[Dict[str, Any]]:
    """Return a nodedef entry by its nodedef name."""
    if not manifest:
        return None
    return manifest.get("nodes", {}).get(nodedef_name)


def get_node_defs_for_node(manifest: Dict[str, Any], node_name: str) -> List[Dict[str, Any]]:
    """Return all nodedef entries for a node name."""
    if not manifest:
        return []
    names = manifest.get("index", {}).get("by_node", {}).get(node_name, [])
    return [manifest.get("nodes", {}).get(name) for name in names if name in manifest.get("nodes", {})]


def select_nodedef_name_for_node(
    manifest: Dict[str, Any],
    node_name: str,
    input_type: Optional[str] = None,
    output_type: Optional[str] = None,
    signature: Optional[str] = None,
    prefer_non_half: bool = True,
) -> Optional[str]:
    """Select the best nodedef name for a node based on IO signature."""
    if not manifest or not node_name:
        return None

    index = manifest.get("index", {})
    by_node_signature = index.get("by_node_signature", {})
    by_node_io = index.get("by_node_io", {})
    by_node_output = index.get("by_node_output", {})

    candidates: List[str] = []

    if signature:
        candidates = list(by_node_signature.get(node_name, {}).get(signature, []))

    if not candidates and input_type and output_type:
        io_key = f"{_normalize_type(input_type)}->{_normalize_type(output_type)}"
        candidates = list(by_node_io.get(node_name, {}).get(io_key, []))

    if not candidates and output_type:
        candidates = list(by_node_output.get(node_name, {}).get(_normalize_type(output_type), []))

    if not candidates:
        candidates = list(index.get("by_node", {}).get(node_name, []))

    if not candidates:
        return None

    candidates = sorted(set(candidates))
    return _pick_nodedef(manifest, candidates, prefer_non_half=prefer_non_half)


def select_node_def_for_node(
    manifest: Dict[str, Any],
    node_name: str,
    input_type: Optional[str] = None,
    output_type: Optional[str] = None,
    signature: Optional[str] = None,
    prefer_non_half: bool = True,
) -> Optional[Dict[str, Any]]:
    """Return the nodedef entry selected for a node name."""
    nodedef_name = select_nodedef_name_for_node(
        manifest,
        node_name,
        input_type=input_type,
        output_type=output_type,
        signature=signature,
        prefer_non_half=prefer_non_half,
    )
    if not nodedef_name:
        return None
    return get_node_def(manifest, nodedef_name)


def _validate_manifest(manifest: Dict[str, Any], manifest_path: Path) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError(f"Invalid manifest format (expected dict): {manifest_path}")

    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        raise ManifestError(f"Invalid manifest metadata: {manifest_path}")

    version = metadata.get("version")
    if version != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"Unsupported manifest schema {version!r} (expected {MANIFEST_SCHEMA_VERSION!r}): {manifest_path}. "
            f"Rebuild with `python3 scripts/build_materialx_manifest.py`."
        )

    nodes = manifest.get("nodes")
    index = manifest.get("index")
    if not isinstance(nodes, dict) or not isinstance(index, dict):
        raise ManifestError(f"Invalid manifest structure (missing nodes/index): {manifest_path}")


def _normalize_type(type_name: Optional[str]) -> str:
    return (type_name or "").strip().lower()


def _pick_nodedef(
    manifest: Dict[str, Any],
    candidates: List[str],
    prefer_non_half: bool = True,
) -> Optional[str]:
    if not candidates:
        return None
    if not prefer_non_half:
        return candidates[0]

    for name in candidates:
        node = manifest.get("nodes", {}).get(name)
        if node and not node.get("policy", {}).get("half_type"):
            return name
    return candidates[0]
