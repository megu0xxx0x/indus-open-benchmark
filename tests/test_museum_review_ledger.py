from __future__ import annotations

import copy
import math
import unittest
from pathlib import Path

from indusbench.museum_review_ledger import (
    audit_review_chain,
    build_ledger_manifest,
    canonical_review_bytes,
    review_digest,
    review_relative_path,
)
from indusbench.schema_validation import validate_schema_instance
from tests.test_museum_review import blind_subject, valid_review

ROOT = Path(__file__).resolve().parents[1]
REVIEWER_MANIFEST_SHA256 = "sha256:" + "e" * 64


def second_review(subject: dict) -> dict:
    review = valid_review(subject)
    review["review_id"] = "review:synthetic:two"
    review["assignment_id"] = "assignment:synthetic:two"
    review["actor"]["actor_id"] = "reviewer:pseudonymous-two"
    review["actor"]["reviewed_at"] = "2026-07-26T10:05:00Z"
    return review


def adjudication(subject: dict, inputs: list[str]) -> dict:
    review = valid_review(subject)
    review["review_id"] = "review:synthetic:adjudication"
    review["assignment_id"] = "assignment:synthetic:adjudication"
    review["review_stage"] = "adjudication"
    review["actor"] = {
        "actor_id": "reviewer:pseudonymous-adjudicator",
        "role": "adjudicator",
        "expertise": ["collections"],
        "reviewed_at": "2026-07-26T11:00:00Z",
        "independent_pass": False,
        "conflict_status": "none_declared",
        "prior_familiarity": "unknown",
        "viewing_methods": ["exact_image", "sealed_inputs"],
    }
    review["input_reviews"] = inputs
    return review


def audit(subject: dict, reviews: list[dict]) -> dict:
    sealed = {review_digest(review): review for review in reviews}
    return audit_review_chain(
        sealed,
        [subject],
        packet_id=subject["packet_id"],
        reviewer_manifest_sha256=REVIEWER_MANIFEST_SHA256,
    )


def probable_crosswalk(assertion_id: str) -> dict:
    return {
        "assertion_id": assertion_id,
        "target_source_id": "catalog:synthetic",
        "target_edition": "2026",
        "target_record_id": "SYN-1",
        "relationship": "same_physical_artifact",
        "strength": "probable",
        "evidence": ["Matching accession geometry and custody evidence."],
        "counterevidence": [],
        "counterevidence_checked": True,
    }


class MuseumReviewLedgerTests(unittest.TestCase):
    def test_manifest_canonical_digest_and_stage_path(self) -> None:
        subject = blind_subject()[0][0]
        review = valid_review(subject)
        digest = review_digest(review)
        self.assertEqual(canonical_review_bytes(review), canonical_review_bytes(review))
        self.assertEqual(
            f"submissions/sha256-{digest.removeprefix('sha256:')}.json",
            review_relative_path(review, digest),
        )

        manifest = build_ledger_manifest(
            packet_id=subject["packet_id"],
            created_at="2026-07-26T12:00:00Z",
            packet_manifest_sha256="sha256:" + "d" * 64,
            reviewer_manifest_sha256=REVIEWER_MANIFEST_SHA256,
        )
        issues = validate_schema_instance(
            manifest,
            ROOT / "schemas/museum-review-ledger.schema.json",
        )
        self.assertEqual([], [issue.as_dict() for issue in issues])

    def test_canonical_json_rejects_nonfinite_numbers(self) -> None:
        subject = blind_subject()[0][0]
        review = valid_review(subject)
        review["entity_observations"][0]["nonfinite"] = math.nan
        with self.assertRaisesRegex(ValueError, "Out of range float"):
            canonical_review_bytes(review)

    def test_two_distinct_reviews_are_ready_for_adjudication(self) -> None:
        subject = blind_subject()[0][0]
        report = audit(subject, [valid_review(subject), second_review(subject)])
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(1, report["subjects_with_two_reviews"])
        self.assertEqual(1, report["adjudication_ready_subjects"])
        self.assertEqual(0, report["promotion_ready_subjects"])
        self.assertFalse(report["identity_roster_bound"])
        self.assertFalse(report["append_only_proven"])
        self.assertFalse(report["seal_chronology_bound"])

    def test_adjudication_requires_distinct_actor_and_assignment(self) -> None:
        subject = blind_subject()[0][0]
        first = valid_review(subject)
        duplicate_actor = second_review(subject)
        duplicate_actor["actor"]["actor_id"] = first["actor"]["actor_id"]
        result = audit(subject, [first, duplicate_actor])
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(0, result["subjects_with_two_reviews"])

        duplicate_assignment = second_review(subject)
        duplicate_assignment["assignment_id"] = first["assignment_id"]
        result = audit(subject, [first, duplicate_assignment])
        self.assertFalse(result["valid"])
        self.assertEqual(0, result["adjudication_ready_subjects"])
        self.assertTrue(any("multiple active reviews" in error for error in result["errors"]))

    def test_clean_adjudication_completes_subject(self) -> None:
        subject = blind_subject()[0][0]
        first = valid_review(subject)
        second = second_review(subject)
        decision = adjudication(
            subject,
            [review_digest(first), review_digest(second)],
        )
        report = audit(subject, [first, second, decision])
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(1, report["adjudicated_subjects"])
        self.assertEqual(0, report["unresolved_subjects"])
        self.assertEqual(0, report["adjudication_ready_subjects"])

    def test_any_graph_error_fails_readiness_and_completion_closed(self) -> None:
        subject = blind_subject()[0][0]
        first = valid_review(subject)
        second = second_review(subject)
        decision = adjudication(
            subject,
            [review_digest(first), review_digest(second)],
        )
        decision["actor"]["reviewed_at"] = "2026-07-26T09:00:00Z"
        report = audit(subject, [first, second, decision])
        self.assertFalse(report["valid"])
        self.assertEqual(0, report["subjects_with_two_reviews"])
        self.assertEqual(0, report["adjudication_ready_subjects"])
        self.assertEqual(0, report["adjudicated_subjects"])
        self.assertEqual(1, report["unresolved_subjects"])

    def test_supersession_binds_predecessor_digest_and_stales_decision(self) -> None:
        subject = blind_subject()[0][0]
        first = valid_review(subject)
        second = second_review(subject)
        decision = adjudication(
            subject,
            [review_digest(first), review_digest(second)],
        )
        correction = copy.deepcopy(first)
        correction["review_id"] = "review:synthetic:one-correction"
        correction["actor"]["reviewed_at"] = "2026-07-26T12:00:00Z"
        correction["supersedes_review_id"] = first["review_id"]
        correction["supersedes_review_sha256"] = review_digest(first)
        report = audit(subject, [first, second, decision, correction])
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(1, report["stale_adjudication_subjects"])
        self.assertEqual(0, report["adjudicated_subjects"])

        wrong_digest = copy.deepcopy(correction)
        wrong_digest["supersedes_review_sha256"] = "sha256:" + "f" * 64
        report = audit(subject, [first, second, wrong_digest])
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("predecessor digest commitment mismatch" in error for error in report["errors"])
        )

    def test_exact_crosswalk_needs_two_probable_specialist_inputs(self) -> None:
        subject = blind_subject()[0][0]
        first = valid_review(subject)
        second = second_review(subject)
        for index, review in enumerate((first, second), start=1):
            review["actor"]["role"] = "collection_specialist"
            review["actor"]["expertise"] = ["collections"]
            review["catalog_crosswalk_assertions"] = [
                probable_crosswalk(f"crosswalk:probable-{index}")
            ]
        decision = adjudication(
            subject,
            [review_digest(first), review_digest(second)],
        )
        exact = probable_crosswalk("crosswalk:exact")
        exact["strength"] = "exact"
        decision["catalog_crosswalk_assertions"] = [exact]
        report = audit(subject, [first, second, decision])
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(1, report["chain_supported_exact_crosswalk_count"])
        self.assertEqual(1, report["accepted_active_exact_crosswalk_count"])
        self.assertEqual(0, report["promotion_ready_subjects"])

        unsupported_first = copy.deepcopy(first)
        unsupported_first["catalog_crosswalk_assertions"] = []
        unsupported_decision = adjudication(
            subject,
            [review_digest(unsupported_first), review_digest(second)],
        )
        unsupported_decision["catalog_crosswalk_assertions"] = [exact]
        report = audit(
            subject,
            [unsupported_first, second, unsupported_decision],
        )
        self.assertFalse(report["valid"])
        self.assertEqual(0, report["accepted_active_exact_crosswalk_count"])

    def test_exact_crosswalk_cannot_hide_a_current_contradictory_review(self) -> None:
        subject = blind_subject()[0][0]
        first = valid_review(subject)
        second = second_review(subject)
        third = second_review(subject)
        third["review_id"] = "review:synthetic:three"
        third["assignment_id"] = "assignment:synthetic:three"
        third["actor"]["actor_id"] = "reviewer:pseudonymous-three"
        third["actor"]["reviewed_at"] = "2026-07-26T10:10:00Z"
        for index, review in enumerate((first, second), start=1):
            review["actor"]["role"] = "collection_specialist"
            review["actor"]["expertise"] = ["collections"]
            review["catalog_crosswalk_assertions"] = [
                probable_crosswalk(f"crosswalk:probable-{index}")
            ]
        third["actor"]["role"] = "collection_specialist"
        third["actor"]["expertise"] = ["collections"]
        rejected = probable_crosswalk("crosswalk:rejected")
        rejected["strength"] = "rejected"
        third["catalog_crosswalk_assertions"] = [rejected]

        decision = adjudication(
            subject,
            [review_digest(first), review_digest(second)],
        )
        exact = probable_crosswalk("crosswalk:exact")
        exact["strength"] = "exact"
        decision["catalog_crosswalk_assertions"] = [exact]

        report = audit(subject, [first, second, third, decision])

        self.assertFalse(report["valid"])
        self.assertEqual(0, report["accepted_active_exact_crosswalk_count"])
        self.assertTrue(any("cover every current complete" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
