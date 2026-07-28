from __future__ import annotations

import hashlib
import json
import os
import unittest
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any
from unittest.mock import patch

import indusbench.kp1982_bootstrap_review as bootstrap_review_module
from indusbench.io import encode_json
from indusbench.kp1982_bootstrap import (
    EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE,
    EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
)
from indusbench.kp1982_bootstrap_review import (
    KP1982BootstrapReviewError,
    compare_independent_review_bytes,
    validate_bootstrap_review,
    verify_adjudication_bytes,
    verify_independent_review_bytes,
    verify_stripped_bootstrap_assignment_bytes,
)
from indusbench.kp1982_layout import crop_canonical_pbm
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_SCHEMA = ROOT / "schemas" / "kp1982-bootstrap-assignment.schema.json"
REVIEW_SCHEMA = ROOT / "schemas" / "kp1982-bootstrap-review.schema.json"
REAL_INPUT_ENV = (
    "INDUSBENCH_KP1982_PAGE20_PBM",
    "INDUSBENCH_KP1982_PAGE21_PBM",
    "INDUSBENCH_KP1982_BOOTSTRAP_ASSIGNMENT",
)
PAGE_WIDTH = 4888
PAGE_HEIGHT = 6705
CROP_ENCODING = (
    "P4 with exact dimensions; row-major top-to-bottom, left-to-right, "
    "black=1, MSB-first, zero unused low bits"
)
ASSIGNMENT_COMMITMENT = {
    "manifest_id": "KP1982:BATCH0:BOOTSTRAP-ASSIGNMENT:V1",
    "sha256": EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
    "byte_size": EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE,
}
FALSE_SCIENTIFIC_ASSURANCES = {
    "assignment_cell_roster_semantically_verified",
    "source_page_pixels_reverified",
    "input_review_bytes_reverified",
    "human_review_started_verified",
    "human_review_complete_verified",
    "human_adjudication_complete_verified",
    "human_authorship_verified",
    "real_world_independence_verified",
    "reviewer_blinding_verified",
    "reviewer_nonexposure_verified",
    "cell_geometry_accepted",
    "occupancy_accepted",
    "identifiers_transcribed",
    "glyph_observations_accepted",
    "printed_marks_accepted",
    "source_custody_verified",
    "source_rights_verified",
    "sign_inventory_generated",
    "public_release_authorized",
    "evaluation_admissible",
    "decipherment",
    "prize_submission_eligible",
}
FORBIDDEN_INTERPRETIVE_KEYS = {
    "canonical_sign",
    "decipherment",
    "language",
    "meaning",
    "normalized_identifier",
    "phonetic_value",
    "reading",
    "sign_identity",
    "translation",
}


def tagged_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=1)
def synthetic_pages() -> tuple[bytes, bytes]:
    header = f"P4\n{PAGE_WIDTH} {PAGE_HEIGHT}\n".encode("ascii")
    payload = bytes(((PAGE_WIDTH + 7) // 8) * PAGE_HEIGHT)
    page = header + payload
    return page, page


def crop_commitment(page: bytes, bbox: list[int]) -> dict[str, Any]:
    crop = crop_canonical_pbm(
        page,
        page_width=PAGE_WIDTH,
        page_height=PAGE_HEIGHT,
        bbox=bbox,
    )
    return {
        "bbox": list(bbox),
        "sha256": tagged_sha256(crop),
        "byte_size": len(crop),
        "encoding": CROP_ENCODING,
    }


@lru_cache(maxsize=1)
def synthetic_assignment() -> dict[str, Any]:
    pages = synthetic_pages()
    cells: list[dict[str, Any]] = []
    for page_offset, page_index in enumerate((19, 20)):
        page_label = page_index + 1
        for lane_index in range(10):
            for row_index in range(35):
                x0 = 8 * lane_index
                y0 = 2 * row_index
                cell_bbox = [x0, y0, x0 + 8, y0 + 1]
                context_bbox = [x0, y0, x0 + 8, y0 + 2]
                cell_crop = crop_commitment(pages[page_offset], cell_bbox)
                context_crop = crop_commitment(pages[page_offset], context_bbox)
                cells.append(
                    {
                        "cell_id": (f"KP1982:P{page_label}:L{lane_index:02d}:R{row_index:02d}"),
                        "page_index": page_index,
                        "lane_index": lane_index,
                        "row_index": row_index,
                        "proposed_cell_bbox": cell_bbox,
                        "proposed_context_bbox": context_bbox,
                        "cell_crop_sha256": cell_crop["sha256"],
                        "cell_crop_byte_size": cell_crop["byte_size"],
                        "context_crop_sha256": context_crop["sha256"],
                        "context_crop_byte_size": context_crop["byte_size"],
                    }
                )
    return {
        "schema_version": "0.1.0",
        "manifest_id": "KP1982:BATCH0:BOOTSTRAP-ASSIGNMENT:V1",
        "status": (
            "private_proposal_value_stripped_bootstrap_assignment_only_requires_"
            "independent_human_review"
        ),
        "scientific_scope": (
            "proposal-value-stripped sign-inventory bootstrap assignment only; proposed "
            "crop rectangles are review aids, machine occupancy/OCR/identifier values are "
            "withheld, and no accepted observation, sign identity, phonetic, language, "
            "semantic, translation, or decipherment inference is present"
        ),
        "source_contract": {
            "id": "KP1982:BATCH0:SOURCE:V1",
            "sha256": "sha256:83ac4be31eb5be146508534df752c7531b5c14caadc20cdd210556644ccc36ab",
            "byte_size": 4029,
        },
        "layout_seed": {
            "id": "KP1982:BATCH0:LAYOUT-SEED:V1",
            "sha256": "sha256:1254226d13781b67e7c0c52bdeeb01b5327afb9f8b07acadb3e4a4333e72f820",
            "byte_size": 6922,
        },
        "layout_proposal": {
            "id": "KP1982:BATCH0:LAYOUT-PROPOSAL:V1",
            "sha256": "sha256:85dfa34210380ca6f92fa2847d50050642bc221910a05eb2fed33855f3894a78",
            "byte_size": 460008,
        },
        "page_bitmaps": [
            {
                "page_index": 19,
                "canonical_pbm_sha256": (
                    "sha256:092fa7fc48434e68e71aba57db858db5c82151d12692d6018fa836b66ee992cc"
                ),
                "byte_size": 4096768,
            },
            {
                "page_index": 20,
                "canonical_pbm_sha256": (
                    "sha256:c6313d5e597e723f8d3f9c4118d1aaf5d53a05c22b3dc557a8c2b65178445330"
                ),
                "byte_size": 4096768,
            },
        ],
        "crop_policy": {
            "algorithm": "kp1982-half-pitch-cells-v1",
            "coordinate_space": "decoded_embedded_page_image_pixels",
            "origin": "top_left",
            "rectangle_encoding": "half_open_xyxy_integer",
            "canonical_crop_encoding": CROP_ENCODING,
            "cell_crop_role": "locator_only_may_split_foreground",
            "context_crop_role": "review_view_not_accepted_glyph_evidence",
            "context_padding_pixels": 32,
            "bbox_status": "proposal_only_requires_independent_visual_acceptance",
        },
        "withheld_fields": [
            "layout_proposal.cells[].occupancy_proposal",
            "layout_proposal.cells[].accepted_occupancy",
            "all_ocr_output",
            "all_machine_identifier_proposals",
            "all_accepted_observation_fields",
        ],
        "cells": cells,
        "assurances": {
            "source_contract_exact_bytes_verified": True,
            "layout_seed_exact_bytes_verified": True,
            "layout_proposal_exact_bytes_verified": True,
            "canonical_page_bitmaps_verified": True,
            "cell_geometry_accepted": False,
            "occupancy_accepted": False,
            "human_review_complete": False,
            "reviewer_independence_verified": False,
            "reviewer_blinding_verified": False,
            "identifiers_transcribed": False,
            "private_storage_verified": False,
            "public_release_authorized": False,
            "evaluation_admissible": False,
            "decipherment": False,
        },
    }


def review_assurances(*, adjudication: bool) -> dict[str, bool]:
    return {
        "bootstrap_assignment_exact_bytes_bound": True,
        "all_700_cells_structurally_present": True,
        "two_sealed_input_review_commitments_present": adjudication,
        "assignment_cell_roster_semantically_verified": False,
        "source_page_pixels_reverified": False,
        "input_review_bytes_reverified": False,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_adjudication_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "reviewer_nonexposure_verified": False,
        "cell_geometry_accepted": False,
        "occupancy_accepted": False,
        "identifiers_transcribed": False,
        "glyph_observations_accepted": False,
        "printed_marks_accepted": False,
        "source_custody_verified": False,
        "source_rights_verified": False,
        "sign_inventory_generated": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }


def actor(actor_id: str, *, adjudicator: bool = False) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "role": "adjudicator" if adjudicator else "reviewer",
        "authorship_declared": "human",
        "identity_scope": "pseudonymous_identifier_only",
        "declared_access": {
            "machine_occupancy_ocr_identifier_proposals": "not_seen",
            "sealed_peer_review_outputs": "seen" if adjudicator else "not_seen",
            "preexisting_bootstrap_inventory": "not_seen",
        },
        "expertise": ["none_declared"],
    }


def independent_review(
    *,
    review_id: str = "KP1982:REVIEW:A",
    review_assignment_id: str = "KP1982:REVIEW-ASSIGNMENT:A",
    actor_id: str = "KP1982:ACTOR:A",
) -> dict[str, Any]:
    assignment = synthetic_assignment()
    pages = synthetic_pages()
    cells: list[dict[str, Any]] = []
    for ordinal, assignment_cell_value in enumerate(assignment["cells"]):
        assignment_cell = dict(assignment_cell_value)
        page = pages[0 if assignment_cell["page_index"] == 19 else 1]
        cell_bbox = list(assignment_cell["proposed_cell_bbox"])
        context_bbox = list(assignment_cell["proposed_context_bbox"])
        cell_evidence = crop_commitment(page, cell_bbox)
        context_evidence = crop_commitment(page, context_bbox)
        cells.append(
            {
                "cell_id": assignment_cell["cell_id"],
                "page_index": assignment_cell["page_index"],
                "lane_index": assignment_cell["lane_index"],
                "row_index": assignment_cell["row_index"],
                "occupancy": "single_entry",
                "cell_geometry": {
                    "decision": "accepted_as_proposed",
                    "cell_evidence": cell_evidence,
                    "context_evidence": context_evidence,
                    "reason_codes": ["accepted_without_change"],
                },
                "raw_upper_catalog_rank": {
                    "status": "observed",
                    "raw_text": str((ordinal % 35) + 1),
                    "evidence": cell_evidence,
                    "anomaly_codes": [],
                },
                "raw_lower_primary_identifier": {
                    "status": "observed",
                    "raw_text": str(ordinal + 1),
                    "evidence": cell_evidence,
                    "anomaly_codes": [],
                },
                "glyph_with_marks": {
                    "status": "observed",
                    "evidence": cell_evidence,
                    "anomaly_codes": [],
                },
                "glyph_core": None,
                "printed_marks": [],
                "condition": "clear",
                "uncertainty": {
                    "status": "certain",
                    "field_codes": [],
                    "reason_codes": [],
                },
                "input_observations": None,
                "adjudication_codes": [],
            }
        )
    return {
        "schema_version": "0.1.0",
        "record_state": "kp1982_sign_inventory_bootstrap_review",
        "status": "sealed_private_evidence_record_requires_exact_byte_and_semantic_verification",
        "review_id": review_id,
        "review_assignment_id": review_assignment_id,
        "review_stage": "independent_pass",
        "scientific_scope": (
            "visual sign-list inventory bootstrap observations only; no pre-existing sign "
            "inventory is a record dependency and no phonetic, language, semantic, meaning, "
            "translation, or decipherment assignment is present"
        ),
        "bootstrap_assignment": dict(ASSIGNMENT_COMMITMENT),
        "privacy": {
            "classification": "private_item_level_bootstrap_review_evidence",
            "raw_identifier_text_publication_authorized": False,
            "public_export_authorized": False,
        },
        "actor": actor(actor_id),
        "sealed_input_reviews": None,
        "cells": cells,
        "disagreements": [],
        "review_outcome": "complete",
        "limitations": [],
        "assurances": review_assurances(adjudication=False),
    }


def machine_unresolved_review(
    assignment: dict[str, Any],
    pages: list[bytes],
    *,
    review_id: str,
    review_assignment_id: str,
    actor_id: str,
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for assignment_cell_value in assignment["cells"]:
        assignment_cell = dict(assignment_cell_value)
        page = pages[0 if assignment_cell["page_index"] == 19 else 1]
        cell_evidence = crop_commitment(
            page,
            list(assignment_cell["proposed_cell_bbox"]),
        )
        context_evidence = crop_commitment(
            page,
            list(assignment_cell["proposed_context_bbox"]),
        )
        cells.append(
            {
                "cell_id": assignment_cell["cell_id"],
                "page_index": assignment_cell["page_index"],
                "lane_index": assignment_cell["lane_index"],
                "row_index": assignment_cell["row_index"],
                "occupancy": "uncertain",
                "cell_geometry": {
                    "decision": "accepted_as_proposed",
                    "cell_evidence": cell_evidence,
                    "context_evidence": context_evidence,
                    "reason_codes": ["accepted_without_change"],
                },
                "raw_upper_catalog_rank": {
                    "status": "unresolved",
                    "raw_text": None,
                    "evidence": cell_evidence,
                    "anomaly_codes": [],
                },
                "raw_lower_primary_identifier": {
                    "status": "unresolved",
                    "raw_text": None,
                    "evidence": cell_evidence,
                    "anomaly_codes": [],
                },
                "glyph_with_marks": {
                    "status": "unresolved",
                    "evidence": cell_evidence,
                    "anomaly_codes": ["crop_extent_unresolved"],
                },
                "glyph_core": None,
                "printed_marks": [],
                "condition": "unresolved",
                "uncertainty": {
                    "status": "unresolved",
                    "field_codes": [
                        "occupancy",
                        "upper_catalog_rank",
                        "lower_primary_identifier",
                        "glyph_with_marks",
                        "condition",
                        "uncertainty",
                    ],
                    "reason_codes": ["reviewer_abstention"],
                },
                "input_observations": None,
                "adjudication_codes": [],
            }
        )
    review = independent_review(
        review_id=review_id,
        review_assignment_id=review_assignment_id,
        actor_id=actor_id,
    )
    review["actor"]["authorship_declared"] = "machine"
    review["cells"] = cells
    review["review_outcome"] = "complete_with_unresolved_observations"
    review["limitations"] = ["unresolved_cells_present"]
    return review


def sealed_review(review: dict[str, Any]) -> dict[str, Any]:
    payload = encode_json(review)
    return {
        "review_id": review["review_id"],
        "review_sha256": tagged_sha256(payload),
        "review_byte_size": len(payload),
        "review_assignment_id": review["review_assignment_id"],
        "actor_id": review["actor"]["actor_id"],
        "review_stage": "independent_pass",
        "bootstrap_assignment_sha256": EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
        "seal_status": "exact_canonical_bytes_sha256_and_size_committed",
    }


def adjudication(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    has_unresolved_observations = False
    for left_value, right_value in zip(left["cells"], right["cells"], strict=True):
        left_cell = deepcopy(left_value)
        right_cell = dict(right_value)
        has_unresolved_observations = has_unresolved_observations or left_cell["uncertainty"][
            "status"
        ] in {"uncertain", "unresolved"}
        left_cell["input_observations"] = {
            "pass_a": {
                "review_id": left["review_id"],
                "cell_id": left_cell["cell_id"],
                "cell_observation_sha256": tagged_sha256(encode_json(left_value)),
            },
            "pass_b": {
                "review_id": right["review_id"],
                "cell_id": right_cell["cell_id"],
                "cell_observation_sha256": tagged_sha256(encode_json(right_value)),
            },
        }
        left_cell["adjudication_codes"] = ["inputs_agree"]
        cells.append(left_cell)
    adjudicator = actor("KP1982:ACTOR:ADJUDICATOR", adjudicator=True)
    if (
        left["actor"]["authorship_declared"] == "machine"
        and right["actor"]["authorship_declared"] == "machine"
    ):
        adjudicator["authorship_declared"] = "machine"
    return {
        "schema_version": "0.1.0",
        "record_state": "kp1982_sign_inventory_bootstrap_review",
        "status": "sealed_private_evidence_record_requires_exact_byte_and_semantic_verification",
        "review_id": "KP1982:REVIEW:ADJUDICATION",
        "review_assignment_id": "KP1982:REVIEW-ASSIGNMENT:ADJUDICATION",
        "review_stage": "adjudication",
        "scientific_scope": left["scientific_scope"],
        "bootstrap_assignment": dict(ASSIGNMENT_COMMITMENT),
        "privacy": deepcopy(left["privacy"]),
        "actor": adjudicator,
        "sealed_input_reviews": {
            "pass_a": sealed_review(left),
            "pass_b": sealed_review(right),
        },
        "cells": cells,
        "disagreements": [],
        "review_outcome": (
            "complete_with_unresolved_observations" if has_unresolved_observations else "complete"
        ),
        "limitations": (["unresolved_cells_present"] if has_unresolved_observations else []),
        "assurances": review_assurances(adjudication=True),
    }


def real_inputs() -> tuple[bytes, list[bytes]]:
    assignment_path = Path(os.environ[REAL_INPUT_ENV[2]])
    page_paths = [Path(os.environ[name]) for name in REAL_INPUT_ENV[:2]]
    return assignment_path.read_bytes(), [path.read_bytes() for path in page_paths]


def recursively_collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for child in value.values():
            keys.update(recursively_collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(recursively_collect_keys(child))
    return keys


class KP1982BootstrapReviewSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(REVIEW_SCHEMA.read_text(encoding="utf-8"))
        cls.left = independent_review()
        cls.right = independent_review(
            review_id="KP1982:REVIEW:B",
            review_assignment_id="KP1982:REVIEW-ASSIGNMENT:B",
            actor_id="KP1982:ACTOR:B",
        )

    def test_schema_is_closed_and_fixes_exactly_700_cells(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])
        cells = self.schema["properties"]["cells"]
        cell = self.schema["$defs"]["cell_review"]
        self.assertEqual(700, cells["minItems"])
        self.assertEqual(700, cells["maxItems"])
        self.assertTrue(cells["uniqueItems"])
        self.assertFalse(cell["additionalProperties"])
        self.assertEqual(set(cell["required"]), set(cell["properties"]))
        self.assertTrue(FORBIDDEN_INTERPRETIVE_KEYS.isdisjoint(cell["properties"]))

    def test_schema_keeps_scientific_and_prize_assurances_false(self) -> None:
        assurances = self.schema["$defs"]["assurances"]["properties"]
        self.assertTrue(
            all(assurances[name].get("const") is False for name in FALSE_SCIENTIFIC_ASSURANCES)
        )
        self.assertIs(assurances["bootstrap_assignment_exact_bytes_bound"]["const"], True)
        self.assertIs(assurances["all_700_cells_structurally_present"]["const"], True)
        self.assertEqual(
            {"type": "boolean"},
            assurances["two_sealed_input_review_commitments_present"],
        )

    def test_schema_restricts_identifier_text_and_closes_nested_evidence(self) -> None:
        raw_text = self.schema["$defs"]["raw_identifier_text"]
        self.assertEqual("^[0-9.'?]*[0-9][0-9.'?]*$", raw_text["pattern"])
        self.assertEqual(16, raw_text["maxLength"])
        for definition in (
            "actor",
            "bootstrap_assignment",
            "cell_geometry",
            "crop_commitment",
            "printed_mark",
            "raw_identifier_observation",
            "uncertainty",
        ):
            self.assertFalse(self.schema["$defs"][definition]["additionalProperties"])
        unresolved_rule = self.schema["$defs"]["raw_identifier_observation"]["allOf"][1]
        self.assertIn("unresolved", unresolved_rule["if"]["properties"]["status"]["enum"])
        self.assertEqual(
            "null",
            unresolved_rule["then"]["properties"]["raw_text"]["type"],
        )
        self.assertEqual(
            16 * 1024 * 1024,
            self.schema["$defs"]["sealed_input_review"]["properties"]["review_byte_size"][
                "maximum"
            ],
        )

    def test_complete_independent_and_adjudication_fixtures_validate_schema(self) -> None:
        self.assertEqual([], validate_schema_instance(self.left, REVIEW_SCHEMA))
        final = adjudication(self.left, self.right)
        self.assertEqual([], validate_schema_instance(final, REVIEW_SCHEMA))
        self.assertEqual(700, len(final["cells"]))

    def test_schema_rejects_extra_interpretive_field_and_true_nonclaim(self) -> None:
        hostile = deepcopy(self.left)
        hostile["cells"][0]["translation"] = "invented"
        issues = validate_schema_instance(hostile, REVIEW_SCHEMA)
        self.assertTrue(issues)

        false_claim = deepcopy(self.left)
        false_claim["assurances"]["decipherment"] = True
        issues = validate_schema_instance(false_claim, REVIEW_SCHEMA)
        self.assertTrue(issues)

    def test_schema_rejects_incomplete_roster_and_unresolved_identifier_text(self) -> None:
        incomplete = deepcopy(self.left)
        incomplete["cells"].pop()
        self.assertTrue(validate_schema_instance(incomplete, REVIEW_SCHEMA))

        unresolved = deepcopy(self.left)
        unresolved["cells"][0]["raw_upper_catalog_rank"]["status"] = "unresolved"
        self.assertTrue(validate_schema_instance(unresolved, REVIEW_SCHEMA))


class KP1982BootstrapReviewSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assignment = synthetic_assignment()
        cls.pages = list(synthetic_pages())
        cls.left = independent_review()
        cls.right = independent_review(
            review_id="KP1982:REVIEW:B",
            review_assignment_id="KP1982:REVIEW-ASSIGNMENT:B",
            actor_id="KP1982:ACTOR:B",
        )

    def test_mapping_validation_accepts_complete_synthetic_review(self) -> None:
        validate_bootstrap_review(self.left, self.assignment, self.pages)

    def test_mapping_validation_rejects_invalid_assignment_schema(self) -> None:
        invalid_assignment = deepcopy(self.assignment)
        invalid_assignment["unexpected"] = True
        with self.assertRaisesRegex(KP1982BootstrapReviewError, "assignment schema"):
            validate_bootstrap_review(self.left, invalid_assignment, self.pages)

    def test_mapping_validation_rejects_roster_order_and_coordinate_mismatch(self) -> None:
        swapped = deepcopy(self.left)
        swapped["cells"][0], swapped["cells"][1] = (
            swapped["cells"][1],
            swapped["cells"][0],
        )
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(swapped, self.assignment, self.pages)

        mismatched = deepcopy(self.left)
        mismatched["cells"][0]["row_index"] = 1
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(mismatched, self.assignment, self.pages)

    def test_mapping_validation_recomputes_every_submitted_crop(self) -> None:
        tampered = deepcopy(self.left)
        tampered["cells"][0]["glyph_with_marks"]["evidence"]["sha256"] = f"sha256:{'f' * 64}"
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(tampered, self.assignment, self.pages)

        outside_page = deepcopy(self.left)
        outside_page["cells"][0]["glyph_with_marks"]["evidence"]["bbox"] = [
            0,
            0,
            PAGE_WIDTH + 1,
            1,
        ]
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(outside_page, self.assignment, self.pages)

    def test_corrected_evidence_may_leave_proposal_but_must_stay_in_reviewed_context(
        self,
    ) -> None:
        corrected = deepcopy(self.left)
        cell = corrected["cells"][0]
        page = self.pages[0]
        reviewed_cell = [100, 100, 108, 102]
        reviewed_context = [90, 90, 160, 130]
        remote_component = [120, 100, 128, 101]
        remote_mark = [140, 100, 148, 101]
        cell["cell_geometry"] = {
            "decision": "corrected",
            "cell_evidence": crop_commitment(page, reviewed_cell),
            "context_evidence": crop_commitment(page, reviewed_context),
            "reason_codes": ["context_shifted", "foreground_crosses_locator"],
        }
        cell["raw_upper_catalog_rank"]["evidence"] = crop_commitment(
            page,
            remote_component,
        )
        cell["raw_lower_primary_identifier"]["evidence"] = crop_commitment(
            page,
            remote_component,
        )
        cell["glyph_with_marks"]["evidence"] = crop_commitment(
            page,
            remote_component,
        )
        cell["printed_marks"] = [
            {
                "mark_index": 0,
                "nonsemantic_class": "short_stroke_like",
                "association": "other_in_cell",
                "condition": "clear",
                "evidence": crop_commitment(page, remote_mark),
            }
        ]
        validate_bootstrap_review(corrected, self.assignment, self.pages)

        disjoint = deepcopy(corrected)
        disjoint["cells"][0]["glyph_with_marks"]["evidence"] = crop_commitment(
            page,
            [200, 200, 208, 201],
        )
        with self.assertRaisesRegex(KP1982BootstrapReviewError, "reviewed context"):
            validate_bootstrap_review(disjoint, self.assignment, self.pages)

        disjoint_geometry = deepcopy(corrected)
        disjoint_geometry["cells"][0]["cell_geometry"]["context_evidence"] = crop_commitment(
            page,
            [200, 200, 208, 202],
        )
        with self.assertRaisesRegex(KP1982BootstrapReviewError, "reviewed context"):
            validate_bootstrap_review(
                disjoint_geometry,
                self.assignment,
                self.pages,
            )

    def test_mapping_validation_rejects_forbidden_text_and_bidi_controls(self) -> None:
        interpretive = deepcopy(self.left)
        interpretive["cells"][0]["meaning"] = "fish"
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(interpretive, self.assignment, self.pages)

        bidi = deepcopy(self.left)
        bidi["cells"][0]["raw_upper_catalog_rank"]["raw_text"] = "\u202e12"
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(bidi, self.assignment, self.pages)

        punctuation_only = deepcopy(self.left)
        punctuation_only["cells"][0]["raw_upper_catalog_rank"].update(
            {
                "raw_text": "...",
                "anomaly_codes": ["leading_dot_visible"],
            }
        )
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(punctuation_only, self.assignment, self.pages)

        non_observed_punctuation = deepcopy(self.left)
        non_observed_punctuation["cells"][0]["raw_upper_catalog_rank"].update(
            {
                "status": "unreadable",
                "raw_text": None,
                "anomaly_codes": ["leading_dot_visible"],
            }
        )
        non_observed_punctuation["cells"][0]["uncertainty"] = {
            "status": "uncertain",
            "field_codes": ["upper_catalog_rank"],
            "reason_codes": ["identifier_unreadable"],
        }
        non_observed_punctuation["review_outcome"] = "complete_with_unresolved_observations"
        non_observed_punctuation["limitations"] = ["unresolved_cells_present"]
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(
                non_observed_punctuation,
                self.assignment,
                self.pages,
            )

        contradictory_geometry = deepcopy(self.left)
        contradictory_geometry["cells"][0]["cell_geometry"].update(
            {
                "decision": "unresolved",
                "reason_codes": [
                    "accepted_without_change",
                    "unresolved_boundary",
                ],
            }
        )
        contradictory_geometry["cells"][0]["uncertainty"] = {
            "status": "uncertain",
            "field_codes": ["cell_geometry"],
            "reason_codes": ["boundary_ambiguity"],
        }
        contradictory_geometry["review_outcome"] = "complete_with_unresolved_observations"
        contradictory_geometry["limitations"] = ["unresolved_cells_present"]
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(
                contradictory_geometry,
                self.assignment,
                self.pages,
            )

    def test_observation_state_contradictions_fail_closed(self) -> None:
        absent_glyph = deepcopy(self.left)
        cell = absent_glyph["cells"][0]
        cell["occupancy"] = "uncertain"
        cell["glyph_with_marks"].update(
            {
                "status": "not_present",
                "anomaly_codes": ["touches_cell_edge"],
            }
        )
        cell["uncertainty"] = {
            "status": "uncertain",
            "field_codes": ["occupancy"],
            "reason_codes": ["other_unclassified"],
        }
        absent_glyph["review_outcome"] = "complete_with_unresolved_observations"
        absent_glyph["limitations"] = ["unresolved_cells_present"]
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(
                absent_glyph,
                self.assignment,
                self.pages,
            )

        inapplicable_mark = deepcopy(self.left)
        inapplicable_mark["cells"][0]["printed_marks"] = [
            {
                "mark_index": 0,
                "nonsemantic_class": "dot_like",
                "association": "other_in_cell",
                "condition": "not_applicable",
                "evidence": deepcopy(inapplicable_mark["cells"][0]["glyph_with_marks"]["evidence"]),
            }
        ]
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(
                inapplicable_mark,
                self.assignment,
                self.pages,
            )

    def test_independent_pass_rejects_circular_or_peer_exposed_inputs(self) -> None:
        peer_exposed = deepcopy(self.left)
        peer_exposed["actor"]["declared_access"]["sealed_peer_review_outputs"] = "seen"
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(peer_exposed, self.assignment, self.pages)

        inventory_exposed = deepcopy(self.left)
        inventory_exposed["actor"]["declared_access"]["preexisting_bootstrap_inventory"] = "seen"
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(inventory_exposed, self.assignment, self.pages)

        machine_proposals_seen = deepcopy(self.left)
        machine_proposals_seen["actor"]["declared_access"][
            "machine_occupancy_ocr_identifier_proposals"
        ] = "seen"
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(
                machine_proposals_seen,
                self.assignment,
                self.pages,
            )

        for field_codes, reason_codes in (
            (["adjudication"], ["other_unclassified"]),
            (["condition"], ["input_reviews_disagree"]),
        ):
            peer_dependent = deepcopy(self.left)
            peer_dependent["cells"][0]["uncertainty"] = {
                "status": "uncertain",
                "field_codes": field_codes,
                "reason_codes": reason_codes,
            }
            peer_dependent["review_outcome"] = "complete_with_unresolved_observations"
            peer_dependent["limitations"] = ["unresolved_cells_present"]
            with self.assertRaisesRegex(
                KP1982BootstrapReviewError,
                "peer-dependent",
            ):
                validate_bootstrap_review(
                    peer_dependent,
                    self.assignment,
                    self.pages,
                )

    def test_mapping_validation_rejects_duplicate_lower_primary_identifier(self) -> None:
        duplicate = deepcopy(self.left)
        duplicate["cells"][1]["raw_lower_primary_identifier"]["raw_text"] = duplicate["cells"][0][
            "raw_lower_primary_identifier"
        ]["raw_text"]
        with self.assertRaises(KP1982BootstrapReviewError):
            validate_bootstrap_review(duplicate, self.assignment, self.pages)

    def test_mapping_validation_allows_duplicate_upper_catalog_rank(self) -> None:
        duplicate = deepcopy(self.left)
        duplicate["cells"][1]["raw_upper_catalog_rank"]["raw_text"] = duplicate["cells"][0][
            "raw_upper_catalog_rank"
        ]["raw_text"]
        validate_bootstrap_review(duplicate, self.assignment, self.pages)

    def test_honest_machine_authorship_does_not_masquerade_as_verified_human(self) -> None:
        machine = deepcopy(self.left)
        machine["actor"]["authorship_declared"] = "machine"
        validate_bootstrap_review(machine, self.assignment, self.pages)
        self.assertFalse(machine["assurances"]["human_authorship_verified"])

    def test_review_crop_budget_is_checked_before_mass_extraction(self) -> None:
        oversized = deepcopy(self.left)
        full_page = {
            "bbox": [0, 0, PAGE_WIDTH, PAGE_HEIGHT],
            "sha256": tagged_sha256(self.pages[0]),
            "byte_size": len(self.pages[0]),
            "encoding": CROP_ENCODING,
        }
        for cell in oversized["cells"]:
            cell["cell_geometry"] = {
                "decision": "corrected",
                "cell_evidence": dict(full_page),
                "context_evidence": dict(full_page),
                "reason_codes": ["context_expanded"],
            }
            cell["raw_upper_catalog_rank"]["evidence"] = dict(full_page)
            cell["raw_lower_primary_identifier"]["evidence"] = dict(full_page)
            cell["glyph_with_marks"]["evidence"] = dict(full_page)
        with self.assertRaisesRegex(KP1982BootstrapReviewError, "budget"):
            validate_bootstrap_review(oversized, self.assignment, self.pages)

    def test_assignment_exact_byte_gate_runs_before_json_decode(self) -> None:
        with (
            patch.object(
                bootstrap_review_module,
                "_decode_schema_object",
            ) as decode,
            self.assertRaisesRegex(
                KP1982BootstrapReviewError,
                "pinned stripped bytes",
            ),
        ):
            verify_stripped_bootstrap_assignment_bytes(b"{}", [])
        decode.assert_not_called()


class KP1982BootstrapReviewSyntheticExactApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assignment = synthetic_assignment()
        cls.assignment_bytes = encode_json(cls.assignment)
        cls.pages = list(synthetic_pages())
        cls.left = machine_unresolved_review(
            cls.assignment,
            cls.pages,
            review_id="KP1982:TEST-MACHINE-REVIEW:A",
            review_assignment_id="KP1982:TEST-MACHINE-ASSIGNMENT:A",
            actor_id="KP1982:TEST-MACHINE-ACTOR:A",
        )
        cls.right = machine_unresolved_review(
            cls.assignment,
            cls.pages,
            review_id="KP1982:TEST-MACHINE-REVIEW:B",
            review_assignment_id="KP1982:TEST-MACHINE-ASSIGNMENT:B",
            actor_id="KP1982:TEST-MACHINE-ACTOR:B",
        )
        cls.left_bytes = encode_json(cls.left)
        cls.right_bytes = encode_json(cls.right)

    def setUp(self) -> None:
        assignment_patcher = patch.object(
            bootstrap_review_module,
            "_verify_stripped_assignment_bytes",
            return_value=(self.assignment, {}),
        )
        page_patcher = patch.object(
            bootstrap_review_module,
            "_verify_page_pbms",
            return_value={19: self.pages[0], 20: self.pages[1]},
        )
        assignment_patcher.start()
        page_patcher.start()
        self.addCleanup(assignment_patcher.stop)
        self.addCleanup(page_patcher.stop)

    def test_machine_authored_unresolved_review_verifies_without_human_claim(self) -> None:
        summary = verify_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            self.left_bytes,
        )
        self.assertTrue(summary["review_exact_canonical_bytes_verified"])
        self.assertFalse(summary["human_authorship_verified"])
        self.assertFalse(summary["real_world_independence_verified"])
        self.assertFalse(summary["reviewer_blinding_verified"])
        self.assertFalse(summary["decipherment"])
        self.assertFalse(summary["prize_submission_eligible"])

    def test_noncanonical_or_tampered_independent_review_fails_closed(self) -> None:
        noncanonical = self.left_bytes.replace(b"{", b"{ ", 1)
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                noncanonical,
            )

        tampered = deepcopy(self.left)
        tampered["cells"][0]["glyph_with_marks"]["evidence"]["sha256"] = f"sha256:{'f' * 64}"
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                encode_json(tampered),
            )

    def test_excessive_json_depth_is_reported_as_a_fixed_validation_error(self) -> None:
        with (
            patch.object(
                bootstrap_review_module,
                "decode_json",
                side_effect=RecursionError,
            ),
            self.assertRaisesRegex(
                KP1982BootstrapReviewError,
                "safe structural depth",
            ),
        ):
            verify_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                self.left_bytes,
            )

    def test_comparison_requires_distinct_passes_and_never_returns_item_values(self) -> None:
        right = deepcopy(self.right)
        right["cells"][0]["raw_upper_catalog_rank"].update(
            {
                "status": "observed",
                "raw_text": "987654321",
            }
        )
        summary = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [self.left_bytes, encode_json(right)],
        )
        rendered = json.dumps(summary, sort_keys=True)
        self.assertNotIn("987654321", rendered)
        self.assertNotIn("raw_text", recursively_collect_keys(summary))
        self.assertEqual(
            0,
            summary["identifier_metrics"]["upper_catalog_rank"]["raw_comparable_count"],
        )
        self.assertIsNone(summary["identifier_metrics"]["upper_catalog_rank"]["raw_agreement_rate"])
        self.assertEqual(
            0,
            summary["geometry_metrics"]["glyph_core"]["comparable_count"],
        )
        self.assertIsNone(summary["geometry_metrics"]["glyph_core"]["bbox_iou_mean"])
        self.assertIsNone(summary["printed_mark_metrics"]["precision"])
        self.assertIsNone(summary["printed_mark_metrics"]["recall"])
        self.assertIsNone(summary["printed_mark_metrics"]["f1"])

        same_actor = deepcopy(self.right)
        same_actor["actor"]["actor_id"] = self.left["actor"]["actor_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            compare_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, encode_json(same_actor)],
            )

        same_review_id = deepcopy(self.right)
        same_review_id["review_id"] = self.left["review_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            compare_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, encode_json(same_review_id)],
            )

        same_assignment_id = deepcopy(self.right)
        same_assignment_id["review_assignment_id"] = self.left["review_assignment_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            compare_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, encode_json(same_assignment_id)],
            )

        cross_type_reuse = deepcopy(self.right)
        cross_type_reuse["actor"]["actor_id"] = self.left["review_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            compare_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, encode_json(cross_type_reuse)],
            )

    def test_comparison_reports_all_value_free_metric_families(self) -> None:
        left = independent_review(
            review_id="KP1982:METRICS-REVIEW:A",
            review_assignment_id="KP1982:METRICS-ASSIGNMENT:A",
            actor_id="KP1982:METRICS-ACTOR:A",
        )
        right = independent_review(
            review_id="KP1982:METRICS-REVIEW:B",
            review_assignment_id="KP1982:METRICS-ASSIGNMENT:B",
            actor_id="KP1982:METRICS-ACTOR:B",
        )
        right["cells"][0]["occupancy"] = "multiple_or_split"
        right["cells"][1]["raw_upper_catalog_rank"]["raw_text"] = "999999999"
        right["cells"][2]["raw_lower_primary_identifier"]["raw_text"] = "999998"

        remote_cell = [1000, 1000, 1008, 1002]
        remote_context = [992, 992, 1016, 1012]
        right["cells"][3]["cell_geometry"] = {
            "decision": "corrected",
            "cell_evidence": crop_commitment(self.pages[0], remote_cell),
            "context_evidence": crop_commitment(self.pages[0], remote_context),
            "reason_codes": ["context_shifted"],
        }
        for evidence_key in (
            "raw_upper_catalog_rank",
            "raw_lower_primary_identifier",
            "glyph_with_marks",
        ):
            right["cells"][3][evidence_key]["evidence"] = crop_commitment(
                self.pages[0],
                remote_cell,
            )

        shared_mark = {
            "mark_index": 0,
            "nonsemantic_class": "dot_like",
            "association": "other_in_cell",
            "condition": "clear",
            "evidence": crop_commitment(self.pages[0], [0, 8, 4, 9]),
        }
        left["cells"][4]["printed_marks"] = [deepcopy(shared_mark)]
        right["cells"][4]["printed_marks"] = [
            deepcopy(shared_mark),
            {
                "mark_index": 1,
                "nonsemantic_class": "short_stroke_like",
                "association": "other_in_cell",
                "condition": "clear",
                "evidence": crop_commitment(
                    self.pages[0],
                    [4, 8, 8, 9],
                ),
            },
        ]
        right["cells"][5]["condition"] = "worn"
        right["cells"][6]["uncertainty"] = {
            "status": "uncertain",
            "field_codes": ["condition"],
            "reason_codes": ["low_contrast"],
        }
        right["review_outcome"] = "complete_with_unresolved_observations"
        right["limitations"] = ["unresolved_cells_present"]

        summary = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [encode_json(left), encode_json(right)],
        )
        rendered = json.dumps(summary, sort_keys=True)
        self.assertNotIn("999999999", rendered)
        self.assertNotIn("999998", rendered)
        self.assertNotIn("raw_text", recursively_collect_keys(summary))

        occupancy = summary["occupancy_metrics"]
        self.assertEqual(699, occupancy["exact_agreement_count"])
        self.assertAlmostEqual(699 / 700, occupancy["exact_agreement_rate"])
        confusion = json.dumps(occupancy["confusion_matrix"], sort_keys=True)
        self.assertIn("single_entry", confusion)
        self.assertIn("multiple_or_split", confusion)

        for name in ("upper_catalog_rank", "lower_primary_identifier"):
            metrics = summary["identifier_metrics"][name]
            self.assertEqual(700, metrics["status_agreement_count"])
            self.assertEqual(1.0, metrics["status_agreement_rate"])
            self.assertEqual(700, metrics["raw_comparable_count"])
            self.assertEqual(699, metrics["raw_agreement_count"])
            self.assertAlmostEqual(699 / 700, metrics["raw_agreement_rate"])

        for name in ("cell", "context"):
            metrics = summary["geometry_metrics"][name]
            self.assertEqual(700, metrics["comparable_count"])
            self.assertAlmostEqual(699 / 700, metrics["bbox_iou_mean"])
            self.assertAlmostEqual(699 / 700, metrics["left_coverage_mean"])
            self.assertAlmostEqual(699 / 700, metrics["right_coverage_mean"])
            self.assertEqual(699, metrics["crop_sha256_agreement_count"])
            self.assertAlmostEqual(
                699 / 700,
                metrics["crop_sha256_agreement_rate"],
            )
        for name in ("upper_identifier", "lower_identifier", "glyph_with_marks"):
            metrics = summary["geometry_metrics"][name]
            self.assertEqual(700, metrics["comparable_count"])
            self.assertAlmostEqual(699 / 700, metrics["bbox_iou_mean"])
            self.assertAlmostEqual(699 / 700, metrics["left_coverage_mean"])
            self.assertAlmostEqual(699 / 700, metrics["right_coverage_mean"])
            self.assertEqual(699, metrics["crop_sha256_agreement_count"])
            self.assertAlmostEqual(
                699 / 700,
                metrics["crop_sha256_agreement_rate"],
            )
        core_metrics = summary["geometry_metrics"]["glyph_core"]
        self.assertEqual(0, core_metrics["comparable_count"])
        for name in (
            "bbox_iou_mean",
            "left_coverage_mean",
            "right_coverage_mean",
            "crop_sha256_agreement_rate",
        ):
            self.assertIsNone(core_metrics[name])

        marks = summary["printed_mark_metrics"]
        self.assertEqual(1, marks["left_count"])
        self.assertEqual(2, marks["right_count"])
        self.assertEqual(1, marks["matched_count"])
        self.assertEqual({0.5, 1.0}, {marks["precision"], marks["recall"]})
        self.assertAlmostEqual(2 / 3, marks["f1"])
        self.assertEqual(699, marks["exact_multiset_agreement_count"])
        self.assertAlmostEqual(699 / 700, marks["exact_multiset_agreement_rate"])
        self.assertEqual(699, summary["condition_metrics"]["agreement_count"])
        self.assertAlmostEqual(
            699 / 700,
            summary["condition_metrics"]["agreement_rate"],
        )
        self.assertEqual(699, summary["uncertainty_metrics"]["agreement_count"])
        self.assertAlmostEqual(
            699 / 700,
            summary["uncertainty_metrics"]["agreement_rate"],
        )
        self.assertEqual([0, 1], summary["unresolved_cell_count_by_pass"])

    def test_printed_mark_metrics_preserve_multiplicity_and_one_sided_f1(self) -> None:
        left = deepcopy(self.left)
        right = deepcopy(self.right)
        duplicate_mark = {
            "mark_index": 0,
            "nonsemantic_class": "dot_like",
            "association": "other_in_cell",
            "condition": "clear",
            "evidence": crop_commitment(self.pages[0], [0, 0, 1, 1]),
        }
        left["cells"][0]["printed_marks"] = [
            deepcopy(duplicate_mark),
            {
                **deepcopy(duplicate_mark),
                "mark_index": 1,
            },
        ]
        summary = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [encode_json(left), encode_json(right)],
        )
        marks = summary["printed_mark_metrics"]
        self.assertEqual(2, marks["left_count"])
        self.assertEqual(0, marks["right_count"])
        self.assertEqual(0, marks["matched_count"])
        self.assertIsNone(marks["precision"])
        self.assertEqual(0.0, marks["recall"])
        self.assertEqual(0.0, marks["f1"])
        self.assertEqual(699, marks["exact_multiset_agreement_count"])

    def test_adjudication_binds_two_exact_reviews_and_complete_cell_refs(self) -> None:
        final = adjudication(self.left, self.right)
        summary = verify_adjudication_bytes(
            self.assignment_bytes,
            self.pages,
            [self.left_bytes, self.right_bytes],
            encode_json(final),
        )
        self.assertTrue(summary["adjudication_exact_canonical_bytes_verified"])
        self.assertTrue(summary["two_input_review_exact_bytes_verified"])
        self.assertTrue(summary["all_700_input_observation_pairs_verified"])
        self.assertFalse(summary["real_world_independence_verified"])
        self.assertFalse(summary["decipherment"])
        self.assertFalse(summary["prize_submission_eligible"])

        wrong_ref = deepcopy(final)
        wrong_ref["cells"][0]["input_observations"]["pass_a"]["cell_id"] = wrong_ref["cells"][1][
            "cell_id"
        ]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(wrong_ref),
            )

    def test_adjudication_cannot_invent_observation_or_geometry(self) -> None:
        final = adjudication(self.left, self.right)
        invented = deepcopy(final)
        invented["cells"][0]["occupancy"] = "single_entry"
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(invented),
            )

        invented_geometry = deepcopy(final)
        evidence = invented_geometry["cells"][0]["glyph_with_marks"]["evidence"]
        evidence["bbox"] = [0, 0, 16, 1]
        crop = crop_canonical_pbm(
            self.pages[0],
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=evidence["bbox"],
        )
        evidence["sha256"] = tagged_sha256(crop)
        evidence["byte_size"] = len(crop)
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(invented_geometry),
            )

        invented_lower = adjudication(self.left, self.right)
        invented_lower["cells"][0]["raw_lower_primary_identifier"].update(
            {
                "status": "observed",
                "raw_text": "999999",
            }
        )
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(invented_lower),
            )

        invented_mark = adjudication(self.left, self.right)
        invented_mark["cells"][0]["printed_marks"] = [
            {
                "mark_index": 0,
                "nonsemantic_class": "dot_like",
                "association": "other_in_cell",
                "condition": "clear",
                "evidence": deepcopy(invented_mark["cells"][0]["glyph_with_marks"]["evidence"]),
            }
        ]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(invented_mark),
            )

    def test_adjudication_cannot_turn_equal_geometry_into_unresolved(self) -> None:
        final = adjudication(self.left, self.right)
        geometry = final["cells"][0]["cell_geometry"]
        geometry["decision"] = "unresolved"
        geometry["reason_codes"] = ["unresolved_boundary"]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(final),
            )

    def test_confident_identifier_disagreement_may_remain_explicitly_unresolved(
        self,
    ) -> None:
        left = independent_review(
            review_id="KP1982:UNRESOLVED-REVIEW:A",
            review_assignment_id="KP1982:UNRESOLVED-ASSIGNMENT:A",
            actor_id="KP1982:UNRESOLVED-ACTOR:A",
        )
        right = independent_review(
            review_id="KP1982:UNRESOLVED-REVIEW:B",
            review_assignment_id="KP1982:UNRESOLVED-ASSIGNMENT:B",
            actor_id="KP1982:UNRESOLVED-ACTOR:B",
        )
        right["cells"][0]["raw_upper_catalog_rank"]["raw_text"] = "999999"
        left_bytes = encode_json(left)
        right_bytes = encode_json(right)
        comparison = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [left_bytes, right_bytes],
        )

        final = adjudication(left, right)
        final_cell = final["cells"][0]
        final_cell["raw_upper_catalog_rank"].update(
            {
                "status": "unresolved",
                "raw_text": None,
                "anomaly_codes": [],
            }
        )
        final_cell["uncertainty"] = {
            "status": "unresolved",
            "field_codes": [
                "upper_catalog_rank",
                "uncertainty",
                "adjudication",
            ],
            "reason_codes": ["input_reviews_disagree"],
        }
        final_cell["adjudication_codes"] = ["left_unresolved"]
        final["disagreements"] = [
            {
                "cell_id": final_cell["cell_id"],
                "field_codes": ["upper_catalog_rank"],
                "input_review_ids": [left["review_id"], right["review_id"]],
                "comparison_sha256": comparison["comparison_sha256"],
                "resolution_code": "left_unresolved",
            }
        ]
        final["review_outcome"] = "complete_with_unresolved_observations"
        final["limitations"] = ["unresolved_cells_present"]

        summary = verify_adjudication_bytes(
            self.assignment_bytes,
            self.pages,
            [left_bytes, right_bytes],
            encode_json(final),
        )
        self.assertTrue(summary["no_third_observation_or_field_invention_verified"])
        self.assertEqual(1, summary["unresolved_cell_count"])
        self.assertFalse(summary["sign_inventory_generated"])

    def test_printed_mark_disagreement_can_remain_flagged_unresolved(self) -> None:
        left = independent_review(
            review_id="KP1982:MARK-REVIEW:A",
            review_assignment_id="KP1982:MARK-ASSIGNMENT:A",
            actor_id="KP1982:MARK-ACTOR:A",
        )
        right = independent_review(
            review_id="KP1982:MARK-REVIEW:B",
            review_assignment_id="KP1982:MARK-ASSIGNMENT:B",
            actor_id="KP1982:MARK-ACTOR:B",
        )
        right["cells"][0]["printed_marks"] = [
            {
                "mark_index": 0,
                "nonsemantic_class": "dot_like",
                "association": "other_in_cell",
                "condition": "clear",
                "evidence": deepcopy(right["cells"][0]["glyph_with_marks"]["evidence"]),
            }
        ]
        left_bytes = encode_json(left)
        right_bytes = encode_json(right)
        comparison = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [left_bytes, right_bytes],
        )

        final = adjudication(left, right)
        final_cell = final["cells"][0]
        final_cell["uncertainty"] = {
            "status": "unresolved",
            "field_codes": [
                "printed_marks",
                "uncertainty",
                "adjudication",
            ],
            "reason_codes": ["input_reviews_disagree"],
        }
        final_cell["adjudication_codes"] = [
            "selected_pass_a",
            "left_unresolved",
        ]
        final["disagreements"] = [
            {
                "cell_id": final_cell["cell_id"],
                "field_codes": ["printed_marks"],
                "input_review_ids": [left["review_id"], right["review_id"]],
                "comparison_sha256": comparison["comparison_sha256"],
                "resolution_code": "left_unresolved",
            }
        ]
        final["review_outcome"] = "complete_with_unresolved_observations"
        final["limitations"] = ["unresolved_cells_present"]

        summary = verify_adjudication_bytes(
            self.assignment_bytes,
            self.pages,
            [left_bytes, right_bytes],
            encode_json(final),
        )
        self.assertTrue(summary["no_third_observation_or_field_invention_verified"])
        self.assertEqual(1, summary["unresolved_cell_count"])
        self.assertFalse(summary["printed_marks_accepted"])

    def test_unresolved_geometry_cannot_mix_evidence_from_different_passes(self) -> None:
        right = deepcopy(self.right)
        right_geometry = right["cells"][0]["cell_geometry"]
        right_geometry["decision"] = "corrected"
        right_geometry["cell_evidence"] = crop_commitment(
            self.pages[0],
            [100, 100, 108, 102],
        )
        right_geometry["context_evidence"] = crop_commitment(
            self.pages[0],
            [0, 0, 116, 112],
        )
        right_geometry["reason_codes"] = ["context_shifted"]
        right_bytes = encode_json(right)
        comparison = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [self.left_bytes, right_bytes],
        )

        final = adjudication(self.left, right)
        final_geometry = final["cells"][0]["cell_geometry"]
        final_geometry["decision"] = "unresolved"
        final_geometry["cell_evidence"] = deepcopy(
            self.left["cells"][0]["cell_geometry"]["cell_evidence"]
        )
        final_geometry["context_evidence"] = deepcopy(
            right["cells"][0]["cell_geometry"]["context_evidence"]
        )
        final_geometry["reason_codes"] = ["unresolved_boundary"]
        final["cells"][0]["adjudication_codes"] = ["left_unresolved"]
        final["disagreements"] = [
            {
                "cell_id": final["cells"][0]["cell_id"],
                "field_codes": ["cell_geometry"],
                "input_review_ids": [self.left["review_id"], right["review_id"]],
                "comparison_sha256": comparison["comparison_sha256"],
                "resolution_code": "left_unresolved",
            }
        ]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, right_bytes],
                encode_json(final),
            )

    def test_adjudication_rejects_tampered_seals_and_reused_ids(self) -> None:
        final = adjudication(self.left, self.right)
        final["sealed_input_reviews"]["pass_a"]["review_sha256"] = f"sha256:{'f' * 64}"
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(final),
            )

        reused_actor = adjudication(self.left, self.right)
        reused_actor["actor"]["actor_id"] = self.left["actor"]["actor_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(reused_actor),
            )

        reused_review_id = adjudication(self.left, self.right)
        reused_review_id["review_id"] = self.left["review_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(reused_review_id),
            )

        reused_assignment_id = adjudication(self.left, self.right)
        reused_assignment_id["review_assignment_id"] = self.left["review_assignment_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(reused_assignment_id),
            )

        internally_reused_id = adjudication(self.left, self.right)
        internally_reused_id["actor"]["actor_id"] = internally_reused_id["review_id"]
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_adjudication_bytes(
                self.assignment_bytes,
                self.pages,
                [self.left_bytes, self.right_bytes],
                encode_json(internally_reused_id),
            )


@unittest.skipUnless(
    all(os.environ.get(name) for name in REAL_INPUT_ENV),
    "set canonical PBM and private bootstrap-assignment paths",
)
class KP1982BootstrapReviewRealAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assignment_bytes, cls.pages = real_inputs()
        assignment = json.loads(cls.assignment_bytes)
        if not isinstance(assignment, dict):
            raise TypeError("canonical bootstrap assignment must decode to an object")
        cls.assignment = assignment

    def test_stripped_assignment_verification_needs_no_layout_proposal(self) -> None:
        summary = verify_stripped_bootstrap_assignment_bytes(
            self.assignment_bytes,
            self.pages,
        )
        self.assertTrue(summary["assignment_exact_bytes_verified"])
        self.assertTrue(summary["all_700_assignment_crops_recomputed"])
        self.assertTrue(summary["layout_proposal_not_supplied"])
        self.assertFalse(summary["reviewer_blinding_verified"])
        self.assertFalse(summary["real_world_independence_verified"])
        self.assertFalse(summary["decipherment"])

    def test_noncanonical_assignment_bytes_fail_closed(self) -> None:
        noncanonical = self.assignment_bytes.replace(b"{", b"{ ", 1)
        with self.assertRaises(KP1982BootstrapReviewError):
            verify_stripped_bootstrap_assignment_bytes(noncanonical, self.pages)

    def test_machine_abstention_records_exercise_complete_exact_api_graph(self) -> None:
        left = machine_unresolved_review(
            self.assignment,
            self.pages,
            review_id="KP1982:REAL-TEST-MACHINE-REVIEW:A",
            review_assignment_id="KP1982:REAL-TEST-MACHINE-ASSIGNMENT:A",
            actor_id="KP1982:REAL-TEST-MACHINE-ACTOR:A",
        )
        right = machine_unresolved_review(
            self.assignment,
            self.pages,
            review_id="KP1982:REAL-TEST-MACHINE-REVIEW:B",
            review_assignment_id="KP1982:REAL-TEST-MACHINE-ASSIGNMENT:B",
            actor_id="KP1982:REAL-TEST-MACHINE-ACTOR:B",
        )
        left_bytes = encode_json(left)
        right_bytes = encode_json(right)
        for review_bytes in (left_bytes, right_bytes):
            summary = verify_independent_review_bytes(
                self.assignment_bytes,
                self.pages,
                review_bytes,
            )
            self.assertTrue(summary["review_exact_canonical_bytes_verified"])
            self.assertFalse(summary["human_authorship_verified"])

        comparison = compare_independent_review_bytes(
            self.assignment_bytes,
            self.pages,
            [left_bytes, right_bytes],
        )
        self.assertEqual(700, comparison["exact_cell_agreement_count"])
        self.assertTrue(comparison["adjudication_required"])

        final = adjudication(left, right)
        final_summary = verify_adjudication_bytes(
            self.assignment_bytes,
            self.pages,
            [left_bytes, right_bytes],
            encode_json(final),
        )
        self.assertTrue(final_summary["all_700_input_observation_pairs_verified"])
        self.assertTrue(final_summary["no_third_observation_or_field_invention_verified"])
        self.assertFalse(final_summary["human_adjudication_complete_verified"])
        self.assertFalse(final_summary["decipherment"])


if __name__ == "__main__":
    unittest.main()
