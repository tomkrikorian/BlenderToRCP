"""Stage-then-swap publication for experimental RCP ``.import`` packages.

``rcp_import_generator.generate_static_import`` writes a complete directory
tree and refuses to touch a destination that already exists. That refusal is a
good default - a generated package can be one Reality Composer Pro is actively
managing - but it left no supported way to refresh a package after a scene
edit, because reimport inside RCP duplicates every record.

This module adds the explicit opt-in and, with it, the publication discipline
the USD publisher already applies to files
(``Plugin/export/blender_usd_export.py``): the whole replacement is written to
a staging directory first, the swap is the last step, and the previous package
is *moved aside* rather than deleted, so it can be put back if anything after
the move fails. Nothing is ever removed from the destination path while it is
still the destination.

The staging directory is a sibling of the destination on purpose. It has to be
on the same filesystem for the swap to be a rename, and the package records the
source USD as a path relative to ``destination.parent``, so a sibling produces
byte-identical output to writing at the destination directly. That identity is
what makes a refresh safe: the writer is deterministic, so re-exporting an
unchanged scene reproduces the same package rather than churning every record's
identity.

Nothing here imports ``bpy`` or ``pxr``, so the refusals can be evaluated
during early validation, before an export spends minutes baking.
"""

from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path


PACKAGE_SUFFIX = ".import"
# Every generated package carries a root directory record. A directory without
# it is not something this add-on wrote, and is never replaced.
PACKAGE_MARKER = "__tm_directory.tm_dir"

_STAGING_PREFIX = ".blendertorcp-import-staging-"
_REPLACED_PREFIX = ".blendertorcp-import-replaced-"

# Error codes. ``RCP_IMPORT_EXISTS`` is the pre-existing default refusal and its
# code and message are deliberately unchanged.
EXISTS = "RCP_IMPORT_EXISTS"
NOT_IMPORT_PATH = "RCP_IMPORT_REPLACE_NOT_IMPORT_PATH"
SYMLINK = "RCP_IMPORT_REPLACE_SYMLINK"
NOT_A_PACKAGE = "RCP_IMPORT_REPLACE_NOT_A_PACKAGE"
BUSY = "RCP_IMPORT_REPLACE_BUSY"
RESTORE_FAILED = "RCP_IMPORT_REPLACE_RESTORE_FAILED"
NOT_APPLICABLE = "RCP_IMPORT_REPLACE_NOT_APPLICABLE"


class ImportPublishError(RuntimeError):
    """A refusal carrying the stable error code the surfaces report."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Opt-in resolution
# ---------------------------------------------------------------------------

def resolve_replace_request(args: dict, settings, *, rcp_import_export: bool) -> bool:
    """Resolve the effective replace opt-in for one export.

    ``--replace`` is a per-run request; ``rcp_import_replace`` is the sticky
    scene setting the Blender sidebar checkbox writes. Either one enables a
    refresh, and both are ignored for formats that have no package to refresh -
    except that passing the flag explicitly for such a format is an error
    rather than a silent no-op, so a mistyped command never looks like it did
    something it did not.
    """
    requested = bool((args or {}).get("replace"))
    if requested and not rcp_import_export:
        raise ImportPublishError(
            "--replace refreshes an existing .import package and only applies "
            "to --format RCP_IMPORT.",
            code=NOT_APPLICABLE,
        )
    if not rcp_import_export:
        return False
    return requested or bool(getattr(settings, "rcp_import_replace", False))


# ---------------------------------------------------------------------------
# Destination inspection
# ---------------------------------------------------------------------------

def is_package_directory(path: str | Path) -> bool:
    """Report whether ``path`` looks like a package this add-on generated."""
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_dir():
        return False
    marker = candidate / PACKAGE_MARKER
    return marker.is_file() and not marker.is_symlink()


def _is_present(path: Path) -> bool:
    # ``exists()`` follows symlinks and so reports False for a broken one.
    # A dangling symlink still occupies the destination name.
    return path.exists() or path.is_symlink()


def _require_package_path(path: Path, display: str) -> None:
    name = path.name
    if not name.endswith(PACKAGE_SUFFIX) or len(name) <= len(PACKAGE_SUFFIX):
        raise ImportPublishError(
            f"Refusing to touch a destination that is not a .import path: {display}",
            code=NOT_IMPORT_PATH,
        )


def check_destination(destination: str | Path, *, replace: bool) -> None:
    """Validate a ``.import`` destination before an export commits to it.

    Heals an interrupted earlier replacement first, so validation sees the real
    state of the world rather than the middle of an abandoned swap. Raises
    :class:`ImportPublishError` for every refusal; returns ``None`` when the
    export may proceed.
    """
    path = Path(destination)
    _require_package_path(path, str(destination))
    recover_interrupted_replacement(path)
    _validate_destination(path, destination, replace=replace)


def _validate_destination(path: Path, destination, *, replace: bool) -> None:
    """Apply the destination refusals without healing anything first."""
    display = str(destination)
    if not _is_present(path):
        return
    if not replace:
        raise ImportPublishError(
            f"Refusing to overwrite existing .import directory: {display}",
            code=EXISTS,
        )
    if path.is_symlink():
        raise ImportPublishError(
            f"Refusing to replace symlinked .import destination: {display}",
            code=SYMLINK,
        )
    if not path.is_dir():
        raise ImportPublishError(
            f"Refusing to replace .import destination that is not a directory: {display}",
            code=NOT_A_PACKAGE,
        )
    if not is_package_directory(path):
        raise ImportPublishError(
            "Refusing to replace a directory that is not a generated .import "
            f"package (no {PACKAGE_MARKER}): {display}",
            code=NOT_A_PACKAGE,
        )


# ---------------------------------------------------------------------------
# Interrupted-swap recovery
# ---------------------------------------------------------------------------

def _backup_path(destination: Path) -> Path:
    return destination.parent / f"{_REPLACED_PREFIX}{destination.name}"


def recover_interrupted_replacement(destination: str | Path) -> str | None:
    """Heal a replacement interrupted between its two renames.

    The swap moves the old package aside, moves the new one in, then removes
    the old one. A hard exit therefore leaves exactly one of two states, both
    of which still hold a complete package:

    ``restored``
        the destination is missing and the backup holds the old package.
    ``discarded``
        the destination holds the new package and the backup is redundant.

    Returns the action taken, or ``None`` when there was nothing to heal.
    """
    path = Path(destination)
    backup = _backup_path(path)
    # A symlink at the backup name is not something this module created.
    if backup.is_symlink() or not backup.is_dir():
        return None
    if _is_present(path):
        shutil.rmtree(backup, ignore_errors=True)
        return "discarded"
    os.rename(backup, path)
    return "restored"


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

def _staging_path(destination: Path) -> Path:
    token = secrets.token_hex(8)
    return destination.parent / f"{_STAGING_PREFIX}{token}-{destination.name}"


def _discard(path: Path) -> None:
    if path.is_symlink():
        return
    shutil.rmtree(path, ignore_errors=True)


def publish_static_import(
    *,
    staged_source: str | Path,
    recorded_source: str | Path,
    destination: str | Path,
    replace: bool,
    generate=None,
    commit_source=None,
):
    """Generate a package into staging and swap it into ``destination``.

    ``staged_source`` is the USD actually read. ``recorded_source`` is the path
    the package records as its source - the ``.usda`` published beside the
    package, which may not exist yet. Reading the staged copy and recording the
    final path keeps the package and its source USD consistent: the package is
    fully built before ``commit_source`` publishes the ``.usda``, so a
    generation failure leaves both the old package and the old ``.usda`` in
    place instead of pairing a refreshed source with a stale package.

    ``generate`` defaults to
    ``rcp_import_generator.generate_static_import``; it is injectable so the
    publication discipline can be tested without a USD stage.
    """
    destination_path = Path(destination)
    check_destination(destination_path, replace=replace)

    if generate is None:
        from .rcp_import_generator import generate_static_import as generate

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    staging = _staging_path(destination_path)
    try:
        generate(
            staged_source,
            staging,
            record_source=recorded_source,
        )
        if commit_source is not None:
            commit_source()
        _install(staging, destination_path, replace=replace)
    except BaseException:
        _discard(staging)
        raise
    return destination_path


def _install(staging: Path, destination: Path, *, replace: bool) -> None:
    """Move a fully written staged package into place.

    Re-validates the destination immediately before the destructive step: the
    early check ran before the export, and this is the code that actually moves
    user data.
    """
    if not _is_present(destination):
        os.rename(staging, destination)
        return

    # Deliberately without recovery: the backup name is about to hold the only
    # copy of the previous package, and healing here could discard it.
    _validate_destination(destination, destination, replace=replace)

    backup = _backup_path(destination)
    if _is_present(backup):
        raise ImportPublishError(
            "Refusing to replace an .import package while another replacement "
            f"is in progress: {backup}",
            code=BUSY,
        )

    os.rename(destination, backup)
    try:
        os.rename(staging, destination)
    except BaseException:
        try:
            os.rename(backup, destination)
        except BaseException as restore_error:
            raise ImportPublishError(
                f"Replacing {destination} failed and the previous package could "
                f"not be moved back; it is preserved at {backup} "
                f"({restore_error}).",
                code=RESTORE_FAILED,
            ) from restore_error
        raise
    shutil.rmtree(backup, ignore_errors=True)
