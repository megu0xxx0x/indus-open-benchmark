"""Template-only controls and threshold freezing for the KP1979 glyph matcher.

This module deliberately has no filesystem or page API.  Its only image inputs
are caller-supplied template PBM bytes.  Closed-set synthetic controls select a
configuration; leave-one-variant-out (LOVO) is reported only as an open-set
negative control and never as evidence of allograph generalisation.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from .io import decode_json, encode_json
from .kp1979_glyph_match import (
    MATCHER_ALGORITHM_ID,
    MAX_TEMPLATE_COUNT,
    SCORE_SCALE,
    BinaryMask,
    MatcherConfig,
    TemplateIndex,
    _match_row_sequence_from_workspace,
    _prepare_row_match_workspace,
    _RowMatchWorkspace,
    build_template_index,
    match_row_sequence,
    parse_canonical_pbm,
)
from .kp1979_sign_template_roster import TemplateBinding, template_bindings

CALIBRATION_PROTOCOL_ID = "kp1979-template-only-match-calibration-v2"
MATCHER_PLAN_ID = "KP1979:GLYPH-MATCHER-PLAN:V2"
MATCHER_PLAN_SCHEMA_VERSION = "0.2.0"
FOLD_COUNT = 5
VALIDATION_FOLD = 4
SYNTHETIC_PADDING = 6
SYNTHETIC_REPLICATES_PER_LENGTH = 3
MAX_GRID_CONFIGURATIONS = 256
MAX_CONTROL_CASES = 10_000
MAX_MATCHER_PLAN_BYTES = 1024 * 1024
MAX_MATCHER_PLAN_NESTING_DEPTH = 64
_HASH_DOMAIN = b"indusbench:kp1979:glyph-match-calibration:v2\x00"
_POSITIVE_CONTROL_STRATA = ("identity", "other_view", "concatenation")
_FOLD_STRATA = (*_POSITIVE_CONTROL_STRATA, "collision_identity")
# These result-independent floors are part of the protocol identity. Exact
# template retrieval must cover every identity control; perturbation and joint
# segmentation controls must each achieve a ceil-half floor.
_COVERAGE_FRACTIONS = {
    "identity": (1, 1),
    "other_view": (1, 2),
    "concatenation": (1, 2),
}
_COVERAGE_POLICY = {
    "policy_id": "kp1979-template-only-stratified-coverage-v1",
    "partition_assignment": "result-blind-sha256-stratified-fixed-quota-v1",
    "selection_partition": "calibration_only",
    "validation_role": "single_held_out_qualification_only",
    "minimum_cases_per_stratum_per_partition": 1,
    "minimum_correct_fractions": {
        stratum: {"numerator": fraction[0], "denominator": fraction[1]}
        for stratum, fraction in _COVERAGE_FRACTIONS.items()
    },
    "positive_view_eligibility": "exclude_cross_rank_normalized_collision_variants",
    "cross_rank_collision_identity": {
        "role": "expected_different_rank_ambiguity_negative_control",
        "required_abstention_fraction": {"numerator": 1, "denominator": 1},
        "rank_proposal_is_false_accept": True,
    },
}
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
_CLAIM_SCOPE = {
    "closed_template_near_exact_retrieval_only": True,
    "open_set_allograph_generalization_claimed": False,
    "language_or_frequency_prior_used": False,
    "reading_direction_inferred": False,
    "accepted_transcription": False,
    "decipherment": False,
}
_FOLD_PROTOCOL = {
    "algorithm": "sha256-domain-separated-stratified-fixed-quota-v1",
    "fold_count": FOLD_COUNT,
    "validation_fold": VALIDATION_FOLD,
    "development_rows_used": False,
    "page_images_used": False,
}
_SELECTION_RULE = (
    "require_zero_closed_set_false_accepted",
    "require_zero_accepted_single_glyph_splits",
    "require_predeclared_stratified_coverage_floors",
    "maximize_correct_accepted_coverage",
    "tie_break_lower_max_cost_then_higher_rank_path_cut_support_and_cut_penalty",
)
_ASSURANCES = {
    "template_pbms_only": True,
    "development_rows_consumed_by_calibration": False,
    "future_evaluation_pixels_consumed_by_calibration": False,
    "thresholds_selected_from_open_set_lovo": False,
    "human_review_complete": False,
    "evaluation_admissible": False,
    "public_release_authorized": False,
    "decipherment": False,
    "prize_submission_eligible": False,
}
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

TemplatePBM = tuple[str, int, bytes]


class KP1979MatchCalibrationError(ValueError):
    """Raised when template-only calibration cannot fail closed."""


@dataclass(frozen=True, slots=True)
class CalibrationGrid:
    """A bounded integer grid fixed before any development-row execution."""

    max_token_costs: tuple[int, ...] = (250_000, 500_000, 750_000, 1_000_000, 1_250_000)
    min_different_rank_margins: tuple[int, ...] = (1, 100_000, 200_000)
    min_path_margins: tuple[int, ...] = (1, 100_000, 250_000)
    cut_policies: tuple[tuple[int, int], ...] = ((0, 0), (125_000, 250_000))
    unknown_edge_cost: int = 4_500_000
    candidate_aspect_slack_ppm: int = 250_000

    def __post_init__(self) -> None:
        _validate_sorted_unique(
            self.max_token_costs,
            label="maximum token-cost grid",
            minimum=0,
            maximum=5 * SCORE_SCALE,
        )
        _validate_sorted_unique(
            self.min_different_rank_margins,
            label="different-rank margin grid",
            minimum=1,
            maximum=5 * SCORE_SCALE,
        )
        _validate_sorted_unique(
            self.min_path_margins,
            label="path-margin grid",
            minimum=1,
            maximum=100 * SCORE_SCALE,
        )
        if not self.cut_policies or len(set(self.cut_policies)) != len(self.cut_policies):
            raise KP1979MatchCalibrationError("cut-policy grid must be nonempty and unique")
        for policy in self.cut_policies:
            if not isinstance(policy, tuple) or len(policy) != 2:
                raise KP1979MatchCalibrationError("cut policy must contain two integers")
            support, penalty = policy
            if (
                not _is_int(support)
                or not _is_int(penalty)
                or not 0 <= support <= SCORE_SCALE
                or not 0 <= penalty <= 5 * SCORE_SCALE
                or (support == 0) != (penalty == 0)
            ):
                raise KP1979MatchCalibrationError("cut policy is outside its integer bounds")
        if not _is_int(self.unknown_edge_cost) or not 0 < self.unknown_edge_cost <= 5 * SCORE_SCALE:
            raise KP1979MatchCalibrationError("unknown-edge cost is outside its range")
        if (
            not _is_int(self.candidate_aspect_slack_ppm)
            or not 0 <= self.candidate_aspect_slack_ppm <= SCORE_SCALE
        ):
            raise KP1979MatchCalibrationError("candidate aspect slack is outside its range")
        if self.configuration_count > MAX_GRID_CONFIGURATIONS:
            raise KP1979MatchCalibrationError("calibration grid exceeds its configuration limit")

    @property
    def configuration_count(self) -> int:
        return (
            len(self.max_token_costs)
            * len(self.min_different_rank_margins)
            * len(self.min_path_margins)
            * len(self.cut_policies)
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "candidate_aspect_slack_ppm": self.candidate_aspect_slack_ppm,
            "cut_policies": [list(policy) for policy in self.cut_policies],
            "max_token_costs": list(self.max_token_costs),
            "min_different_rank_margins": list(self.min_different_rank_margins),
            "min_path_margins": list(self.min_path_margins),
            "unknown_edge_cost": self.unknown_edge_cost,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CalibrationGrid:
        required = {
            "candidate_aspect_slack_ppm",
            "cut_policies",
            "max_token_costs",
            "min_different_rank_margins",
            "min_path_margins",
            "unknown_edge_cost",
        }
        if set(value) != required:
            raise KP1979MatchCalibrationError("calibration grid fields are not exact")
        integer_rosters: dict[str, tuple[int, ...]] = {}
        for key in (
            "max_token_costs",
            "min_different_rank_margins",
            "min_path_margins",
        ):
            raw = value.get(key)
            if not isinstance(raw, list):
                raise KP1979MatchCalibrationError("calibration grid roster is invalid")
            integer_rosters[key] = tuple(raw)
        raw_policies = value.get("cut_policies")
        if not isinstance(raw_policies, list) or any(
            not isinstance(policy, list) or len(policy) != 2 for policy in raw_policies
        ):
            raise KP1979MatchCalibrationError("calibration cut-policy roster is invalid")
        return cls(
            max_token_costs=integer_rosters["max_token_costs"],
            min_different_rank_margins=integer_rosters["min_different_rank_margins"],
            min_path_margins=integer_rosters["min_path_margins"],
            cut_policies=tuple(tuple(policy) for policy in raw_policies),  # type: ignore[arg-type]
            unknown_edge_cost=value.get("unknown_edge_cost"),  # type: ignore[arg-type]
            candidate_aspect_slack_ppm=value.get(  # type: ignore[arg-type]
                "candidate_aspect_slack_ppm"
            ),
        )


@dataclass(frozen=True, slots=True)
class _VariantSource:
    variant_id: str
    catalog_rank: int
    raw_bytes: bytes
    source_width: int
    source_height: int
    tight_mask: BinaryMask


@dataclass(frozen=True, slots=True)
class _ControlCase:
    case_id: str
    fold: int
    row_pbm: bytes
    expected_ranks: tuple[int, ...]
    single_source_glyph: bool
    stratum: str


@dataclass(frozen=True, slots=True)
class _Observation:
    case_id: str
    fold: int
    expected_ranks: tuple[int, ...]
    predicted_ranks: tuple[int, ...]
    base_eligible: bool
    minimum_rank_margin: int
    path_margin: int
    single_source_glyph: bool
    stratum: str
    negative_control_passed: bool
    unexpected_rank_proposal: bool


@dataclass(frozen=True, slots=True)
class ThresholdEvaluation:
    """Aggregate used by the deterministic threshold selector."""

    config: MatcherConfig
    false_accepted: int
    split_errors: int
    correct_accepted: int
    case_count: int
    coverage_floor_passed: bool = True

    def __post_init__(self) -> None:
        for value in (
            self.false_accepted,
            self.split_errors,
            self.correct_accepted,
            self.case_count,
        ):
            if not _is_int(value) or value < 0:
                raise KP1979MatchCalibrationError("threshold evaluation counts are invalid")
        if self.correct_accepted > self.case_count:
            raise KP1979MatchCalibrationError("accepted count exceeds evaluated cases")
        if not isinstance(self.coverage_floor_passed, bool):
            raise KP1979MatchCalibrationError("coverage-floor state is invalid")


def calibrate_matcher_plan(
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> dict[str, Any]:
    """Return a deterministic matcher plan from template-only controls.

    Folds and coverage floors are fixed from case identities before matching.
    Grid selection sees only calibration cases and uses the same speck/shift
    gates as the final configuration.  The held-out partition is evaluated
    exactly once after selection.  LOVO cannot make the plan eligible.
    """

    return _calibrate_matcher_plan(template_pbms, grid=grid, use_workspace=True)


def _calibrate_matcher_plan_reference(
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> dict[str, Any]:
    """Retain the V2 uncached execution path for byte-exact differential tests."""

    return _calibrate_matcher_plan(template_pbms, grid=grid, use_workspace=False)


def _calibrate_matcher_plan(
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None,
    use_workspace: bool,
) -> dict[str, Any]:
    """Run the unchanged V2 protocol with either cached or reference matching."""

    selected_grid = grid if grid is not None else CalibrationGrid()
    sources = _materialize_sources(template_pbms)
    index = build_template_index(
        (source.variant_id, source.catalog_rank, source.raw_bytes) for source in sources
    )
    controls = _build_closed_set_control_cases(
        sources,
        collision_variant_ids=index.cross_rank_normalized_variant_ids,
    )
    if len(controls) > MAX_CONTROL_CASES:
        raise KP1979MatchCalibrationError("template-only control inventory exceeds its limit")
    calibration_cases = tuple(case for case in controls if case.fold != VALIDATION_FOLD)
    validation_cases = tuple(case for case in controls if case.fold == VALIDATION_FOLD)
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
        _config(
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
        observation_lists: list[list[_Observation]] = [[] for _ in probes]
        for case in calibration_cases:
            workspace = _prepare_row_match_workspace(
                row_id=_safe_case_row_id(case.case_id),
                row_pbm=case.row_pbm,
                sign_region_bbox=None,
                index=index,
                config=probes[0],
            )
            for position, probe in enumerate(probes):
                observation_lists[position].append(
                    _observe(
                        case,
                        index=index,
                        config=probe,
                        require_proposed_status=True,
                        workspace=workspace,
                    )
                )
        observations_by_probe = tuple(tuple(values) for values in observation_lists)
    else:
        observations_by_probe = tuple(
            tuple(
                _observe(case, index=index, config=probe, require_proposed_status=True)
                for case in calibration_cases
            )
            for probe in probes
        )

    evaluations: list[ThresholdEvaluation] = []
    observations_by_evaluation: list[tuple[_Observation, ...]] = []
    for (
        max_token_cost,
        (cut_support, cut_penalty),
        rank_margin,
    ), calibration_observations in zip(
        probe_specs,
        observations_by_probe,
        strict=True,
    ):
        # Path margin changes only the final joint-path gate.  Evaluate every
        # other final gate once, then share that result across path thresholds.
        for path_margin in selected_grid.min_path_margins:
            config = _config(
                max_token_cost=max_token_cost,
                rank_margin=rank_margin,
                path_margin=path_margin,
                cut_support=cut_support,
                cut_penalty=cut_penalty,
                grid=selected_grid,
                stability=True,
            )
            evaluations.append(_aggregate_observations(calibration_observations, config=config))
            observations_by_evaluation.append(calibration_observations)

    selected = select_threshold_evaluation(evaluations)
    plan_status = "no_go"
    threshold_state = "not_frozen"
    selected_config: MatcherConfig | None = None
    calibration_metrics = _empty_metrics(calibration_cases)
    validation_metrics = _empty_metrics(validation_cases)
    lovo_metrics = _empty_lovo_metrics()
    if selected is not None:
        selected_config = selected.config
        if use_workspace:
            selected_position = next(
                position
                for position, evaluation in enumerate(evaluations)
                if evaluation is selected
            )
            calibration_observations = observations_by_evaluation[selected_position]
        else:
            calibration_observations = tuple(
                _observe(case, index=index, config=selected_config, require_proposed_status=True)
                for case in calibration_cases
            )
        validation_observations = tuple(
            _observe(case, index=index, config=selected_config, require_proposed_status=True)
            for case in validation_cases
        )
        calibration_evaluation = _aggregate_observations(
            calibration_observations,
            config=selected_config,
        )
        validation_evaluation = _aggregate_observations(
            validation_observations,
            config=selected_config,
        )
        calibration_metrics = _evaluation_mapping(
            calibration_evaluation,
            calibration_observations,
            config=selected_config,
        )
        validation_metrics = _evaluation_mapping(
            validation_evaluation,
            validation_observations,
            config=selected_config,
        )
        if _eligible_evaluation(calibration_evaluation) and _eligible_evaluation(
            validation_evaluation
        ):
            plan_status = "frozen_closed_template_retrieval_only"
            threshold_state = "frozen"
            lovo_metrics = _lovo_negative_control(sources, index=index, config=selected_config)

    equality_groups = detect_cross_rank_normalized_equalities(index)
    return {
        "schema_version": MATCHER_PLAN_SCHEMA_VERSION,
        "matcher_plan_id": MATCHER_PLAN_ID,
        "calibration_protocol_id": CALIBRATION_PROTOCOL_ID,
        "matcher_algorithm_id": MATCHER_ALGORITHM_ID,
        "status": plan_status,
        "threshold_state": threshold_state,
        "template_roster_commitment": _template_roster_commitment(sources),
        "calibration_grid": selected_grid.to_mapping(),
        "configuration": (
            selected_config.to_mapping()
            if selected_config is not None and threshold_state == "frozen"
            else None
        ),
        "claim_scope": dict(_CLAIM_SCOPE),
        "fold_protocol": dict(_FOLD_PROTOCOL),
        "selection_rule": list(_SELECTION_RULE),
        "coverage_policy": _coverage_policy_mapping(),
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


def matcher_config_from_plan(
    plan_bytes: bytes,
    template_roster_bytes: bytes,
) -> MatcherConfig:
    """Structurally check a canonical plan's self-reported aggregates.

    This two-argument API does not recompute calibration and is insufficient
    for production row matching.  Use :func:`matcher_config_from_recomputed_plan`
    with the exact raw template PBMs at the execution boundary.
    """

    plan = _decode_plan(plan_bytes)
    if set(plan) != _PLAN_KEYS:
        raise KP1979MatchCalibrationError("matcher plan fields are not exact")
    for key, expected in (
        ("schema_version", MATCHER_PLAN_SCHEMA_VERSION),
        ("matcher_plan_id", MATCHER_PLAN_ID),
        ("calibration_protocol_id", CALIBRATION_PROTOCOL_ID),
        ("matcher_algorithm_id", MATCHER_ALGORITHM_ID),
        ("status", "frozen_closed_template_retrieval_only"),
        ("threshold_state", "frozen"),
    ):
        if plan.get(key) != expected:
            raise KP1979MatchCalibrationError("matcher plan identity or freeze gate failed")

    bindings = _validated_template_bindings(template_roster_bytes)
    if plan.get("template_roster_commitment") != _binding_roster_commitment(bindings):
        raise KP1979MatchCalibrationError("matcher plan template commitment differs")
    grid_mapping = _exact_mapping(
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
        label="calibration grid",
    )
    try:
        parsed_grid = CalibrationGrid.from_mapping(grid_mapping)
    except (TypeError, ValueError) as error:
        raise KP1979MatchCalibrationError("matcher plan calibration grid is invalid") from error
    if parsed_grid.to_mapping() != grid_mapping:
        raise KP1979MatchCalibrationError("matcher plan calibration grid is not canonical")
    if plan.get("claim_scope") != _CLAIM_SCOPE:
        raise KP1979MatchCalibrationError("matcher plan claim scope is not exact")
    if plan.get("fold_protocol") != _FOLD_PROTOCOL:
        raise KP1979MatchCalibrationError("matcher plan fold protocol is not exact")
    if plan.get("selection_rule") != list(_SELECTION_RULE):
        raise KP1979MatchCalibrationError("matcher plan selection rule is not exact")
    if plan.get("coverage_policy") != _coverage_policy_mapping():
        raise KP1979MatchCalibrationError("matcher plan coverage policy is not exact")
    if plan.get("assurances") != _ASSURANCES:
        raise KP1979MatchCalibrationError("matcher plan assurances are not exact")

    configuration = _exact_mapping(
        plan.get("configuration"),
        keys=_MATCHER_CONFIG_KEYS,
        label="matcher configuration",
    )
    try:
        config = MatcherConfig.from_mapping(configuration)
    except ValueError as error:
        raise KP1979MatchCalibrationError("matcher configuration is invalid") from error
    if (
        config.min_different_rank_margin < 1
        or config.min_path_margin < 1
        or not config.require_speck_stability
        or not config.require_shift_stability
        or (config.cut_gap_support_ppm == 0) != (config.max_cut_penalty == 0)
        or config.max_token_cost not in parsed_grid.max_token_costs
        or config.min_different_rank_margin not in parsed_grid.min_different_rank_margins
        or config.min_path_margin not in parsed_grid.min_path_margins
        or (config.cut_gap_support_ppm, config.max_cut_penalty) not in parsed_grid.cut_policies
        or config.unknown_edge_cost != parsed_grid.unknown_edge_cost
        or config.candidate_aspect_slack_ppm != parsed_grid.candidate_aspect_slack_ppm
    ):
        raise KP1979MatchCalibrationError("matcher configuration weakens a frozen gate")

    controls = _exact_mapping(
        plan.get("closed_set_controls"),
        keys=frozenset({"calibration", "validation"}),
        label="closed-set controls",
    )
    calibration = _verified_closed_metrics(controls.get("calibration"))
    validation = _verified_closed_metrics(controls.get("validation"))
    lovo = _exact_mapping(
        plan.get("open_set_lovo_negative_control"),
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
        label="LOVO negative control",
    )
    if (
        lovo.get("control_role") != "open_set_negative_control_only"
        or lovo.get("used_for_threshold_selection") is not False
        or lovo.get("generalization_claimed") is not False
    ):
        raise KP1979MatchCalibrationError("LOVO negative-control scope is invalid")
    lovo_counts = {
        key: _count(lovo.get(key), label="LOVO count")
        for key in (
            "case_count",
            "same_rank_proposed",
            "wrong_rank_proposed",
            "abstained",
            "empty_gallery",
        )
    }
    if (
        lovo_counts["case_count"] != len(bindings)
        or lovo_counts["same_rank_proposed"]
        + lovo_counts["wrong_rank_proposed"]
        + lovo_counts["abstained"]
        != len(bindings)
        or lovo_counts["empty_gallery"] > lovo_counts["abstained"]
    ):
        raise KP1979MatchCalibrationError("LOVO negative-control counts are inconsistent")

    equalities = _exact_mapping(
        plan.get("cross_rank_normalized_equality"),
        keys=frozenset(
            {"group_count", "affected_variant_count", "forces_different_rank_ambiguity"}
        ),
        label="cross-rank equality summary",
    )
    group_count = _count(equalities.get("group_count"), label="equality group count")
    affected_count = _count(
        equalities.get("affected_variant_count"),
        label="affected variant count",
    )
    if (
        equalities.get("forces_different_rank_ambiguity") is not True
        or affected_count > len(bindings)
        or 2 * group_count > affected_count
        or (group_count == 0) != (affected_count == 0)
        or calibration["collision_case_count"] + validation["collision_case_count"]
        != affected_count
    ):
        raise KP1979MatchCalibrationError("cross-rank equality summary is inconsistent")
    expected_case_count = (
        3 * len(bindings) + 7 * SYNTHETIC_REPLICATES_PER_LENGTH - 2 * affected_count
    )
    if calibration["case_count"] + validation["case_count"] != expected_case_count:
        raise KP1979MatchCalibrationError("closed-set control coverage is inconsistent")
    positive_variant_count = len(bindings) - affected_count
    for stratum, total in (
        ("identity", positive_variant_count),
        ("other_view", 2 * positive_variant_count),
        ("concatenation", 7 * SYNTHETIC_REPLICATES_PER_LENGTH),
    ):
        validation_quota = _validation_case_quota(total)
        if (
            calibration[f"{stratum}_case_count"] != total - validation_quota
            or validation[f"{stratum}_case_count"] != validation_quota
        ):
            raise KP1979MatchCalibrationError("closed-set stratum inventory is inconsistent")
    collision_validation_quota = _validation_case_quota(affected_count)
    if (
        calibration["collision_case_count"] != affected_count - collision_validation_quota
        or validation["collision_case_count"] != collision_validation_quota
    ):
        raise KP1979MatchCalibrationError("collision identity inventory is inconsistent")
    return config


def matcher_config_from_recomputed_plan(
    plan_bytes: bytes,
    template_roster_bytes: bytes,
    template_pbms: Iterable[TemplatePBM],
    *,
    grid: CalibrationGrid | None = None,
) -> MatcherConfig:
    """Recompute and exact-byte-verify a frozen plan before row matching.

    ``grid=None`` always means this module's compiled default grid.  An
    explicit grid is a trusted test/protocol input, never a value learned from
    the untrusted plan.  No row or page bytes are accepted by this API.
    """

    # Parse and canonicalize the bounded plan before touching either roster or
    # caller-supplied template iterators.  Run every cheap structural gate
    # before raw-template work or exact recalibration so a canonical-looking
    # forged plan cannot turn verification into a compute-amplification path.
    plan = _decode_plan(plan_bytes)
    if grid is not None and not isinstance(grid, CalibrationGrid):
        raise KP1979MatchCalibrationError("trusted calibration grid has an invalid type")
    structurally_verified = matcher_config_from_plan(plan_bytes, template_roster_bytes)
    selected_grid = grid if grid is not None else CalibrationGrid()
    if plan.get("calibration_grid") != selected_grid.to_mapping():
        raise KP1979MatchCalibrationError("matcher plan does not bind the trusted grid")
    bindings = _validated_template_bindings(template_roster_bytes)
    sources = _materialize_sources(template_pbms)
    _verify_sources_against_bindings(sources, bindings=bindings)
    raw_values = tuple(
        (source.variant_id, source.catalog_rank, source.raw_bytes) for source in sources
    )
    recomputed = calibrate_matcher_plan(raw_values, grid=selected_grid)
    if plan != recomputed or plan_bytes != encode_json(recomputed):
        raise KP1979MatchCalibrationError("matcher plan differs from exact recomputation")
    if recomputed.get("configuration") != structurally_verified.to_mapping():
        raise KP1979MatchCalibrationError("matcher configuration differs after recomputation")
    return structurally_verified


def build_closed_set_control_cases(
    template_pbms: Iterable[TemplatePBM],
) -> tuple[_ControlCase, ...]:
    """Build deterministic padded single-glyph and 2--8 glyph controls."""

    sources = _materialize_sources(template_pbms)
    index = build_template_index(
        (source.variant_id, source.catalog_rank, source.raw_bytes) for source in sources
    )
    return _build_closed_set_control_cases(
        sources,
        collision_variant_ids=index.cross_rank_normalized_variant_ids,
    )


def _build_closed_set_control_cases(
    sources: Sequence[_VariantSource],
    *,
    collision_variant_ids: frozenset[str],
) -> tuple[_ControlCase, ...]:
    ordered = tuple(sorted(sources, key=lambda item: _hash_key("variant-order", item.variant_id)))
    concatenation_sources = (
        tuple(source for source in ordered if source.variant_id not in collision_variant_ids)
        or ordered
    )
    cases: list[_ControlCase] = []
    for source in ordered:
        for view_name, view in (
            ("identity", source.tight_mask),
            ("dilate", _dilate_mask(source.tight_mask)),
            ("dropout", _deterministic_dropout(source.tight_mask, source.variant_id)),
        ):
            if view_name != "identity" and source.variant_id in collision_variant_ids:
                continue
            case_id = f"single:{view_name}:{source.variant_id}"
            cases.append(
                _ControlCase(
                    case_id=case_id,
                    fold=0,
                    row_pbm=_compose_row((view,), case_id=case_id),
                    expected_ranks=(source.catalog_rank,),
                    single_source_glyph=True,
                    stratum=(
                        "collision_identity"
                        if view_name == "identity" and source.variant_id in collision_variant_ids
                        else "identity"
                        if view_name == "identity"
                        else "other_view"
                    ),
                )
            )

    for length in range(2, 9):
        for replicate in range(SYNTHETIC_REPLICATES_PER_LENGTH):
            start, step = _concatenation_walk(
                source_count=len(concatenation_sources),
                length=length,
                replicate=replicate,
            )
            selected = tuple(
                concatenation_sources[(start + offset * step) % len(concatenation_sources)]
                for offset in range(length)
            )
            # Concatenation isolates joint segmentation from the separately
            # stratified single-glyph perturbation controls.
            views = tuple(source.tight_mask for source in selected)
            roster = ",".join(source.variant_id for source in selected)
            case_id = f"concat:{length}:{replicate}:{roster}"
            cases.append(
                _ControlCase(
                    case_id=case_id,
                    fold=0,
                    row_pbm=_compose_row(views, case_id=case_id),
                    expected_ranks=tuple(source.catalog_rank for source in selected),
                    single_source_glyph=False,
                    stratum="concatenation",
                )
            )
    return _assign_stratified_folds(cases)


def _assign_stratified_folds(cases: Sequence[_ControlCase]) -> tuple[_ControlCase, ...]:
    output: list[_ControlCase] = []
    for stratum in _FOLD_STRATA:
        members = sorted(
            (case for case in cases if case.stratum == stratum),
            key=lambda case: _hash_key(f"fold-order:{stratum}", case.case_id),
        )
        if not members and stratum == "collision_identity":
            continue
        if not members:
            raise KP1979MatchCalibrationError("synthetic control stratum is empty")
        validation_count = _validation_case_quota(len(members))
        for position, case in enumerate(members):
            fold = (
                VALIDATION_FOLD
                if position < validation_count
                else ((position - validation_count) % VALIDATION_FOLD)
            )
            output.append(
                _ControlCase(
                    case_id=case.case_id,
                    fold=fold,
                    row_pbm=case.row_pbm,
                    expected_ranks=case.expected_ranks,
                    single_source_glyph=case.single_source_glyph,
                    stratum=case.stratum,
                )
            )
    if len(output) != len(cases):
        raise KP1979MatchCalibrationError("synthetic control stratum is invalid")
    return tuple(sorted(output, key=lambda case: case.case_id))


def _validation_case_quota(member_count: int) -> int:
    if member_count == 0:
        return 0
    validation_count = max(1, (member_count + FOLD_COUNT - 1) // FOLD_COUNT)
    if member_count > 1:
        validation_count = min(validation_count, member_count - 1)
    return validation_count


def detect_cross_rank_normalized_equalities(index: TemplateIndex) -> tuple[dict[str, Any], ...]:
    """Return exact normalized-shape groups spanning different ranks."""

    groups: dict[tuple[int, ...], list[Any]] = {}
    for template in index.templates:
        groups.setdefault(template.normalized.rows, []).append(template)
    output: list[dict[str, Any]] = []
    for values in groups.values():
        ranks = tuple(sorted({template.catalog_rank for template in values}))
        if len(ranks) < 2:
            continue
        output.append(
            {
                "catalog_ranks": list(ranks),
                "variant_ids": sorted(template.variant_id for template in values),
            }
        )
    return tuple(
        sorted(
            output,
            key=lambda group: (
                tuple(group["catalog_ranks"]),
                tuple(group["variant_ids"]),
            ),
        )
    )


def select_threshold_evaluation(
    evaluations: Sequence[ThresholdEvaluation],
) -> ThresholdEvaluation | None:
    """Select zero-error calibration first, then coverage, then strictness."""

    eligible = [evaluation for evaluation in evaluations if _eligible_evaluation(evaluation)]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda evaluation: (
            -evaluation.correct_accepted,
            evaluation.config.max_token_cost,
            -evaluation.config.min_different_rank_margin,
            -evaluation.config.min_path_margin,
            # A larger support threshold penalizes cuts across a wider range
            # of small gaps; a larger penalty makes that discouragement
            # stronger.  Both are therefore the conservative tie direction.
            -evaluation.config.cut_gap_support_ppm,
            -evaluation.config.max_cut_penalty,
            tuple(sorted(evaluation.config.to_mapping().items())),
        ),
    )


def _materialize_sources(template_pbms: Iterable[TemplatePBM]) -> tuple[_VariantSource, ...]:
    try:
        iterator = iter(template_pbms)
    except TypeError as error:
        raise KP1979MatchCalibrationError("template PBM input is not iterable") from error
    sources: list[_VariantSource] = []
    for position, value in enumerate(iterator):
        if position >= MAX_TEMPLATE_COUNT:
            raise KP1979MatchCalibrationError("template PBM input exceeds its count limit")
        # Validate the yielded object and its PBM bounds before retaining it.
        # This single-item index applies the matcher's authoritative tuple,
        # identifier, rank, byte-size, canonical-PBM, dimension, ink, and run
        # gates incrementally; the bounded aggregate pass below adds duplicate
        # and cross-item constraints.
        try:
            build_template_index((value,))
        except ValueError as error:
            raise KP1979MatchCalibrationError("template PBM input is invalid") from error
        variant_id, catalog_rank, raw_bytes = value
        mask = parse_canonical_pbm(raw_bytes)
        bbox = mask.tight_bbox()
        if bbox is None:
            raise KP1979MatchCalibrationError("template PBM contains no ink")
        sources.append(
            _VariantSource(
                variant_id=variant_id,
                catalog_rank=catalog_rank,
                raw_bytes=raw_bytes,
                source_width=mask.width,
                source_height=mask.height,
                tight_mask=mask.crop(bbox),
            )
        )
    if not sources:
        raise KP1979MatchCalibrationError("template PBM input is empty")
    try:
        build_template_index(
            (source.variant_id, source.catalog_rank, source.raw_bytes) for source in sources
        )
    except ValueError as error:
        raise KP1979MatchCalibrationError("template PBM input is invalid") from error
    return tuple(sources)


def _config(
    *,
    max_token_cost: int,
    rank_margin: int,
    path_margin: int,
    cut_support: int,
    cut_penalty: int,
    grid: CalibrationGrid,
    stability: bool,
) -> MatcherConfig:
    return MatcherConfig(
        max_token_cost=max_token_cost,
        min_different_rank_margin=rank_margin,
        min_path_margin=path_margin,
        unknown_edge_cost=grid.unknown_edge_cost,
        cut_gap_support_ppm=cut_support,
        max_cut_penalty=cut_penalty,
        candidate_aspect_slack_ppm=grid.candidate_aspect_slack_ppm,
        require_speck_stability=stability,
        require_shift_stability=stability,
    )


def _observe(
    case: _ControlCase,
    *,
    index: TemplateIndex,
    config: MatcherConfig,
    require_proposed_status: bool = False,
    workspace: _RowMatchWorkspace | None = None,
) -> _Observation:
    row_id = _safe_case_row_id(case.case_id)
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
    paths = result["candidate_paths"]
    if not paths:
        return _Observation(
            case.case_id,
            case.fold,
            case.expected_ranks,
            (),
            False,
            0,
            0,
            case.single_source_glyph,
            case.stratum,
            False,
            False,
        )
    best = paths[0]
    segments = best["segments"]
    rank_segments = [segment for segment in segments if segment["segment_kind"] == "rank_proposal"]
    predicted = tuple(int(segment["catalog_rank"]) for segment in rank_segments)
    contains_unknown = len(rank_segments) != len(segments)
    minimum_margin = min(
        (int(segment["different_rank_margin"]) for segment in rank_segments),
        default=0,
    )
    path_margin = int(paths[1]["margin_from_best"]) if len(paths) > 1 else 100 * SCORE_SCALE
    base_eligible = (
        not contains_unknown
        and bool(rank_segments)
        and result["gates"]["sign_region_boundary_clear"] is True
    )
    if require_proposed_status:
        base_eligible = base_eligible and result["proposal_status"] == "proposed"
    collision_identity = case.stratum == "collision_identity"
    negative_control_passed = (
        collision_identity
        and result["proposal_status"] == "ambiguous"
        and result["gates"]["different_rank_margin_passed"] is False
    )
    unexpected_rank_proposal = collision_identity and result["proposal_status"] == "proposed"
    return _Observation(
        case.case_id,
        case.fold,
        case.expected_ranks,
        predicted,
        base_eligible,
        minimum_margin,
        path_margin,
        case.single_source_glyph,
        case.stratum,
        negative_control_passed,
        unexpected_rank_proposal,
    )


def _aggregate_observations(
    observations: Sequence[_Observation],
    *,
    config: MatcherConfig,
) -> ThresholdEvaluation:
    false_accepted = 0
    split_errors = 0
    correct_accepted = 0
    for observation in observations:
        outcome = _observation_outcome(observation, config=config)
        if outcome == "split":
            split_errors += 1
        elif outcome == "correct":
            correct_accepted += 1
        elif outcome == "false":
            false_accepted += 1
    return ThresholdEvaluation(
        config=config,
        false_accepted=false_accepted,
        split_errors=split_errors,
        correct_accepted=correct_accepted,
        case_count=len(observations),
        coverage_floor_passed=_coverage_floor_passed(observations, config=config),
    )


def _observation_outcome(
    observation: _Observation,
    *,
    config: MatcherConfig,
) -> str | None:
    if observation.stratum == "collision_identity":
        if observation.unexpected_rank_proposal:
            return "false"
        if observation.negative_control_passed:
            return "negative_correct"
        return None
    accepted = (
        observation.base_eligible
        and observation.minimum_rank_margin >= config.min_different_rank_margin
        and observation.path_margin >= config.min_path_margin
    )
    if not accepted:
        return None
    if observation.single_source_glyph and len(observation.predicted_ranks) != 1:
        return "split"
    if observation.predicted_ranks == observation.expected_ranks:
        return "correct"
    return "false"


def _stratum_metrics(
    observations: Sequence[_Observation],
    *,
    config: MatcherConfig,
) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for stratum in _POSITIVE_CONTROL_STRATA:
        members = tuple(item for item in observations if item.stratum == stratum)
        correct = sum(_observation_outcome(item, config=config) == "correct" for item in members)
        numerator, denominator = _COVERAGE_FRACTIONS[stratum]
        required = (len(members) * numerator + denominator - 1) // denominator
        output[stratum] = {
            "case_count": len(members),
            "correct_accepted": correct,
            "required_correct": required,
        }
    return output


def _coverage_floor_passed(
    observations: Sequence[_Observation],
    *,
    config: MatcherConfig,
) -> bool:
    positive_passed = all(
        values["case_count"] >= 1 and values["correct_accepted"] >= values["required_correct"]
        for values in _stratum_metrics(observations, config=config).values()
    )
    collision_members = tuple(item for item in observations if item.stratum == "collision_identity")
    collision_passed = all(item.negative_control_passed for item in collision_members)
    return positive_passed and collision_passed


def _eligible_evaluation(evaluation: ThresholdEvaluation) -> bool:
    return (
        evaluation.case_count > 0
        and evaluation.false_accepted == 0
        and evaluation.split_errors == 0
        and evaluation.correct_accepted > 0
        and evaluation.coverage_floor_passed
    )


def _lovo_negative_control(
    sources: Sequence[_VariantSource],
    *,
    index: TemplateIndex,
    config: MatcherConfig,
) -> dict[str, Any]:
    same_rank_proposed = 0
    wrong_rank_proposed = 0
    abstained = 0
    empty_gallery = 0
    for source in sources:
        retained = tuple(
            template for template in index.templates if template.variant_id != source.variant_id
        )
        if not retained:
            empty_gallery += 1
            abstained += 1
            continue
        max_aspect = max(
            template.source_width * SCORE_SCALE // template.source_height for template in retained
        )
        max_white_runs = max(template.internal_white_runs for template in retained)
        leave_one_out_index = TemplateIndex(
            retained,
            max_white_runs,
            max_aspect,
        )
        case_id = f"lovo:{source.variant_id}"
        row_pbm = _compose_row((source.tight_mask,), case_id=case_id)
        row = parse_canonical_pbm(row_pbm)
        result = match_row_sequence(
            row_id=_safe_case_row_id(case_id),
            row_pbm=row_pbm,
            sign_region_bbox=(0, 0, row.width, row.height),
            index=leave_one_out_index,
            config=config,
        )
        if result["proposal_status"] != "proposed":
            abstained += 1
            continue
        ranks = tuple(
            int(segment["catalog_rank"])
            for segment in result["candidate_paths"][0]["segments"]
            if segment["segment_kind"] == "rank_proposal"
        )
        if ranks == (source.catalog_rank,):
            same_rank_proposed += 1
        else:
            wrong_rank_proposed += 1
    return {
        "control_role": "open_set_negative_control_only",
        "used_for_threshold_selection": False,
        "generalization_claimed": False,
        "case_count": len(sources),
        "same_rank_proposed": same_rank_proposed,
        "wrong_rank_proposed": wrong_rank_proposed,
        "abstained": abstained,
        "empty_gallery": empty_gallery,
    }


def _compose_row(masks: Sequence[BinaryMask], *, case_id: str) -> bytes:
    if not masks:
        raise KP1979MatchCalibrationError("synthetic row requires at least one glyph")
    digest = hashlib.sha256(_HASH_DOMAIN + b"compose\x00" + case_id.encode()).digest()
    gaps = [3 + digest[index % len(digest)] % 13 for index in range(len(masks) - 1)]
    offsets = [digest[(index + 17) % len(digest)] % 5 for index in range(len(masks))]
    content_height = max(offset + mask.height for offset, mask in zip(offsets, masks, strict=True))
    width = 2 * SYNTHETIC_PADDING + sum(mask.width for mask in masks) + sum(gaps)
    height = 2 * SYNTHETIC_PADDING + content_height
    if width > 4_096 or height > 512:
        raise KP1979MatchCalibrationError("synthetic concatenation exceeds matcher row limits")
    rows = [0] * height
    x = SYNTHETIC_PADDING
    for index, (mask, y_offset) in enumerate(zip(masks, offsets, strict=True)):
        y = SYNTHETIC_PADDING + y_offset
        shift = width - (x + mask.width)
        for source_y, source_row in enumerate(mask.rows):
            rows[y + source_y] |= source_row << shift
        x += mask.width
        if index < len(gaps):
            x += gaps[index]
    return _encode_pbm(BinaryMask(width, height, tuple(rows)))


def _encode_pbm(mask: BinaryMask) -> bytes:
    row_bytes = (mask.width + 7) // 8
    unused_bits = row_bytes * 8 - mask.width
    payload = b"".join((row << unused_bits).to_bytes(row_bytes, "big") for row in mask.rows)
    return f"P4\n{mask.width} {mask.height}\n".encode("ascii") + payload


def _dilate_mask(mask: BinaryMask) -> BinaryMask:
    bit_limit = (1 << mask.width) - 1
    horizontal = tuple((row | (row << 1) | (row >> 1)) & bit_limit for row in mask.rows)
    rows: list[int] = []
    for y, row in enumerate(horizontal):
        value = row
        if y:
            value |= horizontal[y - 1]
        if y + 1 < mask.height:
            value |= horizontal[y + 1]
        rows.append(value & bit_limit)
    return BinaryMask(mask.width, mask.height, tuple(rows))


def _deterministic_dropout(mask: BinaryMask, variant_id: str) -> BinaryMask:
    digest = hashlib.sha256(_HASH_DOMAIN + b"dropout\x00" + variant_id.encode()).digest()
    seed = int.from_bytes(digest[:8])
    rows: list[int] = []
    for y, row in enumerate(mask.rows):
        output = row
        value = row
        while value:
            bit = value.bit_length() - 1
            x = mask.width - 1 - bit
            mixed = seed ^ (x * 0x9E3779B185EBCA87) ^ (y * 0xC2B2AE3D27D4EB4F)
            if mixed & 63 == 0:
                output &= ~(1 << bit)
            value ^= 1 << bit
        rows.append(output)
    result = BinaryMask(mask.width, mask.height, tuple(rows))
    return result if result.ink_count else mask


def _hash_key(label: str, value: str) -> bytes:
    return hashlib.sha256(_HASH_DOMAIN + label.encode() + b"\x00" + value.encode()).digest()


def _concatenation_walk(*, source_count: int, length: int, replicate: int) -> tuple[int, int]:
    seed = _hash_key("concatenation-walk", f"{length}:{replicate}")
    start = int.from_bytes(seed[:8], "big") % source_count
    if source_count == 1:
        return start, 1
    step = 1 + int.from_bytes(seed[8:16], "big") % (source_count - 1)
    while math.gcd(step, source_count) != 1:
        step = step % (source_count - 1) + 1
    return start, step


def _safe_case_row_id(case_id: str) -> str:
    digest = hashlib.sha256(_HASH_DOMAIN + b"row-id\x00" + case_id.encode()).hexdigest()
    return f"synthetic:{digest}"


def _decode_plan(plan_bytes: bytes) -> dict[str, Any]:
    if (
        not isinstance(plan_bytes, bytes)
        or not plan_bytes
        or len(plan_bytes) > MAX_MATCHER_PLAN_BYTES
    ):
        raise KP1979MatchCalibrationError("matcher plan byte length is invalid")
    try:
        value = decode_json(plan_bytes, source="matcher plan")
    except (RecursionError, ValueError) as error:
        raise KP1979MatchCalibrationError("matcher plan is not strict finite JSON") from error
    if not isinstance(value, dict):
        raise KP1979MatchCalibrationError("matcher plan must be an object")
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_MATCHER_PLAN_NESTING_DEPTH:
            raise KP1979MatchCalibrationError("matcher plan nesting exceeds its limit")
        if isinstance(current, Mapping):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    try:
        canonical = encode_json(value)
    except (RecursionError, TypeError, ValueError) as error:
        raise KP1979MatchCalibrationError("matcher plan cannot be canonicalized") from error
    if canonical != plan_bytes:
        raise KP1979MatchCalibrationError("matcher plan bytes are not canonical")
    return value


def _validated_template_bindings(template_roster_bytes: bytes) -> tuple[TemplateBinding, ...]:
    try:
        bindings = template_bindings(template_roster_bytes)
    except (RecursionError, ValueError) as error:
        raise KP1979MatchCalibrationError("template roster is invalid") from error
    if not bindings:
        raise KP1979MatchCalibrationError("template roster contains no bindings")
    return bindings


def _verify_sources_against_bindings(
    sources: Sequence[_VariantSource],
    *,
    bindings: Sequence[TemplateBinding],
) -> None:
    if len(sources) != len(bindings):
        raise KP1979MatchCalibrationError("raw templates do not cover the roster exactly")
    for source, binding in zip(sources, bindings, strict=True):
        if (
            source.variant_id != binding.variant_id
            or source.catalog_rank != binding.catalog_rank
            or len(source.raw_bytes) != binding.byte_size
            or source.source_width != binding.width
            or source.source_height != binding.height
            or f"sha256:{hashlib.sha256(source.raw_bytes).hexdigest()}" != binding.sha256
        ):
            raise KP1979MatchCalibrationError("raw template binding differs from the roster")


def _coverage_policy_mapping() -> dict[str, Any]:
    collision = _COVERAGE_POLICY["cross_rank_collision_identity"]
    if not isinstance(collision, Mapping):
        raise AssertionError("compiled collision coverage policy is invalid")
    required_abstention = collision["required_abstention_fraction"]
    if not isinstance(required_abstention, Mapping):
        raise AssertionError("compiled collision abstention policy is invalid")
    return {
        "policy_id": _COVERAGE_POLICY["policy_id"],
        "partition_assignment": _COVERAGE_POLICY["partition_assignment"],
        "selection_partition": _COVERAGE_POLICY["selection_partition"],
        "validation_role": _COVERAGE_POLICY["validation_role"],
        "positive_view_eligibility": _COVERAGE_POLICY["positive_view_eligibility"],
        "minimum_cases_per_stratum_per_partition": _COVERAGE_POLICY[
            "minimum_cases_per_stratum_per_partition"
        ],
        "minimum_correct_fractions": {
            stratum: {
                "numerator": _COVERAGE_FRACTIONS[stratum][0],
                "denominator": _COVERAGE_FRACTIONS[stratum][1],
            }
            for stratum in _POSITIVE_CONTROL_STRATA
        },
        "cross_rank_collision_identity": {
            "role": collision["role"],
            "required_abstention_fraction": dict(required_abstention),
            "rank_proposal_is_false_accept": collision["rank_proposal_is_false_accept"],
        },
    }


def _exact_mapping(
    value: object,
    *,
    keys: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise KP1979MatchCalibrationError(f"{label} fields are not exact")
    return value


def _count(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise KP1979MatchCalibrationError(f"{label} is not a nonnegative integer")
    return value


def _verified_closed_metrics(value: object) -> dict[str, int]:
    metrics = _exact_mapping(
        value,
        keys=frozenset(
            {
                "case_count",
                "false_accepted",
                "accepted_single_glyph_splits",
                "correct_accepted",
                "coverage_floor_passed",
                "strata",
                "collision_identity_negative_control",
            }
        ),
        label="closed-set metric",
    )
    output = {
        key: _count(metrics.get(key), label="closed-set count")
        for key in (
            "case_count",
            "false_accepted",
            "accepted_single_glyph_splits",
            "correct_accepted",
        )
    }
    if metrics.get("coverage_floor_passed") is not True:
        raise KP1979MatchCalibrationError("closed-set coverage floor did not pass")
    strata = _exact_mapping(
        metrics.get("strata"),
        keys=frozenset(_POSITIVE_CONTROL_STRATA),
        label="closed-set strata",
    )
    stratum_case_count = 0
    stratum_correct = 0
    for stratum in _POSITIVE_CONTROL_STRATA:
        values = _exact_mapping(
            strata.get(stratum),
            keys=frozenset({"case_count", "correct_accepted", "required_correct"}),
            label="closed-set stratum",
        )
        case_count = _count(values.get("case_count"), label="stratum case count")
        correct = _count(values.get("correct_accepted"), label="stratum accepted count")
        required = _count(values.get("required_correct"), label="stratum required count")
        numerator, denominator = _COVERAGE_FRACTIONS[stratum]
        if (
            case_count < 1
            or required != (case_count * numerator + denominator - 1) // denominator
            or not required <= correct <= case_count
        ):
            raise KP1979MatchCalibrationError("closed-set stratum coverage is inconsistent")
        stratum_case_count += case_count
        stratum_correct += correct
        output[f"{stratum}_case_count"] = case_count
    collision = _exact_mapping(
        metrics.get("collision_identity_negative_control"),
        keys=frozenset(
            {
                "case_count",
                "correct_abstained",
                "required_correct_abstentions",
                "rank_proposals",
            }
        ),
        label="collision identity negative control",
    )
    collision_count = _count(collision.get("case_count"), label="collision case count")
    collision_correct = _count(
        collision.get("correct_abstained"),
        label="collision abstention count",
    )
    collision_required = _count(
        collision.get("required_correct_abstentions"),
        label="required collision abstentions",
    )
    collision_proposals = _count(
        collision.get("rank_proposals"),
        label="collision rank proposals",
    )
    if (
        output["case_count"] == 0
        or output["false_accepted"] != 0
        or output["accepted_single_glyph_splits"] != 0
        or output["correct_accepted"] != stratum_correct
        or output["case_count"] != stratum_case_count + collision_count
        or collision_required != collision_count
        or collision_correct != collision_count
        or collision_proposals != 0
    ):
        raise KP1979MatchCalibrationError("closed-set freeze metrics are ineligible")
    output["collision_case_count"] = collision_count
    return output


def _template_roster_commitment(sources: Sequence[_VariantSource]) -> str:
    entries = tuple(
        (
            source.variant_id,
            source.catalog_rank,
            len(source.raw_bytes),
            hashlib.sha256(source.raw_bytes).digest(),
        )
        for source in sources
    )
    return _roster_commitment(entries)


def _binding_roster_commitment(bindings: Sequence[TemplateBinding]) -> str:
    entries = tuple(
        (
            binding.variant_id,
            binding.catalog_rank,
            binding.byte_size,
            bytes.fromhex(binding.sha256.removeprefix("sha256:")),
        )
        for binding in bindings
    )
    return _roster_commitment(entries)


def _roster_commitment(entries: Sequence[tuple[str, int, int, bytes]]) -> str:
    digest = hashlib.sha256()
    digest.update(_HASH_DOMAIN + b"template-roster\x00")
    for variant_id, catalog_rank, byte_size, raw_digest in sorted(
        entries,
        key=lambda item: (item[1], item[0]),
    ):
        identifier = variant_id.encode("utf-8")
        digest.update(len(identifier).to_bytes(4, "big"))
        digest.update(identifier)
        digest.update(catalog_rank.to_bytes(8, "big"))
        digest.update(byte_size.to_bytes(8, "big"))
        digest.update(raw_digest)
    return "sha256:" + digest.hexdigest()


def _evaluation_mapping(
    evaluation: ThresholdEvaluation,
    observations: Sequence[_Observation],
    *,
    config: MatcherConfig,
) -> dict[str, Any]:
    collision_members = tuple(item for item in observations if item.stratum == "collision_identity")
    return {
        "case_count": evaluation.case_count,
        "false_accepted": evaluation.false_accepted,
        "accepted_single_glyph_splits": evaluation.split_errors,
        "correct_accepted": evaluation.correct_accepted,
        "coverage_floor_passed": evaluation.coverage_floor_passed,
        "strata": _stratum_metrics(observations, config=config),
        "collision_identity_negative_control": {
            "case_count": len(collision_members),
            "correct_abstained": sum(item.negative_control_passed for item in collision_members),
            "required_correct_abstentions": len(collision_members),
            "rank_proposals": sum(item.unexpected_rank_proposal for item in collision_members),
        },
    }


def _empty_metrics(cases: Sequence[_ControlCase]) -> dict[str, Any]:
    strata: dict[str, dict[str, int]] = {}
    for stratum in _POSITIVE_CONTROL_STRATA:
        case_count = sum(case.stratum == stratum for case in cases)
        numerator, denominator = _COVERAGE_FRACTIONS[stratum]
        strata[stratum] = {
            "case_count": case_count,
            "correct_accepted": 0,
            "required_correct": (case_count * numerator + denominator - 1) // denominator,
        }
    collision_count = sum(case.stratum == "collision_identity" for case in cases)
    return {
        "case_count": len(cases),
        "false_accepted": 0,
        "accepted_single_glyph_splits": 0,
        "correct_accepted": 0,
        "coverage_floor_passed": False,
        "strata": strata,
        "collision_identity_negative_control": {
            "case_count": collision_count,
            "correct_abstained": 0,
            "required_correct_abstentions": collision_count,
            "rank_proposals": 0,
        },
    }


def _empty_lovo_metrics() -> dict[str, Any]:
    return {
        "control_role": "open_set_negative_control_only",
        "used_for_threshold_selection": False,
        "generalization_claimed": False,
        "case_count": 0,
        "same_rank_proposed": 0,
        "wrong_rank_proposed": 0,
        "abstained": 0,
        "empty_gallery": 0,
    }


def _validate_sorted_unique(
    values: tuple[int, ...],
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> None:
    if (
        not values
        or tuple(sorted(set(values))) != values
        or any(not _is_int(value) or not minimum <= value <= maximum for value in values)
    ):
        raise KP1979MatchCalibrationError(f"{label} must be sorted unique bounded integers")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


__all__ = [
    "CALIBRATION_PROTOCOL_ID",
    "CalibrationGrid",
    "KP1979MatchCalibrationError",
    "ThresholdEvaluation",
    "build_closed_set_control_cases",
    "calibrate_matcher_plan",
    "detect_cross_rank_normalized_equalities",
    "matcher_config_from_plan",
    "matcher_config_from_recomputed_plan",
    "select_threshold_evaluation",
]
