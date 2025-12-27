#!/usr/bin/env python3
"""
Systematic Reality Composer Pro node validation.

Generates a minimal .rkassets bundle per supported node, then (optionally)
compiles each one with realitytool to verify ShaderGraph compatibility.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
    "ASsJTYQAAAAASUVORK5CYII="
)


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    try:
        from pxr import Usd, UsdShade, Sdf, Gf
    except Exception as exc:
        print(f"ERROR: pxr (OpenUSD) not available: {exc}")
        return 2

    from Plugin.manifest.materialx_nodes import (
        load_manifest,
        select_node_def_for_node,
        select_nodedef_name_for_node,
    )
    from Plugin.nodes import metadata as rk_metadata

    manifest = load_manifest()
    catalog = rk_metadata.get_node_catalog()
    node_ids = sorted({entry["export_id"] for entry in catalog})

    if args.filter:
        node_ids = [node_id for node_id in node_ids if args.filter in node_id]
    if args.limit:
        node_ids = node_ids[: args.limit]

    out_root = Path(args.output).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    platform = args.platform
    deployment_target = args.deployment_target or _sdk_platform_version(platform)

    results: List[Dict[str, Any]] = []
    skipped = 0
    failures = 0

    for node_id in node_ids:
        node_def = select_node_def_for_node(manifest, node_id)
        if not node_def:
            results.append(_skip_result(node_id, "nodedef_not_found"))
            skipped += 1
            continue

        policy = node_def.get("policy", {})
        if policy.get("requires_ktx") and not args.include_ktx:
            results.append(_skip_result(node_id, "requires_ktx"))
            skipped += 1
            continue
        if policy.get("omitted_in_defs") and not args.include_omitted:
            results.append(_skip_result(node_id, "omitted_in_defs"))
            skipped += 1
            continue
        if policy.get("fallback") and not args.include_fallback:
            results.append(_skip_result(node_id, "fallback"))
            skipped += 1
            continue
        if policy.get("half_type") and not args.include_half:
            results.append(_skip_result(node_id, "half_type"))
            skipped += 1
            continue

        bundle_dir = out_root / f"{_sanitize_name(node_id)}.rkassets"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        scene_path = bundle_dir / "scene.usda"

        node_output = _build_usd_for_node(
            Usd,
            UsdShade,
            Sdf,
            Gf,
            manifest,
            node_id,
            node_def,
            scene_path,
            bundle_dir,
            select_node_def_for_node,
            select_nodedef_name_for_node,
        )
        if node_output is None:
            results.append(_skip_result(node_id, "unable_to_connect_output"))
            skipped += 1
            continue

        compile_result: Dict[str, Any] = {
            "compiled": False,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
        }

        if not args.no_compile:
            compile_result = _compile_bundle(
                bundle_dir,
                platform,
                deployment_target,
            )
            if compile_result["exit_code"] != 0:
                failures += 1

        results.append(
            {
                "node_id": node_id,
                "nodedef_name": node_def.get("nodedef_name"),
                "output_type": node_def.get("outputs", [{}])[0].get("type"),
                "policy": policy,
                "bundle": str(bundle_dir),
                "compile": compile_result,
            }
        )

    report = {
        "platform": platform,
        "deployment_target": deployment_target,
        "node_count": len(node_ids),
        "skipped": skipped,
        "failures": failures,
        "results": results,
    }

    report_path = out_root / "node_validation.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"Validation complete. Nodes: {len(node_ids)} | Skipped: {skipped} | Failures: {failures}")
    print(f"Report: {report_path}")
    return 0 if failures == 0 else 1


def _build_usd_for_node(
    Usd,
    UsdShade,
    Sdf,
    Gf,
    manifest: Dict[str, Any],
    node_id: str,
    node_def: Dict[str, Any],
    scene_path: Path,
    bundle_dir: Path,
    select_node_def_for_node,
    select_nodedef_name_for_node,
):
    stage = Usd.Stage.CreateNew(str(scene_path))
    stage.SetMetadata("upAxis", "Y")
    stage.SetMetadata("metersPerUnit", 1)

    root = stage.DefinePrim("/Root", "Xform")
    stage.SetDefaultPrim(root)

    material = UsdShade.Material.Define(stage, "/Root/Material")

    shader_name = _sanitize_name(node_id)
    shader = UsdShade.Shader.Define(stage, f"/Root/Material/{shader_name}")
    shader.CreateIdAttr(node_def.get("nodedef_name"))

    needs_texture = False
    for input_def in node_def.get("inputs", []):
        name = input_def.get("name")
        mtlx_type = input_def.get("type")
        if not name or not mtlx_type:
            continue

        sdf_type = _mtlx_type_to_sdf(Sdf, mtlx_type)
        if not sdf_type:
            continue
        input_attr = shader.CreateInput(name, sdf_type)
        value = _default_value_for_input(Gf, Sdf, input_def)
        if value is None:
            continue
        if mtlx_type.lower() == "filename":
            value = Sdf.AssetPath("textures/placeholder.png")
            needs_texture = True
        input_attr.Set(value)

    outputs = node_def.get("outputs", [])
    if not outputs:
        stage.Save()
        return None

    output_name = outputs[0].get("name") or "out"
    output_type = outputs[0].get("type") or "token"
    output_type_norm = output_type.lower()
    output_sdf_type = _mtlx_type_to_sdf(Sdf, output_type) or Sdf.ValueTypeNames.Token
    shader_output = shader.CreateOutput(output_name, output_sdf_type)

    if output_type_norm in {"token", "surfaceshader", "displacementshader", "volumeshader"}:
        surface_output = material.CreateSurfaceOutput("mtlx")
        surface_output.ConnectToSource(shader_output)
    else:
        surface_def = select_node_def_for_node(manifest, "realitykit_pbr_surfaceshader")
        if not surface_def:
            stage.Save()
            return None

        surface_shader = UsdShade.Shader.Define(stage, "/Root/Material/Surface")
        surface_shader.CreateIdAttr(surface_def.get("nodedef_name"))
        surface_output = surface_shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
        material.CreateSurfaceOutput("mtlx").ConnectToSource(surface_output)

        target_input, target_type = _pick_surface_target(output_type_norm)
        if not target_input:
            stage.Save()
            return None

        adapted_output = _adapt_output(
            manifest,
            UsdShade,
            Sdf,
            select_nodedef_name_for_node,
            stage,
            "/Root/Material",
            shader_output,
            output_type_norm,
            target_type,
            shader_name,
        )
        if adapted_output is None:
            stage.Save()
            return None

        surface_input = surface_shader.CreateInput(
            target_input,
            _mtlx_type_to_sdf(Sdf, target_type) or adapted_output.GetTypeName(),
        )
        surface_input.ConnectToSource(adapted_output)

    stage.Save()

    if needs_texture:
        textures_dir = bundle_dir / "textures"
        textures_dir.mkdir(parents=True, exist_ok=True)
        (textures_dir / "placeholder.png").write_bytes(PLACEHOLDER_PNG)

    return shader_output


def _adapt_output(
    manifest: Dict[str, Any],
    UsdShade,
    Sdf,
    select_nodedef_name_for_node,
    stage,
    nodegraph_path: str,
    source_output,
    from_type: str,
    to_type: str,
    name_seed: str,
):
    if from_type == to_type:
        return source_output

    chain = _conversion_chain(from_type, to_type)
    current = source_output
    current_type = from_type

    for next_type in chain:
        nodedef_name = select_nodedef_name_for_node(
            manifest,
            "convert",
            input_type=current_type,
            output_type=next_type,
        )
        if not nodedef_name:
            return None

        convert_name = _unique_name(stage, nodegraph_path, f"Convert_{name_seed}_{current_type}_to_{next_type}")
        convert_shader = UsdShade.Shader.Define(stage, f"{nodegraph_path}/{convert_name}")
        convert_shader.CreateIdAttr(nodedef_name)

        in_type = _mtlx_type_to_sdf(Sdf, current_type) or current.GetTypeName()
        out_type = _mtlx_type_to_sdf(Sdf, next_type) or current.GetTypeName()
        in_input = convert_shader.CreateInput("in", in_type)
        in_input.ConnectToSource(current)
        current = convert_shader.CreateOutput("out", out_type)
        current_type = next_type

    return current if current_type == to_type else None


def _conversion_chain(from_type: str, to_type: str) -> List[str]:
    if from_type == to_type:
        return [to_type]

    chain: List[str] = []
    if from_type == "vector2" and to_type == "color3":
        chain = ["vector3", "color3"]
    elif from_type == "vector4" and to_type == "color3":
        chain = ["color4", "color3"]
    else:
        chain = [to_type]

    return chain


def _pick_surface_target(output_type: str) -> Tuple[Optional[str], Optional[str]]:
    if output_type in {"boolean", "bool"}:
        return "hasPremultipliedAlpha", "boolean"
    if output_type in {"float", "integer", "half"}:
        return "roughness", "float"
    if output_type in {"color3", "color4", "vector2", "vector3", "vector4"}:
        return "baseColor", "color3"
    return None, None


def _default_value_for_input(Gf, Sdf, input_def: Dict[str, Any]):
    value = input_def.get("value")
    enum_values = input_def.get("enum") or []
    mtlx_type = (input_def.get("type") or "").lower()

    if mtlx_type == "filename":
        return Sdf.AssetPath("")

    if enum_values:
        return enum_values[0]

    if value is None or value == "":
        return _default_for_type(Gf, mtlx_type)

    try:
        return _parse_value(Gf, mtlx_type, value)
    except Exception:
        return _default_for_type(Gf, mtlx_type)


def _default_for_type(Gf, mtlx_type: str):
    if mtlx_type in {"boolean", "bool"}:
        return False
    if mtlx_type in {"integer", "int"}:
        return 0
    if mtlx_type in {"float", "half"}:
        return 0.5
    if mtlx_type in {"color3", "vector3"}:
        return Gf.Vec3f(1.0, 0.0, 0.0)
    if mtlx_type in {"color4", "vector4"}:
        return Gf.Vec4f(1.0, 0.0, 0.0, 1.0)
    if mtlx_type == "vector2":
        return Gf.Vec2f(0.5, 0.5)
    if mtlx_type == "matrix33":
        return Gf.Matrix3d(1.0)
    if mtlx_type == "matrix44":
        return Gf.Matrix4d(1.0)
    if mtlx_type in {"string", "token"}:
        return "default"
    return None


def _parse_value(Gf, mtlx_type: str, value: str):
    if mtlx_type in {"boolean", "bool"}:
        return str(value).strip().lower() in {"1", "true", "yes"}
    if mtlx_type in {"integer", "int"}:
        return int(float(value))
    if mtlx_type in {"float", "half"}:
        return float(value)
    if mtlx_type == "vector2":
        parts = [float(p.strip()) for p in value.split(",")]
        return Gf.Vec2f(*parts[:2])
    if mtlx_type in {"vector3", "color3"}:
        parts = [float(p.strip()) for p in value.split(",")]
        return Gf.Vec3f(*parts[:3])
    if mtlx_type in {"vector4", "color4"}:
        parts = [float(p.strip()) for p in value.split(",")]
        return Gf.Vec4f(*parts[:4])
    if mtlx_type == "matrix33":
        return Gf.Matrix3d(1.0)
    if mtlx_type == "matrix44":
        return Gf.Matrix4d(1.0)
    if mtlx_type in {"string", "token"}:
        return str(value)
    return value


def _mtlx_type_to_sdf(Sdf, type_name: Optional[str]):
    if not type_name:
        return None
    type_name = type_name.lower()
    color4_type = getattr(Sdf.ValueTypeNames, "Color4f", Sdf.ValueTypeNames.Float4)
    mapping = {
        "boolean": Sdf.ValueTypeNames.Bool,
        "bool": Sdf.ValueTypeNames.Bool,
        "integer": Sdf.ValueTypeNames.Int,
        "int": Sdf.ValueTypeNames.Int,
        "float": Sdf.ValueTypeNames.Float,
        "half": Sdf.ValueTypeNames.Float,
        "vector2": Sdf.ValueTypeNames.Float2,
        "vector3": Sdf.ValueTypeNames.Float3,
        "vector4": Sdf.ValueTypeNames.Float4,
        "color3": Sdf.ValueTypeNames.Color3f,
        "color4": color4_type,
        "matrix33": Sdf.ValueTypeNames.Matrix3d,
        "matrix44": Sdf.ValueTypeNames.Matrix4d,
        "string": Sdf.ValueTypeNames.String,
        "token": Sdf.ValueTypeNames.Token,
        "filename": Sdf.ValueTypeNames.Asset,
        "surfaceshader": Sdf.ValueTypeNames.Token,
        "volumeshader": Sdf.ValueTypeNames.Token,
        "displacementshader": Sdf.ValueTypeNames.Token,
    }
    return mapping.get(type_name)


def _compile_bundle(bundle_dir: Path, platform: str, deployment_target: Optional[str]) -> Dict[str, Any]:
    output_reality = bundle_dir / "compiled.reality"
    cmd = [
        "xcrun",
        "realitytool",
        "compile",
        "--platform",
        platform,
        "--deployment-target",
        deployment_target,
        "--output-reality",
        str(output_reality),
        str(bundle_dir),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {
            "compiled": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {
            "compiled": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def _sdk_platform_version(platform: str) -> str:
    sdk = "xros" if platform == "xros" else "macosx"
    try:
        proc = subprocess.run(
            ["xcrun", "--sdk", sdk, "--show-sdk-platform-version"],
            capture_output=True,
            text=True,
            check=False,
        )
        version = proc.stdout.strip()
        if version:
            return version
    except Exception:
        pass
    return "1.0" if platform == "xros" else "15.0"


def _skip_result(node_id: str, reason: str) -> Dict[str, Any]:
    return {"node_id": node_id, "skip": True, "reason": reason}


def _sanitize_name(name: str) -> str:
    cleaned = []
    for ch in name:
        if ch.isalnum() or ch in {"_", "-"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    return "".join(cleaned) or "Node"


def _unique_name(stage, parent_path: str, base_name: str) -> str:
    candidate = base_name
    suffix = 1
    while stage.GetPrimAtPath(f"{parent_path}/{candidate}"):
        suffix += 1
        candidate = f"{base_name}_{suffix}"
    return candidate


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate ShaderGraph nodes via realitytool.")
    parser.add_argument("--output", default="tests/node_validation", help="Output directory for bundles/results.")
    parser.add_argument("--platform", default="xros", help="realitytool platform (xros, macosx, etc).")
    parser.add_argument("--deployment-target", default=None, help="Deployment target (defaults to SDK platform version).")
    parser.add_argument("--filter", default=None, help="Only validate node IDs containing this substring.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of nodes to validate.")
    parser.add_argument("--no-compile", action="store_true", help="Only generate USD without running realitytool.")
    parser.add_argument("--include-ktx", action="store_true", help="Include KTX-required nodes.")
    parser.add_argument("--include-omitted", action="store_true", help="Include nodes omitted from defs.")
    parser.add_argument("--include-fallback", action="store_true", help="Include fallback nodes.")
    parser.add_argument("--include-half", action="store_true", help="Include half-type nodedefs.")
    return parser.parse_args(_script_argv())


def _script_argv() -> List[str]:
    """Return argv intended for this script (handles Blender's argv forwarding)."""
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        return sys.argv[idx + 1 :]
    return sys.argv[1:]


if __name__ == "__main__":
    raise SystemExit(main())
