"""Asset preflight helper tests."""

from __future__ import annotations

from types import SimpleNamespace

from Plugin.export.asset_preflight import collect_missing_image_files_for_objects


class _FakePath:
    @staticmethod
    def abspath(path, library=None):
        return str(path).replace("//", "/project/")


def test_collect_missing_image_files_finds_nested_node_group_image(tmp_path):
    existing = tmp_path / "ok.png"
    existing.write_bytes(b"png")
    missing = tmp_path / "missing.png"

    image_ok = SimpleNamespace(
        name="Existing",
        filepath=str(existing),
        filepath_raw=str(existing),
        source="FILE",
        packed_file=None,
        packed_files=[],
        library=None,
    )
    image_missing = SimpleNamespace(
        name="Missing",
        filepath=str(missing),
        filepath_raw=str(missing),
        source="FILE",
        packed_file=None,
        packed_files=[],
        library=None,
    )
    group_tree = SimpleNamespace(nodes=[
        SimpleNamespace(type="TEX_IMAGE", image=image_missing, name="Nested Image"),
    ])
    root_tree = SimpleNamespace(nodes=[
        SimpleNamespace(type="TEX_IMAGE", image=image_ok, name="Root Image"),
        SimpleNamespace(type="GROUP", node_tree=group_tree, name="Group"),
    ])
    material = SimpleNamespace(name="Material", use_nodes=True, node_tree=root_tree)
    obj = SimpleNamespace(name="Object", material_slots=[SimpleNamespace(material=material)])

    result = collect_missing_image_files_for_objects([obj], SimpleNamespace(path=_FakePath()))

    assert len(result) == 1
    assert result[0]["image"] == "Missing"
    assert result[0]["users"] == [{"object": "Object", "material": "Material", "node": "Nested Image"}]
