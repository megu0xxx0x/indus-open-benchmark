"""Identifier-free aggregate metrics for V3 development."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .contracts import V3_STRUCTURAL_STATES, V3StructuralState


class V3MetricError(ValueError):
    """Raised when a development metric input violates the closed contract."""


@dataclass(frozen=True, slots=True)
class WeightedStatePrediction:
    """One internal weighted prediction.

    The family identifier is deliberately absent. Callers must calculate
    family-normalized weights before constructing these rows.
    """

    truth: V3StructuralState
    predicted: V3StructuralState
    weight: float

    def __post_init__(self) -> None:
        if self.truth not in V3_STRUCTURAL_STATES:
            raise V3MetricError("truth state is outside the five-state contract")
        if self.predicted not in V3_STRUCTURAL_STATES:
            raise V3MetricError("predicted state is outside the five-state contract")
        if (
            isinstance(self.weight, bool)
            or not isinstance(self.weight, (int, float))
            or not math.isfinite(self.weight)
            or self.weight <= 0.0
        ):
            raise V3MetricError("prediction weight must be finite and positive")


def weighted_state_metrics(
    rows: Sequence[WeightedStatePrediction],
) -> dict[str, Any]:
    """Return deterministic five-state metrics from caller-normalized rows."""

    if not rows:
        raise V3MetricError("at least one weighted prediction is required")
    contributions: dict[
        V3StructuralState,
        dict[V3StructuralState, list[float]],
    ] = {
        truth: {predicted: [] for predicted in V3_STRUCTURAL_STATES}
        for truth in V3_STRUCTURAL_STATES
    }
    for row in rows:
        contributions[row.truth][row.predicted].append(float(row.weight))
    confusion: dict[
        V3StructuralState,
        dict[V3StructuralState, float],
    ] = {
        truth: {
            predicted: math.fsum(contributions[truth][predicted])
            for predicted in V3_STRUCTURAL_STATES
        }
        for truth in V3_STRUCTURAL_STATES
    }
    return metrics_from_confusion(confusion)


def metrics_from_confusion(
    confusion: Mapping[
        V3StructuralState,
        Mapping[V3StructuralState, float],
    ],
) -> dict[str, Any]:
    """Validate and score one complete weighted confusion matrix."""

    if set(confusion) != set(V3_STRUCTURAL_STATES):
        raise V3MetricError("confusion truth axis must contain the exact five states")
    normalized: dict[V3StructuralState, dict[V3StructuralState, float]] = {}
    for truth in V3_STRUCTURAL_STATES:
        row = confusion[truth]
        if set(row) != set(V3_STRUCTURAL_STATES):
            raise V3MetricError("confusion prediction axis must contain the exact five states")
        normalized[truth] = {}
        for predicted in V3_STRUCTURAL_STATES:
            value = row[predicted]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0.0
            ):
                raise V3MetricError("confusion masses must be finite and non-negative")
            normalized[truth][predicted] = float(value)

    truth_mass = {
        truth: math.fsum(normalized[truth][predicted] for predicted in V3_STRUCTURAL_STATES)
        for truth in V3_STRUCTURAL_STATES
    }
    predicted_mass = {
        predicted: math.fsum(normalized[truth][predicted] for truth in V3_STRUCTURAL_STATES)
        for predicted in V3_STRUCTURAL_STATES
    }
    if any(value <= 0.0 for value in truth_mass.values()):
        raise V3MetricError("every state must have positive truth support")
    total_mass = math.fsum(truth_mass.values())
    per_state: dict[str, dict[str, float]] = {}
    recalls: list[float] = []
    f1_values: list[float] = []
    for state in V3_STRUCTURAL_STATES:
        true_positive = normalized[state][state]
        precision = true_positive / predicted_mass[state] if predicted_mass[state] > 0.0 else 0.0
        recall = true_positive / truth_mass[state]
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall > 0.0 else 0.0
        per_state[state] = {
            "truth_mass": truth_mass[state],
            "predicted_mass": predicted_mass[state],
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        recalls.append(recall)
        f1_values.append(f1)

    return {
        "states": list(V3_STRUCTURAL_STATES),
        "weighted_confusion_matrix": normalized,
        "total_family_mass": total_mass,
        "weighted_accuracy": (
            math.fsum(normalized[state][state] for state in V3_STRUCTURAL_STATES) / total_mass
        ),
        "balanced_accuracy": math.fsum(recalls) / len(V3_STRUCTURAL_STATES),
        "macro_f1": math.fsum(f1_values) / len(V3_STRUCTURAL_STATES),
        "worst_state_recall": min(recalls),
        "per_state": per_state,
    }


def add_confusion_matrices(
    matrices: Sequence[
        Mapping[
            V3StructuralState,
            Mapping[V3StructuralState, float],
        ]
    ],
) -> dict[V3StructuralState, dict[V3StructuralState, float]]:
    """Add complete matrices using stable summation."""

    if not matrices:
        raise V3MetricError("at least one confusion matrix is required")
    output: dict[V3StructuralState, dict[V3StructuralState, float]] = {}
    for truth in V3_STRUCTURAL_STATES:
        output[truth] = {}
        for predicted in V3_STRUCTURAL_STATES:
            values: list[float] = []
            for matrix in matrices:
                if set(matrix) != set(V3_STRUCTURAL_STATES):
                    raise V3MetricError("confusion truth axis must contain the exact five states")
                row = matrix[truth]
                if set(row) != set(V3_STRUCTURAL_STATES):
                    raise V3MetricError(
                        "confusion prediction axis must contain the exact five states"
                    )
                value = row[predicted]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0.0
                ):
                    raise V3MetricError("confusion masses must be finite and non-negative")
                values.append(float(value))
            output[truth][predicted] = math.fsum(values)
    return output


__all__ = [
    "V3MetricError",
    "WeightedStatePrediction",
    "add_confusion_matrices",
    "metrics_from_confusion",
    "weighted_state_metrics",
]
