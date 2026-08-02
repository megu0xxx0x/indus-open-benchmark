from __future__ import annotations

import copy
import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from indusbench.io import encode_json, read_json
from indusbench.nmfa_preregistration import (
    _CLAIM_SLOT_RESERVATION_DOMAIN,
    _CONTEXT_CONTRACT_DOMAIN,
    _FREEZE_SEQUENCE_DOMAIN,
    _IDENTIFIER_KEY_CEREMONY_DOMAIN,
    _MANIFEST_DOMAIN,
    _NUISANCE_VOCABULARY_DOMAIN,
    _POPULATION_DOMAIN,
    _POPULATION_FREEZE_CLAIM_DOMAIN,
    _PREINVENTORY_CONTRACT_DOMAIN,
    _RECEIPT_DOMAIN,
    _RELATION_POLICY,
    _RELATION_POLICY_DOMAIN,
    _RIGHTS_EVIDENCE_DOMAIN,
    _SEALED_F_ROSTER_DOMAIN,
    _SOURCE_FRAME_DOMAIN,
    _SPLIT_STRUCTURAL_INPUT_DOMAIN,
    _TARGET_SEAL_DOMAIN,
    _TRANSCRIPTION_SEAL_DOMAIN,
    NMFAPreregistrationError,
    NMFAPreregistrationErrorCode,
    _eligible_split_inventory_digest,
    _evaluate_with_resources,
    _population_semantics,
    _primary_f,
    _Resources,
    _tuple_search,
    _validate_manifest_with_resources,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json"
BUNDLE_PATH = ROOT / "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"
PLAN_SCHEMA_PATH = ROOT / "schemas/nmfa-value-blind-preregistration-gate-plan.schema.json"
MANIFEST_SCHEMA_PATH = ROOT / "schemas/nmfa-value-blind-preregistration-manifest.schema.json"
REPORT_SCHEMA_PATH = ROOT / "schemas/nmfa-value-blind-preregistration-report.schema.json"
PARENT_PATH = ROOT / "benchmark/numeral-metrology-functional-anchor-protocol-v1.json"

PARENT_SHA256 = "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307"
AXES = ("site", "period", "medium", "object_type")
LAYERS = (
    "source_frame_metadata",
    "transcription_x",
    "context_c",
    "physical_identity_f",
    "dependence_g",
    "target_y",
    "derived_aggregate",
)
PURPOSES = (
    "analyze",
    "custodial_transfer",
    "derive",
    "prize_submit",
    "publish_aggregate",
    "publish_item",
    "retain_protected",
    "retrieve",
)
TEST_ID_KEY = hashlib.sha256(b"nmfa-synthetic-test-key-only").digest()


def checksum(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def opaque(label: str) -> str:
    digest = hmac.new(
        TEST_ID_KEY,
        b"indusbench:nmfa:synthetic-id:v1\x00" + label.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return "hmac-sha256:" + digest


def registry_id(label: str) -> str:
    return "registry-id:" + hashlib.sha256(("nmfa-registry-test:" + label).encode()).hexdigest()


def domain_digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + encode_json(value)).hexdigest()


def resources() -> _Resources:
    return _Resources(
        evaluator_bundle=BUNDLE_PATH.read_bytes(),
        io_source=(ROOT / "src/indusbench/io.py").read_bytes(),
        module_source=(ROOT / "src/indusbench/nmfa_preregistration.py").read_bytes(),
        plan=PLAN_PATH.read_bytes(),
        plan_schema=PLAN_SCHEMA_PATH.read_bytes(),
        manifest_schema=MANIFEST_SCHEMA_PATH.read_bytes(),
        report_schema=REPORT_SCHEMA_PATH.read_bytes(),
        parent_protocol=PARENT_PATH.read_bytes(),
    )


def context_for(index: int) -> dict[str, Any]:
    pair = index // 2
    if index < 20:
        values = ("selected-site", f"period-{pair}", f"medium-{pair}", f"object-{pair}")
    elif index < 40:
        values = (f"site-{pair}", "selected-period", f"medium-{pair}", f"object-{pair}")
    elif index < 60:
        values = (f"site-{pair}", f"period-{pair}", "selected-medium", f"object-{pair}")
    elif index < 80:
        values = (f"site-{pair}", f"period-{pair}", f"medium-{pair}", "selected-object")
    else:
        values = (f"site-{pair}", f"period-{pair}", f"medium-{pair}", f"object-{pair}")
    context: dict[str, Any] = {
        axis: opaque(value) for axis, value in zip(AXES, values, strict=True)
    }
    context["nuisance"] = [opaque(f"nuisance-{pair}")]
    return context


def closure_tables(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables = []
    for axis in AXES:
        values = sorted(
            {unit["context"][axis] for unit in units if type(unit["context"][axis]) is str}
        )
        tables.append(
            {
                "axis": axis,
                "groups": [{"group_id": value, "member_value_ids": [value]} for value in values],
            }
        )
    return tables


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
        "axis_order": list(AXES),
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
    manifest: dict[str, Any], bindings: dict[str, Any]
) -> dict[str, Any]:
    sequence = manifest["freeze_sequence"]
    return {
        "claim_slot_reservation_receipt": sequence["claim_slot_reservation_receipt"],
        "claim_slot_reservation_sha256": bindings["claim_slot_reservation_sha256"],
        "claim_slot_id": manifest["claim_policy"]["claim_slot_id"],
        "evaluator_bundle_sha256": bindings["evaluator_bundle_sha256"],
        "evidence_envelope_contract": manifest["evidence_envelope_contract"],
        "experiment_instance_id": manifest["experiment_instance_id"],
        "gate_plan_sha256": bindings["gate_plan_sha256"],
        "identifier_key_ceremony_sha256": bindings["identifier_key_ceremony_sha256"],
        "identifier_key_generation_receipt": sequence["identifier_key_generation_receipt"],
        "parent_protocol_sha256": bindings["parent_protocol_sha256"],
        "population_inventory_sha256": bindings["population_inventory_sha256"],
        "preinventory_contract_receipt": sequence["preinventory_contract_receipt"],
        "preinventory_contract_sha256": bindings["preinventory_contract_sha256"],
        "source_frame_sha256": bindings["source_frame_sha256"],
        "split_structural_input_sha256": bindings["split_structural_input_sha256"],
        "earliest_target_y_access_receipt": sequence["earliest_target_y_access_receipt"],
        "target_seal_receipt": sequence["target_seal_receipt"],
        "target_seal_sha256": bindings["target_seal_sha256"],
        "earliest_transcription_x_access_receipt": sequence[
            "earliest_transcription_x_access_receipt"
        ],
        "clean_roles_first_claim_instance_source_metadata_access_receipt": sequence[
            "clean_roles_first_claim_instance_source_metadata_access_receipt"
        ],
        "transcription_seal_receipt": sequence["transcription_seal_receipt"],
        "transcription_seal_sha256": bindings["transcription_seal_sha256"],
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


def finalize(manifest: dict[str, Any]) -> dict[str, Any]:
    bindings = manifest["bindings"]
    sequence = manifest["freeze_sequence"]
    bindings["claim_slot_reservation_sha256"] = domain_digest(
        _CLAIM_SLOT_RESERVATION_DOMAIN, _claim_slot_reservation_payload(manifest)
    )
    sequence["claim_slot_reservation_receipt"]["subject_sha256"] = bindings[
        "claim_slot_reservation_sha256"
    ]
    bindings["identifier_key_ceremony_sha256"] = domain_digest(
        _IDENTIFIER_KEY_CEREMONY_DOMAIN,
        _identifier_key_ceremony_payload(manifest, bindings["claim_slot_reservation_sha256"]),
    )
    sequence["identifier_key_generation_receipt"]["subject_sha256"] = bindings[
        "identifier_key_ceremony_sha256"
    ]
    sequence["clean_roles_first_claim_instance_source_metadata_access_receipt"][
        "subject_sha256"
    ] = bindings["identifier_key_ceremony_sha256"]
    bindings["context_contract_sha256"] = domain_digest(
        _CONTEXT_CONTRACT_DOMAIN, manifest["context_contract"]
    )
    bindings["preinventory_contract_sha256"] = domain_digest(
        _PREINVENTORY_CONTRACT_DOMAIN, _preinventory_payload(manifest)
    )
    bindings["population_inventory_sha256"] = domain_digest(
        _POPULATION_DOMAIN, _population_payload(manifest)
    )
    bindings["relation_policy_sha256"] = domain_digest(_RELATION_POLICY_DOMAIN, _RELATION_POLICY)
    bindings["rights_evidence_set_sha256"] = (
        domain_digest(_RIGHTS_EVIDENCE_DOMAIN, manifest["rights"])
        if all(row["evidence_sha256"] is not None for row in manifest["rights"])
        else None
    )
    bindings["source_frame_sha256"] = domain_digest(
        _SOURCE_FRAME_DOMAIN, _source_frame_payload(manifest)
    )
    bindings["split_structural_input_sha256"] = domain_digest(
        _SPLIT_STRUCTURAL_INPUT_DOMAIN, _split_structural_input_payload(manifest)
    )
    bindings["target_seal_sha256"] = domain_digest(
        _TARGET_SEAL_DOMAIN, manifest["sealed_datasets"]["target_y"]
    )
    bindings["transcription_seal_sha256"] = domain_digest(
        _TRANSCRIPTION_SEAL_DOMAIN, manifest["sealed_datasets"]["transcription_x"]
    )
    sequence["preinventory_contract_receipt"]["subject_sha256"] = bindings[
        "preinventory_contract_sha256"
    ]
    sequence["earliest_target_y_access_receipt"]["subject_sha256"] = bindings[
        "preinventory_contract_sha256"
    ]
    sequence["earliest_transcription_x_access_receipt"]["subject_sha256"] = bindings[
        "preinventory_contract_sha256"
    ]
    sequence["target_seal_receipt"]["subject_sha256"] = bindings["target_seal_sha256"]
    sequence["transcription_seal_receipt"]["subject_sha256"] = bindings["transcription_seal_sha256"]
    bindings["population_freeze_claim_sha256"] = domain_digest(
        _POPULATION_FREEZE_CLAIM_DOMAIN,
        _population_freeze_claim_payload(manifest, bindings),
    )
    sequence["population_inventory_receipt"]["subject_sha256"] = bindings[
        "population_freeze_claim_sha256"
    ]
    bindings["freeze_sequence_sha256"] = domain_digest(_FREEZE_SEQUENCE_DOMAIN, sequence)
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = (
        "sha256:" + hashlib.sha256(_MANIFEST_DOMAIN + encode_json(payload)).hexdigest()
    )
    return manifest


def ready_manifest(unit_count: int = 160) -> dict[str, Any]:
    units = []
    for index in range(unit_count):
        units.append(
            {
                "context": context_for(index),
                "context_evidence_envelope_sha256": checksum(f"context-{index}"),
                "f_id": opaque(f"f-{index:05d}"),
                "physical_identity_evidence_envelope_sha256": checksum(f"identity-{index}"),
                "relation_coverage_evidence_envelope_sha256": checksum(f"relations-{index}"),
                "source_membership_complete": True,
            }
        )
    units.sort(key=lambda unit: unit["f_id"])
    eligibility = [
        {
            "all_applicable_reason_codes_recorded": True,
            "attestation_id": opaque(f"eligibility-{unit['f_id']}"),
            "eligible": True,
            "f_id": unit["f_id"],
            "g_exclusion_reason": "NONE",
            "prior_project_exposure": False,
            "reason_codes": ["ELIGIBLE"],
        }
        for unit in units
    ]
    source_records = []
    for index, unit in enumerate(units):
        source_records.append(
            {
                "f_id": unit["f_id"],
                "source_entry_id": opaque(f"source-entry-{index}"),
                "source_entry_kind": "catalog_record",
                "source_order": index,
                "source_record_id": opaque(f"source-record-{index}"),
                "source_revision_id": opaque("source-revision-1"),
                "source_view_id": opaque(f"source-view-{index}"),
            }
        )
    if units:
        source_records.append(
            {
                "f_id": units[0]["f_id"],
                "source_entry_id": opaque("source-entry-alias"),
                "source_entry_kind": "cross_edition_record",
                "source_order": len(source_records),
                "source_record_id": opaque("source-record-alias"),
                "source_revision_id": opaque("source-revision-alias"),
                "source_view_id": opaque("source-view-alias"),
            }
        )
    rights = [
        {
            "evidence_sha256": checksum(f"rights-{layer}"),
            "layer": layer,
            "purposes": {purpose: "permitted" for purpose in PURPOSES},
        }
        for layer in LAYERS
    ]
    plan = read_json(PLAN_PATH)
    plan_sha256 = "sha256:" + hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
    experiment_instance_id = registry_id("experiment-instance")
    claim_slot_id = registry_id("claim-slot")
    nuisance_vocabularies = [
        {
            "canonical_value_ids": sorted({unit["context"]["nuisance"][0] for unit in units}),
            "field_id": opaque("nuisance-field-0"),
        }
    ]

    def sealed_dataset(layer: str) -> dict[str, Any]:
        if layer == "transcription_x":
            role = "independent_transcription_archive_custodian"
            scope = (
                "all_F_to_approved_X_or_explicit_status_with_side_line_token_allograph_order_"
                "and_source_revision_binding"
            )
        else:
            role = "independent_target_archive_custodian"
            scope = (
                "all_F_to_exact_rational_Y_or_explicit_status_with_family_unit_conversion_"
                "missingness_and_repeated_resolution"
            )
        roster_digest = domain_digest(
            _SEALED_F_ROSTER_DOMAIN,
            {
                "claim_slot_id": claim_slot_id,
                "data_layer": layer,
                "experiment_instance_id": experiment_instance_id,
                "ordered_f_ids": [unit["f_id"] for unit in units],
            },
        )
        return {
            "commitment": {
                "canonical_f_order": True,
                "ciphertext_archive_manifest_sha256": checksum(f"{layer}-archive-manifest"),
                "ciphertext_merkle_root_sha256": checksum(f"{layer}-merkle-root"),
                "committed_f_count": len(units),
                "complete_f_roster_covered": True,
                "ordered_f_roster_sha256": roster_digest,
                "plaintext_digest_present": False,
                "seal_created_before_population_receipt": True,
            },
            "contract": {
                "algorithm": "XChaCha20-Poly1305-record-AEAD-SHA256-Merkle-v1",
                "archive_custodian_role": role,
                "canonical_payload_contract_sha256": checksum(f"{layer}-payload-contract"),
                "encryption_profile_sha256": checksum(f"{layer}-encryption-profile"),
                "independent_random_record_keys": True,
                "leaf_aad_contract_sha256": checksum(f"{layer}-leaf-aad-contract"),
                "merkle_profile_sha256": checksum(f"{layer}-merkle-profile"),
                "payload_scope": scope,
                "record_keys_independently_wrapped_for_staged_release": True,
                "separate_archive_and_keys_from_other_layer": True,
                "unique_random_nonce_per_record": True,
            },
            "data_layer": layer,
        }

    manifest: dict[str, Any] = {
        "bindings": {
            "claim_slot_reservation_sha256": checksum("placeholder-claim-reservation"),
            "context_contract_sha256": checksum("placeholder-context"),
            "custody_contract_sha256": checksum("custody-contract"),
            "evaluator_bundle_sha256": "sha256:"
            + hashlib.sha256(BUNDLE_PATH.read_bytes()).hexdigest(),
            "freeze_sequence_sha256": checksum("placeholder-freeze"),
            "gate_plan_sha256": plan_sha256,
            "identifier_key_ceremony_sha256": checksum("placeholder-identifier-ceremony"),
            "manifest_sha256_domain": "indusbench:nmfa:preregistration-manifest:v1",
            "parent_protocol_sha256": "sha256:" + PARENT_SHA256,
            "population_inventory_sha256": checksum("placeholder-population"),
            "population_freeze_claim_sha256": checksum("placeholder-freeze-claim"),
            "preinventory_contract_sha256": checksum("placeholder-preinventory"),
            "relation_policy_sha256": checksum("placeholder-relations"),
            "rights_evidence_set_sha256": checksum("placeholder-rights"),
            "source_frame_sha256": checksum("placeholder-frame"),
            "split_structural_input_sha256": checksum("placeholder-split-structural"),
            "target_seal_sha256": checksum("placeholder-target-seal"),
            "transcription_seal_sha256": checksum("placeholder-transcription-seal"),
        },
        "claim_policy": {
            "aborted_and_prior_slots_must_be_enumerable": True,
            "claim_family_id": registry_id("claim-family"),
            "claim_slot_id": claim_slot_id,
            "external_registry_single_active_chain_required": True,
            "fork_or_parallel_registration_forbidden": True,
            "prior_chain_head_sha256": None,
            "registry_scope_evidence_sha256": checksum("registry-scope-evidence"),
            "supersession_after_external_registration_forbidden": True,
        },
        "context_contract": {
            "alias_and_descendant_closures_frozen": True,
            "axis_mapping_rule_sha256": checksum("axis-mapping-rule"),
            "canonical_vocabularies_frozen": True,
            "closure_tables": closure_tables(units),
            "multiple_or_overlapping_values_ineligible": True,
            "nuisance_field_ids": [opaque("nuisance-field-0")],
            "nuisance_fields_complete": True,
            "nuisance_mapping_rule_sha256": checksum("nuisance-mapping-rule"),
            "nuisance_value_vocabularies_sha256": domain_digest(
                _NUISANCE_VOCABULARY_DOMAIN, nuisance_vocabularies
            ),
            "nuisance_vocabularies": nuisance_vocabularies,
            "provenance_policy": "complete_canonical_nuisance_tuple",
            "single_regime_contract_sha256": None,
            "taxonomy_evidence_sha256": checksum("taxonomy-evidence"),
            "unknown_values_ineligible": True,
        },
        "created_at": "2026-08-03T01:10:00Z",
        "eligibility": eligibility,
        "evidence_envelope_contract": {
            "algorithm": "randomized_AEAD_or_signed_nonce_envelope",
            "external_rederivation_and_content_review_required": True,
            "profile_sha256": checksum("evidence-envelope-profile"),
            "raw_source_context_transcription_or_target_digest_forbidden": True,
        },
        "experiment_instance_id": experiment_instance_id,
        "exposure": {
            "development_subset_values_released": False,
            "holdout_mapping_opened": False,
            "holdout_x_seen_by_evaluator_or_model_before_model_freeze": False,
            "holdout_y_seen_before_prediction_manifest_freeze": False,
            "numeric_y_seen_by_context_curator_role": False,
            "numeric_y_seen_by_evaluator_role": False,
            "numeric_y_seen_by_identifier_custodian_role": False,
            "numeric_y_seen_by_physical_identity_curator_role": False,
            "numeric_y_seen_by_relation_curator_role": False,
            "numeric_y_seen_by_split_role": False,
            "numeric_y_seen_by_source_frame_curator_role": False,
            "numeric_y_seen_by_target_seal_custodian_role": True,
            "numeric_y_seen_by_target_curator": True,
            "numeric_y_seen_by_transcription_role": False,
            "numeric_y_seen_by_transcription_seal_custodian_role": False,
            "score_or_prediction_material_present": False,
            "score_or_predictions_seen_by_target_curator_role": False,
            "sealed_record_keys_released_before_external_registration": False,
            "source_records_seen_by_curator_roles": True,
            "transcription_x_seen_by_evaluator_or_model_before_split_receipt": False,
            "transcription_x_seen_by_identifier_custodian_role": False,
            "transcription_x_seen_by_relation_curator_role": False,
            "transcription_x_seen_by_target_seal_custodian_role": False,
            "transcription_x_seen_by_target_curator_role": False,
            "transcription_x_seen_by_transcription_role": True,
            "transcription_x_seen_by_transcription_seal_custodian_role": True,
            "unkeyed_target_value_digest_present": False,
        },
        "exposure_control": {
            "candidate_coverage_complete": True,
            "exposed_f_marking_complete": True,
            "exposed_g_ineligible": True,
            "project_access_ledger_sha256": checksum("project-access-ledger"),
            "audit_plaintext_or_keys_release_forbidden": True,
            "audit_roles_separate_from_identifier_source_frame_physical_identity_and_"
            "context_roles": True,
            "base_e_joint_derivation_contract_sha256": checksum("base-e-joint-derivation-contract"),
            "external_registration_review_rederives_complete_base_e_and_component_exclusions": True,
            "independent_transcription_audit_custodian_in_place_pre_registration_"
            "rederivation_required": True,
            "independent_target_audit_custodian_in_place_pre_registration_"
            "rederivation_required": True,
            "prevalue_exact_source_record_f_context_and_prior_exposure_inventory_committed": True,
            "relation_curator_receives_only_relation_graph_and_evidence_envelopes": True,
            "relation_derivation_before_seal_role": "transcription_curator",
            "target_auditor_distinct_from_originating_curator_and_seal_custodian": True,
            "target_audit_role_separate_from_transcription_context_relation_split_evaluator_"
            "and_model_roles": True,
            "target_audit_rederives_target_contract_all_f_roster_target_e_contribution_and_"
            "exact_y_or_status": True,
            "transcription_audit_rederives_all_f_exact_x_or_status_source_revision_"
            "transcription_e_and_complete_relations": True,
            "transcription_audit_role_separate_from_relation_split_evaluator_model_and_"
            "target_roles": True,
            "transcription_auditor_distinct_from_originating_curator_and_seal_custodian": True,
        },
        "format_version": "1.0.0",
        "freeze_sequence": {
            "claim_slot_reservation_receipt": {
                "attestor_key_id": opaque("reservation-attestor"),
                "receipt_id": opaque("reservation-receipt"),
                "receipt_kind": "claim_slot_reservation",
                "recorded_at": "2026-08-03T00:00:00Z",
                "signed_receipt_evidence_sha256": checksum("reservation-signed-receipt"),
                "subject_sha256": checksum("placeholder-claim-reservation"),
            },
            "external_timestamp_validation": "not_performed_by_gate",
            "identifier_key_generation_receipt": {
                "attestor_key_id": opaque("identifier-key-attestor"),
                "receipt_id": opaque("identifier-key-receipt"),
                "receipt_kind": "identifier_key_ceremony",
                "recorded_at": "2026-08-03T00:10:00Z",
                "signed_receipt_evidence_sha256": checksum("identifier-key-signed-receipt"),
                "subject_sha256": checksum("placeholder-identifier-ceremony"),
            },
            "population_inventory_receipt": {
                "attestor_key_id": opaque("population-attestor"),
                "receipt_id": opaque("population-receipt"),
                "receipt_kind": "population_freeze_claim",
                "recorded_at": "2026-08-03T01:00:00Z",
                "signed_receipt_evidence_sha256": checksum("population-signed-receipt"),
                "subject_sha256": checksum("placeholder-population"),
            },
            "preinventory_contract_receipt": {
                "attestor_key_id": opaque("preinventory-attestor"),
                "receipt_id": opaque("preinventory-receipt"),
                "receipt_kind": "preinventory_contract",
                "recorded_at": "2026-08-03T00:30:00Z",
                "signed_receipt_evidence_sha256": checksum("preinventory-signed-receipt"),
                "subject_sha256": checksum("placeholder-preinventory"),
            },
            "earliest_target_y_access_receipt": {
                "attestor_key_id": opaque("target-attestor"),
                "receipt_id": opaque("target-access-receipt"),
                "receipt_kind": "earliest_target_y_access",
                "recorded_at": "2026-08-03T00:41:00Z",
                "signed_receipt_evidence_sha256": checksum("target-access-signed-receipt"),
                "subject_sha256": checksum("placeholder-preinventory"),
            },
            "target_seal_receipt": {
                "attestor_key_id": opaque("target-seal-attestor"),
                "receipt_id": opaque("target-seal-receipt"),
                "receipt_kind": "target_seal",
                "recorded_at": "2026-08-03T00:51:00Z",
                "signed_receipt_evidence_sha256": checksum("target-seal-signed-receipt"),
                "subject_sha256": checksum("placeholder-target-seal"),
            },
            "target_values_revealed_to_evaluator_at": None,
            "earliest_transcription_x_access_receipt": {
                "attestor_key_id": opaque("transcription-attestor"),
                "receipt_id": opaque("transcription-access-receipt"),
                "receipt_kind": "earliest_transcription_x_access",
                "recorded_at": "2026-08-03T00:40:00Z",
                "signed_receipt_evidence_sha256": checksum("transcription-access-signed-receipt"),
                "subject_sha256": checksum("placeholder-preinventory"),
            },
            "transcription_seal_receipt": {
                "attestor_key_id": opaque("transcription-seal-attestor"),
                "receipt_id": opaque("transcription-seal-receipt"),
                "receipt_kind": "transcription_seal",
                "recorded_at": "2026-08-03T00:50:00Z",
                "signed_receipt_evidence_sha256": checksum("transcription-seal-signed-receipt"),
                "subject_sha256": checksum("placeholder-transcription-seal"),
            },
            "clean_roles_first_claim_instance_source_metadata_access_receipt": {
                "attestor_key_id": opaque("source-metadata-attestor"),
                "receipt_id": opaque("source-metadata-access-receipt"),
                "receipt_kind": "clean_roles_first_claim_instance_source_metadata_access",
                "recorded_at": "2026-08-03T00:20:00Z",
                "signed_receipt_evidence_sha256": checksum("source-metadata-access-signed-receipt"),
                "subject_sha256": checksum("placeholder-identifier-ceremony"),
            },
        },
        "governance": {
            "authority_evidence_sha256": checksum("authority-evidence"),
            "external_registration_capability": "verified",
            "independent_role_separation_capability": "verified",
            "protected_custody_capability": "verified",
            "registration_route_evidence_sha256": checksum("registration-route"),
            "role_assignment_contract_sha256": checksum("role-assignment"),
            "role_separation_evidence_sha256": checksum("role-separation"),
            "source_access_authority": "authorized",
        },
        "identifier_contract": {
            "algorithm": "HMAC-SHA256",
            "canonicalization_rule_sha256": checksum("identifier-canonicalization"),
            "domain_separation_rule_sha256": checksum("identifier-domains"),
            "input_framing_sha256": checksum("identifier-framing"),
            "key_commitment_sha256": checksum("synthetic-key-commitment"),
            "key_disclosed": False,
            "key_generated_before_claim_instance_identifier_mapping_access": True,
            "key_generation_profile": "CSPRNG_minimum_256_bits",
            "key_holder_role": "independent_identifier_custodian",
            "full_rederivation_at_external_review_required": True,
            "rotation_or_resalting_allowed": False,
        },
        "manifest_sha256": checksum("placeholder-manifest"),
        "n1_deferred_contract": {
            "actual_candidate_classes_present": False,
            "sample_assignments_frozen": False,
            "sample_assignment_freeze_stage": (
                "post_holdout_prediction_manifest_pre_holdout_y_open"
            ),
            "sampler_contract_sha256": domain_digest(
                b"indusbench:nmfa:n1-sampler-contract:v1\x00", plan["n1"]["sampler"]
            ),
            "support_feasibility_evaluated": False,
            "support_feasibility_stage": "model_frozen_pre_holdout_x_open",
        },
        "nonce_event_contract": {
            "event_anchor": "first_qualifying_event_strictly_after_external_registration_receipt",
            "event_selection_rule_sha256": checksum("nonce-event"),
            "extraction_rule_sha256": checksum("nonce-extraction"),
            "minimum_entropy_bits": 128,
            "provider_rule_sha256": checksum("nonce-provider"),
            "retry_or_resalt_allowed": False,
            "target_event_value_present": False,
        },
        "prospective": {
            "complete_future_frame_committed": True,
            "first_availability_policy_committed": True,
            "first_availability_rule_sha256": checksum("first-availability"),
            "fixed_close_date_rule_committed": True,
            "fixed_close_date_rule_sha256": checksum("fixed-close"),
            "future_frame_rule_sha256": checksum("future-frame"),
            "power_or_sensitivity_rationale_committed": True,
            "power_or_sensitivity_rationale_sha256": checksum("power-rationale"),
        },
        "protection": {
            "classification": "protected_do_not_publish",
            "contains_numeric_target_values": False,
            "contains_predictions": False,
            "contains_randomized_aead_dataset_commitments": True,
            "contains_sign_or_sequence_values": False,
            "contains_unkeyed_dataset_digests": False,
            "publication_review_required": True,
            "public_release_authorized": False,
        },
        "record_kind": "nmfa_protected_value_blind_preregistration_manifest",
        "relations": [],
        "rights": rights,
        "sealed_datasets": {
            "target_y": sealed_dataset("target_y"),
            "transcription_x": sealed_dataset("transcription_x"),
        },
        "staged_release_contract": {
            "development_x_y_release_stage": "after_external_registration_and_split_receipt",
            "holdout_x_release_stage": (
                "after_exactly_one_model_freeze_and_successful_N1_support_feasibility_receipts"
            ),
            "holdout_y_release_stage": (
                "after_holdout_prediction_manifest_and_frozen_N1_sample_assignment_receipts"
            ),
            "per_record_aead_and_merkle_proof_verification_required": True,
            "release_policy_sha256": checksum("staged-release-policy"),
            "unlisted_release_forbidden": True,
        },
        "source_frame": {
            "complete": True,
            "completeness_rule_committed": True,
            "declared_physical_original_count": len(units),
            "declared_source_entry_count": len(source_records),
            "enumeration_and_order_rule_sha256": checksum("enumeration-order"),
            "exact_revisions_frozen": True,
            "finite": True,
            "mutation_status": "stable",
            "ordered_roster_committed": True,
            "pagination_or_enumeration_complete": True,
            "query_and_filter_frozen": True,
            "query_filter_rule_sha256": checksum("query-filter"),
            "revision_policy_sha256": checksum("revision-policy"),
            "universe_definition_sha256": checksum("universe-definition"),
        },
        "source_records": source_records,
        "target": {
            "canonical_unit_id": opaque("canonical-unit"),
            "contract_complete": True,
            "conversion_denominator": "1",
            "conversion_numerator": "1",
            "conversion_table_sha256": checksum("conversion-table"),
            "measurement_policy_sha256": checksum("measurement-policy"),
            "policies": {
                "approximate": "ineligible",
                "conflicting": "ineligible",
                "derived_from_inscription": "forbidden",
                "imputed": "forbidden",
                "range": "ineligible",
                "repeated": "single_frozen_resolution_rule",
                "rounding": "forbidden",
            },
            "target_family": "mass",
            "target_values_present": False,
        },
        "units": units,
    }
    return finalize(manifest)


def raw_manifest(manifest: dict[str, Any]) -> bytes:
    return encode_json(finalize(copy.deepcopy(manifest)))


def relation(
    left: str,
    right: str,
    *,
    disposition: str,
    status: str,
    kind: str,
    label: str,
) -> dict[str, Any]:
    left, right = sorted((left, right))
    return {
        "disposition": disposition,
        "evidence_envelope_sha256": checksum(label),
        "kind": kind,
        "left_f_id": left,
        "right_f_id": right,
        "status": status,
    }


def sort_relations(rows: list[dict[str, Any]]) -> None:
    rows.sort(
        key=lambda row: (
            row["left_f_id"],
            row["right_f_id"],
            row["kind"],
            row["status"],
            row["disposition"],
        )
    )


def eligibility_row(manifest: dict[str, Any], f_id: str) -> dict[str, Any]:
    return next(row for row in manifest["eligibility"] if row["f_id"] == f_id)


def context_table(manifest: dict[str, Any], axis: str) -> dict[str, Any]:
    return next(
        table for table in manifest["context_contract"]["closure_tables"] if table["axis"] == axis
    )


def context_group(manifest: dict[str, Any], axis: str, group_id: str) -> dict[str, Any]:
    table = context_table(manifest, axis)
    return next(group for group in table["groups"] if group["group_id"] == group_id)


def selector_inventory_digest(manifest: dict[str, Any]) -> str:
    (
        population_invalid,
        dependence_invalid,
        components,
        units_by_id,
        eligibility_flags,
        closures,
    ) = _population_semantics(manifest)
    if population_invalid or dependence_invalid:
        raise AssertionError("synthetic selector fixture is invalid")
    return _eligible_split_inventory_digest(
        components,
        units_by_id,
        eligibility_flags,
        closures,
        manifest["context_contract"],
    )


class NMFAPreregistrationTests(unittest.TestCase):
    maxDiff = None

    def evaluate(self, manifest: dict[str, Any]):
        return _evaluate_with_resources(raw_manifest(manifest), resources())

    def test_plan_schemas_and_source_free_boundaries(self) -> None:
        self.assertEqual(PLAN_PATH.read_bytes(), encode_json(read_json(PLAN_PATH)))
        for path in (PLAN_SCHEMA_PATH, MANIFEST_SCHEMA_PATH, REPORT_SCHEMA_PATH):
            with self.subTest(path=path.name):
                schema = read_json(path)
                Draft202012Validator.check_schema(schema)
        plan = read_json(PLAN_PATH)
        errors = list(Draft202012Validator(read_json(PLAN_SCHEMA_PATH)).iter_errors(plan))
        self.assertEqual([], errors)
        self.assertEqual("control-n1-v1", plan["n1"]["sampler"]["stream_label"])
        self.assertEqual(_RELATION_POLICY, plan["relation_policy"])
        self.assertEqual(
            domain_digest(_RELATION_POLICY_DOMAIN, plan["relation_policy"]),
            domain_digest(_RELATION_POLICY_DOMAIN, _RELATION_POLICY),
        )
        self.assertFalse(plan["n1"]["actual_candidate_classes_allowed_in_preregistration_manifest"])
        self.assertEqual(
            "model_frozen_pre_holdout_X_open",
            plan["n1"]["support_feasibility_stage"],
        )
        self.assertEqual(
            "post_holdout_prediction_manifest_pre_holdout_Y_open",
            plan["n1"]["sample_assignment_freeze_stage"],
        )
        self.assertTrue(plan["n1"]["support_feasibility_without_random_draw_required"])
        self.assertIn("raw_split_nonce_bytes", plan["n1"]["sampler"]["key_must_bind"])
        self.assertIn("holdout_prediction_manifest", plan["n1"]["sampler"]["key_must_bind"])
        preinventory = next(
            row for row in plan["digest_dag"] if row["node"] == "preinventory_contract_sha256"
        )
        self.assertTrue(
            any("source_records_exact_ordered" in row for row in preinventory["inputs"])
        )
        self.assertTrue(
            any("prevalue_f_context_inventory" in row for row in preinventory["inputs"])
        )
        self.assertTrue(
            any("prevalue_prior_project_exposure" in row for row in preinventory["inputs"])
        )
        self.assertIn(
            "exact_draft_parent", plan["claim_chain_policy"]["external_registration_requirement"]
        )
        self.assertTrue(all(value is False for value in plan["execution_boundary"].values()))

        split = plan["split_selection"]
        tuple_bytes = bytes.fromhex(split["test_vector_canonical_tuple_json_hex"])
        self.assertEqual(tuple_bytes, encode_json(json.loads(tuple_bytes)))
        ticket = hashlib.sha256(
            bytes.fromhex(split["test_vector_nonce_hex"])
            + b"\x00"
            + split["test_vector_inventory_sha256"].encode("ascii")
            + b"\x00"
            + tuple_bytes
        ).hexdigest()
        self.assertEqual(split["test_vector_ticket_sha256"], "sha256:" + ticket)

        primary = plan["split_feasibility"]["primary_f_selection"]
        primary_rank = hashlib.sha256(
            b"indusbench:nmfa:preregistration-primary-f:v1\x00"
            + primary["test_vector_gate_plan_sha256"].encode("ascii")
            + b"\x00"
            + primary["test_vector_candidate_f_id"].encode("ascii")
        ).hexdigest()
        self.assertEqual(primary["test_vector_primary_rank_sha256"], "sha256:" + primary_rank)

        sampler = plan["n1"]["sampler"]
        n1_block = hmac.new(
            bytes.fromhex(sampler["test_vector_key_hex"]),
            bytes.fromhex(sampler["test_vector_message_hex"]),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(sampler["test_vector_hmac_block_hex"], n1_block)

    def test_exact_160_is_candidate_for_external_review_but_authorizes_nothing(self) -> None:
        result = self.evaluate(ready_manifest())
        report = result.report()
        self.assertEqual("CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW", result.terminal_state)
        self.assertEqual([], report["reason_codes"])
        self.assertEqual(
            "SPLIT_FEASIBLE_N2_UNIVERSALLY_SUPPORTED",
            report["feasibility"]["structural_status"],
        )
        self.assertEqual("EXHAUSTED_SPLIT_ROSTER_N2_SAFE", report["feasibility"]["search_outcome"])
        self.assertEqual("UNVERIFIED", report["feasibility"]["external_assurance"])
        self.assertEqual("DEFERRED_NOT_EVALUATED", report["feasibility"]["actual_n1_support"])
        self.assertEqual(1, report["feasibility"]["split_eligible_tuple_count"])
        self.assertEqual(1, report["feasibility"]["n2_supported_tuple_count"])
        self.assertEqual(160, report["counts"]["eligible_g"])
        self.assertEqual(161, report["counts"]["source_frame_entries"])
        self.assertEqual(
            {
                "complement_g": 80,
                "holdout_g": 80,
                "medium_cell_g": 20,
                "n2_movable_g": 80,
                "object_type_cell_g": 20,
                "period_cell_g": 20,
                "site_cell_g": 20,
            },
            report["feasibility"]["first_split_eligible_aggregate_in_canonical_search"],
        )
        self.assertFalse(report["assurance"]["target_values_loaded_by_gate_or_evaluator"])
        self.assertTrue(report["assurance"]["source_records_seen_by_curator_roles_declared"])
        self.assertTrue(report["assurance"]["target_values_seen_by_target_curator_declared"])
        self.assertTrue(
            report["assurance"]["transcription_values_seen_by_transcription_curator_declared"]
        )
        self.assertFalse(hasattr(result, "public_summary"))

    def test_159_cell_19_and_complement_79_fail_closed(self) -> None:
        self.assertEqual(
            "INSUFFICIENT_ELIGIBLE_G", self.evaluate(ready_manifest(159)).terminal_state
        )

        cell_19 = ready_manifest()
        selected = opaque("selected-site")
        unit = next(unit for unit in cell_19["units"] if unit["context"]["site"] == selected)
        unit["context"]["site"] = opaque("site-40")
        self.assertEqual("NO_FEASIBLE_DOMAIN_TUPLE", self.evaluate(cell_19).terminal_state)

        complement_79 = ready_manifest()
        unit = next(
            unit
            for unit in complement_79["units"]
            if all(
                unit["context"][axis] != opaque(f"selected-{axis.replace('_type', '')}")
                for axis in AXES
            )
        )
        unit["context"]["site"] = selected
        self.assertEqual("NO_FEASIBLE_DOMAIN_TUPLE", self.evaluate(complement_79).terminal_state)

    def test_n2_uses_internal_named_full_context_tuple(self) -> None:
        manifest = ready_manifest()
        selected = {
            "site": opaque("selected-site"),
            "period": opaque("selected-period"),
            "medium": opaque("selected-medium"),
            "object_type": opaque("selected-object"),
        }
        holdout = [
            unit
            for unit in manifest["units"]
            if any(unit["context"][axis] == selected[axis] for axis in AXES)
        ]
        self.assertEqual(80, len(holdout))
        for index, unit in enumerate(holdout):
            unit["context"]["nuisance"] = [opaque(f"unique-nuisance-{index}")]
        manifest["context_contract"]["nuisance_vocabularies"][0]["canonical_value_ids"] = sorted(
            {unit["context"]["nuisance"][0] for unit in manifest["units"]}
        )
        manifest["context_contract"]["nuisance_value_vocabularies_sha256"] = domain_digest(
            _NUISANCE_VOCABULARY_DOMAIN,
            manifest["context_contract"]["nuisance_vocabularies"],
        )
        result = self.evaluate(manifest)
        self.assertEqual("N2_UNIVERSAL_SUPPORT_BLOCKED", result.terminal_state)
        self.assertEqual(
            ("SPLIT_ELIGIBLE_ROSTER_NOT_UNIVERSALLY_N2_SUPPORTED",), result.reason_codes
        )

    def test_child_closure_moves_g_out_of_complement(self) -> None:
        manifest = ready_manifest()
        selected = opaque("selected-site")
        unit = next(
            unit
            for unit in manifest["units"]
            if unit["context"]["site"] != selected
            and unit["context"]["period"] != opaque("selected-period")
            and unit["context"]["medium"] != opaque("selected-medium")
            and unit["context"]["object_type"] != opaque("selected-object")
        )
        child = opaque("selected-site-child")
        unit["context"]["site"] = child
        selected_group = context_group(manifest, "site", selected)
        selected_group["member_value_ids"] = sorted([selected, child])
        site_table = context_table(manifest, "site")
        site_table["groups"].append({"group_id": child, "member_value_ids": [child]})
        site_table["groups"].sort(key=lambda group: group["group_id"])
        self.assertEqual("NO_FEASIBLE_DOMAIN_TUPLE", self.evaluate(manifest).terminal_state)

    def test_duplicate_closure_is_rejected_but_canonical_parent_child_tickets_are_retained(
        self,
    ) -> None:
        duplicate_closure = ready_manifest()
        groups = context_table(duplicate_closure, "site")["groups"]
        first, second = groups[0], groups[1]
        members = sorted([first["group_id"], second["group_id"]])
        first["member_value_ids"] = members
        second["member_value_ids"] = members
        self.assertEqual(
            "DEPENDENCE_CONTEXT_INVALID", self.evaluate(duplicate_closure).terminal_state
        )

        sequential = ready_manifest()
        site_unit = next(
            unit
            for unit in sequential["units"]
            if unit["context"]["site"] == opaque("selected-site")
        )
        extra_period = site_unit["context"]["period"]
        group = context_group(sequential, "period", extra_period)
        group["member_value_ids"] = sorted([extra_period, opaque("selected-period")])
        result = self.evaluate(sequential)
        self.assertEqual("CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW", result.terminal_state)
        self.assertEqual(2, result.report()["feasibility"]["split_eligible_tuple_count"])

    def test_closures_must_be_transitive_laminar_and_cover_observed_canonical_values(
        self,
    ) -> None:
        nontransitive = ready_manifest()
        groups = context_table(nontransitive, "site")["groups"]
        a, b, c = groups[:3]
        a["member_value_ids"] = sorted([a["group_id"], b["group_id"]])
        b["member_value_ids"] = sorted([b["group_id"], c["group_id"]])
        self.assertEqual("DEPENDENCE_CONTEXT_INVALID", self.evaluate(nontransitive).terminal_state)

        nonlaminar = ready_manifest()
        groups = context_table(nonlaminar, "site")["groups"]
        a, b, c = groups[:3]
        a["member_value_ids"] = sorted([a["group_id"], c["group_id"]])
        b["member_value_ids"] = sorted([b["group_id"], c["group_id"]])
        self.assertEqual("DEPENDENCE_CONTEXT_INVALID", self.evaluate(nonlaminar).terminal_state)

        uncovered = ready_manifest()
        table = context_table(uncovered, "site")
        observed = uncovered["units"][0]["context"]["site"]
        table["groups"] = [group for group in table["groups"] if group["group_id"] != observed]
        self.assertEqual("DEPENDENCE_CONTEXT_INVALID", self.evaluate(uncovered).terminal_state)

    def test_exclude_both_propagates_to_final_union_components(self) -> None:
        manifest = ready_manifest(162)
        complement = [
            unit
            for unit in manifest["units"]
            if unit["context"]["site"] != opaque("selected-site")
            and unit["context"]["period"] != opaque("selected-period")
            and unit["context"]["medium"] != opaque("selected-medium")
            and unit["context"]["object_type"] != opaque("selected-object")
        ]
        a, b, c, d = [unit["f_id"] for unit in complement[:4]]
        manifest["relations"] = [
            relation(
                a,
                c,
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="a-c",
            ),
            relation(
                b,
                d,
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="b-d",
            ),
            relation(
                a,
                b,
                disposition="exclude_both",
                status="unresolved",
                kind="unresolved_dependence",
                label="a-b",
            ),
        ]
        sort_relations(manifest["relations"])
        for f_id in (a, b):
            row = eligibility_row(manifest, f_id)
            row["g_exclusion_reason"] = "DEPENDENCE_COMPONENT"
        self.assertEqual("DEPENDENCE_CONTEXT_INVALID", self.evaluate(manifest).terminal_state)

        for f_id in (c, d):
            row = eligibility_row(manifest, f_id)
            row["g_exclusion_reason"] = "DEPENDENCE_COMPONENT"
        self.assertEqual("INSUFFICIENT_ELIGIBLE_G", self.evaluate(manifest).terminal_state)

    def test_prior_exposure_contaminates_the_whole_g_with_closed_reason_precedence(self) -> None:
        manifest = ready_manifest()
        left, right = [unit["f_id"] for unit in manifest["units"][-2:]]
        manifest["relations"] = [
            relation(
                left,
                right,
                disposition="union",
                status="confirmed",
                kind="exact_normalized_sequence",
                label="exposure-union",
            )
        ]
        exposed = eligibility_row(manifest, left)
        exposed["g_exclusion_reason"] = "PRIOR_EXPOSURE_COMPONENT"
        exposed["prior_project_exposure"] = True
        self.assertEqual("DEPENDENCE_CONTEXT_INVALID", self.evaluate(manifest).terminal_state)

        connected = eligibility_row(manifest, right)
        connected["g_exclusion_reason"] = "PRIOR_EXPOSURE_COMPONENT"
        result = self.evaluate(manifest)
        self.assertEqual("INSUFFICIENT_ELIGIBLE_G", result.terminal_state)
        _, _, components, _, _, _ = _population_semantics(manifest)
        component = next(
            component for component in components if {left, right} <= set(component.member_ids)
        )
        self.assertEqual({left, right}, set(component.m_g_member_ids))
        self.assertEqual((), component.eligible_member_ids)

    def test_identity_or_content_conflict_contaminates_the_whole_g(self) -> None:
        manifest = ready_manifest(162)
        complement = [
            unit
            for unit in manifest["units"]
            if unit["context"]["site"] != opaque("selected-site")
            and unit["context"]["period"] != opaque("selected-period")
            and unit["context"]["medium"] != opaque("selected-medium")
            and unit["context"]["object_type"] != opaque("selected-object")
        ]
        left, right = [unit["f_id"] for unit in complement[:2]]
        manifest["relations"] = [
            relation(
                left,
                right,
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="identity-conflict-union",
            )
        ]
        row = eligibility_row(manifest, left)
        row["eligible"] = False
        row["g_exclusion_reason"] = "CONFLICT_COMPONENT"
        row["reason_codes"] = ["IDENTITY_UNRESOLVED"]
        self.assertEqual("DEPENDENCE_CONTEXT_INVALID", self.evaluate(manifest).terminal_state)

        connected = eligibility_row(manifest, right)
        connected["g_exclusion_reason"] = "CONFLICT_COMPONENT"
        self.assertEqual(
            "CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW",
            self.evaluate(manifest).terminal_state,
        )

    def test_g_exclusion_precedence_is_exposure_then_conflict_then_dependence(self) -> None:
        manifest = ready_manifest(162)
        left, right = [unit["f_id"] for unit in manifest["units"][-2:]]
        manifest["relations"] = [
            relation(
                left,
                right,
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="precedence-union",
            ),
            relation(
                left,
                right,
                disposition="exclude_both",
                status="unresolved",
                kind="unresolved_dependence",
                label="precedence-exclude",
            ),
        ]
        sort_relations(manifest["relations"])
        eligibility_row(manifest, left)["prior_project_exposure"] = True
        conflict = eligibility_row(manifest, right)
        conflict["eligible"] = False
        conflict["reason_codes"] = ["IDENTITY_UNRESOLVED"]
        for f_id in (left, right):
            eligibility_row(manifest, f_id)["g_exclusion_reason"] = "PRIOR_EXPOSURE_COMPONENT"
        _, dependence_invalid, components, _, _, _ = _population_semantics(manifest)
        self.assertFalse(dependence_invalid)
        component = next(
            component for component in components if {left, right} <= set(component.member_ids)
        )
        self.assertEqual((left,), component.m_g_member_ids)
        self.assertEqual((), component.eligible_member_ids)

        eligibility_row(manifest, right)["g_exclusion_reason"] = "CONFLICT_COMPONENT"
        self.assertTrue(_population_semantics(manifest)[1])

    def test_all_applicable_base_e_reasons_are_recorded_and_any_conflict_contaminates_g(
        self,
    ) -> None:
        manifest = ready_manifest(162)
        left, right = [unit["f_id"] for unit in manifest["units"][-2:]]
        manifest["relations"] = [
            relation(
                left,
                right,
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="multi-reason-union",
            )
        ]
        row = eligibility_row(manifest, left)
        row["eligible"] = False
        row["reason_codes"] = ["IDENTITY_UNRESOLVED", "TARGET_MISSING"]
        self.assertTrue(_population_semantics(manifest)[1])

        for f_id in (left, right):
            eligibility_row(manifest, f_id)["g_exclusion_reason"] = "CONFLICT_COMPONENT"
        population_invalid, dependence_invalid, components, _, _, _ = _population_semantics(
            manifest
        )
        self.assertFalse(population_invalid)
        self.assertFalse(dependence_invalid)
        component = next(
            component for component in components if {left, right} <= set(component.member_ids)
        )
        self.assertEqual((right,), component.m_g_member_ids)
        self.assertEqual((), component.eligible_member_ids)

        unsorted = copy.deepcopy(manifest)
        eligibility_row(unsorted, left)["reason_codes"] = [
            "TARGET_MISSING",
            "IDENTITY_UNRESOLVED",
        ]
        self.assertTrue(_population_semantics(unsorted)[0])

    def test_source_records_are_total_many_to_one_and_cannot_duplicate_or_float_f(self) -> None:
        ready = self.evaluate(ready_manifest())
        self.assertEqual("CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW", ready.terminal_state)

        duplicate = ready_manifest()
        copied = copy.deepcopy(duplicate["source_records"][0])
        copied["source_entry_id"] = opaque("new-entry-same-record-view")
        copied["source_order"] = len(duplicate["source_records"])
        duplicate["source_records"].append(copied)
        duplicate["source_frame"]["declared_source_entry_count"] += 1
        self.assertEqual("POPULATION_MANIFEST_INVALID", self.evaluate(duplicate).terminal_state)

        floating = ready_manifest()
        floating["source_records"][0]["f_id"] = opaque("unknown-f")
        self.assertEqual("POPULATION_MANIFEST_INVALID", self.evaluate(floating).terminal_state)

        split_record = ready_manifest()
        split_record["source_records"][1]["source_record_id"] = split_record["source_records"][0][
            "source_record_id"
        ]
        self.assertNotEqual(
            split_record["source_records"][1]["f_id"],
            split_record["source_records"][0]["f_id"],
        )
        self.assertEqual("POPULATION_MANIFEST_INVALID", self.evaluate(split_record).terminal_state)

    def test_sealed_x_y_archives_bind_exact_distinct_complete_f_rosters(self) -> None:
        count = ready_manifest()
        count["sealed_datasets"]["transcription_x"]["commitment"]["committed_f_count"] -= 1
        self.assertEqual("POPULATION_MANIFEST_INVALID", self.evaluate(count).terminal_state)

        roster = ready_manifest()
        roster["sealed_datasets"]["target_y"]["commitment"]["ordered_f_roster_sha256"] = checksum(
            "wrong-roster"
        )
        self.assertEqual("POPULATION_MANIFEST_INVALID", self.evaluate(roster).terminal_state)

        shared_root = ready_manifest()
        shared_root["sealed_datasets"]["target_y"]["commitment"][
            "ciphertext_merkle_root_sha256"
        ] = shared_root["sealed_datasets"]["transcription_x"]["commitment"][
            "ciphertext_merkle_root_sha256"
        ]
        self.assertEqual("POPULATION_MANIFEST_INVALID", self.evaluate(shared_root).terminal_state)

        shared_payload = ready_manifest()
        shared_payload["sealed_datasets"]["target_y"]["contract"][
            "canonical_payload_contract_sha256"
        ] = shared_payload["sealed_datasets"]["transcription_x"]["contract"][
            "canonical_payload_contract_sha256"
        ]
        self.assertEqual(
            "POPULATION_MANIFEST_INVALID", self.evaluate(shared_payload).terminal_state
        )

    def test_prevalue_receipt_binds_exact_source_f_context_and_prior_exposure(self) -> None:
        original = ready_manifest()
        original_digest = original["bindings"]["preinventory_contract_sha256"]

        mutations: list[dict[str, Any]] = []
        source = copy.deepcopy(original)
        source["source_records"][0]["source_view_id"] = opaque("post-value-source-view")
        mutations.append(source)

        context = copy.deepcopy(original)
        context["units"][0]["context"]["site"] = opaque("post-value-site")
        mutations.append(context)

        identity = copy.deepcopy(original)
        identity["units"][0]["physical_identity_evidence_envelope_sha256"] = checksum(
            "post-value-identity"
        )
        mutations.append(identity)

        exposure = copy.deepcopy(original)
        exposure["eligibility"][0]["prior_project_exposure"] = True
        mutations.append(exposure)

        for mutation in mutations:
            with self.subTest(field=mutation["manifest_sha256"]):
                changed = domain_digest(
                    _PREINVENTORY_CONTRACT_DOMAIN,
                    _preinventory_payload(mutation),
                )
                self.assertNotEqual(original_digest, changed)

        forged = finalize(copy.deepcopy(source))
        forged["bindings"]["preinventory_contract_sha256"] = original_digest
        for name in (
            "preinventory_contract_receipt",
            "earliest_transcription_x_access_receipt",
            "earliest_target_y_access_receipt",
        ):
            forged["freeze_sequence"][name]["subject_sha256"] = original_digest
        forged["bindings"]["population_freeze_claim_sha256"] = domain_digest(
            _POPULATION_FREEZE_CLAIM_DOMAIN,
            _population_freeze_claim_payload(forged, forged["bindings"]),
        )
        forged["freeze_sequence"]["population_inventory_receipt"]["subject_sha256"] = forged[
            "bindings"
        ]["population_freeze_claim_sha256"]
        forged["bindings"]["freeze_sequence_sha256"] = domain_digest(
            _FREEZE_SEQUENCE_DOMAIN, forged["freeze_sequence"]
        )
        payload = dict(forged)
        payload.pop("manifest_sha256")
        forged["manifest_sha256"] = domain_digest(_MANIFEST_DOMAIN, payload)
        with self.assertRaises(NMFAPreregistrationError) as raised:
            _validate_manifest_with_resources(encode_json(forged), resources())
        self.assertEqual(
            NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID,
            raised.exception.code,
        )

    def test_single_regime_zero_nuisance_and_wholly_ineligible_incomplete_context(self) -> None:
        single = ready_manifest()
        contract = single["context_contract"]
        contract["nuisance_field_ids"] = []
        contract["nuisance_vocabularies"] = []
        contract["nuisance_value_vocabularies_sha256"] = domain_digest(
            _NUISANCE_VOCABULARY_DOMAIN, []
        )
        contract["provenance_policy"] = "single_prespecified_regime"
        contract["single_regime_contract_sha256"] = checksum("single-regime")
        for unit in single["units"]:
            unit["context"]["nuisance"] = []
        self.assertEqual(
            "CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW",
            self.evaluate(single).terminal_state,
        )

        incomplete = ready_manifest(161)
        unit = incomplete["units"][-1]
        for axis in AXES:
            unit["context"][axis] = None
        unit["context"]["nuisance"] = []
        row = eligibility_row(incomplete, unit["f_id"])
        row["eligible"] = False
        row["g_exclusion_reason"] = "CONFLICT_COMPONENT"
        row["reason_codes"] = ["CONTEXT_INCOMPLETE_OR_CONFLICTING"]
        self.assertEqual(
            "CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW",
            self.evaluate(incomplete).terminal_state,
        )

    def test_primary_selection_is_not_changed_by_e_attestation_or_population_digest(self) -> None:
        manifest = ready_manifest()
        ids = [
            unit["f_id"]
            for unit in manifest["units"]
            if unit["context"]["site"] == opaque("selected-site")
        ][:2]
        manifest["relations"] = [
            relation(
                ids[0],
                ids[1],
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="primary-union",
            )
        ]
        sort_relations(manifest["relations"])
        _, _, components, units_by_id, _, closures = _population_semantics(manifest)
        component = next(
            component for component in components if set(ids) <= set(component.member_ids)
        )
        gate_digest = "sha256:" + hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        first = _primary_f(
            component,
            "site",
            closures["site"][opaque("selected-site")],
            gate_digest,
            units_by_id,
        )
        for row in manifest["eligibility"]:
            row["attestation_id"] = opaque("changed-" + row["f_id"])
        _, _, components, units_by_id, _, closures = _population_semantics(manifest)
        component = next(
            component for component in components if set(ids) <= set(component.member_ids)
        )
        second = _primary_f(
            component,
            "site",
            closures["site"][opaque("selected-site")],
            gate_digest,
            units_by_id,
        )
        self.assertEqual(first, second)

    def test_selector_inventory_excludes_random_salt_but_binds_exact_e_f_g_and_c(self) -> None:
        manifest = ready_manifest(162)
        left, right = [unit["f_id"] for unit in manifest["units"][-2:]]
        manifest["relations"] = [
            relation(
                left,
                right,
                disposition="union",
                status="confirmed",
                kind="production_batch",
                label="base-union",
            )
        ]
        row = eligibility_row(manifest, left)
        row["eligible"] = False
        row["reason_codes"] = ["TARGET_MISSING"]
        baseline = selector_inventory_digest(manifest)
        _, _, components, _, _, _ = _population_semantics(manifest)
        mixed = next(
            component for component in components if {left, right} <= set(component.member_ids)
        )
        self.assertEqual((right,), mixed.m_g_member_ids)
        self.assertEqual((right,), mixed.eligible_member_ids)
        self.assertEqual(
            {manifest["units"][-2]["context"]["site"], manifest["units"][-1]["context"]["site"]},
            set(mixed.contexts["site"]),
        )

        random_envelopes = copy.deepcopy(manifest)
        random_envelopes["units"][0]["context_evidence_envelope_sha256"] = checksum(
            "rerandomized-context-envelope"
        )
        random_envelopes["eligibility"][0]["attestation_id"] = opaque(
            "rerandomized-eligibility-attestation"
        )
        random_envelopes["relations"][0]["evidence_envelope_sha256"] = checksum(
            "rerandomized-relation-envelope"
        )
        random_envelopes["sealed_datasets"]["target_y"]["commitment"][
            "ciphertext_merkle_root_sha256"
        ] = checksum("rerandomized-target-merkle")
        self.assertEqual(baseline, selector_inventory_digest(random_envelopes))

        redundant_edge = copy.deepcopy(manifest)
        redundant_edge["relations"].append(
            relation(
                left,
                right,
                disposition="union",
                status="confirmed",
                kind="workshop",
                label="redundant-union",
            )
        )
        sort_relations(redundant_edge["relations"])
        self.assertEqual(baseline, selector_inventory_digest(redundant_edge))
        self.assertNotEqual(
            domain_digest(
                _SPLIT_STRUCTURAL_INPUT_DOMAIN, _split_structural_input_payload(manifest)
            ),
            domain_digest(
                _SPLIT_STRUCTURAL_INPUT_DOMAIN,
                _split_structural_input_payload(redundant_edge),
            ),
        )

        reason_only = copy.deepcopy(manifest)
        eligibility_row(reason_only, left)["reason_codes"] = ["RIGHTS_INSUFFICIENT"]
        self.assertEqual(baseline, selector_inventory_digest(reason_only))

        changed_e = copy.deepcopy(manifest)
        changed_row = eligibility_row(changed_e, left)
        changed_row["eligible"] = True
        changed_row["reason_codes"] = ["ELIGIBLE"]
        self.assertNotEqual(baseline, selector_inventory_digest(changed_e))

        changed_g = copy.deepcopy(manifest)
        changed_g["relations"] = []
        self.assertNotEqual(baseline, selector_inventory_digest(changed_g))

        changed_c = copy.deepcopy(manifest)
        changed_c["units"][0]["context"]["site"] = changed_c["units"][1]["context"]["site"]
        self.assertNotEqual(baseline, selector_inventory_digest(changed_c))

        changed_closure = copy.deepcopy(manifest)
        site_groups = context_table(changed_closure, "site")["groups"]
        first, second = site_groups[0], site_groups[1]
        first["member_value_ids"] = sorted([first["group_id"], second["group_id"]])
        self.assertNotEqual(baseline, selector_inventory_digest(changed_closure))

    def test_tuple_n2_assignment_and_cache_limits_have_exact_admission_boundaries(self) -> None:
        manifest = ready_manifest()
        _, _, snapshot = _validate_manifest_with_resources(raw_manifest(manifest), resources())
        (
            population_invalid,
            dependence_invalid,
            components,
            units_by_id,
            _,
            closures,
        ) = _population_semantics(manifest)
        self.assertFalse(population_invalid)
        self.assertFalse(dependence_invalid)

        def search(**limits: int):
            return _tuple_search(
                components,
                units_by_id,
                closures,
                snapshot.gate_plan_sha256,
                replace(snapshot, **limits),
            )

        exact_tuple = search(max_tuple_evaluations=1)
        self.assertEqual("EXHAUSTED_SPLIT_ROSTER_N2_SAFE", exact_tuple.outcome)
        over_tuple = search(max_tuple_evaluations=0)
        self.assertEqual("LIMIT_REACHED", over_tuple.outcome)
        self.assertEqual(0, over_tuple.tuple_evaluations)

        exact_n2 = search(max_n2_tuple_evaluations=1)
        self.assertEqual("EXHAUSTED_SPLIT_ROSTER_N2_SAFE", exact_n2.outcome)
        over_n2 = search(max_n2_tuple_evaluations=0)
        self.assertEqual("LIMIT_REACHED", over_n2.outcome)
        self.assertEqual(0, over_n2.n2_tuple_evaluations)

        exact_assignments = search(max_n2_primary_assignments=80)
        self.assertEqual("EXHAUSTED_SPLIT_ROSTER_N2_SAFE", exact_assignments.outcome)
        over_assignments = search(max_n2_primary_assignments=79)
        self.assertEqual("LIMIT_REACHED", over_assignments.outcome)
        self.assertEqual(0, over_assignments.n2_tuple_evaluations)
        self.assertEqual(0, over_assignments.n2_primary_assignments)

        exact_cache = search(max_primary_cache_entries=80)
        self.assertEqual("EXHAUSTED_SPLIT_ROSTER_N2_SAFE", exact_cache.outcome)
        over_cache = search(max_primary_cache_entries=79)
        self.assertEqual("LIMIT_REACHED", over_cache.outcome)
        self.assertEqual(1, over_cache.n2_tuple_evaluations)
        self.assertEqual(80, over_cache.n2_primary_assignments)

    def test_freeze_chronology_sampler_and_binding_tampering_fail_contract(self) -> None:
        cases = []
        chronology = ready_manifest()
        chronology["freeze_sequence"]["earliest_target_y_access_receipt"]["recorded_at"] = (
            "2026-08-02T05:59:59Z"
        )
        cases.append(chronology)
        sampler = ready_manifest()
        sampler["n1_deferred_contract"]["sampler_contract_sha256"] = checksum("wrong")
        cases.append(sampler)
        invalid_calendar = ready_manifest()
        invalid_calendar["freeze_sequence"]["population_inventory_receipt"]["recorded_at"] = (
            "2026-99-99T99:99:99Z"
        )
        with self.assertRaises(NMFAPreregistrationError) as raised:
            _validate_manifest_with_resources(raw_manifest(invalid_calendar), resources())
        self.assertEqual(
            NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID,
            raised.exception.code,
        )
        stale = ready_manifest()
        finalized = finalize(copy.deepcopy(stale))
        finalized["units"][0]["context_evidence_envelope_sha256"] = checksum("tampered")
        with self.assertRaises(NMFAPreregistrationError) as raised:
            _validate_manifest_with_resources(encode_json(finalized), resources())
        self.assertEqual(
            NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID, raised.exception.code
        )
        for manifest in cases:
            with self.subTest(case=manifest["manifest_sha256"]):
                raw = encode_json(finalize(copy.deepcopy(manifest)))
                # Reapply the semantic defect after helper refreshes receipt subjects.
                value = json.loads(raw)
                if manifest is chronology:
                    value["freeze_sequence"]["earliest_target_y_access_receipt"]["recorded_at"] = (
                        "2026-08-02T05:59:59Z"
                    )
                else:
                    value["n1_deferred_contract"]["sampler_contract_sha256"] = checksum("wrong")
                payload = dict(value)
                payload.pop("manifest_sha256")
                value["manifest_sha256"] = (
                    "sha256:" + hashlib.sha256(_MANIFEST_DOMAIN + encode_json(payload)).hexdigest()
                )
                with self.assertRaises(NMFAPreregistrationError) as raised:
                    _validate_manifest_with_resources(encode_json(value), resources())
                self.assertEqual(
                    NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID,
                    raised.exception.code,
                )

    def test_every_freeze_boundary_is_strict_typed_and_manifest_assembly_is_later(self) -> None:
        cases: list[dict[str, Any]] = []

        equal_key = ready_manifest()
        equal_key["freeze_sequence"]["identifier_key_generation_receipt"]["recorded_at"] = (
            equal_key["freeze_sequence"]["claim_slot_reservation_receipt"]["recorded_at"]
        )
        cases.append(equal_key)

        equal_source = ready_manifest()
        equal_source["freeze_sequence"][
            "clean_roles_first_claim_instance_source_metadata_access_receipt"
        ]["recorded_at"] = equal_source["freeze_sequence"]["identifier_key_generation_receipt"][
            "recorded_at"
        ]
        cases.append(equal_source)

        equal_x_access = ready_manifest()
        equal_x_access["freeze_sequence"]["earliest_transcription_x_access_receipt"][
            "recorded_at"
        ] = equal_x_access["freeze_sequence"]["preinventory_contract_receipt"]["recorded_at"]
        cases.append(equal_x_access)

        equal_x_seal = ready_manifest()
        equal_x_seal["freeze_sequence"]["transcription_seal_receipt"]["recorded_at"] = equal_x_seal[
            "freeze_sequence"
        ]["earliest_transcription_x_access_receipt"]["recorded_at"]
        cases.append(equal_x_seal)

        equal_population = ready_manifest()
        equal_population["freeze_sequence"]["population_inventory_receipt"]["recorded_at"] = (
            equal_population["freeze_sequence"]["target_seal_receipt"]["recorded_at"]
        )
        cases.append(equal_population)

        equal_created = ready_manifest()
        equal_created["created_at"] = equal_created["freeze_sequence"][
            "population_inventory_receipt"
        ]["recorded_at"]
        cases.append(equal_created)

        wrong_kind = ready_manifest()
        wrong_kind["freeze_sequence"]["target_seal_receipt"]["receipt_kind"] = "transcription_seal"
        cases.append(wrong_kind)

        for index, manifest in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(NMFAPreregistrationError) as raised:
                    _validate_manifest_with_resources(raw_manifest(manifest), resources())
                self.assertEqual(
                    NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID,
                    raised.exception.code,
                )

        bundle_equal = ready_manifest()
        bundle = read_json(BUNDLE_PATH)
        bundle["created_at"] = bundle_equal["freeze_sequence"]["claim_slot_reservation_receipt"][
            "recorded_at"
        ]
        forged_bundle = encode_json(bundle)
        bundle_equal["bindings"]["evaluator_bundle_sha256"] = (
            "sha256:" + hashlib.sha256(forged_bundle).hexdigest()
        )
        forged_resources = copy.copy(resources())
        object.__setattr__(forged_resources, "evaluator_bundle", forged_bundle)
        with self.assertRaises(NMFAPreregistrationError) as raised:
            _validate_manifest_with_resources(raw_manifest(bundle_equal), forged_resources)
        self.assertEqual(
            NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID,
            raised.exception.code,
        )

    def test_schema_substitution_is_rejected_before_manifest_validation(self) -> None:
        altered = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        altered["$defs"]["unit"]["properties"]["target_value"] = {"type": "integer"}
        forged_resources = copy.copy(resources())
        object.__setattr__(forged_resources, "manifest_schema", encode_json(altered))
        with self.assertRaises(NMFAPreregistrationError) as raised:
            _validate_manifest_with_resources(raw_manifest(ready_manifest()), forged_resources)
        self.assertEqual(
            NMFAPreregistrationErrorCode.PACKAGE_RESOURCE_INVALID, raised.exception.code
        )

    def test_forbidden_value_surface_float_bom_duplicate_and_noncanonical_are_rejected(
        self,
    ) -> None:
        manifest = ready_manifest()
        manifest["units"][0]["target_value"] = 17
        with self.assertRaises(NMFAPreregistrationError):
            self.evaluate(manifest)

        valid_raw = raw_manifest(ready_manifest())
        attacks = (
            b"\xef\xbb\xbf" + valid_raw,
            valid_raw.replace(b'"conversion_numerator": "1"', b'"conversion_numerator": 1.5'),
            valid_raw.replace(
                b'"format_version": "1.0.0"',
                b'"format_version": "1.0.0",\n  "format_version": "1.0.0"',
            ),
            json.dumps(json.loads(valid_raw), separators=(",", ":")).encode("utf-8"),
        )
        for attack in attacks:
            with self.subTest(prefix=attack[:24]):
                with self.assertRaises(NMFAPreregistrationError) as raised:
                    _validate_manifest_with_resources(attack, resources())
                self.assertEqual(
                    NMFAPreregistrationErrorCode.MANIFEST_CONTRACT_INVALID,
                    raised.exception.code,
                )

    def test_report_receipt_schema_thresholds_and_private_boundary(self) -> None:
        result = self.evaluate(ready_manifest())
        report = result.report()
        receipt = report.pop("receipt_sha256")
        expected = "sha256:" + hashlib.sha256(_RECEIPT_DOMAIN + encode_json(report)).hexdigest()
        self.assertEqual(expected, receipt)

        forged = result.report()
        forged["counts"]["eligible_g"] = 0
        aggregate = forged["feasibility"]["first_split_eligible_aggregate_in_canonical_search"]
        for key in aggregate:
            aggregate[key] = 0
        errors = list(Draft202012Validator(read_json(REPORT_SCHEMA_PATH)).iter_errors(forged))
        self.assertTrue(errors)

        manifest = ready_manifest()
        sentinels = {
            manifest["units"][0]["f_id"],
            manifest["source_records"][0]["source_record_id"],
            manifest["units"][0]["context"]["site"],
            "/private/source/path",
            "17.25",
        }
        output = result.report_bytes.decode("utf-8")
        for sentinel in sentinels:
            self.assertNotIn(sentinel, output)
        self.assertFalse(result.report()["privacy"]["public_release_authorized"])

    def test_report_schema_is_structural_and_semantic_authenticity_requires_exact_reexecution(
        self,
    ) -> None:
        manifest = ready_manifest()
        site_unit = next(
            unit for unit in manifest["units"] if unit["context"]["site"] == opaque("selected-site")
        )
        extra_period = site_unit["context"]["period"]
        context_group(manifest, "period", extra_period)["member_value_ids"] = sorted(
            [extra_period, opaque("selected-period")]
        )
        result = self.evaluate(manifest)
        forged = result.report()
        self.assertEqual(2, forged["feasibility"]["split_eligible_tuple_count"])
        forged["feasibility"]["n2_supported_tuple_count"] = 1
        forged.pop("receipt_sha256")
        forged["receipt_sha256"] = domain_digest(_RECEIPT_DOMAIN, forged)
        schema = read_json(REPORT_SCHEMA_PATH)
        self.assertIn("exact deterministic evaluator re-execution", schema["$comment"])
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(forged)))
        self.assertNotEqual(encode_json(forged), result.report_bytes)

    def test_declaration_precedence_does_not_claim_external_verification(self) -> None:
        manifest = ready_manifest()
        manifest["exposure"]["numeric_y_seen_by_evaluator_role"] = True
        manifest["governance"]["source_access_authority"] = "not_authorized"
        manifest["rights"][0]["purposes"]["retrieve"] = "unknown"
        manifest["governance"]["protected_custody_capability"] = "not_verified"
        self.assertEqual("SOURCE_VALUE_BLINDNESS_BREACH", self.evaluate(manifest).terminal_state)
        manifest["exposure"]["numeric_y_seen_by_evaluator_role"] = False
        self.assertEqual("AUTHORITY_BLOCKED", self.evaluate(manifest).terminal_state)
        manifest["governance"]["source_access_authority"] = "authorized"
        self.assertEqual("RIGHTS_BLOCKED", self.evaluate(manifest).terminal_state)
        manifest["rights"][0]["purposes"]["retrieve"] = "permitted"
        self.assertEqual("CUSTODY_BLOCKED", self.evaluate(manifest).terminal_state)

    def test_early_terminal_reports_do_not_compute_structural_counts_and_repr_is_safe(self) -> None:
        manifest = ready_manifest()
        manifest["governance"]["source_access_authority"] = "not_authorized"
        raw = raw_manifest(manifest)
        validated, _, _ = _validate_manifest_with_resources(raw, resources())
        result = _evaluate_with_resources(raw, resources())
        report = result.report()
        self.assertEqual("AUTHORITY_BLOCKED", result.terminal_state)
        self.assertFalse(report["counts"]["structural_counts_evaluated"])
        for key in (
            "base_e_eligible_f",
            "eligible_g",
            "split_eligible_f",
            "split_excluded_f",
            "total_g",
        ):
            self.assertIsNone(report["counts"][key])
        self.assertIsNone(report["feasibility"]["eligible_split_inventory_sha256"])
        protected_values = (
            manifest["units"][0]["f_id"],
            manifest["manifest_sha256"],
            str(len(manifest["units"])),
        )
        for rendered in (repr(validated), repr(result)):
            for protected in protected_values:
                self.assertNotIn(protected, rendered)

    def test_each_clean_role_value_exposure_fails_before_governance_checks(self) -> None:
        forbidden = (
            "development_subset_values_released",
            "holdout_mapping_opened",
            "holdout_x_seen_by_evaluator_or_model_before_model_freeze",
            "holdout_y_seen_before_prediction_manifest_freeze",
            "numeric_y_seen_by_context_curator_role",
            "numeric_y_seen_by_evaluator_role",
            "numeric_y_seen_by_identifier_custodian_role",
            "numeric_y_seen_by_physical_identity_curator_role",
            "numeric_y_seen_by_relation_curator_role",
            "numeric_y_seen_by_source_frame_curator_role",
            "numeric_y_seen_by_split_role",
            "numeric_y_seen_by_transcription_role",
            "numeric_y_seen_by_transcription_seal_custodian_role",
            "score_or_prediction_material_present",
            "score_or_predictions_seen_by_target_curator_role",
            "sealed_record_keys_released_before_external_registration",
            "transcription_x_seen_by_evaluator_or_model_before_split_receipt",
            "transcription_x_seen_by_identifier_custodian_role",
            "transcription_x_seen_by_relation_curator_role",
            "transcription_x_seen_by_target_curator_role",
            "transcription_x_seen_by_target_seal_custodian_role",
            "unkeyed_target_value_digest_present",
        )
        for key in forbidden:
            with self.subTest(key=key):
                manifest = ready_manifest()
                manifest["exposure"][key] = True
                manifest["governance"]["source_access_authority"] = "not_authorized"
                self.assertEqual(
                    "SOURCE_VALUE_BLINDNESS_BREACH", self.evaluate(manifest).terminal_state
                )

    def test_source_has_no_network_subprocess_random_or_write_surface(self) -> None:
        source = (ROOT / "src/indusbench/nmfa_preregistration.py").read_text(encoding="utf-8")
        for forbidden in (
            "import socket",
            "import subprocess",
            "import random",
            "import requests",
            "import urllib",
            ".write_bytes(",
            ".write_text(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
