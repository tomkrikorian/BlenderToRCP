"""Support bundle helper tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from Plugin.export.support_bundle import create_support_bundle


def test_support_bundle_redacts_paths_and_includes_manifest(tmp_path: Path):
    blend = tmp_path / "Scene.blend"
    export = tmp_path / "Scene.usdz"
    diagnostics = tmp_path / "Scene.diagnostics.json"
    job_dir = tmp_path / ".blendertorcp_jobs" / "job"
    job_dir.mkdir(parents=True)

    blend.write_bytes(b"blend")
    export.write_bytes(b"usdz")
    diagnostics.write_text(json.dumps({"filepath": str(export), "errors": []}))
    (job_dir / "status.json").write_text(json.dumps({"log_path": str(job_dir / "log.txt")}))
    (job_dir / "settings.json").write_text(json.dumps({"blend_file": str(blend)}))
    (job_dir / "log.txt").write_text(f"opened {blend}\n")

    result = create_support_bundle(
        blend_file=str(blend),
        export_path=str(export),
        diagnostics_path=str(diagnostics),
        job_dir=str(job_dir),
        bundle_output=str(tmp_path / "support.zip"),
    )

    bundle = Path(result["support_bundle_path"])
    assert bundle.exists()
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        assert any(name.endswith("manifest.json") for name in names)
        diag_name = next(name for name in names if name.endswith("diagnostics/export.diagnostics.json"))
        diag_text = zf.read(diag_name).decode()
        assert str(tmp_path) not in diag_text
        assert "$EXPORT_DIR" in diag_text or "$BLEND_DIR" in diag_text or "$HOME" in diag_text
