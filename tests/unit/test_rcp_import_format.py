from __future__ import annotations

import pytest

from scripts._lib.rcp_import_format import (
    Field,
    ImportFormatError,
    ListValue,
    ObjectValue,
    buffer_content_hash,
    murmur_hash64a,
    parse_record,
    render_record,
)


def test_murmur_hash_matches_rcp_build_80_buffer_suffixes() -> None:
    face_counts = bytes.fromhex(
        "04000000 04000000 04000000 04000000 04000000 04000000"
    )
    face_indices = bytes.fromhex(
        "00000000 04000000 06000000 02000000 03000000 02000000 "
        "06000000 07000000 07000000 06000000 04000000 05000000 "
        "05000000 01000000 03000000 07000000 01000000 00000000 "
        "02000000 03000000 05000000 04000000 00000000 01000000"
    )

    assert buffer_content_hash(face_counts) == "23a5bc0bce0ff040"
    assert buffer_content_hash(face_indices) == "c59cd85f45ff481c"
    assert murmur_hash64a(b"") == 0
    assert int("1928501b5ca5c10", 16) == int("01928501b5ca5c10", 16)


def test_parse_and_render_measured_record_shape() -> None:
    text = (
        '__type: "tm_mesh_resource"\n'
        '__uuid: "00000000-0000-0000-0000-000000000001"\n'
        "models: [\n"
        "\t{\n"
        '\t\t__uuid: "00000000-0000-0000-0000-000000000002"\n'
        '\t\tname: "Cube"\n'
        '\t\tgeometry: "00000000-0000-0000-0000-000000000003"\n'
        "\t\tbounds_min: {\n"
        '\t\t\t__uuid: "00000000-0000-0000-0000-000000000004"\n'
        "\t\t\tx: -1\n"
        "\t\t\ty: -1.5\n"
        "\t\t\tz: -1\n"
        "\t\t}\n"
        "\t}\n"
        "]\n"
        '__asset_uuid: "00000000-0000-0000-0000-000000000005"\n'
    )

    record = parse_record(text)

    assert record.require_one("__type") == "tm_mesh_resource"
    models = record.require_one("models")
    assert isinstance(models, ListValue)
    assert render_record(record) == text


def test_renderer_preserves_duplicate_fields_and_escapes_strings() -> None:
    record = ObjectValue(
        (
            Field("name", 'A "quoted" name'),
            Field("value", 1),
            Field("value", 2),
            Field("enabled", True),
            Field("settings", ObjectValue(())),
            Field("items", ListValue(())),
            Field("skeleton hierarchy", "00000000-0000-0000-0000-000000000003"),
        )
    )

    rendered = render_record(record)
    reparsed = parse_record(rendered)

    assert reparsed.values("value") == (1, 2)
    assert reparsed.require_one("name") == 'A "quoted" name'
    assert reparsed.require_one("enabled") is True
    assert (
        reparsed.require_one("skeleton hierarchy")
        == "00000000-0000-0000-0000-000000000003"
    )


@pytest.mark.parametrize(
    "text",
    (
        "field: future_token\n",
        'field: "unterminated\n',
        "field: [\n",
        "field = 1\n",
        "field: 1, 2\n",
    ),
)
def test_parser_fails_closed_on_unmeasured_syntax(text: str) -> None:
    with pytest.raises(ImportFormatError):
        parse_record(text)
