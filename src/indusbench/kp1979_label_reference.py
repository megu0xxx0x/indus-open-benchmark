"""Proposal-free KP1979 label-reference assignments and review verification."""

from __future__ import annotations

import copy
import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from .io import decode_json, encode_json
from .kp1979 import (
    MAX_CONTRACT_BYTES,
    MAX_PAGE_MAP_BYTES,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    verify_kp1979_source,
)
from .kp1982_layout import crop_canonical_pbm
from .schema_validation import validate_schema_instance

JsonObject = dict[str, Any]
BBox = tuple[int, int, int, int]

ASSIGNMENT_SCHEMA = "kp1979-label-reference-assignment.schema.json"
REVIEW_SCHEMA = "kp1979-label-reference-review.schema.json"
MAX_ASSIGNMENT_BYTES = 2 * 1024 * 1024
MAX_REVIEW_BYTES = 16 * 1024 * 1024
MAX_NESTING_DEPTH = 64
MAX_TOTAL_REVIEW_CROP_BYTES = 128 * 1024 * 1024
MAX_TARGET_BBOX_WIDTH = 320
MAX_TARGET_BBOX_HEIGHT = 128
CROP_ENCODING = (
    "P4 with exact dimensions; row-major top-to-bottom, left-to-right, "
    "black=1, MSB-first, zero unused low bits"
)

PARTITION_PAGES: Final[dict[str, tuple[int, ...]]] = {
    "development": (20, 22, 79, 129, 131, 180),
    "future_evaluation": (8, 78, 99, 128, 130, 175),
}
_PARTITION_PROTOCOL_KEYS: Final[dict[str, str]] = {
    "development": "development_pdf_pages",
    "future_evaluation": "future_evaluation_pdf_pages",
}
_MANIFEST_IDS: Final[dict[str, str]] = {
    "development": "KP1979:LABEL-REFERENCE-ASSIGNMENT:DEVELOPMENT:V1",
    "future_evaluation": "KP1979:LABEL-REFERENCE-ASSIGNMENT:FUTURE-EVALUATION:V1",
}
_STATUS = "private_answer_free_label_reference_assignment_requires_exact_byte_verification"
_ASSIGNMENT_SCOPE = (
    "proposal-free physical-page and lane roster for recording visible target-label "
    "geometry only; no detector output, proposed label or row geometry, OCR, identifier, "
    "code, sign, reading direction, language, meaning, translation, accepted observation, "
    "evaluation result, or decipherment inference is present"
)
_REVIEW_SCOPE = (
    "tight half-open geometry, [y0,y1) vertical reference intervals, and exact "
    "source-pixel evidence for complete visible two-line corpus-row label blocks consisting "
    "of the upper printed identifier and lower source-local code or qualifier line or "
    "lines, including typographically attached punctuation, prime marks, and question "
    "marks; record only visible label ink and uncertainty when a component is missing, and "
    "retain visible row labels whose associated sign region is damaged, hatched, auxiliary "
    "or nonlinguistic, broken, or later excluded; exclude adjacent sign drawings, hatching "
    "or damage blocks, row baselines, headings, page numbers, prose, sign-list rank or "
    "identifier cells, and auxiliary-grid cells; record labels top-to-bottom within two "
    "physical lanes without assumed lane fill; no page role, layout class, scan band, "
    "detector output, proposal geometry, OCR, identifier value, code value, sign value, "
    "reading direction, language, meaning, translation, accepted observation, evaluation "
    "result, or decipherment inference is present"
)
_COORDINATE_POLICY: Final[JsonObject] = {
    "page_width": PAGE_WIDTH,
    "page_height": PAGE_HEIGHT,
    "coordinate_space": "decoded_embedded_page_image_pixels",
    "origin": "top_left",
    "rectangle_encoding": "half_open_xyxy_integer",
    "visible_target_definition": (
        "one complete visible two-line corpus-row label block: the upper printed identifier "
        "together with the lower source-local code or qualifier line or lines"
    ),
    "target_inclusion_rule": (
        "include punctuation, prime marks, and question marks typographically attached to "
        "the row-label lines; when a component is not visible, include only visible label "
        "ink and mark damage or uncertainty; keep a visible corpus-row label as a geometry "
        "target even when its associated sign region is damaged, fully hatched, auxiliary "
        "or nonlinguistic, broken, or later excluded from linguistic sequences"
    ),
    "target_exclusion_rule": (
        "exclude adjacent sign drawings, hatching or damage blocks, row baselines, "
        "headings, page numbers, prose, sign-list rank or identifier cells, and "
        "auxiliary-grid cells"
    ),
    "target_bbox_rule": (
        "tight half-open bbox around only visible two-line row-label ink; black ink must "
        "touch all four bbox edges"
    ),
    "target_bbox_size_rule": (
        "width at most 320 pixels and height at most 128 pixels; whitespace-only, "
        "sign-inclusive, and full-lane rectangles are invalid"
    ),
    "vertical_reference_interval_rule": "[bbox.y0,bbox.y1)",
    "physical_lane_order": "left_then_right_zero_based",
    "within_lane_observation_order": "top_to_bottom_zero_based",
    "lane_fill_rule": (
        "record only observed visible targets; never synthesize or assume lane fill"
    ),
    "physical_lane_bboxes": [
        [0, 0, PAGE_WIDTH // 2, PAGE_HEIGHT],
        [PAGE_WIDTH // 2, 0, PAGE_WIDTH, PAGE_HEIGHT],
    ],
    "canonical_crop_encoding": CROP_ENCODING,
    "downstream_scoring_policy": (
        "absent_and_must_be_frozen_separately_before_future_evaluation_values_are_opened"
    ),
}
_WITHHELD_FIELDS: Final[tuple[str, ...]] = (
    "all_page_roles",
    "all_layout_classes",
    "all_scan_bands",
    "all_detector_output",
    "all_proposal_geometry",
    "all_target_label_values",
    "all_target_label_counts",
    "all_ocr_output",
    "all_identifier_values",
    "all_code_values",
    "all_sign_values",
    "all_reading_direction_values",
    "all_language_values",
    "all_meaning_values",
    "all_translation_values",
    "all_accepted_observations",
)
_ACCESS_DECLARATION_KEYS = frozenset(
    {
        "source_page_pixels",
        "detector_output",
        "kp1979_57_page_row_assignment",
        "ocr_output",
        "peer_review_record",
        "existing_label_reference",
        "page_role_expectations",
        "scoring_expectations",
    }
)
_PROHIBITED_ACCESS_KEYS = _ACCESS_DECLARATION_KEYS - {"source_page_pixels"}
_ACCESS_STATES = frozenset({"not_seen", "seen", "unknown"})
_ASSIGNMENT_ASSURANCES: Final[JsonObject] = {
    "source_contract_exact_bytes_verified": True,
    "page_map_exact_bytes_verified": True,
    "source_pdf_exact_bytes_verified": True,
    "selected_page_bitmaps_verified": True,
    "answer_values_withheld": True,
    "page_roles_disclosed": False,
    "layout_classes_disclosed": False,
    "scan_bands_disclosed": False,
    "detector_output_present": False,
    "proposal_geometry_present": False,
    "target_label_values_present": False,
    "target_label_counts_disclosed": False,
    "human_review_started_verified": False,
    "human_review_complete_verified": False,
    "human_authorship_verified": False,
    "real_world_independence_verified": False,
    "reviewer_blinding_verified": False,
    "label_geometry_accepted": False,
    "row_geometry_accepted": False,
    "reference_custody_verified": False,
    "detector_freeze_verified": False,
    "scorer_freeze_verified": False,
    "runtime_isolation_verified": False,
    "public_release_authorized": False,
    "evaluation_admissible": False,
    "decipherment": False,
    "prize_submission_eligible": False,
}
_FORBIDDEN_ASSIGNMENT_KEYS = frozenset(
    {
        "candidate_count",
        "candidate_y",
        "detector",
        "detector_output",
        "identifier",
        "identifier_value",
        "label_bbox",
        "label_count",
        "labels",
        "layout_class",
        "ocr",
        "ocr_output",
        "page_role",
        "proposal",
        "proposal_bbox",
        "proposal_scan_bands",
        "row_bbox",
        "scan_band",
        "sign",
        "sign_sequence",
        "slot_count",
        "slots",
    }
)
_FORBIDDEN_REVIEW_KEYS = frozenset(
    {
        "accepted_observation",
        "code",
        "code_value",
        "detector",
        "detector_output",
        "gloss",
        "identifier",
        "identifier_value",
        "language",
        "layout_class",
        "meaning",
        "ocr",
        "ocr_output",
        "page_role",
        "phonetic",
        "phonetic_value",
        "proposal",
        "proposal_bbox",
        "raw_text",
        "reading_direction",
        "reading_order",
        "scan_band",
        "sign",
        "sign_id",
        "sign_sequence",
        "transcription",
        "translation",
    }
)
_BIDI_CLASSES = frozenset(
    {
        "LRE",
        "RLE",
        "LRO",
        "RLO",
        "PDF",
        "LRI",
        "RLI",
        "FSI",
        "PDI",
    }
)


class KP1979LabelReferenceError(ValueError):
    """Raised when label-reference evidence violates its closed contract."""


def build_label_reference_assignment(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
    source_bytes: bytes,
    page_pbm_bytes: Iterable[tuple[int, bytes]],
    *,
    partition: str,
) -> JsonObject:
    """Build one deterministic six-page assignment without detector output or answers."""

    if partition not in PARTITION_PAGES:
        raise KP1979LabelReferenceError("unknown KP1979 label-reference partition")
    try:
        source_summary = verify_kp1979_source(
            source_contract_bytes,
            page_map_bytes,
            source_bytes,
        )
    except ValueError as error:
        raise KP1979LabelReferenceError(
            "KP1979 label-reference source verification failed"
        ) from error
    if (
        source_summary.get("valid") is not True
        or source_summary.get("source_snapshot_match") is not True
        or source_summary.get("page_map_snapshot_match") is not True
        or source_summary.get("layout_candidates_accepted") is not False
        or source_summary.get("decipherment") is not False
    ):
        raise KP1979LabelReferenceError(
            "KP1979 label-reference source verifier returned an incomplete assurance state"
        )

    source_contract = _decode_object(
        source_contract_bytes,
        label="KP1979 source contract",
        max_bytes=MAX_CONTRACT_BYTES,
    )
    page_map = _decode_object(
        page_map_bytes,
        label="KP1979 page map",
        max_bytes=MAX_PAGE_MAP_BYTES,
    )
    source = _mapping(source_contract.get("source"), "source contract source")
    expected_pages = _selected_page_entries(page_map, partition=partition)
    page_bitmaps, _pages = _consume_selected_pages(
        expected_pages,
        page_pbm_bytes,
    )
    assignment: JsonObject = {
        "schema_version": "0.1.0",
        "manifest_id": _MANIFEST_IDS[partition],
        "status": _STATUS,
        "scientific_scope": _ASSIGNMENT_SCOPE,
        "protocol_partition": partition,
        "source_contract": {
            "id": _string(source_contract.get("contract_id"), "source contract id"),
            "sha256": _tagged_sha256(source_contract_bytes),
            "byte_size": len(source_contract_bytes),
        },
        "page_map": {
            "id": _string(page_map.get("map_id"), "page map id"),
            "sha256": _tagged_sha256(page_map_bytes),
            "byte_size": len(page_map_bytes),
        },
        "source_pdf": {
            "source_id": _string(source.get("source_id"), "source id"),
            "sha256": _tagged_sha256(source_bytes),
            "byte_size": len(source_bytes),
        },
        "page_bitmaps": page_bitmaps,
        "coordinate_policy": copy.deepcopy(_COORDINATE_POLICY),
        "withheld_fields": list(_WITHHELD_FIELDS),
        "assurances": dict(_ASSIGNMENT_ASSURANCES),
    }
    _reject_forbidden_keys(
        assignment,
        forbidden=_FORBIDDEN_ASSIGNMENT_KEYS,
        label="KP1979 label-reference assignment",
    )
    _require_schema(assignment, ASSIGNMENT_SCHEMA, "generated label-reference assignment")
    if len(encode_json(assignment)) > MAX_ASSIGNMENT_BYTES:
        raise KP1979LabelReferenceError(
            "generated KP1979 label-reference assignment exceeds its byte limit"
        )
    return assignment


def verify_label_reference_assignment_bytes(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
    source_bytes: bytes,
    page_pbm_bytes: Iterable[tuple[int, bytes]],
    assignment_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and exact-byte-check one untrusted six-page assignment."""

    assignment = _decode_schema_bytes(
        assignment_bytes,
        label="KP1979 label-reference assignment",
        schema_filename=ASSIGNMENT_SCHEMA,
        max_bytes=MAX_ASSIGNMENT_BYTES,
        forbidden_keys=_FORBIDDEN_ASSIGNMENT_KEYS,
    )
    partition = _string(assignment.get("protocol_partition"), "protocol partition")
    expected = build_label_reference_assignment(
        source_contract_bytes,
        page_map_bytes,
        source_bytes,
        page_pbm_bytes,
        partition=partition,
    )
    if assignment != expected or assignment_bytes != encode_json(expected):
        raise KP1979LabelReferenceError(
            "KP1979 label-reference assignment differs from canonical source recomputation"
        )
    return {
        "valid": True,
        "claim_class": "private_kp1979_label_reference_assignment_only",
        "source_snapshot_match": True,
        "page_map_snapshot_match": True,
        "selected_page_pixels_verified": True,
        "assignment_canonical_bytes_verified": True,
        "answer_values_withheld": True,
        "detector_output_absent": True,
        "proposal_geometry_absent": True,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "reference_custody_verified": False,
        "detector_freeze_verified": False,
        "scorer_freeze_verified": False,
        "runtime_isolation_verified": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }


def validate_label_reference_review(
    review_value: Mapping[str, Any],
    assignment_value: Mapping[str, Any],
    page_pbm_bytes: Iterable[tuple[int, bytes]],
) -> None:
    """Validate review mappings without making exact-byte or authorship claims."""

    assignment = _mapping(assignment_value, "label-reference assignment")
    review = _mapping(review_value, "label-reference review")
    _reject_forbidden_keys(
        assignment,
        forbidden=_FORBIDDEN_ASSIGNMENT_KEYS,
        label="KP1979 label-reference assignment",
    )
    _reject_forbidden_keys(
        review,
        forbidden=_FORBIDDEN_REVIEW_KEYS,
        label="KP1979 label-reference review",
    )
    _validate_text_safety(review)
    _require_schema(assignment, ASSIGNMENT_SCHEMA, "label-reference assignment")
    _require_schema(review, REVIEW_SCHEMA, "label-reference review")
    _page_commitments, pages = _consume_assignment_pages(assignment, page_pbm_bytes)
    _validate_review_semantics(
        review,
        assignment,
        pages,
        expected_assignment_commitment=None,
    )


def verify_independent_label_reference_review_bytes(
    assignment_bytes: bytes,
    page_pbm_bytes: Iterable[tuple[int, bytes]],
    review_bytes: bytes,
) -> dict[str, bool | str]:
    """Verify one canonical pass against a proposal-free assignment and exact pixels."""

    assignment = _decode_schema_bytes(
        assignment_bytes,
        label="KP1979 label-reference assignment",
        schema_filename=ASSIGNMENT_SCHEMA,
        max_bytes=MAX_ASSIGNMENT_BYTES,
        forbidden_keys=_FORBIDDEN_ASSIGNMENT_KEYS,
    )
    _page_commitments, pages = _consume_assignment_pages(assignment, page_pbm_bytes)
    review = _decode_schema_bytes(
        review_bytes,
        label="KP1979 label-reference review",
        schema_filename=REVIEW_SCHEMA,
        max_bytes=MAX_REVIEW_BYTES,
        forbidden_keys=_FORBIDDEN_REVIEW_KEYS,
    )
    _validate_text_safety(review)
    expected_commitment: JsonObject = {
        "manifest_id": _string(assignment.get("manifest_id"), "assignment manifest id"),
        "sha256": _tagged_sha256(assignment_bytes),
        "byte_size": len(assignment_bytes),
    }
    _validate_review_semantics(
        review,
        assignment,
        pages,
        expected_assignment_commitment=expected_commitment,
    )
    return {
        "valid": True,
        "claim_class": "private_kp1979_label_reference_review_verification",
        "assignment_canonical_bytes_verified": True,
        "assignment_commitment_verified": True,
        "selected_page_pixels_verified": True,
        "review_canonical_bytes_verified": True,
        "review_roster_verified": True,
        "submitted_crop_bytes_recomputed": True,
        "opaque_record_ids_structurally_distinct": True,
        "authorship_declaration_recorded": True,
        "access_declaration_recorded": True,
        "authorship_declaration_verified": False,
        "access_declaration_verified": False,
        "actor_identity_verified": False,
        "human_review_started_verified": False,
        "human_review_complete_verified": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "reviewer_nonexposure_verified": False,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "identifiers_transcribed": False,
        "codes_transcribed": False,
        "sign_sequences_transcribed": False,
        "reading_direction_assigned": False,
        "source_custody_verified": False,
        "source_rights_verified": False,
        "reference_custody_verified": False,
        "detector_freeze_verified": False,
        "scorer_freeze_verified": False,
        "runtime_isolation_verified": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }


def _default_schema_path(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def _selected_page_entries(
    page_map: Mapping[str, Any],
    *,
    partition: str,
) -> tuple[Mapping[str, Any], ...]:
    protocol = _mapping(
        page_map.get("layout_evaluation_page_protocol"),
        "layout evaluation page protocol",
    )
    protocol_key = _PARTITION_PROTOCOL_KEYS[partition]
    protocol_pages = _list(protocol.get(protocol_key), protocol_key)
    expected_numbers = PARTITION_PAGES[partition]
    if tuple(protocol_pages) != expected_numbers:
        raise KP1979LabelReferenceError(
            "KP1979 page-map partition differs from the fixed six-page protocol"
        )
    pages = _list(page_map.get("pages"), "page map pages")
    by_number: dict[int, Mapping[str, Any]] = {}
    for value in pages:
        page = _mapping(value, "page map page")
        page_number = _integer(page.get("pdf_page_number"), "PDF page number")
        if page_number in by_number:
            raise KP1979LabelReferenceError("KP1979 page map contains a duplicate page")
        by_number[page_number] = page
    try:
        return tuple(by_number[number] for number in expected_numbers)
    except KeyError as error:
        raise KP1979LabelReferenceError(
            "KP1979 page map lacks a fixed label-reference page"
        ) from error


def _consume_selected_pages(
    expected_pages: Sequence[Mapping[str, Any]],
    page_pbm_bytes: Iterable[tuple[int, bytes]],
) -> tuple[list[JsonObject], dict[int, bytes]]:
    supplied = iter(page_pbm_bytes)
    commitments: list[JsonObject] = []
    pages: dict[int, bytes] = {}
    for expected in expected_pages:
        supplied_number, raw_bytes = _next_page(supplied)
        page_number = _integer(expected.get("pdf_page_number"), "PDF page number")
        if supplied_number != page_number:
            raise KP1979LabelReferenceError(
                "label-reference page bitmap order differs from its fixed partition"
            )
        if not isinstance(raw_bytes, bytes):
            raise KP1979LabelReferenceError(
                "label-reference page bitmap must be supplied as exact bytes"
            )
        expected_size = 4_276_113
        expected_sha256 = _string(
            expected.get("canonical_pbm_sha256"),
            "canonical PBM SHA-256",
        )
        actual_sha256 = _tagged_sha256(raw_bytes)
        if len(raw_bytes) != expected_size or actual_sha256 != expected_sha256:
            raise KP1979LabelReferenceError(
                "label-reference page bitmap differs from its page-map commitment"
            )
        page_index = _integer(expected.get("page_index"), "page index")
        commitments.append(
            {
                "page_index": page_index,
                "pdf_page_number": page_number,
                "canonical_pbm_sha256": actual_sha256,
                "byte_size": len(raw_bytes),
            }
        )
        pages[page_number] = raw_bytes
    try:
        next(supplied)
    except StopIteration:
        pass
    else:
        raise KP1979LabelReferenceError(
            "label-reference page bitmap iterator contains an unexpected extra page"
        )
    return commitments, pages


def _consume_assignment_pages(
    assignment: Mapping[str, Any],
    page_pbm_bytes: Iterable[tuple[int, bytes]],
) -> tuple[list[JsonObject], dict[int, bytes]]:
    partition = _string(assignment.get("protocol_partition"), "protocol partition")
    if partition not in PARTITION_PAGES:
        raise KP1979LabelReferenceError("unknown KP1979 label-reference partition")
    values = _list(assignment.get("page_bitmaps"), "assignment page bitmaps")
    if len(values) != 6:
        raise KP1979LabelReferenceError(
            "label-reference assignment must contain exactly six page commitments"
        )
    expected_pages = tuple(_mapping(value, "assignment page bitmap") for value in values)
    commitments, pages = _consume_selected_pages(expected_pages, page_pbm_bytes)
    if commitments != values:
        raise KP1979LabelReferenceError(
            "label-reference assignment page commitments are not canonical"
        )
    if tuple(value["pdf_page_number"] for value in commitments) != PARTITION_PAGES[partition]:
        raise KP1979LabelReferenceError(
            "label-reference assignment page roster differs from its partition"
        )
    return commitments, pages


def _validate_review_semantics(
    review: Mapping[str, Any],
    assignment: Mapping[str, Any],
    pages: Mapping[int, bytes],
    *,
    expected_assignment_commitment: Mapping[str, Any] | None,
) -> None:
    if review.get("scientific_scope") != _REVIEW_SCOPE:
        raise KP1979LabelReferenceError(
            "KP1979 label-reference review scientific_scope is not fail-closed"
        )
    if review.get("review_stage") != "independent_pass":
        raise KP1979LabelReferenceError(
            "KP1979 label-reference record is not an independent-pass record"
        )
    if review.get("authorship_declaration") not in {
        "human",
        "machine",
        "mixed",
        "unknown",
    }:
        raise KP1979LabelReferenceError("KP1979 label-reference authorship declaration is invalid")
    access_declaration = _mapping(
        review.get("access_declaration"),
        "access declaration",
    )
    if (
        set(access_declaration) != _ACCESS_DECLARATION_KEYS
        or access_declaration.get("source_page_pixels") != "seen"
        or any(access_declaration.get(key) not in _ACCESS_STATES for key in _PROHIBITED_ACCESS_KEYS)
    ):
        raise KP1979LabelReferenceError("KP1979 label-reference access declaration is invalid")
    identifiers = {
        _string(review.get("review_id"), "review id"),
        _string(review.get("review_assignment_id"), "review assignment id"),
        _string(review.get("actor_id"), "actor id"),
    }
    if len(identifiers) != 3:
        raise KP1979LabelReferenceError(
            "review, review-assignment, and actor identifiers must be structurally distinct"
        )
    partition = _string(assignment.get("protocol_partition"), "assignment partition")
    if review.get("protocol_partition") != partition:
        raise KP1979LabelReferenceError(
            "review partition differs from its label-reference assignment"
        )
    commitment = _mapping(
        review.get("label_reference_assignment"),
        "label-reference assignment commitment",
    )
    if expected_assignment_commitment is not None:
        if commitment != expected_assignment_commitment:
            raise KP1979LabelReferenceError(
                "review does not bind the supplied label-reference assignment bytes"
            )
    elif (
        commitment.get("manifest_id") != assignment.get("manifest_id")
        or commitment.get("byte_size") is None
        or commitment.get("sha256") is None
    ):
        raise KP1979LabelReferenceError("review assignment commitment is structurally inconsistent")

    assignment_pages = _list(assignment.get("page_bitmaps"), "assignment page bitmaps")
    review_pages = _list(review.get("pages"), "review pages")
    if len(assignment_pages) != 6 or len(review_pages) != 6:
        raise KP1979LabelReferenceError("review must bind exactly six assignment pages")
    _preflight_review_crop_budget(review_pages)
    unresolved_present = False
    for page_value, assignment_page_value in zip(
        review_pages,
        assignment_pages,
        strict=True,
    ):
        page = _mapping(page_value, "review page")
        assignment_page = _mapping(assignment_page_value, "assignment page")
        locator = (
            page.get("page_index"),
            page.get("pdf_page_number"),
        )
        expected_locator = (
            assignment_page.get("page_index"),
            assignment_page.get("pdf_page_number"),
        )
        if locator != expected_locator:
            raise KP1979LabelReferenceError(
                "review page roster differs from its label-reference assignment"
            )
        page_number = _integer(page.get("pdf_page_number"), "review PDF page number")
        page_bytes = pages.get(page_number)
        if page_bytes is None:
            raise KP1979LabelReferenceError("review cites an unknown page bitmap")
        lanes = _list(page.get("lanes"), "review page lanes")
        if len(lanes) != 2:
            raise KP1979LabelReferenceError("review page must contain two physical lanes")
        page_unresolved = False
        page_has_targets = False
        for expected_lane_index, lane_value in enumerate(lanes):
            lane = _mapping(lane_value, "review lane")
            if lane.get("lane_index") != expected_lane_index:
                raise KP1979LabelReferenceError("review lane roster is not left-then-right")
            lane_unresolved, lane_has_targets = _validate_review_lane(
                lane,
                page_bytes,
                lane_index=expected_lane_index,
            )
            page_unresolved = page_unresolved or lane_unresolved
            page_has_targets = page_has_targets or lane_has_targets
        expected_page_state = (
            "unresolved"
            if page_unresolved
            else "complete_with_targets"
            if page_has_targets
            else "complete_no_targets"
        )
        if page.get("review_state") != expected_page_state:
            raise KP1979LabelReferenceError("review page status contradicts its lane observations")
        unresolved_present = unresolved_present or page_unresolved

    limitations = set(_list(review.get("limitations"), "review limitations"))
    outcome = review.get("review_outcome")
    if outcome == "complete":
        if unresolved_present:
            raise KP1979LabelReferenceError(
                "complete review cannot contain unresolved observations"
            )
        if "incomplete_review" in limitations or "unresolved_observations_present" in limitations:
            raise KP1979LabelReferenceError("complete review has contradictory limitation codes")
    elif outcome == "complete_with_unresolved_observations":
        if not unresolved_present or "unresolved_observations_present" not in limitations:
            raise KP1979LabelReferenceError(
                "unresolved review outcome contradicts its observations"
            )
    elif outcome == "abstain":
        if not unresolved_present or "incomplete_review" not in limitations:
            raise KP1979LabelReferenceError(
                "abstained review must contain an unresolved observation and limitation"
            )
    else:
        raise KP1979LabelReferenceError("unknown label-reference review outcome")


def _validate_review_lane(
    lane: Mapping[str, Any],
    page_bytes: bytes,
    *,
    lane_index: int,
) -> tuple[bool, bool]:
    labels = _list(lane.get("visible_target_labels"), "visible target labels")
    previous_y1 = -1
    unresolved = False
    for expected_index, value in enumerate(labels):
        label = _mapping(value, "visible target label")
        if label.get("visual_label_index") != expected_index:
            raise KP1979LabelReferenceError("visible target labels are not contiguously indexed")
        bbox = _bbox(label.get("bbox"), "visible target label bbox")
        lane_x0 = lane_index * (PAGE_WIDTH // 2)
        lane_x1 = lane_x0 + (PAGE_WIDTH // 2)
        x0, y0, x1, y1 = bbox
        if not (lane_x0 <= x0 < x1 <= lane_x1 and 0 <= y0 < y1 <= PAGE_HEIGHT):
            raise KP1979LabelReferenceError(
                "visible target label bbox lies outside its physical lane"
            )
        if x1 - x0 > MAX_TARGET_BBOX_WIDTH or y1 - y0 > MAX_TARGET_BBOX_HEIGHT:
            raise KP1979LabelReferenceError(
                "visible target label bbox exceeds the tight target size limit"
            )
        if y0 < previous_y1:
            raise KP1979LabelReferenceError("visible target label y intervals overlap")
        previous_y1 = y1
        y_interval = _list(label.get("y_interval"), "visible target y interval")
        if y_interval != [y0, y1]:
            raise KP1979LabelReferenceError("visible target y interval differs from bbox [y0,y1)")
        geometry_status = label.get("geometry_status")
        reason_codes = set(_list(label.get("reason_codes"), "label reason codes"))
        if geometry_status == "unresolved":
            if not reason_codes or reason_codes == {"clear_visible_target_label"}:
                raise KP1979LabelReferenceError(
                    "unresolved label geometry lacks an unresolved reason"
                )
            unresolved = True
        elif geometry_status == "observed":
            if reason_codes.intersection(
                {
                    "boundary_ambiguous",
                    "multiple_visible_groups",
                    "crop_extent_unresolved",
                }
            ):
                raise KP1979LabelReferenceError(
                    "observed label geometry has a contradictory unresolved reason"
                )
        else:
            raise KP1979LabelReferenceError("unknown label geometry status")
        _verify_crop_commitment(label, page_bytes, bbox=bbox)
    lane_state = lane.get("review_state")
    unresolved_reasons = _list(
        lane.get("unresolved_reason_codes"),
        "lane unresolved reason codes",
    )
    if lane_state == "unresolved":
        if not unresolved_reasons:
            raise KP1979LabelReferenceError("unresolved lane lacks a structured reason")
        unresolved = True
    elif lane_state == "complete_no_targets":
        if labels or unresolved_reasons:
            raise KP1979LabelReferenceError("complete-no-targets lane contradicts its observations")
    elif lane_state == "complete_with_targets":
        if not labels or unresolved_reasons:
            raise KP1979LabelReferenceError(
                "complete-with-targets lane contradicts its observations"
            )
    else:
        raise KP1979LabelReferenceError("unknown lane review state")
    if lane_state != "unresolved" and unresolved:
        raise KP1979LabelReferenceError("complete lane cannot contain unresolved label geometry")
    return unresolved, bool(labels)


def _preflight_review_crop_budget(review_pages: Sequence[Any]) -> None:
    total = 0
    for page_value in review_pages:
        page = _mapping(page_value, "review page")
        for lane_value in _list(page.get("lanes"), "review page lanes"):
            lane = _mapping(lane_value, "review lane")
            for label_value in _list(
                lane.get("visible_target_labels"),
                "visible target labels",
            ):
                label = _mapping(label_value, "visible target label")
                bbox = _bbox(label.get("bbox"), "visible target label bbox")
                if (
                    bbox[2] - bbox[0] > MAX_TARGET_BBOX_WIDTH
                    or bbox[3] - bbox[1] > MAX_TARGET_BBOX_HEIGHT
                ):
                    raise KP1979LabelReferenceError(
                        "visible target label bbox exceeds the tight target size limit"
                    )
                expected_size = _expected_crop_byte_size(bbox)
                if label.get("crop_byte_size") != expected_size:
                    raise KP1979LabelReferenceError(
                        "visible target crop byte size is not canonical"
                    )
                total += expected_size
                if total > MAX_TOTAL_REVIEW_CROP_BYTES:
                    raise KP1979LabelReferenceError(
                        "label-reference review crop budget exceeds its limit"
                    )


def _verify_crop_commitment(
    label: Mapping[str, Any],
    page_bytes: bytes,
    *,
    bbox: BBox,
) -> None:
    try:
        crop = crop_canonical_pbm(
            page_bytes,
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=bbox,
        )
    except ValueError as error:
        raise KP1979LabelReferenceError("visible target crop could not be recomputed") from error
    if label.get("crop_sha256") != _tagged_sha256(crop) or label.get("crop_byte_size") != len(crop):
        raise KP1979LabelReferenceError(
            "visible target crop commitment differs from exact page pixels"
        )
    if not _crop_has_black_ink_on_all_edges(crop, bbox=bbox):
        raise KP1979LabelReferenceError(
            "visible target bbox is not tight to black ink on all four edges"
        )


def _crop_has_black_ink_on_all_edges(crop: bytes, *, bbox: BBox) -> bool:
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    header = f"P4\n{width} {height}\n".encode("ascii")
    if not crop.startswith(header):
        return False
    payload = memoryview(crop)[len(header) :]
    row_bytes = (width + 7) // 8
    if len(payload) != row_bytes * height:
        return False

    def black(x: int, y: int) -> bool:
        value = payload[y * row_bytes + x // 8]
        return bool(value & (1 << (7 - (x % 8))))

    return (
        any(black(x, 0) for x in range(width))
        and any(black(x, height - 1) for x in range(width))
        and any(black(0, y) for y in range(height))
        and any(black(width - 1, y) for y in range(height))
    )


def _expected_crop_byte_size(bbox: BBox) -> int:
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    if width <= 0 or height <= 0:
        raise KP1979LabelReferenceError("visible target bbox is empty")
    return len(f"P4\n{width} {height}\n".encode("ascii")) + ((width + 7) // 8) * height


def _decode_schema_bytes(
    raw_bytes: bytes,
    *,
    label: str,
    schema_filename: str,
    max_bytes: int,
    forbidden_keys: frozenset[str],
) -> JsonObject:
    value = _decode_object(raw_bytes, label=label, max_bytes=max_bytes)
    _reject_forbidden_keys(value, forbidden=forbidden_keys, label=label)
    _require_schema(value, schema_filename, label)
    if raw_bytes != encode_json(value):
        raise KP1979LabelReferenceError(f"{label} is not canonical JSON")
    return value


def _decode_object(raw_bytes: bytes, *, label: str, max_bytes: int) -> JsonObject:
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1979LabelReferenceError(f"{label} has an invalid byte length")
    try:
        value = decode_json(raw_bytes, source=label)
    except (RecursionError, ValueError) as error:
        raise KP1979LabelReferenceError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1979LabelReferenceError(f"{label} must decode to an object")
    return value


def _require_schema(
    value: Mapping[str, Any],
    schema_filename: str,
    label: str,
) -> None:
    try:
        issues = validate_schema_instance(value, _default_schema_path(schema_filename))
    except RecursionError as error:
        raise KP1979LabelReferenceError(f"{label} exceeds the safe structural depth") from error
    if issues:
        raise KP1979LabelReferenceError(f"{label} schema invalid at {issues[0].path}")


def _reject_forbidden_keys(
    value: object,
    *,
    forbidden: frozenset[str],
    label: str,
) -> None:
    pending: list[tuple[object, int, tuple[str, ...]]] = [(value, 0, ())]
    while pending:
        current, depth, path = pending.pop()
        if depth > MAX_NESTING_DEPTH:
            raise KP1979LabelReferenceError(f"{label} nesting exceeds its limit")
        if isinstance(current, Mapping):
            for key, child in current.items():
                child_path = (*path, key)
                declaration_exception = path == ("access_declaration",) and key in {
                    "detector_output",
                    "ocr_output",
                }
                if key in forbidden and not declaration_exception:
                    raise KP1979LabelReferenceError(
                        f"{label} contains a forbidden answer or proposal field"
                    )
                if key == "decipherment" and child_path != (
                    "assurances",
                    "decipherment",
                ):
                    raise KP1979LabelReferenceError(
                        f"{label} contains a forbidden interpretive field"
                    )
                pending.append((child, depth + 1, child_path))
        elif isinstance(current, list):
            pending.extend((child, depth + 1, path) for child in current)


def _validate_text_safety(value: object) -> None:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, str) and any(
            ord(character) < 0x20
            or ord(character) == 0x7F
            or unicodedata.bidirectional(character) in _BIDI_CLASSES
            for character in current
        ):
            raise KP1979LabelReferenceError("label-reference review contains unsafe text controls")


def _next_page(iterator: Iterator[tuple[int, bytes]]) -> tuple[int, bytes]:
    try:
        value = next(iterator)
    except StopIteration as error:
        raise KP1979LabelReferenceError(
            "label-reference page bitmap iterator ended early"
        ) from error
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], int)
        or isinstance(value[0], bool)
    ):
        raise KP1979LabelReferenceError("label-reference page bitmap iterator entry is malformed")
    return value


def _tagged_sha256(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1979LabelReferenceError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise KP1979LabelReferenceError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1979LabelReferenceError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1979LabelReferenceError(f"{label} must be an integer")
    return value


def _bbox(value: object, label: str) -> BBox:
    values = _list(value, label)
    if len(values) != 4:
        raise KP1979LabelReferenceError(f"{label} must contain four integers")
    return (
        _integer(values[0], label),
        _integer(values[1], label),
        _integer(values[2], label),
        _integer(values[3], label),
    )
