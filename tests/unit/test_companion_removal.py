"""Regression guard for the removed Companion preview feature."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "Plugin"


def test_companion_app_and_plugin_bridge_are_absent() -> None:
    forbidden_paths = (
        ROOT / "Companion",
        PLUGIN / "live_preview",
        PLUGIN / "ops" / "preview_operators.py",
    )

    assert not [path for path in forbidden_paths if path.exists()]


def test_plugin_has_no_companion_registration_hooks() -> None:
    forbidden_tokens = (
        "live_preview",
        "preview_operators",
        "RCPPreview",
        "start_live_preview",
        "stop_live_preview",
    )
    findings: list[str] = []

    for source in sorted(PLUGIN.rglob("*.py")):
        text = source.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                findings.append(f"{source.relative_to(ROOT)}: {token}")

    assert not findings, "\n".join(findings)
