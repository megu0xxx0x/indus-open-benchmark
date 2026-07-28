"""Exact-byte verifier for the development-only MTAAC V4 plan."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Final

V4_DEVELOPMENT_PLAN_ID: Final = "mtaac-v4-development-v1"
V4_DEVELOPMENT_PLAN_VERSION: Final = "mtaac-v4-development-v1"
V4_DEVELOPMENT_PLAN_SHA256: Final = (
    "sha256:604725a5929b63f578ade07b65ca784eefefefce9b827e1686d4836f668c123b"
)
MAX_V4_DEVELOPMENT_PLAN_BYTES: Final = 16 * 1024

_EXPECTED_PLAN_BLAKE2B: Final = (
    "4c1f254931e390f2c9f8fa44a903001c723481670ed39edb435537c6fa2438ba"
    "b04dd24ebe8adbd7289cafb13d4dff78eae11f21b8918a59c26952c44109e117"
)
_EXPECTED_SEMANTIC_SHA256: Final = (
    "6666d5a5da92eada7b98a57374b790baff1b16997bef97e003675bde0ed6f49a"
)
_EXPECTED_ROOT_KEYS: Final = frozenset(
    {
        "data_boundary",
        "decision",
        "diagnostics",
        "features",
        "folds",
        "implementation",
        "model",
        "nonclaims",
        "optimizer",
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


class V4DevelopmentPlanError(ValueError):
    """Raised when supplied plan bytes do not match the frozen V4 contract."""


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
        raise V4DevelopmentPlanError("development plan is not strict UTF-8 JSON") from error


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
        raise V4DevelopmentPlanError("development plan has unsupported JSON values") from error
    return hashlib.sha256(raw).hexdigest()


def validate_v4_development_plan(plan_bytes: bytes) -> dict[str, Any]:
    """Verify the exact frozen bytes and every closed semantic field."""

    if not isinstance(plan_bytes, bytes):
        raise V4DevelopmentPlanError("development plan must be supplied as exact bytes")
    if not plan_bytes:
        raise V4DevelopmentPlanError("development plan is empty")
    if len(plan_bytes) > MAX_V4_DEVELOPMENT_PLAN_BYTES:
        raise V4DevelopmentPlanError("development plan exceeds the byte limit")
    actual_sha256 = f"sha256:{hashlib.sha256(plan_bytes).hexdigest()}"
    if actual_sha256 != V4_DEVELOPMENT_PLAN_SHA256:
        raise V4DevelopmentPlanError("development plan SHA-256 does not match the freeze")
    if hashlib.blake2b(plan_bytes).hexdigest() != _EXPECTED_PLAN_BLAKE2B:
        raise V4DevelopmentPlanError("development plan byte layout does not match the freeze")

    value = _strict_json(plan_bytes)
    if not isinstance(value, dict):
        raise V4DevelopmentPlanError("development plan JSON root must be an object")
    if set(value) != _EXPECTED_ROOT_KEYS:
        raise V4DevelopmentPlanError("development plan root does not match the closed contract")
    if _semantic_sha256(value) != _EXPECTED_SEMANTIC_SHA256:
        raise V4DevelopmentPlanError("development plan fields do not match the closed contract")
    if (
        value.get("protocol_id") != V4_DEVELOPMENT_PLAN_ID
        or value.get("protocol_version") != V4_DEVELOPMENT_PLAN_VERSION
        or value.get("protocol_status")
        != "development_only_post_v3_result_before_reserved_source_execution"
    ):
        raise V4DevelopmentPlanError("development plan identity does not match the freeze")
    return value


__all__ = [
    "MAX_V4_DEVELOPMENT_PLAN_BYTES",
    "V4_DEVELOPMENT_PLAN_ID",
    "V4_DEVELOPMENT_PLAN_SHA256",
    "V4_DEVELOPMENT_PLAN_VERSION",
    "V4DevelopmentPlanError",
    "validate_v4_development_plan",
]
