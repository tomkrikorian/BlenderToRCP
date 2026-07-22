"""Unit tests for USD sidecar asset staging helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.export import usd_assets, usd_textures


class _FakeAssetPath:
    def __init__(self, path: str):
        self.path = path
        self.resolvedPath = path


class _FakeValueTypeNames:
    Asset = "asset"


class _FakeSdf:
    AssetPath = _FakeAssetPath
    ValueTypeNames = _FakeValueTypeNames


class _FakeAttr:
    def __init__(self, value: str):
        self._value = _FakeAssetPath(value)
        self.set_value = None

    def GetTypeName(self):
        return _FakeSdf.ValueTypeNames.Asset

    def Get(self):
        return self._value

    def Set(self, value):
        self.set_value = value

    def GetPath(self):
        return "/Fake.attr"


class _FakePrim:
    def __init__(self, attrs):
        self._attrs = attrs

    def GetAttributes(self):
        return self._attrs


class _FakeStage:
    def __init__(self, attrs):
        self._attrs = attrs

    def Traverse(self):
        return [_FakePrim(self._attrs)]


def test_prepare_assets_does_not_create_empty_assets_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_assets, "Sdf", _FakeSdf)

    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    stage = _FakeStage([])

    usd_assets.prepare_assets(stage, str(usd_path))

    assert not (tmp_path / "assets").exists()


def test_prepare_textures_reuses_identical_source_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)

    source_a = tmp_path / "a" / "texture.png"
    source_b = tmp_path / "b" / "texture.png"
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    source_a.write_bytes(b"same texture bytes")
    source_b.write_bytes(b"same texture bytes")

    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr_a = _FakeAttr(str(source_a))
    attr_b = _FakeAttr(str(source_b))
    stage = _FakeStage([attr_a, attr_b])
    settings = SimpleNamespace(export_texture_settings_enabled=False)

    usd_textures.prepare_textures(stage, str(usd_path), settings)

    texture_files = sorted((tmp_path / "textures").iterdir())
    assert [path.name for path in texture_files] == ["scene-texture.png"]
    assert attr_a.set_value.path == "textures/scene-texture.png"
    assert attr_b.set_value.path == "textures/scene-texture.png"


def test_prepare_textures_prefixes_names_with_export_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)

    source = tmp_path / "extracted_image_0.jpg"
    source.write_bytes(b"source bytes")

    usd_path = tmp_path / "badge-streak-7.usdc"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source))
    stage = _FakeStage([attr])
    settings = SimpleNamespace(export_texture_settings_enabled=False)

    usd_textures.prepare_textures(stage, str(usd_path), settings)

    texture = tmp_path / "textures" / "badge-streak-7-extracted_image_0.jpg"
    assert texture.read_bytes() == b"source bytes"
    assert attr.set_value.path == "textures/badge-streak-7-extracted_image_0.jpg"


def test_prepare_textures_keeps_prefixed_names_collision_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)

    source_a = tmp_path / "a" / "shared.png"
    source_b = tmp_path / "b" / "shared.png"
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    source_a.write_bytes(b"source a")
    source_b.write_bytes(b"source b")

    usd_path = tmp_path / "badge-streak-7.usdc"
    usd_path.write_text("#usda 1.0\n")
    attr_a = _FakeAttr(str(source_a))
    attr_b = _FakeAttr(str(source_b))
    stage = _FakeStage([attr_a, attr_b])
    settings = SimpleNamespace(export_texture_settings_enabled=False)

    usd_textures.prepare_textures(stage, str(usd_path), settings)

    texture_files = sorted(path.name for path in (tmp_path / "textures").iterdir())
    assert len(texture_files) == 2
    assert texture_files[0] == "badge-streak-7-shared.png"
    assert texture_files[1].startswith("badge-streak-7-shared_")
    assert texture_files[1].endswith(".png")
    assert attr_a.set_value.path == f"textures/{texture_files[0]}"
    assert attr_b.set_value.path == f"textures/{texture_files[1]}"


def test_avif_texture_conversion_uses_imbuf(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    dest = tmp_path / "source.avif"
    source.write_bytes(b"source bytes")

    class _FakeIbuf:
        def __init__(self):
            self.size = (64, 64)
            self.quality = 0
            self.file_type = ""
            self.freed = False

        def resize(self, size, method="FAST"):
            assert method == "BILINEAR"
            self.size = tuple(size)

        def free(self):
            self.freed = True

    fake_ibuf = _FakeIbuf()
    loads = []

    def fake_load(filepath):
        loads.append(filepath)
        return fake_ibuf

    def fake_write(ibuf, *, filepath=None):
        assert ibuf is fake_ibuf
        Path(filepath).write_bytes(b"converted bytes")

    monkeypatch.setitem(sys.modules, "imbuf", SimpleNamespace(load=fake_load, write=fake_write))

    converted = usd_textures._convert_texture(
        source,
        dest,
        {
            "file_format": "AVIF",
            "extension": ".avif",
            "resolution": 32,
        },
    )

    assert converted is True
    assert dest.read_bytes() == b"converted bytes"
    assert loads == [str(source)]
    assert fake_ibuf.size == (32, 32)
    assert fake_ibuf.file_type == "AVIF"
    assert fake_ibuf.quality == usd_textures._LOSSY_TEXTURE_QUALITY
    assert fake_ibuf.freed is True


def test_avif_texture_conversion_falls_back_to_image_datablock(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    dest = tmp_path / "source.avif"
    source.write_bytes(b"source bytes")

    def failing_load(_filepath):
        raise RuntimeError("imbuf cannot read this file")

    monkeypatch.setitem(sys.modules, "imbuf", SimpleNamespace(load=failing_load, write=None))

    class _FakeImage:
        def __init__(self):
            self.size = [64, 64]
            self.users = 0
            self.filepath_raw = ""
            self.file_format = ""

        def scale(self, width, height):
            self.size = [width, height]

        def save(self):
            assert self.file_format == "AVIF"
            Path(self.filepath_raw).write_bytes(b"datablock avif")

    class _FakeImages:
        def load(self, *_args, **_kwargs):
            return _FakeImage()

        def remove(self, _image):
            pass

    fake_bpy = SimpleNamespace(
        app=SimpleNamespace(background=False),
        data=SimpleNamespace(images=_FakeImages()),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)

    converted = usd_textures._convert_texture(
        source,
        dest,
        {
            "file_format": "AVIF",
            "extension": ".avif",
            "resolution": 32,
        },
    )

    assert converted is True
    assert dest.read_bytes() == b"datablock avif"


def test_prepare_textures_writes_resized_png_when_avif_saving_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)

    source = tmp_path / "source.png"
    source.write_bytes(b"source bytes")
    saved_sizes = []

    class _FakeImage:
        def __init__(self):
            self.size = [128, 64]
            self.users = 0
            self.filepath_raw = ""
            self.file_format = ""

        def scale(self, width, height):
            self.size = [width, height]
            saved_sizes.append((width, height))

        def save(self):
            assert self.file_format == "PNG"
            Path(self.filepath_raw).write_bytes(b"resized png")

    class _FakeImages:
        def load(self, *_args, **_kwargs):
            return _FakeImage()

        def remove(self, _image):
            pass

    fake_bpy = SimpleNamespace(
        app=SimpleNamespace(background=False),
        data=SimpleNamespace(images=_FakeImages()),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)
    from Plugin.export import bake_textures

    monkeypatch.setattr(bake_textures, "bpy", fake_bpy, raising=False)

    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source))
    stage = _FakeStage([attr])
    settings = SimpleNamespace(
        export_texture_settings_enabled=True,
        bake_image_format="AVIF",
        bake_resolution="32",
        bake_resolution_custom=32,
    )

    usd_textures.prepare_textures(stage, str(usd_path), settings)

    fallback = tmp_path / "textures" / "scene-source.png"
    assert fallback.read_bytes() == b"resized png"
    # The failed AVIF attempt scales once before the PNG fallback scales again.
    assert saved_sizes[-1] == (32, 16)
    assert attr.set_value.path == "textures/scene-source.png"


def test_prepare_textures_original_format_and_resolution_copies_source(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)

    source = tmp_path / "photo.jpg"
    source.write_bytes(b"original jpg")

    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source))
    stage = _FakeStage([attr])
    settings = SimpleNamespace(
        export_texture_settings_enabled=True,
        bake_image_format="ORIGINAL",
        bake_resolution="ORIGINAL",
        bake_resolution_custom=32,
    )

    usd_textures.prepare_textures(stage, str(usd_path), settings)

    copied = tmp_path / "textures" / "scene-photo.jpg"
    assert copied.read_bytes() == b"original jpg"
    assert attr.set_value.path == "textures/scene-photo.jpg"


def test_prepare_textures_resizes_with_original_source_format(tmp_path, monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)

    source = tmp_path / "photo.jpg"
    source.write_bytes(b"source jpg")
    saved_sizes = []

    class _FakeImage:
        def __init__(self):
            self.size = [128, 64]
            self.users = 0
            self.filepath_raw = ""
            self.file_format = ""

        def scale(self, width, height):
            self.size = [width, height]
            saved_sizes.append((width, height))

        def save(self):
            assert self.file_format == "JPEG"
            Path(self.filepath_raw).write_bytes(b"resized jpg")

    class _FakeImages:
        def load(self, *_args, **_kwargs):
            return _FakeImage()

        def remove(self, _image):
            pass

    fake_bpy = SimpleNamespace(
        app=SimpleNamespace(background=False),
        data=SimpleNamespace(images=_FakeImages()),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)

    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source))
    stage = _FakeStage([attr])
    settings = SimpleNamespace(
        export_texture_settings_enabled=True,
        bake_image_format="ORIGINAL",
        bake_resolution="32",
        bake_resolution_custom=32,
    )

    usd_textures.prepare_textures(stage, str(usd_path), settings)

    resized = tmp_path / "textures" / "scene-photo.jpg"
    assert resized.read_bytes() == b"resized jpg"
    assert saved_sizes == [(32, 16)]
    assert attr.set_value.path == "textures/scene-photo.jpg"
