"""Exact-byte KP1982 Batch 0 bootstrap review and adjudication verification.

The reviewer-side boundary in this module deliberately accepts only the pinned,
proposal-value-stripped assignment and the two canonical page PBMs.  It never
accepts the layout proposal or a pre-existing sign inventory.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.resources
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .kp1982_bootstrap import (
    ASSIGNMENT_SCHEMA,
    EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE,
    EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
    MANIFEST_ID,
    MAX_ASSIGNMENT_BYTES,
)
from .kp1982_layout import crop_canonical_pbm
from .schema_validation import validate_schema_instance

JsonObject = dict[str, Any]

REVIEW_SCHEMA = "kp1982-bootstrap-review.schema.json"
SCHEMA_VERSION = "0.1.0"
MAX_REVIEW_BYTES = 16 * 1024 * 1024
MAX_TOTAL_REVIEW_CROP_BYTES = 128 * 1024 * 1024
PAGE_WIDTH = 4888
PAGE_HEIGHT = 6705
CELL_COUNT = 700
CROP_ENCODING = (
    "P4 with exact dimensions; row-major top-to-bottom, left-to-right, "
    "black=1, MSB-first, zero unused low bits"
)
SCIENTIFIC_SCOPE = (
    "visual sign-list inventory bootstrap observations only; no pre-existing sign "
    "inventory is a record dependency and no phonetic, language, semantic, meaning, "
    "translation, or decipherment assignment is present"
)

_COMPARISON_FIELDS = (
    "occupancy",
    "cell_geometry",
    "upper_catalog_rank",
    "lower_primary_identifier",
    "glyph_with_marks",
    "glyph_core",
    "printed_marks",
    "condition",
    "uncertainty",
)
_CELL_KEYS_BY_COMPARISON_FIELD = {
    "occupancy": "occupancy",
    "cell_geometry": "cell_geometry",
    "upper_catalog_rank": "raw_upper_catalog_rank",
    "lower_primary_identifier": "raw_lower_primary_identifier",
    "glyph_with_marks": "glyph_with_marks",
    "glyph_core": "glyph_core",
    "printed_marks": "printed_marks",
    "condition": "condition",
    "uncertainty": "uncertainty",
}
_FORBIDDEN_INTERPRETIVE_KEYS = frozenset(
    {
        "gloss",
        "language",
        "language_assignment",
        "meaning",
        "phonetic",
        "phonetic_value",
        "semantic_assignment",
        "translation",
    }
)
_FORBIDDEN_CIRCULAR_KEYS = frozenset(
    {
        "accepted_occupancy",
        "accepted_observation",
        "inventory",
        "inventory_id",
        "layout_proposal",
        "machine_identifier_proposal",
        "occupancy_proposal",
        "ocr",
        "ocr_output",
        "sign_id",
        "sign_inventory",
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
_UNRESOLVED_IDENTIFIER_STATUSES = frozenset({"unreadable", "unresolved"})
_CropCache = dict[tuple[int, tuple[int, int, int, int]], tuple[str, int]]


class KP1982BootstrapReviewError(ValueError):
    """Raised when bootstrap review evidence fails closed."""


def sha256_bytes(raw_bytes: bytes) -> str:
    """Return the project's tagged SHA-256 representation."""

    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def verify_stripped_bootstrap_assignment_bytes(
    assignment_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
) -> JsonObject:
    """Verify the reviewer-safe assignment and PBMs without the layout proposal.

    This verifies the frozen stripped-assignment bytes, the complete ordered
    700-cell roster, the two exact canonical PBMs, and every proposed cell and
    context crop commitment.  It does not prove reviewer identity, real-world
    independence, blinding, source custody, rights, or decipherment.
    """

    _assignment, summary = _verify_stripped_assignment_bytes(
        assignment_bytes,
        page_pbm_bytes,
    )
    return copy.deepcopy(summary)


def _verify_stripped_assignment_bytes(
    assignment_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
) -> tuple[JsonObject, JsonObject]:
    if (
        len(assignment_bytes) != EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE
        or sha256_bytes(assignment_bytes) != EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256
    ):
        raise KP1982BootstrapReviewError(
            "bootstrap assignment does not match the pinned stripped bytes"
        )
    assignment = _decode_schema_object(
        assignment_bytes,
        label="bootstrap assignment",
        schema_filename=ASSIGNMENT_SCHEMA,
        max_bytes=MAX_ASSIGNMENT_BYTES,
    )
    if assignment_bytes != encode_json(assignment):
        raise KP1982BootstrapReviewError("bootstrap assignment is not canonical JSON")
    if assignment.get("manifest_id") != MANIFEST_ID:
        raise KP1982BootstrapReviewError("bootstrap assignment manifest is not pinned")
    _validate_text_safety(assignment)
    pages = _verify_page_pbms(assignment, page_pbm_bytes, require_exact_commitments=True)
    _validate_assignment_cells(assignment, pages, require_crop_commitments=True)
    return assignment, {
        "schema_version": SCHEMA_VERSION,
        "valid": True,
        "claim_class": "private_stripped_bootstrap_assignment_verification",
        "cell_count": CELL_COUNT,
        "assignment_exact_bytes_verified": True,
        "bootstrap_assignment_canonical_json_verified": True,
        "canonical_page_bitmaps_exact_bytes_verified": True,
        "assignment_cell_roster_semantically_verified": True,
        "all_700_assignment_crops_recomputed": True,
        "layout_proposal_not_supplied": True,
        "layout_proposal_recomputed": False,
        "source_pdf_reparsed": False,
        "human_authorship_verified": False,
        "real_world_independence_verified": False,
        "reviewer_blinding_verified": False,
        "source_custody_verified": False,
        "source_rights_verified": False,
        "sign_inventory_generated": False,
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


def _decode_schema_object(
    raw_bytes: bytes,
    *,
    label: str,
    schema_filename: str,
    max_bytes: int,
) -> JsonObject:
    if not isinstance(raw_bytes, bytes):
        raise KP1982BootstrapReviewError(f"{label} must be supplied as exact bytes")
    if not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1982BootstrapReviewError(f"{label} has an invalid byte length")
    try:
        value = decode_json(raw_bytes, source=label)
    except RecursionError as error:
        raise KP1982BootstrapReviewError(f"{label} exceeds the safe structural depth") from error
    except ValueError as error:
        raise KP1982BootstrapReviewError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1982BootstrapReviewError(f"{label} must decode to an object")
    try:
        issues = validate_schema_instance(value, _default_schema_path(schema_filename))
    except RecursionError as error:
        raise KP1982BootstrapReviewError(f"{label} exceeds the safe structural depth") from error
    if issues:
        raise KP1982BootstrapReviewError(f"{label} schema invalid at {issues[0].path}")
    return value


def _verify_page_pbms(
    assignment: Mapping[str, Any],
    page_pbm_bytes: Sequence[bytes],
    *,
    require_exact_commitments: bool,
) -> dict[int, bytes]:
    if isinstance(page_pbm_bytes, bytes) or len(page_pbm_bytes) != 2:
        raise KP1982BootstrapReviewError(
            "exactly two canonical page PBMs are required in assignment order"
        )
    page_values = _require_list(assignment.get("page_bitmaps"), "assignment page_bitmaps")
    if len(page_values) != 2:
        raise KP1982BootstrapReviewError("assignment page bitmap roster is incomplete")
    pages: dict[int, bytes] = {}
    for position, (page_value, page_bytes) in enumerate(
        zip(page_values, page_pbm_bytes, strict=True)
    ):
        page = _require_mapping(page_value, "assignment page bitmap")
        page_index = _require_integer(page.get("page_index"), "page_index")
        if page_index != (19, 20)[position] or page_index in pages:
            raise KP1982BootstrapReviewError("assignment page order is invalid")
        _verify_canonical_pbm_shape(page_bytes)
        if require_exact_commitments and (
            len(page_bytes) != _require_integer(page.get("byte_size"), "PBM byte_size")
            or sha256_bytes(page_bytes)
            != _require_string(page.get("canonical_pbm_sha256"), "PBM sha256")
        ):
            raise KP1982BootstrapReviewError(
                "page PBM does not match the stripped assignment commitment"
            )
        pages[page_index] = page_bytes
    return pages


def _verify_canonical_pbm_shape(page_bytes: object) -> None:
    if not isinstance(page_bytes, bytes):
        raise KP1982BootstrapReviewError("page PBM must be supplied as exact bytes")
    header = f"P4\n{PAGE_WIDTH} {PAGE_HEIGHT}\n".encode("ascii")
    if not page_bytes.startswith(header):
        raise KP1982BootstrapReviewError("page image does not use the canonical PBM header")
    expected_size = len(header) + ((PAGE_WIDTH + 7) // 8) * PAGE_HEIGHT
    if len(page_bytes) != expected_size:
        raise KP1982BootstrapReviewError("page PBM payload has an invalid byte size")


def _validate_assignment_cells(
    assignment: Mapping[str, Any],
    pages: Mapping[int, bytes],
    *,
    require_crop_commitments: bool,
) -> list[Mapping[str, Any]]:
    values = _require_list(assignment.get("cells"), "assignment cells")
    if len(values) != CELL_COUNT:
        raise KP1982BootstrapReviewError("assignment must contain exactly 700 cells")
    _preflight_assignment_crop_budget(values)
    crop_cache: _CropCache = {}
    cells: list[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        cell = _require_mapping(value, "assignment cell")
        expected = _expected_locator(index)
        actual = (
            cell.get("cell_id"),
            cell.get("page_index"),
            cell.get("lane_index"),
            cell.get("row_index"),
        )
        if actual != expected:
            raise KP1982BootstrapReviewError("assignment cell roster or order is invalid")
        page_index = expected[1]
        page_bytes = pages.get(page_index)
        if page_bytes is None:
            raise KP1982BootstrapReviewError("assignment cell cites an unknown page")
        cell_bbox = _native_bbox(cell.get("proposed_cell_bbox"), "proposed cell bbox")
        context_bbox = _native_bbox(
            cell.get("proposed_context_bbox"),
            "proposed context bbox",
        )
        if not _bbox_within(cell_bbox, context_bbox):
            raise KP1982BootstrapReviewError("assignment proposed cell is outside its context")
        if require_crop_commitments:
            _verify_flat_crop_commitment(
                page_bytes,
                cell_bbox,
                page_index=page_index,
                cache=crop_cache,
                expected_sha256=cell.get("cell_crop_sha256"),
                expected_byte_size=cell.get("cell_crop_byte_size"),
                label="assignment cell crop",
            )
            _verify_flat_crop_commitment(
                page_bytes,
                context_bbox,
                page_index=page_index,
                cache=crop_cache,
                expected_sha256=cell.get("context_crop_sha256"),
                expected_byte_size=cell.get("context_crop_byte_size"),
                label="assignment context crop",
            )
        cells.append(cell)
    return cells


def _expected_locator(index: int) -> tuple[str, int, int, int]:
    page_offset, page_cell_index = divmod(index, 350)
    lane_index, row_index = divmod(page_cell_index, 35)
    page_index = 19 + page_offset
    cell_id = f"KP1982:P{page_index + 1}:L{lane_index:02d}:R{row_index:02d}"
    return cell_id, page_index, lane_index, row_index


def _native_bbox(value: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise KP1982BootstrapReviewError(f"{label} must contain four integers")
    if any(not isinstance(coordinate, int) or isinstance(coordinate, bool) for coordinate in value):
        raise KP1982BootstrapReviewError(f"{label} must contain four integers")
    x0, y0, x1, y1 = value
    if not 0 <= x0 < x1 <= PAGE_WIDTH or not 0 <= y0 < y1 <= PAGE_HEIGHT:
        raise KP1982BootstrapReviewError(f"{label} is outside the native page")
    return x0, y0, x1, y1


def _bbox_within(
    inner: tuple[int, int, int, int],
    outer: tuple[int, int, int, int],
) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def _verify_flat_crop_commitment(
    page_bytes: bytes,
    bbox: tuple[int, int, int, int],
    *,
    page_index: int,
    cache: _CropCache,
    expected_sha256: object,
    expected_byte_size: object,
    label: str,
) -> None:
    cache_key = (page_index, bbox)
    observed = cache.get(cache_key)
    if observed is None:
        crop = crop_canonical_pbm(
            page_bytes,
            page_width=PAGE_WIDTH,
            page_height=PAGE_HEIGHT,
            bbox=bbox,
        )
        observed = sha256_bytes(crop), len(crop)
        cache[cache_key] = observed
    if (
        expected_sha256 != observed[0]
        or expected_byte_size != observed[1]
        or isinstance(expected_byte_size, bool)
    ):
        raise KP1982BootstrapReviewError(f"{label} commitment does not match page pixels")


def _preflight_assignment_crop_budget(values: Sequence[object]) -> None:
    total = 0
    for value in values:
        cell = _require_mapping(value, "assignment cell")
        for key in ("proposed_cell_bbox", "proposed_context_bbox"):
            bbox = _native_bbox(cell.get(key), "assignment crop bbox")
            total += _expected_crop_byte_size(bbox)
            if total > MAX_TOTAL_REVIEW_CROP_BYTES:
                raise KP1982BootstrapReviewError(
                    "assignment crop recomputation exceeds the deterministic budget"
                )


def _expected_crop_byte_size(bbox: tuple[int, int, int, int]) -> int:
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    header_size = len(f"P4\n{width} {height}\n".encode("ascii"))
    return header_size + ((width + 7) // 8) * height


def validate_bootstrap_review(
    review_value: Mapping[str, Any],
    assignment_value: Mapping[str, Any],
    page_pbm_bytes: Sequence[bytes],
) -> None:
    """Validate review schema, roster, pixels, and stage semantics from mappings.

    This mapping API is useful for constructing and testing records.  It does
    not verify the exact bytes, canonical JSON encoding, or pinned digest of the
    assignment or review.  Only the exact-byte public APIs may make those
    integrity claims.  It also cannot prove human authorship, real-world
    independence, blinding, custody, rights, or decipherment.
    """

    review = _require_mapping(review_value, "bootstrap review")
    assignment = _require_mapping(assignment_value, "bootstrap assignment")
    assignment_issues = validate_schema_instance(
        assignment,
        _default_schema_path(ASSIGNMENT_SCHEMA),
    )
    if assignment_issues:
        raise KP1982BootstrapReviewError(
            f"bootstrap assignment schema invalid at {assignment_issues[0].path}"
        )
    issues = validate_schema_instance(review, _default_schema_path(REVIEW_SCHEMA))
    if issues:
        raise KP1982BootstrapReviewError(f"bootstrap review schema invalid at {issues[0].path}")
    _validate_text_safety(review)
    _reject_forbidden_review_keys(review)
    pages = _verify_page_pbms(assignment, page_pbm_bytes, require_exact_commitments=False)
    assignment_cells = _validate_assignment_cells(
        assignment,
        pages,
        require_crop_commitments=True,
    )
    _validate_review_semantics(review, assignment_cells, pages)


def verify_independent_review_bytes(
    assignment_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    review_bytes: bytes,
) -> JsonObject:
    """Verify one exact canonical independent pass against pixels and assignment.

    The result establishes byte, roster, and crop consistency only.  A declared
    human pseudonym is not proof of a human author, real-world independence,
    blinding, source custody, rights, inventory validity, or decipherment.
    """

    assignment, _assignment_summary = _verify_stripped_assignment_bytes(
        assignment_bytes,
        page_pbm_bytes,
    )
    review = _decode_review_bytes(review_bytes, label="independent review")
    pages = _verify_page_pbms(assignment, page_pbm_bytes, require_exact_commitments=True)
    assignment_cells = _validate_assignment_cells(
        assignment,
        pages,
        require_crop_commitments=False,
    )
    unresolved_count = _validate_review_semantics(review, assignment_cells, pages)
    if review.get("review_stage") != "independent_pass":
        raise KP1982BootstrapReviewError("review is not an independent pass")
    return _review_verification_summary(
        unresolved_cell_count=unresolved_count,
        review_exact_bytes_verified=True,
        input_review_bytes_reverified=False,
    )


def _decode_review_bytes(raw_bytes: bytes, *, label: str) -> JsonObject:
    review = _decode_schema_object(
        raw_bytes,
        label=label,
        schema_filename=REVIEW_SCHEMA,
        max_bytes=MAX_REVIEW_BYTES,
    )
    if raw_bytes != encode_json(review):
        raise KP1982BootstrapReviewError(f"{label} is not canonical JSON")
    _validate_text_safety(review)
    _reject_forbidden_review_keys(review)
    return review


def _validate_review_semantics(
    review: Mapping[str, Any],
    assignment_cells: Sequence[Mapping[str, Any]],
    pages: Mapping[int, bytes],
) -> int:
    if review.get("schema_version") != SCHEMA_VERSION:
        raise KP1982BootstrapReviewError("unsupported bootstrap review schema_version")
    if review.get("scientific_scope") != SCIENTIFIC_SCOPE:
        raise KP1982BootstrapReviewError("bootstrap review scientific_scope is not fail-closed")
    assignment_commitment = _require_mapping(
        review.get("bootstrap_assignment"),
        "bootstrap_assignment",
    )
    if assignment_commitment != {
        "manifest_id": MANIFEST_ID,
        "sha256": EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
        "byte_size": EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE,
    }:
        raise KP1982BootstrapReviewError("review does not bind the pinned stripped assignment")

    stage = review.get("review_stage")
    actor = _require_mapping(review.get("actor"), "actor")
    declared_access = _require_mapping(actor.get("declared_access"), "declared_access")
    record_identifiers = {
        _require_string(actor.get("actor_id"), "actor_id"),
        _require_string(review.get("review_id"), "review_id"),
        _require_string(review.get("review_assignment_id"), "review_assignment_id"),
    }
    if len(record_identifiers) != 3:
        raise KP1982BootstrapReviewError(
            "review, actor, and assignment identifiers must be distinct"
        )
    if stage == "independent_pass":
        if actor.get("role") != "reviewer":
            raise KP1982BootstrapReviewError("independent pass actor must be a reviewer")
        if review.get("sealed_input_reviews") is not None:
            raise KP1982BootstrapReviewError("independent pass cannot contain sealed input reviews")
        if _require_list(review.get("disagreements"), "disagreements"):
            raise KP1982BootstrapReviewError("independent pass cannot contain disagreements")
        if any(
            declared_access.get(key) != "not_seen"
            for key in (
                "machine_occupancy_ocr_identifier_proposals",
                "sealed_peer_review_outputs",
                "preexisting_bootstrap_inventory",
            )
        ):
            raise KP1982BootstrapReviewError(
                "independent pass access declarations do not satisfy the sealed protocol"
            )
    elif stage == "adjudication":
        if actor.get("role") != "adjudicator":
            raise KP1982BootstrapReviewError("adjudication actor must be an adjudicator")
        _require_mapping(review.get("sealed_input_reviews"), "sealed_input_reviews")
        if (
            declared_access.get("machine_occupancy_ocr_identifier_proposals") != "not_seen"
            or declared_access.get("preexisting_bootstrap_inventory") != "not_seen"
            or declared_access.get("sealed_peer_review_outputs") != "seen"
        ):
            raise KP1982BootstrapReviewError(
                "adjudication access declarations do not satisfy the sealed protocol"
            )
    else:
        raise KP1982BootstrapReviewError("unknown bootstrap review stage")

    values = _require_list(review.get("cells"), "review cells")
    if len(values) != CELL_COUNT or len(assignment_cells) != CELL_COUNT:
        raise KP1982BootstrapReviewError("review must bind exactly 700 assignment cells")
    _preflight_review_crop_budget(values)
    crop_cache: _CropCache = {}
    unresolved_count = 0
    lower_identifiers: set[str] = set()
    for index, (value, assignment_cell) in enumerate(zip(values, assignment_cells, strict=True)):
        cell = _require_mapping(value, "review cell")
        expected = _expected_locator(index)
        actual = (
            cell.get("cell_id"),
            cell.get("page_index"),
            cell.get("lane_index"),
            cell.get("row_index"),
        )
        assignment_actual = (
            assignment_cell.get("cell_id"),
            assignment_cell.get("page_index"),
            assignment_cell.get("lane_index"),
            assignment_cell.get("row_index"),
        )
        if actual != expected or actual != assignment_actual:
            raise KP1982BootstrapReviewError("review cell roster or assignment binding is invalid")
        page_bytes = pages.get(expected[1])
        if page_bytes is None:
            raise KP1982BootstrapReviewError("review cell cites an unknown page")
        _validate_review_cell(
            cell,
            assignment_cell,
            page_bytes,
            page_index=expected[1],
            crop_cache=crop_cache,
            stage=stage,
        )
        lower = _require_mapping(
            cell.get("raw_lower_primary_identifier"),
            "raw_lower_primary_identifier",
        )
        if lower.get("status") == "observed":
            raw_lower = _require_string(lower.get("raw_text"), "lower raw_text")
            if raw_lower in lower_identifiers:
                raise KP1982BootstrapReviewError(
                    "review contains a duplicate observed lower primary identifier"
                )
            lower_identifiers.add(raw_lower)
        unresolved_count += int(_cell_has_unresolved_observation(cell))

    limitations = set(_require_list(review.get("limitations"), "limitations"))
    outcome = review.get("review_outcome")
    if outcome == "complete":
        if unresolved_count:
            raise KP1982BootstrapReviewError(
                "complete review cannot contain unresolved observations"
            )
        if "incomplete_review" in limitations or "unresolved_cells_present" in limitations:
            raise KP1982BootstrapReviewError("complete review has contradictory limitation codes")
    elif outcome == "complete_with_unresolved_observations":
        if not unresolved_count or "unresolved_cells_present" not in limitations:
            raise KP1982BootstrapReviewError(
                "unresolved review outcome does not match cell observations"
            )
    elif outcome == "abstain":
        if "incomplete_review" not in limitations:
            raise KP1982BootstrapReviewError("abstention must declare an incomplete review")
    else:
        raise KP1982BootstrapReviewError("unknown bootstrap review outcome")
    return unresolved_count


def _validate_review_cell(
    cell: Mapping[str, Any],
    assignment_cell: Mapping[str, Any],
    page_bytes: bytes,
    *,
    page_index: int,
    crop_cache: _CropCache,
    stage: object,
) -> None:
    geometry = _require_mapping(cell.get("cell_geometry"), "cell_geometry")
    cell_evidence = _verify_crop_commitment(
        geometry.get("cell_evidence"),
        page_bytes,
        page_index=page_index,
        cache=crop_cache,
        label="reviewed cell crop",
    )
    context_evidence = _verify_crop_commitment(
        geometry.get("context_evidence"),
        page_bytes,
        page_index=page_index,
        cache=crop_cache,
        label="reviewed context crop",
    )
    if not _bbox_within(cell_evidence, context_evidence):
        raise KP1982BootstrapReviewError("reviewed cell crop is outside its reviewed context")
    decision = geometry.get("decision")
    reason_codes = set(_require_list(geometry.get("reason_codes"), "geometry reason_codes"))
    proposed_cell = _native_bbox(
        assignment_cell.get("proposed_cell_bbox"),
        "proposed cell bbox",
    )
    proposed_context = _native_bbox(
        assignment_cell.get("proposed_context_bbox"),
        "proposed context bbox",
    )
    if decision == "accepted_as_proposed":
        if cell_evidence != proposed_cell or context_evidence != proposed_context:
            raise KP1982BootstrapReviewError(
                "accepted geometry differs from the assignment proposal"
            )
        _require_exact_assignment_crop(
            geometry.get("cell_evidence"),
            assignment_cell,
            prefix="cell",
        )
        _require_exact_assignment_crop(
            geometry.get("context_evidence"),
            assignment_cell,
            prefix="context",
        )
    elif decision == "corrected":
        if cell_evidence == proposed_cell and context_evidence == proposed_context:
            raise KP1982BootstrapReviewError(
                "corrected geometry does not change either proposed crop"
            )
        if "accepted_without_change" in reason_codes or "unresolved_boundary" in reason_codes:
            raise KP1982BootstrapReviewError("corrected geometry has contradictory reason codes")
    elif decision == "unresolved":
        if "unresolved_boundary" not in reason_codes:
            raise KP1982BootstrapReviewError("unresolved geometry lacks its reason code")
        if "accepted_without_change" in reason_codes:
            raise KP1982BootstrapReviewError("unresolved geometry has contradictory reason codes")
    else:
        raise KP1982BootstrapReviewError("unknown cell geometry decision")

    upper, upper_evidence = _validate_identifier_observation(
        cell.get("raw_upper_catalog_rank"),
        page_bytes,
        page_index=page_index,
        cache=crop_cache,
        label="upper identifier",
    )
    lower, lower_evidence = _validate_identifier_observation(
        cell.get("raw_lower_primary_identifier"),
        page_bytes,
        page_index=page_index,
        cache=crop_cache,
        label="lower identifier",
    )
    glyph = _require_mapping(cell.get("glyph_with_marks"), "glyph_with_marks")
    glyph_anomalies = _require_list(
        glyph.get("anomaly_codes"),
        "glyph_with_marks anomaly_codes",
    )
    if glyph.get("status") == "not_present" and glyph_anomalies:
        raise KP1982BootstrapReviewError("absent glyph cannot contain anomaly codes")
    glyph_evidence = _verify_crop_commitment(
        glyph.get("evidence"),
        page_bytes,
        page_index=page_index,
        cache=crop_cache,
        label="glyph-with-marks crop",
    )
    core_value = cell.get("glyph_core")
    component_evidence = [upper_evidence, lower_evidence, glyph_evidence]
    if core_value is not None:
        core = _require_mapping(core_value, "glyph_core")
        component_evidence.append(
            _verify_crop_commitment(
                core.get("evidence"),
                page_bytes,
                page_index=page_index,
                cache=crop_cache,
                label="glyph-core crop",
            )
        )

    marks = _require_list(cell.get("printed_marks"), "printed_marks")
    for mark_index, value in enumerate(marks):
        mark = _require_mapping(value, "printed mark")
        if mark.get("mark_index") != mark_index:
            raise KP1982BootstrapReviewError(
                "printed mark indices must be unique and contiguous from zero"
            )
        if mark.get("condition") == "not_applicable":
            raise KP1982BootstrapReviewError(
                "present printed mark cannot have an inapplicable condition"
            )
        component_evidence.append(
            _verify_crop_commitment(
                mark.get("evidence"),
                page_bytes,
                page_index=page_index,
                cache=crop_cache,
                label="printed-mark crop",
            )
        )
    if any(not _bbox_within(evidence, context_evidence) for evidence in component_evidence):
        raise KP1982BootstrapReviewError(
            "review observation evidence is outside its reviewed context"
        )

    occupancy = cell.get("occupancy")
    condition = cell.get("condition")
    uncertainty = _require_mapping(cell.get("uncertainty"), "uncertainty")
    uncertainty_status = uncertainty.get("status")
    uncertainty_fields = set(
        _require_list(uncertainty.get("field_codes"), "uncertainty field_codes")
    )
    uncertainty_reasons = _require_list(
        uncertainty.get("reason_codes"),
        "uncertainty reason_codes",
    )
    if occupancy == "blank":
        if (
            upper.get("status") != "not_applicable"
            or lower.get("status") != "not_applicable"
            or glyph.get("status") != "not_present"
            or core_value is not None
            or marks
            or condition != "not_applicable"
        ):
            raise KP1982BootstrapReviewError(
                "blank cell contains incompatible graphic or identifier observations"
            )
    elif occupancy in {
        "single_entry",
        "multiple_or_split",
        "continuation_or_merge",
    }:
        if (
            upper.get("status") == "not_applicable"
            or lower.get("status") == "not_applicable"
            or glyph.get("status") == "not_present"
            or condition == "not_applicable"
        ):
            raise KP1982BootstrapReviewError("occupied cell lacks applicable graphic observations")
    elif occupancy == "uncertain":
        if uncertainty_status not in {"uncertain", "unresolved"}:
            raise KP1982BootstrapReviewError("uncertain occupancy requires explicit uncertainty")
        if "occupancy" not in uncertainty_fields:
            raise KP1982BootstrapReviewError("uncertain occupancy lacks an uncertainty field code")
    else:
        raise KP1982BootstrapReviewError("unknown occupancy decision")

    if glyph.get("status") != "observed" and core_value is not None:
        raise KP1982BootstrapReviewError("glyph core requires an observed glyph-with-marks crop")
    if uncertainty_status in {"certain", "not_applicable"}:
        if uncertainty_fields or uncertainty_reasons:
            raise KP1982BootstrapReviewError(
                "certain or not-applicable uncertainty cannot contain reasons"
            )
    elif not uncertainty_fields or not uncertainty_reasons:
        raise KP1982BootstrapReviewError(
            "uncertain or unresolved cell requires field and reason codes"
        )

    expected_uncertainty_fields = _unresolved_field_codes(cell)
    if not expected_uncertainty_fields.issubset(uncertainty_fields):
        raise KP1982BootstrapReviewError("cell uncertainty omits an unresolved field")
    if expected_uncertainty_fields and uncertainty_status not in {"uncertain", "unresolved"}:
        raise KP1982BootstrapReviewError("unresolved observation is marked certain")

    input_observations = cell.get("input_observations")
    adjudication_codes = _require_list(
        cell.get("adjudication_codes"),
        "adjudication_codes",
    )
    if stage == "independent_pass":
        if input_observations is not None or adjudication_codes:
            raise KP1982BootstrapReviewError("independent cell contains adjudication evidence")
        if "adjudication" in uncertainty_fields or "input_reviews_disagree" in uncertainty_reasons:
            raise KP1982BootstrapReviewError(
                "independent cell contains peer-dependent uncertainty evidence"
            )
    elif stage == "adjudication":
        _require_mapping(input_observations, "input_observations")
        if not adjudication_codes:
            raise KP1982BootstrapReviewError("adjudicated cell lacks an adjudication code")


def _validate_identifier_observation(
    value: object,
    page_bytes: bytes,
    *,
    page_index: int,
    cache: _CropCache,
    label: str,
) -> tuple[Mapping[str, Any], tuple[int, int, int, int]]:
    observation = _require_mapping(value, label)
    evidence = _verify_crop_commitment(
        observation.get("evidence"),
        page_bytes,
        page_index=page_index,
        cache=cache,
        label=f"{label} crop",
    )
    status = observation.get("status")
    raw_text = observation.get("raw_text")
    anomalies = set(_require_list(observation.get("anomaly_codes"), "identifier anomaly_codes"))
    visible_punctuation_codes = {
        "leading_dot_visible",
        "trailing_apostrophe_visible",
        "question_mark_visible",
    }
    if status == "observed":
        if not isinstance(raw_text, str) or not raw_text:
            raise KP1982BootstrapReviewError("observed identifier lacks source-faithful raw text")
        if not any(character.isascii() and character.isdigit() for character in raw_text):
            raise KP1982BootstrapReviewError("observed identifier lacks a visible ASCII digit")
        visible_codes = {
            "leading_dot_visible": raw_text.startswith("."),
            "trailing_apostrophe_visible": raw_text.endswith("'"),
            "question_mark_visible": "?" in raw_text,
        }
        if any((code in anomalies) != visible for code, visible in visible_codes.items()):
            raise KP1982BootstrapReviewError(
                "identifier punctuation and anomaly codes are inconsistent"
            )
    else:
        if raw_text is not None:
            raise KP1982BootstrapReviewError("non-observed identifier cannot contain raw text")
        if anomalies.intersection(visible_punctuation_codes):
            raise KP1982BootstrapReviewError(
                "non-observed identifier cannot assert visible punctuation"
            )
        if status in {"not_present", "not_applicable"} and anomalies:
            raise KP1982BootstrapReviewError(
                "absent or inapplicable identifier cannot contain anomaly codes"
            )
    return observation, evidence


def _verify_crop_commitment(
    value: object,
    page_bytes: bytes,
    *,
    page_index: int,
    cache: _CropCache,
    label: str,
) -> tuple[int, int, int, int]:
    commitment = _require_mapping(value, label)
    bbox = _native_bbox(commitment.get("bbox"), f"{label} bbox")
    if commitment.get("encoding") != CROP_ENCODING:
        raise KP1982BootstrapReviewError(f"{label} uses an unknown crop encoding")
    _verify_flat_crop_commitment(
        page_bytes,
        bbox,
        page_index=page_index,
        cache=cache,
        expected_sha256=commitment.get("sha256"),
        expected_byte_size=commitment.get("byte_size"),
        label=label,
    )
    return bbox


def _preflight_review_crop_budget(values: Sequence[object]) -> None:
    """Reject pathological crop workloads before extracting any review crop."""

    total = 0
    for value in values:
        cell = _require_mapping(value, "review cell")
        geometry = _require_mapping(cell.get("cell_geometry"), "cell_geometry")
        commitments: list[object] = [
            geometry.get("cell_evidence"),
            geometry.get("context_evidence"),
            _require_mapping(
                cell.get("raw_upper_catalog_rank"),
                "raw_upper_catalog_rank",
            ).get("evidence"),
            _require_mapping(
                cell.get("raw_lower_primary_identifier"),
                "raw_lower_primary_identifier",
            ).get("evidence"),
            _require_mapping(cell.get("glyph_with_marks"), "glyph_with_marks").get("evidence"),
        ]
        core_value = cell.get("glyph_core")
        if core_value is not None:
            commitments.append(_require_mapping(core_value, "glyph_core").get("evidence"))
        commitments.extend(
            _require_mapping(mark, "printed mark").get("evidence")
            for mark in _require_list(cell.get("printed_marks"), "printed_marks")
        )
        for commitment_value in commitments:
            commitment = _require_mapping(commitment_value, "crop commitment")
            bbox = _native_bbox(commitment.get("bbox"), "crop commitment bbox")
            expected_size = _expected_crop_byte_size(bbox)
            if commitment.get("byte_size") != expected_size:
                raise KP1982BootstrapReviewError(
                    "crop byte_size is inconsistent with its native bbox"
                )
            total += expected_size
            if total > MAX_TOTAL_REVIEW_CROP_BYTES:
                raise KP1982BootstrapReviewError(
                    "review crop recomputation exceeds the deterministic budget"
                )


def _require_exact_assignment_crop(
    crop_value: object,
    assignment_cell: Mapping[str, Any],
    *,
    prefix: str,
) -> None:
    crop = _require_mapping(crop_value, f"{prefix} evidence")
    expected = {
        "bbox": assignment_cell.get(f"proposed_{prefix}_bbox"),
        "sha256": assignment_cell.get(f"{prefix}_crop_sha256"),
        "byte_size": assignment_cell.get(f"{prefix}_crop_byte_size"),
        "encoding": CROP_ENCODING,
    }
    if crop != expected:
        raise KP1982BootstrapReviewError(
            "accepted proposed crop differs from the assignment commitment"
        )


def _unresolved_field_codes(cell: Mapping[str, Any]) -> set[str]:
    fields: set[str] = set()
    if cell.get("occupancy") == "uncertain":
        fields.add("occupancy")
    geometry = _require_mapping(cell.get("cell_geometry"), "cell_geometry")
    if geometry.get("decision") == "unresolved":
        fields.add("cell_geometry")
    upper = _require_mapping(
        cell.get("raw_upper_catalog_rank"),
        "raw_upper_catalog_rank",
    )
    if upper.get("status") in _UNRESOLVED_IDENTIFIER_STATUSES:
        fields.add("upper_catalog_rank")
    lower = _require_mapping(
        cell.get("raw_lower_primary_identifier"),
        "raw_lower_primary_identifier",
    )
    if lower.get("status") in _UNRESOLVED_IDENTIFIER_STATUSES:
        fields.add("lower_primary_identifier")
    glyph = _require_mapping(cell.get("glyph_with_marks"), "glyph_with_marks")
    if glyph.get("status") == "unresolved":
        fields.add("glyph_with_marks")
    core_value = cell.get("glyph_core")
    if isinstance(core_value, Mapping) and core_value.get("derivation_status") == "unresolved":
        fields.add("glyph_core")
    marks = _require_list(cell.get("printed_marks"), "printed_marks")
    if any(
        _require_mapping(value, "printed mark").get("nonsemantic_class") == "unresolved"
        or _require_mapping(value, "printed mark").get("association") == "unresolved"
        or _require_mapping(value, "printed mark").get("condition") == "unresolved"
        for value in marks
    ):
        fields.add("printed_marks")
    if cell.get("condition") in {"unreadable", "unresolved"}:
        fields.add("condition")
    uncertainty = _require_mapping(cell.get("uncertainty"), "uncertainty")
    if uncertainty.get("status") == "unresolved":
        fields.add("uncertainty")
    return fields


def _cell_has_unresolved_observation(cell: Mapping[str, Any]) -> bool:
    uncertainty = _require_mapping(cell.get("uncertainty"), "uncertainty")
    return bool(_unresolved_field_codes(cell)) or uncertainty.get("status") in {
        "uncertain",
        "unresolved",
    }


def _review_verification_summary(
    *,
    unresolved_cell_count: int,
    review_exact_bytes_verified: bool,
    input_review_bytes_reverified: bool,
) -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "valid": True,
        "claim_class": "private_kp1982_bootstrap_review_verification",
        "cell_count": CELL_COUNT,
        "unresolved_cell_count": unresolved_cell_count,
        "bootstrap_assignment_exact_bytes_verified": True,
        "review_exact_canonical_bytes_verified": review_exact_bytes_verified,
        "canonical_page_bitmaps_exact_bytes_verified": True,
        "assignment_cell_roster_semantically_verified": True,
        "review_crop_commitments_recomputed": True,
        "input_review_bytes_reverified": input_review_bytes_reverified,
        "layout_proposal_not_supplied": True,
        "preexisting_sign_inventory_not_supplied": True,
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


def compare_independent_review_bytes(
    assignment_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    independent_review_bytes: Sequence[bytes],
) -> JsonObject:
    """Return a private, value-free audit of exactly two independent passes.

    The report includes pseudonymous review IDs and per-cell mismatch categories
    so it is useful for private adjudication, but it never copies raw identifier
    text.  Distinct strings do not prove distinct people, independence, or
    blinding, and the comparison makes no inventory or decipherment claim.
    """

    reviews, digests = _verify_independent_pair(
        assignment_bytes,
        page_pbm_bytes,
        independent_review_bytes,
    )
    summary, _differences = _compare_review_records(reviews, digests)
    return copy.deepcopy(summary)


def _verify_independent_pair(
    assignment_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    independent_review_bytes: Sequence[bytes],
) -> tuple[tuple[JsonObject, JsonObject], tuple[str, str]]:
    if isinstance(independent_review_bytes, bytes) or len(independent_review_bytes) != 2:
        raise KP1982BootstrapReviewError(
            "comparison and adjudication require exactly two review byte strings"
        )
    assignment, _summary = _verify_stripped_assignment_bytes(
        assignment_bytes,
        page_pbm_bytes,
    )
    pages = _verify_page_pbms(assignment, page_pbm_bytes, require_exact_commitments=True)
    assignment_cells = _validate_assignment_cells(
        assignment,
        pages,
        require_crop_commitments=False,
    )
    reviews: list[JsonObject] = []
    digests: list[str] = []
    for index, raw_bytes in enumerate(independent_review_bytes):
        review = _decode_review_bytes(raw_bytes, label=f"independent review {index}")
        _validate_review_semantics(review, assignment_cells, pages)
        if review.get("review_stage") != "independent_pass":
            raise KP1982BootstrapReviewError("an input is not an independent pass")
        if review.get("review_outcome") == "abstain":
            raise KP1982BootstrapReviewError(
                "an abstained pass cannot enter comparison or adjudication"
            )
        reviews.append(review)
        digests.append(sha256_bytes(raw_bytes))
    _require_distinct_passes(reviews)
    return (reviews[0], reviews[1]), (digests[0], digests[1])


def _require_distinct_passes(reviews: Sequence[Mapping[str, Any]]) -> None:
    review_ids = {_require_string(review.get("review_id"), "review_id") for review in reviews}
    assignment_ids = {
        _require_string(review.get("review_assignment_id"), "review_assignment_id")
        for review in reviews
    }
    actor_ids = {
        _require_string(
            _require_mapping(review.get("actor"), "actor").get("actor_id"),
            "actor_id",
        )
        for review in reviews
    }
    all_identifiers = review_ids | assignment_ids | actor_ids
    if (
        len(review_ids) != 2
        or len(assignment_ids) != 2
        or len(actor_ids) != 2
        or len(all_identifiers) != 6
    ):
        raise KP1982BootstrapReviewError(
            "independent passes require distinct review, actor, and assignment identifiers"
        )


def _compare_review_records(
    reviews: tuple[Mapping[str, Any], Mapping[str, Any]],
    digests: tuple[str, str],
) -> tuple[JsonObject, dict[str, tuple[str, ...]]]:
    left, right = reviews
    left_cells = _require_list(left.get("cells"), "left review cells")
    right_cells = _require_list(right.get("cells"), "right review cells")
    if len(left_cells) != CELL_COUNT or len(right_cells) != CELL_COUNT:
        raise KP1982BootstrapReviewError("comparison requires two complete cell rosters")
    metrics = {
        field: {"agreement_count": 0, "disagreement_count": 0} for field in _COMPARISON_FIELDS
    }
    differences: dict[str, tuple[str, ...]] = {}
    cell_differences: list[JsonObject] = []
    exact_cell_agreement_count = 0
    for left_value, right_value in zip(left_cells, right_cells, strict=True):
        left_cell = _require_mapping(left_value, "left review cell")
        right_cell = _require_mapping(right_value, "right review cell")
        if left_cell.get("cell_id") != right_cell.get("cell_id"):
            raise KP1982BootstrapReviewError("comparison cell rosters differ")
        differing_fields: list[str] = []
        for field in _COMPARISON_FIELDS:
            key = _CELL_KEYS_BY_COMPARISON_FIELD[field]
            equal = left_cell.get(key) == right_cell.get(key)
            metric = metrics[field]
            metric["agreement_count" if equal else "disagreement_count"] += 1
            if not equal:
                differing_fields.append(field)
        if differing_fields:
            cell_id = _require_string(left_cell.get("cell_id"), "cell_id")
            fields = tuple(differing_fields)
            differences[cell_id] = fields
            cell_differences.append(
                {
                    "cell_id": cell_id,
                    "field_codes": list(fields),
                }
            )
        else:
            exact_cell_agreement_count += 1

    unresolved_counts = [
        sum(
            int(_cell_has_unresolved_observation(_require_mapping(value, "review cell")))
            for value in cells
        )
        for cells in (left_cells, right_cells)
    ]
    occupancy_metrics = _occupancy_metrics(left_cells, right_cells)
    identifier_metrics = {
        "upper_catalog_rank": _identifier_metrics(
            left_cells,
            right_cells,
            key="raw_upper_catalog_rank",
        ),
        "lower_primary_identifier": _identifier_metrics(
            left_cells,
            right_cells,
            key="raw_lower_primary_identifier",
        ),
    }
    geometry_metrics = {
        name: _geometry_metrics(left_cells, right_cells, evidence_kind=name)
        for name in (
            "cell",
            "context",
            "upper_identifier",
            "lower_identifier",
            "glyph_with_marks",
            "glyph_core",
        )
    }
    printed_mark_metrics = _printed_mark_metrics(left_cells, right_cells)
    condition_agreement_count = sum(
        _require_mapping(left_value, "left cell").get("condition")
        == _require_mapping(right_value, "right cell").get("condition")
        for left_value, right_value in zip(left_cells, right_cells, strict=True)
    )
    uncertainty_agreement_count = sum(
        _require_mapping(left_value, "left cell").get("uncertainty")
        == _require_mapping(right_value, "right cell").get("uncertainty")
        for left_value, right_value in zip(left_cells, right_cells, strict=True)
    )
    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "claim_class": "private_kp1982_bootstrap_two_pass_comparison",
        "review_ids": [
            _require_string(left.get("review_id"), "review_id"),
            _require_string(right.get("review_id"), "review_id"),
        ],
        "review_sha256": list(digests),
        "review_count": 2,
        "compared_cell_count": CELL_COUNT,
        "exact_cell_agreement_count": exact_cell_agreement_count,
        "disagreement_cell_count": len(cell_differences),
        "unresolved_cell_count_by_pass": unresolved_counts,
        "field_metrics": metrics,
        "occupancy_metrics": occupancy_metrics,
        "identifier_metrics": identifier_metrics,
        "geometry_metrics": geometry_metrics,
        "printed_mark_metrics": printed_mark_metrics,
        "condition_metrics": {
            "agreement_count": condition_agreement_count,
            "agreement_rate": _rate(condition_agreement_count, CELL_COUNT),
        },
        "uncertainty_metrics": {
            "agreement_count": uncertainty_agreement_count,
            "agreement_rate": _rate(uncertainty_agreement_count, CELL_COUNT),
        },
        "cell_differences": cell_differences,
        "adjudication_required": bool(cell_differences or any(unresolved_counts)),
    }
    comparison_sha256 = sha256_bytes(encode_json(payload))
    summary = {
        **payload,
        "valid": True,
        "comparison_sha256": comparison_sha256,
        "raw_identifier_values_included": False,
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
    return summary, differences


def _occupancy_metrics(
    left_cells: Sequence[object],
    right_cells: Sequence[object],
) -> JsonObject:
    values = (
        "blank",
        "single_entry",
        "multiple_or_split",
        "continuation_or_merge",
        "uncertain",
    )
    matrix: JsonObject = {
        left_value: {right_value: 0 for right_value in values} for left_value in values
    }
    agreement_count = 0
    for left_value, right_value in zip(left_cells, right_cells, strict=True):
        left_occupancy = _require_string(
            _require_mapping(left_value, "left cell").get("occupancy"),
            "left occupancy",
        )
        right_occupancy = _require_string(
            _require_mapping(right_value, "right cell").get("occupancy"),
            "right occupancy",
        )
        row = _require_mapping(matrix.get(left_occupancy), "occupancy confusion row")
        current = row.get(right_occupancy)
        if not isinstance(current, int) or isinstance(current, bool):
            raise KP1982BootstrapReviewError("occupancy comparison contains an unknown value")
        # The nested rows are ordinary dicts created above.
        matrix[left_occupancy][right_occupancy] = current + 1
        agreement_count += int(left_occupancy == right_occupancy)
    return {
        "confusion_matrix": matrix,
        "exact_agreement_count": agreement_count,
        "exact_agreement_rate": _rate(agreement_count, CELL_COUNT),
    }


def _identifier_metrics(
    left_cells: Sequence[object],
    right_cells: Sequence[object],
    *,
    key: str,
) -> JsonObject:
    status_agreement_count = 0
    raw_comparable_count = 0
    raw_agreement_count = 0
    for left_value, right_value in zip(left_cells, right_cells, strict=True):
        left = _require_mapping(
            _require_mapping(left_value, "left cell").get(key),
            "left identifier",
        )
        right = _require_mapping(
            _require_mapping(right_value, "right cell").get(key),
            "right identifier",
        )
        status_agreement_count += int(left.get("status") == right.get("status"))
        if left.get("status") == right.get("status") == "observed":
            raw_comparable_count += 1
            raw_agreement_count += int(left.get("raw_text") == right.get("raw_text"))
    return {
        "status_agreement_count": status_agreement_count,
        "status_agreement_rate": _rate(status_agreement_count, CELL_COUNT),
        "raw_comparable_count": raw_comparable_count,
        "raw_agreement_count": raw_agreement_count,
        "raw_agreement_rate": _rate(raw_agreement_count, raw_comparable_count),
    }


def _geometry_metrics(
    left_cells: Sequence[object],
    right_cells: Sequence[object],
    *,
    evidence_kind: str,
) -> JsonObject:
    comparable_count = 0
    iou_sum = 0.0
    left_coverage_sum = 0.0
    right_coverage_sum = 0.0
    crop_agreement_count = 0
    for left_value, right_value in zip(left_cells, right_cells, strict=True):
        left = _comparison_evidence(
            _require_mapping(left_value, "left cell"),
            evidence_kind,
        )
        right = _comparison_evidence(
            _require_mapping(right_value, "right cell"),
            evidence_kind,
        )
        if left is None or right is None:
            continue
        left_bbox = _native_bbox(left.get("bbox"), "left comparison bbox")
        right_bbox = _native_bbox(right.get("bbox"), "right comparison bbox")
        intersection = _bbox_intersection_area(left_bbox, right_bbox)
        left_area = _bbox_area(left_bbox)
        right_area = _bbox_area(right_bbox)
        union = left_area + right_area - intersection
        comparable_count += 1
        iou_sum += intersection / union
        left_coverage_sum += intersection / left_area
        right_coverage_sum += intersection / right_area
        crop_agreement_count += int(left.get("sha256") == right.get("sha256"))
    return {
        "comparable_count": comparable_count,
        "bbox_iou_mean": _mean(iou_sum, comparable_count),
        "left_coverage_mean": _mean(left_coverage_sum, comparable_count),
        "right_coverage_mean": _mean(right_coverage_sum, comparable_count),
        "crop_sha256_agreement_count": crop_agreement_count,
        "crop_sha256_agreement_rate": _rate(
            crop_agreement_count,
            comparable_count,
        ),
    }


def _comparison_evidence(
    cell: Mapping[str, Any],
    kind: str,
) -> Mapping[str, Any] | None:
    if kind in {"cell", "context"}:
        geometry = _require_mapping(cell.get("cell_geometry"), "cell_geometry")
        return _require_mapping(geometry.get(f"{kind}_evidence"), f"{kind}_evidence")
    if kind == "upper_identifier":
        return _require_mapping(
            _require_mapping(
                cell.get("raw_upper_catalog_rank"),
                "raw_upper_catalog_rank",
            ).get("evidence"),
            "upper identifier evidence",
        )
    if kind == "lower_identifier":
        return _require_mapping(
            _require_mapping(
                cell.get("raw_lower_primary_identifier"),
                "raw_lower_primary_identifier",
            ).get("evidence"),
            "lower identifier evidence",
        )
    if kind == "glyph_with_marks":
        return _require_mapping(
            _require_mapping(cell.get("glyph_with_marks"), "glyph_with_marks").get("evidence"),
            "glyph evidence",
        )
    if kind == "glyph_core":
        core = cell.get("glyph_core")
        if core is None:
            return None
        return _require_mapping(
            _require_mapping(core, "glyph_core").get("evidence"),
            "glyph-core evidence",
        )
    raise KP1982BootstrapReviewError("unknown comparison evidence kind")


def _printed_mark_metrics(
    left_cells: Sequence[object],
    right_cells: Sequence[object],
) -> JsonObject:
    left_count = 0
    right_count = 0
    matched_count = 0
    exact_multiset_agreement_count = 0
    for left_value, right_value in zip(left_cells, right_cells, strict=True):
        left_marks = Counter(
            _printed_mark_fingerprint(_require_mapping(mark, "left printed mark"))
            for mark in _require_list(
                _require_mapping(left_value, "left cell").get("printed_marks"),
                "left printed_marks",
            )
        )
        right_marks = Counter(
            _printed_mark_fingerprint(_require_mapping(mark, "right printed mark"))
            for mark in _require_list(
                _require_mapping(right_value, "right cell").get("printed_marks"),
                "right printed_marks",
            )
        )
        left_count += left_marks.total()
        right_count += right_marks.total()
        matched_count += (left_marks & right_marks).total()
        exact_multiset_agreement_count += int(left_marks == right_marks)
    precision = _rate(matched_count, right_count)
    recall = _rate(matched_count, left_count)
    f1 = _rate(2 * matched_count, left_count + right_count)
    return {
        "left_count": left_count,
        "right_count": right_count,
        "matched_count": matched_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_multiset_agreement_count": exact_multiset_agreement_count,
        "exact_multiset_agreement_rate": _rate(
            exact_multiset_agreement_count,
            CELL_COUNT,
        ),
    }


def _printed_mark_fingerprint(mark: Mapping[str, Any]) -> bytes:
    """Return a multiset-comparison fingerprint excluding pass-local enumeration."""

    return encode_json(
        {
            "nonsemantic_class": mark.get("nonsemantic_class"),
            "association": mark.get("association"),
            "condition": mark.get("condition"),
            "evidence": mark.get("evidence"),
        }
    )


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])


def _bbox_intersection_area(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> int:
    width = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _mean(total: float, count: int) -> float | None:
    return None if count == 0 else total / count


def verify_adjudication_bytes(
    assignment_bytes: bytes,
    page_pbm_bytes: Sequence[bytes],
    independent_review_bytes: Sequence[bytes],
    adjudication_bytes: bytes,
) -> JsonObject:
    """Verify one adjudication against exactly two sealed review byte strings.

    The verifier checks exact canonical commitments, every cell reference, all
    disagreements, and strict selection from input values or an explicit
    unresolved sentinel.  It permits no third observation.  Pseudonymous IDs
    still do not prove human identity, real independence, blinding, custody,
    rights, inventory validity, prize eligibility, or decipherment.
    """

    reviews, review_digests = _verify_independent_pair(
        assignment_bytes,
        page_pbm_bytes,
        independent_review_bytes,
    )
    assignment, _summary = _verify_stripped_assignment_bytes(
        assignment_bytes,
        page_pbm_bytes,
    )
    pages = _verify_page_pbms(assignment, page_pbm_bytes, require_exact_commitments=True)
    assignment_cells = _validate_assignment_cells(
        assignment,
        pages,
        require_crop_commitments=False,
    )
    adjudication = _decode_review_bytes(adjudication_bytes, label="adjudication")
    unresolved_count = _validate_review_semantics(
        adjudication,
        assignment_cells,
        pages,
    )
    if adjudication.get("review_stage") != "adjudication":
        raise KP1982BootstrapReviewError("final record is not an adjudication")
    _verify_adjudication_graph(
        reviews,
        review_digests,
        independent_review_bytes,
        adjudication,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "valid": True,
        "claim_class": "private_kp1982_bootstrap_adjudication_verification",
        "cell_count": CELL_COUNT,
        "unresolved_cell_count": unresolved_count,
        "adjudication_exact_canonical_bytes_verified": True,
        "two_input_review_exact_bytes_verified": True,
        "all_700_input_observation_pairs_verified": True,
        "all_disagreements_recomputed": True,
        "no_third_observation_or_field_invention_verified": True,
        "canonical_page_bitmaps_exact_bytes_verified": True,
        "assignment_cell_roster_semantically_verified": True,
        "review_crop_commitments_recomputed": True,
        "layout_proposal_not_supplied": True,
        "preexisting_sign_inventory_not_supplied": True,
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


def _verify_adjudication_graph(
    reviews: tuple[Mapping[str, Any], Mapping[str, Any]],
    review_digests: tuple[str, str],
    review_bytes: Sequence[bytes],
    adjudication: Mapping[str, Any],
) -> None:
    left, right = reviews
    input_pair = _require_mapping(
        adjudication.get("sealed_input_reviews"),
        "sealed_input_reviews",
    )
    for position, key in enumerate(("pass_a", "pass_b")):
        review = reviews[position]
        expected = {
            "review_id": review.get("review_id"),
            "review_sha256": review_digests[position],
            "review_byte_size": len(review_bytes[position]),
            "review_assignment_id": review.get("review_assignment_id"),
            "actor_id": _require_mapping(review.get("actor"), "actor").get("actor_id"),
            "review_stage": "independent_pass",
            "bootstrap_assignment_sha256": EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
            "seal_status": "exact_canonical_bytes_sha256_and_size_committed",
        }
        if _require_mapping(input_pair.get(key), "sealed input review") != expected:
            raise KP1982BootstrapReviewError(
                "sealed input commitment does not match the exact review bytes"
            )

    adjudication_ids = {
        _require_string(adjudication.get("review_id"), "adjudication review_id"),
        _require_string(
            adjudication.get("review_assignment_id"),
            "adjudication review_assignment_id",
        ),
        _require_string(
            _require_mapping(adjudication.get("actor"), "adjudication actor").get("actor_id"),
            "adjudication actor_id",
        ),
    }
    if len(adjudication_ids) != 3:
        raise KP1982BootstrapReviewError(
            "adjudication review, actor, and assignment identifiers must be distinct"
        )
    input_review_ids = {_require_string(review.get("review_id"), "review_id") for review in reviews}
    input_assignment_ids = {
        _require_string(review.get("review_assignment_id"), "review_assignment_id")
        for review in reviews
    }
    input_actor_ids = {
        _require_string(
            _require_mapping(review.get("actor"), "actor").get("actor_id"),
            "actor_id",
        )
        for review in reviews
    }
    if (
        adjudication_ids.intersection(input_review_ids)
        or adjudication_ids.intersection(input_assignment_ids)
        or adjudication_ids.intersection(input_actor_ids)
    ):
        raise KP1982BootstrapReviewError(
            "adjudicator identifiers must differ from both input passes"
        )

    comparison, differences = _compare_review_records(reviews, review_digests)
    comparison_sha256 = _require_string(
        comparison.get("comparison_sha256"),
        "comparison_sha256",
    )
    left_cells = _require_list(left.get("cells"), "left cells")
    right_cells = _require_list(right.get("cells"), "right cells")
    output_cells = _require_list(adjudication.get("cells"), "adjudication cells")
    expected_disagreements: list[JsonObject] = []
    for left_value, right_value, output_value in zip(
        left_cells,
        right_cells,
        output_cells,
        strict=True,
    ):
        left_cell = _require_mapping(left_value, "left cell")
        right_cell = _require_mapping(right_value, "right cell")
        output_cell = _require_mapping(output_value, "adjudication cell")
        cell_id = _require_string(left_cell.get("cell_id"), "cell_id")
        _verify_input_observation_pair(
            output_cell,
            left,
            left_cell,
            right,
            right_cell,
        )
        differing_fields = differences.get(cell_id, ())
        resolution_code = _verify_no_field_invention(
            output_cell,
            left_cell,
            right_cell,
            differing_fields=differing_fields,
        )
        if differing_fields:
            expected_disagreements.append(
                {
                    "cell_id": cell_id,
                    "field_codes": list(differing_fields),
                    "input_review_ids": [
                        left.get("review_id"),
                        right.get("review_id"),
                    ],
                    "comparison_sha256": comparison_sha256,
                    "resolution_code": resolution_code,
                }
            )
    actual_disagreements = [
        dict(_require_mapping(value, "disagreement"))
        for value in _require_list(adjudication.get("disagreements"), "disagreements")
    ]
    if actual_disagreements != expected_disagreements:
        raise KP1982BootstrapReviewError(
            "adjudication disagreements do not match the exact two-pass comparison"
        )


def _verify_input_observation_pair(
    output_cell: Mapping[str, Any],
    left_review: Mapping[str, Any],
    left_cell: Mapping[str, Any],
    right_review: Mapping[str, Any],
    right_cell: Mapping[str, Any],
) -> None:
    refs = _require_mapping(output_cell.get("input_observations"), "input_observations")
    for key, review, cell in (
        ("pass_a", left_review, left_cell),
        ("pass_b", right_review, right_cell),
    ):
        expected = {
            "review_id": review.get("review_id"),
            "cell_id": cell.get("cell_id"),
            "cell_observation_sha256": sha256_bytes(encode_json(cell)),
        }
        if _require_mapping(refs.get(key), "input observation") != expected:
            raise KP1982BootstrapReviewError(
                "adjudication input observation does not match its exact review cell"
            )


def _verify_no_field_invention(
    output: Mapping[str, Any],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    differing_fields: Sequence[str],
) -> str:
    selected_sources: set[str] = set()
    unresolved = False
    differing_field_set = set(differing_fields)
    output_uncertainty_fields = set(
        _require_list(
            _require_mapping(output.get("uncertainty"), "adjudication uncertainty").get(
                "field_codes"
            ),
            "adjudication uncertainty field_codes",
        )
    )
    for field in _COMPARISON_FIELDS:
        key = _CELL_KEYS_BY_COMPARISON_FIELD[field]
        output_value = output.get(key)
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value == right_value:
            if output_value != left_value:
                if (
                    field == "uncertainty"
                    and unresolved
                    and _is_permitted_unresolved_value(
                        field,
                        output_value,
                        left_value,
                        right_value,
                        differing_fields=differing_field_set,
                    )
                ):
                    source = "unresolved"
                else:
                    raise KP1982BootstrapReviewError(
                        "adjudication changed a field on which both inputs agree"
                    )
            else:
                source = "both"
        elif output_value == left_value:
            source = "pass_a"
        elif output_value == right_value:
            source = "pass_b"
        elif _is_permitted_unresolved_value(
            field,
            output_value,
            left_value,
            right_value,
            differing_fields=differing_field_set,
        ):
            source = "unresolved"
        else:
            raise KP1982BootstrapReviewError(
                "adjudication introduced a field value absent from both input reviews"
            )
        if field in differing_fields:
            if source in {"pass_a", "pass_b"}:
                selected_sources.add(source)
            if (
                source == "unresolved"
                or _field_value_is_unresolved(field, output_value)
                or field in output_uncertainty_fields
            ):
                unresolved = True

    if not differing_fields:
        expected_codes = {"inputs_agree"}
        resolution_code = "inputs_agree_after_exact_comparison"
    else:
        expected_codes: set[str] = set()
        if selected_sources == {"pass_a"}:
            expected_codes.add("selected_pass_a")
            resolution_code = "selected_pass_a"
        elif selected_sources == {"pass_b"}:
            expected_codes.add("selected_pass_b")
            resolution_code = "selected_pass_b"
        elif selected_sources == {"pass_a", "pass_b"}:
            expected_codes.add("selected_fields_from_both_inputs")
            resolution_code = "selected_fields_from_both_inputs"
        else:
            resolution_code = "left_unresolved"
        if unresolved:
            expected_codes.add("left_unresolved")
            resolution_code = "left_unresolved"
        if not expected_codes:
            expected_codes.add("left_unresolved")
    actual_codes = set(_require_list(output.get("adjudication_codes"), "adjudication_codes"))
    if actual_codes != expected_codes:
        raise KP1982BootstrapReviewError("adjudication codes do not match selected input fields")
    return resolution_code


def _field_value_is_unresolved(field: str, value: object) -> bool:
    if field == "occupancy":
        return value == "uncertain"
    if field == "condition":
        return value in {"unreadable", "unresolved"}
    if field == "glyph_core":
        return isinstance(value, Mapping) and value.get("derivation_status") == "unresolved"
    if field == "printed_marks":
        if not isinstance(value, list):
            return False
        return any(
            isinstance(mark, Mapping)
            and (
                mark.get("nonsemantic_class") == "unresolved"
                or mark.get("association") == "unresolved"
                or mark.get("condition") == "unresolved"
            )
            for mark in value
        )
    if not isinstance(value, Mapping):
        return False
    if field == "cell_geometry":
        return value.get("decision") == "unresolved"
    if field in {"upper_catalog_rank", "lower_primary_identifier"}:
        return value.get("status") in _UNRESOLVED_IDENTIFIER_STATUSES
    if field == "glyph_with_marks":
        return value.get("status") == "unresolved"
    if field == "uncertainty":
        return value.get("status") in {"uncertain", "unresolved"}
    return False


def _is_permitted_unresolved_value(
    field: str,
    output: object,
    left: object,
    right: object,
    *,
    differing_fields: set[str],
) -> bool:
    if field == "occupancy":
        return output == "uncertain"
    if field == "condition":
        return output == "unresolved"
    if field == "glyph_core":
        if output is None:
            return False
        core = _require_mapping(output, "adjudicated glyph_core")
        if core.get("derivation_status") != "unresolved":
            return False
        left_evidence = (
            None if left is None else _require_mapping(left, "left glyph_core").get("evidence")
        )
        right_evidence = (
            None if right is None else _require_mapping(right, "right glyph_core").get("evidence")
        )
        return core.get("evidence") in (left_evidence, right_evidence)
    if field == "printed_marks":
        return False
    output_mapping = _require_mapping(output, f"adjudicated {field}")
    left_mapping = _require_mapping(left, f"left {field}")
    right_mapping = _require_mapping(right, f"right {field}")
    if field == "cell_geometry":
        if output_mapping.get("decision") != "unresolved":
            return False
        output_pair = (
            output_mapping.get("cell_evidence"),
            output_mapping.get("context_evidence"),
        )
        if output_pair not in (
            (
                left_mapping.get("cell_evidence"),
                left_mapping.get("context_evidence"),
            ),
            (
                right_mapping.get("cell_evidence"),
                right_mapping.get("context_evidence"),
            ),
        ):
            return False
        allowed_reasons = set(
            _require_list(left_mapping.get("reason_codes"), "left geometry reasons")
        ) | set(_require_list(right_mapping.get("reason_codes"), "right geometry reasons"))
        allowed_reasons.add("unresolved_boundary")
        output_reasons = set(
            _require_list(output_mapping.get("reason_codes"), "output geometry reasons")
        )
        return "unresolved_boundary" in output_reasons and output_reasons.issubset(allowed_reasons)
    if field in {"upper_catalog_rank", "lower_primary_identifier"}:
        if (
            output_mapping.get("status") != "unresolved"
            or output_mapping.get("raw_text") is not None
            or output_mapping.get("evidence")
            not in (left_mapping.get("evidence"), right_mapping.get("evidence"))
        ):
            return False
        allowed = set(
            _require_list(left_mapping.get("anomaly_codes"), "left identifier anomalies")
        ) | set(_require_list(right_mapping.get("anomaly_codes"), "right identifier anomalies"))
        return set(
            _require_list(output_mapping.get("anomaly_codes"), "output identifier anomalies")
        ).issubset(allowed)
    if field == "glyph_with_marks":
        if output_mapping.get("status") != "unresolved" or output_mapping.get("evidence") not in (
            left_mapping.get("evidence"),
            right_mapping.get("evidence"),
        ):
            return False
        allowed = set(
            _require_list(left_mapping.get("anomaly_codes"), "left glyph anomalies")
        ) | set(_require_list(right_mapping.get("anomaly_codes"), "right glyph anomalies"))
        return set(
            _require_list(output_mapping.get("anomaly_codes"), "output glyph anomalies")
        ).issubset(allowed)
    if field == "uncertainty":
        if output_mapping.get("status") != "unresolved":
            return False
        allowed_fields = set(
            _require_list(left_mapping.get("field_codes"), "left uncertainty fields")
        ) | set(_require_list(right_mapping.get("field_codes"), "right uncertainty fields"))
        allowed_fields.update(differing_fields)
        allowed_fields.update({"adjudication", "uncertainty"})
        output_fields = set(
            _require_list(output_mapping.get("field_codes"), "output uncertainty fields")
        )
        allowed_reasons = set(
            _require_list(left_mapping.get("reason_codes"), "left uncertainty reasons")
        ) | set(_require_list(right_mapping.get("reason_codes"), "right uncertainty reasons"))
        allowed_reasons.add("input_reviews_disagree")
        output_reasons = set(
            _require_list(output_mapping.get("reason_codes"), "output uncertainty reasons")
        )
        return (
            {"adjudication", "uncertainty"}.issubset(output_fields)
            and bool(output_fields.intersection(differing_fields))
            and "input_reviews_disagree" in output_reasons
            and output_fields.issubset(allowed_fields)
            and output_reasons.issubset(allowed_reasons)
        )
    return False


def _validate_text_safety(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_safe_text(key)
            _validate_text_safety(child)
    elif isinstance(value, list):
        for child in value:
            _validate_text_safety(child)
    elif isinstance(value, str):
        _validate_safe_text(value)


def _validate_safe_text(value: str) -> None:
    if any(
        unicodedata.category(character) in {"Cc", "Cf"}
        or unicodedata.bidirectional(character) in _BIDI_CLASSES
        for character in value
    ):
        raise KP1982BootstrapReviewError(
            "bootstrap review text contains a control or bidi formatting character"
        )


def _reject_forbidden_review_keys(value: object, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = (*path, key)
            if key in _FORBIDDEN_INTERPRETIVE_KEYS or key in _FORBIDDEN_CIRCULAR_KEYS:
                raise KP1982BootstrapReviewError(
                    "bootstrap review contains a forbidden interpretive or circular field"
                )
            if key == "decipherment" and child_path != ("assurances", "decipherment"):
                raise KP1982BootstrapReviewError(
                    "bootstrap review contains a forbidden interpretive field"
                )
            _reject_forbidden_review_keys(child, path=child_path)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_review_keys(child, path=path)


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1982BootstrapReviewError(f"{label} must be an object")
    return value


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise KP1982BootstrapReviewError(f"{label} must be an array")
    return value


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1982BootstrapReviewError(f"{label} must be a non-empty string")
    return value


def _require_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1982BootstrapReviewError(f"{label} must be an integer")
    return value
