"""Preflight checks for source assets used during export and baking."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def collect_missing_image_files_for_objects(objects: Iterable[Any], bpy_module=None) -> list[dict[str, Any]]:
    """Return external image files referenced by exported objects that are missing."""
    if bpy_module is None:
        import bpy as bpy_module  # type: ignore

    records: dict[str, dict[str, Any]] = {}
    for obj in objects or []:
        object_name = getattr(obj, "name", "")
        for material in _iter_object_materials(obj):
            material_name = getattr(material, "name", "")
            for image, node_name in _iter_material_images(material):
                if _image_is_packed(image):
                    continue
                source = getattr(image, "source", "")
                if source not in {"FILE", "SEQUENCE", "MOVIE", "TILED"}:
                    continue
                for raw_path, resolved_path in _resolved_image_paths(image, bpy_module):
                    if not raw_path:
                        continue
                    if _path_exists(resolved_path):
                        continue
                    key = resolved_path or raw_path
                    record = records.setdefault(key, {
                        "image": getattr(image, "name", ""),
                        "filepath": raw_path,
                        "resolved_path": resolved_path,
                        "source": source,
                        "users": [],
                    })
                    record["users"].append({
                        "object": object_name,
                        "material": material_name,
                        "node": node_name,
                    })
    return sorted(records.values(), key=lambda item: (item.get("resolved_path") or item.get("filepath") or ""))


def collect_asset_dependency_snapshot(context=None) -> dict[str, Any]:
    """Collect support-bundle friendly source asset dependency state."""
    try:
        import bpy

        context = context or bpy.context
        objects = list(getattr(context.scene, "objects", []) or [])
        missing = collect_missing_image_files_for_objects(objects, bpy)
        return {
            "missing_image_count": len(missing),
            "missing_images": missing,
        }
    except Exception as exc:
        return {"error": str(exc)}


def record_missing_image_files(diagnostics, missing_images: list[dict[str, Any]]) -> None:
    """Attach missing image information to diagnostics."""
    if not missing_images:
        return
    payload = {
        "missing_image_count": len(missing_images),
        "missing_images": missing_images,
    }
    diagnostics.data.setdefault("asset_dependencies", {}).update(payload)
    diagnostics.data.setdefault("textures", {}).setdefault("missing", []).extend(missing_images)
    diagnostics.add_error(_missing_images_message(missing_images))


def missing_images_status_message(missing_images: list[dict[str, Any]]) -> str:
    return _missing_images_message(missing_images)


def _missing_images_message(missing_images: list[dict[str, Any]]) -> str:
    count = len(missing_images)
    noun = "file" if count == 1 else "files"
    return (
        f"Missing external image {noun} ({count}). "
        "Pack or relink textures before Bake Textures & Export."
    )


def _iter_object_materials(obj) -> Iterable[Any]:
    seen: set[int] = set()
    for slot in getattr(obj, "material_slots", []) or []:
        material = getattr(slot, "material", None)
        if material is None:
            continue
        marker = id(material)
        if marker in seen:
            continue
        seen.add(marker)
        yield material


def _iter_material_images(material) -> Iterable[tuple[Any, str]]:
    if not getattr(material, "use_nodes", False):
        return
    node_tree = getattr(material, "node_tree", None)
    if node_tree is None:
        return
    yield from _iter_node_tree_images(node_tree, set())


def _iter_node_tree_images(node_tree, seen_trees: set[int]) -> Iterable[tuple[Any, str]]:
    marker = id(node_tree)
    if marker in seen_trees:
        return
    seen_trees.add(marker)
    for node in getattr(node_tree, "nodes", []) or []:
        if getattr(node, "type", "") == "TEX_IMAGE":
            image = getattr(node, "image", None)
            if image is not None:
                yield image, getattr(node, "name", "")
        nested_tree = getattr(node, "node_tree", None)
        if nested_tree is not None:
            yield from _iter_node_tree_images(nested_tree, seen_trees)


def _image_is_packed(image) -> bool:
    if getattr(image, "packed_file", None) is not None:
        return True
    packed_files = getattr(image, "packed_files", None)
    if packed_files is None:
        return False
    try:
        return len(packed_files) > 0
    except Exception:
        return False


def _resolved_image_paths(image, bpy_module) -> list[tuple[str, str]]:
    raw_path = str(getattr(image, "filepath", "") or getattr(image, "filepath_raw", "") or "")
    if not raw_path:
        return []
    try:
        resolved_path = str(bpy_module.path.abspath(raw_path, library=getattr(image, "library", None)))
    except Exception:
        try:
            resolved_path = str(bpy_module.path.abspath(raw_path))
        except Exception:
            resolved_path = raw_path

    if "<UDIM>" not in resolved_path:
        return [(raw_path, resolved_path)]

    paths: list[tuple[str, str]] = []
    for tile in getattr(image, "tiles", []) or []:
        number = str(getattr(tile, "number", ""))
        if not number:
            continue
        paths.append((raw_path.replace("<UDIM>", number), resolved_path.replace("<UDIM>", number)))
    return paths or [(raw_path, resolved_path)]


def _path_exists(path: str) -> bool:
    if not path:
        return False
    try:
        return Path(path).exists()
    except OSError:
        return False
