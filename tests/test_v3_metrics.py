from __future__ import annotations

import math
import unittest

from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES, V3StructuralState
from indusbench.v3dev.metrics import (
    V3MetricError,
    WeightedStatePrediction,
    add_confusion_matrices,
    metrics_from_confusion,
    weighted_state_metrics,
)


class V3MetricTests(unittest.TestCase):
    def test_perfect_five_state_metrics_are_exact(self) -> None:
        rows = [
            WeightedStatePrediction(state, state, float(index + 1))
            for index, state in enumerate(V3_STRUCTURAL_STATES)
        ]
        report = weighted_state_metrics(rows)
        self.assertEqual(list(V3_STRUCTURAL_STATES), report["states"])
        self.assertEqual(15.0, report["total_family_mass"])
        self.assertEqual(1.0, report["weighted_accuracy"])
        self.assertEqual(1.0, report["balanced_accuracy"])
        self.assertEqual(1.0, report["macro_f1"])
        self.assertEqual(1.0, report["worst_state_recall"])

    def test_metrics_recompute_from_confusion_and_add_stably(self) -> None:
        first: dict[V3StructuralState, dict[V3StructuralState, float]] = {
            truth: {
                predicted: (0.5 if predicted == truth else 0.0)
                for predicted in V3_STRUCTURAL_STATES
            }
            for truth in V3_STRUCTURAL_STATES
        }
        second: dict[V3StructuralState, dict[V3StructuralState, float]] = {
            truth: {
                predicted: (0.25 if predicted == truth else 0.0)
                for predicted in V3_STRUCTURAL_STATES
            }
            for truth in V3_STRUCTURAL_STATES
        }
        combined = add_confusion_matrices([first, second])
        report = metrics_from_confusion(combined)
        self.assertTrue(math.isclose(report["total_family_mass"], 3.75))
        self.assertEqual(1.0, report["macro_f1"])

    def test_missing_state_support_and_bad_weights_fail_closed(self) -> None:
        with self.assertRaisesRegex(V3MetricError, "positive truth support"):
            metrics_from_confusion(
                {
                    truth: {
                        predicted: (
                            1.0 if truth != "settlement_name" and predicted == truth else 0.0
                        )
                        for predicted in V3_STRUCTURAL_STATES
                    }
                    for truth in V3_STRUCTURAL_STATES
                }
            )
        with self.assertRaisesRegex(V3MetricError, "finite and positive"):
            WeightedStatePrediction("context_only", "context_only", 0.0)


if __name__ == "__main__":
    unittest.main()
