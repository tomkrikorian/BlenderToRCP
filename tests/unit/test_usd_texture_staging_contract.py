"""Release-contract tests for USD texture dependency staging."""

from __future__ import annotations

import hashlib
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.export import usd_assets, usd_textures


def _texture_generation_dir(usd_path: Path) -> Path:
    return usd_path.parent / "textures" / usd_textures.output_sidecar_namespace(usd_path)


def _texture_asset_path(usd_path: Path, name: str) -> str:
    return (
        Path("textures") / usd_textures.output_sidecar_namespace(usd_path) / name
    ).as_posix()


def _content_name(stem: str, contents: bytes, suffix: str) -> str:
    return f"{stem}-{hashlib.sha256(contents).hexdigest()}{suffix}"


class _FakeAssetPath:
    def __init__(self, path: str, resolved_path: str = ""):
        self.path = path
        self.resolvedPath = resolved_path


class _FakeValueTypeNames:
    Asset = "asset"


class _FakeSdf:
    AssetPath = _FakeAssetPath
    ValueTypeNames = _FakeValueTypeNames


class _FakeLayer:
    def __init__(self, file_path: Path):
        self.realPath = str(file_path)
        self.identifier = str(file_path)

    def ComputeAbsolutePath(self, authored_path: str):
        return str((Path(self.realPath).parent / authored_path).resolve())


class _FakeSpec:
    def __init__(self, layer, authored_path: str):
        self.layer = layer
        self.default = _FakeAssetPath(authored_path)


class _FakeAttr:
    def __init__(self, authored_path: str, resolved_path: str = "", specs=None):
        self._value = _FakeAssetPath(authored_path, resolved_path)
        self._specs = list(specs or [])
        self.set_value = None

    def GetTypeName(self):
        return _FakeSdf.ValueTypeNames.Asset

    def Get(self):
        return self._value

    def Set(self, value):
        self.set_value = value
        self._value = value

    def GetPath(self):
        return "/Material/Texture.inputs:file"

    def GetPropertyStack(self):
        return self._specs


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


@pytest.fixture(autouse=True)
def _fake_sdf(monkeypatch):
    monkeypatch.setattr(usd_textures, "Sdf", _FakeSdf)


def _settings():
    return SimpleNamespace(export_texture_settings_enabled=False)


@pytest.mark.parametrize(
    (
        "source_name",
        "alpha_mode",
        "has_premultiplied_alpha",
        "texture_override",
        "should_reject",
    ),
    [
        (
            "albedo.png",
            "premul",
            True,
            {"file_format": "AVIF", "extension": ".avif", "resolution": 0},
            True,
        ),
        (
            "albedo.avif",
            "premul",
            True,
            {"file_format": "ORIGINAL", "extension": "", "resolution": 1024},
            True,
        ),
        ("albedo.avif", "premul", True, None, False),
        (
            "albedo.png",
            "premul",
            True,
            {"file_format": "PNG", "extension": ".png", "resolution": 1024},
            False,
        ),
        (
            "albedo.png",
            "straight",
            False,
            {"file_format": "AVIF", "extension": ".avif", "resolution": 0},
            False,
        ),
    ],
)
def test_premultiplied_alpha_policy_matches_effective_texture_staging(
    tmp_path,
    monkeypatch,
    source_name,
    alpha_mode,
    has_premultiplied_alpha,
    texture_override,
    should_reject,
):
    source = tmp_path / source_name
    monkeypatch.setattr(
        usd_textures,
        "_texture_override_settings",
        lambda *_args, **_kwargs: texture_override,
    )

    def validate():
        usd_textures.require_safe_texture_alpha_staging_policy(
            source,
            alpha_mode=alpha_mode,
            has_premultiplied_alpha=has_premultiplied_alpha,
            settings=SimpleNamespace(),
        )

    if should_reject:
        with pytest.raises(
            RuntimeError,
            match=r"Select PNG.*disable the unsafe AVIF/resolution override",
        ):
            validate()
    else:
        validate()


def test_resolved_path_wins_for_texture_authored_in_referenced_layer(tmp_path):
    root_dir = tmp_path / "export"
    layer_dir = tmp_path / "library"
    root_texture = root_dir / "textures" / "albedo.png"
    referenced_texture = layer_dir / "textures" / "albedo.png"
    root_texture.parent.mkdir(parents=True)
    referenced_texture.parent.mkdir(parents=True)
    root_texture.write_bytes(b"wrong root-relative texture")
    referenced_texture.write_bytes(b"referenced-layer texture")

    usd_path = root_dir / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr("textures/albedo.png", str(referenced_texture))

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    name = _content_name("scene-albedo", b"referenced-layer texture", ".png")
    staged = _texture_generation_dir(usd_path) / name
    assert staged.read_bytes() == b"referenced-layer texture"
    assert attr.set_value.path == _texture_asset_path(usd_path, name)
    assert attr.set_value.resolvedPath == ""


def test_property_stack_layer_resolves_relative_path_when_resolved_path_is_empty(tmp_path):
    root_dir = tmp_path / "export"
    sublayer_dir = tmp_path / "composition" / "look"
    sublayer_texture = sublayer_dir / "maps" / "coat.png"
    sublayer_texture.parent.mkdir(parents=True)
    sublayer_texture.write_bytes(b"sublayer texture")
    layer = _FakeLayer(sublayer_dir / "materials.usda")
    authored_path = "maps/coat.png"

    usd_path = root_dir / "scene.usda"
    root_dir.mkdir()
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(authored_path, specs=[_FakeSpec(layer, authored_path)])

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    name = _content_name("scene-coat", b"sublayer texture", ".png")
    assert (_texture_generation_dir(usd_path) / name).read_bytes() == b"sublayer texture"
    assert attr.set_value.path == _texture_asset_path(usd_path, name)


def test_real_usd_sublayer_texture_resolves_against_its_authored_layer(tmp_path, monkeypatch):
    from pxr import Sdf, Usd

    monkeypatch.setattr(usd_textures, "Sdf", Sdf)
    export_dir = tmp_path / "export"
    library_dir = tmp_path / "library"
    texture = library_dir / "maps" / "coat.png"
    texture.parent.mkdir(parents=True)
    texture.write_bytes(b"real composed texture")

    look_layer = library_dir / "look.usda"
    look_layer.write_text(
        '#usda 1.0\n\n'
        'def Shader "Texture"\n'
        '{\n'
        '    asset inputs:file = @maps/coat.png@\n'
        '}\n'
    )
    export_dir.mkdir()
    usd_path = export_dir / "scene.usda"
    usd_path.write_text(
        '#usda 1.0\n'
        '(\n'
        '    subLayers = [@../library/look.usda@]\n'
        ')\n'
    )
    stage = Usd.Stage.Open(str(usd_path), Usd.Stage.LoadAll)
    attr = stage.GetPrimAtPath("/Texture").GetAttribute("inputs:file")
    assert Path(attr.Get().resolvedPath) == texture.resolve()

    usd_textures.prepare_textures(stage, str(usd_path), _settings())

    name = _content_name("scene-coat", b"real composed texture", ".png")
    staged_path = _texture_generation_dir(usd_path) / name
    assert staged_path.read_bytes() == b"real composed texture"
    # Localizing the sublayer recomposes the stage, so refetch the attribute
    # instead of retaining an expired composed prim handle.
    staged_attr = stage.GetPrimAtPath("/Texture").GetAttribute("inputs:file")
    staged_value = staged_attr.Get()
    assert staged_value.path.endswith(name)
    assert Path(staged_value.resolvedPath) == staged_path.resolve()
    assert "@maps/coat.png@" in look_layer.read_text()


def test_file_url_is_normalized_before_copying(tmp_path):
    source = tmp_path / "source library" / "detail.png"
    source.parent.mkdir()
    source.write_bytes(b"file url texture")
    usd_path = tmp_path / "export" / "scene.usda"
    usd_path.parent.mkdir()
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(source.as_uri())

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    name = _content_name("scene-detail", b"file url texture", ".png")
    assert (_texture_generation_dir(usd_path) / name).read_bytes() == b"file url texture"
    assert attr.set_value.path == _texture_asset_path(usd_path, name)


def test_remote_texture_fails_self_contained_export(tmp_path):
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr("https://assets.example.invalid/material/albedo.png")
    diagnostics = SimpleNamespace(
        failures=[],
        add_texture_failed=lambda path, reason: diagnostics.failures.append((path, reason)),
    )

    with pytest.raises(RuntimeError, match="self-contained export"):
        usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings(), diagnostics)

    assert diagnostics.failures
    assert attr.set_value is None


@pytest.mark.parametrize("create_empty", [False, True])
def test_missing_or_empty_texture_fails_before_authoring_package_path(tmp_path, create_empty):
    source = tmp_path / "source.png"
    if create_empty:
        source.touch()
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))

    with pytest.raises(RuntimeError, match="not found|empty"):
        usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    assert attr.set_value is None


def test_destination_names_are_collision_safe_under_nfc_and_casefold(tmp_path):
    source_a = tmp_path / "a" / "ÉCLAIR.png"
    source_b = tmp_path / "b" / unicodedata.normalize("NFD", "éclair.png")
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    source_a.write_bytes(b"first")
    source_b.write_bytes(b"second")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr_a = _FakeAttr(str(source_a), str(source_a))
    attr_b = _FakeAttr(str(source_b), str(source_b))

    usd_textures.prepare_textures(_FakeStage([attr_a, attr_b]), str(usd_path), _settings())

    names = [path.name for path in _texture_generation_dir(usd_path).iterdir()]
    keys = [unicodedata.normalize("NFC", name).casefold() for name in names]
    assert len(names) == 2
    assert len(set(keys)) == 2
    assert attr_a.set_value.path != attr_b.set_value.path


def test_unsupported_input_format_is_forced_to_native_size_png(tmp_path, monkeypatch):
    source = tmp_path / "surface.webp"
    source.write_bytes(b"webp source")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))
    conversions = []

    def convert(source_path, dest_path, texture_override, diagnostics=None):
        conversions.append((source_path, dest_path, dict(texture_override)))
        dest_path.write_bytes(b"nonempty png")
        return True

    monkeypatch.setattr(usd_textures, "_convert_texture", convert)
    monkeypatch.setattr(usd_textures, "_validate_transcoded_texture", lambda *_args: True)

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    assert conversions[0][2] == {"file_format": "PNG", "extension": ".png", "resolution": 0}
    name = _content_name("scene-surface", b"nonempty png", ".png")
    assert attr.set_value.path == _texture_asset_path(usd_path, name)
    assert not (_texture_generation_dir(usd_path) / "scene-surface.webp").exists()


def test_exr_is_preserved_byte_for_byte_even_with_texture_override(tmp_path, monkeypatch):
    source = tmp_path / "lighting.exr"
    source.write_bytes(b"float-openexr-payload")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))

    monkeypatch.setattr(
        usd_textures,
        "_texture_override_settings",
        lambda *_args: {"file_format": "PNG", "extension": ".png", "resolution": 1024},
    )
    monkeypatch.setattr(
        usd_textures,
        "_convert_texture",
        lambda *_args, **_kwargs: pytest.fail("EXR must not be transcoded"),
    )

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    name = _content_name("scene-lighting", source.read_bytes(), ".exr")
    staged = _texture_generation_dir(usd_path) / name
    assert staged.read_bytes() == source.read_bytes()
    assert attr.set_value.path == _texture_asset_path(usd_path, name)


def test_radiance_hdr_fails_closed_instead_of_losing_float_fidelity(tmp_path, monkeypatch):
    source = tmp_path / "lighting.hdr"
    source.write_bytes(b"radiance-hdr-payload")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))
    monkeypatch.setattr(
        usd_textures,
        "_convert_texture",
        lambda *_args, **_kwargs: pytest.fail("HDR must fail before PNG conversion"),
    )

    with pytest.raises(RuntimeError, match="convert it to OpenEXR"):
        usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    assert attr.set_value is None


def test_failed_same_path_conversion_never_deletes_or_truncates_source(tmp_path, monkeypatch):
    textures = tmp_path / "textures"
    textures.mkdir()
    source = textures / "scene-surface.png"
    source.write_bytes(b"authoritative-source")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr("textures/scene-surface.png", str(source))

    monkeypatch.setattr(
        usd_textures,
        "_texture_override_settings",
        lambda *_args: {"file_format": "PNG", "extension": ".png", "resolution": 512},
    )

    def fail_after_partial_write(_source_path, temporary_path, _override, diagnostics=None):
        assert temporary_path != source
        temporary_path.write_bytes(b"partial-output")
        return False

    monkeypatch.setattr(usd_textures, "_convert_texture", fail_after_partial_write)

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    assert source.read_bytes() == b"authoritative-source"
    name = _content_name("scene-surface", b"authoritative-source", ".png")
    assert attr.set_value.path == _texture_asset_path(usd_path, name)
    assert not list(_texture_generation_dir(usd_path).glob(".*.convert-*.png"))


def test_avif_failure_falls_back_to_native_size_png(tmp_path, monkeypatch):
    source = tmp_path / "surface.png"
    source.write_bytes(b"png source")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))
    conversions = []

    monkeypatch.setattr(
        usd_textures,
        "_texture_override_settings",
        lambda *_args: {"file_format": "AVIF", "extension": ".avif", "resolution": 0},
    )

    def convert(_source_path, dest_path, texture_override, diagnostics=None):
        conversions.append(dict(texture_override))
        if texture_override["file_format"] == "AVIF":
            return False
        dest_path.write_bytes(b"native-size png")
        return True

    monkeypatch.setattr(usd_textures, "_convert_texture", convert)
    monkeypatch.setattr(usd_textures, "_validate_transcoded_texture", lambda *_args: True)

    usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    assert conversions == [
        {"file_format": "AVIF", "extension": ".avif", "resolution": 0},
        {"file_format": "PNG", "extension": ".png", "resolution": 0},
    ]
    name = _content_name("scene-surface", b"native-size png", ".png")
    assert attr.set_value.path == _texture_asset_path(usd_path, name)


def test_empty_transcode_of_unsupported_format_fails_closed(tmp_path, monkeypatch):
    source = tmp_path / "surface.tga"
    source.write_bytes(b"tga source")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))

    def write_empty(_source_path, dest_path, _texture_override, diagnostics=None):
        dest_path.write_bytes(b"")
        return True

    monkeypatch.setattr(usd_textures, "_convert_texture", write_empty)

    with pytest.raises(RuntimeError, match="could not be transcoded to PNG"):
        usd_textures.prepare_textures(_FakeStage([attr]), str(usd_path), _settings())

    assert attr.set_value is None
    assert not (_texture_generation_dir(usd_path) / "scene-surface.png").exists()


def test_content_addressed_leaf_is_deterministic_and_changes_with_bytes(tmp_path):
    leaves = []
    for directory, contents in (
        ("first", b"identical texture"),
        ("second", b"identical texture"),
        ("changed", b"changed texture"),
    ):
        export_dir = tmp_path / directory
        export_dir.mkdir()
        source = export_dir / "source" / "albedo.png"
        source.parent.mkdir()
        source.write_bytes(contents)
        usd_path = export_dir / "scene.usda"
        usd_path.write_text("#usda 1.0\n")
        attr = _FakeAttr(str(source), str(source))

        usd_textures.prepare_textures(
            _FakeStage([attr]),
            str(usd_path),
            _settings(),
        )
        leaves.append(Path(attr.set_value.path).name)

    assert leaves[0] == leaves[1]
    assert leaves[0] != leaves[2]
    assert leaves[0] == _content_name(
        "scene-albedo",
        b"identical texture",
        ".png",
    )


def test_two_pass_lossy_override_reuses_hash_verified_current_generation(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "albedo.png"
    source.write_bytes(b"original pixels")
    usd_path = tmp_path / "scene.usda"
    usd_path.write_text("#usda 1.0\n")
    attr = _FakeAttr(str(source), str(source))
    stage = _FakeStage([attr])
    conversions = []

    monkeypatch.setattr(
        usd_textures,
        "_texture_override_settings",
        lambda *_args: {
            "file_format": "JPEG",
            "extension": ".jpg",
            "resolution": 1024,
        },
    )

    def encode(source_path, dest_path, _override, diagnostics=None):
        conversions.append(source_path.read_bytes())
        dest_path.write_bytes(source_path.read_bytes() + b"|jpeg-encode")
        return True

    monkeypatch.setattr(usd_textures, "_convert_texture", encode)
    monkeypatch.setattr(
        usd_textures,
        "_validate_transcoded_texture",
        lambda *_args: True,
    )

    usd_textures.prepare_textures(stage, str(usd_path), _settings())
    first_path = attr.set_value.path
    first_bytes = (tmp_path / first_path).read_bytes()
    usd_textures.prepare_textures(stage, str(usd_path), _settings())

    assert conversions == [b"original pixels"]
    assert attr.set_value.path == first_path
    assert (tmp_path / attr.set_value.path).read_bytes() == first_bytes
    assert first_bytes == b"original pixels|jpeg-encode"


def test_instanceable_reference_localizes_prototype_texture_in_copied_layer(
    tmp_path,
    monkeypatch,
):
    from pxr import Sdf, Usd

    monkeypatch.setattr(usd_textures, "Sdf", Sdf)

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    texture = source_dir / "tex.png"
    texture.write_bytes(b"prototype texture")
    model_path = source_dir / "model.usda"
    model_stage = Usd.Stage.CreateNew(str(model_path))
    model = model_stage.DefinePrim("/Model", "Xform")
    model_stage.SetDefaultPrim(model)
    shader = model_stage.DefinePrim("/Model/Texture", "Shader")
    shader.CreateAttribute("inputs:file", Sdf.ValueTypeNames.Asset).Set(
        Sdf.AssetPath("tex.png")
    )
    model_stage.GetRootLayer().Save()
    source_bytes = model_path.read_bytes()

    usd_path = tmp_path / "scene.usda"
    stage = Usd.Stage.CreateNew(str(usd_path))
    for name in ("One", "Two"):
        instance = stage.DefinePrim(f"/{name}", "Xform")
        instance.GetReferences().AddReference(str(model_path), "/Model")
        instance.SetInstanceable(True)
    stage.GetRootLayer().Save()

    usd_assets.prepare_assets(
        stage,
        str(usd_path),
        settings=_settings(),
    )
    stage.GetRootLayer().Save()

    assert model_path.read_bytes() == source_bytes
    localized_models = list(
        (tmp_path / "assets" / "scene.usda").glob("*/model.usda")
    )
    assert len(localized_models) == 1
    staged_textures = list(
        (tmp_path / "textures" / "scene.usda").glob("*/*.png")
    )
    assert len(staged_textures) == 1
    assert staged_textures[0].read_bytes() == b"prototype texture"

    reopened = Usd.Stage.Open(str(usd_path), Usd.Stage.LoadAll)
    one = reopened.GetPrimAtPath("/One")
    two = reopened.GetPrimAtPath("/Two")
    assert one.IsInstance() and two.IsInstance()
    assert one.GetPrototype() == two.GetPrototype()
    prototype_texture = one.GetPrototype().GetChild("Texture")
    value = prototype_texture.GetAttribute("inputs:file").Get()
    assert Path(value.resolvedPath) == staged_textures[0].resolve()


def test_inactive_variant_texture_opinions_are_all_localized_without_collapse(
    tmp_path,
    monkeypatch,
):
    from pxr import Sdf, Usd

    monkeypatch.setattr(usd_textures, "Sdf", Sdf)

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "red.png").write_bytes(b"red texture")
    (source_dir / "blue.png").write_bytes(b"blue texture")
    model_path = source_dir / "model.usda"
    model_stage = Usd.Stage.CreateNew(str(model_path))
    model = model_stage.DefinePrim("/Model", "Xform")
    model_stage.SetDefaultPrim(model)
    variants = model.GetVariantSets().AddVariantSet("look")
    for variant_name, texture_name in (("Red", "red.png"), ("Blue", "blue.png")):
        variants.AddVariant(variant_name)
        variants.SetVariantSelection(variant_name)
        with variants.GetVariantEditContext():
            shader = model_stage.DefinePrim("/Model/Texture", "Shader")
            shader.CreateAttribute("inputs:file", Sdf.ValueTypeNames.Asset).Set(
                Sdf.AssetPath(texture_name)
            )
    variants.SetVariantSelection("Red")
    model_stage.GetRootLayer().Save()
    source_bytes = model_path.read_bytes()

    usd_path = tmp_path / "scene.usda"
    stage = Usd.Stage.CreateNew(str(usd_path))
    referenced = stage.DefinePrim("/Referenced", "Xform")
    referenced.GetReferences().AddReference(str(model_path), "/Model")
    stage.GetRootLayer().Save()

    usd_assets.prepare_assets(
        stage,
        str(usd_path),
        settings=_settings(),
    )
    stage.GetRootLayer().Save()

    assert model_path.read_bytes() == source_bytes
    localized_models = list(
        (tmp_path / "assets" / "scene.usda").glob("*/model.usda")
    )
    assert len(localized_models) == 1
    staged_textures = list(
        (tmp_path / "textures" / "scene.usda").glob("*/*.png")
    )
    assert {path.read_bytes() for path in staged_textures} == {
        b"red texture",
        b"blue texture",
    }

    localized_stage = Usd.Stage.Open(str(localized_models[0]), Usd.Stage.LoadAll)
    localized_model = localized_stage.GetPrimAtPath("/Model")
    localized_variants = localized_model.GetVariantSet("look")
    assert localized_variants.GetVariantSelection() == "Red"
    red_value = localized_stage.GetPrimAtPath("/Model/Texture").GetAttribute(
        "inputs:file"
    ).Get()
    assert Path(red_value.resolvedPath).read_bytes() == b"red texture"
    localized_variants.SetVariantSelection("Blue")
    blue_value = localized_stage.GetPrimAtPath("/Model/Texture").GetAttribute(
        "inputs:file"
    ).Get()
    assert Path(blue_value.resolvedPath).read_bytes() == b"blue texture"
    assert red_value.path != blue_value.path
