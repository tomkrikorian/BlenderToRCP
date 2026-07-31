"""``--replace`` for experimental RCP ``.import`` packages.

Covers the default refusal (unchanged), the safety refusals that protect user
data, the stage-then-swap discipline that makes a refresh interruptible, and
the identity stability that makes a refresh meaningful at all.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Plugin.export import rcp_import_publish
from Plugin.export.rcp_import_publish import ImportPublishError


_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fakes: the publication discipline is testable without a USD stage.
# ---------------------------------------------------------------------------

def _write_package(destination: Path, marker_text: str = "old") -> Path:
    destination.mkdir(parents=True)
    (destination / rcp_import_publish.PACKAGE_MARKER).write_text(marker_text)
    (destination / "geometry").mkdir()
    (destination / "geometry" / "Cube.tm_geometry").write_text(marker_text)
    return destination


def _fake_generate(payload: str = "new", *, on_call=None):
    def generate(source, destination, *, record_source=None):
        if on_call is not None:
            on_call()
        destination = Path(destination)
        _write_package(destination, payload)
        (destination / "settings.tm_usd").write_text(
            f"source_path: {os.path.relpath(record_source or source, destination.parent)}"
        )
        return destination

    return generate


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _publish(destination: Path, *, replace: bool, generate=None, commit_source=None):
    source = destination.parent / "source.usda"
    if not source.exists():
        source.write_text("#usda 1.0\n")
    return rcp_import_publish.publish_static_import(
        staged_source=source,
        recorded_source=source,
        destination=destination,
        replace=replace,
        generate=generate or _fake_generate(),
        commit_source=commit_source,
    )


# ---------------------------------------------------------------------------
# The default refusal is unchanged
# ---------------------------------------------------------------------------

def test_existing_package_still_refuses_without_replace(tmp_path):
    destination = _write_package(tmp_path / "Scene.import")

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=False)

    assert caught.value.code == "RCP_IMPORT_EXISTS"
    assert str(caught.value) == (
        f"Refusing to overwrite existing .import directory: {destination}"
    )
    assert _tree(destination)["__tm_directory.tm_dir"] == b"old"


def test_publish_refuses_existing_package_without_replace(tmp_path):
    destination = _write_package(tmp_path / "Scene.import")
    before = _tree(destination)

    with pytest.raises(ImportPublishError) as caught:
        _publish(destination, replace=False)

    assert caught.value.code == "RCP_IMPORT_EXISTS"
    assert _tree(destination) == before


def test_missing_destination_is_published_without_replace(tmp_path):
    destination = tmp_path / "Scene.import"

    _publish(destination, replace=False)

    assert _tree(destination)["__tm_directory.tm_dir"] == b"new"


# ---------------------------------------------------------------------------
# Safety refusals — each must be distinct and must delete nothing
# ---------------------------------------------------------------------------

def test_replace_refuses_a_destination_that_is_not_an_import_path(tmp_path):
    destination = _write_package(tmp_path / "Scene.usdz")

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=True)

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_IMPORT_PATH"
    assert destination.is_dir()
    assert (destination / rcp_import_publish.PACKAGE_MARKER).exists()


def test_replace_refuses_a_bare_dot_import_name(tmp_path):
    destination = tmp_path / ".import"

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=True)

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_IMPORT_PATH"


def test_replace_refuses_a_directory_without_the_package_marker(tmp_path):
    destination = tmp_path / "Precious.import"
    destination.mkdir()
    (destination / "family-photos.txt").write_text("do not delete")

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=True)

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_A_PACKAGE"
    assert rcp_import_publish.PACKAGE_MARKER in str(caught.value)
    assert (destination / "family-photos.txt").read_text() == "do not delete"


def test_replace_refuses_a_symlinked_destination(tmp_path):
    real = _write_package(tmp_path / "real" / "Scene.import")
    destination = tmp_path / "Scene.import"
    destination.symlink_to(real, target_is_directory=True)

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=True)

    assert caught.value.code == "RCP_IMPORT_REPLACE_SYMLINK"
    assert destination.is_symlink()
    assert _tree(real)["__tm_directory.tm_dir"] == b"old"


def test_replace_refuses_a_file_destination(tmp_path):
    destination = tmp_path / "Scene.import"
    destination.write_text("not a package")

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=True)

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_A_PACKAGE"
    assert destination.read_text() == "not a package"


def test_publish_never_generates_when_a_refusal_applies(tmp_path):
    destination = tmp_path / "Precious.import"
    destination.mkdir()
    (destination / "keep.txt").write_text("keep")
    calls = []

    with pytest.raises(ImportPublishError):
        _publish(
            destination,
            replace=True,
            generate=_fake_generate(on_call=lambda: calls.append("generate")),
        )

    assert calls == []
    assert (destination / "keep.txt").read_text() == "keep"


# ---------------------------------------------------------------------------
# Stage then swap
# ---------------------------------------------------------------------------

def test_replace_swaps_a_new_package_into_place(tmp_path):
    destination = _write_package(tmp_path / "Scene.import")

    _publish(destination, replace=True)

    assert _tree(destination)["__tm_directory.tm_dir"] == b"new"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "Scene.import",
        "source.usda",
    ]


def test_the_old_package_is_intact_while_the_new_one_is_generated(tmp_path):
    destination = _write_package(tmp_path / "Scene.import")
    observed = []

    def observe():
        observed.append(
            (destination / rcp_import_publish.PACKAGE_MARKER).read_bytes()
        )

    _publish(destination, replace=True, generate=_fake_generate(on_call=observe))

    assert observed == [b"old"]


def test_a_failed_generation_leaves_the_old_package_and_never_publishes_the_source(
    tmp_path,
):
    destination = _write_package(tmp_path / "Scene.import")
    before = _tree(destination)
    committed = []

    def exploding_generate(source, staging, *, record_source=None):
        staging = Path(staging)
        staging.mkdir(parents=True)
        (staging / "half-written.tm_geometry").write_bytes(b"partial")
        raise RuntimeError("unsupported geometry")

    with pytest.raises(RuntimeError, match="unsupported geometry"):
        _publish(
            destination,
            replace=True,
            generate=exploding_generate,
            commit_source=lambda: committed.append("usda"),
        )

    assert _tree(destination) == before
    assert committed == []
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "Scene.import",
        "source.usda",
    ]


def test_a_failed_source_publication_leaves_the_old_package(tmp_path):
    destination = _write_package(tmp_path / "Scene.import")
    before = _tree(destination)

    def failing_commit():
        raise RuntimeError("could not publish .usda")

    with pytest.raises(RuntimeError, match="could not publish"):
        _publish(destination, replace=True, commit_source=failing_commit)

    assert _tree(destination) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "Scene.import",
        "source.usda",
    ]


def test_a_failed_swap_puts_the_old_package_back(tmp_path, monkeypatch):
    destination = _write_package(tmp_path / "Scene.import")
    before = _tree(destination)
    real_rename = os.rename
    calls = []

    def flaky_rename(src, dst):
        calls.append((src, dst))
        if len(calls) == 2:
            raise OSError("interrupted")
        return real_rename(src, dst)

    monkeypatch.setattr(rcp_import_publish.os, "rename", flaky_rename)

    with pytest.raises(OSError, match="interrupted"):
        _publish(destination, replace=True)

    assert _tree(destination) == before


# ---------------------------------------------------------------------------
# Interrupted-swap recovery
# ---------------------------------------------------------------------------

def test_an_interrupted_swap_restores_the_old_package_on_the_next_run(tmp_path):
    destination = tmp_path / "Scene.import"
    backup = _write_package(
        tmp_path / f".blendertorcp-import-replaced-{destination.name}"
    )

    assert rcp_import_publish.recover_interrupted_replacement(destination) == "restored"

    assert not backup.exists()
    assert _tree(destination)["__tm_directory.tm_dir"] == b"old"


def test_a_completed_swap_with_a_leftover_backup_is_cleaned_up(tmp_path):
    destination = _write_package(tmp_path / "Scene.import", "new")
    backup = _write_package(
        tmp_path / f".blendertorcp-import-replaced-{destination.name}"
    )

    assert rcp_import_publish.recover_interrupted_replacement(destination) == "discarded"

    assert not backup.exists()
    assert _tree(destination)["__tm_directory.tm_dir"] == b"new"


def test_recovery_never_follows_a_symlinked_backup(tmp_path):
    real = _write_package(tmp_path / "elsewhere")
    destination = tmp_path / "Scene.import"
    backup = tmp_path / f".blendertorcp-import-replaced-{destination.name}"
    backup.symlink_to(real, target_is_directory=True)

    assert rcp_import_publish.recover_interrupted_replacement(destination) is None
    assert backup.is_symlink()
    assert real.is_dir()


def test_validation_heals_an_interrupted_swap_before_refusing(tmp_path):
    destination = tmp_path / "Scene.import"
    _write_package(tmp_path / f".blendertorcp-import-replaced-{destination.name}")

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.check_destination(destination, replace=False)

    assert caught.value.code == "RCP_IMPORT_EXISTS"
    assert _tree(destination)["__tm_directory.tm_dir"] == b"old"


# ---------------------------------------------------------------------------
# Opt-in resolution
# ---------------------------------------------------------------------------

def test_replace_flag_is_an_error_for_a_non_rcp_format():
    settings = SimpleNamespace(rcp_import_replace=False)

    with pytest.raises(ImportPublishError) as caught:
        rcp_import_publish.resolve_replace_request(
            {"replace": True},
            settings,
            rcp_import_export=False,
        )

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_APPLICABLE"


def test_replace_setting_is_ignored_for_a_non_rcp_format():
    settings = SimpleNamespace(rcp_import_replace=True)

    assert rcp_import_publish.resolve_replace_request(
        {},
        settings,
        rcp_import_export=False,
    ) is False


def test_replace_comes_from_either_the_flag_or_the_setting():
    off = SimpleNamespace(rcp_import_replace=False)
    on = SimpleNamespace(rcp_import_replace=True)

    assert rcp_import_publish.resolve_replace_request({}, off, rcp_import_export=True) is False
    assert rcp_import_publish.resolve_replace_request(
        {"replace": True}, off, rcp_import_export=True
    ) is True
    assert rcp_import_publish.resolve_replace_request({}, on, rcp_import_export=True) is True


# ---------------------------------------------------------------------------
# Identity stability with the real generator
# ---------------------------------------------------------------------------

_CUBE_USDA = """#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{
    float3 xformOp:rotateXYZ = (-90, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    def Mesh "Cube"
    {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 4, 6, 2, 3, 2, 6, 7, 7, 6, 4, 5, 5, 1, 3, 7, 1, 0, 2, 3, 5, 4, 0, 1]
        point3f[] points = [(1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]
        normal3f[] normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, -1, 0), (0, -1, 0), (0, -1, 0), (0, -1, 0), (-1, 0, 0), (-1, 0, 0), (-1, 0, 0), (-1, 0, 0), (0, 0, -1), (0, 0, -1), (0, 0, -1), (0, 0, -1), (1, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)] (
            interpolation = "faceVarying"
        )
        texCoord2f[] primvars:st = [(0.625, 0.5), (0.875, 0.5), (0.875, 0.75), (0.625, 0.75), (0.375, 0.75), (0.625, 0.75), (0.625, 1), (0.375, 1), (0.375, 0), (0.625, 0), (0.625, 0.25), (0.375, 0.25), (0.125, 0.5), (0.375, 0.5), (0.375, 0.75), (0.125, 0.75), (0.375, 0.5), (0.625, 0.5), (0.625, 0.75), (0.375, 0.75), (0.375, 0.25), (0.625, 0.25), (0.625, 0.5), (0.375, 0.5)] (
            interpolation = "faceVarying"
        )
        uniform token subdivisionScheme = "none"
    }
}
"""


@pytest.fixture
def cube_usda(tmp_path) -> Path:
    pytest.importorskip("pxr")
    source = tmp_path / "output" / "Cube.usda"
    source.parent.mkdir()
    source.write_text(_CUBE_USDA, encoding="utf-8")
    return source


def test_generating_from_a_staged_copy_records_the_final_source(cube_usda, tmp_path):
    """The staging detour must not change one byte of the package."""
    from Plugin.export.rcp_import_generator import generate_static_import

    direct = cube_usda.parent / "Cube.import"
    generate_static_import(cube_usda, direct)

    staged_source = tmp_path / "staging" / "Cube.usda"
    staged_source.parent.mkdir()
    shutil.copy(cube_usda, staged_source)
    staged = cube_usda.parent / ".staged-Cube.import"
    generate_static_import(staged_source, staged, record_source=cube_usda)

    assert _tree(staged) == _tree(direct)


def test_a_refresh_reproduces_the_package_byte_for_byte(cube_usda):
    """Identity stability: a refresh of an unchanged scene must not churn."""
    destination = cube_usda.parent / "Cube.import"

    rcp_import_publish.publish_static_import(
        staged_source=cube_usda,
        recorded_source=cube_usda,
        destination=destination,
        replace=False,
    )
    first = _tree(destination)

    rcp_import_publish.publish_static_import(
        staged_source=cube_usda,
        recorded_source=cube_usda,
        destination=destination,
        replace=True,
    )

    assert _tree(destination) == first
    assert sorted(p.name for p in cube_usda.parent.iterdir()) == [
        "Cube.import",
        "Cube.usda",
    ]


# ---------------------------------------------------------------------------
# Command surface
# ---------------------------------------------------------------------------

def _export_harness(monkeypatch, tmp_path, *, export_format="RCP_IMPORT", replace_setting=False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_material_profile_callers import _install_export_dependencies, _settings

    settings = _settings(
        export_format=export_format,
        rcp_import_replace=replace_setting,
    )
    validate_module = SimpleNamespace(
        collect_scene_materials=lambda _context: [],
        validate_material=lambda *_args, **_kwargs: {
            "ok": True,
            "errors": [],
            "warnings": [],
        },
    )
    _install_export_dependencies(
        monkeypatch,
        settings=settings,
        export_objects=[SimpleNamespace(name="Cube")],
        validate_module=validate_module,
    )
    monkeypatch.setattr(
        "Plugin.export.rcp_import_generator.generate_static_import",
        _fake_generate(),
    )
    return settings


def test_export_command_refuses_an_existing_package_without_replace(
    monkeypatch, tmp_path
):
    from Plugin.api.commands import export as export_command
    from Plugin.api.errors import CommandError

    _export_harness(monkeypatch, tmp_path)
    destination = _write_package(tmp_path / "Scene.import")

    with pytest.raises(CommandError) as caught:
        export_command.handle({"filepath": str(destination), "format": "RCP_IMPORT"})

    assert caught.value.code == "RCP_IMPORT_EXISTS"
    assert caught.value.stage == "validation"
    assert str(caught.value) == (
        f"Refusing to overwrite existing .import directory: {destination}"
    )
    assert _tree(destination)["__tm_directory.tm_dir"] == b"old"


def test_export_command_refreshes_an_existing_package_with_replace(
    monkeypatch, tmp_path
):
    from Plugin.api.commands import export as export_command

    _export_harness(monkeypatch, tmp_path)
    destination = _write_package(tmp_path / "Scene.import")

    result = export_command.handle(
        {"filepath": str(destination), "format": "RCP_IMPORT", "replace": True}
    )

    assert result["ok"] is True
    assert result["export_path"] == str(destination)
    assert _tree(destination)["__tm_directory.tm_dir"] == b"new"


def test_export_command_honours_the_scene_replace_setting(monkeypatch, tmp_path):
    from Plugin.api.commands import export as export_command

    _export_harness(monkeypatch, tmp_path, replace_setting=True)
    destination = _write_package(tmp_path / "Scene.import")

    result = export_command.handle(
        {"filepath": str(destination), "format": "RCP_IMPORT"}
    )

    assert result["ok"] is True
    assert _tree(destination)["__tm_directory.tm_dir"] == b"new"


def test_export_command_rejects_replace_for_a_non_rcp_format(monkeypatch, tmp_path):
    from Plugin.api.commands import export as export_command
    from Plugin.api.errors import CommandError

    _export_harness(monkeypatch, tmp_path, export_format="USDZ")

    with pytest.raises(CommandError) as caught:
        export_command.handle(
            {"filepath": str(tmp_path / "Scene.usdz"), "format": "USDZ", "replace": True}
        )

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_APPLICABLE"
    assert caught.value.stage == "validation"


def test_export_command_refuses_a_destination_that_is_not_a_package(
    monkeypatch, tmp_path
):
    from Plugin.api.commands import export as export_command
    from Plugin.api.errors import CommandError

    _export_harness(monkeypatch, tmp_path)
    destination = tmp_path / "Scene.import"
    destination.mkdir()
    (destination / "keep.txt").write_text("keep")

    with pytest.raises(CommandError) as caught:
        export_command.handle(
            {"filepath": str(destination), "format": "RCP_IMPORT", "replace": True}
        )

    assert caught.value.code == "RCP_IMPORT_REPLACE_NOT_A_PACKAGE"
    assert (destination / "keep.txt").read_text() == "keep"


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command,handler_name",
    [("export", "cmd_export"), ("bake-export", "cmd_bake_export")],
)
def test_cli_replace_flag_reaches_the_command_payload(
    monkeypatch, command, handler_name
):
    from Plugin.cli import __main__ as cli

    captured = {}

    def fake_run(name, args, parsed):
        captured["command"] = name
        captured["args"] = args
        return {"ok": True, "duration_seconds": 0}

    monkeypatch.setattr(cli, "_run", fake_run)
    parser = cli.build_parser()
    handler = getattr(cli, handler_name)

    handler(
        parser.parse_args(
            [
                command,
                "scene.blend",
                "-o",
                "out.import",
                "--format",
                "RCP_IMPORT",
                "--replace",
            ]
        )
    )
    assert captured["args"]["replace"] is True

    captured.clear()
    handler(
        parser.parse_args(
            [command, "scene.blend", "-o", "out.import", "--format", "RCP_IMPORT"]
        )
    )
    assert "replace" not in captured["args"]


# ---------------------------------------------------------------------------
# Every RCP_IMPORT lane goes through the one guard
# ---------------------------------------------------------------------------

_PUBLISHING_LANES = (
    "Plugin/api/commands/export.py",
    "Plugin/api/commands/bake_export.py",
    "Plugin/bake_export_runner.py",
    "Plugin/ops/export_operator.py",
)
_GUARD_ONLY_LANES = ("Plugin/ops/bake_export_operator.py",)


@pytest.mark.parametrize("relative_path", _PUBLISHING_LANES + _GUARD_ONLY_LANES)
def test_every_rcp_import_lane_uses_the_shared_guard(relative_path):
    source = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert "rcp_import_publish.check_destination(" in source, relative_path
    # The hand-rolled refusal each lane used to carry must be gone, so the
    # refusal and the safety rules can never drift apart again.
    assert "Refusing to overwrite existing .import directory" not in source


@pytest.mark.parametrize("relative_path", _PUBLISHING_LANES)
def test_no_lane_writes_a_package_outside_the_publisher(relative_path):
    source = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert "rcp_import_publish.publish_static_import(" in source, relative_path
    assert "generate_static_import(" not in source, relative_path
