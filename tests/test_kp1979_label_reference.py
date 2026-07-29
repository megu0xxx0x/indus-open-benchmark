"""Core tests for proposal-free KP1979 visible-target-label reference evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from functools import lru_cache
from pathlib import Path
from typing import Any
from unittest.mock import patch

from indusbench.io import encode_json
from indusbench.kp1979_label_reference import (
    ASSIGNMENT_SCHEMA,
    PARTITION_PAGES,
    REVIEW_SCHEMA,
    KP1979LabelReferenceError,
    build_label_reference_assignment,
    validate_label_reference_review,
    verify_independent_label_reference_review_bytes,
    verify_label_reference_assignment_bytes,
)
from indusbench.kp1982_layout import crop_canonical_pbm
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_SCHEMA_PATH = ROOT / "schemas" / ASSIGNMENT_SCHEMA
REVIEW_SCHEMA_PATH = ROOT / "schemas" / REVIEW_SCHEMA
PAGE_WIDTH = 4880
PAGE_HEIGHT = 7010
PAGE_BYTE_SIZE = 4_276_113


def tagged_sha256(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


@lru_cache(maxsize=12)
def synthetic_page(page_number: int) -> bytes:
    header = f"P4\n{PAGE_WIDTH} {PAGE_HEIGHT}\n".encode("ascii")
    payload_size = ((PAGE_WIDTH + 7) // 8) * PAGE_HEIGHT
    payload = b"\xff" * (payload_size - 1) + bytes([0x80 | (page_number % 127)])
    page = header + payload
    assert len(page) == PAGE_BYTE_SIZE
    return page


@lru_cache(maxsize=1)
def blank_page() -> bytes:
    header = f"P4\n{PAGE_WIDTH} {PAGE_HEIGHT}\n".encode("ascii")
    payload = b"\x00" * (((PAGE_WIDTH + 7) // 8) * PAGE_HEIGHT)
    page = header + payload
    assert len(page) == PAGE_BYTE_SIZE
    return page


def synthetic_protocol_inputs() -> tuple[bytes, bytes, bytes]:
    source_contract = {
        "contract_id": "KP1979:CORPUS:SOURCE:V1",
        "source": {"source_id": "helsinki-indus-corpus-1979"},
    }
    pages = []
    for page_number in (*PARTITION_PAGES["development"], *PARTITION_PAGES["future_evaluation"]):
        pages.append(
            {
                "page_index": page_number - 1,
                "pdf_page_number": page_number,
                "canonical_pbm_sha256": tagged_sha256(synthetic_page(page_number)),
                "page_role": "synthetic-role-must-not-leak",
                "layout_class": "synthetic-class-must-not-leak",
                "proposal_scan_bands": [[1, 2, 3, 4]],
            }
        )
    page_map = {
        "map_id": "KP1979:CORPUS:PAGE-MAP:V1",
        "layout_evaluation_page_protocol": {
            "development_pdf_pages": list(PARTITION_PAGES["development"]),
            "future_evaluation_pdf_pages": list(PARTITION_PAGES["future_evaluation"]),
        },
        "pages": pages,
    }
    return encode_json(source_contract), encode_json(page_map), b"synthetic-pdf"


def page_inputs(partition: str) -> tuple[tuple[int, bytes], ...]:
    return tuple((number, synthetic_page(number)) for number in PARTITION_PAGES[partition])


def schema_assignment(partition: str) -> dict[str, Any]:
    schema = json.loads(ASSIGNMENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    partition_index = 0 if partition == "development" else 1
    branch = schema["allOf"][partition_index]["then"]["properties"]
    return {
        "schema_version": schema["properties"]["schema_version"]["const"],
        "manifest_id": branch["manifest_id"]["const"],
        "status": schema["properties"]["status"]["const"],
        "scientific_scope": schema["properties"]["scientific_scope"]["const"],
        "protocol_partition": partition,
        "source_contract": copy.deepcopy(schema["properties"]["source_contract"]["const"]),
        "page_map": copy.deepcopy(schema["properties"]["page_map"]["const"]),
        "source_pdf": copy.deepcopy(schema["properties"]["source_pdf"]["const"]),
        "page_bitmaps": [
            copy.deepcopy(value["const"]) for value in branch["page_bitmaps"]["prefixItems"]
        ],
        "coordinate_policy": copy.deepcopy(schema["properties"]["coordinate_policy"]["const"]),
        "withheld_fields": copy.deepcopy(schema["properties"]["withheld_fields"]["const"]),
        "assurances": copy.deepcopy(schema["properties"]["assurances"]["const"]),
    }


def synthetic_assignment(partition: str = "development") -> dict[str, Any]:
    contract_bytes, page_map_bytes, source_bytes = synthetic_protocol_inputs()
    with (
        patch(
            "indusbench.kp1979_label_reference.verify_kp1979_source",
            return_value={
                "valid": True,
                "source_snapshot_match": True,
                "page_map_snapshot_match": True,
                "layout_candidates_accepted": False,
                "decipherment": False,
            },
        ),
        patch("indusbench.kp1979_label_reference._require_schema"),
    ):
        return build_label_reference_assignment(
            contract_bytes,
            page_map_bytes,
            source_bytes,
            page_inputs(partition),
            partition=partition,
        )


def crop_fields(page_bytes: bytes, bbox: list[int]) -> dict[str, Any]:
    crop = crop_canonical_pbm(
        page_bytes,
        page_width=PAGE_WIDTH,
        page_height=PAGE_HEIGHT,
        bbox=bbox,
    )
    return {
        "bbox": bbox,
        "y_interval": [bbox[1], bbox[3]],
        "crop_sha256": tagged_sha256(crop),
        "crop_byte_size": len(crop),
    }


def independent_review(
    assignment: dict[str, Any],
    assignment_bytes: bytes,
    *,
    include_labels: bool,
    unresolved: bool = False,
) -> dict[str, Any]:
    review_schema = json.loads(REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
    pages = []
    for page_offset, commitment in enumerate(assignment["page_bitmaps"]):
        page_number = commitment["pdf_page_number"]
        lanes = []
        for lane_index in range(2):
            labels: list[dict[str, Any]] = []
            if include_labels and (page_offset + lane_index) % 2 == 0:
                x0 = lane_index * (PAGE_WIDTH // 2) + 16
                bbox = [x0, 32 + page_offset * 8, x0 + 16, 48 + page_offset * 8]
                labels.append(
                    {
                        "visual_label_index": 0,
                        "geometry_status": "unresolved" if unresolved else "observed",
                        **crop_fields(synthetic_page(page_number), bbox),
                        "reason_codes": (
                            ["boundary_ambiguous"] if unresolved else ["clear_visible_target_label"]
                        ),
                    }
                )
            lanes.append(
                {
                    "lane_index": lane_index,
                    "review_state": (
                        "unresolved"
                        if unresolved
                        else "complete_with_targets"
                        if labels
                        else "complete_no_targets"
                    ),
                    "unresolved_reason_codes": (
                        ["target_presence_uncertain"] if unresolved else []
                    ),
                    "visible_target_labels": labels,
                }
            )
        page_has_targets = any(lane["visible_target_labels"] for lane in lanes)
        pages.append(
            {
                "page_index": commitment["page_index"],
                "pdf_page_number": page_number,
                "review_state": (
                    "unresolved"
                    if unresolved
                    else "complete_with_targets"
                    if page_has_targets
                    else "complete_no_targets"
                ),
                "lanes": lanes,
            }
        )
    return {
        "schema_version": "0.1.0",
        "record_state": "kp1979_visible_target_label_reference_review",
        "status": "sealed_private_evidence_record_requires_exact_byte_and_semantic_verification",
        "review_id": "opaque:" + "1" * 64,
        "review_assignment_id": "opaque:" + "2" * 64,
        "actor_id": "opaque:" + "3" * 64,
        "review_stage": "independent_pass",
        "authorship_declaration": "unknown",
        "access_declaration": {
            "source_page_pixels": "seen",
            "detector_output": "not_seen",
            "kp1979_57_page_row_assignment": "not_seen",
            "ocr_output": "not_seen",
            "peer_review_record": "not_seen",
            "existing_label_reference": "not_seen",
            "page_role_expectations": "not_seen",
            "scoring_expectations": "not_seen",
        },
        "scientific_scope": review_schema["properties"]["scientific_scope"]["const"],
        "protocol_partition": assignment["protocol_partition"],
        "label_reference_assignment": {
            "manifest_id": assignment["manifest_id"],
            "sha256": tagged_sha256(assignment_bytes),
            "byte_size": len(assignment_bytes),
        },
        "privacy": copy.deepcopy(review_schema["properties"]["privacy"]["const"]),
        "pages": pages,
        "review_outcome": ("complete_with_unresolved_observations" if unresolved else "complete"),
        "limitations": ["unresolved_observations_present"] if unresolved else [],
        "assurances": copy.deepcopy(review_schema["properties"]["assurances"]["const"]),
    }


class KP1979LabelReferenceSchemaTests(unittest.TestCase):
    def test_assignment_schema_is_closed_partitioned_and_answer_free(self) -> None:
        schema = json.loads(ASSIGNMENT_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        for partition in PARTITION_PAGES:
            assignment = schema_assignment(partition)
            self.assertEqual([], validate_schema_instance(assignment, ASSIGNMENT_SCHEMA_PATH))
            encoded = encode_json(assignment).decode("utf-8")
            for forbidden in (
                '"page_role"',
                '"layout_class"',
                '"proposal_scan_bands"',
                '"candidate_y"',
                '"label_bbox"',
                '"label_count"',
                '"detector_output":{',
            ):
                self.assertNotIn(forbidden, encoded)
            self.assertFalse(assignment["assurances"]["target_label_counts_disclosed"])
            self.assertFalse(assignment["assurances"]["evaluation_admissible"])
            self.assertFalse(assignment["assurances"]["decipherment"])
        invalid = schema_assignment("development")
        invalid["unexpected"] = True
        self.assertTrue(validate_schema_instance(invalid, ASSIGNMENT_SCHEMA_PATH))

    def test_review_schema_allows_zero_nonzero_and_unresolved_on_any_page(self) -> None:
        assignment = synthetic_assignment()
        assignment_bytes = encode_json(assignment)
        for include_labels, unresolved in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            with self.subTest(include_labels=include_labels, unresolved=unresolved):
                review = independent_review(
                    assignment,
                    assignment_bytes,
                    include_labels=include_labels,
                    unresolved=unresolved,
                )
                self.assertEqual([], validate_schema_instance(review, REVIEW_SCHEMA_PATH))
        extra = independent_review(
            assignment,
            assignment_bytes,
            include_labels=False,
        )
        extra["pages"][0]["lanes"][0]["identifier"] = "forbidden"
        self.assertTrue(validate_schema_instance(extra, REVIEW_SCHEMA_PATH))

    def test_review_schema_fixes_nonclaims_and_opaque_identifiers(self) -> None:
        schema = json.loads(REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
        assurances = schema["properties"]["assurances"]["const"]
        for key in (
            "actor_identity_verified",
            "human_review_complete_verified",
            "human_authorship_verified",
            "real_world_independence_verified",
            "reviewer_blinding_verified",
            "evaluation_admissible",
            "decipherment",
            "prize_submission_eligible",
        ):
            self.assertIs(False, assurances[key])
        assignment = synthetic_assignment()
        raw = encode_json(assignment)
        review = independent_review(assignment, raw, include_labels=False)
        review["actor_id"] = "named-person"
        self.assertTrue(validate_schema_instance(review, REVIEW_SCHEMA_PATH))

    def test_target_rubric_and_freeze_nonclaims_are_machine_bound(self) -> None:
        assignment_schema = json.loads(ASSIGNMENT_SCHEMA_PATH.read_text(encoding="utf-8"))
        policy = assignment_schema["properties"]["coordinate_policy"]["const"]
        self.assertIn("two-line", policy["visible_target_definition"])
        self.assertIn("lower source-local code", policy["visible_target_definition"])
        self.assertIn("prime marks", policy["target_inclusion_rule"])
        self.assertIn("associated sign region", policy["target_inclusion_rule"])
        for excluded in (
            "sign drawings",
            "hatching",
            "row baselines",
            "page numbers",
            "prose",
            "sign-list",
            "auxiliary-grid",
        ):
            self.assertIn(excluded, policy["target_exclusion_rule"])
        self.assertIn("320", policy["target_bbox_size_rule"])
        self.assertIn("all four bbox edges", policy["target_bbox_rule"])
        self.assertIn(
            "must_be_frozen_separately",
            policy["downstream_scoring_policy"],
        )
        for schema_path in (ASSIGNMENT_SCHEMA_PATH, REVIEW_SCHEMA_PATH):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            assurances = schema["properties"]["assurances"]["const"]
            for key in (
                "reference_custody_verified",
                "detector_freeze_verified",
                "scorer_freeze_verified",
                "runtime_isolation_verified",
                "evaluation_admissible",
                "decipherment",
            ):
                self.assertIs(False, assurances[key])


class KP1979LabelReferenceCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        from indusbench import kp1979_label_reference as module

        self._original_schema_gate = module._require_schema
        self.assignment = synthetic_assignment()
        self.assignment_bytes = encode_json(self.assignment)
        self.pages = page_inputs("development")
        self.review = independent_review(
            self.assignment,
            self.assignment_bytes,
            include_labels=True,
        )

    def _schema_gate(self, value: Any, filename: str, label: str) -> None:
        if filename == ASSIGNMENT_SCHEMA:
            return
        original = self._original_schema_gate
        original(value, filename, label)

    def test_builder_separates_partitions_and_does_not_copy_page_metadata(self) -> None:
        contract_bytes, page_map_bytes, source_bytes = synthetic_protocol_inputs()
        source_summary = {
            "valid": True,
            "source_snapshot_match": True,
            "page_map_snapshot_match": True,
            "layout_candidates_accepted": False,
            "decipherment": False,
        }
        with (
            patch(
                "indusbench.kp1979_label_reference.verify_kp1979_source",
                return_value=source_summary,
            ),
            patch("indusbench.kp1979_label_reference._require_schema"),
        ):
            development = build_label_reference_assignment(
                contract_bytes,
                page_map_bytes,
                source_bytes,
                page_inputs("development"),
                partition="development",
            )
            evaluation = build_label_reference_assignment(
                contract_bytes,
                page_map_bytes,
                source_bytes,
                page_inputs("future_evaluation"),
                partition="future_evaluation",
            )
        self.assertEqual(
            list(PARTITION_PAGES["development"]),
            [value["pdf_page_number"] for value in development["page_bitmaps"]],
        )
        self.assertEqual(
            list(PARTITION_PAGES["future_evaluation"]),
            [value["pdf_page_number"] for value in evaluation["page_bitmaps"]],
        )
        self.assertTrue(
            set(PARTITION_PAGES["development"]).isdisjoint(PARTITION_PAGES["future_evaluation"])
        )
        encoded = encode_json(development).decode("utf-8")
        self.assertNotIn("synthetic-role-must-not-leak", encoded)
        self.assertNotIn("synthetic-class-must-not-leak", encoded)
        self.assertNotIn("proposal_scan_bands", encoded)

    def test_builder_returns_fresh_nested_coordinate_policy(self) -> None:
        contract_bytes, page_map_bytes, source_bytes = synthetic_protocol_inputs()
        source_summary = {
            "valid": True,
            "source_snapshot_match": True,
            "page_map_snapshot_match": True,
            "layout_candidates_accepted": False,
            "decipherment": False,
        }
        with (
            patch(
                "indusbench.kp1979_label_reference.verify_kp1979_source",
                return_value=source_summary,
            ),
            patch("indusbench.kp1979_label_reference._require_schema"),
        ):
            first = build_label_reference_assignment(
                contract_bytes,
                page_map_bytes,
                source_bytes,
                page_inputs("development"),
                partition="development",
            )
            first["coordinate_policy"]["physical_lane_bboxes"][0][0] = 99
            second = build_label_reference_assignment(
                contract_bytes,
                page_map_bytes,
                source_bytes,
                page_inputs("development"),
                partition="development",
            )
        self.assertEqual(0, second["coordinate_policy"]["physical_lane_bboxes"][0][0])

    def test_assignment_rejects_wrong_page_bytes_and_noncanonical_bytes(self) -> None:
        contract_bytes, page_map_bytes, source_bytes = synthetic_protocol_inputs()
        damaged_pages = list(self.pages)
        damaged_pages[0] = (damaged_pages[0][0], damaged_pages[0][1][:-1] + b"\x00")
        with (
            patch(
                "indusbench.kp1979_label_reference.verify_kp1979_source",
                return_value={
                    "valid": True,
                    "source_snapshot_match": True,
                    "page_map_snapshot_match": True,
                    "layout_candidates_accepted": False,
                    "decipherment": False,
                },
            ),
            patch("indusbench.kp1979_label_reference._require_schema"),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "page-map commitment",
            ),
        ):
            build_label_reference_assignment(
                contract_bytes,
                page_map_bytes,
                source_bytes,
                damaged_pages,
                partition="development",
            )

        with (
            patch(
                "indusbench.kp1979_label_reference._require_schema",
            ),
            patch(
                "indusbench.kp1979_label_reference.build_label_reference_assignment",
                return_value=self.assignment,
            ),
            self.assertRaisesRegex(KP1979LabelReferenceError, "not canonical JSON"),
        ):
            verify_label_reference_assignment_bytes(
                contract_bytes,
                page_map_bytes,
                source_bytes,
                self.pages,
                self.assignment_bytes + b" ",
            )

    def test_exact_review_api_recomputes_crops_and_keeps_nonclaims_false(self) -> None:
        from indusbench import kp1979_label_reference as module

        self._original_schema_gate = module._require_schema
        with patch.object(module, "_require_schema", side_effect=self._schema_gate):
            summary = verify_independent_label_reference_review_bytes(
                self.assignment_bytes,
                self.pages,
                encode_json(self.review),
            )
        self.assertTrue(summary["valid"])
        self.assertTrue(summary["assignment_commitment_verified"])
        self.assertTrue(summary["submitted_crop_bytes_recomputed"])
        self.assertTrue(summary["opaque_record_ids_structurally_distinct"])
        self.assertTrue(summary["authorship_declaration_recorded"])
        self.assertTrue(summary["access_declaration_recorded"])
        for key in (
            "actor_identity_verified",
            "human_review_complete_verified",
            "human_authorship_verified",
            "real_world_independence_verified",
            "reviewer_blinding_verified",
            "evaluation_admissible",
            "decipherment",
            "prize_submission_eligible",
        ):
            self.assertIs(False, summary[key])

    def test_review_rejects_crop_y_lane_roster_and_identifier_tampering(self) -> None:
        from indusbench import kp1979_label_reference as module

        self._original_schema_gate = module._require_schema
        cases: list[tuple[str, dict[str, Any], str]] = []

        crop_tamper = copy.deepcopy(self.review)
        crop_tamper["pages"][0]["lanes"][0]["visible_target_labels"][0]["crop_sha256"] = (
            "sha256:" + "0" * 64
        )
        cases.append(("crop", crop_tamper, "crop commitment"))

        y_tamper = copy.deepcopy(self.review)
        y_tamper["pages"][0]["lanes"][0]["visible_target_labels"][0]["y_interval"] = [
            0,
            1,
        ]
        cases.append(("y", y_tamper, "y interval"))

        lane_tamper = copy.deepcopy(self.review)
        lane_tamper["pages"][0]["lanes"][0]["lane_index"] = 1
        cases.append(("lane", lane_tamper, "schema invalid"))

        identifier_tamper = copy.deepcopy(self.review)
        identifier_tamper["pages"][0]["lanes"][0]["visible_target_labels"][0]["identifier"] = "123"
        cases.append(("identifier", identifier_tamper, "forbidden answer"))

        for name, review, message in cases:
            with (
                self.subTest(name=name),
                patch.object(module, "_require_schema", side_effect=self._schema_gate),
                self.assertRaisesRegex(KP1979LabelReferenceError, message),
            ):
                verify_independent_label_reference_review_bytes(
                    self.assignment_bytes,
                    self.pages,
                    encode_json(review),
                )

    def test_review_rejects_assignment_commitment_and_noncanonical_bytes(self) -> None:
        from indusbench import kp1979_label_reference as module

        for field, replacement in (
            ("sha256", "sha256:" + "0" * 64),
            ("byte_size", len(self.assignment_bytes) + 1),
        ):
            review = copy.deepcopy(self.review)
            review["label_reference_assignment"][field] = replacement
            with (
                self.subTest(field=field),
                patch.object(module, "_require_schema", side_effect=self._schema_gate),
                self.assertRaisesRegex(
                    KP1979LabelReferenceError,
                    "does not bind",
                ),
            ):
                verify_independent_label_reference_review_bytes(
                    self.assignment_bytes,
                    self.pages,
                    encode_json(review),
                )

        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "not canonical JSON",
            ),
        ):
            verify_independent_label_reference_review_bytes(
                self.assignment_bytes,
                self.pages,
                encode_json(self.review) + b" ",
            )

    def test_review_rejects_nested_forbidden_depth_duplicate_and_nonfinite_json(
        self,
    ) -> None:
        from indusbench import kp1979_label_reference as module

        nested_forbidden = copy.deepcopy(self.review)
        nested_forbidden["privacy"]["nested"] = {"wrapper": {"identifier": "forbidden-value"}}
        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "forbidden answer",
            ),
        ):
            verify_independent_label_reference_review_bytes(
                self.assignment_bytes,
                self.pages,
                encode_json(nested_forbidden),
            )

        over_depth = copy.deepcopy(self.review)
        cursor: dict[str, Any] = over_depth["privacy"]
        for index in range(70):
            child: dict[str, Any] = {}
            cursor[f"safe_{index}"] = child
            cursor = child
        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "nesting exceeds",
            ),
        ):
            verify_independent_label_reference_review_bytes(
                self.assignment_bytes,
                self.pages,
                encode_json(over_depth),
            )

        canonical = encode_json(self.review)
        duplicate_key = b'{"schema_version":"0.1.0",' + canonical[1:]
        for name, malformed in (
            ("duplicate", duplicate_key),
            ("nonfinite", b'{"value":NaN}'),
        ):
            with (
                self.subTest(name=name),
                patch.object(module, "_require_schema", side_effect=self._schema_gate),
                self.assertRaisesRegex(
                    KP1979LabelReferenceError,
                    "strict finite JSON",
                ),
            ):
                verify_independent_label_reference_review_bytes(
                    self.assignment_bytes,
                    self.pages,
                    malformed,
                )

    def test_mapping_api_preflights_depth_before_json_schema(self) -> None:
        from indusbench import kp1979_label_reference as module

        over_depth = copy.deepcopy(self.review)
        cursor: dict[str, Any] = over_depth["privacy"]
        for index in range(70):
            child: dict[str, Any] = {}
            cursor[f"safe_{index}"] = child
            cursor = child
        with (
            patch.object(module, "_require_schema") as schema_gate,
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "nesting exceeds",
            ),
        ):
            validate_label_reference_review(
                over_depth,
                self.assignment,
                self.pages,
            )
        schema_gate.assert_not_called()

    def test_review_requires_distinct_opaque_ids_and_consistent_unresolved_state(self) -> None:
        duplicate_ids = copy.deepcopy(self.review)
        duplicate_ids["actor_id"] = duplicate_ids["review_id"]
        from indusbench import kp1979_label_reference as module

        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "structurally distinct",
            ),
        ):
            validate_label_reference_review(duplicate_ids, self.assignment, self.pages)

        unresolved = independent_review(
            self.assignment,
            self.assignment_bytes,
            include_labels=False,
            unresolved=True,
        )
        unresolved["review_outcome"] = "complete"
        unresolved["limitations"] = []
        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "complete review",
            ),
        ):
            validate_label_reference_review(unresolved, self.assignment, self.pages)

    def test_review_accepts_complete_zero_and_nonzero_rosters(self) -> None:
        from indusbench import kp1979_label_reference as module

        for include_labels in (False, True):
            with (
                self.subTest(include_labels=include_labels),
                patch.object(module, "_require_schema", side_effect=self._schema_gate),
            ):
                review = independent_review(
                    self.assignment,
                    self.assignment_bytes,
                    include_labels=include_labels,
                )
                validate_label_reference_review(
                    review,
                    self.assignment,
                    self.pages,
                )

    def test_access_seen_and_unknown_remain_valid_unattested_declarations(self) -> None:
        from indusbench import kp1979_label_reference as module

        for key, state in (
            ("detector_output", "seen"),
            ("kp1979_57_page_row_assignment", "unknown"),
            ("ocr_output", "seen"),
            ("peer_review_record", "unknown"),
            ("existing_label_reference", "seen"),
            ("page_role_expectations", "seen"),
            ("scoring_expectations", "unknown"),
        ):
            with self.subTest(key=key, state=state):
                review = copy.deepcopy(self.review)
                review["authorship_declaration"] = "human"
                review["access_declaration"][key] = state
                with patch.object(
                    module,
                    "_require_schema",
                    side_effect=self._schema_gate,
                ):
                    summary = verify_independent_label_reference_review_bytes(
                        self.assignment_bytes,
                        self.pages,
                        encode_json(review),
                    )
                self.assertTrue(summary["authorship_declaration_recorded"])
                self.assertTrue(summary["access_declaration_recorded"])
                self.assertFalse(summary["authorship_declaration_verified"])
                self.assertFalse(summary["access_declaration_verified"])
                self.assertFalse(summary["reviewer_nonexposure_verified"])
                self.assertFalse(summary["real_world_independence_verified"])
                self.assertFalse(summary["evaluation_admissible"])

    def test_tight_bbox_rejects_whitespace_and_oversized_geometry(self) -> None:
        from indusbench import kp1979_label_reference as module

        altered_assignment = copy.deepcopy(self.assignment)
        altered_assignment["page_bitmaps"][0]["canonical_pbm_sha256"] = tagged_sha256(blank_page())
        altered_pages = list(self.pages)
        altered_pages[0] = (altered_pages[0][0], blank_page())
        altered_assignment_bytes = encode_json(altered_assignment)
        whitespace_review = independent_review(
            altered_assignment,
            altered_assignment_bytes,
            include_labels=True,
        )
        first_label = whitespace_review["pages"][0]["lanes"][0]["visible_target_labels"][0]
        first_label.update(crop_fields(blank_page(), first_label["bbox"]))
        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "tight to black ink",
            ),
        ):
            validate_label_reference_review(
                whitespace_review,
                altered_assignment,
                tuple(altered_pages),
            )

        oversized = copy.deepcopy(self.review)
        label = oversized["pages"][0]["lanes"][0]["visible_target_labels"][0]
        bbox = [16, 32, 337, 48]
        label.update(crop_fields(synthetic_page(20), bbox))
        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "tight target size limit",
            ),
        ):
            validate_label_reference_review(
                oversized,
                self.assignment,
                self.pages,
            )

    def test_overlapping_vertical_intervals_are_rejected(self) -> None:
        from indusbench import kp1979_label_reference as module

        overlapping = copy.deepcopy(self.review)
        labels = overlapping["pages"][0]["lanes"][0]["visible_target_labels"]
        second_bbox = [16, 40, 32, 56]
        labels.append(
            {
                "visual_label_index": 1,
                "geometry_status": "observed",
                **crop_fields(synthetic_page(20), second_bbox),
                "reason_codes": ["clear_visible_target_label"],
            }
        )
        with (
            patch.object(module, "_require_schema", side_effect=self._schema_gate),
            self.assertRaisesRegex(
                KP1979LabelReferenceError,
                "y intervals overlap",
            ),
        ):
            validate_label_reference_review(
                overlapping,
                self.assignment,
                self.pages,
            )

    def test_lane_state_and_reason_contradictions_fail_closed(self) -> None:
        from indusbench import kp1979_label_reference as module

        cases: list[tuple[str, dict[str, Any], str]] = []

        empty_claims_targets = independent_review(
            self.assignment,
            self.assignment_bytes,
            include_labels=False,
        )
        empty_claims_targets["pages"][0]["lanes"][0]["review_state"] = "complete_with_targets"
        cases.append(("empty-targets", empty_claims_targets, "schema invalid"))

        targets_claim_empty = copy.deepcopy(self.review)
        targets_claim_empty["pages"][0]["lanes"][0]["review_state"] = "complete_no_targets"
        cases.append(("targets-empty", targets_claim_empty, "schema invalid"))

        unresolved_without_reason = independent_review(
            self.assignment,
            self.assignment_bytes,
            include_labels=False,
            unresolved=True,
        )
        unresolved_without_reason["pages"][0]["lanes"][0]["unresolved_reason_codes"] = []
        cases.append(("unresolved-reason", unresolved_without_reason, "schema invalid"))

        wrong_page_state = copy.deepcopy(self.review)
        wrong_page_state["pages"][0]["review_state"] = "complete_no_targets"
        cases.append(("page-state", wrong_page_state, "page status contradicts"))

        observed_ambiguous = copy.deepcopy(self.review)
        observed_ambiguous["pages"][0]["lanes"][0]["visible_target_labels"][0]["reason_codes"] = [
            "boundary_ambiguous"
        ]
        cases.append(("observed-ambiguous", observed_ambiguous, "schema invalid"))

        for name, review, message in cases:
            with (
                self.subTest(name=name),
                patch.object(module, "_require_schema", side_effect=self._schema_gate),
                self.assertRaisesRegex(KP1979LabelReferenceError, message),
            ):
                validate_label_reference_review(
                    review,
                    self.assignment,
                    self.pages,
                )


if __name__ == "__main__":
    unittest.main()
