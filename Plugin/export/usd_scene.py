"""
USD scene normalization utilities.

Keeps stage metadata and prim names aligned with RealityKit expectations.
"""

import re

from .usd_utils import Sdf


def normalize_scene(stage, settings) -> None:
    """Normalize scene metadata and prim names for RCP."""
    # Ensure default prim
    if not stage.GetDefaultPrim():
        root_prim_name = settings.root_prim_name or "Scene"
        root_prim = stage.GetPrimAtPath(f"/{root_prim_name}")
        if not root_prim:
            root_prim = stage.DefinePrim(f"/{root_prim_name}", "Xform")
        stage.SetDefaultPrim(root_prim)

    # Set up upAxis metadata based on convert orientation settings.
    if settings.convert_orientation:
        up_axis = getattr(settings, "up_axis", "Y")
        if up_axis:
            stage.SetMetadata("upAxis", up_axis.lstrip('-'))

    # Fix illegal prim names if needed (USD has restrictions on prim names).
    rename_ops = []
    for prim in stage.Traverse():
        prim_name = prim.GetName()
        if not _is_valid_identifier(prim_name):
            new_name = f"prim_{prim_name}" if prim_name else "prim"
            rename_ops.append((prim.GetPath(), prim.GetTypeName(), new_name))

    for prim_path, prim_type, new_name in rename_ops:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            continue
        parent = prim.GetParent()
        if not parent:
            continue

        base_name = new_name
        suffix = 1
        new_path = parent.GetPath().AppendChild(base_name)
        while stage.GetPrimAtPath(new_path):
            suffix += 1
            new_path = parent.GetPath().AppendChild(f"{base_name}_{suffix}")

        stage.DefinePrim(new_path, prim_type)
        new_prim = stage.GetPrimAtPath(new_path)
        if new_prim:
            for attr in prim.GetAttributes():
                new_attr = new_prim.CreateAttribute(
                    attr.GetName(),
                    attr.GetTypeName()
                )
                if new_attr:
                    new_attr.Set(attr.Get())
        stage.RemovePrim(prim_path)

    # Blender can sometimes export mesh schema attributes onto an Xform prim type.
    # Reality Composer Pro won't treat this as geometry, so we re-type such prims
    # to Mesh when they clearly contain mesh topology.
    _repair_xform_mesh_prims(stage)


def _is_valid_identifier(name: str) -> bool:
    """Return True if name is a valid USD identifier."""
    if not name:
        return False
    try:
        return Sdf.Path.IsValidIdentifier(name)
    except Exception:
        return re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name) is not None


def _repair_xform_mesh_prims(stage) -> None:
    def has_attr(prim, name: str) -> bool:
        try:
            attr = prim.GetAttribute(name)
            return bool(attr and attr.IsValid())
        except Exception:
            return False

    for prim in stage.Traverse():
        try:
            if prim.GetTypeName() != "Xform":
                continue
        except Exception:
            continue

        # Minimal signature of a Mesh: topology + points.
        if has_attr(prim, "faceVertexCounts") and has_attr(prim, "faceVertexIndices") and has_attr(prim, "points"):
            try:
                prim.SetTypeName("Mesh")
            except Exception:
                continue
