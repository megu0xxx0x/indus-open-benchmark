from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
import unittest
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator

from indusbench.io import encode_json
from indusbench.nmfa_preflight import (
    _ARCHIVE_CONTRACT_DOMAIN,
    _CLAIM_SUBJECT_DOMAIN,
    _CONTEXT_AXES,
    _ED25519_FIELD_PRIME,
    _ED25519_GROUP_ORDER,
    _F_ROSTER_DOMAIN,
    _IDENTIFIER_SUBJECT_DOMAIN,
    _INVENTORY_DOMAIN,
    _PREMETADATA_ROLES,
    _PREVALUE_ROLES,
    _RIGHTS_LAYERS,
    NMFAPreflightError,
    NMFAPreflightErrorCode,
    _decode_canonical_json,
    _domain_digest,
    _evaluate_premetadata,
    _first_metadata_head,
    _installed,
    _is_ed25519_identity,
    _is_strict_ed25519_point,
    _ledger_head,
    _multiply_ed25519_point,
    _premetadata_semantics,
    _prevalue_semantics,
    _receipt_head,
    _request_subject,
    _Resources,
    _sha256,
    _signature_message,
    _verify_signatures,
    build_nmfa_preflight_signature_message,
    evaluate_premetadata_preflight,
    evaluate_prevalue_preflight,
    load_installed_nmfa_activation_preflight_plan,
    validate_external_trust_profile,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/nmfa-activation-preflight-plan-v1.json"
BUNDLE_PATH = ROOT / "benchmark/nmfa-activation-preflight-evaluator-bundle-v1.json"
PLAN_SCHEMA_PATH = ROOT / "schemas/nmfa-activation-preflight-plan.schema.json"
TRUST_SCHEMA_PATH = ROOT / "schemas/nmfa-external-trust-profile.schema.json"
REQUEST_SCHEMA_PATH = ROOT / "schemas/nmfa-activation-preflight-request.schema.json"
REPORT_SCHEMA_PATH = ROOT / "schemas/nmfa-activation-preflight-report.schema.json"
PARENT_PATH = ROOT / "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
GATE_PLAN_PATH = ROOT / "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
GATE_BUNDLE_PATH = ROOT / "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"

ALL_ROLES = (
    "authority",
    "governance_reviewer",
    "metadata_controller",
    "transcription_controller",
    "target_controller",
    "value_barrier_coordinator",
)
COMPILED_BLOCKERS = (
    "TYPED_EXECUTION_BUNDLE_UNBOUND",
    "EXTERNAL_TRUST_PROFILE_UNBOUND",
    "EXTERNAL_TIME_ANCHOR_UNBOUND",
    "CONSUMPTION_REGISTRY_UNBOUND",
    "ACTIVATION_WRAPPER_UNBOUND",
)


def digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def opaque(label: str) -> str:
    return "hmac-sha256:" + hashlib.sha256(("nmfa-preflight-test:" + label).encode()).hexdigest()


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def resources() -> _Resources:
    return _Resources(
        bundle=BUNDLE_PATH.read_bytes(),
        gate_bundle=GATE_BUNDLE_PATH.read_bytes(),
        gate_plan=GATE_PLAN_PATH.read_bytes(),
        io_source=(ROOT / "src/indusbench/io.py").read_bytes(),
        module_source=(ROOT / "src/indusbench/nmfa_preflight.py").read_bytes(),
        parent=PARENT_PATH.read_bytes(),
        plan=PLAN_PATH.read_bytes(),
        plan_schema=PLAN_SCHEMA_PATH.read_bytes(),
        report_schema=REPORT_SCHEMA_PATH.read_bytes(),
        request_schema=REQUEST_SCHEMA_PATH.read_bytes(),
        trust_schema=TRUST_SCHEMA_PATH.read_bytes(),
    )


def keyring() -> dict[str, Ed25519PrivateKey]:
    return {
        role: Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(("nmfa-preflight-test-key:" + role).encode()).digest()
        )
        for role in ALL_ROLES
    }


def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def trust_profile(
    keys: dict[str, Ed25519PrivateKey],
) -> dict[str, Any]:
    rows = []
    for role in ALL_ROLES:
        raw_public_key = public_key_bytes(keys[role])
        rows.append(
            {
                "actor_id": opaque("actor:" + role),
                "algorithm": "Ed25519",
                "conflict_domain_id": opaque("conflict:" + role),
                "controller_id": opaque("controller:" + role),
                "key_id": "ed25519:" + hashlib.sha256(raw_public_key).hexdigest(),
                "public_key_base64url": b64url(raw_public_key),
                "role": role,
                "status": "ACTIVE",
            }
        )
    return {
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
        "format_version": "1.0.0",
        "issuer_id": opaque("issuer"),
        "profile_id": opaque("profile"),
        "record_kind": "nmfa_external_trust_profile",
        "registry_sequence": 1,
        "revocation_snapshot_sha256": digest("revocation-snapshot"),
        "role_bindings": rows,
        "trust_domain_id": opaque("trust-domain"),
    }


def sign_request(
    request: dict[str, Any],
    trust: dict[str, Any],
    keys: dict[str, Ed25519PrivateKey],
) -> dict[str, Any]:
    signed = copy.deepcopy(request)
    signed["signatures"] = []
    _, subject_sha256 = _request_subject(signed)
    roles = _PREMETADATA_ROLES if signed["request_kind"] == "PREMETADATA" else _PREVALUE_ROLES
    by_role = {row["role"]: row for row in trust["role_bindings"]}
    signed["signatures"] = [
        {
            "actor_id": by_role[role]["actor_id"],
            "algorithm": "Ed25519",
            "key_id": by_role[role]["key_id"],
            "role": role,
            "signature_base64url": b64url(
                keys[role].sign(_signature_message(signed, subject_sha256, trust, role))
            ),
        }
        for role in roles
    ]
    return signed


def receipt(
    *,
    kind: str,
    label: str,
    prior: str,
    sequence: int,
    recorded_at: str,
    subject: str,
) -> dict[str, Any]:
    value = {
        "event_head_sha256": digest("placeholder-event-head"),
        "external_time_anchor_sha256": digest("time-anchor:" + label),
        "identifier_key_commitment_sha256": (
            None if kind == "CLAIM_SLOT_RESERVATION" else digest("identifier-key-commitment")
        ),
        "kind": kind,
        "prior_event_head_sha256": prior,
        "receipt_id": opaque("receipt:" + label),
        "recorded_at": recorded_at,
        "sequence": sequence,
        "subject_sha256": subject,
    }
    value["event_head_sha256"] = _receipt_head(value)
    return value


def ledger(
    *,
    label: str,
    prior: str,
    sequence: int,
    recorded_at: str,
    metadata_access_count: int,
) -> dict[str, Any]:
    value = {
        "event_head_sha256": digest("placeholder-ledger-head"),
        "ledger_id": opaque("ledger:" + label),
        "metadata_access_count": metadata_access_count,
        "prior_event_head_sha256": prior,
        "recorded_at": recorded_at,
        "sequence": sequence,
        "source_value_access_count": 0,
        "target_y_access_count": 0,
        "transcription_x_access_count": 0,
    }
    value["event_head_sha256"] = _ledger_head(value)
    return value


def rights() -> list[dict[str, Any]]:
    rows = []
    protected_actions = {
        "analyze",
        "custodial_transfer",
        "derive",
        "retain_protected",
        "retrieve",
    }
    for layer in _RIGHTS_LAYERS:
        permissions = {
            action: "NOT_APPLICABLE"
            for action in (
                "analyze",
                "custodial_transfer",
                "derive",
                "prize_submit",
                "publish_aggregate",
                "retain_protected",
                "retrieve",
            )
        }
        if layer == "derived_aggregate":
            for action in ("derive", "publish_aggregate"):
                permissions[action] = "PERMITTED"
        else:
            for action in protected_actions:
                permissions[action] = "PERMITTED"
        rows.append(
            {
                "evidence_envelope_sha256": digest("rights-evidence:" + layer),
                "layer": layer,
                "permissions": permissions,
                "scope_sha256": digest("rights-scope:" + layer),
                "status": "READY",
            }
        )
    return rows


def bindings(installed: Any, trust_sha256: str) -> dict[str, Any]:
    return {
        "activation_preflight_evaluator_bundle_sha256": installed.bundle_sha256,
        "activation_preflight_plan_sha256": installed.snapshot.plan_sha256,
        "activation_root_sha256": digest("activation-root"),
        "external_time_anchor_profile_sha256": digest("external-time-profile"),
        "external_trust_profile_sha256": trust_sha256,
        "one_time_consumption_registry_profile_sha256": digest("consumption-registry"),
        "parent_protocol_sha256": _sha256(PARENT_PATH.read_bytes()),
        "preregistration_evaluator_bundle_sha256": _sha256(GATE_BUNDLE_PATH.read_bytes()),
        "preregistration_gate_plan_sha256": _sha256(GATE_PLAN_PATH.read_bytes()),
        "typed_execution_bundle_sha256": digest("typed-execution-bundle"),
    }


def premetadata_request(
    installed: Any,
    trust_sha256: str,
) -> dict[str, Any]:
    request_bindings = bindings(installed, trust_sha256)
    claim_family_id = opaque("claim-family")
    instance_id = opaque("experiment-instance")
    slot_id = opaque("claim-slot")
    claim_subject = _domain_digest(
        _CLAIM_SUBJECT_DOMAIN,
        {
            "activation_root_sha256": request_bindings["activation_root_sha256"],
            "claim_family_id": claim_family_id,
            "experiment_instance_id": instance_id,
            "slot_id": slot_id,
        },
    )
    claim = receipt(
        kind="CLAIM_SLOT_RESERVATION",
        label="claim",
        prior=digest("genesis-event"),
        sequence=1,
        recorded_at="2026-06-01T00:01:00Z",
        subject=claim_subject,
    )
    ceremony_subject = _domain_digest(
        _IDENTIFIER_SUBJECT_DOMAIN,
        {
            "claim_reservation": claim,
            "claim_family_id": claim_family_id,
            "experiment_instance_id": instance_id,
            "identifier_key_commitment_sha256": digest("identifier-key-commitment"),
            "slot_id": slot_id,
        },
    )
    ceremony = receipt(
        kind="IDENTIFIER_KEY_CEREMONY",
        label="identifier-ceremony",
        prior=claim["event_head_sha256"],
        sequence=2,
        recorded_at="2026-06-01T00:02:00Z",
        subject=ceremony_subject,
    )
    zero_access = ledger(
        label="claim-access",
        prior=ceremony["event_head_sha256"],
        sequence=3,
        recorded_at="2026-06-01T00:03:00Z",
        metadata_access_count=0,
    )
    return {
        "bindings": request_bindings,
        "claim_reservation": claim,
        "claim_family_id": claim_family_id,
        "created_at": "2026-06-01T00:04:00Z",
        "custody": {
            "access_mediation_required": True,
            "custody_contract_sha256": digest("custody-contract"),
            "decision": "READY",
            "ephemeral_processing_required": True,
            "publication_review_required": True,
            "retention_policy_sha256": digest("retention-policy"),
        },
        "experiment_instance_id": instance_id,
        "format_version": "1.0.0",
        "identifier_ceremony": ceremony,
        "no_access_ledger": zero_access,
        "record_kind": "nmfa_activation_preflight_request",
        "request_kind": "PREMETADATA",
        "rights": rights(),
        "role_separation": {
            "conflict_matrix_sha256": digest("conflict-matrix"),
            "same_actor_for_incompatible_roles_forbidden": True,
            "same_conflict_domain_for_incompatible_roles_forbidden": True,
            "same_controller_for_incompatible_roles_forbidden": True,
            "separation_evidence_sha256": digest("separation-evidence"),
            "structural_only_not_human_independence_proof": True,
        },
        "sequence": 4,
        "signatures": [],
        "slot_id": slot_id,
        "source_policy": {
            "browser_forbidden": True,
            "cache_forbidden": True,
            "log_body_forbidden": True,
            "metadata_projection_contract_sha256": digest("metadata-projection"),
            "mixed_value_transport_forbidden": True,
            "parser_profile_sha256": digest("parser-profile"),
            "proxy_body_capture_forbidden": True,
            "transport_profile_sha256": digest("transport-profile"),
            "value_fields_byte_inaccessible_required": True,
        },
        "source_scope": {
            "actions": [
                "enumerate_metadata",
                "read_allowlisted_projection",
                "freeze_prevalue_inventory",
            ],
            "authority_evidence_sha256": digest("authority-evidence"),
            "decision": "AUTHORIZED",
            "phase": "metadata_only",
            "purposes": [
                "scientific_preregistration",
                "rights_aware_custodial_evaluation",
            ],
            "revocation_snapshot_sha256": digest("revocation-snapshot"),
            "valid_from": "2026-05-01T00:00:00Z",
            "valid_until": "2026-07-01T00:00:00Z",
        },
        "target_policy": {
            "key_release_forbidden_before_verified_prevalue_composite": True,
            "target_y_access_forbidden": True,
            "transcription_x_access_forbidden": True,
        },
    }


def first_metadata_access(premetadata: Any) -> dict[str, Any]:
    value = {
        "event_head_sha256": digest("placeholder-first-metadata-head"),
        "metadata_projection_contract_sha256": digest("metadata-projection"),
        "premetadata_report_sha256": _sha256(premetadata.report.report_bytes),
        "prior_event_head_sha256": premetadata.request["no_access_ledger"]["event_head_sha256"],
        "recorded_at": "2026-06-01T00:05:00Z",
        "sequence": 5,
    }
    value["event_head_sha256"] = _first_metadata_head(value)
    return value


def unit(f_id: str, order: int) -> dict[str, Any]:
    axes = [
        {
            "axis": axis,
            "evidence_envelope_sha256": digest(f"context-evidence:{order}:{axis}"),
            "status": "EXACT",
            "value_id": opaque(f"context-value:{order}:{axis}"),
        }
        for axis in _CONTEXT_AXES
    ]
    return {
        "context_axes": axes,
        "epre_reason_codes": [],
        "f_id": f_id,
        "identity_evidence_sha256": digest(f"identity:{order}"),
        "identity_status": "RESOLVED",
        "nuisance_values": [
            {
                "evidence_envelope_sha256": digest(f"nuisance:{order}"),
                "field_id": opaque("nuisance-field"),
                "status": "EXACT",
                "value_ids": [opaque(f"nuisance-value:{order}")],
            }
        ],
        "physical_original_status": "CONFIRMED_PHYSICAL_ORIGINAL",
        "provenance_evidence_sha256": digest(f"provenance:{order}"),
        "provenance_status": "COMPLETE",
        "rights_evidence_sha256": digest(f"unit-rights:{order}"),
        "rights_status": "SUFFICIENT",
        "source_binding_evidence_sha256": digest(f"source-binding:{order}"),
        "source_binding_status": "COMPLETE",
        "unit_order": order,
    }


def inventory(access_ledger_head: str) -> dict[str, Any]:
    f_ids = sorted([opaque("f:zero"), opaque("f:one")])
    units = [unit(f_id, index) for index, f_id in enumerate(f_ids)]
    source_records = [
        {
            "entry_id": opaque(f"entry:{index}"),
            "f_id": f_id,
            "metadata_projection_sha256": digest(f"projection:{index}"),
            "record_id": opaque(f"record:{index}"),
            "revision_id": opaque(f"revision:{index}"),
            "source_order": index,
            "view_id": opaque(f"view:{index}"),
        }
        for index, f_id in enumerate(f_ids)
    ]
    return {
        "context_contract_sha256": digest("prevalue-context-contract"),
        "declared_source_record_count": len(source_records),
        "declared_unit_count": len(units),
        "exposure_cutoff_event_head_sha256": access_ledger_head,
        "prevalue_exposure": [
            {
                "access_ledger_proof_sha256": digest(f"exposure-proof:{index}"),
                "alias_closure_sha256": digest(f"alias-closure:{index}"),
                "f_id": f_id,
                "policy_sha256": digest("exposure-policy"),
                "status": "NOT_EXPOSED",
            }
            for index, f_id in enumerate(f_ids)
        ],
        "declared_pre_x_relation_edges": [
            {
                "disposition": "UNION",
                "evidence_envelope_sha256": digest("relation-evidence"),
                "kind": "PHYSICAL_IDENTITY",
                "left_f_id": f_ids[0],
                "right_f_id": f_ids[1],
                "status": "CONFIRMED",
            }
        ],
        "source_records": source_records,
        "units": units,
    }


def prevalue_request(premetadata: Any) -> dict[str, Any]:
    first = first_metadata_access(premetadata)
    access = ledger(
        label="claim-access",
        prior=first["event_head_sha256"],
        sequence=6,
        recorded_at="2026-06-01T00:06:00Z",
        metadata_access_count=2,
    )
    frozen_inventory = inventory(access["event_head_sha256"])
    inventory_sha256 = _domain_digest(_INVENTORY_DOMAIN, frozen_inventory)
    f_ids = [row["f_id"] for row in frozen_inventory["units"]]
    f_roster_sha256 = _domain_digest(_F_ROSTER_DOMAIN, {"ordered_f_ids": f_ids})
    archives = {}
    barriers = {}
    for layer, role, prepared_at, sequence in (
        ("target_y", "target_controller", "2026-06-01T00:07:00Z", 7),
        (
            "transcription_x",
            "transcription_controller",
            "2026-06-01T00:08:00Z",
            8,
        ),
    ):
        archive = {
            "archive_profile_sha256": digest("archive-profile:" + layer),
            "controller_role": role,
            "data_layer": layer,
            "experiment_instance_id": premetadata.request["experiment_instance_id"],
            "f_roster_sha256": f_roster_sha256,
            "planned_f_count": len(f_ids),
            "prevalue_inventory_sha256": inventory_sha256,
            "record_state": "CONTRACT_ONLY_NO_ARCHIVE_MATERIAL",
            "slot_id": premetadata.request["slot_id"],
        }
        archives[layer] = archive
        barriers[layer] = {
            "archive_contract_sha256": _domain_digest(_ARCHIVE_CONTRACT_DOMAIN, archive),
            "cas_token_commitment_sha256": digest("cas-token:" + layer),
            "controller_role": role,
            "data_layer": layer,
            "expected_prior_event_head_sha256": access["event_head_sha256"],
            "prepared_at": prepared_at,
            "sequence": sequence,
            "state": "PREPARED_LOCKED_NOT_ARMED_NOT_RELEASED",
            "value_access_count": 0,
        }
    return {
        "access_ledger": access,
        "archives": archives,
        "barriers": barriers,
        "bindings": copy.deepcopy(premetadata.request["bindings"]),
        "claim_family_id": premetadata.request["claim_family_id"],
        "created_at": "2026-06-01T00:09:00Z",
        "experiment_instance_id": premetadata.request["experiment_instance_id"],
        "first_metadata_access": first,
        "format_version": "1.0.0",
        "inventory": frozen_inventory,
        "predecessor": {
            "premetadata_report_sha256": _sha256(premetadata.report.report_bytes),
            "premetadata_request_sha256": _sha256(encode_json(premetadata.request)),
            "premetadata_subject_sha256": premetadata.subject_sha256,
        },
        "record_kind": "nmfa_activation_preflight_request",
        "request_kind": "PREVALUE",
        "sequence": 9,
        "signatures": [],
        "slot_id": premetadata.request["slot_id"],
    }


def noncanonical_last_base64url_character(value: str) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    index = alphabet.index(value[-1])
    return value[:-1] + alphabet[index + 1]


class NMFAPreflightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resources = resources()
        cls.installed = _installed(cls.resources)
        cls.keys = keyring()
        cls.trust = trust_profile(cls.keys)
        cls.trust_raw = encode_json(cls.trust)
        cls.trust_sha256 = _sha256(cls.trust_raw)
        cls.premetadata = sign_request(
            premetadata_request(cls.installed, cls.trust_sha256),
            cls.trust,
            cls.keys,
        )
        cls.premetadata_raw = encode_json(cls.premetadata)
        cls.premetadata_evaluation = cls.evaluate_premetadata(cls.premetadata)
        ready_report = replace(
            cls.premetadata_evaluation.report,
            terminal_state="PREMETADATA_READY",
        )
        cls.ready_premetadata_evaluation = replace(
            cls.premetadata_evaluation,
            report=ready_report,
        )
        cls.prevalue = sign_request(
            prevalue_request(cls.ready_premetadata_evaluation),
            cls.trust,
            cls.keys,
        )

    @classmethod
    def evaluate_premetadata(
        cls,
        request: dict[str, Any],
        *,
        trust: dict[str, Any] | None = None,
        trust_raw: bytes | None = None,
        expected_trust_sha256: str | None = None,
    ) -> Any:
        selected_trust = cls.trust if trust is None else trust
        selected_raw = encode_json(selected_trust) if trust_raw is None else trust_raw
        selected_digest = (
            _sha256(selected_raw) if expected_trust_sha256 is None else expected_trust_sha256
        )
        return _evaluate_premetadata(
            encode_json(request),
            selected_raw,
            selected_digest,
            cls.resources,
            cls.installed,
        )

    def assert_premetadata_reason(
        self,
        mutate: Callable[[dict[str, Any]], None],
        reason: str,
        *,
        resign: bool = True,
    ) -> Any:
        request = copy.deepcopy(self.premetadata)
        mutate(request)
        if resign:
            request = sign_request(request, self.trust, self.keys)
        evaluation = self.evaluate_premetadata(request)
        self.assertIn(reason, evaluation.report.reason_codes)
        return evaluation

    def assert_prevalue_reason(
        self,
        mutate: Callable[[dict[str, Any]], None],
        reason: str,
    ) -> set[str]:
        request = copy.deepcopy(self.prevalue)
        mutate(request)
        reasons = _prevalue_semantics(
            request,
            self.ready_premetadata_evaluation,
            self.trust,
        )
        self.assertIn(reason, reasons)
        return reasons

    def test_installed_snapshot_is_source_free_and_closed(self) -> None:
        with patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources):
            snapshot = load_installed_nmfa_activation_preflight_plan()
        self.assertEqual(snapshot.plan_id, "nmfa-activation-preflight-plan-v1")
        self.assertEqual(snapshot.compiled_blockers, COMPILED_BLOCKERS)
        self.assertFalse(snapshot.premetadata_ready_enabled)
        self.assertFalse(snapshot.prevalue_ready_enabled)
        self.assertFalse(snapshot.source_access_authorized)
        self.assertFalse(snapshot.execution_authorized)

    def test_plan_declares_installed_nonclaims_and_exact_chronology(self) -> None:
        scope = self.installed.plan["installed_semantic_scope"]
        self.assertEqual(scope["relation_edges"], "DECLARED_SET_STRUCTURE_ONLY")
        self.assertEqual(
            scope["expected_trust_digest_origin"],
            "CALLER_SUPPLIED_NOT_AUTHENTICATED",
        )
        self.assertEqual(
            scope["inventory_universe"],
            "DECLARED_ROSTER_CONSISTENCY_ONLY_EXTERNAL_COMPLETENESS_NOT_VERIFIED",
        )
        self.assertEqual(
            scope["r0_completeness"],
            "DEFERRED_TO_TYPED_EXECUTION_BUNDLE_AND_ACTIVATION_WRAPPER",
        )
        self.assertEqual(
            scope["rpre_closure"],
            "DEFERRED_TO_TYPED_EXECUTION_BUNDLE_AND_ACTIVATION_WRAPPER",
        )
        self.assertEqual(
            self.installed.plan["chronology"],
            [
                "source_free_bundles_frozen",
                "claim_slot_reserved",
                "identifier_key_ceremony_completed",
                "PREMETADATA_evaluator_package_verified",
                "PREMETADATA_READY_registry_consumed",
                "first_metadata_access",
                "declared_inventory_frozen",
                "both_value_layers_PREPARED_LOCKED",
                "prevalue_request_subject_frozen",
                "prevalue_request_signatures_collected",
                "PREVALUE_evaluator_package_verified",
                "PREVALUE_READY_registry_consumed",
                "both_value_layers_ARMED_NOT_RELEASED_via_CAS",
                "first_transcription_or_target_access",
            ],
        )

    def test_public_schemas_and_artifacts_validate(self) -> None:
        plan_schema = json.loads(PLAN_SCHEMA_PATH.read_text())
        trust_schema = json.loads(TRUST_SCHEMA_PATH.read_text())
        request_schema = json.loads(REQUEST_SCHEMA_PATH.read_text())
        report_schema = json.loads(REPORT_SCHEMA_PATH.read_text())
        for schema in (plan_schema, trust_schema, request_schema, report_schema):
            Draft202012Validator.check_schema(schema)
        Draft202012Validator(plan_schema).validate(json.loads(PLAN_PATH.read_text()))
        Draft202012Validator(trust_schema).validate(self.trust)
        validator = Draft202012Validator(request_schema)
        validator.validate(self.premetadata)
        validator.validate(self.prevalue)
        Draft202012Validator(report_schema).validate(self.premetadata_evaluation.report.report())

    def test_signature_arrays_are_empty_or_complete_and_prize_is_outside_preflight(self) -> None:
        from indusbench.nmfa_preflight import _parse_request

        partial = copy.deepcopy(self.prevalue)
        partial["signatures"] = partial["signatures"][:1]
        with self.assertRaises(NMFAPreflightError) as partial_caught:
            _parse_request(encode_json(partial), self.resources, "PREVALUE")
        self.assertEqual(
            partial_caught.exception.code,
            NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
        )

        prize_claim = copy.deepcopy(self.premetadata)
        prize_claim["rights"][-1]["permissions"]["prize_submit"] = "PERMITTED"
        with self.assertRaises(NMFAPreflightError) as prize_caught:
            _parse_request(encode_json(prize_claim), self.resources, "PREMETADATA")
        self.assertEqual(
            prize_caught.exception.code,
            NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
        )

    def test_valid_signed_premetadata_is_semantically_valid_but_compiled_blocked(self) -> None:
        report = self.premetadata_evaluation.report
        value = report.report()
        self.assertEqual(report.terminal_state, "PREMETADATA_BLOCKED")
        self.assertEqual(report.reason_codes, COMPILED_BLOCKERS)
        self.assertTrue(value["semantic_core_valid"])
        self.assertTrue(value["signatures_valid"])
        self.assertEqual(value["reason_codes"], list(COMPILED_BLOCKERS))
        self.assertTrue(value["privacy"]["private_report"])
        self.assertFalse(value["assurance"]["execution_authorized"])
        self.assertFalse(value["assurance"]["decipherment_claim_allowed"])
        with patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources):
            public_report = evaluate_premetadata_preflight(
                self.premetadata_raw,
                self.trust_raw,
                self.trust_sha256,
            )
        self.assertEqual(public_report.report_bytes, report.report_bytes)

    def test_external_trust_profile_matches_caller_expected_digest(self) -> None:
        with patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources):
            validated = validate_external_trust_profile(self.trust_raw, self.trust_sha256)
        self.assertEqual(validated.canonical_bytes, self.trust_raw)
        self.assertEqual(validated.trust_profile_sha256, self.trust_sha256)
        self.assertEqual(repr(validated), "<ValidatedNMFAExternalTrustProfile protected>")
        with (
            patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources),
            self.assertRaises(NMFAPreflightError) as caught,
        ):
            validate_external_trust_profile(self.trust_raw, digest("wrong-trust-root"))
        self.assertEqual(
            caught.exception.code, NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID
        )

    def test_public_signature_message_matches_internal_contract(self) -> None:
        unsigned = copy.deepcopy(self.premetadata)
        unsigned["signatures"] = []
        with patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources):
            actual = build_nmfa_preflight_signature_message(
                encode_json(unsigned),
                self.trust_raw,
                self.trust_sha256,
                "authority",
            )
        _, subject = _request_subject(unsigned)
        expected = _signature_message(unsigned, subject, self.trust, "authority")
        self.assertEqual(actual, expected)
        with (
            patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources),
            self.assertRaises(NMFAPreflightError) as caught,
        ):
            build_nmfa_preflight_signature_message(
                encode_json(unsigned),
                self.trust_raw,
                self.trust_sha256,
                "target_controller",
            )
        self.assertEqual(
            caught.exception.code, NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID
        )
        with (
            patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources),
            self.assertRaises(NMFAPreflightError) as signed_caught,
        ):
            build_nmfa_preflight_signature_message(
                self.premetadata_raw,
                self.trust_raw,
                self.trust_sha256,
                "authority",
            )
        self.assertEqual(
            signed_caught.exception.code,
            NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
        )

    def test_report_and_error_repr_are_private_and_fixed(self) -> None:
        report = self.premetadata_evaluation.report
        self.assertEqual(repr(report), "<NMFAActivationPreflightReport protected>")
        self.assertNotIn(report.report()["report_sha256"], repr(report))
        first = report.report()
        first["terminal_state"] = "PREMETADATA_READY"
        self.assertEqual(report.report()["terminal_state"], "PREMETADATA_BLOCKED")
        error = NMFAPreflightError(NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)
        self.assertEqual(str(error), "REQUEST_CONTRACT_INVALID")

    def test_noncanonical_or_duplicate_json_is_rejected_with_fixed_code(self) -> None:
        noncanonical = json.dumps(self.premetadata, sort_keys=True).encode("utf-8")
        with self.assertRaises(NMFAPreflightError) as caught:
            _evaluate_premetadata(
                noncanonical,
                self.trust_raw,
                self.trust_sha256,
                self.resources,
                self.installed,
            )
        self.assertEqual(caught.exception.code, NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)
        with self.assertRaises(NMFAPreflightError) as caught:
            _evaluate_premetadata(
                b'{"x":1,"x":2}\n',
                self.trust_raw,
                self.trust_sha256,
                self.resources,
                self.installed,
            )
        self.assertEqual(caught.exception.code, NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)

    def test_json_resource_boundaries_fail_with_fixed_code(self) -> None:
        def assert_rejected(raw: bytes) -> None:
            with self.assertRaises(NMFAPreflightError) as caught:
                _decode_canonical_json(
                    raw,
                    error=NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
                )
            self.assertEqual(
                caught.exception.code,
                NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID,
            )

        for raw in (
            b"\xef\xbb\xbf{}\n",
            b"1.0\n",
            b"NaN\n",
            f"{1 << 63}\n".encode(),
            f"{-((1 << 63) + 1)}\n".encode(),
        ):
            assert_rejected(raw)
        encoded = encode_json({"x": 1})
        with patch("indusbench.nmfa_preflight._MAX_JSON_BYTES", len(encoded) - 1):
            assert_rejected(encoded)
        with patch("indusbench.nmfa_preflight._MAX_JSON_STRING_LENGTH", 3):
            assert_rejected(encode_json("four"))
        with patch("indusbench.nmfa_preflight._MAX_JSON_DEPTH", 2):
            assert_rejected(encode_json([[[0]]]))
        with patch("indusbench.nmfa_preflight._MAX_JSON_NODES", 3):
            assert_rejected(encode_json([0, 1, 2]))

    def test_candidate_profile_cannot_replace_profile_under_fixed_expected_digest(self) -> None:
        attacker_keys = dict(self.keys)
        attacker_keys["authority"] = Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(b"candidate-self-signing-key").digest()
        )
        attacker_trust = trust_profile(attacker_keys)
        attacker_raw = encode_json(attacker_trust)
        request = premetadata_request(self.installed, _sha256(attacker_raw))
        request = sign_request(request, attacker_trust, attacker_keys)
        with self.assertRaises(NMFAPreflightError) as caught:
            self.evaluate_premetadata(
                request,
                trust=attacker_trust,
                trust_raw=attacker_raw,
                expected_trust_sha256=self.trust_sha256,
            )
        self.assertEqual(
            caught.exception.code,
            NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
        )
        candidate_selected = self.evaluate_premetadata(
            request,
            trust=attacker_trust,
            trust_raw=attacker_raw,
            expected_trust_sha256=_sha256(attacker_raw),
        ).report
        self.assertTrue(candidate_selected.report()["semantic_core_valid"])
        self.assertEqual(candidate_selected.reason_codes, COMPILED_BLOCKERS)

    def test_wrong_role_payload_tamper_and_replay_are_signature_failures(self) -> None:
        attacks: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
            (
                "wrong-role-order",
                lambda value: value["signatures"].reverse(),
            ),
            (
                "payload-tamper",
                lambda value: value["source_scope"].__setitem__(
                    "authority_evidence_sha256", digest("tampered-authority-evidence")
                ),
            ),
            (
                "slot-replay",
                lambda value: value.__setitem__("slot_id", opaque("different-slot")),
            ),
            (
                "sequence-replay",
                lambda value: value.__setitem__("sequence", value["sequence"] + 1),
            ),
        ]
        for label, mutate in attacks:
            with self.subTest(label=label):
                evaluation = self.assert_premetadata_reason(
                    mutate,
                    "SIGNATURE_INVALID",
                    resign=False,
                )
                self.assertFalse(evaluation.report.report()["signatures_valid"])

    def test_signature_tamper_and_strict_ed25519_encodings_are_rejected(self) -> None:
        def set_signature(raw: bytes) -> Callable[[dict[str, Any]], None]:
            return lambda value: value["signatures"][0].__setitem__(
                "signature_base64url", b64url(raw)
            )

        valid = base64.urlsafe_b64decode(
            self.premetadata["signatures"][0]["signature_base64url"] + "=="
        )
        tampered = bytes([valid[0] ^ 1]) + valid[1:]
        noncanonical_s = valid[:32] + _ED25519_GROUP_ORDER.to_bytes(32, "little")
        noncanonical_r = _ED25519_FIELD_PRIME.to_bytes(32, "little") + valid[32:]
        attacks = {
            "tampered": set_signature(tampered),
            "noncanonical-S": set_signature(noncanonical_s),
            "noncanonical-R": set_signature(noncanonical_r),
            "noncanonical-base64url": lambda value: value["signatures"][0].__setitem__(
                "signature_base64url",
                noncanonical_last_base64url_character(
                    value["signatures"][0]["signature_base64url"]
                ),
            ),
        }
        for label, mutate in attacks.items():
            with self.subTest(label=label):
                evaluation = self.assert_premetadata_reason(
                    mutate,
                    "SIGNATURE_INVALID",
                    resign=False,
                )
                self.assertFalse(evaluation.report.report()["signatures_valid"])

    def test_missing_ed25519_backend_support_is_fixed_package_failure(self) -> None:
        _, subject_sha256 = _request_subject(self.premetadata)
        with (
            patch(
                "cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey"
            ) as public_key_class,
            self.assertRaises(NMFAPreflightError) as caught,
        ):
            public_key_class.from_public_bytes.side_effect = UnsupportedAlgorithm(
                "synthetic unavailable backend"
            )
            _verify_signatures(
                self.premetadata,
                subject_sha256,
                self.trust,
                True,
            )
        self.assertEqual(
            caught.exception.code,
            NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID,
        )

    def test_identity_public_key_zero_signature_forgery_is_rejected(self) -> None:
        identity = b"\x01" + b"\x00" * 31
        identity_trust = copy.deepcopy(self.trust)
        authority = identity_trust["role_bindings"][0]
        self.assertEqual(authority["role"], "authority")
        authority["public_key_base64url"] = b64url(identity)
        authority["key_id"] = "ed25519:" + hashlib.sha256(identity).hexdigest()
        identity_trust_raw = encode_json(identity_trust)

        request = premetadata_request(self.installed, _sha256(identity_trust_raw))
        request = sign_request(request, identity_trust, self.keys)
        request["signatures"][0]["signature_base64url"] = b64url(identity + b"\x00" * 32)

        with self.assertRaises(NMFAPreflightError) as caught:
            self.evaluate_premetadata(
                request,
                trust=identity_trust,
                trust_raw=identity_trust_raw,
            )
        self.assertEqual(
            caught.exception.code,
            NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
        )

    def test_low_order_identity_r_is_rejected_for_normal_key(self) -> None:
        identity = b"\x01" + b"\x00" * 31
        evaluation = self.assert_premetadata_reason(
            lambda value: value["signatures"][0].__setitem__(
                "signature_base64url",
                b64url(identity + b"\x00" * 32),
            ),
            "SIGNATURE_INVALID",
            resign=False,
        )
        report = evaluation.report.report()
        self.assertFalse(report["signatures_valid"])
        self.assertFalse(report["semantic_core_valid"])

    def test_strict_ed25519_subgroup_check_rejects_torsion_components(self) -> None:
        basepoint = bytes.fromhex("58" + "66" * 31)
        identity = bytes.fromhex("01" + "00" * 31)
        order_two = bytes.fromhex("ec" + "ff" * 30 + "7f")
        basepoint_plus_order_two = bytes.fromhex("95" + "99" * 31)
        self.assertTrue(_is_strict_ed25519_point(basepoint))
        self.assertFalse(_is_strict_ed25519_point(identity))
        self.assertFalse(_is_strict_ed25519_point(order_two))
        self.assertFalse(_is_strict_ed25519_point(basepoint_plus_order_two))
        with self.assertRaises(ValueError):
            _multiply_ed25519_point((0, 1, 1, 0), -1)
        self.assertFalse(_is_ed25519_identity((0, 0, 0, 0)))

    def test_noncanonical_public_key_and_wrong_trust_digest_block(self) -> None:
        malformed_trust = copy.deepcopy(self.trust)
        malformed_trust["role_bindings"][0]["public_key_base64url"] = (
            noncanonical_last_base64url_character(
                malformed_trust["role_bindings"][0]["public_key_base64url"]
            )
        )
        malformed_raw = encode_json(malformed_trust)
        request = premetadata_request(self.installed, _sha256(malformed_raw))
        request = sign_request(request, self.trust, self.keys)
        with self.assertRaises(NMFAPreflightError) as caught:
            self.evaluate_premetadata(
                request,
                trust=malformed_trust,
                trust_raw=malformed_raw,
            )
        self.assertEqual(
            caught.exception.code,
            NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
        )

        with self.assertRaises(NMFAPreflightError) as caught:
            self.evaluate_premetadata(
                self.premetadata,
                expected_trust_sha256=digest("incorrect-expected-digest"),
            )
        self.assertEqual(
            caught.exception.code,
            NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
        )

    def test_role_separation_duplicate_actor_is_blocking(self) -> None:
        duplicate = copy.deepcopy(self.trust)
        duplicate["role_bindings"][1]["actor_id"] = duplicate["role_bindings"][0]["actor_id"]
        duplicate_raw = encode_json(duplicate)
        request = premetadata_request(self.installed, _sha256(duplicate_raw))
        request = sign_request(request, duplicate, self.keys)
        with self.assertRaises(NMFAPreflightError) as caught:
            self.evaluate_premetadata(
                request,
                trust=duplicate,
                trust_raw=duplicate_raw,
            )
        self.assertEqual(
            caught.exception.code,
            NMFAPreflightErrorCode.TRUST_PROFILE_CONTRACT_INVALID,
        )
        self.assertIn(
            "ROLE_SEPARATION_INVALID",
            _premetadata_semantics(request, duplicate),
        )

    def test_resource_binding_chronology_and_ledger_fail_closed(self) -> None:
        self.assert_premetadata_reason(
            lambda value: value["bindings"].__setitem__(
                "parent_protocol_sha256", digest("substituted-parent")
            ),
            "RESOURCE_BINDING_MISMATCH",
        )

        def chronology(value: dict[str, Any]) -> None:
            value["no_access_ledger"]["recorded_at"] = "2026-06-01T00:01:30Z"
            value["no_access_ledger"]["event_head_sha256"] = _ledger_head(value["no_access_ledger"])

        self.assert_premetadata_reason(chronology, "CHRONOLOGY_INVALID")
        self.assert_premetadata_reason(
            lambda value: value["no_access_ledger"].__setitem__(
                "event_head_sha256", digest("tampered-ledger-head")
            ),
            "ACCESS_LEDGER_INVALID",
        )

    def test_package_resource_substitution_is_fixed_code_failure(self) -> None:
        corrupted = replace(self.resources, plan=self.resources.plan + b" ")
        with self.assertRaises(NMFAPreflightError) as caught:
            _installed(corrupted)
        self.assertEqual(caught.exception.code, NMFAPreflightErrorCode.PACKAGE_RESOURCE_INVALID)

    def test_prevalue_fixture_is_schema_valid_signed_and_semantically_closed(self) -> None:
        _, subject = _request_subject(self.prevalue)
        self.assertTrue(
            _verify_signatures(
                self.prevalue,
                subject,
                self.trust,
                True,
            )
        )
        self.assertEqual(
            _prevalue_semantics(
                self.prevalue,
                self.ready_premetadata_evaluation,
                self.trust,
            ),
            set(),
        )

    def test_installed_prevalue_cannot_cross_blocked_premetadata(self) -> None:
        installed_prevalue = sign_request(
            prevalue_request(self.premetadata_evaluation),
            self.trust,
            self.keys,
        )
        with patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources):
            report = evaluate_prevalue_preflight(
                self.premetadata_raw,
                self.premetadata_evaluation.report.report_bytes,
                encode_json(installed_prevalue),
                self.trust_raw,
                self.trust_sha256,
            )
        self.assertEqual(report.terminal_state, "PREVALUE_BLOCKED")
        self.assertIn("PREMETADATA_CHAIN_INVALID", report.reason_codes)
        self.assertTrue(report.report()["signatures_valid"])
        self.assertFalse(report.report()["semantic_core_valid"])

    def test_predecessor_report_must_be_byte_identical_to_reexecution(self) -> None:
        changed = self.premetadata_evaluation.report.report()
        changed["report_sha256"] = digest("schema-valid-but-not-identical-report")
        with (
            patch("indusbench.nmfa_preflight._load_resources", return_value=self.resources),
            self.assertRaises(NMFAPreflightError) as caught,
        ):
            evaluate_prevalue_preflight(
                self.premetadata_raw,
                encode_json(changed),
                encode_json(self.prevalue),
                self.trust_raw,
                self.trust_sha256,
            )
        self.assertEqual(caught.exception.code, NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)

    def test_inventory_order_duplicate_and_unknown_exposure_are_blocked(self) -> None:
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["source_records"][0].__setitem__("source_order", 1),
            "INVENTORY_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["source_records"][1].__setitem__(
                "entry_id", value["inventory"]["source_records"][0]["entry_id"]
            ),
            "INVENTORY_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["prevalue_exposure"][0].__setitem__(
                "status", "UNKNOWN"
            ),
            "ACCESS_LEDGER_INVALID",
        )

    def test_epre_context_and_nuisance_contributions_are_typed_and_ordered(self) -> None:
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["units"][0]["context_axes"].reverse(),
            "PREVALUE_E_CONTRIBUTION_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["units"][0]["context_axes"][0].__setitem__(
                "value_id", None
            ),
            "PREVALUE_E_CONTRIBUTION_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["units"][0]["nuisance_values"][0].__setitem__(
                "value_ids", []
            ),
            "PREVALUE_E_CONTRIBUTION_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["units"][0].__setitem__(
                "epre_reason_codes", ["RIGHTS_INSUFFICIENT"]
            ),
            "PREVALUE_E_CONTRIBUTION_INVALID",
        )

    def test_relation_archive_and_barrier_contracts_are_bound(self) -> None:
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["declared_pre_x_relation_edges"][0].__setitem__(
                "right_f_id", opaque("unknown-f")
            ),
            "RELATION_CONTRIBUTION_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["archives"]["target_y"].__setitem__("planned_f_count", 99),
            "ARCHIVE_PREPARE_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["barriers"]["target_y"].__setitem__(
                "archive_contract_sha256", digest("wrong-archive-contract")
            ),
            "VALUE_BARRIER_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["barriers"]["target_y"].__setitem__(
                "sequence", value["barriers"]["transcription_x"]["sequence"]
            ),
            "VALUE_BARRIER_INVALID",
        )
        self.assert_prevalue_reason(
            lambda value: value["barriers"]["target_y"].__setitem__(
                "cas_token_commitment_sha256",
                value["barriers"]["transcription_x"]["cas_token_commitment_sha256"],
            ),
            "VALUE_BARRIER_INVALID",
        )

    def test_forbidden_value_surface_or_extra_field_is_contract_failure(self) -> None:
        request = copy.deepcopy(self.prevalue)
        request["target_y"] = [1, 2, 3]
        with self.assertRaises(NMFAPreflightError) as caught:
            from indusbench.nmfa_preflight import _parse_request

            _parse_request(encode_json(request), self.resources, "PREVALUE")
        self.assertEqual(caught.exception.code, NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)

        request = copy.deepcopy(self.prevalue)
        request["prediction_or_score_present"] = True
        with self.assertRaises(NMFAPreflightError) as caught:
            from indusbench.nmfa_preflight import _parse_request

            _parse_request(encode_json(request), self.resources, "PREVALUE")
        self.assertEqual(caught.exception.code, NMFAPreflightErrorCode.REQUEST_CONTRACT_INVALID)

    def test_premetadata_requires_zero_metadata_access(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["no_access_ledger"]["metadata_access_count"] = 1
            value["no_access_ledger"]["event_head_sha256"] = _ledger_head(value["no_access_ledger"])

        self.assert_premetadata_reason(mutate, "ACCESS_LEDGER_INVALID")

    def test_claim_family_is_bound_into_reservation_and_ceremony(self) -> None:
        self.assert_premetadata_reason(
            lambda value: value.__setitem__("claim_family_id", opaque("different-family")),
            "PREMETADATA_CHAIN_INVALID",
        )

    def test_first_metadata_access_head_is_recomputed(self) -> None:
        request = copy.deepcopy(self.prevalue)
        request["first_metadata_access"]["metadata_projection_contract_sha256"] = digest(
            "tampered-projection-contract"
        )
        request["access_ledger"]["prior_event_head_sha256"] = request["first_metadata_access"][
            "event_head_sha256"
        ]
        request["access_ledger"]["event_head_sha256"] = _ledger_head(request["access_ledger"])
        reasons = _prevalue_semantics(
            request,
            self.ready_premetadata_evaluation,
            self.trust,
        )
        self.assertIn("ACCESS_LEDGER_INVALID", reasons)

    def test_exposure_cutoff_is_exact_access_ledger_head(self) -> None:
        self.assert_prevalue_reason(
            lambda value: value["inventory"].__setitem__(
                "exposure_cutoff_event_head_sha256", digest("wrong-exposure-cutoff")
            ),
            "ACCESS_LEDGER_INVALID",
        )

    def test_prevalue_continues_the_same_declared_access_ledger(self) -> None:
        self.assert_prevalue_reason(
            lambda value: value["access_ledger"].__setitem__(
                "ledger_id", opaque("different-ledger")
            ),
            "ACCESS_LEDGER_INVALID",
        )

    def test_only_confirmed_relations_can_union(self) -> None:
        self.assert_prevalue_reason(
            lambda value: value["inventory"]["declared_pre_x_relation_edges"][0].__setitem__(
                "status", "POSSIBLE"
            ),
            "RELATION_CONTRIBUTION_INVALID",
        )

    def test_empty_declared_relation_edge_set_is_not_complete_r0_claim(self) -> None:
        request = copy.deepcopy(self.prevalue)
        request["inventory"]["declared_pre_x_relation_edges"] = []
        reasons = _prevalue_semantics(
            request,
            self.ready_premetadata_evaluation,
            self.trust,
        )
        self.assertNotIn("RELATION_CONTRIBUTION_INVALID", reasons)
        self.assertEqual(
            self.installed.plan["installed_semantic_scope"]["relation_edges"],
            "DECLARED_SET_STRUCTURE_ONLY",
        )

    def test_evaluator_has_no_network_random_subprocess_clock_or_write_surface(self) -> None:
        source = (ROOT / "src/indusbench/nmfa_preflight.py").read_text()
        tree = ast.parse(source)
        forbidden_imports = {
            "http",
            "httpx",
            "os",
            "random",
            "requests",
            "secrets",
            "socket",
            "subprocess",
            "time",
            "urllib",
        }
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(imported_roots & forbidden_imports)
        forbidden_calls = {
            "open",
            "write",
            "write_bytes",
            "write_text",
            "now",
            "utcnow",
        }
        observed_calls = {
            (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        self.assertFalse(observed_calls & forbidden_calls)
        self.assertNotIn("not in set(f_ids)", source)


if __name__ == "__main__":
    unittest.main()
