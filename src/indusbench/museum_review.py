"""Catalog-blinded, observation-only review records for verified museum media."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from indusbench.manifest import sha256_json

SUBJECT_SCHEMA_VERSION = "0.1.0"
REVIEW_SCHEMA_VERSION = "0.2.0"
CUSTODY_SCHEMA_VERSION = "0.1.0"
REVIEW_PACKET_VERSION = "0.1.0"
REVIEW_SCOPE = (
    "physical and catalog observation only; no sign reading, phonetic, "
    "language, semantic, or translation inference"
)
REVIEWER_PRIVACY_CLASSIFICATION = "catalog_blind_private_review"
CUSTODY_PRIVACY_CLASSIFICATION = "private_custody_do_not_share"
CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
STABLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
SAFE_RELATIVE_PATH_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tif",
    "image/x-tiff": ".tif",
}
FORBIDDEN_INTERPRETIVE_KEYS = {
    "decipherment",
    "gloss",
    "language_assignment",
    "phonetic_value",
    "reading_direction",
    "sign_id",
    "sign_sequence",
    "tokens",
    "transcription",
    "translation",
}
FORBIDDEN_BLIND_SUBJECT_KEYS = FORBIDDEN_INTERPRETIVE_KEYS | {
    "accession_number",
    "bundle_relative_path",
    "institution",
    "intake_id",
    "media_id",
    "object_id",
    "official_record",
    "provider_derivative",
    "provider_view_index",
    "provider_view_role",
    "record_uri",
    "source_id",
    "source_uri",
    "title_as_catalogued",
}


class MuseumReviewError(ValueError):
    """Raised when a museum review artifact violates the private-review contract."""


def build_blind_review_materials(
    intake_records: Sequence[Mapping[str, Any]],
    verification_reports: Sequence[Mapping[str, Any]],
    *,
    packet_id: str,
    pseudonym_key: bytes,
    source_bundle_manifest_sha256: str,
    source_bundle_version: str,
    source_bundle_created_at: str,
    source_bundle_externally_anchored: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Create blind subjects, a separate identity map, and byte-copy instructions."""

    _require_stable_id(packet_id, "packet_id")
    if len(pseudonym_key) < 32:
        raise MuseumReviewError("pseudonym_key must contain at least 32 bytes")
    if not intake_records:
        raise MuseumReviewError("a review packet requires at least one intake record")
    report_by_intake_id = {
        report.get("intake_id"): report
        for report in verification_reports
        if isinstance(report.get("intake_id"), str)
    }
    if len(report_by_intake_id) != len(verification_reports):
        raise MuseumReviewError("verification reports must have unique intake_id values")

    subjects: list[dict[str, Any]] = []
    custody_entries: list[dict[str, Any]] = []
    copy_specs: list[dict[str, Any]] = []
    for intake_record in intake_records:
        intake_id = intake_record.get("intake_id")
        if not isinstance(intake_id, str):
            raise MuseumReviewError("intake record lacks intake_id")
        report = report_by_intake_id.get(intake_id)
        if report is None:
            raise MuseumReviewError(f"missing verification report for {intake_id}")
        subject, custody_entry, subject_copy_specs = _build_blind_subject(
            intake_record,
            report,
            packet_id=packet_id,
            pseudonym_key=pseudonym_key,
        )
        subjects.append(subject)
        custody_entries.append(custody_entry)
        copy_specs.extend(subject_copy_specs)

    subjects.sort(key=lambda item: item["subject_id"])
    custody_entries.sort(key=lambda item: item["subject_id"])
    copy_specs.sort(key=lambda item: item["review_relative_path"])
    subject_ids = [subject["subject_id"] for subject in subjects]
    if len(set(subject_ids)) != len(subject_ids):
        raise MuseumReviewError("pseudonymization produced duplicate subject IDs")
    image_ids = [specification["image_id"] for specification in copy_specs]
    if len(set(image_ids)) != len(image_ids):
        raise MuseumReviewError("pseudonymization produced duplicate image IDs")

    custody_map = {
        "schema_version": CUSTODY_SCHEMA_VERSION,
        "packet_id": packet_id,
        "privacy_classification": CUSTODY_PRIVACY_CLASSIFICATION,
        "pseudonymization_key_sha256": ("sha256:" + hashlib.sha256(pseudonym_key).hexdigest()),
        "source_bundle": {
            "bundle_version": source_bundle_version,
            "created_at": source_bundle_created_at,
            "manifest_sha256": source_bundle_manifest_sha256,
            "externally_anchored": source_bundle_externally_anchored,
        },
        "subjects": custody_entries,
    }
    validate_custody_semantics(custody_map)
    return subjects, custody_map, copy_specs


def build_reviewer_manifest(
    subjects: Sequence[Mapping[str, Any]],
    *,
    packet_id: str,
    created_at: str,
    subjects_file_sha256: str,
    instructions_file_sha256: str,
    evidence_inventory: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a self-contained manifest that carries no catalog identity fields."""

    view_group_count = sum(len(subject["view_groups"]) for subject in subjects)
    evidence_bytes = sum(int(item["bytes"]) for item in evidence_inventory)
    manifest = {
        "manifest_version": REVIEW_PACKET_VERSION,
        "packet_id": packet_id,
        "created_at": created_at,
        "privacy_classification": REVIEWER_PRIVACY_CLASSIFICATION,
        "scientific_scope": REVIEW_SCOPE,
        "required_independent_reviews_per_subject": 2,
        "subject_count": len(subjects),
        "view_group_count": view_group_count,
        "evidence_image_count": len(evidence_inventory),
        "evidence_bytes": evidence_bytes,
        "subjects_file": "subjects.jsonl",
        "subjects_file_sha256": subjects_file_sha256,
        "instructions_file": "REVIEW_INSTRUCTIONS.md",
        "instructions_file_sha256": instructions_file_sha256,
        "evidence": [dict(item) for item in evidence_inventory],
    }
    validate_reviewer_manifest_semantics(manifest)
    return manifest


def build_packet_manifest(
    *,
    packet_id: str,
    created_at: str,
    source_bundle_manifest_sha256: str,
    source_bundle_version: str,
    source_bundle_created_at: str,
    source_bundle_externally_anchored: bool,
    reviewer_manifest_sha256: str,
    custody_map_sha256: str,
    subject_count: int,
    view_group_count: int,
    evidence_image_count: int,
    evidence_bytes: int,
) -> dict[str, Any]:
    """Build the private controller manifest joining blind and custody layers."""

    publication_gate = (
        "rights_and_heritage_review_required"
        if source_bundle_externally_anchored
        else "blocked_missing_external_source_anchor"
    )
    manifest = {
        "packet_version": REVIEW_PACKET_VERSION,
        "packet_id": packet_id,
        "created_at": created_at,
        "privacy_classification": "private_review_controller",
        "scientific_scope": REVIEW_SCOPE,
        "source_bundle": {
            "bundle_version": source_bundle_version,
            "created_at": source_bundle_created_at,
            "manifest_sha256": source_bundle_manifest_sha256,
            "externally_anchored": source_bundle_externally_anchored,
        },
        "reviewer_packet": {
            "directory": "reviewer",
            "manifest_file": "reviewer/manifest.json",
            "manifest_sha256": reviewer_manifest_sha256,
        },
        "custody": {
            "directory": "custody",
            "identity_map_file": "custody/identity-map.json",
            "identity_map_sha256": custody_map_sha256,
            "share_with_reviewers": False,
        },
        "required_independent_reviews_per_subject": 2,
        "subject_count": subject_count,
        "view_group_count": view_group_count,
        "evidence_image_count": evidence_image_count,
        "evidence_bytes": evidence_bytes,
        "publication_gate": publication_gate,
    }
    validate_packet_manifest_semantics(manifest)
    return manifest


def validate_subject_semantics(subject: Mapping[str, Any]) -> None:
    """Validate one catalog-blinded review subject."""

    _reject_keys(subject, FORBIDDEN_BLIND_SUBJECT_KEYS, "review subject")
    _require_closed_keys(
        subject,
        {
            "schema_version",
            "packet_id",
            "subject_id",
            "record_state",
            "privacy_classification",
            "scientific_scope",
            "view_groups",
            "limitations",
        },
        "review subject",
    )
    if subject["schema_version"] != SUBJECT_SCHEMA_VERSION:
        raise MuseumReviewError("unsupported review subject schema version")
    if subject["record_state"] != "human_observation_review_pending":
        raise MuseumReviewError("review subject must remain pending")
    if subject["privacy_classification"] != REVIEWER_PRIVACY_CLASSIFICATION:
        raise MuseumReviewError("review subject privacy classification mismatch")
    if subject["scientific_scope"] != REVIEW_SCOPE:
        raise MuseumReviewError("review subject scientific scope mismatch")
    _require_stable_id(subject["packet_id"], "packet_id")
    _require_stable_id(subject["subject_id"], "subject_id")
    view_groups = subject["view_groups"]
    if not isinstance(view_groups, list) or not view_groups:
        raise MuseumReviewError("review subject needs at least one view group")
    view_group_ids: list[str] = []
    image_ids: list[str] = []
    image_paths: list[str] = []
    for group_index, value in enumerate(view_groups):
        group = _require_mapping(value, f"view_groups[{group_index}]")
        _require_closed_keys(
            group,
            {"view_group_id", "evidence_images"},
            f"view_groups[{group_index}]",
        )
        _require_stable_id(group["view_group_id"], "view_group_id")
        view_group_ids.append(group["view_group_id"])
        images = group["evidence_images"]
        if not isinstance(images, list) or not images:
            raise MuseumReviewError("each view group needs at least one evidence image")
        for image_index, image_value in enumerate(images):
            image = _require_mapping(
                image_value,
                f"view_groups[{group_index}].evidence_images[{image_index}]",
            )
            _require_closed_keys(
                image,
                {
                    "image_id",
                    "sha256",
                    "bytes",
                    "content_type",
                    "relative_path",
                },
                "review evidence image",
            )
            _require_stable_id(image["image_id"], "image_id")
            _require_checksum(image["sha256"], "image.sha256")
            byte_count = image["bytes"]
            if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
                raise MuseumReviewError("review evidence image bytes must be positive")
            if image["content_type"] not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise MuseumReviewError("review evidence image content type is unsupported")
            _require_safe_relative_path(image["relative_path"], "image.relative_path")
            expected_prefix = f"evidence/{str(image['image_id']).split(':', 1)[-1]}"
            if not str(image["relative_path"]).startswith(expected_prefix):
                raise MuseumReviewError("review evidence filename must use its opaque image ID")
            image_ids.append(image["image_id"])
            image_paths.append(image["relative_path"])
    if len(set(view_group_ids)) != len(view_group_ids):
        raise MuseumReviewError("review subject has duplicate view_group_id values")
    if len(set(image_ids)) != len(image_ids) or len(set(image_paths)) != len(image_paths):
        raise MuseumReviewError("review subject has duplicate evidence identifiers or paths")
    limitations = subject["limitations"]
    if not isinstance(limitations, list) or any(
        not isinstance(item, str) or not item.strip() for item in limitations
    ):
        raise MuseumReviewError("review subject limitations must be non-empty strings")


def validate_custody_semantics(custody_map: Mapping[str, Any]) -> None:
    """Validate the private identity layer without exposing it to reviewers."""

    _require_closed_keys(
        custody_map,
        {
            "schema_version",
            "packet_id",
            "privacy_classification",
            "pseudonymization_key_sha256",
            "source_bundle",
            "subjects",
        },
        "review custody map",
    )
    if custody_map["schema_version"] != CUSTODY_SCHEMA_VERSION:
        raise MuseumReviewError("unsupported custody schema version")
    if custody_map["privacy_classification"] != CUSTODY_PRIVACY_CLASSIFICATION:
        raise MuseumReviewError("custody privacy classification mismatch")
    _require_stable_id(custody_map["packet_id"], "custody packet_id")
    _require_checksum(
        custody_map["pseudonymization_key_sha256"],
        "pseudonymization_key_sha256",
    )
    source_bundle = _require_mapping(custody_map["source_bundle"], "source_bundle")
    _validate_source_bundle(source_bundle)
    subjects = custody_map["subjects"]
    if not isinstance(subjects, list) or not subjects:
        raise MuseumReviewError("custody map needs at least one subject")
    subject_ids: list[str] = []
    intake_ids: list[str] = []
    image_ids: list[str] = []
    for index, value in enumerate(subjects):
        subject = _require_mapping(value, f"custody subjects[{index}]")
        _require_closed_keys(
            subject,
            {
                "subject_id",
                "intake_id",
                "source_id",
                "institution",
                "official_record",
                "item_rights",
                "source_record_sha256",
                "view_groups",
            },
            f"custody subjects[{index}]",
        )
        _require_stable_id(subject["subject_id"], "custody subject_id")
        _require_stable_id(subject["intake_id"], "custody intake_id")
        _require_stable_id(subject["source_id"], "custody source_id")
        _require_checksum(subject["source_record_sha256"], "source_record_sha256")
        subject_ids.append(subject["subject_id"])
        intake_ids.append(subject["intake_id"])
        view_groups = subject["view_groups"]
        if not isinstance(view_groups, list) or not view_groups:
            raise MuseumReviewError("custody subject needs view groups")
        for group in view_groups:
            group_mapping = _require_mapping(group, "custody view group")
            _require_closed_keys(
                group_mapping,
                {"view_group_id", "provider_view_index", "images"},
                "custody view group",
            )
            images = group_mapping["images"]
            if not isinstance(images, list) or not images:
                raise MuseumReviewError("custody view group needs images")
            for image in images:
                image_mapping = _require_mapping(image, "custody image")
                _require_closed_keys(
                    image_mapping,
                    {
                        "image_id",
                        "media_id",
                        "provider_derivative",
                        "provider_view_role",
                        "source_uri",
                        "source_bundle_relative_path",
                        "review_relative_path",
                        "sha256",
                        "bytes",
                        "content_type",
                    },
                    "custody image",
                )
                _require_stable_id(image_mapping["image_id"], "custody image_id")
                _require_stable_id(image_mapping["media_id"], "custody media_id")
                _require_safe_relative_path(
                    image_mapping["source_bundle_relative_path"],
                    "source_bundle_relative_path",
                )
                _require_safe_relative_path(
                    image_mapping["review_relative_path"],
                    "review_relative_path",
                )
                _require_checksum(image_mapping["sha256"], "custody image sha256")
                image_ids.append(image_mapping["image_id"])
    if len(set(subject_ids)) != len(subject_ids) or len(set(intake_ids)) != len(intake_ids):
        raise MuseumReviewError("custody map has duplicate subject or intake identifiers")
    if len(set(image_ids)) != len(image_ids):
        raise MuseumReviewError("custody map has duplicate image identifiers")


def validate_reviewer_manifest_semantics(manifest: Mapping[str, Any]) -> None:
    """Validate the catalog-blind reviewer manifest."""

    _require_closed_keys(
        manifest,
        {
            "manifest_version",
            "packet_id",
            "created_at",
            "privacy_classification",
            "scientific_scope",
            "required_independent_reviews_per_subject",
            "subject_count",
            "view_group_count",
            "evidence_image_count",
            "evidence_bytes",
            "subjects_file",
            "subjects_file_sha256",
            "instructions_file",
            "instructions_file_sha256",
            "evidence",
        },
        "reviewer manifest",
    )
    _reject_keys(manifest, FORBIDDEN_BLIND_SUBJECT_KEYS, "reviewer manifest")
    if manifest["manifest_version"] != REVIEW_PACKET_VERSION:
        raise MuseumReviewError("unsupported reviewer manifest version")
    if manifest["privacy_classification"] != REVIEWER_PRIVACY_CLASSIFICATION:
        raise MuseumReviewError("reviewer manifest privacy classification mismatch")
    if manifest["scientific_scope"] != REVIEW_SCOPE:
        raise MuseumReviewError("reviewer manifest scientific scope mismatch")
    _require_stable_id(manifest["packet_id"], "reviewer manifest packet_id")
    _require_canonical_utc(manifest["created_at"], "reviewer manifest created_at")
    if manifest["required_independent_reviews_per_subject"] != 2:
        raise MuseumReviewError("reviewer manifest requires exactly two independent reviews")
    for field in (
        "subject_count",
        "view_group_count",
        "evidence_image_count",
        "evidence_bytes",
    ):
        _require_nonnegative_integer(manifest[field], f"reviewer manifest {field}")
    if manifest["subject_count"] < 1 or manifest["evidence_image_count"] < 1:
        raise MuseumReviewError("reviewer manifest cannot be empty")
    if manifest["subjects_file"] != "subjects.jsonl":
        raise MuseumReviewError("reviewer manifest subjects filename mismatch")
    if manifest["instructions_file"] != "REVIEW_INSTRUCTIONS.md":
        raise MuseumReviewError("reviewer manifest instructions filename mismatch")
    _require_checksum(manifest["subjects_file_sha256"], "subjects_file_sha256")
    _require_checksum(manifest["instructions_file_sha256"], "instructions_file_sha256")
    evidence = manifest["evidence"]
    if not isinstance(evidence, list):
        raise MuseumReviewError("reviewer manifest evidence must be a list")
    if len(evidence) != manifest["evidence_image_count"]:
        raise MuseumReviewError("reviewer manifest evidence_image_count mismatch")
    if sum(item["bytes"] for item in evidence) != manifest["evidence_bytes"]:
        raise MuseumReviewError("reviewer manifest evidence_bytes mismatch")
    image_ids: list[str] = []
    paths: list[str] = []
    for value in evidence:
        item = _require_mapping(value, "reviewer manifest evidence")
        _require_closed_keys(
            item,
            {"image_id", "relative_path", "sha256", "bytes", "content_type"},
            "reviewer manifest evidence",
        )
        _require_stable_id(item["image_id"], "reviewer evidence image_id")
        _require_safe_relative_path(item["relative_path"], "reviewer evidence relative_path")
        _require_checksum(item["sha256"], "reviewer evidence sha256")
        _require_nonnegative_integer(item["bytes"], "reviewer evidence bytes")
        if item["bytes"] < 1 or item["content_type"] not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise MuseumReviewError("reviewer evidence metadata is invalid")
        image_ids.append(item["image_id"])
        paths.append(item["relative_path"])
    if len(set(image_ids)) != len(image_ids) or len(set(paths)) != len(paths):
        raise MuseumReviewError("reviewer manifest has duplicate evidence identifiers or paths")


def validate_packet_manifest_semantics(manifest: Mapping[str, Any]) -> None:
    """Validate the private controller manifest."""

    _require_closed_keys(
        manifest,
        {
            "packet_version",
            "packet_id",
            "created_at",
            "privacy_classification",
            "scientific_scope",
            "source_bundle",
            "reviewer_packet",
            "custody",
            "required_independent_reviews_per_subject",
            "subject_count",
            "view_group_count",
            "evidence_image_count",
            "evidence_bytes",
            "publication_gate",
        },
        "review packet manifest",
    )
    if manifest["packet_version"] != REVIEW_PACKET_VERSION:
        raise MuseumReviewError("unsupported review packet version")
    if manifest["privacy_classification"] != "private_review_controller":
        raise MuseumReviewError("review packet privacy classification mismatch")
    if manifest["scientific_scope"] != REVIEW_SCOPE:
        raise MuseumReviewError("review packet scientific scope mismatch")
    _require_stable_id(manifest["packet_id"], "review packet_id")
    _require_canonical_utc(manifest["created_at"], "review packet created_at")
    source_bundle = _require_mapping(manifest["source_bundle"], "source_bundle")
    _validate_source_bundle(source_bundle)
    reviewer_packet = _require_mapping(manifest["reviewer_packet"], "reviewer_packet")
    _require_closed_keys(
        reviewer_packet,
        {"directory", "manifest_file", "manifest_sha256"},
        "reviewer_packet",
    )
    if (
        reviewer_packet["directory"] != "reviewer"
        or reviewer_packet["manifest_file"] != "reviewer/manifest.json"
    ):
        raise MuseumReviewError("reviewer packet layout mismatch")
    _require_checksum(reviewer_packet["manifest_sha256"], "reviewer manifest sha256")
    custody = _require_mapping(manifest["custody"], "custody")
    _require_closed_keys(
        custody,
        {
            "directory",
            "identity_map_file",
            "identity_map_sha256",
            "share_with_reviewers",
        },
        "custody",
    )
    if (
        custody["directory"] != "custody"
        or custody["identity_map_file"] != "custody/identity-map.json"
        or custody["share_with_reviewers"] is not False
    ):
        raise MuseumReviewError("custody isolation contract mismatch")
    _require_checksum(custody["identity_map_sha256"], "custody map sha256")
    if manifest["required_independent_reviews_per_subject"] != 2:
        raise MuseumReviewError("review packet requires exactly two independent reviews")
    for field in (
        "subject_count",
        "view_group_count",
        "evidence_image_count",
        "evidence_bytes",
    ):
        _require_nonnegative_integer(manifest[field], f"review packet {field}")
    expected_gate = (
        "rights_and_heritage_review_required"
        if source_bundle["externally_anchored"]
        else "blocked_missing_external_source_anchor"
    )
    if manifest["publication_gate"] != expected_gate:
        raise MuseumReviewError("review packet publication gate is inconsistent")


def validate_review_submission(
    review: Mapping[str, Any],
    *,
    subject: Mapping[str, Any] | None = None,
) -> None:
    """Validate one append-only observation review or adjudication record."""

    _require_closed_keys(
        review,
        {
            "schema_version",
            "record_state",
            "review_id",
            "packet_id",
            "assignment_id",
            "review_stage",
            "subject_id",
            "scientific_scope",
            "source_commitment",
            "actor",
            "input_reviews",
            "entity_observations",
            "relationship_assertions",
            "catalog_crosswalk_assertions",
            "disagreements",
            "outcome",
            "limitations",
            "supersedes_review_id",
            "supersedes_review_sha256",
        },
        "museum review",
    )
    _reject_keys(review, FORBIDDEN_INTERPRETIVE_KEYS, "museum review")
    if review["schema_version"] != REVIEW_SCHEMA_VERSION:
        raise MuseumReviewError("unsupported museum review schema version")
    if review["record_state"] != "human_observation_review":
        raise MuseumReviewError("museum review record_state mismatch")
    if review["scientific_scope"] != REVIEW_SCOPE:
        raise MuseumReviewError("museum review scientific scope mismatch")
    for field in ("review_id", "packet_id", "assignment_id", "subject_id"):
        _require_stable_id(review[field], field)
    supersedes = review["supersedes_review_id"]
    supersedes_sha256 = review["supersedes_review_sha256"]
    if (supersedes is None) != (supersedes_sha256 is None):
        raise MuseumReviewError(
            "supersession requires both predecessor review_id and SHA-256 digest"
        )
    if supersedes is not None:
        _require_stable_id(supersedes, "supersedes_review_id")
        _require_checksum(supersedes_sha256, "supersedes_review_sha256")
        if supersedes == review["review_id"]:
            raise MuseumReviewError("a review cannot supersede itself")

    commitment = _require_mapping(review["source_commitment"], "source_commitment")
    _require_closed_keys(
        commitment,
        {
            "reviewer_manifest_sha256",
            "subject_record_sha256",
            "evidence_sha256s",
        },
        "source_commitment",
    )
    _require_checksum(
        commitment["reviewer_manifest_sha256"],
        "reviewer_manifest_sha256",
    )
    _require_checksum(commitment["subject_record_sha256"], "subject_record_sha256")
    evidence_sha256s = commitment["evidence_sha256s"]
    if (
        not isinstance(evidence_sha256s, list)
        or not evidence_sha256s
        or len(set(evidence_sha256s)) != len(evidence_sha256s)
    ):
        raise MuseumReviewError("source_commitment evidence hashes must be unique")
    for checksum in evidence_sha256s:
        _require_checksum(checksum, "source_commitment evidence sha256")

    actor = _require_mapping(review["actor"], "actor")
    _require_closed_keys(
        actor,
        {
            "actor_id",
            "role",
            "expertise",
            "reviewed_at",
            "independent_pass",
            "conflict_status",
            "prior_familiarity",
            "viewing_methods",
        },
        "actor",
    )
    _require_stable_id(actor["actor_id"], "actor.actor_id")
    if actor["role"] not in {
        "visual_reviewer",
        "collection_specialist",
        "archaeologist",
        "adjudicator",
    }:
        raise MuseumReviewError("unknown review actor role")
    expertise = actor["expertise"]
    if not isinstance(expertise, list) or any(
        item not in {"visual", "collections", "archaeology"} for item in expertise
    ):
        raise MuseumReviewError("actor expertise contains an unsupported value")
    _require_canonical_utc(actor["reviewed_at"], "actor.reviewed_at")
    if actor["conflict_status"] not in {"none_declared", "declared", "unknown"}:
        raise MuseumReviewError("actor conflict_status is invalid")
    if actor["prior_familiarity"] not in {"none", "possible", "known", "unknown"}:
        raise MuseumReviewError("actor prior_familiarity is invalid")
    if not isinstance(actor["viewing_methods"], list) or not actor["viewing_methods"]:
        raise MuseumReviewError("actor viewing_methods must be a non-empty list")

    stage = review["review_stage"]
    input_reviews = review["input_reviews"]
    if not isinstance(input_reviews, list) or len(set(input_reviews)) != len(input_reviews):
        raise MuseumReviewError("input_reviews must be a unique list")
    for checksum in input_reviews:
        _require_checksum(checksum, "input review sha256")
    if stage == "independent":
        if input_reviews or actor["independent_pass"] is not True:
            raise MuseumReviewError("independent review cannot inspect prior reviews")
        if actor["role"] == "adjudicator":
            raise MuseumReviewError("adjudicator role is invalid for an independent review")
    elif stage == "adjudication":
        if len(input_reviews) < 2 or actor["independent_pass"] is not False:
            raise MuseumReviewError("adjudication requires at least two sealed input reviews")
        if actor["role"] != "adjudicator":
            raise MuseumReviewError("adjudication requires an adjudicator")
    else:
        raise MuseumReviewError("unknown review_stage")

    observations = review["entity_observations"]
    if not isinstance(observations, list):
        raise MuseumReviewError("entity_observations must be a list")
    entity_ids: set[str] = set()
    for observation in observations:
        _validate_entity_observation(observation)
        entity_id = observation["entity_id"]
        if entity_id in entity_ids:
            raise MuseumReviewError("entity_observations contain duplicate entity_id values")
        entity_ids.add(entity_id)
    relationships = review["relationship_assertions"]
    if not isinstance(relationships, list):
        raise MuseumReviewError("relationship_assertions must be a list")
    assertion_ids: set[str] = set()
    for relationship in relationships:
        _validate_relationship_assertion(relationship)
        assertion_id = relationship["assertion_id"]
        if assertion_id in assertion_ids:
            raise MuseumReviewError("review assertion_id values must be unique")
        assertion_ids.add(assertion_id)
        if (
            relationship["left_entity_id"] not in entity_ids
            or relationship["right_entity_id"] not in entity_ids
        ):
            raise MuseumReviewError(
                "relationship endpoints must cite entity_observations in the same review"
            )
    crosswalks = review["catalog_crosswalk_assertions"]
    if not isinstance(crosswalks, list):
        raise MuseumReviewError("catalog_crosswalk_assertions must be a list")
    if actor["role"] == "visual_reviewer" and crosswalks:
        raise MuseumReviewError("catalog-blind visual reviewers cannot assert catalog crosswalks")
    for crosswalk in crosswalks:
        _validate_catalog_crosswalk(crosswalk, stage=stage, actor=actor)
        assertion_id = crosswalk["assertion_id"]
        if assertion_id in assertion_ids:
            raise MuseumReviewError("review assertion_id values must be unique")
        assertion_ids.add(assertion_id)

    for field in ("disagreements", "limitations"):
        values = review[field]
        if not isinstance(values, list) or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise MuseumReviewError(f"{field} must contain only non-empty strings")
    if review["outcome"] not in {"complete", "needs_more_evidence", "abstain"}:
        raise MuseumReviewError("unknown review outcome")
    if review["outcome"] == "complete" and not observations:
        raise MuseumReviewError("a complete review requires entity observations")

    if subject is not None:
        validate_subject_semantics(subject)
        if review["packet_id"] != subject["packet_id"]:
            raise MuseumReviewError("review packet_id does not match subject")
        if review["subject_id"] != subject["subject_id"]:
            raise MuseumReviewError("review subject_id does not match subject")
        if commitment["subject_record_sha256"] != f"sha256:{sha256_json(subject)}":
            raise MuseumReviewError("review subject commitment hash mismatch")
        subject_images = _subject_images(subject)
        expected_hashes = {image["sha256"] for image in subject_images.values()}
        if set(evidence_sha256s) != expected_hashes:
            raise MuseumReviewError("review evidence commitment does not cover the subject")
        observed_image_ids = {observation["image_id"] for observation in observations}
        if not observed_image_ids.issubset(subject_images):
            raise MuseumReviewError("review observation cites an unknown image")
        if review["outcome"] == "complete" and observed_image_ids != set(subject_images):
            raise MuseumReviewError(
                "a complete review must contain an observation for every subject image"
            )
        for observation in observations:
            if observation["image_sha256"] != subject_images[observation["image_id"]]["sha256"]:
                raise MuseumReviewError("review observation image hash mismatch")


def render_review_instructions() -> str:
    """Return the catalog-blind packet's human-review instructions."""

    return """# Private catalog-blind museum observation review

This directory is a private observation queue, not a decipherment result and
not a publication package. Catalog identity fields are intentionally kept in a
separate custody directory that must not be shared with visual reviewers.

## Record only what the evidence supports

- whether an image appears to depict a seal matrix, ancient impression, modern
  impression, modern cast, directly inscribed object, drawing, or an unresolved carrier;
- the observable physical surface, while preserving uncertainty;
- inscription-region polygons in normalized coordinates of the exact original image;
- damage, occlusion, and evidence-supported relationships between depicted entities;
- for authorized catalog specialists only, versioned candidate crosswalks with
  evidence and counterevidence.

## Forbidden in this review layer

- sign IDs, sign segmentation, or reading direction;
- phonetic values, language assignments, meanings, glosses, or translations;
- exact artifact identity based only on motif, catalog prose, or an assumed sign sequence.

Independent reviewers must not inspect each other's submissions. Adjudication
starts only after at least two sealed review hashes exist. An exact catalog
crosswalk additionally requires collections or archaeology expertise and a
documented counterevidence check.

Image filenames and metadata records are catalog-blinded, but pixels or embedded
image metadata may still reveal provenance. Reviewers must declare prior
familiarity and conflicts. The source bundle and custody map remain private.
"""


def _build_blind_subject(
    intake_record: Mapping[str, Any],
    verification_report: Mapping[str, Any],
    *,
    packet_id: str,
    pseudonym_key: bytes,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    intake_id = str(intake_record["intake_id"])
    subject_id = _opaque_id("subject", pseudonym_key, intake_id)
    grouped_media: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for media_value in intake_record["media"]:
        media = _require_mapping(media_value, "intake media")
        download = _require_mapping(media["download"], "intake media download")
        if download["status"] != "downloaded":
            raise MuseumReviewError(
                f"{intake_id}: blind review packet requires every image to be downloaded"
            )
        provider_index = media["provider_view_index"]
        if isinstance(provider_index, bool) or not isinstance(provider_index, int):
            raise MuseumReviewError(f"{intake_id}: invalid provider view index")
        grouped_media[provider_index].append(media)

    view_groups = []
    custody_view_groups = []
    copy_specs: list[dict[str, Any]] = []
    for provider_index in sorted(
        grouped_media,
        key=lambda value: _opaque_sort_key(
            pseudonym_key,
            intake_id,
            "view",
            str(value),
        ),
    ):
        view_group_id = _opaque_id(
            "view",
            pseudonym_key,
            intake_id,
            str(provider_index),
        )
        evidence_images = []
        custody_images = []
        for media in sorted(
            grouped_media[provider_index],
            key=lambda value: _opaque_sort_key(
                pseudonym_key,
                intake_id,
                str(value["media_id"]),
            ),
        ):
            download = _require_mapping(media["download"], "intake media download")
            content_type = download["content_type"]
            extension = ALLOWED_IMAGE_CONTENT_TYPES.get(content_type)
            if extension is None:
                raise MuseumReviewError(
                    f"{intake_id}: unsupported review image content type {content_type!r}"
                )
            image_id = _opaque_id(
                "image",
                pseudonym_key,
                intake_id,
                str(media["media_id"]),
            )
            token = image_id.split(":", 1)[1]
            review_relative_path = f"evidence/{token}{extension}"
            evidence_image = {
                "image_id": image_id,
                "sha256": download["sha256"],
                "bytes": download["bytes"],
                "content_type": content_type,
                "relative_path": review_relative_path,
            }
            evidence_images.append(evidence_image)
            source_relative_path = download["local_relative_path"]
            custody_image = {
                "image_id": image_id,
                "media_id": media["media_id"],
                "provider_derivative": media["provider_derivative"],
                "provider_view_role": media["view_role"],
                "source_uri": media["source_uri"],
                "source_bundle_relative_path": source_relative_path,
                "review_relative_path": review_relative_path,
                "sha256": download["sha256"],
                "bytes": download["bytes"],
                "content_type": content_type,
            }
            custody_images.append(custody_image)
            copy_specs.append(
                {
                    "subject_id": subject_id,
                    "view_group_id": view_group_id,
                    "image_id": image_id,
                    "source_relative_path": source_relative_path,
                    "review_relative_path": review_relative_path,
                    "sha256": download["sha256"],
                    "bytes": download["bytes"],
                    "content_type": content_type,
                }
            )
        view_groups.append(
            {
                "view_group_id": view_group_id,
                "evidence_images": evidence_images,
            }
        )
        custody_view_groups.append(
            {
                "view_group_id": view_group_id,
                "provider_view_index": provider_index,
                "images": custody_images,
            }
        )

    subject = {
        "schema_version": SUBJECT_SCHEMA_VERSION,
        "packet_id": packet_id,
        "subject_id": subject_id,
        "record_state": "human_observation_review_pending",
        "privacy_classification": REVIEWER_PRIVACY_CLASSIFICATION,
        "scientific_scope": REVIEW_SCOPE,
        "view_groups": view_groups,
        "limitations": [
            "One review subject is not yet an asserted unique physical artifact.",
            "A view group is a provider grouping, not an asserted physical side.",
            "Evidence images may depict a matrix, impression, cast, drawing, or another entity.",
            "No sign, reading, language, meaning, or translation inference belongs here.",
        ],
    }
    validate_subject_semantics(subject)
    custody_entry = {
        "subject_id": subject_id,
        "intake_id": intake_id,
        "source_id": intake_record["source_id"],
        "institution": dict(intake_record["institution"]),
        "official_record": dict(intake_record["official_record"]),
        "item_rights": {
            key: intake_record["item_rights"][key]
            for key in (
                "status",
                "license_id",
                "rights_holder",
                "redistribution",
                "derivatives",
                "commercial_use",
            )
        },
        "source_record_sha256": verification_report["record_sha256"],
        "view_groups": custody_view_groups,
    }
    return subject, custody_entry, copy_specs


def _validate_source_bundle(source_bundle: Mapping[str, Any]) -> None:
    _require_closed_keys(
        source_bundle,
        {"bundle_version", "created_at", "manifest_sha256", "externally_anchored"},
        "source_bundle",
    )
    if not isinstance(source_bundle["bundle_version"], str) or not source_bundle["bundle_version"]:
        raise MuseumReviewError("source bundle version must be non-empty")
    _require_canonical_utc(source_bundle["created_at"], "source bundle created_at")
    _require_checksum(source_bundle["manifest_sha256"], "source bundle manifest_sha256")
    if not isinstance(source_bundle["externally_anchored"], bool):
        raise MuseumReviewError("source bundle externally_anchored must be boolean")


def _validate_entity_observation(value: object) -> None:
    observation = _require_mapping(value, "entity observation")
    _require_closed_keys(
        observation,
        {
            "entity_id",
            "image_id",
            "image_sha256",
            "depicted_carrier",
            "physical_surface",
            "inscription_regions",
            "damage_or_occlusion",
            "notes",
        },
        "entity observation",
    )
    _require_stable_id(observation["entity_id"], "entity_id")
    _require_stable_id(observation["image_id"], "entity image_id")
    _require_checksum(observation["image_sha256"], "entity image_sha256")
    if observation["depicted_carrier"] not in {
        "seal_matrix",
        "ancient_impression",
        "modern_impression",
        "modern_cast",
        "direct_inscribed_object",
        "drawing",
        "unknown",
    }:
        raise MuseumReviewError("unknown depicted_carrier")
    if observation["physical_surface"] not in {
        "inscribed_surface",
        "back_surface",
        "edge",
        "other_surface",
        "not_applicable",
        "unknown",
    }:
        raise MuseumReviewError("unknown physical_surface")
    regions = observation["inscription_regions"]
    if not isinstance(regions, list):
        raise MuseumReviewError("inscription_regions must be a list")
    region_ids: set[str] = set()
    for region in regions:
        _validate_inscription_region(region, observation["image_id"], observation["image_sha256"])
        region_id = region["region_id"]
        if region_id in region_ids:
            raise MuseumReviewError("inscription_regions contain duplicate region_id values")
        region_ids.add(region_id)
    damage = observation["damage_or_occlusion"]
    if not isinstance(damage, list) or any(
        not isinstance(item, str) or not item.strip() for item in damage
    ):
        raise MuseumReviewError("damage_or_occlusion must contain non-empty strings")
    if not isinstance(observation["notes"], str):
        raise MuseumReviewError("entity observation notes must be a string")


def _validate_inscription_region(
    value: object,
    expected_image_id: object,
    expected_image_sha256: object,
) -> None:
    region = _require_mapping(value, "inscription region")
    _require_closed_keys(
        region,
        {
            "region_id",
            "image_id",
            "image_sha256",
            "coordinate_space",
            "presence",
            "polygon",
            "uncertainty",
        },
        "inscription region",
    )
    _require_stable_id(region["region_id"], "region_id")
    if region["image_id"] != expected_image_id or region["image_sha256"] != expected_image_sha256:
        raise MuseumReviewError("inscription region must cite its exact source image")
    if region["coordinate_space"] != "normalized_original_image":
        raise MuseumReviewError("inscription region must use normalized original-image coordinates")
    if region["presence"] not in {
        "present",
        "possible",
        "not_visible",
        "absent",
        "unresolved",
    }:
        raise MuseumReviewError("unknown inscription region presence")
    polygon = region["polygon"]
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise MuseumReviewError("inscription polygon needs at least three points")
    points: list[tuple[float, float]] = []
    for point in polygon:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(
                isinstance(coordinate, bool)
                or not isinstance(coordinate, (int, float))
                or coordinate < 0
                or coordinate > 1
                for coordinate in point
            )
        ):
            raise MuseumReviewError("inscription polygon coordinates must be numbers from 0 to 1")
        points.append((float(point[0]), float(point[1])))
    twice_area = abs(
        sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    )
    if twice_area <= 1e-12:
        raise MuseumReviewError("inscription polygon must have nonzero area")
    _validate_uncertainty(region["uncertainty"])


def _validate_uncertainty(value: object) -> None:
    uncertainty = _require_mapping(value, "uncertainty")
    _require_closed_keys(
        uncertainty,
        {"status", "confidence", "basis_codes", "notes"},
        "uncertainty",
    )
    if uncertainty["status"] not in {
        "clear",
        "uncertain",
        "ambiguous",
        "unresolved",
        "not_assessable",
    }:
        raise MuseumReviewError("unknown uncertainty status")
    confidence = uncertainty["confidence"]
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or confidence < 0
        or confidence > 1
    ):
        raise MuseumReviewError("uncertainty confidence must be null or between 0 and 1")
    if not isinstance(uncertainty["basis_codes"], list):
        raise MuseumReviewError("uncertainty basis_codes must be a list")
    if not isinstance(uncertainty["notes"], str):
        raise MuseumReviewError("uncertainty notes must be a string")


def _validate_relationship_assertion(value: object) -> None:
    relationship = _require_mapping(value, "relationship assertion")
    _require_closed_keys(
        relationship,
        {
            "assertion_id",
            "left_entity_id",
            "right_entity_id",
            "relationship",
            "uncertainty",
            "evidence",
            "counterevidence",
        },
        "relationship assertion",
    )
    for field in ("assertion_id", "left_entity_id", "right_entity_id"):
        _require_stable_id(relationship[field], field)
    if relationship["left_entity_id"] == relationship["right_entity_id"]:
        raise MuseumReviewError("relationship endpoints must differ")
    if relationship["relationship"] not in {
        "same_physical_artifact",
        "seal_to_impression",
        "modern_cast_of",
        "fragment_of",
        "joins_with",
        "same_mold_or_template_family",
        "possible_same_artifact",
        "rejected_same_artifact",
        "unresolved",
    }:
        raise MuseumReviewError("unknown relationship assertion")
    _validate_uncertainty(relationship["uncertainty"])
    for field in ("evidence", "counterevidence"):
        values = relationship[field]
        if not isinstance(values, list) or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise MuseumReviewError(f"relationship {field} must contain only non-empty strings")
    if not relationship["evidence"]:
        raise MuseumReviewError("relationship assertions require non-empty evidence")


def _validate_catalog_crosswalk(
    value: object,
    *,
    stage: object,
    actor: Mapping[str, Any],
) -> None:
    crosswalk = _require_mapping(value, "catalog crosswalk")
    _require_closed_keys(
        crosswalk,
        {
            "assertion_id",
            "target_source_id",
            "target_edition",
            "target_record_id",
            "relationship",
            "strength",
            "evidence",
            "counterevidence",
            "counterevidence_checked",
        },
        "catalog crosswalk",
    )
    _require_stable_id(crosswalk["assertion_id"], "crosswalk assertion_id")
    for field in ("target_source_id", "target_edition", "target_record_id"):
        if not isinstance(crosswalk[field], str) or not crosswalk[field].strip():
            raise MuseumReviewError(f"catalog crosswalk {field} must be non-empty")
    if crosswalk["relationship"] not in {
        "same_physical_artifact",
        "impression_of",
        "cast_of",
        "catalog_representation_of",
        "possible_match",
        "rejected_match",
    }:
        raise MuseumReviewError("unknown catalog crosswalk relationship")
    if crosswalk["strength"] not in {"possible", "probable", "exact", "rejected"}:
        raise MuseumReviewError("unknown catalog crosswalk strength")
    for field in ("evidence", "counterevidence"):
        values = crosswalk[field]
        if not isinstance(values, list) or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise MuseumReviewError(
                f"catalog crosswalk {field} must contain only non-empty strings"
            )
    if not crosswalk["evidence"]:
        raise MuseumReviewError("catalog crosswalk assertions require non-empty evidence")
    if not isinstance(crosswalk["counterevidence_checked"], bool):
        raise MuseumReviewError("counterevidence_checked must be boolean")
    if crosswalk["strength"] == "exact":
        if stage != "adjudication":
            raise MuseumReviewError("exact crosswalks can only be adopted in adjudication")
        if not {"collections", "archaeology"}.intersection(actor["expertise"]):
            raise MuseumReviewError("exact crosswalk requires collections or archaeology expertise")
        if actor["conflict_status"] != "none_declared":
            raise MuseumReviewError("exact crosswalk requires no declared or unknown conflict")
        if not crosswalk["evidence"]:
            raise MuseumReviewError("exact crosswalk requires non-empty evidence")
        if crosswalk["counterevidence_checked"] is not True:
            raise MuseumReviewError("exact crosswalk requires a counterevidence check")


def _subject_images(subject: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        image["image_id"]: image
        for group in subject["view_groups"]
        for image in group["evidence_images"]
    }


def _opaque_id(prefix: str, key: bytes, *parts: str) -> str:
    message = "\0".join(parts).encode("utf-8")
    token = hmac.new(key, message, hashlib.sha256).hexdigest()[:24]
    return f"{prefix}:{token}"


def _opaque_sort_key(key: bytes, *parts: str) -> str:
    return hmac.new(key, "\0".join(parts).encode("utf-8"), hashlib.sha256).hexdigest()


def _reject_keys(value: object, forbidden: set[str], label: str) -> None:
    if isinstance(value, Mapping):
        overlap = forbidden.intersection(value)
        if overlap:
            raise MuseumReviewError(f"{label} contains forbidden fields: {sorted(overlap)}")
        for child in value.values():
            _reject_keys(child, forbidden, label)
    elif isinstance(value, list):
        for child in value:
            _reject_keys(child, forbidden, label)


def _require_closed_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise MuseumReviewError(f"{label} keys mismatch; missing={missing}, unknown={unknown}")


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MuseumReviewError(f"{label} must be an object")
    return value


def _require_stable_id(value: object, label: str) -> None:
    if not isinstance(value, str) or not STABLE_ID_PATTERN.fullmatch(value):
        raise MuseumReviewError(f"{label} must be a stable identifier")


def _require_checksum(value: object, label: str) -> None:
    if not isinstance(value, str) or not CHECKSUM_PATTERN.fullmatch(value):
        raise MuseumReviewError(f"{label} must be a SHA-256 checksum")


def _require_safe_relative_path(value: object, label: str) -> None:
    if not isinstance(value, str) or not SAFE_RELATIVE_PATH_PATTERN.fullmatch(value):
        raise MuseumReviewError(f"{label} must be a safe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise MuseumReviewError(f"{label} must not escape its packet root")


def _require_nonnegative_integer(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MuseumReviewError(f"{label} must be a nonnegative integer")


def _require_canonical_utc(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MuseumReviewError(f"{label} must be a canonical UTC date-time")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise MuseumReviewError(f"{label} must be a valid date-time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MuseumReviewError(f"{label} must include a UTC offset")
    canonical = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise MuseumReviewError(f"{label} must use canonical UTC form")
