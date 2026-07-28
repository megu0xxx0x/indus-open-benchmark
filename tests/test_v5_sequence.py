from __future__ import annotations

import inspect
import math
import re
import unittest
from unittest.mock import patch

from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES, V3StructuralState
from indusbench.v4dev.contracts import (
    FeatureRow,
    V4FeatureLine,
    V4LabeledFeatureDocument,
    V4LabeledFeatureFamily,
    V4LabeledFeatureLine,
)
from indusbench.v4dev.sequence import (
    CLASS_ADJUSTMENT_GAMMA as V4_CLASS_ADJUSTMENT_GAMMA,
)
from indusbench.v4dev.sequence import (
    CRF_L2_RHO as V4_CRF_L2_RHO,
)
from indusbench.v4dev.sequence import (
    JEFFREYS_ALPHA as V4_JEFFREYS_ALPHA,
)
from indusbench.v4dev.sequence import (
    V4LinearChainCRF,
    _lbfgs_minimize,
    _ParameterLayout,
    _prepare_problem,
)
from indusbench.v5dev.sequence import (
    CLASS_ADJUSTMENT_GAMMA,
    CRF_L2_RHO,
    EMISSION_CONTRAST_MULTIPLIER,
    JEFFREYS_ALPHA,
    V5_CRF_MODEL_VERSION,
    V5GroupContrastLinearChainCRF,
    _evaluate_group_contrast_objective,
    _group_contrast_regularizer,
    _V5CRFProblem,
)

_STATE_CATEGORIES = dict(
    zip(
        V3_STRUCTURAL_STATES,
        ("UNSEEN", "1", "2", "3-4", "5-8"),
        strict=True,
    )
)


def _row(category: str, numeric: float) -> FeatureRow:
    return (
        ("type_support", category),
        ("type_frequency", numeric),
    )


def _family(states: tuple[V3StructuralState, ...]) -> V4LabeledFeatureFamily:
    return V4LabeledFeatureFamily(
        documents=(
            V4LabeledFeatureDocument(
                lines=(
                    V4LabeledFeatureLine(
                        feature_line=V4FeatureLine(
                            rows=tuple(
                                _row(
                                    _STATE_CATEGORIES[state],
                                    (index + 1) / (len(states) + 1),
                                )
                                for index, state in enumerate(states)
                            )
                        ),
                        states=states,
                    ),
                ),
            ),
        ),
    )


def _cycle_families() -> tuple[V4LabeledFeatureFamily, ...]:
    return tuple(
        _family(
            (
                state,
                V3_STRUCTURAL_STATES[(index + 1) % len(V3_STRUCTURAL_STATES)],
            )
        )
        for index, state in enumerate(V3_STRUCTURAL_STATES)
    )


class V5GroupContrastMathematicsTests(unittest.TestCase):
    def test_exact_regularizer_and_gradient_math(self) -> None:
        layout = _ParameterLayout(feature_count=2)
        parameters = tuple(
            (index - layout.parameter_count / 2.0) / 7.0 for index in range(layout.parameter_count)
        )
        penalty, gradient = _group_contrast_regularizer(
            parameters,
            layout,
            contrast_multiplier=2.0,
        )

        paired_states = ((1, 2), (3, 4))
        paired_indices: set[int] = set()
        expected_terms: list[float] = []
        expected_gradient = [0.0] * layout.parameter_count
        for first_state, second_state in paired_states:
            pairs = [
                *(
                    (
                        layout.emission_index(first_state, feature_index),
                        layout.emission_index(second_state, feature_index),
                    )
                    for feature_index in range(layout.feature_count)
                ),
                (
                    layout.bias_index(first_state),
                    layout.bias_index(second_state),
                ),
            ]
            for first_index, second_index in pairs:
                paired_indices.update((first_index, second_index))
                first = parameters[first_index]
                second = parameters[second_index]
                mean = (first + second) / 2.0
                contrast = (first - second) / 2.0
                expected_terms.append(CRF_L2_RHO * (mean * mean + 2.0 * contrast * contrast))
                expected_gradient[first_index] = CRF_L2_RHO * (mean + 2.0 * contrast)
                expected_gradient[second_index] = CRF_L2_RHO * (mean - 2.0 * contrast)

        for index, value in enumerate(parameters):
            if index not in paired_indices:
                expected_terms.append(0.5 * CRF_L2_RHO * value * value)
                expected_gradient[index] = CRF_L2_RHO * value

        self.assertAlmostEqual(penalty, math.fsum(expected_terms), places=15)
        for observed, expected in zip(gradient, expected_gradient, strict=True):
            self.assertAlmostEqual(observed, expected, places=15)

    def test_analytic_gradient_matches_central_finite_difference(self) -> None:
        _, base_problem, _ = _prepare_problem(_cycle_families())
        problem = _V5CRFProblem(base_problem)
        parameters = tuple(
            0.03 * math.sin(index + 1) for index in range(problem.layout.parameter_count)
        )
        _, analytic = problem.evaluate(parameters)
        epsilon = 1e-6
        relative_errors: list[float] = []
        for index, expected in enumerate(analytic):
            upper = list(parameters)
            lower = list(parameters)
            upper[index] += epsilon
            lower[index] -= epsilon
            upper_value, _ = problem.evaluate(tuple(upper))
            lower_value, _ = problem.evaluate(tuple(lower))
            numerical = (upper_value - lower_value) / (2.0 * epsilon)
            relative_errors.append(
                abs(numerical - expected) / max(1.0, abs(numerical), abs(expected))
            )

        self.assertLessEqual(max(relative_errors), 1e-5)

    def test_multiplier_one_is_v4_objective_gradient_and_decode(self) -> None:
        encoder, base_problem, priors = _prepare_problem(_cycle_families())
        parameters = tuple(
            0.02 * math.cos(index + 1) for index in range(base_problem.layout.parameter_count)
        )
        v4_objective, v4_gradient = base_problem.evaluate(parameters)
        equivalent_objective, equivalent_gradient = _evaluate_group_contrast_objective(
            base_problem,
            parameters,
            contrast_multiplier=1.0,
        )
        self.assertAlmostEqual(equivalent_objective, v4_objective, places=14)
        for observed, expected in zip(
            equivalent_gradient,
            v4_gradient,
            strict=True,
        ):
            self.assertAlmostEqual(observed, expected, places=14)

        gradient_norm = max(abs(value) for value in v4_gradient)
        common = {
            "encoder": encoder,
            "parameters": parameters,
            "class_priors": priors,
            "training_iterations": 0,
            "training_gradient_infinity_norm": gradient_norm,
            "termination_reason": "gradient_infinity_norm",
            "objective": v4_objective,
        }
        v4_model = V4LinearChainCRF(**common)
        v5_model = V5GroupContrastLinearChainCRF(**common)
        query = V4FeatureLine(
            rows=(
                _row("1", 0.2),
                _row("3-4", 0.5),
                _row("5-8", 0.8),
            )
        )
        self.assertEqual(v5_model.decode(query), v4_model.decode(query))
        self.assertEqual(
            v5_model.decode(query, transition_zero=True),
            v4_model.decode(query, transition_zero=True),
        )


class V5GroupContrastContractTests(unittest.TestCase):
    def test_fixed_contract_has_no_tuning_surface_and_same_capacity(self) -> None:
        self.assertEqual(EMISSION_CONTRAST_MULTIPLIER, 2.0)
        self.assertEqual(CRF_L2_RHO, V4_CRF_L2_RHO)
        self.assertEqual(CRF_L2_RHO, 0.01)
        self.assertEqual(CLASS_ADJUSTMENT_GAMMA, V4_CLASS_ADJUSTMENT_GAMMA)
        self.assertEqual(CLASS_ADJUSTMENT_GAMMA, 0.5)
        self.assertEqual(JEFFREYS_ALPHA, V4_JEFFREYS_ALPHA)
        self.assertEqual(JEFFREYS_ALPHA, 0.5)
        self.assertEqual(
            tuple(inspect.signature(V5GroupContrastLinearChainCRF.fit).parameters),
            ("families",),
        )

        v5 = V5GroupContrastLinearChainCRF.fit(_cycle_families())
        v4 = V4LinearChainCRF.fit(_cycle_families())
        expected_parameter_count = (
            len(V3_STRUCTURAL_STATES) * v5.feature_count
            + len(V3_STRUCTURAL_STATES)
            + len(V3_STRUCTURAL_STATES)
            + len(V3_STRUCTURAL_STATES) ** 2
        )
        self.assertEqual(v5.feature_count, v4.feature_count)
        self.assertEqual(v5.parameter_count, expected_parameter_count)
        self.assertNotIn(
            "contrast_multiplier",
            inspect.signature(V5GroupContrastLinearChainCRF.fit).parameters,
        )

    def test_fit_uses_exact_zero_initialization_and_frozen_optimizer(self) -> None:
        with patch(
            "indusbench.v5dev.sequence._lbfgs_minimize",
            wraps=_lbfgs_minimize,
        ) as optimizer:
            V5GroupContrastLinearChainCRF.fit(_cycle_families())

        self.assertEqual(optimizer.call_count, 1)
        initial = optimizer.call_args.args[1]
        self.assertTrue(initial)
        self.assertTrue(all(value == 0.0 for value in initial))
        self.assertEqual(optimizer.call_args.kwargs, {})

    def test_fit_is_deterministic_and_commitment_is_distinct(self) -> None:
        first = V5GroupContrastLinearChainCRF.fit(_cycle_families())
        second = V5GroupContrastLinearChainCRF.fit(_cycle_families())
        reversed_input = V5GroupContrastLinearChainCRF.fit(tuple(reversed(_cycle_families())))
        v4 = V4LinearChainCRF.fit(_cycle_families())

        self.assertEqual(first.model_state_commitment(), second.model_state_commitment())
        self.assertEqual(
            first.model_state_commitment(),
            reversed_input.model_state_commitment(),
        )
        self.assertNotEqual(first.model_state_commitment(), v4.model_state_commitment())
        self.assertIsNotNone(re.fullmatch(r"sha256:[0-9a-f]{64}", first.model_state_commitment()))
        self.assertIn(V5_CRF_MODEL_VERSION, repr(first))
        self.assertFalse(hasattr(first, "__dict__"))


if __name__ == "__main__":
    unittest.main()
