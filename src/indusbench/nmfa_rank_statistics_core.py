"""Joint exact-rank statistics over separately produced NMFA receipts."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Any, TypeVar, cast

from indusbench.io import encode_json
from indusbench.nmfa_measurement_common import (
    _BLOCKERS,
    _GATE_PLAN_SHA256,
    _METRIC_SCHEMA_PATH,
    _PARENT_PROTOCOL_SHA256,
    _PLAN_SHA256,
    _SELECTOR_PLAN_SHA256,
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
    validate_nmfa_metric_roster,
)
from indusbench.nmfa_x_model_core import _decode_score_receipt
from indusbench.nmfa_y_rational_core import CanonicalRational, _decode_target_receipt

__all__ = (
    "ProtectedNMFAMetricState",
    "doubled_midranks_integers",
    "evaluate_nmfa_rank_metrics",
    "exact_nmfa_spearman_at_least",
    "verify_nmfa_metric_receipt",
)

_SCALE = 1_000_000_000_000
_RANK_DOMAIN = b"indusbench:nmfa:doubled-ranks:v1\x00"
_METRIC_RECEIPT_DOMAIN = b"indusbench:nmfa:metric-state:v1\x00"

T = TypeVar("T")


@dataclass(frozen=True, repr=False)
class ProtectedNMFAMetricState:
    """Aggregate protected metric receipt; it contains no item rows."""

    receipt_bytes: bytes
    receipt_raw_sha256: str
    receipt_sha256: str
    bundle_sha256: str

    def __repr__(self) -> str:
        return "<ProtectedNMFAMetricState protected>"

    def receipt(self) -> dict[str, Any]:
        """Return a copy after schema, bundle, and encoded-arithmetic checks."""

        value = _decode_metric_receipt(
            self.receipt_bytes,
            self.receipt_raw_sha256,
            self.bundle_sha256,
        )
        if _domain_digest(_METRIC_RECEIPT_DOMAIN, value) != self.receipt_sha256:
            _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
        _require_unchanged_bundle(self.bundle_sha256)
        return value


def _compare_rational(left: CanonicalRational, right: CanonicalRational) -> int:
    comparison = left.numerator * right.denominator - right.numerator * left.denominator
    return (comparison > 0) - (comparison < 0)


def _compare_integer(left: int, right: int) -> int:
    return (left > right) - (left < right)


def _doubled_midranks(values: list[T], compare: Callable[[T, T], int]) -> list[int]:
    n = len(values)
    ordered = sorted(
        range(n), key=cmp_to_key(lambda left, right: compare(values[left], values[right]))
    )
    ranks = [0] * n
    start = 0
    while start < n:
        end = start + 1
        while end < n and compare(values[ordered[start]], values[ordered[end]]) == 0:
            end += 1
        doubled_rank = start + end + 1
        for position in range(start, end):
            ranks[ordered[position]] = doubled_rank
        start = end
    if n and (min(ranks) < 2 or max(ranks) > 2 * n or sum(ranks) != n * (n + 1)):
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    return ranks


def doubled_midranks_integers(values: tuple[int, ...]) -> tuple[int, ...]:
    """Return exact doubled average ranks for a bounded integer vector."""

    bundle_sha256 = _validate_installed_bundle()
    if type(values) is not tuple or not values or len(values) > 20_000:
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    if any(type(value) is not int or value < 0 or value > 32_000_000 for value in values):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    result = tuple(_doubled_midranks(list(values), _compare_integer))
    _require_unchanged_bundle(bundle_sha256)
    return result


def _round_ratio_sqrt(numerator: int, denominator_radicand: int, scale: int = _SCALE) -> int:
    if denominator_radicand <= 0 or scale <= 0:
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    if numerator == 0:
        return 0
    absolute = abs(numerator) * scale
    squared = absolute * absolute
    floor_value = math.isqrt(squared // denominator_radicand)
    midpoint_left = 4 * squared
    midpoint_right = denominator_radicand * (2 * floor_value + 1) ** 2
    if midpoint_left > midpoint_right or (midpoint_left == midpoint_right and floor_value % 2 == 1):
        floor_value += 1
    return -floor_value if numerator < 0 else floor_value


def _format_scaled(value: int) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    return f"{sign}{absolute // _SCALE}.{absolute % _SCALE:012d}"


def exact_nmfa_spearman_at_least(
    covariance_c: int,
    variance_left: int,
    variance_target: int,
    threshold_numerator: int,
    threshold_denominator: int,
) -> bool:
    """Compare defined rho to one nonnegative unit-interval threshold exactly."""

    bundle_sha256 = _validate_installed_bundle()
    if (
        type(covariance_c) is not int
        or type(variance_left) is not int
        or type(variance_target) is not int
        or type(threshold_numerator) is not int
        or type(threshold_denominator) is not int
        or variance_left <= 0
        or variance_target <= 0
        or threshold_numerator < 0
        or threshold_denominator <= 0
        or threshold_numerator > threshold_denominator
        or abs(covariance_c).bit_length() > 256
        or variance_left.bit_length() > 256
        or variance_target.bit_length() > 256
        or threshold_numerator.bit_length() > 256
        or threshold_denominator.bit_length() > 256
    ):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    radicand = variance_left * variance_target
    if covariance_c * covariance_c > radicand:
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    result = covariance_c >= 0 and (
        threshold_denominator * threshold_denominator * covariance_c * covariance_c
        >= threshold_numerator * threshold_numerator * radicand
    )
    _require_unchanged_bundle(bundle_sha256)
    return result


def _metric_state(left_values: list[int], target_values: list[CanonicalRational]) -> dict[str, Any]:
    if len(left_values) != len(target_values) or not left_values:
        _fail(NMFAMeasurementErrorCode.ROSTER_MISMATCH)
    n = len(left_values)
    left_ranks = _doubled_midranks(left_values, _compare_integer)
    target_ranks = _doubled_midranks(target_values, _compare_rational)
    common: dict[str, Any] = {
        "distinct_left_levels": len(set(left_values)),
        "distinct_target_levels": len(
            {(value.numerator, value.denominator) for value in target_values}
        ),
        "left_doubled_ranks_sha256": _domain_digest(_RANK_DOMAIN, left_ranks),
        "n": n,
        "target_doubled_ranks_sha256": _domain_digest(_RANK_DOMAIN, target_ranks),
    }
    if n < 2:
        return common | {"status": "undefined_insufficient_observations"}
    sum_left = sum(left_ranks)
    sum_target = sum(target_ranks)
    covariance = (
        n * sum(left * target for left, target in zip(left_ranks, target_ranks, strict=True))
        - sum_left * sum_target
    )
    variance_left = n * sum(value * value for value in left_ranks) - sum_left * sum_left
    variance_target = n * sum(value * value for value in target_ranks) - sum_target * sum_target
    if variance_left == 0 and variance_target == 0:
        return common | {"status": "undefined_zero_variance_both"}
    if variance_left == 0:
        return common | {"status": "undefined_zero_variance_left"}
    if variance_target == 0:
        return common | {"status": "undefined_zero_variance_target"}
    radicand = variance_left * variance_target
    if variance_left < 0 or variance_target < 0 or covariance * covariance > radicand:
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    scaled = _round_ratio_sqrt(covariance, radicand)
    if scaled < -_SCALE or scaled > _SCALE:
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    return common | {
        "covariance_c": str(covariance),
        "denominator_radicand": str(radicand),
        "rho_decimal_12": _format_scaled(scaled),
        "rho_scaled_1e12": scaled,
        "status": "defined",
        "variance_left": str(variance_left),
        "variance_target": str(variance_target),
    }


def _parse_canonical_decimal(value: object, *, signed: bool) -> int:
    if type(value) is not str or not value or len(value) > 77:
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    if value == "0":
        return 0
    body = value
    if signed and body.startswith("-"):
        body = body[1:]
        sign = -1
    else:
        sign = 1
    if not body or body[0] == "0" or any(character not in "0123456789" for character in body):
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    return sign * int(body)


def _decode_metric_receipt(
    raw: bytes,
    expected_raw_sha256: str,
    expected_bundle_sha256: str | None = None,
) -> dict[str, Any]:
    if not _is_checksum(expected_raw_sha256) or not _raw_sha256_matches(raw, expected_raw_sha256):
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    value = _decode_canonical_json(raw, NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    _validate_schema(
        value,
        _METRIC_SCHEMA_PATH,
        NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID,
    )
    bundle_sha256 = _validate_installed_bundle()
    if (
        value["bindings"]["measurement_bundle_sha256"] != bundle_sha256
        or (expected_bundle_sha256 is not None and bundle_sha256 != expected_bundle_sha256)
        or tuple(value["compiled_blockers"]) != _BLOCKERS
    ):
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    metrics = tuple(value["metrics"].values())
    if (
        len(
            {
                (
                    metric["n"],
                    metric["distinct_target_levels"],
                    metric["target_doubled_ranks_sha256"],
                )
                for metric in metrics
            }
        )
        != 1
    ):
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    for metric in metrics:
        n = metric["n"]
        distinct_left = metric["distinct_left_levels"]
        distinct_target = metric["distinct_target_levels"]
        status = metric["status"]
        if distinct_left > n or distinct_target > n:
            _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
        expected_undefined = {
            "undefined_insufficient_observations": n == 1
            and distinct_left == 1
            and distinct_target == 1,
            "undefined_zero_variance_both": n >= 2 and distinct_left == 1 and distinct_target == 1,
            "undefined_zero_variance_left": n >= 2 and distinct_left == 1 and distinct_target >= 2,
            "undefined_zero_variance_target": n >= 2
            and distinct_left >= 2
            and distinct_target == 1,
        }
        if status != "defined":
            if not expected_undefined.get(status, False):
                _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
            continue
        if n < 2 or distinct_left < 2 or distinct_target < 2:
            _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
        covariance = _parse_canonical_decimal(metric["covariance_c"], signed=True)
        variance_left = _parse_canonical_decimal(metric["variance_left"], signed=False)
        variance_target = _parse_canonical_decimal(metric["variance_target"], signed=False)
        radicand = _parse_canonical_decimal(metric["denominator_radicand"], signed=False)
        scaled = metric["rho_scaled_1e12"]
        minimum_variance = n * n * (n - 1)
        maximum_variance = n * n * (n * n - 1) // 3
        if (
            variance_left < minimum_variance
            or variance_target < minimum_variance
            or variance_left > maximum_variance
            or variance_target > maximum_variance
            or radicand != variance_left * variance_target
            or covariance * covariance > radicand
            or scaled != _round_ratio_sqrt(covariance, radicand)
            or metric["rho_decimal_12"] != _format_scaled(scaled)
        ):
            _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    defined_target_variances = {
        metric["variance_target"] for metric in metrics if metric["status"] == "defined"
    }
    if len(defined_target_variances) > 1:
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    _require_unchanged_bundle(bundle_sha256)
    return cast(dict[str, Any], value)


def evaluate_nmfa_rank_metrics(
    full_roster_raw: bytes,
    expected_full_roster_raw_sha256: str,
    metric_roster_raw: bytes,
    expected_metric_roster_raw_sha256: str,
    score_receipt_raw: bytes,
    expected_score_receipt_raw_sha256: str,
    target_receipt_raw: bytes,
    expected_target_receipt_raw_sha256: str,
) -> ProtectedNMFAMetricState:
    """Join only protected receipts over one separately declared metric subset."""

    metric_roster = validate_nmfa_metric_roster(
        full_roster_raw,
        expected_full_roster_raw_sha256,
        metric_roster_raw,
        expected_metric_roster_raw_sha256,
    )
    bundle_sha256 = metric_roster.full_roster.bundle_sha256
    score_receipt = _decode_score_receipt(
        score_receipt_raw,
        expected_score_receipt_raw_sha256,
        bundle_sha256,
    )
    target_receipt = _decode_target_receipt(
        target_receipt_raw,
        expected_target_receipt_raw_sha256,
        bundle_sha256,
    )
    score_bindings = score_receipt["bindings"]
    target_bindings = target_receipt["bindings"]
    if (
        score_receipt["claim_binding"] != metric_roster.full_roster.claim_binding
        or target_receipt["claim_binding"] != metric_roster.full_roster.claim_binding
        or score_bindings["assignment_roster_sha256"] != metric_roster.full_roster.roster_sha256
        or target_bindings["assignment_roster_sha256"] != metric_roster.full_roster.roster_sha256
        or score_bindings["selector_assignment_raw_sha256"]
        != metric_roster.full_roster.selector_assignment_raw_sha256
        or target_bindings["selector_assignment_raw_sha256"]
        != metric_roster.full_roster.selector_assignment_raw_sha256
    ):
        _fail(NMFAMeasurementErrorCode.ROSTER_MISMATCH)
    score_keys = tuple((row["g_id"], row["primary_f_id"]) for row in score_receipt["rows"])
    target_keys = tuple((row["g_id"], row["primary_f_id"]) for row in target_receipt["rows"])
    if score_keys != metric_roster.full_roster.rows or target_keys != score_keys:
        _fail(NMFAMeasurementErrorCode.ROSTER_MISMATCH)
    score_by_key = {key: row for key, row in zip(score_keys, score_receipt["rows"], strict=True)}
    target_by_key = {
        key: CanonicalRational(
            int(row["canonical_value"]["numerator"]),
            int(row["canonical_value"]["denominator"]),
        )
        for key, row in zip(target_keys, target_receipt["rows"], strict=True)
    }
    selected_scores = [score_by_key[key] for key in metric_roster.rows]
    selected_targets = [target_by_key[key] for key in metric_roster.rows]
    metrics = {
        "l_distinct_vs_target": _metric_state(
            [row["l_distinct"] for row in selected_scores],
            selected_targets,
        ),
        "l_total_vs_target": _metric_state(
            [row["l_total"] for row in selected_scores],
            selected_targets,
        ),
        "score_vs_target": _metric_state(
            [row["score"] for row in selected_scores],
            selected_targets,
        ),
    }
    receipt = {
        "assurance_boundary": {
            "confirmatory_or_prospective_gate_evaluated": False,
            "metric_roster_origin_verified": False,
            "process_custody_information_separation_enforced": False,
            "scientific_result": False,
            "score_receipt_digest_origin_verified": False,
            "selector_assignment_roster_origin_verified": False,
            "target_receipt_digest_origin_verified": False,
        },
        "bindings": {
            "assignment_roster_sha256": metric_roster.full_roster.roster_sha256,
            "gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
            "measurement_bundle_sha256": bundle_sha256,
            "measurement_plan_sha256": "sha256:" + _PLAN_SHA256,
            "metric_roster_raw_sha256": metric_roster.raw_sha256,
            "metric_roster_sha256": metric_roster.metric_roster_sha256,
            "model_sha256": score_bindings["model_sha256"],
            "parent_protocol_sha256": "sha256:" + _PARENT_PROTOCOL_SHA256,
            "score_receipt_raw_sha256": expected_score_receipt_raw_sha256,
            "selector_assignment_raw_sha256": (
                metric_roster.full_roster.selector_assignment_raw_sha256
            ),
            "selector_plan_sha256": "sha256:" + _SELECTOR_PLAN_SHA256,
            "target_contract_sha256": target_bindings["target_contract_sha256"],
            "target_receipt_raw_sha256": expected_target_receipt_raw_sha256,
        },
        "claim_binding": metric_roster.full_roster.claim_binding,
        "compiled_blockers": list(_BLOCKERS),
        "format_version": "1.0.0",
        "metrics": metrics,
        "record_kind": "nmfa_protected_rank_metric_state",
        "terminal_state": "EXACT_RANK_METRIC_STATE_ONLY",
    }
    _validate_schema(
        receipt,
        _METRIC_SCHEMA_PATH,
        NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID,
    )
    raw_receipt = encode_json(receipt)
    receipt_raw_sha256 = _sha256(raw_receipt)
    receipt_sha256 = _domain_digest(_METRIC_RECEIPT_DOMAIN, receipt)
    _require_unchanged_bundle(bundle_sha256)
    return ProtectedNMFAMetricState(
        receipt_bytes=raw_receipt,
        receipt_raw_sha256=receipt_raw_sha256,
        receipt_sha256=receipt_sha256,
        bundle_sha256=bundle_sha256,
    )


def verify_nmfa_metric_receipt(
    full_roster_raw: bytes,
    expected_full_roster_raw_sha256: str,
    metric_roster_raw: bytes,
    expected_metric_roster_raw_sha256: str,
    score_receipt_raw: bytes,
    expected_score_receipt_raw_sha256: str,
    target_receipt_raw: bytes,
    expected_target_receipt_raw_sha256: str,
    metric_receipt_raw: bytes,
) -> None:
    """Require exact byte equality with a complete metric reexecution."""

    expected = evaluate_nmfa_rank_metrics(
        full_roster_raw,
        expected_full_roster_raw_sha256,
        metric_roster_raw,
        expected_metric_roster_raw_sha256,
        score_receipt_raw,
        expected_score_receipt_raw_sha256,
        target_receipt_raw,
        expected_target_receipt_raw_sha256,
    )
    if type(metric_receipt_raw) is not bytes or metric_receipt_raw != expected.receipt_bytes:
        _fail(NMFAMeasurementErrorCode.METRIC_RECEIPT_INVALID)
    _decode_metric_receipt(
        metric_receipt_raw,
        expected.receipt_raw_sha256,
        expected.bundle_sha256,
    )
    _require_unchanged_bundle(expected.bundle_sha256)
