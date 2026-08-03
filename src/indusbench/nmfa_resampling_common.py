"""Shared immutable contracts for the source-free NMFA resampling core.

This additive component accepts only separately digest-bound protected
receipts.  It authenticates neither their external origin nor a real frozen
protocol chain head, and it never reads sources, the network, a clock, or a
randomness provider.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import sys
from enum import StrEnum
from typing import Any, Never, cast

from indusbench.io import CorpusFormatError, decode_json, encode_json

__all__ = (
    "NMFAResamplingError",
    "NMFAResamplingErrorCode",
    "load_installed_nmfa_resampling_plan",
)

_PLAN_PATH = "benchmark/nmfa-resampling-core-plan-v1.json"
_BUNDLE_PATH = "benchmark/nmfa-resampling-core-evaluator-bundle-v1.json"
_PLAN_SCHEMA_PATH = "schemas/nmfa-resampling-core-plan.schema.json"
_BOOTSTRAP_SCHEMA_PATH = "schemas/nmfa-bootstrap-receipt.schema.json"
_SELECTOR_RECEIPT_SCHEMA_PATH = "schemas/nmfa-selector-receipt.schema.json"
_PARENT_PROTOCOL_PATH = "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
_GATE_PLAN_PATH = "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
_GATE_BUNDLE_PATH = "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"
_SELECTOR_PLAN_PATH = "benchmark/nmfa-selector-core-plan-v1.json"
_SELECTOR_BUNDLE_PATH = "benchmark/nmfa-selector-core-evaluator-bundle-v1.json"
_MEASUREMENT_PLAN_PATH = "benchmark/nmfa-measurement-core-plan-v1.json"
_MEASUREMENT_BUNDLE_PATH = "benchmark/nmfa-measurement-core-evaluator-bundle-v1.json"

_PARENT_PROTOCOL_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
_GATE_PLAN_SHA256 = "dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
_GATE_BUNDLE_SHA256 = "ec9ba6fbaa5df13dce438f819114206da2d6ca6e68afb521476635d5abd91a79"
_SELECTOR_PLAN_SHA256 = "f4c80a15804c4dffcef4f850d597f54836b44c3444af811f1c686814f39c5190"
_SELECTOR_BUNDLE_SHA256 = "c8aa0101a5e0396dbd7a577154302e1823235d31075bd2407247a8fbe0209eb6"
_MEASUREMENT_PLAN_SHA256 = "d7907ec8e9edbdd04e2904c8fc28007facf27c177e33994df20472025567e267"
_MEASUREMENT_BUNDLE_SHA256 = "c1b8d41cf6acc7edca9b9e0f0381fe309a2b862020d185d44b0df4f294e8ff12"
_PLAN_SHA256 = "0dc48fbfa188ce7bef6ce6a229fe9ea9639ff9ba607828ce4cda21ff3c3c0549"
_BUNDLE_CREATED_AT = "2026-08-03T12:18:41Z"

_MAX_JSON_BYTES = 67_108_864
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 2_000_000
_MAX_JSON_STRING_LENGTH = 16_384
_MAX_UNITS = 20_000
_CELL_MINIMUM = 20
_HOLDOUT_MINIMUM = 80
_BOOTSTRAP_RUNS = 10_000
_LOWER_ENDPOINT_INDEX = 249
_AXES = ("site", "period", "medium", "object_type")

_BOOTSTRAP_RECEIPT_DOMAIN = b"indusbench:nmfa:bootstrap-state:v1\x00"
_CELL_ROSTER_DOMAIN = b"indusbench:nmfa:bootstrap-cell-roster:v1\x00"
_SCHEDULE_DOMAIN = b"indusbench:nmfa:bootstrap-schedule:v1\x00"

_BLOCKERS = (
    "CLAIM_BINDING_ORIGIN_UNBOUND",
    "SELECTOR_ASSIGNMENT_ROSTER_ORIGIN_UNBOUND",
    "METRIC_ROSTER_ORIGIN_UNBOUND",
    "MODEL_DIGEST_ORIGIN_UNBOUND",
    "TARGET_CONTRACT_DIGEST_ORIGIN_UNBOUND",
    "X_BATCH_DIGEST_ORIGIN_UNBOUND",
    "Y_BATCH_DIGEST_ORIGIN_UNBOUND",
    "SCORE_RECEIPT_DIGEST_ORIGIN_UNBOUND",
    "TARGET_RECEIPT_DIGEST_ORIGIN_UNBOUND",
    "FROZEN_PROTOCOL_CHAIN_HEAD_ORIGIN_UNBOUND",
    "PROCESS_CUSTODY_INFORMATION_SEPARATION_UNBOUND",
    "X_SOURCE_PROJECTION_ORIGIN_UNBOUND",
    "Y_TARGET_PROVENANCE_ORIGIN_UNBOUND",
    "MODEL_SELECTION_AND_FREEZE_ORCHESTRATOR_UNBOUND",
    "N1_N2_RUNNER_UNBOUND",
    "CONFIRMATORY_GATE_ORCHESTRATOR_UNBOUND",
    "PROSPECTIVE_EVALUATOR_UNBOUND",
    "TERMINAL_ORCHESTRATOR_UNBOUND",
    "ACTIVATION_WRAPPER_UNBOUND",
    "COMPLETE_EXECUTION_BUNDLE_UNBOUND",
)

_EXPECTED_RUNTIME_PROFILE = {
    "canonical_encoder": "indusbench.io:encode_json",
    "dependencies": {"jsonschema": "4.26.0"},
    "dependency_requirement": "jsonschema[format]==4.26.0",
    "dependency_scope": "direct_declared_requirement_only_runtime_environment_not_attested",
    "entrypoints": [
        "indusbench.nmfa_resampling_common:load_installed_nmfa_resampling_plan",
        "indusbench.nmfa_counter_stream:nmfa_hmac_counter_block",
        "indusbench.nmfa_counter_stream:NMFACounterStream",
        "indusbench.nmfa_exact_order:compare_exact_rho",
        "indusbench.nmfa_exact_order:compare_exact_paired_delta",
        "indusbench.nmfa_bootstrap_core:evaluate_nmfa_paired_bootstrap",
        "indusbench.nmfa_bootstrap_core:verify_nmfa_bootstrap_receipt",
    ],
    "implementation": "CPython",
    "integer_arithmetic": "exact_bounded_integer_and_fraction_intermediates",
    "supported_python_minors": ["3.11", "3.12", "3.13", "3.14"],
}

_EXPECTED_SECURITY_BOUNDARY = {
    "activation_or_source_authority_included": False,
    "complete_execution_bundle": False,
    "external_chain_head_or_receipt_origin_verified": False,
    "network_clock_random_or_file_write_used": False,
    "protected_input_or_receipt_included": False,
    "real_source_or_target_values_included": False,
    "runtime_environment_attested": False,
    "scientific_result": False,
}

_RESOURCE_LOCKS: dict[str, tuple[int, str]] = {
    _BOOTSTRAP_SCHEMA_PATH: (
        14_904,
        "42b4f1073c1b230ba723b5e84d8f2fe7588b5e34641731df066f177837f6ac1a",
    ),
    _PLAN_PATH: (14_574, _PLAN_SHA256),
    _PLAN_SCHEMA_PATH: (
        15_441,
        "5233a22ffaf6bb4b4e7c9459184854452289fd445751e3e97700060104ad070a",
    ),
}

_BUNDLE_FILE_PATHS = frozenset(
    {
        _PLAN_PATH,
        _PLAN_SCHEMA_PATH,
        _BOOTSTRAP_SCHEMA_PATH,
        _SELECTOR_RECEIPT_SCHEMA_PATH,
        _PARENT_PROTOCOL_PATH,
        _GATE_PLAN_PATH,
        _GATE_BUNDLE_PATH,
        _SELECTOR_PLAN_PATH,
        _SELECTOR_BUNDLE_PATH,
        _MEASUREMENT_PLAN_PATH,
        _MEASUREMENT_BUNDLE_PATH,
        "src/indusbench/io.py",
        "src/indusbench/nmfa_bootstrap_core.py",
        "src/indusbench/nmfa_counter_stream.py",
        "src/indusbench/nmfa_exact_order.py",
        "src/indusbench/nmfa_measurement_common.py",
        "src/indusbench/nmfa_rank_statistics_core.py",
        "src/indusbench/nmfa_resampling_common.py",
        "src/indusbench/nmfa_x_model_core.py",
        "src/indusbench/nmfa_y_rational_core.py",
    }
)


class NMFAResamplingErrorCode(StrEnum):
    """Stable path-free failures for the exact resampling component."""

    BOOTSTRAP_RECEIPT_INVALID = "BOOTSTRAP_RECEIPT_INVALID"
    COMPUTATION_LIMIT_BLOCKED = "COMPUTATION_LIMIT_BLOCKED"
    COUNTER_STREAM_INVALID = "COUNTER_STREAM_INVALID"
    EXACT_ORDER_INVALID = "EXACT_ORDER_INVALID"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    PACKAGE_RESOURCE_INVALID = "PACKAGE_RESOURCE_INVALID"
    ROSTER_MISMATCH = "ROSTER_MISMATCH"
    SCHEMA_DEPENDENCY_MISSING = "SCHEMA_DEPENDENCY_MISSING"
    SCORE_RECEIPT_INVALID = "SCORE_RECEIPT_INVALID"
    SELECTOR_ASSIGNMENT_INVALID = "SELECTOR_ASSIGNMENT_INVALID"
    TARGET_RECEIPT_INVALID = "TARGET_RECEIPT_INVALID"


class NMFAResamplingError(ValueError):
    """Fixed-code exception that never interpolates protected input."""

    def __init__(self, code: NMFAResamplingErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _fail(code: NMFAResamplingErrorCode) -> Never:
    raise NMFAResamplingError(code)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _domain_digest(domain: bytes, value: Any) -> str:
    return _sha256(domain + encode_json(value))


def _is_checksum(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _raw_sha256_matches(raw: object, expected_raw_sha256: str) -> bool:
    return (
        type(raw) is bytes
        and 0 < len(raw) <= _MAX_JSON_BYTES
        and _sha256(raw) == expected_raw_sha256
    )


def _json_shape(value: Any) -> tuple[int, int, int]:
    nodes = 0
    depth = 0
    longest = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        node, node_depth = stack.pop()
        nodes += 1
        depth = max(depth, node_depth)
        if nodes > _MAX_JSON_NODES or depth > _MAX_JSON_DEPTH:
            break
        if type(node) is dict:
            for key, child in node.items():
                longest = max(longest, len(key))
                stack.append((child, node_depth + 1))
        elif type(node) is list:
            stack.extend((child, node_depth + 1) for child in node)
        elif type(node) is str:
            longest = max(longest, len(node))
        elif type(node) is int:
            if node < -(1 << 63) or node > (1 << 63) - 1:
                return _MAX_JSON_NODES + 1, _MAX_JSON_DEPTH + 1, _MAX_JSON_STRING_LENGTH + 1
        elif type(node) not in (bool, type(None)):
            return _MAX_JSON_NODES + 1, _MAX_JSON_DEPTH + 1, _MAX_JSON_STRING_LENGTH + 1
    return nodes, depth, longest


def _decode_canonical_json(raw: bytes, error_code: NMFAResamplingErrorCode) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_JSON_BYTES:
        _fail(error_code)
    try:
        value = decode_json(raw)
    except (CorpusFormatError, OverflowError, RecursionError, ValueError):
        _fail(error_code)
    nodes, depth, longest = _json_shape(value)
    try:
        canonical = encode_json(value)
    except (OverflowError, RecursionError, TypeError, UnicodeEncodeError, ValueError):
        _fail(error_code)
    if (
        nodes > _MAX_JSON_NODES
        or depth > _MAX_JSON_DEPTH
        or longest > _MAX_JSON_STRING_LENGTH
        or canonical != raw
    ):
        _fail(error_code)
    return value


def _package_root():
    try:
        return importlib.resources.files("indusbench")
    except (AttributeError, ModuleNotFoundError):
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)


def _resource_bytes(path: str) -> bytes:
    try:
        raw = _package_root().joinpath(*path.split("/")).read_bytes()
    except (FileNotFoundError, OSError, TypeError):
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    locked = _RESOURCE_LOCKS.get(path)
    if locked is not None and (
        len(raw) != locked[0] or hashlib.sha256(raw).hexdigest() != locked[1]
    ):
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    return raw


def _validate_schema(
    value: Any,
    schema_path: str,
    error_code: NMFAResamplingErrorCode,
) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        _fail(NMFAResamplingErrorCode.SCHEMA_DEPENDENCY_MISSING)
    try:
        schema = decode_json(_resource_bytes(schema_path))
        Draft202012Validator.check_schema(schema)
        first_error = next(Draft202012Validator(schema).iter_errors(value), None)
    except Exception as error:
        if isinstance(error, NMFAResamplingError):
            raise
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    if first_error is not None:
        _fail(error_code)


def _bundle_member_bytes(path: str) -> bytes:
    prefix = "src/indusbench/"
    return _resource_bytes(path[len(prefix) :] if path.startswith(prefix) else path)


def _validate_installed_bundle() -> str:
    raw = _resource_bytes(_BUNDLE_PATH)
    bundle = _decode_canonical_json(raw, NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    if (
        type(bundle) is not dict
        or set(bundle)
        != {
            "bundle_id",
            "created_at",
            "files",
            "format_version",
            "runtime_profile",
            "security_boundary",
        }
        or bundle["bundle_id"] != "nmfa-resampling-core-evaluator-bundle-v1"
        or bundle["created_at"] != _BUNDLE_CREATED_AT
        or bundle["format_version"] != "1.0.0"
        or type(bundle["files"]) is not list
        or bundle["runtime_profile"] != _EXPECTED_RUNTIME_PROFILE
        or bundle["security_boundary"] != _EXPECTED_SECURITY_BOUNDARY
    ):
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_paths = sorted(_BUNDLE_FILE_PATHS)
    if len(bundle["files"]) != len(expected_paths):
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    for expected_path, row in zip(expected_paths, bundle["files"], strict=True):
        if (
            type(row) is not dict
            or set(row) != {"bytes", "path", "sha256", "verification"}
            or type(row["bytes"]) is not int
            or row["bytes"] < 1
            or row["path"] != expected_path
            or not _is_checksum(row["sha256"])
            or row["verification"] != "runtime_and_ci"
        ):
            _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    for row in bundle["files"]:
        member = _bundle_member_bytes(row["path"])
        if len(member) != row["bytes"] or _sha256(member) != row["sha256"]:
            _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    if (
        sys.implementation.name != "cpython"
        or f"{sys.version_info.major}.{sys.version_info.minor}"
        not in _EXPECTED_RUNTIME_PROFILE["supported_python_minors"]
    ):
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    try:
        version = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    if version != _EXPECTED_RUNTIME_PROFILE["dependencies"]["jsonschema"]:
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    return _sha256(raw)


def _require_unchanged_bundle(bundle_sha256: str) -> None:
    if _validate_installed_bundle() != bundle_sha256:
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)


def _validate_predecessors() -> None:
    expected = {
        _PARENT_PROTOCOL_PATH: _PARENT_PROTOCOL_SHA256,
        _GATE_PLAN_PATH: _GATE_PLAN_SHA256,
        _GATE_BUNDLE_PATH: _GATE_BUNDLE_SHA256,
        _SELECTOR_PLAN_PATH: _SELECTOR_PLAN_SHA256,
        _SELECTOR_BUNDLE_PATH: _SELECTOR_BUNDLE_SHA256,
        _MEASUREMENT_PLAN_PATH: _MEASUREMENT_PLAN_SHA256,
        _MEASUREMENT_BUNDLE_PATH: _MEASUREMENT_BUNDLE_SHA256,
    }
    for path, digest in expected.items():
        if hashlib.sha256(_resource_bytes(path)).hexdigest() != digest:
            _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)


def _decode_selector_assignment(raw: bytes, expected_raw_sha256: str) -> dict[str, Any]:
    if not _is_checksum(expected_raw_sha256) or not _raw_sha256_matches(raw, expected_raw_sha256):
        _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    value = _decode_canonical_json(raw, NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    if type(value) is not dict:
        _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    _validate_schema(
        value,
        _SELECTOR_RECEIPT_SCHEMA_PATH,
        NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID,
    )
    if value["bindings"]["selector_bundle_sha256"] != "sha256:" + _SELECTOR_BUNDLE_SHA256:
        _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    rows = value["assignments"]
    keys = [(row["g_id"], row["primary_f_id"]) for row in rows]
    if (
        len(rows) > _MAX_UNITS
        or keys != sorted(keys)
        or len(keys) != len(set(keys))
        or len({key[0] for key in keys}) != len(keys)
        or len({key[1] for key in keys}) != len(keys)
    ):
        _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    counts = {axis: 0 for axis in _AXES}
    for row in rows:
        if row["partition"] == "holdout":
            if row["cell"] not in counts:
                _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
            counts[row["cell"]] += 1
        elif row["cell"] is not None:
            _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    if (
        any(count < _CELL_MINIMUM for count in counts.values())
        or sum(counts.values()) < _HOLDOUT_MINIMUM
    ):
        _fail(NMFAResamplingErrorCode.SELECTOR_ASSIGNMENT_INVALID)
    return cast(dict[str, Any], value)


def load_installed_nmfa_resampling_plan() -> dict[str, Any]:
    """Load and fully revalidate the installed exact bootstrap plan."""

    bundle_sha256 = _validate_installed_bundle()
    _validate_predecessors()
    raw = _resource_bytes(_PLAN_PATH)
    value = _decode_canonical_json(raw, NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    if type(value) is not dict or _sha256(raw) != "sha256:" + _PLAN_SHA256:
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    _validate_schema(
        value,
        _PLAN_SCHEMA_PATH,
        NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID,
    )
    if tuple(value["compiled_blockers"]) != _BLOCKERS:
        _fail(NMFAResamplingErrorCode.PACKAGE_RESOURCE_INVALID)
    _require_unchanged_bundle(bundle_sha256)
    return cast(dict[str, Any], value)
