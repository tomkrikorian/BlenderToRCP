import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.generate_pbr2_specular_tint_research import research_variants


def test_research_fixture_keeps_weight_redistribution_out_of_shipping_policy():
    variants = {item["name"]: item for item in research_variants()}

    assert variants["ClampOnly"]["specular_tint"] == [1.0, 1.0, 1.0]
    assert variants["ClampOnly"]["specular_weight"] == 1.0
    assert variants["ClampAndRedistribute"]["specular_weight"] == 2.0
    assert "Research hypothesis" in variants["ClampAndRedistribute"]["strategy"]
