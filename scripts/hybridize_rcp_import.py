#!/usr/bin/env python3
"""Build a disposable record-group hybrid from two RCP ``.import`` artifacts.

This is a reverse-engineering harness, not an exporter.  It starts with an
RCP-authored baseline, substitutes selected groups from a generated candidate,
and rewrites candidate UUIDs to their structurally corresponding baseline
identities.  Unknown files, conflicting identity matches, dangling references,
and overwrite attempts fail closed.

The source artifacts are never modified.  The output is suitable only for a
disposable project on the exact RCP build that authored the baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._lib.rcp_import_contract import UUID_RE, inspect_import
from scripts._lib.rcp_import_format import ListValue, ObjectValue, parse_record

GROUPS = (
    "directories",
    "settings",
    "entities",
    "geometry",
    "skeleton",
    "animations",
    "materials",
)
_GROUP_SET = frozenset(GROUPS)
_TOP_LEVEL_GROUPS = {
    "geometry": "geometry",
    "mesh_descriptors": "geometry",
    "meshes": "geometry",
    "skeletons": "skeleton",
    "animations": "animations",
    "materials": "materials",
}
_RECORD_SUFFIXES = (
    ".tm_dir",
    ".tm_entity",
    ".tm_usd",
    ".tm_mesh_resource",
    ".tm_mesh_descriptor",
    ".tm_material",
    ".tm_texture",
    ".tm_geometry",
    ".tm_animation",
    ".tm_skeleton_hierarchy",
    ".tm_skeleton_definition",
)
_IDENTITY_FIELDS = frozenset({"__uuid", "__asset_uuid"})
_UUID_FULL_RE = re.compile(rf"^{UUID_RE.pattern}$")


class HybridizationError(ValueError):
    """Raised when two artifacts cannot be combined without guessing."""


def _require_import(root: Path, *, label: str) -> None:
    if not root.is_dir() or root.suffix != ".import":
        raise HybridizationError(f"{label} must be an existing .import directory")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise HybridizationError(f"{label} contains a symlink: {path}")


def _is_record(path: Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in _RECORD_SUFFIXES)


def record_group(relative_path: Path) -> str:
    """Return the closed record group for one artifact file."""

    if relative_path.name == "__tm_directory.tm_dir":
        return "directories"
    first = relative_path.parts[0]
    if first == "settings.tm_usd" or first == "settings.tm_buffers":
        return "settings"
    if len(relative_path.parts) == 1 and relative_path.name.endswith(".tm_entity"):
        return "entities"
    if len(relative_path.parts) > 1 and first.startswith("__") and first.endswith(
        ".tm_buffers"
    ):
        return "entities"
    group = _TOP_LEVEL_GROUPS.get(first)
    if group is not None:
        return group
    raise HybridizationError(f"unsupported artifact path: {relative_path}")


def _files(root: Path) -> dict[Path, Path]:
    files: dict[Path, Path] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        record_group(relative_path)
        files[relative_path] = path
    return files


def _uuid_paths(
    value: object,
    *,
    path: tuple[object, ...] = (),
) -> dict[tuple[object, ...], tuple[str, str]]:
    found: dict[tuple[object, ...], tuple[str, str]] = {}
    if isinstance(value, ObjectValue):
        occurrences: dict[str, int] = defaultdict(int)
        for field in value.fields:
            occurrence = occurrences[field.name]
            occurrences[field.name] += 1
            found.update(
                _uuid_paths(
                    field.value,
                    path=path + (("field", field.name, occurrence),),
                )
            )
    elif isinstance(value, ListValue):
        for index, item in enumerate(value.values):
            found.update(_uuid_paths(item, path=path + (("index", index),)))
    elif isinstance(value, str) and _UUID_FULL_RE.fullmatch(value):
        field_name = ""
        for segment in reversed(path):
            if isinstance(segment, tuple) and segment[0] == "field":
                field_name = str(segment[1])
                break
        found[path] = (value, field_name)
    return found


def _add_mapping(
    mapping: dict[str, str],
    inverse: dict[str, str],
    generated_uuid: str,
    baseline_uuid: str,
    *,
    context: str,
) -> None:
    existing = mapping.get(generated_uuid)
    if existing is not None and existing != baseline_uuid:
        raise HybridizationError(
            f"{context}: generated UUID {generated_uuid} maps to both "
            f"{existing} and {baseline_uuid}"
        )
    reverse = inverse.get(baseline_uuid)
    if reverse is not None and reverse != generated_uuid:
        raise HybridizationError(
            f"{context}: baseline UUID {baseline_uuid} maps from both "
            f"{reverse} and {generated_uuid}"
        )
    mapping[generated_uuid] = baseline_uuid
    inverse[baseline_uuid] = generated_uuid


def _record_identity_mapping(
    baseline_files: dict[Path, Path],
    generated_files: dict[Path, Path],
) -> tuple[dict[str, str], dict[str, str]]:
    mapping: dict[str, str] = {}
    inverse: dict[str, str] = {}
    for relative_path in sorted(set(baseline_files) & set(generated_files)):
        baseline_path = baseline_files[relative_path]
        generated_path = generated_files[relative_path]
        if not _is_record(baseline_path) or not _is_record(generated_path):
            continue
        try:
            baseline_record = parse_record(baseline_path.read_text(encoding="utf-8"))
            generated_record = parse_record(
                generated_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise HybridizationError(
                f"cannot parse corresponding record {relative_path}: {error}"
            ) from error
        baseline_values = _uuid_paths(baseline_record)
        generated_values = _uuid_paths(generated_record)
        for semantic_path in sorted(
            set(baseline_values) & set(generated_values), key=repr
        ):
            baseline_uuid, baseline_field = baseline_values[semantic_path]
            generated_uuid, generated_field = generated_values[semantic_path]
            if (
                baseline_field not in _IDENTITY_FIELDS
                or generated_field not in _IDENTITY_FIELDS
            ):
                continue
            _add_mapping(
                mapping,
                inverse,
                generated_uuid,
                baseline_uuid,
                context=str(relative_path),
            )
    return mapping, inverse


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _buffer_uuid(path: Path) -> str | None:
    prefix = path.name.split(".", 1)[0]
    if _UUID_FULL_RE.fullmatch(prefix):
        return prefix
    return None


def _buffer_identity_mapping(
    baseline: Path,
    generated: Path,
    baseline_files: dict[Path, Path],
    generated_files: dict[Path, Path],
    mapping: dict[str, str],
    inverse: dict[str, str],
) -> int:
    baseline_by_payload: dict[tuple[Path, int, str], list[Path]] = defaultdict(list)
    generated_by_payload: dict[tuple[Path, int, str], list[Path]] = defaultdict(list)
    for root, files, index in (
        (baseline, baseline_files, baseline_by_payload),
        (generated, generated_files, generated_by_payload),
    ):
        for relative_path, path in files.items():
            buffer_uuid = _buffer_uuid(path)
            if buffer_uuid is None:
                continue
            key = (
                relative_path.parent,
                path.stat().st_size,
                _sha256(path),
            )
            index[key].append(path.relative_to(root))

    matched = 0
    for key in sorted(set(baseline_by_payload) & set(generated_by_payload), key=repr):
        baseline_paths = sorted(baseline_by_payload[key])
        generated_paths = sorted(generated_by_payload[key])
        if len(baseline_paths) != len(generated_paths):
            raise HybridizationError(
                f"ambiguous content-identical buffers under {key[0]}"
            )
        for baseline_path, generated_path in zip(baseline_paths, generated_paths):
            baseline_uuid = _buffer_uuid(baseline / baseline_path)
            generated_uuid = _buffer_uuid(generated / generated_path)
            if baseline_uuid is None or generated_uuid is None:
                raise AssertionError("buffer UUID classification drift")
            _add_mapping(
                mapping,
                inverse,
                generated_uuid,
                baseline_uuid,
                context=str(key[0]),
            )
            matched += 1
    return matched


def build_identity_mapping(
    baseline: Path,
    generated: Path,
) -> tuple[dict[str, str], int]:
    """Return generated-to-baseline UUID mappings and matched buffer count."""

    baseline_files = _files(baseline)
    generated_files = _files(generated)
    mapping, inverse = _record_identity_mapping(baseline_files, generated_files)
    buffer_count = _buffer_identity_mapping(
        baseline,
        generated,
        baseline_files,
        generated_files,
        mapping,
        inverse,
    )
    return mapping, buffer_count


def _rewrite_uuid_text(text: str, mapping: dict[str, str]) -> str:
    return UUID_RE.sub(lambda match: mapping.get(match.group(0), match.group(0)), text)


def _uuid_graph(files: dict[Path, Path]) -> tuple[set[str], set[str]]:
    definitions: set[str] = set()
    occurrences: set[str] = set()
    for path in files.values():
        buffer_uuid = _buffer_uuid(path)
        if buffer_uuid is not None:
            definitions.add(buffer_uuid)
        if not _is_record(path):
            continue
        text = path.read_text(encoding="utf-8")
        record = parse_record(text)
        occurrences.update(UUID_RE.findall(text))
        for _semantic_path, (value, field_name) in _uuid_paths(record).items():
            if field_name in _IDENTITY_FIELDS:
                definitions.add(value)
    return definitions, occurrences


def _validate_no_new_dangling_references(
    baseline: Path,
    generated: Path,
    destination: Path,
    *,
    mapping: dict[str, str],
) -> int:
    baseline_definitions, baseline_occurrences = _uuid_graph(_files(baseline))
    generated_definitions, generated_occurrences = _uuid_graph(_files(generated))
    destination_definitions, destination_occurrences = _uuid_graph(
        _files(destination)
    )
    allowed_unresolved = baseline_occurrences - baseline_definitions
    allowed_unresolved.update(
        mapping.get(value, value)
        for value in generated_occurrences - generated_definitions
    )
    unresolved = destination_occurrences - destination_definitions
    unexpected = unresolved - allowed_unresolved
    if unexpected:
        rendered = ", ".join(sorted(unexpected))
        raise HybridizationError(
            f"hybrid introduces dangling UUID references: {rendered}"
        )
    return len(unresolved)


def _mapped_relative_path(relative_path: Path, mapping: dict[str, str]) -> Path:
    parts = []
    for part in relative_path.parts:
        prefix, separator, remainder = part.partition(".")
        if separator and prefix in mapping:
            parts.append(mapping[prefix] + separator + remainder)
        else:
            parts.append(part)
    return Path(*parts)


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "little"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _copy_selected_file(
    source: Path,
    destination: Path,
    *,
    rewrite_uuids: bool,
    mapping: dict[str, str],
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if rewrite_uuids and _is_record(source):
        text = source.read_text(encoding="utf-8")
        destination.write_text(_rewrite_uuid_text(text, mapping), encoding="utf-8")
        shutil.copystat(source, destination)
    else:
        shutil.copy2(source, destination)
    destination.chmod(destination.stat().st_mode | stat.S_IWUSR)


def create_hybrid_import(
    baseline: Path,
    generated: Path,
    destination: Path,
    *,
    generated_groups: Iterable[str],
    expected_profile: str = "skeletal",
) -> dict[str, object]:
    """Create and structurally validate one disposable hybrid artifact."""

    baseline = baseline.resolve()
    generated = generated.resolve()
    destination = destination.resolve()
    _require_import(baseline, label="baseline")
    _require_import(generated, label="generated")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    if destination.suffix != ".import":
        raise HybridizationError("destination must end in .import")
    groups = frozenset(generated_groups)
    unknown_groups = groups - _GROUP_SET
    if unknown_groups:
        raise HybridizationError(
            f"unknown generated groups: {', '.join(sorted(unknown_groups))}"
        )
    if not groups:
        raise HybridizationError("at least one generated group is required")

    baseline_files = _files(baseline)
    generated_files = _files(generated)
    mapping, matched_buffers = build_identity_mapping(baseline, generated)
    destination.mkdir(parents=True)
    try:
        selected_paths = set(baseline_files) | set(generated_files)
        for relative_path in sorted(selected_paths):
            group = record_group(relative_path)
            use_generated = group in groups
            source_files = generated_files if use_generated else baseline_files
            source = source_files.get(relative_path)
            if source is None:
                continue
            output_relative = (
                _mapped_relative_path(relative_path, mapping)
                if use_generated
                else relative_path
            )
            _copy_selected_file(
                source,
                destination / output_relative,
                rewrite_uuids=use_generated,
                mapping=mapping,
            )

        unresolved_uuid_count = _validate_no_new_dangling_references(
            baseline,
            generated,
            destination,
            mapping=mapping,
        )
        inspection = inspect_import(destination, expected_profile=expected_profile)
        inspection.require_valid()
        manifest: dict[str, object] = {
            "schema_version": 1,
            "baseline": str(baseline),
            "generated": str(generated),
            "destination": str(destination),
            "generated_groups": sorted(groups),
            "identity_mappings": len(mapping),
            "content_matched_buffers": matched_buffers,
            "record_count": len(inspection.records),
            "buffer_count": len(inspection.buffers),
            "unresolved_uuid_count": unresolved_uuid_count,
            "tree_sha256": _tree_sha256(destination),
        }
        manifest_path = destination.with_name(destination.name + ".hybrid.json")
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a fail-closed RCP build-80 hybrid for record-group bisection."
        )
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("generated", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--generated-group",
        dest="generated_groups",
        action="append",
        choices=GROUPS,
        required=True,
        help="record group to take from the generated candidate; repeat as needed",
    )
    parser.add_argument(
        "--profile",
        choices=("static", "transform", "skeletal"),
        default="skeletal",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        manifest = create_hybrid_import(
            args.baseline,
            args.generated,
            args.destination,
            generated_groups=args.generated_groups,
            expected_profile=args.profile,
        )
    except (FileExistsError, HybridizationError, OSError, ValueError) as error:
        print(f"rcp-import hybridization failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
