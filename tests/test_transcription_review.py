from __future__ import annotations

import copy
import errno
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import indusbench.cli as cli_module
from indusbench.baseline import extract_sequences
from indusbench.cli import main
from indusbench.io import encode_json, write_json
from indusbench.schema_validation import validate_schema_instance
from indusbench.transcription_review import (
    INVENTORY_SCOPE,
    SCIENTIFIC_SCOPE,
    TranscriptionReviewError,
    compare_independent_transcriptions,
    promote_adjudicated_transcription,
    sha256_bytes,
    validate_sign_inventory,
    validate_transcription_review,
    verify_transcription_evidence_bytes,
)
from indusbench.validation import has_errors, validate_artifact
from tests.test_validation import valid_artifact

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SCHEMA = ROOT / "schemas" / "sign-inventory.schema.json"
REVIEW_SCHEMA = ROOT / "schemas" / "transcription-review.schema.json"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(argv)
    return result, stdout.getvalue(), stderr.getvalue()


def sign_inventory() -> dict:
    return {
        "schema_version": "0.1.0",
        "inventory_id": "SYN:INVENTORY",
        "edition": "fixture-v1",
        "title": "Synthetic visual sign inventory",
        "source_id": "synthetic",
        "revision": "fixture-v1",
        "primary_identifier_scheme": "SYN:PRIMARY",
        "scientific_scope": INVENTORY_SCOPE,
        "rights": {
            "analysis_use": "permitted",
            "redistribution": True,
            "derivatives": True,
            "license_id": "CC0-1.0",
            "evidence_uri": "https://example.org/synthetic-rights",
            "statement": "Synthetic fixture.",
        },
        "source_documents": [
            {
                "document_id": "SYN:DOC",
                "source_record_id": "SYN:DOC:RECORD",
                "title": "Synthetic sign list",
                "creators": ["Synthetic fixture author"],
                "publication_year": 2026,
                "uri": "https://example.org/synthetic-sign-list.pdf",
                "sha256": f"sha256:{'9' * 64}",
                "media_type": "application/pdf",
                "page_count": 1,
                "license_id": "CC0-1.0",
                "license_uri": "https://creativecommons.org/publicdomain/zero/1.0/",
                "rights_evidence_uri": "https://example.org/synthetic-rights",
            }
        ],
        "signs": [
            {
                "sign_id": "S001",
                "project_sign_id": "SYN:001",
                "graphic_label": "synthetic one",
                "published_identifiers": [
                    {
                        "scheme_id": "SYN:PRIMARY",
                        "value": "S001",
                        "role": "primary_source_identifier",
                        "document_id": "SYN:DOC",
                        "evidence_id": "SYN:EVIDENCE:1",
                    },
                    {
                        "scheme_id": "SYN:RANK",
                        "value": "1",
                        "role": "catalog_rank",
                        "document_id": "SYN:DOC",
                        "evidence_id": "SYN:EVIDENCE:1",
                    },
                ],
                "graphic_sources": [
                    {
                        "evidence_id": "SYN:EVIDENCE:1",
                        "document_id": "SYN:DOC",
                        "page_index": 0,
                        "printed_page_label": "1",
                        "coordinate_space": "normalized_page",
                        "polygon": [
                            [0.1, 0.1],
                            [0.2, 0.1],
                            [0.2, 0.2],
                            [0.1, 0.2],
                        ],
                        "crop_sha256": f"sha256:{'7' * 64}",
                        "extraction_method": "human_double_transcription",
                        "doubt_markers": [],
                        "doubt_notes": None,
                    }
                ],
                "deprecated": False,
                "superseded_by": None,
                "notes": None,
            },
            {
                "sign_id": "S002",
                "project_sign_id": "SYN:002",
                "graphic_label": "synthetic two",
                "published_identifiers": [
                    {
                        "scheme_id": "SYN:PRIMARY",
                        "value": "S002",
                        "role": "primary_source_identifier",
                        "document_id": "SYN:DOC",
                        "evidence_id": "SYN:EVIDENCE:2",
                    },
                    {
                        "scheme_id": "SYN:RANK",
                        "value": "1",
                        "role": "catalog_rank",
                        "document_id": "SYN:DOC",
                        "evidence_id": "SYN:EVIDENCE:2",
                    },
                ],
                "graphic_sources": [
                    {
                        "evidence_id": "SYN:EVIDENCE:2",
                        "document_id": "SYN:DOC",
                        "page_index": 0,
                        "printed_page_label": "1",
                        "coordinate_space": "normalized_page",
                        "polygon": [
                            [0.3, 0.1],
                            [0.4, 0.1],
                            [0.4, 0.2],
                            [0.3, 0.2],
                        ],
                        "crop_sha256": f"sha256:{'8' * 64}",
                        "extraction_method": "human_double_transcription",
                        "doubt_markers": [],
                        "doubt_notes": None,
                    }
                ],
                "deprecated": False,
                "superseded_by": None,
                "notes": None,
            },
        ],
    }


def sign_ref(sign_id: str) -> dict:
    return {
        "inventory_id": "SYN:INVENTORY",
        "edition": "fixture-v1",
        "sign_id": sign_id,
    }


def token(
    token_id: str,
    *,
    visual_index: int,
    reading_index: int,
    sign_id: str,
    left: float,
) -> dict:
    return {
        "token_id": token_id,
        "visual_index": visual_index,
        "reading_index": reading_index,
        "geometry": {
            "image_id": "SYN:IMG001",
            "image_sha256": f"sha256:{'0' * 64}",
            "coordinate_space": "normalized_original_image",
            "polygon": [
                [left, 0.2],
                [left + 0.2, 0.2],
                [left + 0.2, 0.8],
                [left, 0.8],
            ],
        },
        "segmentation": "single",
        "condition": "clear",
        "selected_sign": sign_ref(sign_id),
        "alternatives": [],
        "confidence": 1.0,
        "uncertainty": {"status": "certain", "notes": None},
        "input_token_refs": [],
        "adjudication_reason": None,
    }


def independent_review(
    inventory_sha256: str,
    *,
    review_id: str,
    assignment_id: str,
    actor_id: str,
) -> dict:
    return {
        "schema_version": "0.1.0",
        "record_state": "sign_transcription_review",
        "review_id": review_id,
        "assignment_id": assignment_id,
        "review_stage": "independent",
        "subject_id": "SYN:A001:obverse:L1",
        "scientific_scope": SCIENTIFIC_SCOPE,
        "visual_order_basis": "left_to_right_in_image",
        "sign_inventory": {
            "inventory_id": "SYN:INVENTORY",
            "edition": "fixture-v1",
            "sha256": inventory_sha256,
        },
        "source_commitment": {
            "subject_id": "SYN:A001:obverse:L1",
            "source_record_ids": ["SYN:A001:source"],
            "image_id": "SYN:IMG001",
            "image_sha256": f"sha256:{'0' * 64}",
            "region_id": "SYN:A001:obverse:L1:region",
            "coordinate_space": "normalized_original_image",
            "region_polygon": [
                [0.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [0.0, 1.0],
            ],
            "carrier_view": "seal_impression",
            "view_transform": {"mirrored": False, "rotation_degrees": 0},
            "rights": {
                "transcription_use": "permitted",
                "derived_observation_redistribution": "permitted",
                "evidence_id": "SYN:RIGHTS",
            },
        },
        "actor": {
            "actor_id": actor_id,
            "role": "transcriber",
            "independent_pass": True,
            "sign_inventory_access": True,
            "artifact_identity_blind": True,
            "expertise": ["palaeography"],
        },
        "input_reviews": [],
        "promotion_target": None,
        "reading_direction": {
            "value": "right_to_left",
            "confidence": 0.95,
            "evidence": ["edge_crowding"],
            "adjudication_reason": None,
        },
        "tokens": [
            token(
                f"{review_id}:T1",
                visual_index=0,
                reading_index=1,
                sign_id="S001",
                left=0.1,
            ),
            token(
                f"{review_id}:T2",
                visual_index=1,
                reading_index=0,
                sign_id="S002",
                left=0.6,
            ),
        ],
        "outcome": "complete",
        "disagreements": [],
        "limitations": [],
    }


def adjudication(
    inventory_sha256: str,
    reviews: list[tuple[dict, str]],
) -> dict:
    left = reviews[0][0]
    output_tokens = [
        token(
            "SYN:ADJ:T1",
            visual_index=0,
            reading_index=1,
            sign_id="S001",
            left=0.1,
        ),
        token(
            "SYN:ADJ:T2",
            visual_index=1,
            reading_index=0,
            sign_id="S002",
            left=0.6,
        ),
    ]
    for index, output in enumerate(output_tokens):
        output["input_token_refs"] = [
            {
                "review_id": review["review_id"],
                "token_id": review["tokens"][index]["token_id"],
            }
            for review, _digest in reviews
        ]
        output["adjudication_reason"] = "Both independent observations agree."

    return {
        "schema_version": "0.1.0",
        "record_state": "sign_transcription_review",
        "review_id": "SYN:ADJ",
        "assignment_id": "SYN:ASSIGN:ADJ",
        "review_stage": "adjudication",
        "subject_id": left["subject_id"],
        "scientific_scope": SCIENTIFIC_SCOPE,
        "visual_order_basis": "left_to_right_in_image",
        "sign_inventory": {
            "inventory_id": "SYN:INVENTORY",
            "edition": "fixture-v1",
            "sha256": inventory_sha256,
        },
        "source_commitment": copy.deepcopy(left["source_commitment"]),
        "actor": {
            "actor_id": "ACTOR:C",
            "role": "adjudicator",
            "independent_pass": False,
            "sign_inventory_access": True,
            "artifact_identity_blind": False,
            "expertise": ["epigraphy"],
        },
        "input_reviews": [
            {
                "review_id": review["review_id"],
                "review_sha256": digest,
                "assignment_id": review["assignment_id"],
                "actor_id": review["actor"]["actor_id"],
            }
            for review, digest in reviews
        ],
        "promotion_target": {
            "artifact_id": "SYN:A001",
            "side_id": "SYN:A001:obverse",
            "line_id": "SYN:A001:L1",
        },
        "reading_direction": {
            "value": "right_to_left",
            "confidence": 0.95,
            "evidence": ["edge_crowding"],
            "adjudication_reason": "Both independent direction judgments agree.",
        },
        "tokens": output_tokens,
        "outcome": "complete",
        "disagreements": [],
        "limitations": [],
    }


def evidence_bundle() -> tuple[dict, str, list[tuple[dict, str]], dict]:
    inventory = sign_inventory()
    inventory_sha256 = sha256_bytes(encode_json(inventory))
    left = independent_review(
        inventory_sha256,
        review_id="SYN:REVIEW:A",
        assignment_id="SYN:ASSIGN:A",
        actor_id="ACTOR:A",
    )
    right = independent_review(
        inventory_sha256,
        review_id="SYN:REVIEW:B",
        assignment_id="SYN:ASSIGN:B",
        actor_id="ACTOR:B",
    )
    reviews = [
        (left, sha256_bytes(encode_json(left))),
        (right, sha256_bytes(encode_json(right))),
    ]
    return inventory, inventory_sha256, reviews, adjudication(inventory_sha256, reviews)


def promotion_template() -> dict:
    artifact = valid_artifact()
    line = artifact["sides"][0]["lines"][0]
    line["reading_direction"] = "unknown"
    line["direction_confidence"] = 0.0
    line["tokens"] = [
        {
            "token_id": "SYN:A001:L1:UNRESOLVED",
            "sign_id": None,
            "visual_index": 0,
            "reading_index": None,
            "confidence": 0.0,
            "condition": "unreadable",
            "uncertainty": {
                "status": "unresolved",
                "alternatives": [],
                "notes": None,
            },
            "geometry": None,
            "source_record_ids": ["SYN:A001:source"],
        }
    ]
    return artifact


def verify_evidence_bundle(
    inventory: dict,
    reviews: list[tuple[dict, str]],
    final: dict,
) -> dict:
    return verify_transcription_evidence_bytes(
        encode_json(inventory),
        [encode_json(review) for review, _digest in reviews],
        encode_json(final),
    )


class TranscriptionReviewTests(unittest.TestCase):
    def test_valid_evidence_graph_promotes_to_baseline_sequence(self) -> None:
        inventory, inventory_sha256, reviews, final = evidence_bundle()
        self.assertEqual(
            [],
            validate_schema_instance(inventory, INVENTORY_SCHEMA),
        )
        for review, _digest in [*reviews, (final, "")]:
            self.assertEqual([], validate_schema_instance(review, REVIEW_SCHEMA))
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

        summary = compare_independent_transcriptions(reviews[0][0], reviews[1][0])
        self.assertFalse(summary["adjudication_required"])
        self.assertNotIn("S001", json.dumps(summary))
        self.assertNotIn("S002", json.dumps(summary))
        verification = verify_evidence_bundle(inventory, reviews, final)
        self.assertTrue(verification["input_digest_references_match_supplied_bytes"])
        self.assertFalse(verification["real_world_independence_verified"])

        promotion = promote_adjudicated_transcription(
            promotion_template(),
            inventory_bytes=encode_json(inventory),
            independent_review_bytes=[encode_json(review) for review, _digest in reviews],
            adjudication_bytes=encode_json(final),
            side_id="SYN:A001:obverse",
            line_id="SYN:A001:L1",
            release_scope="private_research",
        )
        artifact = promotion.artifact
        self.assertTrue(promotion.verification["input_digest_references_match_supplied_bytes"])
        self.assertFalse(has_errors(validate_artifact(artifact)))
        self.assertEqual([], extract_sequences([artifact]))
        self.assertEqual(
            ["SYN:001", "SYN:002"],
            [item["sign_id"] for item in artifact["sides"][0]["lines"][0]["tokens"]],
        )
        assurance = artifact["extensions"]["indusbench:transcription_bridge"]["assurances"]
        self.assertFalse(assurance["decipherment"])
        self.assertFalse(assurance["blind_evaluation"])
        self.assertFalse(assurance["inventory_source_document_bytes_rehashed"])
        self.assertFalse(assurance["inventory_graphic_crop_bytes_rehashed"])
        extension_text = json.dumps(
            artifact["extensions"]["indusbench:transcription_bridge"],
            sort_keys=True,
        )
        self.assertIn("SYN:ADJ", extension_text)
        self.assertIn(reviews[0][1], extension_text)
        self.assertIn(reviews[1][1], extension_text)
        self.assertIn("private_commitments", extension_text)

    def test_exact_inventory_and_review_commitments_are_required(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        tampered_inventory = copy.deepcopy(inventory)
        tampered_inventory["title"] = "Changed bytes and content"
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "inventory digest",
        ):
            validate_transcription_review(
                reviews[0][0],
                tampered_inventory,
                inventory_sha256=sha256_bytes(encode_json(tampered_inventory)),
            )

        final["input_reviews"][0]["review_sha256"] = f"sha256:{'f' * 64}"
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "exact independent reviews",
        ):
            verify_evidence_bundle(inventory, reviews, final)

    def test_independent_reviews_require_distinct_actors_and_assignments(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        right = reviews[1][0]
        right["actor"]["actor_id"] = reviews[0][0]["actor"]["actor_id"]
        with self.assertRaisesRegex(TranscriptionReviewError, "actors and assignments"):
            verify_evidence_bundle(inventory, reviews, final)

    def test_review_ids_are_unique_and_incomplete_inputs_cannot_be_promoted(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        reviews[1][0]["review_id"] = reviews[0][0]["review_id"]
        with self.assertRaisesRegex(TranscriptionReviewError, "review_id values"):
            verify_evidence_bundle(inventory, reviews, final)

    def test_agreement_gate_includes_segmentation_order_uncertainty_and_outcome(self) -> None:
        _inventory, _inventory_sha256, reviews, _final = evidence_bundle()
        left, right = reviews[0][0], reviews[1][0]
        right["tokens"][0]["segmentation"] = "compound_candidate"
        self.assertTrue(compare_independent_transcriptions(left, right)["adjudication_required"])

        _inventory, _inventory_sha256, reviews, _final = evidence_bundle()
        left, right = reviews[0][0], reviews[1][0]
        right["tokens"][0]["reading_index"] = 0
        right["tokens"][1]["reading_index"] = 1
        self.assertTrue(compare_independent_transcriptions(left, right)["adjudication_required"])

        _inventory, _inventory_sha256, reviews, _final = evidence_bundle()
        left, right = reviews[0][0], reviews[1][0]
        right["tokens"][0]["uncertainty"]["notes"] = "Visible abrasion."
        self.assertTrue(compare_independent_transcriptions(left, right)["adjudication_required"])

        left["outcome"] = "needs_more_evidence"
        right["outcome"] = "needs_more_evidence"
        summary = compare_independent_transcriptions(left, right)
        self.assertFalse(summary["both_outcomes_complete"])
        self.assertTrue(summary["adjudication_required"])

    def test_unimplemented_supersession_fields_are_rejected(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        reviews[0][0]["supersedes_review_id"] = "SYN:OLDER"
        reviews[0][0]["supersedes_review_sha256"] = f"sha256:{'1' * 64}"
        final["input_reviews"][0]["review_sha256"] = sha256_bytes(encode_json(reviews[0][0]))
        with self.assertRaisesRegex(TranscriptionReviewError, "schema invalid"):
            verify_transcription_evidence_bytes(
                encode_json(inventory),
                [encode_json(review) for review, _digest in reviews],
                encode_json(final),
            )

    def test_input_token_reuse_cannot_inflate_the_output_sequence(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        first = final["tokens"][0]
        second = final["tokens"][1]
        first["geometry"]["polygon"] = [
            [0.1, 0.2],
            [0.2, 0.2],
            [0.2, 0.8],
            [0.1, 0.8],
        ]
        first["visual_index"] = 0
        first["reading_index"] = 2
        inflated = copy.deepcopy(first)
        inflated["token_id"] = "SYN:ADJ:INFLATED"
        inflated["geometry"]["polygon"] = [
            [0.2, 0.2],
            [0.3, 0.2],
            [0.3, 0.8],
            [0.2, 0.8],
        ]
        inflated["visual_index"] = 1
        inflated["reading_index"] = 1
        second["visual_index"] = 2
        second["reading_index"] = 0
        final["tokens"] = [first, inflated, second]
        with self.assertRaisesRegex(TranscriptionReviewError, "uniquely used"):
            verify_evidence_bundle(inventory, reviews, final)

        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        reviews[0][0]["outcome"] = "needs_more_evidence"
        with self.assertRaisesRegex(TranscriptionReviewError, "must be complete"):
            verify_evidence_bundle(inventory, reviews, final)

    def test_adjudication_cannot_invent_sign_or_remote_geometry(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        final["tokens"][0]["selected_sign"] = sign_ref("S002")
        with self.assertRaisesRegex(TranscriptionReviewError, "introduced a sign"):
            verify_evidence_bundle(inventory, reviews, final)

        _inventory, _inventory_sha256, reviews, final = evidence_bundle()
        final["tokens"][0]["geometry"]["polygon"] = [
            [0.35, 0.1],
            [0.5, 0.1],
            [0.5, 0.15],
            [0.35, 0.15],
        ]
        with self.assertRaisesRegex(TranscriptionReviewError, "does not sufficiently overlap"):
            verify_evidence_bundle(inventory, reviews, final)

        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        final["tokens"][0]["geometry"]["polygon"] = [
            [0.1, 0.2],
            [0.10001, 0.2],
            [0.10001, 0.20001],
            [0.1, 0.20001],
        ]
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "do not sufficiently cover cited input geometry",
        ):
            verify_evidence_bundle(inventory, reviews, final)

        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        final["tokens"][0]["geometry"]["polygon"] = [
            [0.0, 0.0],
            [0.49, 0.0],
            [0.49, 1.0],
            [0.0, 1.0],
        ]
        final["tokens"][1]["geometry"]["polygon"] = [
            [0.51, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.51, 1.0],
        ]
        with self.assertRaisesRegex(TranscriptionReviewError, "does not sufficiently overlap"):
            verify_evidence_bundle(inventory, reviews, final)

    def test_tiny_identical_rectangles_use_relative_overlap(self) -> None:
        inventory, inventory_sha256, reviews, _final = evidence_bundle()
        tiny_rectangles = [
            [
                [0.1, 0.2],
                [0.10001, 0.2],
                [0.10001, 0.20001],
                [0.1, 0.20001],
            ],
            [
                [0.2, 0.2],
                [0.20001, 0.2],
                [0.20001, 0.20001],
                [0.2, 0.20001],
            ],
        ]
        for review, _digest in reviews:
            for index, rectangle in enumerate(tiny_rectangles):
                review["tokens"][index]["geometry"]["polygon"] = copy.deepcopy(rectangle)
        reviews = [(review, sha256_bytes(encode_json(review))) for review, _digest in reviews]
        final = adjudication(inventory_sha256, reviews)
        for index, rectangle in enumerate(tiny_rectangles):
            final["tokens"][index]["geometry"]["polygon"] = copy.deepcopy(rectangle)
        self.assertTrue(verify_evidence_bundle(inventory, reviews, final)["valid"])

    def test_reviewer_conflicts_require_exact_pairwise_commitments(self) -> None:
        inventory, inventory_sha256, reviews, _final = evidence_bundle()
        reviews[1][0]["tokens"][0]["selected_sign"] = sign_ref("S002")
        reviews = [(review, sha256_bytes(encode_json(review))) for review, _digest in reviews]
        final = adjudication(inventory_sha256, reviews)
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "disagreement commitments",
        ):
            verify_evidence_bundle(inventory, reviews, final)

        comparison = compare_independent_transcriptions(reviews[0][0], reviews[1][0])
        final["disagreements"] = [
            {
                "review_ids": sorted([reviews[0][0]["review_id"], reviews[1][0]["review_id"]]),
                "comparison_sha256": sha256_bytes(encode_json(comparison)),
                "resolution": "Adjudicator selected one attested visual identity.",
            }
        ]
        self.assertTrue(verify_evidence_bundle(inventory, reviews, final)["valid"])

    def test_adjudication_review_id_must_be_distinct(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        final["review_id"] = reviews[0][0]["review_id"]
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "must differ",
        ):
            verify_evidence_bundle(inventory, reviews, final)

    def test_interpretation_fields_and_degenerate_geometry_fail_closed(self) -> None:
        inventory, inventory_sha256, reviews, _final = evidence_bundle()
        review = reviews[0][0]
        review["translation"] = "not an observation"
        with self.assertRaisesRegex(TranscriptionReviewError, "interpretive field"):
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

        _inventory, _inventory_sha256, reviews, _final = evidence_bundle()
        review = reviews[0][0]
        review["tokens"][0]["geometry"]["polygon"] = [
            [0.1, 0.1],
            [0.2, 0.2],
            [0.3, 0.3],
        ]
        with self.assertRaisesRegex(TranscriptionReviewError, "four-corner"):
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

        _inventory, _inventory_sha256, reviews, _final = evidence_bundle()
        review = reviews[0][0]
        review["tokens"][0]["geometry"]["polygon"] = [
            [0.1, 0.1],
            [0.3, 0.3],
            [0.1, 0.3],
            [0.3, 0.1],
        ]
        with self.assertRaisesRegex(TranscriptionReviewError, "perimeter"):
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

    def test_non_finite_confidence_fails_closed(self) -> None:
        inventory, inventory_sha256, reviews, _final = evidence_bundle()
        review = reviews[0][0]
        review["tokens"][0]["confidence"] = float("nan")
        with self.assertRaisesRegex(TranscriptionReviewError, "must be finite"):
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

        _inventory, _inventory_sha256, reviews, _final = evidence_bundle()
        review = reviews[0][0]
        review["reading_direction"]["confidence"] = float("inf")
        with self.assertRaisesRegex(TranscriptionReviewError, "must be finite"):
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

    def test_populated_target_and_target_mismatch_cannot_be_replaced(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        promotion_args = {
            "inventory_bytes": encode_json(inventory),
            "independent_review_bytes": [encode_json(review) for review, _digest in reviews],
            "adjudication_bytes": encode_json(final),
            "side_id": "SYN:A001:obverse",
            "line_id": "SYN:A001:L1",
            "release_scope": "private_research",
        }
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "promotion scaffold",
        ):
            promote_adjudicated_transcription(
                valid_artifact(),
                **promotion_args,
            )

        noted = promotion_template()
        noted["sides"][0]["lines"][0]["tokens"][0]["uncertainty"] = {
            "status": "unresolved",
            "alternatives": [{"sign_id": "SYN:999", "probability": 0.1}],
            "notes": "Existing human observation.",
        }
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "contains observations",
        ):
            promote_adjudicated_transcription(
                noted,
                **promotion_args,
            )

        mismatched = promotion_template()
        mismatched["artifact_id"] = "SYN:OTHER"
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "committed artifact target",
        ):
            promote_adjudicated_transcription(
                mismatched,
                **promotion_args,
            )

    def test_artifact_and_image_rights_cannot_be_overridden_by_a_review(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        promotion_args = {
            "inventory_bytes": encode_json(inventory),
            "independent_review_bytes": [encode_json(review) for review, _digest in reviews],
            "adjudication_bytes": encode_json(final),
            "side_id": "SYN:A001:obverse",
            "line_id": "SYN:A001:L1",
            "release_scope": "private_research",
        }
        restricted_artifact = promotion_template()
        restricted_artifact["rights"].update(
            {
                "status": "restricted",
                "license_id": None,
                "license_uri": None,
                "redistribution": False,
                "derivatives": False,
                "commercial_use": False,
            }
        )
        with self.assertRaisesRegex(TranscriptionReviewError, "artifact rights"):
            promote_adjudicated_transcription(
                restricted_artifact,
                **promotion_args,
            )

        restricted_image = promotion_template()
        restricted_image["images"][0]["rights"].update(
            {
                "status": "restricted",
                "license_id": None,
                "license_uri": None,
                "redistribution": False,
                "derivatives": False,
                "commercial_use": False,
            }
        )
        with self.assertRaisesRegex(TranscriptionReviewError, "source image rights"):
            promote_adjudicated_transcription(
                restricted_image,
                **promotion_args,
            )

    def test_existing_transcription_receipt_cannot_be_overwritten(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        template = promotion_template()
        template.setdefault("extensions", {})["indusbench:transcription_bridge"] = {
            "existing": "receipt"
        }
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "existing promotion receipt",
        ):
            promote_adjudicated_transcription(
                template,
                inventory_bytes=encode_json(inventory),
                independent_review_bytes=[encode_json(review) for review, _digest in reviews],
                adjudication_bytes=encode_json(final),
                side_id="SYN:A001:obverse",
                line_id="SYN:A001:L1",
                release_scope="private_research",
            )

    def test_promotion_rehashes_exact_review_bytes_internally(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        tampered_review = copy.deepcopy(reviews[0][0])
        tampered_review["limitations"] = ["Changed after adjudication sealing."]
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "exact independent reviews",
        ):
            promote_adjudicated_transcription(
                promotion_template(),
                inventory_bytes=encode_json(inventory),
                independent_review_bytes=[
                    encode_json(tampered_review),
                    encode_json(reviews[1][0]),
                ],
                adjudication_bytes=encode_json(final),
                side_id="SYN:A001:obverse",
                line_id="SYN:A001:L1",
                release_scope="private_research",
            )

    def test_unknown_direction_is_preserved_but_public_export_is_blocked(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        final["reading_direction"] = {
            "value": "unknown",
            "confidence": 0.0,
            "evidence": ["unknown"],
            "adjudication_reason": "No direction can be resolved.",
        }
        for item in final["tokens"]:
            item["reading_index"] = None
        promotion = promote_adjudicated_transcription(
            promotion_template(),
            inventory_bytes=encode_json(inventory),
            independent_review_bytes=[encode_json(review) for review, _digest in reviews],
            adjudication_bytes=encode_json(final),
            side_id="SYN:A001:obverse",
            line_id="SYN:A001:L1",
            release_scope="private_research",
        )
        promoted_line = promotion.artifact["sides"][0]["lines"][0]
        self.assertEqual("unknown", promoted_line["reading_direction"])
        self.assertTrue(all(item["reading_index"] is None for item in promoted_line["tokens"]))
        self.assertFalse(
            promotion.artifact["extensions"]["indusbench:transcription_bridge"][
                "evaluation_admissible"
            ]
        )

        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        with self.assertRaisesRegex(TranscriptionReviewError, "public transcription export"):
            promote_adjudicated_transcription(
                promotion_template(),
                inventory_bytes=encode_json(inventory),
                independent_review_bytes=[encode_json(review) for review, _digest in reviews],
                adjudication_bytes=encode_json(final),
                side_id="SYN:A001:obverse",
                line_id="SYN:A001:L1",
                release_scope="public_release",
            )

    def test_nonidentity_view_transform_is_rejected_in_v0_1(self) -> None:
        inventory, inventory_sha256, reviews, _final = evidence_bundle()
        review = reviews[0][0]
        review["source_commitment"]["view_transform"] = {
            "mirrored": True,
            "rotation_degrees": 0,
        }
        with self.assertRaisesRegex(TranscriptionReviewError, "unmirrored"):
            validate_transcription_review(
                review,
                inventory,
                inventory_sha256=inventory_sha256,
            )

    def test_visual_indices_must_follow_left_to_right_geometry(self) -> None:
        inventory, _inventory_sha256, reviews, final = evidence_bundle()
        for review, _digest in reviews:
            first_polygon = copy.deepcopy(review["tokens"][0]["geometry"]["polygon"])
            review["tokens"][0]["geometry"]["polygon"] = copy.deepcopy(
                review["tokens"][1]["geometry"]["polygon"]
            )
            review["tokens"][1]["geometry"]["polygon"] = first_polygon
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "strictly increasing horizontal centers",
        ):
            verify_evidence_bundle(inventory, reviews, final)

    def test_cli_audits_promotes_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, final = evidence_bundle()
            paths = {
                "inventory": temporary / "inventory.json",
                "left": temporary / "left.json",
                "right": temporary / "right.json",
                "final": temporary / "adjudication.json",
                "template": temporary / "template.json",
                "output": temporary / "artifact.json",
                "audit": temporary / "agreement.json",
            }
            write_json(paths["inventory"], inventory)
            write_json(paths["left"], reviews[0][0])
            write_json(paths["right"], reviews[1][0])
            write_json(paths["final"], final)
            write_json(paths["template"], promotion_template())

            result, stdout, stderr = run_cli(
                [
                    "audit-transcription-agreement",
                    str(paths["inventory"]),
                    str(paths["left"]),
                    str(paths["right"]),
                    "--private-report",
                    str(paths["audit"]),
                ]
            )
            self.assertEqual(0, result, stderr)
            audit = json.loads(stdout)
            self.assertFalse(audit["counts_disclosed"])
            self.assertFalse(audit["agreement_result_disclosed"])
            self.assertTrue(audit["private_report_written"])
            private_audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
            self.assertFalse(private_audit["adjudication_required"])
            self.assertEqual(0o600, paths["audit"].stat().st_mode & 0o777)
            self.assertNotIn("S001", stdout)
            self.assertNotIn("S002", stdout)

            command = [
                "promote-transcription",
                str(paths["inventory"]),
                str(paths["template"]),
                str(paths["final"]),
                str(paths["output"]),
                "--review",
                str(paths["left"]),
                "--review",
                str(paths["right"]),
                "--side-id",
                "SYN:A001:obverse",
                "--line-id",
                "SYN:A001:L1",
                "--release-scope",
                "private_research",
            ]
            result, stdout, stderr = run_cli(command)
            self.assertEqual(0, result, stderr)
            self.assertFalse(json.loads(stdout)["evaluation_admissible"])
            self.assertFalse(json.loads(stdout)["private_evidence_disclosed"])
            self.assertEqual(0o600, paths["output"].stat().st_mode & 0o777)
            output_before = paths["output"].read_bytes()
            artifact = json.loads(output_before)
            self.assertFalse(has_errors(validate_artifact(artifact)))

            result, _stdout, stderr = run_cli(command)
            self.assertEqual(1, result)
            self.assertIn("could not be created safely", stderr)
            self.assertNotIn(paths["output"].name, stderr)
            self.assertNotIn(str(paths["output"]), stderr)
            self.assertEqual(output_before, paths["output"].read_bytes())

    def test_cli_requires_a_physical_owner_only_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, final = evidence_bundle()
            inventory_path = temporary / "inventory.json"
            left_path = temporary / "left.json"
            right_path = temporary / "right.json"
            final_path = temporary / "adjudication.json"
            template_path = temporary / "template.json"
            write_json(inventory_path, inventory)
            write_json(left_path, reviews[0][0])
            write_json(right_path, reviews[1][0])
            write_json(final_path, final)
            write_json(template_path, promotion_template())

            def command(output: Path) -> list[str]:
                return [
                    "promote-transcription",
                    str(inventory_path),
                    str(template_path),
                    str(final_path),
                    str(output),
                    "--review",
                    str(left_path),
                    "--review",
                    str(right_path),
                    "--side-id",
                    "SYN:A001:obverse",
                    "--line-id",
                    "SYN:A001:L1",
                ]

            broad_parent = temporary / "broad"
            broad_parent.mkdir(mode=0o755)
            broad_parent.chmod(0o755)
            result, _stdout, stderr = run_cli(command(broad_parent / "artifact.json"))
            self.assertEqual(1, result)
            self.assertIn("could not be created safely", stderr)

            result, _stdout, stderr = run_cli(command(temporary / "missing" / "artifact.json"))
            self.assertEqual(1, result)
            self.assertIn("could not be created safely", stderr)

            physical_parent = temporary / "physical"
            physical_parent.mkdir(mode=0o700)
            physical_parent.chmod(0o700)
            linked_parent = temporary / "linked"
            linked_parent.symlink_to(physical_parent, target_is_directory=True)
            result, _stdout, stderr = run_cli(command(linked_parent / "artifact.json"))
            self.assertEqual(1, result)
            self.assertIn("could not be created safely", stderr)

            unsafe_ancestor = temporary / "unsafe-ancestor"
            unsafe_ancestor.mkdir(mode=0o777)
            unsafe_ancestor.chmod(0o777)
            nested_private = unsafe_ancestor / "private"
            nested_private.mkdir(mode=0o700)
            nested_private.chmod(0o700)
            result, _stdout, stderr = run_cli(command(nested_private / "artifact.json"))
            self.assertEqual(1, result)
            self.assertIn("could not be created safely", stderr)

    def test_cli_private_output_does_not_follow_a_dangling_final_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, final = evidence_bundle()
            inventory_path = temporary / "inventory.json"
            left_path = temporary / "left.json"
            right_path = temporary / "right.json"
            final_path = temporary / "adjudication.json"
            template_path = temporary / "template.json"
            outside_target = temporary.parent / (
                f"{temporary.name}-PRIVATE-TRANSCRIPTION-ESCAPE.json"
            )
            output_path = temporary / "PRIVATE-SUBJECT-SECRET.json"
            write_json(inventory_path, inventory)
            write_json(left_path, reviews[0][0])
            write_json(right_path, reviews[1][0])
            write_json(final_path, final)
            write_json(template_path, promotion_template())
            output_path.symlink_to(outside_target)

            result, _stdout, stderr = run_cli(
                [
                    "promote-transcription",
                    str(inventory_path),
                    str(template_path),
                    str(final_path),
                    str(output_path),
                    "--review",
                    str(left_path),
                    "--review",
                    str(right_path),
                    "--side-id",
                    "SYN:A001:obverse",
                    "--line-id",
                    "SYN:A001:L1",
                ]
            )
            self.assertEqual(1, result)
            self.assertFalse(outside_target.exists())
            self.assertNotIn(output_path.name, stderr)
            self.assertNotIn(str(output_path), stderr)

    def test_cli_schema_errors_do_not_echo_private_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, _final = evidence_bundle()
            inventory_path = temporary / "inventory.json"
            left_path = temporary / "left.json"
            right_path = temporary / "right.json"
            sentinel = "PRIVATE-ITEM-SECRET-42"
            reviews[0][0]["outcome"] = sentinel
            write_json(inventory_path, inventory)
            write_json(left_path, reviews[0][0])
            write_json(right_path, reviews[1][0])

            result, _stdout, stderr = run_cli(
                [
                    "audit-transcription-agreement",
                    str(inventory_path),
                    str(left_path),
                    str(right_path),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("schema invalid", stderr)
            self.assertNotIn(sentinel, stderr)

    def test_cli_reports_durability_unknown_without_claiming_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, final = evidence_bundle()
            paths = {
                "inventory": temporary / "inventory.json",
                "left": temporary / "left.json",
                "right": temporary / "right.json",
                "final": temporary / "adjudication.json",
                "template": temporary / "template.json",
                "audit": temporary / "audit.json",
                "output": temporary / "artifact.json",
            }
            write_json(paths["inventory"], inventory)
            write_json(paths["left"], reviews[0][0])
            write_json(paths["right"], reviews[1][0])
            write_json(paths["final"], final)
            write_json(paths["template"], promotion_template())
            real_rename = cli_module._rename_private_name_no_replace

            def rename_then_report_unknown(
                parent_descriptor: int,
                source_name: str,
                destination_name: str,
            ) -> None:
                real_rename(parent_descriptor, source_name, destination_name)
                raise cli_module._CommittedDurabilityUnknown(
                    errno.ENOTSUP,
                    "synthetic durability failure",
                    "redacted",
                    content_verified=True,
                )

            with patch(
                "indusbench.cli._rename_private_name_no_replace",
                side_effect=rename_then_report_unknown,
            ):
                result, stdout, stderr = run_cli(
                    [
                        "audit-transcription-agreement",
                        str(paths["inventory"]),
                        str(paths["left"]),
                        str(paths["right"]),
                        "--private-report",
                        str(paths["audit"]),
                    ]
                )
            self.assertEqual(1, result, stderr)
            audit_payload = json.loads(stdout)
            self.assertFalse(audit_payload["private_report_written"])
            self.assertTrue(audit_payload["output_content_verified"])
            self.assertFalse(audit_payload["durability_confirmed"])
            self.assertTrue(paths["audit"].is_file())

            with patch(
                "indusbench.cli._rename_private_name_no_replace",
                side_effect=rename_then_report_unknown,
            ):
                result, stdout, stderr = run_cli(
                    [
                        "promote-transcription",
                        str(paths["inventory"]),
                        str(paths["template"]),
                        str(paths["final"]),
                        str(paths["output"]),
                        "--review",
                        str(paths["left"]),
                        "--review",
                        str(paths["right"]),
                        "--side-id",
                        "SYN:A001:obverse",
                        "--line-id",
                        "SYN:A001:L1",
                    ]
                )
            self.assertEqual(1, result, stderr)
            promotion_payload = json.loads(stdout)
            self.assertFalse(promotion_payload["written"])
            self.assertTrue(promotion_payload["output_content_verified"])
            self.assertFalse(promotion_payload["durability_confirmed"])
            self.assertTrue(paths["output"].is_file())

    def test_cli_detects_requested_parent_replacement_after_pinning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            private_parent = temporary / "private"
            private_parent.mkdir(mode=0o700)
            private_parent.chmod(0o700)
            moved_parent = temporary / "private-pinned"
            inventory, _inventory_sha256, reviews, final = evidence_bundle()
            paths = {
                "inventory": temporary / "inventory.json",
                "left": temporary / "left.json",
                "right": temporary / "right.json",
                "final": temporary / "adjudication.json",
                "template": temporary / "template.json",
                "output": private_parent / "artifact.json",
            }
            write_json(paths["inventory"], inventory)
            write_json(paths["left"], reviews[0][0])
            write_json(paths["right"], reviews[1][0])
            write_json(paths["final"], final)
            write_json(paths["template"], promotion_template())
            real_rename = cli_module._rename_private_name_no_replace

            def replace_parent_then_rename(
                parent_descriptor: int,
                source_name: str,
                destination_name: str,
            ) -> None:
                os.rename(private_parent, moved_parent)
                private_parent.mkdir(mode=0o700)
                private_parent.chmod(0o700)
                real_rename(parent_descriptor, source_name, destination_name)

            with patch(
                "indusbench.cli._rename_private_name_no_replace",
                side_effect=replace_parent_then_rename,
            ):
                result, stdout, stderr = run_cli(
                    [
                        "promote-transcription",
                        str(paths["inventory"]),
                        str(paths["template"]),
                        str(paths["final"]),
                        str(paths["output"]),
                        "--review",
                        str(paths["left"]),
                        "--review",
                        str(paths["right"]),
                        "--side-id",
                        "SYN:A001:obverse",
                        "--line-id",
                        "SYN:A001:L1",
                    ]
                )
            self.assertEqual(1, result, stderr)
            payload = json.loads(stdout)
            self.assertFalse(payload["written"])
            self.assertFalse(payload["durability_confirmed"])
            self.assertFalse(paths["output"].exists())
            self.assertTrue((moved_parent / paths["output"].name).is_file())

    def test_cli_rejects_non_finite_json_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, _final = evidence_bundle()
            inventory_path = temporary / "inventory.json"
            left_path = temporary / "left.json"
            right_path = temporary / "right.json"
            write_json(inventory_path, inventory)
            left_path.write_text(
                json.dumps(reviews[0][0], allow_nan=True).replace(
                    '"confidence": 1.0',
                    '"confidence": NaN',
                    1,
                ),
                encoding="utf-8",
            )
            write_json(right_path, reviews[1][0])

            result, _stdout, stderr = run_cli(
                [
                    "audit-transcription-agreement",
                    str(inventory_path),
                    str(left_path),
                    str(right_path),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("safe finite JSON object", stderr)

    def test_cli_rejects_symbolic_link_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            inventory, _inventory_sha256, reviews, _final = evidence_bundle()
            inventory_path = temporary / "inventory.json"
            inventory_link = temporary / "inventory-link.json"
            left_path = temporary / "left.json"
            right_path = temporary / "right.json"
            write_json(inventory_path, inventory)
            inventory_link.symlink_to(inventory_path)
            write_json(left_path, reviews[0][0])
            write_json(right_path, reviews[1][0])

            result, _stdout, stderr = run_cli(
                [
                    "audit-transcription-agreement",
                    str(inventory_link),
                    str(left_path),
                    str(right_path),
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("safe finite JSON object", stderr)

    def test_deprecated_signs_are_not_valid_new_transcription_targets(self) -> None:
        inventory, inventory_sha256, reviews, _final = evidence_bundle()
        inventory["signs"][0]["deprecated"] = True
        inventory["signs"][0]["superseded_by"] = "S002"
        inventory_sha256 = sha256_bytes(encode_json(inventory))
        reviews[0][0]["sign_inventory"]["sha256"] = inventory_sha256
        validate_sign_inventory(inventory)
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "outside the fixed inventory",
        ):
            validate_transcription_review(
                reviews[0][0],
                inventory,
                inventory_sha256=inventory_sha256,
            )

    def test_identifier_evidence_must_come_from_the_same_document(self) -> None:
        inventory = sign_inventory()
        inventory["source_documents"].append(
            {
                **copy.deepcopy(inventory["source_documents"][0]),
                "document_id": "SYN:OTHER:DOC",
            }
        )
        inventory["signs"][0]["published_identifiers"][0]["document_id"] = "SYN:OTHER:DOC"
        with self.assertRaisesRegex(
            TranscriptionReviewError,
            "different documents",
        ):
            validate_sign_inventory(inventory)


if __name__ == "__main__":
    unittest.main()
