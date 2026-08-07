"""Tiered template-only calibration for the KP1979 glyph matcher.

V3 reuses the V2 synthetic control bytes, identities, folds, and calibration
grid exactly.  It changes only how matcher evidence is ranked: a fully stable
proposal is Tier A, while a proposal whose only failed matcher gate is speck
ablation stability is retained as non-accepted Tier B evidence named
``provisional_speck_sensitive``.  No row, page, assignment, or filesystem API
is present in this module.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any, Literal

from . import kp1979_match_calibration as v2
from .io import encode_json
from .kp1979_glyph_match import (
    MATCHER_ALGORITHM_ID,
    SCORE_SCALE,
    MatcherConfig,
    TemplateIndex,
    _match_row_sequence_from_workspace,
    _prepare_row_match_workspace,
    _RowMatchWorkspace,
    build_template_index,
    match_row_sequence,
    parse_canonical_pbm,
)

CALIBRATION_PROTOCOL_ID = "kp1979-template-only-match-calibration-v3"
MATCHER_PLAN_ID = "KP1979:GLYPH-MATCHER-PLAN:V3"
MATCHER_PLAN_SCHEMA_VERSION = "0.3.0"
COVERAGE_POLICY_ID = "kp1979-template-only-tiered-candidate-coverage-v3"

CalibrationGrid = v2.CalibrationGrid
KP1979MatchCalibrationError = v2.KP1979MatchCalibrationError
TemplatePBM = tuple[str, int, bytes]
TierName = Literal["tier_a_stable", "tier_b_provisional_speck_sensitive"]

_POSITIVE_CONTROL_STRATA = ("identity", "other_view", "concatenation")
_CANDIDATE_COVERAGE_FRACTIONS = {
    "identity": (99, 100),
    "other_view": (19, 20),
    "concatenation": (4, 5),
}
_TIER_A_AGGREGATE_FRACTION = (3, 4)
_TIER_A = "tier_a_stable"
_TIER_B = "tier_b_provisional_speck_sensitive"
_FOLD_PROTOCOL = dict(v2._FOLD_PROTOCOL)

_PLAN_KEYS = frozenset(
    {
        "schema_version",
        "matcher_plan_id",
        "calibration_protocol_id",
        "matcher_algorithm_id",
        "status",
        "threshold_state",
        "template_roster_commitment",
        "calibration_grid",
        "configuration",
        "claim_scope",
        "fold_protocol",
        "selection_rule",
        "coverage_policy",
        "closed_set_controls",
        "open_set_lovo_negative_control",
        "cross_rank_normalized_equality",
        "assurances",
    }
)
_MATCHER_CONFIG_KEYS = frozenset(
    {
        "candidate_aspect_slack_ppm",
        "cut_gap_support_ppm",
        "max_cut_penalty",
        "max_token_cost",
        "min_different_rank_margin",
        "min_path_margin",
        "require_shift_stability",
        "require_speck_stability",
        "top_paths",
        "top_ranks_per_span",
        "unknown_edge_cost",
    }
)
_CLAIM_SCOPE = {
    "closed_template_candidate_ranking_only": True,
    "speck_robustness_claimed": False,
    "open_set_allograph_generalization_claimed": False,
    "real_row_performance_claimed": False,
    "accepted_identity_or_sequence": False,
    "accepted_transcription": False,
    "reading_direction_inferred": False,
    "language_or_frequency_prior_used": False,
    "decipherment": False,
    "prize_submission_eligible": False,
}
_SELECTION_RULE = (
    "require_zero_tier_a_plus_b_wrong_ranked",
    "require_zero_tier_a_plus_b_single_glyph_splits",
    "require_predeclared_candidate_stratum_coverage_floors",
    "require_all_collision_identity_controls_to_abstain",
    "require_tier_a_stable_positive_aggregate_floor",
    "maximize_tier_a_stable_correct_ranked",
    "maximize_tier_a_plus_b_correct_ranked",
    "tie_break_using_v2_strictness_order",
    "evaluate_validation_once_after_selection_without_reselection",
)
_ASSURANCES = {
    "template_pbms_only": True,
    "v2_control_case_bytes_reused": True,
    "v2_control_case_ids_reused": True,
    "v2_hash_domain_reused": True,
    "v2_fold_assignment_reused": True,
    "v2_calibration_grid_reused": True,
    "development_rows_consumed_by_calibration": False,
    "future_evaluation_pixels_consumed_by_calibration": False,
    "validation_used_for_threshold_selection": False,
    "validation_used_for_diagnostics": False,
    "validation_evaluated_only_after_selection": True,
    "validation_reselection_permitted": False,
    "tier_b_disposition": "provisional_speck_sensitive",
    "tier_b_accepted": False,
    "no_go_floor_revision_permitted": False,
    "thresholds_selected_from_open_set_lovo": False,
    "human_review_complete": False,
    "evaluation_admissible": False,
    "public_release_authorized": False,
    "decipherment": False,
    "prize_submission_eligible": False,
}


@dataclass(frozen=True, slots=True)
class _V3Observation:
    case_id: str
    fold: int
    expected_ranks: tuple[int, ...]
    predicted_ranks: tuple[int, ...]
    single_source_glyph: bool
    stratum: str
    candidate_path_available: bool
    contains_unknown: bool
    absolute_shape_cost_passed: bool
    different_rank_margin_passed: bool
    speck_ablation_stability_passed: bool
    normalization_shift_stability_passed: bool
    sign_region_boundary_clear: bool
    minimum_rank_margin: int
    path_margin: int
    proposal_status: str
    negative_control_passed: bool


@dataclass(frozen=True, slots=True)
class V3ThresholdEvaluation:
    """Aggregate used by the deterministic V3 threshold selector."""

    config: MatcherConfig
    wrong_ranked: int
    split_errors: int
    tier_a_correct_ranked: int
    tier_b_correct_ranked: int
    case_count: int
    coverage_floor_passed: bool = True

    def __post_init__(self) -> None:
        counts = (
            self.wrong_ranked,
            self.split_errors,
            self.tier_a_correct_ranked,
            self.tier_b_correct_ranked,
            self.case_count,
        )
        if any(not _is_count(value) for value in counts):
            raise KP1979MatchCalibrationError("V3 threshold evaluation counts are invalid")
        if sum(counts[:4]) > self.case_count:
            raise KP1979MatchCalibrationError("V3 ranked outcomes exceed evaluated cases")
        if not isinstance(self.coverage_floor_passed, bool):
            raise KP1979MatchCalibrationError("V3 coverage-floor state is invalid")
        if not self.config.require_speck_stability or not self.config.require_shift_stability:
            raise KP1979MatchCalibrationError("V3 threshold evaluation weakens stability")

    @property
    def correct_ranked(self) -> int:
        return self.tier_a_correct_ranked + self.tier_b_correct_ranked


def calibrate_matcher_plan_v3(
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> dict[str, Any]:
    """Return a deterministic V3 plan from template-only controls."""

    return _calibrate_matcher_plan_v3(template_pbms, grid=grid, use_workspace=True)


def build_closed_set_control_cases_v3(
    template_pbms: Iterable[TemplatePBM],
) -> tuple[v2._ControlCase, ...]:
    """Return the exact V2 control cases inherited by V3."""

    return v2.build_closed_set_control_cases(template_pbms)


def _calibrate_matcher_plan_v3_reference(
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> dict[str, Any]:
    """Run V3 without the case-local matcher workspace for differential tests."""

    return _calibrate_matcher_plan_v3(template_pbms, grid=grid, use_workspace=False)


def _calibrate_matcher_plan_v3(
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None,
    use_workspace: bool,
) -> dict[str, Any]:
    selected_grid = grid if grid is not None else CalibrationGrid()
    sources = v2._materialize_sources(template_pbms)
    index = build_template_index(
        (source.variant_id, source.catalog_rank, source.raw_bytes) for source in sources
    )
    controls = v2._build_closed_set_control_cases(
        sources,
        collision_variant_ids=index.cross_rank_normalized_variant_ids,
    )
    if len(controls) > v2.MAX_CONTROL_CASES:
        raise KP1979MatchCalibrationError("template-only control inventory exceeds its limit")
    calibration_cases = tuple(case for case in controls if case.fold != v2.VALIDATION_FOLD)
    validation_cases = tuple(case for case in controls if case.fold == v2.VALIDATION_FOLD)
    if not calibration_cases or not validation_cases:
        raise KP1979MatchCalibrationError("hash folds did not populate both control partitions")

    probe_specs = tuple(
        product(
            selected_grid.max_token_costs,
            selected_grid.cut_policies,
            selected_grid.min_different_rank_margins,
        )
    )
    probes = tuple(
        v2._config(
            max_token_cost=max_token_cost,
            rank_margin=rank_margin,
            path_margin=0,
            cut_support=cut_support,
            cut_penalty=cut_penalty,
            grid=selected_grid,
            stability=True,
        )
        for max_token_cost, (cut_support, cut_penalty), rank_margin in probe_specs
    )
    if use_workspace:
        observation_lists: list[list[_V3Observation]] = [[] for _ in probes]
        for case in calibration_cases:
            workspace = _prepare_row_match_workspace(
                row_id=v2._safe_case_row_id(case.case_id),
                row_pbm=case.row_pbm,
                sign_region_bbox=None,
                index=index,
                config=probes[0],
            )
            for position, probe in enumerate(probes):
                observation_lists[position].append(
                    _probe_case_v3(case, index=index, config=probe, workspace=workspace)
                )
        observations_by_probe = tuple(tuple(values) for values in observation_lists)
    else:
        observations_by_probe = tuple(
            tuple(_probe_case_v3(case, index=index, config=probe) for case in calibration_cases)
            for probe in probes
        )

    evaluations: list[V3ThresholdEvaluation] = []
    observations_by_evaluation: list[tuple[_V3Observation, ...]] = []
    for (
        max_token_cost,
        (cut_support, cut_penalty),
        rank_margin,
    ), observations in zip(probe_specs, observations_by_probe, strict=True):
        for path_margin in selected_grid.min_path_margins:
            config = v2._config(
                max_token_cost=max_token_cost,
                rank_margin=rank_margin,
                path_margin=path_margin,
                cut_support=cut_support,
                cut_penalty=cut_penalty,
                grid=selected_grid,
                stability=True,
            )
            evaluations.append(_aggregate_v3_observations(observations, config=config))
            observations_by_evaluation.append(observations)

    selected = select_v3_threshold_evaluation(evaluations)
    plan_status = "no_go"
    threshold_state = "not_frozen"
    selected_config: MatcherConfig | None = None
    calibration_metrics = _empty_v3_metrics(calibration_cases)
    validation_metrics = _empty_v3_metrics(validation_cases)
    lovo_metrics = v2._empty_lovo_metrics()
    if selected is not None:
        selected_config = selected.config
        selected_position = next(
            position for position, evaluation in enumerate(evaluations) if evaluation is selected
        )
        calibration_observations = observations_by_evaluation[selected_position]
        # Validation is deliberately absent from grid evaluation and
        # diagnostics.  Each held-out case is matched once, here, only after
        # the calibration-only selector has fixed one configuration.
        validation_observations = tuple(
            _probe_case_v3(case, index=index, config=selected_config) for case in validation_cases
        )
        calibration_evaluation = _aggregate_v3_observations(
            calibration_observations,
            config=selected_config,
        )
        validation_evaluation = _aggregate_v3_observations(
            validation_observations,
            config=selected_config,
        )
        calibration_metrics = _evaluation_mapping_v3(
            calibration_evaluation,
            calibration_observations,
            config=selected_config,
        )
        validation_metrics = _evaluation_mapping_v3(
            validation_evaluation,
            validation_observations,
            config=selected_config,
        )
        if _eligible_v3_evaluation(calibration_evaluation) and _eligible_v3_evaluation(
            validation_evaluation
        ):
            plan_status = "frozen_closed_template_candidate_ranking_only"
            threshold_state = "frozen"
            lovo_metrics = v2._lovo_negative_control(
                sources,
                index=index,
                config=selected_config,
            )

    equality_groups = v2.detect_cross_rank_normalized_equalities(index)
    return {
        "schema_version": MATCHER_PLAN_SCHEMA_VERSION,
        "matcher_plan_id": MATCHER_PLAN_ID,
        "calibration_protocol_id": CALIBRATION_PROTOCOL_ID,
        "matcher_algorithm_id": MATCHER_ALGORITHM_ID,
        "status": plan_status,
        "threshold_state": threshold_state,
        "template_roster_commitment": v2._template_roster_commitment(sources),
        "calibration_grid": selected_grid.to_mapping(),
        "configuration": (
            selected_config.to_mapping()
            if selected_config is not None and threshold_state == "frozen"
            else None
        ),
        "claim_scope": dict(_CLAIM_SCOPE),
        "fold_protocol": dict(_FOLD_PROTOCOL),
        "selection_rule": list(_SELECTION_RULE),
        "coverage_policy": _coverage_policy_mapping_v3(),
        "closed_set_controls": {
            "calibration": calibration_metrics,
            "validation": validation_metrics,
        },
        "open_set_lovo_negative_control": lovo_metrics,
        "cross_rank_normalized_equality": {
            "group_count": len(equality_groups),
            "affected_variant_count": sum(len(group["variant_ids"]) for group in equality_groups),
            "forces_different_rank_ambiguity": True,
        },
        "assurances": dict(_ASSURANCES),
    }


def _probe_case_v3(
    case: v2._ControlCase,
    *,
    index: TemplateIndex,
    config: MatcherConfig,
    workspace: _RowMatchWorkspace | None = None,
) -> _V3Observation:
    row_id = v2._safe_case_row_id(case.case_id)
    if workspace is None:
        row = parse_canonical_pbm(case.row_pbm)
        result = match_row_sequence(
            row_id=row_id,
            row_pbm=case.row_pbm,
            sign_region_bbox=(0, 0, row.width, row.height),
            index=index,
            config=config,
        )
    else:
        if (
            workspace.row_id != row_id
            or workspace.row_pbm_sha256 != hashlib.sha256(case.row_pbm).digest()
        ):
            raise KP1979MatchCalibrationError("row match workspace belongs to another case")
        result = _match_row_sequence_from_workspace(workspace, index=index, config=config)
    paths = result.get("candidate_paths")
    gates = result.get("gates")
    proposal_status = result.get("proposal_status")
    if (
        not isinstance(paths, list)
        or not isinstance(gates, Mapping)
        or not isinstance(proposal_status, str)
    ):
        raise KP1979MatchCalibrationError("matcher returned invalid V3 evidence")

    def gate(name: str) -> bool:
        value = gates.get(name)
        if not isinstance(value, bool):
            raise KP1979MatchCalibrationError("matcher returned a non-boolean V3 gate")
        return value

    absolute = gate("absolute_shape_cost_passed")
    rank_margin_passed = gate("different_rank_margin_passed")
    speck = gate("speck_ablation_stability_passed")
    shift = gate("normalization_shift_stability_passed")
    boundary = gate("sign_region_boundary_clear")
    if not paths:
        return _V3Observation(
            case_id=case.case_id,
            fold=case.fold,
            expected_ranks=case.expected_ranks,
            predicted_ranks=(),
            single_source_glyph=case.single_source_glyph,
            stratum=case.stratum,
            candidate_path_available=False,
            contains_unknown=True,
            absolute_shape_cost_passed=absolute,
            different_rank_margin_passed=rank_margin_passed,
            speck_ablation_stability_passed=speck,
            normalization_shift_stability_passed=shift,
            sign_region_boundary_clear=boundary,
            minimum_rank_margin=0,
            path_margin=0,
            proposal_status=proposal_status,
            negative_control_passed=False,
        )

    best = paths[0]
    if not isinstance(best, Mapping) or not isinstance(best.get("segments"), list):
        raise KP1979MatchCalibrationError("matcher returned an invalid V3 best path")
    segments = best["segments"]
    if any(not isinstance(segment, Mapping) for segment in segments):
        raise KP1979MatchCalibrationError("matcher returned an invalid V3 segment")
    kinds = tuple(segment.get("segment_kind") for segment in segments)
    if any(kind not in {"rank_proposal", "unmatched_ink"} for kind in kinds):
        raise KP1979MatchCalibrationError("matcher returned an unknown V3 segment kind")
    rank_segments = [
        segment for segment in segments if segment.get("segment_kind") == "rank_proposal"
    ]
    try:
        predicted = tuple(int(segment["catalog_rank"]) for segment in rank_segments)
        minimum_margin = min(
            (int(segment["different_rank_margin"]) for segment in rank_segments),
            default=0,
        )
        if len(paths) > 1:
            second = paths[1]
            if not isinstance(second, Mapping):
                raise TypeError("second candidate path is not a mapping")
            path_margin = int(second["margin_from_best"])
        else:
            path_margin = 100 * SCORE_SCALE
    except (KeyError, TypeError, ValueError) as error:
        raise KP1979MatchCalibrationError("matcher returned invalid V3 numeric evidence") from error
    collision_identity = case.stratum == "collision_identity"
    negative_control_passed = (
        collision_identity and proposal_status == "ambiguous" and not rank_margin_passed
    )
    return _V3Observation(
        case_id=case.case_id,
        fold=case.fold,
        expected_ranks=case.expected_ranks,
        predicted_ranks=predicted,
        single_source_glyph=case.single_source_glyph,
        stratum=case.stratum,
        candidate_path_available=True,
        contains_unknown=len(rank_segments) != len(segments),
        absolute_shape_cost_passed=absolute,
        different_rank_margin_passed=rank_margin_passed,
        speck_ablation_stability_passed=speck,
        normalization_shift_stability_passed=shift,
        sign_region_boundary_clear=boundary,
        minimum_rank_margin=minimum_margin,
        path_margin=path_margin,
        proposal_status=proposal_status,
        negative_control_passed=negative_control_passed,
    )


def _classify_v3_tier(
    observation: _V3Observation,
    *,
    config: MatcherConfig,
) -> TierName | None:
    common = (
        observation.candidate_path_available
        and not observation.contains_unknown
        and bool(observation.predicted_ranks)
        and observation.absolute_shape_cost_passed
        and observation.different_rank_margin_passed
        and observation.minimum_rank_margin >= config.min_different_rank_margin
        and observation.path_margin >= config.min_path_margin
        and observation.normalization_shift_stability_passed
        and observation.sign_region_boundary_clear
    )
    if not common:
        return None
    if observation.speck_ablation_stability_passed:
        return _TIER_A if observation.proposal_status == "proposed" else None
    return _TIER_B if observation.proposal_status == "ambiguous" else None


def _v3_outcome(
    observation: _V3Observation,
    *,
    config: MatcherConfig,
) -> tuple[TierName | None, str] | None:
    tier = _classify_v3_tier(observation, config=config)
    if observation.stratum == "collision_identity":
        if tier is not None:
            return tier, "wrong"
        if observation.negative_control_passed:
            return None, "collision_correct"
        return None
    if tier is None:
        return None
    if observation.single_source_glyph and len(observation.predicted_ranks) != 1:
        return tier, "split"
    if observation.predicted_ranks == observation.expected_ranks:
        return tier, "correct"
    return tier, "wrong"


def _aggregate_v3_observations(
    observations: Sequence[_V3Observation],
    *,
    config: MatcherConfig,
) -> V3ThresholdEvaluation:
    wrong = 0
    split = 0
    tier_a_correct = 0
    tier_b_correct = 0
    for observation in observations:
        outcome = _v3_outcome(observation, config=config)
        if outcome is None:
            continue
        tier, result = outcome
        if result == "wrong":
            wrong += 1
        elif result == "split":
            split += 1
        elif result == "correct" and tier == _TIER_A:
            tier_a_correct += 1
        elif result == "correct" and tier == _TIER_B:
            tier_b_correct += 1
    return V3ThresholdEvaluation(
        config=config,
        wrong_ranked=wrong,
        split_errors=split,
        tier_a_correct_ranked=tier_a_correct,
        tier_b_correct_ranked=tier_b_correct,
        case_count=len(observations),
        coverage_floor_passed=_v3_coverage_floor_passed(observations, config=config),
    )


def _v3_stratum_metrics(
    observations: Sequence[_V3Observation],
    *,
    config: MatcherConfig,
) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for stratum in _POSITIVE_CONTROL_STRATA:
        members = tuple(item for item in observations if item.stratum == stratum)
        correct = sum(
            (outcome := _v3_outcome(item, config=config)) is not None and outcome[1] == "correct"
            for item in members
        )
        numerator, denominator = _CANDIDATE_COVERAGE_FRACTIONS[stratum]
        output[stratum] = {
            "case_count": len(members),
            "tier_a_plus_b_correct_ranked": correct,
            "required_correct_ranked": _ceil_fraction(len(members), numerator, denominator),
        }
    return output


def _tier_a_aggregate_metrics(
    observations: Sequence[_V3Observation],
    *,
    config: MatcherConfig,
) -> dict[str, int]:
    members = tuple(item for item in observations if item.stratum in _POSITIVE_CONTROL_STRATA)
    correct = sum(
        (outcome := _v3_outcome(item, config=config)) is not None
        and outcome == (_TIER_A, "correct")
        for item in members
    )
    numerator, denominator = _TIER_A_AGGREGATE_FRACTION
    return {
        "positive_case_count": len(members),
        "correct_ranked": correct,
        "required_correct_ranked": _ceil_fraction(len(members), numerator, denominator),
    }


def _v3_coverage_floor_passed(
    observations: Sequence[_V3Observation],
    *,
    config: MatcherConfig,
) -> bool:
    strata_passed = all(
        values["case_count"] >= 1
        and values["tier_a_plus_b_correct_ranked"] >= values["required_correct_ranked"]
        for values in _v3_stratum_metrics(observations, config=config).values()
    )
    tier_a = _tier_a_aggregate_metrics(observations, config=config)
    tier_a_passed = (
        tier_a["positive_case_count"] >= 1
        and tier_a["correct_ranked"] >= tier_a["required_correct_ranked"]
    )
    collisions = tuple(item for item in observations if item.stratum == "collision_identity")
    collision_passed = all(item.negative_control_passed for item in collisions)
    return strata_passed and tier_a_passed and collision_passed


def _eligible_v3_evaluation(evaluation: V3ThresholdEvaluation) -> bool:
    return (
        evaluation.case_count > 0
        and evaluation.wrong_ranked == 0
        and evaluation.split_errors == 0
        and evaluation.correct_ranked > 0
        and evaluation.coverage_floor_passed
    )


def select_v3_threshold_evaluation(
    evaluations: Sequence[V3ThresholdEvaluation],
) -> V3ThresholdEvaluation | None:
    """Select by V3 tiers, then use the exact V2 strictness tie order."""

    eligible = [evaluation for evaluation in evaluations if _eligible_v3_evaluation(evaluation)]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda evaluation: (
            -evaluation.tier_a_correct_ranked,
            -evaluation.correct_ranked,
            *_v2_strict_tie_key(evaluation.config),
        ),
    )


def _v2_strict_tie_key(config: MatcherConfig) -> tuple[object, ...]:
    return (
        config.max_token_cost,
        -config.min_different_rank_margin,
        -config.min_path_margin,
        -config.cut_gap_support_ppm,
        -config.max_cut_penalty,
        tuple(sorted(config.to_mapping().items())),
    )


def _tier_metrics(
    observations: Sequence[_V3Observation],
    *,
    config: MatcherConfig,
) -> dict[str, dict[str, int | bool | str]]:
    counts: dict[str, dict[str, int]] = {
        _TIER_A: {"correct_ranked": 0, "wrong_ranked": 0, "single_glyph_splits": 0},
        _TIER_B: {"correct_ranked": 0, "wrong_ranked": 0, "single_glyph_splits": 0},
    }
    for observation in observations:
        outcome = _v3_outcome(observation, config=config)
        if outcome is None:
            continue
        tier, result = outcome
        if tier is None:
            continue
        if result == "correct":
            counts[tier]["correct_ranked"] += 1
        elif result == "wrong":
            counts[tier]["wrong_ranked"] += 1
        elif result == "split":
            counts[tier]["single_glyph_splits"] += 1
    tier_a = counts[_TIER_A]
    tier_b = counts[_TIER_B]
    return {
        _TIER_A: {
            "disposition": "stable_proposal",
            **tier_a,
            "proposal_count": sum(tier_a.values()),
        },
        _TIER_B: {
            "disposition": "provisional_speck_sensitive",
            "accepted": False,
            **tier_b,
            "proposal_count": sum(tier_b.values()),
        },
    }


def _evaluation_mapping_v3(
    evaluation: V3ThresholdEvaluation,
    observations: Sequence[_V3Observation],
    *,
    config: MatcherConfig,
) -> dict[str, Any]:
    collisions = tuple(item for item in observations if item.stratum == "collision_identity")
    collision_proposals = sum(
        _classify_v3_tier(item, config=config) is not None for item in collisions
    )
    return {
        "case_count": evaluation.case_count,
        "tier_a_plus_b_wrong_ranked": evaluation.wrong_ranked,
        "tier_a_plus_b_single_glyph_splits": evaluation.split_errors,
        "tier_a_plus_b_correct_ranked": evaluation.correct_ranked,
        "coverage_floor_passed": evaluation.coverage_floor_passed,
        "candidate_tiers": _tier_metrics(observations, config=config),
        "strata": _v3_stratum_metrics(observations, config=config),
        "tier_a_stable_aggregate": _tier_a_aggregate_metrics(observations, config=config),
        "collision_identity_negative_control": {
            "case_count": len(collisions),
            "correct_abstained": sum(item.negative_control_passed for item in collisions),
            "required_correct_abstentions": len(collisions),
            "rank_proposals": collision_proposals,
        },
    }


def _empty_v3_metrics(cases: Sequence[v2._ControlCase]) -> dict[str, Any]:
    strata: dict[str, dict[str, int]] = {}
    positive_count = 0
    for stratum in _POSITIVE_CONTROL_STRATA:
        case_count = sum(case.stratum == stratum for case in cases)
        positive_count += case_count
        numerator, denominator = _CANDIDATE_COVERAGE_FRACTIONS[stratum]
        strata[stratum] = {
            "case_count": case_count,
            "tier_a_plus_b_correct_ranked": 0,
            "required_correct_ranked": _ceil_fraction(case_count, numerator, denominator),
        }
    tier_a_numerator, tier_a_denominator = _TIER_A_AGGREGATE_FRACTION
    collision_count = sum(case.stratum == "collision_identity" for case in cases)
    return {
        "case_count": len(cases),
        "tier_a_plus_b_wrong_ranked": 0,
        "tier_a_plus_b_single_glyph_splits": 0,
        "tier_a_plus_b_correct_ranked": 0,
        "coverage_floor_passed": False,
        "candidate_tiers": {
            _TIER_A: {
                "disposition": "stable_proposal",
                "correct_ranked": 0,
                "wrong_ranked": 0,
                "single_glyph_splits": 0,
                "proposal_count": 0,
            },
            _TIER_B: {
                "disposition": "provisional_speck_sensitive",
                "accepted": False,
                "correct_ranked": 0,
                "wrong_ranked": 0,
                "single_glyph_splits": 0,
                "proposal_count": 0,
            },
        },
        "strata": strata,
        "tier_a_stable_aggregate": {
            "positive_case_count": positive_count,
            "correct_ranked": 0,
            "required_correct_ranked": _ceil_fraction(
                positive_count,
                tier_a_numerator,
                tier_a_denominator,
            ),
        },
        "collision_identity_negative_control": {
            "case_count": collision_count,
            "correct_abstained": 0,
            "required_correct_abstentions": collision_count,
            "rank_proposals": 0,
        },
    }


def _coverage_policy_mapping_v3() -> dict[str, Any]:
    return {
        "policy_id": COVERAGE_POLICY_ID,
        "partition_assignment": v2._COVERAGE_POLICY["partition_assignment"],
        "selection_partition": "calibration_only",
        "validation_role": "single_held_out_qualification_only",
        "minimum_cases_per_stratum_per_partition": 1,
        "candidate_definition": "tier_a_plus_tier_b_correct_ranked",
        "minimum_candidate_correct_fractions": {
            stratum: {"numerator": fraction[0], "denominator": fraction[1]}
            for stratum, fraction in _CANDIDATE_COVERAGE_FRACTIONS.items()
        },
        "tier_a_stable_positive_aggregate": {
            "numerator": _TIER_A_AGGREGATE_FRACTION[0],
            "denominator": _TIER_A_AGGREGATE_FRACTION[1],
        },
        "tier_b": {
            "disposition": "provisional_speck_sensitive",
            "accepted": False,
            "only_failed_matcher_gate": "speck_ablation_stability_passed",
        },
        "cross_rank_collision_identity": {
            "role": "expected_different_rank_ambiguity_negative_control",
            "required_abstention_fraction": {"numerator": 1, "denominator": 1},
            "tier_a_or_b_rank_proposal_is_wrong_ranked": True,
        },
        "no_go_floor_revision_permitted": False,
    }


def _validate_matcher_plan_v3_structure(
    plan_bytes: bytes,
    template_roster_bytes: bytes,
) -> MatcherConfig | None:
    """Return an internal config only after structural plan validation."""

    plan = v2._decode_plan(plan_bytes)
    if set(plan) != _PLAN_KEYS:
        raise KP1979MatchCalibrationError("V3 matcher plan fields are not exact")
    for key, expected in (
        ("schema_version", MATCHER_PLAN_SCHEMA_VERSION),
        ("matcher_plan_id", MATCHER_PLAN_ID),
        ("calibration_protocol_id", CALIBRATION_PROTOCOL_ID),
        ("matcher_algorithm_id", MATCHER_ALGORITHM_ID),
    ):
        if plan.get(key) != expected:
            raise KP1979MatchCalibrationError("V3 matcher plan identity is invalid")
    status = plan.get("status")
    threshold_state = plan.get("threshold_state")
    if (status, threshold_state) not in {
        ("no_go", "not_frozen"),
        ("frozen_closed_template_candidate_ranking_only", "frozen"),
    }:
        raise KP1979MatchCalibrationError("V3 matcher plan state is invalid")

    bindings = v2._validated_template_bindings(template_roster_bytes)
    if plan.get("template_roster_commitment") != v2._binding_roster_commitment(bindings):
        raise KP1979MatchCalibrationError("V3 matcher plan template commitment differs")
    grid_mapping = v2._exact_mapping(
        plan.get("calibration_grid"),
        keys=frozenset(
            {
                "candidate_aspect_slack_ppm",
                "cut_policies",
                "max_token_costs",
                "min_different_rank_margins",
                "min_path_margins",
                "unknown_edge_cost",
            }
        ),
        label="V3 calibration grid",
    )
    try:
        grid = CalibrationGrid.from_mapping(grid_mapping)
    except (TypeError, ValueError) as error:
        raise KP1979MatchCalibrationError("V3 matcher plan grid is invalid") from error
    if grid.to_mapping() != grid_mapping:
        raise KP1979MatchCalibrationError("V3 matcher plan grid is not canonical")
    if (
        plan.get("claim_scope") != _CLAIM_SCOPE
        or plan.get("fold_protocol") != _FOLD_PROTOCOL
        or plan.get("selection_rule") != list(_SELECTION_RULE)
        or plan.get("coverage_policy") != _coverage_policy_mapping_v3()
        or plan.get("assurances") != _ASSURANCES
    ):
        raise KP1979MatchCalibrationError("V3 compiled protocol surface differs")

    config: MatcherConfig | None = None
    raw_config = plan.get("configuration")
    if status == "no_go":
        if raw_config is not None:
            raise KP1979MatchCalibrationError("V3 NO_GO plan must not freeze a configuration")
    else:
        config_mapping = v2._exact_mapping(
            raw_config,
            keys=_MATCHER_CONFIG_KEYS,
            label="V3 matcher configuration",
        )
        try:
            config = MatcherConfig.from_mapping(config_mapping)
        except ValueError as error:
            raise KP1979MatchCalibrationError("V3 matcher configuration is invalid") from error
        _validate_config_in_grid(config, grid=grid)

    controls = v2._exact_mapping(
        plan.get("closed_set_controls"),
        keys=frozenset({"calibration", "validation"}),
        label="V3 closed-set controls",
    )
    calibration = _verified_v3_metrics(controls.get("calibration"))
    validation = _verified_v3_metrics(controls.get("validation"))
    lovo_counts = _validate_lovo(
        plan.get("open_set_lovo_negative_control"), binding_count=len(bindings)
    )
    equality = _validate_equality_summary(
        plan.get("cross_rank_normalized_equality"),
        binding_count=len(bindings),
        calibration=calibration,
        validation=validation,
    )
    _validate_partition_inventory(
        binding_count=len(bindings),
        affected_count=equality["affected_variant_count"],
        calibration=calibration,
        validation=validation,
    )
    calibration_eligible = _verified_metrics_are_eligible(calibration)
    validation_eligible = _verified_metrics_are_eligible(validation)
    if status == "no_go":
        if calibration_eligible and validation_eligible:
            raise KP1979MatchCalibrationError("V3 NO_GO metrics are jointly eligible")
        if any(lovo_counts.values()):
            raise KP1979MatchCalibrationError("V3 NO_GO plan must not run LOVO")
    else:
        if not calibration_eligible or not validation_eligible:
            raise KP1979MatchCalibrationError("V3 frozen plan metrics are ineligible")
        if lovo_counts["case_count"] != len(bindings):
            raise KP1979MatchCalibrationError("V3 frozen plan must complete LOVO")
    return config


def validate_matcher_plan_v3(
    plan_bytes: bytes,
    template_roster_bytes: bytes,
) -> str:
    """Validate canonical structure without authorizing a matcher config.

    The return value is only the closed state ``"frozen"`` or ``"no_go"``.
    Runtime configuration requires exact raw-template recomputation through
    :func:`matcher_config_from_recomputed_plan_v3`.
    """

    config = _validate_matcher_plan_v3_structure(plan_bytes, template_roster_bytes)
    return "frozen" if config is not None else "no_go"


def validate_recomputed_matcher_plan_v3(
    plan_bytes: bytes,
    template_roster_bytes: bytes,
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> MatcherConfig | None:
    """Recompute and byte-verify a frozen or NO_GO V3 plan."""

    plan = v2._decode_plan(plan_bytes)
    if grid is not None and not isinstance(grid, CalibrationGrid):
        raise KP1979MatchCalibrationError("trusted V3 calibration grid has an invalid type")
    structurally_verified = _validate_matcher_plan_v3_structure(
        plan_bytes,
        template_roster_bytes,
    )
    selected_grid = grid if grid is not None else CalibrationGrid()
    if plan.get("calibration_grid") != selected_grid.to_mapping():
        raise KP1979MatchCalibrationError("V3 matcher plan does not bind the trusted grid")
    bindings = v2._validated_template_bindings(template_roster_bytes)
    sources = v2._materialize_sources(template_pbms)
    v2._verify_sources_against_bindings(sources, bindings=bindings)
    raw_values = tuple(
        (source.variant_id, source.catalog_rank, source.raw_bytes) for source in sources
    )
    recomputed = calibrate_matcher_plan_v3(raw_values, grid=selected_grid)
    if plan != recomputed or plan_bytes != encode_json(recomputed):
        raise KP1979MatchCalibrationError("V3 matcher plan differs from exact recomputation")
    if (
        structurally_verified is not None
        and recomputed.get("configuration") != structurally_verified.to_mapping()
    ):
        raise KP1979MatchCalibrationError("V3 matcher configuration differs after recomputation")
    return structurally_verified


def matcher_config_from_recomputed_plan_v3(
    plan_bytes: bytes,
    template_roster_bytes: bytes,
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> MatcherConfig:
    """Recompute one frozen V3 plan before any future row integration."""

    config = validate_recomputed_matcher_plan_v3(
        plan_bytes,
        template_roster_bytes,
        template_pbms,
        grid=grid,
    )
    if config is None:
        raise KP1979MatchCalibrationError("V3 recomputed matcher plan is not frozen")
    return config


def _verified_v3_metrics(value: object) -> dict[str, int | bool]:
    metrics = v2._exact_mapping(
        value,
        keys=frozenset(
            {
                "case_count",
                "tier_a_plus_b_wrong_ranked",
                "tier_a_plus_b_single_glyph_splits",
                "tier_a_plus_b_correct_ranked",
                "coverage_floor_passed",
                "candidate_tiers",
                "strata",
                "tier_a_stable_aggregate",
                "collision_identity_negative_control",
            }
        ),
        label="V3 closed-set metric",
    )
    counts = {
        key: v2._count(metrics.get(key), label="V3 closed-set count")
        for key in (
            "case_count",
            "tier_a_plus_b_wrong_ranked",
            "tier_a_plus_b_single_glyph_splits",
            "tier_a_plus_b_correct_ranked",
        )
    }
    coverage = metrics.get("coverage_floor_passed")
    if not isinstance(coverage, bool):
        raise KP1979MatchCalibrationError("V3 coverage-floor state is invalid")
    tiers = v2._exact_mapping(
        metrics.get("candidate_tiers"),
        keys=frozenset({_TIER_A, _TIER_B}),
        label="V3 candidate tiers",
    )
    tier_counts: dict[str, dict[str, int]] = {}
    for tier in (_TIER_A, _TIER_B):
        expected_keys = {
            "disposition",
            "correct_ranked",
            "wrong_ranked",
            "single_glyph_splits",
            "proposal_count",
        }
        if tier == _TIER_B:
            expected_keys.add("accepted")
        values = v2._exact_mapping(
            tiers.get(tier),
            keys=frozenset(expected_keys),
            label="V3 candidate tier",
        )
        if tier == _TIER_A and values.get("disposition") != "stable_proposal":
            raise KP1979MatchCalibrationError("V3 Tier A disposition is invalid")
        if tier == _TIER_B and (
            values.get("disposition") != "provisional_speck_sensitive"
            or values.get("accepted") is not False
        ):
            raise KP1979MatchCalibrationError("V3 Tier B disposition is invalid")
        parsed = {
            key: v2._count(values.get(key), label="V3 tier count")
            for key in (
                "correct_ranked",
                "wrong_ranked",
                "single_glyph_splits",
                "proposal_count",
            )
        }
        if parsed["proposal_count"] != sum(
            parsed[key] for key in ("correct_ranked", "wrong_ranked", "single_glyph_splits")
        ):
            raise KP1979MatchCalibrationError("V3 tier accounting is inconsistent")
        tier_counts[tier] = parsed

    strata = v2._exact_mapping(
        metrics.get("strata"),
        keys=frozenset(_POSITIVE_CONTROL_STRATA),
        label="V3 closed-set strata",
    )
    positive_count = 0
    stratum_correct = 0
    floors_passed = True
    output: dict[str, int | bool] = {**counts, "coverage_floor_passed": coverage}
    for stratum in _POSITIVE_CONTROL_STRATA:
        values = v2._exact_mapping(
            strata.get(stratum),
            keys=frozenset(
                {"case_count", "tier_a_plus_b_correct_ranked", "required_correct_ranked"}
            ),
            label="V3 closed-set stratum",
        )
        case_count = v2._count(values.get("case_count"), label="V3 stratum case count")
        correct = v2._count(values.get("tier_a_plus_b_correct_ranked"), label="V3 correct count")
        required = v2._count(values.get("required_correct_ranked"), label="V3 required count")
        numerator, denominator = _CANDIDATE_COVERAGE_FRACTIONS[stratum]
        if (
            case_count < 1
            or required != _ceil_fraction(case_count, numerator, denominator)
            or correct > case_count
        ):
            raise KP1979MatchCalibrationError("V3 stratum accounting is inconsistent")
        positive_count += case_count
        stratum_correct += correct
        floors_passed = floors_passed and correct >= required
        output[f"{stratum}_case_count"] = case_count

    tier_a = v2._exact_mapping(
        metrics.get("tier_a_stable_aggregate"),
        keys=frozenset({"positive_case_count", "correct_ranked", "required_correct_ranked"}),
        label="V3 Tier A aggregate",
    )
    tier_a_positive = v2._count(tier_a.get("positive_case_count"), label="V3 positive count")
    tier_a_correct = v2._count(tier_a.get("correct_ranked"), label="V3 Tier A correct count")
    tier_a_required = v2._count(tier_a.get("required_correct_ranked"), label="V3 Tier A required")
    tier_a_numerator, tier_a_denominator = _TIER_A_AGGREGATE_FRACTION
    if (
        tier_a_positive != positive_count
        or tier_a_required != _ceil_fraction(positive_count, tier_a_numerator, tier_a_denominator)
        or tier_a_correct != tier_counts[_TIER_A]["correct_ranked"]
        or tier_a_correct > positive_count
    ):
        raise KP1979MatchCalibrationError("V3 Tier A aggregate is inconsistent")
    floors_passed = floors_passed and tier_a_correct >= tier_a_required

    collision = v2._exact_mapping(
        metrics.get("collision_identity_negative_control"),
        keys=frozenset(
            {
                "case_count",
                "correct_abstained",
                "required_correct_abstentions",
                "rank_proposals",
            }
        ),
        label="V3 collision identity control",
    )
    collision_count = v2._count(collision.get("case_count"), label="V3 collision count")
    collision_correct = v2._count(
        collision.get("correct_abstained"), label="V3 collision abstention count"
    )
    collision_required = v2._count(
        collision.get("required_correct_abstentions"), label="V3 collision required count"
    )
    collision_proposals = v2._count(
        collision.get("rank_proposals"), label="V3 collision proposal count"
    )
    if (
        collision_required != collision_count
        or collision_correct + collision_proposals > collision_count
    ):
        raise KP1979MatchCalibrationError("V3 collision accounting is inconsistent")
    floors_passed = floors_passed and collision_correct == collision_count

    tier_wrong = sum(tier_counts[tier]["wrong_ranked"] for tier in (_TIER_A, _TIER_B))
    tier_splits = sum(tier_counts[tier]["single_glyph_splits"] for tier in (_TIER_A, _TIER_B))
    tier_correct = sum(tier_counts[tier]["correct_ranked"] for tier in (_TIER_A, _TIER_B))
    tier_proposals = sum(tier_counts[tier]["proposal_count"] for tier in (_TIER_A, _TIER_B))
    if (
        counts["case_count"] != positive_count + collision_count
        or counts["tier_a_plus_b_wrong_ranked"] != tier_wrong
        or counts["tier_a_plus_b_single_glyph_splits"] != tier_splits
        or counts["tier_a_plus_b_correct_ranked"] != tier_correct
        or stratum_correct != tier_correct
        or collision_proposals > tier_wrong
        or tier_proposals > counts["case_count"]
        or coverage != floors_passed
    ):
        raise KP1979MatchCalibrationError("V3 closed-set metric accounting differs")
    output["collision_case_count"] = collision_count
    output["tier_a_correct_ranked"] = tier_counts[_TIER_A]["correct_ranked"]
    output["tier_b_correct_ranked"] = tier_counts[_TIER_B]["correct_ranked"]
    return output


def _verified_metrics_are_eligible(metrics: Mapping[str, int | bool]) -> bool:
    return (
        int(metrics["case_count"]) > 0
        and int(metrics["tier_a_plus_b_wrong_ranked"]) == 0
        and int(metrics["tier_a_plus_b_single_glyph_splits"]) == 0
        and int(metrics["tier_a_plus_b_correct_ranked"]) > 0
        and metrics["coverage_floor_passed"] is True
    )


def _validate_config_in_grid(config: MatcherConfig, *, grid: CalibrationGrid) -> None:
    compiled = v2._config(
        max_token_cost=grid.max_token_costs[0],
        rank_margin=grid.min_different_rank_margins[0],
        path_margin=grid.min_path_margins[0],
        cut_support=grid.cut_policies[0][0],
        cut_penalty=grid.cut_policies[0][1],
        grid=grid,
        stability=True,
    )
    if (
        config.min_different_rank_margin < 1
        or config.min_path_margin < 1
        or not config.require_speck_stability
        or not config.require_shift_stability
        or (config.cut_gap_support_ppm == 0) != (config.max_cut_penalty == 0)
        or config.max_token_cost not in grid.max_token_costs
        or config.min_different_rank_margin not in grid.min_different_rank_margins
        or config.min_path_margin not in grid.min_path_margins
        or (config.cut_gap_support_ppm, config.max_cut_penalty) not in grid.cut_policies
        or config.unknown_edge_cost != grid.unknown_edge_cost
        or config.candidate_aspect_slack_ppm != grid.candidate_aspect_slack_ppm
        or config.top_paths != compiled.top_paths
        or config.top_ranks_per_span != compiled.top_ranks_per_span
    ):
        raise KP1979MatchCalibrationError("V3 matcher configuration weakens a frozen gate")


def _validate_lovo(value: object, *, binding_count: int) -> dict[str, int]:
    lovo = v2._exact_mapping(
        value,
        keys=frozenset(
            {
                "control_role",
                "used_for_threshold_selection",
                "generalization_claimed",
                "case_count",
                "same_rank_proposed",
                "wrong_rank_proposed",
                "abstained",
                "empty_gallery",
            }
        ),
        label="V3 LOVO negative control",
    )
    if (
        lovo.get("control_role") != "open_set_negative_control_only"
        or lovo.get("used_for_threshold_selection") is not False
        or lovo.get("generalization_claimed") is not False
    ):
        raise KP1979MatchCalibrationError("V3 LOVO scope is invalid")
    counts = {
        key: v2._count(lovo.get(key), label="V3 LOVO count")
        for key in (
            "case_count",
            "same_rank_proposed",
            "wrong_rank_proposed",
            "abstained",
            "empty_gallery",
        )
    }
    if counts["case_count"] not in {0, binding_count}:
        raise KP1979MatchCalibrationError("V3 LOVO case count is invalid")
    if counts["case_count"] and (
        counts["same_rank_proposed"] + counts["wrong_rank_proposed"] + counts["abstained"]
        != binding_count
        or counts["empty_gallery"] > counts["abstained"]
    ):
        raise KP1979MatchCalibrationError("V3 LOVO counts are inconsistent")
    if not counts["case_count"] and any(counts.values()):
        raise KP1979MatchCalibrationError("V3 empty LOVO counts are inconsistent")
    return counts


def _validate_equality_summary(
    value: object,
    *,
    binding_count: int,
    calibration: Mapping[str, int | bool],
    validation: Mapping[str, int | bool],
) -> dict[str, int]:
    equality = v2._exact_mapping(
        value,
        keys=frozenset(
            {"group_count", "affected_variant_count", "forces_different_rank_ambiguity"}
        ),
        label="V3 cross-rank equality summary",
    )
    group_count = v2._count(equality.get("group_count"), label="V3 equality group count")
    affected_count = v2._count(
        equality.get("affected_variant_count"), label="V3 affected variant count"
    )
    if (
        equality.get("forces_different_rank_ambiguity") is not True
        or affected_count > binding_count
        or 2 * group_count > affected_count
        or (group_count == 0) != (affected_count == 0)
        or int(calibration["collision_case_count"]) + int(validation["collision_case_count"])
        != affected_count
    ):
        raise KP1979MatchCalibrationError("V3 cross-rank equality summary is inconsistent")
    return {"group_count": group_count, "affected_variant_count": affected_count}


def _validate_partition_inventory(
    *,
    binding_count: int,
    affected_count: int,
    calibration: Mapping[str, int | bool],
    validation: Mapping[str, int | bool],
) -> None:
    expected_case_count = (
        3 * binding_count + 7 * v2.SYNTHETIC_REPLICATES_PER_LENGTH - 2 * affected_count
    )
    if int(calibration["case_count"]) + int(validation["case_count"]) != expected_case_count:
        raise KP1979MatchCalibrationError("V3 control coverage is inconsistent")
    positive_variant_count = binding_count - affected_count
    for stratum, total in (
        ("identity", positive_variant_count),
        ("other_view", 2 * positive_variant_count),
        ("concatenation", 7 * v2.SYNTHETIC_REPLICATES_PER_LENGTH),
    ):
        validation_quota = v2._validation_case_quota(total)
        if (
            int(calibration[f"{stratum}_case_count"]) != total - validation_quota
            or int(validation[f"{stratum}_case_count"]) != validation_quota
        ):
            raise KP1979MatchCalibrationError("V3 stratum inventory is inconsistent")
    collision_validation_quota = v2._validation_case_quota(affected_count)
    if (
        int(calibration["collision_case_count"]) != affected_count - collision_validation_quota
        or int(validation["collision_case_count"]) != collision_validation_quota
    ):
        raise KP1979MatchCalibrationError("V3 collision inventory is inconsistent")


def _ceil_fraction(case_count: int, numerator: int, denominator: int) -> int:
    return (case_count * numerator + denominator - 1) // denominator


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = [
    "CALIBRATION_PROTOCOL_ID",
    "COVERAGE_POLICY_ID",
    "MATCHER_PLAN_ID",
    "MATCHER_PLAN_SCHEMA_VERSION",
    "CalibrationGrid",
    "KP1979MatchCalibrationError",
    "V3ThresholdEvaluation",
    "build_closed_set_control_cases_v3",
    "calibrate_matcher_plan_v3",
    "matcher_config_from_recomputed_plan_v3",
    "select_v3_threshold_evaluation",
    "validate_matcher_plan_v3",
    "validate_recomputed_matcher_plan_v3",
]
