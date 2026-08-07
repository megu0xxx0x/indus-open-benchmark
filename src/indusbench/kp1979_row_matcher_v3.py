"""V3-plan-bound private KP1979 development row proposal envelope.

This additive adapter preserves the V1 row matcher and separator bytes. It
authorizes a matcher configuration only by exact V3 recalibration from the raw
glyph PBMs committed by the supplied roster. The structural V3 plan validator
is deliberately not an authorization boundary.

Tier B remains calibration-only provisional evidence. It never disables the
speck stability gate and never promotes a speck-failed real-row result. Only
development rows on public PDF pages 22 through 77 may reach the row loader.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import kp1979_row_matcher as v1
from .io import encode_json
from .kp1979_glyph_match import MatcherConfig, parse_canonical_pbm
from .kp1979_match_calibration import MAX_MATCHER_PLAN_BYTES
from .kp1979_match_calibration_v3 import (
    CALIBRATION_PROTOCOL_ID,
    MATCHER_PLAN_ID,
    CalibrationGrid,
    matcher_config_from_recomputed_plan_v3,
)
from .kp1979_row_separator import match_row_with_separator
from .schema_validation import validate_schema_instance

PROPOSAL_SCHEMA = "kp1979-row-match-proposal-v2.schema.json"
PROPOSAL_ID = "KP1979:BASE:DEVELOPMENT:ROW-MATCH-PROPOSAL:V2"
STATUS = "private_development_shape_proposals_v3_plan_require_independent_validation"
SCIENTIFIC_SCOPE = (
    "language-blind shape proposals intended for owner-only storage for the KP1979 "
    "development rows under an exactly recomputed V3 candidate-ranking plan; Tier B "
    "remains provisional and nonaccepted, catalog ranks, segmentation paths, row geometry, "
    "and sign sequences are unaccepted, the future evaluation page is reserved and this "
    "matcher run does not load its row pixels, and no speck robustness, reading direction, "
    "language, meaning, translation, decipherment, or prize claim is present"
)

MATCHING_POLICY = dict(v1.MATCHING_POLICY)
CALIBRATION_SCOPE = {
    "calibration_protocol_id": CALIBRATION_PROTOCOL_ID,
    "matcher_plan_id": MATCHER_PLAN_ID,
    "matcher_plan_status": "frozen_closed_template_candidate_ranking_only",
    "threshold_state": "frozen",
    "closed_set_validation_gate_applies_to": "glyph_matcher_core_only",
    "closed_template_candidate_ranking_only": True,
    "candidate_coverage_floors_use_tier_a_plus_b": True,
    "tier_a_stable_positive_aggregate_floor_verified": True,
    "tier_b_disposition": "provisional_speck_sensitive",
    "tier_b_accepted": False,
    "speck_robustness_claimed": False,
    "zero_tier_a_plus_b_wrong_ranked_verified": True,
    "zero_tier_a_plus_b_single_glyph_splits_verified": True,
    "collision_identity_controls_abstained": True,
    "predeclared_stratified_coverage_floors_verified": True,
    "trusted_compiled_calibration_grid_bound": True,
    "configuration_and_metrics_recomputed_from_committed_template_pbms": True,
    "validation_evaluated_once_after_selection": True,
    "validation_reselection_permitted": False,
    "open_set_allograph_generalization_claimed": False,
    "row_separator_calibration_claimed": False,
    "real_row_performance_claimed": False,
    "development_rows_consumed_by_calibration": False,
    "future_evaluation_pixels_consumed_by_calibration": False,
    "thresholds_selected_from_open_set_lovo": False,
}
ASSURANCES = {
    **v1.ASSURANCES,
    "matcher_plan_v3_candidate_ranking_scope_verified": True,
    "tier_b_accepted": False,
    "speck_robustness_claimed": False,
    "real_row_tier_assigned": False,
}

JsonObject = dict[str, Any]
GlyphLoader = v1.GlyphLoader
RowLoader = v1.RowLoader

_TRUSTED_CALIBRATION_GRID = CalibrationGrid()


def build_row_match_proposal_v3(
    row_assignment_bytes: bytes,
    template_roster_bytes: bytes,
    matcher_plan_bytes: bytes,
    glyph_loader: GlyphLoader,
    row_loader: RowLoader,
) -> JsonObject:
    """Build owner-only development proposals from one exact frozen V3 plan."""

    if not callable(glyph_loader) or not callable(row_loader):
        raise v1.KP1979RowMatcherError("private glyph and row loaders must be callable")

    development_ids = v1.development_row_ids(row_assignment_bytes)
    assignment, slots = v1._validated_assignment(row_assignment_bytes)
    slots_by_id = {slot_id: slot for slot_id, _page, slot in slots}

    roster, index, template_pbms = v1._validated_template_index(
        template_roster_bytes,
        glyph_loader,
    )
    config, plan = _validated_matcher_plan_v3(
        matcher_plan_bytes,
        template_roster_bytes,
        template_pbms,
    )

    rows: list[JsonObject] = []
    for row_id in development_ids:
        slot = slots_by_id[row_id]
        row_bytes = v1._load_committed_row(slot, row_loader)
        try:
            row_mask = parse_canonical_pbm(row_bytes)
        except ValueError as error:
            raise v1.KP1979RowMatcherError("development row PBM is not canonical") from error
        relative_label_bbox = v1._relative_label_bbox(
            slot,
            row_mask.width,
            row_mask.height,
        )
        try:
            proposal = match_row_with_separator(
                row_id=row_id,
                row_pbm=row_bytes,
                proposed_label_bbox=relative_label_bbox,
                index=index,
                config=config,
            )
        except (RecursionError, ValueError) as error:
            raise v1.KP1979RowMatcherError("development row shape matching failed") from error
        v1._validate_separator_result(
            proposal,
            row_id=row_id,
            relative_label_bbox=relative_label_bbox,
        )
        _validate_speck_nonpromotion(proposal)
        rows.append(
            {
                "row_id": row_id,
                "page_index": v1._exact_integer(slot.get("page_index"), "row page index"),
                "pdf_page_number": v1._exact_integer(
                    slot.get("pdf_page_number"),
                    "row PDF page number",
                ),
                "lane_index": v1._exact_integer(slot.get("lane_index"), "row lane index"),
                "visual_row_index": v1._exact_integer(
                    slot.get("visual_row_index"),
                    "visual row index",
                ),
                "assignment_locator": {
                    "proposed_row_bbox": list(
                        v1._bbox(slot.get("proposed_row_bbox"), "proposed row bbox")
                    ),
                    "proposed_label_bbox": list(
                        v1._bbox(slot.get("proposed_label_bbox"), "proposed label bbox")
                    ),
                    "relative_proposed_label_bbox": list(relative_label_bbox),
                },
                "row_crop": {
                    "sha256": v1._tagged_sha256(
                        slot.get("row_crop_sha256"),
                        "row crop digest",
                    ),
                    "byte_size": len(row_bytes),
                    "width": row_mask.width,
                    "height": row_mask.height,
                },
                "proposal": proposal,
            }
        )

    output: JsonObject = {
        "schema_version": "0.2.0",
        "manifest_id": PROPOSAL_ID,
        "record_state": "private_owner_only_development_proposal",
        "status": STATUS,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "input_bindings": {
            "row_assignment": v1._input_binding(
                v1._nonempty_string(assignment.get("manifest_id"), "row assignment ID"),
                row_assignment_bytes,
            ),
            "template_roster": v1._input_binding(
                v1._nonempty_string(roster.get("manifest_id"), "template roster ID"),
                template_roster_bytes,
            ),
            "matcher_plan": v1._input_binding(
                v1._nonempty_string(plan.get("matcher_plan_id"), "matcher plan ID"),
                matcher_plan_bytes,
            ),
        },
        "partition_policy": dict(v1.PARTITION_POLICY),
        "matching_policy": dict(MATCHING_POLICY),
        "calibration_scope": dict(CALIBRATION_SCOPE),
        "withheld_fields": list(v1.WITHHELD_FIELDS),
        "rows": rows,
        "assurances": dict(ASSURANCES),
    }
    v1._reject_forbidden_keys(output)
    _validate_proposal_v3(output)
    if len(encode_json(output)) > v1.MAX_PROPOSAL_BYTES:
        raise v1.KP1979RowMatcherError("generated V3 row-match proposal exceeds its byte limit")
    return output


def verify_row_match_proposal_v3_bytes(
    row_assignment_bytes: bytes,
    template_roster_bytes: bytes,
    matcher_plan_bytes: bytes,
    glyph_loader: GlyphLoader,
    row_loader: RowLoader,
    proposal_bytes: bytes,
) -> dict[str, bool | str]:
    """Rebuild and exact-byte-check one untrusted private V3 proposal."""

    proposal = v1._decode_object(
        proposal_bytes,
        label="V3 row-match proposal",
        max_bytes=v1.MAX_PROPOSAL_BYTES,
    )
    v1._reject_forbidden_keys(proposal)
    _validate_proposal_v3(proposal)
    if proposal_bytes != encode_json(proposal):
        raise v1.KP1979RowMatcherError("V3 row-match proposal bytes are not canonical")
    expected = build_row_match_proposal_v3(
        row_assignment_bytes,
        template_roster_bytes,
        matcher_plan_bytes,
        glyph_loader,
        row_loader,
    )
    if proposal != expected or proposal_bytes != encode_json(expected):
        raise v1.KP1979RowMatcherError("V3 row-match proposal differs from exact recomputation")
    return {
        "valid": True,
        "claim_class": "private_kp1979_development_shape_proposals_v3_plan_only",
        "raw_input_bytes_bound": True,
        "row_crop_commitments_verified": True,
        "template_glyph_commitments_verified": True,
        "frozen_matcher_plan_v3_verified": True,
        "proposal_canonical_bytes_verified": True,
        "reserved_future_rows_loaded": False,
        "row_assignment_source_pixels_recomputed": False,
        "template_roster_source_inputs_recomputed": False,
        "tier_b_accepted": False,
        "speck_robustness_claimed": False,
        "real_row_tier_assigned": False,
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


def _validated_matcher_plan_v3(
    plan_bytes: bytes,
    roster_bytes: bytes,
    template_pbms: Sequence[tuple[str, int, bytes]],
) -> tuple[MatcherConfig, JsonObject]:
    try:
        config = matcher_config_from_recomputed_plan_v3(
            plan_bytes,
            roster_bytes,
            template_pbms,
            grid=_TRUSTED_CALIBRATION_GRID,
        )
    except (RecursionError, ValueError) as error:
        raise v1.KP1979RowMatcherError(
            "V3 matcher plan exact template-only recomputation failed"
        ) from error
    if not config.require_speck_stability or not config.require_shift_stability:
        raise v1.KP1979RowMatcherError("V3 matcher configuration weakens stability")
    plan = v1._decode_object(
        plan_bytes,
        label="V3 matcher plan",
        max_bytes=MAX_MATCHER_PLAN_BYTES,
    )
    if (
        plan_bytes != encode_json(plan)
        or plan.get("matcher_plan_id") != MATCHER_PLAN_ID
        or plan.get("calibration_protocol_id") != CALIBRATION_PROTOCOL_ID
        or plan.get("status") != "frozen_closed_template_candidate_ranking_only"
        or plan.get("threshold_state") != "frozen"
    ):
        raise v1.KP1979RowMatcherError("V3 matcher plan identity or canonical bytes differ")
    return config, plan


def _validate_speck_nonpromotion(value: Mapping[str, Any]) -> None:
    paths = value.get("candidate_paths")
    if not isinstance(paths, list) or not paths:
        return
    best = v1._mapping(paths[0], "V3 separator best path")
    gates = v1._mapping(best.get("matcher_gates"), "V3 matcher gates")
    speck = gates.get("speck_ablation_stability_passed")
    if not isinstance(speck, bool):
        raise v1.KP1979RowMatcherError("V3 matcher speck gate is invalid")
    if speck:
        return
    outer_gates = v1._mapping(value.get("gates"), "V3 separator gates")
    if (
        best.get("matcher_proposal_status") == "proposed"
        or value.get("proposal_status") == "proposed"
        or outer_gates.get("best_matcher_proposed") is not False
    ):
        raise v1.KP1979RowMatcherError("V3 speck-failed evidence was promoted")


def _validate_proposal_v3(value: JsonObject) -> None:
    issues = validate_schema_instance(value, v1._schema_path(PROPOSAL_SCHEMA))
    if issues:
        raise v1.KP1979RowMatcherError(f"V3 row-match proposal schema invalid at {issues[0].path}")


__all__ = [
    "ASSURANCES",
    "CALIBRATION_SCOPE",
    "MATCHING_POLICY",
    "PROPOSAL_ID",
    "PROPOSAL_SCHEMA",
    "SCIENTIFIC_SCOPE",
    "STATUS",
    "build_row_match_proposal_v3",
    "verify_row_match_proposal_v3_bytes",
]
