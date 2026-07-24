from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts._lib.rcp_import_acceptance import AcceptanceError, validate_acceptance

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "rcp_import"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_pending_template_fails_closed() -> None:
    with pytest.raises(AcceptanceError, match="not_run"):
        validate_acceptance(_load("corpus.json"), _load("acceptance.template.json"))


def test_complete_evidence_passes() -> None:
    corpus = _load("corpus.json")
    evidence = copy.deepcopy(_load("acceptance.template.json"))
    for fixture in evidence["fixtures"]:
        fixture["expected_structures"] = {
            "clean_import": "a" * 64,
            "reimport": "a" * 64,
        }
        for run in fixture["runs"]:
            run["status"] = "pass"
            run["evidence"] = "evidence/session.json"
            run["source_sha256"] = fixture["source_sha256"]
            run["canonical_structure_sha256"] = "a" * 64
        for gate in fixture["gates"].values():
            gate["status"] = "pass"
            gate["evidence"] = "evidence/session.json"

    validate_acceptance(corpus, evidence)


def test_build_mismatch_fails_closed() -> None:
    evidence = _load("acceptance.template.json")
    evidence["rcp"]["build"] = "future-build"

    with pytest.raises(AcceptanceError, match="version/build"):
        validate_acceptance(_load("corpus.json"), evidence, require_pass=False)


def test_unknown_gate_fails_closed() -> None:
    evidence = _load("acceptance.template.json")
    evidence["fixtures"][0]["gates"]["future_gate"] = {
        "status": "pass",
        "evidence": "future.json",
    }

    with pytest.raises(AcceptanceError, match="unknown gates"):
        validate_acceptance(_load("corpus.json"), evidence, require_pass=False)


def test_missing_repeatability_run_fails_closed() -> None:
    evidence = _load("acceptance.template.json")
    evidence["fixtures"][0]["runs"].pop()

    with pytest.raises(AcceptanceError, match="missing runs"):
        validate_acceptance(_load("corpus.json"), evidence, require_pass=False)


def test_phase_pinned_reimport_canonicalization_passes() -> None:
    corpus = _load("corpus.json")
    evidence = copy.deepcopy(_load("acceptance.template.json"))
    fixture = evidence["fixtures"][2]
    for run in fixture["runs"]:
        run["status"] = "pass"
        run["evidence"] = "evidence/session.json"
        run["source_sha256"] = fixture["source_sha256"]
        run["canonical_structure_sha256"] = fixture["expected_structures"][run["kind"]]

    validate_acceptance(corpus, evidence, require_pass=False)


def test_unpinned_structural_change_fails_closed() -> None:
    evidence = copy.deepcopy(_load("acceptance.template.json"))
    fixture = evidence["fixtures"][2]
    run = fixture["runs"][2]
    run["status"] = "pass"
    run["evidence"] = "evidence/session.json"
    run["source_sha256"] = fixture["source_sha256"]
    run["canonical_structure_sha256"] = "f" * 64

    with pytest.raises(AcceptanceError, match="pinned reimport phase"):
        validate_acceptance(_load("corpus.json"), evidence, require_pass=False)
