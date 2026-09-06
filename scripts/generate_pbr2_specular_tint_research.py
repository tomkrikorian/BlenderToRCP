#!/usr/bin/env python3
"""Generate an RCP 3 A/B fixture for Blender Specular Tint research.

Run this with Blender 5.2's Python so OpenUSD is available.  The fixture uses
the production MaterialX graph builder, but none of its experimental strategies
are enabled in normal exports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def research_variants() -> tuple[dict[str, object], ...]:
    """Return the deliberately small, reviewable PBR2 comparison matrix."""
    return (
        {
            "name": "DirectOverbright",
            "specular_tint": [2.0, 2.0, 2.0],
            "specular_weight": 1.0,
            "strategy": "Direct Blender value; outside the verified color range",
        },
        {
            "name": "ClampOnly",
            "specular_tint": [1.0, 1.0, 1.0],
            "specular_weight": 1.0,
            "strategy": "Shipping opt-in policy: clamp color only",
        },
        {
            "name": "ClampAndRedistribute",
            "specular_tint": [1.0, 1.0, 1.0],
            "specular_weight": 2.0,
            "strategy": (
                "Research hypothesis: move achromatic excess into specularWeight"
            ),
        },
    )


def generate(output: Path) -> Path:
    """Author the comparison stage with BlenderToRCP's PBR2 implementation."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

    from Plugin.export.materials.author import create_materialx_material
    from Plugin.export.materials.graph import MaterialXGraphBuilder
    from Plugin.manifest.materialx_nodes import load_manifest

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    stage = Usd.Stage.CreateNew(str(output))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/SpecularTintResearch")
    stage.SetDefaultPrim(root.GetPrim())
    root.GetPrim().SetDocumentation(
        "Manual RCP 3 A/B fixture. Do not infer a production mapping from this asset."
    )

    manifest = load_manifest()
    builder = MaterialXGraphBuilder(
        manifest,
    )

    for index, variant in enumerate(research_variants()):
        name = str(variant["name"])
        sphere = UsdGeom.Sphere.Define(
            stage,
            f"/SpecularTintResearch/{name}",
        )
        sphere.CreateRadiusAttr(0.75)
        sphere.AddTranslateOp().Set(Gf.Vec3d((index - 1) * 2.0, 0.0, 0.0))
        prim = sphere.GetPrim()
        prim.CreateAttribute(
            "research:strategy",
            Sdf.ValueTypeNames.String,
        ).Set(str(variant["strategy"]))
        prim.CreateAttribute(
            "research:sourceSpecularTint",
            Sdf.ValueTypeNames.Color3f,
        ).Set(Gf.Vec3f(2.0, 2.0, 2.0))
        prim.CreateAttribute(
            "research:exportedSpecularTint",
            Sdf.ValueTypeNames.Color3f,
        ).Set(Gf.Vec3f(*variant["specular_tint"]))
        prim.CreateAttribute(
            "research:exportedSpecularWeight",
            Sdf.ValueTypeNames.Float,
        ).Set(float(variant["specular_weight"]))

        graph = builder.build_pbr_material(
            {
                "type": "principled",
                "base_color": [0.45, 0.45, 0.45],
                "metallic": 1.0,
                "roughness": 0.41008475,
                "specular_tint": list(variant["specular_tint"]),
                "specular_weight": float(variant["specular_weight"]),
            }
        )
        material = create_materialx_material(
            stage,
            f"/SpecularTintResearch/Looks/{name}",
            name,
            graph,
            manifest,
        )
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)

    stage.GetRootLayer().Save()
    return output


def _argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination .usda or .usdc fixture",
    )
    args = parser.parse_args(_argv())
    output = generate(args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
