"""Private, development-only KP1979 row-matching proposal envelope.

The module consumes an already-created canonical row-assignment record.  It
does not call the assignment's pixel-recomputing verifier and it has no page
bitmap or PDF API.  The public page boundary is applied before any row crop is
loaded: rows on the reserved future page are never supplied to ``row_loader``.

Outputs contain private proposal material and should be stored owner-only; this
pure module does not enforce storage.  Catalog ranks and source geometry remain
machine proposals, and left-to-right coordinates are not a reading direction.
"""

from __future__ import annotations

import hashlib
import importlib.resources  # nosemgrep: python37-compatibility-importlib2 -- requires 3.11+
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .io import decode_json, encode_json
from .kp1979 import PAGE_HEIGHT, PAGE_WIDTH
from .kp1979_glyph_match import (
    MATCHER_ALGORITHM_ID,
    MAX_ROW_HEIGHT,
    MAX_ROW_PBM_BYTES,
    MAX_ROW_WIDTH,
    MatcherConfig,
    TemplateIndex,
    build_template_index,
    parse_canonical_pbm,
)
from .kp1979_match_calibration import (
    MAX_MATCHER_PLAN_BYTES,
    matcher_config_from_recomputed_plan,
)
from .kp1979_row_assignment import (
    ASSIGNMENT_SCHEMA,
    MAX_ASSIGNMENT_BYTES,
    ROW_VERTICAL_PADDING_PIXELS,
)
from .kp1979_row_separator import ROW_SEPARATOR_METHOD, match_row_with_separator
from .kp1979_sign_template_roster import (
    MANIFEST_ID as TEMPLATE_ROSTER_ID,
)
from .kp1979_sign_template_roster import (
    MAX_TEMPLATE_ROSTER_BYTES,
    TemplateBinding,
    template_bindings,
)
from .schema_validation import validate_schema_instance

PROPOSAL_SCHEMA = "kp1979-row-match-proposal.schema.json"
PROPOSAL_ID = "KP1979:BASE:DEVELOPMENT:ROW-MATCH-PROPOSAL:V1"
STATUS = "private_development_shape_proposals_require_independent_validation"
SCIENTIFIC_SCOPE = (
    "language-blind shape proposals intended for owner-only storage for the KP1979 "
    "development rows; catalog "
    "ranks, segmentation paths, row geometry, and sign sequences are unaccepted, the future "
    "evaluation page is reserved and this matcher run does not load its row pixels, and no "
    "reading direction, language, meaning, translation, decipherment, or prize claim is present"
)
FIRST_DEVELOPMENT_PDF_PAGE = 22
LAST_DEVELOPMENT_PDF_PAGE = 77
RESERVED_FUTURE_PDF_PAGE = 78
MAX_PROPOSAL_BYTES = 64 * 1024 * 1024
MAX_JSON_NESTING_DEPTH = 96
MAX_SLOT_COUNT = 5_000

PARTITION_POLICY = {
    "role": "private_development_only",
    "included_pdf_page_boundary": "public_pdf_pages_22_through_77",
    "reserved_future_pdf_page": RESERVED_FUTURE_PDF_PAGE,
    "reserved_future_rows_loaded": False,
    "caller_selectable_partition": False,
}
MATCHING_POLICY = {
    "matcher_algorithm_id": MATCHER_ALGORITHM_ID,
    "separator_method": ROW_SEPARATOR_METHOD,
    "visual_order": "left_to_right_coordinate_order_not_reading_direction",
    "template_scope": "closed_machine_provisional_signlist_variants_only",
    "maximum_retained_paths": 3,
    "language_or_frequency_prior_used": False,
}
CALIBRATION_SCOPE = {
    "matcher_plan_status": "frozen_closed_template_retrieval_only",
    "threshold_state": "frozen",
    "closed_set_validation_gate_applies_to": "glyph_matcher_core_only",
    "closed_template_near_exact_retrieval_only": True,
    "closed_set_validation_zero_false_accepts": True,
    "closed_set_validation_zero_accepted_single_glyph_splits": True,
    "predeclared_stratified_coverage_floors_verified": True,
    "trusted_compiled_calibration_grid_bound": True,
    "configuration_and_metrics_recomputed_from_committed_template_pbms": True,
    "open_set_allograph_generalization_claimed": False,
    "row_separator_calibration_claimed": False,
    "real_row_performance_claimed": False,
    "development_rows_consumed_by_calibration": False,
    "future_evaluation_pixels_consumed_by_calibration": False,
    "thresholds_selected_from_open_set_lovo": False,
}
WITHHELD_FIELDS = (
    "all_identifier_values",
    "all_code_values",
    "all_reading_direction_values",
    "all_language_values",
    "all_meaning_values",
    "all_translation_values",
    "all_accepted_sign_sequences",
    "all_evaluation_values",
)
ASSURANCES = {
    "row_assignment_schema_and_canonical_bytes_verified": True,
    "row_assignment_raw_bytes_bound": True,
    "row_assignment_source_pixels_recomputed": False,
    "template_roster_schema_and_canonical_bytes_verified": True,
    "template_roster_raw_bytes_bound": True,
    "template_roster_source_inputs_recomputed": False,
    "template_glyph_crop_commitments_reverified": True,
    "matcher_plan_structure_and_canonical_bytes_verified": True,
    "matcher_plan_raw_bytes_bound": True,
    "matcher_plan_freeze_and_scope_gates_verified": True,
    "matcher_plan_exact_template_only_recomputation_verified": True,
    "development_row_crop_commitments_verified": True,
    "reserved_future_rows_loaded": False,
    "row_geometry_accepted": False,
    "catalog_values_accepted": False,
    "sign_identity_accepted": False,
    "sign_sequences_accepted": False,
    "reading_direction_assigned": False,
    "language_assigned": False,
    "meaning_assigned": False,
    "translations_assigned": False,
    "human_review_complete": False,
    "independent_replication_complete": False,
    "public_release_authorized": False,
    "evaluation_admissible": False,
    "decipherment": False,
    "prize_submission_eligible": False,
}

_SLOT_ID = re.compile(r"\AKP1979:P([0-9]{3}):L([01]):V([0-9]{2})\Z")
_TAGGED_SHA256 = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
_FORBIDDEN_KEYS = frozenset(
    {
        "accepted_code",
        "accepted_identifier",
        "accepted_meaning",
        "accepted_sign",
        "accepted_translation",
        "code",
        "deciphered_text",
        "identifier",
        "language",
        "meaning",
        "ocr",
        "phonetic_value",
        "reading",
        "reading_direction",
        "sign_sequence",
        "transcription",
        "translation",
    }
)

JsonObject = dict[str, Any]
GlyphLoader = Callable[[str], bytes]
RowLoader = Callable[[str], bytes]


class KP1979RowMatcherError(ValueError):
    """Raised when a private proposal input or exact recomputation fails closed."""


def _schema_path(filename: str) -> Path:
    project_candidate = Path(__file__).resolve().parents[2] / "schemas" / filename
    if project_candidate.is_file():
        return project_candidate
    package_candidate = importlib.resources.files("indusbench").joinpath(f"schemas/{filename}")
    return Path(str(package_candidate))


def development_row_ids(row_assignment_bytes: bytes) -> tuple[str, ...]:
    """Return the closed development allowlist without loading any row pixels.

    The canonical assignment may contain its reserved boundary page.  Those
    IDs are validated as reserved and omitted here, so callers can create a
    descriptor-pinned row loader only after receiving this allowlist.
    """

    assignment, slots = _validated_assignment(row_assignment_bytes)
    del assignment
    selected = tuple(
        slot_id
        for slot_id, pdf_page_number, _slot in slots
        if FIRST_DEVELOPMENT_PDF_PAGE <= pdf_page_number <= LAST_DEVELOPMENT_PDF_PAGE
    )
    if not selected:
        raise KP1979RowMatcherError("row assignment contains no development rows")
    return selected


def build_row_match_proposal(
    row_assignment_bytes: bytes,
    template_roster_bytes: bytes,
    matcher_plan_bytes: bytes,
    glyph_loader: GlyphLoader,
    row_loader: RowLoader,
) -> JsonObject:
    """Build deterministic proposals intended for owner-only development storage."""

    if not callable(glyph_loader) or not callable(row_loader):
        raise KP1979RowMatcherError("private glyph and row loaders must be callable")

    # Resolve and validate the closed development allowlist before either
    # private loader is called.  In particular, reserved IDs cannot reach the
    # row loader even when they remain present in the source assignment.
    development_ids = development_row_ids(row_assignment_bytes)
    assignment, slots = _validated_assignment(row_assignment_bytes)
    slots_by_id = {slot_id: slot for slot_id, _page, slot in slots}

    roster, index, template_pbms = _validated_template_index(
        template_roster_bytes,
        glyph_loader,
    )
    config, plan = _validated_matcher_plan(
        matcher_plan_bytes,
        template_roster_bytes,
        template_pbms,
    )

    rows: list[JsonObject] = []
    for row_id in development_ids:
        slot = slots_by_id[row_id]
        row_bytes = _load_committed_row(slot, row_loader)
        try:
            row_mask = parse_canonical_pbm(row_bytes)
        except ValueError as error:
            raise KP1979RowMatcherError("development row PBM is not canonical") from error
        relative_label_bbox = _relative_label_bbox(slot, row_mask.width, row_mask.height)
        try:
            proposal = match_row_with_separator(
                row_id=row_id,
                row_pbm=row_bytes,
                proposed_label_bbox=relative_label_bbox,
                index=index,
                config=config,
            )
        except (RecursionError, ValueError) as error:
            raise KP1979RowMatcherError("development row shape matching failed") from error
        _validate_separator_result(
            proposal,
            row_id=row_id,
            relative_label_bbox=relative_label_bbox,
        )
        rows.append(
            {
                "row_id": row_id,
                "page_index": _exact_integer(slot.get("page_index"), "row page index"),
                "pdf_page_number": _exact_integer(
                    slot.get("pdf_page_number"),
                    "row PDF page number",
                ),
                "lane_index": _exact_integer(slot.get("lane_index"), "row lane index"),
                "visual_row_index": _exact_integer(
                    slot.get("visual_row_index"),
                    "visual row index",
                ),
                "assignment_locator": {
                    "proposed_row_bbox": list(
                        _bbox(slot.get("proposed_row_bbox"), "proposed row bbox")
                    ),
                    "proposed_label_bbox": list(
                        _bbox(slot.get("proposed_label_bbox"), "proposed label bbox")
                    ),
                    "relative_proposed_label_bbox": list(relative_label_bbox),
                },
                "row_crop": {
                    "sha256": _tagged_sha256(slot.get("row_crop_sha256"), "row crop digest"),
                    "byte_size": len(row_bytes),
                    "width": row_mask.width,
                    "height": row_mask.height,
                },
                "proposal": proposal,
            }
        )

    output: JsonObject = {
        "schema_version": "0.1.0",
        "manifest_id": PROPOSAL_ID,
        "record_state": "private_owner_only_development_proposal",
        "status": STATUS,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "input_bindings": {
            "row_assignment": _input_binding(
                _nonempty_string(assignment.get("manifest_id"), "row assignment ID"),
                row_assignment_bytes,
            ),
            "template_roster": _input_binding(
                _nonempty_string(roster.get("manifest_id"), "template roster ID"),
                template_roster_bytes,
            ),
            "matcher_plan": _input_binding(
                _nonempty_string(plan.get("matcher_plan_id"), "matcher plan ID"),
                matcher_plan_bytes,
            ),
        },
        "partition_policy": dict(PARTITION_POLICY),
        "matching_policy": dict(MATCHING_POLICY),
        "calibration_scope": dict(CALIBRATION_SCOPE),
        "withheld_fields": list(WITHHELD_FIELDS),
        "rows": rows,
        "assurances": dict(ASSURANCES),
    }
    _reject_forbidden_keys(output)
    _validate_proposal(output)
    if len(encode_json(output)) > MAX_PROPOSAL_BYTES:
        raise KP1979RowMatcherError("generated row-match proposal exceeds its byte limit")
    return output


def verify_row_match_proposal_bytes(
    row_assignment_bytes: bytes,
    template_roster_bytes: bytes,
    matcher_plan_bytes: bytes,
    glyph_loader: GlyphLoader,
    row_loader: RowLoader,
    proposal_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and exact-byte-check one untrusted private proposal envelope."""

    proposal = _decode_object(
        proposal_bytes,
        label="row-match proposal",
        max_bytes=MAX_PROPOSAL_BYTES,
    )
    _reject_forbidden_keys(proposal)
    _validate_proposal(proposal)
    if proposal_bytes != encode_json(proposal):
        raise KP1979RowMatcherError("row-match proposal bytes are not canonical")
    expected = build_row_match_proposal(
        row_assignment_bytes,
        template_roster_bytes,
        matcher_plan_bytes,
        glyph_loader,
        row_loader,
    )
    if proposal != expected or proposal_bytes != encode_json(expected):
        raise KP1979RowMatcherError("row-match proposal differs from exact recomputation")
    return {
        "valid": True,
        "claim_class": "private_kp1979_development_shape_proposals_only",
        "raw_input_bytes_bound": True,
        "row_crop_commitments_verified": True,
        "template_glyph_commitments_verified": True,
        "frozen_matcher_plan_verified": True,
        "proposal_canonical_bytes_verified": True,
        "reserved_future_rows_loaded": False,
        "row_assignment_source_pixels_recomputed": False,
        "template_roster_source_inputs_recomputed": False,
        "row_separator_calibration_claimed": False,
        "open_set_allograph_generalization_claimed": False,
        "real_row_performance_claimed": False,
        "row_geometry_accepted": False,
        "catalog_values_accepted": False,
        "sign_identity_accepted": False,
        "sign_sequences_accepted": False,
        "reading_direction_assigned": False,
        "language_assigned": False,
        "meaning_assigned": False,
        "translations_assigned": False,
        "human_review_complete": False,
        "independent_replication_complete": False,
        "public_release_authorized": False,
        "evaluation_admissible": False,
        "decipherment": False,
        "prize_submission_eligible": False,
    }


def _validated_assignment(
    raw_bytes: bytes,
) -> tuple[JsonObject, tuple[tuple[str, int, Mapping[str, Any]], ...]]:
    assignment = _decode_object(
        raw_bytes,
        label="row assignment",
        max_bytes=MAX_ASSIGNMENT_BYTES,
    )
    if raw_bytes != encode_json(assignment):
        raise KP1979RowMatcherError("row assignment bytes are not canonical")
    issues = validate_schema_instance(assignment, _schema_path(ASSIGNMENT_SCHEMA))
    if issues:
        raise KP1979RowMatcherError(f"row assignment schema invalid at {issues[0].path}")
    values = assignment.get("slots")
    if not isinstance(values, list) or not values or len(values) > MAX_SLOT_COUNT:
        raise KP1979RowMatcherError("row assignment slot coverage is invalid")

    slots: list[tuple[str, int, Mapping[str, Any]]] = []
    seen: set[str] = set()
    previous_order: tuple[int, int, int] | None = None
    for value in values:
        slot = _mapping(value, "row assignment slot")
        slot_id = _nonempty_string(slot.get("slot_id"), "row slot ID")
        match = _SLOT_ID.fullmatch(slot_id)
        if match is None:
            raise KP1979RowMatcherError("row slot ID is invalid")
        page_from_id = int(match.group(1))
        lane_from_id = int(match.group(2))
        visual_from_id = int(match.group(3))
        pdf_page_number = _exact_integer(slot.get("pdf_page_number"), "row PDF page number")
        page_index = _exact_integer(slot.get("page_index"), "row page index")
        lane_index = _exact_integer(slot.get("lane_index"), "row lane index")
        visual_index = _exact_integer(slot.get("visual_row_index"), "visual row index")
        if (
            page_from_id != pdf_page_number
            or page_index != pdf_page_number - 1
            or lane_from_id != lane_index
            or visual_from_id != visual_index
        ):
            raise KP1979RowMatcherError("row slot identity fields disagree")
        if not FIRST_DEVELOPMENT_PDF_PAGE <= pdf_page_number <= RESERVED_FUTURE_PDF_PAGE:
            raise KP1979RowMatcherError("row slot lies outside the fixed base boundary")
        if slot_id in seen:
            raise KP1979RowMatcherError("row assignment contains a duplicate slot ID")
        seen.add(slot_id)
        order = (pdf_page_number, lane_index, visual_index)
        if previous_order is not None and order <= previous_order:
            raise KP1979RowMatcherError("row assignment slots are not in canonical order")
        previous_order = order
        _validate_slot_geometry(slot)
        slots.append((slot_id, pdf_page_number, slot))
    return assignment, tuple(slots)


def _validated_matcher_plan(
    plan_bytes: bytes,
    roster_bytes: bytes,
    template_pbms: Sequence[tuple[str, int, bytes]],
) -> tuple[MatcherConfig, JsonObject]:
    try:
        config = matcher_config_from_recomputed_plan(
            plan_bytes,
            roster_bytes,
            template_pbms,
        )
    except (RecursionError, ValueError) as error:
        raise KP1979RowMatcherError(
            "matcher plan exact template-only recomputation failed"
        ) from error
    plan = _decode_object(
        plan_bytes,
        label="matcher plan",
        max_bytes=MAX_MATCHER_PLAN_BYTES,
    )
    if plan_bytes != encode_json(plan):
        raise KP1979RowMatcherError("matcher plan bytes are not canonical")
    return config, plan


def _validated_template_index(
    roster_bytes: bytes,
    glyph_loader: GlyphLoader,
) -> tuple[JsonObject, TemplateIndex, tuple[tuple[str, int, bytes], ...]]:
    if not isinstance(roster_bytes, bytes) or len(roster_bytes) > MAX_TEMPLATE_ROSTER_BYTES:
        raise KP1979RowMatcherError("template roster byte length is invalid")
    try:
        bindings = template_bindings(roster_bytes)
    except (RecursionError, ValueError) as error:
        raise KP1979RowMatcherError("template roster is invalid") from error
    roster = _decode_object(
        roster_bytes,
        label="template roster",
        max_bytes=MAX_TEMPLATE_ROSTER_BYTES,
    )
    if roster_bytes != encode_json(roster) or roster.get("manifest_id") != TEMPLATE_ROSTER_ID:
        raise KP1979RowMatcherError("template roster identity or canonical bytes differ")
    sources: list[tuple[str, int, bytes]] = []
    for binding in bindings:
        glyph_bytes = _load_glyph(binding, glyph_loader)
        sources.append((binding.variant_id, binding.catalog_rank, glyph_bytes))
    try:
        index = build_template_index(sources)
    except (RecursionError, ValueError) as error:
        raise KP1979RowMatcherError("template glyph index construction failed") from error
    return roster, index, tuple(sources)


def _load_glyph(binding: TemplateBinding, loader: GlyphLoader) -> bytes:
    try:
        raw_bytes = loader(binding.variant_id)
    except (KeyError, OSError, ValueError) as error:
        raise KP1979RowMatcherError("private template glyph loader failed") from error
    if not isinstance(raw_bytes, bytes):
        raise KP1979RowMatcherError("private template glyph loader did not return bytes")
    if len(raw_bytes) != binding.byte_size or _digest(raw_bytes) != binding.sha256:
        raise KP1979RowMatcherError("template glyph differs from its roster commitment")
    try:
        mask = parse_canonical_pbm(raw_bytes)
    except ValueError as error:
        raise KP1979RowMatcherError("template glyph PBM is not canonical") from error
    if mask.width != binding.width or mask.height != binding.height:
        raise KP1979RowMatcherError("template glyph dimensions differ from their commitment")
    return raw_bytes


def _load_committed_row(slot: Mapping[str, Any], loader: RowLoader) -> bytes:
    row_id = _nonempty_string(slot.get("slot_id"), "row slot ID")
    try:
        raw_bytes = loader(row_id)
    except (KeyError, OSError, ValueError) as error:
        raise KP1979RowMatcherError("private development row loader failed") from error
    if not isinstance(raw_bytes, bytes):
        raise KP1979RowMatcherError("private development row loader did not return bytes")
    expected_size = _positive_integer(slot.get("row_crop_byte_size"), "row crop byte size")
    expected_digest = _tagged_sha256(slot.get("row_crop_sha256"), "row crop digest")
    if expected_size > MAX_ROW_PBM_BYTES:
        raise KP1979RowMatcherError("row crop commitment exceeds the matcher byte limit")
    if len(raw_bytes) != expected_size or _digest(raw_bytes) != expected_digest:
        raise KP1979RowMatcherError("row crop differs from its assignment commitment")
    return raw_bytes


def _relative_label_bbox(
    slot: Mapping[str, Any],
    row_width: int,
    row_height: int,
) -> tuple[int, int, int, int]:
    row_x0, row_y0, row_x1, row_y1 = _bbox(
        slot.get("proposed_row_bbox"),
        "proposed row bbox",
    )
    label_x0, label_y0, label_x1, label_y1 = _bbox(
        slot.get("proposed_label_bbox"),
        "proposed label bbox",
    )
    if row_x1 - row_x0 != row_width or row_y1 - row_y0 != row_height:
        raise KP1979RowMatcherError("row PBM dimensions differ from the assignment bbox")
    relative = (
        label_x0 - row_x0,
        label_y0 - row_y0,
        label_x1 - row_x0,
        label_y1 - row_y0,
    )
    if not (
        0 <= relative[0] < relative[2] <= row_width and 0 <= relative[1] < relative[3] <= row_height
    ):
        raise KP1979RowMatcherError("relative label locator lies outside the row crop")
    return relative


def _validate_slot_geometry(slot: Mapping[str, Any]) -> None:
    row_x0, row_y0, row_x1, row_y1 = _bbox(
        slot.get("proposed_row_bbox"),
        "proposed row bbox",
    )
    label_x0, label_y0, label_x1, label_y1 = _bbox(
        slot.get("proposed_label_bbox"),
        "proposed label bbox",
    )
    lane_index = _exact_integer(slot.get("lane_index"), "row lane index")
    lane_x0 = lane_index * (PAGE_WIDTH // 2)
    lane_x1 = lane_x0 + (PAGE_WIDTH // 2)
    if not lane_x0 <= label_x0 < label_x1 <= lane_x1:
        raise KP1979RowMatcherError("proposed label bbox lies outside its page lane")
    expected_row_bbox = (
        lane_x0,
        max(0, label_y0 - ROW_VERTICAL_PADDING_PIXELS),
        label_x1,
        min(PAGE_HEIGHT, label_y1 + ROW_VERTICAL_PADDING_PIXELS),
    )
    if (row_x0, row_y0, row_x1, row_y1) != expected_row_bbox:
        raise KP1979RowMatcherError("proposed row bbox differs from the fixed crop policy")
    if row_x1 - row_x0 > MAX_ROW_WIDTH or row_y1 - row_y0 > MAX_ROW_HEIGHT:
        raise KP1979RowMatcherError("proposed row dimensions exceed matcher limits")
    expected_size = _positive_integer(slot.get("row_crop_byte_size"), "row crop byte size")
    if expected_size > MAX_ROW_PBM_BYTES:
        raise KP1979RowMatcherError("row crop byte commitment exceeds matcher limits")
    _tagged_sha256(slot.get("row_crop_sha256"), "row crop digest")


def _validate_separator_result(
    value: Mapping[str, Any],
    *,
    row_id: str,
    relative_label_bbox: Sequence[int],
) -> None:
    if value.get("row_id") != row_id:
        raise KP1979RowMatcherError("separator result row identity differs")
    if value.get("proposed_label_bbox") != list(relative_label_bbox):
        raise KP1979RowMatcherError("separator result label locator differs")
    paths = value.get("candidate_paths")
    if not isinstance(paths, list) or len(paths) > 3:
        raise KP1979RowMatcherError("separator result path coverage is invalid")
    previous_cost = -1
    for expected_index, path_value in enumerate(paths):
        path = _mapping(path_value, "separator candidate path")
        if path.get("path_index") != expected_index:
            raise KP1979RowMatcherError("separator candidate path order differs")
        cost = _nonnegative_integer(path.get("total_cost"), "candidate path cost")
        margin = _nonnegative_integer(path.get("margin_from_best"), "candidate path margin")
        if cost < previous_cost or (expected_index == 0 and margin != 0):
            raise KP1979RowMatcherError("separator candidate path costs are inconsistent")
        previous_cost = cost


def _validate_proposal(value: JsonObject) -> None:
    issues = validate_schema_instance(value, _schema_path(PROPOSAL_SCHEMA))
    if issues:
        raise KP1979RowMatcherError(f"row-match proposal schema invalid at {issues[0].path}")


def _decode_object(raw_bytes: bytes, *, label: str, max_bytes: int) -> JsonObject:
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > max_bytes:
        raise KP1979RowMatcherError(f"{label} byte length is invalid")
    try:
        value = decode_json(raw_bytes, source=label)
    except (RecursionError, ValueError) as error:
        raise KP1979RowMatcherError(f"{label} is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1979RowMatcherError(f"{label} must decode to an object")
    _check_nesting(value)
    return value


def _check_nesting(value: object) -> None:
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_JSON_NESTING_DEPTH:
            raise KP1979RowMatcherError("private JSON nesting exceeds its limit")
        if isinstance(current, Mapping):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)


def _reject_forbidden_keys(value: object) -> None:
    pending: list[object] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            if _FORBIDDEN_KEYS.intersection(current):
                raise KP1979RowMatcherError("row-match proposal contains an interpretation field")
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KP1979RowMatcherError(f"{label} must be an object")
    return value


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise KP1979RowMatcherError(f"{label} must be a nonempty string")
    return value


def _exact_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise KP1979RowMatcherError(f"{label} must be an integer")
    return value


def _nonnegative_integer(value: object, label: str) -> int:
    result = _exact_integer(value, label)
    if result < 0:
        raise KP1979RowMatcherError(f"{label} must be nonnegative")
    return result


def _positive_integer(value: object, label: str) -> int:
    result = _exact_integer(value, label)
    if result < 1:
        raise KP1979RowMatcherError(f"{label} must be positive")
    return result


def _bbox(value: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise KP1979RowMatcherError(f"{label} must contain four integers")
    x0 = _exact_integer(value[0], label)
    y0 = _exact_integer(value[1], label)
    x1 = _exact_integer(value[2], label)
    y1 = _exact_integer(value[3], label)
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise KP1979RowMatcherError(f"{label} is not a positive half-open rectangle")
    return x0, y0, x1, y1


def _tagged_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _TAGGED_SHA256.fullmatch(value) is None:
        raise KP1979RowMatcherError(f"{label} is not a tagged SHA-256")
    return value


def _digest(raw_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


def _input_binding(record_id: str, raw_bytes: bytes) -> JsonObject:
    return {
        "id": record_id,
        "sha256": _digest(raw_bytes),
        "byte_size": len(raw_bytes),
    }
