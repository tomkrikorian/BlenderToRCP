"""
Material rewrite orchestration for USD stages.
"""

from ..usd_utils import UsdShade, UsdGeom
from ..usd_hook import consume_captured_material_map
from ...manifest.materialx_nodes import load_manifest
from .graph import MaterialXGraphBuilder
from .extract import extract_blender_material_data, collect_material_warnings
from .author import create_materialx_material
from .helpers import _get_blender_data_name


def rewrite_materials(stage, settings, context, diagnostics=None) -> None:
    """Rewrite materials to MaterialX graphs (Pass 2)."""
    manifest = load_manifest()
    builder = MaterialXGraphBuilder(manifest, diagnostics)
    force_unlit = bool(getattr(settings, "force_unlit_materials", False))

    blender_materials = {
        material.name: material
        for material in context.blend_data.materials
        if material
    }
    # Exact {material prim path: Blender material name} recorded by the
    # USDHook during export; empty when the export ran without the hook.
    hook_material_map = consume_captured_material_map() or {}

    created_materials = {}

    for prim in stage.Traverse():
        # Multi-material meshes bind materials on GeomSubset children, not on
        # the mesh prim itself, so both prim kinds must be rewritten.
        if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Subset)):
            continue

        material_binding = UsdShade.MaterialBindingAPI(prim)
        bound_material = material_binding.GetDirectBinding().GetMaterial()
        if not bound_material:
            continue

        material_prim = bound_material.GetPrim()
        material_name = material_prim.GetName()
        blender_name = _get_blender_data_name(material_prim) or material_name
        material_key = str(material_prim.GetPath())

        mapped_name = hook_material_map.get(material_key)
        blender_material = blender_materials.get(mapped_name) if mapped_name else None
        if blender_material:
            blender_name = mapped_name
        else:
            blender_material = blender_materials.get(blender_name) or blender_materials.get(material_name)
        if not blender_material:
            continue

        if material_key not in created_materials:
            warnings = collect_material_warnings(blender_material)
            if diagnostics:
                for warning in warnings:
                    diagnostics.add_warning(warning)

            material_data = extract_blender_material_data(blender_material)
            unresolved = material_data.get("unresolved_warnings") or []
            if diagnostics:
                for warning in unresolved:
                    diagnostics.add_warning(warning)
                    diagnostics.add_error(warning)

            try:
                if force_unlit and material_data['type'] in {'principled', 'emission', 'simple'}:
                    graph = builder.build_unlit_material(material_data)
                elif material_data['type'] == 'principled':
                    graph = builder.build_pbr_material(material_data)
                elif material_data['type'] in ['emission', 'simple']:
                    graph = builder.build_unlit_material(material_data)
                elif material_data['type'] == 'rk_graph':
                    graph = builder.build_rk_graph(material_data.get('rk_graph'))
                elif material_data['type'] == 'rk_group':
                    graph = builder.build_rk_material(
                        material_data.get('rk_node_id'),
                        material_data.get('rk_inputs', {})
                    )
                else:
                    graph = None

                if graph:
                    created_materials[material_key] = create_materialx_material(
                        stage,
                        str(material_prim.GetPath()),
                        blender_name,
                        graph,
                        manifest,
                        diagnostics
                    )
                    if diagnostics:
                        diagnostics.add_material_converted(blender_name)
                else:
                    # Cache the miss so other prims bound to this material
                    # (e.g. GeomSubsets) don't re-extract and re-warn.
                    created_materials[material_key] = None
                    if diagnostics:
                        diagnostics.add_material_failed(
                            blender_name,
                            f"Material type '{material_data.get('type')}' could not be mapped to a RealityKit graph.",
                        )
            except Exception as e:
                if diagnostics:
                    diagnostics.add_material_failed(blender_name, str(e))
                created_materials[material_key] = None

        new_material = created_materials.get(material_key)
        if new_material:
            material_binding.Bind(new_material)
