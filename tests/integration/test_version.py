"""Integration test — blendertorcp version."""

import pytest


pytestmark = pytest.mark.integration


class TestVersion:
    def test_has_plugin_version(self, run_cli):
        result = run_cli("version")
        assert result.ok
        assert "plugin" in result.json
        assert isinstance(result.json["plugin"], str)
        assert len(result.json["plugin"]) > 0

    def test_has_blender_version(self, run_cli):
        result = run_cli("version")
        assert result.ok
        assert "blender" in result.json
        assert isinstance(result.json["blender"], str)
        assert len(result.json["blender"]) > 0

    def test_has_python_version(self, run_cli):
        result = run_cli("version")
        assert result.ok
        assert "python" in result.json
        assert isinstance(result.json["python"], str)
        assert len(result.json["python"]) > 0
