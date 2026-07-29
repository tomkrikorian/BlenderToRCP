"""Fail-closed structural inspection for Reality Composer Pro ``.import`` assets.

The text grammar and ordinary buffer content hash are decoded. Nested record
semantics and optimized geometry validity hashes remain build-pinned work in
progress. Unknown record types, top-level fields, or filesystem shapes are
errors.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts._lib.rcp_import_format import buffer_content_hash, parse_record

CONTRACT_NAME = "rcp-import-structural-v1"
REPORT_SCHEMA_VERSION = 1

UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
UUID_RE = re.compile(rf"\b({UUID_PATTERN})\b")
BUFFER_NAME_RE = re.compile(rf"^({UUID_PATTERN})\.([0-9a-f]{{15,16}})(?:\..+)?$")
TOP_LEVEL_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:\s|$)")
TYPE_LINE_RE = re.compile(r'^__type:\s*"([^"]+)"\s*$')
UUID_LINE_RE = re.compile(rf'^__uuid:\s*"({UUID_PATTERN})"\s*$')
SOURCE_PATH_RE = re.compile(r'^source_path:\s*"([^"]+)"\s*$', re.MULTILINE)

RECORD_SUFFIX_TYPES: dict[str, frozenset[str]] = {
    ".tm_dir": frozenset({"tm_asset_directory"}),
    ".tm_entity": frozenset({"tm_entity"}),
    ".tm_usd": frozenset({"tm_usd_asset"}),
    ".tm_mesh_resource": frozenset({"tm_mesh_resource"}),
    ".tm_mesh_descriptor": frozenset({"tm_mesh_descriptor"}),
    ".tm_material": frozenset({"tm_material"}),
    ".tm_texture": frozenset({"tm_texture"}),
    ".tm_geometry": frozenset({"tm_geometry"}),
    ".tm_animation": frozenset({"tm_timeline"}),
    ".tm_skeleton_hierarchy": frozenset({"tm_skeleton_hierarchy"}),
    ".tm_skeleton_definition": frozenset({"tm_skeleton_definition"}),
}

# Only top-level fields are contracted here. Nested semantics are still opaque
# and must not be used as a writer specification.
TOP_LEVEL_FIELDS: dict[str, frozenset[str]] = {
    "tm_asset_directory": frozenset({"__type", "__uuid", "name", "parent"}),
    "tm_entity": frozenset(
        {
            "__type",
            "__uuid",
            "name",
            "components",
            "children",
            "__asset_uuid",
            "__asset_labels",
            "__prototype_type",
            "__prototype_uuid",
        }
    ),
    "tm_usd_asset": frozenset(
        {
            "__type",
            "__uuid",
            "source_path",
            "settings",
            "pro_settings",
            "variants",
            "__asset_uuid",
        }
    ),
    "tm_mesh_resource": frozenset(
        {"__type", "__uuid", "instances", "models", "skeletons", "__asset_uuid"}
    ),
    "tm_mesh_descriptor": frozenset(
        {
            "__type",
            "__uuid",
            "vertex_count",
            "face_vertex_counts",
            "indices",
            "attributes",
            # RCP 3 build 80 authors face-material partitions here during
            # reimport.  The writer does not synthesize this field until its
            # nested buffer/UUID contract is independently understood.
            "subsets",
            "skinning_data",
            "__asset_uuid",
        }
    ),
    "tm_material": frozenset(
        {
            "__type",
            "__uuid",
            "shader",
            "shader_graph",
            "descriptor",
            "__asset_uuid",
            "__asset_thumbnail",
        }
    ),
    "tm_texture": frozenset(
        {
            "__type",
            "__uuid",
            "source_filename",
            "source_texture",
            "transform",
            "transform_settings",
            "color_space",
            "__asset_uuid",
            "__asset_labels",
            "__asset_thumbnail",
        }
    ),
    "tm_geometry": frozenset(
        {
            "__type",
            "__uuid",
            "name",
            "input_geometry",
            "transform",
            "transform_settings",
            "output_geometry",
            "validity_hash",
            "__asset_uuid",
        }
    ),
    "tm_timeline": frozenset(
        {"__type", "__uuid", "name", "type", "properties", "__asset_uuid"}
    ),
    "tm_skeleton_hierarchy": frozenset(
        {"__type", "__uuid", "name", "joints", "__asset_uuid"}
    ),
    "tm_skeleton_definition": frozenset(
        {
            "__type",
            "__uuid",
            "skeleton hierarchy",
            # RCP 3 build 80 adds this external matching result on skeletal
            # reimport.  The referenced UUID is not defined by the .import
            # record graph, so it remains inspector-only and must never be
            # synthesized by the writer.
            "matched_skeleton_hierarchies",
            "__asset_uuid",
        }
    ),
}

# RCP resolves this identity before creating internal asset data. On the pinned
# build, omitting it sends a nil item into CoreRealityTools and rejects the
# record rather than treating it as optional metadata.
REQUIRED_TOP_LEVEL_FIELDS: dict[str, frozenset[str]] = {
    record_type: frozenset({"__type", "__uuid", "__asset_uuid"})
    for record_type in TOP_LEVEL_FIELDS
    if record_type != "tm_asset_directory"
}
REQUIRED_TOP_LEVEL_FIELDS["tm_asset_directory"] = frozenset(
    {"__type", "__uuid", "name"}
)

PROFILE_REQUIREMENTS: dict[str, dict[str, int]] = {
    "static": {
        "tm_usd_asset": 1,
        "tm_entity": 1,
        "tm_mesh_resource": 1,
        "tm_mesh_descriptor": 1,
        "tm_geometry": 1,
    },
    "transform": {
        "tm_usd_asset": 1,
        "tm_entity": 1,
        "tm_mesh_resource": 1,
        "tm_mesh_descriptor": 1,
        "tm_geometry": 1,
        "tm_timeline": 1,
    },
    "skeletal": {
        "tm_usd_asset": 1,
        "tm_entity": 1,
        "tm_mesh_resource": 1,
        "tm_mesh_descriptor": 1,
        "tm_geometry": 1,
        "tm_timeline": 2,
        "tm_skeleton_hierarchy": 1,
        "tm_skeleton_definition": 1,
    },
}


class ContractError(ValueError):
    """Raised when an asset falls outside the bounded structural contract."""


@dataclass(frozen=True)
class Record:
    relative_path: str
    record_type: str
    byte_count: int
    sha256: str
    normalized_sha256: str
    top_level_fields: tuple[str, ...]
    uuid_definition_count: int
    uuid_occurrence_count: int


@dataclass
class Inspection:
    root: Path
    records: list[Record] = field(default_factory=list)
    buffers: list[dict[str, Any]] = field(default_factory=list)
    source_path: str | None = None
    source_path_kind: str | None = None
    resolved_source_path: Path | None = None
    all_uuid_definitions: set[str] = field(default_factory=set)
    all_uuid_mentions: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    def require_valid(self) -> None:
        if self.errors:
            joined = "\n".join(f"- {error}" for error in self.errors)
            raise ContractError(f"{self.root} violates {CONTRACT_NAME}:\n{joined}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_suffix(path: Path) -> str | None:
    for suffix in sorted(RECORD_SUFFIX_TYPES, key=len, reverse=True):
        if path.name.endswith(suffix):
            return suffix
    return None


def _check_balanced(text: str) -> str | None:
    stack: list[tuple[str, int]] = []
    pairs = {"}": "{", "]": "["}
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            stack.append((character, index))
        elif character in "]}":
            if not stack or stack[-1][0] != pairs[character]:
                return f"unbalanced {character!r} at byte {index}"
            stack.pop()
    if in_string:
        return "unterminated string"
    if stack:
        return f"unclosed {stack[-1][0]!r} at byte {stack[-1][1]}"
    return None


def _normalized_record_bytes(text: str) -> bytes:
    normalized = UUID_RE.sub("<uuid>", text)
    normalized = re.sub(
        r'(?m)^source_path:\s*"[^"]*"\s*$',
        'source_path: "<absolute-source-path>"',
        normalized,
    )
    return normalized.encode("utf-8")


def _canonical_relative_path(relative_path: str) -> str:
    path = UUID_RE.sub("<uuid>", relative_path)
    return re.sub(r"(?<=\.)[0-9a-f]{15,16}(?=\.|$)", "<payload-hash>", path)


def _inspect_record(path: Path, relative_path: str, inspection: Inspection) -> None:
    suffix = _record_suffix(path)
    if suffix is None:
        inspection.errors.append(f"{relative_path}: unsupported record suffix")
        return
    try:
        data = path.read_bytes()
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        inspection.errors.append(f"{relative_path}: record is not UTF-8 text")
        return

    lines = text.splitlines()
    if len(lines) < 2:
        inspection.errors.append(
            f"{relative_path}: record must start with __type and __uuid"
        )
        return
    type_match = TYPE_LINE_RE.fullmatch(lines[0])
    uuid_match = UUID_LINE_RE.fullmatch(lines[1])
    if not type_match or not uuid_match:
        inspection.errors.append(f"{relative_path}: invalid __type/__uuid header")
        return

    record_type = type_match.group(1)
    if record_type not in RECORD_SUFFIX_TYPES[suffix]:
        inspection.errors.append(
            f"{relative_path}: {record_type!r} is not allowed for {suffix}"
        )
        return

    balance_error = _check_balanced(text)
    parsed_record = None
    if balance_error:
        inspection.errors.append(f"{relative_path}: {balance_error}")
    else:
        try:
            parsed_record = parse_record(text)
        except ValueError as error:
            inspection.errors.append(f"{relative_path}: invalid record syntax: {error}")

    if parsed_record is not None:
        top_level_fields = tuple(field.name for field in parsed_record.fields)
    else:
        top_level_fields = tuple(
            match.group(1)
            for line in lines
            if (match := TOP_LEVEL_FIELD_RE.match(line)) is not None
        )
    unknown_fields = sorted(set(top_level_fields) - TOP_LEVEL_FIELDS[record_type])
    if unknown_fields:
        inspection.errors.append(
            f"{relative_path}: unsupported top-level fields {unknown_fields}"
        )
    missing_fields = sorted(
        REQUIRED_TOP_LEVEL_FIELDS[record_type] - set(top_level_fields)
    )
    if missing_fields:
        inspection.errors.append(
            f"{relative_path}: missing required top-level fields {missing_fields}"
        )

    definitions = re.findall(rf'(?m)^\s*__uuid:\s*"({UUID_PATTERN})"\s*$', text)
    duplicates = inspection.all_uuid_definitions.intersection(definitions)
    if duplicates:
        inspection.errors.append(
            f"{relative_path}: duplicate UUID definitions {sorted(duplicates)}"
        )
    if len(definitions) != len(set(definitions)):
        inspection.errors.append(
            f"{relative_path}: duplicate UUID definition within record"
        )
    inspection.all_uuid_definitions.update(definitions)
    inspection.all_uuid_mentions.update(UUID_RE.findall(text))

    source_match = SOURCE_PATH_RE.search(text)
    if source_match:
        if inspection.source_path is not None:
            inspection.errors.append(f"{relative_path}: multiple source_path fields")
        inspection.source_path = source_match.group(1)

    inspection.records.append(
        Record(
            relative_path=relative_path,
            record_type=record_type,
            byte_count=len(data),
            sha256=_sha256(data),
            normalized_sha256=_sha256(_normalized_record_bytes(text)),
            top_level_fields=top_level_fields,
            uuid_definition_count=len(definitions),
            uuid_occurrence_count=len(UUID_RE.findall(text)),
        )
    )


def inspect_import(
    root: Path | str, *, expected_profile: str | None = None
) -> Inspection:
    root = Path(root).resolve()
    inspection = Inspection(root=root)
    if not root.is_dir() or not root.name.endswith(".import"):
        inspection.errors.append("root must be an existing directory ending in .import")
        return inspection

    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root).as_posix()
        if path.is_symlink():
            inspection.errors.append(f"{relative_path}: symlinks are unsupported")
            continue
        if path.is_dir():
            if path.name.endswith(".tm_buffers"):
                continue
            marker = path / "__tm_directory.tm_dir"
            if not marker.is_file():
                inspection.errors.append(
                    f"{relative_path}: non-buffer directory lacks __tm_directory.tm_dir"
                )
            continue

        in_buffer_dir = any(
            parent.name.endswith(".tm_buffers") for parent in path.parents
        )
        if in_buffer_dir:
            match = BUFFER_NAME_RE.fullmatch(path.name)
            if match is None:
                inspection.errors.append(
                    f"{relative_path}: unsupported opaque buffer filename"
                )
                continue
            data = path.read_bytes()
            content_hash = buffer_content_hash(data)
            name_hash = match.group(2)
            inspection.buffers.append(
                {
                    "relative_path": relative_path,
                    "canonical_path": _canonical_relative_path(relative_path),
                    "byte_count": len(data),
                    "sha256": _sha256(data),
                    "id": match.group(1),
                    "name_hash": name_hash,
                    "content_hash": content_hash,
                    "name_hash_matches_content": int(name_hash, 16)
                    == int(content_hash, 16),
                }
            )
            continue
        _inspect_record(path, relative_path, inspection)

    root_marker = root / "__tm_directory.tm_dir"
    if not root_marker.is_file():
        inspection.errors.append("root lacks __tm_directory.tm_dir")

    # Every RCP-authored asset measured for build 80.0.1.500.1 mentions each of
    # its buffer payload ids from at least one record. A payload no record can
    # name is unreachable, and is how a record silently overwritten by a name
    # collision shows up on disk.
    orphaned_buffers = sorted(
        item["relative_path"]
        for item in inspection.buffers
        if item["id"] not in inspection.all_uuid_mentions
    )
    for relative_path in orphaned_buffers:
        inspection.errors.append(
            f"{relative_path}: buffer payload is referenced by no record"
        )

    type_counts = Counter(record.record_type for record in inspection.records)
    if type_counts["tm_usd_asset"] != 1:
        inspection.errors.append(
            f"expected exactly one tm_usd_asset, found {type_counts['tm_usd_asset']}"
        )
    if inspection.source_path is None:
        inspection.errors.append("tm_usd_asset lacks source_path")
    else:
        source_path = Path(inspection.source_path)
        if source_path.is_absolute():
            inspection.source_path_kind = "absolute"
            inspection.resolved_source_path = source_path.resolve()
        else:
            project_root = root.parent
            workspace_root = project_root.parent.resolve()
            resolved_source = (project_root / source_path).resolve()
            try:
                resolved_source.relative_to(workspace_root)
            except ValueError:
                inspection.errors.append(
                    "relative source_path escapes the project workspace"
                )
            else:
                inspection.source_path_kind = "project-relative"
                inspection.resolved_source_path = resolved_source

    if expected_profile is not None:
        if expected_profile not in PROFILE_REQUIREMENTS:
            inspection.errors.append(f"unknown expected profile {expected_profile!r}")
        else:
            for record_type, minimum in PROFILE_REQUIREMENTS[expected_profile].items():
                actual = type_counts[record_type]
                if actual < minimum:
                    inspection.errors.append(
                        f"profile {expected_profile!r} requires {minimum} {record_type}, found {actual}"
                    )
            if expected_profile == "static" and type_counts["tm_timeline"]:
                inspection.errors.append(
                    "static profile unexpectedly contains tm_timeline"
                )
            if expected_profile in {"static", "transform"} and (
                type_counts["tm_skeleton_hierarchy"]
                or type_counts["tm_skeleton_definition"]
            ):
                inspection.errors.append(
                    f"{expected_profile} profile unexpectedly contains skeletal records"
                )

    return inspection


def build_report(
    inspection: Inspection,
    *,
    expected_profile: str | None = None,
    rcp_version: str | None = None,
    rcp_build: str | None = None,
) -> dict[str, Any]:
    inspection.require_valid()
    type_counts = Counter(record.record_type for record in inspection.records)
    canonical_record_fingerprints = sorted(
        (
            {
                "path": _canonical_relative_path(record.relative_path),
                "record_type": record.record_type,
                "normalized_sha256": record.normalized_sha256,
            }
            for record in inspection.records
        ),
        key=lambda item: (item["path"], item["record_type"]),
    )
    canonical_buffer_fingerprints = sorted(
        (
            {
                "path": item["canonical_path"],
                "byte_count": item["byte_count"],
                "sha256": item["sha256"],
            }
            for item in inspection.buffers
        ),
        key=lambda item: (item["path"], item["sha256"]),
    )
    canonical_buffer_layout = sorted(
        (
            {
                "path": item["canonical_path"],
                "byte_count": item["byte_count"],
            }
            for item in inspection.buffers
        ),
        key=lambda item: (item["path"], item["byte_count"]),
    )
    source_path = inspection.source_path or ""
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "contract": CONTRACT_NAME,
        "asset_name": inspection.root.name,
        "expected_profile": expected_profile,
        "rcp": {"version": rcp_version, "build": rcp_build},
        "source": {
            "basename": Path(source_path).name,
            "extension": Path(source_path).suffix,
            "path_kind": inspection.source_path_kind,
            "redacted_path_sha256": _sha256(source_path.encode("utf-8")),
            "exists": bool(
                inspection.resolved_source_path
                and inspection.resolved_source_path.is_file()
            ),
        },
        "identity": {
            "uuid_definition_set_sha256": _sha256(
                "\n".join(sorted(inspection.all_uuid_definitions)).encode("ascii")
            )
        },
        "counts": {
            "records": len(inspection.records),
            "opaque_buffers": len(inspection.buffers),
            "record_bytes": sum(record.byte_count for record in inspection.records),
            "opaque_buffer_bytes": sum(
                item["byte_count"] for item in inspection.buffers
            ),
            "uuid_definitions": len(inspection.all_uuid_definitions),
            "uuid_occurrences": sum(
                record.uuid_occurrence_count for record in inspection.records
            ),
            "content_hashed_buffers": sum(
                bool(item["name_hash_matches_content"]) for item in inspection.buffers
            ),
            "derived_or_unknown_hashed_buffers": sum(
                not item["name_hash_matches_content"] for item in inspection.buffers
            ),
        },
        "record_types": dict(sorted(type_counts.items())),
        "canonical_record_fingerprints": canonical_record_fingerprints,
        "canonical_buffer_layout": canonical_buffer_layout,
        "canonical_buffer_fingerprints": canonical_buffer_fingerprints,
    }
    report["canonical_structure_sha256"] = _sha256(
        json.dumps(
            {
                "record_types": report["record_types"],
                "records": canonical_record_fingerprints,
                "buffer_layout": canonical_buffer_layout,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    report["canonical_contract_sha256"] = _sha256(
        json.dumps(
            {
                "record_types": report["record_types"],
                "records": canonical_record_fingerprints,
                "buffers": canonical_buffer_fingerprints,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return report


def compare_reports(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Compare two captures while separating normalized structure from volatility."""
    structure_keys = (
        "record_types",
        "canonical_record_fingerprints",
        "canonical_buffer_layout",
        "canonical_structure_sha256",
    )
    stable = {key: baseline.get(key) == candidate.get(key) for key in structure_keys}
    opaque_payloads_equal = baseline.get(
        "canonical_buffer_fingerprints"
    ) == candidate.get("canonical_buffer_fingerprints")
    volatile = {
        "source_path_hash_changed": baseline.get("source", {}).get(
            "redacted_path_sha256"
        )
        != candidate.get("source", {}).get("redacted_path_sha256"),
        "raw_uuid_identity_changed": baseline.get("identity", {}).get(
            "uuid_definition_set_sha256"
        )
        != candidate.get("identity", {}).get("uuid_definition_set_sha256"),
        "raw_uuid_counts_changed": baseline.get("counts", {}).get("uuid_definitions")
        != candidate.get("counts", {}).get("uuid_definitions"),
    }
    return {
        "schema_version": 1,
        "contract": CONTRACT_NAME,
        "normalized_structure_equal": all(stable.values()),
        "opaque_payloads_equal": opaque_payloads_equal,
        "stable_checks": stable,
        "volatile_observations": volatile,
    }
