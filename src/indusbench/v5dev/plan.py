"""Exact-byte verifier for the final development-only MTAAC V5 plan."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Final

V5_DEVELOPMENT_PLAN_ID: Final = "mtaac-v5-development-v1"
V5_DEVELOPMENT_PLAN_VERSION: Final = "mtaac-v5-development-v1"
V5_DEVELOPMENT_PLAN_SHA256: Final = (
    "sha256:3c4a7c733218fcd0c4e6e25fbd59e5b86c1fd589512e9a88bb243b1d036c10f1"
)
MAX_V5_DEVELOPMENT_PLAN_BYTES: Final = 16 * 1024

_EXPECTED_PLAN_BLAKE2B: Final = (
    "a9e76c1d5e4940c05c7eef541856255098dbbef818c6f59feb7154b6e884ab3ce"
    "ef3ac054735e442714261eb9c8fc9b1d235eab2d81a2a3516134232f0598d86"
)
_EXPECTED_SEMANTIC_SHA256: Final = (
    "fcfede9e42615a8cfbd1cd9952108ba208a60bf43718c6e2b601bb73d02ea523"
)
_EXPECTED_ROOT_KEYS: Final = frozenset(
    {
        "attempt_semantics",
        "data_boundary",
        "decision",
        "features",
        "folds",
        "implementation",
        "model",
        "nonclaims",
        "optimizer",
        "paired_v4_baseline",
        "parent_boundary",
        "profiles",
        "protocol_id",
        "protocol_status",
        "protocol_version",
        "report_contract",
        "task",
        "weighting",
    }
)


class V5DevelopmentPlanError(ValueError):
    """Raised when supplied plan bytes do not match the frozen V5 contract."""


class _StrictJsonError(ValueError):
    """Internal marker for JSON values rejected by the strict decoder."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJsonError("duplicate object key")
        result[key] = value
    return result


def _reject_nonfinite_constant(_value: str) -> None:
    raise _StrictJsonError("non-finite number")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _StrictJsonError("non-finite number")
    return parsed


def _strict_json(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
            parse_float=_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _StrictJsonError) as error:
        raise V5DevelopmentPlanError("development plan is not strict UTF-8 JSON") from error


def _semantic_sha256(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise V5DevelopmentPlanError("development plan has unsupported JSON values") from error
    return hashlib.sha256(raw).hexdigest()


def validate_v5_development_plan(plan_bytes: bytes) -> dict[str, Any]:
    """Verify the exact frozen bytes and every closed semantic field."""

    if not isinstance(plan_bytes, bytes):
        raise V5DevelopmentPlanError("development plan must be supplied as exact bytes")
    if not plan_bytes:
        raise V5DevelopmentPlanError("development plan is empty")
    if len(plan_bytes) > MAX_V5_DEVELOPMENT_PLAN_BYTES:
        raise V5DevelopmentPlanError("development plan exceeds the byte limit")
    actual_sha256 = f"sha256:{hashlib.sha256(plan_bytes).hexdigest()}"
    if actual_sha256 != V5_DEVELOPMENT_PLAN_SHA256:
        raise V5DevelopmentPlanError("development plan SHA-256 does not match the freeze")
    if hashlib.blake2b(plan_bytes).hexdigest() != _EXPECTED_PLAN_BLAKE2B:
        raise V5DevelopmentPlanError("development plan byte layout does not match the freeze")

    value = _strict_json(plan_bytes)
    if not isinstance(value, dict):
        raise V5DevelopmentPlanError("development plan JSON root must be an object")
    if set(value) != _EXPECTED_ROOT_KEYS:
        raise V5DevelopmentPlanError("development plan root does not match the closed contract")
    if _semantic_sha256(value) != _EXPECTED_SEMANTIC_SHA256:
        raise V5DevelopmentPlanError("development plan fields do not match the closed contract")
    if (
        value.get("protocol_id") != V5_DEVELOPMENT_PLAN_ID
        or value.get("protocol_version") != V5_DEVELOPMENT_PLAN_VERSION
        or value.get("protocol_status")
        != "development_only_post_v4_result_final_mtaac_attempt_before_reserved_source_execution"
    ):
        raise V5DevelopmentPlanError("development plan identity does not match the freeze")
    return value


__all__ = [
    "MAX_V5_DEVELOPMENT_PLAN_BYTES",
    "V5_DEVELOPMENT_PLAN_ID",
    "V5_DEVELOPMENT_PLAN_SHA256",
    "V5_DEVELOPMENT_PLAN_VERSION",
    "V5DevelopmentPlanError",
    "validate_v5_development_plan",
]
