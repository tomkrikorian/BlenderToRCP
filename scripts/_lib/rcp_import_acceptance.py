"""Validation for build-pinned RCP ``.import`` acceptance evidence."""

from __future__ import annotations

import re
from typing import Any

EVIDENCE_SCHEMA_VERSION = 2
ALLOWED_STATUSES = frozenset({"pass", "fail", "not_run"})
COMMON_GATES = frozenset(
    {
        "golden_structure",
        "rcp_open",
        "rcp_reimport",
        "realitykit_runtime_load",
        "entity_material_bounds",
    }
)
ANIMATION_GATES = frozenset({"sequence_editor_clip", "animation_playback"})
REQUIRED_RUNS = {"clean_import": 2, "reimport": 2}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AcceptanceError(ValueError):
    """Raised when acceptance evidence is incomplete, failed, or mismatched."""


def _required_gates(profile: str) -> frozenset[str]:
    if profile == "static":
        return COMMON_GATES
    if profile in {"transform", "skeletal"}:
        return COMMON_GATES | ANIMATION_GATES
    raise AcceptanceError(f"unknown fixture profile {profile!r}")


def validate_acceptance(
    corpus: dict[str, Any],
    evidence: dict[str, Any],
    *,
    require_pass: bool = True,
) -> None:
    errors: list[str] = []
    if evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(
            f"unsupported evidence schema_version {evidence.get('schema_version')!r}"
        )
    if evidence.get("contract") != corpus.get("contract"):
        errors.append("evidence contract does not match corpus")
    if evidence.get("rcp") != corpus.get("rcp"):
        errors.append("evidence RCP version/build does not match corpus")

    corpus_fixtures = {item["id"]: item for item in corpus.get("fixtures", [])}
    evidence_fixtures = {item.get("id"): item for item in evidence.get("fixtures", [])}
    missing_fixtures = sorted(set(corpus_fixtures) - set(evidence_fixtures))
    unknown_fixtures = sorted(set(evidence_fixtures) - set(corpus_fixtures))
    if missing_fixtures:
        errors.append(f"missing fixture evidence {missing_fixtures}")
    if unknown_fixtures:
        errors.append(f"unknown fixture evidence {unknown_fixtures}")

    for fixture_id, fixture in corpus_fixtures.items():
        result = evidence_fixtures.get(fixture_id)
        if result is None:
            continue
        if result.get("profile") != fixture.get("profile"):
            errors.append(f"{fixture_id}: profile does not match corpus")
        if result.get("source_sha256") != fixture.get("source_asset", {}).get("sha256"):
            errors.append(f"{fixture_id}: source SHA-256 does not match corpus")
        if result.get("canonical_contract_sha256") != fixture.get("captured", {}).get(
            "canonical_contract_sha256"
        ):
            errors.append(f"{fixture_id}: structural capture does not match corpus")

        expected_structures = result.get("expected_structures")
        if not isinstance(expected_structures, dict):
            errors.append(f"{fixture_id}: expected_structures must be an object")
            expected_structures = {}
        else:
            missing_structure_kinds = sorted(
                set(REQUIRED_RUNS) - set(expected_structures)
            )
            unknown_structure_kinds = sorted(
                set(expected_structures) - set(REQUIRED_RUNS)
            )
            if missing_structure_kinds:
                errors.append(
                    f"{fixture_id}: missing expected structures "
                    f"{missing_structure_kinds}"
                )
            if unknown_structure_kinds:
                errors.append(
                    f"{fixture_id}: unknown expected structures "
                    f"{unknown_structure_kinds}"
                )
            for kind, structure_sha256 in expected_structures.items():
                if kind in REQUIRED_RUNS and not SHA256_RE.fullmatch(
                    str(structure_sha256)
                ):
                    errors.append(
                        f"{fixture_id}/{kind}: invalid expected structural SHA-256"
                    )

        runs = result.get("runs")
        if not isinstance(runs, list):
            errors.append(f"{fixture_id}: runs must be an array")
        else:
            expected_runs = {
                (kind, ordinal)
                for kind, count in REQUIRED_RUNS.items()
                for ordinal in range(1, count + 1)
            }
            actual_runs: dict[tuple[Any, Any], dict[str, Any]] = {}
            for run in runs:
                if not isinstance(run, dict):
                    errors.append(f"{fixture_id}: run must be an object")
                    continue
                kind = run.get("kind")
                ordinal = run.get("ordinal")
                if not isinstance(kind, str) or not isinstance(ordinal, int):
                    errors.append(f"{fixture_id}: invalid run identity")
                    continue
                key = (kind, ordinal)
                if key in actual_runs:
                    errors.append(f"{fixture_id}: duplicate run {key!r}")
                    continue
                actual_runs[key] = run
            missing_runs = sorted(expected_runs - set(actual_runs))
            unknown_runs = sorted(set(actual_runs) - expected_runs)
            if missing_runs:
                errors.append(f"{fixture_id}: missing runs {missing_runs}")
            if unknown_runs:
                errors.append(f"{fixture_id}: unknown runs {unknown_runs}")

            for key in sorted(expected_runs & set(actual_runs)):
                run = actual_runs[key]
                status = run.get("status")
                if status not in ALLOWED_STATUSES:
                    errors.append(f"{fixture_id}/{key}: unsupported status {status!r}")
                    continue
                if require_pass and status != "pass":
                    errors.append(f"{fixture_id}/{key}: status is {status!r}, not pass")
                if status != "pass":
                    continue
                if not str(run.get("evidence", "")).strip():
                    errors.append(f"{fixture_id}/{key}: pass lacks evidence")
                source_sha256 = str(run.get("source_sha256", ""))
                structure_sha256 = str(run.get("canonical_structure_sha256", ""))
                if not SHA256_RE.fullmatch(source_sha256):
                    errors.append(f"{fixture_id}/{key}: invalid source SHA-256")
                if not SHA256_RE.fullmatch(structure_sha256):
                    errors.append(f"{fixture_id}/{key}: invalid structural SHA-256")
                elif structure_sha256 != expected_structures.get(key[0]):
                    errors.append(
                        f"{fixture_id}/{key}: structural SHA-256 does not match "
                        f"the pinned {key[0]} phase"
                    )
                if key[0] == "clean_import" and source_sha256 != fixture.get(
                    "source_asset", {}
                ).get("sha256"):
                    errors.append(
                        f"{fixture_id}/{key}: clean source SHA-256 does not match corpus"
                    )
        gates = result.get("gates", {})
        if not isinstance(gates, dict):
            errors.append(f"{fixture_id}: gates must be an object")
            continue
        required = _required_gates(fixture["profile"])
        missing_gates = sorted(required - set(gates))
        unknown_gates = sorted(set(gates) - required)
        if missing_gates:
            errors.append(f"{fixture_id}: missing gates {missing_gates}")
        if unknown_gates:
            errors.append(f"{fixture_id}: unknown gates {unknown_gates}")
        for gate_name in sorted(required & set(gates)):
            gate = gates[gate_name]
            if not isinstance(gate, dict):
                errors.append(f"{fixture_id}/{gate_name}: gate must be an object")
                continue
            status = gate.get("status")
            if status not in ALLOWED_STATUSES:
                errors.append(
                    f"{fixture_id}/{gate_name}: unsupported status {status!r}"
                )
                continue
            if status == "pass" and not str(gate.get("evidence", "")).strip():
                errors.append(f"{fixture_id}/{gate_name}: pass lacks evidence")
            if require_pass and status != "pass":
                errors.append(
                    f"{fixture_id}/{gate_name}: status is {status!r}, not pass"
                )

    if errors:
        raise AcceptanceError(
            "RCP .import acceptance is not satisfied:\n"
            + "\n".join(f"- {error}" for error in errors)
        )
