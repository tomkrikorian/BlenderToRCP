from __future__ import annotations

from pathlib import Path

import pytest

from scripts._lib.rcp_import_format import parse_record
from scripts.ablate_rcp_import import (
    strip_buffer_backed_cache,
    strip_geometry_processing_metadata,
)


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "source.import"
    root.mkdir()
    (root / "settings.tm_usd").write_text(
        '__type: "tm_usd_asset"\n'
        '__uuid: "00000000-0000-0000-0000-000000000001"\n'
        "settings: [\n"
        "\t{\n"
        '\t\t__type: "tm_scene_optimizer"\n'
        '\t\toutput: "00000000-0000-0000-0000-000000000002"\n'
        "\t}\n"
        "]\n"
        "variants: [\n"
        "\t{\n"
        '\t\tname: "Default"\n'
        '\t\tsession: "00000000-0000-0000-0000-000000000003"\n'
        "\t}\n"
        "]",
        encoding="utf-8",
    )
    buffers = root / "settings.tm_buffers"
    buffers.mkdir()
    (buffers / "00000000-0000-0000-0000-000000000002.hash").write_bytes(b"output")
    (buffers / "00000000-0000-0000-0000-000000000003.hash").write_bytes(b"session")
    return root


def test_strip_buffer_backed_cache_is_copy_only(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "candidate.import"

    strip_buffer_backed_cache(source, destination)

    original = parse_record((source / "settings.tm_usd").read_text(encoding="utf-8"))
    candidate = parse_record(
        (destination / "settings.tm_usd").read_text(encoding="utf-8")
    )
    assert "output" in {
        field.name
        for value in original.require_one("settings").values
        for field in value.fields
    }
    assert "output" not in {
        field.name
        for value in candidate.require_one("settings").values
        for field in value.fields
    }
    assert not (destination / "settings.tm_buffers").exists()
    assert (
        source
        / "settings.tm_buffers"
        / "00000000-0000-0000-0000-000000000002.hash"
    ).is_file()


def test_ablation_refuses_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "candidate.import"
    destination.mkdir()

    with pytest.raises(FileExistsError):
        strip_buffer_backed_cache(source, destination)


@pytest.mark.parametrize(
    ("strip_output", "strip_session", "remaining_field", "remaining_buffer"),
    [
        (True, False, "session", "00000000-0000-0000-0000-000000000003"),
        (False, True, "output", "00000000-0000-0000-0000-000000000002"),
    ],
)
def test_strip_single_cache_class(
    tmp_path: Path,
    strip_output: bool,
    strip_session: bool,
    remaining_field: str,
    remaining_buffer: str,
) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "candidate.import"

    strip_buffer_backed_cache(
        source,
        destination,
        strip_output=strip_output,
        strip_session=strip_session,
    )

    candidate = parse_record(
        (destination / "settings.tm_usd").read_text(encoding="utf-8")
    )
    all_fields = {
        field.name
        for list_name in ("settings", "variants")
        for value in candidate.require_one(list_name).values
        for field in value.fields
    }
    assert remaining_field in all_fields
    assert (destination / "settings.tm_buffers" / f"{remaining_buffer}.hash").is_file()


def test_strip_geometry_processing_metadata(tmp_path: Path) -> None:
    source = _source(tmp_path)
    geometry_dir = source / "geometry"
    geometry_dir.mkdir()
    (geometry_dir / "mesh.tm_geometry").write_text(
        '__type: "tm_geometry"\n'
        '__uuid: "00000000-0000-0000-0000-000000000004"\n'
        "input_geometry: {\n"
        '\t__uuid: "00000000-0000-0000-0000-000000000005"\n'
        "}\n"
        'transform: "3865a2eea51b6038"\n'
        "transform_settings: {\n"
        '\t__uuid: "00000000-0000-0000-0000-000000000006"\n'
        "}\n"
        "output_geometry: {\n"
        '\t__uuid: "00000000-0000-0000-0000-000000000007"\n'
        "}",
        encoding="utf-8",
    )
    destination = tmp_path / "candidate.import"

    strip_geometry_processing_metadata(source, destination)

    record = parse_record(
        (destination / "geometry" / "mesh.tm_geometry").read_text(encoding="utf-8")
    )
    names = {field.name for field in record.fields}
    assert "input_geometry" in names
    assert "transform" not in names
    assert "transform_settings" not in names
    assert "output_geometry" not in names


def test_strip_only_geometry_transform_metadata(tmp_path: Path) -> None:
    source = _source(tmp_path)
    geometry_dir = source / "geometry"
    geometry_dir.mkdir()
    (geometry_dir / "mesh.tm_geometry").write_text(
        '__type: "tm_geometry"\n'
        '__uuid: "00000000-0000-0000-0000-000000000004"\n'
        "input_geometry: {\n"
        '\t__uuid: "00000000-0000-0000-0000-000000000005"\n'
        "}\n"
        'transform: "3865a2eea51b6038"\n'
        "transform_settings: {\n"
        '\t__uuid: "00000000-0000-0000-0000-000000000006"\n'
        "}\n"
        "output_geometry: {\n"
        '\t__uuid: "00000000-0000-0000-0000-000000000007"\n'
        "}",
        encoding="utf-8",
    )
    destination = tmp_path / "candidate.import"

    strip_geometry_processing_metadata(
        source, destination, strip_transform=True, strip_output=False
    )

    record = parse_record(
        (destination / "geometry" / "mesh.tm_geometry").read_text(encoding="utf-8")
    )
    names = {field.name for field in record.fields}
    assert "input_geometry" in names
    assert "transform" not in names
    assert "transform_settings" not in names
    assert "output_geometry" in names
