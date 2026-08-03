"""Target-blind positive-additive X scorer for the NMFA numeric core."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from indusbench.io import encode_json
from indusbench.nmfa_measurement_common import (
    _BLOCKERS,
    _GATE_PLAN_SHA256,
    _MAX_UNITS,
    _PARENT_PROTOCOL_SHA256,
    _PLAN_SHA256,
    _SCORE_SCHEMA_PATH,
    _SELECTOR_PLAN_SHA256,
    _X_SCHEMA_PATH,
    NMFAMeasurementErrorCode,
    _decode_canonical_json,
    _domain_digest,
    _fail,
    _is_checksum,
    _raw_sha256_matches,
    _require_unchanged_bundle,
    _sha256,
    _validate_installed_bundle,
    _validate_schema,
    _validate_static_bindings,
    validate_nmfa_gf_roster,
)

__all__ = ("ProtectedNMFAScoreState", "score_nmfa_x_batch", "verify_nmfa_score_receipt")

_MAX_TOTAL_TOKENS = 2_000_000
_MAX_MODEL_MEMBER_IDS = 20_000

_CLASS_DOMAIN = b"indusbench:nmfa:model-class:v1\x00"
_MODEL_DOMAIN = b"indusbench:nmfa:x-model:v1\x00"
_X_BATCH_DOMAIN = b"indusbench:nmfa:x-batch:v1\x00"
_SCORE_RECEIPT_DOMAIN = b"indusbench:nmfa:score-state:v1\x00"


@dataclass(frozen=True, repr=False)
class ProtectedNMFAScoreState:
    """Canonical protected score receipt; not an authentication token."""

    receipt_bytes: bytes
    receipt_raw_sha256: str
    receipt_sha256: str
    bundle_sha256: str

    def __repr__(self) -> str:
        return "<ProtectedNMFAScoreState protected>"

    def receipt(self) -> dict[str, Any]:
        """Return a fresh decoded copy after complete current-bundle validation."""

        value = _decode_score_receipt(
            self.receipt_bytes,
            self.receipt_raw_sha256,
            self.bundle_sha256,
        )
        if _domain_digest(_SCORE_RECEIPT_DOMAIN, value) != self.receipt_sha256:
            _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
        _require_unchanged_bundle(self.bundle_sha256)
        return value


def _class_id(member_token_ids: list[str]) -> str:
    return _domain_digest(_CLASS_DOMAIN, {"member_token_ids": member_token_ids})


def _decode_score_receipt(
    raw: bytes,
    expected_raw_sha256: str,
    expected_bundle_sha256: str | None = None,
) -> dict[str, Any]:
    if not _is_checksum(expected_raw_sha256) or not _raw_sha256_matches(raw, expected_raw_sha256):
        _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    value = _decode_canonical_json(raw, NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    _validate_schema(
        value,
        _SCORE_SCHEMA_PATH,
        NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID,
    )
    bundle_sha256 = _validate_installed_bundle()
    if (
        value["bindings"]["measurement_bundle_sha256"] != bundle_sha256
        or (expected_bundle_sha256 is not None and bundle_sha256 != expected_bundle_sha256)
        or tuple(value["compiled_blockers"]) != _BLOCKERS
    ):
        _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    rows = value["rows"]
    row_keys = [(row["g_id"], row["primary_f_id"]) for row in rows]
    if (
        row_keys != sorted(row_keys)
        or len({row["g_id"] for row in rows}) != len(rows)
        or len({row["primary_f_id"] for row in rows}) != len(rows)
    ):
        _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    for row in rows:
        if (
            row["l_distinct"] > row["l_total"]
            or bool(row["l_distinct"]) != bool(row["l_total"])
            or row["score"] > 16 * row["l_total"]
        ):
            _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    _require_unchanged_bundle(bundle_sha256)
    return cast(dict[str, Any], value)


def _validated_model(model: dict[str, Any], expected_model_sha256: str) -> dict[str, int]:
    if not _is_checksum(expected_model_sha256):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    actual_model_sha256 = _domain_digest(_MODEL_DOMAIN, model)
    if actual_model_sha256 != expected_model_sha256:
        _fail(NMFAMeasurementErrorCode.MODEL_CONTRACT_INVALID)
    classes = model["classes"]
    class_ids = [row["class_id"] for row in classes]
    if class_ids != sorted(class_ids) or len(class_ids) != len(set(class_ids)):
        _fail(NMFAMeasurementErrorCode.MODEL_CONTRACT_INVALID)
    weights = [row["weight"] for row in classes]
    if math.gcd(*weights) != 1:
        _fail(NMFAMeasurementErrorCode.MODEL_CONTRACT_INVALID)
    identity_to_weight: dict[str, int] = {}
    member_count = 0
    for row in classes:
        members = row["member_token_ids"]
        if (
            members != sorted(members)
            or len(members) != len(set(members))
            or row["class_id"] != _class_id(members)
        ):
            _fail(NMFAMeasurementErrorCode.MODEL_CONTRACT_INVALID)
        member_count += len(members)
        if member_count > _MAX_MODEL_MEMBER_IDS:
            _fail(NMFAMeasurementErrorCode.COMPUTATION_LIMIT_BLOCKED)
        for member in members:
            if member in identity_to_weight:
                _fail(NMFAMeasurementErrorCode.MODEL_CONTRACT_INVALID)
            identity_to_weight[member] = row["weight"]
    return identity_to_weight


def score_nmfa_x_batch(
    roster_raw: bytes,
    expected_roster_raw_sha256: str,
    x_batch_raw: bytes,
    expected_x_batch_raw_sha256: str,
    expected_model_sha256: str,
) -> ProtectedNMFAScoreState:
    """Score canonical X without receiving Y, partition, cell, or outcomes."""

    if not _is_checksum(expected_x_batch_raw_sha256):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    if not _raw_sha256_matches(x_batch_raw, expected_x_batch_raw_sha256):
        _fail(NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
    roster = validate_nmfa_gf_roster(roster_raw, expected_roster_raw_sha256)
    value = _decode_canonical_json(x_batch_raw, NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
    _validate_schema(value, _X_SCHEMA_PATH, NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
    _validate_static_bindings(value)
    if (
        value["assignment_roster_sha256"] != roster.roster_sha256
        or value["selector_assignment_raw_sha256"] != roster.selector_assignment_raw_sha256
        or value["claim_binding"] != roster.claim_binding
    ):
        _fail(NMFAMeasurementErrorCode.ROSTER_MISMATCH)
    raw_units = value["units"]
    unit_keys = tuple((row["g_id"], row["primary_f_id"]) for row in raw_units)
    if unit_keys != roster.rows or len(raw_units) > _MAX_UNITS:
        _fail(NMFAMeasurementErrorCode.ROSTER_MISMATCH)
    identity_to_weight = _validated_model(value["model"], expected_model_sha256)

    output_rows: list[dict[str, Any]] = []
    total_tokens = 0
    seen_side_ids: set[str] = set()
    seen_line_ids: set[str] = set()
    for raw_unit in raw_units:
        score = 0
        l_total = 0
        length_identities: set[str] = set()
        sides = raw_unit["sides"]
        for side_index, side in enumerate(sides):
            if side["side_index"] != side_index or side["side_id"] in seen_side_ids:
                _fail(NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
            seen_side_ids.add(side["side_id"])
            for line_index, line in enumerate(side["lines"]):
                if line["line_index"] != line_index or line["line_id"] in seen_line_ids:
                    _fail(NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
                seen_line_ids.add(line["line_id"])
                for token_index, token in enumerate(line["tokens"]):
                    total_tokens += 1
                    if total_tokens > _MAX_TOTAL_TOKENS:
                        _fail(NMFAMeasurementErrorCode.COMPUTATION_LIMIT_BLOCKED)
                    if token["token_index"] != token_index:
                        _fail(NMFAMeasurementErrorCode.X_CONTRACT_INVALID)
                    if token["disposition"] != "included":
                        continue
                    l_total += 1
                    length_identities.add(token["length_identity_id"])
                    score += identity_to_weight.get(token["scoring_identity_id"], 0)
        if score > 32_000_000 or l_total > _MAX_TOTAL_TOKENS:
            _fail(NMFAMeasurementErrorCode.COMPUTATION_LIMIT_BLOCKED)
        output_rows.append(
            {
                "g_id": raw_unit["g_id"],
                "l_distinct": len(length_identities),
                "l_total": l_total,
                "primary_f_id": raw_unit["primary_f_id"],
                "score": score,
            }
        )

    bundle_sha256 = roster.bundle_sha256
    receipt = {
        "assurance_boundary": {
            "all_side_completeness_authenticated": False,
            "model_digest_origin_verified": False,
            "scientific_result": False,
            "selector_assignment_roster_origin_verified": False,
            "x_batch_digest_origin_verified": False,
            "x_source_projection_authenticated": False,
        },
        "bindings": {
            "assignment_roster_sha256": roster.roster_sha256,
            "gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
            "measurement_bundle_sha256": bundle_sha256,
            "measurement_plan_sha256": "sha256:" + _PLAN_SHA256,
            "model_sha256": expected_model_sha256,
            "parent_protocol_sha256": "sha256:" + _PARENT_PROTOCOL_SHA256,
            "selector_assignment_raw_sha256": roster.selector_assignment_raw_sha256,
            "selector_plan_sha256": "sha256:" + _SELECTOR_PLAN_SHA256,
            "x_batch_sha256": _domain_digest(_X_BATCH_DOMAIN, value),
            "x_batch_raw_sha256": expected_x_batch_raw_sha256,
        },
        "claim_binding": roster.claim_binding,
        "compiled_blockers": list(_BLOCKERS),
        "format_version": "1.0.0",
        "record_kind": "nmfa_protected_score_state",
        "rows": output_rows,
        "terminal_state": "EXACT_X_SCORE_STATE_ONLY",
    }
    _validate_schema(
        receipt,
        _SCORE_SCHEMA_PATH,
        NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID,
    )
    raw_receipt = encode_json(receipt)
    receipt_raw_sha256 = _sha256(raw_receipt)
    receipt_sha256 = _domain_digest(_SCORE_RECEIPT_DOMAIN, receipt)
    _require_unchanged_bundle(bundle_sha256)
    return ProtectedNMFAScoreState(
        receipt_bytes=raw_receipt,
        receipt_raw_sha256=receipt_raw_sha256,
        receipt_sha256=receipt_sha256,
        bundle_sha256=bundle_sha256,
    )


def verify_nmfa_score_receipt(
    roster_raw: bytes,
    expected_roster_raw_sha256: str,
    x_batch_raw: bytes,
    expected_x_batch_raw_sha256: str,
    expected_model_sha256: str,
    receipt_raw: bytes,
) -> None:
    """Require exact byte equality with a complete score reexecution."""

    expected = score_nmfa_x_batch(
        roster_raw,
        expected_roster_raw_sha256,
        x_batch_raw,
        expected_x_batch_raw_sha256,
        expected_model_sha256,
    )
    if type(receipt_raw) is not bytes or receipt_raw != expected.receipt_bytes:
        _fail(NMFAMeasurementErrorCode.SCORE_RECEIPT_INVALID)
    _decode_score_receipt(receipt_raw, expected.receipt_raw_sha256, expected.bundle_sha256)
    _require_unchanged_bundle(expected.bundle_sha256)
