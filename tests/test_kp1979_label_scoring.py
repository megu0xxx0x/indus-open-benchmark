from __future__ import annotations

import ast
import unittest
from pathlib import Path

from indusbench.kp1979_label_scoring import (
    KP1979LabelScoringError,
    LabelPrediction,
    LabelReferenceInterval,
    PageLane,
    _score_label_positions,
)

ROOT = Path(__file__).resolve().parents[1]
score_label_positions = _score_label_positions


def prediction(
    page: int,
    lane: int,
    y0: int,
    *,
    height: int = 96,
) -> LabelPrediction:
    return LabelPrediction(page, lane, y0, y0 + height)


def reference(
    page: int,
    lane: int,
    y0: int,
    y1: int,
) -> LabelReferenceInterval:
    return LabelReferenceInterval(page, lane, y0, y1)


class KP1979LabelScoringTests(unittest.TestCase):
    def test_unique_matches_use_half_open_anchor_intervals(self) -> None:
        result = score_label_positions(
            [
                prediction(22, 0, 100),  # anchor 148: included at the lower bound
                prediction(22, 0, 200),  # anchor 248: excluded at the upper bound
            ],
            [
                reference(22, 0, 148, 180),
                reference(22, 0, 220, 248),
            ],
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[],
        )

        self.assertEqual("scored", result.status)
        self.assertEqual(1, result.true_positives)
        self.assertEqual(1, result.false_positives)
        self.assertEqual(1, result.false_negatives)
        self.assertEqual(0.5, result.micro_precision)
        self.assertEqual(0.5, result.micro_recall)
        self.assertEqual(1, len(result.matches))
        self.assertEqual(148, result.matches[0].prediction.anchor_y)
        self.assertEqual("synthetic_control", result.reference_use)
        self.assertFalse(result.reference_eligibility_verified)
        self.assertFalse(result.evaluation_admissible)
        self.assertFalse(result.real_accuracy)
        self.assertFalse(result.decipherment)
        self.assertFalse(result.prize_submission_eligible)

    def test_machine_development_geometry_is_ineligible_for_scoring(self) -> None:
        with self.assertRaisesRegex(
            KP1979LabelScoringError,
            "machine-development geometry is ineligible",
        ):
            score_label_positions(
                [prediction(22, 0, 100)],
                [reference(22, 0, 140, 180)],
                reference_use="machine_development",
                positive_pages=[22],
                negative_pages=[],
            )

    def test_external_reference_requires_a_future_exact_artifact_gate(self) -> None:
        with self.assertRaisesRegex(
            KP1979LabelScoringError,
            "exact-artifact eligibility gate",
        ):
            score_label_positions(
                [prediction(22, 0, 100)],
                [reference(22, 0, 140, 180)],
                reference_use="external_reference_candidate",
                positive_pages=[22],
                negative_pages=[],
            )

    def test_matching_is_same_page_same_lane_and_order_preserving(self) -> None:
        result = score_label_positions(
            [
                prediction(22, 0, 300),
                prediction(22, 0, 100),
                prediction(22, 1, 100),
                prediction(23, 0, 100),
            ],
            [
                reference(22, 0, 140, 180),
                reference(22, 0, 340, 380),
                reference(22, 1, 500, 540),
                reference(23, 0, 500, 540),
            ],
            reference_use="synthetic_control",
            positive_pages=[23, 22],
            negative_pages=[],
        )

        self.assertEqual("scored", result.status)
        self.assertEqual(
            [(22, 0, 148), (22, 0, 348)],
            [
                (
                    match.prediction.pdf_page_number,
                    match.prediction.lane_index,
                    match.prediction.anchor_y,
                )
                for match in result.matches
            ],
        )
        self.assertEqual(2, result.true_positives)
        self.assertEqual(2, result.false_positives)
        self.assertEqual(2, result.false_negatives)
        self.assertEqual([22, 23], [page.pdf_page_number for page in result.positive_pages])

    def test_more_than_one_maximum_matching_is_ambiguous_and_unscored(self) -> None:
        result = score_label_positions(
            [
                prediction(22, 0, 0),  # anchor 48
                prediction(22, 0, 10),  # anchor 58
            ],
            [reference(22, 0, 40, 100)],
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[],
        )

        self.assertEqual("ambiguous_matching", result.status)
        self.assertEqual((), result.matches)
        self.assertEqual((), result.positive_pages)
        self.assertIsNone(result.true_positives)
        self.assertIsNone(result.false_positives)
        self.assertIsNone(result.false_negatives)
        self.assertIsNone(result.micro_precision)
        self.assertIsNone(result.micro_recall)

    def test_any_unresolved_lane_suppresses_all_scores(self) -> None:
        result = score_label_positions(
            [prediction(22, 0, 100)],
            [reference(22, 0, 140, 180)],
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[20],
            unresolved_lanes=[PageLane(22, 1)],
        )

        self.assertEqual("reference_incomplete", result.status)
        self.assertEqual((), result.matches)
        self.assertEqual((), result.positive_pages)
        self.assertEqual((), result.negative_controls)
        self.assertIsNone(result.true_positives)
        self.assertIsNone(result.false_positives)
        self.assertIsNone(result.false_negatives)
        self.assertIsNone(result.micro_precision)
        self.assertIsNone(result.micro_recall)
        self.assertIsNone(result.negative_control_empty)

    def test_empty_negative_controls_have_a_gate_but_no_ratios(self) -> None:
        result = score_label_positions(
            [prediction(22, 0, 100)],
            [reference(22, 0, 140, 180)],
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[20, 129],
        )

        self.assertEqual("scored", result.status)
        self.assertTrue(result.negative_control_empty)
        self.assertEqual(2, len(result.negative_controls))
        for gate in result.negative_controls:
            self.assertTrue(gate.empty)
            self.assertEqual(0, gate.prediction_count)
            self.assertEqual(0, gate.reference_count)
            self.assertFalse(hasattr(gate, "precision"))
            self.assertFalse(hasattr(gate, "recall"))

    def test_negative_prediction_fails_only_the_separate_empty_gate(self) -> None:
        result = score_label_positions(
            [
                prediction(22, 0, 100),
                prediction(20, 0, 100),
            ],
            [reference(22, 0, 140, 180)],
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[20],
        )

        self.assertEqual("scored", result.status)
        self.assertEqual(1.0, result.micro_precision)
        self.assertEqual(1.0, result.micro_recall)
        self.assertFalse(result.negative_control_empty)
        self.assertEqual(1, result.negative_controls[0].prediction_count)
        self.assertFalse(result.negative_controls[0].empty)

    def test_negative_only_evaluation_emits_no_accuracy_counts_or_ratios(self) -> None:
        result = score_label_positions(
            [],
            [],
            reference_use="synthetic_control",
            positive_pages=[],
            negative_pages=[20],
        )

        self.assertEqual("scored", result.status)
        self.assertTrue(result.negative_control_empty)
        self.assertEqual((), result.positive_pages)
        self.assertIsNone(result.true_positives)
        self.assertIsNone(result.false_positives)
        self.assertIsNone(result.false_negatives)
        self.assertIsNone(result.micro_precision)
        self.assertIsNone(result.micro_recall)

    def test_positive_page_with_no_predictions_has_zero_precision_and_recall(self) -> None:
        result = score_label_positions(
            [],
            [reference(22, 0, 140, 180)],
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[],
        )

        self.assertEqual("scored", result.status)
        self.assertEqual(0, result.true_positives)
        self.assertEqual(0, result.false_positives)
        self.assertEqual(1, result.false_negatives)
        self.assertEqual(0.0, result.micro_precision)
        self.assertEqual(0.0, result.micro_recall)
        self.assertIsNone(result.negative_control_empty)
        self.assertEqual(0.0, result.positive_pages[0].precision)
        self.assertEqual(0.0, result.positive_pages[0].recall)

    def test_prediction_height_is_exactly_96_pixels(self) -> None:
        for height in (95, 97):
            with (
                self.subTest(height=height),
                self.assertRaisesRegex(
                    KP1979LabelScoringError,
                    "exactly 96 pixels",
                ),
            ):
                score_label_positions(
                    [prediction(22, 0, 100, height=height)],
                    [reference(22, 0, 140, 180)],
                    reference_use="synthetic_control",
                    positive_pages=[22],
                    negative_pages=[],
                )

    def test_complete_page_role_contracts_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            KP1979LabelScoringError,
            "positive page",
        ):
            score_label_positions(
                [],
                [],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )
        with self.assertRaisesRegex(
            KP1979LabelScoringError,
            "negative-control",
        ):
            score_label_positions(
                [],
                [reference(20, 0, 140, 180)],
                reference_use="synthetic_control",
                positive_pages=[],
                negative_pages=[20],
            )
        with self.assertRaisesRegex(
            KP1979LabelScoringError,
            "disjoint",
        ):
            score_label_positions(
                [],
                [],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[22],
            )

    def test_invalid_coordinates_rosters_and_types_fail_closed(self) -> None:
        invalid_predictions = [
            LabelPrediction(True, 0, 100, 196),
            LabelPrediction(22, 2, 100, 196),
            LabelPrediction(22, 0, -1, 95),
            LabelPrediction(22, 0, 100, 100),
        ]
        for invalid in invalid_predictions:
            with self.subTest(invalid=invalid), self.assertRaises(KP1979LabelScoringError):
                score_label_positions(
                    [invalid],
                    [reference(22, 0, 140, 180)],
                    reference_use="synthetic_control",
                    positive_pages=[22],
                    negative_pages=[],
                )

        with self.assertRaisesRegex(KP1979LabelScoringError, "undeclared"):
            score_label_positions(
                [prediction(23, 0, 100)],
                [reference(22, 0, 140, 180)],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )
        with self.assertRaisesRegex(KP1979LabelScoringError, "duplicate"):
            score_label_positions(
                [],
                [],
                reference_use="synthetic_control",
                positive_pages=[],
                negative_pages=[20, 20],
            )
        with self.assertRaisesRegex(KP1979LabelScoringError, "PageLane"):
            score_label_positions(
                [],
                [],
                reference_use="synthetic_control",
                positive_pages=[],
                negative_pages=[20],
                unresolved_lanes=[("20", 0)],  # type: ignore[list-item]
            )

    def test_native_page_and_fixed_roster_limits_fail_closed_before_matching(self) -> None:
        with self.assertRaisesRegex(KP1979LabelScoringError, "half-open integer"):
            score_label_positions(
                [LabelPrediction(22, 0, 6915, 7011)],
                [reference(22, 0, 6900, 7010)],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )
        with self.assertRaisesRegex(KP1979LabelScoringError, "six-page limit"):
            score_label_positions(
                [],
                [],
                reference_use="synthetic_control",
                positive_pages=[1, 2, 3, 4, 5, 6, 7],
                negative_pages=[],
            )
        with self.assertRaisesRegex(KP1979LabelScoringError, "prediction lane"):
            score_label_positions(
                [prediction(22, 0, y0) for y0 in range(65)],
                [reference(22, 0, 0, 7010)],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )

    def test_duplicate_and_overlapping_reference_rosters_fail_closed(self) -> None:
        duplicate_prediction = prediction(22, 0, 100)
        with self.assertRaisesRegex(KP1979LabelScoringError, "prediction roster"):
            score_label_positions(
                [duplicate_prediction, duplicate_prediction],
                [reference(22, 0, 140, 180)],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )
        duplicate_reference = reference(22, 0, 140, 180)
        with self.assertRaisesRegex(KP1979LabelScoringError, "reference roster"):
            score_label_positions(
                [prediction(22, 0, 100)],
                [duplicate_reference, duplicate_reference],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )
        with self.assertRaisesRegex(KP1979LabelScoringError, "must not overlap"):
            score_label_positions(
                [prediction(22, 0, 100)],
                [
                    reference(22, 0, 100, 180),
                    reference(22, 0, 160, 220),
                ],
                reference_use="synthetic_control",
                positive_pages=[22],
                negative_pages=[],
            )

    def test_input_order_does_not_change_the_result(self) -> None:
        predictions = [
            prediction(22, 1, 300),
            prediction(22, 0, 100),
            prediction(22, 1, 100),
            prediction(22, 0, 300),
        ]
        references = [
            reference(22, 1, 340, 380),
            reference(22, 0, 140, 180),
            reference(22, 0, 340, 380),
            reference(22, 1, 140, 180),
        ]
        first = score_label_positions(
            predictions,
            references,
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[20],
        )
        second = score_label_positions(
            list(reversed(predictions)),
            list(reversed(references)),
            reference_use="synthetic_control",
            positive_pages=[22],
            negative_pages=[20],
        )
        self.assertEqual(first, second)

    def test_module_has_no_detector_source_or_reserved_evaluation_import(self) -> None:
        from indusbench import kp1979_label_scoring as module

        self.assertFalse(hasattr(module, "score_label_positions"))
        self.assertNotIn("_score_label_positions", module.__all__)
        module_path = ROOT / "src" / "indusbench" / "kp1979_label_scoring.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertEqual(
            {"__future__", "collections", "dataclasses", "itertools", "typing"},
            imported_roots,
        )


if __name__ == "__main__":
    unittest.main()
