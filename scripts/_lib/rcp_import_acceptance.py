"""Validation for build-pinned RCP ``.import`` acceptance evidence."""

from __future__ import annotations

from typing import Any

EVIDENCE_SCHEMA_VERSION = 1
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
