"""Focused tests for archive-installed export smoke helpers."""

from __future__ import annotations

import struct
from types import SimpleNamespace
import zipfile

import pytest

from Plugin.export.pack_usdz import USDZ_ALLOWED_MEMBER_EXTENSIONS
from scripts import smoke_extension_archive as smoke


def _write_aligned_member(archive, name: str, payload: bytes) -> None:
    encoded_name = name.encode("utf-8")
    local_header_offset = archive.fp.tell()
    padding_length = -(
        local_header_offset + 30 + len(encoded_name) + 4
    ) % smoke.USDZ_ALIGNMENT
    info = zipfile.ZipInfo(name)
    info.compress_type = zipfile.ZIP_STORED
    info.extra = struct.pack("<HH", 0x1986, padding_length) + (b"\0" * padding_length)
    archive.writestr(info, payload)


def test_usdc_structure_requires_binary_crate_signature(tmp_path):
    valid = tmp_path / "scene.usdc"
    valid.write_bytes(b"PXR-USDC" + (b"\0" * 64))

    result = smoke._validate_usdc_structure(valid)

    assert result["ok"] is True
    assert result["profile"] == "binary-usd-crate"

    invalid = tmp_path / "not-a-crate.usdc"
    invalid.write_bytes(b"#usda 1.0" + (b"\0" * 64))
    with pytest.raises(RuntimeError, match="invalid crate signature"):
        smoke._validate_usdc_structure(invalid)


def test_usdz_structure_accepts_aligned_uncompressed_root(tmp_path):
    package = tmp_path / "scene.usdz"
    with zipfile.ZipFile(package, "w") as archive:
        _write_aligned_member(archive, "scene.usdc", b"PXR-USDC" + (b"\0" * 64))
        _write_aligned_member(archive, "textures/base-color.avif", b"fake-avif")

    result = smoke._validate_usdz_structure(
        package,
        USDZ_ALLOWED_MEMBER_EXTENSIONS,
    )

    assert result["ok"] is True
    assert result["members"] == ["scene.usdc", "textures/base-color.avif"]
    assert result["payload_offsets"]["scene.usdc"] % 64 == 0
    assert result["payload_offsets"]["textures/base-color.avif"] % 64 == 0


def test_usdz_structure_rejects_default_zip_alignment(tmp_path):
    package = tmp_path / "misaligned.usdz"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("scene.usdc", b"PXR-USDC" + (b"\0" * 64))

    with pytest.raises(RuntimeError, match="misaligned member"):
        smoke._validate_usdz_structure(package, USDZ_ALLOWED_MEMBER_EXTENSIONS)


def test_usdz_structure_rejects_internal_generation_markers(tmp_path):
    package = tmp_path / "internal-marker.usdz"
    with zipfile.ZipFile(package, "w") as archive:
        _write_aligned_member(archive, "scene.usdc", b"PXR-USDC" + (b"\0" * 64))
        _write_aligned_member(
            archive,
            ".blendertorcp_generations/export.txt",
            b"internal state must not ship\n",
        )

    with pytest.raises(RuntimeError, match="unsupported Apple USDZ member extension"):
        smoke._validate_usdz_structure(package, USDZ_ALLOWED_MEMBER_EXTENSIONS)


def test_blender_usd_probe_is_source_package_independent():
    probe = smoke._usd_stage_probe_code()

    assert "from pxr import" in probe
    assert "Plugin" not in probe
    assert "ND_realitykit_pbr_surfaceshader" in probe
    assert 'GetSurfaceOutput("mtlx")' in probe
    assert "BLENDERTORCP_USD_STAGE_SMOKE=" in probe


def test_apple_member_allowlist_includes_os27_avif_and_nested_packages():
    assert isinstance(USDZ_ALLOWED_MEMBER_EXTENSIONS, frozenset)
    assert ".avif" in USDZ_ALLOWED_MEMBER_EXTENSIONS
    assert ".usdz" in USDZ_ALLOWED_MEMBER_EXTENSIONS


def test_usdz_structure_requires_a_valid_installed_extension_contract(tmp_path):
    package = tmp_path / "scene.usdz"
    package.write_bytes(b"not inspected when contract is invalid")

    with pytest.raises(RuntimeError, match="invalid USDZ member-extension contract"):
        smoke._validate_usdz_structure(package, ())


def test_apple_installed_smoke_runs_generic_and_arkit_strict_profiles(
    monkeypatch,
    tmp_path,
):
    assets = [tmp_path / "scene.usdc", tmp_path / "scene.usdz"]
    commands = []

    monkeypatch.setattr(
        smoke,
        "_resolve_tool_command",
        lambda _name, _env: (["/usr/bin/xcrun", "usdchecker"], "/apple/usdchecker"),
    )

    def fake_run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="Success!", stderr="")

    monkeypatch.setattr(smoke, "_run", fake_run)

    result = smoke._run_strict_usdchecker(
        assets,
        env={"PATH": "/usr/bin"},
        cwd=tmp_path,
    )

    assert [entry["profile"] for entry in result["validated"]] == [
        "generic-strict",
        "arkit-strict",
        "generic-strict",
        "arkit-strict",
    ]
    assert commands == [
        ["/usr/bin/xcrun", "usdchecker", "--strict", str(assets[0])],
        ["/usr/bin/xcrun", "usdchecker", "--arkit", "--strict", str(assets[0])],
        ["/usr/bin/xcrun", "usdchecker", "--strict", str(assets[1])],
        ["/usr/bin/xcrun", "usdchecker", "--arkit", "--strict", str(assets[1])],
    ]
