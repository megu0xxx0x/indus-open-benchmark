from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from indusbench.manifest import sha256_json
from indusbench.museum_review import (
    REVIEW_SCOPE,
    MuseumReviewError,
    build_blind_review_materials,
    validate_review_submission,
    validate_subject_semantics,
)
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
CHECKSUM_A = "sha256:" + "a" * 64
CHECKSUM_B = "sha256:" + "b" * 64
CHECKSUM_C = "sha256:" + "c" * 64


def synthetic_intake() -> dict:
    return {
        "intake_id": "museum:synthetic:object-1",
        "source_id": "synthetic-open-access",
        "institution": {
            "institution_id": "synthetic-museum",
            "name": "Synthetic Museum",
        },
        "official_record": {
            "object_id": "object-1",
            "accession_number": "SYN.1",
            "title_as_catalogued": "Synthetic seal and impression",
            "record_uri": "https://example.org/objects/object-1",
        },
        "item_rights": {
            "status": "public_domain",
            "license_id": "CC0-1.0",
            "rights_holder": "Synthetic Museum",
            "redistribution": True,
            "derivatives": True,
            "commercial_use": True,
        },
        "media": [
            {
                "media_id": "synthetic:object-1:view-0:print",
                "provider_view_index": 0,
                "provider_derivative": "print",
                "view_role": "provider_primary",
                "source_uri": "https://example.org/media/print.jpg",
                "download": {
                    "status": "downloaded",
                    "sha256": CHECKSUM_A,
                    "bytes": 10,
                    "content_type": "image/jpeg",
                    "local_relative_path": "images/object-1/print.jpg",
                    "downloaded_at": "2026-07-26T08:00:00Z",
                },
            },
            {
                "media_id": "synthetic:object-1:view-0:full",
                "provider_view_index": 0,
                "provider_derivative": "full",
                "view_role": "provider_primary",
                "source_uri": "https://example.org/media/full.tif",
                "download": {
                    "status": "downloaded",
                    "sha256": CHECKSUM_B,
                    "bytes": 20,
                    "content_type": "image/tiff",
                    "local_relative_path": "images/object-1/full.tif",
                    "downloaded_at": "2026-07-26T08:00:00Z",
                },
            },
        ],
    }


def blind_subject() -> tuple[list[dict], dict, list[dict]]:
    record = synthetic_intake()
    return build_blind_review_materials(
        [record],
        [
            {
                "intake_id": record["intake_id"],
                "record_sha256": CHECKSUM_C,
            }
        ],
        packet_id="packet:synthetic",
        pseudonym_key=b"k" * 32,
        source_bundle_manifest_sha256="sha256:" + "d" * 64,
        source_bundle_version="0.2.0",
        source_bundle_created_at="2026-07-26T08:00:00Z",
        source_bundle_externally_anchored=False,
    )


def valid_review(subject: dict) -> dict:
    images = [image for group in subject["view_groups"] for image in group["evidence_images"]]
    observations = [
        {
            "entity_id": f"entity:{index}",
            "image_id": image["image_id"],
            "image_sha256": image["sha256"],
            "depicted_carrier": "unknown",
            "physical_surface": "unknown",
            "inscription_regions": [
                {
                    "region_id": f"region:{index}",
                    "image_id": image["image_id"],
                    "image_sha256": image["sha256"],
                    "coordinate_space": "normalized_original_image",
                    "presence": "possible",
                    "polygon": [
                        [0.1, 0.1],
                        [0.9, 0.1],
                        [0.5, 0.8],
                    ],
                    "uncertainty": {
                        "status": "uncertain",
                        "confidence": None,
                        "basis_codes": ["low_contrast"],
                        "notes": "Synthetic observation only.",
                    },
                }
            ],
            "damage_or_occlusion": [],
            "notes": "No carrier identity asserted.",
        }
        for index, image in enumerate(images, start=1)
    ]
    return {
        "schema_version": "0.2.0",
        "record_state": "human_observation_review",
        "review_id": "review:synthetic:one",
        "packet_id": subject["packet_id"],
        "assignment_id": "assignment:synthetic:one",
        "review_stage": "independent",
        "subject_id": subject["subject_id"],
        "scientific_scope": REVIEW_SCOPE,
        "source_commitment": {
            "reviewer_manifest_sha256": "sha256:" + "e" * 64,
            "subject_record_sha256": f"sha256:{sha256_json(subject)}",
            "evidence_sha256s": sorted(item["sha256"] for item in images),
        },
        "actor": {
            "actor_id": "reviewer:pseudonymous-one",
            "role": "visual_reviewer",
            "expertise": ["visual"],
            "reviewed_at": "2026-07-26T10:00:00Z",
            "independent_pass": True,
            "conflict_status": "none_declared",
            "prior_familiarity": "unknown",
            "viewing_methods": ["exact_image", "zoom"],
        },
        "input_reviews": [],
        "entity_observations": observations,
        "relationship_assertions": [],
        "catalog_crosswalk_assertions": [],
        "disagreements": [],
        "outcome": "complete",
        "limitations": ["Synthetic fixture; no real inscription."],
        "supersedes_review_id": None,
        "supersedes_review_sha256": None,
    }


class MuseumReviewTests(unittest.TestCase):
    def test_checked_in_synthetic_review_is_valid(self) -> None:
        fixture = ROOT / "examples/synthetic_museum_review.jsonl"
        rows = [
            json.loads(line)
            for line in fixture.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(1, len(rows))
        validate_review_submission(rows[0])
        issues = validate_schema_instance(
            rows[0],
            ROOT / "schemas/museum-review.schema.json",
        )
        self.assertEqual([], [issue.as_dict() for issue in issues])

    def test_blind_subject_separates_identity_and_validates_schema(self) -> None:
        subjects, custody, copy_specs = blind_subject()
        self.assertEqual(1, len(subjects))
        subject = subjects[0]
        validate_subject_semantics(subject)
        issues = validate_schema_instance(
            subject,
            ROOT / "schemas/museum-review-subject.schema.json",
        )
        self.assertEqual([], [issue.as_dict() for issue in issues])

        serialized_subject = json.dumps(subject, ensure_ascii=False)
        for forbidden in (
            "Synthetic Museum",
            "SYN.1",
            "museum:synthetic:object-1",
            "https://example.org/",
            "synthetic:object-1:view-0:print",
            "images/object-1/print.jpg",
        ):
            self.assertNotIn(forbidden, serialized_subject)
        self.assertEqual(
            "museum:synthetic:object-1",
            custody["subjects"][0]["intake_id"],
        )
        self.assertEqual(1, len(subject["view_groups"]))
        self.assertEqual(2, len(subject["view_groups"][0]["evidence_images"]))
        self.assertEqual(2, len(copy_specs))
        self.assertTrue(
            all(
                specification["review_relative_path"].startswith("evidence/")
                for specification in copy_specs
            )
        )

    def test_blind_packet_rejects_missing_media_and_identity_fields(self) -> None:
        record = synthetic_intake()
        record["media"][0]["download"] = {
            "status": "not_downloaded",
            "sha256": None,
            "bytes": None,
            "content_type": None,
            "local_relative_path": None,
            "downloaded_at": None,
        }
        with self.assertRaisesRegex(MuseumReviewError, "requires every image"):
            build_blind_review_materials(
                [record],
                [{"intake_id": record["intake_id"], "record_sha256": CHECKSUM_C}],
                packet_id="packet:synthetic",
                pseudonym_key=b"k" * 32,
                source_bundle_manifest_sha256="sha256:" + "d" * 64,
                source_bundle_version="0.2.0",
                source_bundle_created_at="2026-07-26T08:00:00Z",
                source_bundle_externally_anchored=False,
            )

        subject = blind_subject()[0][0]
        subject["institution"] = "must not leak"
        with self.assertRaisesRegex(MuseumReviewError, "forbidden fields"):
            validate_subject_semantics(subject)

    def test_independent_review_is_schema_valid_and_bound_to_subject(self) -> None:
        subject = blind_subject()[0][0]
        review = valid_review(subject)
        validate_review_submission(review, subject=subject)
        issues = validate_schema_instance(
            review,
            ROOT / "schemas/museum-review.schema.json",
        )
        self.assertEqual([], [issue.as_dict() for issue in issues])

    def test_forbidden_interpretation_fields_are_rejected_at_any_depth(self) -> None:
        subject = blind_subject()[0][0]
        for field in (
            "sign_id",
            "tokens",
            "reading_direction",
            "transcription",
            "phonetic_value",
            "language_assignment",
            "gloss",
            "translation",
        ):
            with self.subTest(field=field):
                review = valid_review(subject)
                review["entity_observations"][0]["nested"] = {field: "forbidden"}
                with self.assertRaisesRegex(MuseumReviewError, "forbidden fields"):
                    validate_review_submission(review, subject=subject)

    def test_roi_and_source_commitments_fail_closed(self) -> None:
        subject = blind_subject()[0][0]
        degenerate = valid_review(subject)
        degenerate["entity_observations"][0]["inscription_regions"][0]["polygon"] = [
            [0.1, 0.1],
            [0.2, 0.2],
            [0.3, 0.3],
        ]
        with self.assertRaisesRegex(MuseumReviewError, "nonzero area"):
            validate_review_submission(degenerate, subject=subject)

        wrong_hash = valid_review(subject)
        wrong_hash["source_commitment"]["subject_record_sha256"] = CHECKSUM_A
        with self.assertRaisesRegex(MuseumReviewError, "commitment hash mismatch"):
            validate_review_submission(wrong_hash, subject=subject)

        wrong_image = valid_review(subject)
        wrong_image["entity_observations"][0]["image_sha256"] = CHECKSUM_C
        wrong_image["entity_observations"][0]["inscription_regions"][0]["image_sha256"] = CHECKSUM_C
        with self.assertRaisesRegex(MuseumReviewError, "image hash mismatch"):
            validate_review_submission(wrong_image, subject=subject)

    def test_independent_and_exact_crosswalk_gates(self) -> None:
        subject = blind_subject()[0][0]
        prior_review = valid_review(subject)
        prior_review["input_reviews"] = [CHECKSUM_A]
        with self.assertRaisesRegex(MuseumReviewError, "cannot inspect prior"):
            validate_review_submission(prior_review, subject=subject)

        visual_crosswalk = valid_review(subject)
        visual_crosswalk["catalog_crosswalk_assertions"] = [
            {
                "assertion_id": "crosswalk:one",
                "target_source_id": "synthetic-catalog",
                "target_edition": "2026",
                "target_record_id": "SYN-1",
                "relationship": "possible_match",
                "strength": "possible",
                "evidence": ["Synthetic candidate."],
                "counterevidence": [],
                "counterevidence_checked": False,
            }
        ]
        with self.assertRaisesRegex(MuseumReviewError, "visual reviewers"):
            validate_review_submission(visual_crosswalk, subject=subject)

        exact_independent = copy.deepcopy(visual_crosswalk)
        exact_independent["actor"]["role"] = "collection_specialist"
        exact_independent["actor"]["expertise"] = ["collections"]
        exact_independent["catalog_crosswalk_assertions"][0]["strength"] = "exact"
        exact_independent["catalog_crosswalk_assertions"][0]["counterevidence_checked"] = True
        with self.assertRaisesRegex(MuseumReviewError, "only be adopted"):
            validate_review_submission(exact_independent, subject=subject)

        adjudication = copy.deepcopy(exact_independent)
        adjudication["review_id"] = "review:synthetic:adjudication"
        adjudication["review_stage"] = "adjudication"
        adjudication["actor"]["role"] = "adjudicator"
        adjudication["actor"]["independent_pass"] = False
        adjudication["input_reviews"] = [CHECKSUM_A, CHECKSUM_B]
        validate_review_submission(adjudication, subject=subject)
        issues = validate_schema_instance(
            adjudication,
            ROOT / "schemas/museum-review.schema.json",
        )
        self.assertEqual([], [issue.as_dict() for issue in issues])


if __name__ == "__main__":
    unittest.main()
