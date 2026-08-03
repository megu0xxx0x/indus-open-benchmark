"""X-blind exact rational target normalizer for the NMFA numeric core."""

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
    _SELECTOR_PLAN_SHA256,
    _TARGET_SCHEMA_PATH,
    _Y_SCHEMA_PATH,
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

__all__ = (
    "CanonicalRational",
    "ProtectedNMFATargetState",
    "normalize_nmfa_y_batch",
    "verify_nmfa_target_receipt",
)

_MAX_CONVERSIONS = 512
_MAX_INPUT = (1 << 63) - 1
_MAX_OUTPUT_BITS = 126

_TARGET_CONTRACT_DOMAIN = b"indusbench:nmfa:target-contract:v1\x00"
_Y_BATCH_DOMAIN = b"indusbench:nmfa:y-batch:v1\x00"
_TARGET_RECEIPT_DOMAIN = b"indusbench:nmfa:target-state:v1\x00"


@dataclass(frozen=True)
class CanonicalRational:
    """Nonnegative irreducible rational in the locked canonical unit."""

    numerator: int
    denominator: int


@dataclass(frozen=True, repr=False)
class ProtectedNMFATargetState:
    """Canonical protected target receipt; not an authentication token."""

    receipt_bytes: bytes
    receipt_raw_sha256: str
    receipt_sha256: str
    bundle_sha256: str

    def __repr__(self) -> str:
        return "<ProtectedNMFATargetState protected>"

    def receipt(self) -> dict[str, Any]:
        """Return a fresh decoded copy after complete current-bundle validation."""

        value = _decode_target_receipt(
            self.receipt_bytes,
            self.receipt_raw_sha256,
            self.bundle_sha256,
        )
        if _domain_digest(_TARGET_RECEIPT_DOMAIN, value) != self.receipt_sha256:
            _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
        _require_unchanged_bundle(self.bundle_sha256)
        return value


def _parse_decimal_integer(value: object, *, positive: bool) -> int:
    if type(value) is not str or not value or len(value) > 38:
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    if value == "0":
        if positive:
            _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
        return 0
    if value[0] == "0" or any(character not in "0123456789" for character in value):
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    parsed = int(value)
    if parsed.bit_length() > _MAX_OUTPUT_BITS:
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    return parsed


def _decode_target_receipt(
    raw: bytes,
    expected_raw_sha256: str,
    expected_bundle_sha256: str | None = None,
) -> dict[str, Any]:
    if not _is_checksum(expected_raw_sha256) or not _raw_sha256_matches(raw, expected_raw_sha256):
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    value = _decode_canonical_json(raw, NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    _validate_schema(
        value,
        _TARGET_SCHEMA_PATH,
        NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID,
    )
    bundle_sha256 = _validate_installed_bundle()
    if (
        value["bindings"]["measurement_bundle_sha256"] != bundle_sha256
        or (expected_bundle_sha256 is not None and bundle_sha256 != expected_bundle_sha256)
        or tuple(value["compiled_blockers"]) != _BLOCKERS
    ):
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    rows = value["rows"]
    row_keys = [(row["g_id"], row["primary_f_id"]) for row in rows]
    if (
        row_keys != sorted(row_keys)
        or len({row["g_id"] for row in rows}) != len(rows)
        or len({row["primary_f_id"] for row in rows}) != len(rows)
    ):
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    family = value["target_family"]
    for row in rows:
        raw_rational = row["canonical_value"]
        numerator = _parse_decimal_integer(raw_rational["numerator"], positive=False)
        denominator = _parse_decimal_integer(raw_rational["denominator"], positive=True)
        if (
            math.gcd(numerator, denominator) != 1
            or (numerator == 0 and denominator != 1)
            or (family == "direct_count" and denominator != 1)
            or (family != "direct_count" and numerator == 0)
        ):
            _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    _require_unchanged_bundle(bundle_sha256)
    return cast(dict[str, Any], value)


def _input_rational(
    value: dict[str, Any],
    error_code: NMFAMeasurementErrorCode,
    *,
    positive: bool,
) -> CanonicalRational:
    numerator = value["numerator"]
    denominator = value["denominator"]
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or numerator < (1 if positive else 0)
        or numerator > _MAX_INPUT
        or denominator < 1
        or denominator > _MAX_INPUT
        or math.gcd(numerator, denominator) != 1
        or (numerator == 0 and denominator != 1)
    ):
        _fail(error_code)
    return CanonicalRational(numerator, denominator)


def _multiply_exact(
    source: CanonicalRational,
    multiplier: CanonicalRational,
) -> CanonicalRational:
    g1 = math.gcd(source.numerator, multiplier.denominator)
    g2 = math.gcd(multiplier.numerator, source.denominator)
    numerator = (source.numerator // g1) * (multiplier.numerator // g2)
    denominator = (source.denominator // g2) * (multiplier.denominator // g1)
    if numerator.bit_length() > _MAX_OUTPUT_BITS or denominator.bit_length() > _MAX_OUTPUT_BITS:
        _fail(NMFAMeasurementErrorCode.COMPUTATION_LIMIT_BLOCKED)
    return CanonicalRational(numerator, denominator)


def normalize_nmfa_y_batch(
    roster_raw: bytes,
    expected_roster_raw_sha256: str,
    y_batch_raw: bytes,
    expected_y_batch_raw_sha256: str,
    expected_target_contract_sha256: str,
) -> ProtectedNMFATargetState:
    """Normalize exact Y without receiving X, model, score, partition, or cell."""

    if not _is_checksum(expected_target_contract_sha256):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    if not _is_checksum(expected_y_batch_raw_sha256):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    if not _raw_sha256_matches(y_batch_raw, expected_y_batch_raw_sha256):
        _fail(NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
    roster = validate_nmfa_gf_roster(roster_raw, expected_roster_raw_sha256)
    value = _decode_canonical_json(y_batch_raw, NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
    _validate_schema(value, _Y_SCHEMA_PATH, NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
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

    target_contract = value["target_contract"]
    if _domain_digest(_TARGET_CONTRACT_DOMAIN, target_contract) != expected_target_contract_sha256:
        _fail(NMFAMeasurementErrorCode.TARGET_CONTRACT_INVALID)
    conversions = target_contract["conversions"]
    source_unit_ids = [row["source_unit_id"] for row in conversions]
    if (
        len(conversions) > _MAX_CONVERSIONS
        or source_unit_ids != sorted(source_unit_ids)
        or len(source_unit_ids) != len(set(source_unit_ids))
    ):
        _fail(NMFAMeasurementErrorCode.TARGET_CONTRACT_INVALID)
    conversion_by_unit: dict[str, CanonicalRational] = {}
    for row in conversions:
        conversion_by_unit[row["source_unit_id"]] = _input_rational(
            row["multiplier"],
            NMFAMeasurementErrorCode.TARGET_CONTRACT_INVALID,
            positive=True,
        )
    canonical_unit_id = target_contract["canonical_unit_id"]
    if conversion_by_unit.get(canonical_unit_id) != CanonicalRational(1, 1):
        _fail(NMFAMeasurementErrorCode.TARGET_CONTRACT_INVALID)

    family = target_contract["target_family"]
    output_rows: list[dict[str, Any]] = []
    for raw_unit in raw_units:
        multiplier = conversion_by_unit.get(raw_unit["source_unit_id"])
        if multiplier is None:
            _fail(NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
        source = _input_rational(
            raw_unit["source_value"],
            NMFAMeasurementErrorCode.Y_CONTRACT_INVALID,
            positive=family != "direct_count",
        )
        if family == "direct_count" and source.denominator != 1:
            _fail(NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
        converted = _multiply_exact(source, multiplier)
        if (family == "direct_count" and converted.denominator != 1) or (
            family != "direct_count" and converted.numerator == 0
        ):
            _fail(NMFAMeasurementErrorCode.Y_CONTRACT_INVALID)
        output_rows.append(
            {
                "canonical_value": {
                    "denominator": str(converted.denominator),
                    "numerator": str(converted.numerator),
                },
                "g_id": raw_unit["g_id"],
                "primary_f_id": raw_unit["primary_f_id"],
            }
        )

    bundle_sha256 = roster.bundle_sha256
    receipt = {
        "assurance_boundary": {
            "scientific_result": False,
            "selector_assignment_roster_origin_verified": False,
            "target_contract_digest_origin_verified": False,
            "target_provenance_authenticated": False,
            "y_batch_digest_origin_verified": False,
        },
        "bindings": {
            "assignment_roster_sha256": roster.roster_sha256,
            "gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
            "measurement_bundle_sha256": bundle_sha256,
            "measurement_plan_sha256": "sha256:" + _PLAN_SHA256,
            "parent_protocol_sha256": "sha256:" + _PARENT_PROTOCOL_SHA256,
            "selector_assignment_raw_sha256": roster.selector_assignment_raw_sha256,
            "selector_plan_sha256": "sha256:" + _SELECTOR_PLAN_SHA256,
            "target_contract_sha256": expected_target_contract_sha256,
            "y_batch_sha256": _domain_digest(_Y_BATCH_DOMAIN, value),
            "y_batch_raw_sha256": expected_y_batch_raw_sha256,
        },
        "canonical_unit_id": canonical_unit_id,
        "claim_binding": roster.claim_binding,
        "compiled_blockers": list(_BLOCKERS),
        "format_version": "1.0.0",
        "record_kind": "nmfa_protected_target_state",
        "rows": output_rows,
        "target_family": family,
        "terminal_state": "EXACT_CANONICAL_TARGET_STATE_ONLY",
    }
    _validate_schema(
        receipt,
        _TARGET_SCHEMA_PATH,
        NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID,
    )
    raw_receipt = encode_json(receipt)
    receipt_raw_sha256 = _sha256(raw_receipt)
    receipt_sha256 = _domain_digest(_TARGET_RECEIPT_DOMAIN, receipt)
    _require_unchanged_bundle(bundle_sha256)
    return ProtectedNMFATargetState(
        receipt_bytes=raw_receipt,
        receipt_raw_sha256=receipt_raw_sha256,
        receipt_sha256=receipt_sha256,
        bundle_sha256=bundle_sha256,
    )


def verify_nmfa_target_receipt(
    roster_raw: bytes,
    expected_roster_raw_sha256: str,
    y_batch_raw: bytes,
    expected_y_batch_raw_sha256: str,
    expected_target_contract_sha256: str,
    receipt_raw: bytes,
) -> None:
    """Require exact byte equality with a complete target reexecution."""

    expected = normalize_nmfa_y_batch(
        roster_raw,
        expected_roster_raw_sha256,
        y_batch_raw,
        expected_y_batch_raw_sha256,
        expected_target_contract_sha256,
    )
    if type(receipt_raw) is not bytes or receipt_raw != expected.receipt_bytes:
        _fail(NMFAMeasurementErrorCode.TARGET_RECEIPT_INVALID)
    _decode_target_receipt(receipt_raw, expected.receipt_raw_sha256, expected.bundle_sha256)
    _require_unchanged_bundle(expected.bundle_sha256)
