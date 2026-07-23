#!/usr/bin/env python3
"""
Build the MaterialX nodedef manifest used by BlenderToRCP.

This script reads Apple's `.mtlx` definition files and produces a single JSON
index consumed by the add-on at runtime:

  `Plugin/manifest/rk_nodes_manifest.json`

The add-on intentionally does NOT rebuild this manifest inside Blender.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional


# Policy flags based on Apple's README / observed RealityKit behavior.
GEOMETRY_MODIFIER_NODEDEFS = {
    "ND_realitykit_geometry_modifier_model_to_view",
    "ND_realitykit_geometry_modifier_model_to_world",
    "ND_realitykit_geometry_modifier_normal_to_world",
    "ND_realitykit_geometry_modifier_projection_to_view",
    "ND_realitykit_geometry_modifier_vertex_id",
    "ND_realitykit_geometry_modifier_view_to_projection",
    "ND_realitykit_geometry_modifier_world_to_model",
    "ND_realitykit_geometrymodifier_vertexshader",
}

KTX_REQUIRED_NODEDEFS = {
    "ND_realitykit_textureread",
    "ND_realitykit_texturecube",
    "ND_realitykit_texturecubelod",
    "ND_realitykit_texturecubegradient",
}

FALLBACK_NODEDEFS = {
    "ND_realitykit_occlusion_surfaceshader",
    "ND_realitykit_shadowreceiver_surfaceshader",
    "ND_realitykit_cameraposition_vector3",
    "ND_realitykit_viewdirection_vector3",
    "ND_realitykit_environment_radiance",
}


# The generated manifest is a checked-in interoperability contract, not a
# snapshot of whichever SDK happens to be installed on a contributor's Mac.
MATERIALX_PROFILE = "1.39"
MATERIALX_REFERENCE_RELEASE = "1.39.4"
REALITY_COMPOSER_PRO_VERSION = "3.0"
REALITY_COMPOSER_PRO_BUILD = "79.3.0.500.4"
APPLE_PLATFORM_GENERATION = "27.0"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build rk_nodes_manifest.json from MaterialX .mtlx files.")
    parser.add_argument(
        "--source",
        default="References/MaterialX-definitions",
        help="Folder containing Apple MaterialX .mtlx definition files.",
    )
    parser.add_argument(
        "--output",
        default="Plugin/manifest/rk_nodes_manifest.json",
        help="Output JSON path (inside the add-on).",
    )
    parser.add_argument(
        "--include-half",
        action="store_true",
        help="Include .mtlx files with 'half' in their filename (RealityKit half libraries).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    source_dir = Path(args.source)
    if not source_dir.is_absolute():
        source_dir = repo_root / source_dir
    source_dir = source_dir.resolve()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path = output_path.resolve()

    manifest = build_manifest(repo_root, source_dir, include_half=bool(args.include_half))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2))

    print(f"Wrote {len(manifest.get('nodes', {}))} nodedefs -> {output_path}")
    return 0


def build_manifest(repo_root: Path, source_dir: Path, include_half: bool) -> Dict[str, Any]:
    if not source_dir.exists():
        raise SystemExit(f"MaterialX source directory not found: {source_dir}")

    mtlx_files = sorted([p for p in source_dir.rglob("*.mtlx") if p.is_file()])
    if not include_half:
        # PBR Surface 2 has real half inputs, so its scalar conversion contract
        # is mandatory even in the compact/default manifest. Implementation
        # nodegraphs remain optional; RCP3 supplies them at runtime.
        required_half_defs = {"realitykit_half_defs.mtlx"}
        mtlx_files = [
            p
            for p in mtlx_files
            if "half" not in p.name.lower() or p.name in required_half_defs
        ]

    manifest: Dict[str, Any] = {
        "nodes": {},
        "index": {
            "by_node": {},
            "by_node_signature": {},
            "by_node_io": {},
            "by_node_output": {},
        },
        "metadata": {
            "version": "2.0.0",
            "profile": "realitykit-os27",
            "materialx_version": MATERIALX_PROFILE,
            "materialx_reference_release": MATERIALX_REFERENCE_RELEASE,
            "reality_composer_pro": {
                "version": REALITY_COMPOSER_PRO_VERSION,
                "build": REALITY_COMPOSER_PRO_BUILD,
            },
            "apple_platform_generation": APPLE_PLATFORM_GENERATION,
            "source_provenance": (
                "Repo-vendored, licensed nodedefs verified against Reality Composer Pro 3 "
                "and MaterialX 1.39.4; no machine-local SDK paths are embedded."
            ),
            "source_files": [],
            "source_sha256": {},
            "document_versions": {},
        },
    }

    for mtlx_file in mtlx_files:
        _parse_mtlx_file(repo_root, manifest, mtlx_file)
        source_path = _format_source_path(repo_root, mtlx_file)
        manifest["metadata"]["source_files"].append(source_path)
        manifest["metadata"]["source_sha256"][source_path] = hashlib.sha256(
            mtlx_file.read_bytes()
        ).hexdigest()
        document_version = _materialx_document_version(mtlx_file)
        if document_version:
            manifest["metadata"]["document_versions"][source_path] = document_version

    return manifest


def _parse_mtlx_file(repo_root: Path, manifest: Dict[str, Any], filepath: Path) -> None:
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        ns_uri = _get_namespace_uri(root.tag)
        ns = {"mx": ns_uri} if ns_uri else None

        nodedefs = root.findall(".//mx:nodedef", ns) if ns else root.findall(".//nodedef")
        for nodedef in nodedefs:
            node_info = _extract_nodedef_info(repo_root, nodedef, ns, filepath)
            if not node_info:
                continue
            nodedef_name = node_info["nodedef_name"]
            existing = manifest["nodes"].get(nodedef_name)
            if existing is not None and existing != node_info:
                raise RuntimeError(
                    f"Conflicting MaterialX nodedef '{nodedef_name}' in "
                    f"{existing.get('source_file')} and {_format_source_path(repo_root, filepath)}"
                )
            manifest["nodes"][nodedef_name] = node_info
            _index_node(manifest, node_info)
    except ET.ParseError as exc:
        print(f"Warning: Failed to parse {filepath}: {exc}")


def _extract_nodedef_info(
    repo_root: Path,
    nodedef,
    ns,
    filepath: Path,
) -> Optional[Dict[str, Any]]:
    nodedef_name = nodedef.get("name", "") or ""
    if not nodedef_name:
        return None

    node_name = (nodedef.get("node", "") or "").strip()
    nodegroup = (nodedef.get("nodegroup", "") or "").strip()
    node_version = (nodedef.get("version", "") or "").strip()
    target = (nodedef.get("target", "") or "").strip()
    availability = (nodedef.get("available", "") or "").strip()
    apple_availability = (nodedef.get("apple_availability", "") or "").strip()
    is_default_version = (nodedef.get("isdefaultversion", "false") or "").lower() == "true"

    # Inputs
    inputs: List[Dict[str, Any]] = []
    input_elems = nodedef.findall(".//mx:input", ns) if ns else nodedef.findall(".//input")
    for input_elem in input_elems:
        input_info: Dict[str, Any] = {
            "name": input_elem.get("name", ""),
            "type": input_elem.get("type", ""),
            "value": input_elem.get("value", ""),
            "uniform": (input_elem.get("uniform", "false") or "").lower() == "true",
        }
        enum = input_elem.get("enum", "")
        if enum:
            input_info["enum"] = enum.split(",")
        inputs.append(input_info)

    # Outputs
    outputs: List[Dict[str, Any]] = []
    output_elems = nodedef.findall(".//mx:output", ns) if ns else nodedef.findall(".//output")
    for output_elem in output_elems:
        outputs.append(
            {
                "name": output_elem.get("name", ""),
                "type": output_elem.get("type", ""),
            }
        )

    is_half = "half" in filepath.name.lower()
    is_omitted = nodedef_name in GEOMETRY_MODIFIER_NODEDEFS
    requires_ktx = nodedef_name.lower() in {n.lower() for n in KTX_REQUIRED_NODEDEFS}
    is_fallback = nodedef_name in FALLBACK_NODEDEFS

    signature = _signature_from_io(inputs, outputs)
    node_id = node_name or nodedef_name.replace("ND_", "")
    node_key = node_name or node_id

    result = {
        "nodedef_name": nodedef_name,
        "node_id": node_id,
        "node_name": node_key,
        "nodegroup": nodegroup,
        "inputs": inputs,
        "outputs": outputs,
        "signature": signature,
        "policy": {
            "omitted_in_defs": is_omitted,
            "requires_ktx": requires_ktx,
            "half_type": is_half,
            "fallback": is_fallback,
        },
        # Keep stable paths (avoid machine-specific absolute paths).
        "source_file": _format_source_path(repo_root, filepath),
    }
    if node_version:
        result["node_version"] = node_version
    if target:
        result["target"] = target
    if availability:
        result["availability"] = availability
    if apple_availability:
        result["apple_availability"] = apple_availability
    if is_default_version:
        result["is_default_version"] = True
    return result


def _index_node(manifest: Dict[str, Any], node_info: Dict[str, Any]) -> None:
    """Index a nodedef by node name and signature for lookup."""
    index = manifest.get("index", {})
    by_node = index.get("by_node", {})
    by_node_signature = index.get("by_node_signature", {})
    by_node_io = index.get("by_node_io", {})
    by_node_output = index.get("by_node_output", {})

    node_name = node_info.get("node_name") or node_info.get("node_id")
    if not node_name:
        return

    nodedef_name = node_info.get("nodedef_name")
    if not nodedef_name:
        return

    by_node.setdefault(node_name, [])
    if nodedef_name not in by_node[node_name]:
        by_node[node_name].append(nodedef_name)

    signature = node_info.get("signature")
    if signature:
        by_node_signature.setdefault(node_name, {}).setdefault(signature, [])
        if nodedef_name not in by_node_signature[node_name][signature]:
            by_node_signature[node_name][signature].append(nodedef_name)

    inputs = node_info.get("inputs", [])
    outputs = node_info.get("outputs", [])
    if len(inputs) == 1 and len(outputs) == 1:
        input_type = _normalize_type(inputs[0].get("type"))
        output_type = _normalize_type(outputs[0].get("type"))
        if input_type and output_type:
            io_key = f"{input_type}->{output_type}"
            by_node_io.setdefault(node_name, {}).setdefault(io_key, [])
            if nodedef_name not in by_node_io[node_name][io_key]:
                by_node_io[node_name][io_key].append(nodedef_name)

    if len(outputs) == 1:
        output_type = _normalize_type(outputs[0].get("type"))
        if output_type:
            by_node_output.setdefault(node_name, {}).setdefault(output_type, [])
            if nodedef_name not in by_node_output[node_name][output_type]:
                by_node_output[node_name][output_type].append(nodedef_name)


def _get_namespace_uri(tag: str) -> Optional[str]:
    if tag and tag.startswith("{") and "}" in tag:
        return tag[1 : tag.find("}")]
    return None


def _format_source_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root))
    except Exception as exc:
        raise ValueError(
            f"MaterialX sources must be vendored below the repository root: {path}"
        ) from exc


def _materialx_document_version(path: Path) -> Optional[str]:
    """Return a MaterialX document version without retaining SDK-local data."""
    try:
        return (ET.parse(path).getroot().get("version", "") or "").strip() or None
    except ET.ParseError:
        return None


def _normalize_type(type_name: Optional[str]) -> str:
    return (type_name or "").strip().lower()


def _signature_from_io(inputs: List[Dict[str, Any]], outputs: List[Dict[str, Any]]) -> str:
    input_sig = ",".join(f"{item.get('name')}:{_normalize_type(item.get('type'))}" for item in inputs)
    output_sig = ",".join(f"{item.get('name')}:{_normalize_type(item.get('type'))}" for item in outputs)
    return f"in[{input_sig}]|out[{output_sig}]"


if __name__ == "__main__":
    raise SystemExit(main())
