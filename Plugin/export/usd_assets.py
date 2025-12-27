"""
USD asset staging utilities.

Normalizes non-texture asset paths to be relative and stages assets
alongside the exported USD so the output stays portable.
"""

from pathlib import Path
import hashlib
from urllib.parse import urlparse
from urllib.request import url2pathname

from .usd_utils import Sdf
from .usd_textures import _is_texture_path


NON_FILE_PREFIXES = (
    "anon:",
    "mem:",
    "http:",
    "https:",
    "data:",
    "blob:",
)


def prepare_assets(stage, usd_path: str, diagnostics=None) -> None:
    """Stage non-texture assets and normalize their paths to be relative."""
    usd_dir = Path(usd_path).parent
    assets_dir = usd_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    import shutil

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

            if _is_texture_path(asset_path):
                continue

            if _is_non_file_asset(asset_path):
                continue

            source_path = Path(_normalize_file_url(asset_path))
            if not source_path.is_absolute():
                source_path = (usd_dir / source_path).resolve()

            if not source_path.name:
                continue

            dest_name = _unique_destination_name(source_path, seen_names, diagnostics, "asset")
            dest_path = assets_dir / dest_name
            if source_path.exists():
                if source_path not in seen_sources:
                    try:
                        if source_path.resolve() != dest_path.resolve():
                            shutil.copy2(source_path, dest_path)
                        seen_sources[source_path] = dest_path
                    except Exception as exc:
                        if diagnostics:
                            diagnostics.add_warning(
                                f"Failed to stage asset '{source_path}': {exc}"
                            )
            else:
                if diagnostics:
                    diagnostics.add_warning(
                        f"Asset file not found for '{source_path}'"
                    )

            relative_path = Path("assets") / dest_path.name
            attr.Set(Sdf.AssetPath(str(relative_path)))


def _is_non_file_asset(asset_path: str) -> bool:
    """Return True if the asset path is not a local file path."""
    lowered = asset_path.lower()
    if lowered.startswith(NON_FILE_PREFIXES):
        return True
    return False


def _normalize_file_url(asset_path: str) -> str:
    """Convert file:// URLs to filesystem paths when needed."""
    if asset_path.startswith("file://"):
        parsed = urlparse(asset_path)
        return url2pathname(parsed.path)
    return asset_path


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
