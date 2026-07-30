"""Cross-validate our .import knowledge against RCP's own shipped schema.

The app ships the complete Truth-type schema as plain ASCII
(``__type_index.tm_meta``, 963 types on build 80.0.1.500.1) — the
authoritative form of the contract this repo previously reverse-measured from
sample packages. These tests hold three artifacts to it:

* the structural inspector's record/field tables (rcp_import_contract),
* every ``__type`` the generator writes,
* the murmur64a(type name) hashing rule all cross-references rely on.

They are pinned to the locally installed app and skip when it is absent, so
they double as the per-build regression check: after an RCP update, a failure
here is the earliest possible signal that the format moved.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts._lib.rcp_import_contract import (
    RECORD_SUFFIX_TYPES,
    TOP_LEVEL_FIELDS,
)
from scripts._lib.rcp_import_format import murmur_hash64a
from scripts._lib.rcp_type_index import (
    ANYTHING_TYPE_HASH,
    DEFAULT_TYPE_INDEX_PATH,
    load_type_index,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not DEFAULT_TYPE_INDEX_PATH.exists(),
    reason="RealityComposerPro.app type index not installed",
)


@pytest.fixture(scope="module")
def type_index():
    return load_type_index()


def test_the_index_parses_completely(type_index):
    # 963 on build 80.0.1.500.1; a different count on a future build is not
    # an error, but a collapse below the known baseline means the parse broke.
    assert len(type_index) >= 900


def test_every_contracted_record_type_is_a_real_truth_type(type_index):
    contracted = set().union(*RECORD_SUFFIX_TYPES.values())
    missing = sorted(name for name in contracted if name not in type_index)
    assert missing == []


def test_every_contracted_field_is_a_schema_property(type_index):
    """The inspector's field tables may bound the schema (fields we accept)
    but must never invent a property the app does not declare. Serializer
    dunders (__type, __uuid, __asset_uuid, ...) are file-format tokens owned
    by the serializer, not schema properties."""
    problems = []
    for record_type, fields in TOP_LEVEL_FIELDS.items():
        schema = type_index[record_type]
        for field_name in sorted(fields):
            if field_name.startswith("__"):
                continue
            if field_name not in schema.properties:
                problems.append(f"{record_type}.{field_name}")
    assert problems == []


def test_every_generator_written_type_is_a_real_truth_type(type_index):
    source = (REPO_ROOT / "Plugin" / "export" / "rcp_import_generator.py").read_text()
    written = sorted(set(re.findall(r'__type: "([A-Za-z_][A-Za-z0-9_]*)"', source)))
    assert written, "no __type emissions found in the generator"
    missing = [name for name in written if name not in type_index]
    assert missing == []


def test_type_hashes_are_murmur64a_of_the_type_name(type_index):
    """Every subobject/reference target hash in the index must be
    murmur64a(name, seed 0) of a declared type; the single legal nonmember is
    the engine's wildcard, murmur64a("tm_anything")."""
    declared = {
        f"{murmur_hash64a(name.encode('utf-8')):016x}" for name in type_index
    }
    assert f"{murmur_hash64a(b'tm_anything'):016x}" == ANYTHING_TYPE_HASH

    referenced = set()
    for truth_type in type_index.values():
        for prop in truth_type.properties.values():
            target = prop.get("type_hash")
            if isinstance(target, str):
                referenced.add(target)
    unresolved = referenced - declared - {ANYTHING_TYPE_HASH}
    assert unresolved == set()


def test_members_sort_values_is_a_legal_timeline_group_property(type_index):
    """The generator emits members_sort_values inside tm_timeline_clip's
    source_group; RCP's own files omit it. The schema settles the question:
    it is a declared subobject_set of tm_double on tm_timeline_group."""
    group = type_index["tm_timeline_group"]
    assert group.property_kind("members_sort_values") == "subobject_set"
    double_hash = f"{murmur_hash64a(b'tm_double'):016x}"
    assert group.property_target_hash("members_sort_values") == double_hash

    clip = type_index["tm_timeline_clip"]
    group_hash = f"{murmur_hash64a(b'tm_timeline_group'):016x}"
    assert clip.property_target_hash("source_group") == group_hash


def test_canonical_multi_material_descriptor_schema(type_index):
    """The canonical multi-material form RCP normalizes reimports into.
    Pinned here as the writer specification for emitting subsets and
    material_bindings directly."""
    descriptor = type_index["tm_mesh_descriptor"]
    assert descriptor.property_kind("subsets") == "subobject_set"
    # Singular: ONE binding object per descriptor, whose buffer maps subset
    # index -> material index. Not a set of per-subset bindings.
    assert descriptor.property_kind("material_bindings") == "subobject"
    assert descriptor.property_kind("winding_order") == "uint32_t"

    subset = type_index["tm_mesh_descriptor_subset"]
    assert set(subset.properties) == {"name", "index", "face_indices", "face_count"}
    assert subset.property_kind("face_indices") == "buffer"
    assert subset.property_kind("index") == "uint32_t"

    binding = type_index["tm_mesh_descriptor_material_binding"]
    assert set(binding.properties) == {
        "mesh_material_index",
        "subset_to_material_index",
        "subset_count",
    }
    assert binding.property_kind("subset_to_material_index") == "buffer"
