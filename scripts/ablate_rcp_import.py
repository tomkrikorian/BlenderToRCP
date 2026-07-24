#!/usr/bin/env python3
"""Create a disposable `.import` copy with measured cache fields removed.

This is a reverse-engineering harness, not an exporter. It never edits the
source fixture and refuses to overwrite an existing destination.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._lib.rcp_import_format import (
    Field,
    ListValue,
    ObjectValue,
    parse_record,
    render_record,
)


def _without_fields(value: ObjectValue, names: frozenset[str]) -> ObjectValue:
    return ObjectValue(tuple(field for field in value.fields if field.name not in names))


def _strip_fields_from_list(
    record: ObjectValue, field_name: str, names: frozenset[str]
) -> ObjectValue:
    rewritten: list[Field] = []
    found = False
    for field in record.fields:
        if field.name != field_name:
            rewritten.append(field)
            continue
        found = True
        if not isinstance(field.value, ListValue):
            raise TypeError(f"{field_name!r} must be a list")
        values = []
        for value in field.value.values:
            if not isinstance(value, ObjectValue):
                raise TypeError(f"{field_name!r} must contain only objects")
            values.append(_without_fields(value, names))
        rewritten.append(Field(field.name, ListValue(tuple(values))))
    if not found:
        raise ValueError(f"record lacks required {field_name!r} field")
    return ObjectValue(tuple(rewritten))


def _string_field_values(
    record: ObjectValue, list_name: str, field_name: str
) -> frozenset[str]:
    values: set[str] = set()
    items = record.require_one(list_name)
    if not isinstance(items, ListValue):
        raise TypeError(f"{list_name!r} must be a list")
    for item in items.values:
        if not isinstance(item, ObjectValue):
            raise TypeError(f"{list_name!r} must contain only objects")
        for field in item.fields:
            if field.name == field_name:
                if not isinstance(field.value, str):
                    raise TypeError(f"{field_name!r} must be a string")
                values.add(field.value)
    return frozenset(values)


def strip_buffer_backed_cache(
    source: Path,
    destination: Path,
    *,
    strip_output: bool = True,
    strip_session: bool = True,
) -> None:
    """Copy an import and remove observed session/optimizer cache references."""

    if not source.is_dir() or source.suffix != ".import":
        raise ValueError("source must be an existing .import directory")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    if destination.suffix != ".import":
        raise ValueError("destination must end in .import")

    if not strip_output and not strip_session:
        raise ValueError("at least one cache class must be selected")

    shutil.copytree(source, destination)
    settings_path = destination / "settings.tm_usd"
    record = parse_record(settings_path.read_text(encoding="utf-8"))
    removed_ids: set[str] = set()
    if strip_output:
        removed_ids.update(_string_field_values(record, "settings", "output"))
        record = _strip_fields_from_list(record, "settings", frozenset({"output"}))
    if strip_session:
        removed_ids.update(_string_field_values(record, "variants", "session"))
        record = _strip_fields_from_list(record, "variants", frozenset({"session"}))
    settings_path.write_text(render_record(record).rstrip("\n"), encoding="utf-8")

    buffers = destination / "settings.tm_buffers"
    if buffers.exists():
        for buffer_path in buffers.iterdir():
            if buffer_path.name.split(".", 1)[0] in removed_ids:
                buffer_path.unlink()
        if not any(buffers.iterdir()):
            buffers.rmdir()


def strip_geometry_processing_metadata(
    source: Path,
    destination: Path,
    *,
    strip_transform: bool = True,
    strip_output: bool = True,
) -> None:
    """Copy an import and retain only each geometry's realized input payload."""

    if not source.is_dir() or source.suffix != ".import":
        raise ValueError("source must be an existing .import directory")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    if destination.suffix != ".import":
        raise ValueError("destination must end in .import")
    if not strip_transform and not strip_output:
        raise ValueError("at least one geometry metadata class must be selected")

    shutil.copytree(source, destination)
    geometry_records = sorted((destination / "geometry").glob("*.tm_geometry"))
    if not geometry_records:
        raise ValueError("import has no geometry records")
    for geometry_path in geometry_records:
        record = parse_record(geometry_path.read_text(encoding="utf-8"))
        removed_fields = set()
        if strip_transform:
            removed_fields.update({"transform", "transform_settings"})
        if strip_output:
            removed_fields.add("output_geometry")
        record = _without_fields(
            record,
            frozenset(removed_fields),
        )
        geometry_path.write_text(render_record(record).rstrip("\n"), encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a disposable build-80 .import cache-ablation fixture."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    cache_group = parser.add_mutually_exclusive_group(required=True)
    cache_group.add_argument(
        "--strip-buffer-backed-cache",
        action="store_true",
        help="remove both scene-optimizer output and variant-session buffers",
    )
    cache_group.add_argument(
        "--strip-output-cache",
        action="store_true",
        help="remove only the scene-optimizer output buffer",
    )
    cache_group.add_argument(
        "--strip-session-cache",
        action="store_true",
        help="remove only the variant-session buffer",
    )
    cache_group.add_argument(
        "--strip-geometry-processing",
        action="store_true",
        help="remove transform settings and unrealized output geometry metadata",
    )
    cache_group.add_argument(
        "--strip-geometry-transform",
        action="store_true",
        help="remove only geometry transform and transform-settings metadata",
    )
    cache_group.add_argument(
        "--strip-output-geometry",
        action="store_true",
        help="remove only unrealized output-geometry metadata",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if (
            args.strip_geometry_processing
            or args.strip_geometry_transform
            or args.strip_output_geometry
        ):
            strip_geometry_processing_metadata(
                args.source.resolve(),
                args.destination.resolve(),
                strip_transform=(
                    args.strip_geometry_processing or args.strip_geometry_transform
                ),
                strip_output=(
                    args.strip_geometry_processing or args.strip_output_geometry
                ),
            )
        else:
            strip_buffer_backed_cache(
                args.source.resolve(),
                args.destination.resolve(),
                strip_output=args.strip_buffer_backed_cache or args.strip_output_cache,
                strip_session=args.strip_buffer_backed_cache or args.strip_session_cache,
            )
    except (FileExistsError, OSError, TypeError, ValueError) as error:
        print(f"rcp-import ablation failed: {error}", file=sys.stderr)
        return 2
    print(args.destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
