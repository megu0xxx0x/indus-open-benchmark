"""Proposal-only row assignments for the KP1979 identifier-order base rendering."""

from __future__ import annotations

import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .kp1979 import (
    MAX_CONTRACT_BYTES,
    MAX_PAGE_MAP_BYTES,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    audit_kp1979_layout,
    detect_kp1979_page_layout,
)
from .kp1982_layout import crop_canonical_pbm
from .schema_validation import validate_schema_instance

ASSIGNMENT_SCHEMA = "kp1979-row-assignment.schema.json"
MAX_ASSIGNMENT_BYTES = 16 * 1024 * 1024
MANIFEST_ID = "KP1979:BASE:ROW-ASSIGNMENT:V1"
STATUS = "private_proposal_only_row_assignment_requires_independent_manual_reference"
SCIENTIFIC_SCOPE = (
    "proposal-only label and row crop assignment for the fixed KP1979 identifier-order "
    "base rendering; no OCR, identifier, code, sign, occupancy, reading direction, "
    "language, meaning, translation, accepted observation, or decipherment inference is present"
)
FIRST_BASE_PDF_PAGE = 22
LAST_BASE_PDF_PAGE = 78
BASE_PAGE_COUNT = LAST_BASE_PDF_PAGE - FIRST_BASE_PDF_PAGE + 1
ROW_VERTICAL_PADDING_PIXELS = 36
MAX_SLOT_COUNT = 5_000
MAX_ASSIGNMENT_NESTING_DEPTH = 64
WITHHELD_FIELDS = (
    "all_ocr_output",
    "all_identifier_values",
    "all_code_values",
    "all_sign_values",
    "all_occupancy_values",
    "all_reading_direction_values",
    "all_language_values",
    "all_meaning_values",
    "all_translation_values",
    "all_accepted_observations",
    "all_external_manual_row_values",
)
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "accepted_code",
        "accepted_identifier",
        "accepted_meaning",
        "accepted_observation",
        "accepted_occupancy",
        "accepted_sign",
        "accepted_translation",
        "canonical_digits",
        "code",
        "code_proposal",
        "code_value",
        "identifier",
        "identifier_proposal",
        "identifier_value",
        "language",
        "meaning",
        "occupancy",
        "occupancy_proposal",
        "ocr",
        "ocr_output",
        "phonetic_value",
        "raw_text",
        "reading_direction",
        "reading_order",
        "sign",
        "sign_id",
        "sign_sequence",
        "transcription",
        "translation",
    }
)

JsonObject = dict[str, Any]
BBox = tuple[int, int, int, int]


class KP1979RowAssignmentError(ValueError):
    """Raised when a KP1979 row assignment violates the closed proposal-only contract."""


def _default_schema_path() -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / ASSIGNMENT_SCHEMA
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(
        f"schemas/{ASSIGNMENT_SCHEMA}"
    )
    return Path(str(package_candidate))


def build_row_assignment(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
    source_bytes: bytes,
    audit_page_pbm_bytes: Iterable[tuple[int, bytes]],
    base_page_pbm_bytes: Iterable[tuple[int, bytes]],
) -> JsonObject:
    """Build a deterministic, answer-free row assignment from exact public source pixels."""

    try:
        audit_summary = audit_kp1979_layout(
            source_contract_bytes,
            page_map_bytes,
            source_bytes,
            audit_page_pbm_bytes,
        )
    except ValueError as error:
        raise KP1979RowAssignmentError(
            "KP1979 full-page source and negative-control audit failed"
        ) from error
    required_audit_results = (
        "valid",
        "source_snapshot_match",
        "page_map_snapshot_match",
        "all_mapped_page_pixels_verified",
        "selected_page_layout_status_gates_passed",
        "normal_page_detector_gates_passed",
    )
    if any(audit_summary.get(field) is not True for field in required_audit_results):
        raise KP1979RowAssignmentError(
            "KP1979 full-page audit did not attest every required source and layout gate"
        )
    required_audit_nonclaims = (
        "candidate_counts_disclosed",
        "layout_candidates_accepted",
        "identifiers_transcribed",
        "sign_sequences_transcribed",
        "three_way_reconciliation_complete",
        "decipherment",
    )
    if any(audit_summary.get(field) is not False for field in required_audit_nonclaims):
        raise KP1979RowAssignmentError(
            "KP1979 full-page audit did not preserve every required scientific nonclaim"
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
    base_pages = _base_page_entries(page_map)
    selected_page_bitmaps, slots = _build_base_slots(
        base_pages,
        page_map=page_map,
        base_page_pbm_bytes=base_page_pbm_bytes,
    )

    source = _mapping(source_contract.get("source"), "source contract source")
    evaluation_protocol = _mapping(
        page_map.get("layout_evaluation_page_protocol"),
        "layout evaluation page protocol",
    )
    assignment: JsonObject = {
        "schema_version": "0.1.0",
        "manifest_id": MANIFEST_ID,
        "status": STATUS,
        "scientific_scope": SCIENTIFIC_SCOPE,
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
        "layout_evaluation_page_protocol": dict(evaluation_protocol),
        "selected_page_bitmaps": selected_page_bitmaps,
        "crop_policy": {
            "algorithm": "kp1979-label-slot-row-crops-v1",
            "coordinate_space": "decoded_embedded_page_image_pixels",
            "origin": "top_left",
            "rectangle_encoding": "half_open_xyxy_integer",
            "canonical_crop_encoding": (
                "P4 with exact dimensions; row-major top-to-bottom, left-to-right, "
                "black=1, MSB-first, zero unused low bits"
            ),
            "lane_order": "left_then_right_zero_based",
            "visual_row_order": "top_to_bottom_zero_based_within_lane",
            "label_crop_role": "proposal_label_locator_only",
            "row_crop_role": "proposal_review_context_only_not_accepted_row_evidence",
            "row_horizontal_rule": (
                "x0=0 for lane 0 or 2440 for lane 1; x1=proposed_label_bbox.x1"
            ),
            "row_vertical_rule": (
                "y0=max(0,proposed_label_bbox.y0-36); y1=min(7010,proposed_label_bbox.y1+36)"
            ),
            "row_vertical_padding_pixels": ROW_VERTICAL_PADDING_PIXELS,
            "bbox_status": "proposal_only_requires_independent_manual_reference",
        },
        "withheld_fields": list(WITHHELD_FIELDS),
        "slots": slots,
        "assurances": {
            "source_contract_exact_bytes_verified": True,
            "page_map_exact_bytes_verified": True,
            "source_pdf_exact_bytes_verified": True,
            "audit_page_bitmaps_verified": True,
            "audit_layout_gates_passed": True,
            "selected_base_page_bitmaps_verified": True,
            "proposal_geometry_only": True,
            "label_geometry_accepted": False,
            "row_geometry_accepted": False,
            "occupancy_accepted": False,
            "human_review_complete": False,
            "reviewer_independence_verified": False,
            "identifiers_transcribed": False,
            "codes_transcribed": False,
            "sign_sequences_transcribed": False,
            "reading_direction_assigned": False,
            "language_assigned": False,
            "meaning_assigned": False,
            "private_storage_verified": False,
            "public_release_authorized": False,
            "evaluation_admissible": False,
            "decipherment": False,
        },
    }
    _reject_answer_keys(assignment)
    issues = validate_schema_instance(assignment, _default_schema_path())
    if issues:
        first = issues[0]
        raise KP1979RowAssignmentError(f"generated KP1979 row assignment invalid at {first.path}")
    if len(encode_json(assignment)) > MAX_ASSIGNMENT_BYTES:
        raise KP1979RowAssignmentError("generated KP1979 row assignment exceeds its byte limit")
    return assignment


def verify_row_assignment_bytes(
    source_contract_bytes: bytes,
    page_map_bytes: bytes,
    source_bytes: bytes,
    audit_page_pbm_bytes: Iterable[tuple[int, bytes]],
    base_page_pbm_bytes: Iterable[tuple[int, bytes]],
    assignment_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and exact-byte-check one untrusted KP1979 row assignment."""

    assignment = _decode_object(
        assignment_bytes,
        label="KP1979 row assignment",
        max_bytes=MAX_ASSIGNMENT_BYTES,
    )
    _reject_answer_keys(assignment)
    issues = validate_schema_instance(assignment, _default_schema_path())
    if issues:
        first = issues[0]
        raise KP1979RowAssignmentError(f"KP1979 row assignment schema invalid at {first.path}")
    expected = build_row_assignment(
        source_contract_bytes,
        page_map_bytes,
        source_bytes,
        audit_page_pbm_bytes,
        base_page_pbm_bytes,
    )
    if assignment != expected or assignment_bytes != encode_json(expected):
        raise KP1979RowAssignmentError(
            "KP1979 row assignment bytes differ from canonical pixel recomputation"
        )
    return {
        "valid": True,
        "claim_class": "private_kp1979_row_assignment_only",
        "source_page_pixels_verified": True,
        "audit_page_layout_gates_passed": True,
        "base_page_pixels_verified": True,
        "assignment_canonical_bytes_verified": True,
        "proposal_geometry_only": True,
        "machine_answer_values_withheld": True,
        "label_geometry_accepted": False,
        "row_geometry_accepted": False,
        "human_review_complete": False,
        "reviewer_independence_verified": False,
        "identifiers_transcribed": False,
        "codes_transcribed": False,
        "sign_sequences_transcribed": False,
        "reading_direction_assigned": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
    }


def _base_page_entries(page_map: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = _list(page_map.get("pages"), "page map pages")
    pages: list[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        page = _mapping(value, f"page map page {index}")
        if page.get("corpus_sequence_role") == "base_rendering":
            pages.append(page)
    if len(pages) != BASE_PAGE_COUNT:
        raise KP1979RowAssignmentError("page map does not contain the fixed 57-page base rendering")
    expected_numbers = list(range(FIRST_BASE_PDF_PAGE, LAST_BASE_PDF_PAGE + 1))
    observed_numbers = [
        _integer(page.get("pdf_page_number"), "base PDF page number") for page in pages
    ]
    if observed_numbers != expected_numbers:
        raise KP1979RowAssignmentError("base-rendering pages are not the fixed PDF pages 22-78")
    for page in pages:
        if (
            page.get("page_role") != "corpus_data"
            or page.get("layout_class") != "identifier_order_2_column_labels_right"
            or page.get("label_side") != "right"
        ):
            raise KP1979RowAssignmentError("base-rendering page semantics are not fixed")
    return pages


def _build_base_slots(
    base_pages: Sequence[Mapping[str, Any]],
    *,
    page_map: Mapping[str, Any],
    base_page_pbm_bytes: Iterable[tuple[int, bytes]],
) -> tuple[list[JsonObject], list[JsonObject]]:
    canonicalization = _mapping(page_map.get("canonicalization"), "page map canonicalization")
    expected_pbm_size = _integer(
        canonicalization.get("canonical_pbm_byte_size"),
        "canonical PBM byte size",
    )
    supplied = iter(base_page_pbm_bytes)
    page_commitments: list[JsonObject] = []
    slots: list[JsonObject] = []
    seen_slot_ids: set[str] = set()

    for page in base_pages:
        supplied_page_number, page_bytes = _next_page(supplied)
        pdf_page_number = _integer(page.get("pdf_page_number"), "PDF page number")
        if supplied_page_number != pdf_page_number:
            raise KP1979RowAssignmentError(
                "base page bitmap order differs from fixed PDF pages 22-78"
            )
        if len(page_bytes) != expected_pbm_size:
            raise KP1979RowAssignmentError(
                f"base page {pdf_page_number} does not match its page-map commitment"
            )
        expected_page_sha256 = _string(
            page.get("canonical_pbm_sha256"),
            "canonical PBM SHA-256",
        )
        actual_page_sha256 = _tagged_sha256(page_bytes)
        if actual_page_sha256 != expected_page_sha256:
            raise KP1979RowAssignmentError(
                f"base page {pdf_page_number} does not match its page-map commitment"
            )

        result = detect_kp1979_page_layout(page, page_bytes)
        if result.detection_status != "proposed" or len(result.label_slot_lanes) != 2:
            raise KP1979RowAssignmentError(
                f"base page {pdf_page_number} did not produce two proposal lanes"
            )
        page_commitments.append(
            {
                "page_index": _integer(page.get("page_index"), "page index"),
                "pdf_page_number": pdf_page_number,
                "canonical_pbm_sha256": actual_page_sha256,
                "byte_size": len(page_bytes),
            }
        )
        for lane_index, lane in enumerate(result.label_slot_lanes):
            previous_label_y0 = -1
            for visual_row_index, label_bbox in enumerate(lane):
                if len(slots) >= MAX_SLOT_COUNT:
                    raise KP1979RowAssignmentError("KP1979 row proposal exceeds its slot limit")
                if label_bbox[1] <= previous_label_y0:
                    raise KP1979RowAssignmentError(
                        "KP1979 label proposals are not in stable top-to-bottom order"
                    )
                previous_label_y0 = label_bbox[1]
                slot = _build_slot(
                    page=page,
                    page_bytes=page_bytes,
                    lane_index=lane_index,
                    visual_row_index=visual_row_index,
                    label_bbox=label_bbox,
                )
                slot_id = _string(slot.get("slot_id"), "slot id")
                if slot_id in seen_slot_ids:
                    raise KP1979RowAssignmentError("KP1979 row proposal contains a duplicate slot")
                seen_slot_ids.add(slot_id)
                slots.append(slot)

    try:
        next(supplied)
    except StopIteration:
        pass
    else:
        raise KP1979RowAssignmentError(
            "base page bitmap iterator contains an unexpected extra page"
        )
    if not slots:
        raise KP1979RowAssignmentError("KP1979 row proposal contains no slots")
    return page_commitments, slots


def _build_slot(
    *,
    page: Mapping[str, Any],
    page_bytes: bytes,
    lane_index: int,
    visual_row_index: int,
    label_bbox: BBox,
) -> JsonObject:
    pdf_page_number = _integer(page.get("pdf_page_number"), "PDF page number")
    page_index = _integer(page.get("page_index"), "page index")
    if lane_index not in {0, 1}:
        raise KP1979RowAssignmentError("KP1979 row proposal lane index is invalid")
    if visual_row_index < 0 or visual_row_index > 99:
        raise KP1979RowAssignmentError("KP1979 visual row index exceeds its stable-ID range")

    label_x0, label_y0, label_x1, label_y1 = label_bbox
    lane_x0 = lane_index * (PAGE_WIDTH // 2)
    lane_x1 = lane_x0 + (PAGE_WIDTH // 2)
    if not (lane_x0 <= label_x0 < label_x1 <= lane_x1 and 0 <= label_y0 < label_y1 <= PAGE_HEIGHT):
        raise KP1979RowAssignmentError("proposed label bbox lies outside its page half")
    row_bbox: BBox = (
        lane_x0,
        max(0, label_y0 - ROW_VERTICAL_PADDING_PIXELS),
        label_x1,
        min(PAGE_HEIGHT, label_y1 + ROW_VERTICAL_PADDING_PIXELS),
    )
    try:
        label_crop = crop_canonical_pbm(
            page_bytes,
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=label_bbox,
        )
        row_crop = crop_canonical_pbm(
            page_bytes,
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=row_bbox,
        )
    except ValueError as error:
        raise KP1979RowAssignmentError("KP1979 row crop could not be reproduced") from error
    return {
        "slot_id": (f"KP1979:P{pdf_page_number:03d}:L{lane_index}:V{visual_row_index:02d}"),
        "page_index": page_index,
        "pdf_page_number": pdf_page_number,
        "lane_index": lane_index,
        "visual_row_index": visual_row_index,
        "proposed_label_bbox": list(label_bbox),
        "proposed_row_bbox": list(row_bbox),
        "label_crop_sha256": _tagged_sha256(label_crop),
        "label_crop_byte_size": len(label_crop),
        "row_crop_sha256": _tagged_sha256(row_crop),
        "row_crop_byte_size": len(row_crop),
    }


def _next_page(supplied: Iterator[tuple[int, bytes]]) -> tuple[int, bytes]:
    try:
        value = next(supplied)
    except StopIteration as error:
        raise KP1979RowAssignmentError(
            "base page bitmap iterator ended before PDF page 78"
        ) from error
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], int)
        or isinstance(value[0], bool)
        or not isinstance(value[1], bytes)
    ):
        raise KP1979RowAssignmentError("base page bitmap iterator yielded an invalid item")
    return value


def _decode_object(raw_bytes: bytes, *, label: str, max_bytes: int) -> JsonObject:
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1979RowAssignmentError(f"{label} has an invalid byte length")
    try:
        value = decode_json(raw_bytes, source=label)
    except (RecursionError, ValueError) as error:
        raise KP1979RowAssignmentError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1979RowAssignmentError(f"{label} must decode to an object")
    return value


def _reject_answer_keys(value: object) -> None:
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_ASSIGNMENT_NESTING_DEPTH:
            raise KP1979RowAssignmentError("KP1979 row assignment nesting exceeds its limit")
        if isinstance(current, Mapping):
            forbidden = _FORBIDDEN_OUTPUT_KEYS.intersection(current)
            if forbidden:
                raise KP1979RowAssignmentError("KP1979 row assignment contains an answer field")
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1979RowAssignmentError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise KP1979RowAssignmentError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1979RowAssignmentError(f"{label} must be a nonempty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1979RowAssignmentError(f"{label} must be an integer")
    return value


def _tagged_sha256(raw_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
