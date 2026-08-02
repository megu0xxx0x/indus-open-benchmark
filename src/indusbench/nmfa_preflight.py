"""Signed, source-free activation preflight for the NMFA experiment.

The evaluator reads only packaged public contracts, a separately supplied trust
profile plus caller-expected digest, and caller-supplied canonical JSON bytes.
It has no private key and performs no network access, write, random draw,
wall-clock read, protected source access, value access, execution, registration,
or scientific scoring.

The installed V1 companion intentionally has five compiled blockers.  It can
therefore validate contracts and detached signatures, but it cannot issue a
real PREMETADATA_READY or PREVALUE_READY decision.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.metadata
import importlib.resources
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Never, cast

from indusbench.io import encode_json

_PLAN_PATH = "benchmark/nmfa-activation-preflight-plan-v1.json"
_BUNDLE_PATH = "benchmark/nmfa-activation-preflight-evaluator-bundle-v1.json"
_PLAN_SCHEMA_PATH = "schemas/nmfa-activation-preflight-plan.schema.json"
_TRUST_SCHEMA_PATH = "schemas/nmfa-external-trust-profile.schema.json"
_REQUEST_SCHEMA_PATH = "schemas/nmfa-activation-preflight-request.schema.json"
_REPORT_SCHEMA_PATH = "schemas/nmfa-activation-preflight-report.schema.json"
_PARENT_PATH = "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
_GATE_PLAN_PATH = "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
_GATE_BUNDLE_PATH = "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"

# These exact identities are immutable after the bundle freeze.
_PLAN_SIZE = 5513
_PLAN_SHA256 = "2d75e6f4ceec9f599b4b96720e4373327758b7f863bb0bd884c2361690d11d96"
_PLAN_SCHEMA_SIZE = 13013
_PLAN_SCHEMA_SHA256 = "d15372283c9ee9a5ce573e8d456ff7f4648e36b41e3c9804da8a953ce22cc3b1"
_TRUST_SCHEMA_SIZE = 3006
_TRUST_SCHEMA_SHA256 = "66a989243b43a7511834effd52149be4ec16c7bf525a347ac4ce1d4b2e672c40"
_REQUEST_SCHEMA_SIZE = 29656
_REQUEST_SCHEMA_SHA256 = "b2223622af7cc0c8e23aab846c5cb0d79ed9578fbaa5bd3594f2cd1efe3194c5"
_REPORT_SCHEMA_SIZE = 6822
_REPORT_SCHEMA_SHA256 = "a329393cfe38c22cfaaa5296d1f81e64910a9c81b9ed987df057ee70cd75286e"

_PARENT_SIZE = 25450
_PARENT_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
_GATE_PLAN_SIZE = 30641
_GATE_PLAN_SHA256 = "dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
_GATE_BUNDLE_SIZE = 3181
_GATE_BUNDLE_SHA256 = "ec9ba6fbaa5df13dce438f819114206da2d6ca6e68afb521476635d5abd91a79"

_MAX_JSON_BYTES = 67_108_864
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 2_000_000
_MAX_JSON_STRING_LENGTH = 16_384
_MAX_INTEGER = (1 << 63) - 1
_MIN_INTEGER = -(1 << 63)

_ALL_ROLES = (
    "authority",
    "governance_reviewer",
    "metadata_controller",
    "transcription_controller",
    "target_controller",
    "value_barrier_coordinator",
)
_PREMETADATA_ROLES = (
    "authority",
    "governance_reviewer",
    "metadata_controller",
)
_PREVALUE_ROLES = (
    "authority",
    "governance_reviewer",
    "metadata_controller",
    "target_controller",
    "transcription_controller",
    "value_barrier_coordinator",
)
_RIGHTS_LAYERS = (
    "source_frame_metadata",
    "transcription_x",
    "context_c",
    "physical_identity_f",
    "dependence_g",
    "target_y",
    "derived_aggregate",
)
_DATA_PERMISSIONS = (
    "retrieve",
    "retain_protected",
    "analyze",
    "derive",
    "custodial_transfer",
)
_CONTEXT_AXES = ("medium", "object_type", "period", "site")
_EPRE_REASONS = (
    "NOT_PHYSICAL_ORIGINAL",
    "IDENTITY_UNRESOLVED",
    "SOURCE_BINDING_INCOMPLETE",
    "CONTEXT_INCOMPLETE_OR_CONFLICTING",
    "PROVENANCE_INCOMPLETE",
    "RIGHTS_INSUFFICIENT",
)
_COMPILED_BLOCKERS = {
    "activation_wrapper_sha256": "ACTIVATION_WRAPPER_UNBOUND",
    "consumption_registry_profile_sha256": "CONSUMPTION_REGISTRY_UNBOUND",
    "external_time_anchor_profile_sha256": "EXTERNAL_TIME_ANCHOR_UNBOUND",
    "external_trust_profile_sha256": "EXTERNAL_TRUST_PROFILE_UNBOUND",
    "typed_execution_bundle_sha256": "TYPED_EXECUTION_BUNDLE_UNBOUND",
}
_REASON_PRECEDENCE = (
    "TRUST_PROFILE_INVALID",
    "SIGNATURE_INVALID",
    "RESOURCE_BINDING_MISMATCH",
    "FORBIDDEN_VALUE_SURFACE",
    "PREMETADATA_CHAIN_INVALID",
    "CHRONOLOGY_INVALID",
    "ACCESS_LEDGER_INVALID",
    "AUTHORITY_SCOPE_INVALID",
    "RIGHTS_NOT_READY",
    "CUSTODY_NOT_READY",
    "ROLE_SEPARATION_INVALID",
    "SOURCE_RULE_INVALID",
    "TARGET_RULE_INVALID",
    "INVENTORY_INVALID",
    "PREVALUE_E_CONTRIBUTION_INVALID",
    "RELATION_CONTRIBUTION_INVALID",
    "ARCHIVE_PREPARE_INVALID",
    "VALUE_BARRIER_INVALID",
    "TYPED_EXECUTION_BUNDLE_UNBOUND",
    "EXTERNAL_TRUST_PROFILE_UNBOUND",
    "EXTERNAL_TIME_ANCHOR_UNBOUND",
    "CONSUMPTION_REGISTRY_UNBOUND",
    "ACTIVATION_WRAPPER_UNBOUND",
)

_SUBJECT_DOMAINS = {
    "PREMETADATA": b"indusbench:nmfa:activation-preflight:premetadata-subject:v1\x00",
    "PREVALUE": b"indusbench:nmfa:activation-preflight:prevalue-subject:v1\x00",
}
_SIGNATURE_DOMAIN = b"indusbench:nmfa:activation-preflight:detached-signature:v1\x00"
_REPORT_DOMAIN = b"indusbench:nmfa:activation-preflight:private-report:v1\x00"
_RECEIPT_HEAD_DOMAIN = b"indusbench:nmfa:activation-preflight:event-head:v1\x00"
_FIRST_METADATA_HEAD_DOMAIN = b"indusbench:nmfa:activation-preflight:first-metadata-head:v1\x00"
_CLAIM_SUBJECT_DOMAIN = b"indusbench:nmfa:activation-preflight:claim-subject:v1\x00"
_IDENTIFIER_SUBJECT_DOMAIN = b"indusbench:nmfa:activation-preflight:identifier-subject:v1\x00"
_LEDGER_HEAD_DOMAIN = b"indusbench:nmfa:activation-preflight:ledger-head:v1\x00"
_INVENTORY_DOMAIN = b"indusbench:nmfa:activation-preflight:prevalue-inventory:v1\x00"
_F_ROSTER_DOMAIN = b"indusbench:nmfa:activation-preflight:ordered-f-roster:v1\x00"
_ARCHIVE_CONTRACT_DOMAIN = b"indusbench:nmfa:activation-preflight:archive-contract:v1\x00"

_ED25519_FIELD_PRIME = (1 << 255) - 19
_ED25519_GROUP_ORDER = (1 << 252) + 27742317777372353535851937790883648493
_ED25519_D = (-121665 * pow(121666, _ED25519_FIELD_PRIME - 2, _ED25519_FIELD_PRIME)) % (
    _ED25519_FIELD_PRIME
)
_ED25519_SQRT_MINUS_ONE = pow(2, (_ED25519_FIELD_PRIME - 1) // 4, _ED25519_FIELD_PRIME)
_ED25519_IDENTITY = (0, 1, 1, 0)

_ASSURANCE = {
    "access_ledger_prefix_authenticated": False,
    "authority_evidence_authenticated": False,
    "decipherment_claim_allowed": False,
    "evaluator_holds_private_keys": False,
    "execution_authorized": False,
    "external_independence_proven": False,
    "external_time_proven_by_signature": False,
    "metadata_channel_byte_separation_verified": False,
    "opaque_identifier_origin_verified": False,
    "prize_program_acceptance_verified": False,
    "prize_submission_eligible": False,
    "protected_source_accessed_by_evaluator": False,
    "public_release_authorized": False,
    "rights_evidence_authenticated": False,
    "target_or_transcription_loaded_by_evaluator": False,
}
_PRIVACY = {
    "counts_disclosed": False,
    "identifiers_disclosed": False,
    "private_digests_publicly_releasable": False,
    "private_report": True,
    "source_names_or_paths_disclosed": False,
}


class NMFAPreflightErrorCode(StrEnum):
    """Stable fixed-code error surface that never embeds protected data."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    PACKAGE_RESOURCE_INVALID = "PACKAGE_RESOURCE_INVALID"
    REQUEST_CONTRACT_INVALID = "REQUEST_CONTRACT_INVALID"
    SCHEMA_DEPENDENCY_MISSING = "SCHEMA_DEPENDENCY_MISSING"
    TRUST_PROFILE_CONTRACT_INVALID = "TRUST_PROFILE_CONTRACT_INVALID"


class NMFAPreflightError(ValueError):
    """A fixed-code exception with no path, identifier, digest, or count."""

    def __init__(self, code: NMFAPreflightErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class _JsonViolation(ValueError):
    pass


@dataclass(frozen=True)
class NMFAActivationPreflightPlanSnapshot:
    """Public source-free identity and installed blocker summary."""

    plan_id: str
    plan_sha256: str
    evaluator_bundle_sha256: str
    compiled_blockers: tuple[str, ...]
    premetadata_ready_enabled: bool = False
    prevalue_ready_enabled: bool = False
    source_access_authorized: bool = False
    execution_authorized: bool = False


@dataclass(frozen=True, repr=False)
class ValidatedNMFAExternalTrustProfile:
    """Validated canonical trust bytes matched to a caller-expected raw digest."""

    canonical_bytes: bytes
    trust_profile_sha256: str

    def __repr__(self) -> str:
        return "<ValidatedNMFAExternalTrustProfile protected>"


@dataclass(frozen=True, repr=False)
class NMFAActivationPreflightReport:
    """Deterministic report whose readable fields and bytes are private-only."""

    terminal_state: str
    reason_codes: tuple[str, ...]
    report_bytes: bytes

    def __repr__(self) -> str:
        return "<NMFAActivationPreflightReport protected>"

    def report(self) -> dict[str, Any]:
        """Return a fresh decoded copy for authorized private processing."""

        value = _decode_canonical_json(
            self.report_bytes,
            error=NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID,
        )
        if type(value) is not dict:
            _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
        return value


@dataclass(frozen=True)
class _Resources:
    bundle: bytes
    gate_bundle: bytes
    gate_plan: bytes
    io_source: bytes
    module_source: bytes
    parent: bytes
    plan: bytes
    plan_schema: bytes
    report_schema: bytes
    request_schema: bytes
    trust_schema: bytes


@dataclass(frozen=True)
class _Installed:
    bundle_sha256: str
    plan: dict[str, Any]
    snapshot: NMFAActivationPreflightPlanSnapshot


@dataclass(frozen=True)
class _Evaluation:
    report: NMFAActivationPreflightReport
    report_value: dict[str, Any]
    request: dict[str, Any]
    subject_sha256: str


def _fail(code: NMFAPreflightErrorCode) -> Never:
    raise NMFAPreflightError(code)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _JsonViolation
        result[key] = value
    return result


def _reject_float(_value: str) -> Never:
    raise _JsonViolation


def _parse_integer(value: str) -> int:
    parsed = int(value)
    if parsed < _MIN_INTEGER or parsed > _MAX_INTEGER:
        raise _JsonViolation
    return parsed


def _check_json_complexity(value: Any, *, allow_floats: bool = False) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_JSON_NODES or depth > _MAX_JSON_DEPTH:
            raise _JsonViolation
        if type(current) is dict:
            for key, child in current.items():
                if len(key) > _MAX_JSON_STRING_LENGTH:
                    raise _JsonViolation
                stack.append((child, depth + 1))
        elif type(current) is list:
            stack.extend((child, depth + 1) for child in current)
        elif type(current) is str:
            if len(current) > _MAX_JSON_STRING_LENGTH:
                raise _JsonViolation
        elif (
            current is None
            or type(current) in {bool, int}
            or (allow_floats and type(current) is float and math.isfinite(current))
        ):
            continue
        else:
            raise _JsonViolation


def _decode_canonical_json(raw: bytes, *, error: NMFAPreflightErrorCode) -> Any:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > _MAX_JSON_BYTES
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        _fail(error)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_float,
            parse_float=_reject_float,
            parse_int=_parse_integer,
        )
        _check_json_complexity(value)
        if encode_json(value) != raw:
            raise _JsonViolation
    except (UnicodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
        _fail(error)
    return value


def _decode_resource_json(raw: bytes, *, allow_floats: bool = False) -> Any:
    try:
        if not raw or len(raw) > _MAX_JSON_BYTES or raw.startswith(b"\xef\xbb\xbf"):
            raise _JsonViolation
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_float,
            parse_float=float if allow_floats else _reject_float,
            parse_int=_parse_integer,
        )
        _check_json_complexity(value, allow_floats=allow_floats)
        if not allow_floats and encode_json(value) != raw:
            raise _JsonViolation
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _domain_digest(domain: bytes, value: Any) -> str:
    return _sha256(domain + encode_json(value))


def _canonical_timestamp(value: Any) -> bool:
    if type(value) is not str or len(value) != 20 or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _load_resources() -> _Resources:
    try:
        root = importlib.resources.files("indusbench")
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    if not isinstance(root, Path):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)

    def read(relative: str) -> bytes:
        try:
            return root.joinpath(*relative.split("/")).read_bytes()
        except (OSError, TypeError, ValueError):
            _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)

    return _Resources(
        bundle=read(_BUNDLE_PATH),
        gate_bundle=read(_GATE_BUNDLE_PATH),
        gate_plan=read(_GATE_PLAN_PATH),
        io_source=read("io.py"),
        module_source=read("nmfa_preflight.py"),
        parent=read(_PARENT_PATH),
        plan=read(_PLAN_PATH),
        plan_schema=read(_PLAN_SCHEMA_PATH),
        report_schema=read(_REPORT_SCHEMA_PATH),
        request_schema=read(_REQUEST_SCHEMA_PATH),
        trust_schema=read(_TRUST_SCHEMA_PATH),
    )


def _compile_validator(schema_raw: bytes) -> Any:
    schema = _decode_resource_json(schema_raw)
    if type(schema) is not dict:
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError
    except ImportError:
        _fail(NMFAPreflightErrorCode.SCHEMA_DEPENDENCY_MISSING)
    try:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except (SchemaError, TypeError, ValueError):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)


def _validate_instance(
    value: Any,
    schema_raw: bytes,
    *,
    error: NMFAPreflightErrorCode,
) -> None:
    validator = _compile_validator(schema_raw)
    try:
        first_error = next(validator.iter_errors(value), None)
    except Exception:
        _fail(error)
    if first_error is not None:
        _fail(error)


def _expected_runtime_profile() -> dict[str, Any]:
    return {
        "canonical_encoder": "indusbench.io:encode_json",
        "conditional_dependencies": {
            "python_version_less_than_3_13": {"typing-extensions": "4.16.0"}
        },
        "cryptography_contract": {
            "algorithm": "Ed25519",
            "public_key_format": "Raw_32_bytes",
            "strict_canonical_S_precheck": True,
            "strict_nonidentity_prime_subgroup_A_and_R_precheck": True,
        },
        "dependencies": {
            "attrs": "26.1.0",
            "cffi": "2.1.0",
            "cryptography": "50.0.0",
            "jsonschema": "4.26.0",
            "jsonschema-specifications": "2025.9.1",
            "pycparser": "3.0",
            "referencing": "0.37.0",
            "rfc3339-validator": "0.1.4",
            "rpds-py": "2026.6.3",
            "six": "1.17.0",
        },
        "dependency_lock": "uv.lock",
        "entrypoints": [
            "indusbench.nmfa_preflight:evaluate_premetadata_preflight",
            "indusbench.nmfa_preflight:evaluate_prevalue_preflight",
        ],
        "implementation": "CPython",
        "supported_python_minors": ["3.11", "3.12", "3.13", "3.14"],
    }


def _validate_bundle(resources: _Resources) -> str:
    bundle = _decode_resource_json(resources.bundle)
    expected_security = {
        "candidate_or_tofu_trust_accepted": False,
        "evaluator_private_keys_included": False,
        "external_time_verified_by_bundle": False,
        "one_time_registry_verified_by_bundle": False,
        "protected_requests_included": False,
        "runtime_artifact_provenance_attested": False,
        "runtime_environment_attested": False,
        "source_or_target_values_included": False,
    }
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
        or bundle["bundle_id"] != "nmfa-activation-preflight-evaluator-bundle-v1"
        or bundle["format_version"] != "1.0.0"
        or not _canonical_timestamp(bundle["created_at"])
        or bundle["runtime_profile"] != _expected_runtime_profile()
        or bundle["security_boundary"] != expected_security
        or type(bundle["files"]) is not list
        or sys.implementation.name != "cpython"
        or f"{sys.version_info.major}.{sys.version_info.minor}"
        not in bundle["runtime_profile"]["supported_python_minors"]
    ):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_runtime = bundle["runtime_profile"]["dependencies"]
    expected_conditional = (
        bundle["runtime_profile"]["conditional_dependencies"]["python_version_less_than_3_13"]
        if sys.version_info < (3, 13)
        else {}
    )
    try:
        observed_runtime = {name: importlib.metadata.version(name) for name in expected_runtime}
        observed_conditional = {
            name: importlib.metadata.version(name) for name in expected_conditional
        }
    except importlib.metadata.PackageNotFoundError:
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    if observed_runtime != expected_runtime or observed_conditional != expected_conditional:
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)

    actual = {
        _GATE_BUNDLE_PATH: resources.gate_bundle,
        _GATE_PLAN_PATH: resources.gate_plan,
        _PARENT_PATH: resources.parent,
        _PLAN_PATH: resources.plan,
        _PLAN_SCHEMA_PATH: resources.plan_schema,
        _REPORT_SCHEMA_PATH: resources.report_schema,
        _REQUEST_SCHEMA_PATH: resources.request_schema,
        _TRUST_SCHEMA_PATH: resources.trust_schema,
        "src/indusbench/io.py": resources.io_source,
        "src/indusbench/nmfa_preflight.py": resources.module_source,
    }
    rows = bundle["files"]
    if any(type(row) is not dict or type(row.get("path")) is not str for row in rows):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    paths = cast(list[str], [row["path"] for row in rows])
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    if set(paths) != set(actual):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    for row in rows:
        if (
            type(row) is not dict
            or set(row) != {"bytes", "path", "sha256", "verification"}
            or type(row["bytes"]) is not int
            or row["bytes"] <= 0
            or type(row["sha256"]) is not str
            or row["verification"] != "runtime_and_ci"
        ):
            _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
        path = row["path"]
        if path in actual:
            raw = actual[path]
            if (
                row["verification"] != "runtime_and_ci"
                or row["bytes"] != len(raw)
                or row["sha256"] != _sha256(raw)
            ):
                _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    return _sha256(resources.bundle)


def _installed(resources: _Resources) -> _Installed:
    bundle_sha256 = _validate_bundle(resources)
    expected = (
        (resources.plan, _PLAN_SIZE, _PLAN_SHA256),
        (resources.plan_schema, _PLAN_SCHEMA_SIZE, _PLAN_SCHEMA_SHA256),
        (resources.trust_schema, _TRUST_SCHEMA_SIZE, _TRUST_SCHEMA_SHA256),
        (resources.request_schema, _REQUEST_SCHEMA_SIZE, _REQUEST_SCHEMA_SHA256),
        (resources.report_schema, _REPORT_SCHEMA_SIZE, _REPORT_SCHEMA_SHA256),
        (resources.parent, _PARENT_SIZE, _PARENT_SHA256),
        (resources.gate_plan, _GATE_PLAN_SIZE, _GATE_PLAN_SHA256),
        (resources.gate_bundle, _GATE_BUNDLE_SIZE, _GATE_BUNDLE_SHA256),
    )
    if any(
        len(raw) != size or hashlib.sha256(raw).hexdigest() != digest
        for raw, size, digest in expected
    ):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    plan = _decode_resource_json(resources.plan)
    if type(plan) is not dict:
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    _validate_instance(
        plan,
        resources.plan_schema,
        error=NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID,
    )
    bundle = _decode_resource_json(resources.bundle)
    if plan["created_at"] >= bundle["created_at"]:
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    assets = plan["bound_assets"]
    actual_assets = {
        "parent_protocol": resources.parent,
        "preregistration_evaluator_bundle": resources.gate_bundle,
        "preregistration_gate_plan": resources.gate_plan,
    }
    if any(
        assets[name]["bytes"] != len(raw) or assets[name]["sha256"] != _sha256(raw)
        for name, raw in actual_assets.items()
    ):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    blocker_codes = tuple(
        code
        for field, code in _COMPILED_BLOCKERS.items()
        if plan["compiled_blockers"][field] is None
    )
    if blocker_codes != (
        "ACTIVATION_WRAPPER_UNBOUND",
        "CONSUMPTION_REGISTRY_UNBOUND",
        "EXTERNAL_TIME_ANCHOR_UNBOUND",
        "EXTERNAL_TRUST_PROFILE_UNBOUND",
        "TYPED_EXECUTION_BUNDLE_UNBOUND",
    ):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    snapshot = NMFAActivationPreflightPlanSnapshot(
        plan_id=plan["plan_id"],
        plan_sha256=_sha256(resources.plan),
        evaluator_bundle_sha256=bundle_sha256,
        compiled_blockers=tuple(_ordered_reasons(set(blocker_codes))),
    )
    return _Installed(bundle_sha256=bundle_sha256, plan=plan, snapshot=snapshot)


def load_installed_nmfa_activation_preflight_plan() -> NMFAActivationPreflightPlanSnapshot:
    """Validate and summarize the exact source-free installed companion."""

    return _installed(_load_resources()).snapshot


def _ordered_reasons(reasons: set[str]) -> list[str]:
    if not reasons.issubset(_REASON_PRECEDENCE):
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    return [reason for reason in _REASON_PRECEDENCE if reason in reasons]


def _decode_ed25519_point(raw: bytes) -> tuple[int, int, int, int] | None:
    """Decode one canonical compressed Edwards point into extended coordinates."""

    if len(raw) != 32:
        return None
    sign = raw[31] >> 7
    encoded_y = bytearray(raw)
    encoded_y[31] &= 0x7F
    y = int.from_bytes(encoded_y, "little")
    if y >= _ED25519_FIELD_PRIME:
        return None
    y_squared = y * y % _ED25519_FIELD_PRIME
    numerator = (y_squared - 1) % _ED25519_FIELD_PRIME
    denominator = (_ED25519_D * y_squared + 1) % _ED25519_FIELD_PRIME
    if denominator == 0:
        return None
    x_squared = (
        numerator
        * pow(
            denominator,
            _ED25519_FIELD_PRIME - 2,
            _ED25519_FIELD_PRIME,
        )
        % _ED25519_FIELD_PRIME
    )
    x = pow(x_squared, (_ED25519_FIELD_PRIME + 3) // 8, _ED25519_FIELD_PRIME)
    if x * x % _ED25519_FIELD_PRIME != x_squared:
        x = x * _ED25519_SQRT_MINUS_ONE % _ED25519_FIELD_PRIME
    if x * x % _ED25519_FIELD_PRIME != x_squared:
        return None
    if x & 1 != sign:
        x = (-x) % _ED25519_FIELD_PRIME
    if x == 0 and sign != 0:
        return None
    return x, y, 1, x * y % _ED25519_FIELD_PRIME


def _add_ed25519_points(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Add extended-coordinate Edwards points without field inversion."""

    x1, y1, z1, t1 = left
    x2, y2, z2, t2 = right
    a = (y1 - x1) * (y2 - x2) % _ED25519_FIELD_PRIME
    b = (y1 + x1) * (y2 + x2) % _ED25519_FIELD_PRIME
    c = 2 * _ED25519_D * t1 * t2 % _ED25519_FIELD_PRIME
    d = 2 * z1 * z2 % _ED25519_FIELD_PRIME
    e = (b - a) % _ED25519_FIELD_PRIME
    f = (d - c) % _ED25519_FIELD_PRIME
    g = (d + c) % _ED25519_FIELD_PRIME
    h = (b + a) % _ED25519_FIELD_PRIME
    return (
        e * f % _ED25519_FIELD_PRIME,
        g * h % _ED25519_FIELD_PRIME,
        f * g % _ED25519_FIELD_PRIME,
        e * h % _ED25519_FIELD_PRIME,
    )


def _multiply_ed25519_point(
    point: tuple[int, int, int, int],
    scalar: int,
) -> tuple[int, int, int, int]:
    if type(scalar) is not int or scalar < 0:
        raise ValueError("Ed25519 scalar must be a nonnegative integer")
    result = _ED25519_IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = _add_ed25519_points(result, addend)
        addend = _add_ed25519_points(addend, addend)
        scalar >>= 1
    return result


def _is_ed25519_identity(point: tuple[int, int, int, int]) -> bool:
    x, y, z, _ = point
    return (
        z % _ED25519_FIELD_PRIME != 0
        and x % _ED25519_FIELD_PRIME == 0
        and (y - z) % _ED25519_FIELD_PRIME == 0
    )


def _is_strict_ed25519_point(raw: bytes) -> bool:
    """Require a non-identity point in Ed25519's prime-order subgroup."""

    point = _decode_ed25519_point(raw)
    return (
        point is not None
        and not _is_ed25519_identity(point)
        and _is_ed25519_identity(_multiply_ed25519_point(point, _ED25519_GROUP_ORDER))
    )


def _validate_trust_profile(
    raw: bytes,
    expected_sha256: str,
    resources: _Resources,
) -> tuple[ValidatedNMFAExternalTrustProfile, dict[str, Any], bool]:
    if (
        type(expected_sha256) is not str
        or len(expected_sha256) != 71
        or not expected_sha256.startswith("sha256:")
    ):
        _fail(NMFAPreflightErrorCode.INVALID_ARGUMENT)
    value = _decode_canonical_json(
        raw,
        error=NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
    )
    if type(value) is not dict:
        _fail(NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID)
    _validate_instance(
        value,
        resources.trust_schema,
        error=NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
    )
    actual_sha256 = _sha256(raw)
    structurally_valid = actual_sha256 == expected_sha256
    rows = value["role_bindings"]
    structurally_valid = structurally_valid and [row["role"] for row in rows] == list(_ALL_ROLES)
    for field in ("actor_id", "controller_id", "conflict_domain_id", "key_id"):
        structurally_valid = structurally_valid and len({row[field] for row in rows}) == len(rows)
    for row in rows:
        try:
            public_key = _decode_base64url(row["public_key_base64url"], 32)
        except _JsonViolation:
            structurally_valid = False
            continue
        structurally_valid = structurally_valid and _is_strict_ed25519_point(public_key)
        structurally_valid = structurally_valid and row["key_id"] == (
            "ed25519:" + hashlib.sha256(public_key).hexdigest()
        )
    structurally_valid = structurally_valid and value["created_at"] < value["expires_at"]
    return (
        ValidatedNMFAExternalTrustProfile(raw, actual_sha256),
        value,
        structurally_valid,
    )


def validate_external_trust_profile(
    raw: bytes,
    expected_sha256: str,
) -> ValidatedNMFAExternalTrustProfile:
    """Validate canonical trust bytes against a caller-expected raw digest."""

    if type(raw) is not bytes:
        _fail(NMFAPreflightErrorCode.INVALID_ARGUMENT)
    validated, _, structurally_valid = _validate_trust_profile(
        raw,
        expected_sha256,
        _load_resources(),
    )
    if not structurally_valid:
        _fail(NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID)
    return validated


def _decode_base64url(value: str, size: int) -> bytes:
    if type(value) is not str or "=" in value:
        raise _JsonViolation
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        raise _JsonViolation from None
    if (
        len(decoded) != size
        or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value
    ):
        raise _JsonViolation
    return decoded


def _request_subject(request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    unsigned = {key: value for key, value in request.items() if key != "signatures"}
    kind = request["request_kind"]
    return unsigned, _domain_digest(_SUBJECT_DOMAINS[kind], unsigned)


def _signature_message(
    request: dict[str, Any],
    subject_sha256: str,
    trust: dict[str, Any],
    role: str,
) -> bytes:
    rows = {row["role"]: row for row in trust["role_bindings"]}
    row = rows[role]
    return _SIGNATURE_DOMAIN + encode_json(
        {
            "actor_id": row["actor_id"],
            "claim_family_id": request["claim_family_id"],
            "created_at": request["created_at"],
            "experiment_instance_id": request["experiment_instance_id"],
            "key_id": row["key_id"],
            "registry_sequence": trust["registry_sequence"],
            "request_kind": request["request_kind"],
            "request_sequence": request["sequence"],
            "revocation_snapshot_sha256": trust["revocation_snapshot_sha256"],
            "role": role,
            "slot_id": request["slot_id"],
            "subject_sha256": subject_sha256,
            "trust_domain_id": trust["trust_domain_id"],
            "trust_profile_id": trust["profile_id"],
            "trust_profile_sha256": request["bindings"]["external_trust_profile_sha256"],
        }
    )


def build_nmfa_preflight_signature_message(
    request_raw: bytes,
    trust_profile_raw: bytes,
    expected_trust_profile_sha256: str,
    role: str,
) -> bytes:
    """Build the exact detached-signature message without holding a private key."""

    if (
        type(request_raw) is not bytes
        or type(trust_profile_raw) is not bytes
        or type(role) is not str
    ):
        _fail(NMFAPreflightErrorCode.INVALID_ARGUMENT)
    resources = _load_resources()
    _installed(resources)
    _, trust, valid = _validate_trust_profile(
        trust_profile_raw,
        expected_trust_profile_sha256,
        resources,
    )
    if not valid:
        _fail(NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID)
    request = _decode_canonical_json(
        request_raw,
        error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
    )
    if type(request) is not dict:
        _fail(NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)
    _validate_instance(
        request,
        resources.request_schema,
        error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
    )
    if request["signatures"] != []:
        _fail(NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)
    expected_roles = (
        _PREMETADATA_ROLES if request["request_kind"] == "PREMETADATA" else _PREVALUE_ROLES
    )
    if role not in expected_roles:
        _fail(NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID)
    _, subject_sha256 = _request_subject(request)
    return _signature_message(request, subject_sha256, trust, role)


def _verify_signatures(
    request: dict[str, Any],
    subject_sha256: str,
    trust: dict[str, Any],
    trust_valid: bool,
) -> bool:
    expected_roles = (
        _PREMETADATA_ROLES if request["request_kind"] == "PREMETADATA" else _PREVALUE_ROLES
    )
    signatures = request["signatures"]
    if [row["role"] for row in signatures] != list(expected_roles) or not trust_valid:
        return False
    trust_by_role = {row["role"]: row for row in trust["role_bindings"]}
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
    for signature in signatures:
        trust_row = trust_by_role[signature["role"]]
        if (
            signature["actor_id"] != trust_row["actor_id"]
            or signature["key_id"] != trust_row["key_id"]
        ):
            return False
        try:
            public_key = _decode_base64url(trust_row["public_key_base64url"], 32)
            signature_bytes = _decode_base64url(signature["signature_base64url"], 64)
        except _JsonViolation:
            return False
        if (
            not _is_strict_ed25519_point(public_key)
            or not _is_strict_ed25519_point(signature_bytes[:32])
            or int.from_bytes(signature_bytes[32:], "little") >= _ED25519_GROUP_ORDER
        ):
            return False
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature_bytes,
                _signature_message(request, subject_sha256, trust, signature["role"]),
            )
        except UnsupportedAlgorithm:
            _fail(NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)
        except (InvalidSignature, ValueError):
            return False
    return True


def _resource_binding_reasons(
    request: dict[str, Any],
    trust_sha256: str,
    installed: _Installed,
) -> set[str]:
    bindings = request["bindings"]
    expected = {
        "activation_preflight_evaluator_bundle_sha256": installed.bundle_sha256,
        "activation_preflight_plan_sha256": installed.snapshot.plan_sha256,
        "external_trust_profile_sha256": trust_sha256,
        "parent_protocol_sha256": "sha256:" + _PARENT_SHA256,
        "preregistration_evaluator_bundle_sha256": "sha256:" + _GATE_BUNDLE_SHA256,
        "preregistration_gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
    }
    if any(bindings[field] != value for field, value in expected.items()):
        return {"RESOURCE_BINDING_MISMATCH"}
    return set()


def _compiled_blocker_reasons(plan: dict[str, Any]) -> set[str]:
    return {
        code
        for field, code in _COMPILED_BLOCKERS.items()
        if plan["compiled_blockers"][field] is None
    }


def _receipt_head(receipt: dict[str, Any]) -> str:
    payload = {key: value for key, value in receipt.items() if key != "event_head_sha256"}
    return _domain_digest(_RECEIPT_HEAD_DOMAIN, payload)


def _ledger_head(ledger: dict[str, Any]) -> str:
    payload = {key: value for key, value in ledger.items() if key != "event_head_sha256"}
    return _domain_digest(_LEDGER_HEAD_DOMAIN, payload)


def _first_metadata_head(receipt: dict[str, Any]) -> str:
    payload = {key: value for key, value in receipt.items() if key != "event_head_sha256"}
    return _domain_digest(_FIRST_METADATA_HEAD_DOMAIN, payload)


def _premetadata_semantics(request: dict[str, Any], trust: dict[str, Any]) -> set[str]:
    reasons: set[str] = set()
    claim = request["claim_reservation"]
    ceremony = request["identifier_ceremony"]
    ledger = request["no_access_ledger"]
    if (
        claim["kind"] != "CLAIM_SLOT_RESERVATION"
        or ceremony["kind"] != "IDENTIFIER_KEY_CEREMONY"
        or claim["identifier_key_commitment_sha256"] is not None
        or ceremony["identifier_key_commitment_sha256"] is None
        or claim["subject_sha256"]
        != _domain_digest(
            _CLAIM_SUBJECT_DOMAIN,
            {
                "activation_root_sha256": request["bindings"]["activation_root_sha256"],
                "claim_family_id": request["claim_family_id"],
                "experiment_instance_id": request["experiment_instance_id"],
                "slot_id": request["slot_id"],
            },
        )
        or claim["event_head_sha256"] != _receipt_head(claim)
        or ceremony["event_head_sha256"] != _receipt_head(ceremony)
        or ceremony["prior_event_head_sha256"] != claim["event_head_sha256"]
        or ceremony["subject_sha256"]
        != _domain_digest(
            _IDENTIFIER_SUBJECT_DOMAIN,
            {
                "claim_reservation": claim,
                "claim_family_id": request["claim_family_id"],
                "identifier_key_commitment_sha256": ceremony["identifier_key_commitment_sha256"],
                "experiment_instance_id": request["experiment_instance_id"],
                "slot_id": request["slot_id"],
            },
        )
    ):
        reasons.add("PREMETADATA_CHAIN_INVALID")
    if (
        ledger["event_head_sha256"] != _ledger_head(ledger)
        or ledger["prior_event_head_sha256"] != ceremony["event_head_sha256"]
        or ledger["metadata_access_count"] != 0
    ):
        reasons.add("ACCESS_LEDGER_INVALID")
    if not (
        claim["sequence"] + 1
        == ceremony["sequence"]
        == ledger["sequence"] - 1
        == request["sequence"] - 2
        and claim["recorded_at"]
        < ceremony["recorded_at"]
        < ledger["recorded_at"]
        < request["created_at"]
    ):
        reasons.add("CHRONOLOGY_INVALID")
    scope = request["source_scope"]
    if not (
        scope["valid_from"] <= request["created_at"] < scope["valid_until"]
        and trust["created_at"] <= request["created_at"] < trust["expires_at"]
        and scope["revocation_snapshot_sha256"] == trust["revocation_snapshot_sha256"]
    ):
        reasons.add("AUTHORITY_SCOPE_INVALID")
    rights = request["rights"]
    rights_ready = [row["layer"] for row in rights] == list(_RIGHTS_LAYERS)
    rights_ready = rights_ready and all(
        all(row["permissions"][permission] == "PERMITTED" for permission in _DATA_PERMISSIONS)
        for row in rights[:-1]
    )
    aggregate = rights[-1]
    rights_ready = rights_ready and all(
        aggregate["permissions"][permission] == "PERMITTED"
        for permission in ("derive", "publish_aggregate")
    )
    if not rights_ready:
        reasons.add("RIGHTS_NOT_READY")
    role_rows = trust["role_bindings"]
    if any(
        len({row[field] for row in role_rows}) != len(role_rows)
        for field in ("actor_id", "controller_id", "conflict_domain_id", "key_id")
    ):
        reasons.add("ROLE_SEPARATION_INVALID")
    return reasons


def _inventory_semantics(request: dict[str, Any]) -> tuple[set[str], str, str]:
    reasons: set[str] = set()
    inventory = request["inventory"]
    source_rows = inventory["source_records"]
    units = inventory["units"]
    exposure = inventory["prevalue_exposure"]
    relations = inventory["declared_pre_x_relation_edges"]
    inventory_sha256 = _domain_digest(_INVENTORY_DOMAIN, inventory)
    f_ids = [row["f_id"] for row in units]
    f_id_set = set(f_ids)
    f_roster_sha256 = _domain_digest(_F_ROSTER_DOMAIN, {"ordered_f_ids": f_ids})

    source_f_ids = [row["f_id"] for row in source_rows]
    record_assignments: dict[str, str] = {}
    assignment_conflict = False
    for row in source_rows:
        previous = record_assignments.setdefault(row["record_id"], row["f_id"])
        assignment_conflict = assignment_conflict or previous != row["f_id"]
    source_triples = [(row["record_id"], row["revision_id"], row["view_id"]) for row in source_rows]
    if (
        inventory["declared_source_record_count"] != len(source_rows)
        or inventory["declared_unit_count"] != len(units)
        or [row["source_order"] for row in source_rows] != list(range(len(source_rows)))
        or [row["unit_order"] for row in units] != list(range(len(units)))
        or len({row["entry_id"] for row in source_rows}) != len(source_rows)
        or len(set(source_triples)) != len(source_triples)
        or assignment_conflict
        or f_ids != sorted(f_ids)
        or len(set(f_ids)) != len(f_ids)
        or set(source_f_ids) != f_id_set
        or [row["f_id"] for row in exposure] != f_ids
    ):
        reasons.add("INVENTORY_INVALID")
    if any(row["status"] == "UNKNOWN" for row in exposure):
        reasons.add("ACCESS_LEDGER_INVALID")

    contribution_invalid = False
    for unit in units:
        axes = unit["context_axes"]
        if [axis["axis"] for axis in axes] != list(_CONTEXT_AXES):
            contribution_invalid = True
        for axis in axes:
            if (axis["status"] == "EXACT") != (axis["value_id"] is not None):
                contribution_invalid = True
        nuisance = unit["nuisance_values"]
        if [row["field_id"] for row in nuisance] != sorted(row["field_id"] for row in nuisance):
            contribution_invalid = True
        if len({row["field_id"] for row in nuisance}) != len(nuisance):
            contribution_invalid = True
        for row in nuisance:
            if row["value_ids"] != sorted(row["value_ids"]):
                contribution_invalid = True
            if (row["status"] == "EXACT") != bool(row["value_ids"]):
                contribution_invalid = True
        epre_conditions = (
            unit["physical_original_status"] != "CONFIRMED_PHYSICAL_ORIGINAL",
            unit["identity_status"] != "RESOLVED",
            unit["source_binding_status"] != "COMPLETE",
            any(axis["status"] != "EXACT" for axis in axes)
            or any(row["status"] != "EXACT" for row in nuisance),
            unit["provenance_status"] != "COMPLETE",
            unit["rights_status"] != "SUFFICIENT",
        )
        derived_epre = [
            reason
            for reason, condition in zip(_EPRE_REASONS, epre_conditions, strict=True)
            if condition
        ]
        if unit["epre_reason_codes"] != derived_epre:
            contribution_invalid = True
    if contribution_invalid:
        reasons.add("PREVALUE_E_CONTRIBUTION_INVALID")

    relation_keys: list[tuple[str, str, str, str, str]] = []
    relation_invalid = False
    for row in relations:
        key = (
            row["left_f_id"],
            row["right_f_id"],
            row["kind"],
            row["status"],
            row["disposition"],
        )
        relation_keys.append(key)
        if (
            row["left_f_id"] not in f_id_set
            or row["right_f_id"] not in f_id_set
            or row["left_f_id"] >= row["right_f_id"]
            or (row["status"] == "CONFIRMED" and row["disposition"] != "UNION")
            or (row["status"] != "CONFIRMED" and row["disposition"] != "EXCLUDE_BOTH")
        ):
            relation_invalid = True
    if relation_keys != sorted(relation_keys) or len(relation_keys) != len(set(relation_keys)):
        relation_invalid = True
    if relation_invalid:
        reasons.add("RELATION_CONTRIBUTION_INVALID")
    return reasons, inventory_sha256, f_roster_sha256


def _prevalue_semantics(
    request: dict[str, Any],
    premetadata: _Evaluation,
    trust: dict[str, Any],
) -> set[str]:
    reasons: set[str] = set()
    if not trust["created_at"] <= request["created_at"] < trust["expires_at"]:
        reasons.add("AUTHORITY_SCOPE_INVALID")
    predecessor = request["predecessor"]
    if (
        predecessor["premetadata_request_sha256"] != _sha256(encode_json(premetadata.request))
        or predecessor["premetadata_report_sha256"] != _sha256(premetadata.report.report_bytes)
        or predecessor["premetadata_subject_sha256"] != premetadata.subject_sha256
        or premetadata.report.terminal_state != "PREMETADATA_READY"
        or request["claim_family_id"] != premetadata.request["claim_family_id"]
        or request["experiment_instance_id"] != premetadata.request["experiment_instance_id"]
        or request["slot_id"] != premetadata.request["slot_id"]
        or request["bindings"] != premetadata.request["bindings"]
    ):
        reasons.add("PREMETADATA_CHAIN_INVALID")
    first = request["first_metadata_access"]
    preledger = premetadata.request["no_access_ledger"]
    ledger = request["access_ledger"]
    if (
        first["premetadata_report_sha256"] != predecessor["premetadata_report_sha256"]
        or first["prior_event_head_sha256"] != preledger["event_head_sha256"]
        or first["event_head_sha256"] != _first_metadata_head(first)
        or first["metadata_projection_contract_sha256"]
        != premetadata.request["source_policy"]["metadata_projection_contract_sha256"]
        or ledger["prior_event_head_sha256"] != first["event_head_sha256"]
        or ledger["ledger_id"] != preledger["ledger_id"]
        or ledger["event_head_sha256"] != _ledger_head(ledger)
        or ledger["metadata_access_count"] < 1
        or request["inventory"]["exposure_cutoff_event_head_sha256"] != ledger["event_head_sha256"]
    ):
        reasons.add("ACCESS_LEDGER_INVALID")
    if not (
        premetadata.request["sequence"] + 1 == first["sequence"] == ledger["sequence"] - 1
        and premetadata.request["created_at"]
        < first["recorded_at"]
        <= ledger["recorded_at"]
        < request["created_at"]
    ):
        reasons.add("CHRONOLOGY_INVALID")

    inventory_reasons, inventory_sha256, f_roster_sha256 = _inventory_semantics(request)
    reasons.update(inventory_reasons)
    archives = request["archives"]
    barriers = request["barriers"]
    archive_invalid = False
    barrier_invalid = False
    for layer, role in (
        ("target_y", "target_controller"),
        ("transcription_x", "transcription_controller"),
    ):
        archive = archives[layer]
        barrier = barriers[layer]
        if (
            archive["data_layer"] != layer
            or archive["controller_role"] != role
            or archive["experiment_instance_id"] != request["experiment_instance_id"]
            or archive["slot_id"] != request["slot_id"]
            or archive["prevalue_inventory_sha256"] != inventory_sha256
            or archive["f_roster_sha256"] != f_roster_sha256
            or archive["planned_f_count"] != request["inventory"]["declared_unit_count"]
        ):
            archive_invalid = True
        if (
            barrier["data_layer"] != layer
            or barrier["controller_role"] != role
            or barrier["archive_contract_sha256"]
            != _domain_digest(_ARCHIVE_CONTRACT_DOMAIN, archive)
            or barrier["expected_prior_event_head_sha256"] != ledger["event_head_sha256"]
        ):
            barrier_invalid = True
    target_barrier = barriers["target_y"]
    transcription_barrier = barriers["transcription_x"]
    if not (
        ledger["sequence"] + 1
        == target_barrier["sequence"]
        == transcription_barrier["sequence"] - 1
        == request["sequence"] - 2
        and ledger["recorded_at"]
        < target_barrier["prepared_at"]
        < transcription_barrier["prepared_at"]
        < request["created_at"]
    ):
        barrier_invalid = True
    if (
        target_barrier["cas_token_commitment_sha256"]
        == transcription_barrier["cas_token_commitment_sha256"]
    ):
        barrier_invalid = True
    if archive_invalid:
        reasons.add("ARCHIVE_PREPARE_INVALID")
    if barrier_invalid:
        reasons.add("VALUE_BARRIER_INVALID")
    return reasons


def _report(
    *,
    request: dict[str, Any],
    request_raw: bytes,
    subject_sha256: str,
    trust_sha256: str,
    installed: _Installed,
    resources: _Resources,
    reasons: set[str],
    semantic_reasons: set[str],
    signatures_valid: bool,
    predecessor_report_sha256: str | None,
) -> NMFAActivationPreflightReport:
    request_kind = request["request_kind"]
    terminal = f"{request_kind}_READY" if not reasons else f"{request_kind}_BLOCKED"
    value: dict[str, Any] = {
        "assurance": dict(_ASSURANCE),
        "bindings": {
            "activation_preflight_evaluator_bundle_sha256": installed.bundle_sha256,
            "activation_preflight_plan_sha256": installed.snapshot.plan_sha256,
            "external_trust_profile_sha256": trust_sha256,
            "predecessor_report_sha256": predecessor_report_sha256,
            "request_sha256": _sha256(request_raw),
            "subject_sha256": subject_sha256,
        },
        "created_at": request["created_at"],
        "format_version": "1.0.0",
        "privacy": dict(_PRIVACY),
        "reason_codes": _ordered_reasons(reasons),
        "record_kind": "nmfa_private_activation_preflight_report",
        "request_kind": request_kind,
        "semantic_core_valid": not semantic_reasons,
        "signatures_valid": signatures_valid,
        "terminal_state": terminal,
    }
    value["report_sha256"] = _domain_digest(_REPORT_DOMAIN, value)
    _validate_instance(
        value,
        resources.report_schema,
        error=NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID,
    )
    return NMFAActivationPreflightReport(
        terminal_state=terminal,
        reason_codes=tuple(value["reason_codes"]),
        report_bytes=encode_json(value),
    )


def _parse_request(raw: bytes, resources: _Resources, expected_kind: str) -> dict[str, Any]:
    value = _decode_canonical_json(
        raw,
        error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
    )
    if type(value) is not dict:
        _fail(NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)
    _validate_instance(
        value,
        resources.request_schema,
        error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
    )
    if value["request_kind"] != expected_kind:
        _fail(NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)
    return value


def _evaluate_premetadata(
    request_raw: bytes,
    trust_profile_raw: bytes,
    expected_trust_profile_sha256: str,
    resources: _Resources,
    installed: _Installed,
) -> _Evaluation:
    validated_trust, trust, trust_valid = _validate_trust_profile(
        trust_profile_raw,
        expected_trust_profile_sha256,
        resources,
    )
    if not trust_valid:
        _fail(NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID)
    request = _parse_request(request_raw, resources, "PREMETADATA")
    _, subject_sha256 = _request_subject(request)
    signatures_valid = _verify_signatures(request, subject_sha256, trust, trust_valid)
    semantic_reasons = _resource_binding_reasons(
        request,
        validated_trust.trust_profile_sha256,
        installed,
    )
    if not signatures_valid:
        semantic_reasons.add("SIGNATURE_INVALID")
    semantic_reasons.update(_premetadata_semantics(request, trust))
    reasons = semantic_reasons | _compiled_blocker_reasons(installed.plan)
    report = _report(
        request=request,
        request_raw=request_raw,
        subject_sha256=subject_sha256,
        trust_sha256=validated_trust.trust_profile_sha256,
        installed=installed,
        resources=resources,
        reasons=reasons,
        semantic_reasons=semantic_reasons,
        signatures_valid=signatures_valid,
        predecessor_report_sha256=None,
    )
    return _Evaluation(report, report.report(), request, subject_sha256)


def evaluate_premetadata_preflight(
    request_raw: bytes,
    trust_profile_raw: bytes,
    expected_trust_profile_sha256: str,
) -> NMFAActivationPreflightReport:
    """Verify a protected PREMETADATA request; installed V1 remains blocked."""

    if type(request_raw) is not bytes or type(trust_profile_raw) is not bytes:
        _fail(NMFAPreflightErrorCode.INVALID_ARGUMENT)
    resources = _load_resources()
    installed = _installed(resources)
    return _evaluate_premetadata(
        request_raw,
        trust_profile_raw,
        expected_trust_profile_sha256,
        resources,
        installed,
    ).report


def evaluate_prevalue_preflight(
    premetadata_request_raw: bytes,
    premetadata_report_raw: bytes,
    prevalue_request_raw: bytes,
    trust_profile_raw: bytes,
    expected_trust_profile_sha256: str,
) -> NMFAActivationPreflightReport:
    """Re-execute PREMETADATA and verify PREVALUE; installed V1 remains blocked."""

    if any(
        type(raw) is not bytes
        for raw in (
            premetadata_request_raw,
            premetadata_report_raw,
            prevalue_request_raw,
            trust_profile_raw,
        )
    ):
        _fail(NMFAPreflightErrorCode.INVALID_ARGUMENT)
    resources = _load_resources()
    installed = _installed(resources)
    premetadata = _evaluate_premetadata(
        premetadata_request_raw,
        trust_profile_raw,
        expected_trust_profile_sha256,
        resources,
        installed,
    )
    supplied_report = _decode_canonical_json(
        premetadata_report_raw,
        error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
    )
    _validate_instance(
        supplied_report,
        resources.report_schema,
        error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
    )
    if premetadata.report.report_bytes != premetadata_report_raw:
        _fail(NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)

    validated_trust, trust, trust_valid = _validate_trust_profile(
        trust_profile_raw,
        expected_trust_profile_sha256,
        resources,
    )
    if not trust_valid:
        _fail(NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID)
    request = _parse_request(prevalue_request_raw, resources, "PREVALUE")
    _, subject_sha256 = _request_subject(request)
    signatures_valid = _verify_signatures(request, subject_sha256, trust, trust_valid)
    semantic_reasons = _resource_binding_reasons(
        request,
        validated_trust.trust_profile_sha256,
        installed,
    )
    if not signatures_valid:
        semantic_reasons.add("SIGNATURE_INVALID")
    semantic_reasons.update(_prevalue_semantics(request, premetadata, trust))
    reasons = semantic_reasons | _compiled_blocker_reasons(installed.plan)
    return _report(
        request=request,
        request_raw=prevalue_request_raw,
        subject_sha256=subject_sha256,
        trust_sha256=validated_trust.trust_profile_sha256,
        installed=installed,
        resources=resources,
        reasons=reasons,
        semantic_reasons=semantic_reasons,
        signatures_valid=signatures_valid,
        predecessor_report_sha256=_sha256(premetadata_report_raw),
    )
