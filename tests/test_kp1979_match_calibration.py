from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from collections.abc import Iterator
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import indusbench.kp1979_match_calibration as calibration_module
from indusbench.io import encode_json
from indusbench.kp1979_glyph_match import (
    MAX_TEMPLATE_COUNT,
    MAX_TEMPLATE_PBM_BYTES,
    MatcherConfig,
    build_template_index,
    parse_canonical_pbm,
)
from indusbench.kp1979_match_calibration import (
    CalibrationGrid,
    KP1979MatchCalibrationError,
    ThresholdEvaluation,
    build_closed_set_control_cases,
    calibrate_matcher_plan,
    detect_cross_rank_normalized_equalities,
    matcher_config_from_plan,
    matcher_config_from_recomputed_plan,
    select_threshold_evaluation,
)
from indusbench.kp1979_sign_template_roster import build_sign_template_roster
from tests.test_kp1979_sign_template_roster import inputs

TemplatePBM = tuple[str, int, bytes]


def pbm(*rows: str) -> bytes:
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise AssertionError("synthetic PBM rows must be rectangular")
    width = len(rows[0])
    row_bytes = (width + 7) // 8
    payload = bytearray()
    for row in rows:
        value = 0
        for symbol in row:
            value = (value << 1) | (1 if symbol == "#" else 0)
        value <<= row_bytes * 8 - width
        payload.extend(value.to_bytes(row_bytes, "big"))
    return f"P4\n{width} {len(rows)}\n".encode() + bytes(payload)


CROSS = pbm(
    "..#..",
    "..#..",
    "#####",
    "..#..",
    "..#..",
)
BOX = pbm(
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####",
)
TWO_BARS = pbm(
    "#...#",
    "#...#",
    "#...#",
    "#...#",
    "#...#",
)
DIAGONAL_CROSS = pbm(
    "#...#",
    ".#.#.",
    "..#..",
    ".#.#.",
    "#...#",
)
HASH_MUTATED_CROSS = pbm(
    ".##..",
    "..#..",
    "#####",
    "..#..",
    "..#..",
)

SYNTHETIC_TEMPLATES: tuple[TemplatePBM, ...] = (
    ("glyph-5", 11, CROSS),
    ("box", 22, BOX),
    ("bars", 33, TWO_BARS),
)
# These deliberately impossible lane coordinates keep every public test value
# separate from a private sign-list inventory while satisfying the roster ID
# grammar.  This set freezes under both the explicit small grid and the
# compiled default grid.
BOUND_TEMPLATES: tuple[TemplatePBM, ...] = (
    ("KP1979:P20:L99:R00", 11, CROSS),
    ("KP1979:P20:L99:R01", 22, BOX),
    ("KP1979:P20:L99:R02", 33, TWO_BARS),
)
COLLISION_TEMPLATES: tuple[TemplatePBM, ...] = (
    ("KP1979:P20:L98:R00", 10, CROSS),
    ("KP1979:P20:L98:R01", 11, CROSS),
    ("KP1979:P20:L98:R02", 12, BOX),
    ("KP1979:P20:L98:R03", 13, TWO_BARS),
    ("KP1979:P20:L98:R04", 14, DIAGONAL_CROSS),
)
SMALL_GRID = CalibrationGrid(
    max_token_costs=(500_000, 1_250_000),
    min_different_rank_margins=(1,),
    min_path_margins=(1,),
    cut_policies=((0, 0),),
)


def config(
    *,
    max_token_cost: int = 500_000,
    rank_margin: int = 1,
    path_margin: int = 1,
    cut_support: int = 0,
    cut_penalty: int = 0,
) -> MatcherConfig:
    return MatcherConfig(
        max_token_cost=max_token_cost,
        min_different_rank_margin=rank_margin,
        min_path_margin=path_margin,
        unknown_edge_cost=4_500_000,
        cut_gap_support_ppm=cut_support,
        max_cut_penalty=cut_penalty,
    )


def roster_bytes_for(template_pbms: tuple[TemplatePBM, ...]) -> bytes:
    catalog_bytes, geometry_bytes, glyphs = inputs()
    roster = build_sign_template_roster(
        catalog_bytes,
        geometry_bytes,
        glyphs.__getitem__,
    )
    roster["templates"] = [
        {
            "variant_id": variant_id,
            "catalog_rank": catalog_rank,
            "glyph": {
                "sha256": f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}",
                "byte_size": len(raw_bytes),
                "width": parse_canonical_pbm(raw_bytes).width,
                "height": parse_canonical_pbm(raw_bytes).height,
            },
        }
        for variant_id, catalog_rank, raw_bytes in template_pbms
    ]
    return encode_json(roster)


class CalibrationGridTests(unittest.TestCase):
    def test_grid_rejects_noncanonical_integer_values_and_malformed_cut_policy(self) -> None:
        invalid_values: tuple[dict[str, Any], ...] = (
            {"max_token_costs": (500_000, 250_000)},
            {"min_different_rank_margins": (False,)},
            {"min_path_margins": (0,)},
            {"cut_policies": ((0, 1),)},
        )
        for changes in invalid_values:
            with self.subTest(changes=changes), self.assertRaises(KP1979MatchCalibrationError):
                CalibrationGrid(**changes)

    def test_grid_round_trip_is_exact_and_rejects_extra_fields(self) -> None:
        mapping = SMALL_GRID.to_mapping()
        self.assertEqual(SMALL_GRID, CalibrationGrid.from_mapping(mapping))
        mapping["unexpected"] = 0
        with self.assertRaises(KP1979MatchCalibrationError):
            CalibrationGrid.from_mapping(mapping)


class ClosedSetControlTests(unittest.TestCase):
    def test_controls_are_result_blind_deterministic_padded_and_cover_lengths(self) -> None:
        first = build_closed_set_control_cases(SYNTHETIC_TEMPLATES)
        second = build_closed_set_control_cases(reversed(SYNTHETIC_TEMPLATES))
        self.assertEqual(first, second)
        self.assertEqual(
            set(range(2, 9)),
            {len(case.expected_ranks) for case in first if not case.single_source_glyph},
        )
        self.assertTrue(all(0 <= case.fold < 5 for case in first))
        self.assertEqual(
            {"identity", "other_view", "concatenation"},
            {case.stratum for case in first},
        )
        for case in first:
            mask = parse_canonical_pbm(case.row_pbm)
            edge_bits = (1 << (mask.width - 1)) | 1
            self.assertEqual(0, mask.rows[0])
            self.assertEqual(0, mask.rows[-1])
            self.assertFalse(any(row & edge_bits for row in mask.rows))

    def test_cross_rank_normalized_equalities_match_core_collision_guard(self) -> None:
        near_square_a = pbm(*(["#" * 55] * 56))
        near_square_b = pbm(*(["#" * 56] * 57))
        index = build_template_index(
            [
                ("same-rank-a", 1, CROSS),
                ("same-rank-b", 1, CROSS),
                ("different-rank", 2, CROSS),
                ("distinct", 3, BOX),
                ("rounded-aspect-a", 4, near_square_a),
                ("rounded-aspect-b", 5, near_square_b),
            ]
        )
        groups = detect_cross_rank_normalized_equalities(index)
        self.assertTrue(
            any(
                set(group["catalog_ranks"]) == {1, 2}
                and set(group["variant_ids"]) == {"same-rank-a", "same-rank-b", "different-rank"}
                for group in groups
            )
        )
        self.assertTrue(all(len(set(group["catalog_ranks"])) > 1 for group in groups))
        self.assertEqual(
            index.cross_rank_normalized_variant_ids,
            frozenset(variant_id for group in groups for variant_id in group["variant_ids"]),
        )

    def test_collision_variants_have_only_required_ambiguity_identity_controls(self) -> None:
        cases = build_closed_set_control_cases(COLLISION_TEMPLATES)
        collision_ids = {COLLISION_TEMPLATES[0][0], COLLISION_TEMPLATES[1][0]}
        collision_cases = [
            case
            for case in cases
            if any(variant_id in case.case_id for variant_id in collision_ids)
            and case.single_source_glyph
        ]
        self.assertEqual(2, len(collision_cases))
        self.assertTrue(all(case.stratum == "collision_identity" for case in collision_cases))
        self.assertTrue(
            all(case.case_id.startswith("single:identity:") for case in collision_cases)
        )

    def test_materialization_stops_after_bounded_max_plus_one(self) -> None:
        consumed = 0

        def endless() -> Iterator[TemplatePBM]:
            nonlocal consumed
            while True:
                consumed += 1
                yield ("unvalidated", 1, CROSS)

        with self.assertRaisesRegex(KP1979MatchCalibrationError, "count limit"):
            calibrate_matcher_plan(endless(), grid=SMALL_GRID)
        self.assertEqual(MAX_TEMPLATE_COUNT + 1, consumed)

    def test_materialization_rejects_first_oversized_item_before_consuming_second(self) -> None:
        consumed = 0

        def values() -> Iterator[TemplatePBM]:
            nonlocal consumed
            consumed += 1
            yield ("oversized", 1, b"x" * (MAX_TEMPLATE_PBM_BYTES + 1))
            consumed += 1
            yield ("must-not-be-consumed", 2, CROSS)

        with self.assertRaisesRegex(KP1979MatchCalibrationError, "input is invalid"):
            calibrate_matcher_plan(values(), grid=SMALL_GRID)
        self.assertEqual(1, consumed)


class ThresholdSelectionTests(unittest.TestCase):
    def test_selection_requires_zero_false_accepts_then_zero_splits_then_coverage(self) -> None:
        false_accept = ThresholdEvaluation(config(), 1, 0, 100, 101)
        split = ThresholdEvaluation(config(), 0, 1, 90, 100)
        failed_floor = ThresholdEvaluation(config(), 0, 0, 99, 100, False)
        lower_coverage = ThresholdEvaluation(config(), 0, 0, 4, 100)
        higher_coverage = ThresholdEvaluation(config(max_token_cost=750_000), 0, 0, 5, 100)

        selected = select_threshold_evaluation(
            (false_accept, split, failed_floor, lower_coverage, higher_coverage)
        )
        self.assertIs(higher_coverage, selected)

    def test_equal_coverage_prefers_stricter_integer_thresholds(self) -> None:
        loose = ThresholdEvaluation(
            config(max_token_cost=750_000, rank_margin=1, path_margin=1),
            0,
            0,
            5,
            10,
        )
        strict = ThresholdEvaluation(
            config(max_token_cost=500_000, rank_margin=100_000, path_margin=100_000),
            0,
            0,
            5,
            10,
        )
        self.assertIs(strict, select_threshold_evaluation((loose, strict)))
        self.assertIsNone(
            select_threshold_evaluation((ThresholdEvaluation(config(), 0, 0, 0, 10),))
        )

    def test_equal_coverage_prefers_stronger_small_gap_cut_penalty(self) -> None:
        unpenalized = ThresholdEvaluation(config(), 0, 0, 5, 10)
        penalized = ThresholdEvaluation(
            config(cut_support=125_000, cut_penalty=250_000),
            0,
            0,
            5,
            10,
        )
        self.assertIs(
            penalized,
            select_threshold_evaluation((unpenalized, penalized)),
        )


class MatcherPlanTests(unittest.TestCase):
    def test_template_only_plan_freezes_with_predeclared_coverage_in_both_partitions(self) -> None:
        with patch("builtins.open", side_effect=AssertionError("filesystem read attempted")):
            first = calibrate_matcher_plan(SYNTHETIC_TEMPLATES, grid=SMALL_GRID)
            second = calibrate_matcher_plan(reversed(SYNTHETIC_TEMPLATES), grid=SMALL_GRID)

        self.assertEqual(first, second)
        self.assertEqual("frozen_closed_template_retrieval_only", first["status"])
        self.assertEqual("frozen", first["threshold_state"])
        self.assertIsNotNone(first["configuration"])
        MatcherConfig.from_mapping(first["configuration"])

        for partition in ("calibration", "validation"):
            metrics = first["closed_set_controls"][partition]
            self.assertEqual(0, metrics["false_accepted"])
            self.assertEqual(0, metrics["accepted_single_glyph_splits"])
            self.assertTrue(metrics["coverage_floor_passed"])
            for stratum in ("identity", "other_view", "concatenation"):
                values = metrics["strata"][stratum]
                self.assertGreaterEqual(values["case_count"], 1)
                self.assertGreaterEqual(values["correct_accepted"], values["required_correct"])
            identity = metrics["strata"]["identity"]
            self.assertEqual(identity["case_count"], identity["correct_accepted"])

        lovo = first["open_set_lovo_negative_control"]
        self.assertEqual(len(SYNTHETIC_TEMPLATES), lovo["case_count"])
        self.assertFalse(lovo["used_for_threshold_selection"])
        self.assertFalse(lovo["generalization_claimed"])
        self.assertEqual(
            lovo["case_count"],
            lovo["same_rank_proposed"] + lovo["wrong_rank_proposed"] + lovo["abstained"],
        )

        self.assertEqual(
            {
                "closed_template_near_exact_retrieval_only": True,
                "open_set_allograph_generalization_claimed": False,
                "language_or_frequency_prior_used": False,
                "reading_direction_inferred": False,
                "accepted_transcription": False,
                "decipherment": False,
            },
            first["claim_scope"],
        )
        self.assertEqual(
            "exclude_cross_rank_normalized_collision_variants",
            first["coverage_policy"]["positive_view_eligibility"],
        )
        self.assertFalse(first["fold_protocol"]["development_rows_used"])
        self.assertFalse(first["fold_protocol"]["page_images_used"])
        self.assertFalse(first["assurances"]["development_rows_consumed_by_calibration"])
        self.assertFalse(first["assurances"]["future_evaluation_pixels_consumed_by_calibration"])
        self.assertFalse(first["assurances"]["thresholds_selected_from_open_set_lovo"])
        self.assertFalse(first["assurances"]["prize_submission_eligible"])

    def test_one_template_cannot_freeze_both_partition_coverage(self) -> None:
        plan = calibrate_matcher_plan((BOUND_TEMPLATES[0],), grid=SMALL_GRID)
        self.assertEqual("no_go", plan["status"])
        self.assertEqual("not_frozen", plan["threshold_state"])
        self.assertIsNone(plan["configuration"])
        self.assertFalse(plan["closed_set_controls"]["calibration"]["coverage_floor_passed"])

    def test_grid_search_uses_final_stability_gates_shares_path_work_and_holds_validation(
        self,
    ) -> None:
        grid = CalibrationGrid(
            max_token_costs=(500_000, 1_250_000),
            min_different_rank_margins=(1, 100_000),
            min_path_margins=(1, 100_000, 250_000),
            cut_policies=((0, 0), (125_000, 250_000)),
        )
        cases = build_closed_set_control_cases(SYNTHETIC_TEMPLATES)
        calibration_count = sum(case.fold != 4 for case in cases)
        validation_count = len(cases) - calibration_count
        calls: list[tuple[str, int, MatcherConfig]] = []
        original = calibration_module._observe

        def recording_observe(
            case: Any,
            *,
            index: Any,
            config: MatcherConfig,
            require_proposed_status: bool = False,
        ) -> Any:
            calls.append((case.case_id, case.fold, config))
            return original(
                case,
                index=index,
                config=config,
                require_proposed_status=require_proposed_status,
            )

        with patch.object(calibration_module, "_observe", side_effect=recording_observe):
            plan = calibrate_matcher_plan(SYNTHETIC_TEMPLATES, grid=grid)

        self.assertEqual("frozen_closed_template_retrieval_only", plan["status"])
        probe_configurations = (
            len(grid.max_token_costs)
            * len(grid.cut_policies)
            * len(grid.min_different_rank_margins)
        )
        self.assertEqual(
            calibration_count * probe_configurations + len(cases),
            len(calls),
        )
        self.assertTrue(all(call_config.require_speck_stability for _, _, call_config in calls))
        self.assertTrue(all(call_config.require_shift_stability for _, _, call_config in calls))
        validation_calls = [case_id for case_id, fold, _ in calls if fold == 4]
        self.assertEqual(validation_count, len(validation_calls))
        self.assertTrue(all(count == 1 for count in Counter(validation_calls).values()))
        calibration_calls = [case_id for case_id, fold, _ in calls if fold != 4]
        self.assertTrue(
            all(count == probe_configurations + 1 for count in Counter(calibration_calls).values())
        )

    def test_collision_identity_is_required_negative_and_structural_inventory_is_exact(
        self,
    ) -> None:
        roster_bytes = roster_bytes_for(COLLISION_TEMPLATES)
        plan = calibrate_matcher_plan(COLLISION_TEMPLATES, grid=SMALL_GRID)
        self.assertEqual("frozen_closed_template_retrieval_only", plan["status"])
        equality = plan["cross_rank_normalized_equality"]
        self.assertEqual(1, equality["group_count"])
        self.assertEqual(2, equality["affected_variant_count"])
        for partition in ("calibration", "validation"):
            collision = plan["closed_set_controls"][partition][
                "collision_identity_negative_control"
            ]
            self.assertEqual(1, collision["case_count"])
            self.assertEqual(1, collision["correct_abstained"])
            self.assertEqual(0, collision["rank_proposals"])
        metrics = plan["closed_set_controls"]
        expected_count = 3 * len(COLLISION_TEMPLATES) + 21 - 2 * 2
        self.assertEqual(
            expected_count,
            metrics["calibration"]["case_count"] + metrics["validation"]["case_count"],
        )
        plan_bytes = encode_json(plan)
        matcher_config_from_plan(plan_bytes, roster_bytes)
        matcher_config_from_recomputed_plan(
            plan_bytes,
            roster_bytes,
            COLLISION_TEMPLATES,
            grid=SMALL_GRID,
        )

    def test_structural_verifier_rejects_no_go_unknown_fields_and_noncanonical_bytes(self) -> None:
        roster_bytes = roster_bytes_for(BOUND_TEMPLATES)
        plan = calibrate_matcher_plan(BOUND_TEMPLATES, grid=SMALL_GRID)
        plan_bytes = encode_json(plan)
        verified = matcher_config_from_plan(plan_bytes, roster_bytes)
        self.assertEqual(plan["configuration"], verified.to_mapping())

        tampered_values: list[dict[str, Any]] = []
        no_go = deepcopy(plan)
        no_go["status"] = "no_go"
        tampered_values.append(no_go)
        weakened = deepcopy(plan)
        weakened["configuration"]["min_different_rank_margin"] = 0
        tampered_values.append(weakened)
        false_accept = deepcopy(plan)
        false_accept["closed_set_controls"]["validation"]["false_accepted"] = 1
        tampered_values.append(false_accept)
        unknown_field = deepcopy(plan)
        unknown_field["unexpected"] = False
        tampered_values.append(unknown_field)

        for tampered in tampered_values:
            with self.subTest(tampered=tampered), self.assertRaises(KP1979MatchCalibrationError):
                matcher_config_from_plan(encode_json(tampered), roster_bytes)

        noncanonical = json.dumps(plan, separators=(",", ":")).encode()
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "not canonical"):
            matcher_config_from_plan(noncanonical, roster_bytes)


class RecomputedPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roster_bytes = roster_bytes_for(BOUND_TEMPLATES)
        self.plan = calibrate_matcher_plan(BOUND_TEMPLATES, grid=SMALL_GRID)
        self.plan_bytes = encode_json(self.plan)

    def test_exact_api_recomputes_and_binds_explicit_grid(self) -> None:
        verified = matcher_config_from_recomputed_plan(
            self.plan_bytes,
            self.roster_bytes,
            BOUND_TEMPLATES,
            grid=SMALL_GRID,
        )
        self.assertEqual(self.plan["configuration"], verified.to_mapping())

        consumed = False

        def unexplored() -> Iterator[TemplatePBM]:
            nonlocal consumed
            consumed = True
            yield from BOUND_TEMPLATES

        with self.assertRaisesRegex(KP1979MatchCalibrationError, "trusted grid"):
            matcher_config_from_recomputed_plan(
                self.plan_bytes,
                self.roster_bytes,
                unexplored(),
            )
        self.assertFalse(consumed)

    def test_default_grid_is_compiled_not_learned_from_plan_and_has_frozen_fixture(self) -> None:
        default_plan = calibrate_matcher_plan(BOUND_TEMPLATES)
        self.assertEqual("frozen_closed_template_retrieval_only", default_plan["status"])
        verified = matcher_config_from_recomputed_plan(
            encode_json(default_plan),
            self.roster_bytes,
            BOUND_TEMPLATES,
        )
        self.assertEqual(default_plan["configuration"], verified.to_mapping())

    def test_exact_recomputation_rejects_coherent_self_report_tampering(self) -> None:
        in_range_config = deepcopy(self.plan)
        in_range_config["configuration"]["max_token_cost"] = 1_250_000

        coherent_metrics = deepcopy(self.plan)
        validation = coherent_metrics["closed_set_controls"]["validation"]
        validation["strata"]["other_view"]["correct_accepted"] = 2
        validation["correct_accepted"] = 8

        coherent_lovo = deepcopy(self.plan)
        coherent_lovo["open_set_lovo_negative_control"]["wrong_rank_proposed"] = 1
        coherent_lovo["open_set_lovo_negative_control"]["abstained"] = 2

        coherent_collision = deepcopy(self.plan)
        equality = coherent_collision["cross_rank_normalized_equality"]
        equality["group_count"] = 1
        equality["affected_variant_count"] = 2
        calibration = coherent_collision["closed_set_controls"]["calibration"]
        calibration["case_count"] = 19
        calibration["correct_accepted"] = 18
        calibration["strata"]["other_view"] = {
            "case_count": 1,
            "correct_accepted": 1,
            "required_correct": 1,
        }
        calibration["strata"]["concatenation"] = {
            "case_count": 15,
            "correct_accepted": 15,
            "required_correct": 8,
        }
        calibration["collision_identity_negative_control"] = {
            "case_count": 1,
            "correct_abstained": 1,
            "required_correct_abstentions": 1,
            "rank_proposals": 0,
        }
        validation = coherent_collision["closed_set_controls"]["validation"]
        validation["case_count"] = 7
        validation["correct_accepted"] = 6
        validation["strata"]["other_view"] = {
            "case_count": 1,
            "correct_accepted": 1,
            "required_correct": 1,
        }
        validation["strata"]["concatenation"] = {
            "case_count": 4,
            "correct_accepted": 4,
            "required_correct": 2,
        }
        validation["collision_identity_negative_control"] = {
            "case_count": 1,
            "correct_abstained": 1,
            "required_correct_abstentions": 1,
            "rank_proposals": 0,
        }

        for tampered in (in_range_config, coherent_metrics, coherent_lovo):
            tampered_bytes = encode_json(tampered)
            # These mutations remain internally plausible to the deliberately
            # weaker two-argument structural verifier and therefore exercise
            # exact recalibration rather than only a cheap aggregate gate.
            matcher_config_from_plan(tampered_bytes, self.roster_bytes)
            with (
                self.subTest(tampered=tampered),
                self.assertRaisesRegex(
                    KP1979MatchCalibrationError,
                    "exact recomputation",
                ),
            ):
                matcher_config_from_recomputed_plan(
                    tampered_bytes,
                    self.roster_bytes,
                    BOUND_TEMPLATES,
                    grid=SMALL_GRID,
                )

        # The collision mutation is cheap-rejected because V2 can derive the
        # exact per-stratum partition inventory from N and affected count.
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "stratum inventory"):
            matcher_config_from_recomputed_plan(
                encode_json(coherent_collision),
                self.roster_bytes,
                BOUND_TEMPLATES,
                grid=SMALL_GRID,
            )

    def test_exact_api_binds_raw_order_identity_rank_hash_size_and_dimensions(self) -> None:
        wrong_id = list(BOUND_TEMPLATES)
        wrong_id[0] = ("KP1979:P20:L99:R03", wrong_id[0][1], wrong_id[0][2])
        wrong_rank = list(BOUND_TEMPLATES)
        wrong_rank[0] = (wrong_rank[0][0], 99, wrong_rank[0][2])
        wrong_hash = list(BOUND_TEMPLATES)
        wrong_hash[0] = (wrong_hash[0][0], wrong_hash[0][1], HASH_MUTATED_CROSS)
        wrong_dimensions = list(BOUND_TEMPLATES)
        wrong_dimensions[0] = (
            wrong_dimensions[0][0],
            wrong_dimensions[0][1],
            pbm("...#..", "...#..", "######", "...#..", "...#.."),
        )
        wrong_size = list(BOUND_TEMPLATES)
        wrong_size[0] = (
            wrong_size[0][0],
            wrong_size[0][1],
            pbm("....#....", "....#....", "#########", "....#....", "....#...."),
        )
        raw_variants = (
            tuple(reversed(BOUND_TEMPLATES)),
            tuple(wrong_id),
            tuple(wrong_rank),
            tuple(wrong_hash),
            tuple(wrong_dimensions),
            tuple(wrong_size),
        )
        for raw_values in raw_variants:
            with (
                self.subTest(raw_values=raw_values),
                self.assertRaisesRegex(
                    KP1979MatchCalibrationError,
                    "binding differs",
                ),
            ):
                matcher_config_from_recomputed_plan(
                    self.plan_bytes,
                    self.roster_bytes,
                    raw_values,
                    grid=SMALL_GRID,
                )

        reordered_roster = json.loads(self.roster_bytes)
        reordered_roster["templates"].reverse()
        reordered_roster_bytes = encode_json(reordered_roster)
        matcher_config_from_plan(self.plan_bytes, reordered_roster_bytes)
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "binding differs"):
            matcher_config_from_recomputed_plan(
                self.plan_bytes,
                reordered_roster_bytes,
                BOUND_TEMPLATES,
                grid=SMALL_GRID,
            )

        wrong_dimension_roster = json.loads(self.roster_bytes)
        wrong_dimension_roster["templates"][0]["glyph"]["width"] = 4
        wrong_dimension_roster_bytes = encode_json(wrong_dimension_roster)
        matcher_config_from_plan(self.plan_bytes, wrong_dimension_roster_bytes)
        with self.assertRaisesRegex(KP1979MatchCalibrationError, "binding differs"):
            matcher_config_from_recomputed_plan(
                self.plan_bytes,
                wrong_dimension_roster_bytes,
                BOUND_TEMPLATES,
                grid=SMALL_GRID,
            )

    def test_plan_canonical_and_structural_gates_run_before_iterator_or_recalibration(self) -> None:
        consumed = False

        def unexplored() -> Iterator[TemplatePBM]:
            nonlocal consumed
            consumed = True
            yield from BOUND_TEMPLATES

        noncanonical = json.dumps(self.plan, separators=(",", ":")).encode()
        with (
            patch.object(
                calibration_module,
                "calibrate_matcher_plan",
                side_effect=AssertionError("recalibration must not run"),
            ),
            self.assertRaisesRegex(KP1979MatchCalibrationError, "not canonical"),
        ):
            matcher_config_from_recomputed_plan(
                noncanonical,
                self.roster_bytes,
                unexplored(),
                grid=SMALL_GRID,
            )
        self.assertFalse(consumed)

        nested: object = 0
        for _ in range(66):
            nested = [nested]
        excessive_nesting = deepcopy(self.plan)
        excessive_nesting["claim_scope"] = nested
        with (
            patch.object(
                calibration_module,
                "calibrate_matcher_plan",
                side_effect=AssertionError("recalibration must not run"),
            ),
            self.assertRaisesRegex(KP1979MatchCalibrationError, "nesting"),
        ):
            matcher_config_from_recomputed_plan(
                encode_json(excessive_nesting),
                self.roster_bytes,
                unexplored(),
                grid=SMALL_GRID,
            )
        self.assertFalse(consumed)

        structurally_invalid = deepcopy(self.plan)
        structurally_invalid["closed_set_controls"]["validation"]["false_accepted"] = 1
        with (
            patch.object(
                calibration_module,
                "calibrate_matcher_plan",
                side_effect=AssertionError("recalibration must not run"),
            ),
            self.assertRaises(KP1979MatchCalibrationError),
        ):
            matcher_config_from_recomputed_plan(
                encode_json(structurally_invalid),
                self.roster_bytes,
                unexplored(),
                grid=SMALL_GRID,
            )
        self.assertFalse(consumed)


if __name__ == "__main__":
    unittest.main()
