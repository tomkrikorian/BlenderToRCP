"""Immutable sidecar-generation namespaces for crash-safe publication."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import secrets
import unicodedata


GENERATION_MARKER_DIRECTORY = ".blendertorcp_generations"
_GENERATION_PATTERN = re.compile(r"[0-9a-f]{32}")


def output_sidecar_namespace(usd_path: str | Path) -> Path:
    """Return ``<root filename>/<generation>`` for one export attempt.

    The generation token is intentionally immutable and unique, rather than a
    stable output-name prefix. A publisher can therefore install every new
    sidecar first and atomically replace the root USD last. A hard process exit
    at any point leaves the old root and old generation coherent, or the new
    root and fully installed new generation coherent; at worst it leaks an
    unreferenced generation for later cleanup.
    """
    path = Path(usd_path).resolve()
    return Path(_portable_output_name(path.name)) / _generation_token(path)


def _generation_token(usd_path: Path) -> str:
    marker_root = usd_path.parent / GENERATION_MARKER_DIRECTORY
    if marker_root.is_symlink():
        raise RuntimeError(
            f"Refusing symlinked export-generation directory: {marker_root}"
        )
    if marker_root.exists() and not marker_root.is_dir():
        raise RuntimeError(
            f"Export-generation path is not a directory: {marker_root}"
        )
    marker_root.mkdir(parents=True, exist_ok=True)

    marker_key = hashlib.sha256(usd_path.name.encode("utf-8")).hexdigest()[:24]
    marker = marker_root / f"{marker_key}.txt"
    existing = _read_generation_marker(marker)
    if existing:
        return existing

    token = secrets.token_hex(16)
    try:
        descriptor = os.open(
            marker,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        existing = _read_generation_marker(marker)
        if existing:
            return existing
        raise RuntimeError(f"Invalid export-generation marker: {marker}")
    try:
        os.write(descriptor, f"{token}\n".encode("ascii"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return token


def _read_generation_marker(marker: Path) -> str | None:
    if not marker.exists():
        return None
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError(f"Invalid export-generation marker: {marker}")
    try:
        token = marker.read_text(encoding="ascii").strip()
    except Exception as exc:
        raise RuntimeError(
            f"Could not read export-generation marker '{marker}': {exc}"
        ) from exc
    if not _GENERATION_PATTERN.fullmatch(token):
        raise RuntimeError(f"Invalid export-generation marker: {marker}")
    return token


def _portable_output_name(name: str) -> str:
    normalized = unicodedata.normalize("NFC", str(name or "scene.usd"))
    portable = "".join(
        character
        if (character.isalnum() or character in {"-", "_", "."})
        else "_"
        for character in normalized
    )
    portable = portable or "scene.usd"
    if portable != normalized:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        portable = f"{portable}-{digest}"
    return portable
