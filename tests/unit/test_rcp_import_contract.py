from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts._lib.rcp_import_contract import (
    ContractError,
    build_report,
    compare_reports,
    inspect_import,
)
from scripts.inspect_rcp_import import _unwrap_report

UUIDS = iter(f"00000000-0000-0000-0000-{number:012d}" for number in range(1, 1000))


def _uuid() -> str:
    return next(UUIDS)


def _record(path: Path, record_type: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'__type: "{record_type}"\n__uuid: "{_uuid()}"\n{body}',
        encoding="utf-8",
    )


def _directory(path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _record(
        path / "__tm_directory.tm_dir",
        "tm_asset_directory",
        f'name: "{name}"\nparent: "{_uuid()}"\n',
    )


def _fixture(tmp_path: Path, profile: str) -> Path:
    root = tmp_path / f"{profile}.import"
    _directory(root, root.name)
    for directory in ("geometry", "mesh_descriptors", "meshes"):
        _directory(root / directory, directory)
    _record(
        root / "settings.tm_usd",
        "tm_usd_asset",
        'source_path: "/controlled/source.usda"\n'
        "settings: [\n]\npro_settings: [\n]\nvariants: [\n]\n"
        f'__asset_uuid: "{_uuid()}"\n',
    )
    _record(
        root / "Scene.tm_entity",
        "tm_entity",
        f'name: "/"\ncomponents: [\n]\nchildren: [\n]\n__asset_uuid: "{_uuid()}"\n',
    )
    _record(
        root / "geometry" / "Mesh.tm_geometry",
        "tm_geometry",
        'name: "Mesh"\ninput_geometry: {\n}\ntransform_settings: {\n}\n'
        "output_geometry: {\n}\n"
        f'__asset_uuid: "{_uuid()}"\n',
    )
    _record(
        root / "mesh_descriptors" / "Mesh.tm_mesh_descriptor",
        "tm_mesh_descriptor",
        f'vertex_count: 3\nattributes: [\n]\n__asset_uuid: "{_uuid()}"\n',
    )
    _record(
        root / "meshes" / "Mesh.tm_mesh_resource",
        "tm_mesh_resource",
        f'models: [\n]\n__asset_uuid: "{_uuid()}"\n',
    )
    buffer_dir = root / "geometry" / "Mesh.tm_buffers"
    buffer_dir.mkdir()
    (buffer_dir / f"{_uuid()}.0123456789abcde").write_bytes(b"opaque")

    if profile in {"transform", "skeletal"}:
        _directory(root / "animations", "animations")
        _record(
            root / "animations" / "transform.tm_animation",
            "tm_timeline",
            'name: "transform"\ntype: 1\nproperties: {\n}\n'
            f'__asset_uuid: "{_uuid()}"\n',
        )
    if profile == "skeletal":
        _directory(root / "skeletons", "skeletons")
        _record(
            root / "animations" / "skeletal.tm_animation",
            "tm_timeline",
            'name: "skeletal"\ntype: 1\nproperties: {\n}\n'
            f'__asset_uuid: "{_uuid()}"\n',
        )
        _record(
            root / "skeletons" / "root.tm_skeleton_definition",
            "tm_skeleton_definition",
            f'__asset_uuid: "{_uuid()}"\n',
        )
        _record(
            root / "skeletons" / "root.tm_skeleton_hierarchy",
            "tm_skeleton_hierarchy",
            f'name: "root"\njoints: [\n]\n__asset_uuid: "{_uuid()}"\n',
        )
    return root


@pytest.mark.parametrize("profile", ("static", "transform", "skeletal"))
def test_controlled_profiles_pass(profile: str, tmp_path: Path) -> None:
    inspection = inspect_import(_fixture(tmp_path, profile), expected_profile=profile)
    report = build_report(
        inspection,
        expected_profile=profile,
        rcp_version="3.0",
        rcp_build="80.0.1.500.1",
    )

    assert report["expected_profile"] == profile
    assert report["record_types"]["tm_usd_asset"] == 1
    assert report["counts"]["opaque_buffers"] == 1
    if profile == "skeletal":
        assert report["record_types"]["tm_timeline"] == 2


def test_unknown_top_level_field_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "static")
    entity = root / "Scene.tm_entity"
    entity.write_text(entity.read_text() + "future_field: true\n", encoding="utf-8")

    with pytest.raises(ContractError, match="unsupported top-level fields"):
        build_report(inspect_import(root, expected_profile="static"))


def test_missing_asset_uuid_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "skeletal")
    hierarchy = root / "skeletons" / "root.tm_skeleton_hierarchy"
    lines = [
        line
        for line in hierarchy.read_text().splitlines()
        if not line.startswith("__asset_uuid:")
    ]
    hierarchy.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ContractError, match="missing required top-level fields"):
        build_report(inspect_import(root, expected_profile="skeletal"))


def test_unknown_record_suffix_fails_closed(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "static")
    (root / "future.tm_magic").write_text("opaque", encoding="utf-8")

    with pytest.raises(ContractError, match="unsupported record suffix"):
        build_report(inspect_import(root, expected_profile="static"))


def test_observed_texture_record_is_accepted(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "skeletal")
    _directory(root / "textures", "textures")
    _record(
        root / "textures" / "texture.tm_texture",
        "tm_texture",
        'source_filename: "../sources/textures/texture.png"\n'
        f'source_texture: "{_uuid()}"\n'
        'transform: "6b5fd8e4eec2cf5b"\n'
        "transform_settings: {\n}\n"
        "color_space: {\n}\n"
        f'__asset_uuid: "{_uuid()}"\n'
        "__asset_labels: [\n]\n"
        "__asset_thumbnail: {\n}\n",
    )

    report = build_report(inspect_import(root, expected_profile="skeletal"))

    assert report["record_types"]["tm_texture"] == 1


def test_rcp_authored_skeleton_match_result_is_accepted(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "skeletal")
    definition = root / "skeletons" / "root.tm_skeleton_definition"
    definition.write_text(
        definition.read_text().replace(
            "__asset_uuid:",
            'matched_skeleton_hierarchies: [\n'
            f'\t"{_uuid()}"\n'
            "]\n"
            "__asset_uuid:",
        ),
        encoding="utf-8",
    )

    report = build_report(inspect_import(root, expected_profile="skeletal"))

    assert report["record_types"]["tm_skeleton_definition"] == 1


def test_rcp_authored_mesh_subsets_are_accepted(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "skeletal")
    descriptor = root / "mesh_descriptors" / "Mesh.tm_mesh_descriptor"
    descriptor.write_text(
        descriptor.read_text().replace(
            "attributes:",
            "subsets: [\n"
            "\t{\n"
            f'\t\t__uuid: "{_uuid()}"\n'
            '\t\tname: "/root/Mesh/Material"\n'
            f'\t\tface_indices: "{_uuid()}"\n'
            "\t\tface_count: 1\n"
            "\t}\n"
            "]\n"
            "attributes:",
        ),
        encoding="utf-8",
    )

    report = build_report(inspect_import(root, expected_profile="skeletal"))

    assert report["record_types"]["tm_mesh_descriptor"] == 1


def test_static_profile_rejects_timeline(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "transform")

    with pytest.raises(ContractError, match="static profile unexpectedly contains"):
        build_report(inspect_import(root, expected_profile="static"))


def test_project_relative_source_path_is_resolved_inside_workspace(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    root = _fixture(project, "static")
    source = tmp_path / "sources" / "source.usda"
    source.parent.mkdir()
    source.write_text("#usda 1.0\n", encoding="utf-8")
    settings = root / "settings.tm_usd"
    settings.write_text(
        settings.read_text().replace(
            "/controlled/source.usda", "../sources/source.usda"
        ),
        encoding="utf-8",
    )

    inspection = inspect_import(root)
    report = build_report(inspection)

    assert inspection.resolved_source_path == source
    assert report["source"]["path_kind"] == "project-relative"
    assert report["source"]["exists"]


def test_relative_source_path_cannot_escape_workspace(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "static")
    settings = root / "settings.tm_usd"
    settings.write_text(
        settings.read_text().replace(
            "/controlled/source.usda", "../../../../outside.usda"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="escapes the project workspace"):
        build_report(inspect_import(root))


def test_comparison_ignores_uuid_and_absolute_source_path_churn(tmp_path: Path) -> None:
    first = build_report(inspect_import(_fixture(tmp_path / "a", "static")))
    second_root = _fixture(tmp_path / "b", "static")
    settings = second_root / "settings.tm_usd"
    settings.write_text(
        settings.read_text().replace("/controlled/source.usda", "/other/source.usda"),
        encoding="utf-8",
    )
    second = build_report(inspect_import(second_root))

    comparison = compare_reports(first, second)

    assert comparison["normalized_structure_equal"]
    assert comparison["opaque_payloads_equal"]
    assert comparison["volatile_observations"]["source_path_hash_changed"]
    assert comparison["volatile_observations"]["raw_uuid_identity_changed"]


def test_comparison_separates_opaque_payload_churn_from_layout(tmp_path: Path) -> None:
    first_root = _fixture(tmp_path / "a", "static")
    first = build_report(inspect_import(first_root))
    second_root = _fixture(tmp_path / "b", "static")
    buffer = next(second_root.rglob("*.tm_buffers/*"))
    buffer.write_bytes(b"change")
    second = build_report(inspect_import(second_root))

    comparison = compare_reports(first, second)

    assert comparison["normalized_structure_equal"]
    assert not comparison["opaque_payloads_equal"]


def test_comparison_input_unwraps_prior_comparison_envelope(tmp_path: Path) -> None:
    report = build_report(inspect_import(_fixture(tmp_path, "static")))

    assert _unwrap_report(report) is report
    assert _unwrap_report({"report": report, "comparison": {}}) is report
    with pytest.raises(ContractError, match="must contain a JSON object"):
        _unwrap_report([])
    with pytest.raises(ContractError, match="report must contain a JSON object"):
        _unwrap_report({"report": []})


def test_real_rcp_corpus_when_available() -> None:
    corpus_path = Path(__file__).parents[1] / "fixtures" / "rcp_import" / "corpus.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    environment = corpus["fixture_root_environment"]
    fixture_root_value = os.environ.get(environment)
    if not fixture_root_value:
        pytest.skip(f"set {environment} to run RCP-generated golden corpus")
    fixture_root = Path(fixture_root_value)

    for fixture in corpus["fixtures"]:
        inspection = inspect_import(
            fixture_root / fixture["relative_path"],
            expected_profile=fixture["profile"],
        )
        report = build_report(inspection, expected_profile=fixture["profile"])
        source_path = Path(inspection.source_path or "")
        source_data = source_path.read_bytes()
        assert report["record_types"] == fixture["expected_record_types"]
        assert report["counts"]["opaque_buffers"] == fixture["expected_opaque_buffers"]
        assert source_path.name == fixture["source_asset"]["name"]
        assert len(source_data) == fixture["source_asset"]["byte_count"]
        assert (
            hashlib.sha256(source_data).hexdigest() == fixture["source_asset"]["sha256"]
        )
        assert report["counts"]["record_bytes"] == fixture["captured"]["record_bytes"]
        assert (
            report["counts"]["opaque_buffer_bytes"]
            == fixture["captured"]["opaque_buffer_bytes"]
        )
        assert (
            report["canonical_contract_sha256"]
            == fixture["captured"]["canonical_contract_sha256"]
        )
