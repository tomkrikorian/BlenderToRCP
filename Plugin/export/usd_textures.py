"""
USD texture staging utilities.

Ensures referenced assets are copied and paths are made relative for USDZ.
"""

from pathlib import Path
import hashlib
import shutil

from .usd_utils import Sdf


TEXTURE_EXTENSIONS = {
    ".avif",
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

_CONVERTIBLE_TEXTURE_EXTENSIONS = {
    ".avif",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".tga",
    ".bmp",
    ".webp",
}

_ORIGINAL_FORMAT_BY_EXTENSION = {
    ".avif": "AVIF",
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".tga": "TARGA",
    ".bmp": "BMP",
    ".webp": "WEBP",
}

# Quality for lossy output formats (AVIF/JPEG/WebP) written via imbuf.
_LOSSY_TEXTURE_QUALITY = 90

# Image.file_format enum names whose ImBuf file_type identifier differs.
_IMBUF_FILE_TYPE_BY_FORMAT = {
    "TARGA": "TGA",
}


def prepare_textures(stage, usd_path: str, settings, diagnostics=None) -> None:
    """Prepare textures for USDZ packaging."""
    usd_dir = Path(usd_path).parent
    textures_dir = usd_dir / "textures"

    # Copy textures and update asset paths
    seen_sources = {}
    seen_names = {}
    seen_fingerprints = {}
    superseded_paths = set()
    texture_override = _texture_override_settings(settings, diagnostics)
    output_name_prefix = _texture_name_prefix(usd_path)
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

            effective_override = texture_override if _can_convert_texture(source_path) else None
            destination_source = _destination_source_path(source_path, effective_override, output_name_prefix)
            dest_name = _unique_destination_name(destination_source, seen_names, diagnostics, "texture")
            dest_path = textures_dir / dest_name

            if source_path.exists():
                source_key = _source_key(source_path, effective_override)
                fingerprint = _source_fingerprint(source_path, effective_override)
                deduped_dest = seen_fingerprints.get(fingerprint) if fingerprint else None
                if deduped_dest:
                    seen_sources[source_key] = deduped_dest
                    dest_path = deduped_dest
                elif source_key not in seen_sources:
                    try:
                        textures_dir.mkdir(parents=True, exist_ok=True)
                        if effective_override:
                            converted = _convert_texture(source_path, dest_path, effective_override, diagnostics)
                            conversion_artifact_type = "texture_override"
                            if not converted:
                                fallback_override = _texture_fallback_override(effective_override)
                                if fallback_override:
                                    fallback_dest_source = _destination_source_path(
                                        source_path,
                                        fallback_override,
                                        output_name_prefix,
                                    )
                                    fallback_dest_name = _unique_destination_name(
                                        fallback_dest_source,
                                        seen_names,
                                        diagnostics,
                                        "texture",
                                    )
                                    fallback_dest_path = textures_dir / fallback_dest_name
                                    converted = _convert_texture(
                                        source_path,
                                        fallback_dest_path,
                                        fallback_override,
                                        diagnostics,
                                    )
                                    if converted:
                                        dest_path = fallback_dest_path
                                        conversion_artifact_type = "texture_override_fallback"
                                        if diagnostics:
                                            diagnostics.add_warning(
                                                f"Saved resized PNG fallback for texture '{source_path}' because AVIF conversion failed."
                                            )
                            if converted and diagnostics:
                                diagnostics.add_texture_converted(str(source_path))
                                diagnostics.add_generated_file(
                                    conversion_artifact_type,
                                    str(dest_path),
                                    source=str(source_path),
                                    usd_attribute=str(attr.GetPath()),
                                    authored_path=asset_path,
                                )
                            if converted:
                                _mark_superseded_export_texture(
                                    source_path,
                                    dest_path,
                                    textures_dir,
                                    superseded_paths,
                                )
                            if not converted:
                                fallback_source = _destination_source_path(source_path, None, output_name_prefix)
                                dest_name = _unique_destination_name(fallback_source, seen_names, diagnostics, "texture")
                                dest_path = textures_dir / dest_name
                                if source_path.resolve() != dest_path.resolve():
                                    shutil.copy2(source_path, dest_path)
                        elif source_path.resolve() != dest_path.resolve():
                            shutil.copy2(source_path, dest_path)
                        if source_path.resolve() != dest_path.resolve():
                            _mark_superseded_export_texture(
                                source_path,
                                dest_path,
                                textures_dir,
                                superseded_paths,
                            )
                        seen_sources[source_key] = dest_path
                        if fingerprint:
                            seen_fingerprints[fingerprint] = dest_path
                        if diagnostics:
                            diagnostics.add_texture_copied(
                                str(source_path),
                                str(dest_path),
                                usd_attribute=str(attr.GetPath()),
                                authored_path=asset_path,
                            )
                    except Exception as e:
                        if diagnostics:
                            diagnostics.add_texture_failed(str(source_path), str(e))
                else:
                    dest_path = seen_sources[source_key]
            else:
                # Normalize to relative even if the source is missing.
                if not dest_path.exists():
                    if diagnostics:
                        diagnostics.add_texture_failed(str(source_path), "Texture file not found")

            relative_path = Path("textures") / dest_path.name
            attr.Set(Sdf.AssetPath(str(relative_path)))

    _remove_unreferenced_superseded_textures(stage, usd_dir, superseded_paths, diagnostics)


def _is_texture_path(asset_path: str) -> bool:
    suffix = Path(asset_path).suffix.lower()
    return suffix in TEXTURE_EXTENSIONS


def _texture_override_settings(settings, diagnostics=None):
    if not bool(getattr(settings, "export_texture_settings_enabled", False)):
        return None

    try:
        from . import bake_textures

        image_format = bake_textures._resolve_bake_image_format(settings, diagnostics)
        resolution = bake_textures._resolve_texture_override_resolution(settings)
    except Exception as exc:
        if diagnostics:
            diagnostics.add_warning(f"Export texture overrides disabled: {exc}")
        return None

    if image_format["file_format"] == "ORIGINAL" and int(resolution) <= 0:
        return None

    return {
        "file_format": image_format["file_format"],
        "extension": image_format["extension"],
        "resolution": int(resolution),
    }


def _texture_fallback_override(texture_override):
    file_format = str(texture_override.get("file_format") or "").upper()
    if file_format != "AVIF":
        return None
    resolution = int(texture_override.get("resolution") or 0)
    if resolution <= 0:
        return None
    return {
        "file_format": "PNG",
        "extension": ".png",
        "resolution": resolution,
    }


def _texture_name_prefix(usd_path: str) -> str:
    prefix = _safe_filename_stem(Path(usd_path).stem)
    return prefix or "scene"


def _safe_filename_stem(name: str) -> str:
    cleaned = []
    previous_separator = False
    for char in str(name or ""):
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
            previous_separator = False
        elif not previous_separator:
            cleaned.append("-")
            previous_separator = True
    return "".join(cleaned).strip("-_")


def _destination_source_path(source_path: Path, texture_override, output_name_prefix: str = "") -> Path:
    texture_override = texture_override or {}
    extension = texture_override.get("extension") or source_path.suffix
    stem = source_path.stem
    prefix = _safe_filename_stem(output_name_prefix)
    if prefix and not stem.startswith(f"{prefix}-"):
        stem = f"{prefix}-{stem}"
    return source_path.with_name(f"{stem}{extension}")


def _source_key(source_path: Path, texture_override) -> tuple[str, tuple | None]:
    try:
        resolved = str(source_path.resolve())
    except Exception:
        resolved = str(source_path)
    return resolved, _override_key(texture_override)


def _source_fingerprint(source_path: Path, texture_override) -> tuple[str, tuple | None] | None:
    digest = _file_digest(source_path)
    if not digest:
        return None
    return digest, _override_key(texture_override)


def _override_key(texture_override) -> tuple | None:
    if not texture_override:
        return None
    return (
        texture_override.get("file_format"),
        texture_override.get("extension"),
        int(texture_override.get("resolution") or 0),
    )


def _file_digest(path: Path) -> str | None:
    try:
        digest = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _can_convert_texture(source_path: Path) -> bool:
    return source_path.suffix.lower() in _CONVERTIBLE_TEXTURE_EXTENSIONS


def _convert_texture(source_path: Path, dest_path: Path, texture_override, diagnostics=None) -> bool:
    file_format = str(texture_override.get("file_format") or "").upper()
    if file_format == "ORIGINAL":
        file_format = _original_file_format_for_source(source_path)
        if not file_format:
            if diagnostics:
                diagnostics.add_warning(
                    f"Could not resize texture '{source_path}' in its original format; copied the original instead."
                )
            return False
        texture_override = dict(texture_override)
        texture_override["file_format"] = file_format

    if _convert_texture_with_imbuf(source_path, dest_path, texture_override, diagnostics):
        return True

    try:
        import bpy
    except Exception as exc:
        if diagnostics:
            diagnostics.add_warning(f"Could not convert texture '{source_path}': Blender image API unavailable ({exc}).")
        return False
    return _convert_texture_in_current_process(source_path, dest_path, texture_override, bpy, diagnostics)


def _original_file_format_for_source(source_path: Path) -> str | None:
    return _ORIGINAL_FORMAT_BY_EXTENSION.get(source_path.suffix.lower())


def _convert_texture_in_current_process(
    source_path: Path,
    dest_path: Path,
    texture_override,
    bpy,
    diagnostics=None,
) -> bool:
    image = None
    try:
        image = bpy.data.images.load(str(source_path), check_existing=False)
        _scale_image_to_max_resolution(image, int(texture_override.get("resolution") or 0))
        image.filepath_raw = str(dest_path)
        image.file_format = texture_override["file_format"]
        image.save()
        return dest_path.exists()
    except Exception as exc:
        if diagnostics:
            diagnostics.add_warning(
                f"Could not convert texture '{source_path}' to '{dest_path.suffix}'; copied the original instead ({exc})."
            )
        return False
    finally:
        if image is not None:
            try:
                if getattr(image, "users", 0) == 0:
                    bpy.data.images.remove(image)
            except Exception:
                pass


def _convert_texture_with_imbuf(
    source_path: Path,
    dest_path: Path,
    texture_override,
    diagnostics=None,
) -> bool:
    """Convert/resize a texture with the imbuf API (format chosen by extension)."""
    try:
        import imbuf
    except Exception:
        return False

    file_format = str(texture_override.get("file_format") or "").upper()
    ibuf = None
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        ibuf = imbuf.load(str(source_path))
        _scale_imbuf_to_max_resolution(ibuf, int(texture_override.get("resolution") or 0))
        # imbuf.write() encodes according to the buffer's file_type, not the
        # destination extension.
        ibuf.file_type = _IMBUF_FILE_TYPE_BY_FORMAT.get(file_format, file_format)
        ibuf.quality = _LOSSY_TEXTURE_QUALITY
        imbuf.write(ibuf, filepath=str(dest_path))
        return dest_path.exists()
    except Exception as exc:
        _remove_failed_conversion_output(dest_path)
        if diagnostics:
            diagnostics.add_warning(
                f"Could not convert texture '{source_path}' to '{dest_path.suffix}' via imbuf ({exc})."
            )
        return False
    finally:
        if ibuf is not None:
            try:
                ibuf.free()
            except Exception:
                pass


def _scale_imbuf_to_max_resolution(ibuf, max_resolution: int) -> None:
    if max_resolution <= 0:
        return
    width, height = ibuf.size
    largest = max(width, height)
    if largest <= max_resolution:
        return
    scale = max_resolution / largest
    ibuf.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        method='BILINEAR',
    )


def _remove_failed_conversion_output(dest_path: Path) -> None:
    try:
        if dest_path.exists():
            dest_path.unlink()
    except Exception:
        pass


def _scale_image_to_max_resolution(image, resolution: int) -> None:
    if resolution <= 0:
        return
    try:
        width, height = int(image.size[0]), int(image.size[1])
    except Exception:
        return
    if width <= 0 or height <= 0:
        return
    max_dimension = max(width, height)
    if max_dimension <= resolution:
        return
    scale = resolution / float(max_dimension)
    target_width = max(1, int(round(width * scale)))
    target_height = max(1, int(round(height * scale)))
    image.scale(target_width, target_height)


def _mark_superseded_export_texture(
    source_path: Path,
    dest_path: Path,
    textures_dir: Path,
    superseded_paths: set[Path],
) -> None:
    try:
        source_resolved = source_path.resolve()
        dest_resolved = dest_path.resolve()
        textures_resolved = textures_dir.resolve()
    except Exception:
        return
    if source_resolved == dest_resolved:
        return
    try:
        source_resolved.relative_to(textures_resolved)
    except ValueError:
        return
    superseded_paths.add(source_resolved)


def _remove_unreferenced_superseded_textures(
    stage,
    usd_dir: Path,
    superseded_paths: set[Path],
    diagnostics=None,
) -> None:
    if not superseded_paths:
        return

    referenced_paths = _referenced_texture_paths(stage, usd_dir)
    for path in sorted(superseded_paths):
        if path in referenced_paths or not path.exists():
            continue
        try:
            path.unlink()
            if diagnostics:
                diagnostics.add_generated_file("removed_superseded_texture", str(path))
        except Exception as exc:
            if diagnostics:
                diagnostics.add_warning(f"Failed to remove superseded texture '{path}': {exc}")


def _referenced_texture_paths(stage, usd_dir: Path) -> set[Path]:
    paths = set()
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            asset_value = attr.Get()
            if isinstance(asset_value, Sdf.AssetPath):
                asset_path = asset_value.path or asset_value.resolvedPath
            elif asset_value:
                asset_path = str(asset_value)
            else:
                continue
            if not asset_path or not _is_texture_path(asset_path):
                continue
            path = Path(asset_path)
            if not path.is_absolute():
                path = usd_dir / path
            try:
                paths.add(path.resolve())
            except Exception:
                paths.add(path)
    return paths


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
