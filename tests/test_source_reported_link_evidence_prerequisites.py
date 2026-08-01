from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import re
import secrets
import subprocess
import unittest
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from indusbench.io import CorpusFormatError, decode_json, encode_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT_PATH = ROOT / "registry" / "source-reported-link-source-contract-v1.json"
SOURCE_POLICY_PATH = ROOT / "registry" / "source-reported-link-policy-v1.json"
SOURCE_REGISTRY_PATH = ROOT / "registry" / "sources.json"
CUSTODY_CONTRACT_PATH = (
    ROOT / "registry" / "source-reported-link-protected-ephemeral-custody-contract-v1.json"
)
CUSTODY_SCHEMA_PATH = (
    ROOT / "schemas" / "source-reported-link-protected-ephemeral-custody-contract.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "source-reported-link-source-revision-receipt.schema.json"
ENVELOPE_SCHEMA_PATH = (
    ROOT / "schemas" / "source-reported-link-receipt-commitment-envelope.schema.json"
)
REVISION_SET_SCHEMA_PATH = ROOT / "schemas" / "source-reported-link-source-revision-set.schema.json"
COMPLETENESS_SCHEMA_PATH = (
    ROOT / "schemas" / "source-reported-link-completeness-attestation.schema.json"
)

SOURCE_CONTRACT_SHA256 = "e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f"
SOURCE_POLICY_SHA256 = "c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90"
SOURCE_REGISTRY_SHA256 = "e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584"
CONTRACT_SHA256 = f"sha256:{SOURCE_CONTRACT_SHA256}"
ORDERED_ROSTER_SHA256 = "sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f"
ORDERED_ROSTER_DOMAIN = "indusbench:source-reported-link:ordered-inspection-roster:v1"
RECEIPT_DOMAIN = "indusbench:source-reported-link:source-revision-receipt:v1"
REVISION_SET_DOMAIN = "indusbench:source-reported-link:source-revision-set:v1"
COMPLETENESS_DOMAIN = "indusbench:source-reported-link:completeness-attestation:v1"
ACQUISITION_GRAPH_DOMAIN = "indusbench:source-reported-link:acquisition-artifact-graph:v1"
PASS_OBSERVATION_DOMAIN = "indusbench:source-reported-link:pass-observation-payload:v1"
PASS_PROOF_DOMAIN = "indusbench:source-reported-link:typed-pass-proof-bundle:v1"
PASS_SEAL_DOMAIN = "indusbench:source-reported-link:pass-seal-statement:v1"
ENVELOPE_DOMAIN = "indusbench:source-reported-link:receipt-commitment-envelope:v1"
SCHEMA_SET_DOMAIN = "indusbench:source-reported-link:artifact-schema-set:v1"
DELETION_RECORD_DOMAIN = "indusbench:source-reported-link:custody-deletion-record:v1"
LEDGER_GENERATION_DOMAIN = "indusbench:source-reported-link:attempt-ledger-generation:v1"
REGISTRY_GENERATION_DOMAIN = "indusbench:source-reported-link:attempt-registry-generation:v1"
G20_PROJECTION_DOMAIN = "indusbench:source-reported-link:g20-sanitized-control-projection:v1"
_TEST_ATTEMPT_ROLE_KEY = "a" * 64
_TEST_REGISTRY_NAMESPACE = "attempt-v1:" + "b" * 64
RUNTIME_DISTRIBUTION_MEMBER_DOMAIN = (
    "indusbench:source-reported-link:runtime-distribution-member:v1"
)
RUNTIME_DISTRIBUTION_ID = "authorized-runtime-distribution-v1"
RUNTIME_DISTRIBUTION_PATH = "runtime/authorized-runtime-distribution-v1.bin"
RUNTIME_DISTRIBUTION_VECTOR = b"indus-source-reported-link-runtime-distribution-v1\n"
PENN_RECORD_IDS = ("83830", "83829", "149372", "238862", "329820")
PENN_RESOURCE_IDS = tuple(
    f"source-resource-v1:penn-object-{record_id}" for record_id in PENN_RECORD_IDS
)
PENN_ITEM_URIS = tuple(
    f"https://collections.penn.museum/collections/object/{record_id}"
    for record_id in PENN_RECORD_IDS
)
LINK_IDS = tuple(f"chanhu-daro-preselection-v1:{index:03d}" for index in range(6))
MACKAY_FIELD_NUMBERS = ("SF 2000", "SF 3495", "SF 3493", "SF 2428", "SF 3051", "SF 2558")
PENN_ACCESSION_NUMBERS = (
    "L-141-160",
    "L-141-159",
    "L-141-92",
    "L-141-176",
    "L-141-177",
    "L-141-177",
)
PASS_ROLES = (
    "lead_no_listed_material_conflict",
    "excavation_location_axis_conflict",
    "lead_no_listed_material_conflict",
    "lead_no_listed_material_conflict",
    "shared_penn_target_identity_collision",
    "shared_penn_target_identity_collision",
)
PASS_SLOT_TASKS: tuple[dict[str, Any], ...] = tuple(
    {
        "collision_group": ("chanhu-daro-penn-329820-collision" if index in (4, 5) else None),
        "index": index,
        "link_id": LINK_IDS[index],
        "mackay_locator": {
            "identifier": MACKAY_FIELD_NUMBERS[index],
            "identifier_namespace": "field_number",
            "resource_id": "source-resource-v1:mackay-report",
        },
        "penn_locators": [
            {
                "identifier": (*PENN_RECORD_IDS, PENN_RECORD_IDS[-1])[index],
                "identifier_namespace": "official_record_id",
            },
            {
                "identifier": PENN_ACCESSION_NUMBERS[index],
                "identifier_namespace": "accession_number",
            },
        ],
        "penn_resource_id": (*PENN_RESOURCE_IDS, PENN_RESOURCE_IDS[-1])[index],
        "role": PASS_ROLES[index],
        "unresolved_axis": "excavation_location" if index == 1 else None,
    }
    for index in range(6)
)
PASS_RESULT_KEYS = set(PASS_SLOT_TASKS[0]) | {"outcome", "source_local_locator"}
OFFICIAL_RECORD_ID_RE = re.compile(r"^[0-9]{1,16}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SCHEMA_PATHS = (
    CUSTODY_SCHEMA_PATH,
    RECEIPT_SCHEMA_PATH,
    ENVELOPE_SCHEMA_PATH,
    REVISION_SET_SCHEMA_PATH,
    COMPLETENESS_SCHEMA_PATH,
)
DYNAMIC_SCHEMA_PATHS = (
    RECEIPT_SCHEMA_PATH,
    ENVELOPE_SCHEMA_PATH,
    REVISION_SET_SCHEMA_PATH,
    COMPLETENESS_SCHEMA_PATH,
)
CANDIDATE_PATHS = (
    CUSTODY_CONTRACT_PATH,
    *SCHEMA_PATHS,
    Path(__file__),
    ROOT / "tests" / "test_source_reported_link_source_contract.py",
)
PRIVATE_MARKERS = {
    "personal home path": re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+"),
    "literal IPv4": re.compile(
        r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
    ),
    "private key": re.compile(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----"),
    "token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
}
IMF_FIXDATE_RE = re.compile(
    r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([0-9]{2}) "
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"([0-9]{4}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) GMT$"
)
IMF_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
IMF_MONTHS = {
    token: index
    for index, token in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        start=1,
    )
}
GIT_OID_RE = re.compile(r"^[0-9a-f]{40}$")
VALID_PASS_OUTCOMES = {
    "exact_one_candidate",
    "explicit_source_rejection",
    "row_absent",
    "valid_unresolved_source_field_unreadable",
    "valid_unresolved_inspection_indeterminate",
    "valid_unresolved_ambiguous",
    "valid_unresolved_multiple_candidates",
}
_HANDLE_SEAL_KEY = secrets.token_bytes(32)
_ACQUISITION_GRAPH_MAX_BYTES = 16384
_PASS_PROOF_MAX_BYTES = 16384
_COMPLETENESS_MAX_BYTES = 8192
_RAW_ARTIFACT_PROFILES: dict[str, tuple[str, int, Path | None]] = {
    "authority_proof_bundle": (
        "indusbench:source-reported-link:authority-proof-bundle:v1",
        16384,
        None,
    ),
    "one_time_attempt_reservation": (
        "indusbench:source-reported-link:attempt-reservation:v1",
        16384,
        None,
    ),
    "attempt_registry_generation": (
        "indusbench:source-reported-link:attempt-registry-generation:v1",
        16384,
        None,
    ),
    "pre_acquisition_attestation": (
        "indusbench:source-reported-link:acquisition-preflight-attestation:v1",
        16384,
        None,
    ),
    "source_revision_receipt_payload": (RECEIPT_DOMAIN, 65536, RECEIPT_SCHEMA_PATH),
    "receipt_commitment_envelope": (ENVELOPE_DOMAIN, 4096, ENVELOPE_SCHEMA_PATH),
    "source_revision_set_payload": (REVISION_SET_DOMAIN, 16384, REVISION_SET_SCHEMA_PATH),
    "transitive_runtime_input_manifest": (
        "indusbench:source-reported-link:transitive-runtime-input-manifest:v1",
        65536,
        None,
    ),
    "post_acquisition_execution_attestation": (
        "indusbench:source-reported-link:acquisition-execution-attestation:v1",
        32768,
        None,
    ),
}
_RAW_PROFILE_CONTRACT_KEYS = {
    "authority_proof_bundle": ("authority_proof_sha256", "authority_proof_bundle"),
    "one_time_attempt_reservation": (
        "attempt_reservation_sha256",
        "one_time_attempt_reservation",
    ),
    "attempt_registry_generation": (
        "attempt_registry_generation_sha256",
        "attempt_registry_generation",
    ),
    "pre_acquisition_attestation": (
        "acquisition_preflight_attestation_sha256",
        "pre_acquisition_attestation",
    ),
    "source_revision_receipt_payload": (
        "revision_receipt_sha256",
        "source_revision_receipt_payload",
    ),
    "receipt_commitment_envelope": (
        "receipt_commitment_envelope_sha256",
        "receipt_commitment_envelope",
    ),
    "source_revision_set_payload": (
        "source_revision_sha256",
        "source_revision_set_payload",
    ),
    "transitive_runtime_input_manifest": (
        "transitive_runtime_input_manifest_sha256",
        "transitive_runtime_input_manifest",
    ),
    "post_acquisition_execution_attestation": (
        "acquisition_execution_attestation_sha256",
        "post_acquisition_execution_attestation",
    ),
}
_ACQUISITION_GRAPH_ROLES = (
    "authority_proof_bundle",
    "one_time_attempt_reservation",
    "attempt_registry_generation",
    "pre_acquisition_attestation",
    "source_revision_receipt_payload",
    "receipt_commitment_envelope",
    "source_revision_set_payload",
)
_CONTROL_ARTIFACT_STATE_BY_ROLE = {
    "authority_proof_bundle": "AUTHORITY_VERIFIED_DURABLE",
    "one_time_attempt_reservation": "GRANT_RESERVED_DURABLE",
    "attempt_registry_generation": "ACQUISITION_STARTED_DURABLE",
    "pre_acquisition_attestation": "PREFLIGHT_BOUND_DURABLE",
    "transitive_runtime_input_manifest": "RUNTIME_MANIFEST_VERIFIED",
    "post_acquisition_execution_attestation": ("POST_ACQUISITION_ATTESTED_DURABLE"),
}


@dataclass(frozen=True)
class ValidatedRuntimeDistributionHandle:
    raw: bytes
    sha256: str
    size: int
    artifact_id: str
    path: str
    member_commitment_sha256: str
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ValidatedRawArtifactHandle:
    role: str
    raw: bytes
    payload: dict[str, Any]
    artifact_sha256: str
    canonical_size: int
    digest_domain: str
    maximum_bytes: int
    authority_grant_id: str
    attempt_id: str
    schema_id: str | None
    schema_sha256: str | None
    runtime_distribution: ValidatedRuntimeDistributionHandle | None
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ValidatedAcquisitionGraphHandle:
    raw: bytes
    payload: dict[str, Any]
    artifact_sha256: str
    canonical_size: int
    authority_grant_id: str
    attempt_id: str
    revision_receipt_sha256: str
    receipt_commitment_envelope_sha256: str
    source_revision_sha256: str
    ordered_prerequisites: tuple[ValidatedRawArtifactHandle, ...]
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ValidatedPassObservationHandle:
    raw: bytes
    payload: dict[str, Any]
    artifact_sha256: str
    canonical_size: int
    authority_grant_id: str
    attempt_id: str
    revision_receipt_sha256: str
    source_revision_sha256: str
    acquisition_artifact_graph_sha256: str
    pass_id: str
    pass_ordinal: int
    owner_typed_pass_proof_bundle_sha256: str
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ValidatedPassProofHandle:
    raw: bytes
    payload: dict[str, Any]
    artifact_sha256: str
    canonical_size: int
    authority_grant_id: str
    attempt_id: str
    revision_receipt_sha256: str
    source_revision_sha256: str
    acquisition_artifact_graph_sha256: str
    pass_id: str
    pass_ordinal: int
    pass_observation: ValidatedPassObservationHandle
    runtime_manifest: ValidatedRawArtifactHandle
    execution_attestation: ValidatedRawArtifactHandle
    source_policy_sha256: str
    custody_contract_sha256: str
    nullable_completeness_attestation_sha256: str | None
    completeness_applicability: str
    seal_sha256: str
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ValidatedCompletenessHandle:
    raw: bytes
    payload: dict[str, Any]
    artifact_sha256: str
    canonical_size: int
    authority_grant_id: str
    attempt_id: str
    revision_receipt_sha256: str
    source_revision_sha256: str
    pass_id: str
    pass_ordinal: int
    acquisition_artifact_graph_sha256: str
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ValidatedStaticBindingSet:
    artifact_schema_set_sha256: str
    custody_contract_sha256: str
    ordered_source_roster_sha256: str
    runtime_distribution_sha256: str
    source_contract_sha256: str
    source_policy_sha256: str
    source_registry_sha256: str
    transitive_runtime_input_manifest_sha256: str
    _seal: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class ReferenceLedgerGeneration:
    raw: bytes
    generation_index: int
    generation_name: str
    lifecycle_state: str
    domain_digest: str
    canonical_size: int
    previous_generation_domain_digest: str | None


@dataclass(frozen=True)
class ReferenceLedgerChain:
    generations: tuple[ReferenceLedgerGeneration, ...]
    success_prefix_count: int
    terminal_branch_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceTerminalLedgerCopy:
    payload: dict[str, Any]
    success_prefix_count: int
    terminal_branch_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceRegistryGeneration:
    raw: bytes
    generation_index: int
    generation_name: str
    registry_state: str
    domain_digest: str
    canonical_size: int
    previous_generation_domain_digest: str | None


@dataclass(frozen=True)
class ReferenceRegistryChain:
    generations: tuple[ReferenceRegistryGeneration, ...]
    candidate_branch_ids: tuple[str, ...]
    selected_branch_id: str | None
    terminal_copy_profile: str | None
    terminal_registry_provenance: str | None
    terminal_ledger_copy: ReferenceTerminalLedgerCopy | None


@dataclass(frozen=True)
class ReferenceLedgerRootChild:
    name: str
    file_type: str
    nlink: int
    raw: bytes


@dataclass(frozen=True)
class ReferenceLedgerRootSnapshot:
    classification: str
    opened: bool
    children: tuple[ReferenceLedgerRootChild, ...]


@dataclass(frozen=True)
class ReferenceSourceAccessEvidence:
    selector: str
    submode: str
    registry_chain: ReferenceRegistryChain
    ledger_root_snapshot: ReferenceLedgerRootSnapshot
    normalized_remaining_generation_names: tuple[str, ...]
    recovery_action: str
    source_access_status: str


REFERENCE_RECOVERY_ACTIONS = {
    "APPEND_T_COPY_KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK",
    "APPEND_T_COPY_THEN_ALLOWED_LEDGER_REMOVAL_SEQUENCE",
    "COMPLETE_EXACT_COPIED_LEDGER_REMOVAL_SEQUENCE",
    "REQUIRE_EXTERNAL_SAME_PROCESS_PROOF_BEFORE_ANY_CONTINUATION",
    "KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK",
    "NO_LEDGER_RECONSTRUCTION_USE_DURABLE_TERMINAL_REGISTRY_COPY_ONLY",
    "TERMINALIZE_CONTROL_ONLY_NO_RECONSTRUCTION_OR_SOURCE_RETRY",
    "TERMINAL_NO_LEDGER_NO_MUTATION_USE_DURABLE_W_COPY_ONLY",
}
W_REGISTRY_ONLY_TERMINAL_BRANCH_IDS = {
    "workspace_never_created_with_initial_ledger:1",
    "workspace_never_created_without_ledger:0",
}


def contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_float(child) for child in value)
    return False


def canonical_payload(value: Any) -> bytes:
    if contains_float(value):
        raise CorpusFormatError("canonical prerequisite payload: floats are forbidden")
    return encode_json(value)


def decode_canonical(raw: bytes, *, source: str) -> Any:
    value = decode_json(raw, source=source)
    if contains_float(value):
        raise CorpusFormatError(f"{source}: floats are forbidden")
    if encode_json(value) != raw:
        raise CorpusFormatError(f"{source}: noncanonical raw bytes")
    return value


def tagged_digest(domain: str, payload: Any) -> str:
    framed = domain.encode("utf-8") + b"\0" + canonical_payload(payload)
    return "sha256:" + hashlib.sha256(framed).hexdigest()


def recompute_authority_static_bindings(
    runtime_manifest: ValidatedRawArtifactHandle,
) -> dict[str, str]:
    validate_raw_artifact_handle(
        runtime_manifest, expected_role="transitive_runtime_input_manifest"
    )
    if runtime_manifest.runtime_distribution is None:
        raise CorpusFormatError("runtime manifest distribution handle is missing")
    source_contract_raw = SOURCE_CONTRACT_PATH.read_bytes()
    source_contract = decode_canonical(
        source_contract_raw,
        source="authority-bound source contract",
    )
    if not isinstance(source_contract, dict):
        raise CorpusFormatError("authority-bound source contract is not an object")
    custody_raw = CUSTODY_CONTRACT_PATH.read_bytes()
    custody = decode_canonical(custody_raw, source="authority-bound custody contract")
    if not isinstance(custody, dict):
        raise CorpusFormatError("authority-bound custody contract is not an object")
    commitments = custody["artifact_schema_commitments"]
    schema_entries = []
    for entry in commitments["schemas"]:
        schema_raw = (ROOT / entry["path"]).read_bytes()
        schema_entries.append(
            {
                "id": entry["id"],
                "index": entry["index"],
                "path": entry["path"],
                "sha256": "sha256:" + hashlib.sha256(schema_raw).hexdigest(),
                "size": len(schema_raw),
            }
        )
    schema_set_sha256 = tagged_digest(
        SCHEMA_SET_DOMAIN,
        {
            "schema_count": commitments["schema_count"],
            "schema_set_version": commitments["schema_set_version"],
            "schemas": schema_entries,
        },
    )
    roster_sha256 = tagged_digest(
        ORDERED_ROSTER_DOMAIN,
        source_contract["ordered_inspection_roster"]["tasks"],
    )
    return {
        "artifact_schema_set_sha256": schema_set_sha256,
        "custody_contract_sha256": "sha256:" + hashlib.sha256(custody_raw).hexdigest(),
        "ordered_source_roster_sha256": roster_sha256,
        "source_contract_sha256": "sha256:" + hashlib.sha256(source_contract_raw).hexdigest(),
        "source_policy_sha256": "sha256:"
        + hashlib.sha256(SOURCE_POLICY_PATH.read_bytes()).hexdigest(),
        "source_registry_sha256": "sha256:"
        + hashlib.sha256(SOURCE_REGISTRY_PATH.read_bytes()).hexdigest(),
        "runtime_distribution_sha256": runtime_manifest.runtime_distribution.sha256,
        "transitive_runtime_input_manifest_sha256": runtime_manifest.artifact_sha256,
    }


def static_binding_set_payload(handle: ValidatedStaticBindingSet) -> dict[str, str]:
    return {
        "artifact_schema_set_sha256": handle.artifact_schema_set_sha256,
        "custody_contract_sha256": handle.custody_contract_sha256,
        "ordered_source_roster_sha256": handle.ordered_source_roster_sha256,
        "runtime_distribution_sha256": handle.runtime_distribution_sha256,
        "source_contract_sha256": handle.source_contract_sha256,
        "source_policy_sha256": handle.source_policy_sha256,
        "source_registry_sha256": handle.source_registry_sha256,
        "transitive_runtime_input_manifest_sha256": (
            handle.transitive_runtime_input_manifest_sha256
        ),
    }


def validate_static_binding_set(handle: ValidatedStaticBindingSet) -> None:
    if type(handle) is not ValidatedStaticBindingSet:
        raise CorpusFormatError("static bindings require an exact typed handle")
    bindings = static_binding_set_payload(handle)
    if set(bindings) != {
        "artifact_schema_set_sha256",
        "custody_contract_sha256",
        "ordered_source_roster_sha256",
        "runtime_distribution_sha256",
        "source_contract_sha256",
        "source_policy_sha256",
        "source_registry_sha256",
        "transitive_runtime_input_manifest_sha256",
    }:
        raise CorpusFormatError("static binding handle is not exact eight")
    for key, value in bindings.items():
        require_sha256(value, source=f"static binding {key}")
    expected_seal = hmac.digest(_HANDLE_SEAL_KEY, canonical_payload(bindings), "sha256")
    if not isinstance(handle._seal, bytes) or not hmac.compare_digest(handle._seal, expected_seal):
        raise CorpusFormatError("static binding handle seal mismatch")


def resolve_static_binding_set(
    *,
    authority: ValidatedRawArtifactHandle,
    runtime_manifest: ValidatedRawArtifactHandle,
) -> ValidatedStaticBindingSet:
    validate_raw_artifact_handle(authority, expected_role="authority_proof_bundle")
    validate_raw_artifact_handle(
        runtime_manifest, expected_role="transitive_runtime_input_manifest"
    )
    recomputed = recompute_authority_static_bindings(runtime_manifest)
    if recomputed["source_policy_sha256"] != f"sha256:{SOURCE_POLICY_SHA256}":
        raise CorpusFormatError("authority-bound source policy exact bytes mismatch")
    if recomputed["source_contract_sha256"] != CONTRACT_SHA256:
        raise CorpusFormatError("authority-bound source contract exact bytes mismatch")
    if recomputed["source_registry_sha256"] != f"sha256:{SOURCE_REGISTRY_SHA256}":
        raise CorpusFormatError("authority-bound source registry exact bytes mismatch")
    if recomputed["ordered_source_roster_sha256"] != ORDERED_ROSTER_SHA256:
        raise CorpusFormatError("authority-bound ordered roster digest mismatch")
    expected_authority_bindings = recomputed
    if authority.payload["parent_bindings"] != expected_authority_bindings:
        raise CorpusFormatError("static files or runtime manifest are not authority bound")
    handle = ValidatedStaticBindingSet(
        artifact_schema_set_sha256=recomputed["artifact_schema_set_sha256"],
        custody_contract_sha256=recomputed["custody_contract_sha256"],
        ordered_source_roster_sha256=recomputed["ordered_source_roster_sha256"],
        runtime_distribution_sha256=recomputed["runtime_distribution_sha256"],
        source_contract_sha256=recomputed["source_contract_sha256"],
        source_policy_sha256=recomputed["source_policy_sha256"],
        source_registry_sha256=recomputed["source_registry_sha256"],
        transitive_runtime_input_manifest_sha256=(
            recomputed["transitive_runtime_input_manifest_sha256"]
        ),
        _seal=hmac.digest(_HANDLE_SEAL_KEY, canonical_payload(recomputed), "sha256"),
    )
    validate_static_binding_set(handle)
    return handle


def require_exact_keys(payload: dict[str, Any], expected: set[str], *, source: str) -> None:
    if set(payload) != expected:
        raise CorpusFormatError(f"{source}: payload is not closed")


def require_sha256(value: Any, *, source: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise CorpusFormatError(f"{source}: invalid sha256")
    return value


def require_grant_attempt_binding(authority_grant_id: Any, attempt_id: Any) -> None:
    if not isinstance(authority_grant_id, str):
        raise CorpusFormatError("invalid authority grant id")
    derived = derive_grant_identifiers(authority_grant_id)
    if attempt_id != derived["attempt_id"]:
        raise CorpusFormatError("authority grant and attempt binding mismatch")


def handle_seal(
    handle_type: str,
    *,
    raw: bytes,
    artifact_sha256: str,
    canonical_size: int,
    bindings: dict[str, Any],
) -> bytes:
    seal_payload = {
        "artifact_sha256": artifact_sha256,
        "bindings": bindings,
        "canonical_size": canonical_size,
        "handle_type": handle_type,
        "raw_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }
    return hmac.digest(_HANDLE_SEAL_KEY, canonical_payload(seal_payload), "sha256")


def require_handle_integrity(
    *,
    handle_type: str,
    raw: bytes,
    payload: dict[str, Any],
    artifact_sha256: str,
    canonical_size: int,
    domain: str,
    maximum_bytes: int,
    bindings: dict[str, Any],
    seal: bytes,
) -> None:
    if canonical_size != len(raw) or canonical_size > maximum_bytes:
        raise CorpusFormatError(f"tampered {handle_type} handle size is a hard reject")
    decoded = decode_canonical(raw, source=f"validated {handle_type} handle")
    if decoded != payload:
        raise CorpusFormatError(f"tampered {handle_type} handle payload is a hard reject")
    if tagged_digest(domain, decoded) != artifact_sha256:
        raise CorpusFormatError(f"tampered {handle_type} handle digest is a hard reject")
    expected_seal = handle_seal(
        handle_type,
        raw=raw,
        artifact_sha256=artifact_sha256,
        canonical_size=canonical_size,
        bindings=bindings,
    )
    if not isinstance(seal, bytes) or not hmac.compare_digest(seal, expected_seal):
        raise CorpusFormatError(f"tampered {handle_type} handle seal is a hard reject")


def require_two_nonnull_equal_completeness_digests(
    validator: Draft202012Validator,
    first: dict[str, Any],
    second: dict[str, Any],
) -> str:
    validator.validate(first)
    validator.validate(second)
    first_digest = tagged_digest(COMPLETENESS_DOMAIN, first)
    second_digest = tagged_digest(COMPLETENESS_DOMAIN, second)
    if first_digest != second_digest:
        raise CorpusFormatError("two completeness attestation digests differ")
    return first_digest


def body_identity_matches(member: dict[str, Any], body: bytes) -> bool:
    return member["byte_size"] == len(body) and member["sha256"] == (
        "sha256:" + hashlib.sha256(body).hexdigest()
    )


def validate_imf_fixdate(value: str) -> bool:
    match = IMF_FIXDATE_RE.fullmatch(value)
    if match is None:
        return False
    weekday, day, month, year, hour, minute, second = match.groups()
    try:
        parsed = datetime(
            int(year),
            IMF_MONTHS[month],
            int(day),
            int(hour),
            int(minute),
            int(second),
        )
    except (KeyError, ValueError):
        return False
    return IMF_WEEKDAYS[parsed.weekday()] == weekday


def valid_published_git_oid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if any(separator in value for separator in ("\r", "\n", "\u2028", "\u2029")):
        return False
    return len(value) == 40 and GIT_OID_RE.fullmatch(value) is not None


def derive_grant_identifiers(authority_grant_id: str) -> dict[str, str]:
    match = re.fullmatch(r"grant-v1:([0-9a-f]{32})", authority_grant_id)
    if match is None:
        raise CorpusFormatError("invalid authority grant id")
    entropy = bytes.fromhex(match.group(1))
    if len(entropy) != 16 or entropy.hex() != match.group(1):
        raise CorpusFormatError("noncanonical authority grant entropy")
    specifications: dict[str, tuple[str, int | None, str, int | None]] = {
        "attempt_id": (
            "indusbench:source-reported-link:authority-grant-attempt-id:v1",
            None,
            "attempt-v1:",
            16,
        ),
        "pre_authorized_pass_id_ordinal_1": (
            "indusbench:source-reported-link:authority-grant-pass-id:v1",
            1,
            "pass-v1:",
            16,
        ),
        "pre_authorized_pass_id_ordinal_2": (
            "indusbench:source-reported-link:authority-grant-pass-id:v1",
            2,
            "pass-v1:",
            16,
        ),
        "public_safe_attempt_role_key": (
            "indusbench:source-reported-link:authority-grant-attempt-role-key:v1",
            None,
            "",
            None,
        ),
        "public_safe_control_root_id": (
            "indusbench:source-reported-link:authority-grant-control-root-id:v1",
            None,
            "control-root-v1:",
            16,
        ),
        "public_safe_ledger_root_id": (
            "indusbench:source-reported-link:authority-grant-ledger-root-id:v1",
            None,
            "ledger-root-v1:",
            16,
        ),
        "public_safe_workspace_id": (
            "indusbench:source-reported-link:authority-grant-workspace-id:v1",
            None,
            "workspace-v1:",
            16,
        ),
    }
    derived: dict[str, str] = {}
    for role, (domain, ordinal, prefix, byte_count) in specifications.items():
        payload: dict[str, Any] = {
            "authority_grant_entropy_hex": entropy.hex(),
            "derivation_role": role,
        }
        if ordinal is not None:
            payload["pass_ordinal"] = ordinal
        framed = domain.encode("utf-8") + b"\0" + canonical_payload(payload)
        digest = hashlib.sha256(framed).digest()
        derived[role] = prefix + (digest if byte_count is None else digest[:byte_count]).hex()
    normalized_components = [
        value.split(":", maxsplit=1)[1] if ":" in value else value for value in derived.values()
    ]
    if len(set(normalized_components)) != len(normalized_components):
        raise CorpusFormatError("derived grant identifier collision")
    return derived


REFERENCE_MODEL_GRANT_ID = "grant-v1:000102030405060708090a0b0c0d0e0f"
REFERENCE_MODEL_RESERVATION_SHA256 = (
    "sha256:" + hashlib.sha256(b"source-access-reference-model-reservation-v1").hexdigest()
)


def _reference_contract() -> dict[str, Any]:
    value = decode_json(
        CUSTODY_CONTRACT_PATH.read_bytes(),
        source="source-access static reference contract",
    )
    if not isinstance(value, dict):
        raise CorpusFormatError("source-access static reference contract is not an object")
    status = value["executable_reference_model_status"]
    if (
        status["RUNTIME_STRICT_VERIFIER_IMPLEMENTED"] is not False
        or status[
            "root_classifier_terminalizer_restart_bootstrap_and_strict_runtime_verifier_status"
        ]
        != "NOT_IMPLEMENTED_HARD_BLOCK"
        or status[
            "source_access_execution_review_retention_or_publication_authorized_by_reference_model"
        ]
        is not False
    ):
        raise CorpusFormatError("reference model must remain a non-authorizing hard block")
    return value


def _reference_policy() -> tuple[
    tuple[str, ...],
    dict[str, tuple[str, ...]],
    tuple[dict[str, Any], ...],
    dict[str, list[str]],
]:
    contract = _reference_contract()
    ledger_protocol = contract["custody_lifecycle"]["recovery_boundary"][
        "future_ledger_protocol_requirements"
    ]
    success = tuple(ledger_protocol["exact_longest_closed_success_generation_sequence"])
    expanded: dict[str, tuple[str, ...]] = {"clean_evaluated_success:29": success}
    for branch_name, branch in ledger_protocol["normative_closed_branch_table"].items():
        if not isinstance(branch, dict) or "suffix_exact" not in branch:
            continue
        if "prefix_count_exact" in branch:
            prefix_counts = (branch["prefix_count_exact"],)
        else:
            lower, upper = branch["prefix_count_closed_integer_range_inclusive"]
            prefix_counts = range(lower, upper + 1)
        for prefix_count in prefix_counts:
            expanded[f"{branch_name}:{prefix_count}"] = success[:prefix_count] + tuple(
                branch["suffix_exact"]
            )
    setup = contract["future_protocol_prerequisite_blueprints"][
        "one_time_attempt_and_pre_source_setup"
    ]
    rows = tuple(setup["closed_attempt_state_machine"]["normative_registry_only_branches_exact"])
    terminal_crosswalk = setup["cross_file_registry_and_ledger_transition_protocol"][
        "registry_ledger_checkpoint_crosswalk_exact"
    ]["terminal_registry_branch_to_ledger_terminal_branch_crosswalk_exact"]
    if len(rows) != 18 or set(terminal_crosswalk) != {row["branch_id"] for row in rows}:
        raise CorpusFormatError("reference model policy is not exact eighteen")
    return success, expanded, rows, terminal_crosswalk


def _reference_attempt_bindings() -> dict[str, str]:
    derived = derive_grant_identifiers(REFERENCE_MODEL_GRANT_ID)
    return {
        "attempt_id": derived["attempt_id"],
        "attempt_reservation_sha256": REFERENCE_MODEL_RESERVATION_SHA256,
        "attempt_role_key": derived["public_safe_attempt_role_key"],
        "authority_grant_id": REFERENCE_MODEL_GRANT_ID,
        "ledger_root_id": derived["public_safe_ledger_root_id"],
    }


def _success_prefix_count(states: Sequence[str], success: tuple[str, ...]) -> int:
    count = 0
    for actual, expected in zip(states, success, strict=False):
        if actual != expected:
            break
        count += 1
    return count


def _normal_checkpoint_for_prefix(prefix_count: int) -> str:
    if prefix_count <= 2:
        return "R"
    if prefix_count == 3:
        return "P"
    if prefix_count <= 19:
        return "A"
    if prefix_count == 20:
        return "C"
    return "E"


def _checkpoint_range(checkpoint: str) -> tuple[int, int]:
    return {
        "R": (0, 2),
        "P": (2, 3),
        "A": (3, 19),
        "C": (19, 20),
        "E": (20, 29),
    }[checkpoint]


def _ledger_counts_and_status(
    success_prefix_count: int,
    registry_checkpoint: str,
) -> tuple[int, int | None, int | None, str]:
    if not 0 <= success_prefix_count <= 29:
        raise CorpusFormatError("ledger success prefix count is outside the closed range")
    lower, upper = _checkpoint_range(registry_checkpoint)
    if not lower <= success_prefix_count <= upper:
        raise CorpusFormatError("registry checkpoint and ledger prefix are incompatible")
    if registry_checkpoint in {"R", "P"}:
        return 0, 0, 0, "NONE"
    if registry_checkpoint == "A" and success_prefix_count in {3, 4}:
        return 0, 0, 0, "POSSIBLE_KNOWN"
    if registry_checkpoint in {"C", "E"} and success_prefix_count <= 20:
        return 5, 5, 5, "POSSIBLE_KNOWN"
    if success_prefix_count >= 21:
        return 5, 5, 5, "CONFIRMED_COMPLETE"
    if not 5 <= success_prefix_count <= 19:
        raise CorpusFormatError("request-progress prefix is not closed")
    request_step = success_prefix_count - 5
    request_number = request_step // 3 + 1
    phase = request_step % 3
    if phase == 0:
        return request_number, None, None, "POSSIBLE_DISPATCH_UNKNOWN"
    if phase == 1:
        return request_number, request_number, None, "POSSIBLE_BODY_UNKNOWN"
    return request_number, request_number, request_number, "POSSIBLE_KNOWN"


def _count_status(value: int | None, *, kind: str) -> str:
    if value is not None:
        return {
            "body": "exact_complete_body_count",
            "dispatch": "exact_confirmed_application_dispatch_count",
            "intent": "exact_durable_intent_count",
        }[kind]
    return {
        "body": "unknown_before_durable_body_completion",
        "dispatch": "unknown_before_durable_dispatch_confirmation",
    }[kind]


def _g20_projection() -> dict[str, Any]:
    bindings = _reference_attempt_bindings()
    return {
        "attempt_id": bindings["attempt_id"],
        "authority_grant_id": bindings["authority_grant_id"],
        "complete_body_count": 5,
        "confirmed_application_dispatch_count": 5,
        "ledger_generation_index": 20,
        "ledger_lifecycle_state": "POST_ACQUISITION_ATTESTED_DURABLE",
        "request_intent_count": 5,
        "source_access_status": "CONFIRMED_COMPLETE",
    }


def _ledger_generation_payload(
    *,
    generation_index: int,
    lifecycle_state: str,
    previous_digest: str | None,
    success_prefix_count: int,
    registry_checkpoint: str,
    terminal_branch_disposition: str | None,
) -> dict[str, Any]:
    bindings = _reference_attempt_bindings()
    intent, dispatch, body, status = _ledger_counts_and_status(
        success_prefix_count,
        registry_checkpoint,
    )
    projection = _g20_projection() if success_prefix_count >= 21 else None
    payload = {
        "attempt_id": bindings["attempt_id"],
        "attempt_reservation_sha256": bindings["attempt_reservation_sha256"],
        "attempt_role_key": bindings["attempt_role_key"],
        "authority_grant_id": bindings["authority_grant_id"],
        "complete_body_count": body,
        "complete_body_count_status": _count_status(body, kind="body"),
        "confirmed_application_dispatch_count": dispatch,
        "confirmed_application_dispatch_count_status": _count_status(dispatch, kind="dispatch"),
        "g20_sanitized_control_projection": projection,
        "g20_sanitized_control_projection_sha256": (
            tagged_digest(G20_PROJECTION_DOMAIN, projection) if projection is not None else None
        ),
        "generation_index": generation_index,
        "generation_name": (
            f"ledger-v1:{bindings['attempt_role_key']}:generation-{generation_index}"
        ),
        "lifecycle_state": lifecycle_state,
        "previous_ledger_generation_sha256": previous_digest,
        "registry_checkpoint": registry_checkpoint,
        "request_intent_count": intent,
        "request_intent_count_status": _count_status(intent, kind="intent"),
        "source_access_status": status,
        "terminal_branch_disposition": terminal_branch_disposition,
    }
    if terminal_branch_disposition is not None:
        payload["success_prefix_count"] = success_prefix_count
    return payload


def model_build_ledger_generation_raws(
    states: tuple[str, ...],
    *,
    terminal_checkpoint_override: str | None = None,
    terminal_branch_disposition: str | None = None,
) -> tuple[bytes, ...]:
    success, expanded, _rows, _crosswalk = _reference_policy()
    if type(states) is not tuple or not all(type(state) is str for state in states):
        raise CorpusFormatError("reference ledger builder requires an exact state tuple")
    if not any(states == sequence[: len(states)] for sequence in expanded.values()):
        raise CorpusFormatError("reference ledger builder state sequence is not closed")
    terminal_candidates = tuple(
        branch_id for branch_id, sequence in expanded.items() if states == sequence
    )
    selected_terminal_id: str | None = None
    if terminal_branch_disposition is not None:
        matching_ids = tuple(
            branch_id
            for branch_id in terminal_candidates
            if branch_id.rsplit(":", maxsplit=1)[0] == terminal_branch_disposition
        )
        if len(matching_ids) != 1:
            raise CorpusFormatError(
                "ambiguous terminal ledger fixture requires an exact disposition"
            )
        selected_terminal_id = matching_ids[0]
        if selected_terminal_id in W_REGISTRY_ONLY_TERMINAL_BRANCH_IDS:
            raise CorpusFormatError("W terminal disposition is forbidden in causal ledger bytes")
    elif terminal_candidates and not (
        states == success[: len(states)] and len(states) < len(success)
    ):
        if len(terminal_candidates) != 1:
            raise CorpusFormatError(
                "ambiguous terminal ledger fixture requires an exact disposition"
            )
        selected_terminal_id = terminal_candidates[0]
        terminal_branch_disposition = selected_terminal_id.rsplit(":", maxsplit=1)[0]
    terminal_prefix = (
        int(selected_terminal_id.rsplit(":", maxsplit=1)[1])
        if selected_terminal_id is not None
        else len(states)
    )
    previous_digest: str | None = None
    raws: list[bytes] = []
    for index, state in enumerate(states):
        prefix = min(index + 1, terminal_prefix)
        checkpoint = _normal_checkpoint_for_prefix(prefix)
        if (
            terminal_checkpoint_override is not None
            and selected_terminal_id is not None
            and terminal_prefix < len(states)
            and index >= terminal_prefix
        ):
            checkpoint = terminal_checkpoint_override
        payload = _ledger_generation_payload(
            generation_index=index,
            lifecycle_state=state,
            previous_digest=previous_digest,
            success_prefix_count=prefix,
            registry_checkpoint=checkpoint,
            terminal_branch_disposition=(
                terminal_branch_disposition
                if selected_terminal_id is not None and index == len(states) - 1
                else None
            ),
        )
        raw = canonical_payload(payload)
        raws.append(raw)
        previous_digest = tagged_digest(LEDGER_GENERATION_DOMAIN, payload)
    return tuple(raws)


def model_resolve_ledger_chain(
    raw_generations: tuple[bytes, ...],
) -> ReferenceLedgerChain:
    success, expanded, _rows, _crosswalk = _reference_policy()
    if type(raw_generations) is not tuple or not all(type(raw) is bytes for raw in raw_generations):
        raise CorpusFormatError("reference ledger chain requires raw byte tuple")
    decoded: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_generations):
        payload = decode_canonical(raw, source=f"reference ledger generation {index}")
        if not isinstance(payload, dict):
            raise CorpusFormatError("reference ledger generation is not an object")
        decoded.append(payload)
    try:
        states = tuple(payload["lifecycle_state"] for payload in decoded)
    except KeyError as error:
        raise CorpusFormatError("reference ledger generation lacks lifecycle state") from error
    if not any(states == sequence[: len(states)] for sequence in expanded.values()):
        raise CorpusFormatError("reference ledger chain is outside fixed contract policy")
    terminal_candidates = tuple(
        branch_id for branch_id, sequence in expanded.items() if states == sequence
    )
    selected_terminal_id: str | None = None
    if decoded:
        claimed_disposition = decoded[-1].get("terminal_branch_disposition")
        claimed_prefix = decoded[-1].get("success_prefix_count")
        discriminator_present = (
            claimed_disposition is not None or "success_prefix_count" in decoded[-1]
        )
        if discriminator_present and (
            type(claimed_disposition) is not str or type(claimed_prefix) is not int
        ):
            raise CorpusFormatError("terminal ledger discriminator is incomplete")
        if discriminator_present:
            selected_terminal_id = f"{claimed_disposition}:{claimed_prefix}"
            if selected_terminal_id in W_REGISTRY_ONLY_TERMINAL_BRANCH_IDS:
                raise CorpusFormatError(
                    "W terminal disposition is forbidden in causal ledger bytes"
                )
        if selected_terminal_id is not None and selected_terminal_id not in terminal_candidates:
            raise CorpusFormatError("terminal ledger disposition is missing or invalid")
        if selected_terminal_id is None and not (
            states == success[: len(states)] and len(states) < len(success)
        ):
            raise CorpusFormatError("terminal ledger disposition is missing or invalid")
        terminal_ids = (selected_terminal_id,) if selected_terminal_id is not None else ()
    else:
        terminal_ids = ()
    terminal_prefix = (
        int(selected_terminal_id.rsplit(":", maxsplit=1)[1])
        if selected_terminal_id is not None
        else len(states)
    )
    suffix_checkpoint: str | None = None
    previous_digest: str | None = None
    refs: list[ReferenceLedgerGeneration] = []
    for index, (raw, payload, state) in enumerate(
        zip(raw_generations, decoded, states, strict=True)
    ):
        prefix = min(index + 1, terminal_prefix)
        expected_checkpoint = _normal_checkpoint_for_prefix(prefix)
        if (
            selected_terminal_id is not None
            and terminal_prefix < len(states)
            and index >= terminal_prefix
        ):
            claimed = payload.get("registry_checkpoint")
            if not isinstance(claimed, str):
                raise CorpusFormatError("terminal suffix lacks a valid registry checkpoint")
            if suffix_checkpoint is None:
                suffix_checkpoint = claimed
            if claimed != suffix_checkpoint:
                raise CorpusFormatError("terminal suffix changes registry checkpoint")
            expected_checkpoint = suffix_checkpoint
        expected = _ledger_generation_payload(
            generation_index=index,
            lifecycle_state=state,
            previous_digest=previous_digest,
            success_prefix_count=prefix,
            registry_checkpoint=expected_checkpoint,
            terminal_branch_disposition=(
                selected_terminal_id.rsplit(":", maxsplit=1)[0]
                if selected_terminal_id is not None and index == len(states) - 1
                else None
            ),
        )
        require_exact_keys(
            payload,
            set(expected),
            source=f"reference ledger generation {index}",
        )
        if payload != expected:
            raise CorpusFormatError("reference ledger generation semantic mismatch")
        digest = tagged_digest(LEDGER_GENERATION_DOMAIN, payload)
        refs.append(
            ReferenceLedgerGeneration(
                raw=raw,
                generation_index=index,
                generation_name=payload["generation_name"],
                lifecycle_state=state,
                domain_digest=digest,
                canonical_size=len(raw),
                previous_generation_domain_digest=previous_digest,
            )
        )
        previous_digest = digest
    return ReferenceLedgerChain(
        generations=tuple(refs),
        success_prefix_count=terminal_prefix,
        terminal_branch_ids=terminal_ids,
    )


def model_validate_ledger_chain(chain: ReferenceLedgerChain) -> None:
    if type(chain) is not ReferenceLedgerChain:
        raise CorpusFormatError("source reference model requires ReferenceLedgerChain")
    reconstructed = model_resolve_ledger_chain(tuple(ref.raw for ref in chain.generations))
    if reconstructed != chain:
        raise CorpusFormatError("reference ledger chain was mutated")


def model_derive_ledger_source_access_status(chain: ReferenceLedgerChain) -> str:
    model_validate_ledger_chain(chain)
    if not chain.generations:
        return "NONE"
    payload = decode_canonical(
        chain.generations[-1].raw,
        source="reference ledger status head",
    )
    return payload["source_access_status"]


def _terminal_pattern_matches(pattern: str, terminal_branch_id: str) -> bool:
    pattern_name, pattern_suffix = pattern.rsplit(":", maxsplit=1)
    branch_name, branch_suffix = terminal_branch_id.rsplit(":", maxsplit=1)
    if pattern_name != branch_name:
        return False
    if ".." in pattern_suffix:
        lower_text, upper_text = pattern_suffix.split("..", maxsplit=1)
        return int(lower_text) <= int(branch_suffix) <= int(upper_text)
    return pattern_suffix == branch_suffix


def _row_context(row_id: str) -> str:
    if row_id in {
        "scientific_candidate_memory_loss_before_durable_review",
        "review_approved_retention_committed",
        "review_denied",
        "review_failure",
        "candidate_lost_after_approval",
    }:
        return "SCIENTIFIC_CANDIDATE_REVIEW_PENDING"
    if row_id == "clean_execution_attestation_prefix":
        return "NO_ELIGIBLE_SCIENTIFIC_CANDIDATE"
    return "CONTROL_ONLY_DISPOSITION"


def _registry_terminal_index(states: Sequence[str]) -> int | None:
    for terminal_state in (
        "WORKSPACE_NOT_CREATED_TERMINAL_DURABLE",
        "TERMINAL_REGISTRY_DURABLE",
    ):
        if terminal_state in states:
            return states.index(terminal_state)
    return None


def _row_checkpoint(row: dict[str, Any]) -> str:
    states = row["generation_states_exact"]
    terminal_index = _registry_terminal_index(states)
    if terminal_index is None:
        raise CorpusFormatError("registry row lacks a terminal copy state")
    if states[terminal_index] == "WORKSPACE_NOT_CREATED_TERMINAL_DURABLE":
        return "W"
    abbreviations = _reference_contract()["future_protocol_prerequisite_blueprints"][
        "one_time_attempt_and_pre_source_setup"
    ]["closed_attempt_state_machine"]["registry_only_state_abbreviations_exact"]
    reverse = {state: token for token, state in abbreviations.items()}
    return reverse[states[terminal_index - 1]]


def _terminal_copy_payload(
    chain: ReferenceLedgerChain,
    *,
    checkpoint: str,
    branch_context: str,
    w_terminal_branch_id: str | None = None,
) -> dict[str, Any]:
    model_validate_ledger_chain(chain)
    if checkpoint == "W":
        if chain.terminal_branch_ids or type(w_terminal_branch_id) is not str:
            raise CorpusFormatError(
                "W terminal copy requires a registry-derived branch and active ledger"
            )
        expanded_terminal_branch_id = w_terminal_branch_id
    elif w_terminal_branch_id is not None or len(chain.terminal_branch_ids) != 1:
        raise CorpusFormatError("terminal ledger copy requires one exact branch")
    else:
        expanded_terminal_branch_id = chain.terminal_branch_ids[0]
    if checkpoint != "W" and chain.generations:
        suffix_start = chain.success_prefix_count
        inspected = chain.generations[suffix_start:] or chain.generations[-1:]
        if any(
            decode_canonical(
                ref.raw,
                source="reference terminal suffix checkpoint",
            )["registry_checkpoint"]
            != checkpoint
            for ref in inspected
        ):
            raise CorpusFormatError("terminal ledger suffix checkpoint differs from registry row")
    bindings = _reference_attempt_bindings()
    if chain.generations:
        head_payload = decode_canonical(
            chain.generations[-1].raw,
            source="reference terminal ledger head",
        )
        source_status = head_payload["source_access_status"]
        intent = head_payload["request_intent_count"]
        dispatch = head_payload["confirmed_application_dispatch_count"]
        body = head_payload["complete_body_count"]
        intent_status = head_payload["request_intent_count_status"]
        dispatch_status = head_payload["confirmed_application_dispatch_count_status"]
        body_status = head_payload["complete_body_count_status"]
    else:
        source_status = "NONE"
        intent = dispatch = body = 0
        intent_status = "exact_durable_intent_count"
        dispatch_status = "exact_confirmed_application_dispatch_count"
        body_status = "exact_complete_body_count"
    g20_ref = next(
        (
            ref
            for ref in chain.generations
            if ref.lifecycle_state == "POST_ACQUISITION_ATTESTED_DURABLE"
        ),
        None,
    )
    g20_generation: dict[str, Any] | None = None
    if g20_ref is not None:
        g20_payload = decode_canonical(g20_ref.raw, source="reference copied g20")
        if not isinstance(g20_payload, dict):
            raise CorpusFormatError("reference copied g20 is not an object")
        g20_generation = {
            "canonical_size": g20_ref.canonical_size,
            "generation_index": g20_ref.generation_index,
            "generation_name": g20_ref.generation_name,
            "g20_sanitized_control_projection": g20_payload["g20_sanitized_control_projection"],
            "g20_sanitized_control_projection_sha256": g20_payload[
                "g20_sanitized_control_projection_sha256"
            ],
            "sha256": g20_ref.domain_digest,
        }
    terminal_branch_disposition, prefix_text = expanded_terminal_branch_id.rsplit(":", maxsplit=1)
    if int(prefix_text) != chain.success_prefix_count:
        raise CorpusFormatError("terminal ledger branch/prefix mismatch")
    return {
        "attempt_id": bindings["attempt_id"],
        "attempt_role_key": bindings["attempt_role_key"],
        "branch_disposition": branch_context,
        "complete_body_count": body,
        "complete_body_count_status": body_status,
        "confirmed_application_dispatch_count": dispatch,
        "confirmed_application_dispatch_count_status": dispatch_status,
        "g20_generation": g20_generation,
        "ledger_generation_count": len(chain.generations),
        "ledger_head_generation_index": (
            chain.generations[-1].generation_index if chain.generations else None
        ),
        "ledger_head_generation_sha256": (
            chain.generations[-1].domain_digest if chain.generations else None
        ),
        "ledger_root_id": bindings["ledger_root_id"],
        "ordered_ledger_generation_name_digest_state_size_roster": [
            {
                "generation_index": ref.generation_index,
                "generation_name": ref.generation_name,
                "lifecycle_state": ref.lifecycle_state,
                "sha256": ref.domain_digest,
                "size": ref.canonical_size,
            }
            for ref in chain.generations
        ],
        "registry_checkpoint": checkpoint,
        "request_intent_count": intent,
        "request_intent_count_status": intent_status,
        "source_access_status": source_status,
        "expanded_terminal_branch_id": expanded_terminal_branch_id,
        "success_prefix_count": chain.success_prefix_count,
        "terminal_branch_disposition": terminal_branch_disposition,
    }


def _parse_terminal_copy(payload: dict[str, Any]) -> ReferenceTerminalLedgerCopy:
    expected_keys = {
        "attempt_id",
        "attempt_role_key",
        "branch_disposition",
        "complete_body_count",
        "complete_body_count_status",
        "confirmed_application_dispatch_count",
        "confirmed_application_dispatch_count_status",
        "g20_generation",
        "ledger_generation_count",
        "ledger_head_generation_index",
        "ledger_head_generation_sha256",
        "ledger_root_id",
        "ordered_ledger_generation_name_digest_state_size_roster",
        "registry_checkpoint",
        "request_intent_count",
        "request_intent_count_status",
        "source_access_status",
        "expanded_terminal_branch_id",
        "success_prefix_count",
        "terminal_branch_disposition",
    }
    require_exact_keys(payload, expected_keys, source="reference terminal ledger copy")
    bindings = _reference_attempt_bindings()
    if (
        payload["attempt_id"] != bindings["attempt_id"]
        or payload["attempt_role_key"] != bindings["attempt_role_key"]
        or payload["ledger_root_id"] != bindings["ledger_root_id"]
    ):
        raise CorpusFormatError("terminal copy cross-attempt binding mismatch")
    roster = payload["ordered_ledger_generation_name_digest_state_size_roster"]
    if not isinstance(roster, list) or payload["ledger_generation_count"] != len(roster):
        raise CorpusFormatError("terminal copy count/roster mismatch")
    roster_keys = {
        "generation_index",
        "generation_name",
        "lifecycle_state",
        "sha256",
        "size",
    }
    for index, member in enumerate(roster):
        if not isinstance(member, dict):
            raise CorpusFormatError("terminal copy roster member is not an object")
        require_exact_keys(member, roster_keys, source="terminal copy roster member")
        if (
            member["generation_index"] != index
            or member["generation_name"]
            != f"ledger-v1:{bindings['attempt_role_key']}:generation-{index}"
            or not isinstance(member["size"], int)
            or member["size"] <= 0
        ):
            raise CorpusFormatError("terminal copy roster identity mismatch")
        require_sha256(member["sha256"], source="terminal copy roster digest")
    if roster:
        if (
            payload["ledger_head_generation_index"] != len(roster) - 1
            or payload["ledger_head_generation_sha256"] != roster[-1]["sha256"]
        ):
            raise CorpusFormatError("terminal copy head mismatch")
    elif (
        payload["ledger_head_generation_index"] is not None
        or payload["ledger_head_generation_sha256"] is not None
    ):
        raise CorpusFormatError("empty terminal copy has a head")
    _success, expanded, rows, _crosswalk = _reference_policy()
    branch_context = payload["branch_disposition"]
    if type(branch_context) is not str or branch_context not in {
        _row_context(row["branch_id"]) for row in rows
    }:
        raise CorpusFormatError("terminal copy branch disposition is not closed")
    states = tuple(member["lifecycle_state"] for member in roster)
    terminal_candidates = tuple(
        branch_id for branch_id, sequence in expanded.items() if states == sequence
    )
    disposition = payload["terminal_branch_disposition"]
    prefix = payload["success_prefix_count"]
    expanded_id = payload["expanded_terminal_branch_id"]
    if type(disposition) is not str or type(prefix) is not int:
        raise CorpusFormatError("terminal copy discriminator is not closed")
    if (
        type(expanded_id) is not str
        or expanded_id != f"{disposition}:{prefix}"
        or expanded_id not in terminal_candidates
    ):
        raise CorpusFormatError("terminal copy is not an exact fixed ledger branch")
    terminal_ids = (expanded_id,)
    checkpoint = payload["registry_checkpoint"]
    if checkpoint == "W":
        expected = (0, 0, 0, "NONE")
    else:
        expected = _ledger_counts_and_status(prefix, checkpoint)
    intent, dispatch, body, status = expected
    if (
        payload["request_intent_count"] != intent
        or payload["confirmed_application_dispatch_count"] != dispatch
        or payload["complete_body_count"] != body
        or payload["source_access_status"] != status
        or payload["request_intent_count_status"] != _count_status(intent, kind="intent")
        or payload["confirmed_application_dispatch_count_status"]
        != _count_status(dispatch, kind="dispatch")
        or payload["complete_body_count_status"] != _count_status(body, kind="body")
    ):
        raise CorpusFormatError("terminal copy count/status lattice mismatch")
    g20_members = [
        member
        for member in roster
        if member["lifecycle_state"] == "POST_ACQUISITION_ATTESTED_DURABLE"
    ]
    if len(g20_members) > 1:
        raise CorpusFormatError("terminal copy has duplicate g20")
    g20 = payload["g20_generation"]
    if g20_members:
        member = g20_members[0]
        projection = _g20_projection()
        expected_g20 = {
            "canonical_size": member["size"],
            "generation_index": member["generation_index"],
            "generation_name": member["generation_name"],
            "g20_sanitized_control_projection": projection,
            "g20_sanitized_control_projection_sha256": tagged_digest(
                G20_PROJECTION_DOMAIN, projection
            ),
            "sha256": member["sha256"],
        }
        if g20 != expected_g20:
            raise CorpusFormatError("terminal copy g20 projection mismatch")
    elif g20 is not None:
        raise CorpusFormatError("terminal copy invents g20")
    return ReferenceTerminalLedgerCopy(
        payload=payload,
        success_prefix_count=prefix,
        terminal_branch_ids=terminal_ids,
    )


def _terminal_copy_allowed_for_row(
    row: dict[str, Any],
    terminal_copy: ReferenceTerminalLedgerCopy,
) -> bool:
    _success, _expanded, _rows, crosswalk = _reference_policy()
    patterns = crosswalk[row["branch_id"]]
    if terminal_copy.payload["registry_checkpoint"] != _row_checkpoint(row):
        return False
    if terminal_copy.payload["branch_disposition"] != _row_context(row["branch_id"]):
        return False
    if not any(
        _terminal_pattern_matches(pattern, terminal_id)
        for pattern in patterns
        for terminal_id in terminal_copy.terminal_branch_ids
    ):
        return False
    profile = row["terminal_copy_profile_exact"]
    states = tuple(
        member["lifecycle_state"]
        for member in terminal_copy.payload[
            "ordered_ledger_generation_name_digest_state_size_roster"
        ]
    )
    if profile == "WORKSPACE_NEVER_CREATED_NO_LEDGER":
        return not states
    if profile == "WORKSPACE_NEVER_CREATED_G0_ONLY":
        return states == ("INITIAL_LEDGER_DURABLE",)
    if profile == "WORKSPACE_CREATED_LEDGER_RETAINED_UNCERTAINTY":
        return bool(states) and states[-1] == "LEDGER_RETAINED_UNCERTAINTY"
    if not states or states[-1] != "TERMINAL_LEDGER_DURABLE":
        return False
    if profile == "WORKSPACE_CREATED_POST_CLOSURE_REVIEW":
        return (
            terminal_copy.success_prefix_count == 29
            and terminal_copy.payload["g20_generation"] is not None
        )
    return True


def _registry_generation_payload(
    *,
    generation_index: int,
    registry_state: str,
    previous_digest: str | None,
    terminal_metadata: dict[str, Any] | None,
    terminal_registry_generation_sha256: str | None,
) -> dict[str, Any]:
    bindings = _reference_attempt_bindings()
    return {
        "attempt_id": bindings["attempt_id"],
        "attempt_reservation_sha256": bindings["attempt_reservation_sha256"],
        "attempt_role_key": bindings["attempt_role_key"],
        "authority_grant_id": bindings["authority_grant_id"],
        "generation_index": generation_index,
        "generation_name": (
            f"attempt-v1:{bindings['attempt_role_key']}:generation-{generation_index}"
        ),
        "previous_registry_generation_sha256": previous_digest,
        "registry_state": registry_state,
        "terminal_branch_context": (
            terminal_metadata["terminal_branch_context"] if terminal_metadata else None
        ),
        "terminal_copy_profile": (
            terminal_metadata["terminal_copy_profile"] if terminal_metadata else None
        ),
        "terminal_ledger_copy": (
            terminal_metadata["terminal_ledger_copy"] if terminal_metadata else None
        ),
        "terminal_registry_generation_sha256": terminal_registry_generation_sha256,
        "terminal_registry_provenance": (
            terminal_metadata["terminal_registry_provenance"] if terminal_metadata else None
        ),
    }


def model_build_registry_generation_raws(
    row_id: str,
    *,
    terminal_ledger_chain: ReferenceLedgerChain,
) -> tuple[bytes, ...]:
    _success, _expanded, rows, crosswalk = _reference_policy()
    row_by_id = {row["branch_id"]: row for row in rows}
    try:
        row = row_by_id[row_id]
    except KeyError as error:
        raise CorpusFormatError("reference registry builder row id is not exact") from error
    checkpoint = _row_checkpoint(row)
    w_terminal_branch_id: str | None = None
    if checkpoint == "W":
        patterns = crosswalk[row_id]
        if len(patterns) != 1 or ".." in patterns[0]:
            raise CorpusFormatError("W registry row lacks one exact terminal branch")
        w_terminal_branch_id = patterns[0]
    terminal_copy = _terminal_copy_payload(
        terminal_ledger_chain,
        checkpoint=checkpoint,
        branch_context=_row_context(row_id),
        w_terminal_branch_id=w_terminal_branch_id,
    )
    parsed_copy = _parse_terminal_copy(terminal_copy)
    if not _terminal_copy_allowed_for_row(row, parsed_copy):
        raise CorpusFormatError("registry row and terminal ledger branch are incompatible")
    states = tuple(row["generation_states_exact"])
    terminal_index = _registry_terminal_index(states)
    if terminal_index is None:
        raise CorpusFormatError("registry row lacks terminal copy")
    metadata = {
        "terminal_branch_context": _row_context(row_id),
        "terminal_copy_profile": row["terminal_copy_profile_exact"],
        "terminal_ledger_copy": terminal_copy,
        "terminal_registry_provenance": row.get("terminal_registry_provenance_exact"),
    }
    previous_digest: str | None = None
    terminal_digest: str | None = None
    raws: list[bytes] = []
    for index, state in enumerate(states):
        payload = _registry_generation_payload(
            generation_index=index,
            registry_state=state,
            previous_digest=previous_digest,
            terminal_metadata=metadata if index == terminal_index else None,
            terminal_registry_generation_sha256=(
                terminal_digest if index > terminal_index else None
            ),
        )
        raw = canonical_payload(payload)
        raws.append(raw)
        previous_digest = tagged_digest(REGISTRY_GENERATION_DOMAIN, payload)
        if index == terminal_index:
            terminal_digest = previous_digest
    return tuple(raws)


def model_resolve_registry_chain(
    raw_generations: tuple[bytes, ...],
    *,
    terminal_ledger_chain_at_creation: ReferenceLedgerChain | None = None,
) -> ReferenceRegistryChain:
    _success, _expanded, rows, _crosswalk = _reference_policy()
    if (
        type(raw_generations) is not tuple
        or not raw_generations
        or not all(type(raw) is bytes for raw in raw_generations)
    ):
        raise CorpusFormatError("reference registry chain requires nonempty raw tuple")
    decoded: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_generations):
        payload = decode_canonical(raw, source=f"reference registry generation {index}")
        if not isinstance(payload, dict):
            raise CorpusFormatError("reference registry generation is not an object")
        decoded.append(payload)
    try:
        states = tuple(payload["registry_state"] for payload in decoded)
    except KeyError as error:
        raise CorpusFormatError("reference registry generation lacks state") from error
    candidates = [
        row for row in rows if states == tuple(row["generation_states_exact"])[: len(states)]
    ]
    if not candidates:
        raise CorpusFormatError("reference registry chain is outside fixed contract policy")
    terminal_index = _registry_terminal_index(states)
    terminal_copy: ReferenceTerminalLedgerCopy | None = None
    profile: str | None = None
    provenance: str | None = None
    context: str | None = None
    terminal_digest: str | None = None
    previous_digest: str | None = None
    refs: list[ReferenceRegistryGeneration] = []
    for index, (raw, payload, state) in enumerate(
        zip(raw_generations, decoded, states, strict=True)
    ):
        if terminal_index is not None and index == terminal_index:
            raw_copy = payload.get("terminal_ledger_copy")
            if not isinstance(raw_copy, dict):
                raise CorpusFormatError("terminal registry generation lacks closed copy")
            terminal_copy = _parse_terminal_copy(raw_copy)
            profile = payload.get("terminal_copy_profile")
            provenance = payload.get("terminal_registry_provenance")
            context = payload.get("terminal_branch_context")
            filtered: list[dict[str, Any]] = []
            for row in candidates:
                if (
                    row["terminal_copy_profile_exact"] == profile
                    and row.get("terminal_registry_provenance_exact") == provenance
                    and _row_context(row["branch_id"]) == context
                    and _terminal_copy_allowed_for_row(row, terminal_copy)
                ):
                    filtered.append(row)
            candidates = filtered
            if not candidates:
                raise CorpusFormatError("terminal registry context predicts no valid branch")
        expected = _registry_generation_payload(
            generation_index=index,
            registry_state=state,
            previous_digest=previous_digest,
            terminal_metadata=(
                {
                    "terminal_branch_context": context,
                    "terminal_copy_profile": profile,
                    "terminal_ledger_copy": terminal_copy.payload,
                    "terminal_registry_provenance": provenance,
                }
                if terminal_index is not None
                and index == terminal_index
                and terminal_copy is not None
                else None
            ),
            terminal_registry_generation_sha256=(
                terminal_digest if terminal_index is not None and index > terminal_index else None
            ),
        )
        require_exact_keys(
            payload,
            set(expected),
            source=f"reference registry generation {index}",
        )
        if payload != expected:
            raise CorpusFormatError("reference registry generation semantic mismatch")
        digest = tagged_digest(REGISTRY_GENERATION_DOMAIN, payload)
        refs.append(
            ReferenceRegistryGeneration(
                raw=raw,
                generation_index=index,
                generation_name=payload["generation_name"],
                registry_state=state,
                domain_digest=digest,
                canonical_size=len(raw),
                previous_generation_domain_digest=previous_digest,
            )
        )
        previous_digest = digest
        if terminal_index is not None and index == terminal_index:
            terminal_digest = digest
    if terminal_ledger_chain_at_creation is not None:
        model_validate_ledger_chain(terminal_ledger_chain_at_creation)
        if terminal_copy is None:
            raise CorpusFormatError("creation chain supplied before terminal copy")
        expected_creation_copy = _terminal_copy_payload(
            terminal_ledger_chain_at_creation,
            checkpoint=terminal_copy.payload["registry_checkpoint"],
            branch_context=terminal_copy.payload["branch_disposition"],
            w_terminal_branch_id=(
                terminal_copy.payload["expanded_terminal_branch_id"]
                if terminal_copy.payload["registry_checkpoint"] == "W"
                else None
            ),
        )
        if terminal_copy.payload != expected_creation_copy:
            raise CorpusFormatError("T creation chain differs from durable terminal copy")
    exact_rows = [row for row in candidates if tuple(row["generation_states_exact"]) == states]
    selected = exact_rows[0]["branch_id"] if len(exact_rows) == 1 else None
    return ReferenceRegistryChain(
        generations=tuple(refs),
        candidate_branch_ids=tuple(row["branch_id"] for row in candidates),
        selected_branch_id=selected,
        terminal_copy_profile=profile,
        terminal_registry_provenance=provenance,
        terminal_ledger_copy=terminal_copy,
    )


def model_validate_registry_chain(chain: ReferenceRegistryChain) -> None:
    if type(chain) is not ReferenceRegistryChain:
        raise CorpusFormatError("source reference model requires ReferenceRegistryChain")
    reconstructed = model_resolve_registry_chain(tuple(ref.raw for ref in chain.generations))
    if reconstructed != chain:
        raise CorpusFormatError("reference registry chain was mutated")


def model_ledger_root_snapshot(
    classification: str,
    children: tuple[ReferenceLedgerRootChild, ...] = (),
) -> ReferenceLedgerRootSnapshot:
    allowed = {
        "complete_live_chain",
        "not_safely_opened_no_valid_generation_created",
        "terminal_copy_remaining",
        "verified_empty_after_L",
    }
    if classification not in allowed or type(children) is not tuple:
        raise CorpusFormatError("reference ledger root classification is not closed")
    opened = classification != "not_safely_opened_no_valid_generation_created"
    if not opened and children:
        raise CorpusFormatError("unsafe unopened root cannot expose children")
    return ReferenceLedgerRootSnapshot(
        classification=classification,
        opened=opened,
        children=children,
    )


def model_root_children_from_chain(
    chain: ReferenceLedgerChain,
    *,
    indices_in_enumeration_order: Sequence[int] | None = None,
) -> tuple[ReferenceLedgerRootChild, ...]:
    model_validate_ledger_chain(chain)
    indices = (
        tuple(range(len(chain.generations)))
        if indices_in_enumeration_order is None
        else tuple(indices_in_enumeration_order)
    )
    return tuple(
        ReferenceLedgerRootChild(
            name=chain.generations[index].generation_name,
            file_type="regular",
            nlink=1,
            raw=chain.generations[index].raw,
        )
        for index in indices
    )


def _ledger_chain_from_complete_root(
    snapshot: ReferenceLedgerRootSnapshot,
) -> ReferenceLedgerChain:
    if snapshot.classification != "complete_live_chain" or not snapshot.opened:
        raise CorpusFormatError("complete live chain root classification required")
    decoded_children: list[tuple[int, ReferenceLedgerRootChild]] = []
    names: set[str] = set()
    for child in snapshot.children:
        if (
            type(child) is not ReferenceLedgerRootChild
            or child.file_type != "regular"
            or child.nlink != 1
            or child.name in names
        ):
            raise CorpusFormatError("live ledger root child identity mismatch")
        payload = decode_canonical(child.raw, source="reference live ledger child")
        if not isinstance(payload, dict) or payload.get("generation_name") != child.name:
            raise CorpusFormatError("live ledger child name/raw mismatch")
        names.add(child.name)
        decoded_children.append((payload["generation_index"], child))
    decoded_children.sort(key=lambda pair: pair[0])
    if [index for index, _child in decoded_children] != list(range(len(decoded_children))):
        raise CorpusFormatError("live ledger root has a generation gap")
    return model_resolve_ledger_chain(tuple(child.raw for _index, child in decoded_children))


def _preterminal_status(
    registry_chain: ReferenceRegistryChain,
    ledger_chain: ReferenceLedgerChain,
) -> tuple[str, bool]:
    highest = registry_chain.generations[-1].registry_state
    abbreviations = _reference_contract()["future_protocol_prerequisite_blueprints"][
        "one_time_attempt_and_pre_source_setup"
    ]["closed_attempt_state_machine"]["registry_only_state_abbreviations_exact"]
    reverse = {state: token for token, state in abbreviations.items()}
    checkpoint = reverse.get(highest)
    if checkpoint not in {"R", "P", "A", "C", "E"}:
        raise CorpusFormatError("preterminal registry checkpoint is not closed")
    expected = _ledger_counts_and_status(
        ledger_chain.success_prefix_count,
        checkpoint,
    )[3]
    actual = model_derive_ledger_source_access_status(ledger_chain)
    ahead_pair = False
    if ledger_chain.generations:
        last_payload = decode_canonical(
            ledger_chain.generations[-1].raw,
            source="reference preterminal ledger head",
        )
        ledger_checkpoint = last_payload["registry_checkpoint"]
        lower, _upper = _checkpoint_range(checkpoint)
        ahead_pair = (
            ledger_chain.success_prefix_count == lower
            and ledger_checkpoint
            == _normal_checkpoint_for_prefix(ledger_chain.success_prefix_count)
            and len(ledger_chain.generations) == ledger_chain.success_prefix_count
            and ledger_chain.terminal_branch_ids == ()
        )
        if ledger_checkpoint != checkpoint and not ahead_pair:
            raise CorpusFormatError("preterminal registry/ledger status mismatch")
        if not ahead_pair and actual != expected:
            raise CorpusFormatError("preterminal registry/ledger status mismatch")
    elif checkpoint != "R":
        raise CorpusFormatError("only R may have a zero-length live ledger chain")
    return expected, ahead_pair


def model_resolve_source_access_evidence(
    *,
    registry_chain: ReferenceRegistryChain,
    ledger_root_snapshot: ReferenceLedgerRootSnapshot,
) -> ReferenceSourceAccessEvidence:
    model_validate_registry_chain(registry_chain)
    if type(ledger_root_snapshot) is not ReferenceLedgerRootSnapshot:
        raise CorpusFormatError("source reference model requires a root snapshot")
    states = tuple(ref.registry_state for ref in registry_chain.generations)
    terminal_present = any(
        state
        in {
            "TERMINAL_REGISTRY_DURABLE",
            "WORKSPACE_NOT_CREATED_TERMINAL_DURABLE",
        }
        for state in states
    )
    ledger_removed = "LEDGER_REMOVED_DURABLE" in states
    profile = registry_chain.terminal_copy_profile
    terminal_copy = registry_chain.terminal_ledger_copy
    normalized_names: tuple[str, ...] = ()
    if not terminal_present:
        live_chain = _ledger_chain_from_complete_root(ledger_root_snapshot)
        status, ahead_pair = _preterminal_status(registry_chain, live_chain)
        selector = "pre_terminal_copy_live"
        if live_chain.terminal_branch_ids:
            tail = (
                live_chain.generations[-1].lifecycle_state
                if live_chain.generations
                else "NO_LEDGER"
            )
            submode = (
                "T_PENDING_RETAINED_UNCERTAINTY"
                if tail == "LEDGER_RETAINED_UNCERTAINTY"
                else "T_PENDING_CLEAN_TERMINAL_COPY"
            )
            recovery_action = (
                "APPEND_T_COPY_KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK"
                if tail == "LEDGER_RETAINED_UNCERTAINTY"
                else "APPEND_T_COPY_THEN_ALLOWED_LEDGER_REMOVAL_SEQUENCE"
            )
        else:
            submode = "LIVE_ACTIVE_PREFIX"
            recovery_action = (
                "TERMINALIZE_CONTROL_ONLY_NO_RECONSTRUCTION_OR_SOURCE_RETRY"
                if ahead_pair
                else "REQUIRE_EXTERNAL_SAME_PROCESS_PROOF_BEFORE_ANY_CONTINUATION"
            )
    elif profile == "WORKSPACE_NEVER_CREATED_NO_LEDGER":
        if (
            ledger_root_snapshot.classification != "not_safely_opened_no_valid_generation_created"
            or ledger_root_snapshot.opened
            or ledger_root_snapshot.children
            or ledger_removed
        ):
            raise CorpusFormatError("WNC no-ledger root classification is unsafe")
        selector = "WNC_no_ledger_terminal"
        submode = "UNOPENED_SEQUENCE_PROOF_ONLY"
        status = "NONE"
        recovery_action = "TERMINAL_NO_LEDGER_NO_MUTATION_USE_DURABLE_W_COPY_ONLY"
    elif ledger_removed:
        if (
            ledger_root_snapshot.classification != "verified_empty_after_L"
            or not ledger_root_snapshot.opened
            or ledger_root_snapshot.children
            or terminal_copy is None
        ):
            raise CorpusFormatError("post-L root must be opened and verified empty")
        selector = (
            "post_L_WNC_g0"
            if profile == "WORKSPACE_NEVER_CREATED_G0_ONLY"
            else "post_L_workspace_created"
        )
        submode = "POST_L_TERMINAL_REGISTRY_COPY_ONLY_NO_DELETED_RAW"
        status = terminal_copy.payload["source_access_status"]
        recovery_action = "NO_LEDGER_RECONSTRUCTION_USE_DURABLE_TERMINAL_REGISTRY_COPY_ONLY"
    elif profile == "WORKSPACE_CREATED_LEDGER_RETAINED_UNCERTAINTY":
        if terminal_copy is None:
            raise CorpusFormatError("retained uncertainty lacks terminal copy")
        live_chain = _ledger_chain_from_complete_root(ledger_root_snapshot)
        copied_roster = terminal_copy.payload[
            "ordered_ledger_generation_name_digest_state_size_roster"
        ]
        actual_roster = [
            {
                "generation_index": ref.generation_index,
                "generation_name": ref.generation_name,
                "lifecycle_state": ref.lifecycle_state,
                "sha256": ref.domain_digest,
                "size": ref.canonical_size,
            }
            for ref in live_chain.generations
        ]
        if actual_roster != copied_roster:
            raise CorpusFormatError("retained live ledger differs from T copy")
        selector = "terminal_retained_uncertainty"
        submode = "FULL_RETAINED_CHAIN"
        status = terminal_copy.payload["source_access_status"]
        recovery_action = "KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK"
    else:
        if (
            terminal_copy is None
            or ledger_root_snapshot.classification != "terminal_copy_remaining"
            or not ledger_root_snapshot.opened
        ):
            raise CorpusFormatError("pre-L recovery requires remaining-root snapshot")
        roster = terminal_copy.payload["ordered_ledger_generation_name_digest_state_size_roster"]
        by_name = {member["generation_name"]: member for member in roster}
        seen: set[str] = set()
        for child in ledger_root_snapshot.children:
            if (
                type(child) is not ReferenceLedgerRootChild
                or child.file_type != "regular"
                or child.nlink != 1
                or child.name in seen
                or child.name not in by_name
            ):
                raise CorpusFormatError("remaining ledger child identity mismatch")
            member = by_name[child.name]
            payload = decode_canonical(child.raw, source="remaining ledger child")
            if (
                payload.get("generation_name") != child.name
                or len(child.raw) != member["size"]
                or tagged_digest(LEDGER_GENERATION_DOMAIN, payload) != member["sha256"]
                or payload.get("lifecycle_state") != member["lifecycle_state"]
                or payload.get("generation_index") != member["generation_index"]
            ):
                raise CorpusFormatError("remaining ledger child raw/copy mismatch")
            seen.add(child.name)
        normalized_names = tuple(
            member["generation_name"] for member in roster if member["generation_name"] in seen
        )
        selector = "terminal_copy_pre_L_removal_recovery"
        submode = "FULL_PARTIAL_OR_EMPTY_COPY_ORDER_UNLINK"
        status = terminal_copy.payload["source_access_status"]
        recovery_action = "COMPLETE_EXACT_COPIED_LEDGER_REMOVAL_SEQUENCE"
    if recovery_action not in REFERENCE_RECOVERY_ACTIONS:
        raise CorpusFormatError("source reference recovery action is not closed")
    return ReferenceSourceAccessEvidence(
        selector=selector,
        submode=submode,
        registry_chain=registry_chain,
        ledger_root_snapshot=ledger_root_snapshot,
        normalized_remaining_generation_names=normalized_names,
        recovery_action=recovery_action,
        source_access_status=status,
    )


def model_derive_source_access_status(
    evidence: ReferenceSourceAccessEvidence,
) -> str:
    if type(evidence) is not ReferenceSourceAccessEvidence:
        raise CorpusFormatError("source reference model requires ReferenceSourceAccessEvidence")
    reconstructed = model_resolve_source_access_evidence(
        registry_chain=evidence.registry_chain,
        ledger_root_snapshot=evidence.ledger_root_snapshot,
    )
    if reconstructed != evidence:
        raise CorpusFormatError("source reference evidence was mutated")
    return evidence.source_access_status


def validate_resource_cardinality_crosswalk(
    crosswalk: dict[str, Any],
    source_contract: dict[str, Any],
) -> None:
    receipt = source_contract["revision_receipt_requirement"]
    expected_members = receipt["expected_members"]
    expected_ids = [member["resource_id"] for member in expected_members]
    expected_uris = [member["requested_uri"] for member in expected_members]
    if (
        len(expected_members) != 5
        or crosswalk["network_request_transport_trace_receipt_and_body_identity_count_exact"] != 5
        or crosswalk["penn_receipt_resource_ids_exact_parent_order"] != expected_ids
        or crosswalk["penn_receipt_requested_uris_exact_parent_order"] != expected_uris
    ):
        raise CorpusFormatError("five-member Penn acquisition crosswalk mismatch")
    revision_spec = receipt["source_revision_set_specification"]
    resources = source_contract["retrieval_resources"]["resources"]
    mackay = resources[0]
    expected_mackay = {
        "resource_id": mackay["resource_id"],
        "requested_uri": None,
        "final_uri": None,
        "response_representation": None,
        "byte_size": mackay["revision"]["byte_size"],
        "sha256": mackay["revision"]["sha256"],
    }
    if (
        revision_spec["member_count"] != 6
        or crosswalk["source_revision_set_count_exact"] != 6
        or crosswalk["source_revision_set_index_zero_mackay_projection_exact"] != expected_mackay
        or revision_spec["ordered_resource_ids"] != [mackay["resource_id"], *expected_ids]
    ):
        raise CorpusFormatError("six-member revision crosswalk mismatch")
    tasks = source_contract["ordered_inspection_roster"]["tasks"]
    expected_indices = [expected_ids.index(task["penn_resource_id"]) for task in tasks]
    expected_slots = [
        {
            "slot_index": task["index"],
            "penn_receipt_index": expected_indices[index],
            "penn_resource_id": task["penn_resource_id"],
            "mackay_field_number": task["mackay_locator"]["identifier"],
            "collision_group": task["collision_group"],
        }
        for index, task in enumerate(tasks)
    ]
    if (
        expected_indices != [0, 1, 2, 3, 4, 4]
        or crosswalk["pass_slot_to_penn_receipt_index_exact"] != expected_indices
        or crosswalk["pass_slot_crosswalk_exact"] != expected_slots
        or tasks[4]["link_id"] == tasks[5]["link_id"]
        or tasks[4]["mackay_locator"] == tasks[5]["mackay_locator"]
        or tasks[4]["collision_group"] != tasks[5]["collision_group"]
    ):
        raise CorpusFormatError("six-slot pass collision crosswalk mismatch")
    if "network fetch nor local read Mackay content" not in crosswalk[
        "mackay_runtime_content_access_rule"
    ].replace("_", " "):
        raise CorpusFormatError("Mackay no-read rule is missing")


def derive_completeness_applicability(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> str:
    validate_pass_result_vector(first)
    validate_pass_result_vector(second)
    any_row_absent = any(result["outcome"] == "row_absent" for result in (*first, *second))
    if not any_row_absent:
        return "not_applicable_no_row_absent_observation"
    unavailable_outcomes = {
        "valid_unresolved_source_field_unreadable",
        "valid_unresolved_inspection_indeterminate",
        "valid_unresolved_ambiguous",
        "valid_unresolved_multiple_candidates",
    }
    if any(result["outcome"] in unavailable_outcomes for result in (*first, *second)):
        return "applicable_but_payload_forbidden_due_valid_U"
    return "applicable_parent_zero_count_payload_permitted"


def runtime_distribution_member_payload(
    *,
    artifact_id: str,
    path: str,
    sha256: str,
    size: int,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "path": path,
        "sha256": sha256,
        "size": size,
    }


def resolve_runtime_distribution_handle(raw: bytes) -> ValidatedRuntimeDistributionHandle:
    if type(raw) is not bytes or not 1 <= len(raw) <= 32768:
        raise CorpusFormatError("runtime distribution raw resource exceeds exact bound")
    sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
    member_payload = runtime_distribution_member_payload(
        artifact_id=RUNTIME_DISTRIBUTION_ID,
        path=RUNTIME_DISTRIBUTION_PATH,
        sha256=sha256,
        size=len(raw),
    )
    member_commitment = tagged_digest(RUNTIME_DISTRIBUTION_MEMBER_DOMAIN, member_payload)
    seal = hmac.digest(
        _HANDLE_SEAL_KEY,
        canonical_payload(
            {
                "member_commitment_sha256": member_commitment,
                **member_payload,
            }
        ),
        "sha256",
    )
    return ValidatedRuntimeDistributionHandle(
        raw=raw,
        sha256=sha256,
        size=len(raw),
        artifact_id=RUNTIME_DISTRIBUTION_ID,
        path=RUNTIME_DISTRIBUTION_PATH,
        member_commitment_sha256=member_commitment,
        _seal=seal,
    )


def validate_runtime_distribution_handle(
    handle: ValidatedRuntimeDistributionHandle,
) -> None:
    if type(handle) is not ValidatedRuntimeDistributionHandle:
        raise CorpusFormatError("runtime distribution requires a typed raw handle")
    expected_sha256 = "sha256:" + hashlib.sha256(handle.raw).hexdigest()
    member_payload = runtime_distribution_member_payload(
        artifact_id=handle.artifact_id,
        path=handle.path,
        sha256=handle.sha256,
        size=handle.size,
    )
    expected_member_commitment = tagged_digest(RUNTIME_DISTRIBUTION_MEMBER_DOMAIN, member_payload)
    expected_seal = hmac.digest(
        _HANDLE_SEAL_KEY,
        canonical_payload(
            {
                "member_commitment_sha256": handle.member_commitment_sha256,
                **member_payload,
            }
        ),
        "sha256",
    )
    if (
        not 1 <= len(handle.raw) <= 32768
        or handle.sha256 != expected_sha256
        or handle.size != len(handle.raw)
        or handle.artifact_id != RUNTIME_DISTRIBUTION_ID
        or handle.path != RUNTIME_DISTRIBUTION_PATH
        or handle.member_commitment_sha256 != expected_member_commitment
        or not hmac.compare_digest(handle._seal, expected_seal)
    ):
        raise CorpusFormatError("runtime distribution raw or manifest member mismatch")


def runtime_distribution_manifest_bindings(
    handle: ValidatedRuntimeDistributionHandle,
) -> dict[str, str]:
    validate_runtime_distribution_handle(handle)
    return {
        "runtime_distribution_member_commitment_sha256": (handle.member_commitment_sha256),
        "runtime_distribution_sha256": handle.sha256,
    }


def runtime_distribution_manifest_members(
    handle: ValidatedRuntimeDistributionHandle,
) -> list[dict[str, Any]]:
    validate_runtime_distribution_handle(handle)
    return [
        runtime_distribution_member_payload(
            artifact_id=handle.artifact_id,
            path=handle.path,
            sha256=handle.sha256,
            size=handle.size,
        )
    ]


def validate_runtime_manifest_membership(
    payload: dict[str, Any],
    distribution: ValidatedRuntimeDistributionHandle,
) -> None:
    validate_runtime_distribution_handle(distribution)
    members = payload.get("members")
    if type(members) is not list or len(members) != 1:
        raise CorpusFormatError("runtime manifest members are not exact one")
    member = members[0]
    if not isinstance(member, dict):
        raise CorpusFormatError("runtime manifest member is not an object")
    require_exact_keys(
        member,
        {"artifact_id", "path", "sha256", "size"},
        source="runtime manifest distribution member",
    )
    if members != runtime_distribution_manifest_members(distribution):
        raise CorpusFormatError("runtime manifest distribution member mismatch")


def raw_artifact_handle_bindings(handle: ValidatedRawArtifactHandle) -> dict[str, Any]:
    return {
        "attempt_id": handle.attempt_id,
        "authority_grant_id": handle.authority_grant_id,
        "digest_domain": handle.digest_domain,
        "maximum_bytes": handle.maximum_bytes,
        "role": handle.role,
        "schema_id": handle.schema_id,
        "schema_sha256": handle.schema_sha256,
        "runtime_distribution_member_commitment_sha256": (
            handle.runtime_distribution.member_commitment_sha256
            if handle.runtime_distribution is not None
            else None
        ),
        "runtime_distribution_sha256": (
            handle.runtime_distribution.sha256 if handle.runtime_distribution is not None else None
        ),
    }


def validate_raw_artifact_handle(
    handle: ValidatedRawArtifactHandle,
    *,
    expected_role: str,
) -> None:
    if type(handle) is not ValidatedRawArtifactHandle or handle.role != expected_role:
        raise CorpusFormatError("unresolved typed raw artifact handle is a hard reject")
    try:
        domain, maximum_bytes, schema_path = _RAW_ARTIFACT_PROFILES[expected_role]
    except KeyError as error:
        raise CorpusFormatError("unknown typed raw artifact role") from error
    if handle.digest_domain != domain or handle.maximum_bytes != maximum_bytes:
        raise CorpusFormatError("typed raw artifact profile mismatch")
    if expected_role == "transitive_runtime_input_manifest":
        if handle.runtime_distribution is None:
            raise CorpusFormatError("runtime manifest lacks its distribution handle")
        validate_runtime_distribution_handle(handle.runtime_distribution)
        if handle.raw == handle.runtime_distribution.raw:
            raise CorpusFormatError("runtime manifest and distribution raw bytes alias")
        if handle.payload["parent_bindings"] != runtime_distribution_manifest_bindings(
            handle.runtime_distribution
        ):
            raise CorpusFormatError("runtime manifest distribution membership mismatch")
        validate_runtime_manifest_membership(handle.payload, handle.runtime_distribution)
    elif handle.runtime_distribution is not None:
        raise CorpusFormatError("runtime distribution attached to the wrong artifact role")
    require_handle_integrity(
        handle_type=f"typed raw artifact {expected_role}",
        raw=handle.raw,
        payload=handle.payload,
        artifact_sha256=handle.artifact_sha256,
        canonical_size=handle.canonical_size,
        domain=domain,
        maximum_bytes=maximum_bytes,
        bindings=raw_artifact_handle_bindings(handle),
        seal=handle._seal,
    )
    require_grant_attempt_binding(handle.authority_grant_id, handle.attempt_id)
    if schema_path is None:
        expected_keys = {
            "artifact_role",
            "artifact_state",
            "artifact_version",
            "attempt_id",
            "authority_grant_id",
            "parent_bindings",
        }
        if expected_role == "transitive_runtime_input_manifest":
            expected_keys.add("members")
        require_exact_keys(
            handle.payload,
            expected_keys,
            source=f"typed raw artifact {expected_role}",
        )
        if (
            handle.payload["artifact_role"] != expected_role
            or handle.payload["artifact_state"] != _CONTROL_ARTIFACT_STATE_BY_ROLE[expected_role]
            or handle.payload["artifact_version"] != "v1"
            or handle.payload["authority_grant_id"] != handle.authority_grant_id
            or handle.payload["attempt_id"] != handle.attempt_id
            or not isinstance(handle.payload["parent_bindings"], dict)
        ):
            raise CorpusFormatError("typed raw artifact closed binding mismatch")
        for key, value in handle.payload["parent_bindings"].items():
            if not isinstance(key, str):
                raise CorpusFormatError("typed raw artifact parent binding key mismatch")
            require_sha256(value, source="typed raw artifact parent binding")
        if handle.schema_id is not None or handle.schema_sha256 is not None:
            raise CorpusFormatError("unexpected schema binding on uncommitted role")
    else:
        expected_schema_sha256 = "sha256:" + hashlib.sha256(schema_path.read_bytes()).hexdigest()
        if handle.schema_id != schema_path.name or handle.schema_sha256 != expected_schema_sha256:
            raise CorpusFormatError("typed raw artifact schema binding mismatch")


def build_raw_artifact_handle(
    raw: bytes,
    *,
    role: str,
    authority_grant_id: str,
    attempt_id: str,
    payload: dict[str, Any],
    runtime_distribution: ValidatedRuntimeDistributionHandle | None = None,
) -> ValidatedRawArtifactHandle:
    domain, maximum_bytes, schema_path = _RAW_ARTIFACT_PROFILES[role]
    if len(raw) > maximum_bytes:
        raise CorpusFormatError(f"{role} raw resource exceeds bound")
    artifact_sha256 = tagged_digest(domain, payload)
    schema_id = schema_path.name if schema_path is not None else None
    schema_sha256 = (
        "sha256:" + hashlib.sha256(schema_path.read_bytes()).hexdigest()
        if schema_path is not None
        else None
    )
    bindings = {
        "attempt_id": attempt_id,
        "authority_grant_id": authority_grant_id,
        "digest_domain": domain,
        "maximum_bytes": maximum_bytes,
        "role": role,
        "schema_id": schema_id,
        "schema_sha256": schema_sha256,
    }
    handle = ValidatedRawArtifactHandle(
        role=role,
        raw=raw,
        payload=payload,
        artifact_sha256=artifact_sha256,
        canonical_size=len(raw),
        digest_domain=domain,
        maximum_bytes=maximum_bytes,
        authority_grant_id=authority_grant_id,
        attempt_id=attempt_id,
        schema_id=schema_id,
        schema_sha256=schema_sha256,
        runtime_distribution=runtime_distribution,
        _seal=handle_seal(
            f"typed raw artifact {role}",
            raw=raw,
            artifact_sha256=artifact_sha256,
            canonical_size=len(raw),
            bindings={
                **bindings,
                "runtime_distribution_member_commitment_sha256": (
                    runtime_distribution.member_commitment_sha256
                    if runtime_distribution is not None
                    else None
                ),
                "runtime_distribution_sha256": (
                    runtime_distribution.sha256 if runtime_distribution is not None else None
                ),
            },
        ),
    )
    validate_raw_artifact_handle(handle, expected_role=role)
    return handle


def resolve_control_artifact_handle(
    raw: bytes,
    *,
    role: str,
    expected_parent_bindings: dict[str, str],
    runtime_distribution: ValidatedRuntimeDistributionHandle | None = None,
) -> ValidatedRawArtifactHandle:
    if _RAW_ARTIFACT_PROFILES[role][2] is not None:
        raise CorpusFormatError("schema artifact sent to control resolver")
    if len(raw) > _RAW_ARTIFACT_PROFILES[role][1]:
        raise CorpusFormatError(f"{role} raw resource exceeds bound before decode")
    payload = decode_canonical(raw, source=f"resolved {role} payload")
    if not isinstance(payload, dict):
        raise CorpusFormatError(f"{role} payload is not an object")
    expected_keys = {
        "artifact_role",
        "artifact_state",
        "artifact_version",
        "attempt_id",
        "authority_grant_id",
        "parent_bindings",
    }
    if role == "transitive_runtime_input_manifest":
        expected_keys.add("members")
    require_exact_keys(payload, expected_keys, source=role)
    if payload["parent_bindings"] != expected_parent_bindings:
        raise CorpusFormatError(f"{role} parent binding mismatch")
    return build_raw_artifact_handle(
        raw,
        role=role,
        authority_grant_id=payload["authority_grant_id"],
        attempt_id=payload["attempt_id"],
        payload=payload,
        runtime_distribution=runtime_distribution,
    )


def resolve_receipt_handle(
    raw: bytes,
    *,
    validators: dict[Path, Draft202012Validator],
    authority_grant_id: str,
    attempt_id: str,
) -> ValidatedRawArtifactHandle:
    if len(raw) > _RAW_ARTIFACT_PROFILES["source_revision_receipt_payload"][1]:
        raise CorpusFormatError("receipt raw resource exceeds bound before decode")
    payload = decode_canonical(raw, source="resolved receipt payload")
    if not isinstance(payload, dict):
        raise CorpusFormatError("receipt payload is not an object")
    try:
        validators[RECEIPT_SCHEMA_PATH].validate(payload)
    except ValidationError as error:
        raise CorpusFormatError("receipt payload schema mismatch") from error
    return build_raw_artifact_handle(
        raw,
        role="source_revision_receipt_payload",
        authority_grant_id=authority_grant_id,
        attempt_id=attempt_id,
        payload=payload,
    )


def resolve_envelope_handle(
    raw: bytes,
    *,
    validators: dict[Path, Draft202012Validator],
    receipt: ValidatedRawArtifactHandle,
) -> ValidatedRawArtifactHandle:
    validate_raw_artifact_handle(receipt, expected_role="source_revision_receipt_payload")
    if len(raw) > _RAW_ARTIFACT_PROFILES["receipt_commitment_envelope"][1]:
        raise CorpusFormatError("receipt envelope raw resource exceeds bound before decode")
    payload = decode_canonical(raw, source="resolved receipt envelope payload")
    if not isinstance(payload, dict):
        raise CorpusFormatError("receipt envelope payload is not an object")
    try:
        validators[ENVELOPE_SCHEMA_PATH].validate(payload)
    except ValidationError as error:
        raise CorpusFormatError("receipt envelope schema mismatch") from error
    if payload["revision_receipt_sha256"] != receipt.artifact_sha256:
        raise CorpusFormatError("receipt envelope digest mismatch")
    return build_raw_artifact_handle(
        raw,
        role="receipt_commitment_envelope",
        authority_grant_id=receipt.authority_grant_id,
        attempt_id=receipt.attempt_id,
        payload=payload,
    )


def resolve_revision_set_handle(
    raw: bytes,
    *,
    validators: dict[Path, Draft202012Validator],
    receipt: ValidatedRawArtifactHandle,
) -> ValidatedRawArtifactHandle:
    validate_raw_artifact_handle(receipt, expected_role="source_revision_receipt_payload")
    if len(raw) > _RAW_ARTIFACT_PROFILES["source_revision_set_payload"][1]:
        raise CorpusFormatError("source revision set raw resource exceeds bound before decode")
    payload = decode_canonical(raw, source="resolved source revision set payload")
    if not isinstance(payload, dict):
        raise CorpusFormatError("source revision set payload is not an object")
    try:
        validators[REVISION_SET_SCHEMA_PATH].validate(payload)
    except ValidationError as error:
        raise CorpusFormatError("source revision set schema mismatch") from error
    projection_keys = (
        "resource_id",
        "requested_uri",
        "final_uri",
        "response_representation",
        "byte_size",
        "sha256",
    )
    expected_projection = [
        {key: member[key] for key in projection_keys} for member in receipt.payload["members"]
    ]
    if payload["resources"][1:] != expected_projection:
        raise CorpusFormatError("receipt to source revision projection mismatch")
    return build_raw_artifact_handle(
        raw,
        role="source_revision_set_payload",
        authority_grant_id=receipt.authority_grant_id,
        attempt_id=receipt.attempt_id,
        payload=payload,
    )


def validate_parent_handle_chain(
    receipt: ValidatedRawArtifactHandle,
    envelope: ValidatedRawArtifactHandle,
    revision_set: ValidatedRawArtifactHandle,
) -> None:
    validate_raw_artifact_handle(receipt, expected_role="source_revision_receipt_payload")
    validate_raw_artifact_handle(envelope, expected_role="receipt_commitment_envelope")
    validate_raw_artifact_handle(revision_set, expected_role="source_revision_set_payload")
    for handle in (envelope, revision_set):
        if (
            handle.authority_grant_id != receipt.authority_grant_id
            or handle.attempt_id != receipt.attempt_id
        ):
            raise CorpusFormatError("typed scientific parent attempt mismatch")
    if envelope.payload["revision_receipt_sha256"] != receipt.artifact_sha256:
        raise CorpusFormatError("typed receipt envelope digest mismatch")
    projection_keys = (
        "resource_id",
        "requested_uri",
        "final_uri",
        "response_representation",
        "byte_size",
        "sha256",
    )
    expected_projection = [
        {key: member[key] for key in projection_keys} for member in receipt.payload["members"]
    ]
    if revision_set.payload["resources"][1:] != expected_projection:
        raise CorpusFormatError("typed receipt to revision projection mismatch")


def expected_graph_parent_bindings(
    prerequisites: tuple[ValidatedRawArtifactHandle, ...],
) -> dict[str, dict[str, str]]:
    by_role = {handle.role: handle for handle in prerequisites}
    authority_bindings = by_role["authority_proof_bundle"].payload["parent_bindings"]
    if set(authority_bindings) != {
        "artifact_schema_set_sha256",
        "custody_contract_sha256",
        "ordered_source_roster_sha256",
        "runtime_distribution_sha256",
        "source_contract_sha256",
        "source_policy_sha256",
        "source_registry_sha256",
        "transitive_runtime_input_manifest_sha256",
    }:
        raise CorpusFormatError("authority runtime manifest binding is not exact")
    for value in authority_bindings.values():
        require_sha256(value, source="authority static binding")
    authority = by_role["authority_proof_bundle"].artifact_sha256
    reservation = by_role["one_time_attempt_reservation"].artifact_sha256
    registry = by_role["attempt_registry_generation"].artifact_sha256
    return {
        "authority_proof_bundle": authority_bindings,
        "one_time_attempt_reservation": {"authority_proof_sha256": authority},
        "attempt_registry_generation": {
            "attempt_reservation_sha256": reservation,
            "authority_proof_sha256": authority,
        },
        "pre_acquisition_attestation": {
            "attempt_registry_generation_sha256": registry,
            "attempt_reservation_sha256": reservation,
            "authority_proof_sha256": authority,
        },
    }


def graph_node_reference(
    index: int,
    handle: ValidatedRawArtifactHandle,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "artifact_sha256": handle.artifact_sha256,
        "canonical_size": handle.canonical_size,
        "index": index,
        "role": handle.role,
    }
    if handle.schema_id is not None:
        node["schema_id"] = handle.schema_id
        node["schema_sha256"] = handle.schema_sha256
    return node


def validate_graph_prerequisites(
    prerequisites: tuple[ValidatedRawArtifactHandle, ...],
) -> None:
    if type(prerequisites) is not tuple or len(prerequisites) != len(_ACQUISITION_GRAPH_ROLES):
        raise CorpusFormatError("acquisition graph prerequisite tuple is not exact seven")
    if any(type(handle) is not ValidatedRawArtifactHandle for handle in prerequisites):
        raise CorpusFormatError("acquisition graph prerequisite is not a typed raw handle")
    if tuple(handle.role for handle in prerequisites) != _ACQUISITION_GRAPH_ROLES:
        raise CorpusFormatError("acquisition graph prerequisite role order mismatch")
    authority_grant_id = prerequisites[0].authority_grant_id
    attempt_id = prerequisites[0].attempt_id
    for role, handle in zip(_ACQUISITION_GRAPH_ROLES, prerequisites, strict=True):
        validate_raw_artifact_handle(handle, expected_role=role)
        if handle.authority_grant_id != authority_grant_id or handle.attempt_id != attempt_id:
            raise CorpusFormatError("acquisition graph prerequisite attempt mismatch")
    expected_bindings = expected_graph_parent_bindings(prerequisites)
    for role in _ACQUISITION_GRAPH_ROLES[:4]:
        if (
            prerequisites[_ACQUISITION_GRAPH_ROLES.index(role)].payload["parent_bindings"]
            != expected_bindings[role]
        ):
            raise CorpusFormatError("acquisition graph prerequisite chain mismatch")
    validate_parent_handle_chain(prerequisites[4], prerequisites[5], prerequisites[6])


def graph_handle_bindings(handle: ValidatedAcquisitionGraphHandle) -> dict[str, Any]:
    return {
        "attempt_id": handle.attempt_id,
        "authority_grant_id": handle.authority_grant_id,
        "ordered_prerequisite_digests": [
            prerequisite.artifact_sha256 for prerequisite in handle.ordered_prerequisites
        ],
        "receipt_commitment_envelope_sha256": (handle.receipt_commitment_envelope_sha256),
        "revision_receipt_sha256": handle.revision_receipt_sha256,
        "source_revision_sha256": handle.source_revision_sha256,
    }


def validate_acquisition_graph_handle(handle: ValidatedAcquisitionGraphHandle) -> None:
    if type(handle) is not ValidatedAcquisitionGraphHandle:
        raise CorpusFormatError("unresolved acquisition graph handle is a hard reject")
    validate_graph_prerequisites(handle.ordered_prerequisites)
    require_handle_integrity(
        handle_type="acquisition graph",
        raw=handle.raw,
        payload=handle.payload,
        artifact_sha256=handle.artifact_sha256,
        canonical_size=handle.canonical_size,
        domain=ACQUISITION_GRAPH_DOMAIN,
        maximum_bytes=_ACQUISITION_GRAPH_MAX_BYTES,
        bindings=graph_handle_bindings(handle),
        seal=handle._seal,
    )
    require_exact_keys(
        handle.payload,
        {
            "attempt_id",
            "authority_proof_sha256",
            "graph_phase",
            "graph_version",
            "ordered_node_role_and_domain_digest_pairs",
        },
        source="acquisition graph",
    )
    if (
        handle.payload["graph_version"] != "v1"
        or handle.payload["graph_phase"] != "post_acquisition_pre_execution_attestation_core"
    ):
        raise CorpusFormatError("acquisition graph phase or version mismatch")
    expected_nodes = [
        graph_node_reference(index, prerequisite)
        for index, prerequisite in enumerate(handle.ordered_prerequisites)
    ]
    if handle.payload["ordered_node_role_and_domain_digest_pairs"] != expected_nodes:
        raise CorpusFormatError("acquisition graph exact resolved node roster mismatch")
    authority = handle.ordered_prerequisites[0]
    receipt, envelope, revision_set = handle.ordered_prerequisites[4:7]
    if (
        handle.payload["authority_proof_sha256"] != authority.artifact_sha256
        or handle.payload["attempt_id"] != authority.attempt_id
        or handle.authority_grant_id != authority.authority_grant_id
        or handle.attempt_id != authority.attempt_id
        or handle.revision_receipt_sha256 != receipt.artifact_sha256
        or handle.receipt_commitment_envelope_sha256 != envelope.artifact_sha256
        or handle.source_revision_sha256 != revision_set.artifact_sha256
    ):
        raise CorpusFormatError("acquisition graph resolved artifact binding mismatch")


def resolve_acquisition_graph_handle(
    raw: bytes,
    *,
    prerequisites: tuple[ValidatedRawArtifactHandle, ...],
) -> ValidatedAcquisitionGraphHandle:
    if len(raw) > _ACQUISITION_GRAPH_MAX_BYTES:
        raise CorpusFormatError("acquisition graph raw resource exceeds bound")
    validate_graph_prerequisites(prerequisites)
    payload = decode_canonical(raw, source="resolved acquisition graph payload")
    if not isinstance(payload, dict):
        raise CorpusFormatError("acquisition graph payload is not an object")
    authority = prerequisites[0]
    receipt, envelope, revision_set = prerequisites[4:7]
    artifact_sha256 = tagged_digest(ACQUISITION_GRAPH_DOMAIN, payload)
    provisional = ValidatedAcquisitionGraphHandle(
        raw=raw,
        payload=payload,
        artifact_sha256=artifact_sha256,
        canonical_size=len(raw),
        authority_grant_id=authority.authority_grant_id,
        attempt_id=authority.attempt_id,
        revision_receipt_sha256=receipt.artifact_sha256,
        receipt_commitment_envelope_sha256=envelope.artifact_sha256,
        source_revision_sha256=revision_set.artifact_sha256,
        ordered_prerequisites=prerequisites,
        _seal=b"",
    )
    handle = replace(
        provisional,
        _seal=handle_seal(
            "acquisition graph",
            raw=raw,
            artifact_sha256=artifact_sha256,
            canonical_size=len(raw),
            bindings=graph_handle_bindings(provisional),
        ),
    )
    validate_acquisition_graph_handle(handle)
    return handle


def prerequisite_by_role(
    graph: ValidatedAcquisitionGraphHandle,
    role: str,
) -> ValidatedRawArtifactHandle:
    matches = [item for item in graph.ordered_prerequisites if item.role == role]
    if len(matches) != 1:
        raise CorpusFormatError("acquisition graph prerequisite lookup mismatch")
    return matches[0]


def pass_observation_handle_bindings(
    handle: ValidatedPassObservationHandle,
) -> dict[str, Any]:
    return {
        "acquisition_artifact_graph_sha256": (handle.acquisition_artifact_graph_sha256),
        "attempt_id": handle.attempt_id,
        "authority_grant_id": handle.authority_grant_id,
        "owner_typed_pass_proof_bundle_sha256": (handle.owner_typed_pass_proof_bundle_sha256),
        "pass_id": handle.pass_id,
        "pass_ordinal": handle.pass_ordinal,
        "revision_receipt_sha256": handle.revision_receipt_sha256,
        "source_revision_sha256": handle.source_revision_sha256,
    }


def validate_pass_observation_handle(
    handle: ValidatedPassObservationHandle,
    graph: ValidatedAcquisitionGraphHandle,
    runtime_manifest: ValidatedRawArtifactHandle,
    execution_attestation: ValidatedRawArtifactHandle,
    *,
    owner_bundle_sha256: str,
) -> None:
    if type(handle) is not ValidatedPassObservationHandle:
        raise CorpusFormatError("unresolved nested pass observation handle is a hard reject")
    validate_acquisition_graph_handle(graph)
    validate_raw_artifact_handle(
        runtime_manifest, expected_role="transitive_runtime_input_manifest"
    )
    validate_raw_artifact_handle(
        execution_attestation,
        expected_role="post_acquisition_execution_attestation",
    )
    require_handle_integrity(
        handle_type="nested pass observation",
        raw=handle.raw,
        payload=handle.payload,
        artifact_sha256=handle.artifact_sha256,
        canonical_size=handle.canonical_size,
        domain=PASS_OBSERVATION_DOMAIN,
        maximum_bytes=_PASS_PROOF_MAX_BYTES,
        bindings=pass_observation_handle_bindings(handle),
        seal=handle._seal,
    )
    require_exact_keys(
        handle.payload,
        {
            "acquisition_artifact_graph_sha256",
            "acquisition_execution_attestation_sha256",
            "acquisition_preflight_attestation_sha256",
            "attempt_id",
            "authority_proof_sha256",
            "custody_contract_sha256",
            "exact_six_ordered_result_slots",
            "ordered_source_roster_sha256",
            "receipt_commitment_envelope_sha256",
            "revision_receipt_sha256",
            "source_contract_sha256",
            "source_policy_sha256",
            "source_revision_sha256",
            "transitive_runtime_input_manifest_sha256",
        },
        source="nested pass observation",
    )
    authority = prerequisite_by_role(graph, "authority_proof_bundle")
    preflight = prerequisite_by_role(graph, "pre_acquisition_attestation")
    static_bindings = resolve_static_binding_set(
        authority=authority,
        runtime_manifest=runtime_manifest,
    )
    if (
        runtime_manifest.authority_grant_id != graph.authority_grant_id
        or runtime_manifest.attempt_id != graph.attempt_id
        or execution_attestation.authority_grant_id != graph.authority_grant_id
        or execution_attestation.attempt_id != graph.attempt_id
    ):
        raise CorpusFormatError("pass runtime or execution attempt binding mismatch")
    if runtime_manifest.runtime_distribution is None:
        raise CorpusFormatError("pass runtime distribution handle is missing")
    expected_runtime_bindings = runtime_distribution_manifest_bindings(
        runtime_manifest.runtime_distribution
    )
    expected_execution_bindings = {
        "acquisition_artifact_graph_sha256": graph.artifact_sha256,
        "acquisition_preflight_attestation_sha256": preflight.artifact_sha256,
        "authority_proof_sha256": authority.artifact_sha256,
        "receipt_commitment_envelope_sha256": (graph.receipt_commitment_envelope_sha256),
        "revision_receipt_sha256": graph.revision_receipt_sha256,
        "source_revision_sha256": graph.source_revision_sha256,
        "transitive_runtime_input_manifest_sha256": runtime_manifest.artifact_sha256,
    }
    if (
        runtime_manifest.payload["parent_bindings"] != expected_runtime_bindings
        or execution_attestation.payload["parent_bindings"] != expected_execution_bindings
    ):
        raise CorpusFormatError("pass runtime or execution parent binding mismatch")
    expected = {
        "acquisition_artifact_graph_sha256": graph.artifact_sha256,
        "acquisition_execution_attestation_sha256": execution_attestation.artifact_sha256,
        "acquisition_preflight_attestation_sha256": preflight.artifact_sha256,
        "attempt_id": graph.attempt_id,
        "authority_proof_sha256": authority.artifact_sha256,
        "custody_contract_sha256": static_bindings.custody_contract_sha256,
        "ordered_source_roster_sha256": static_bindings.ordered_source_roster_sha256,
        "receipt_commitment_envelope_sha256": (graph.receipt_commitment_envelope_sha256),
        "revision_receipt_sha256": graph.revision_receipt_sha256,
        "source_contract_sha256": static_bindings.source_contract_sha256,
        "source_policy_sha256": static_bindings.source_policy_sha256,
        "source_revision_sha256": graph.source_revision_sha256,
        "transitive_runtime_input_manifest_sha256": runtime_manifest.artifact_sha256,
    }
    if any(handle.payload[key] != value for key, value in expected.items()):
        raise CorpusFormatError("nested pass observation resolved binding mismatch")
    if (
        handle.owner_typed_pass_proof_bundle_sha256 != owner_bundle_sha256
        or handle.authority_grant_id != graph.authority_grant_id
        or handle.attempt_id != graph.attempt_id
        or handle.acquisition_artifact_graph_sha256 != graph.artifact_sha256
        or handle.revision_receipt_sha256 != graph.revision_receipt_sha256
        or handle.source_revision_sha256 != graph.source_revision_sha256
    ):
        raise CorpusFormatError("nested pass observation owner or handle mismatch")
    results = handle.payload["exact_six_ordered_result_slots"]
    if not isinstance(results, list):
        raise CorpusFormatError("nested pass observation result vector is not a list")
    validate_pass_result_vector(results)


def pass_proof_handle_bindings(handle: ValidatedPassProofHandle) -> dict[str, Any]:
    return {
        "acquisition_artifact_graph_sha256": (handle.acquisition_artifact_graph_sha256),
        "attempt_id": handle.attempt_id,
        "authority_grant_id": handle.authority_grant_id,
        "completeness_applicability": handle.completeness_applicability,
        "custody_contract_sha256": handle.custody_contract_sha256,
        "execution_attestation_sha256": handle.execution_attestation.artifact_sha256,
        "nullable_completeness_attestation_sha256": (
            handle.nullable_completeness_attestation_sha256
        ),
        "pass_id": handle.pass_id,
        "pass_observation_payload_sha256": handle.pass_observation.artifact_sha256,
        "pass_ordinal": handle.pass_ordinal,
        "runtime_manifest_sha256": handle.runtime_manifest.artifact_sha256,
        "seal_sha256": handle.seal_sha256,
        "source_policy_sha256": handle.source_policy_sha256,
    }


def validate_pass_proof_handle(
    handle: ValidatedPassProofHandle,
    graph: ValidatedAcquisitionGraphHandle,
    *,
    expected_ordinal: int,
) -> None:
    if type(handle) is not ValidatedPassProofHandle:
        raise CorpusFormatError("unresolved pass proof handle is a hard reject")
    validate_acquisition_graph_handle(graph)
    require_handle_integrity(
        handle_type="typed pass proof bundle",
        raw=handle.raw,
        payload=handle.payload,
        artifact_sha256=handle.artifact_sha256,
        canonical_size=handle.canonical_size,
        domain=PASS_PROOF_DOMAIN,
        maximum_bytes=_PASS_PROOF_MAX_BYTES,
        bindings=pass_proof_handle_bindings(handle),
        seal=handle._seal,
    )
    require_exact_keys(
        handle.payload,
        {
            "bundle_version",
            "detached_pass_proof_envelope",
            "pass_observation_payload",
        },
        source="typed pass proof bundle",
    )
    if handle.payload["bundle_version"] != "v1":
        raise CorpusFormatError("typed pass proof bundle version mismatch")
    envelope = handle.payload["detached_pass_proof_envelope"]
    observation_payload = handle.payload["pass_observation_payload"]
    if not isinstance(envelope, dict) or not isinstance(observation_payload, dict):
        raise CorpusFormatError("typed pass proof nested role shape mismatch")
    require_exact_keys(
        envelope,
        {"proof_core", "seal_sha256"},
        source="detached pass proof envelope",
    )
    proof_core = envelope["proof_core"]
    if not isinstance(proof_core, dict):
        raise CorpusFormatError("detached pass proof core is not an object")
    require_exact_keys(
        proof_core,
        {
            "attempt_id",
            "authority_proof_sha256",
            "completeness_applicability",
            "nullable_completeness_attestation_sha256",
            "pass_observation_payload_sha256",
            "pass_ordinal",
            "pre_authorized_pass_id",
        },
        source="detached pass proof core",
    )
    if handle.pass_ordinal != expected_ordinal:
        raise CorpusFormatError("pass proof tuple position or ordinal mismatch")
    derived = derive_grant_identifiers(handle.authority_grant_id)
    expected_pass_id = derived[f"pre_authorized_pass_id_ordinal_{expected_ordinal}"]
    authority = prerequisite_by_role(graph, "authority_proof_bundle")
    expected_core = {
        "attempt_id": graph.attempt_id,
        "authority_proof_sha256": authority.artifact_sha256,
        "completeness_applicability": handle.completeness_applicability,
        "nullable_completeness_attestation_sha256": (
            handle.nullable_completeness_attestation_sha256
        ),
        "pass_observation_payload_sha256": handle.pass_observation.artifact_sha256,
        "pass_ordinal": expected_ordinal,
        "pre_authorized_pass_id": expected_pass_id,
    }
    if proof_core != expected_core:
        raise CorpusFormatError("detached pass proof core binding mismatch")
    expected_seal_sha256 = tagged_digest(PASS_SEAL_DOMAIN, proof_core)
    if envelope["seal_sha256"] != expected_seal_sha256:
        raise CorpusFormatError("deterministic pass seal recomputation mismatch")
    if (
        handle.seal_sha256 != expected_seal_sha256
        or handle.pass_id != expected_pass_id
        or handle.authority_grant_id != graph.authority_grant_id
        or handle.attempt_id != graph.attempt_id
        or handle.acquisition_artifact_graph_sha256 != graph.artifact_sha256
        or handle.revision_receipt_sha256 != graph.revision_receipt_sha256
        or handle.source_revision_sha256 != graph.source_revision_sha256
    ):
        raise CorpusFormatError("typed pass proof handle binding mismatch")
    nested_raw = canonical_payload(observation_payload)
    if nested_raw != handle.pass_observation.raw:
        raise CorpusFormatError("pass proof retained raw omits or changes nested observation")
    validate_pass_observation_handle(
        handle.pass_observation,
        graph,
        handle.runtime_manifest,
        handle.execution_attestation,
        owner_bundle_sha256=handle.artifact_sha256,
    )
    if handle.pass_observation.pass_id != handle.pass_id:
        raise CorpusFormatError("pass proof to nested observation pass binding mismatch")
    nullable_digest = handle.nullable_completeness_attestation_sha256
    if nullable_digest is not None:
        require_sha256(nullable_digest, source="pass proof completeness reference")


def resolve_pass_proof_handle(
    raw: bytes,
    *,
    graph: ValidatedAcquisitionGraphHandle,
    runtime_manifest: ValidatedRawArtifactHandle,
    execution_attestation: ValidatedRawArtifactHandle,
) -> ValidatedPassProofHandle:
    if len(raw) > _PASS_PROOF_MAX_BYTES:
        raise CorpusFormatError("typed pass proof bundle raw resource exceeds bound")
    validate_acquisition_graph_handle(graph)
    validate_raw_artifact_handle(
        runtime_manifest, expected_role="transitive_runtime_input_manifest"
    )
    validate_raw_artifact_handle(
        execution_attestation,
        expected_role="post_acquisition_execution_attestation",
    )
    authority = prerequisite_by_role(graph, "authority_proof_bundle")
    static_bindings = resolve_static_binding_set(
        authority=authority,
        runtime_manifest=runtime_manifest,
    )
    source_policy_sha256 = static_bindings.source_policy_sha256
    custody_contract_sha256 = static_bindings.custody_contract_sha256
    payload = decode_canonical(raw, source="resolved typed pass proof bundle")
    if not isinstance(payload, dict):
        raise CorpusFormatError("typed pass proof bundle is not an object")
    require_exact_keys(
        payload,
        {
            "bundle_version",
            "detached_pass_proof_envelope",
            "pass_observation_payload",
        },
        source="typed pass proof bundle",
    )
    envelope = payload["detached_pass_proof_envelope"]
    observation_payload = payload["pass_observation_payload"]
    if not isinstance(envelope, dict) or not isinstance(observation_payload, dict):
        raise CorpusFormatError("typed pass proof nested role shape mismatch")
    require_exact_keys(
        envelope,
        {"proof_core", "seal_sha256"},
        source="detached pass proof envelope",
    )
    proof_core = envelope["proof_core"]
    if not isinstance(proof_core, dict):
        raise CorpusFormatError("detached pass proof core is not an object")
    artifact_sha256 = tagged_digest(PASS_PROOF_DOMAIN, payload)
    observation_raw = canonical_payload(observation_payload)
    observation_sha256 = tagged_digest(PASS_OBSERVATION_DOMAIN, observation_payload)
    pass_ordinal = proof_core.get("pass_ordinal")
    pass_id = proof_core.get("pre_authorized_pass_id")
    if pass_ordinal not in (1, 2) or not isinstance(pass_id, str):
        raise CorpusFormatError("detached pass proof identity shape mismatch")
    observation_bindings = {
        "acquisition_artifact_graph_sha256": graph.artifact_sha256,
        "attempt_id": graph.attempt_id,
        "authority_grant_id": graph.authority_grant_id,
        "owner_typed_pass_proof_bundle_sha256": artifact_sha256,
        "pass_id": pass_id,
        "pass_ordinal": pass_ordinal,
        "revision_receipt_sha256": graph.revision_receipt_sha256,
        "source_revision_sha256": graph.source_revision_sha256,
    }
    observation = ValidatedPassObservationHandle(
        raw=observation_raw,
        payload=observation_payload,
        artifact_sha256=observation_sha256,
        canonical_size=len(observation_raw),
        authority_grant_id=graph.authority_grant_id,
        attempt_id=graph.attempt_id,
        revision_receipt_sha256=graph.revision_receipt_sha256,
        source_revision_sha256=graph.source_revision_sha256,
        acquisition_artifact_graph_sha256=graph.artifact_sha256,
        pass_id=pass_id,
        pass_ordinal=pass_ordinal,
        owner_typed_pass_proof_bundle_sha256=artifact_sha256,
        _seal=handle_seal(
            "nested pass observation",
            raw=observation_raw,
            artifact_sha256=observation_sha256,
            canonical_size=len(observation_raw),
            bindings=observation_bindings,
        ),
    )
    nullable_digest = proof_core.get("nullable_completeness_attestation_sha256")
    completeness_applicability = proof_core.get("completeness_applicability")
    seal_sha256 = envelope.get("seal_sha256")
    if not isinstance(completeness_applicability, str) or not isinstance(seal_sha256, str):
        raise CorpusFormatError("detached pass proof control shape mismatch")
    bindings = {
        "acquisition_artifact_graph_sha256": graph.artifact_sha256,
        "attempt_id": graph.attempt_id,
        "authority_grant_id": graph.authority_grant_id,
        "completeness_applicability": completeness_applicability,
        "custody_contract_sha256": custody_contract_sha256,
        "execution_attestation_sha256": execution_attestation.artifact_sha256,
        "nullable_completeness_attestation_sha256": nullable_digest,
        "pass_id": pass_id,
        "pass_observation_payload_sha256": observation_sha256,
        "pass_ordinal": pass_ordinal,
        "runtime_manifest_sha256": runtime_manifest.artifact_sha256,
        "seal_sha256": seal_sha256,
        "source_policy_sha256": source_policy_sha256,
    }
    handle = ValidatedPassProofHandle(
        raw=raw,
        payload=payload,
        artifact_sha256=artifact_sha256,
        canonical_size=len(raw),
        authority_grant_id=graph.authority_grant_id,
        attempt_id=graph.attempt_id,
        revision_receipt_sha256=graph.revision_receipt_sha256,
        source_revision_sha256=graph.source_revision_sha256,
        acquisition_artifact_graph_sha256=graph.artifact_sha256,
        pass_id=pass_id,
        pass_ordinal=pass_ordinal,
        pass_observation=observation,
        runtime_manifest=runtime_manifest,
        execution_attestation=execution_attestation,
        source_policy_sha256=source_policy_sha256,
        custody_contract_sha256=custody_contract_sha256,
        nullable_completeness_attestation_sha256=nullable_digest,
        completeness_applicability=completeness_applicability,
        seal_sha256=seal_sha256,
        _seal=handle_seal(
            "typed pass proof bundle",
            raw=raw,
            artifact_sha256=artifact_sha256,
            canonical_size=len(raw),
            bindings=bindings,
        ),
    )
    validate_pass_proof_handle(handle, graph, expected_ordinal=pass_ordinal)
    return handle


def completeness_handle_bindings(handle: ValidatedCompletenessHandle) -> dict[str, Any]:
    return {
        "acquisition_artifact_graph_sha256": (handle.acquisition_artifact_graph_sha256),
        "attempt_id": handle.attempt_id,
        "authority_grant_id": handle.authority_grant_id,
        "pass_id": handle.pass_id,
        "pass_ordinal": handle.pass_ordinal,
        "revision_receipt_sha256": handle.revision_receipt_sha256,
        "source_revision_sha256": handle.source_revision_sha256,
    }


def validate_completeness_handle(
    handle: ValidatedCompletenessHandle,
    graph: ValidatedAcquisitionGraphHandle,
    proof: ValidatedPassProofHandle,
    *,
    expected_ordinal: int,
) -> None:
    if type(handle) is not ValidatedCompletenessHandle:
        raise CorpusFormatError("unresolved completeness reference is a hard reject")
    validate_pass_proof_handle(proof, graph, expected_ordinal=expected_ordinal)
    require_handle_integrity(
        handle_type="completeness",
        raw=handle.raw,
        payload=handle.payload,
        artifact_sha256=handle.artifact_sha256,
        canonical_size=handle.canonical_size,
        domain=COMPLETENESS_DOMAIN,
        maximum_bytes=_COMPLETENESS_MAX_BYTES,
        bindings=completeness_handle_bindings(handle),
        seal=handle._seal,
    )
    require_exact_keys(
        handle.payload,
        {
            "ambiguous_count",
            "contract_sha256",
            "duplicate_count",
            "error_count",
            "extra_count",
            "missing_count",
            "ordered_source_roster_count",
            "ordered_source_roster_sha256",
            "processed_count",
            "processed_link_ids",
            "revision_receipt_sha256",
            "source_revision_sha256",
            "unreadable_count",
        },
        source="completeness",
    )
    expected = {
        "acquisition_artifact_graph_sha256": graph.artifact_sha256,
        "attempt_id": graph.attempt_id,
        "authority_grant_id": graph.authority_grant_id,
        "pass_id": proof.pass_id,
        "pass_ordinal": expected_ordinal,
        "revision_receipt_sha256": graph.revision_receipt_sha256,
        "source_revision_sha256": graph.source_revision_sha256,
    }
    if any(getattr(handle, key) != value for key, value in expected.items()):
        raise CorpusFormatError("completeness pass graph or parent binding mismatch")
    if (
        handle.payload["revision_receipt_sha256"] != graph.revision_receipt_sha256
        or handle.payload["source_revision_sha256"] != graph.source_revision_sha256
        or proof.nullable_completeness_attestation_sha256 != handle.artifact_sha256
    ):
        raise CorpusFormatError("completeness pass graph or parent binding mismatch")


def resolve_completeness_handle(
    raw: bytes,
    *,
    receipt: ValidatedRawArtifactHandle,
    envelope: ValidatedRawArtifactHandle,
    revision_set: ValidatedRawArtifactHandle,
    validators: dict[Path, Draft202012Validator],
    graph: ValidatedAcquisitionGraphHandle,
    proof: ValidatedPassProofHandle,
) -> ValidatedCompletenessHandle:
    if len(raw) > _COMPLETENESS_MAX_BYTES:
        raise CorpusFormatError("completeness raw resource exceeds bound")
    validate_pass_proof_handle(proof, graph, expected_ordinal=proof.pass_ordinal)
    payload = decode_canonical(raw, source="resolved completeness payload")
    if not isinstance(payload, dict):
        raise CorpusFormatError("completeness payload is not an object")
    try:
        validators[COMPLETENESS_SCHEMA_PATH].validate(payload)
    except ValidationError as error:
        raise CorpusFormatError("completeness payload schema mismatch") from error
    validate_parent_handle_chain(receipt, envelope, revision_set)
    if (
        graph.revision_receipt_sha256 != receipt.artifact_sha256
        or graph.receipt_commitment_envelope_sha256 != envelope.artifact_sha256
        or graph.source_revision_sha256 != revision_set.artifact_sha256
        or payload["revision_receipt_sha256"] != receipt.artifact_sha256
        or payload["source_revision_sha256"] != revision_set.artifact_sha256
    ):
        raise CorpusFormatError("completeness graph parent binding mismatch")
    artifact_sha256 = tagged_digest(COMPLETENESS_DOMAIN, payload)
    if proof.nullable_completeness_attestation_sha256 != artifact_sha256:
        raise CorpusFormatError("completeness pass or graph binding mismatch")
    bindings = {
        "acquisition_artifact_graph_sha256": graph.artifact_sha256,
        "attempt_id": graph.attempt_id,
        "authority_grant_id": graph.authority_grant_id,
        "pass_id": proof.pass_id,
        "pass_ordinal": proof.pass_ordinal,
        "revision_receipt_sha256": receipt.artifact_sha256,
        "source_revision_sha256": revision_set.artifact_sha256,
    }
    handle = ValidatedCompletenessHandle(
        raw=raw,
        payload=payload,
        artifact_sha256=artifact_sha256,
        canonical_size=len(raw),
        authority_grant_id=graph.authority_grant_id,
        attempt_id=graph.attempt_id,
        revision_receipt_sha256=receipt.artifact_sha256,
        source_revision_sha256=revision_set.artifact_sha256,
        pass_id=proof.pass_id,
        pass_ordinal=proof.pass_ordinal,
        acquisition_artifact_graph_sha256=graph.artifact_sha256,
        _seal=handle_seal(
            "completeness",
            raw=raw,
            artifact_sha256=artifact_sha256,
            canonical_size=len(raw),
            bindings=bindings,
        ),
    )
    validate_completeness_handle(handle, graph, proof, expected_ordinal=proof.pass_ordinal)
    return handle


def derive_completeness_reference_state(
    applicability: str,
    graph: ValidatedAcquisitionGraphHandle,
    proofs: tuple[ValidatedPassProofHandle, ValidatedPassProofHandle],
    handles: tuple[ValidatedCompletenessHandle | None, ValidatedCompletenessHandle | None],
) -> str:
    if applicability != "applicable_parent_zero_count_payload_permitted":
        if handles != (None, None) or any(
            proof.nullable_completeness_attestation_sha256 is not None for proof in proofs
        ):
            raise CorpusFormatError("extraneous completeness handle is a hard reject")
        return "both_null_payload_forbidden"
    nonnull: list[ValidatedCompletenessHandle] = []
    for expected_ordinal, (proof, handle) in enumerate(zip(proofs, handles, strict=True), start=1):
        if handle is None:
            if proof.nullable_completeness_attestation_sha256 is not None:
                raise CorpusFormatError("unresolved completeness reference is a hard reject")
            continue
        validate_completeness_handle(
            handle,
            graph,
            proof,
            expected_ordinal=expected_ordinal,
        )
        nonnull.append(handle)
    if not nonnull:
        return "zero_valid_nonnull"
    if len(nonnull) == 1:
        return "one_valid_nonnull"
    if nonnull[0].pass_ordinal != 1 or nonnull[1].pass_ordinal != 2:
        raise CorpusFormatError("completeness tuple position or ordinal mismatch")
    if (
        nonnull[0].raw != nonnull[1].raw
        or nonnull[0].artifact_sha256 != nonnull[1].artifact_sha256
        or nonnull[0].authority_grant_id != nonnull[1].authority_grant_id
        or nonnull[0].attempt_id != nonnull[1].attempt_id
        or nonnull[0].revision_receipt_sha256 != nonnull[1].revision_receipt_sha256
        or nonnull[0].source_revision_sha256 != nonnull[1].source_revision_sha256
        or nonnull[0].acquisition_artifact_graph_sha256
        != nonnull[1].acquisition_artifact_graph_sha256
    ):
        raise CorpusFormatError("unequal completeness handles are a hard reject")
    return "two_valid_nonnull_equal"


def validate_pass_result_vector(results: list[dict[str, Any]]) -> None:
    if len(results) != 6:
        raise CorpusFormatError("pass result vector is not exact six")
    task_keys = set(PASS_SLOT_TASKS[0])
    for result, expected in zip(results, PASS_SLOT_TASKS, strict=True):
        if set(result) != PASS_RESULT_KEYS:
            raise CorpusFormatError("pass result has extra missing or forbidden channel")
        if {key: result[key] for key in task_keys} != expected:
            raise CorpusFormatError("pass result vector context or order mismatch")
        outcome = result["outcome"]
        if outcome not in VALID_PASS_OUTCOMES:
            raise CorpusFormatError("invalid pass outcome")
        locator = result["source_local_locator"]
        if outcome == "exact_one_candidate":
            if not isinstance(locator, dict) or set(locator) != {
                "identifier",
                "identifier_namespace",
            }:
                raise CorpusFormatError("invalid candidate locator shape")
            if locator["identifier_namespace"] != "official_record_id" or not isinstance(
                locator["identifier"], str
            ):
                raise CorpusFormatError("invalid candidate locator namespace or type")
            if OFFICIAL_RECORD_ID_RE.fullmatch(locator["identifier"]) is None:
                raise CorpusFormatError("invalid candidate locator grammar")
        elif locator is not None:
            raise CorpusFormatError("noncandidate locator must be null")


def evaluate_terminal_rows(
    graph: ValidatedAcquisitionGraphHandle,
    proofs: tuple[ValidatedPassProofHandle, ValidatedPassProofHandle],
    *,
    completeness_handles: tuple[
        ValidatedCompletenessHandle | None,
        ValidatedCompletenessHandle | None,
    ] = (None, None),
) -> list[str]:
    if type(graph) is not ValidatedAcquisitionGraphHandle:
        raise CorpusFormatError("unresolved acquisition graph handle is a hard reject")
    if type(proofs) is not tuple or len(proofs) != 2:
        raise CorpusFormatError("pass proof handle tuple is not exact two")
    validate_acquisition_graph_handle(graph)
    for expected_ordinal, proof in enumerate(proofs, start=1):
        validate_pass_proof_handle(proof, graph, expected_ordinal=expected_ordinal)
    first_proof, second_proof = proofs
    common_fields = (
        "authority_grant_id",
        "attempt_id",
        "revision_receipt_sha256",
        "source_revision_sha256",
        "acquisition_artifact_graph_sha256",
        "source_policy_sha256",
        "custody_contract_sha256",
    )
    if any(getattr(first_proof, key) != getattr(second_proof, key) for key in common_fields):
        raise CorpusFormatError("pass proof common scientific binding mismatch")
    if (
        first_proof.pass_id == second_proof.pass_id
        or first_proof.seal_sha256 == second_proof.seal_sha256
    ):
        raise CorpusFormatError("pass proof identity or seal distinctness mismatch")
    first = first_proof.pass_observation.payload["exact_six_ordered_result_slots"]
    second = second_proof.pass_observation.payload["exact_six_ordered_result_slots"]
    applicability = derive_completeness_applicability(first, second)
    if any(proof.completeness_applicability != applicability for proof in proofs):
        raise CorpusFormatError("pass proof completeness applicability mismatch")
    reference_state = derive_completeness_reference_state(
        applicability,
        graph,
        proofs,
        completeness_handles,
    )
    completeness_no_link_basis = reference_state == "two_valid_nonnull_equal"
    states: list[str] = []
    for left, right in zip(first, second, strict=True):
        left_outcome = left["outcome"]
        right_outcome = right["outcome"]
        if left_outcome == right_outcome == "exact_one_candidate":
            states.append(
                "source_reported_link"
                if left.get("source_local_locator") == right.get("source_local_locator")
                else "unresolved"
            )
        elif left_outcome == right_outcome == "explicit_source_rejection":
            states.append("no_link")
        elif left_outcome == right_outcome == "row_absent":
            states.append("no_link" if completeness_no_link_basis else "unresolved")
        else:
            states.append("unresolved")
    return states


def require_completeness_parent_digest_bindings(
    receipt: dict[str, Any],
    envelope: dict[str, Any],
    revision_set: dict[str, Any],
    attestations: Sequence[dict[str, Any]],
) -> None:
    receipt_digest = tagged_digest(RECEIPT_DOMAIN, receipt)
    revision_digest = tagged_digest(REVISION_SET_DOMAIN, revision_set)
    if envelope["revision_receipt_sha256"] != receipt_digest:
        raise CorpusFormatError("receipt envelope digest mismatch")
    for attestation in attestations:
        if (
            attestation["revision_receipt_sha256"] != receipt_digest
            or attestation["source_revision_sha256"] != revision_digest
        ):
            raise CorpusFormatError("completeness parent digest mismatch")


class SourceReportedLinkEvidencePrerequisiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_contract_bytes = SOURCE_CONTRACT_PATH.read_bytes()
        self.source_contract = decode_json(self.source_contract_bytes)
        self.custody_bytes = CUSTODY_CONTRACT_PATH.read_bytes()
        self.custody = decode_json(self.custody_bytes)
        self.schemas = {
            path: decode_json(path.read_bytes(), source=str(path)) for path in SCHEMA_PATHS
        }
        self.validators = {
            path: Draft202012Validator(schema, format_checker=FormatChecker())
            for path, schema in self.schemas.items()
        }

    def test_fixed_ed25519_authority_and_review_vectors_verify_exact_framing(self) -> None:
        blueprints = self.custody["future_protocol_prerequisite_blueprints"]
        authority_profile = blueprints["authority_proof_bundle"]["detached_signature_envelope"]
        review_profile = blueprints["internal_retention_review_proof_bundle"][
            "detached_review_signature_envelope"
        ]
        vectors = (
            (
                authority_profile,
                "indusbench:source-reported-link:authority-signed-payload:v1",
                "signed_payload",
            ),
            (
                review_profile,
                "indusbench:source-reported-link:retention-review-payload:v1",
                "review_payload",
            ),
        )
        node_verifier = """
const crypto = require('node:crypto');
const raw = Buffer.from(process.argv[1], 'hex');
const spki = Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), raw]);
const key = crypto.createPublicKey({key: spki, format: 'der', type: 'spki'});
const message = Buffer.from(process.argv[2], 'base64');
const signature = Buffer.from(process.argv[3], 'base64url');
const mutated = Buffer.from(signature);
mutated[0] ^= 1;
process.exit(crypto.verify(null, message, key, signature) &&
  !crypto.verify(null, message, key, mutated) ? 0 : 1);
"""
        for profile, domain, payload_key in vectors:
            vector = profile["fixed_verification_vector"]
            context = dict(profile["constant_values"])
            context["key_id"] = vector["key_id"]
            context["public_key_sha256"] = vector["public_key_sha256"]
            self.assertEqual(set(profile["signature_context_fields_exact"]), set(context))
            message = (
                domain.encode()
                + b"\0"
                + canonical_payload(
                    {
                        payload_key: vector[payload_key],
                        "signature_context": context,
                    }
                )
            )
            self.assertEqual(vector["signed_message_sha256"], hashlib.sha256(message).hexdigest())
            public_key = bytes.fromhex(vector["external_public_key_hex"])
            self.assertEqual(32, len(public_key))
            self.assertEqual(
                vector["public_key_sha256"],
                "sha256:" + hashlib.sha256(public_key).hexdigest(),
            )
            self.assertEqual(
                vector["key_id"],
                "ed25519-sha256-v1:" + vector["public_key_sha256"].removeprefix("sha256:"),
            )
            signature_text = vector["signature_base64url"]
            signature = base64.urlsafe_b64decode(signature_text + "==")
            self.assertEqual(64, len(signature))
            self.assertEqual(
                signature_text,
                base64.urlsafe_b64encode(signature).decode().rstrip("="),
            )
            subprocess.run(
                [
                    "node",
                    "-e",
                    node_verifier,
                    vector["external_public_key_hex"],
                    base64.b64encode(message).decode(),
                    signature_text,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

    def test_static_binding_resolver_recomputes_files_and_rejects_substitution(self) -> None:
        grant_id = "grant-v1:000102030405060708090a0b0c0d0e0f"
        attempt_id = derive_grant_identifiers(grant_id)["attempt_id"]

        def control_payload(
            role: str,
            bindings: dict[str, str],
            distribution_handle: ValidatedRuntimeDistributionHandle | None = None,
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "artifact_role": role,
                "artifact_state": _CONTROL_ARTIFACT_STATE_BY_ROLE[role],
                "artifact_version": "v1",
                "attempt_id": attempt_id,
                "authority_grant_id": grant_id,
                "parent_bindings": bindings,
            }
            if role == "transitive_runtime_input_manifest":
                if distribution_handle is None:
                    raise AssertionError("runtime manifest needs a distribution")
                payload["members"] = runtime_distribution_manifest_members(distribution_handle)
            return payload

        distribution = resolve_runtime_distribution_handle(RUNTIME_DISTRIBUTION_VECTOR)
        runtime_bindings = runtime_distribution_manifest_bindings(distribution)
        runtime = resolve_control_artifact_handle(
            canonical_payload(
                control_payload(
                    "transitive_runtime_input_manifest",
                    runtime_bindings,
                    distribution,
                )
            ),
            role="transitive_runtime_input_manifest",
            expected_parent_bindings=runtime_bindings,
            runtime_distribution=distribution,
        )
        self.assertEqual(
            runtime_distribution_manifest_members(distribution),
            runtime.payload["members"],
        )
        for field_name, substitute in {
            "artifact_id": "authorized-runtime-distribution-v2",
            "path": "runtime/substitute.bin",
            "sha256": "sha256:" + "0" * 64,
            "size": distribution.size + 1,
        }.items():
            tampered_manifest = copy.deepcopy(runtime.payload)
            tampered_manifest["members"][0][field_name] = substitute
            with (
                self.subTest(manifest_member_field=field_name),
                self.assertRaises(CorpusFormatError),
            ):
                resolve_control_artifact_handle(
                    canonical_payload(tampered_manifest),
                    role="transitive_runtime_input_manifest",
                    expected_parent_bindings=runtime_bindings,
                    runtime_distribution=distribution,
                )
        for members in ([], runtime.payload["members"] * 2):
            wrong_cardinality = copy.deepcopy(runtime.payload)
            wrong_cardinality["members"] = members
            with self.assertRaises(CorpusFormatError):
                resolve_control_artifact_handle(
                    canonical_payload(wrong_cardinality),
                    role="transitive_runtime_input_manifest",
                    expected_parent_bindings=runtime_bindings,
                    runtime_distribution=distribution,
                )
        bindings = recompute_authority_static_bindings(runtime)
        authority = resolve_control_artifact_handle(
            canonical_payload(control_payload("authority_proof_bundle", bindings)),
            role="authority_proof_bundle",
            expected_parent_bindings=bindings,
        )
        resolved = resolve_static_binding_set(authority=authority, runtime_manifest=runtime)
        self.assertEqual(bindings["source_policy_sha256"], resolved.source_policy_sha256)
        self.assertEqual(
            bindings["transitive_runtime_input_manifest_sha256"],
            resolved.transitive_runtime_input_manifest_sha256,
        )
        self.assertEqual(bindings, static_binding_set_payload(resolved))
        validate_static_binding_set(resolved)
        for field_name in bindings:
            with (
                self.subTest(tampered_static_binding=field_name),
                self.assertRaisesRegex(CorpusFormatError, "seal mismatch"),
            ):
                validate_static_binding_set(replace(resolved, **{field_name: "sha256:" + "0" * 64}))
        self.assertEqual(
            {
                "artifact_schema_set_sha256",
                "custody_contract_sha256",
                "ordered_source_roster_sha256",
                "runtime_distribution_sha256",
                "source_contract_sha256",
                "source_policy_sha256",
                "source_registry_sha256",
                "transitive_runtime_input_manifest_sha256",
            },
            set(bindings),
        )

        wrong_bindings = dict(bindings)
        wrong_bindings["source_policy_sha256"] = "sha256:" + "0" * 64
        wrong_authority = resolve_control_artifact_handle(
            canonical_payload(control_payload("authority_proof_bundle", wrong_bindings)),
            role="authority_proof_bundle",
            expected_parent_bindings=wrong_bindings,
        )
        with self.assertRaisesRegex(CorpusFormatError, "not authority bound"):
            resolve_static_binding_set(authority=wrong_authority, runtime_manifest=runtime)

        original_read_bytes = Path.read_bytes
        tamper_targets = (
            SOURCE_POLICY_PATH,
            SOURCE_CONTRACT_PATH,
            SOURCE_REGISTRY_PATH,
            CUSTODY_CONTRACT_PATH,
            RECEIPT_SCHEMA_PATH,
        )
        for tamper_target in tamper_targets:

            def tampered_read_bytes(path: Path, *, target: Path = tamper_target) -> bytes:
                raw = original_read_bytes(path)
                return raw + b" " if path == target else raw

            with (
                self.subTest(tampered_static_file=tamper_target.name),
                patch.object(Path, "read_bytes", new=tampered_read_bytes),
                self.assertRaises(CorpusFormatError),
            ):
                resolve_static_binding_set(authority=authority, runtime_manifest=runtime)

        with self.assertRaises(CorpusFormatError):
            resolve_static_binding_set(
                authority=authority,
                runtime_manifest=replace(runtime, raw=runtime.raw + b" "),
            )
        substitute_distribution = resolve_runtime_distribution_handle(
            RUNTIME_DISTRIBUTION_VECTOR + b"substitute\n"
        )
        substitute_bindings = runtime_distribution_manifest_bindings(substitute_distribution)
        substitute_manifest = resolve_control_artifact_handle(
            canonical_payload(
                control_payload(
                    "transitive_runtime_input_manifest",
                    substitute_bindings,
                    substitute_distribution,
                )
            ),
            role="transitive_runtime_input_manifest",
            expected_parent_bindings=substitute_bindings,
            runtime_distribution=substitute_distribution,
        )
        with self.assertRaisesRegex(CorpusFormatError, "not authority bound"):
            resolve_static_binding_set(authority=authority, runtime_manifest=substitute_manifest)
        with self.assertRaises(CorpusFormatError):
            resolve_static_binding_set(
                authority=authority,
                runtime_manifest=replace(runtime, runtime_distribution=substitute_distribution),
            )

    def test_source_access_status_reference_model_exact_lattice(self) -> None:
        success, _expanded, _rows, _crosswalk = _reference_policy()

        def resolve_prefix(prefix_count: int) -> ReferenceLedgerChain:
            return model_resolve_ledger_chain(
                model_build_ledger_generation_raws(
                    success[:prefix_count],
                    terminal_branch_disposition=(
                        "clean_evaluated_success" if prefix_count == 29 else None
                    ),
                )
            )

        expected_by_prefix = {
            0: "NONE",
            1: "NONE",
            2: "NONE",
            3: "NONE",
            4: "POSSIBLE_KNOWN",
            5: "POSSIBLE_DISPATCH_UNKNOWN",
            6: "POSSIBLE_BODY_UNKNOWN",
            7: "POSSIBLE_KNOWN",
            19: "POSSIBLE_KNOWN",
            20: "POSSIBLE_KNOWN",
            21: "CONFIRMED_COMPLETE",
            29: "CONFIRMED_COMPLETE",
        }
        for prefix_count, expected_status in expected_by_prefix.items():
            chain = resolve_prefix(prefix_count)
            with self.subTest(prefix_count=prefix_count):
                self.assertEqual(
                    expected_status,
                    model_derive_ledger_source_access_status(chain),
                )
        intent_payload = decode_canonical(
            resolve_prefix(5).generations[-1].raw,
            source="intent lattice fixture",
        )
        self.assertEqual(1, intent_payload["request_intent_count"])
        self.assertIsNone(intent_payload["confirmed_application_dispatch_count"])
        self.assertIsNone(intent_payload["complete_body_count"])
        dispatch_payload = decode_canonical(
            resolve_prefix(6).generations[-1].raw,
            source="dispatch lattice fixture",
        )
        self.assertEqual(1, dispatch_payload["confirmed_application_dispatch_count"])
        self.assertIsNone(dispatch_payload["complete_body_count"])
        core_payload = decode_canonical(
            resolve_prefix(20).generations[-1].raw,
            source="core graph lattice fixture",
        )
        self.assertEqual(
            (5, 5, 5, "POSSIBLE_KNOWN"),
            (
                core_payload["request_intent_count"],
                core_payload["confirmed_application_dispatch_count"],
                core_payload["complete_body_count"],
                core_payload["source_access_status"],
            ),
        )
        observed = {
            model_derive_ledger_source_access_status(resolve_prefix(prefix_count))
            for prefix_count in range(30)
        }
        self.assertEqual(
            set(
                self.custody["custody_lifecycle"]["source_access_status_derivation"][
                    "closed_values"
                ]
            ),
            observed,
        )
        valid = resolve_prefix(21)
        with self.assertRaisesRegex(CorpusFormatError, "mutated"):
            model_validate_ledger_chain(replace(valid, success_prefix_count=20))
        with self.assertRaisesRegex(CorpusFormatError, "ReferenceLedgerChain"):
            model_derive_ledger_source_access_status({})  # type: ignore[arg-type]
        self.assertIs(
            False,
            self.custody["executable_reference_model_status"][
                "RUNTIME_STRICT_VERIFIER_IMPLEMENTED"
            ],
        )

    def test_source_access_reference_model_exact_six_and_crosswalk(self) -> None:
        success, expanded, branch_rows, terminal_crosswalk = _reference_policy()
        rows = {row["branch_id"]: row for row in branch_rows}
        sequence_by_row = {
            "workspace_never_created_no_ledger": expanded[
                "workspace_never_created_without_ledger:0"
            ],
            "workspace_never_created_with_g0_ledger": expanded[
                "workspace_never_created_with_initial_ledger:1"
            ],
            "clean_reserved_prefix": expanded[
                "workspace_created_empty_before_acquisition_started:2"
            ],
            "clean_g0_orphan_adoption": expanded[
                "workspace_created_after_g0_before_g1_exact_empty_recovery_cleanup:2"
            ],
            "clean_preflight_prefix": expanded[
                "clean_operational_or_scientific_failure_after_workspace_ready:3"
            ],
            "clean_acquisition_started_prefix": expanded[
                "clean_operational_or_scientific_failure_after_workspace_ready:6"
            ],
            "clean_core_graph_prefix": expanded[
                "clean_operational_or_scientific_failure_after_workspace_ready:20"
            ],
            "clean_execution_attestation_prefix": success,
            "cleanup_uncertainty_reserved_prefix": expanded[
                "workspace_created_after_g0_before_g1_ambiguous_or_nonempty:1"
            ],
            "cleanup_uncertainty_preflight_prefix": expanded[
                "cleanup_uncertainty_after_workspace_ready:3"
            ],
            "cleanup_uncertainty_acquisition_started_prefix": expanded[
                "cleanup_uncertainty_after_workspace_ready:6"
            ],
            "cleanup_uncertainty_core_graph_prefix": expanded[
                "cleanup_uncertainty_after_workspace_ready:20"
            ],
            "cleanup_uncertainty_execution_attestation_prefix": expanded[
                "cleanup_uncertainty_after_workspace_ready:21"
            ],
            "scientific_candidate_memory_loss_before_durable_review": success,
            "review_approved_retention_committed": success,
            "review_denied": success,
            "review_failure": success,
            "candidate_lost_after_approval": success,
        }

        def ledger_for_row(row_id: str) -> ReferenceLedgerChain:
            checkpoint = _row_checkpoint(rows[row_id])
            terminal_candidates = tuple(
                branch_id
                for branch_id, sequence in expanded.items()
                if sequence_by_row[row_id] == sequence
                and any(
                    _terminal_pattern_matches(pattern, branch_id)
                    for pattern in terminal_crosswalk[row_id]
                )
            )
            if checkpoint == "W":
                terminal_id = None
            elif "clean_evaluated_success:29" in terminal_candidates:
                terminal_id = "clean_evaluated_success:29"
            elif len(terminal_candidates) == 1:
                terminal_id = terminal_candidates[0]
            else:
                raise AssertionError(
                    f"ambiguous fixture disposition for {row_id}: {terminal_candidates}"
                )
            terminal_disposition = (
                terminal_id.rsplit(":", maxsplit=1)[0] if terminal_id is not None else None
            )
            return model_resolve_ledger_chain(
                model_build_ledger_generation_raws(
                    sequence_by_row[row_id],
                    terminal_checkpoint_override=(
                        checkpoint if checkpoint in {"R", "P", "A", "C", "E"} else None
                    ),
                    terminal_branch_disposition=terminal_disposition,
                )
            )

        def registry(
            row_id: str,
            *,
            prefix_count: int | None = None,
        ) -> ReferenceRegistryChain:
            terminal_chain = ledger_for_row(row_id)
            raws = model_build_registry_generation_raws(
                row_id,
                terminal_ledger_chain=terminal_chain,
            )
            if prefix_count is not None:
                raws = raws[:prefix_count]
            observed_states = tuple(rows[row_id]["generation_states_exact"])[: len(raws)]
            terminal_present = _registry_terminal_index(observed_states) is not None
            return model_resolve_registry_chain(
                raws,
                terminal_ledger_chain_at_creation=(terminal_chain if terminal_present else None),
            )

        clean_chain = ledger_for_row("clean_execution_attestation_prefix")
        uncertainty_chain = ledger_for_row("cleanup_uncertainty_acquisition_started_prefix")
        clean_row = rows["clean_execution_attestation_prefix"]
        clean_terminal_index = tuple(clean_row["generation_states_exact"]).index(
            "TERMINAL_REGISTRY_DURABLE"
        )
        pre_l_registry = registry(
            "clean_execution_attestation_prefix",
            prefix_count=clean_terminal_index + 1,
        )
        post_l_registry = registry(
            "clean_execution_attestation_prefix",
            prefix_count=clean_terminal_index + 2,
        )
        handles = (
            model_resolve_source_access_evidence(
                registry_chain=registry("clean_reserved_prefix", prefix_count=1),
                ledger_root_snapshot=model_ledger_root_snapshot("complete_live_chain"),
            ),
            model_resolve_source_access_evidence(
                registry_chain=registry("cleanup_uncertainty_acquisition_started_prefix"),
                ledger_root_snapshot=model_ledger_root_snapshot(
                    "complete_live_chain",
                    model_root_children_from_chain(uncertainty_chain),
                ),
            ),
            model_resolve_source_access_evidence(
                registry_chain=pre_l_registry,
                ledger_root_snapshot=model_ledger_root_snapshot(
                    "terminal_copy_remaining",
                    model_root_children_from_chain(
                        clean_chain,
                        indices_in_enumeration_order=(20, 0, 5),
                    ),
                ),
            ),
            model_resolve_source_access_evidence(
                registry_chain=post_l_registry,
                ledger_root_snapshot=model_ledger_root_snapshot("verified_empty_after_L"),
            ),
            model_resolve_source_access_evidence(
                registry_chain=registry("workspace_never_created_no_ledger"),
                ledger_root_snapshot=model_ledger_root_snapshot(
                    "not_safely_opened_no_valid_generation_created"
                ),
            ),
            model_resolve_source_access_evidence(
                registry_chain=registry("workspace_never_created_with_g0_ledger"),
                ledger_root_snapshot=model_ledger_root_snapshot("verified_empty_after_L"),
            ),
        )
        expected_selectors = {
            "pre_terminal_copy_live",
            "terminal_retained_uncertainty",
            "terminal_copy_pre_L_removal_recovery",
            "post_L_workspace_created",
            "WNC_no_ledger_terminal",
            "post_L_WNC_g0",
        }
        self.assertEqual(expected_selectors, {handle.selector for handle in handles})
        self.assertEqual(
            tuple(clean_chain.generations[index].generation_name for index in (0, 5, 20)),
            handles[2].normalized_remaining_generation_names,
        )
        self.assertEqual(
            [
                "NONE",
                "POSSIBLE_BODY_UNKNOWN",
                "CONFIRMED_COMPLETE",
                "CONFIRMED_COMPLETE",
                "NONE",
                "NONE",
            ],
            [model_derive_source_access_status(handle) for handle in handles],
        )
        self.assertEqual(
            "TERMINAL_NO_LEDGER_NO_MUTATION_USE_DURABLE_W_COPY_ONLY",
            handles[4].recovery_action,
        )
        with self.assertRaisesRegex(CorpusFormatError, "unsafe"):
            model_resolve_source_access_evidence(
                registry_chain=registry("workspace_never_created_no_ledger"),
                ledger_root_snapshot=model_ledger_root_snapshot("verified_empty_after_L"),
            )

        for row in branch_rows:
            row_id = row["branch_id"]
            chain = ledger_for_row(row_id)
            registry_chain = registry(row_id)
            profile = row["terminal_copy_profile_exact"]
            if profile == "WORKSPACE_NEVER_CREATED_NO_LEDGER":
                root = model_ledger_root_snapshot("not_safely_opened_no_valid_generation_created")
            elif profile == "WORKSPACE_CREATED_LEDGER_RETAINED_UNCERTAINTY":
                root = model_ledger_root_snapshot(
                    "complete_live_chain",
                    model_root_children_from_chain(chain),
                )
            else:
                root = model_ledger_root_snapshot("verified_empty_after_L")
            evidence = model_resolve_source_access_evidence(
                registry_chain=registry_chain,
                ledger_root_snapshot=root,
            )
            with self.subTest(registry_branch=row_id):
                self.assertIn(evidence.selector, expected_selectors)
                self.assertIn(
                    model_derive_source_access_status(evidence),
                    set(
                        self.custody["custody_lifecycle"]["source_access_status_derivation"][
                            "closed_values"
                        ]
                    ),
                )

        ahead_cases = (
            ("clean_preflight_prefix", 2, "NONE"),
            ("clean_acquisition_started_prefix", 3, "POSSIBLE_KNOWN"),
            ("clean_core_graph_prefix", 19, "POSSIBLE_KNOWN"),
            ("clean_execution_attestation_prefix", 20, "POSSIBLE_KNOWN"),
            ("clean_execution_attestation_prefix", 21, "CONFIRMED_COMPLETE"),
        )
        checkpoint_state = {
            "clean_preflight_prefix": "PREFLIGHT_BOUND_DURABLE",
            "clean_acquisition_started_prefix": "ACQUISITION_STARTED_DURABLE",
            "clean_core_graph_prefix": "ACQUISITION_CORE_GRAPH_BOUND_DURABLE",
            "clean_execution_attestation_prefix": "EXECUTION_ATTESTATION_BOUND_DURABLE",
        }
        for row_id, ledger_prefix_count, expected_status in ahead_cases:
            checkpoint_index = tuple(rows[row_id]["generation_states_exact"]).index(
                checkpoint_state[row_id]
            )
            live = model_resolve_ledger_chain(
                model_build_ledger_generation_raws(success[:ledger_prefix_count])
            )
            evidence = model_resolve_source_access_evidence(
                registry_chain=registry(row_id, prefix_count=checkpoint_index + 1),
                ledger_root_snapshot=model_ledger_root_snapshot(
                    "complete_live_chain",
                    model_root_children_from_chain(live),
                ),
            )
            with self.subTest(
                checkpoint=row_id,
                ledger_prefix_count=ledger_prefix_count,
            ):
                self.assertEqual(
                    expected_status,
                    model_derive_source_access_status(evidence),
                )
                self.assertEqual(
                    (
                        "TERMINALIZE_CONTROL_ONLY_NO_RECONSTRUCTION_OR_SOURCE_RETRY"
                        if ledger_prefix_count in {2, 3, 19, 20}
                        else "REQUIRE_EXTERNAL_SAME_PROCESS_PROOF_BEFORE_ANY_CONTINUATION"
                    ),
                    evidence.recovery_action,
                )

        pending_uncertainty = model_resolve_source_access_evidence(
            registry_chain=registry(
                "cleanup_uncertainty_acquisition_started_prefix",
                prefix_count=3,
            ),
            ledger_root_snapshot=model_ledger_root_snapshot(
                "complete_live_chain",
                model_root_children_from_chain(uncertainty_chain),
            ),
        )
        self.assertEqual("pre_terminal_copy_live", pending_uncertainty.selector)
        self.assertEqual(
            "T_PENDING_RETAINED_UNCERTAINTY",
            pending_uncertainty.submode,
        )
        self.assertEqual(
            "APPEND_T_COPY_KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK",
            pending_uncertainty.recovery_action,
        )
        clean_t_pending = model_resolve_source_access_evidence(
            registry_chain=registry(
                "clean_execution_attestation_prefix",
                prefix_count=clean_terminal_index,
            ),
            ledger_root_snapshot=model_ledger_root_snapshot(
                "complete_live_chain",
                model_root_children_from_chain(clean_chain),
            ),
        )
        self.assertEqual("T_PENDING_CLEAN_TERMINAL_COPY", clean_t_pending.submode)
        self.assertEqual(
            "APPEND_T_COPY_THEN_ALLOWED_LEDGER_REMOVAL_SEQUENCE",
            clean_t_pending.recovery_action,
        )
        self.assertEqual(
            "KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK",
            handles[1].recovery_action,
        )
        self.assertEqual(
            "COMPLETE_EXACT_COPIED_LEDGER_REMOVAL_SEQUENCE",
            handles[2].recovery_action,
        )
        self.assertEqual(
            "NO_LEDGER_RECONSTRUCTION_USE_DURABLE_TERMINAL_REGISTRY_COPY_ONLY",
            handles[3].recovery_action,
        )
        self.assertEqual(
            "NO_LEDGER_RECONSTRUCTION_USE_DURABLE_TERMINAL_REGISTRY_COPY_ONLY",
            handles[5].recovery_action,
        )

        active_empty = model_resolve_ledger_chain(())
        active_g0_raws = model_build_ledger_generation_raws(success[:1])
        active_g0 = model_resolve_ledger_chain(active_g0_raws)
        self.assertEqual((), active_empty.terminal_branch_ids)
        self.assertEqual((), active_g0.terminal_branch_ids)
        self.assertEqual(
            active_g0_raws,
            tuple(
                ref.raw
                for ref in ledger_for_row("workspace_never_created_with_g0_ledger").generations
            ),
        )
        active_g0_payload = decode_canonical(
            active_g0.generations[0].raw,
            source="causal active g0 fixture",
        )
        self.assertIsNone(active_g0_payload["terminal_branch_disposition"])
        self.assertNotIn("success_prefix_count", active_g0_payload)
        with self.assertRaisesRegex(CorpusFormatError, "forbidden in causal ledger"):
            model_build_ledger_generation_raws(
                success[:1],
                terminal_branch_disposition=("workspace_never_created_with_initial_ledger"),
            )
        injected_w_g0_payload = dict(active_g0_payload)
        injected_w_g0_payload["terminal_branch_disposition"] = (
            "workspace_never_created_with_initial_ledger"
        )
        injected_w_g0_payload["success_prefix_count"] = 1
        with self.assertRaisesRegex(CorpusFormatError, "forbidden in causal ledger"):
            model_resolve_ledger_chain((canonical_payload(injected_w_g0_payload),))
        self.assertEqual("LIVE_ACTIVE_PREFIX", handles[0].submode)
        self.assertEqual(
            "REQUIRE_EXTERNAL_SAME_PROCESS_PROOF_BEFORE_ANY_CONTINUATION",
            handles[0].recovery_action,
        )

        w_no_ledger = registry("workspace_never_created_no_ledger")
        w_g0 = registry("workspace_never_created_with_g0_ledger")
        for w_chain, disposition, prefix, expanded_id in (
            (
                w_no_ledger,
                "workspace_never_created_without_ledger",
                0,
                "workspace_never_created_without_ledger:0",
            ),
            (
                w_g0,
                "workspace_never_created_with_initial_ledger",
                1,
                "workspace_never_created_with_initial_ledger:1",
            ),
        ):
            w_terminal_copy = w_chain.terminal_ledger_copy
            self.assertIsNotNone(w_terminal_copy)
            if w_terminal_copy is None:
                self.fail("W registry chain lacks its terminal ledger copy")
            w_copy = w_terminal_copy.payload
            self.assertEqual(disposition, w_copy["terminal_branch_disposition"])
            self.assertEqual(prefix, w_copy["success_prefix_count"])
            self.assertEqual(expanded_id, w_copy["expanded_terminal_branch_id"])
        for row_id, causal_chain in (
            ("workspace_never_created_no_ledger", active_g0),
            ("workspace_never_created_with_g0_ledger", active_empty),
        ):
            with (
                self.subTest(W_cross_row=row_id),
                self.assertRaises(CorpusFormatError),
            ):
                model_build_registry_generation_raws(
                    row_id,
                    terminal_ledger_chain=causal_chain,
                )
        w_no_ledger_raws = model_build_registry_generation_raws(
            "workspace_never_created_no_ledger",
            terminal_ledger_chain=active_empty,
        )
        w_no_ledger_index = tuple(
            rows["workspace_never_created_no_ledger"]["generation_states_exact"]
        ).index("WORKSPACE_NOT_CREATED_TERMINAL_DURABLE")
        mutated_w_payload = decode_canonical(
            w_no_ledger_raws[w_no_ledger_index],
            source="W terminal copy mutation fixture",
        )
        mutated_w_payload["terminal_ledger_copy"]["terminal_branch_disposition"] = (
            "workspace_never_created_with_initial_ledger"
        )
        mutated_w_payload["terminal_ledger_copy"]["success_prefix_count"] = 1
        mutated_w_payload["terminal_ledger_copy"]["expanded_terminal_branch_id"] = (
            "workspace_never_created_with_initial_ledger:1"
        )
        with self.assertRaises(CorpusFormatError):
            model_resolve_registry_chain(
                (
                    *w_no_ledger_raws[:w_no_ledger_index],
                    canonical_payload(mutated_w_payload),
                )
            )

        a_ahead_terminal = model_resolve_ledger_chain(
            model_build_ledger_generation_raws(
                expanded["clean_operational_or_scientific_failure_after_workspace_ready:3"],
                terminal_checkpoint_override="A",
            )
        )
        suffix_payloads = [
            decode_canonical(ref.raw, source="A-ahead terminal suffix")
            for ref in a_ahead_terminal.generations[3:]
        ]
        self.assertTrue(suffix_payloads)
        self.assertTrue(
            all(
                (
                    payload["request_intent_count"],
                    payload["confirmed_application_dispatch_count"],
                    payload["complete_body_count"],
                    payload["source_access_status"],
                )
                == (0, 0, 0, "POSSIBLE_KNOWN")
                for payload in suffix_payloads
            )
        )

        terminal_overlap_cases = (
            (
                "clean_acquisition_started_prefix",
                "ACQUISITION_STARTED_DURABLE",
                "clean_operational_or_scientific_failure_after_workspace_ready:3",
                "P",
            ),
            (
                "clean_core_graph_prefix",
                "ACQUISITION_CORE_GRAPH_BOUND_DURABLE",
                "clean_operational_or_scientific_failure_after_workspace_ready:19",
                "A",
            ),
            (
                "clean_execution_attestation_prefix",
                "EXECUTION_ATTESTATION_BOUND_DURABLE",
                "clean_operational_or_scientific_failure_after_workspace_ready:20",
                "C",
            ),
        )
        for row_id, registry_state, branch_id, stale_checkpoint in terminal_overlap_cases:
            checkpoint_index = tuple(rows[row_id]["generation_states_exact"]).index(registry_state)
            stale_terminal = model_resolve_ledger_chain(
                model_build_ledger_generation_raws(
                    expanded[branch_id],
                    terminal_checkpoint_override=stale_checkpoint,
                )
            )
            with (
                self.subTest(
                    terminal_overlap=row_id,
                    stale_checkpoint=stale_checkpoint,
                ),
                self.assertRaisesRegex(
                    CorpusFormatError,
                    "registry/ledger status mismatch",
                ),
            ):
                model_resolve_source_access_evidence(
                    registry_chain=registry(
                        row_id,
                        prefix_count=checkpoint_index + 1,
                    ),
                    ledger_root_snapshot=model_ledger_root_snapshot(
                        "complete_live_chain",
                        model_root_children_from_chain(stale_terminal),
                    ),
                )

        clean_a = ledger_for_row("clean_acquisition_started_prefix")
        uncertainty_a = ledger_for_row("cleanup_uncertainty_acquisition_started_prefix")
        with self.assertRaisesRegex(CorpusFormatError, "incompatible"):
            model_build_registry_generation_raws(
                "clean_acquisition_started_prefix",
                terminal_ledger_chain=uncertainty_a,
            )
        with self.assertRaisesRegex(CorpusFormatError, "incompatible"):
            model_build_registry_generation_raws(
                "cleanup_uncertainty_acquisition_started_prefix",
                terminal_ledger_chain=clean_a,
            )
        c_checkpoint_terminal = model_resolve_ledger_chain(
            model_build_ledger_generation_raws(
                expanded["clean_operational_or_scientific_failure_after_workspace_ready:19"],
                terminal_checkpoint_override="C",
            )
        )
        with self.assertRaisesRegex(CorpusFormatError, "checkpoint differs"):
            model_build_registry_generation_raws(
                "clean_acquisition_started_prefix",
                terminal_ledger_chain=c_checkpoint_terminal,
            )

        clean_a_raws = model_build_registry_generation_raws(
            "clean_acquisition_started_prefix",
            terminal_ledger_chain=clean_a,
        )
        clean_a_terminal_index = tuple(
            rows["clean_acquisition_started_prefix"]["generation_states_exact"]
        ).index("TERMINAL_REGISTRY_DURABLE")
        clean_a_terminal_payload = decode_canonical(
            clean_a_raws[clean_a_terminal_index],
            source="clean A terminal registry mutation fixture",
        )
        for nested_context, error_pattern in (
            ("ATTACKER_UNBOUND", "not closed"),
            ("NO_ELIGIBLE_SCIENTIFIC_CANDIDATE", "predicts no valid branch"),
        ):
            mutated_payload = copy.deepcopy(clean_a_terminal_payload)
            mutated_payload["terminal_ledger_copy"]["branch_disposition"] = nested_context
            mutated_raws = (
                *clean_a_raws[:clean_a_terminal_index],
                canonical_payload(mutated_payload),
            )
            with (
                self.subTest(nested_terminal_copy_context=nested_context),
                self.assertRaisesRegex(CorpusFormatError, error_pattern),
            ):
                model_resolve_registry_chain(mutated_raws)

        candidate_lost_chain = model_resolve_ledger_chain(
            model_build_ledger_generation_raws(
                success,
                terminal_branch_disposition=(
                    "candidate_lost_after_RETENTION_CANDIDATES_MEMORY_READY"
                ),
            )
        )
        clean_success_chain = model_resolve_ledger_chain(
            model_build_ledger_generation_raws(
                success,
                terminal_branch_disposition="clean_evaluated_success",
            )
        )
        self.assertEqual(
            tuple(ref.lifecycle_state for ref in clean_success_chain.generations),
            tuple(ref.lifecycle_state for ref in candidate_lost_chain.generations),
        )
        self.assertEqual(25, candidate_lost_chain.success_prefix_count)
        self.assertEqual(29, clean_success_chain.success_prefix_count)
        self.assertEqual(
            ("candidate_lost_after_RETENTION_CANDIDATES_MEMORY_READY:25",),
            candidate_lost_chain.terminal_branch_ids,
        )
        self.assertEqual(
            ("clean_evaluated_success:29",),
            clean_success_chain.terminal_branch_ids,
        )
        self.assertNotEqual(
            candidate_lost_chain.generations[-1].raw,
            clean_success_chain.generations[-1].raw,
        )
        for chain, disposition, prefix, expanded_id in (
            (
                candidate_lost_chain,
                "candidate_lost_after_RETENTION_CANDIDATES_MEMORY_READY",
                25,
                "candidate_lost_after_RETENTION_CANDIDATES_MEMORY_READY:25",
            ),
            (
                clean_success_chain,
                "clean_evaluated_success",
                29,
                "clean_evaluated_success:29",
            ),
        ):
            terminal_payload = decode_canonical(
                chain.generations[-1].raw,
                source="terminal branch discriminator fixture",
            )
            self.assertEqual(disposition, terminal_payload["terminal_branch_disposition"])
            self.assertEqual(prefix, terminal_payload["success_prefix_count"])
            terminal_copy = _terminal_copy_payload(
                chain,
                checkpoint="E",
                branch_context="NO_ELIGIBLE_SCIENTIFIC_CANDIDATE",
            )
            self.assertEqual(disposition, terminal_copy["terminal_branch_disposition"])
            self.assertEqual(prefix, terminal_copy["success_prefix_count"])
            self.assertEqual(expanded_id, terminal_copy["expanded_terminal_branch_id"])

        orphan_states = expanded["workspace_created_empty_before_acquisition_started:2"]
        orphan_dispositions = (
            "workspace_created_empty_before_acquisition_started",
            "workspace_created_after_g0_before_g1_exact_empty_recovery_cleanup",
        )
        orphan_chains = tuple(
            model_resolve_ledger_chain(
                model_build_ledger_generation_raws(
                    orphan_states,
                    terminal_branch_disposition=disposition,
                )
            )
            for disposition in orphan_dispositions
        )
        self.assertEqual(
            tuple(ref.lifecycle_state for ref in orphan_chains[0].generations),
            tuple(ref.lifecycle_state for ref in orphan_chains[1].generations),
        )
        self.assertNotEqual(
            orphan_chains[0].terminal_branch_ids,
            orphan_chains[1].terminal_branch_ids,
        )

        clean_terminal_payload = decode_canonical(
            clean_success_chain.generations[-1].raw,
            source="clean discriminator mutation fixture",
        )
        for field_name, field_value in (
            (
                "terminal_branch_disposition",
                "candidate_lost_after_RETENTION_CANDIDATES_MEMORY_READY",
            ),
            ("success_prefix_count", 25),
            ("success_prefix_count", True),
        ):
            mutated_terminal_payload = dict(clean_terminal_payload)
            mutated_terminal_payload[field_name] = field_value
            mutated_ledger_raws = (
                *(ref.raw for ref in clean_success_chain.generations[:-1]),
                canonical_payload(mutated_terminal_payload),
            )
            with (
                self.subTest(discriminator_field=field_name, value=field_value),
                self.assertRaises(CorpusFormatError),
            ):
                model_resolve_ledger_chain(mutated_ledger_raws)

        pending_rows = (
            "scientific_candidate_memory_loss_before_durable_review",
            "review_approved_retention_committed",
            "review_denied",
            "review_failure",
            "candidate_lost_after_approval",
        )
        shared_prefixes = [
            model_build_registry_generation_raws(
                row_id,
                terminal_ledger_chain=clean_chain,
            )[:8]
            for row_id in pending_rows
        ]
        self.assertTrue(all(raws == shared_prefixes[0] for raws in shared_prefixes))
        pending_at_m = model_resolve_registry_chain(
            shared_prefixes[0],
            terminal_ledger_chain_at_creation=clean_chain,
        )
        self.assertIsNone(pending_at_m.selected_branch_id)
        self.assertEqual(set(pending_rows), set(pending_at_m.candidate_branch_ids))
        approved_final = registry("review_approved_retention_committed")
        denied_final = registry("review_denied")
        self.assertEqual(
            "review_approved_retention_committed",
            approved_final.selected_branch_id,
        )
        self.assertEqual("review_denied", denied_final.selected_branch_id)

        post_l_terminal_copy = post_l_registry.terminal_ledger_copy
        self.assertIsInstance(post_l_terminal_copy, ReferenceTerminalLedgerCopy)
        if not isinstance(post_l_terminal_copy, ReferenceTerminalLedgerCopy):
            self.fail("post-L registry lacks its terminal ledger copy")
        self.assertFalse(
            any(isinstance(value, ReferenceLedgerChain) for value in vars(post_l_registry).values())
        )
        self.assertNotIn("raw", post_l_terminal_copy.payload)
        self.assertTrue(
            all(
                "raw" not in member
                for member in post_l_terminal_copy.payload[
                    "ordered_ledger_generation_name_digest_state_size_roster"
                ]
            )
        )

        valid_remaining = model_root_children_from_chain(
            clean_chain,
            indices_in_enumeration_order=(0,),
        )[0]
        invalid_children = (
            replace(valid_remaining, name="ledger-v1:" + "0" * 64 + ":generation-0"),
            replace(valid_remaining, file_type="symlink"),
            replace(valid_remaining, nlink=2),
            replace(valid_remaining, raw=valid_remaining.raw + b" "),
        )
        for child in invalid_children:
            with self.subTest(child=child), self.assertRaises(CorpusFormatError):
                model_resolve_source_access_evidence(
                    registry_chain=pre_l_registry,
                    ledger_root_snapshot=model_ledger_root_snapshot(
                        "terminal_copy_remaining",
                        (child,),
                    ),
                )
        with self.assertRaises(CorpusFormatError):
            model_resolve_source_access_evidence(
                registry_chain=pre_l_registry,
                ledger_root_snapshot=model_ledger_root_snapshot(
                    "terminal_copy_remaining",
                    (valid_remaining, valid_remaining),
                ),
            )
        with self.assertRaisesRegex(CorpusFormatError, "mutated"):
            model_derive_source_access_status(
                replace(handles[3], source_access_status="POSSIBLE_KNOWN")
            )
        with self.assertRaisesRegex(CorpusFormatError, "mutated"):
            model_derive_source_access_status(
                replace(
                    handles[3],
                    recovery_action="KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK",
                )
            )
        with self.assertRaisesRegex(CorpusFormatError, "ReferenceSourceAccessEvidence"):
            model_derive_source_access_status({})  # type: ignore[arg-type]
        attacker_keywords = {
            "allowed_expanded_sequences": {"attacker": ("ATTACKER_DEFINED_DURABLE",)}
        }
        with self.assertRaises(TypeError):
            model_resolve_ledger_chain((), **attacker_keywords)
        self.assertEqual(18, len(terminal_crosswalk))
        self.assertEqual(
            {"R", "P", "A", "C", "E", "T", "L", "M", "W"},
            set(
                self.custody["future_protocol_prerequisite_blueprints"][
                    "one_time_attempt_and_pre_source_setup"
                ]["closed_attempt_state_machine"]["registry_only_state_abbreviations_exact"]
            ),
        )
        recovery_contract = self.custody["custody_lifecycle"]["source_access_status_derivation"][
            "reference_model_recovery_action_contract_exact"
        ]
        self.assertEqual(
            REFERENCE_RECOVERY_ACTIONS,
            set(recovery_contract["closed_values_exact"]),
        )
        self.assertEqual(
            {
                "WNC_no_ledger_terminal.UNOPENED_SEQUENCE_PROOF_ONLY": (
                    "TERMINAL_NO_LEDGER_NO_MUTATION_USE_DURABLE_W_COPY_ONLY"
                ),
                "post_L_WNC_g0.POST_L_TERMINAL_REGISTRY_COPY_ONLY_NO_DELETED_RAW": (
                    "NO_LEDGER_RECONSTRUCTION_USE_DURABLE_TERMINAL_REGISTRY_COPY_ONLY"
                ),
                "post_L_workspace_created.POST_L_TERMINAL_REGISTRY_COPY_ONLY_NO_DELETED_RAW": (
                    "NO_LEDGER_RECONSTRUCTION_USE_DURABLE_TERMINAL_REGISTRY_COPY_ONLY"
                ),
                "pre_terminal_copy_live.LIVE_ACTIVE_PREFIX_exact_current_non_ahead": (
                    "REQUIRE_EXTERNAL_SAME_PROCESS_PROOF_BEFORE_ANY_CONTINUATION"
                ),
                (
                    "pre_terminal_copy_live.LIVE_ACTIVE_PREFIX_one_generation_ahead_"
                    "or_any_restart_without_separate_same_process_proof"
                ): ("TERMINALIZE_CONTROL_ONLY_NO_RECONSTRUCTION_OR_SOURCE_RETRY"),
                "pre_terminal_copy_live.T_PENDING_CLEAN_TERMINAL_COPY": (
                    "APPEND_T_COPY_THEN_ALLOWED_LEDGER_REMOVAL_SEQUENCE"
                ),
                "pre_terminal_copy_live.T_PENDING_RETAINED_UNCERTAINTY": (
                    "APPEND_T_COPY_KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK"
                ),
                "terminal_copy_pre_L_removal_recovery.FULL_PARTIAL_OR_EMPTY_COPY_ORDER_UNLINK": (
                    "COMPLETE_EXACT_COPIED_LEDGER_REMOVAL_SEQUENCE"
                ),
                "terminal_retained_uncertainty.FULL_RETAINED_CHAIN": (
                    "KEEP_RETAINED_LEDGER_LIVE_NO_UNLINK"
                ),
            },
            recovery_contract["selector_and_submode_to_action_exact"],
        )
        self.assertIs(
            False,
            recovery_contract["runtime_or_source_access_authority_created"],
        )
        self.assertIn(
            "not_by_raw_registry_ledger_store_or_this_reference_model",
            recovery_contract["same_process_continuation_fact_source"],
        )

    def test_resource_cardinality_crosswalk_is_exact_five_six_six(self) -> None:
        crosswalk = self.custody["future_protocol_prerequisite_blueprints"]["acquisition_evidence"][
            "normative_resource_cardinality_crosswalk"
        ]
        validate_resource_cardinality_crosswalk(crosswalk, self.source_contract)
        mutations = []
        hidden_sixth = copy.deepcopy(crosswalk)
        hidden_sixth["network_request_transport_trace_receipt_and_body_identity_count_exact"] = 6
        mutations.append(hidden_sixth)
        mackay_receipt = copy.deepcopy(crosswalk)
        mackay_receipt["penn_receipt_resource_ids_exact_parent_order"].insert(
            0, "source-resource-v1:mackay-report"
        )
        mutations.append(mackay_receipt)
        reordered = copy.deepcopy(crosswalk)
        reordered["penn_receipt_requested_uris_exact_parent_order"][0:2] = reversed(
            reordered["penn_receipt_requested_uris_exact_parent_order"][0:2]
        )
        mutations.append(reordered)
        wrong_duplicate = copy.deepcopy(crosswalk)
        wrong_duplicate["pass_slot_to_penn_receipt_index_exact"][5] = 3
        mutations.append(wrong_duplicate)
        wrong_mackay = copy.deepcopy(crosswalk)
        wrong_mackay["source_revision_set_index_zero_mackay_projection_exact"]["byte_size"] += 1
        mutations.append(wrong_mackay)
        for mutation in mutations:
            with self.assertRaises(CorpusFormatError):
                validate_resource_cardinality_crosswalk(mutation, self.source_contract)

    def synthetic_receipt(self) -> tuple[dict[str, Any], tuple[bytes, ...]]:
        bodies = tuple(
            f"<!doctype html><title>synthetic-{index}</title>".encode() for index in range(5)
        )
        members = []
        for index, (resource_id, uri, body) in enumerate(
            zip(PENN_RESOURCE_IDS, PENN_ITEM_URIS, bodies, strict=True)
        ):
            members.append(
                {
                    "byte_size": len(body),
                    "content_encoding": "identity",
                    "content_type": "text/html",
                    "etag": 'W/"synthetic-1"' if index == 1 else None,
                    "final_uri": uri,
                    "http_status": 200,
                    "last_modified": ("Sun, 06 Nov 1994 08:49:37 GMT" if index == 2 else None),
                    "redirect_chain": [],
                    "requested_uri": uri,
                    "resource_id": resource_id,
                    "response_representation": (
                        "exact_http_response_body_after_transfer_decoding_before_text_decoding"
                    ),
                    "retrieved_at": f"2026-01-02T03:04:0{index}Z",
                    "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                }
            )
        return (
            {
                "contract_id": "source-reported-link-source-contract-v1",
                "contract_sha256": CONTRACT_SHA256,
                "member_count": 5,
                "members": members,
                "ordered_resource_ids": list(PENN_RESOURCE_IDS),
                "receipt_id": "source-reported-link-source-revision-receipt-v1",
                "receipt_schema_version": "v1",
                "receipt_status": "complete",
                "source_registry_sha256": f"sha256:{SOURCE_REGISTRY_SHA256}",
            },
            bodies,
        )

    def synthetic_envelope(self, receipt: dict[str, Any]) -> dict[str, Any]:
        return {
            "canonical_json_profile_id": "indusbench-io-encode-json-v1",
            "contract_id": "source-reported-link-source-contract-v1",
            "contract_sha256": CONTRACT_SHA256,
            "digest_domain": RECEIPT_DOMAIN,
            "digest_framing": (
                "utf8_domain_then_nul_then_canonical_encode_json_complete_receipt_payload_"
                "excluding_revision_receipt_sha256"
            ),
            "digest_input_bom_permitted": False,
            "digest_input_terminal_lf_included": True,
            "envelope_id": "source-reported-link-receipt-commitment-envelope-v1",
            "envelope_schema_version": "v1",
            "envelope_status": "complete",
            "receipt_id": "source-reported-link-source-revision-receipt-v1",
            "receipt_payload_self_hash_field_permitted": False,
            "revision_receipt_sha256": tagged_digest(RECEIPT_DOMAIN, receipt),
        }

    def synthetic_revision_set(self, receipt: dict[str, Any]) -> dict[str, Any]:
        resources = [
            {
                "byte_size": 27802606,
                "final_uri": None,
                "requested_uri": None,
                "resource_id": "source-resource-v1:mackay-report",
                "response_representation": None,
                "sha256": (
                    "sha256:93a76551ab048c6a455b4239730dce718b96cd5b3747852b025858d86b253ef0"
                ),
            }
        ]
        resources.extend(
            {
                key: member[key]
                for key in (
                    "resource_id",
                    "requested_uri",
                    "final_uri",
                    "response_representation",
                    "byte_size",
                    "sha256",
                )
            }
            for member in receipt["members"]
        )
        return {
            "contract_sha256": CONTRACT_SHA256,
            "resource_count": 6,
            "resources": resources,
            "revision_set_version": "v1",
        }

    def synthetic_attestation(
        self,
        receipt: dict[str, Any],
        revision_set: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "ambiguous_count": 0,
            "contract_sha256": CONTRACT_SHA256,
            "duplicate_count": 0,
            "error_count": 0,
            "extra_count": 0,
            "missing_count": 0,
            "ordered_source_roster_count": 6,
            "ordered_source_roster_sha256": (
                "sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f"
            ),
            "processed_count": 6,
            "processed_link_ids": list(LINK_IDS),
            "revision_receipt_sha256": tagged_digest(RECEIPT_DOMAIN, receipt),
            "source_revision_sha256": tagged_digest(REVISION_SET_DOMAIN, revision_set),
            "unreadable_count": 0,
        }

    def synthetic_deletion_record(self, custody_sha256: str) -> dict[str, Any]:
        authority_grant_id = "grant-v1:" + "0" * 32
        derived = derive_grant_identifiers(authority_grant_id)
        return {
            "attempt_id": derived["attempt_id"],
            "authority_grant_id": authority_grant_id,
            "authority_proof_sha256": "sha256:" + "a" * 64,
            "protected_content_cleanup_ended_at": "2026-01-02T03:05:00Z",
            "protected_content_cleanup_started_at": "2026-01-02T03:04:59Z",
            "cleanup_residue_status": "verified_workspace_absent_and_inodes_detached",
            "cleanup_uncertainty_present": False,
            "contract_id": "source-reported-link-protected-ephemeral-custody-contract-v1",
            "contract_sha256": custody_sha256,
            "protected_content_descriptor_count": 0,
            "protected_content_descriptor_count_status": "exact_bounded_count",
            "record_contains_source_content": False,
            "record_contains_workspace_path": False,
            "record_id": "source-reported-link-custody-deletion-record-v1",
            "record_schema_version": "v1",
            "protected_content_descriptors_closed": True,
            "registered_protected_leaves_logically_unlinked": True,
            "scientific_evidence_review_eligibility": (
                "eligible_for_separate_internal_retention_review"
            ),
            "secure_erasure_claimed": False,
            "request_intent_count": 5,
            "request_intent_count_status": "exact_durable_intent_count",
            "confirmed_application_dispatch_count": 5,
            "confirmed_application_dispatch_count_status": (
                "exact_confirmed_application_dispatch_count"
            ),
            "complete_body_count": 5,
            "complete_body_count_status": "exact_complete_body_count",
            "source_access_status": "CONFIRMED_COMPLETE",
            "protected_content_cleanup_reason_code": "success",
            "workspace_creation_provenance": "normal_workspace_ready_durable",
            "workspace_dentry_absent_from_pinned_parent_and_inode_detached": True,
            "workspace_id": derived["public_safe_workspace_id"],
        }

    def assert_canonical_decoder_rejects_mutations(
        self,
        payload: dict[str, Any],
        *,
        source: str,
    ) -> None:
        canonical = canonical_payload(payload)
        with self.assertRaises(CorpusFormatError):
            decode_canonical(b"\xef\xbb\xbf" + canonical, source=f"{source}-bom")
        first_key = sorted(payload)[0]
        duplicate = b"{\n" + f'  "{first_key}": null,\n'.encode() + canonical.removeprefix(b"{\n")
        with self.assertRaises(CorpusFormatError):
            decode_canonical(duplicate, source=f"{source}-duplicate")
        noncanonical = canonical.replace(b": ", b":", 1)
        with self.assertRaises(CorpusFormatError):
            decode_canonical(noncanonical, source=f"{source}-noncanonical")
        floating = copy.deepcopy(payload)
        floating["canonical_float_probe"] = 1.0
        with self.assertRaises(CorpusFormatError):
            canonical_payload(floating)

    def test_all_static_json_is_canonical_and_all_schemas_are_closed(self) -> None:
        self.assertEqual(canonical_payload(self.custody), self.custody_bytes)
        for path, schema in self.schemas.items():
            with self.subTest(path=path.name):
                Draft202012Validator.check_schema(schema)
                self.assertEqual(canonical_payload(schema), path.read_bytes())
        for path in DYNAMIC_SCHEMA_PATHS:
            with self.subTest(closed_schema=path.name):
                self.assertIn("additionalProperties", self.schemas[path])
                self.assertIs(False, self.schemas[path]["additionalProperties"])
        self.assertIs(
            False,
            self.schemas[RECEIPT_SCHEMA_PATH]["$defs"]["member"]["additionalProperties"],
        )
        self.assertIs(
            False,
            self.schemas[REVISION_SET_SCHEMA_PATH]["$defs"]["pennProjection"][
                "additionalProperties"
            ],
        )
        self.assertIs(
            False,
            self.schemas[REVISION_SET_SCHEMA_PATH]["properties"]["resources"]["prefixItems"][0][
                "additionalProperties"
            ],
        )
        deletion_schema = self.custody["deletion_record_specification"]["embedded_schema"]
        Draft202012Validator.check_schema(deletion_schema)
        self.assertIn("additionalProperties", deletion_schema)
        self.assertIs(False, deletion_schema["additionalProperties"])

        custody_validator = self.validators[CUSTODY_SCHEMA_PATH]
        custody_validator.validate(self.custody)
        self.assertEqual(self.schemas[CUSTODY_SCHEMA_PATH]["const"], self.custody)
        mutated = copy.deepcopy(self.custody)
        mutated["authorization_boundary"]["acquisition_authorized"] = True
        self.assertTrue(list(custody_validator.iter_errors(mutated)))

    def test_parent_source_contract_is_byte_immutable_and_still_blocked(self) -> None:
        self.assertEqual(
            SOURCE_CONTRACT_SHA256,
            hashlib.sha256(self.source_contract_bytes).hexdigest(),
        )
        boundary = self.source_contract["execution_boundary"]
        self.assertEqual("not_authorized", boundary["authorization_status"])
        self.assertEqual("not_executed", boundary["execution_status"])
        self.assertIs(False, boundary["source_access_performed_under_contract"])
        self.assertIs(False, boundary["revision_receipt_present"])
        requirement = self.source_contract["revision_receipt_requirement"]
        self.assertEqual(
            "separate_closed_schema_not_implemented",
            requirement["closed_receipt_schema_status"],
        )
        self.assertEqual("absent_not_created", requirement["receipt_status"])
        self.assertIs(False, requirement["receipt_creation_authorized"])
        self.assertEqual(
            "missing",
            self.source_contract["inspection_procedure"]["content_retention_boundary"][
                "separate_custody_and_deletion_contract_status"
            ],
        )
        for key in (
            "revision_receipt",
            "revision_receipt_sha256",
            "source_revision_set",
            "source_revision_sha256",
            "completeness_attestation",
            "completeness_attestation_sha256",
        ):
            self.assertNotIn(key, self.source_contract)
        transition = self.custody["historical_transition"]
        self.assertIs(True, transition["followup_closure_nonretroactive"])
        self.assertEqual(
            "separate_closed_schema_not_implemented",
            transition["historical_statuses_preserved"]["closed_receipt_schema_status"],
        )
        self.assertEqual(
            "missing",
            transition["historical_statuses_preserved"]["custody_and_deletion_contract_status"],
        )
        future = transition["future_authority_binding"]
        self.assertIs(True, future["external_future_authority_binding_required"])
        self.assertIs(True, future["external_future_authority_must_bind_published_commit"])
        self.assertIn("not_self_bound", future["published_commit_binding"])
        self.assertIn("static_prerequisite_commit", future["published_commit_binding"])
        self.assertIn("authorized_runtime_commit", future["published_commit_binding"])
        self.assertIs(False, future["authorization_record_embedded_in_this_contract"])
        self.assertEqual(
            "not_authorized",
            future["authorization_effect_without_external_binding"],
        )
        self.assertIs(False, transition["self_cycle_permitted"])

    def test_receipt_exact_five_body_identities_and_metadata_lexemes(self) -> None:
        receipt, bodies = self.synthetic_receipt()
        validator = self.validators[RECEIPT_SCHEMA_PATH]
        validator.validate(receipt)
        self.assertEqual(5, len(receipt["members"]))
        for member, body in zip(receipt["members"], bodies, strict=True):
            self.assertEqual(len(body), member["byte_size"])
            self.assertEqual(
                "sha256:" + hashlib.sha256(body).hexdigest(),
                member["sha256"],
            )
        self.assertTrue(validate_imf_fixdate(receipt["members"][2]["last_modified"]))

        mutations: dict[str, dict[str, Any]] = {}
        changed = copy.deepcopy(receipt)
        changed["members"].pop()
        mutations["partial four-member receipt"] = changed
        changed = copy.deepcopy(receipt)
        changed["members"].reverse()
        mutations["member reorder"] = changed
        changed = copy.deepcopy(receipt)
        changed["members"][0]["retrieved_at"] = "2026-01-02T03:04:05+00:00"
        mutations["retrieved_at non-Z"] = changed
        changed = copy.deepcopy(receipt)
        changed["members"][0]["retrieved_at"] = "2026-01-02T03:04:05Z\n"
        mutations["retrieved_at final newline"] = changed
        changed = copy.deepcopy(receipt)
        changed["members"][2]["last_modified"] = "Sunday, 06-Nov-94 08:49:37 GMT"
        mutations["obsolete Last-Modified"] = changed
        changed = copy.deepcopy(receipt)
        changed["members"][0]["unexpected"] = False
        mutations["nested receipt member extra"] = changed
        changed = copy.deepcopy(receipt)
        changed["revision_receipt_sha256"] = "sha256:" + "0" * 64
        mutations["receipt self hash"] = changed
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self.assertTrue(list(validator.iter_errors(mutation)))

        for invalid_etag in ('"tag"\r', '"tag"\n', '"tag"\u2028', '"tag"\u2029'):
            changed = copy.deepcopy(receipt)
            changed["members"][0]["etag"] = invalid_etag
            with self.subTest(invalid_etag=repr(invalid_etag)):
                self.assertTrue(list(validator.iter_errors(changed)))

        lexical_but_semantically_invalid_dates = (
            "Sun, 31 Feb 2026 08:49:37 GMT",
            "Sun, 06 Nov 1995 08:49:37 GMT",
            "Tue, 29 Feb 2023 08:49:37 GMT",
            "Sat, 01 Jan 0000 00:00:00 GMT",
        )
        for invalid_date in lexical_but_semantically_invalid_dates:
            changed = copy.deepcopy(receipt)
            changed["members"][2]["last_modified"] = invalid_date
            with self.subTest(invalid_date=invalid_date):
                self.assertFalse(list(validator.iter_errors(changed)))
                self.assertFalse(validate_imf_fixdate(invalid_date))

        changed = copy.deepcopy(receipt)
        changed["members"][0]["byte_size"] += 1
        self.assertFalse(list(validator.iter_errors(changed)))
        self.assertFalse(body_identity_matches(changed["members"][0], bodies[0]))
        changed = copy.deepcopy(receipt)
        changed["members"][0]["sha256"] = "sha256:" + "0" * 64
        self.assertFalse(list(validator.iter_errors(changed)))
        self.assertFalse(body_identity_matches(changed["members"][0], bodies[0]))

        comment = self.schemas[RECEIPT_SCHEMA_PATH]["$comment"]
        self.assertIn("exactly one header occurrence", comment)
        self.assertIn("multiple occurrences", comment)
        self.assertIn("untrusted local observation", comment)
        profile = self.schemas[RECEIPT_SCHEMA_PATH]["x-member-observation-profile"]
        self.assertEqual("hard_reject", profile["etag"]["multiple_header_occurrences_disposition"])
        self.assertIs(False, profile["etag"]["unicode_line_separator_permitted"])
        self.assertIs(False, profile["etag"]["unicode_paragraph_separator_permitted"])
        self.assertEqual(
            "hard_reject",
            profile["last_modified"]["multiple_header_occurrences_disposition"],
        )
        self.assertEqual(
            "future_strict_verifier_not_implemented",
            profile["last_modified"]["calendar_and_weekday_roundtrip_verifier_status"],
        )
        self.assertEqual(
            "imf_fixdate_shaped_exact_29_ascii_characters_only",
            profile["last_modified"]["lexical_profile"],
        )
        self.assertIs(False, profile["retrieved_at"]["trusted_time_claimed"])
        self.assertIs(True, profile["body_identity"]["recompute_byte_size_and_sha256_required"])
        self.assertIs(
            False,
            profile["body_identity"]["schema_validation_can_substitute_for_byte_comparison"],
        )
        last_modified = self.custody["cross_artifact_verifier_contract"][
            "format_assertion_profile"
        ]["last_modified"]
        self.assertEqual("lexical_shape_only", last_modified["schema_scope"])
        self.assertEqual("proleptic_gregorian", last_modified["calendar"])
        self.assertIs(False, last_modified["locale_dependency_permitted"])
        self.assertIs(False, last_modified["year_0000_permitted"])
        self.assertIs(True, last_modified["weekday_roundtrip_required"])

    def test_receipt_external_digest_envelope_is_domain_separated_and_self_excluding(self) -> None:
        receipt, _ = self.synthetic_receipt()
        self.validators[RECEIPT_SCHEMA_PATH].validate(receipt)
        receipt_bytes = canonical_payload(receipt)
        self.assertTrue(receipt_bytes.endswith(b"\n"))
        revision_receipt_sha256 = tagged_digest(RECEIPT_DOMAIN, receipt)
        envelope = self.synthetic_envelope(receipt)
        self.validators[ENVELOPE_SCHEMA_PATH].validate(envelope)
        without_nul = (
            "sha256:" + hashlib.sha256(RECEIPT_DOMAIN.encode() + receipt_bytes).hexdigest()
        )
        without_lf = (
            "sha256:"
            + hashlib.sha256(RECEIPT_DOMAIN.encode() + b"\0" + receipt_bytes[:-1]).hexdigest()
        )
        self.assertNotEqual(revision_receipt_sha256, without_nul)
        self.assertNotEqual(revision_receipt_sha256, without_lf)
        self.assertNotIn("revision_receipt_sha256", receipt)

        self_hashed = copy.deepcopy(receipt)
        self_hashed["revision_receipt_sha256"] = revision_receipt_sha256
        self.assertTrue(list(self.validators[RECEIPT_SCHEMA_PATH].iter_errors(self_hashed)))
        self.assertNotEqual(tagged_digest(RECEIPT_DOMAIN, self_hashed), revision_receipt_sha256)
        changed_envelope = copy.deepcopy(envelope)
        changed_envelope["unexpected"] = False
        self.assertTrue(list(self.validators[ENVELOPE_SCHEMA_PATH].iter_errors(changed_envelope)))

    def test_revision_set_is_exact_ordered_six_and_projects_receipt_body_identity(self) -> None:
        receipt, bodies = self.synthetic_receipt()
        revision_set = self.synthetic_revision_set(receipt)
        validator = self.validators[REVISION_SET_SCHEMA_PATH]
        validator.validate(revision_set)
        self.assertEqual(6, revision_set["resource_count"])
        self.assertEqual(
            ["source-resource-v1:mackay-report", *PENN_RESOURCE_IDS],
            [resource["resource_id"] for resource in revision_set["resources"]],
        )
        for resource, member, body in zip(
            revision_set["resources"][1:], receipt["members"], bodies, strict=True
        ):
            self.assertEqual(member["byte_size"], resource["byte_size"])
            self.assertEqual(member["sha256"], resource["sha256"])
            self.assertEqual(len(body), resource["byte_size"])
            self.assertEqual("sha256:" + hashlib.sha256(body).hexdigest(), resource["sha256"])
        source_revision_sha256 = tagged_digest(REVISION_SET_DOMAIN, revision_set)
        self.assertRegex(source_revision_sha256, r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("source_revision_sha256", revision_set)

        changed = copy.deepcopy(revision_set)
        changed["source_revision_sha256"] = source_revision_sha256
        self.assertTrue(list(validator.iter_errors(changed)))
        changed = copy.deepcopy(revision_set)
        changed["resources"][1], changed["resources"][2] = (
            changed["resources"][2],
            changed["resources"][1],
        )
        self.assertTrue(list(validator.iter_errors(changed)))
        changed = copy.deepcopy(revision_set)
        changed["resources"][1]["retrieved_at"] = "2026-01-02T03:04:05Z"
        self.assertTrue(list(validator.iter_errors(changed)))

    def test_all_dynamic_tagged_digests_reject_final_newline(self) -> None:
        receipt, _ = self.synthetic_receipt()
        revision_set = self.synthetic_revision_set(receipt)
        attestation = self.synthetic_attestation(receipt, revision_set)
        envelope = self.synthetic_envelope(receipt)

        cases: list[tuple[str, Path, dict[str, Any]]] = []
        changed = copy.deepcopy(receipt)
        changed["members"][0]["sha256"] += "\n"
        cases.append(("receipt member", RECEIPT_SCHEMA_PATH, changed))
        changed = copy.deepcopy(envelope)
        changed["revision_receipt_sha256"] += "\n"
        cases.append(("receipt envelope", ENVELOPE_SCHEMA_PATH, changed))
        changed = copy.deepcopy(revision_set)
        changed["resources"][1]["sha256"] += "\n"
        cases.append(("revision member", REVISION_SET_SCHEMA_PATH, changed))
        changed = copy.deepcopy(attestation)
        changed["revision_receipt_sha256"] += "\n"
        cases.append(("completeness receipt digest", COMPLETENESS_SCHEMA_PATH, changed))
        changed = copy.deepcopy(attestation)
        changed["source_revision_sha256"] += "\n"
        cases.append(("completeness revision digest", COMPLETENESS_SCHEMA_PATH, changed))
        for name, schema_path, payload in cases:
            with self.subTest(name=name):
                self.assertTrue(list(self.validators[schema_path].iter_errors(payload)))

    def test_completeness_is_six_slots_and_two_separately_built_digests_must_match(
        self,
    ) -> None:
        first_receipt, _ = self.synthetic_receipt()
        second_receipt, _ = self.synthetic_receipt()
        first_revision_set = self.synthetic_revision_set(first_receipt)
        second_revision_set = self.synthetic_revision_set(second_receipt)
        first_attestation = self.synthetic_attestation(first_receipt, first_revision_set)
        second_attestation = self.synthetic_attestation(second_receipt, second_revision_set)
        validator = self.validators[COMPLETENESS_SCHEMA_PATH]

        shared_digest = require_two_nonnull_equal_completeness_digests(
            validator,
            first_attestation,
            second_attestation,
        )
        self.assertEqual(71, len(shared_digest))
        self.assertEqual(5, len(first_receipt["members"]))
        self.assertEqual(6, len(first_revision_set["resources"]))
        self.assertEqual(6, len(first_attestation["processed_link_ids"]))
        self.assertNotIn("pass_id", first_attestation)
        self.assertNotIn("seal_sha256", first_attestation)
        envelope = self.synthetic_envelope(first_receipt)
        require_completeness_parent_digest_bindings(
            first_receipt,
            envelope,
            first_revision_set,
            (first_attestation, second_attestation),
        )

        equal_wrong_first = copy.deepcopy(first_attestation)
        equal_wrong_second = copy.deepcopy(second_attestation)
        for attestation in (equal_wrong_first, equal_wrong_second):
            attestation["revision_receipt_sha256"] = "sha256:" + "e" * 64
            attestation["source_revision_sha256"] = "sha256:" + "f" * 64
        wrong_shared_digest = require_two_nonnull_equal_completeness_digests(
            validator,
            equal_wrong_first,
            equal_wrong_second,
        )
        self.assertRegex(wrong_shared_digest, r"^sha256:[0-9a-f]{64}$")
        with self.assertRaisesRegex(CorpusFormatError, "completeness parent digest mismatch"):
            require_completeness_parent_digest_bindings(
                first_receipt,
                envelope,
                first_revision_set,
                (equal_wrong_first, equal_wrong_second),
            )

        schema_valid_mismatch = copy.deepcopy(second_attestation)
        schema_valid_mismatch["source_revision_sha256"] = "sha256:" + "f" * 64
        validator.validate(schema_valid_mismatch)
        self.assertNotEqual(
            tagged_digest(COMPLETENESS_DOMAIN, first_attestation),
            tagged_digest(COMPLETENESS_DOMAIN, schema_valid_mismatch),
        )
        with self.assertRaisesRegex(
            CorpusFormatError,
            "two completeness attestation digests differ",
        ):
            require_two_nonnull_equal_completeness_digests(
                validator,
                first_attestation,
                schema_valid_mismatch,
            )

        changed = copy.deepcopy(first_attestation)
        changed["processed_link_ids"].pop()
        self.assertTrue(list(validator.iter_errors(changed)))
        changed = copy.deepcopy(first_attestation)
        changed["missing_count"] = 1
        self.assertTrue(list(validator.iter_errors(changed)))
        changed = copy.deepcopy(first_attestation)
        changed["pass_id"] = "forbidden"
        self.assertTrue(list(validator.iter_errors(changed)))
        changed = copy.deepcopy(first_attestation)
        changed["unexpected"] = False
        self.assertTrue(list(validator.iter_errors(changed)))

        prerequisites = self.schemas[COMPLETENESS_SCHEMA_PATH]["x-creation-prerequisites"]
        self.assertEqual("not_authorized", prerequisites["authorization_status"])
        self.assertEqual("not_executed", prerequisites["execution_status"])
        self.assertEqual(COMPLETENESS_DOMAIN, prerequisites["digest_domain"])
        self.assertEqual(2, prerequisites["pass_count"])
        self.assertIs(
            True,
            prerequisites["two_valid_nonnull_attestation_digest_equality_required"],
        )
        self.assertIs(
            False,
            prerequisites[
                "admission_or_owner_only_retention_before_required_reference_relation_resolution_permitted"
            ],
        )
        self.assertIs(False, prerequisites["pass_ids_and_seals_in_digest_permitted"])
        self.assertEqual(
            "separately_sealed_coded_machine_passes",
            prerequisites["pass_mode"],
        )
        self.assertIs(True, prerequisites["distinct_pass_id_required"])
        self.assertIs(True, prerequisites["distinct_seal_sha256_required"])
        for nonclaim in (
            "blinding_verified",
            "human_independence_verified",
            "model_independence_verified",
            "nonexposure_verified",
            "organizational_independence_verified",
        ):
            self.assertIs(False, prerequisites[nonclaim])
        binding = self.custody["cross_artifact_verifier_contract"][
            "completeness_parent_digest_binding"
        ]
        self.assertIs(True, binding["required_for_each_pass_when_available"])
        self.assertIs(
            False,
            binding["two_equal_attestations_with_equal_wrong_parent_digests_are_valid_evidence"],
        )

    def test_float_duplicate_bom_and_noncanonical_bytes_are_hard_rejected(
        self,
    ) -> None:
        receipt, _ = self.synthetic_receipt()
        floating = copy.deepcopy(receipt)
        floating["members"][0]["byte_size"] = float(floating["members"][0]["byte_size"])
        self.assertFalse(list(self.validators[RECEIPT_SCHEMA_PATH].iter_errors(floating)))
        with self.assertRaises(CorpusFormatError):
            canonical_payload(floating)

        canonical = canonical_payload(receipt)
        with self.assertRaises(CorpusFormatError):
            decode_canonical(b"\xef\xbb\xbf" + canonical, source="bom")
        duplicate = canonical.replace(
            b'{\n  "contract_id":',
            b'{\n  "contract_id": "duplicate",\n  "contract_id":',
            1,
        )
        with self.assertRaises(CorpusFormatError):
            decode_canonical(duplicate, source="duplicate")
        noncanonical = canonical.replace(b": ", b":", 1)
        with self.assertRaises(CorpusFormatError):
            decode_canonical(noncanonical, source="noncanonical")

        revision_set = self.synthetic_revision_set(receipt)
        attestation = self.synthetic_attestation(receipt, revision_set)
        envelope = self.synthetic_envelope(receipt)
        custody_sha256 = "sha256:" + hashlib.sha256(self.custody_bytes).hexdigest()
        deletion_record = self.synthetic_deletion_record(custody_sha256)
        typed_payloads = (
            ("receipt", receipt),
            ("envelope", envelope),
            ("revision-set", revision_set),
            ("completeness-pass-1", attestation),
            ("completeness-pass-2", copy.deepcopy(attestation)),
            ("deletion-record", deletion_record),
        )
        for source, payload in typed_payloads:
            with self.subTest(source=source):
                self.assert_canonical_decoder_rejects_mutations(payload, source=source)

    def test_custody_cleanup_is_fail_closed_without_secure_erasure_overclaim(self) -> None:
        boundary = self.custody["authorization_boundary"]
        self.assertEqual("not_authorized", boundary["status"])
        self.assertEqual("not_executed", boundary["execution_status"])
        for key in (
            "acquisition_authorized",
            "contract_creates_execution_authority",
            "contract_creates_source_access_authority",
            "custody_workspace_created",
            "deletion_executed",
            "protected_bytes_present",
            "receipt_created",
            "source_access_performed",
        ):
            self.assertIs(False, boundary[key])
        lifecycle = self.custody["custody_lifecycle"]
        deletion = lifecycle["deletion_semantics"]
        self.assertIs(False, deletion["filesystem_content_leaf_logical_unlink_required"])
        self.assertIn(
            "vacuous_for_exact_empty_registered_roster",
            deletion["registered_protected_leaves_logically_unlinked_field_semantics"],
        )
        self.assertIs(False, deletion["secure_erasure_claimed"])
        self.assertEqual(
            "block_scientific_evidence_owner_only_retention_and_all_publication",
            deletion["cleanup_uncertainty_disposition"],
        )
        self.assertEqual(
            0,
            deletion["protected_content_descriptor_count_after_close_required"],
        )
        self.assertIs(
            True,
            deletion["workspace_absence_and_inode_detachment_verification_required"],
        )
        order = deletion["deletion_order"]
        self.assertLess(
            order.index("close_all_consumer_descriptors"),
            order.index("verify_registered_protected_leaf_roster_exact_empty_and_maximum_zero"),
        )
        self.assertLess(
            order.index("descriptor_relative_rmdir_workspace_from_pinned_parent"),
            order.index(
                "close_controller_empty_workspace_descriptor_retain_pinned_parent_ledger_audit_directory_and_management_descriptors"
            ),
        )
        self.assertLess(
            order.index("verify_protected_content_descriptor_count_zero"),
            order.index("construct_validate_and_digest_content_free_deletion_record_candidate"),
        )
        self.assertLess(
            order.index(
                "append_exact_next_DELETION_RECORD_PREPARED_DURABLE_immutable_ledger_generation_binding_exact_canonical_record_bytes_digest_and_authenticated_staging_and_final_child_ids_via_authenticated_staging_file_fsync_RENAME_NOREPLACE_parent_fsync_and_chain_revalidation"
            ),
            order.index(
                "create_no_replace_write_validate_and_file_fsync_authenticated_deletion_record_staging_generation"
            ),
        )
        self.assertLess(
            order.index(
                "descriptor_relative_unlink_each_and_only_copied_ledger_generation_child_roster_entry_then_fsync_ledger_parent"
            ),
            order.index(
                "verify_every_copied_ledger_generation_absent_and_surviving_registry_record_copied_terminal_ledger_projection_relation_without_ledger_reopen_or_volatile_memory_dependency"
            ),
        )
        self.assertLess(
            order.index(
                "verify_every_copied_ledger_generation_absent_and_surviving_registry_record_copied_terminal_ledger_projection_relation_without_ledger_reopen_or_volatile_memory_dependency"
            ),
            order.index(
                "close_every_remaining_registered_acquisition_custody_descriptor_role_in_exact_A_roster_without_same_process_reopen"
            ),
        )
        self.assertLess(
            order.index(
                "close_every_remaining_registered_acquisition_custody_descriptor_role_in_exact_A_roster_without_same_process_reopen"
            ),
            order.index(
                "verify_registered_acquisition_custody_descriptor_roster_runtime_count_zero"
            ),
        )
        boundary = lifecycle["descriptor_pinned_filesystem_boundary"]
        self.assertEqual(
            ["st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size"],
            boundary["fingerprint_fields"],
        )
        self.assertEqual(
            {
                "openat_or_equivalent_dir_fd_relative",
                "O_NOFOLLOW",
                "O_CLOEXEC",
                "O_DIRECTORY_for_parent_and_empty_workspace",
            },
            set(boundary["open_primitives"]),
        )
        self.assertEqual(
            "exactly_empty_control_isolation_directory_no_files_or_subdirectories",
            boundary["workspace_layout"],
        )
        acl = boundary["acl_and_xattr_policy"]
        self.assertIs(False, acl["default_acl_permitted"])
        self.assertIs(False, acl["detectable_extended_acl_permitted"])
        self.assertIs(False, acl["detectable_xattr_permitted"])
        self.assertIs(
            False,
            lifecycle[
                "protected_source_bytes_or_source_derived_content_bearing_material_persistent_retention_permitted"
            ],
        )
        self.assertIs(False, lifecycle["partial_attempt_retention_permitted"])
        recovery = lifecycle["recovery_boundary"]
        self.assertIs(False, recovery["sigkill_same_process_cleanup_claimed"])
        self.assertIs(False, recovery["power_loss_or_process_crash_same_process_cleanup_claimed"])
        self.assertEqual("required_not_implemented", recovery["future_supervisor_status"])
        self.assertEqual(
            "required_not_implemented",
            recovery["ledger_and_stale_recovery_status"],
        )
        self.assertEqual("missing_not_implemented", recovery["ledger_closed_schema_status"])
        crash_rule = recovery["destructive_cleanup_crash_evidence_rule"]
        self.assertIs(
            False,
            crash_rule[
                "restart_may_reconstruct_verified_success_deletion_record_from_workspace_absence_or_namespace_state"
            ],
        )
        self.assertIn(
            "cleanup_uncertainty",
            crash_rule["durable_valid_deletion_record_absent_after_empty_workspace_rmdir"],
        )
        self.assertEqual(
            "missing_not_implemented",
            recovery["ledger_lifecycle_state_machine_status"],
        )
        ledger_requirements = recovery["future_ledger_protocol_requirements"]
        self.assertIs(True, ledger_requirements["initial_create_atomic_no_replace_required"])
        self.assertIs(True, ledger_requirements["initial_create_before_workspace_required"])
        publication_protocol = ledger_requirements["publication_protocol"]
        self.assertIn("RENAME_NOREPLACE", publication_protocol)
        self.assertLess(
            publication_protocol.index("file_fsync"),
            publication_protocol.index("RENAME_NOREPLACE"),
        )
        self.assertIs(
            False,
            ledger_requirements["mutable_ledger_file_pointer_alias_or_content_update_permitted"],
        )
        self.assertEqual(
            "hard_block_without_workspace_derivation_or_child_deletion",
            ledger_requirements["malformed_tampered_or_stale_ledger_disposition"],
        )
        self.assertIs(
            False,
            ledger_requirements[
                "readable_content_bearing_leaf_or_workspace_descriptor_reopen_during_cleanup_or_recovery_permitted"
            ],
        )
        self.assertIn(
            "must_newly_safe_open",
            ledger_requirements["process_restart_management_open_protocol"],
        )
        staging = recovery["orphan_staging_generation_protocol"]
        self.assertEqual(2, len(staging["deletion_record_staging_crash_windows"]))
        self.assertEqual(
            2,
            len(staging["ledger_append_generation_staging_crash_windows"]),
        )
        self.assertEqual(
            2,
            len(staging["registry_append_generation_staging_crash_windows"]),
        )
        self.assertIn(
            "hard_block_without_guess_scan_derived_child_or_deletion",
            staging["unknown_malformed_duplicate_collision_or_mismatch_disposition"],
        )
        discovery = recovery["post_ledger_removal_deletion_record_discovery"]
        self.assertIn(
            "before_any_ledger_generation_unlink",
            discovery["attempt_registry_terminal_transition_order"],
        )
        self.assertIs(
            False,
            discovery["private_child_identifier_or_path_in_public_artifact_permitted"],
        )
        self.assertIs(
            True, recovery["recovery_derives_workspace_only_from_fixed_parent_and_opaque_child_id"]
        )
        self.assertIs(False, recovery["unmatched_ledger_or_workspace_deletion_permitted"])
        self.assertIn(
            "public_safe_workspace_id",
            recovery["future_closed_ledger_minimum_field_names"],
        )
        self.assertEqual(
            "absent_not_created",
            self.custody["deletion_record_specification"]["record_status"],
        )
        durable_record = self.custody["deletion_record_specification"][
            "durable_storage_and_recovery_protocol"
        ]
        self.assertEqual("required_not_implemented", durable_record["status"])
        self.assertIs(
            True,
            durable_record["content_free_record_durable_before_ledger_removal_required"],
        )
        durable_order = durable_record["required_clean_cleanup_order"]
        self.assertLess(
            durable_order.index("file_fsync_temporary_record_generation"),
            durable_order.index(
                "descriptor_relative_atomic_no_replace_publish_final_opaque_record_child"
            ),
        )
        self.assertEqual({False}, set(self.custody["nonclaims"].values()))
        self.assertIs(False, self.custody["nonclaims"]["rights_clearance_established"])
        self.assertIs(
            False,
            self.custody["nonclaims"]["redistribution_permission_established"],
        )
        artifacts = self.custody["artifact_boundaries"]
        self.assertIs(False, artifacts["source_content_log_generation_permitted"])
        self.assertEqual(
            "forbidden_filesystem_content_leaf_count_exact_zero_workspace_is_empty_control_isolation_boundary_only",
            artifacts["content_bearing_filesystem_material_location"],
        )
        leaf_profile = self.custody["custody_lifecycle"]["descriptor_pinned_filesystem_boundary"][
            "content_leaf_profile"
        ]
        self.assertEqual([], leaf_profile["registered_protected_leaf_roster_exact"])
        self.assertEqual(0, leaf_profile["registered_protected_leaf_roster_maximum"])
        self.assertIs(
            False, leaf_profile["any_content_leaf_intent_create_write_seal_or_reopen_permitted"]
        )
        stores = artifacts["content_free_control_and_evidence_store_boundary"]
        self.assertIs(
            True, stores["exact_source_or_source_derived_content_bearing_bytes_forbidden"]
        )
        self.assertIs(True, stores["owner_only_descriptor_pinned_fixed_parents_required"])
        memory = artifacts["protected_process_memory_boundary"]
        self.assertIs(True, memory["network_kernel_tls_and_process_memory_buffers_exist"])
        self.assertIs(False, memory["secure_erasure_or_zeroization_claimed"])
        self.assertIs(
            False,
            memory["kernel_root_same_uid_or_library_buffer_nonexposure_claimed"],
        )
        self.assertEqual(
            {
                "exact_response_body_bytes",
                "temporary_parser_inputs",
                "temporary_inspection_inputs",
            },
            set(artifacts["content_bearing_protected_material_includes"]),
        )
        metadata = set(artifacts["content_free_bounded_metadata_candidates_include"])
        self.assertLessEqual(
            {
                "pre_acquisition_attestation",
                "post_acquisition_execution_attestation",
                "pass_proof_bundle_ordinal_1",
                "pass_proof_bundle_ordinal_2",
                "exact6_terminal_decision",
            },
            metadata,
        )

    def test_authority_attempt_and_acquisition_evidence_form_a_pre_source_chain(self) -> None:
        blueprints = self.custody["future_protocol_prerequisite_blueprints"]
        authority = blueprints["authority_proof_bundle"]
        identifier_profile = authority["authority_grant_and_derived_identifier_profile"]
        vector = identifier_profile["fixed_test_vector"]
        self.assertEqual(
            {key: value for key, value in vector.items() if key != "authority_grant_id"},
            derive_grant_identifiers(vector["authority_grant_id"]),
        )
        self.assertEqual(
            7, len(set(derive_grant_identifiers(vector["authority_grant_id"]).values()))
        )
        for invalid_grant in (
            "grant-v1:" + "0" * 31,
            "grant-v1:" + "A" * 32,
            "grant-v1:" + "0" * 32 + "\n",
        ):
            with (
                self.subTest(invalid_grant=repr(invalid_grant)),
                self.assertRaises(CorpusFormatError),
            ):
                derive_grant_identifiers(invalid_grant)
        with patch("hashlib.sha256") as colliding_sha256:
            colliding_sha256.return_value.digest.return_value = b"\0" * 32
            with self.assertRaisesRegex(CorpusFormatError, "identifier collision"):
                derive_grant_identifiers(vector["authority_grant_id"])
        self.assertEqual(
            ["signed_authority_payload", "detached_authority_signature_envelope"],
            authority["required_bundle_roles_exact"],
        )
        self.assertIs(False, authority["bundle_self_hash_field_permitted"])
        self.assertIs(False, authority["runtime_self_issuance_or_self_approval_permitted"])
        self.assertIn(
            "exact_two_pre_authorized_pass_ids_and_ordinals_derived_from_authority_grant_id",
            authority["signed_authority_payload"]["required_bindings"],
        )
        authority_store = authority["local_durable_input_publication_and_retention"]
        self.assertIs(
            False, authority_store["bundle_payload_child_id_or_self_digest_field_permitted"]
        )
        self.assertIn(
            "authority_proof_sha256", authority_store["authority_proof_child_id_derivation"]
        )
        self.assertTrue(valid_published_git_oid("a" * 40))
        for invalid in ("a" * 39, "A" * 40, "a" * 40 + "\n", "a" * 39 + "\u2028"):
            with self.subTest(invalid=repr(invalid)):
                self.assertFalse(valid_published_git_oid(invalid))

        setup = blueprints["one_time_attempt_and_pre_source_setup"]
        order = setup["exact_order_before_first_network_or_source_request"]
        self.assertLess(
            order.index(
                "under_attempt_lease_staging_write_validate_file_fsync_RENAME_NOREPLACE_and_parent_fsync_one_time_attempt_reservation_binding_the_already_held_lock_role_and_key"
            ),
            order.index(
                "under_exclusive_lease_publish_INITIAL_LEDGER_DURABLE_generation_zero_via_authenticated_staging_write_validate_file_fsync_RENAME_NOREPLACE_ledger_parent_fsync_and_unique_contiguous_chain_revalidation"
            ),
        )
        self.assertLess(
            order.index(
                "under_exclusive_lease_publish_INITIAL_LEDGER_DURABLE_generation_zero_via_authenticated_staging_write_validate_file_fsync_RENAME_NOREPLACE_ledger_parent_fsync_and_unique_contiguous_chain_revalidation"
            ),
            order.index("o_excl_create_open_pin_and_revalidate_fresh_empty_workspace"),
        )
        self.assertEqual(
            "only_then_permit_first_authorized_source_request",
            order[-1],
        )

        acquisition = blueprints["acquisition_evidence"]
        preflight = acquisition["preflight_attestation"]
        execution = acquisition["execution_attestation"]
        self.assertEqual(
            self.source_contract["revision_receipt_requirement"]["fixed_request_profile"],
            preflight["parent_fixed_request_profile_exact_projection"],
        )
        self.assertIn("actual_response_status", preflight["forbidden_future_facts"])
        self.assertIn("actual_tls_or_hostname_success", preflight["forbidden_future_facts"])
        self.assertIn(
            "tls_certificate_validation_succeeded",
            execution["required_observed_facts"],
        )
        self.assertIn("revision_receipt_sha256", execution["required_bindings"])
        self.assertIn("acquisition_artifact_graph_sha256", execution["required_bindings"])
        self.assertEqual("missing_not_implemented", preflight["schema_and_runtime_status"])
        self.assertEqual("missing_not_implemented", execution["schema_and_runtime_status"])
        sequence = acquisition["source_request_sequence"]
        self.assertLess(
            sequence.index("validate_typed_acquisition_preflight_attestation"),
            sequence.index(
                "for_each_of_exactly_five_ordered_members_revalidate_exclusive_lease_require_no_retry_client_state_then_append_exactly_INTENT_N_DURABLE_before_dispatch_DISPATCH_N_CONFIRMED_DURABLE_after_synchronous_application_dispatch_confirmation_and_BODY_N_COMPLETE_DURABLE_after_complete_body_each_as_the_exact_next_immutable_generation_before_advancing"
            ),
        )
        self.assertLess(
            sequence.index(
                "construct_validate_and_digest_acyclic_acquisition_core_graph_without_execution_attestation"
            ),
            sequence.index(
                "construct_validate_and_digest_typed_acquisition_execution_attestation_binding_core_graph"
            ),
        )
        acquisition_graph = blueprints["artifact_graph_commitments"]["acquisition_graph"]
        self.assertNotIn(
            "ACQUISITION_STARTED_DURABLE_ledger_generation",
            acquisition_graph["exact_ordered_node_roles"],
        )
        self.assertNotIn(
            "acquisition_execution_attestation",
            acquisition_graph["exact_ordered_node_roles"],
        )
        registry_chain = setup["attempt_registry_generation_chain"]
        self.assertIs(
            False, registry_chain["old_generation_mutation_replacement_or_deletion_permitted"]
        )
        self.assertIn("RENAME_NOREPLACE", registry_chain["append_only_generation_protocol"])
        self.assertIs(False, registry_chain["mutable_head_object_or_pointer_permitted"])
        self.assertIn(
            "unique_contiguous_chain",
            registry_chain["append_only_generation_protocol"],
        )
        replay = self.custody["cross_artifact_verifier_contract"][
            "single_attempt_binding_and_replay_protection"
        ]
        self.assertIs(True, replay["artifact_graph_digest_exact_one_attempt_binding_required"])
        self.assertIs(False, replay["replay_or_reuse_permitted"])
        self.assertIn(
            "post_acquisition_execution_attestation",
            replay["attempt_id_exact_match_required_across"],
        )
        self.assertIn(
            "exact6_terminal_decision",
            replay["attempt_id_exact_match_required_across"],
        )

    def test_pass_and_terminal_blueprint_is_exact_six_and_conditionally_complete(self) -> None:
        blueprints = self.custody["future_protocol_prerequisite_blueprints"]
        pass_blueprint = blueprints["pass_proof_bundle"]
        self.assertEqual(
            ["pass_observation_payload", "detached_pass_proof_envelope"],
            pass_blueprint["bundle_roles_exact"],
        )
        self.assertIs(
            False,
            pass_blueprint["observation_payload_pass_id_seal_or_completeness_fields_permitted"],
        )
        proof_bindings = set(pass_blueprint["detached_pass_proof_envelope_required_bindings"])
        self.assertLessEqual(
            {
                "pass_ordinal",
                "pre_authorized_pass_id",
                "pass_observation_payload_sha256",
                "nullable_completeness_attestation_sha256",
                "completeness_applicability",
                "seal_sha256",
                "seal_domain_and_exact_proof_core_framing",
            },
            proof_bindings,
        )
        seal_profile = pass_blueprint["deterministic_pass_seal_profile"]
        self.assertEqual(PASS_SEAL_DOMAIN, seal_profile["digest_domain"])
        self.assertEqual(
            [
                "authority_proof_sha256",
                "attempt_id",
                "pass_ordinal",
                "pre_authorized_pass_id",
                "pass_observation_payload_sha256",
                "nullable_completeness_attestation_sha256",
                "completeness_applicability",
            ],
            seal_profile["proof_core_fields_exact"],
        )
        self.assertIs(
            False,
            seal_profile["signer_key_signature_authenticity_or_independence_claimed"],
        )
        self.assertIs(
            False,
            pass_blueprint["pass_seal_distinctness_only"][
                "blinding_authorship_authenticity_human_model_organizational_or_nonexposure_independence_proved"
            ],
        )
        slots = pass_blueprint["ordered_result_slots"]
        self.assertEqual(self.source_contract["ordered_inspection_roster"]["tasks"], slots)
        self.assertEqual(list(range(6)), [slot["index"] for slot in slots])
        self.assertEqual(list(LINK_IDS), [slot["link_id"] for slot in slots])
        self.assertEqual("excavation_location", slots[1]["unresolved_axis"])
        self.assertEqual(slots[4]["collision_group"], slots[5]["collision_group"])
        self.assertNotEqual(slots[4]["link_id"], slots[5]["link_id"])
        self.assertEqual("SF 3051", slots[4]["mackay_locator"]["identifier"])
        self.assertEqual("SF 2558", slots[5]["mackay_locator"]["identifier"])
        self.assertEqual("official_record_id", slots[0]["penn_locators"][0]["identifier_namespace"])
        self.assertEqual(
            7,
            len(pass_blueprint["pass_result_schema_requirements"]["closed_outcome_one_of"]),
        )
        locator_shape = pass_blueprint["pass_result_schema_requirements"]["locator_shape"]
        locator_re = re.compile(locator_shape["identifier_pattern"])
        self.assertEqual("official_record_id", locator_shape["identifier_namespace"])
        self.assertTrue(all(locator_re.fullmatch(record_id) for record_id in PENN_RECORD_IDS))
        self.assertIsNone(locator_re.fullmatch("SF 2000"))
        self.assertIn(
            "free_text", pass_blueprint["forbidden_channels_exact_parent_contract_plus_free_text"]
        )
        self.assertIs(
            False,
            pass_blueprint["pass_result_schema_requirements"][
                "explicit_source_rejection_requirements"
            ]["absence_or_inference_can_substitute"],
        )
        self.assertEqual(
            "missing_not_implemented",
            pass_blueprint["schema_isolation_runtime_and_seal_protocol_status"],
        )

        def vector(outcomes: list[str], *, locator_suffix: str = "") -> list[dict[str, Any]]:
            results = []
            for task, outcome in zip(PASS_SLOT_TASKS, outcomes, strict=True):
                result: dict[str, Any] = copy.deepcopy(task)
                result["outcome"] = outcome
                result["source_local_locator"] = (
                    {
                        "identifier": task["penn_locators"][0]["identifier"] + locator_suffix,
                        "identifier_namespace": "official_record_id",
                    }
                    if outcome == "exact_one_candidate"
                    else None
                )
                results.append(result)
            return results

        receipt_payload, _ = self.synthetic_receipt()
        revision_set_payload = self.synthetic_revision_set(receipt_payload)
        envelope_payload = self.synthetic_envelope(receipt_payload)
        authority_grant_id = "grant-v1:000102030405060708090a0b0c0d0e0f"
        derived_ids = derive_grant_identifiers(authority_grant_id)
        attestation = self.synthetic_attestation(receipt_payload, revision_set_payload)
        attestation_raw = canonical_payload(attestation)
        source_policy_sha256 = (
            "sha256:" + hashlib.sha256(SOURCE_POLICY_PATH.read_bytes()).hexdigest()
        )
        custody_contract_sha256 = "sha256:" + hashlib.sha256(self.custody_bytes).hexdigest()

        digest_definitions = self.custody["cross_artifact_verifier_contract"][
            "dynamic_digest_registry"
        ]["definitions"]
        raw_limits = self.custody["cross_artifact_verifier_contract"]["pre_schema_resource_limits"][
            "artifact_raw_maximum_bytes"
        ]
        acquisition_graph_profile = blueprints["artifact_graph_commitments"]["acquisition_graph"]
        self.assertEqual(
            list(_ACQUISITION_GRAPH_ROLES),
            acquisition_graph_profile["exact_ordered_node_roles"],
        )
        self.assertEqual(
            ACQUISITION_GRAPH_DOMAIN,
            acquisition_graph_profile["digest_domain"],
        )
        self.assertEqual(
            ACQUISITION_GRAPH_DOMAIN,
            digest_definitions["acquisition_artifact_graph_sha256"]["digest_domain"],
        )
        self.assertEqual(
            PASS_PROOF_DOMAIN,
            digest_definitions["pass_proof_bundle_sha256"]["digest_domain"],
        )
        self.assertEqual(
            PASS_OBSERVATION_DOMAIN,
            digest_definitions["pass_observation_payload_sha256"]["digest_domain"],
        )
        self.assertEqual(PASS_SEAL_DOMAIN, digest_definitions["seal_sha256"]["digest_domain"])
        self.assertEqual(
            _ACQUISITION_GRAPH_MAX_BYTES,
            raw_limits["acquisition_core_graph"],
        )
        self.assertEqual(
            _PASS_PROOF_MAX_BYTES,
            raw_limits["pass_proof_bundle_ordinal_1"],
        )
        self.assertEqual(
            _PASS_PROOF_MAX_BYTES,
            raw_limits["pass_proof_bundle_ordinal_2"],
        )
        self.assertNotIn("pass_observation_payload", raw_limits)
        for role, (domain, maximum_bytes, _schema_path) in _RAW_ARTIFACT_PROFILES.items():
            digest_key, raw_limit_key = _RAW_PROFILE_CONTRACT_KEYS[role]
            with self.subTest(exact_raw_profile=role):
                self.assertEqual(
                    domain,
                    digest_definitions[digest_key]["digest_domain"],
                )
                self.assertEqual(maximum_bytes, raw_limits[raw_limit_key])

        def control_payload(
            role: str,
            grant_id: str,
            parent_bindings: dict[str, str],
            distribution_handle: ValidatedRuntimeDistributionHandle | None = None,
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "artifact_role": role,
                "artifact_state": _CONTROL_ARTIFACT_STATE_BY_ROLE[role],
                "artifact_version": "v1",
                "attempt_id": derive_grant_identifiers(grant_id)["attempt_id"],
                "authority_grant_id": grant_id,
                "parent_bindings": parent_bindings,
            }
            if role == "transitive_runtime_input_manifest":
                if distribution_handle is None:
                    raise AssertionError("runtime manifest needs a distribution")
                payload["members"] = runtime_distribution_manifest_members(distribution_handle)
            return payload

        def resolved_graph(
            *,
            grant_id: str = authority_grant_id,
            bound_receipt: dict[str, Any] = receipt_payload,
            bound_envelope: dict[str, Any] = envelope_payload,
            bound_revision_set: dict[str, Any] = revision_set_payload,
        ) -> ValidatedAcquisitionGraphHandle:
            identifiers = derive_grant_identifiers(grant_id)
            attempt_id = identifiers["attempt_id"]
            distribution = resolve_runtime_distribution_handle(RUNTIME_DISTRIBUTION_VECTOR)
            runtime_bindings = runtime_distribution_manifest_bindings(distribution)
            runtime = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload(
                        "transitive_runtime_input_manifest",
                        grant_id,
                        runtime_bindings,
                        distribution,
                    )
                ),
                role="transitive_runtime_input_manifest",
                expected_parent_bindings=runtime_bindings,
                runtime_distribution=distribution,
            )
            authority_bindings = recompute_authority_static_bindings(runtime)
            authority = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload("authority_proof_bundle", grant_id, authority_bindings)
                ),
                role="authority_proof_bundle",
                expected_parent_bindings=authority_bindings,
            )
            reservation_bindings = {"authority_proof_sha256": authority.artifact_sha256}
            reservation = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload("one_time_attempt_reservation", grant_id, reservation_bindings)
                ),
                role="one_time_attempt_reservation",
                expected_parent_bindings=reservation_bindings,
            )
            registry_bindings = {
                "attempt_reservation_sha256": reservation.artifact_sha256,
                "authority_proof_sha256": authority.artifact_sha256,
            }
            registry = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload(
                        "attempt_registry_generation",
                        grant_id,
                        registry_bindings,
                    )
                ),
                role="attempt_registry_generation",
                expected_parent_bindings=registry_bindings,
            )
            preflight_bindings = {
                "attempt_registry_generation_sha256": registry.artifact_sha256,
                "attempt_reservation_sha256": reservation.artifact_sha256,
                "authority_proof_sha256": authority.artifact_sha256,
            }
            preflight = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload("pre_acquisition_attestation", grant_id, preflight_bindings)
                ),
                role="pre_acquisition_attestation",
                expected_parent_bindings=preflight_bindings,
            )
            receipt_handle = resolve_receipt_handle(
                canonical_payload(bound_receipt),
                validators=self.validators,
                authority_grant_id=grant_id,
                attempt_id=attempt_id,
            )
            envelope_handle = resolve_envelope_handle(
                canonical_payload(bound_envelope),
                validators=self.validators,
                receipt=receipt_handle,
            )
            revision_handle = resolve_revision_set_handle(
                canonical_payload(bound_revision_set),
                validators=self.validators,
                receipt=receipt_handle,
            )
            prerequisites = (
                authority,
                reservation,
                registry,
                preflight,
                receipt_handle,
                envelope_handle,
                revision_handle,
            )
            payload = {
                "attempt_id": attempt_id,
                "authority_proof_sha256": authority.artifact_sha256,
                "graph_phase": "post_acquisition_pre_execution_attestation_core",
                "graph_version": "v1",
                "ordered_node_role_and_domain_digest_pairs": [
                    graph_node_reference(index, handle)
                    for index, handle in enumerate(prerequisites)
                ],
            }
            return resolve_acquisition_graph_handle(
                canonical_payload(payload),
                prerequisites=prerequisites,
            )

        def resolved_runtime_and_execution(
            graph: ValidatedAcquisitionGraphHandle,
        ) -> tuple[ValidatedRawArtifactHandle, ValidatedRawArtifactHandle]:
            authority = prerequisite_by_role(graph, "authority_proof_bundle")
            preflight = prerequisite_by_role(graph, "pre_acquisition_attestation")
            distribution = resolve_runtime_distribution_handle(RUNTIME_DISTRIBUTION_VECTOR)
            runtime_bindings = runtime_distribution_manifest_bindings(distribution)
            runtime = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload(
                        "transitive_runtime_input_manifest",
                        graph.authority_grant_id,
                        runtime_bindings,
                        distribution,
                    )
                ),
                role="transitive_runtime_input_manifest",
                expected_parent_bindings=runtime_bindings,
                runtime_distribution=distribution,
            )
            resolve_static_binding_set(authority=authority, runtime_manifest=runtime)
            execution_bindings = {
                "acquisition_artifact_graph_sha256": graph.artifact_sha256,
                "acquisition_preflight_attestation_sha256": preflight.artifact_sha256,
                "authority_proof_sha256": authority.artifact_sha256,
                "receipt_commitment_envelope_sha256": (graph.receipt_commitment_envelope_sha256),
                "revision_receipt_sha256": graph.revision_receipt_sha256,
                "source_revision_sha256": graph.source_revision_sha256,
                "transitive_runtime_input_manifest_sha256": runtime.artifact_sha256,
            }
            execution = resolve_control_artifact_handle(
                canonical_payload(
                    control_payload(
                        "post_acquisition_execution_attestation",
                        graph.authority_grant_id,
                        execution_bindings,
                    )
                ),
                role="post_acquisition_execution_attestation",
                expected_parent_bindings=execution_bindings,
            )
            return runtime, execution

        def resolved_proofs(
            graph: ValidatedAcquisitionGraphHandle,
            first_results: list[dict[str, Any]],
            second_results: list[dict[str, Any]],
            *,
            completeness_digests: tuple[str | None, str | None] = (None, None),
            pass_ids: tuple[str, str] | None = None,
        ) -> tuple[ValidatedPassProofHandle, ValidatedPassProofHandle]:
            identifiers = derive_grant_identifiers(graph.authority_grant_id)
            authority = prerequisite_by_role(graph, "authority_proof_bundle")
            preflight = prerequisite_by_role(graph, "pre_acquisition_attestation")
            runtime, execution = resolved_runtime_and_execution(graph)
            applicability = derive_completeness_applicability(first_results, second_results)
            effective_pass_ids = pass_ids or (
                identifiers["pre_authorized_pass_id_ordinal_1"],
                identifiers["pre_authorized_pass_id_ordinal_2"],
            )
            proofs: list[ValidatedPassProofHandle] = []
            for ordinal, (results, pass_id, completeness_digest) in enumerate(
                zip(
                    (first_results, second_results),
                    effective_pass_ids,
                    completeness_digests,
                    strict=True,
                ),
                start=1,
            ):
                observation_payload = {
                    "acquisition_artifact_graph_sha256": graph.artifact_sha256,
                    "acquisition_execution_attestation_sha256": execution.artifact_sha256,
                    "acquisition_preflight_attestation_sha256": preflight.artifact_sha256,
                    "attempt_id": graph.attempt_id,
                    "authority_proof_sha256": authority.artifact_sha256,
                    "custody_contract_sha256": custody_contract_sha256,
                    "exact_six_ordered_result_slots": results,
                    "ordered_source_roster_sha256": (
                        "sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f"
                    ),
                    "receipt_commitment_envelope_sha256": (
                        graph.receipt_commitment_envelope_sha256
                    ),
                    "revision_receipt_sha256": graph.revision_receipt_sha256,
                    "source_contract_sha256": CONTRACT_SHA256,
                    "source_policy_sha256": source_policy_sha256,
                    "source_revision_sha256": graph.source_revision_sha256,
                    "transitive_runtime_input_manifest_sha256": runtime.artifact_sha256,
                }
                observation_sha256 = tagged_digest(PASS_OBSERVATION_DOMAIN, observation_payload)
                proof_core = {
                    "attempt_id": graph.attempt_id,
                    "authority_proof_sha256": authority.artifact_sha256,
                    "completeness_applicability": applicability,
                    "nullable_completeness_attestation_sha256": completeness_digest,
                    "pass_observation_payload_sha256": observation_sha256,
                    "pass_ordinal": ordinal,
                    "pre_authorized_pass_id": pass_id,
                }
                proof_payload = {
                    "bundle_version": "v1",
                    "detached_pass_proof_envelope": {
                        "proof_core": proof_core,
                        "seal_sha256": tagged_digest(PASS_SEAL_DOMAIN, proof_core),
                    },
                    "pass_observation_payload": observation_payload,
                }
                proofs.append(
                    resolve_pass_proof_handle(
                        canonical_payload(proof_payload),
                        graph=graph,
                        runtime_manifest=runtime,
                        execution_attestation=execution,
                    )
                )
            return proofs[0], proofs[1]

        def resolved_completeness(
            raw: bytes,
            *,
            graph: ValidatedAcquisitionGraphHandle,
            proof: ValidatedPassProofHandle,
            bound_receipt: ValidatedRawArtifactHandle | None = None,
            bound_envelope: ValidatedRawArtifactHandle | None = None,
            bound_revision_set: ValidatedRawArtifactHandle | None = None,
        ) -> ValidatedCompletenessHandle:
            return resolve_completeness_handle(
                raw,
                receipt=bound_receipt
                or prerequisite_by_role(graph, "source_revision_receipt_payload"),
                envelope=bound_envelope
                or prerequisite_by_role(graph, "receipt_commitment_envelope"),
                revision_set=bound_revision_set
                or prerequisite_by_role(graph, "source_revision_set_payload"),
                validators=self.validators,
                graph=graph,
                proof=proof,
            )

        graph = resolved_graph()
        candidates = vector(["exact_one_candidate"] * 6)
        candidate_proofs = resolved_proofs(graph, candidates, copy.deepcopy(candidates))
        self.assertEqual(
            "not_applicable_no_row_absent_observation",
            derive_completeness_applicability(candidates, copy.deepcopy(candidates)),
        )
        self.assertEqual(
            ["source_reported_link"] * 6,
            evaluate_terminal_rows(graph, candidate_proofs),
        )

        different_candidate = copy.deepcopy(candidates)
        different_candidate[0]["source_local_locator"] = {
            "identifier": "83829",
            "identifier_namespace": "official_record_id",
        }
        different_proofs = resolved_proofs(graph, candidates, different_candidate)
        states = evaluate_terminal_rows(graph, different_proofs)
        self.assertEqual("unresolved", states[0])
        self.assertEqual(["source_reported_link"] * 5, states[1:])

        row_absent = copy.deepcopy(candidates)
        row_absent[2]["outcome"] = "row_absent"
        row_absent[2]["source_local_locator"] = None
        self.assertEqual(
            "applicable_parent_zero_count_payload_permitted",
            derive_completeness_applicability(row_absent, copy.deepcopy(row_absent)),
        )
        completeness_digest = tagged_digest(COMPLETENESS_DOMAIN, attestation)
        complete_proofs = resolved_proofs(
            graph,
            row_absent,
            copy.deepcopy(row_absent),
            completeness_digests=(completeness_digest, completeness_digest),
        )
        first_handle = resolved_completeness(attestation_raw, graph=graph, proof=complete_proofs[0])
        second_handle = resolved_completeness(
            attestation_raw, graph=graph, proof=complete_proofs[1]
        )
        states = evaluate_terminal_rows(
            graph,
            complete_proofs,
            completeness_handles=(first_handle, second_handle),
        )
        self.assertEqual("no_link", states[2])

        zero_reference_proofs = resolved_proofs(graph, row_absent, copy.deepcopy(row_absent))
        zero_reference_states = evaluate_terminal_rows(graph, zero_reference_proofs)
        self.assertEqual("unresolved", zero_reference_states[2])

        one_reference_proofs = resolved_proofs(
            graph,
            row_absent,
            copy.deepcopy(row_absent),
            completeness_digests=(completeness_digest, None),
        )
        one_reference_handle = resolved_completeness(
            attestation_raw, graph=graph, proof=one_reference_proofs[0]
        )
        one_reference_states = evaluate_terminal_rows(
            graph,
            one_reference_proofs,
            completeness_handles=(one_reference_handle, None),
        )
        self.assertEqual("unresolved", one_reference_states[2])
        self.assertEqual(
            "one_valid_nonnull",
            derive_completeness_reference_state(
                "applicable_parent_zero_count_payload_permitted",
                graph,
                one_reference_proofs,
                (one_reference_handle, None),
            ),
        )

        second_only_proofs = resolved_proofs(
            graph,
            row_absent,
            copy.deepcopy(row_absent),
            completeness_digests=(None, completeness_digest),
        )
        second_only_handle = resolved_completeness(
            attestation_raw, graph=graph, proof=second_only_proofs[1]
        )
        second_only_states = evaluate_terminal_rows(
            graph,
            second_only_proofs,
            completeness_handles=(None, second_only_handle),
        )
        self.assertEqual("unresolved", second_only_states[2])
        with self.assertRaisesRegex(CorpusFormatError, "binding|ordinal"):
            evaluate_terminal_rows(
                graph,
                second_only_proofs,
                completeness_handles=(second_only_handle, None),
            )

        with self.assertRaisesRegex(CorpusFormatError, "unresolved"):
            evaluate_terminal_rows(
                graph,
                one_reference_proofs,
                completeness_handles=("sha256:" + "a" * 64, None),  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(CorpusFormatError, "extraneous"):
            evaluate_terminal_rows(
                graph,
                candidate_proofs,
                completeness_handles=(first_handle, None),
            )

        mixed_unresolved = copy.deepcopy(row_absent)
        mixed_unresolved[5]["outcome"] = "valid_unresolved_ambiguous"
        mixed_unresolved[5]["source_local_locator"] = None
        self.assertEqual(
            "applicable_but_payload_forbidden_due_valid_U",
            derive_completeness_applicability(row_absent, mixed_unresolved),
        )
        mixed_proofs = resolved_proofs(graph, row_absent, mixed_unresolved)
        states = evaluate_terminal_rows(graph, mixed_proofs)
        self.assertEqual("unresolved", states[2])
        self.assertEqual("unresolved", states[5])
        self.assertEqual("source_reported_link", states[0])
        with self.assertRaisesRegex(CorpusFormatError, "extraneous"):
            evaluate_terminal_rows(
                graph,
                mixed_proofs,
                completeness_handles=(first_handle, None),
            )
        self.assertIs(
            True,
            self.source_contract["inspection_procedure"]["future_completeness_attestation"][
                "two_pass_digest_equality_required"
            ],
        )
        terminal_graph = blueprints["artifact_graph_commitments"]["terminal_graph"]
        self.assertNotIn(
            "completeness_attestation_payload",
            terminal_graph["base_exact_ordered_node_roles"],
        )
        self.assertIn(
            "append_exactly_one_completeness_attestation_payload_at_index_5_iff",
            terminal_graph["conditional_sixth_node_rule"],
        )

        explicit = copy.deepcopy(candidates)
        explicit[3]["outcome"] = "explicit_source_rejection"
        explicit[3]["source_local_locator"] = None
        explicit_proofs = resolved_proofs(graph, explicit, copy.deepcopy(explicit))
        states = evaluate_terminal_rows(graph, explicit_proofs)
        self.assertEqual("no_link", states[3])
        mismatch = copy.deepcopy(explicit)
        mismatch[3]["outcome"] = "row_absent"
        mismatch_proofs = resolved_proofs(graph, explicit, mismatch)
        states = evaluate_terminal_rows(graph, mismatch_proofs)
        self.assertEqual("unresolved", states[3])

        with self.assertRaisesRegex(CorpusFormatError, "pass or graph binding"):
            bad_digest_proofs = resolved_proofs(
                graph,
                row_absent,
                copy.deepcopy(row_absent),
                completeness_digests=("sha256:" + "a" * 64, None),
            )
            resolved_completeness(attestation_raw, graph=graph, proof=bad_digest_proofs[0])
        wrong_parent_receipt_payload = copy.deepcopy(receipt_payload)
        wrong_parent_receipt_payload["members"][0]["retrieved_at"] = "2026-01-02T03:04:09Z"
        wrong_parent_receipt = resolve_receipt_handle(
            canonical_payload(wrong_parent_receipt_payload),
            validators=self.validators,
            authority_grant_id=graph.authority_grant_id,
            attempt_id=graph.attempt_id,
        )
        with self.assertRaisesRegex(
            CorpusFormatError,
            "typed receipt envelope digest mismatch|parent binding",
        ):
            resolved_completeness(
                attestation_raw,
                graph=graph,
                proof=complete_proofs[0],
                bound_receipt=wrong_parent_receipt,
            )
        wrong_schema = copy.deepcopy(attestation)
        wrong_schema["unexpected"] = 0
        with self.assertRaisesRegex(CorpusFormatError, "schema mismatch"):
            resolved_completeness(
                canonical_payload(wrong_schema),
                graph=graph,
                proof=complete_proofs[0],
            )

        tampered_graph = replace(graph, canonical_size=graph.canonical_size + 1)
        with self.assertRaisesRegex(CorpusFormatError, "tampered"):
            evaluate_terminal_rows(
                tampered_graph,
                complete_proofs,
                completeness_handles=(first_handle, second_handle),
            )
        tampered_observation = replace(
            complete_proofs[0].pass_observation,
            pass_id=derived_ids["pre_authorized_pass_id_ordinal_2"],
        )
        tampered_observation_proof = replace(
            complete_proofs[0], pass_observation=tampered_observation
        )
        with self.assertRaisesRegex(CorpusFormatError, "tampered|binding"):
            evaluate_terminal_rows(
                graph,
                (tampered_observation_proof, complete_proofs[1]),
                completeness_handles=(first_handle, second_handle),
            )
        tampered_proof = replace(complete_proofs[0], artifact_sha256="sha256:" + "a" * 64)
        with self.assertRaisesRegex(CorpusFormatError, "tampered"):
            evaluate_terminal_rows(
                graph,
                (tampered_proof, complete_proofs[1]),
                completeness_handles=(first_handle, second_handle),
            )
        tampered_handle = replace(first_handle, raw=first_handle.raw + b" ")
        with self.assertRaisesRegex(CorpusFormatError, "tampered"):
            evaluate_terminal_rows(
                graph,
                complete_proofs,
                completeness_handles=(tampered_handle, second_handle),
            )
        with self.assertRaisesRegex(CorpusFormatError, "unresolved acquisition graph"):
            evaluate_terminal_rows(
                "sha256:" + "a" * 64,  # type: ignore[arg-type]
                complete_proofs,
                completeness_handles=(first_handle, second_handle),
            )
        with self.assertRaisesRegex(CorpusFormatError, "ordinal"):
            evaluate_terminal_rows(
                graph,
                (complete_proofs[1], complete_proofs[0]),
                completeness_handles=(second_handle, first_handle),
            )

        other_receipt_payload = copy.deepcopy(receipt_payload)
        other_receipt_payload["members"][0]["retrieved_at"] = "2026-01-02T03:04:09Z"
        other_revision_payload = self.synthetic_revision_set(other_receipt_payload)
        other_envelope_payload = self.synthetic_envelope(other_receipt_payload)
        other_graph = resolved_graph(
            bound_receipt=other_receipt_payload,
            bound_envelope=other_envelope_payload,
            bound_revision_set=other_revision_payload,
        )
        other_graph_proofs = resolved_proofs(other_graph, row_absent, copy.deepcopy(row_absent))
        with self.assertRaisesRegex(CorpusFormatError, "graph|binding"):
            evaluate_terminal_rows(graph, other_graph_proofs)

        other_grant = "grant-v1:101112131415161718191a1b1c1d1e1f"
        other_attempt_graph = resolved_graph(grant_id=other_grant)
        other_attempt_proofs = resolved_proofs(
            other_attempt_graph, row_absent, copy.deepcopy(row_absent)
        )
        with self.assertRaisesRegex(CorpusFormatError, "graph|binding|attempt"):
            evaluate_terminal_rows(graph, other_attempt_proofs)

        wrong_pass_payload = copy.deepcopy(complete_proofs[0].payload)
        wrong_pass_payload["detached_pass_proof_envelope"]["proof_core"][
            "pre_authorized_pass_id"
        ] = derived_ids["pre_authorized_pass_id_ordinal_2"]
        with self.assertRaisesRegex(CorpusFormatError, "pass|binding"):
            resolve_pass_proof_handle(
                canonical_payload(wrong_pass_payload),
                graph=graph,
                runtime_manifest=complete_proofs[0].runtime_manifest,
                execution_attestation=complete_proofs[0].execution_attestation,
            )

        old_wrong_graph_domain = "indusbench:source-reported-link:acquisition-core-graph:v1"
        wrong_domain_graph = replace(
            graph,
            artifact_sha256=tagged_digest(old_wrong_graph_domain, graph.payload),
        )
        with self.assertRaisesRegex(CorpusFormatError, "tampered.*digest"):
            evaluate_terminal_rows(wrong_domain_graph, candidate_proofs)
        old_wrong_proof_domain = "indusbench:source-reported-link:pass-proof-bundle:v1"
        wrong_domain_proof = replace(
            candidate_proofs[0],
            artifact_sha256=tagged_digest(old_wrong_proof_domain, candidate_proofs[0].payload),
        )
        with self.assertRaisesRegex(CorpusFormatError, "tampered.*digest"):
            evaluate_terminal_rows(
                graph,
                (wrong_domain_proof, candidate_proofs[1]),
            )

        oversized_bundle = b"{" + b" " * _PASS_PROOF_MAX_BYTES + b"}"
        with self.assertRaisesRegex(CorpusFormatError, "exceeds bound"):
            resolve_pass_proof_handle(
                oversized_bundle,
                graph=graph,
                runtime_manifest=complete_proofs[0].runtime_manifest,
                execution_attestation=complete_proofs[0].execution_attestation,
            )
        oversized_graph = b"{" + b" " * _ACQUISITION_GRAPH_MAX_BYTES + b"}"
        with self.assertRaisesRegex(CorpusFormatError, "exceeds bound"):
            resolve_acquisition_graph_handle(
                oversized_graph,
                prerequisites=graph.ordered_prerequisites,
            )

        omitted_nested_observation = copy.deepcopy(complete_proofs[0].payload)
        omitted_nested_observation.pop("pass_observation_payload")
        with self.assertRaisesRegex(CorpusFormatError, "not closed"):
            resolve_pass_proof_handle(
                canonical_payload(omitted_nested_observation),
                graph=graph,
                runtime_manifest=complete_proofs[0].runtime_manifest,
                execution_attestation=complete_proofs[0].execution_attestation,
            )
        changed_nested_observation = copy.deepcopy(complete_proofs[0].payload)
        changed_nested_result = changed_nested_observation["pass_observation_payload"][
            "exact_six_ordered_result_slots"
        ][0]
        changed_nested_result["outcome"] = "row_absent"
        changed_nested_result["source_local_locator"] = None
        with self.assertRaisesRegex(CorpusFormatError, "proof core binding"):
            resolve_pass_proof_handle(
                canonical_payload(changed_nested_observation),
                graph=graph,
                runtime_manifest=complete_proofs[0].runtime_manifest,
                execution_attestation=complete_proofs[0].execution_attestation,
            )

        wrong_roster_payload = copy.deepcopy(graph.payload)
        (
            wrong_roster_payload["ordered_node_role_and_domain_digest_pairs"][0],
            (wrong_roster_payload["ordered_node_role_and_domain_digest_pairs"][1]),
        ) = (
            wrong_roster_payload["ordered_node_role_and_domain_digest_pairs"][1],
            wrong_roster_payload["ordered_node_role_and_domain_digest_pairs"][0],
        )
        with self.assertRaisesRegex(CorpusFormatError, "exact resolved node roster"):
            resolve_acquisition_graph_handle(
                canonical_payload(wrong_roster_payload),
                prerequisites=graph.ordered_prerequisites,
            )
        registry_handle = prerequisite_by_role(graph, "attempt_registry_generation")
        wrong_registry_state = copy.deepcopy(registry_handle.payload)
        wrong_registry_state["artifact_state"] = "PREFLIGHT_BOUND_DURABLE"
        with self.assertRaisesRegex(CorpusFormatError, "closed binding mismatch"):
            resolve_control_artifact_handle(
                canonical_payload(wrong_registry_state),
                role="attempt_registry_generation",
                expected_parent_bindings=registry_handle.payload["parent_bindings"],
            )

        untyped_prerequisites = list(graph.ordered_prerequisites)
        untyped_prerequisites[4] = receipt_payload  # type: ignore[assignment]
        with self.assertRaisesRegex(CorpusFormatError, "role order|typed raw"):
            resolve_acquisition_graph_handle(
                graph.raw,
                prerequisites=tuple(untyped_prerequisites),  # type: ignore[arg-type]
            )

        regex_only_seal = copy.deepcopy(complete_proofs[0].payload)
        regex_only_seal["detached_pass_proof_envelope"]["seal_sha256"] = "sha256:" + "a" * 64
        with self.assertRaisesRegex(CorpusFormatError, "seal recomputation"):
            resolve_pass_proof_handle(
                canonical_payload(regex_only_seal),
                graph=graph,
                runtime_manifest=complete_proofs[0].runtime_manifest,
                execution_attestation=complete_proofs[0].execution_attestation,
            )
        operational_failure = copy.deepcopy(candidates)
        operational_failure[0]["outcome"] = "inspection_failure"
        with self.assertRaisesRegex(CorpusFormatError, "invalid pass outcome"):
            derive_completeness_applicability(candidates, operational_failure)
        with self.assertRaisesRegex(CorpusFormatError, "exact six"):
            derive_completeness_applicability(candidates[:-1], candidates)
        reordered = copy.deepcopy(candidates)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        with self.assertRaisesRegex(CorpusFormatError, "order mismatch"):
            derive_completeness_applicability(candidates, reordered)
        collision_merged = copy.deepcopy(candidates)
        collision_merged[5]["link_id"] = LINK_IDS[4]
        with self.assertRaisesRegex(CorpusFormatError, "order mismatch"):
            derive_completeness_applicability(candidates, collision_merged)
        altered_context = copy.deepcopy(candidates)
        altered_context[1]["unresolved_axis"] = None
        with self.assertRaisesRegex(CorpusFormatError, "context or order"):
            derive_completeness_applicability(candidates, altered_context)
        substituted_mackay_task = copy.deepcopy(candidates)
        substituted_mackay_task[5]["mackay_locator"] = copy.deepcopy(
            substituted_mackay_task[4]["mackay_locator"]
        )
        with self.assertRaisesRegex(CorpusFormatError, "context or order"):
            derive_completeness_applicability(candidates, substituted_mackay_task)
        dropped_penn_locator = copy.deepcopy(candidates)
        dropped_penn_locator[0]["penn_locators"].pop()
        with self.assertRaisesRegex(CorpusFormatError, "context or order"):
            derive_completeness_applicability(candidates, dropped_penn_locator)
        mutated_slot_official_id = copy.deepcopy(candidates)
        mutated_slot_official_id[0]["penn_locators"][0]["identifier"] = "83829"
        with self.assertRaisesRegex(CorpusFormatError, "context or order"):
            derive_completeness_applicability(candidates, mutated_slot_official_id)
        extra_channel = copy.deepcopy(candidates)
        extra_channel[0]["free_text"] = "forbidden"
        with self.assertRaisesRegex(CorpusFormatError, "forbidden channel"):
            derive_completeness_applicability(candidates, extra_channel)
        malformed_locator = copy.deepcopy(candidates)
        malformed_locator[0]["source_local_locator"]["identifier"] = "SF 2000"
        with self.assertRaisesRegex(CorpusFormatError, "locator grammar"):
            derive_completeness_applicability(candidates, malformed_locator)
        null_candidate = copy.deepcopy(candidates)
        null_candidate[0]["source_local_locator"] = None
        with self.assertRaisesRegex(CorpusFormatError, "locator shape"):
            derive_completeness_applicability(candidates, null_candidate)
        locator_on_noncandidate = copy.deepcopy(row_absent)
        locator_on_noncandidate[2]["source_local_locator"] = {
            "identifier": "149372",
            "identifier_namespace": "official_record_id",
        }
        with self.assertRaisesRegex(CorpusFormatError, "must be null"):
            derive_completeness_applicability(row_absent, locator_on_noncandidate)

    def test_owner_only_review_is_self_cycle_free_and_publication_remains_blocked(self) -> None:
        boundaries = self.custody["artifact_boundaries"]
        self.assertIs(
            False, boundaries["public_or_repository_dynamic_evidence_retention_permitted"]
        )
        self.assertIs(
            False,
            boundaries[
                "public_or_repository_operational_timestamp_private_audit_digest_or_result_retention_permitted"
            ],
        )
        mandatory = boundaries["mandatory_content_free_control_retention_by_reached_branch"]
        self.assertIn(
            "selected_canonical_authority_proof_bundle_copy",
            mandatory["always_after_durable_reservation_exact"],
        )
        conditional_roles = mandatory["conditional_role_rules_exact"]
        self.assertIn("custody_deletion_record", conditional_roles)
        self.assertIn(
            "valid_signed_internal_retention_review_proof_control_child",
            conditional_roles,
        )
        review = self.custody["future_protocol_prerequisite_blueprints"][
            "internal_retention_review_proof_bundle"
        ]
        self.assertIs(False, review["proof_bundle_self_hash_field_permitted"])
        self.assertIs(False, review["review_proof_in_its_own_bound_roster_permitted"])
        self.assertIs(False, review["runtime_self_approval_permitted"])
        scientific_without = set(review["scientific_subject_roles_without_completeness_exact"])
        scientific_with = set(review["scientific_subject_roles_with_completeness_exact"])
        self.assertNotIn("internal_retention_review_proof_bundle", scientific_without)
        self.assertIn("exact6_terminal_decision", scientific_without)
        self.assertEqual(
            {"completeness_attestation_payload"},
            scientific_with - scientific_without,
        )
        self.assertIn(
            "at_least_one_fully_resolved_valid_nonnull_pass_reference",
            review["completeness_subject_rule"],
        )
        retention = self.custody["future_protocol_prerequisite_blueprints"][
            "owner_only_atomic_retention_batch"
        ]
        review_controls = set(
            review["control_binding_roles_exact_separate_from_scientific_subjects"]
        )
        self.assertEqual(6, len(review_controls))
        self.assertTrue(review_controls.isdisjoint(scientific_with))
        batch_roles = set(retention["base_required_payload_member_roles_exact"])
        self.assertEqual(
            scientific_without,
            batch_roles - {"internal_retention_review_proof_bundle"},
        )
        self.assertIs(
            False,
            review["review_payload_schema_exact"][
                "review_proof_digest_signature_manifest_receipt_review_or_later_registry_generation_field_permitted"
            ],
        )
        self.assertNotIn(
            "internal_retention_review_proof_bundle_sha256",
            retention["batch_receipt"]["exact_payload_bindings"],
        )
        self.assertEqual(
            ["approved", "denied"],
            self.custody["cross_artifact_verifier_contract"]["internal_retention_review_gate"][
                "authenticated_review_outcome_exactly_one_of"
            ],
        )
        registry_states = self.custody["future_protocol_prerequisite_blueprints"][
            "one_time_attempt_and_pre_source_setup"
        ]["attempt_registry_generation_chain"]["closed_attempt_registry_states"]
        self.assertIn("REVIEW_APPROVED_DURABLE", registry_states)
        self.assertIn("REVIEW_DENIED_DURABLE", registry_states)
        self.assertIn("RETENTION_COMMITTED", registry_states)
        self.assertNotIn("BATCH_FINAL_DURABLE", registry_states)
        self.assertNotIn("RECEIPT_DURABLE", registry_states)
        custody_validator = self.validators[CUSTODY_SCHEMA_PATH]
        public_mutation = copy.deepcopy(self.custody)
        public_mutation["artifact_boundaries"][
            "public_or_repository_dynamic_evidence_retention_permitted"
        ] = True
        self.assertTrue(list(custody_validator.iter_errors(public_mutation)))
        premature_mutation = copy.deepcopy(self.custody)
        premature_mutation["cross_artifact_verifier_contract"][
            "verified_cleanup_owner_only_retention_gate"
        ]["cleanup_before_scientific_evidence_owner_only_retention_required"] = False
        self.assertTrue(list(custody_validator.iter_errors(premature_mutation)))

    def test_dynamic_schema_set_is_exactly_committed_without_a_self_cycle(self) -> None:
        commitments = self.custody["artifact_schema_commitments"]
        self.assertEqual(4, commitments["schema_count"])
        self.assertEqual(4, len(commitments["schemas"]))
        self.assertEqual(list(range(4)), [entry["index"] for entry in commitments["schemas"]])
        for entry in commitments["schemas"]:
            schema_path = ROOT / entry["path"]
            payload = schema_path.read_bytes()
            with self.subTest(schema=entry["id"]):
                self.assertEqual(len(payload), entry["size"])
                self.assertEqual(
                    "sha256:" + hashlib.sha256(payload).hexdigest(),
                    entry["sha256"],
                )
                self.assertEqual(entry["id"], schema_path.name)
        digest_payload = {
            "schema_count": commitments["schema_count"],
            "schema_set_version": commitments["schema_set_version"],
            "schemas": commitments["schemas"],
        }
        self.assertEqual(
            tagged_digest(SCHEMA_SET_DOMAIN, digest_payload),
            commitments["schema_set_sha256"],
        )
        transition = self.custody["historical_transition"]
        self.assertEqual(
            commitments["schema_set_sha256"],
            transition["future_authority_binding"]["schema_set_sha256"],
        )
        self.assertNotIn("custody_contract_sha256", commitments)
        self.assertIs(
            True, transition["future_authority_binding"]["custody_contract_sha256_required"]
        )

    def test_embedded_deletion_record_schema_closes_success_failure_and_uncertainty(self) -> None:
        specification = self.custody["deletion_record_specification"]
        deletion_schema = specification["embedded_schema"]
        validator = Draft202012Validator(deletion_schema, format_checker=FormatChecker())
        custody_sha256 = "sha256:" + hashlib.sha256(self.custody_bytes).hexdigest()
        success = self.synthetic_deletion_record(custody_sha256)
        validator.validate(success)
        self.assertEqual(
            "eligible_for_separate_internal_retention_review",
            success["scientific_evidence_review_eligibility"],
        )

        clean_failure = copy.deepcopy(success)
        clean_failure["protected_content_cleanup_reason_code"] = "validation_failure"
        clean_failure["scientific_evidence_review_eligibility"] = "blocked"
        validator.validate(clean_failure)

        uncertainty = copy.deepcopy(success)
        uncertainty["cleanup_uncertainty_present"] = True
        uncertainty["cleanup_residue_status"] = "workspace_or_source_bytes_may_remain_unverified"
        uncertainty["protected_content_descriptor_count"] = None
        uncertainty["protected_content_descriptor_count_status"] = "unknown_or_above_record_bound"
        uncertainty["protected_content_descriptors_closed"] = None
        uncertainty["registered_protected_leaves_logically_unlinked"] = True
        uncertainty["scientific_evidence_review_eligibility"] = "blocked"
        uncertainty["protected_content_cleanup_reason_code"] = "cleanup_uncertainty"
        uncertainty["workspace_dentry_absent_from_pinned_parent_and_inode_detached"] = None
        validator.validate(uncertainty)

        bounded_uncertainty = copy.deepcopy(uncertainty)
        bounded_uncertainty["protected_content_descriptor_count"] = 64
        bounded_uncertainty["protected_content_descriptor_count_status"] = "exact_bounded_count"
        bounded_uncertainty["protected_content_descriptors_closed"] = False
        bounded_uncertainty["workspace_dentry_absent_from_pinned_parent_and_inode_detached"] = True
        validator.validate(bounded_uncertainty)

        mutations = []
        changed = copy.deepcopy(success)
        changed["unexpected"] = False
        mutations.append(changed)
        changed = copy.deepcopy(success)
        changed["cleanup_uncertainty_present"] = True
        mutations.append(changed)
        changed = copy.deepcopy(success)
        changed["contract_sha256"] += "\n"
        mutations.append(changed)
        changed = copy.deepcopy(success)
        changed["authority_proof_sha256"] += "\n"
        mutations.append(changed)
        changed = copy.deepcopy(success)
        changed["attempt_id"] = "../escape"
        mutations.append(changed)
        changed = copy.deepcopy(success)
        changed["protected_content_cleanup_started_at"] += "\n"
        mutations.append(changed)
        changed = copy.deepcopy(uncertainty)
        changed["protected_content_descriptor_count"] = 65
        changed["protected_content_descriptor_count_status"] = "unknown_or_above_record_bound"
        mutations.append(changed)
        changed = copy.deepcopy(uncertainty)
        changed["protected_content_descriptor_count"] = None
        changed["protected_content_descriptor_count_status"] = "exact_bounded_count"
        mutations.append(changed)
        for mutation in mutations:
            self.assertTrue(list(validator.iter_errors(mutation)))

        reversed_time = copy.deepcopy(success)
        reversed_time["protected_content_cleanup_started_at"] = "2026-01-02T03:05:01Z"
        validator.validate(reversed_time)
        cross = specification["cross_field_verifier"]
        self.assertIs(False, cross["schema_validity_alone_proves_timestamp_order"])
        self.assertIs(True, cross["protected_content_cleanup_ended_not_before_started_required"])
        self.assertIs(
            False,
            cross["protected_content_cleanup_ended_timestamp_proves_complete_custody_cleanup"],
        )
        self.assertIs(True, cross["contract_sha256_recomputation_required"])
        self.assertEqual("future_strict_verifier_not_implemented", cross["status"])
        semantics = specification["record_field_semantics"]
        self.assertIs(
            False,
            semantics[
                "external_kernel_root_same_uid_unregistered_descriptor_or_copy_absence_claimed"
            ],
        )
        self.assertIs(False, semantics["management_descriptor_absence_claimed_by_record"])
        self.assertIn("valid_unresolved", semantics["scientific_evidence_review_eligibility"])
        self.assertIn("signed_CSPRNG_authority_grant_id", semantics["attempt_id"])
        self.assertIn("signed_CSPRNG_authority_grant_id", semantics["workspace_id"])
        self.assertIn("not_a_claim", semantics["record_contains_source_content"])
        self.assertIn("not_a_claim", semantics["record_contains_workspace_path"])
        self.assertNotIn("source_content_present", success)
        self.assertNotIn("workspace_path_present", success)
        self.assertNotIn("ledger_terminally_reconciled_and_absent", success)

        deletion_record_digest = tagged_digest(DELETION_RECORD_DOMAIN, success)
        self.assertRegex(deletion_record_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("custody_deletion_record_sha256", success)

    def test_strict_verifier_remains_unimplemented_and_preflight_contract_is_frozen(
        self,
    ) -> None:
        verifier = self.custody["cross_artifact_verifier_contract"]
        self.assertEqual("not_implemented", verifier["status"])
        self.assertIs(False, verifier["schema_validity_alone_is_evidence"])
        canonical = verifier["canonical_input_verification"]
        self.assertIs(False, canonical["bom_permitted"])
        self.assertIs(False, canonical["duplicate_json_keys_permitted"])
        self.assertIs(False, canonical["finite_floats_permitted"])
        self.assertIs(True, canonical["raw_bytes_must_equal_indusbench_io_encode_json"])
        formats = verifier["format_assertion_profile"]
        self.assertIs(True, formats["format_checker_required"])
        self.assertEqual("lexical_shape_only", formats["last_modified"]["schema_scope"])
        self.assertIs(False, formats["last_modified"]["locale_dependency_permitted"])
        limits = verifier["pre_schema_resource_limits"]
        self.assertIs(
            True, limits["resource_limits_checked_before_json_decode_and_schema_validation"]
        )
        self.assertIs(True, limits["strict_utf8_decode_required"])
        self.assertEqual(
            "hard_reject", limits["unsupported_platform_or_missing_primitive_disposition"]
        )
        checks = verifier["ordered_checks"]
        self.assertEqual(
            {
                "branch_composition_exact",
                "cleanup_uncertainty_pipeline",
                "common_post_ledger_management_closure_pipeline",
                "common_static_authority_attempt_prefix",
                "evaluated_result_only_pipeline",
                "evaluated_verified_cleanup_and_terminal_control_pipeline",
                "evaluated_verified_cleanup_review_and_retention_pipeline",
                "guard_rules",
                "operational_failure_with_verified_cleanup_pipeline",
                "pre_source_setup_and_request_guarded",
                "pre_source_workspace_failure_pipelines",
                "successful_acquisition_core_and_execution_pipeline",
            },
            set(checks),
        )
        common = checks["common_static_authority_attempt_prefix"]
        self.assertLess(
            common.index("atomic_no_replace_attempt_reservation_file_fsync_and_parent_fsync"),
            common.index(
                "initial_attempt_registry_generation_staging_write_validate_file_fsync_RENAME_NOREPLACE_generation_zero_and_generation_parent_fsync_then_revalidate_unique_contiguous_chain_without_head_pointer"
            ),
        )
        pre_source = checks["pre_source_setup_and_request_guarded"]
        self.assertLess(
            pre_source.index(
                "typed_acquisition_preflight_attestation_raw_canonical_schema_domain_digest_and_pre_request_fact_binding"
            ),
            pre_source.index("only_then_issue_first_authorized_source_request"),
        )
        evaluated = checks["evaluated_result_only_pipeline"]
        self.assertLess(
            evaluated.index(
                "derive_conditional_completeness_applicability_from_both_pass_result_vectors"
            ),
            evaluated.index(
                "terminal_decision_exact_six_rows_parent_policy_precedence_mutual_exclusion_collision_conflict_and_conditional_completeness_recomputation"
            ),
        )
        cleanup = checks["evaluated_verified_cleanup_and_terminal_control_pipeline"]
        self.assertLess(
            cleanup.index("custody_deletion_record_embedded_schema_with_format_assertions"),
            cleanup.index("custody_deletion_record_verified_success_branch_check"),
        )
        closure = checks["common_post_ledger_management_closure_pipeline"]
        review = checks["evaluated_verified_cleanup_review_and_retention_pipeline"]
        self.assertLess(
            closure.index(
                "management_descriptor_closure_observation_domain_nul_digest_recomputation"
            ),
            len(closure),
        )
        self.assertLess(
            review.index(
                "detached_external_internal_retention_reviewer_signature_envelope_identity_trust_root_algorithm_domain_framing_and_payload_digest_check"
            ),
            review.index(
                "owner_only_retention_staging_only_after_durable_signed_approval_proof_and_every_prior_evaluated_check"
            ),
        )
        canonical_scope = verifier["canonical_input_verification"]
        self.assertEqual(21, len(canonical_scope["applies_to_all_typed_json_inputs"]))
        self.assertEqual(
            "raw_byte_resource_preflight",
            canonical_scope["per_artifact_required_order"][0],
        )
        retention_gate = verifier["verified_cleanup_owner_only_retention_gate"]
        self.assertIs(
            True,
            retention_gate["cleanup_before_scientific_evidence_owner_only_retention_required"],
        )
        self.assertIs(
            True,
            retention_gate[
                "owner_only_scientific_evidence_retention_requires_verified_success_deletion_record"
            ],
        )
        self.assertEqual(
            "missing_not_implemented",
            retention_gate["internal_retention_review_proof_bundle_schema_status"],
        )
        pass_gate = verifier["pass_proof_bundle_gate"]
        self.assertEqual(
            "missing_not_implemented",
            pass_gate["pass_proof_bundle_schema_status"],
        )
        self.assertEqual(
            "missing_not_implemented",
            pass_gate["seal_recomputation_protocol_status"],
        )
        self.assertIs(True, pass_gate["pass_id_and_seal_sha256_both_distinct_required"])
        self.assertEqual(
            "blocked",
            retention_gate[
                "operational_failure_or_cleanup_uncertainty_scientific_evidence_owner_only_retention"
            ],
        )
        self.assertIn(
            "separate_future_publication_contract",
            retention_gate["public_repository_or_scientific_result_release"],
        )
        locations = verifier["scientific_cross_binding_digest_output_subset"]
        self.assertIs(False, locations["generic_naked_digest_persistence_permitted"])
        self.assertIn("missing_not_implemented", locations["completeness_attestation_sha256"])
        self.assertIn("missing_not_implemented", locations["custody_deletion_record_sha256"])
        digest_registry = verifier["dynamic_digest_registry"]
        definitions = set(digest_registry["definitions"])
        aliases = digest_registry["field_aliases"]
        declared = set(digest_registry["declared_dynamic_field_names_exact"])
        self.assertEqual(27, len(definitions))
        self.assertEqual(15, len(aliases))
        self.assertEqual(42, len(declared))
        self.assertEqual(declared, definitions | set(aliases))
        self.assertTrue(definitions.isdisjoint(aliases))
        self.assertLessEqual(set(aliases.values()), definitions)
        self.assertEqual(
            {
                "artifact_sha256",
                "previous_generation_domain_digest",
                "target_domain_digest",
                "target_generation_domain_digest",
                "target_role_domain_digest",
            },
            set(digest_registry["role_discriminated_dynamic_digest_fields"]),
        )
        self.assertEqual(
            "pass_proof_bundle_sha256",
            aliases["pass_proof_bundle_ordinal_1_sha256"],
        )
        self.assertEqual(
            "pass_proof_bundle_sha256",
            aliases["pass_proof_bundle_ordinal_2_sha256"],
        )
        subset_names = set(locations["subset_field_names_exact"])
        resolved_subset = {aliases.get(name, name) for name in subset_names}
        excluded = set(locations["subset_excluded_dynamic_definition_names_exact"])
        self.assertEqual(14, len(subset_names))
        self.assertEqual(13, len(resolved_subset))
        self.assertEqual(14, len(excluded))
        self.assertTrue(resolved_subset.isdisjoint(excluded))
        self.assertEqual(definitions, resolved_subset | excluded)

        class_profiles = digest_registry["sha256_field_class_profiles"]
        raw_profile = class_profiles["path_discriminated_raw_byte_sha256"]
        self.assertNotIn("sha256", digest_registry["static_external_or_raw_byte_digest_fields"])
        self.assertNotIn(
            "sha256",
            class_profiles["external_or_static_digest"]["raw_byte_field_names_exact"],
        )
        self.assertEqual(["sha256"], raw_profile["field_names"])
        self.assertIs(False, raw_profile["public_or_log_output_permitted"])
        raw_profiles = raw_profile["closed_profiles_exact"]
        self.assertEqual(6, len(raw_profiles))
        self.assertEqual([0, 4], raw_profiles[0]["index_range_inclusive"])
        self.assertIn("owner_only_scientific_evidence", raw_profiles[0]["canonical_owner"])
        mackay_profile = raw_profiles[1]
        mackay_revision = self.source_contract["retrieval_resources"]["resources"][0]["revision"]
        revision_schema_mackay = self.schemas[REVISION_SET_SCHEMA_PATH]["properties"]["resources"][
            "prefixItems"
        ][0]["properties"]
        self.assertEqual(mackay_revision["sha256"], mackay_profile["sha256_const"])
        self.assertEqual(mackay_revision["byte_size"], mackay_profile["size_const"])
        self.assertEqual(
            mackay_profile["sha256_const"],
            revision_schema_mackay["sha256"]["const"],
        )
        self.assertEqual(
            mackay_profile["size_const"],
            revision_schema_mackay["byte_size"]["const"],
        )
        self.assertEqual([1, 5], raw_profiles[2]["index_range_inclusive"])
        self.assertEqual(-1, raw_profiles[2]["receipt_index_offset"])

        static_pointer_profiles = raw_profiles[5]["schema_and_JSON_pointer_sets_exact"]
        expected_pointers_by_schema: dict[str, set[str]] = {}
        for pointer_profile in static_pointer_profiles:
            schema_ids = pointer_profile.get("schema_ids_exact") or [pointer_profile["schema_id"]]
            for schema_id in schema_ids:
                self.assertNotIn(schema_id, expected_pointers_by_schema)
                expected_pointers_by_schema[schema_id] = set(pointer_profile["json_pointers_exact"])

        def scalar_sha256_pointers(value: Any, pointer: str = "") -> set[str]:
            found: set[str] = set()
            if isinstance(value, dict):
                for key, child in value.items():
                    child_pointer = f"{pointer}/{key}"
                    if key == "sha256" and isinstance(child, str):
                        found.add(child_pointer)
                    found.update(scalar_sha256_pointers(child, child_pointer))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    found.update(scalar_sha256_pointers(child, f"{pointer}/{index}"))
            return found

        static_schema_paths = {
            "source-reported-link-protected-ephemeral-custody-contract-v1": (CUSTODY_CONTRACT_PATH),
            "source-reported-link-source-contract-v1": SOURCE_CONTRACT_PATH,
            "source-reported-link-policy-v1": SOURCE_POLICY_PATH,
            "source-reported-link-protected-ephemeral-custody-contract.schema.json": (
                CUSTODY_SCHEMA_PATH
            ),
            "source-reported-link-source-contract.schema.json": (
                ROOT / "schemas" / "source-reported-link-source-contract.schema.json"
            ),
            "source-reported-link-policy.schema.json": (
                ROOT / "schemas" / "source-reported-link-policy.schema.json"
            ),
            "kp1979-label-reference-assignment.schema.json": (
                ROOT / "schemas" / "kp1979-label-reference-assignment.schema.json"
            ),
            "kp1979-row-assignment.schema.json": (
                ROOT / "schemas" / "kp1979-row-assignment.schema.json"
            ),
        }
        self.assertEqual(set(static_schema_paths), set(expected_pointers_by_schema))
        for schema_id, path in static_schema_paths.items():
            decoded = decode_json(path.read_bytes(), source=f"generic sha256 {schema_id}")
            with self.subTest(generic_sha256_schema=schema_id):
                self.assertEqual(
                    expected_pointers_by_schema[schema_id],
                    scalar_sha256_pointers(decoded),
                )
        authority_gate = self.custody["pre_acquisition_authority_gate"]
        self.assertIs(True, authority_gate["all_checks_required_before_network_or_source_access"])
        self.assertIs(True, authority_gate["authority_is_necessary_not_sufficient"])
        self.assertEqual(
            "blocked_multiple_required_prerequisites_missing_not_implemented",
            authority_gate["current_status"],
        )
        self.assertEqual(
            "missing_not_implemented",
            authority_gate["future_typed_authority_proof_bundle_schema_status"],
        )
        self.assertIs(
            False,
            authority_gate["pass_terminal_or_review_artifact_can_retroactively_authorize_access"],
        )
        commit_profile = authority_gate["published_commit_identity_profile"]
        self.assertEqual("sha1", commit_profile["git_object_format_for_both_commits"])
        self.assertEqual(
            "^[0-9a-f]{40}$",
            commit_profile["authorized_runtime_commit_oid_pattern"],
        )
        self.assertEqual(40, commit_profile["authorized_runtime_commit_oid_min_length"])
        self.assertEqual(40, commit_profile["authorized_runtime_commit_oid_max_length"])
        self.assertIn(
            "reject_cr_lf_u2028_u2029_anywhere",
            commit_profile["git_oid_lexical_precheck_order"],
        )
        self.assertIs(
            False,
            commit_profile["git_oid_alone_proves_repository_authenticity_or_authority"],
        )

    def test_static_only_validation_opens_no_network_and_adds_no_runtime(self) -> None:
        with (
            patch("socket.create_connection", side_effect=AssertionError("network forbidden")),
            patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")),
        ):
            receipt, _ = self.synthetic_receipt()
            self.validators[RECEIPT_SCHEMA_PATH].validate(receipt)
            revision_set = self.synthetic_revision_set(receipt)
            self.validators[REVISION_SET_SCHEMA_PATH].validate(revision_set)
            self.validators[CUSTODY_SCHEMA_PATH].validate(self.custody)
        for module_name in (
            "source_reported_link_acquisition.py",
            "source_reported_link_parser.py",
            "source_reported_link_evaluator.py",
            "source_reported_link_receipt.py",
            "source_reported_link_strict_verifier.py",
            "source_reported_link_custody_supervisor.py",
            "source_reported_link_pass_artifact.py",
            "source_reported_link_release_artifact.py",
            "source_reported_link_authority_proof.py",
            "source_reported_link_attempt_registry.py",
            "source_reported_link_acquisition_attestation.py",
            "source_reported_link_pass_proof.py",
            "source_reported_link_terminal_decision.py",
            "source_reported_link_internal_retention_review.py",
        ):
            self.assertFalse((ROOT / "src" / "indusbench" / module_name).exists())
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"schemas" = "indusbench/schemas"', pyproject)
        for packaged_registry in (
            "chanhu-daro-helsinki-gate-v1.json",
            "sources.json",
            "source-reported-link-policy-v1.json",
            "source-reported-link-source-contract-v1.json",
            "source-reported-link-protected-ephemeral-custody-contract-v1.json",
        ):
            self.assertIn(f'"registry/{packaged_registry}"', pyproject)
        self.assertTrue((ROOT / "src" / "indusbench" / "source_reported_link_resource.py").exists())
        self.assertTrue((ROOT / "src" / "indusbench" / "source_reported_link_static.py").exists())
        self.assertIs(
            False,
            self.custody["artifact_boundaries"][
                "static_package_schema_presence_creates_loader_or_authority"
            ],
        )
        self.assertIn(
            "missing_not_implemented",
            self.custody["cross_artifact_verifier_contract"][
                "scientific_cross_binding_digest_output_subset"
            ]["completeness_attestation_sha256"],
        )

    def test_candidate_contains_no_private_infrastructure_markers(self) -> None:
        self.assertEqual(8, len(CANDIDATE_PATHS))
        self.assertEqual(8, len(set(CANDIDATE_PATHS)))
        self.assertTrue(all(path.exists() for path in CANDIDATE_PATHS))
        candidate_text = "\n".join(path.read_text(encoding="utf-8") for path in CANDIDATE_PATHS)
        for label, marker in PRIVATE_MARKERS.items():
            with self.subTest(label=label):
                self.assertIsNone(marker.search(candidate_text))
        self.assertNotIn("data/" + "raw/", candidate_text)
        self.assertNotIn("data/" + "derived/", candidate_text)


if __name__ == "__main__":
    unittest.main()
