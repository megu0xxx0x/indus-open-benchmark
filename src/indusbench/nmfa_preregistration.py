"""Value-blind preregistration feasibility gate for the NMFA experiment.

The public entry point reads only packaged source-free contracts and caller-
supplied canonical JSON bytes.  It performs no network access, file write,
random draw, nonce selection, target-value read, split selection, model fit,
or scientific evaluation.  Real manifests are protected inputs and must not
be committed merely because this module can validate them.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import pairwise, product
from pathlib import Path
from typing import Any, Never, cast

from indusbench.io import encode_json

_PLAN_PATH = "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
_PLAN_SCHEMA_PATH = "schemas/nmfa-value-blind-preregistration-gate-plan.schema.json"
_MANIFEST_SCHEMA_PATH = "schemas/nmfa-value-blind-preregistration-manifest.schema.json"
_REPORT_SCHEMA_PATH = "schemas/nmfa-value-blind-preregistration-report.schema.json"
_EVALUATOR_BUNDLE_PATH = "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"
_PARENT_PROTOCOL_PATH = "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"

_PLAN_SIZE = 30641
_PLAN_SHA256 = "dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
_PLAN_SCHEMA_SIZE = 15667
_PLAN_SCHEMA_SHA256 = "3aba45075fd440affb379e959e4a33cbd24db0c89be22bf2095b7257643b0e03"
_MANIFEST_SCHEMA_SIZE = 47868
_MANIFEST_SCHEMA_SHA256 = "68eb7dbefef5c2bdc4cd670318b190d4beb0db2a7afb5ee096c4e514a6f496c8"
_REPORT_SCHEMA_SIZE = 13980
_REPORT_SCHEMA_SHA256 = "b37b9f4b885ffc0b434924b80a335e6d83e776496678312e7e6388295d0c844e"
_PARENT_PROTOCOL_SIZE = 25450
_PARENT_PROTOCOL_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"

_MAX_JSON_BYTES = 67_108_864
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 2_000_000
_MAX_JSON_STRING_LENGTH = 16_384
_MAX_INTEGER = (1 << 63) - 1
_MIN_INTEGER = -(1 << 63)

_AXES = ("site", "period", "medium", "object_type")
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
_AGGREGATE_PERMISSIONS = ("derive", "publish_aggregate", "prize_submit")

_SOURCE_FRAME_DOMAIN = b"indusbench:nmfa:source-frame:v1\x00"
_POPULATION_DOMAIN = b"indusbench:nmfa:population-inventory:v1\x00"
_CONTEXT_CONTRACT_DOMAIN = b"indusbench:nmfa:context-contract:v1\x00"
_NUISANCE_VOCABULARY_DOMAIN = b"indusbench:nmfa:nuisance-vocabulary:v1\x00"
_PREINVENTORY_CONTRACT_DOMAIN = b"indusbench:nmfa:preinventory-contract:v1\x00"
_RELATION_POLICY_DOMAIN = b"indusbench:nmfa:relation-policy:v1\x00"
_RIGHTS_EVIDENCE_DOMAIN = b"indusbench:nmfa:rights-evidence-set:v1\x00"
_FREEZE_SEQUENCE_DOMAIN = b"indusbench:nmfa:freeze-sequence:v1\x00"
_TRANSCRIPTION_SEAL_DOMAIN = b"indusbench:nmfa:transcription-seal:v1\x00"
_TARGET_SEAL_DOMAIN = b"indusbench:nmfa:target-seal:v1\x00"
_POPULATION_FREEZE_CLAIM_DOMAIN = b"indusbench:nmfa:population-freeze-claim:v1\x00"
_SEALED_F_ROSTER_DOMAIN = b"indusbench:nmfa:sealed-F-roster:v1\x00"
_CLAIM_SLOT_RESERVATION_DOMAIN = b"indusbench:nmfa:claim-slot-reservation:v1\x00"
_IDENTIFIER_KEY_CEREMONY_DOMAIN = b"indusbench:nmfa:identifier-key-ceremony:v1\x00"
_SPLIT_STRUCTURAL_INPUT_DOMAIN = b"indusbench:nmfa:split-structural-input:v1\x00"
_ELIGIBLE_SPLIT_INVENTORY_DOMAIN = b"indusbench:nmfa:eligible-split-inventory:v1\x00"
_MANIFEST_DOMAIN = b"indusbench:nmfa:preregistration-manifest:v1\x00"
_RECEIPT_DOMAIN = b"indusbench:nmfa:preregistration-receipt:v1\x00"
_PRIMARY_F_DOMAIN = b"indusbench:nmfa:preregistration-primary-f:v1\x00"
_SPLIT_ELIGIBLE_TUPLE_ROSTER_DOMAIN = b"indusbench:nmfa:feasible-tuple-roster:v1\x00"

_RELATION_POLICY = {
    "confirmed": ["union"],
    "possible": ["union", "exclude_both"],
    "unresolved": ["union", "exclude_both"],
}
_G_CONTAMINATING_REASONS = frozenset(
    {
        "CONTEXT_INCOMPLETE_OR_CONFLICTING",
        "IDENTITY_UNRESOLVED",
        "PROVENANCE_INCOMPLETE",
        "SOURCE_BINDING_INCOMPLETE",
        "TARGET_AMBIGUOUS_OR_CONFLICTING",
        "TRANSCRIPTION_INCOMPLETE_OR_AMBIGUOUS",
    }
)

_ASSURANCE = {
    "decipherment_claim_allowed": False,
    "execution_authorized": False,
    "externally_registered": False,
    "prize_submission_eligible": False,
    "scientific_result": False,
    "external_evidence_verified_by_gate": False,
    "source_accessed_by_evaluator": False,
    "target_values_loaded_by_gate_or_evaluator": False,
}
_PRIVACY = {
    "aggregate_only": True,
    "context_ids_disclosed": False,
    "item_ids_disclosed": False,
    "paths_disclosed": False,
    "private_values_disclosed": False,
    "publication_review_required": True,
    "public_release_authorized": False,
    "source_names_disclosed": False,
}


class NMFAPreregistrationErrorCode(StrEnum):
    """Stable path- and value-free error surface."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    MANIFEST_CONTRACT_INVALID = "PREFLIGHT_CONTRACT_INVALID"
    PACKAGE_RESOURCE_INVALID = "PACKAGE_RESOURCE_INVALID"
    SCHEMA_DEPENDENCY_MISSING = "SCHEMA_DEPENDENCY_MISSING"


class NMFAPreregistrationError(ValueError):
    """A fixed-code error that never embeds protected input."""

    def __init__(self, code: NMFAPreregistrationErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class _JsonViolation(ValueError):
    pass


@dataclass(frozen=True)
class NMFAGatePlanSnapshot:
    """Immutable identities and thresholds from the installed source-free plan."""

    gate_id: str
    gate_plan_sha256: str
    parent_protocol_sha256: str
    eligible_g_minimum: int
    cell_minimum_g: int
    holdout_minimum_g: int
    complement_minimum_g: int
    n2_minimum_movable_g: int
    n2_minimum_movable_percent: int
    max_tuple_evaluations: int
    max_n2_tuple_evaluations: int
    max_n2_primary_assignments: int
    max_primary_cache_entries: int
    evaluator_bundle_sha256: str
    registration_ready: bool = False
    source_access_authorized: bool = False
    execution_authorized: bool = False


@dataclass(frozen=True, repr=False)
class ValidatedNMFAPreregistrationManifest:
    """Immutable canonical bytes accepted by the closed source-free contract."""

    canonical_bytes: bytes
    manifest_sha256: str
    population_inventory_sha256: str
    source_frame_sha256: str
    unit_count: int

    def __repr__(self) -> str:
        return "<ValidatedNMFAPreregistrationManifest protected>"


@dataclass(frozen=True, repr=False)
class NMFAPreregistrationReport:
    """Private aggregate report with no public-summary surface."""

    terminal_state: str
    reason_codes: tuple[str, ...]
    report_bytes: bytes

    def __repr__(self) -> str:
        return "<NMFAPreregistrationReport protected>"

    def report(self) -> dict[str, Any]:
        """Return a fresh decoded copy of the private aggregate report."""

        value = _decode_canonical_json(self.report_bytes, _MAX_JSON_BYTES)
        if type(value) is not dict:
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
        return value


@dataclass(frozen=True)
class _Resources:
    evaluator_bundle: bytes
    io_source: bytes
    module_source: bytes
    plan: bytes
    plan_schema: bytes
    manifest_schema: bytes
    report_schema: bytes
    parent_protocol: bytes


@dataclass(frozen=True)
class _Component:
    member_ids: tuple[str, ...]
    m_g_member_ids: tuple[str, ...]
    eligible_member_ids: tuple[str, ...]
    contexts: dict[str, frozenset[str]]
    trigger_contexts: dict[str, frozenset[str]]
    complete: bool


@dataclass(frozen=True)
class _TupleAggregate:
    site_cell_g: int
    period_cell_g: int
    medium_cell_g: int
    object_type_cell_g: int
    holdout_g: int
    complement_g: int
    n2_movable_g: int

    def as_dict(self) -> dict[str, int]:
        return {
            "complement_g": self.complement_g,
            "holdout_g": self.holdout_g,
            "medium_cell_g": self.medium_cell_g,
            "n2_movable_g": self.n2_movable_g,
            "object_type_cell_g": self.object_type_cell_g,
            "period_cell_g": self.period_cell_g,
            "site_cell_g": self.site_cell_g,
        }


@dataclass(frozen=True)
class _SearchResult:
    outcome: str
    tuple_evaluations: int
    n2_tuple_evaluations: int
    n2_primary_assignments: int
    split_eligible_tuple_count: int
    split_eligible_tuple_roster_sha256: str | None
    n2_supported_tuple_count: int
    first_aggregate: _TupleAggregate | None


class _UnionFind:
    def __init__(self, identifiers: tuple[str, ...]) -> None:
        self._parent = {identifier: identifier for identifier in identifiers}

    def find(self, identifier: str) -> str:
        parent = self._parent[identifier]
        while parent != self._parent[parent]:
            parent = self._parent[parent]
        while identifier != parent:
            next_identifier = self._parent[identifier]
            self._parent[identifier] = parent
            identifier = next_identifier
        return parent

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        self._parent[second] = first


def _fail(code: NMFAPreregistrationErrorCode) -> Never:
    raise NMFAPreregistrationError(code)


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


def _decode_canonical_json(raw: bytes, max_bytes: int) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > max_bytes or raw.startswith(b"\xef\xbb\xbf"):
        _fail(NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID)
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
        _fail(NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID)
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
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical_utc_timestamp(value: Any) -> bool:
    if type(value) is not str or len(value) != 20 or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _domain_digest(domain: bytes, value: Any) -> str:
    return _sha256(domain + encode_json(value))


def _load_installed_resources() -> _Resources:
    try:
        root = importlib.resources.files("indusbench")
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    if not isinstance(root, Path):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)

    def read(relative: str) -> bytes:
        try:
            return root.joinpath(*relative.split("/")).read_bytes()
        except (OSError, TypeError, ValueError):
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)

    return _Resources(
        evaluator_bundle=read(_EVALUATOR_BUNDLE_PATH),
        io_source=read("io.py"),
        module_source=read("nmfa_preregistration.py"),
        plan=read(_PLAN_PATH),
        plan_schema=read(_PLAN_SCHEMA_PATH),
        manifest_schema=read(_MANIFEST_SCHEMA_PATH),
        report_schema=read(_REPORT_SCHEMA_PATH),
        parent_protocol=read(_PARENT_PROTOCOL_PATH),
    )


def _compile_validator(schema_raw: bytes) -> Any:
    schema = _decode_resource_json(schema_raw)
    if type(schema) is not dict:
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError
    except ImportError:
        _fail(NMFAPreregistrationErrorCode.SCHEMA_DEPENDENCY_MISSING)
    try:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except (SchemaError, TypeError, ValueError):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)


def _validate_instance(value: Any, schema_raw: bytes, *, resource: bool = False) -> None:
    validator = _compile_validator(schema_raw)
    try:
        first_error = next(validator.iter_errors(value), None)
    except Exception:
        if resource:
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
        _fail(NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID)
    if first_error is not None:
        if resource:
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
        _fail(NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID)


def _validate_evaluator_bundle(resources: _Resources) -> tuple[str, str]:
    bundle = _decode_resource_json(resources.evaluator_bundle)
    if type(bundle) is not dict or encode_json(bundle) != resources.evaluator_bundle:
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    if (
        set(bundle)
        != {
            "bundle_id",
            "created_at",
            "files",
            "format_version",
            "runtime_profile",
            "security_boundary",
        }
        or bundle["bundle_id"] != "nmfa-value-blind-preregistration-evaluator-bundle-v1"
        or bundle["format_version"] != "1.0.0"
        or not _canonical_utc_timestamp(bundle["created_at"])
        or type(bundle["files"]) is not list
        or type(bundle["runtime_profile"]) is not dict
        or type(bundle["security_boundary"]) is not dict
    ):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_runtime_profile = {
        "canonical_encoder": "indusbench.io:encode_json",
        "conditional_dependencies": {
            "python_version_less_than_3_13": {"typing-extensions": "4.16.0"}
        },
        "dependencies": {
            "attrs": "26.1.0",
            "jsonschema": "4.26.0",
            "jsonschema-specifications": "2025.9.1",
            "referencing": "0.37.0",
            "rfc3339-validator": "0.1.4",
            "rpds-py": "2026.6.3",
            "six": "1.17.0",
        },
        "dependency_scope": "evaluator_semantic_import_closure_not_all_optional_format_extras",
        "dependency_lock": "uv.lock",
        "entrypoint": "indusbench.nmfa_preregistration:evaluate_preregistration_manifest",
        "implementation": "CPython",
        "supported_python_minors": ["3.11", "3.12", "3.13", "3.14"],
    }
    expected_security_boundary = {
        "external_timestamp_verified_by_bundle": False,
        "real_manifest_included": False,
        "runtime_environment_attested_by_bundle": False,
        "source_values_included": False,
    }
    if (
        bundle["runtime_profile"] != expected_runtime_profile
        or bundle["security_boundary"] != expected_security_boundary
        or sys.implementation.name != "cpython"
        or f"{sys.version_info.major}.{sys.version_info.minor}"
        not in expected_runtime_profile["supported_python_minors"]
    ):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    try:
        observed_dependencies = {
            name: importlib.metadata.version(name)
            for name in expected_runtime_profile["dependencies"]
        }
        if sys.version_info < (3, 13):
            observed_conditional_dependencies = {
                name: importlib.metadata.version(name)
                for name in expected_runtime_profile["conditional_dependencies"][
                    "python_version_less_than_3_13"
                ]
            }
        else:
            observed_conditional_dependencies = {}
    except importlib.metadata.PackageNotFoundError:
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_conditional_dependencies = (
        expected_runtime_profile["conditional_dependencies"]["python_version_less_than_3_13"]
        if sys.version_info < (3, 13)
        else {}
    )
    if (
        observed_dependencies != expected_runtime_profile["dependencies"]
        or observed_conditional_dependencies != expected_conditional_dependencies
    ):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    actual = {
        "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json": resources.plan,
        "benchmark/numeral-metrology-functional-anchor-protocol-v1.json": resources.parent_protocol,
        "schemas/nmfa-value-blind-preregistration-gate-plan.schema.json": resources.plan_schema,
        "schemas/nmfa-value-blind-preregistration-manifest.schema.json": resources.manifest_schema,
        "schemas/nmfa-value-blind-preregistration-report.schema.json": resources.report_schema,
        "src/indusbench/io.py": resources.io_source,
        "src/indusbench/nmfa_preregistration.py": resources.module_source,
    }
    rows = bundle["files"]
    if any(type(row) is not dict or type(row.get("path")) is not str for row in rows):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    paths = cast(list[str], [row["path"] for row in rows])
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_paths = set(actual) | {"pyproject.toml", "uv.lock"}
    if set(paths) != expected_paths:
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    for row in rows:
        if type(row) is not dict or set(row) != {"bytes", "path", "sha256", "verification"}:
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
        path = row["path"]
        if (
            type(row["bytes"]) is not int
            or row["bytes"] <= 0
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 71
            or not row["sha256"].startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in row["sha256"][7:])
            or row["verification"] not in {"runtime_and_ci", "ci_only"}
        ):
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
        if path in actual:
            raw = actual[path]
            if (
                row["verification"] != "runtime_and_ci"
                or row["bytes"] != len(raw)
                or row["sha256"] != _sha256(raw)
            ):
                _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
        elif row["verification"] != "ci_only":
            _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    return _sha256(resources.evaluator_bundle), cast(str, bundle["created_at"])


def _plan_snapshot(
    resources: _Resources,
) -> tuple[NMFAGatePlanSnapshot, dict[str, Any], str]:
    evaluator_bundle_sha256, evaluator_bundle_created_at = _validate_evaluator_bundle(resources)
    if (
        len(resources.plan) != _PLAN_SIZE
        or hashlib.sha256(resources.plan).hexdigest() != _PLAN_SHA256
        or len(resources.plan_schema) != _PLAN_SCHEMA_SIZE
        or hashlib.sha256(resources.plan_schema).hexdigest() != _PLAN_SCHEMA_SHA256
        or len(resources.manifest_schema) != _MANIFEST_SCHEMA_SIZE
        or hashlib.sha256(resources.manifest_schema).hexdigest() != _MANIFEST_SCHEMA_SHA256
        or len(resources.report_schema) != _REPORT_SCHEMA_SIZE
        or hashlib.sha256(resources.report_schema).hexdigest() != _REPORT_SCHEMA_SHA256
        or len(resources.parent_protocol) != _PARENT_PROTOCOL_SIZE
        or hashlib.sha256(resources.parent_protocol).hexdigest() != _PARENT_PROTOCOL_SHA256
    ):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    plan = _decode_resource_json(resources.plan)
    parent = _decode_resource_json(resources.parent_protocol, allow_floats=True)
    if type(plan) is not dict or type(parent) is not dict:
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    _validate_instance(plan, resources.plan_schema, resource=True)
    if (
        plan.get("gate_id") != "nmfa-value-blind-preregistration-gate-v1"
        or plan.get("parent_protocol", {}).get("sha256") != "sha256:" + _PARENT_PROTOCOL_SHA256
        or parent.get("hypothesis_id") != "numeral-metrology-functional-anchor-protocol-v1"
        or parent.get("status") != "draft"
        or plan.get("relation_policy") != _RELATION_POLICY
        or plan.get("g_contaminating_reasons") != sorted(_G_CONTAMINATING_REASONS)
        or not _canonical_utc_timestamp(plan.get("created_at"))
        or not _canonical_utc_timestamp(parent.get("updated_at"))
        or parent["updated_at"] >= plan["created_at"]
        or plan["created_at"] >= evaluator_bundle_created_at
    ):
        _fail(NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID)
    split = plan["split_feasibility"]
    snapshot = NMFAGatePlanSnapshot(
        gate_id=plan["gate_id"],
        gate_plan_sha256="sha256:" + _PLAN_SHA256,
        parent_protocol_sha256="sha256:" + _PARENT_PROTOCOL_SHA256,
        eligible_g_minimum=split["eligible_g_minimum"],
        cell_minimum_g=split["cell_minimum_g"],
        holdout_minimum_g=split["holdout_minimum_g"],
        complement_minimum_g=split["complement_minimum_g"],
        n2_minimum_movable_g=split["n2_minimum_movable_g"],
        n2_minimum_movable_percent=split["n2_minimum_movable_percent"],
        max_tuple_evaluations=plan["limits"]["max_tuple_evaluations"],
        max_n2_tuple_evaluations=plan["limits"]["max_n2_tuple_evaluations"],
        max_n2_primary_assignments=plan["limits"]["max_n2_primary_assignments"],
        max_primary_cache_entries=plan["limits"]["max_primary_cache_entries"],
        evaluator_bundle_sha256=evaluator_bundle_sha256,
    )
    return snapshot, plan, evaluator_bundle_created_at


def load_installed_nmfa_preregistration_gate_plan() -> NMFAGatePlanSnapshot:
    """Validate and summarize the exact source-free installed gate plan."""

    snapshot, _, _ = _plan_snapshot(_load_installed_resources())
    return snapshot


def _source_frame_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "ordered_opaque_source_roster": manifest["source_records"],
        "source_frame": manifest["source_frame"],
    }


def _preinventory_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_policy": manifest["claim_policy"],
        "claim_slot_reservation_receipt": manifest["freeze_sequence"][
            "claim_slot_reservation_receipt"
        ],
        "claim_slot_reservation_sha256": manifest["bindings"]["claim_slot_reservation_sha256"],
        "context_contract": manifest["context_contract"],
        "custody_contract_sha256": manifest["bindings"]["custody_contract_sha256"],
        "evaluator_bundle_sha256": manifest["bindings"]["evaluator_bundle_sha256"],
        "evidence_envelope_contract": manifest["evidence_envelope_contract"],
        "experiment_instance_id": manifest["experiment_instance_id"],
        "gate_plan_sha256": manifest["bindings"]["gate_plan_sha256"],
        "exposure_control": manifest["exposure_control"],
        "governance": manifest["governance"],
        "identifier_contract": manifest["identifier_contract"],
        "identifier_key_ceremony_sha256": manifest["bindings"]["identifier_key_ceremony_sha256"],
        "identifier_key_generation_receipt": manifest["freeze_sequence"][
            "identifier_key_generation_receipt"
        ],
        "n1_deferred_contract": manifest["n1_deferred_contract"],
        "nonce_event_contract": manifest["nonce_event_contract"],
        "parent_protocol_sha256": manifest["bindings"]["parent_protocol_sha256"],
        "prevalue_f_context_inventory": [
            {
                "context": row["context"],
                "context_evidence_envelope_sha256": row["context_evidence_envelope_sha256"],
                "f_id": row["f_id"],
                "physical_identity_evidence_envelope_sha256": row[
                    "physical_identity_evidence_envelope_sha256"
                ],
                "source_membership_complete": row["source_membership_complete"],
            }
            for row in manifest["units"]
        ],
        "prevalue_prior_project_exposure": [
            {
                "f_id": row["f_id"],
                "prior_project_exposure": row["prior_project_exposure"],
            }
            for row in manifest["eligibility"]
        ],
        "prospective": manifest["prospective"],
        "protection": manifest["protection"],
        "relation_policy": _RELATION_POLICY,
        "rights": manifest["rights"],
        "sealed_dataset_contracts": {
            layer: manifest["sealed_datasets"][layer]["contract"]
            for layer in ("target_y", "transcription_x")
        },
        "clean_roles_first_claim_instance_source_metadata_access_receipt": manifest[
            "freeze_sequence"
        ]["clean_roles_first_claim_instance_source_metadata_access_receipt"],
        "source_frame": manifest["source_frame"],
        "source_records": manifest["source_records"],
        "staged_release_contract": manifest["staged_release_contract"],
        "target": manifest["target"],
    }


def _population_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_policy": manifest["claim_policy"],
        "context_contract": manifest["context_contract"],
        "eligibility": manifest["eligibility"],
        "evidence_envelope_contract": manifest["evidence_envelope_contract"],
        "experiment_instance_id": manifest["experiment_instance_id"],
        "exposure": manifest["exposure"],
        "exposure_control": manifest["exposure_control"],
        "identifier_contract": manifest["identifier_contract"],
        "relations": manifest["relations"],
        "sealed_datasets": manifest["sealed_datasets"],
        "source_frame": manifest["source_frame"],
        "source_records": manifest["source_records"],
        "staged_release_contract": manifest["staged_release_contract"],
        "target": manifest["target"],
        "units": manifest["units"],
    }


def _split_structural_input_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    context = manifest["context_contract"]
    return {
        "axis_order": list(_AXES),
        "context_semantics": {
            "closure_tables": context["closure_tables"],
            "nuisance_field_ids": context["nuisance_field_ids"],
            "nuisance_vocabularies": context["nuisance_vocabularies"],
            "provenance_policy": context["provenance_policy"],
        },
        "eligibility": [
            {
                "eligible": row["eligible"],
                "f_id": row["f_id"],
                "g_exclusion_reason": row["g_exclusion_reason"],
                "prior_project_exposure": row["prior_project_exposure"],
                "reason_codes": row["reason_codes"],
            }
            for row in manifest["eligibility"]
        ],
        "relations": [
            {
                "disposition": row["disposition"],
                "kind": row["kind"],
                "left_f_id": row["left_f_id"],
                "right_f_id": row["right_f_id"],
                "status": row["status"],
            }
            for row in manifest["relations"]
        ],
        "units": [{"context": row["context"], "f_id": row["f_id"]} for row in manifest["units"]],
    }


def _population_freeze_claim_payload(
    manifest: dict[str, Any], expected: dict[str, str | None]
) -> dict[str, Any]:
    sequence = manifest["freeze_sequence"]
    return {
        "claim_slot_reservation_receipt": sequence["claim_slot_reservation_receipt"],
        "claim_slot_reservation_sha256": expected["claim_slot_reservation_sha256"],
        "claim_slot_id": manifest["claim_policy"]["claim_slot_id"],
        "evaluator_bundle_sha256": manifest["bindings"]["evaluator_bundle_sha256"],
        "evidence_envelope_contract": manifest["evidence_envelope_contract"],
        "experiment_instance_id": manifest["experiment_instance_id"],
        "gate_plan_sha256": manifest["bindings"]["gate_plan_sha256"],
        "identifier_key_ceremony_sha256": expected["identifier_key_ceremony_sha256"],
        "identifier_key_generation_receipt": sequence["identifier_key_generation_receipt"],
        "parent_protocol_sha256": manifest["bindings"]["parent_protocol_sha256"],
        "population_inventory_sha256": expected["population_inventory_sha256"],
        "preinventory_contract_receipt": sequence["preinventory_contract_receipt"],
        "preinventory_contract_sha256": expected["preinventory_contract_sha256"],
        "source_frame_sha256": expected["source_frame_sha256"],
        "split_structural_input_sha256": expected["split_structural_input_sha256"],
        "earliest_target_y_access_receipt": sequence["earliest_target_y_access_receipt"],
        "target_seal_receipt": sequence["target_seal_receipt"],
        "target_seal_sha256": expected["target_seal_sha256"],
        "earliest_transcription_x_access_receipt": sequence[
            "earliest_transcription_x_access_receipt"
        ],
        "clean_roles_first_claim_instance_source_metadata_access_receipt": sequence[
            "clean_roles_first_claim_instance_source_metadata_access_receipt"
        ],
        "transcription_seal_receipt": sequence["transcription_seal_receipt"],
        "transcription_seal_sha256": expected["transcription_seal_sha256"],
    }


def _claim_slot_reservation_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    frame = manifest["source_frame"]
    context = manifest["context_contract"]
    target = manifest["target"]
    return {
        "claim_policy": manifest["claim_policy"],
        "context_rule_contract": {
            key: context[key]
            for key in (
                "axis_mapping_rule_sha256",
                "multiple_or_overlapping_values_ineligible",
                "nuisance_mapping_rule_sha256",
                "provenance_policy",
                "unknown_values_ineligible",
            )
        },
        "custody_contract_sha256": manifest["bindings"]["custody_contract_sha256"],
        "evaluator_bundle_sha256": manifest["bindings"]["evaluator_bundle_sha256"],
        "evidence_envelope_contract": manifest["evidence_envelope_contract"],
        "experiment_instance_id": manifest["experiment_instance_id"],
        "gate_plan_sha256": manifest["bindings"]["gate_plan_sha256"],
        "governance": manifest["governance"],
        "identifier_policy_without_key_commitment": {
            key: value
            for key, value in manifest["identifier_contract"].items()
            if key != "key_commitment_sha256"
        },
        "nonce_event_contract": manifest["nonce_event_contract"],
        "parent_protocol_sha256": manifest["bindings"]["parent_protocol_sha256"],
        "prospective": manifest["prospective"],
        "protection": manifest["protection"],
        "rights": manifest["rights"],
        "sealed_dataset_contracts": {
            layer: manifest["sealed_datasets"][layer]["contract"]
            for layer in ("target_y", "transcription_x")
        },
        "source_frame_rule_contract": {
            key: frame[key]
            for key in (
                "completeness_rule_committed",
                "enumeration_and_order_rule_sha256",
                "finite",
                "query_and_filter_frozen",
                "query_filter_rule_sha256",
                "revision_policy_sha256",
                "universe_definition_sha256",
            )
        },
        "staged_release_contract": manifest["staged_release_contract"],
        "target_contract_without_opaque_unit_id": {
            key: target[key] for key in target if key != "canonical_unit_id"
        },
    }


def _identifier_key_ceremony_payload(
    manifest: dict[str, Any], claim_slot_reservation_sha256: str
) -> dict[str, Any]:
    return {
        "claim_slot_reservation_receipt": manifest["freeze_sequence"][
            "claim_slot_reservation_receipt"
        ],
        "claim_slot_reservation_sha256": claim_slot_reservation_sha256,
        "claim_slot_id": manifest["claim_policy"]["claim_slot_id"],
        "experiment_instance_id": manifest["experiment_instance_id"],
        "identifier_contract": manifest["identifier_contract"],
    }


def _manifest_digest(manifest: dict[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return _sha256(_MANIFEST_DOMAIN + encode_json(payload))


def _expected_binding_digests(manifest: dict[str, Any]) -> dict[str, str | None]:
    rights_complete = all(row["evidence_sha256"] is not None for row in manifest["rights"])
    claim_slot_reservation_sha256 = _domain_digest(
        _CLAIM_SLOT_RESERVATION_DOMAIN, _claim_slot_reservation_payload(manifest)
    )
    expected: dict[str, str | None] = {
        "claim_slot_reservation_sha256": claim_slot_reservation_sha256,
        "context_contract_sha256": _domain_digest(
            _CONTEXT_CONTRACT_DOMAIN, manifest["context_contract"]
        ),
        "freeze_sequence_sha256": _domain_digest(
            _FREEZE_SEQUENCE_DOMAIN, manifest["freeze_sequence"]
        ),
        "identifier_key_ceremony_sha256": _domain_digest(
            _IDENTIFIER_KEY_CEREMONY_DOMAIN,
            _identifier_key_ceremony_payload(manifest, claim_slot_reservation_sha256),
        ),
        "population_inventory_sha256": _domain_digest(
            _POPULATION_DOMAIN, _population_payload(manifest)
        ),
        "preinventory_contract_sha256": _domain_digest(
            _PREINVENTORY_CONTRACT_DOMAIN, _preinventory_payload(manifest)
        ),
        "relation_policy_sha256": _domain_digest(_RELATION_POLICY_DOMAIN, _RELATION_POLICY),
        "rights_evidence_set_sha256": (
            _domain_digest(_RIGHTS_EVIDENCE_DOMAIN, manifest["rights"]) if rights_complete else None
        ),
        "source_frame_sha256": _domain_digest(
            _SOURCE_FRAME_DOMAIN, _source_frame_payload(manifest)
        ),
        "split_structural_input_sha256": _domain_digest(
            _SPLIT_STRUCTURAL_INPUT_DOMAIN, _split_structural_input_payload(manifest)
        ),
        "target_seal_sha256": _domain_digest(
            _TARGET_SEAL_DOMAIN, manifest["sealed_datasets"]["target_y"]
        ),
        "transcription_seal_sha256": _domain_digest(
            _TRANSCRIPTION_SEAL_DOMAIN, manifest["sealed_datasets"]["transcription_x"]
        ),
    }
    expected["population_freeze_claim_sha256"] = _domain_digest(
        _POPULATION_FREEZE_CLAIM_DOMAIN,
        _population_freeze_claim_payload(manifest, expected),
    )
    return expected


def _freeze_sequence_is_consistent(
    manifest: dict[str, Any], expected: dict[str, str | None]
) -> bool:
    sequence = manifest["freeze_sequence"]
    reservation = sequence["claim_slot_reservation_receipt"]
    identifier_key = sequence["identifier_key_generation_receipt"]
    pre = sequence["preinventory_contract_receipt"]
    source_access = sequence["clean_roles_first_claim_instance_source_metadata_access_receipt"]
    x_access = sequence["earliest_transcription_x_access_receipt"]
    y_access = sequence["earliest_target_y_access_receipt"]
    x_seal = sequence["transcription_seal_receipt"]
    y_seal = sequence["target_seal_receipt"]
    population = sequence["population_inventory_receipt"]
    expected_kinds = {
        "claim_slot_reservation_receipt": "claim_slot_reservation",
        "earliest_target_y_access_receipt": "earliest_target_y_access",
        "earliest_transcription_x_access_receipt": "earliest_transcription_x_access",
        "identifier_key_generation_receipt": "identifier_key_ceremony",
        "population_inventory_receipt": "population_freeze_claim",
        "preinventory_contract_receipt": "preinventory_contract",
        "clean_roles_first_claim_instance_source_metadata_access_receipt": (
            "clean_roles_first_claim_instance_source_metadata_access"
        ),
        "target_seal_receipt": "target_seal",
        "transcription_seal_receipt": "transcription_seal",
    }
    return (
        all(sequence[name]["receipt_kind"] == kind for name, kind in expected_kinds.items())
        and reservation["subject_sha256"] == expected["claim_slot_reservation_sha256"]
        and identifier_key["subject_sha256"] == expected["identifier_key_ceremony_sha256"]
        and source_access["subject_sha256"] == expected["identifier_key_ceremony_sha256"]
        and pre["subject_sha256"] == expected["preinventory_contract_sha256"]
        and x_access["subject_sha256"] == expected["preinventory_contract_sha256"]
        and y_access["subject_sha256"] == expected["preinventory_contract_sha256"]
        and x_seal["subject_sha256"] == expected["transcription_seal_sha256"]
        and y_seal["subject_sha256"] == expected["target_seal_sha256"]
        and population["subject_sha256"] == expected["population_freeze_claim_sha256"]
        and reservation["recorded_at"]
        < identifier_key["recorded_at"]
        < source_access["recorded_at"]
        < pre["recorded_at"]
        and pre["recorded_at"] < x_access["recorded_at"] < x_seal["recorded_at"]
        and pre["recorded_at"] < y_access["recorded_at"] < y_seal["recorded_at"]
        and x_seal["recorded_at"] < population["recorded_at"]
        and y_seal["recorded_at"] < population["recorded_at"]
        and population["recorded_at"] < manifest["created_at"]
        and len(
            {
                pre["receipt_id"],
                reservation["receipt_id"],
                identifier_key["receipt_id"],
                source_access["receipt_id"],
                x_access["receipt_id"],
                y_access["receipt_id"],
                x_seal["receipt_id"],
                y_seal["receipt_id"],
                population["receipt_id"],
            }
        )
        == 9
    )


def _validate_manifest_with_resources(
    raw: bytes, resources: _Resources
) -> tuple[ValidatedNMFAPreregistrationManifest, dict[str, Any], NMFAGatePlanSnapshot]:
    snapshot, plan, evaluator_bundle_created_at = _plan_snapshot(resources)
    value = _decode_canonical_json(raw, _MAX_JSON_BYTES)
    if type(value) is not dict:
        _fail(NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID)
    _validate_instance(value, resources.manifest_schema)
    bindings = value["bindings"]
    expected = _expected_binding_digests(value)
    n1_sampler_digest = _domain_digest(
        b"indusbench:nmfa:n1-sampler-contract:v1\x00", plan["n1"]["sampler"]
    )
    if (
        bindings["gate_plan_sha256"] != snapshot.gate_plan_sha256
        or bindings["evaluator_bundle_sha256"] != snapshot.evaluator_bundle_sha256
        or bindings["parent_protocol_sha256"] != snapshot.parent_protocol_sha256
        or value["manifest_sha256"] != _manifest_digest(value)
        or any(bindings[key] != digest for key, digest in expected.items())
        or not _freeze_sequence_is_consistent(value, expected)
        or evaluator_bundle_created_at
        >= value["freeze_sequence"]["claim_slot_reservation_receipt"]["recorded_at"]
        or value["n1_deferred_contract"]["sampler_contract_sha256"] != n1_sampler_digest
    ):
        _fail(NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID)
    validated = ValidatedNMFAPreregistrationManifest(
        canonical_bytes=raw,
        manifest_sha256=value["manifest_sha256"],
        population_inventory_sha256=bindings["population_inventory_sha256"],
        source_frame_sha256=bindings["source_frame_sha256"],
        unit_count=len(value["units"]),
    )
    return validated, value, snapshot


def validate_preregistration_manifest(raw: bytes) -> ValidatedNMFAPreregistrationManifest:
    """Validate one protected canonical value-blind manifest from bytes only."""

    if type(raw) is not bytes:
        _fail(NMFAPreregistrationErrorCode.INVALID_ARGUMENT)
    validated, _, _ = _validate_manifest_with_resources(raw, _load_installed_resources())
    return validated


def _complete_context(manifest: dict[str, Any], unit: dict[str, Any]) -> bool:
    context = unit["context"]
    contract = manifest["context_contract"]
    return all(type(context[axis]) is str for axis in _AXES) and len(context["nuisance"]) == len(
        contract["nuisance_field_ids"]
    )


def _cached_subset(
    closures_for_axis: dict[str, frozenset[str]],
    cache: dict[tuple[str, str], bool],
    left_id: str,
    right_id: str,
) -> bool:
    key = (left_id, right_id)
    if key not in cache:
        cache[key] = closures_for_axis[left_id].issubset(closures_for_axis[right_id])
    return cache[key]


def _context_semantics(
    manifest: dict[str, Any], units: list[dict[str, Any]]
) -> tuple[bool, dict[str, dict[str, frozenset[str]]]]:
    contract = manifest["context_contract"]
    invalid = not (
        contract["alias_and_descendant_closures_frozen"]
        and contract["canonical_vocabularies_frozen"]
        and contract["nuisance_fields_complete"]
        and contract["provenance_policy"] != "incomplete"
    )
    fields = contract["nuisance_field_ids"]
    vocabularies = contract["nuisance_vocabularies"]
    if contract["nuisance_value_vocabularies_sha256"] != _domain_digest(
        _NUISANCE_VOCABULARY_DOMAIN, vocabularies
    ):
        invalid = True
    if [row["field_id"] for row in vocabularies] != fields:
        invalid = True
    allowed_nuisance_values: list[set[str]] = []
    for row in vocabularies:
        values = row["canonical_value_ids"]
        if values != sorted(values) or len(set(values)) != len(values):
            invalid = True
        allowed_nuisance_values.append(set(values))
    if contract["provenance_policy"] == "single_prespecified_regime":
        invalid = (
            invalid
            or bool(fields)
            or bool(vocabularies)
            or contract["single_regime_contract_sha256"] is None
        )
    elif contract["provenance_policy"] == "complete_canonical_nuisance_tuple":
        invalid = invalid or not fields or contract["single_regime_contract_sha256"] is not None
    else:
        invalid = True
    for unit in units:
        nuisance = unit["context"]["nuisance"]
        if len(nuisance) > len(allowed_nuisance_values) or any(
            value not in allowed_nuisance_values[index]
            for index, value in enumerate(nuisance)
            if index < len(allowed_nuisance_values)
        ):
            invalid = True

    tables = contract["closure_tables"]
    if [table["axis"] for table in tables] != list(_AXES):
        invalid = True
    closures: dict[str, dict[str, frozenset[str]]] = {axis: {} for axis in _AXES}
    for table in tables:
        axis = table["axis"]
        groups = table["groups"]
        group_ids = [group["group_id"] for group in groups]
        if group_ids != sorted(group_ids) or len(set(group_ids)) != len(group_ids):
            invalid = True
        member_sets: set[tuple[str, ...]] = set()
        for group in groups:
            members = group["member_value_ids"]
            canonical_members = tuple(sorted(members))
            if members != list(canonical_members) or group["group_id"] not in members:
                invalid = True
            if canonical_members in member_sets:
                invalid = True
            member_sets.add(canonical_members)
            closures[axis][group["group_id"]] = frozenset(members)

    for axis in _AXES:
        group_ids = set(closures[axis])
        subset_cache: dict[tuple[str, str], bool] = {}

        containing_groups: dict[str, list[str]] = defaultdict(list)
        for parent_id, parent_members in closures[axis].items():
            for child_id in parent_members & group_ids:
                if not _cached_subset(closures[axis], subset_cache, child_id, parent_id):
                    invalid = True
            for member_id in parent_members:
                containing_groups[member_id].append(parent_id)
        for containers in containing_groups.values():
            ordered = sorted(
                containers, key=lambda group_id: (len(closures[axis][group_id]), group_id)
            )
            for smaller, larger in pairwise(ordered):
                if not _cached_subset(closures[axis], subset_cache, smaller, larger):
                    invalid = True
        observed = {unit["context"][axis] for unit in units if type(unit["context"][axis]) is str}
        if not observed.issubset(group_ids):
            invalid = True
    return invalid, closures


def _sealed_datasets_are_consistent(manifest: dict[str, Any]) -> bool:
    sealed = manifest["sealed_datasets"]
    x = sealed["transcription_x"]
    y = sealed["target_y"]
    expected = {
        "transcription_x": (
            "independent_transcription_archive_custodian",
            "all_F_to_approved_X_or_explicit_status_with_side_line_token_allograph_order_and_source_revision_binding",
        ),
        "target_y": (
            "independent_target_archive_custodian",
            "all_F_to_exact_rational_Y_or_explicit_status_with_family_unit_conversion_missingness_and_repeated_resolution",
        ),
    }
    unit_count = len(manifest["units"])
    ordered_f_ids = [unit["f_id"] for unit in manifest["units"]]
    for layer, row in (("target_y", y), ("transcription_x", x)):
        role, scope = expected[layer]
        expected_roster_digest = _domain_digest(
            _SEALED_F_ROSTER_DOMAIN,
            {
                "claim_slot_id": manifest["claim_policy"]["claim_slot_id"],
                "data_layer": layer,
                "experiment_instance_id": manifest["experiment_instance_id"],
                "ordered_f_ids": ordered_f_ids,
            },
        )
        if (
            row["data_layer"] != layer
            or row["contract"]["archive_custodian_role"] != role
            or row["contract"]["payload_scope"] != scope
            or row["commitment"]["committed_f_count"] != unit_count
            or row["commitment"]["ordered_f_roster_sha256"] != expected_roster_digest
        ):
            return False
    return (
        len(
            {
                x["commitment"]["ciphertext_archive_manifest_sha256"],
                y["commitment"]["ciphertext_archive_manifest_sha256"],
            }
        )
        == 2
        and len(
            {
                x["commitment"]["ciphertext_merkle_root_sha256"],
                y["commitment"]["ciphertext_merkle_root_sha256"],
            }
        )
        == 2
        and len(
            {
                x["contract"]["canonical_payload_contract_sha256"],
                y["contract"]["canonical_payload_contract_sha256"],
            }
        )
        == 2
    )


def _population_semantics(
    manifest: dict[str, Any],
) -> tuple[
    bool,
    bool,
    tuple[_Component, ...],
    dict[str, dict[str, Any]],
    dict[str, bool],
    dict[str, dict[str, frozenset[str]]],
]:
    units = manifest["units"]
    source_records = manifest["source_records"]
    eligibility_rows = manifest["eligibility"]
    relations = manifest["relations"]
    population_invalid = not _sealed_datasets_are_consistent(manifest)
    dependence_invalid = False

    unit_ids = tuple(unit["f_id"] for unit in units)
    if unit_ids != tuple(sorted(unit_ids)) or len(set(unit_ids)) != len(unit_ids):
        population_invalid = True
    units_by_id = {unit["f_id"]: unit for unit in units}
    frame = manifest["source_frame"]
    if frame["declared_physical_original_count"] != len(units) or frame[
        "declared_source_entry_count"
    ] != len(source_records):
        population_invalid = True

    entry_ids = [record["source_entry_id"] for record in source_records]
    entry_keys = [
        (
            record["source_record_id"],
            record["source_revision_id"],
            record["source_view_id"],
        )
        for record in source_records
    ]
    record_to_f: dict[str, str] = {}
    record_assignment_conflict = False
    for record in source_records:
        prior = record_to_f.setdefault(record["source_record_id"], record["f_id"])
        if prior != record["f_id"]:
            record_assignment_conflict = True
    if (
        [record["source_order"] for record in source_records] != list(range(len(source_records)))
        or len(set(entry_ids)) != len(entry_ids)
        or len(set(entry_keys)) != len(entry_keys)
        or any(record["f_id"] not in units_by_id for record in source_records)
        or {record["f_id"] for record in source_records} != set(unit_ids)
        or record_assignment_conflict
    ):
        population_invalid = True

    e_ids = [row["f_id"] for row in eligibility_rows]
    if e_ids != sorted(e_ids) or len(set(e_ids)) != len(e_ids) or set(e_ids) != set(unit_ids):
        population_invalid = True
    eligibility = {row["f_id"]: row for row in eligibility_rows if row["f_id"] in units_by_id}
    if any(
        row["reason_codes"] != sorted(row["reason_codes"])
        or len(set(row["reason_codes"])) != len(row["reason_codes"])
        for row in eligibility_rows
    ):
        population_invalid = True

    context_invalid, closures = _context_semantics(manifest, units)
    dependence_invalid = dependence_invalid or context_invalid

    union_find = _UnionFind(unit_ids)
    exclude_edges: list[tuple[str, str]] = []
    relation_keys: list[tuple[str, str, str, str, str]] = []
    for relation in relations:
        left = relation["left_f_id"]
        right = relation["right_f_id"]
        key = (left, right, relation["kind"], relation["status"], relation["disposition"])
        relation_keys.append(key)
        if left >= right or left not in units_by_id or right not in units_by_id:
            population_invalid = True
            continue
        allowed = _RELATION_POLICY.get(relation["status"], [])
        if relation["disposition"] not in allowed:
            dependence_invalid = True
            continue
        if relation["disposition"] == "union":
            union_find.union(left, right)
        else:
            exclude_edges.append((left, right))
    if relation_keys != sorted(relation_keys) or len(set(relation_keys)) != len(relation_keys):
        population_invalid = True

    excluded_roots: set[str] = set()
    for left, right in exclude_edges:
        excluded_roots.update((union_find.find(left), union_find.find(right)))
    exposure_roots = {
        union_find.find(f_id) for f_id, row in eligibility.items() if row["prior_project_exposure"]
    }
    conflict_roots = {
        union_find.find(f_id)
        for f_id, row in eligibility.items()
        if set(row["reason_codes"]) & _G_CONTAMINATING_REASONS
        or not _complete_context(manifest, units_by_id[f_id])
    }

    e_flags = {f_id: bool(row["eligible"]) for f_id, row in eligibility.items()}
    eligibility_flags: dict[str, bool] = {}
    for f_id in unit_ids:
        row = eligibility.get(f_id)
        root = union_find.find(f_id)
        if root in exposure_roots:
            expected_g_reason = "PRIOR_EXPOSURE_COMPONENT"
        elif root in conflict_roots:
            expected_g_reason = "CONFLICT_COMPONENT"
        elif root in excluded_roots:
            expected_g_reason = "DEPENDENCE_COMPONENT"
        else:
            expected_g_reason = "NONE"
        if row is None or row["g_exclusion_reason"] != expected_g_reason:
            dependence_invalid = True
        eligibility_flags[f_id] = e_flags.get(f_id, False) and expected_g_reason == "NONE"

    groups: dict[str, list[str]] = defaultdict(list)
    for f_id in unit_ids:
        groups[union_find.find(f_id)].append(f_id)

    components: list[_Component] = []
    for members in sorted(tuple(sorted(group)) for group in groups.values()):
        m_g_members = tuple(f_id for f_id in members if e_flags.get(f_id, False))
        eligible_members = tuple(f_id for f_id in members if eligibility_flags.get(f_id, False))
        complete = all(_complete_context(manifest, units_by_id[f_id]) for f_id in members)
        if eligible_members and not complete:
            dependence_invalid = True
        contexts = {
            axis: frozenset(
                units_by_id[f_id]["context"][axis]
                for f_id in members
                if type(units_by_id[f_id]["context"][axis]) is str
            )
            for axis in _AXES
        }
        trigger_contexts = {
            axis: frozenset(
                units_by_id[f_id]["context"][axis]
                for f_id in eligible_members
                if type(units_by_id[f_id]["context"][axis]) is str
            )
            for axis in _AXES
        }
        components.append(
            _Component(
                member_ids=members,
                m_g_member_ids=m_g_members,
                eligible_member_ids=eligible_members,
                contexts=contexts,
                trigger_contexts=trigger_contexts,
                complete=complete,
            )
        )
    return (
        population_invalid,
        dependence_invalid,
        tuple(components),
        units_by_id,
        eligibility_flags,
        closures,
    )


def _eligible_split_inventory_digest(
    components: tuple[_Component, ...],
    units_by_id: dict[str, dict[str, Any]],
    eligibility_flags: dict[str, bool],
    closures: dict[str, dict[str, frozenset[str]]],
    context_contract: dict[str, Any],
) -> str:
    component_payloads: list[dict[str, Any]] = []
    for component in components:
        m_g_members = set(component.m_g_member_ids)
        component_payloads.append(
            {
                "complete_c": component.complete,
                "m_g_member_ids": list(component.m_g_member_ids),
                "members": [
                    {
                        "context": units_by_id[f_id]["context"],
                        "e_eligible": f_id in m_g_members,
                        "f_id": f_id,
                        "split_eligible": eligibility_flags[f_id],
                    }
                    for f_id in component.member_ids
                ],
                "split_eligible_g": bool(component.eligible_member_ids) and component.complete,
            }
        )
    payload = {
        "axis_order": list(_AXES),
        "closure_tables": {
            axis: [
                {"group_id": group_id, "member_value_ids": sorted(members)}
                for group_id, members in sorted(closures[axis].items())
            ]
            for axis in _AXES
        },
        "nuisance_semantics": {
            "nuisance_field_ids": context_contract["nuisance_field_ids"],
            "nuisance_vocabularies": context_contract["nuisance_vocabularies"],
            "provenance_policy": context_contract["provenance_policy"],
        },
        "components": component_payloads,
    }
    return _domain_digest(_ELIGIBLE_SPLIT_INVENTORY_DOMAIN, payload)


def _candidate_bitsets(
    eligible: tuple[_Component, ...],
    closures: dict[str, dict[str, frozenset[str]]],
    minimum: int,
) -> tuple[
    dict[str, tuple[str, ...]],
    dict[str, dict[str, int]],
    dict[str, dict[str, int]],
]:
    candidates: dict[str, tuple[str, ...]] = {}
    cells: dict[str, dict[str, int]] = {axis: {} for axis in _AXES}
    triggers: dict[str, dict[str, int]] = {axis: {} for axis in _AXES}
    for axis in _AXES:
        for group_id, members in closures[axis].items():
            cell_bits = 0
            trigger_bits = 0
            for index, component in enumerate(eligible):
                bit = 1 << index
                if component.contexts[axis] & members:
                    cell_bits |= bit
                if component.trigger_contexts[axis] & members:
                    trigger_bits |= bit
            cells[axis][group_id] = cell_bits
            triggers[axis][group_id] = trigger_bits
        candidates[axis] = tuple(
            group_id
            for group_id in sorted(triggers[axis])
            if triggers[axis][group_id].bit_count() >= minimum
        )
    return candidates, cells, triggers


def _primary_f(
    component: _Component,
    axis: str,
    closure_members: frozenset[str],
    gate_plan_digest: str,
    units_by_id: dict[str, dict[str, Any]],
    rank_by_f: dict[str, tuple[bytes, bytes]] | None = None,
) -> str | None:
    candidates = [
        f_id
        for f_id in component.eligible_member_ids
        if units_by_id[f_id]["context"][axis] in closure_members
    ]
    if not candidates:
        return None

    def key(f_id: str) -> tuple[bytes, bytes]:
        if rank_by_f is not None:
            return rank_by_f[f_id]
        encoded_f_id = f_id.encode("ascii")
        return (
            hashlib.sha256(
                _PRIMARY_F_DOMAIN + gate_plan_digest.encode("ascii") + b"\x00" + encoded_f_id
            ).digest(),
            encoded_f_id,
        )

    return min(candidates, key=key)


def _iter_set_bits(bits: int):
    while bits:
        least = bits & -bits
        yield least.bit_length() - 1
        bits ^= least


def _tuple_search(
    components: tuple[_Component, ...],
    units_by_id: dict[str, dict[str, Any]],
    closures: dict[str, dict[str, frozenset[str]]],
    gate_plan_digest: str,
    snapshot: NMFAGatePlanSnapshot,
) -> _SearchResult:
    eligible = tuple(
        component
        for component in components
        if component.eligible_member_ids and component.complete
    )
    candidates, cell_bits, trigger_bits = _candidate_bitsets(
        eligible, closures, snapshot.cell_minimum_g
    )
    all_bits = (1 << len(eligible)) - 1
    n2_evaluations = 0
    n2_primary_assignments = 0
    tuple_evaluations = 0
    split_eligible_tuples: list[list[str]] = []
    n2_supported_tuple_count = 0
    first_aggregate: _TupleAggregate | None = None
    primary_cache: dict[tuple[int, str, str], str | None] = {}
    rank_by_f = {
        f_id: (
            hashlib.sha256(
                _PRIMARY_F_DOMAIN
                + gate_plan_digest.encode("ascii")
                + b"\x00"
                + f_id.encode("ascii")
            ).digest(),
            f_id.encode("ascii"),
        )
        for f_id in units_by_id
    }
    for raw_tuple in product(*(candidates[axis] for axis in _AXES)):
        tuple_evaluations += 1
        if tuple_evaluations > snapshot.max_tuple_evaluations:
            return _SearchResult(
                "LIMIT_REACHED",
                tuple_evaluations - 1,
                n2_evaluations,
                n2_primary_assignments,
                0,
                None,
                0,
                None,
            )
        canonical_tuple = cast(tuple[str, str, str, str], raw_tuple)
        remaining = all_bits
        cells: dict[str, int] = {}
        for axis, group_id in zip(_AXES, canonical_tuple, strict=True):
            cell = remaining & cell_bits[axis][group_id]
            cells[axis] = cell
            if cell.bit_count() < snapshot.cell_minimum_g or cell & (
                all_bits ^ trigger_bits[axis][group_id]
            ):
                break
            remaining ^= cell
        else:
            holdout_count = sum(cells[axis].bit_count() for axis in _AXES)
            if (
                holdout_count < snapshot.holdout_minimum_g
                or remaining.bit_count() < snapshot.complement_minimum_g
            ):
                continue
            split_eligible_tuples.append(list(canonical_tuple))
            if n2_evaluations >= snapshot.max_n2_tuple_evaluations:
                return _SearchResult(
                    "LIMIT_REACHED",
                    tuple_evaluations,
                    n2_evaluations,
                    n2_primary_assignments,
                    0,
                    None,
                    0,
                    None,
                )
            if n2_primary_assignments + holdout_count > snapshot.max_n2_primary_assignments:
                return _SearchResult(
                    "LIMIT_REACHED",
                    tuple_evaluations,
                    n2_evaluations,
                    n2_primary_assignments,
                    0,
                    None,
                    0,
                    None,
                )
            n2_evaluations += 1
            n2_primary_assignments += holdout_count
            strata: Counter[tuple[str, ...]] = Counter()
            primary_complete = True
            for axis, group_id in zip(_AXES, canonical_tuple, strict=True):
                for index in _iter_set_bits(cells[axis]):
                    cache_key = (index, axis, group_id)
                    if cache_key not in primary_cache:
                        if len(primary_cache) >= snapshot.max_primary_cache_entries:
                            return _SearchResult(
                                "LIMIT_REACHED",
                                tuple_evaluations,
                                n2_evaluations,
                                n2_primary_assignments,
                                0,
                                None,
                                0,
                                None,
                            )
                        primary_cache[cache_key] = _primary_f(
                            eligible[index],
                            axis,
                            closures[axis][group_id],
                            gate_plan_digest,
                            units_by_id,
                            rank_by_f,
                        )
                    primary = primary_cache[cache_key]
                    if primary is None:
                        primary_complete = False
                        break
                    context = units_by_id[primary]["context"]
                    strata[(axis, *(context[name] for name in _AXES), *context["nuisance"])] += 1
                if not primary_complete:
                    break
            movable = (
                sum(count for count in strata.values() if count >= 2) if primary_complete else 0
            )
            aggregate = _TupleAggregate(
                site_cell_g=cells["site"].bit_count(),
                period_cell_g=cells["period"].bit_count(),
                medium_cell_g=cells["medium"].bit_count(),
                object_type_cell_g=cells["object_type"].bit_count(),
                holdout_g=holdout_count,
                complement_g=remaining.bit_count(),
                n2_movable_g=movable,
            )
            if first_aggregate is None:
                first_aggregate = aggregate
            if (
                movable >= snapshot.n2_minimum_movable_g
                and movable * 100 >= snapshot.n2_minimum_movable_percent * holdout_count
            ):
                n2_supported_tuple_count += 1
    if split_eligible_tuples:
        roster_digest = _domain_digest(
            _SPLIT_ELIGIBLE_TUPLE_ROSTER_DOMAIN,
            {"canonical_tuples": split_eligible_tuples},
        )
        return _SearchResult(
            (
                "EXHAUSTED_SPLIT_ROSTER_N2_SAFE"
                if n2_supported_tuple_count == len(split_eligible_tuples)
                else "EXHAUSTED_SPLIT_ROSTER_N2_UNSAFE"
            ),
            tuple_evaluations,
            n2_evaluations,
            n2_primary_assignments,
            len(split_eligible_tuples),
            roster_digest,
            n2_supported_tuple_count,
            first_aggregate,
        )
    return _SearchResult(
        "EXHAUSTED_NO_SPLIT_ELIGIBLE_TUPLE",
        tuple_evaluations,
        n2_evaluations,
        n2_primary_assignments,
        0,
        None,
        0,
        None,
    )


def _rights_ready(manifest: dict[str, Any]) -> bool:
    rows = manifest["rights"]
    if [row["layer"] for row in rows] != list(_RIGHTS_LAYERS):
        return False
    for row in rows[:-1]:
        if row["evidence_sha256"] is None or any(
            row["purposes"][permission] != "permitted" for permission in _DATA_PERMISSIONS
        ):
            return False
    aggregate = rows[-1]
    return aggregate["evidence_sha256"] is not None and all(
        aggregate["purposes"][permission] == "permitted" for permission in _AGGREGATE_PERMISSIONS
    )


def _declaration_terminal(manifest: dict[str, Any]) -> tuple[str, tuple[str, ...]] | None:
    exposure = manifest["exposure"]
    forbidden_exposure = any(
        exposure[key]
        for key in (
            "holdout_mapping_opened",
            "development_subset_values_released",
            "holdout_x_seen_by_evaluator_or_model_before_model_freeze",
            "holdout_y_seen_before_prediction_manifest_freeze",
            "numeric_y_seen_by_context_curator_role",
            "numeric_y_seen_by_evaluator_role",
            "numeric_y_seen_by_identifier_custodian_role",
            "numeric_y_seen_by_physical_identity_curator_role",
            "numeric_y_seen_by_relation_curator_role",
            "numeric_y_seen_by_split_role",
            "numeric_y_seen_by_source_frame_curator_role",
            "numeric_y_seen_by_transcription_role",
            "numeric_y_seen_by_transcription_seal_custodian_role",
            "score_or_prediction_material_present",
            "score_or_predictions_seen_by_target_curator_role",
            "sealed_record_keys_released_before_external_registration",
            "transcription_x_seen_by_identifier_custodian_role",
            "transcription_x_seen_by_relation_curator_role",
            "transcription_x_seen_by_evaluator_or_model_before_split_receipt",
            "transcription_x_seen_by_target_seal_custodian_role",
            "transcription_x_seen_by_target_curator_role",
            "unkeyed_target_value_digest_present",
        )
    )
    if forbidden_exposure:
        return "SOURCE_VALUE_BLINDNESS_BREACH", ("EXPOSURE_DECLARATION_BREACH",)
    governance = manifest["governance"]
    authority_ready = (
        governance["source_access_authority"] == "authorized"
        and governance["external_registration_capability"] == "verified"
        and governance["authority_evidence_sha256"] is not None
        and governance["registration_route_evidence_sha256"] is not None
    )
    if not authority_ready:
        return "AUTHORITY_BLOCKED", ("AUTHORITY_ATTESTATION_INCOMPLETE",)
    if not _rights_ready(manifest):
        return "RIGHTS_BLOCKED", ("RIGHTS_ATTESTATION_INCOMPLETE",)
    custody_ready = (
        governance["protected_custody_capability"] == "verified"
        and governance["independent_role_separation_capability"] == "verified"
        and governance["role_assignment_contract_sha256"] is not None
        and governance["role_separation_evidence_sha256"] is not None
        and manifest["bindings"]["custody_contract_sha256"] is not None
    )
    if not custody_ready:
        return "CUSTODY_BLOCKED", ("CUSTODY_ATTESTATION_INCOMPLETE",)
    prospective_ready = all(
        manifest["prospective"][key]
        for key in (
            "complete_future_frame_committed",
            "first_availability_policy_committed",
            "fixed_close_date_rule_committed",
            "power_or_sensitivity_rationale_committed",
        )
    )
    target_ready = (
        manifest["target"]["contract_complete"]
        and manifest["exposure"]["numeric_y_seen_by_target_curator"]
        and manifest["exposure"]["numeric_y_seen_by_target_seal_custodian_role"]
        and prospective_ready
    )
    if not target_ready:
        return "TARGET_CONTRACT_INCOMPLETE", ("TARGET_OR_PROSPECTIVE_CONTRACT_INCOMPLETE",)
    frame = manifest["source_frame"]
    exposure_control = manifest["exposure_control"]
    frame_ready = (
        frame["finite"]
        and frame["complete"]
        and frame["completeness_rule_committed"]
        and frame["exact_revisions_frozen"]
        and frame["ordered_roster_committed"]
        and frame["pagination_or_enumeration_complete"]
        and frame["query_and_filter_frozen"]
        and frame["mutation_status"] == "stable"
        and manifest["exposure"]["source_records_seen_by_curator_roles"]
        and manifest["exposure"]["transcription_x_seen_by_transcription_role"]
        and manifest["exposure"]["transcription_x_seen_by_transcription_seal_custodian_role"]
        and exposure_control["candidate_coverage_complete"]
        and exposure_control["exposed_f_marking_complete"]
    )
    if not frame_ready:
        return "SOURCE_FRAME_INCOMPLETE", ("SOURCE_FRAME_ATTESTATION_INCOMPLETE",)
    return None


def _evaluate_with_resources(raw: bytes, resources: _Resources) -> NMFAPreregistrationReport:
    validated, manifest, snapshot = _validate_manifest_with_resources(raw, resources)
    early = _declaration_terminal(manifest)
    search = _SearchResult("NOT_RUN", 0, 0, 0, 0, None, 0, None)
    eligible_split_inventory_sha256: str | None = None
    if early is not None:
        terminal, reasons = early
        components = ()
        eligibility_flags = {}
        eligible_components = ()
        structural_counts_evaluated = False
    else:
        (
            population_invalid,
            dependence_invalid,
            components,
            units_by_id,
            eligibility_flags,
            closures,
        ) = _population_semantics(manifest)
        structural_counts_evaluated = True
        if not population_invalid and not dependence_invalid:
            eligible_split_inventory_sha256 = _eligible_split_inventory_digest(
                components,
                units_by_id,
                eligibility_flags,
                closures,
                manifest["context_contract"],
            )
        eligible_components = tuple(
            component
            for component in components
            if component.eligible_member_ids and component.complete
        )
        if population_invalid:
            terminal, reasons = (
                "POPULATION_MANIFEST_INVALID",
                ("POPULATION_OR_SOURCE_ROSTER_INCONSISTENT",),
            )
        elif dependence_invalid:
            terminal, reasons = (
                "DEPENDENCE_CONTEXT_INVALID",
                ("DEPENDENCE_OR_CONTEXT_CONTRACT_INVALID",),
            )
        elif len(eligible_components) < snapshot.eligible_g_minimum:
            terminal, reasons = (
                "INSUFFICIENT_ELIGIBLE_G",
                ("ELIGIBLE_G_BELOW_MINIMUM",),
            )
        else:
            search = _tuple_search(
                components,
                units_by_id,
                closures,
                snapshot.gate_plan_sha256,
                snapshot,
            )
            if search.outcome == "LIMIT_REACHED":
                terminal, reasons = (
                    "COMPUTATION_LIMIT_BLOCKED",
                    ("SEARCH_BUDGET_EXHAUSTED",),
                )
            elif search.outcome == "EXHAUSTED_NO_SPLIT_ELIGIBLE_TUPLE":
                terminal, reasons = (
                    "NO_FEASIBLE_DOMAIN_TUPLE",
                    ("NO_DOMAIN_TUPLE_MEETS_ALL_GATES",),
                )
            elif search.outcome == "EXHAUSTED_SPLIT_ROSTER_N2_UNSAFE":
                terminal, reasons = (
                    "N2_UNIVERSAL_SUPPORT_BLOCKED",
                    ("SPLIT_ELIGIBLE_ROSTER_NOT_UNIVERSALLY_N2_SUPPORTED",),
                )
            else:
                terminal, reasons = "CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW", ()

    if search.outcome == "EXHAUSTED_SPLIT_ROSTER_N2_SAFE":
        structural_status = "SPLIT_FEASIBLE_N2_UNIVERSALLY_SUPPORTED"
    elif search.outcome == "EXHAUSTED_SPLIT_ROSTER_N2_UNSAFE":
        structural_status = "SPLIT_FEASIBLE_N2_NOT_UNIVERSALLY_SUPPORTED"
    elif search.outcome == "EXHAUSTED_NO_SPLIT_ELIGIBLE_TUPLE":
        structural_status = "SPLIT_INFEASIBLE"
    elif search.outcome == "LIMIT_REACHED":
        structural_status = "INDETERMINATE"
    else:
        structural_status = "NOT_EVALUATED"
    assurance = {
        **_ASSURANCE,
        "source_records_seen_by_curator_roles_declared": manifest["exposure"][
            "source_records_seen_by_curator_roles"
        ],
        "target_values_seen_by_target_curator_declared": manifest["exposure"][
            "numeric_y_seen_by_target_curator"
        ],
        "transcription_values_seen_by_transcription_curator_declared": manifest["exposure"][
            "transcription_x_seen_by_transcription_role"
        ],
    }
    report: dict[str, Any] = {
        "assurance": assurance,
        "bindings": {
            "claim_slot_reservation_sha256": manifest["bindings"]["claim_slot_reservation_sha256"],
            "evaluator_bundle_sha256": snapshot.evaluator_bundle_sha256,
            "gate_plan_sha256": snapshot.gate_plan_sha256,
            "identifier_key_ceremony_sha256": manifest["bindings"][
                "identifier_key_ceremony_sha256"
            ],
            "manifest_sha256": validated.manifest_sha256,
            "parent_protocol_sha256": snapshot.parent_protocol_sha256,
            "population_inventory_sha256": validated.population_inventory_sha256,
            "population_freeze_claim_sha256": manifest["bindings"][
                "population_freeze_claim_sha256"
            ],
            "preinventory_contract_sha256": manifest["bindings"]["preinventory_contract_sha256"],
            "source_frame_sha256": validated.source_frame_sha256,
            "split_structural_input_sha256": manifest["bindings"]["split_structural_input_sha256"],
            "target_seal_sha256": manifest["bindings"]["target_seal_sha256"],
            "transcription_seal_sha256": manifest["bindings"]["transcription_seal_sha256"],
        },
        "counts": {
            "base_e_eligible_f": (
                sum(row["eligible"] for row in manifest["eligibility"])
                if structural_counts_evaluated
                else None
            ),
            "split_eligible_f": (
                sum(eligibility_flags.values()) if structural_counts_evaluated else None
            ),
            "eligible_g": len(eligible_components) if structural_counts_evaluated else None,
            "split_excluded_f": (
                len(eligibility_flags) - sum(eligibility_flags.values())
                if structural_counts_evaluated
                else None
            ),
            "relation_edges": len(manifest["relations"]),
            "source_frame_entries": len(manifest["source_records"]),
            "source_frame_physical_originals": len(manifest["units"]),
            "structural_counts_evaluated": structural_counts_evaluated,
            "total_g": len(components) if structural_counts_evaluated else None,
        },
        "created_at": manifest["created_at"],
        "feasibility": {
            "actual_n1_support": "DEFERRED_NOT_EVALUATED",
            "eligible_split_inventory_sha256": eligible_split_inventory_sha256,
            "split_eligible_tuple_roster_sha256": search.split_eligible_tuple_roster_sha256,
            "external_assurance": "UNVERIFIED",
            "split_eligible_tuple_count": search.split_eligible_tuple_count,
            "first_split_eligible_aggregate_in_canonical_search": (
                search.first_aggregate.as_dict() if search.first_aggregate is not None else None
            ),
            "n2_included_in_split_tuple_predicate": False,
            "n2_primary_assignments": search.n2_primary_assignments,
            "n2_supported_tuple_count": search.n2_supported_tuple_count,
            "n2_tuple_evaluations": search.n2_tuple_evaluations,
            "search_outcome": search.outcome,
            "structural_status": structural_status,
            "tuple_evaluations": search.tuple_evaluations,
        },
        "format_version": "1.0.0",
        "privacy": dict(_PRIVACY),
        "reason_codes": list(reasons),
        "record_kind": "nmfa_private_aggregate_preregistration_report",
        "terminal_state": terminal,
    }
    report["receipt_sha256"] = _sha256(_RECEIPT_DOMAIN + encode_json(report))
    _validate_instance(report, resources.report_schema, resource=True)
    return NMFAPreregistrationReport(
        terminal_state=terminal,
        reason_codes=reasons,
        report_bytes=encode_json(report),
    )


def evaluate_preregistration_manifest(raw: bytes) -> NMFAPreregistrationReport:
    """Evaluate a protected value-blind inventory without source or target access."""

    if type(raw) is not bytes:
        _fail(NMFAPreregistrationErrorCode.INVALID_ARGUMENT)
    return _evaluate_with_resources(raw, _load_installed_resources())
