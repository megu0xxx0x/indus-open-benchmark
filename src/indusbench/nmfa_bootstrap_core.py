"""Exact paired cell-stratified bootstrap for the source-free NMFA core.

The component consumes only separately digest-bound selector and measurement
receipts.  It performs the frozen 10,000-run bootstrap and returns an
aggregate protected receipt.  It does not evaluate a scientific gate, access
source material, authenticate the supplied chain head, or expose item rows or
the sampled schedule.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Never, TypeVar, cast, final

from indusbench.io import encode_json
from indusbench.nmfa_counter_stream import NMFACounterStream, NMFACounterStreamError
from indusbench.nmfa_exact_order import (
    ExactPairedDelta,
    ExactRho,
    ExactRhoKind,
    NMFAExactOrderError,
    compare_exact_paired_delta,
    compare_exact_rho,
    make_exact_paired_delta,
)
from indusbench.nmfa_measurement_common import (
    NMFAMeasurementError,
    NMFAMeasurementErrorCode,
    validate_nmfa_metric_roster,
)
from indusbench.nmfa_measurement_common import (
    _domain_digest as _measurement_domain_digest,
)
from indusbench.nmfa_rank_statistics_core import _metric_state
from indusbench.nmfa_resampling_common import (
    _AXES,
    _BLOCKERS,
    _BOOTSTRAP_RECEIPT_DOMAIN,
    _BOOTSTRAP_SCHEMA_PATH,
    _CELL_MINIMUM,
    _CELL_ROSTER_DOMAIN,
    _GATE_PLAN_SHA256,
    _HOLDOUT_MINIMUM,
    _MEASUREMENT_BUNDLE_SHA256,
    _MEASUREMENT_PLAN_SHA256,
    _PARENT_PROTOCOL_SHA256,
    _PLAN_SHA256,
    _SCHEDULE_DOMAIN,
    _SELECTOR_BUNDLE_SHA256,
    _SELECTOR_PLAN_SHA256,
    NMFAResamplingErrorCode,
    _decode_canonical_json,
    _decode_selector_assignment,
    _domain_digest,
    _fail,
    _is_checksum,
    _raw_sha256_matches,
    _require_unchanged_bundle,
    _sha256,
    _validate_installed_bundle,
    _validate_predecessors,
    _validate_schema,
)
from indusbench.nmfa_resampling_common import (
    _BOOTSTRAP_RUNS as _FROZEN_BOOTSTRAP_RUNS,
)
from indusbench.nmfa_resampling_common import (
    _LOWER_ENDPOINT_INDEX as _FROZEN_LOWER_ENDPOINT_INDEX,
)
from indusbench.nmfa_x_model_core import _decode_score_receipt
from indusbench.nmfa_y_rational_core import CanonicalRational, _decode_target_receipt

__all__ = (
    "ProtectedNMFABootstrapState",
    "evaluate_nmfa_paired_bootstrap",
    "verify_nmfa_bootstrap_receipt",
)

# These aliases remain private.  Focused tests may lower both together, while
# the installed public component and its plan freeze them at 10,000 and 249.
_BOOTSTRAP_RUNS = _FROZEN_BOOTSTRAP_RUNS
_LOWER_ENDPOINT_INDEX = _FROZEN_LOWER_ENDPOINT_INDEX
_MAX_SAMPLED_POSITIONS = 200_000_000
_COUNTER_ATTEMPTS_PER_DRAW = 16
_STREAM_LABEL = "bootstrap-v1"

_SCORE_RECEIPT_DOMAIN = b"indusbench:nmfa:score-state:v1\x00"
_TARGET_RECEIPT_DOMAIN = b"indusbench:nmfa:target-state:v1\x00"
_BOOTSTRAP_STATE_CONSTRUCTION_TOKEN: Final = object()
_UNDEFINED_METRIC_STATUSES = frozenset(
    {
        "undefined_insufficient_observations",
        "undefined_zero_variance_both",
        "undefined_zero_variance_left",
        "undefined_zero_variance_target",
    }
)


class _BootstrapInputRole(StrEnum):
    ROSTER = "roster"
    SCORE = "score"
    TARGET = "target"


@dataclass(frozen=True, slots=True)
class _BootstrapRow:
    g_id: str
    primary_f_id: str
    score: int
    l_total: int
    l_distinct: int
    target: CanonicalRational


@dataclass(frozen=True, slots=True)
class _IndexedRho:
    run_index: int
    value: ExactRho


@dataclass(frozen=True, slots=True)
class _IndexedDelta:
    run_index: int
    value: ExactPairedDelta


@final
@dataclass(frozen=True, slots=True, repr=False, init=False)
class ProtectedNMFABootstrapState:
    """Factory-issued canonical protected aggregate bootstrap receipt."""

    receipt_bytes: bytes
    receipt_raw_sha256: str
    receipt_sha256: str
    bundle_sha256: str
    _construction_marker: object = field(
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )

    def __init__(
        self,
        *,
        receipt_bytes: bytes,
        receipt_raw_sha256: str,
        receipt_sha256: str,
        bundle_sha256: str,
        _token: object | None = None,
    ) -> None:
        if (
            _token is not _BOOTSTRAP_STATE_CONSTRUCTION_TOKEN
            or type(receipt_bytes) is not bytes
            or not _raw_sha256_matches(receipt_bytes, receipt_raw_sha256)
            or not _is_checksum(receipt_sha256)
            or not _is_checksum(bundle_sha256)
        ):
            _fail(NMFAResamplingErrorCode.INVALID_ARGUMENT)
        object.__setattr__(self, "receipt_bytes", receipt_bytes)
        object.__setattr__(self, "receipt_raw_sha256", receipt_raw_sha256)
        object.__setattr__(self, "receipt_sha256", receipt_sha256)
        object.__setattr__(self, "bundle_sha256", bundle_sha256)
        object.__setattr__(
            self,
            "_construction_marker",
            _BOOTSTRAP_STATE_CONSTRUCTION_TOKEN,
        )

    def __repr__(self) -> str:
        return "<ProtectedNMFABootstrapState protected>"

    def receipt(self) -> dict[str, Any]:
        """Return a fresh copy of state issued by the local evaluator."""

        if (
            type(self) is not ProtectedNMFABootstrapState
            or getattr(self, "_construction_marker", None)
            is not _BOOTSTRAP_STATE_CONSTRUCTION_TOKEN
        ):
            _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)

        value = _decode_bootstrap_receipt(
            self.receipt_bytes,
            self.receipt_raw_sha256,
            self.bundle_sha256,
        )
        if _domain_digest(_BOOTSTRAP_RECEIPT_DOMAIN, value) != self.receipt_sha256:
            _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
        _require_unchanged_bundle(self.bundle_sha256)
        return value


def _map_measurement_error(error: NMFAMeasurementError, role: _BootstrapInputRole) -> Never:
    if error.code in {
        NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID,
        NMFAMeasurementErrorCode.SCHEMA_DEPENDENCY_MISSING,
    }:
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    if error.code is NMFAMeasurementErrorCode.COMPUTATION_LIMIT_BLOCKED:
        _fail(NMFAResamplingErrorCode.COMPUTATION_LIMIT_BLOCKED)
    if role is _BootstrapInputRole.SCORE:
        _fail(NMFAResamplingErrorCode.SCORE_RECEIPT_INVALID)
    if role is _BootstrapInputRole.TARGET:
        _fail(NMFAResamplingErrorCode.TARGET_RECEIPT_INVALID)
    _fail(NMFAResamplingErrorCode.ROSTER_MISMATCH)


def _exact_rho(metric: dict[str, Any], undefined_sentinel: int) -> tuple[ExactRho, bool]:
    try:
        if metric["status"] == "defined":
            return (
                ExactRho.defined(
                    int(metric["covariance_c"]),
                    int(metric["denominator_radicand"]),
                ),
                False,
            )
        if metric["status"] not in _UNDEFINED_METRIC_STATUSES:
            raise ValueError
        return ExactRho.sentinel(undefined_sentinel), True
    except (KeyError, TypeError, ValueError, NMFAExactOrderError):
        _fail(NMFAResamplingErrorCode.EXACT_ORDER_INVALID)


def _rho_payload(value: ExactRho) -> dict[str, str]:
    return {
        "covariance_c": str(value.covariance_c),
        "denominator_radicand": str(value.denominator_radicand),
        "kind": value.kind.value,
    }


def _rho_from_payload(value: object) -> ExactRho:
    if type(value) is not dict:
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    try:
        if set(value) != {"covariance_c", "denominator_radicand", "kind"}:
            raise ValueError
        covariance = _canonical_decimal(value["covariance_c"], signed=True)
        radicand = _canonical_decimal(value["denominator_radicand"], signed=False)
        kind = ExactRhoKind(value["kind"])
        return ExactRho(covariance, radicand, kind)
    except (KeyError, TypeError, ValueError, NMFAExactOrderError):
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)


def _is_candidate_endpoint_rho(value: ExactRho) -> bool:
    return value.kind is ExactRhoKind.DEFINED or (
        value.kind is ExactRhoKind.SENTINEL and value.covariance_c == -1
    )


def _is_selected_length_rho(value: ExactRho, source: str) -> bool:
    if source == "zero":
        return value.kind is ExactRhoKind.SENTINEL and value.covariance_c == 0
    return (
        source in {"l_total", "l_distinct"}
        and value.kind is ExactRhoKind.DEFINED
        and compare_exact_rho(value, ExactRho.sentinel(0)) > 0
    )


def _canonical_decimal(value: object, *, signed: bool) -> int:
    if type(value) is not str or not value or len(value) > 620:
        raise ValueError
    if value == "0":
        return 0
    body = value
    sign = 1
    if signed and body.startswith("-"):
        sign = -1
        body = body[1:]
    if not body or body[0] == "0" or any(character not in "0123456789" for character in body):
        raise ValueError
    return sign * int(body)


_SortItem = TypeVar("_SortItem")


def _stable_merge_sort(
    values: list[_SortItem],
    compare: Callable[[_SortItem, _SortItem], int],
) -> list[_SortItem]:
    """Return one deterministic stable merge sort under an exact comparator."""

    source = list(values)
    target = list(values)
    width = 1
    while width < len(source):
        for start in range(0, len(source), 2 * width):
            middle = min(start + width, len(source))
            end = min(start + 2 * width, len(source))
            left = start
            right = middle
            output = start
            while left < middle and right < end:
                if compare(source[left], source[right]) <= 0:
                    target[output] = source[left]
                    left += 1
                else:
                    target[output] = source[right]
                    right += 1
                output += 1
            while left < middle:
                target[output] = source[left]
                left += 1
                output += 1
            while right < end:
                target[output] = source[right]
                right += 1
                output += 1
        source, target = target, source
        width *= 2
    return source


def _compare_indexed_rho(left: _IndexedRho, right: _IndexedRho) -> int:
    comparison = compare_exact_rho(left.value, right.value)
    if comparison:
        return comparison
    return (left.run_index > right.run_index) - (left.run_index < right.run_index)


def _compare_indexed_delta(left: _IndexedDelta, right: _IndexedDelta) -> int:
    comparison = compare_exact_paired_delta(left.value, right.value)
    if comparison:
        return comparison
    return (left.run_index > right.run_index) - (left.run_index < right.run_index)


def _selector_and_measurement_inputs(
    full_roster_raw: bytes,
    expected_full_roster_raw_sha256: str,
    metric_roster_raw: bytes,
    expected_metric_roster_raw_sha256: str,
    selector_assignment_raw: bytes,
    expected_selector_assignment_raw_sha256: str,
    score_receipt_raw: bytes,
    expected_score_receipt_raw_sha256: str,
    target_receipt_raw: bytes,
    expected_target_receipt_raw_sha256: str,
) -> tuple[
    Any,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    tuple[tuple[str, str], ...],
]:
    try:
        metric_roster = validate_nmfa_metric_roster(
            full_roster_raw,
            expected_full_roster_raw_sha256,
            metric_roster_raw,
            expected_metric_roster_raw_sha256,
        )
    except NMFAMeasurementError as error:
        _map_measurement_error(error, _BootstrapInputRole.ROSTER)
    selector = _decode_selector_assignment(
        selector_assignment_raw,
        expected_selector_assignment_raw_sha256,
    )
    full = metric_roster.full_roster
    if (
        full.selector_assignment_raw_sha256 != expected_selector_assignment_raw_sha256
        or selector["claim_binding"] != full.claim_binding
    ):
        _fail(NMFAResamplingErrorCode.ROSTER_MISMATCH)
    selector_keys = tuple((row["g_id"], row["primary_f_id"]) for row in selector["assignments"])
    holdout_keys = tuple(
        key
        for key, row in zip(selector_keys, selector["assignments"], strict=True)
        if row["partition"] == "holdout"
    )
    if selector_keys != full.rows or holdout_keys != metric_roster.rows:
        _fail(NMFAResamplingErrorCode.ROSTER_MISMATCH)
    try:
        score = _decode_score_receipt(
            score_receipt_raw,
            expected_score_receipt_raw_sha256,
            full.bundle_sha256,
        )
    except NMFAMeasurementError as error:
        _map_measurement_error(error, _BootstrapInputRole.SCORE)
    try:
        target = _decode_target_receipt(
            target_receipt_raw,
            expected_target_receipt_raw_sha256,
            full.bundle_sha256,
        )
    except NMFAMeasurementError as error:
        _map_measurement_error(error, _BootstrapInputRole.TARGET)
    score_bindings = score["bindings"]
    target_bindings = target["bindings"]
    if (
        score["claim_binding"] != full.claim_binding
        or target["claim_binding"] != full.claim_binding
        or score_bindings["assignment_roster_sha256"] != full.roster_sha256
        or target_bindings["assignment_roster_sha256"] != full.roster_sha256
        or score_bindings["selector_assignment_raw_sha256"]
        != expected_selector_assignment_raw_sha256
        or target_bindings["selector_assignment_raw_sha256"]
        != expected_selector_assignment_raw_sha256
    ):
        _fail(NMFAResamplingErrorCode.ROSTER_MISMATCH)
    score_keys = tuple((row["g_id"], row["primary_f_id"]) for row in score["rows"])
    target_keys = tuple((row["g_id"], row["primary_f_id"]) for row in target["rows"])
    if score_keys != full.rows or target_keys != full.rows:
        _fail(NMFAResamplingErrorCode.ROSTER_MISMATCH)
    return metric_roster, selector, score, target, holdout_keys


def _bootstrap_rows_by_cell(
    selector: dict[str, Any],
    score: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, tuple[_BootstrapRow, ...]]:
    score_by_key = {(row["g_id"], row["primary_f_id"]): row for row in score["rows"]}
    target_by_key = {
        (row["g_id"], row["primary_f_id"]): CanonicalRational(
            int(row["canonical_value"]["numerator"]),
            int(row["canonical_value"]["denominator"]),
        )
        for row in target["rows"]
    }
    cells: dict[str, list[_BootstrapRow]] = {axis: [] for axis in _AXES}
    for assignment in selector["assignments"]:
        if assignment["partition"] != "holdout":
            continue
        cell = assignment["cell"]
        if cell not in cells:
            _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
        key = (assignment["g_id"], assignment["primary_f_id"])
        score_row = score_by_key[key]
        cells[cell].append(
            _BootstrapRow(
                g_id=key[0],
                primary_f_id=key[1],
                score=score_row["score"],
                l_total=score_row["l_total"],
                l_distinct=score_row["l_distinct"],
                target=target_by_key[key],
            )
        )
    frozen = {axis: tuple(cells[axis]) for axis in _AXES}
    if (
        any(len(rows) < _CELL_MINIMUM for rows in frozen.values())
        or sum(len(rows) for rows in frozen.values()) < _HOLDOUT_MINIMUM
    ):
        _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    return frozen


def _cell_roster_sha256(selector: dict[str, Any]) -> str:
    # Keep the selector's globally sorted G-F order.  Cell-stratified draw
    # order is a separate schedule-frame contract.
    value = {
        "rows": [
            {
                "cell": row["cell"],
                "g_id": row["g_id"],
                "primary_f_id": row["primary_f_id"],
            }
            for row in selector["assignments"]
            if row["partition"] == "holdout"
        ]
    }
    return _domain_digest(_CELL_ROSTER_DOMAIN, value)


def _schedule_hasher(
    cell_roster_sha256: str,
    chain_head_key: bytes,
    run_count: int,
    cell_sizes: tuple[int, int, int, int],
) -> Any:
    digest = hashlib.sha256()
    digest.update(_SCHEDULE_DOMAIN)
    digest.update(bytes.fromhex(cell_roster_sha256[7:]))
    digest.update(chain_head_key)
    for value in (run_count, sum(cell_sizes), len(_AXES), *cell_sizes):
        digest.update(value.to_bytes(8, "big"))
    return digest


def _endpoint_rho_payload(value: _IndexedRho) -> dict[str, Any]:
    return {"run_index": value.run_index, "rho": _rho_payload(value.value)}


def _endpoint_delta_payload(value: _IndexedDelta) -> dict[str, Any]:
    maximum = value.value.length_maximum
    return {
        "length_maximum": {
            "rho": _rho_payload(maximum.rho),
            "source": maximum.source.value,
        },
        "primary_rho": _rho_payload(value.value.primary),
        "run_index": value.run_index,
    }


def _evaluate_runs(
    cells: dict[str, tuple[_BootstrapRow, ...]],
    chain_head_key: bytes,
    cell_roster_sha256: str,
    run_count: int,
    lower_endpoint_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    holdout_units = sum(len(cells[axis]) for axis in _AXES)
    if (
        type(run_count) is not int
        or type(lower_endpoint_index) is not int
        or run_count < 1
        or run_count > _FROZEN_BOOTSTRAP_RUNS
        or lower_endpoint_index < 0
        or lower_endpoint_index >= run_count
        or run_count * holdout_units > _MAX_SAMPLED_POSITIONS
    ):
        _fail(NMFAResamplingErrorCode.COMPUTATION_LIMIT_BLOCKED)
    cell_sizes = cast(tuple[int, int, int, int], tuple(len(cells[axis]) for axis in _AXES))
    schedule = _schedule_hasher(
        cell_roster_sha256,
        chain_head_key,
        run_count,
        cell_sizes,
    )
    indexed_rhos: list[_IndexedRho] = []
    indexed_deltas: list[_IndexedDelta] = []
    candidate_substitutions = 0
    total_substitutions = 0
    distinct_substitutions = 0
    length_selections = {"zero": 0, "l_total": 0, "l_distinct": 0}
    total_blocks = 0
    total_rejections = 0
    maximum_blocks = 0

    for run_index in range(run_count):
        stream = NMFACounterStream(chain_head_key, _STREAM_LABEL, run_index)
        sampled_scores: list[int] = []
        sampled_total: list[int] = []
        sampled_distinct: list[int] = []
        sampled_targets: list[CanonicalRational] = []
        try:
            for axis in _AXES:
                rows = cells[axis]
                for _ in range(len(rows)):
                    local_index = stream.draw_index(len(rows))
                    schedule.update(local_index.to_bytes(8, "big"))
                    row = rows[local_index]
                    sampled_scores.append(row.score)
                    sampled_total.append(row.l_total)
                    sampled_distinct.append(row.l_distinct)
                    sampled_targets.append(row.target)
        except NMFACounterStreamError as error:
            if error.code.value == "COMPUTATION_LIMIT_BLOCKED":
                _fail(NMFAResamplingErrorCode.COMPUTATION_LIMIT_BLOCKED)
            _fail(NMFAResamplingErrorCode.COUNTER_STREAM_INVALID)
        stats = stream.stats()
        if (
            stats.draws != holdout_units
            or stats.blocks_generated != stats.next_counter
            or stats.blocks_generated != stats.draws + stats.rejected_blocks
        ):
            _fail(NMFAResamplingErrorCode.COUNTER_STREAM_INVALID)
        total_blocks += stats.blocks_generated
        total_rejections += stats.rejected_blocks
        maximum_blocks = max(maximum_blocks, stats.blocks_generated)
        try:
            candidate_metric = _metric_state(sampled_scores, sampled_targets)
            total_metric = _metric_state(sampled_total, sampled_targets)
            distinct_metric = _metric_state(sampled_distinct, sampled_targets)
        except NMFAMeasurementError as error:
            _map_measurement_error(error, _BootstrapInputRole.ROSTER)
        candidate, candidate_substituted = _exact_rho(candidate_metric, -1)
        total, total_substituted = _exact_rho(total_metric, 0)
        distinct, distinct_substituted = _exact_rho(distinct_metric, 0)
        candidate_substitutions += int(candidate_substituted)
        total_substitutions += int(total_substituted)
        distinct_substitutions += int(distinct_substituted)
        try:
            delta = make_exact_paired_delta(candidate, total, distinct)
        except NMFAExactOrderError:
            _fail(NMFAResamplingErrorCode.EXACT_ORDER_INVALID)
        length_selections[delta.length_maximum.source.value] += 1
        indexed_rhos.append(_IndexedRho(run_index, candidate))
        indexed_deltas.append(_IndexedDelta(run_index, delta))

    try:
        sorted_rhos = _stable_merge_sort(indexed_rhos, _compare_indexed_rho)
        sorted_deltas = _stable_merge_sort(indexed_deltas, _compare_indexed_delta)
    except NMFAExactOrderError:
        _fail(NMFAResamplingErrorCode.EXACT_ORDER_INVALID)
    rho_endpoint = sorted_rhos[lower_endpoint_index]
    delta_endpoint = sorted_deltas[lower_endpoint_index]
    bootstrap = {
        "cell_order": list(_AXES),
        "cell_roster_sha256": cell_roster_sha256,
        "cell_sizes": {axis: len(cells[axis]) for axis in _AXES},
        "counter": {
            "maximum_blocks_generated_per_run": maximum_blocks,
            "total_blocks_generated": total_blocks,
            "total_draws": run_count * holdout_units,
            "total_rejected_blocks": total_rejections,
        },
        "discarded_runs": 0,
        "draws_per_run": holdout_units,
        "holdout_units": holdout_units,
        "length_maximum_selections": length_selections,
        "redrawn_runs": 0,
        "run_count": run_count,
        "schedule_sha256": "sha256:" + schedule.hexdigest(),
        "substitutions": {
            "candidate_to_negative_one": candidate_substitutions,
            "l_distinct_to_zero": distinct_substitutions,
            "l_total_to_zero": total_substitutions,
        },
    }
    endpoints = {
        "candidate_rho_lower": _endpoint_rho_payload(rho_endpoint),
        "lower_index_zero_based": lower_endpoint_index,
        "lower_order_one_based": lower_endpoint_index + 1,
        "paired_delta_lower": _endpoint_delta_payload(delta_endpoint),
    }
    return bootstrap, endpoints


def _decode_bootstrap_receipt(
    raw: bytes,
    expected_raw_sha256: str,
    expected_bundle_sha256: str | None = None,
) -> dict[str, Any]:
    if not _is_checksum(expected_raw_sha256) or not _raw_sha256_matches(raw, expected_raw_sha256):
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    value = _decode_canonical_json(raw, NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    if type(value) is not dict:
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    _validate_schema(
        value,
        _BOOTSTRAP_SCHEMA_PATH,
        NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
    )
    bundle_sha256 = _validate_installed_bundle()
    if (
        value["bindings"]["resampling_bundle_sha256"] != bundle_sha256
        or (expected_bundle_sha256 is not None and bundle_sha256 != expected_bundle_sha256)
        or tuple(value["compiled_blockers"]) != _BLOCKERS
        or value["bootstrap"]["run_count"] != _BOOTSTRAP_RUNS
        or value["endpoints"]["lower_index_zero_based"] != _LOWER_ENDPOINT_INDEX
        or value["endpoints"]["lower_order_one_based"] != _LOWER_ENDPOINT_INDEX + 1
    ):
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    bootstrap = value["bootstrap"]
    counter = bootstrap["counter"]
    run_count = bootstrap["run_count"]
    holdout_units = bootstrap["holdout_units"]
    maximum_blocks = counter["maximum_blocks_generated_per_run"]
    total_blocks = counter["total_blocks_generated"]
    total_draws = counter["total_draws"]
    total_rejections = counter["total_rejected_blocks"]
    maximum_rejections_in_one_run = maximum_blocks - holdout_units
    if (
        bootstrap["cell_order"] != list(_AXES)
        or sum(bootstrap["cell_sizes"].values()) != holdout_units
        or bootstrap["draws_per_run"] != holdout_units
        or total_draws != run_count * holdout_units
        or total_blocks != total_draws + total_rejections
        or total_blocks > _COUNTER_ATTEMPTS_PER_DRAW * total_draws
        or maximum_blocks < holdout_units
        or maximum_blocks > _COUNTER_ATTEMPTS_PER_DRAW * holdout_units
        or maximum_blocks > total_blocks
        or (total_rejections == 0 and maximum_blocks != holdout_units)
        or (total_rejections > 0 and maximum_blocks == holdout_units)
        or total_rejections < maximum_rejections_in_one_run
        or total_rejections > run_count * maximum_rejections_in_one_run
        or sum(bootstrap["length_maximum_selections"].values()) != run_count
        or any(value > run_count for value in bootstrap["substitutions"].values())
    ):
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    rho_endpoint = value["endpoints"]["candidate_rho_lower"]
    delta_endpoint = value["endpoints"]["paired_delta_lower"]
    rho = _rho_from_payload(rho_endpoint["rho"])
    primary = _rho_from_payload(delta_endpoint["primary_rho"])
    length = _rho_from_payload(delta_endpoint["length_maximum"]["rho"])
    try:
        source = delta_endpoint["length_maximum"]["source"]
        if (
            not _is_candidate_endpoint_rho(rho)
            or not _is_candidate_endpoint_rho(primary)
            or not _is_selected_length_rho(length, source)
        ):
            raise ValueError
        zero = ExactRho.sentinel(0)
        if source == "zero":
            rebuilt = make_exact_paired_delta(primary, zero, zero)
        elif source == "l_total":
            rebuilt = make_exact_paired_delta(primary, length, zero)
        elif source == "l_distinct":
            rebuilt = make_exact_paired_delta(primary, zero, length)
        else:
            raise ValueError
    except (KeyError, TypeError, ValueError, NMFAExactOrderError):
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    if (
        rho_endpoint["run_index"] >= run_count
        or delta_endpoint["run_index"] >= run_count
        or rebuilt.length_maximum.rho != length
        or rebuilt.length_maximum.source.value != source
        or type(rho) is not ExactRho
        or bootstrap["length_maximum_selections"][source] == 0
        or (
            (rho.kind is ExactRhoKind.SENTINEL or primary.kind is ExactRhoKind.SENTINEL)
            and bootstrap["substitutions"]["candidate_to_negative_one"] == 0
        )
    ):
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    _require_unchanged_bundle(bundle_sha256)
    return cast(dict[str, Any], value)


def evaluate_nmfa_paired_bootstrap(
    full_roster_raw: bytes,
    expected_full_roster_raw_sha256: str,
    metric_roster_raw: bytes,
    expected_metric_roster_raw_sha256: str,
    selector_assignment_raw: bytes,
    expected_selector_assignment_raw_sha256: str,
    score_receipt_raw: bytes,
    expected_score_receipt_raw_sha256: str,
    target_receipt_raw: bytes,
    expected_target_receipt_raw_sha256: str,
    frozen_protocol_chain_head_sha256: str,
) -> ProtectedNMFABootstrapState:
    """Run the frozen paired H-cell bootstrap and return aggregate state only."""

    if not _is_checksum(frozen_protocol_chain_head_sha256):
        _fail(NMFAResamplingErrorCode.INVALID_ARGUMENT)
    bundle_sha256 = _validate_installed_bundle()
    _validate_predecessors()
    metric_roster, selector, score, target, _ = _selector_and_measurement_inputs(
        full_roster_raw,
        expected_full_roster_raw_sha256,
        metric_roster_raw,
        expected_metric_roster_raw_sha256,
        selector_assignment_raw,
        expected_selector_assignment_raw_sha256,
        score_receipt_raw,
        expected_score_receipt_raw_sha256,
        target_receipt_raw,
        expected_target_receipt_raw_sha256,
    )
    cells = _bootstrap_rows_by_cell(selector, score, target)
    cell_roster_sha256 = _cell_roster_sha256(selector)
    chain_head_key = bytes.fromhex(frozen_protocol_chain_head_sha256[7:])
    bootstrap, endpoints = _evaluate_runs(
        cells,
        chain_head_key,
        cell_roster_sha256,
        _BOOTSTRAP_RUNS,
        _LOWER_ENDPOINT_INDEX,
    )
    score_bindings = score["bindings"]
    target_bindings = target["bindings"]
    receipt = {
        "assurance_boundary": {
            "confirmatory_gate_evaluated": False,
            "external_chain_head_origin_verified": False,
            "external_receipt_or_roster_origin_verified": False,
            "process_custody_information_separation_enforced": False,
            "scientific_result": False,
        },
        "bindings": {
            "assignment_roster_sha256": metric_roster.full_roster.roster_sha256,
            "frozen_protocol_chain_head_sha256": frozen_protocol_chain_head_sha256,
            "gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
            "measurement_bundle_sha256": "sha256:" + _MEASUREMENT_BUNDLE_SHA256,
            "measurement_plan_sha256": "sha256:" + _MEASUREMENT_PLAN_SHA256,
            "metric_roster_raw_sha256": metric_roster.raw_sha256,
            "metric_roster_sha256": metric_roster.metric_roster_sha256,
            "model_sha256": score_bindings["model_sha256"],
            "parent_protocol_sha256": "sha256:" + _PARENT_PROTOCOL_SHA256,
            "resampling_bundle_sha256": bundle_sha256,
            "resampling_plan_sha256": "sha256:" + _PLAN_SHA256,
            "score_receipt_raw_sha256": expected_score_receipt_raw_sha256,
            "score_receipt_sha256": _measurement_domain_digest(
                _SCORE_RECEIPT_DOMAIN,
                score,
            ),
            "selector_assignment_raw_sha256": expected_selector_assignment_raw_sha256,
            "selector_bundle_sha256": "sha256:" + _SELECTOR_BUNDLE_SHA256,
            "selector_plan_sha256": "sha256:" + _SELECTOR_PLAN_SHA256,
            "target_contract_sha256": target_bindings["target_contract_sha256"],
            "target_receipt_raw_sha256": expected_target_receipt_raw_sha256,
            "target_receipt_sha256": _measurement_domain_digest(
                _TARGET_RECEIPT_DOMAIN,
                target,
            ),
        },
        "bootstrap": bootstrap,
        "claim_binding": metric_roster.full_roster.claim_binding,
        "compiled_blockers": list(_BLOCKERS),
        "endpoints": endpoints,
        "format_version": "1.0.0",
        "record_kind": "nmfa_protected_paired_bootstrap_state",
        "terminal_state": "EXACT_PAIRED_BOOTSTRAP_STATE_ONLY",
    }
    _validate_schema(
        receipt,
        _BOOTSTRAP_SCHEMA_PATH,
        NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID,
    )
    raw = encode_json(receipt)
    raw_sha256 = _sha256(raw)
    receipt_sha256 = _domain_digest(_BOOTSTRAP_RECEIPT_DOMAIN, receipt)
    _require_unchanged_bundle(bundle_sha256)
    return ProtectedNMFABootstrapState(
        receipt_bytes=raw,
        receipt_raw_sha256=raw_sha256,
        receipt_sha256=receipt_sha256,
        bundle_sha256=bundle_sha256,
        _token=_BOOTSTRAP_STATE_CONSTRUCTION_TOKEN,
    )


def verify_nmfa_bootstrap_receipt(
    full_roster_raw: bytes,
    expected_full_roster_raw_sha256: str,
    metric_roster_raw: bytes,
    expected_metric_roster_raw_sha256: str,
    selector_assignment_raw: bytes,
    expected_selector_assignment_raw_sha256: str,
    score_receipt_raw: bytes,
    expected_score_receipt_raw_sha256: str,
    target_receipt_raw: bytes,
    expected_target_receipt_raw_sha256: str,
    frozen_protocol_chain_head_sha256: str,
    bootstrap_receipt_raw: bytes,
) -> None:
    """Require exact bootstrap receipt equality after complete reexecution."""

    expected = evaluate_nmfa_paired_bootstrap(
        full_roster_raw,
        expected_full_roster_raw_sha256,
        metric_roster_raw,
        expected_metric_roster_raw_sha256,
        selector_assignment_raw,
        expected_selector_assignment_raw_sha256,
        score_receipt_raw,
        expected_score_receipt_raw_sha256,
        target_receipt_raw,
        expected_target_receipt_raw_sha256,
        frozen_protocol_chain_head_sha256,
    )
    if type(bootstrap_receipt_raw) is not bytes or bootstrap_receipt_raw != expected.receipt_bytes:
        _fail(NMFAResamplingErrorCode.BOOTSTRAP_RECEIPT_INVALID)
    _decode_bootstrap_receipt(
        bootstrap_receipt_raw,
        expected.receipt_raw_sha256,
        expected.bundle_sha256,
    )
    _require_unchanged_bundle(expected.bundle_sha256)
