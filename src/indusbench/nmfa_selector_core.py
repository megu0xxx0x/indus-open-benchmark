"""Deterministic, source-free selector core for the NMFA execution stack.

This module is a development component, not the complete typed execution
bundle ``E``.  It consumes only a closed structural inventory.  Its callable
accepts declared nonce bytes and verifies syntax only; a future activation
wrapper may instead supply externally verified, one-use nonce material.  It
never reads X or Y, performs network or file writes, chooses a nonce, or emits
a public summary of a protected assignment.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise, product
from typing import Any, Never, cast

from indusbench.io import CorpusFormatError, decode_json, encode_json

_PLAN_PATH = "benchmark/nmfa-selector-core-plan-v1.json"
_BUNDLE_PATH = "benchmark/nmfa-selector-core-evaluator-bundle-v1.json"
_PLAN_SCHEMA_PATH = "schemas/nmfa-selector-core-plan.schema.json"
_INVENTORY_SCHEMA_PATH = "schemas/nmfa-selector-inventory.schema.json"
_RECEIPT_SCHEMA_PATH = "schemas/nmfa-selector-receipt.schema.json"
_PARENT_PROTOCOL_PATH = "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
_GATE_PLAN_PATH = "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
_GATE_BUNDLE_PATH = "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"

_PARENT_PROTOCOL_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
_GATE_PLAN_SHA256 = "dfea30b6cc0635e98d6fc1c0125e428df454bfbb4f22ba464923801db01273af"
_GATE_BUNDLE_SHA256 = "ec9ba6fbaa5df13dce438f819114206da2d6ca6e68afb521476635d5abd91a79"
_BUNDLE_CREATED_AT = "2026-08-02T15:50:25Z"
_PLAN_SIZE = 11_046
_PLAN_SHA256 = "f4c80a15804c4dffcef4f850d597f54836b44c3444af811f1c686814f39c5190"
_PLAN_SCHEMA_SIZE = 11_782
_PLAN_SCHEMA_SHA256 = "54784e1e554fdaac69d058d0f32619fad358d9d912d45c7caa3383b272902844"
_INVENTORY_SCHEMA_SIZE = 7_893
_INVENTORY_SCHEMA_SHA256 = "8a3be3bc73b393f620b3fe5c3ea87619c11b8791bcb996c4b790e03f4d03b382"
_RECEIPT_SCHEMA_SIZE = 6_743
_RECEIPT_SCHEMA_SHA256 = "7ff0e3a7d13ce6b83b2b5bcbc5f8c0e232805322732ec5107d3f387fa71c2735"

_MAX_JSON_BYTES = 67_108_864
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 2_000_000
_MAX_JSON_STRING_LENGTH = 16_384
_MAX_UNITS = 20_000
_MAX_TUPLE_EVALUATIONS = 200_000
_MAX_N2_TUPLE_EVALUATIONS = 10_000
_MAX_N2_PRIMARY_ASSIGNMENTS = 2_000_000
_MAX_PRIMARY_CACHE_ENTRIES = 200_000

_ELIGIBLE_G_MINIMUM = 160
_CELL_MINIMUM_G = 20
_HOLDOUT_MINIMUM_G = 80
_COMPLEMENT_MINIMUM_G = 80
_N2_MINIMUM_MOVABLE_G = 64
_N2_MINIMUM_MOVABLE_PERCENT = 80

_AXES = ("site", "period", "medium", "object_type")
_PARTITION_CYCLE = ("development", "development", "validation")

_G_ID_DOMAIN = b"indusbench:nmfa:executor-g:v1\x00"
_PRIMARY_F_DOMAIN = b"indusbench:nmfa:preregistration-primary-f:v1\x00"
_TUPLE_ROSTER_DOMAIN = b"indusbench:nmfa:feasible-tuple-roster:v1\x00"
_ELIGIBLE_SPLIT_INVENTORY_DOMAIN = b"indusbench:nmfa:eligible-split-inventory:v1\x00"
_SELECTOR_INVENTORY_DOMAIN = b"indusbench:nmfa:selector-inventory:v1\x00"
_SELECTOR_ASSIGNMENT_DOMAIN = b"indusbench:nmfa:selector-assignment:v1\x00"

_EXPECTED_RUNTIME_PROFILE = {
    "canonical_encoder": "indusbench.io:encode_json",
    "dependencies": {"jsonschema": "4.26.0"},
    "dependency_requirement": "jsonschema[format]==4.26.0",
    "dependency_scope": ("direct_declared_requirement_only_runtime_environment_not_attested"),
    "entrypoints": [
        "indusbench.nmfa_selector_core:validate_nmfa_selector_inventory",
        "indusbench.nmfa_selector_core:evaluate_nmfa_selector_inventory",
        "indusbench.nmfa_selector_core:normalize_nmfa_split_nonce",
        "indusbench.nmfa_selector_core:derive_nmfa_selector_assignment",
        "indusbench.nmfa_selector_core:verify_nmfa_selector_assignment",
    ],
    "implementation": "CPython",
    "integer_arithmetic": "arbitrary_precision_with_frozen_input_and_search_limits",
    "supported_python_minors": ["3.11", "3.12", "3.13", "3.14"],
}

_EXPECTED_SECURITY_BOUNDARY = {
    "activation_or_source_authority_included": False,
    "complete_execution_bundle": False,
    "external_nonce_trust_verified": False,
    "network_clock_random_or_file_write_used": False,
    "protected_declared_assignment_included": False,
    "protected_inventory_included": False,
    "runtime_environment_attested": False,
    "source_or_target_values_included": False,
}

_RESOURCE_LOCKS = {
    _PLAN_PATH: (_PLAN_SIZE, _PLAN_SHA256),
    _PLAN_SCHEMA_PATH: (_PLAN_SCHEMA_SIZE, _PLAN_SCHEMA_SHA256),
    _INVENTORY_SCHEMA_PATH: (_INVENTORY_SCHEMA_SIZE, _INVENTORY_SCHEMA_SHA256),
    _RECEIPT_SCHEMA_PATH: (_RECEIPT_SCHEMA_SIZE, _RECEIPT_SCHEMA_SHA256),
}

_BUNDLE_FILE_PATHS = frozenset(
    {
        _PLAN_PATH,
        _GATE_BUNDLE_PATH,
        _GATE_PLAN_PATH,
        _PARENT_PROTOCOL_PATH,
        _PLAN_SCHEMA_PATH,
        _INVENTORY_SCHEMA_PATH,
        _RECEIPT_SCHEMA_PATH,
        "src/indusbench/io.py",
        "src/indusbench/nmfa_selector_core.py",
    }
)


class NMFASelectorErrorCode(StrEnum):
    """Stable errors that never interpolate protected values or paths."""

    ASSIGNMENT_CONTRACT_INVALID = "ASSIGNMENT_CONTRACT_INVALID"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVENTORY_CONTRACT_INVALID = "INVENTORY_CONTRACT_INVALID"
    NONCE_CONTRACT_INVALID = "NONCE_CONTRACT_INVALID"
    PACKAGE_RESOURCE_INVALID = "PACKAGE_RESOURCE_INVALID"
    SCHEMA_DEPENDENCY_MISSING = "SCHEMA_DEPENDENCY_MISSING"
    SELECTOR_NOT_READY = "SELECTOR_NOT_READY"


class NMFASelectorError(ValueError):
    """Fixed-code selector error with no protected-input echo."""

    def __init__(self, code: NMFASelectorErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class NMFASelectorOutcome(StrEnum):
    """Private pre-execution outcomes; none is a scientific result."""

    INSUFFICIENT_ELIGIBLE_G = "INSUFFICIENT_ELIGIBLE_G"
    COMPUTATION_LIMIT_BLOCKED = "COMPUTATION_LIMIT_BLOCKED"
    NO_FEASIBLE_DOMAIN_TUPLE = "NO_FEASIBLE_DOMAIN_TUPLE"
    N2_UNIVERSAL_SUPPORT_BLOCKED = "N2_UNIVERSAL_SUPPORT_BLOCKED"
    READY_FOR_DECLARED_NONCE_ANALYSIS = "READY_FOR_DECLARED_NONCE_ANALYSIS"
    DECLARED_SELECTOR_ASSIGNMENT_ONLY = "DECLARED_SELECTOR_ASSIGNMENT_ONLY"


@dataclass(frozen=True, repr=False)
class ValidatedNMFASelectorInventory:
    """Canonical protected inventory bytes accepted by the closed contract."""

    canonical_bytes: bytes
    selector_inventory_sha256: str
    eligible_split_inventory_sha256: str
    selector_bundle_sha256: str

    def __repr__(self) -> str:
        return "<ValidatedNMFASelectorInventory protected>"


@dataclass(frozen=True, repr=False)
class NMFASelectorAnalysis:
    """Protected deterministic structural analysis."""

    outcome: NMFASelectorOutcome
    split_eligible_tuple_count: int
    n2_supported_tuple_count: int
    tuple_roster_sha256: str | None
    tuple_evaluations: int
    n2_tuple_evaluations: int
    n2_primary_assignments: int

    def __repr__(self) -> str:
        return "<NMFASelectorAnalysis protected>"


@dataclass(frozen=True, repr=False)
class ProtectedNMFASelectorAssignment:
    """Canonical private declared assignment; not a realized split receipt."""

    receipt_bytes: bytes
    receipt_sha256: str

    def __repr__(self) -> str:
        return "<ProtectedNMFASelectorAssignment protected>"

    def receipt(self) -> dict[str, Any]:
        """Return a fresh decoded copy for an authorized in-custody consumer."""

        if type(self.receipt_bytes) is not bytes or not _is_checksum(self.receipt_sha256):
            _fail(NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID)
        try:
            value = decode_json(self.receipt_bytes)
        except (CorpusFormatError, OverflowError, RecursionError, ValueError):
            _fail(NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID)
        if (
            type(value) is not dict
            or encode_json(value) != self.receipt_bytes
            or _domain_digest(_SELECTOR_ASSIGNMENT_DOMAIN, value) != self.receipt_sha256
        ):
            _fail(NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID)
        _validate_schema(
            value,
            _RECEIPT_SCHEMA_PATH,
            contract_error=NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID,
        )
        if value["bindings"]["selector_bundle_sha256"] != _validate_installed_bundle()[0]:
            _fail(NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID)
        return value


@dataclass(frozen=True)
class _FRow:
    f_id: str
    context: tuple[str, str, str, str]
    nuisance: tuple[str, ...]
    eligible: bool


@dataclass(frozen=True)
class _Component:
    g_id: str
    members: tuple[_FRow, ...]
    contexts: tuple[frozenset[str], ...]
    trigger_contexts: tuple[frozenset[str], ...]

    @property
    def eligible_members(self) -> tuple[_FRow, ...]:
        return tuple(row for row in self.members if row.eligible)


@dataclass(frozen=True)
class _Inventory:
    validated: ValidatedNMFASelectorInventory
    claim_binding: dict[str, str]
    closures: tuple[dict[str, frozenset[str]], ...]
    components: tuple[_Component, ...]


@dataclass(frozen=True)
class _TupleEvaluation:
    canonical_tuple: tuple[str, str, str, str]
    n2_movable_g: int


@dataclass(frozen=True)
class _Search:
    analysis: NMFASelectorAnalysis
    tuples: tuple[_TupleEvaluation, ...]


class _PrimaryCacheLimit(RuntimeError):
    pass


def _fail(code: NMFASelectorErrorCode) -> Never:
    raise NMFASelectorError(code)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _domain_digest(domain: bytes, value: Any) -> str:
    return _sha256(domain + encode_json(value))


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


def _decode_canonical_json(raw: bytes) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_JSON_BYTES:
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    try:
        value = decode_json(raw)
    except (CorpusFormatError, OverflowError, RecursionError, ValueError):
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    nodes, depth, longest = _json_shape(value)
    if (
        nodes > _MAX_JSON_NODES
        or depth > _MAX_JSON_DEPTH
        or longest > _MAX_JSON_STRING_LENGTH
        or encode_json(value) != raw
    ):
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    return value


def _package_root():
    try:
        return importlib.resources.files("indusbench")
    except (AttributeError, ModuleNotFoundError):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)


def _resource_bytes(path: str) -> bytes:
    try:
        raw = _package_root().joinpath(*path.split("/")).read_bytes()
    except (FileNotFoundError, OSError, TypeError):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    locked = _RESOURCE_LOCKS.get(path)
    if locked is not None and (
        len(raw) != locked[0] or hashlib.sha256(raw).hexdigest() != locked[1]
    ):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    return raw


def _validate_schema(
    value: Any,
    schema_path: str,
    *,
    contract_error: NMFASelectorErrorCode = NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID,
) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        _fail(NMFASelectorErrorCode.SCHEMA_DEPENDENCY_MISSING)
    try:
        schema = decode_json(_resource_bytes(schema_path))
        Draft202012Validator.check_schema(schema)
        first_error = next(Draft202012Validator(schema).iter_errors(value), None)
    except Exception as error:
        if isinstance(error, NMFASelectorError):
            raise
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    if first_error is not None:
        _fail(contract_error)


def _bundle_member_bytes(path: str) -> bytes:
    prefix = "src/indusbench/"
    return _resource_bytes(path[len(prefix) :] if path.startswith(prefix) else path)


def _validate_installed_bundle() -> tuple[str, str]:
    raw = _resource_bytes(_BUNDLE_PATH)
    try:
        bundle = decode_json(raw)
    except (CorpusFormatError, OverflowError, RecursionError, ValueError):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    if (
        type(bundle) is not dict
        or encode_json(bundle) != raw
        or set(bundle)
        != {
            "bundle_id",
            "created_at",
            "files",
            "format_version",
            "runtime_profile",
            "security_boundary",
        }
        or bundle["bundle_id"] != "nmfa-selector-core-evaluator-bundle-v1"
        or bundle["created_at"] != _BUNDLE_CREATED_AT
        or bundle["format_version"] != "1.0.0"
        or type(bundle["files"]) is not list
        or bundle["runtime_profile"] != _EXPECTED_RUNTIME_PROFILE
        or bundle["security_boundary"] != _EXPECTED_SECURITY_BOUNDARY
    ):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    expected_paths = sorted(_BUNDLE_FILE_PATHS)
    if len(bundle["files"]) != len(expected_paths):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
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
            _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    for row in bundle["files"]:
        member = _bundle_member_bytes(row["path"])
        if len(member) != row["bytes"] or _sha256(member) != row["sha256"]:
            _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    if _sha256(_resource_bytes(_GATE_BUNDLE_PATH)) != "sha256:" + _GATE_BUNDLE_SHA256:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    if (
        sys.implementation.name != "cpython"
        or f"{sys.version_info.major}.{sys.version_info.minor}"
        not in _EXPECTED_RUNTIME_PROFILE["supported_python_minors"]
    ):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    try:
        jsonschema_version = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    if jsonschema_version != _EXPECTED_RUNTIME_PROFILE["dependencies"]["jsonschema"]:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    return _sha256(raw), bundle["created_at"]


def _validate_installed_predecessors(value: dict[str, Any]) -> None:
    parent = _resource_bytes(_PARENT_PROTOCOL_PATH)
    gate = _resource_bytes(_GATE_PLAN_PATH)
    plan = _resource_bytes(_PLAN_PATH)
    if (
        hashlib.sha256(parent).hexdigest() != _PARENT_PROTOCOL_SHA256
        or hashlib.sha256(gate).hexdigest() != _GATE_PLAN_SHA256
        or value["gate_plan_sha256"] != "sha256:" + _GATE_PLAN_SHA256
        or value["parent_protocol_sha256"] != "sha256:" + _PARENT_PROTOCOL_SHA256
        or value["selector_plan_sha256"] != _sha256(plan)
    ):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)


def _component_id(member_f_ids: tuple[str, ...]) -> str:
    return _domain_digest(_G_ID_DOMAIN, {"member_f_ids": list(member_f_ids)})


def _is_checksum(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _parse_inventory(validated: ValidatedNMFASelectorInventory) -> _Inventory:
    value = cast(dict[str, Any], _decode_canonical_json(validated.canonical_bytes))
    payload = value["eligible_split_inventory"]
    if payload["axis_order"] != list(_AXES):
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)

    nuisance_semantics = payload["nuisance_semantics"]
    nuisance_fields = nuisance_semantics["nuisance_field_ids"]
    nuisance_vocabularies = nuisance_semantics["nuisance_vocabularies"]
    if [row["field_id"] for row in nuisance_vocabularies] != nuisance_fields:
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    allowed_nuisance_values: list[set[str]] = []
    for vocabulary in nuisance_vocabularies:
        canonical_values = vocabulary["canonical_value_ids"]
        if canonical_values != sorted(canonical_values):
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
        allowed_nuisance_values.append(set(canonical_values))
    provenance_policy = nuisance_semantics["provenance_policy"]
    if provenance_policy == "single_prespecified_regime":
        if nuisance_fields or nuisance_vocabularies:
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    elif provenance_policy == "complete_canonical_nuisance_tuple":
        if not nuisance_fields or len(nuisance_vocabularies) != len(nuisance_fields):
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    else:
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)

    closures: list[dict[str, frozenset[str]]] = []
    closure_tables = payload["closure_tables"]
    if set(closure_tables) != set(_AXES):
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    for axis in _AXES:
        groups = closure_tables[axis]
        group_ids = [group["group_id"] for group in groups]
        if group_ids != sorted(group_ids) or len(group_ids) != len(set(group_ids)):
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
        axis_closures: dict[str, frozenset[str]] = {}
        member_sets: set[tuple[str, ...]] = set()
        for group in groups:
            members = group["member_value_ids"]
            if (
                members != sorted(members)
                or len(members) != len(set(members))
                or group["group_id"] not in members
                or tuple(members) in member_sets
            ):
                _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
            member_sets.add(tuple(members))
            axis_closures[group["group_id"]] = frozenset(members)
        subset_cache: dict[tuple[str, str], bool] = {}
        containing: dict[str, list[str]] = defaultdict(list)
        group_id_set = set(group_ids)
        for parent_id, parent_members in axis_closures.items():
            for child_id in parent_members & group_id_set:
                key = (child_id, parent_id)
                subset_cache[key] = axis_closures[child_id].issubset(parent_members)
                if not subset_cache[key]:
                    _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
            for member_id in parent_members:
                containing[member_id].append(parent_id)
        for containers in containing.values():
            ordered = sorted(containers, key=lambda item: (len(axis_closures[item]), item))
            for smaller, larger in pairwise(ordered):
                if not axis_closures[smaller].issubset(axis_closures[larger]):
                    _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
        closures.append(axis_closures)

    components: list[_Component] = []
    seen_f: set[str] = set()
    component_keys: list[tuple[str, ...]] = []
    for component in payload["components"]:
        raw_members = component["members"]
        f_ids = tuple(row["f_id"] for row in raw_members)
        if (
            f_ids != tuple(sorted(f_ids))
            or len(f_ids) != len(set(f_ids))
            or seen_f.intersection(f_ids)
        ):
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
        seen_f.update(f_ids)
        expected_m_g = [row["f_id"] for row in raw_members if row["e_eligible"]]
        if (
            component["m_g_member_ids"] != sorted(component["m_g_member_ids"])
            or component["m_g_member_ids"] != expected_m_g
            or any(row["split_eligible"] and not row["e_eligible"] for row in raw_members)
        ):
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)

        all_complete = True
        rows: list[_FRow] = []
        for raw_row in raw_members:
            raw_context = raw_row["context"]
            raw_axis_values = tuple(raw_context[axis] for axis in _AXES)
            nuisance = tuple(raw_context["nuisance"])
            if len(nuisance) > len(nuisance_fields) or any(
                nuisance_value not in allowed_nuisance_values[index]
                for index, nuisance_value in enumerate(nuisance)
            ):
                _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
            complete = all(type(item) is str for item in raw_axis_values) and len(nuisance) == len(
                nuisance_fields
            )
            all_complete = all_complete and complete
            for axis_index, context_value in enumerate(raw_axis_values):
                if type(context_value) is str and context_value not in closures[axis_index]:
                    _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
            if component["split_eligible_g"]:
                if not complete:
                    _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
                rows.append(
                    _FRow(
                        f_id=raw_row["f_id"],
                        context=cast(tuple[str, str, str, str], raw_axis_values),
                        nuisance=nuisance,
                        eligible=raw_row["split_eligible"],
                    )
                )
        split_member_ids = [row["f_id"] for row in raw_members if row["split_eligible"]]
        expected_split_eligible_g = all_complete and bool(split_member_ids)
        if (
            component["complete_c"] is not all_complete
            or component["split_eligible_g"] is not expected_split_eligible_g
            or bool(split_member_ids) is not component["split_eligible_g"]
            or (bool(split_member_ids) and split_member_ids != expected_m_g)
        ):
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
        component_keys.append(f_ids)
        if not component["split_eligible_g"]:
            continue
        member_tuple = tuple(rows)
        contexts = tuple(
            frozenset(row.context[index] for row in member_tuple) for index in range(len(_AXES))
        )
        triggers = tuple(
            frozenset(row.context[index] for row in member_tuple if row.eligible)
            for index in range(len(_AXES))
        )
        expected_g_id = _component_id(f_ids)
        components.append(
            _Component(
                g_id=expected_g_id,
                members=member_tuple,
                contexts=contexts,
                trigger_contexts=triggers,
            )
        )
    if component_keys != sorted(component_keys) or len(seen_f) > _MAX_UNITS:
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)

    return _Inventory(validated, value["claim_binding"], tuple(closures), tuple(components))


def validate_nmfa_selector_inventory(
    raw: bytes, expected_eligible_split_inventory_sha256: str
) -> ValidatedNMFASelectorInventory:
    """Validate canonical selector bytes against an external predecessor digest."""

    if not _is_checksum(expected_eligible_split_inventory_sha256):
        _fail(NMFASelectorErrorCode.INVALID_ARGUMENT)
    value = _decode_canonical_json(raw)
    if type(value) is not dict:
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    selector_bundle_sha256, _ = _validate_installed_bundle()
    _validate_schema(value, _INVENTORY_SCHEMA_PATH)
    _validate_installed_predecessors(value)
    eligible_digest = _domain_digest(
        _ELIGIBLE_SPLIT_INVENTORY_DOMAIN, value["eligible_split_inventory"]
    )
    if eligible_digest != expected_eligible_split_inventory_sha256:
        _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
    selector_digest = _domain_digest(_SELECTOR_INVENTORY_DOMAIN, value)
    validated = ValidatedNMFASelectorInventory(
        canonical_bytes=raw,
        selector_inventory_sha256=selector_digest,
        eligible_split_inventory_sha256=eligible_digest,
        selector_bundle_sha256=selector_bundle_sha256,
    )
    _parse_inventory(validated)
    _require_unchanged_bundle(validated)
    return validated


def _require_unchanged_bundle(inventory: ValidatedNMFASelectorInventory) -> None:
    if _validate_installed_bundle()[0] != inventory.selector_bundle_sha256:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)


def normalize_nmfa_split_nonce(hex_text: str) -> bytes:
    """Normalize exactly 32 bytes represented as 64 lowercase hexadecimal chars."""

    if (
        type(hex_text) is not str
        or len(hex_text) != 64
        or any(character not in "0123456789abcdef" for character in hex_text)
    ):
        _fail(NMFASelectorErrorCode.NONCE_CONTRACT_INVALID)
    try:
        raw = bytes.fromhex(hex_text)
    except ValueError:
        _fail(NMFASelectorErrorCode.NONCE_CONTRACT_INVALID)
    if len(raw) != 32:
        _fail(NMFASelectorErrorCode.NONCE_CONTRACT_INVALID)
    return raw


def _candidate_bitsets(
    inventory: _Inventory,
) -> tuple[tuple[tuple[str, ...], ...], tuple[dict[str, int], ...], tuple[dict[str, int], ...]]:
    candidates: list[tuple[str, ...]] = []
    cells: list[dict[str, int]] = []
    triggers: list[dict[str, int]] = []
    for axis_index in range(len(_AXES)):
        axis_cells: dict[str, int] = {}
        axis_triggers: dict[str, int] = {}
        for group_id, members in inventory.closures[axis_index].items():
            cell_bits = 0
            trigger_bits = 0
            for component_index, component in enumerate(inventory.components):
                bit = 1 << component_index
                if component.contexts[axis_index] & members:
                    cell_bits |= bit
                if component.trigger_contexts[axis_index] & members:
                    trigger_bits |= bit
            axis_cells[group_id] = cell_bits
            axis_triggers[group_id] = trigger_bits
        candidates.append(
            tuple(
                group_id
                for group_id in sorted(axis_triggers)
                if axis_triggers[group_id].bit_count() >= _CELL_MINIMUM_G
            )
        )
        cells.append(axis_cells)
        triggers.append(axis_triggers)
    return tuple(candidates), tuple(cells), tuple(triggers)


def _iter_set_bits(bits: int):
    while bits:
        least = bits & -bits
        yield least.bit_length() - 1
        bits ^= least


def _primary_f(
    component: _Component,
    axis_index: int | None,
    closure_members: frozenset[str] | None,
    gate_plan_sha256: str,
) -> _FRow | None:
    if axis_index is None:
        candidates = component.eligible_members
    else:
        if closure_members is None:
            return None
        candidates = tuple(
            row for row in component.eligible_members if row.context[axis_index] in closure_members
        )
    if not candidates:
        return None

    def rank(row: _FRow) -> tuple[bytes, bytes]:
        encoded = row.f_id.encode("ascii")
        return (
            hashlib.sha256(
                _PRIMARY_F_DOMAIN + gate_plan_sha256.encode("ascii") + b"\x00" + encoded
            ).digest(),
            encoded,
        )

    return min(candidates, key=rank)


def _structural_tuple(
    inventory: _Inventory,
    canonical_tuple: tuple[str, str, str, str],
    cell_bits: tuple[dict[str, int], ...],
    trigger_bits: tuple[dict[str, int], ...],
) -> tuple[tuple[int, int, int, int], int] | None:
    all_bits = (1 << len(inventory.components)) - 1
    remaining = all_bits
    cells: list[int] = []
    for axis_index, group_id in enumerate(canonical_tuple):
        cell = remaining & cell_bits[axis_index][group_id]
        if cell.bit_count() < _CELL_MINIMUM_G or cell & (
            all_bits ^ trigger_bits[axis_index][group_id]
        ):
            return None
        cells.append(cell)
        remaining ^= cell
    holdout_count = sum(cell.bit_count() for cell in cells)
    if holdout_count < _HOLDOUT_MINIMUM_G or remaining.bit_count() < _COMPLEMENT_MINIMUM_G:
        return None

    return cast(tuple[int, int, int, int], tuple(cells)), remaining


def _n2_evaluate(
    inventory: _Inventory,
    canonical_tuple: tuple[str, str, str, str],
    cells: tuple[int, int, int, int],
    primary_cache: dict[tuple[int, int, str], _FRow | None],
) -> _TupleEvaluation:
    strata: Counter[tuple[str, ...]] = Counter()
    for axis_index, (group_id, cell) in enumerate(zip(canonical_tuple, cells, strict=True)):
        closure_members = inventory.closures[axis_index][group_id]
        for component_index in _iter_set_bits(cell):
            component = inventory.components[component_index]
            cache_key = (component_index, axis_index, group_id)
            if cache_key not in primary_cache:
                if len(primary_cache) >= _MAX_PRIMARY_CACHE_ENTRIES:
                    raise _PrimaryCacheLimit
                primary_cache[cache_key] = _primary_f(
                    component,
                    axis_index,
                    closure_members,
                    "sha256:" + _GATE_PLAN_SHA256,
                )
            primary = primary_cache[cache_key]
            if primary is None:
                _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
            strata[(_AXES[axis_index], *primary.context, *primary.nuisance)] += 1
    movable = sum(count for count in strata.values() if count >= 2)
    return _TupleEvaluation(
        canonical_tuple=canonical_tuple,
        n2_movable_g=movable,
    )


def _search(inventory: _Inventory) -> _Search:
    component_count = len(inventory.components)
    if component_count < _ELIGIBLE_G_MINIMUM:
        return _Search(
            NMFASelectorAnalysis(NMFASelectorOutcome.INSUFFICIENT_ELIGIBLE_G, 0, 0, None, 0, 0, 0),
            (),
        )
    candidates, cell_bits, trigger_bits = _candidate_bitsets(inventory)
    tuples: list[_TupleEvaluation] = []
    tuple_evaluations = 0
    n2_evaluations = 0
    n2_primary_assignments = 0
    n2_supported = 0
    primary_cache: dict[tuple[int, int, str], _FRow | None] = {}
    for raw_tuple in product(*candidates):
        tuple_evaluations += 1
        if tuple_evaluations > _MAX_TUPLE_EVALUATIONS:
            return _Search(
                NMFASelectorAnalysis(
                    NMFASelectorOutcome.COMPUTATION_LIMIT_BLOCKED,
                    0,
                    0,
                    None,
                    tuple_evaluations - 1,
                    n2_evaluations,
                    n2_primary_assignments,
                ),
                (),
            )
        canonical_tuple = cast(tuple[str, str, str, str], raw_tuple)
        structural = _structural_tuple(inventory, canonical_tuple, cell_bits, trigger_bits)
        if structural is None:
            continue
        if n2_evaluations >= _MAX_N2_TUPLE_EVALUATIONS:
            return _Search(
                NMFASelectorAnalysis(
                    NMFASelectorOutcome.COMPUTATION_LIMIT_BLOCKED,
                    0,
                    0,
                    None,
                    tuple_evaluations,
                    n2_evaluations,
                    n2_primary_assignments,
                ),
                (),
            )
        cells, _ = structural
        holdout_count = sum(cell.bit_count() for cell in cells)
        if n2_primary_assignments + holdout_count > _MAX_N2_PRIMARY_ASSIGNMENTS:
            return _Search(
                NMFASelectorAnalysis(
                    NMFASelectorOutcome.COMPUTATION_LIMIT_BLOCKED,
                    0,
                    0,
                    None,
                    tuple_evaluations,
                    n2_evaluations,
                    n2_primary_assignments,
                ),
                (),
            )
        n2_evaluations += 1
        n2_primary_assignments += holdout_count
        try:
            evaluation = _n2_evaluate(
                inventory,
                canonical_tuple,
                cells,
                primary_cache,
            )
        except _PrimaryCacheLimit:
            return _Search(
                NMFASelectorAnalysis(
                    NMFASelectorOutcome.COMPUTATION_LIMIT_BLOCKED,
                    0,
                    0,
                    None,
                    tuple_evaluations,
                    n2_evaluations,
                    n2_primary_assignments,
                ),
                (),
            )
        tuples.append(evaluation)
        if (
            evaluation.n2_movable_g >= _N2_MINIMUM_MOVABLE_G
            and evaluation.n2_movable_g * 100 >= _N2_MINIMUM_MOVABLE_PERCENT * holdout_count
        ):
            n2_supported += 1
    if not tuples:
        outcome = NMFASelectorOutcome.NO_FEASIBLE_DOMAIN_TUPLE
        roster_digest = None
    else:
        roster_digest = _domain_digest(
            _TUPLE_ROSTER_DOMAIN,
            {"canonical_tuples": [list(item.canonical_tuple) for item in tuples]},
        )
        outcome = (
            NMFASelectorOutcome.READY_FOR_DECLARED_NONCE_ANALYSIS
            if n2_supported == len(tuples)
            else NMFASelectorOutcome.N2_UNIVERSAL_SUPPORT_BLOCKED
        )
    return _Search(
        NMFASelectorAnalysis(
            outcome,
            len(tuples),
            n2_supported,
            roster_digest,
            tuple_evaluations,
            n2_evaluations,
            n2_primary_assignments,
        ),
        tuple(tuples),
    )


def evaluate_nmfa_selector_inventory(
    raw: bytes,
    expected_eligible_split_inventory_sha256: str,
) -> NMFASelectorAnalysis:
    """Validate raw bytes, then exhaust the tuple roster and universal N2 gate."""

    validated = validate_nmfa_selector_inventory(
        raw,
        expected_eligible_split_inventory_sha256,
    )
    analysis = _search(_parse_inventory(validated)).analysis
    _require_unchanged_bundle(validated)
    return analysis


def _ticket(raw_nonce: bytes, inventory_digest: str, canonical_tuple: tuple[str, ...]) -> bytes:
    return hashlib.sha256(
        raw_nonce
        + b"\x00"
        + inventory_digest.encode("ascii")
        + b"\x00"
        + encode_json(list(canonical_tuple))
    ).digest()


def _receipt_payload(
    inventory: _Inventory,
    search: _Search,
    selected: _TupleEvaluation,
    raw_nonce: bytes,
) -> dict[str, Any]:
    selected_ticket = _ticket(
        raw_nonce,
        inventory.validated.eligible_split_inventory_sha256,
        selected.canonical_tuple,
    )
    _, cell_bits, trigger_bits = _candidate_bitsets(inventory)
    structural = _structural_tuple(
        inventory,
        selected.canonical_tuple,
        cell_bits,
        trigger_bits,
    )
    if structural is None:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    cells, complement = structural
    assignments: list[dict[str, Any]] = []
    holdout_indexes: set[int] = set()
    for axis_index, cell in enumerate(cells):
        for component_index in _iter_set_bits(cell):
            holdout_indexes.add(component_index)
            component = inventory.components[component_index]
            primary = _primary_f(
                component,
                axis_index,
                inventory.closures[axis_index][selected.canonical_tuple[axis_index]],
                "sha256:" + _GATE_PLAN_SHA256,
            )
            if primary is None:
                _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
            assignments.append(
                {
                    "cell": _AXES[axis_index],
                    "g_id": component.g_id,
                    "partition": "holdout",
                    "primary_f_id": primary.f_id,
                }
            )
    development_rows: list[tuple[str, int, _Component]] = []
    for component_index in _iter_set_bits(complement):
        component = inventory.components[component_index]
        development_rows.append((component.g_id, component_index, component))
    development_rows.sort(key=lambda item: (bytes.fromhex(item[0][7:]), item[0]))
    for position, (_, _, component) in enumerate(development_rows):
        primary = _primary_f(component, None, None, "sha256:" + _GATE_PLAN_SHA256)
        if primary is None:
            _fail(NMFASelectorErrorCode.INVENTORY_CONTRACT_INVALID)
        assignments.append(
            {
                "cell": None,
                "g_id": component.g_id,
                "partition": _PARTITION_CYCLE[position % len(_PARTITION_CYCLE)],
                "primary_f_id": primary.f_id,
            }
        )
    if len(assignments) != len(inventory.components) or len(holdout_indexes) != sum(
        cell.bit_count() for cell in cells
    ):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    assignments.sort(key=lambda row: (bytes.fromhex(row["g_id"][7:]), row["g_id"]))
    return {
        "assignments": assignments,
        "assurance_boundary": {
            "claim_binding_origin_verified": False,
            "eligible_inventory_digest_origin_verified": False,
            "external_nonce_provenance_verified": False,
            "one_use_consumption_verified": False,
            "realized_split": False,
            "relation_evidence_origin_verified": False,
            "scientific_result": False,
            "value_free_identifier_origin_verified": False,
        },
        "bindings": {
            "eligible_split_inventory_sha256": inventory.validated.eligible_split_inventory_sha256,
            "gate_evaluator_bundle_sha256": "sha256:" + _GATE_BUNDLE_SHA256,
            "gate_plan_sha256": "sha256:" + _GATE_PLAN_SHA256,
            "parent_protocol_sha256": "sha256:" + _PARENT_PROTOCOL_SHA256,
            "selector_bundle_sha256": inventory.validated.selector_bundle_sha256,
            "selector_inventory_sha256": inventory.validated.selector_inventory_sha256,
            "selector_plan_sha256": _sha256(_resource_bytes(_PLAN_PATH)),
            "tuple_roster_sha256": search.analysis.tuple_roster_sha256,
        },
        "claim_binding": inventory.claim_binding,
        "compiled_blockers": [
            "CLAIM_BINDING_ORIGIN_UNBOUND",
            "COMPLETE_RELATION_CLOSURE_UNBOUND",
            "EXTERNAL_ELIGIBLE_INVENTORY_DIGEST_ORIGIN_UNBOUND",
            "VALUE_FREE_IDENTIFIER_ORIGIN_UNBOUND",
            "NONCE_EVENT_TRUST_UNBOUND",
            "ONE_USE_CONSUMPTION_UNBOUND",
            "TYPED_X_MODEL_UNBOUND",
            "TYPED_Y_METRICS_UNBOUND",
            "N1_N2_RUNNER_UNBOUND",
            "PROSPECTIVE_EVALUATOR_UNBOUND",
            "TERMINAL_ORCHESTRATOR_UNBOUND",
            "ACTIVATION_WRAPPER_UNBOUND",
            "COMPLETE_EXECUTION_BUNDLE_UNBOUND",
        ],
        "format_version": "1.0.0",
        "n2_movable_g": selected.n2_movable_g,
        "nonce_sha256": _sha256(raw_nonce),
        "record_kind": "nmfa_protected_selector_assignment",
        "selected_ticket_sha256": "sha256:" + selected_ticket.hex(),
        "selected_tuple": list(selected.canonical_tuple),
        "split_eligible_tuple_count": search.analysis.split_eligible_tuple_count,
        "terminal_state": NMFASelectorOutcome.DECLARED_SELECTOR_ASSIGNMENT_ONLY.value,
    }


def derive_nmfa_selector_assignment(
    raw: bytes,
    expected_eligible_split_inventory_sha256: str,
    nonce_hex: str,
) -> ProtectedNMFASelectorAssignment:
    """Derive a non-operational assignment from declared nonce bytes."""

    raw_nonce = normalize_nmfa_split_nonce(nonce_hex)
    validated = validate_nmfa_selector_inventory(
        raw,
        expected_eligible_split_inventory_sha256,
    )
    parsed = _parse_inventory(validated)
    search = _search(parsed)
    if search.analysis.outcome is not NMFASelectorOutcome.READY_FOR_DECLARED_NONCE_ANALYSIS:
        _fail(NMFASelectorErrorCode.SELECTOR_NOT_READY)
    selected = min(
        search.tuples,
        key=lambda item: (
            _ticket(
                raw_nonce,
                validated.eligible_split_inventory_sha256,
                item.canonical_tuple,
            ),
            encode_json(list(item.canonical_tuple)),
        ),
    )
    payload = _receipt_payload(parsed, search, selected, raw_nonce)
    _validate_schema(
        payload,
        _RECEIPT_SCHEMA_PATH,
        contract_error=NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID,
    )
    receipt_bytes = encode_json(payload)
    _require_unchanged_bundle(validated)
    return ProtectedNMFASelectorAssignment(
        receipt_bytes=receipt_bytes,
        receipt_sha256=_domain_digest(_SELECTOR_ASSIGNMENT_DOMAIN, payload),
    )


def verify_nmfa_selector_assignment(
    raw: bytes,
    expected_eligible_split_inventory_sha256: str,
    nonce_hex: str,
    assignment_bytes: bytes,
) -> ProtectedNMFASelectorAssignment:
    """Reexecute and require exact canonical assignment-byte equality."""

    if type(assignment_bytes) is not bytes:
        _fail(NMFASelectorErrorCode.INVALID_ARGUMENT)
    expected = derive_nmfa_selector_assignment(
        raw,
        expected_eligible_split_inventory_sha256,
        nonce_hex,
    )
    if assignment_bytes != expected.receipt_bytes:
        _fail(NMFASelectorErrorCode.ASSIGNMENT_CONTRACT_INVALID)
    return expected


def load_installed_nmfa_selector_plan() -> dict[str, Any]:
    """Load a fresh copy of the installed source-free selector plan."""

    _, bundle_created_at = _validate_installed_bundle()
    raw = _resource_bytes(_PLAN_PATH)
    try:
        value = decode_json(raw)
    except CorpusFormatError:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    if type(value) is not dict or encode_json(value) != raw:
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    _validate_schema(
        value,
        _PLAN_SCHEMA_PATH,
        contract_error=NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID,
    )
    bindings = value["bindings"]
    if (
        bindings["parent_protocol_sha256"] != "sha256:" + _PARENT_PROTOCOL_SHA256
        or bindings["gate_plan_sha256"] != "sha256:" + _GATE_PLAN_SHA256
        or hashlib.sha256(_resource_bytes(_PARENT_PROTOCOL_PATH)).hexdigest()
        != _PARENT_PROTOCOL_SHA256
        or hashlib.sha256(_resource_bytes(_GATE_PLAN_PATH)).hexdigest() != _GATE_PLAN_SHA256
        or value["created_at"] >= bundle_created_at
    ):
        _fail(NMFASelectorErrorCode.PACKAGE_RESOURCE_INVALID)
    return value


__all__ = [
    "NMFASelectorAnalysis",
    "NMFASelectorError",
    "NMFASelectorErrorCode",
    "NMFASelectorOutcome",
    "ProtectedNMFASelectorAssignment",
    "ValidatedNMFASelectorInventory",
    "derive_nmfa_selector_assignment",
    "evaluate_nmfa_selector_inventory",
    "load_installed_nmfa_selector_plan",
    "normalize_nmfa_split_nonce",
    "validate_nmfa_selector_inventory",
    "verify_nmfa_selector_assignment",
]
