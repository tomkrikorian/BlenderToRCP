from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.hybridize_rcp_import import (
    HybridizationError,
    build_identity_mapping,
    create_hybrid_import,
    record_group,
)


def _record(identity: str, asset_identity: str, *, name: str) -> str:
    return (
        '__type: "tm_entity"\n'
        f'__uuid: "{identity}"\n'
        f'name: "{name}"\n'
        "components: [\n"
        "\t{\n"
        '\t\t__type: "tm_transform_component"\n'
        f'\t\t__uuid: "{asset_identity}"\n'
        "\t}\n"
        "]\n"
        f'__asset_uuid: "{asset_identity}"'
    )


def _artifact(
    root: Path,
    *,
    identity: str,
    asset_identity: str,
    buffer_identity: str,
) -> Path:
    root.mkdir()
    (root / "Thing.tm_entity").write_text(
        _record(identity, asset_identity, name="Thing"),
        encoding="utf-8",
    )
    buffers = root / "__Thing.tm_buffers"
    buffers.mkdir()
    (buffers / f"{buffer_identity}.0123456789abcdef").write_bytes(b"same payload")
    return root


def _timeline(identity: str, asset_identity: str, *, name: str) -> str:
    return (
        '__type: "tm_timeline"\n'
        f'__uuid: "{identity}"\n'
        f'name: "{name}"\n'
        "type: 1\n"
        "properties: {\n"
        f'\t__uuid: "{asset_identity}"\n'
        "}\n"
        f'__asset_uuid: "{asset_identity}"'
    )


def test_record_group_partitions_known_artifact_paths() -> None:
    assert record_group(Path("settings.tm_usd")) == "settings"
    assert record_group(Path("settings.tm_buffers/id.hash")) == "settings"
    assert record_group(Path("Thing.tm_entity")) == "entities"
    assert record_group(Path("__Thing.tm_buffers/id.hash")) == "entities"
    assert record_group(Path("geometry/Thing.tm_geometry")) == "geometry"
    assert record_group(Path("skeletons/root.tm_skeleton_hierarchy")) == "skeleton"
    assert record_group(Path("animations/Clip.tm_animation")) == "animations"
    assert record_group(Path("materials/Thing.tm_material")) == "materials"
    assert record_group(Path("geometry/__tm_directory.tm_dir")) == "directories"

    with pytest.raises(HybridizationError, match="unsupported artifact path"):
        record_group(Path("unknown.bin"))


def test_identity_mapping_uses_definition_paths_and_equal_buffer_payloads(
    tmp_path: Path,
) -> None:
    baseline = _artifact(
        tmp_path / "Baseline.import",
        identity="00000000-0000-0000-0000-000000000001",
        asset_identity="00000000-0000-0000-0000-000000000002",
        buffer_identity="00000000-0000-0000-0000-000000000003",
    )
    generated = _artifact(
        tmp_path / "Generated.import",
        identity="10000000-0000-0000-0000-000000000001",
        asset_identity="10000000-0000-0000-0000-000000000002",
        buffer_identity="10000000-0000-0000-0000-000000000003",
    )

    mapping, matched_buffers = build_identity_mapping(baseline, generated)

    assert mapping == {
        "10000000-0000-0000-0000-000000000001": (
            "00000000-0000-0000-0000-000000000001"
        ),
        "10000000-0000-0000-0000-000000000002": (
            "00000000-0000-0000-0000-000000000002"
        ),
        "10000000-0000-0000-0000-000000000003": (
            "00000000-0000-0000-0000-000000000003"
        ),
    }
    assert matched_buffers == 1


def test_create_hybrid_refuses_overwrite(tmp_path: Path) -> None:
    baseline = _artifact(
        tmp_path / "Baseline.import",
        identity="00000000-0000-0000-0000-000000000001",
        asset_identity="00000000-0000-0000-0000-000000000002",
        buffer_identity="00000000-0000-0000-0000-000000000003",
    )
    generated = _artifact(
        tmp_path / "Generated.import",
        identity="10000000-0000-0000-0000-000000000001",
        asset_identity="10000000-0000-0000-0000-000000000002",
        buffer_identity="10000000-0000-0000-0000-000000000003",
    )
    destination = tmp_path / "Hybrid.import"
    destination.mkdir()

    with pytest.raises(FileExistsError):
        create_hybrid_import(
            baseline,
            generated,
            destination,
            generated_groups=("entities",),
        )


def test_manifest_stays_adjacent_to_import_package(tmp_path: Path, monkeypatch) -> None:
    baseline = _artifact(
        tmp_path / "Baseline.import",
        identity="00000000-0000-0000-0000-000000000001",
        asset_identity="00000000-0000-0000-0000-000000000002",
        buffer_identity="00000000-0000-0000-0000-000000000003",
    )
    generated = _artifact(
        tmp_path / "Generated.import",
        identity="10000000-0000-0000-0000-000000000001",
        asset_identity="10000000-0000-0000-0000-000000000002",
        buffer_identity="10000000-0000-0000-0000-000000000003",
    )
    destination = tmp_path / "Hybrid.import"

    class _Inspection:
        records = (object(),)
        buffers = (object(),)

        def require_valid(self) -> None:
            return None

    monkeypatch.setattr(
        "scripts.hybridize_rcp_import.inspect_import",
        lambda *_args, **_kwargs: _Inspection(),
    )
    manifest = create_hybrid_import(
        baseline,
        generated,
        destination,
        generated_groups=("entities",),
    )

    assert not (destination / "hybrid-manifest.json").exists()
    manifest_path = tmp_path / "Hybrid.import.hybrid.json"
    assert json.loads(manifest_path.read_text()) == manifest
    text = (destination / "Thing.tm_entity").read_text()
    assert "10000000-0000-0000-0000-000000000001" not in text
    assert "00000000-0000-0000-0000-000000000001" in text
    assert (
        destination
        / "__Thing.tm_buffers"
        / "00000000-0000-0000-0000-000000000003.0123456789abcdef"
    ).is_file()


def test_hybrid_rejects_new_dangling_cross_group_reference(
    tmp_path: Path,
) -> None:
    baseline = _artifact(
        tmp_path / "Baseline.import",
        identity="00000000-0000-0000-0000-000000000001",
        asset_identity="00000000-0000-0000-0000-000000000002",
        buffer_identity="00000000-0000-0000-0000-000000000003",
    )
    generated = _artifact(
        tmp_path / "Generated.import",
        identity="10000000-0000-0000-0000-000000000001",
        asset_identity="10000000-0000-0000-0000-000000000002",
        buffer_identity="10000000-0000-0000-0000-000000000003",
    )
    baseline_animation = baseline / "animations"
    baseline_animation.mkdir()
    (baseline_animation / "Base.tm_animation").write_text(
        _timeline(
            "00000000-0000-0000-0000-000000000010",
            "00000000-0000-0000-0000-000000000011",
            name="Base",
        ),
        encoding="utf-8",
    )
    generated_animation = generated / "animations"
    generated_animation.mkdir()
    (generated_animation / "New.tm_animation").write_text(
        _timeline(
            "10000000-0000-0000-0000-000000000010",
            "10000000-0000-0000-0000-000000000011",
            name="New",
        ),
        encoding="utf-8",
    )
    baseline_entity = baseline / "Thing.tm_entity"
    generated_entity = generated / "Thing.tm_entity"
    baseline_entity.write_text(
        baseline_entity.read_text()
        + '\nsource_timeline: "00000000-0000-0000-0000-000000000010"',
        encoding="utf-8",
    )
    generated_entity.write_text(
        generated_entity.read_text()
        + '\nsource_timeline: "10000000-0000-0000-0000-000000000010"',
        encoding="utf-8",
    )
    destination = tmp_path / "Hybrid.import"

    with pytest.raises(
        HybridizationError, match="introduces dangling UUID references"
    ):
        create_hybrid_import(
            baseline,
            generated,
            destination,
            generated_groups=("animations",),
        )

    assert not destination.exists()
