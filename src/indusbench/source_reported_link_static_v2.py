"""Fail-closed exact-16 package-local source-link static resolver.

This sidecar consumes the frozen V2 compatibility wrapper without changing the
legacy exact-14 loader's public behavior.  A successful snapshot establishes
only agreement among fixed installed bytes, schemas, parent bindings, and the
exact-two canonical re-encoding canaries.  It does not authenticate the
package, satisfy the future runtime or authority boundary, permit source
access, or establish a scientific result.
"""

from __future__ import annotations

import hashlib
import importlib.resources
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

from .io import encode_json
from .source_reported_link_static import (
    _LEGACY_EXACT_BYTE_JSON_KEYS,
    _MISSING_BINDING_FIELDS,
    _STRICT_V1_RESOLVER_BLOCKERS,
    SourceLinkStaticError,
    SourceLinkStaticErrorCode,
    _decode_static_resource,
    _fail,
    _inspect_schema_keywords,
    _read_static_package_exact,
    _require_object,
    _ResourceKey,
    _StaticResourceSpec,
    _validate_schemas_and_instances,
    _verify_cross_bindings,
)
from .source_reported_link_static import (
    _RESOURCE_SPECS as _V1_RESOURCE_SPECS,
)

_STATIC_RESOURCE_COUNT: Final = 16
_STATIC_TOTAL_BYTES: Final = 1_069_631
_CANONICAL_JSON_PROFILE_ID: Final = "indusbench-io-encode-json-v1"
_COMPATIBILITY_PROFILE_ID: Final = "source-reported-link-exact-two-static-byte-compatibility-v2"
_PACKAGE_LOCAL_STATUS: Final = "validated_package_local_exact16_only"
_ACTIVATION_STATUS: Final = "blocked_external_prerequisites_absent"
_DEFAULT_AND_EXCEPTION_PRECEDENCE: Final = (
    "after_exact_raw_path_regular_file_size_and_sha256_match_apply_the_closed_exact_two_"
    "canonical_reencoding_canary_rule_only_to_the_ordered_exception_members_and_hard_"
    "reject_noncanonical_raw_bytes_for_every_other_static_dynamic_or_runtime_resource"
)

_WRAPPER_SPEC: Final = _StaticResourceSpec(
    _ResourceKey.CUSTODY_CONTRACT_V2,
    "registry",
    "source-reported-link-protected-ephemeral-custody-contract-v2.json",
    16981,
    "a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c",
)
_WRAPPER_SCHEMA_SPEC: Final = _StaticResourceSpec(
    _ResourceKey.CUSTODY_CONTRACT_V2_SCHEMA,
    "schemas",
    "source-reported-link-protected-ephemeral-custody-contract-v2.schema.json",
    17694,
    "1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671",
)
_RESOURCE_SPECS: Final = (
    *_V1_RESOURCE_SPECS,
    _WRAPPER_SPEC,
    _WRAPPER_SCHEMA_SPEC,
)
_SPEC_BY_KEY: Final[Mapping[_ResourceKey, _StaticResourceSpec]] = MappingProxyType(
    {spec.key: spec for spec in _RESOURCE_SPECS}
)


@dataclass(frozen=True, slots=True)
class _LegacyCanonicalCanary:
    key: _ResourceKey
    canonical_size: int
    canonical_sha256: str
    validation_mode: str
    schema_key: _ResourceKey
    binding_sources: tuple[str, ...]


_LEGACY_CANARIES: Final = (
    _LegacyCanonicalCanary(
        _ResourceKey.SOURCE_REGISTRY,
        43239,
        "da9254e6a8cd4d6cbe7a465119bd1a1be7b6583586b8b1cb0cb8af02e9f83b1b",
        "instance_against_exact_schema",
        _ResourceKey.SOURCE_REGISTRY_SCHEMA,
        (
            "registry/source-reported-link-source-contract-v1.json"
            "#/parent_commitments/source_registry",
            "registry/source-reported-link-source-contract-v1.json"
            "#/revision_receipt_requirement/future_receipt_top_level/"
            "expected_source_registry_sha256",
            "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json"
            "#/cross_artifact_verifier_contract/static_file_binding_resolver/"
            "exact_authority_bound_static_files/parent_source_registry",
            "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json"
            "#/parent_commitments/source_registry",
        ),
    ),
    _LegacyCanonicalCanary(
        _ResourceKey.SOURCE_REGISTRY_SCHEMA,
        8295,
        "b118345e10446f92446114b3a1773bb0927a6b808e253268088d953776218073",
        "draft202012_check_schema",
        _ResourceKey.SOURCE_REGISTRY_SCHEMA,
        (
            "registry/source-reported-link-source-contract-v1.json"
            "#/parent_commitments/source_registry_schema",
        ),
    ),
)
_CANARY_BY_KEY: Final[Mapping[_ResourceKey, _LegacyCanonicalCanary]] = MappingProxyType(
    {canary.key: canary for canary in _LEGACY_CANARIES}
)

_ACTIVATION_PRECONDITIONS: Final = (
    "successor_static_resolver_implementation_validated",
    "v2_wrapper_raw_sha256_and_size_bound_by_external_authority_and_transitive_runtime_manifest",
    "v2_const_schema_raw_sha256_and_size_bound_by_transitive_runtime_manifest",
    "complete_transitive_runtime_input_manifest_validated",
    "runtime_distribution_validated_as_a_distinct_resource",
    "independent_bootstrap_verifier_and_fixed_external_trust_root_validated",
    "typed_external_authority_proof_validated",
    "all_remaining_v1_runtime_custody_and_recovery_prerequisites_implemented_and_validated",
)
_STATIC_BINDING_VALUES_UNCHANGED: Final = (
    "source_contract_sha256",
    "source_policy_sha256",
    "source_registry_sha256",
    "ordered_source_roster_sha256",
    "artifact_schema_set_sha256",
)
_AUTHORIZATION_FALSE_FIELDS: Final = (
    "acquisition_authorized",
    "contract_creates_execution_authority",
    "contract_creates_source_access_authority",
    "future_authority_proof_bundle_present",
    "future_dynamic_evidence_or_result_artifacts_present",
    "network_request_performed",
    "profile_packaging_activates_resolver",
    "protected_bytes_present",
    "resolver_implementation_present",
    "source_access_performed",
)
_NONCLAIM_FALSE_FIELDS: Final = (
    "acquisition_authority_established",
    "decipherment_established",
    "independent_custody_established",
    "link_or_no_link_result_established",
    "package_authenticity_established",
    "prize_eligibility_established",
    "redistribution_permission_established",
    "rights_clearance_established",
    "runtime_eligibility_established",
    "scientific_result_established",
    "source_access_occurred",
    "translation_established",
    "trust_root_established",
)
_PREVALIDATION_ORDER: Final = (
    "open_only_the_compiled_package_relative_resource_without_following_links_and_require_"
    "the_fixed_regular_file_boundary",
    "read_bounded_exact_raw_bytes_and_require_the_compiled_path_size_and_raw_SHA256_identity",
    "strictly_decode_UTF8_without_BOM_and_reject_duplicate_keys_floats_nonfinite_numbers_or_"
    "bound_violations",
    "reencode_with_indusbench_io_encode_json_v1",
    "for_an_exact_ordered_exception_require_raw_bytes_to_differ_from_canonical_reencoding_"
    "and_require_its_fixed_canonical_size_and_SHA256_canary",
    "for_every_nonexception_resource_require_exact_raw_and_canonical_byte_equality",
    "never_persist_write_back_return_or_adopt_the_canonical_reencoding_as_identity",
    "validate_the_exact_Draft_2020_12_schema_and_all_parent_roster_schema_set_and_cross_bindings",
    "validate_the_v2_wrapper_and_const_schema_against_externally_compiled_raw_size_and_"
    "SHA256_identities",
    "remain_package_local_and_block_authority_runtime_or_source_access_until_every_future_"
    "external_binding_precondition_is_satisfied",
)
_COMPOSED_PARENT_RULE: Final = {
    "artifact_id": "source-reported-link-protected-ephemeral-custody-contract-v1",
    "artifact_path": ("registry/source-reported-link-protected-ephemeral-custody-contract-v1.json"),
    "base_json_pointer": (
        "/cross_artifact_verifier_contract/static_file_binding_resolver/resolver_exact_order"
    ),
    "composition_rule": (
        "replace_exactly_one_literal_strict_decode_canonical_reencode_token_with_the_closed_"
        "v2_canonical_byte_check_splice_and_preserve_every_other_byte_of_the_v1_order"
    ),
    "replacement_json_pointer": "/resolver_successor/canonical_byte_check_splice",
    "scope": "exact_single_token_static_canonical_byte_check_splice_only",
}
_SUPERSEDED_PARENT_RULES: Final = (
    {
        "artifact_id": "source-reported-link-source-contract-v1",
        "artifact_path": "registry/source-reported-link-source-contract-v1.json",
        "json_pointer": "/canonical_json_profile/noncanonical_raw_bytes_disposition",
        "replacement_json_pointer": "/resolver_successor/default_and_exception_precedence",
        "scope": (
            "only_the_two_ordered_resources_in_resolver_successor_"
            "legacy_noncanonical_static_resources_exact"
        ),
    },
    {
        "artifact_id": "source-reported-link-source-contract-v1",
        "artifact_path": "registry/source-reported-link-source-contract-v1.json",
        "json_pointer": "/execution_boundary/canonical_byte_identity_required",
        "replacement_json_pointer": "/resolver_successor/default_and_exception_precedence",
        "scope": (
            "only_the_two_ordered_resources_in_resolver_successor_"
            "legacy_noncanonical_static_resources_exact"
        ),
    },
    {
        "artifact_id": "source-reported-link-protected-ephemeral-custody-contract-v1",
        "artifact_path": (
            "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json"
        ),
        "json_pointer": "/canonical_json_profile/noncanonical_raw_bytes_disposition",
        "replacement_json_pointer": "/resolver_successor/default_and_exception_precedence",
        "scope": (
            "only_the_two_ordered_resources_in_resolver_successor_"
            "legacy_noncanonical_static_resources_exact"
        ),
    },
    {
        "artifact_id": "source-reported-link-protected-ephemeral-custody-contract-v1",
        "artifact_path": (
            "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json"
        ),
        "json_pointer": (
            "/cross_artifact_verifier_contract/static_file_binding_resolver/"
            "exact_authority_bound_static_files/custody_contract/path"
        ),
        "replacement_json_pointer": (
            "/future_external_binding/custody_contract_sha256_after_successor_activation/path"
        ),
        "scope": "future_external_authority_binding_only_after_all_activation_preconditions",
    },
)

_SNAPSHOT_CONSTRUCTION_TOKEN: Final = object()


@dataclass(frozen=True, slots=True, repr=False, init=False)
class SourceFreeStaticProfileV2Snapshot:
    """Immutable package-local conformance result with no activation meaning."""

    artifact_schema_set_sha256: str
    compatibility_profile_id: str
    compatibility_wrapper_sha256: str
    compatibility_wrapper_schema_sha256: str
    incorporated_v1_custody_contract_sha256: str
    ordered_source_roster_sha256: str
    source_contract_sha256: str
    source_policy_sha256: str
    source_registry_sha256: str
    missing_binding_fields: tuple[str, str]
    package_local_static_prevalidation_status: Literal["validated_package_local_exact16_only"]
    package_local_v2_static_profile_conformant: Literal[True]
    strict_v1_resolver_eligible: Literal[False]
    strict_v1_resolver_blockers: tuple[str, str]
    authority_status: Literal["not_authorized"]
    runtime_status: Literal["not_validated"]
    source_access_status: Literal["not_performed"]
    result_status: Literal["not_established"]
    activation_status: Literal["blocked_external_prerequisites_absent"]
    resource_count: int

    def __init__(
        self,
        *,
        _token: object,
        artifact_schema_set_sha256: str,
        compatibility_wrapper_sha256: str,
        compatibility_wrapper_schema_sha256: str,
        incorporated_v1_custody_contract_sha256: str,
        ordered_source_roster_sha256: str,
        source_contract_sha256: str,
        source_policy_sha256: str,
        source_registry_sha256: str,
    ) -> None:
        if _token is not _SNAPSHOT_CONSTRUCTION_TOKEN:
            _fail(SourceLinkStaticErrorCode.INVALID_ARGUMENT_TYPE)
        object.__setattr__(self, "artifact_schema_set_sha256", artifact_schema_set_sha256)
        object.__setattr__(self, "compatibility_profile_id", _COMPATIBILITY_PROFILE_ID)
        object.__setattr__(self, "compatibility_wrapper_sha256", compatibility_wrapper_sha256)
        object.__setattr__(
            self,
            "compatibility_wrapper_schema_sha256",
            compatibility_wrapper_schema_sha256,
        )
        object.__setattr__(
            self,
            "incorporated_v1_custody_contract_sha256",
            incorporated_v1_custody_contract_sha256,
        )
        object.__setattr__(self, "ordered_source_roster_sha256", ordered_source_roster_sha256)
        object.__setattr__(self, "source_contract_sha256", source_contract_sha256)
        object.__setattr__(self, "source_policy_sha256", source_policy_sha256)
        object.__setattr__(self, "source_registry_sha256", source_registry_sha256)
        object.__setattr__(self, "missing_binding_fields", _MISSING_BINDING_FIELDS)
        object.__setattr__(self, "package_local_static_prevalidation_status", _PACKAGE_LOCAL_STATUS)
        object.__setattr__(self, "package_local_v2_static_profile_conformant", True)
        object.__setattr__(self, "strict_v1_resolver_eligible", False)
        object.__setattr__(self, "strict_v1_resolver_blockers", _STRICT_V1_RESOLVER_BLOCKERS)
        object.__setattr__(self, "authority_status", "not_authorized")
        object.__setattr__(self, "runtime_status", "not_validated")
        object.__setattr__(self, "source_access_status", "not_performed")
        object.__setattr__(self, "result_status", "not_established")
        object.__setattr__(self, "activation_status", _ACTIVATION_STATUS)
        object.__setattr__(self, "resource_count", _STATIC_RESOURCE_COUNT)

    def __repr__(self) -> str:
        return (
            "SourceFreeStaticProfileV2Snapshot("
            "resource_count=16, "
            "package_local_static_prevalidation_status="
            "'validated_package_local_exact16_only', "
            "strict_v1_resolver_eligible=False, "
            "activation_status='blocked_external_prerequisites_absent')"
        )


def _decode_v2_static_resource(raw: bytes, key: _ResourceKey) -> Any:
    value = _decode_static_resource(raw, key)
    canary = _CANARY_BY_KEY.get(key)
    if canary is None:
        return value
    encode_failed = False
    try:
        canonical = encode_json(value)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        encode_failed = True
    if encode_failed:
        _fail(SourceLinkStaticErrorCode.JSON_INVALID)
    if (
        raw == canonical
        or len(canonical) != canary.canonical_size
        or hashlib.sha256(canonical).hexdigest() != canary.canonical_sha256
    ):
        _fail(SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH)
    return value


def _validate_v2_wrapper_schema(values: dict[_ResourceKey, Any]) -> None:
    dependency_missing = False
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        dependency_missing = True
    if dependency_missing:
        _fail(SourceLinkStaticErrorCode.SCHEMA_DEPENDENCY_MISSING)

    wrapper = values[_ResourceKey.CUSTODY_CONTRACT_V2]
    schema = _require_object(values[_ResourceKey.CUSTODY_CONTRACT_V2_SCHEMA])
    _inspect_schema_keywords(schema)
    if (
        set(schema) != {"$id", "$schema", "const"}
        or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != _WRAPPER_SCHEMA_SPEC.name
        or schema.get("const") != wrapper
    ):
        _fail(SourceLinkStaticErrorCode.SCHEMA_INVALID)
    validation_failed = False
    try:
        Draft202012Validator.check_schema(schema)
        error = next(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(wrapper),
            None,
        )
    except Exception:
        validation_failed = True
    if validation_failed:
        _fail(SourceLinkStaticErrorCode.SCHEMA_INVALID)
    if error is not None:
        _fail(SourceLinkStaticErrorCode.SCHEMA_VALIDATION_FAILED)


def _resolve_json_pointer(document: Any, pointer: str) -> Any:
    if type(pointer) is not str or not pointer.startswith("/"):
        raise ValueError
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if (
                not token.isascii()
                or not token.isdigit()
                or (len(token) > 1 and token.startswith("0"))
            ):
                raise ValueError
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise TypeError
    return current


def _path_value_map(values: dict[_ResourceKey, Any]) -> dict[str, Any]:
    return {spec.package_path: values[spec.key] for spec in _RESOURCE_SPECS}


def _expected_incorporated_artifacts(values: dict[_ResourceKey, Any]) -> dict[str, Any]:
    custody = _require_object(values[_ResourceKey.CUSTODY_CONTRACT])
    source_contract = _require_object(values[_ResourceKey.SOURCE_CONTRACT])
    entries = {
        "custody_contract_v1": (
            _ResourceKey.CUSTODY_CONTRACT,
            custody["contract_id"],
        ),
        "custody_contract_v1_const_schema": (
            _ResourceKey.CUSTODY_CONTRACT_SCHEMA,
            _SPEC_BY_KEY[_ResourceKey.CUSTODY_CONTRACT_SCHEMA].name,
        ),
        "source_contract_v1": (
            _ResourceKey.SOURCE_CONTRACT,
            source_contract["contract_id"],
        ),
        "source_contract_v1_const_schema": (
            _ResourceKey.SOURCE_CONTRACT_SCHEMA,
            _SPEC_BY_KEY[_ResourceKey.SOURCE_CONTRACT_SCHEMA].name,
        ),
        "source_registry_legacy_raw": (
            _ResourceKey.SOURCE_REGISTRY,
            _SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY].name,
        ),
        "source_registry_schema_legacy_raw": (
            _ResourceKey.SOURCE_REGISTRY_SCHEMA,
            _SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY_SCHEMA].name,
        ),
    }
    return {
        name: {
            "id": identifier,
            "path": _SPEC_BY_KEY[key].package_path,
            "sha256": _SPEC_BY_KEY[key].tagged_sha256,
            "size": _SPEC_BY_KEY[key].size,
        }
        for name, (key, identifier) in entries.items()
    }


def _verify_exception_bindings(
    values: dict[_ResourceKey, Any],
    exceptions: Any,
) -> None:
    if type(exceptions) is not list or len(exceptions) != len(_LEGACY_CANARIES):
        raise ValueError
    path_values = _path_value_map(values)
    selected_paths = [spec.package_path for spec in _RESOURCE_SPECS]
    for exception_index, (entry, canary) in enumerate(
        zip(exceptions, _LEGACY_CANARIES, strict=True)
    ):
        if type(entry) is not dict:
            raise TypeError
        spec = _SPEC_BY_KEY[canary.key]
        schema_spec = _SPEC_BY_KEY[canary.schema_key]
        expected = {
            "exception_index": exception_index,
            "resource_index": selected_paths.index(spec.package_path),
            "path": spec.package_path,
            "raw_size": spec.size,
            "raw_sha256": spec.tagged_sha256,
            "canonical_reencoding_size": canary.canonical_size,
            "canonical_reencoding_sha256": f"sha256:{canary.canonical_sha256}",
            "validation_mode": canary.validation_mode,
            "validation_schema_path": schema_spec.package_path,
            "validation_schema_resource_index": selected_paths.index(schema_spec.package_path),
            "schema_validation_id": schema_spec.name,
            "normalized_bytes_are_identity": False,
            "normalized_bytes_may_be_persisted": False,
            "binding_sources": list(canary.binding_sources),
        }
        for name, expected_value in expected.items():
            if entry.get(name) != expected_value:
                raise ValueError
        for binding in canary.binding_sources:
            relative_path, pointer = binding.split("#", 1)
            resolved = _resolve_json_pointer(path_values[relative_path], pointer)
            if isinstance(resolved, dict):
                if resolved.get("sha256") != spec.tagged_sha256:
                    raise ValueError
                if "size" in resolved and resolved["size"] != spec.size:
                    raise ValueError
                if "path" in resolved and resolved["path"] != spec.package_path:
                    raise ValueError
            elif resolved != spec.tagged_sha256:
                raise ValueError


def _verify_parent_rules(values: dict[_ResourceKey, Any], wrapper: dict[str, Any]) -> None:
    incorporation = _require_object(wrapper["historical_parent_incorporation"])
    if incorporation["composed_parent_rules_exact"] != [_COMPOSED_PARENT_RULE]:
        raise ValueError
    if incorporation["superseded_parent_rules_exact"] != list(_SUPERSEDED_PARENT_RULES):
        raise ValueError
    if (
        incorporation["incorporation_mode"]
        != "normative_raw_sha256_incorporation_with_closed_exact_pointer_supersession_and_"
        "single_token_composition"
        or incorporation["unlisted_parent_artifact_or_rule_disposition"]
        != "incorporated_unchanged_by_exact_parent_raw_sha256"
    ):
        raise ValueError

    path_values = _path_value_map(values)
    for rule, pointer_name in (
        (_COMPOSED_PARENT_RULE, "base_json_pointer"),
        *((rule, "json_pointer") for rule in _SUPERSEDED_PARENT_RULES),
    ):
        parent = _require_object(path_values[rule["artifact_path"]])
        if parent["contract_id"] != rule["artifact_id"]:
            raise ValueError
        _resolve_json_pointer(parent, rule[pointer_name])
        _resolve_json_pointer(wrapper, rule["replacement_json_pointer"])


def _verify_composition(values: dict[_ResourceKey, Any], wrapper: dict[str, Any]) -> None:
    custody = _require_object(values[_ResourceKey.CUSTODY_CONTRACT])
    successor = _require_object(wrapper["resolver_successor"])
    splice = _require_object(successor["canonical_byte_check_splice"])
    base = custody["cross_artifact_verifier_contract"]["static_file_binding_resolver"][
        "resolver_exact_order"
    ]
    token = "strict_decode_canonical_reencode"
    replacement = (
        "strict_decode_then_reencode_with_indusbench_io_encode_json_v1_then_if_and_only_if_"
        "the_loaded_path_size_and_raw_SHA256_equal_one_ordered_closed_exception_require_raw_"
        "canonical_inequality_and_its_fixed_canonical_size_and_SHA256_canary_else_require_raw_"
        "canonical_byte_equality"
    )
    if (
        splice["base_token_exact"] != token
        or splice["base_token_occurrence_count_exact"] != 1
        or base.count(token) != 1
        or splice["v1_resolver_exact_order_incorporated"] != base
        or splice["replacement_token_exact"] != replacement
        or splice["composed_resolver_exact_order_after_activation"]
        != base.replace(token, replacement)
    ):
        raise ValueError


def _verify_future_binding(values: dict[_ResourceKey, Any], wrapper: dict[str, Any]) -> None:
    custody = _require_object(values[_ResourceKey.CUSTODY_CONTRACT])
    future = _require_object(wrapper["future_external_binding"])
    required = custody["future_protocol_prerequisite_blueprints"]["authority_proof_bundle"][
        "signed_authority_payload"
    ]["required_bindings"]
    first_static = required.index("source_contract_sha256")
    exact_eight = required[first_static : first_static + 8]
    if (
        future["activation_preconditions_exact"] != list(_ACTIVATION_PRECONDITIONS)
        or future["existing_exact_eight_field_names_unchanged"] != exact_eight
        or future["static_binding_values_unchanged_except_custody_contract_sha256"]
        != list(_STATIC_BINDING_VALUES_UNCHANGED)
        or future["adding_only_runtime_bindings_is_sufficient"] is not False
        or future["authority_binding_status"] != "missing_not_implemented"
        or future["custody_contract_sha256_after_successor_activation"]
        != {
            "identity_rule": "raw_SHA256_over_exact_canonical_v2_wrapper_bytes",
            "path": _WRAPPER_SPEC.package_path,
        }
    ):
        raise ValueError

    v1_cycle = custody["cross_artifact_verifier_contract"]["static_file_binding_resolver"][
        "schema_set_self_cycle_exclusion_exact"
    ]
    cycle = future["self_cycle_exclusion"]
    expected_ids = [
        v1_cycle["custody_const_schema_id_forbidden_from_exact_four_schema_set"],
        _WRAPPER_SCHEMA_SPEC.name,
    ]
    expected_paths = [
        v1_cycle["custody_const_schema_path_forbidden_from_exact_four_schema_set"],
        _WRAPPER_SCHEMA_SPEC.package_path,
    ]
    exact_four = custody["artifact_schema_commitments"]["schemas"]
    if (
        cycle["custody_const_schema_forbidden_count_exact"] != 2
        or cycle["custody_const_schema_ids_forbidden_from_exact_four_schema_set_exact"]
        != expected_ids
        or cycle["custody_const_schema_paths_forbidden_from_exact_four_schema_set_exact"]
        != expected_paths
        or cycle["v1_and_v2_custody_const_schemas_may_enter_exact_four_artifact_schema_set"]
        is not False
        or cycle["v2_wrapper_or_schema_self_identity_embedded_in_wrapper"] is not False
        or not set(expected_ids).isdisjoint(entry["id"] for entry in exact_four)
        or not set(expected_paths).isdisjoint(entry["path"] for entry in exact_four)
    ):
        raise ValueError


def _verify_frozen_nonclaims(wrapper: dict[str, Any]) -> None:
    boundary = _require_object(wrapper["authorization_boundary"])
    if (
        set(boundary) != {*_AUTHORIZATION_FALSE_FIELDS, "execution_status", "status"}
        or boundary["status"] != "not_authorized"
        or boundary["execution_status"] != "not_executed"
        or any(boundary[name] is not False for name in _AUTHORIZATION_FALSE_FIELDS)
    ):
        raise ValueError
    nonclaims = _require_object(wrapper["nonclaims"])
    if set(nonclaims) != set(_NONCLAIM_FALSE_FIELDS) or any(
        nonclaims[name] is not False for name in _NONCLAIM_FALSE_FIELDS
    ):
        raise ValueError
    successor = _require_object(wrapper["resolver_successor"])
    if (
        wrapper["contract_status"] != "frozen_source_free_successor_wrapper_packaged_not_activated"
        or successor["default_and_exception_precedence"] != _DEFAULT_AND_EXCEPTION_PRECEDENCE
        or successor["resolver_implementation_status"] != "not_implemented"
        or successor["successor_static_profile_conformant"] is not False
        or successor["successor_static_profile_conformance_status"]
        != "not_evaluated_no_installed_resolver_consumes_this_wrapper"
        or successor["strict_v1_resolver_eligible"] is not False
        or successor["strict_v1_resolver_status"]
        != "permanently_ineligible_for_the_legacy_exact14_snapshot"
        or successor["caller_may_select_path_profile_exception_digest_or_schema"] is not False
    ):
        raise ValueError


def _verify_v2_cross_bindings(values: dict[_ResourceKey, Any]) -> None:
    wrapper = _require_object(values[_ResourceKey.CUSTODY_CONTRACT_V2])
    source_contract = _require_object(values[_ResourceKey.SOURCE_CONTRACT])
    custody = _require_object(values[_ResourceKey.CUSTODY_CONTRACT])
    binding_failed = False
    try:
        if (
            len(_RESOURCE_SPECS) != _STATIC_RESOURCE_COUNT
            or len(_SPEC_BY_KEY) != _STATIC_RESOURCE_COUNT
            or sum(spec.size for spec in _RESOURCE_SPECS) != _STATIC_TOTAL_BYTES
            or len(_LEGACY_CANARIES) != 2
            or set(_CANARY_BY_KEY) != set(_LEGACY_EXACT_BYTE_JSON_KEYS)
        ):
            raise ValueError
        if (
            wrapper["contract_id"] != "source-reported-link-protected-ephemeral-custody-contract-v2"
            or wrapper["schema_id"] != _WRAPPER_SCHEMA_SPEC.name
            or wrapper["schema_version"] != "2.0.0"
            or wrapper["canonical_json_profile"] != source_contract["canonical_json_profile"]
            or wrapper["canonical_json_profile"] != custody["canonical_json_profile"]
            or wrapper["canonical_json_profile"]["profile_id"] != _CANONICAL_JSON_PROFILE_ID
            or wrapper["canonical_json_profile"]["noncanonical_raw_bytes_disposition"]
            != "hard_reject"
        ):
            raise ValueError

        incorporation = wrapper["historical_parent_incorporation"]
        if incorporation["incorporated_artifacts"] != _expected_incorporated_artifacts(values):
            raise ValueError

        successor = wrapper["resolver_successor"]
        selected_paths = [spec.package_path for spec in _RESOURCE_SPECS]
        if (
            successor["compatibility_profile_id"] != _COMPATIBILITY_PROFILE_ID
            or successor["selected_static_resource_count_after_implementation"]
            != _STATIC_RESOURCE_COUNT
            or successor["selected_static_resources_after_implementation_exact"] != selected_paths
            or successor["exact_legacy_noncanonical_static_resource_count"] != 2
            or successor["package_local_static_prevalidation_order"] != list(_PREVALIDATION_ORDER)
            or successor["default_and_exception_precedence"] != _DEFAULT_AND_EXCEPTION_PRECEDENCE
            or successor["unlisted_static_dynamic_or_runtime_noncanonical_resource_disposition"]
            != "hard_reject"
        ):
            raise ValueError
        projection = successor["canonical_projection_disposition"]
        if (
            projection["canonical_reencoding_is_identity"] is not False
            or projection["canonical_reencoding_may_be_persisted_or_written_back"] is not False
            or projection["canonical_reencoding_may_be_returned_to_a_caller"] is not False
            or projection["canonical_reencoding_role"] != "verification_canary_only"
        ):
            raise ValueError

        _verify_exception_bindings(
            values,
            successor["legacy_noncanonical_static_resources_exact"],
        )
        _verify_parent_rules(values, wrapper)
        _verify_composition(values, wrapper)
        _verify_future_binding(values, wrapper)
        _verify_frozen_nonclaims(wrapper)
    except SourceLinkStaticError:
        raise
    except (KeyError, IndexError, TypeError, ValueError):
        binding_failed = True
    if binding_failed:
        _fail(SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH)


def _load_source_link_static_profile_v2_from_root(
    root: Path,
) -> SourceFreeStaticProfileV2Snapshot:
    """Load an installed-layout root; private API reserved for adversarial tests."""

    try:
        raw_resources = _read_static_package_exact(root, _RESOURCE_SPECS)
        values = {key: _decode_v2_static_resource(raw, key) for key, raw in raw_resources.items()}
        _validate_schemas_and_instances(values)
        _validate_v2_wrapper_schema(values)
        schema_set_sha256, roster_sha256 = _verify_cross_bindings(values)
        _verify_v2_cross_bindings(values)
        return SourceFreeStaticProfileV2Snapshot(
            _token=_SNAPSHOT_CONSTRUCTION_TOKEN,
            artifact_schema_set_sha256=schema_set_sha256,
            compatibility_wrapper_sha256=_WRAPPER_SPEC.tagged_sha256,
            compatibility_wrapper_schema_sha256=_WRAPPER_SCHEMA_SPEC.tagged_sha256,
            incorporated_v1_custody_contract_sha256=(
                _SPEC_BY_KEY[_ResourceKey.CUSTODY_CONTRACT].tagged_sha256
            ),
            ordered_source_roster_sha256=roster_sha256,
            source_contract_sha256=_SPEC_BY_KEY[_ResourceKey.SOURCE_CONTRACT].tagged_sha256,
            source_policy_sha256=_SPEC_BY_KEY[_ResourceKey.SOURCE_POLICY].tagged_sha256,
            source_registry_sha256=_SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY].tagged_sha256,
        )
    except SourceLinkStaticError as error:
        error_code = error.code
    _fail(error_code)


def load_installed_source_link_static_profile_v2() -> SourceFreeStaticProfileV2Snapshot:
    """Validate the fixed exact-16 surface from a real installed package."""

    package_lookup_failed = False
    try:
        traversable = importlib.resources.files("indusbench")
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        package_lookup_failed = True
    if package_lookup_failed:
        _fail(SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED)
    if not isinstance(traversable, Path):
        _fail(SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED)
    return _load_source_link_static_profile_v2_from_root(traversable)
