"""Shared closed contracts for the source-free NMFA numeric core.

The X scorer and Y normalizer deliberately live in separate modules and do
not import one another.  This module contains only resource validation,
canonical JSON limits, and the value-free G/F roster contracts shared by both
surfaces.  It performs no source access, network operation, clock read,
random draw, or file write.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Never, cast

from indusbench.io import CorpusFormatError, decode_json, encode_json

__all__ = (
    "NMFAMeasurementError",
    "NMFAMeasurementErrorCode",
    "ValidatedNMFAGFRoster",
    "ValidatedNMFAMetricRoster",
    "load_installed_nmfa_measurement_plan",
    "validate_nmfa_gf_roster",
    "validate_nmfa_metric_roster",
)

_PLAN_PATH = "benchmark/nmfa-measurement-core-plan-v1.json"
_BUNDLE_PATH = "benchmark/nmfa-measurement-core-evaluator-bundle-v1.json"
_PLAN_SCHEMA_PATH = "schemas/nmfa-measurement-core-plan.schema.json"
_GF_ROSTER_SCHEMA_PATH = "schemas/nmfa-gf-roster.schema.json"
_METRIC_ROSTER_SCHEMA_PATH = "schemas/nmfa-metric-roster.schema.json"
_X_SCHEMA_PATH = "schemas/nmfa-x-batch.schema.json"
_Y_SCHEMA_PATH = "schemas/nmfa-y-batch.schema.json"
_SCORE_SCHEMA_PATH = "schemas/nmfa-score-receipt.schema.json"
_TARGET_SCHEMA_PATH = "schemas/nmfa-target-receipt.schema.json"
_METRIC_SCHEMA_PATH = "schemas/nmfa-metric-receipt.schema.json"
_PARENT_PROTOCOL_PATH = "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
_GATE_PLAN_PATH = "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
_SELECTOR_PLAN_PATH = "benchmark/nmfa-selector-core-plan-v1.json"
_SELECTOR_BUNDLE_PATH = "benchmark/nmfa-selector-core-evaluator-bundle-v1.json"

_PARENT_PROTOCOL_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
_GATE_PLAN_SHA256 = "dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
_SELECTOR_PLAN_SHA256 = "f4c80a15804c4dffcef4f850d597f54836b44c3444af811f1c686814f39c5190"
_SELECTOR_BUNDLE_SHA256 = "c8aa0101a5e0396dbd7a577154302e1823235d31075bd2407247a8fbe0209eb6"
_PLAN_SHA256 = "d7907ec8e9edbdd04e2904c8fc28007facf27c177e33994df20472025567e267"
_BUNDLE_CREATED_AT = "2026-08-03T01:10:01Z"

_MAX_JSON_BYTES = 67_108_864
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 2_000_000
_MAX_JSON_STRING_LENGTH = 16_384
_MIN_FULL_ASSIGNMENT_UNITS = 160
_MAX_UNITS = 20_000

_ROSTER_DOMAIN = b"indusbench:nmfa:assignment-roster:v1\x00"
_METRIC_ROSTER_DOMAIN = b"indusbench:nmfa:metric-roster:v1\x00"

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
    "PROCESS_CUSTODY_INFORMATION_SEPARATION_UNBOUND",
    "X_SOURCE_PROJECTION_ORIGIN_UNBOUND",
    "Y_TARGET_PROVENANCE_ORIGIN_UNBOUND",
    "MODEL_SELECTION_AND_FREEZE_ORCHESTRATOR_UNBOUND",
    "MULTIRADICAL_DELTA_ORDERING_UNBOUND",
    "HMAC_COUNTER_STREAM_UNBOUND",
    "BOOTSTRAP_RUNNER_UNBOUND",
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
        "indusbench.nmfa_measurement_common:load_installed_nmfa_measurement_plan",
        "indusbench.nmfa_measurement_common:validate_nmfa_gf_roster",
        "indusbench.nmfa_measurement_common:validate_nmfa_metric_roster",
        "indusbench.nmfa_x_model_core:score_nmfa_x_batch",
        "indusbench.nmfa_x_model_core:verify_nmfa_score_receipt",
        "indusbench.nmfa_y_rational_core:normalize_nmfa_y_batch",
        "indusbench.nmfa_y_rational_core:verify_nmfa_target_receipt",
        "indusbench.nmfa_rank_statistics_core:evaluate_nmfa_rank_metrics",
        "indusbench.nmfa_rank_statistics_core:doubled_midranks_integers",
        "indusbench.nmfa_rank_statistics_core:exact_nmfa_spearman_at_least",
        "indusbench.nmfa_rank_statistics_core:verify_nmfa_metric_receipt",
    ],
    "implementation": "CPython",
    "integer_arithmetic": "checked_inputs_and_arbitrary_precision_intermediates",
    "supported_python_minors": ["3.11", "3.12", "3.13", "3.14"],
}

_EXPECTED_SECURITY_BOUNDARY = {
    "activation_or_source_authority_included": False,
    "complete_execution_bundle": False,
    "external_roster_or_digest_origin_verified": False,
    "network_clock_random_or_file_write_used": False,
    "protected_input_or_receipt_included": False,
    "real_source_or_target_values_included": False,
    "runtime_environment_attested": False,
    "scientific_result": False,
}

_RESOURCE_LOCKS: dict[str, tuple[int, str]] = {
    _PLAN_PATH: (14_270, "d7907ec8e9edbdd04e2904c8fc28007facf27c177e33994df20472025567e267"),
    _PLAN_SCHEMA_PATH: (
        15_152,
        "2e2e99e4971de9383edb4c314239b5506b80a97fe726096527b52ed940fdb531",
    ),
    _GF_ROSTER_SCHEMA_PATH: (
        2_735,
        "494b004262467247cf1dcec068347d9fc8d814533b3b009750c0913508830a68",
    ),
    _METRIC_ROSTER_SCHEMA_PATH: (
        2_426,
        "90d191ce2fd4aef6778f9f16c28d0bc9e90f065f3e45c9531924edf810bab564",
    ),
    _X_SCHEMA_PATH: (7_629, "2ef23e518e906c2c127025ffdf6188be6fbcbaade533d95e533f1f8c0ff92393"),
    _Y_SCHEMA_PATH: (5_910, "3ccb7df6c1491fbc50c244d341290707a9a87010e9cf5391ff6a67c54b616968"),
    _SCORE_SCHEMA_PATH: (
        6_349,
        "9b8cf85f3605661acb86108d173d6b38f3f066b3b68ff7e0fcf809f63171473a",
    ),
    _TARGET_SCHEMA_PATH: (
        6_734,
        "02c34a9557402d83df41d26c49d023f86ad965ca4dcd457e0f86c5ab419c8093",
    ),
    _METRIC_SCHEMA_PATH: (
        11_250,
        "88b22ee0c495f906977fa2d575ef0ad8ba67ae198d8df11e7212676f652e8f4a",
    ),
}

_BUNDLE_FILE_PATHS = frozenset(
    {
        _PLAN_PATH,
        _GATE_PLAN_PATH,
        _PARENT_PROTOCOL_PATH,
        _SELECTOR_BUNDLE_PATH,
        _SELECTOR_PLAN_PATH,
        _PLAN_SCHEMA_PATH,
        _GF_ROSTER_SCHEMA_PATH,
        _METRIC_ROSTER_SCHEMA_PATH,
        _X_SCHEMA_PATH,
        _Y_SCHEMA_PATH,
        _SCORE_SCHEMA_PATH,
        _TARGET_SCHEMA_PATH,
        _METRIC_SCHEMA_PATH,
        "src/indusbench/io.py",
        "src/indusbench/nmfa_measurement_common.py",
        "src/indusbench/nmfa_rank_statistics_core.py",
        "src/indusbench/nmfa_x_model_core.py",
        "src/indusbench/nmfa_y_rational_core.py",
    }
)


class NMFAMeasurementErrorCode(StrEnum):
    """Stable path-free errors for all three numeric subcomponents."""

    COMPUTATION_LIMIT_BLOCKED = "COMPUTATION_LIMIT_BLOCKED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    METRIC_RECEIPT_INVALID = "METRIC_RECEIPT_INVALID"
    METRIC_ROSTER_CONTRACT_INVALID = "METRIC_ROSTER_CONTRACT_INVALID"
    MODEL_CONTRACT_INVALID = "MODEL_CONTRACT_INVALID"
    PACKAGE_RESOURCE_INVALID = "PACKAGE_RESOURCE_INVALID"
    ROSTER_CONTRACT_INVALID = "ROSTER_CONTRACT_INVALID"
    ROSTER_MISMATCH = "ROSTER_MISMATCH"
    SCHEMA_DEPENDENCY_MISSING = "SCHEMA_DEPENDENCY_MISSING"
    SCORE_RECEIPT_INVALID = "SCORE_RECEIPT_INVALID"
    TARGET_CONTRACT_INVALID = "TARGET_CONTRACT_INVALID"
    TARGET_RECEIPT_INVALID = "TARGET_RECEIPT_INVALID"
    X_CONTRACT_INVALID = "X_CONTRACT_INVALID"
    Y_CONTRACT_INVALID = "Y_CONTRACT_INVALID"


class NMFAMeasurementError(ValueError):
    """Fixed-code exception that never interpolates protected input."""

    def __init__(self, code: NMFAMeasurementErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, repr=False)
class ValidatedNMFAGFRoster:
    """Canonical value-free full assignment roster."""

    canonical_bytes: bytes
    raw_sha256: str
    roster_sha256: str
    selector_assignment_raw_sha256: str
    claim_binding: dict[str, str]
    rows: tuple[tuple[str, str], ...]
    bundle_sha256: str

    def __repr__(self) -> str:
        return "<ValidatedNMFAGFRoster protected>"


@dataclass(frozen=True, repr=False)
class ValidatedNMFAMetricRoster:
    """Canonical protected metric subset, without partition or cell labels."""

    canonical_bytes: bytes
    raw_sha256: str
    metric_roster_sha256: str
    rows: tuple[tuple[str, str], ...]
    full_roster: ValidatedNMFAGFRoster

    def __repr__(self) -> str:
        return "<ValidatedNMFAMetricRoster protected>"


def _fail(code: NMFAMeasurementErrorCode) -> Never:
    raise NMFAMeasurementError(code)


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
                return (
                    _MAX_JSON_NODES + 1,
                    _MAX_JSON_DEPTH + 1,
                    _MAX_JSON_STRING_LENGTH + 1,
                )
        elif type(node) not in (bool, type(None)):
            return _MAX_JSON_NODES + 1, _MAX_JSON_DEPTH + 1, _MAX_JSON_STRING_LENGTH + 1
    return nodes, depth, longest


def _decode_canonical_json(raw: bytes, error_code: NMFAMeasurementErrorCode) -> Any:
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
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)


def _resource_bytes(path: str) -> bytes:
    try:
        raw = _package_root().joinpath(*path.split("/")).read_bytes()
    except (FileNotFoundError, OSError, TypeError):
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    locked = _RESOURCE_LOCKS.get(path)
    if locked is not None and (
        len(raw) != locked[0] or hashlib.sha256(raw).hexdigest() != locked[1]
    ):
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    return raw


def _validate_schema(
    value: Any,
    schema_path: str,
    error_code: NMFAMeasurementErrorCode,
) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        _fail(NMFAMeasurementErrorCode.SCHEMA_DEPENDENCY_MISSING)
    try:
        schema = decode_json(_resource_bytes(schema_path))
        Draft202012Validator.check_schema(schema)
        first_error = next(Draft202012Validator(schema).iter_errors(value), None)
    except Exception as error:
        if isinstance(error, NMFAMeasurementError):
            raise
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    if first_error is not None:
        _fail(error_code)


def _bundle_member_bytes(path: str) -> bytes:
    prefix = "src/indusbench/"
    return _resource_bytes(path[len(prefix) :] if path.startswith(prefix) else path)


def _validate_installed_bundle() -> str:
    raw = _resource_bytes(_BUNDLE_PATH)
    bundle = _decode_canonical_json(raw, NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
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
        or bundle["bundle_id"] != "nmfa-measurement-core-evaluator-bundle-v1"
        or bundle["created_at"] != _BUNDLE_CREATED_AT
        or bundle["format_version"] != "1.0.0"
        or type(bundle["files"]) is not list
        or bundle["runtime_profile"] != _EXPECTED_RUNTIME_PROFILE
        or bundle["security_boundary"] != _EXPECTED_SECURITY_BOUNDARY
    ):
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_paths = sorted(_BUNDLE_FILE_PATHS)
    if len(bundle["files"]) != len(expected_paths):
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
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
            _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    for row in bundle["files"]:
        member = _bundle_member_bytes(row["path"])
        if len(member) != row["bytes"] or _sha256(member) != row["sha256"]:
            _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    if (
        sys.implementation.name != "cpython"
        or f"{sys.version_info.major}.{sys.version_info.minor}"
        not in _EXPECTED_RUNTIME_PROFILE["supported_python_minors"]
    ):
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    try:
        jsonschema_version = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    if jsonschema_version != _EXPECTED_RUNTIME_PROFILE["dependencies"]["jsonschema"]:
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    return _sha256(raw)


def _validate_static_bindings(value: dict[str, Any]) -> None:
    expected = {
        _PARENT_PROTOCOL_PATH: _PARENT_PROTOCOL_SHA256,
        _GATE_PLAN_PATH: _GATE_PLAN_SHA256,
        _SELECTOR_PLAN_PATH: _SELECTOR_PLAN_SHA256,
        _SELECTOR_BUNDLE_PATH: _SELECTOR_BUNDLE_SHA256,
        _PLAN_PATH: _PLAN_SHA256,
    }
    for path, digest in expected.items():
        if hashlib.sha256(_resource_bytes(path)).hexdigest() != digest:
            _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    checks = {
        "gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
        "measurement_plan_sha256": "sha256:" + _PLAN_SHA256,
        "parent_protocol_sha256": "sha256:" + _PARENT_PROTOCOL_SHA256,
        "selector_plan_sha256": "sha256:" + _SELECTOR_PLAN_SHA256,
    }
    for key, expected_value in checks.items():
        if key in value and value[key] != expected_value:
            _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)


def _require_unchanged_bundle(bundle_sha256: str) -> None:
    if _validate_installed_bundle() != bundle_sha256:
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)


def load_installed_nmfa_measurement_plan() -> dict[str, Any]:
    """Load and fully revalidate the installed exact numeric-core plan."""

    bundle_sha256 = _validate_installed_bundle()
    raw = _resource_bytes(_PLAN_PATH)
    value = _decode_canonical_json(raw, NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    if type(value) is not dict or _sha256(raw) != "sha256:" + _PLAN_SHA256:
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    _validate_schema(
        value,
        _PLAN_SCHEMA_PATH,
        NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID,
    )
    _validate_static_bindings(value["bindings"])
    if tuple(value["compiled_blockers"]) != _BLOCKERS:
        _fail(NMFAMeasurementErrorCode.PACKAGE_RESOURCE_INVALID)
    _require_unchanged_bundle(bundle_sha256)
    return cast(dict[str, Any], value)


def validate_nmfa_gf_roster(
    raw: bytes,
    expected_roster_raw_sha256: str,
) -> ValidatedNMFAGFRoster:
    """Validate the full value-free G/F roster against a separate raw digest."""

    if not _is_checksum(expected_roster_raw_sha256):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    bundle_sha256 = _validate_installed_bundle()
    if not _raw_sha256_matches(raw, expected_roster_raw_sha256):
        _fail(NMFAMeasurementErrorCode.ROSTER_CONTRACT_INVALID)
    value = _decode_canonical_json(raw, NMFAMeasurementErrorCode.ROSTER_CONTRACT_INVALID)
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.ROSTER_CONTRACT_INVALID)
    _validate_schema(
        value,
        _GF_ROSTER_SCHEMA_PATH,
        NMFAMeasurementErrorCode.ROSTER_CONTRACT_INVALID,
    )
    _validate_static_bindings(value)
    rows = tuple((row["g_id"], row["primary_f_id"]) for row in value["rows"])
    g_ids = tuple(row[0] for row in rows)
    primary_f_ids = tuple(row[1] for row in rows)
    if (
        len(rows) < _MIN_FULL_ASSIGNMENT_UNITS
        or len(rows) > _MAX_UNITS
        or rows != tuple(sorted(rows))
        or len(rows) != len(set(rows))
        or len(g_ids) != len(set(g_ids))
        or len(primary_f_ids) != len(set(primary_f_ids))
    ):
        _fail(NMFAMeasurementErrorCode.ROSTER_CONTRACT_INVALID)
    roster_sha256 = _domain_digest(_ROSTER_DOMAIN, {"rows": value["rows"]})
    result = ValidatedNMFAGFRoster(
        canonical_bytes=raw,
        raw_sha256=expected_roster_raw_sha256,
        roster_sha256=roster_sha256,
        selector_assignment_raw_sha256=value["selector_assignment_raw_sha256"],
        claim_binding=dict(value["claim_binding"]),
        rows=rows,
        bundle_sha256=bundle_sha256,
    )
    _require_unchanged_bundle(bundle_sha256)
    return result


def validate_nmfa_metric_roster(
    full_roster_raw: bytes,
    expected_full_roster_raw_sha256: str,
    metric_roster_raw: bytes,
    expected_metric_roster_raw_sha256: str,
) -> ValidatedNMFAMetricRoster:
    """Validate a separately declared ordered subset of the full G/F roster."""

    if not _is_checksum(expected_metric_roster_raw_sha256):
        _fail(NMFAMeasurementErrorCode.INVALID_ARGUMENT)
    full = validate_nmfa_gf_roster(full_roster_raw, expected_full_roster_raw_sha256)
    if not _raw_sha256_matches(metric_roster_raw, expected_metric_roster_raw_sha256):
        _fail(NMFAMeasurementErrorCode.METRIC_ROSTER_CONTRACT_INVALID)
    value = _decode_canonical_json(
        metric_roster_raw,
        NMFAMeasurementErrorCode.METRIC_ROSTER_CONTRACT_INVALID,
    )
    if type(value) is not dict:
        _fail(NMFAMeasurementErrorCode.METRIC_ROSTER_CONTRACT_INVALID)
    _validate_schema(
        value,
        _METRIC_ROSTER_SCHEMA_PATH,
        NMFAMeasurementErrorCode.METRIC_ROSTER_CONTRACT_INVALID,
    )
    if (
        value["assignment_roster_raw_sha256"] != full.raw_sha256
        or value["assignment_roster_sha256"] != full.roster_sha256
        or value["claim_binding"] != full.claim_binding
        or value["selector_assignment_raw_sha256"] != full.selector_assignment_raw_sha256
    ):
        _fail(NMFAMeasurementErrorCode.ROSTER_MISMATCH)
    rows = tuple((row["g_id"], row["primary_f_id"]) for row in value["rows"])
    selected = set(rows)
    expected_order = tuple(row for row in full.rows if row in selected)
    if (
        not rows
        or len(rows) != len(selected)
        or rows != tuple(sorted(rows))
        or rows != expected_order
    ):
        _fail(NMFAMeasurementErrorCode.METRIC_ROSTER_CONTRACT_INVALID)
    metric_digest = _domain_digest(
        _METRIC_ROSTER_DOMAIN,
        {
            "assignment_roster_sha256": full.roster_sha256,
            "rows": value["rows"],
        },
    )
    result = ValidatedNMFAMetricRoster(
        canonical_bytes=metric_roster_raw,
        raw_sha256=expected_metric_roster_raw_sha256,
        metric_roster_sha256=metric_digest,
        rows=rows,
        full_roster=full,
    )
    _require_unchanged_bundle(full.bundle_sha256)
    return result
