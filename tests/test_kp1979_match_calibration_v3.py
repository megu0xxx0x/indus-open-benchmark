from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from dataclasses import replace
from typing import Any
from unittest.mock import patch

import indusbench.kp1979_match_calibration as v2
import indusbench.kp1979_match_calibration_v3 as v3
from indusbench.io import encode_json
from indusbench.kp1979_glyph_match import MatcherConfig, build_template_index
from indusbench.kp1979_match_calibration_v3 import (
    KP1979MatchCalibrationError,
    V3ThresholdEvaluation,
    build_closed_set_control_cases_v3,
    calibrate_matcher_plan_v3,
    matcher_config_from_recomputed_plan_v3,
    select_v3_threshold_evaluation,
    validate_matcher_plan_v3,
    validate_recomputed_matcher_plan_v3,
)
from tests.test_kp1979_match_calibration import (
    BOUND_TEMPLATES,
    COLLISION_TEMPLATES,
    CROSS,
    SMALL_GRID,
    SYNTHETIC_TEMPLATES,
    config,
    pbm,
    roster_bytes_for,
)

RICH_GRID = v3.CalibrationGrid(
    max_token_costs=(500_000, 1_250_000),
    min_different_rank_margins=(1, 100_000),
    min_path_margins=(1, 100_000),
    cut_policies=((0, 0), (125_000, 250_000)),
)


def observation(
    *,
    case_id: str = "synthetic-v3-case",
    stratum: str = "identity",
    expected_ranks: tuple[int, ...] = (11,),
    predicted_ranks: tuple[int, ...] = (11,),
    single_source_glyph: bool = True,
    candidate_path_available: bool = True,
    contains_unknown: bool = False,
    absolute_shape_cost_passed: bool = True,
    different_rank_margin_passed: bool = True,
    speck_ablation_stability_passed: bool = True,
    normalization_shift_stability_passed: bool = True,
    sign_region_boundary_clear: bool = True,
    minimum_rank_margin: int = 500_000,
    path_margin: int = 500_000,
    proposal_status: str = "proposed",
    negative_control_passed: bool = False,
) -> v3._V3Observation:
    return v3._V3Observation(
        case_id=case_id,
        fold=0,
        expected_ranks=expected_ranks,
        predicted_ranks=predicted_ranks,
        single_source_glyph=single_source_glyph,
        stratum=stratum,
        candidate_path_available=candidate_path_available,
        contains_unknown=contains_unknown,
        absolute_shape_cost_passed=absolute_shape_cost_passed,
        different_rank_margin_passed=different_rank_margin_passed,
        speck_ablation_stability_passed=speck_ablation_stability_passed,
        normalization_shift_stability_passed=normalization_shift_stability_passed,
        sign_region_boundary_clear=sign_region_boundary_clear,
        minimum_rank_margin=minimum_rank_margin,
        path_margin=path_margin,
        proposal_status=proposal_status,
        negative_control_passed=negative_control_passed,
    )


def tier_b(value: v3._V3Observation) -> v3._V3Observation:
    return replace(
        value,
        speck_ablation_stability_passed=False,
        proposal_status="ambiguous",
    )


def eligible_metrics(
    *,
    identity_count: int,
    other_count: int,
    concatenation_count: int,
    identity_correct: int,
    other_correct: int,
    concatenation_correct: int,
    tier_a_correct: int,
    tier_b_correct: int,
) -> dict[str, Any]:
    case_count = identity_count + other_count + concatenation_count
    correct = identity_correct + other_correct + concatenation_correct
    return {
        "case_count": case_count,
        "tier_a_plus_b_wrong_ranked": 0,
        "tier_a_plus_b_single_glyph_splits": 0,
        "tier_a_plus_b_correct_ranked": correct,
        "coverage_floor_passed": True,
        "candidate_tiers": {
            "tier_a_stable": {
                "disposition": "stable_proposal",
                "correct_ranked": tier_a_correct,
                "wrong_ranked": 0,
                "single_glyph_splits": 0,
                "proposal_count": tier_a_correct,
            },
            "tier_b_provisional_speck_sensitive": {
                "disposition": "provisional_speck_sensitive",
                "accepted": False,
                "correct_ranked": tier_b_correct,
                "wrong_ranked": 0,
                "single_glyph_splits": 0,
                "proposal_count": tier_b_correct,
            },
        },
        "strata": {
            "identity": {
                "case_count": identity_count,
                "tier_a_plus_b_correct_ranked": identity_correct,
                "required_correct_ranked": (identity_count * 99 + 99) // 100,
            },
            "other_view": {
                "case_count": other_count,
                "tier_a_plus_b_correct_ranked": other_correct,
                "required_correct_ranked": (other_count * 19 + 19) // 20,
            },
            "concatenation": {
                "case_count": concatenation_count,
                "tier_a_plus_b_correct_ranked": concatenation_correct,
                "required_correct_ranked": (concatenation_count * 4 + 4) // 5,
            },
        },
        "tier_a_stable_aggregate": {
            "positive_case_count": case_count,
            "correct_ranked": tier_a_correct,
            "required_correct_ranked": (case_count * 3 + 3) // 4,
        },
        "collision_identity_negative_control": {
            "case_count": 0,
            "correct_abstained": 0,
            "required_correct_abstentions": 0,
            "rank_proposals": 0,
        },
    }


class V3ParentContractTests(unittest.TestCase):
    def test_v2_synthetic_plan_bytes_remain_frozen(self) -> None:
        plan_bytes = encode_json(v2.calibrate_matcher_plan(BOUND_TEMPLATES, grid=SMALL_GRID))
        self.assertEqual(
            "4304594a48543c7ea3e603b2f7eecc61fac2db0619718de9f258bb5de6d0501f",
            hashlib.sha256(plan_bytes).hexdigest(),
        )

    def test_v3_reuses_v2_control_ids_folds_pixels_order_and_grid(self) -> None:
        for templates in (SYNTHETIC_TEMPLATES, tuple(reversed(SYNTHETIC_TEMPLATES))):
            v2_cases = v2.build_closed_set_control_cases(templates)
            v3_cases = build_closed_set_control_cases_v3(templates)
            self.assertEqual(v2_cases, v3_cases)
            self.assertEqual(
                [(case.case_id, case.fold, case.row_pbm) for case in v2_cases],
                [(case.case_id, case.fold, case.row_pbm) for case in v3_cases],
            )
        self.assertIs(v2.CalibrationGrid, v3.CalibrationGrid)
        self.assertEqual(v2.CalibrationGrid().to_mapping(), v3.CalibrationGrid().to_mapping())
        self.assertEqual(v2._FOLD_PROTOCOL, v3._FOLD_PROTOCOL)

    def test_v3_ids_are_distinct_while_matcher_algorithm_is_inherited(self) -> None:
        self.assertNotEqual(v2.CALIBRATION_PROTOCOL_ID, v3.CALIBRATION_PROTOCOL_ID)
        self.assertNotEqual(v2.MATCHER_PLAN_ID, v3.MATCHER_PLAN_ID)
        self.assertNotEqual(v2.MATCHER_PLAN_SCHEMA_VERSION, v3.MATCHER_PLAN_SCHEMA_VERSION)
        self.assertEqual(
            v2.MATCHER_ALGORITHM_ID,
            v3.MATCHER_ALGORITHM_ID,
        )

    def test_v3_plan_is_input_order_invariant_like_v2(self) -> None:
        first = calibrate_matcher_plan_v3(SYNTHETIC_TEMPLATES, grid=SMALL_GRID)
        second = calibrate_matcher_plan_v3(reversed(SYNTHETIC_TEMPLATES), grid=SMALL_GRID)
        self.assertEqual(first, second)
        self.assertEqual(encode_json(first), encode_json(second))


class V3TierTests(unittest.TestCase):
    def test_actual_matcher_speck_only_failure_bridges_to_nonaccepted_tier_b(
        self,
    ) -> None:
        matcher_config = config()
        padded_dot = pbm("...", ".#.", "...")
        index = build_template_index(
            (
                ("dot", 1, pbm("#")),
                ("cross", 2, CROSS),
            )
        )
        case = v2._ControlCase(
            "synthetic-speck-only",
            0,
            padded_dot,
            (1,),
            True,
            "identity",
        )

        observed = v3._probe_case_v3(case, index=index, config=matcher_config)

        self.assertFalse(observed.speck_ablation_stability_passed)
        self.assertTrue(observed.absolute_shape_cost_passed)
        self.assertTrue(observed.different_rank_margin_passed)
        self.assertTrue(observed.normalization_shift_stability_passed)
        self.assertTrue(observed.sign_region_boundary_clear)
        self.assertEqual("ambiguous", observed.proposal_status)
        self.assertEqual(
            "tier_b_provisional_speck_sensitive",
            v3._classify_v3_tier(observed, config=matcher_config),
        )

        evaluation = v3._aggregate_v3_observations(
            (observed,),
            config=matcher_config,
        )
        tier_b_metrics = v3._evaluation_mapping_v3(
            evaluation,
            (observed,),
            config=matcher_config,
        )["candidate_tiers"]["tier_b_provisional_speck_sensitive"]
        self.assertEqual("provisional_speck_sensitive", tier_b_metrics["disposition"])
        self.assertIs(False, tier_b_metrics["accepted"])
        self.assertEqual(1, tier_b_metrics["correct_ranked"])
        self.assertEqual(1, tier_b_metrics["proposal_count"])

    def test_tier_a_and_only_speck_failed_tier_b_truth_table(self) -> None:
        matcher_config = config()
        stable = observation()
        self.assertEqual("tier_a_stable", v3._classify_v3_tier(stable, config=matcher_config))
        self.assertEqual(
            "tier_b_provisional_speck_sensitive",
            v3._classify_v3_tier(tier_b(stable), config=matcher_config),
        )

        failures = (
            replace(stable, candidate_path_available=False),
            replace(stable, contains_unknown=True),
            replace(stable, absolute_shape_cost_passed=False, proposal_status="ambiguous"),
            replace(stable, different_rank_margin_passed=False, proposal_status="ambiguous"),
            replace(stable, minimum_rank_margin=0),
            replace(stable, path_margin=0),
            replace(
                stable, normalization_shift_stability_passed=False, proposal_status="ambiguous"
            ),
            replace(stable, sign_region_boundary_clear=False, proposal_status="unknown_damage"),
            replace(tier_b(stable), normalization_shift_stability_passed=False),
            replace(tier_b(stable), proposal_status="proposed"),
            replace(stable, proposal_status="ambiguous"),
        )
        for failed in failures:
            with self.subTest(failed=failed):
                self.assertIsNone(v3._classify_v3_tier(failed, config=matcher_config))

    def test_candidate_floors_use_a_plus_b_but_stable_aggregate_uses_a_only(self) -> None:
        matcher_config = config()
        observations: list[v3._V3Observation] = []

        def add(stratum: str, tier_a_count: int, tier_b_count: int, abstained: int) -> None:
            start = len(observations)
            for offset in range(tier_a_count):
                observations.append(
                    observation(case_id=f"{stratum}-a-{start + offset}", stratum=stratum)
                )
            start = len(observations)
            for offset in range(tier_b_count):
                observations.append(
                    tier_b(observation(case_id=f"{stratum}-b-{start + offset}", stratum=stratum))
                )
            start = len(observations)
            for offset in range(abstained):
                observations.append(
                    replace(
                        observation(case_id=f"{stratum}-n-{start + offset}", stratum=stratum),
                        candidate_path_available=False,
                        proposal_status="no_match",
                    )
                )

        add("identity", 74, 25, 1)
        add("other_view", 16, 3, 1)
        add("concatenation", 4, 0, 1)
        evaluation = v3._aggregate_v3_observations(observations, config=matcher_config)
        self.assertTrue(evaluation.coverage_floor_passed)
        self.assertEqual(94, evaluation.tier_a_correct_ranked)
        self.assertEqual(28, evaluation.tier_b_correct_ranked)

        one_less_stable = list(observations)
        first_stable = next(
            index
            for index, value in enumerate(one_less_stable)
            if v3._classify_v3_tier(value, config=matcher_config) == "tier_a_stable"
        )
        one_less_stable[first_stable] = tier_b(one_less_stable[first_stable])
        failed = v3._aggregate_v3_observations(one_less_stable, config=matcher_config)
        self.assertEqual(evaluation.correct_ranked, failed.correct_ranked)
        self.assertFalse(failed.coverage_floor_passed)

    def test_wrong_split_and_collision_tier_proposals_fail(self) -> None:
        matcher_config = config()
        wrong = replace(observation(), predicted_ranks=(22,))
        split = replace(observation(), predicted_ranks=(11, 11))
        collision = replace(
            observation(stratum="collision_identity"),
            negative_control_passed=False,
        )
        negative_correct = observation(
            stratum="collision_identity",
            different_rank_margin_passed=False,
            proposal_status="ambiguous",
            negative_control_passed=True,
        )
        self.assertEqual(("tier_a_stable", "wrong"), v3._v3_outcome(wrong, config=matcher_config))
        self.assertEqual(("tier_a_stable", "split"), v3._v3_outcome(split, config=matcher_config))
        self.assertEqual(
            ("tier_a_stable", "wrong"),
            v3._v3_outcome(collision, config=matcher_config),
        )
        self.assertEqual(
            (None, "collision_correct"), v3._v3_outcome(negative_correct, config=matcher_config)
        )
        tier_b_wrong = tier_b(wrong)
        tier_b_split = tier_b(split)
        tier_b_collision = tier_b(collision)
        for value, field in (
            (wrong, "wrong_ranked"),
            (split, "split_errors"),
            (collision, "wrong_ranked"),
            (tier_b_wrong, "wrong_ranked"),
            (tier_b_split, "split_errors"),
            (tier_b_collision, "wrong_ranked"),
        ):
            evaluation = v3._aggregate_v3_observations((value,), config=matcher_config)
            self.assertEqual(1, getattr(evaluation, field))
            self.assertFalse(v3._eligible_v3_evaluation(evaluation))


class V3SelectionTests(unittest.TestCase):
    def test_selection_maximizes_tier_a_then_a_plus_b_then_v2_strictness(self) -> None:
        loose = V3ThresholdEvaluation(config(max_token_cost=750_000), 0, 0, 8, 4, 20, True)
        more_total = V3ThresholdEvaluation(config(max_token_cost=750_000), 0, 0, 8, 5, 20, True)
        more_stable = V3ThresholdEvaluation(config(max_token_cost=750_000), 0, 0, 9, 0, 20, True)
        strict = V3ThresholdEvaluation(
            config(max_token_cost=500_000, rank_margin=100_000, path_margin=100_000),
            0,
            0,
            9,
            0,
            20,
            True,
        )
        selected = select_v3_threshold_evaluation((loose, more_total, more_stable, strict))
        self.assertIs(strict, selected)

        for ineligible in (
            V3ThresholdEvaluation(config(), 1, 0, 20, 0, 21, True),
            V3ThresholdEvaluation(config(), 0, 1, 20, 0, 21, True),
            V3ThresholdEvaluation(config(), 0, 0, 20, 0, 21, False),
            V3ThresholdEvaluation(config(), 0, 0, 0, 0, 21, True),
        ):
            self.assertIsNone(select_v3_threshold_evaluation((ineligible,)))
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "weakens stability"):
            V3ThresholdEvaluation(
                replace(config(), require_speck_stability=False),
                0,
                0,
                20,
                0,
                20,
                True,
            )


class V3PlanTests(unittest.TestCase):
    def test_cached_plan_is_byte_exact_reference_across_rich_public_fixtures(self) -> None:
        fixtures = (
            (BOUND_TEMPLATES, SMALL_GRID),
            (tuple(reversed(BOUND_TEMPLATES)), RICH_GRID),
            (COLLISION_TEMPLATES, RICH_GRID),
        )
        for templates, grid in fixtures:
            with self.subTest(template_count=len(templates)):
                reference = v3._calibrate_matcher_plan_v3_reference(templates, grid=grid)
                cached = calibrate_matcher_plan_v3(templates, grid=grid)
                self.assertEqual(reference, cached)
                self.assertEqual(encode_json(reference), encode_json(cached))

    def test_actual_matcher_frozen_path_is_byte_exact_through_validation_and_lovo(
        self,
    ) -> None:
        # Test-only forcing reaches the selected/validation/LOVO branch while
        # retaining the real matcher, controls, cache, and reference paths.
        # Production eligibility and its immutable floors are not changed.
        def force_eligible(evaluation: V3ThresholdEvaluation) -> bool:
            return evaluation.case_count > 0

        with patch.object(v3, "_eligible_v3_evaluation", side_effect=force_eligible):
            reference = v3._calibrate_matcher_plan_v3_reference(
                BOUND_TEMPLATES,
                grid=RICH_GRID,
            )
            cached = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=RICH_GRID)

        self.assertEqual(
            "frozen_closed_template_candidate_ranking_only",
            reference["status"],
        )
        self.assertEqual(reference, cached)
        self.assertEqual(encode_json(reference), encode_json(cached))
        self.assertEqual(
            len(BOUND_TEMPLATES),
            reference["open_set_lovo_negative_control"]["case_count"],
        )

    def test_no_selected_calibration_configuration_never_matches_validation(self) -> None:
        validation_calls: list[str] = []

        def no_match(
            case: v2._ControlCase,
            *,
            index: object,
            config: MatcherConfig,
            workspace: object = None,
        ) -> v3._V3Observation:
            del index, config, workspace
            if case.fold == v2.VALIDATION_FOLD:
                validation_calls.append(case.case_id)
            return observation(
                case_id=case.case_id,
                stratum=case.stratum,
                expected_ranks=case.expected_ranks,
                predicted_ranks=(),
                single_source_glyph=case.single_source_glyph,
                candidate_path_available=False,
                proposal_status="no_match",
            )

        with patch.object(v3, "_probe_case_v3", side_effect=no_match):
            plan = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=SMALL_GRID)
        self.assertEqual("no_go", plan["status"])
        self.assertEqual([], validation_calls)

    def test_plan_scope_keeps_every_scientific_and_operational_claim_false(self) -> None:
        plan = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=SMALL_GRID)
        claims = plan["claim_scope"]
        for key in (
            "speck_robustness_claimed",
            "open_set_allograph_generalization_claimed",
            "real_row_performance_claimed",
            "accepted_identity_or_sequence",
            "accepted_transcription",
            "reading_direction_inferred",
            "language_or_frequency_prior_used",
            "decipherment",
            "prize_submission_eligible",
        ):
            self.assertIs(claims[key], False)
        self.assertIs(plan["assurances"]["tier_b_accepted"], False)
        self.assertIs(plan["assurances"]["public_release_authorized"], False)

    def test_validation_is_absent_from_selection_and_each_case_runs_once_afterward(self) -> None:
        events: list[tuple[str, str | None]] = []
        real_selector = select_v3_threshold_evaluation

        def fake_probe(
            case: v2._ControlCase,
            *,
            index: object,
            config: MatcherConfig,
            workspace: object = None,
        ) -> v3._V3Observation:
            del index, workspace
            phase = "validation" if case.fold == v2.VALIDATION_FOLD else "calibration"
            events.append((phase, case.case_id))
            return observation(
                case_id=case.case_id,
                stratum=case.stratum,
                expected_ranks=case.expected_ranks,
                predicted_ranks=case.expected_ranks,
                single_source_glyph=case.single_source_glyph,
                negative_control_passed=case.stratum == "collision_identity",
                different_rank_margin_passed=case.stratum != "collision_identity",
                proposal_status="ambiguous" if case.stratum == "collision_identity" else "proposed",
            )

        def selector_spy(
            evaluations: list[V3ThresholdEvaluation],
        ) -> V3ThresholdEvaluation | None:
            events.append(("selection", None))
            self.assertFalse(any(phase == "validation" for phase, _ in events))
            return real_selector(evaluations)

        with (
            patch.object(v3, "_probe_case_v3", side_effect=fake_probe),
            patch.object(v3, "select_v3_threshold_evaluation", side_effect=selector_spy),
        ):
            plan = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=SMALL_GRID)
        self.assertEqual("frozen_closed_template_candidate_ranking_only", plan["status"])
        validation_ids = [
            case.case_id
            for case in v2.build_closed_set_control_cases(BOUND_TEMPLATES)
            if case.fold == v2.VALIDATION_FOLD
        ]
        observed_validation_ids = [value for phase, value in events if phase == "validation"]
        self.assertCountEqual(validation_ids, observed_validation_ids)
        self.assertEqual(len(validation_ids), len(observed_validation_ids))
        self.assertLess(
            events.index(("selection", None)),
            next(index for index, event in enumerate(events) if event[0] == "validation"),
        )

    def test_validation_failure_returns_no_go_without_trying_another_configuration(self) -> None:
        validation_configs: list[int] = []
        failed_validation_case: str | None = None
        controls = v2.build_closed_set_control_cases(BOUND_TEMPLATES)
        failed_validation_case = next(
            case.case_id
            for case in controls
            if case.fold == v2.VALIDATION_FOLD and case.stratum == "identity"
        )

        def fake_probe(
            case: v2._ControlCase,
            *,
            index: object,
            config: MatcherConfig,
            workspace: object = None,
        ) -> v3._V3Observation:
            del index, workspace
            if case.fold == v2.VALIDATION_FOLD:
                validation_configs.append(config.max_token_cost)
            value = observation(
                case_id=case.case_id,
                stratum=case.stratum,
                expected_ranks=case.expected_ranks,
                predicted_ranks=case.expected_ranks,
                single_source_glyph=case.single_source_glyph,
                negative_control_passed=case.stratum == "collision_identity",
                different_rank_margin_passed=case.stratum != "collision_identity",
                proposal_status="ambiguous" if case.stratum == "collision_identity" else "proposed",
            )
            if case.case_id == failed_validation_case:
                value = replace(value, candidate_path_available=False, proposal_status="no_match")
            return value

        with patch.object(v3, "_probe_case_v3", side_effect=fake_probe):
            plan = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=SMALL_GRID)
        self.assertEqual("no_go", plan["status"])
        self.assertEqual("not_frozen", plan["threshold_state"])
        self.assertIsNone(plan["configuration"])
        self.assertEqual({500_000}, set(validation_configs))
        self.assertEqual(
            "no_go",
            validate_matcher_plan_v3(
                encode_json(plan),
                roster_bytes_for(BOUND_TEMPLATES),
            ),
        )

    def test_no_go_and_frozen_plan_shapes_are_canonical_and_exactly_validated(self) -> None:
        roster_bytes = roster_bytes_for(BOUND_TEMPLATES)
        no_go = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=SMALL_GRID)
        no_go_bytes = encode_json(no_go)
        self.assertEqual("no_go", validate_matcher_plan_v3(no_go_bytes, roster_bytes))
        self.assertIsNone(
            validate_recomputed_matcher_plan_v3(
                no_go_bytes,
                roster_bytes,
                BOUND_TEMPLATES,
                grid=SMALL_GRID,
            )
        )
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "not frozen"):
            matcher_config_from_recomputed_plan_v3(
                no_go_bytes,
                roster_bytes,
                BOUND_TEMPLATES,
                grid=SMALL_GRID,
            )

        frozen = deepcopy(no_go)
        frozen["status"] = "frozen_closed_template_candidate_ranking_only"
        frozen["threshold_state"] = "frozen"
        frozen["configuration"] = config().to_mapping()
        frozen["closed_set_controls"] = {
            "calibration": eligible_metrics(
                identity_count=2,
                other_count=4,
                concatenation_count=16,
                identity_correct=2,
                other_correct=4,
                concatenation_correct=13,
                tier_a_correct=17,
                tier_b_correct=2,
            ),
            "validation": eligible_metrics(
                identity_count=1,
                other_count=2,
                concatenation_count=5,
                identity_correct=1,
                other_correct=2,
                concatenation_correct=4,
                tier_a_correct=6,
                tier_b_correct=1,
            ),
        }
        frozen["open_set_lovo_negative_control"] = {
            "control_role": "open_set_negative_control_only",
            "used_for_threshold_selection": False,
            "generalization_claimed": False,
            "case_count": len(BOUND_TEMPLATES),
            "same_rank_proposed": 0,
            "wrong_rank_proposed": 0,
            "abstained": len(BOUND_TEMPLATES),
            "empty_gallery": 0,
        }
        frozen_bytes = encode_json(frozen)
        self.assertEqual("frozen", validate_matcher_plan_v3(frozen_bytes, roster_bytes))

        weakened_config = deepcopy(frozen)
        weakened_config["configuration"]["top_paths"] = 2
        with self.assertRaisesRegex(
            KP1979MatchCalibrationError,
            "configuration is invalid|weakens",
        ):
            validate_matcher_plan_v3(encode_json(weakened_config), roster_bytes)

        missing_lovo = deepcopy(frozen)
        missing_lovo["open_set_lovo_negative_control"] = v2._empty_lovo_metrics()
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "complete LOVO"):
            validate_matcher_plan_v3(encode_json(missing_lovo), roster_bytes)

        with self.assertRaisesRegex(KP1979MatchCalibrationError, "exact recomputation"):
            matcher_config_from_recomputed_plan_v3(
                frozen_bytes,
                roster_bytes,
                BOUND_TEMPLATES,
                grid=SMALL_GRID,
            )

        noncanonical = json.dumps(no_go, separators=(",", ":")).encode()
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "not canonical"):
            validate_matcher_plan_v3(noncanonical, roster_bytes)

    def test_tampered_tier_floor_claim_and_extra_field_fail_closed(self) -> None:
        roster_bytes = roster_bytes_for(BOUND_TEMPLATES)
        plan = calibrate_matcher_plan_v3(BOUND_TEMPLATES, grid=SMALL_GRID)
        tampered_values = []
        extra = deepcopy(plan)
        extra["unexpected"] = False
        tampered_values.append(extra)
        tier_b_accepted = deepcopy(plan)
        tier_b_accepted["closed_set_controls"]["calibration"]["candidate_tiers"][
            "tier_b_provisional_speck_sensitive"
        ]["accepted"] = True
        tampered_values.append(tier_b_accepted)
        floor = deepcopy(plan)
        floor["coverage_policy"]["minimum_candidate_correct_fractions"]["identity"]["numerator"] = (
            98
        )
        tampered_values.append(floor)
        claim = deepcopy(plan)
        claim["claim_scope"]["speck_robustness_claimed"] = True
        tampered_values.append(claim)
        for tampered in tampered_values:
            with self.subTest(tampered=tampered), self.assertRaises(KP1979MatchCalibrationError):
                validate_matcher_plan_v3(encode_json(tampered), roster_bytes)


if __name__ == "__main__":
    unittest.main()
