from __future__ import annotations

import math
import unittest

from indusbench.baseline import (
    AddOneNGramBaseline,
    UnigramBaseline,
    extract_sequences,
    score_missing_signs,
)


class SequenceExtractionTests(unittest.TestCase):
    def test_nested_tokens_are_sorted_by_reading_index(self) -> None:
        records = [
            {
                "artifact_id": "A",
                "sides": [
                    {
                        "lines": [
                            {
                                "tokens": [
                                    {"sign_id": "M003", "reading_index": 2},
                                    {"sign_id": "M001", "reading_index": 0},
                                    {"sign_id": "M002", "reading_index": 1},
                                ]
                            }
                        ]
                    }
                ],
            }
        ]
        self.assertEqual(extract_sequences(records), [("M001", "M002", "M003")])

    def test_unreadable_token_breaks_context_instead_of_collapsing_it(self) -> None:
        self.assertEqual(
            extract_sequences([["M001", None, "M002"]]),
            [("M001",), ("M002",)],
        )

    def test_right_to_left_visual_order_is_used_when_reading_index_is_missing(self) -> None:
        record = {
            "artifact_id": "A",
            "tokens": [
                {"sign_id": "M002", "visual_index": 0},
                {"sign_id": "M001", "visual_index": 1},
            ],
            "reading_direction": "right_to_left",
        }
        self.assertEqual(extract_sequences(record), [("M001", "M002")])


class UnigramBaselineTests(unittest.TestCase):
    def test_probabilities_and_heldout_score(self) -> None:
        model = UnigramBaseline().fit([["A", "A", "B"]])
        self.assertAlmostEqual(model.token_probability("A"), 2 / 3)
        self.assertAlmostEqual(model.token_probability("B"), 1 / 3)
        self.assertEqual(model.predict_missing(["A"], 0), {"A": 2 / 3, "B": 1 / 3})

        score = model.score_heldout([["A", "B"]])
        self.assertEqual(score.sequence_count, 1)
        self.assertEqual(score.token_count, 2)
        self.assertAlmostEqual(score.log_likelihood, math.log(2 / 3) + math.log(1 / 3))
        self.assertAlmostEqual(score.perplexity, math.sqrt(9 / 2))

    def test_unseen_heldout_sign_has_infinite_perplexity(self) -> None:
        model = UnigramBaseline().fit([["A", "B"]])
        score = model.score_heldout([["Z"]])
        self.assertEqual(score.log_likelihood, -math.inf)
        self.assertEqual(score.perplexity, math.inf)


class AddOneNGramBaselineTests(unittest.TestCase):
    def test_add_one_conditional_probability(self) -> None:
        model = AddOneNGramBaseline(order=2).fit([["A", "B"], ["A", "B"], ["A", "C"]])
        # Vocabulary A/B/C plus an explicit unknown outcome:
        # (count(A→B) + 1) / (count(A→*) + 4) = 3 / 7.
        self.assertAlmostEqual(model.token_probability("B", ["A"]), 3 / 7)

    def test_unseen_sign_receives_finite_heldout_score(self) -> None:
        model = AddOneNGramBaseline(order=3).fit([["A", "B", "C"]])
        score = model.score_heldout([["A", "Z", "C"]])
        self.assertTrue(math.isfinite(score.log_likelihood))
        self.assertTrue(math.isfinite(score.perplexity))

    def test_missing_sign_prediction_and_metrics_are_deterministic(self) -> None:
        model = AddOneNGramBaseline(order=2).fit(
            [
                ["A", "B", "X"],
                ["A", "B", "X"],
                ["A", "B", "X"],
                ["A", "C", "Y"],
            ]
        )
        probabilities = model.predict_missing(["A", "B", "X"], 1)
        self.assertAlmostEqual(sum(probabilities.values()), 1.0)
        self.assertEqual(max(probabilities, key=lambda sign: probabilities[sign]), "B")

        score = score_missing_signs(model, [["A", "B", "X"]])
        self.assertEqual(score.evaluated_tokens, 3)
        self.assertEqual(score.skipped_oov_tokens, 0)
        self.assertGreaterEqual(score.accuracy, 0.0)
        self.assertLessEqual(score.accuracy, 1.0)
        self.assertGreater(score.mean_reciprocal_rank, 0.0)

    def test_missing_sign_scoring_skips_oov_by_default(self) -> None:
        model = AddOneNGramBaseline(order=2).fit([["A", "B"]])
        score = score_missing_signs(model, [["A", "Z"]])
        self.assertEqual(score.evaluated_tokens, 1)
        self.assertEqual(score.skipped_oov_tokens, 1)

    def test_optimized_missing_prediction_matches_full_sequence_rescoring(self) -> None:
        training = [
            ["A", "B", "C", "A"],
            ["A", "C", "B", "A"],
            ["B", "A", "C", "B"],
        ]
        target = ["A", "B", "C", "A"]
        for order in (1, 2, 3):
            model = AddOneNGramBaseline(order=order).fit(training)
            for missing_index in range(len(target)):
                optimized = model.predict_missing(target, missing_index)
                log_scores = {}
                for candidate in model.vocabulary:
                    candidate_sequence = target.copy()
                    candidate_sequence[missing_index] = candidate
                    log_scores[candidate] = model.sequence_log_probability(candidate_sequence)
                maximum = max(log_scores.values())
                weights = {
                    sign: math.exp(log_score - maximum) for sign, log_score in log_scores.items()
                }
                normalizer = sum(weights.values())
                expected = {sign: weight / normalizer for sign, weight in weights.items()}
                for sign in model.vocabulary:
                    self.assertAlmostEqual(expected[sign], optimized[sign])

    def test_invalid_order_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AddOneNGramBaseline(order=0)


if __name__ == "__main__":
    unittest.main()
