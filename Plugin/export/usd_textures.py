"""
USD texture staging utilities.

Ensures referenced assets are copied and paths are made relative for USDZ.
"""

from pathlib import Path
import hashlib

from .usd_utils import Sdf


TEXTURE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".exr",
    ".hdr",
    ".ktx",
    ".ktx2",
    ".tga",
    ".bmp",
    ".gif",
    ".dds",
    ".webp",
}


def prepare_textures(stage, usd_path: str, settings, diagnostics=None) -> None:
    """Prepare textures for USDZ packaging."""
    usd_dir = Path(usd_path).parent
    textures_dir = usd_dir / "textures"
    textures_dir.mkdir(exist_ok=True)

    import shutil

    # Copy textures and update asset paths
    seen_sources = {}
    seen_names = {}
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue

            asset_value = attr.Get()
            asset_path = None
            if isinstance(asset_value, Sdf.AssetPath):
                asset_path = asset_value.path or asset_value.resolvedPath
            elif asset_value:
                asset_path = str(asset_value)

            if not asset_path:
                continue

            if not _is_texture_path(asset_path):
                continue

            if asset_path.lower().startswith(("http:", "https:", "data:", "blob:", "mem:", "anon:")):
                continue

            source_path = Path(asset_path)
            if not source_path.is_absolute():
                source_path = (usd_dir / source_path).resolve()

            if not source_path.name:
                continue

            dest_name = _unique_destination_name(source_path, seen_names, diagnostics, "texture")
            dest_path = textures_dir / dest_name

            if source_path.exists():
                if source_path not in seen_sources:
                    try:
                        if source_path.resolve() != dest_path.resolve():
                            shutil.copy2(source_path, dest_path)
                        seen_sources[source_path] = dest_path
                        if diagnostics:
                            diagnostics.add_texture_copied(str(source_path))
                    except Exception as e:
                        if diagnostics:
                            diagnostics.add_texture_failed(str(source_path), str(e))
            else:
                # Normalize to relative even if the source is missing.
                if not dest_path.exists():
                    if diagnostics:
                        diagnostics.add_texture_failed(str(source_path), "Texture file not found")

            relative_path = Path("textures") / dest_path.name
            attr.Set(Sdf.AssetPath(str(relative_path)))


def _is_texture_path(asset_path: str) -> bool:
    suffix = Path(asset_path).suffix.lower()
    return suffix in TEXTURE_EXTENSIONS


def _unique_destination_name(path: Path, used: dict, diagnostics=None, label: str = "asset") -> str:
    """Return a deterministic unique filename, avoiding collisions."""
    name = path.name
    existing = used.get(name)
    if existing is None or existing == path:
        used[name] = path
        return name

    stem = path.stem
    suffix = path.suffix
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    candidate = f"{stem}_{digest}{suffix}"
    counter = 1
    while candidate in used and used[candidate] != path:
        candidate = f"{stem}_{digest}_{counter}{suffix}"
        counter += 1
    used[candidate] = path

    if diagnostics:
        diagnostics.add_warning(
            f"Renamed {label} '{name}' to '{candidate}' to avoid a name collision."
        )

    return candidate
