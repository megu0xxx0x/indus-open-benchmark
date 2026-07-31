from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from indusbench.io import encode_json

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "registry" / "source-reported-link-policy-v1.json"
SCHEMA_PATH = ROOT / "schemas" / "source-reported-link-policy.schema.json"
PARENT_REGISTRY_PATH = ROOT / "registry" / "chanhu-daro-helsinki-gate-v1.json"
PARENT_SCHEMA_PATH = ROOT / "schemas" / "context-source-link-gate.schema.json"
SOURCE_REGISTRY_PATH = ROOT / "registry" / "sources.json"

PARENT_REGISTRY_SHA256 = "43c0fae1a8558fbffeb062725e401e0c3c1de570e5f8f7eef610ca2616cbfb3d"
PARENT_SCHEMA_SHA256 = "72109818eb55aca008b0f34b1d6c627efd0e38bdbaff8c500cb3c60dc74e3002"
LINK_IDS = tuple(f"chanhu-daro-preselection-v1:{index:03d}" for index in range(6))
SLOT_CONTEXT = (
    (None, "lead_no_listed_material_conflict", None),
    (None, "excavation_location_axis_conflict", "excavation_location"),
    (None, "lead_no_listed_material_conflict", None),
    (None, "lead_no_listed_material_conflict", None),
    (
        "chanhu-daro-penn-329820-collision",
        "shared_penn_target_identity_collision",
        None,
    ),
    (
        "chanhu-daro-penn-329820-collision",
        "shared_penn_target_identity_collision",
        None,
    ),
)


def expected_policy() -> dict[str, Any]:
    slots = [
        {
            "collision_group": context[0],
            "index": index,
            "link_id": LINK_IDS[index],
            "role": context[1],
            "unresolved_axis": context[2],
        }
        for index, context in enumerate(SLOT_CONTEXT)
    ]
    return {
        "decision_policy": {
            "contract_blocked_requires_empty_observations": True,
            "contract_blocked_triggers": [
                "external_source_registration_commitment_absent",
                "external_source_revision_commitment_absent",
                "external_rights_handling_commitment_absent",
                "external_inspection_commitment_absent",
                "external_ordered_source_roster_commitment_absent",
                "observations_empty",
            ],
            "hard_reject_inputs": [
                "malformed_input",
                "noncanonical_input",
                "observations_present_before_prerequisites",
                "parent_commitment_mismatch",
                "verification_commitment_mismatch",
                "forbidden_channel_present",
            ],
            "hard_reject_is_result_state": False,
            "hard_reject_precedes_state_evaluation": True,
            "no_link": {
                "allowed_alternatives": [
                    "dual_explicit_source_rejection",
                    "dual_row_absent_with_exact_completeness_attestation_digest",
                ],
                "complete_roster_applies_to": (
                    "dual_row_absent_with_exact_completeness_attestation_digest"
                ),
                "complete_roster_requirements": {
                    "applies_to_both_passes": True,
                    "coverage_cardinality": "ordered_complete_source_roster_one_to_one",
                    "ordered_source_roster_count_exact": True,
                    "ordered_source_roster_sha256_exact": True,
                    "processed_count_equals_ordered_source_roster_count": True,
                    "source_revision_sha256_exact": True,
                    "zero_count_fields": [
                        "missing_count",
                        "extra_count",
                        "duplicate_count",
                        "unreadable_count",
                        "error_count",
                        "ambiguous_count",
                    ],
                },
                "explicit_source_rejection_requirements": [
                    "both_passes_same_exact_target",
                    "both_passes_same_source_revision",
                    "both_passes_explicit_source_rejection",
                ],
                "not_found_without_complete_roster_state": "unresolved",
                "scope": "per_parent_row_only",
            },
            "source_reported_link_requirements": [
                "separately_sealed_coded_machine_passes",
                "external_prerequisites_exact",
                "both_passes_same_source_revision",
                "dual_exact_one_candidate",
                "same_target_parent_link_id",
                "same_source_local_locator",
                "bounded_ascii_source_local_locator",
                "forbidden_channels_not_used",
            ],
            "state_precedence": [
                "contract_blocked",
                "unresolved",
                "source_reported_link",
                "no_link",
            ],
            "terminal_states_mutually_exclusive": True,
            "unresolved_triggers": [
                "unreadable",
                "inspection_error",
                "ambiguous",
                "multiple_candidates",
                "pass_disagreement",
                "source_revision_disagreement",
                "ordered_source_roster_commitment_disagreement",
                "incomplete_ordered_source_roster_coverage",
            ],
        },
        "execution_boundary": {
            "authorization_status": "not_authorized",
            "canonical_byte_identity_required": True,
            "current_prerequisite_state": "contract_blocked",
            "execution_status": "not_executed",
            "future_unblock_requires": "separate_source_registration_and_rights_contract",
            "operational_verification_scope": (
                "external_comparison_only_no_truth_authentication_or_anti_fabrication"
            ),
            "runtime_evaluator_implemented": False,
            "schema_validation_scope": "semantic_exact_const_with_json_number_equivalence",
        },
        "forbidden_channels": [
            "confidence",
            "excerpt",
            "free_text",
            "glyph",
            "image",
            "linguistic",
            "media",
            "notes",
            "ocr",
            "page",
            "raw",
            "sequence",
            "sign",
            "similarity",
            "source_bytes",
            "token",
            "transcription",
            "visual",
        ],
        "nonclaims": {
            "caller_fabrication_prevented": False,
            "context_correctness_verified": False,
            "decipherment_evidence": False,
            "evaluation_admitted": False,
            "field_number_truth_verified": False,
            "future_join_rights_verified": False,
            "helsinki_source_used": False,
            "join_admitted": False,
            "object_authenticity_verified": False,
            "physical_identity_resolved": False,
            "selection_representativeness_verified": False,
            "source_independence_verified": False,
            "transcription_approved": False,
            "truth_authenticated": False,
        },
        "ordering": {
            "all_six_rows_required": True,
            "attempt_order": list(LINK_IDS),
            "ordering_semantics": "source_table_order_only_not_rank",
            "post_hoc_row_substitution_permitted": False,
            "result_aggregation_permitted": False,
            "result_vector_length": 6,
        },
        "parent": {
            "ordered_link_ids": list(LINK_IDS),
            "registry": {
                "id": "chanhu-daro-helsinki-gate-v1",
                "sha256": PARENT_REGISTRY_SHA256,
                "size": 6955,
            },
            "schema": {
                "id": "context-source-link-gate.schema.json",
                "sha256": PARENT_SCHEMA_SHA256,
                "size": 9216,
            },
        },
        "passes": {
            "authorship": "machine",
            "count": 2,
            "mode": "separately_sealed_coded_machine_passes",
            "nonclaims": {
                "blinding_verified": False,
                "human_independence_verified": False,
                "model_independence_verified": False,
                "nonexposure_verified": False,
                "organizational_independence_verified": False,
            },
            "required_distinct_fields": ["pass_id", "seal_sha256"],
            "separation_scope": "distinct_identifiers_and_seals_only",
        },
        "policy_id": "source-reported-link-policy-v1",
        "result_slots": slots,
        "schema_version": "0.1.0",
        "source_scope": [
            {
                "license_id": None,
                "redistribution_permitted": False,
                "registration_status": "registered",
                "rights_status": "unknown",
                "scope": "link_only",
                "source_id": "mackay-chanhu-daro-1943",
                "source_layer": "mackay_report_locator",
            },
            {
                "bulk_metadata_license_inherited": False,
                "bulk_metadata_source_id": "penn-museum-collections-data",
                "license_id": None,
                "noninherited_bulk_license_id": "CC-BY-4.0",
                "redistribution_permitted": False,
                "registration_status": "unregistered",
                "rights_status": "unknown",
                "scope": "link_only",
                "source_id": "penn-museum-object-pages",
                "source_layer": "penn_item_page_association",
                "source_registry_binding": None,
            },
        ],
    }


def recursive_mutations(value: Any):
    if isinstance(value, dict):
        added = copy.deepcopy(value)
        added["unexpected"] = False
        yield added
        for key, child in value.items():
            removed = copy.deepcopy(value)
            del removed[key]
            yield removed
            for mutation in recursive_mutations(child):
                changed = copy.deepcopy(value)
                changed[key] = mutation
                yield changed
    elif isinstance(value, list):
        yield [*copy.deepcopy(value), None]
        if value:
            yield copy.deepcopy(value[:-1])
            reversed_value = list(reversed(copy.deepcopy(value)))
            if reversed_value != value:
                yield reversed_value
        for index, child in enumerate(value):
            for mutation in recursive_mutations(child):
                changed = copy.deepcopy(value)
                changed[index] = mutation
                yield changed
    elif isinstance(value, bool):
        yield not value
    elif isinstance(value, int):
        yield value + 1
    elif value is None:
        yield "unexpected"
    else:
        yield f"{value}-mutated"


class SourceReportedLinkPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy_bytes = POLICY_PATH.read_bytes()
        self.schema_bytes = SCHEMA_PATH.read_bytes()
        self.policy = json.loads(self.policy_bytes)
        self.schema = json.loads(self.schema_bytes)
        self.validator = Draft202012Validator(self.schema)

    def test_policy_schema_and_expected_object_are_exact_and_canonical(self) -> None:
        expected = expected_policy()
        Draft202012Validator.check_schema(self.schema)
        self.validator.validate(self.policy)
        self.assertEqual(expected, self.policy)
        self.assertEqual(expected, self.schema["const"])
        self.assertEqual(encode_json(expected), self.policy_bytes)
        self.assertEqual(encode_json(self.schema), self.schema_bytes)

    def test_exact_const_rejects_generated_recursive_mutations(self) -> None:
        checked = 0
        for mutation in recursive_mutations(self.policy):
            checked += 1
            self.assertTrue(list(self.validator.iter_errors(mutation)))
        self.assertGreater(checked, 200)

    def test_json_number_equivalence_still_changes_canonical_bytes(self) -> None:
        mutation = copy.deepcopy(self.policy)
        mutation["ordering"]["result_vector_length"] = 6.0
        self.assertFalse(list(self.validator.iter_errors(mutation)))
        self.assertNotEqual(self.policy_bytes, encode_json(mutation))
        self.assertIn("noncanonical_input", self.policy["decision_policy"]["hard_reject_inputs"])
        boundary = self.policy["execution_boundary"]
        self.assertIs(True, boundary["canonical_byte_identity_required"])

    def test_parent_hash_size_rows_conflict_and_collision_are_preserved(self) -> None:
        registry_bytes = PARENT_REGISTRY_PATH.read_bytes()
        schema_bytes = PARENT_SCHEMA_PATH.read_bytes()
        self.assertEqual(
            (6955, PARENT_REGISTRY_SHA256),
            (len(registry_bytes), hashlib.sha256(registry_bytes).hexdigest()),
        )
        self.assertEqual(
            (9216, PARENT_SCHEMA_SHA256),
            (len(schema_bytes), hashlib.sha256(schema_bytes).hexdigest()),
        )
        rows = json.loads(registry_bytes)["links"]
        self.assertEqual(list(LINK_IDS), [row["link_id"] for row in rows])
        self.assertEqual("excavation_location", rows[1]["unresolved_axis"])
        self.assertEqual(rows[4]["collision_group"], rows[5]["collision_group"])
        self.assertEqual(rows[4]["identifiers"][1:], rows[5]["identifiers"][1:])
        self.assertNotEqual(rows[4]["link_id"], rows[5]["link_id"])

    def test_per_row_order_precedence_and_no_link_proof_are_frozen(self) -> None:
        ordering = self.policy["ordering"]
        self.assertEqual(list(LINK_IDS), ordering["attempt_order"])
        self.assertIs(False, ordering["result_aggregation_permitted"])
        self.assertIs(False, ordering["post_hoc_row_substitution_permitted"])
        decision = self.policy["decision_policy"]
        self.assertIs(True, decision["contract_blocked_requires_empty_observations"])
        self.assertIn(
            "observations_present_before_prerequisites",
            decision["hard_reject_inputs"],
        )
        self.assertIs(False, decision["hard_reject_is_result_state"])
        self.assertIs(True, decision["hard_reject_precedes_state_evaluation"])
        self.assertEqual(
            ["contract_blocked", "unresolved", "source_reported_link", "no_link"],
            decision["state_precedence"],
        )
        self.assertIs(True, decision["terminal_states_mutually_exclusive"])
        proof = decision["no_link"]["complete_roster_requirements"]
        self.assertEqual(
            "dual_row_absent_with_exact_completeness_attestation_digest",
            decision["no_link"]["complete_roster_applies_to"],
        )
        self.assertEqual(6, len(proof["zero_count_fields"]))
        self.assertEqual(
            "unresolved",
            decision["no_link"]["not_found_without_complete_roster_state"],
        )

    def test_source_rights_pass_separation_and_nonclaims_remain_closed(self) -> None:
        mackay, penn = self.policy["source_scope"]
        self.assertEqual(
            ("registered", "unknown", "link_only"),
            (mackay["registration_status"], mackay["rights_status"], mackay["scope"]),
        )
        self.assertEqual(
            ("unregistered", "unknown", "link_only"),
            (penn["registration_status"], penn["rights_status"], penn["scope"]),
        )
        self.assertIs(False, penn["bulk_metadata_license_inherited"])
        self.assertIsNone(penn["source_registry_binding"])
        source_ids = {
            value["source_id"] for value in json.loads(SOURCE_REGISTRY_PATH.read_bytes())["sources"]
        }
        self.assertLessEqual(
            {"mackay-chanhu-daro-1943", "penn-museum-collections-data"}, source_ids
        )
        self.assertEqual(
            ("penn-museum-object-pages", "unregistered", None),
            (
                penn["source_id"],
                penn["registration_status"],
                penn["source_registry_binding"],
            ),
        )
        passes = self.policy["passes"]
        self.assertEqual("machine", passes["authorship"])
        self.assertEqual(["pass_id", "seal_sha256"], passes["required_distinct_fields"])
        self.assertEqual({False}, set(passes["nonclaims"].values()))
        self.assertEqual({False}, set(self.policy["nonclaims"].values()))

    def test_static_publication_boundary_has_no_runtime_or_outcome(self) -> None:
        boundary = self.policy["execution_boundary"]
        self.assertEqual("not_authorized", boundary["authorization_status"])
        self.assertEqual("not_executed", boundary["execution_status"])
        self.assertEqual("contract_blocked", boundary["current_prerequisite_state"])
        self.assertIs(False, boundary["runtime_evaluator_implemented"])
        self.assertNotIn("observations", self.policy)
        self.assertFalse((ROOT / "src" / "indusbench" / "source_reported_link.py").exists())


if __name__ == "__main__":
    unittest.main()
