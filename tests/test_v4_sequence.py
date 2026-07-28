from __future__ import annotations

import itertools
import math
import re
import unittest

from indusbench.v3dev.contracts import (
    V3_STRUCTURAL_STATES,
    V3ObservationLine,
    V3ObservationToken,
    V3StructuralState,
)
from indusbench.v4dev.contracts import (
    FeatureRow,
    V4FeatureLine,
    V4LabeledFeatureDocument,
    V4LabeledFeatureFamily,
    V4LabeledFeatureLine,
    V4ObservationCorpus,
    V4ObservationDocument,
)
from indusbench.v4dev.corpus_statistics import V4CorpusProfile
from indusbench.v4dev.sequence import (
    CLASS_ADJUSTMENT_GAMMA,
    CRF_L2_RHO,
    LBFGS_MIN_STEP,
    V4LinearChainCRF,
    V4LogisticEmissionModel,
    V4SequenceError,
    _lbfgs_minimize,
    _LBFGSSettings,
    _LogisticProblem,
    _prepare_problem,
)

_STATE_SUPPORT_CATEGORY = dict(
    zip(
        V3_STRUCTURAL_STATES,
        ("UNSEEN", "1", "2", "3-4", "5-8"),
        strict=True,
    )
)


def _row(category: str, numeric: float = 0.5) -> FeatureRow:
    return (
        ("type_support", category),
        ("type_frequency", numeric),
    )


def _line(
    states: tuple[V3StructuralState, ...],
    *,
    categories: tuple[str, ...] | None = None,
) -> V4LabeledFeatureLine:
    selected_categories = (
        tuple(_STATE_SUPPORT_CATEGORY[state] for state in states)
        if categories is None
        else categories
    )
    return V4LabeledFeatureLine(
        feature_line=V4FeatureLine(
            rows=tuple(
                _row(category, (index + 1) / (len(states) + 1))
                for index, category in enumerate(selected_categories)
            )
        ),
        states=states,
    )


def _family(
    states: tuple[V3StructuralState, ...],
    *,
    categories: tuple[str, ...] | None = None,
) -> V4LabeledFeatureFamily:
    return V4LabeledFeatureFamily(
        documents=(
            V4LabeledFeatureDocument(
                lines=(_line(states, categories=categories),),
            ),
        ),
    )


def _balanced_families() -> tuple[V4LabeledFeatureFamily, ...]:
    return tuple(_family((state,)) for state in V3_STRUCTURAL_STATES)


def _cycle_families() -> tuple[V4LabeledFeatureFamily, ...]:
    return tuple(
        _family(
            (
                state,
                V3_STRUCTURAL_STATES[(index + 1) % len(V3_STRUCTURAL_STATES)],
            ),
            categories=("1", "1"),
        )
        for index, state in enumerate(V3_STRUCTURAL_STATES)
    )


class V4CRFMathematicsTests(unittest.TestCase):
    def test_forward_partition_and_viterbi_equal_brute_force(self) -> None:
        model = V4LinearChainCRF.fit(_cycle_families())
        query = V4FeatureLine(rows=(_row("1", 0.25), _row("1", 0.75)))
        paths = tuple(itertools.product(V3_STRUCTURAL_STATES, repeat=len(query.rows)))

        for transition_zero in (False, True):
            scored = tuple(
                (
                    path,
                    model.sequence_score(
                        query,
                        path,
                        class_adjusted=True,
                        transition_zero=transition_zero,
                    ),
                )
                for path in paths
            )
            maximum = max(score for _, score in scored)
            expected_partition = maximum + math.log(
                math.fsum(math.exp(score - maximum) for _, score in scored)
            )
            expected_path = max(scored, key=lambda item: item[1])[0]

            self.assertAlmostEqual(
                model.log_partition(
                    query,
                    class_adjusted=True,
                    transition_zero=transition_zero,
                ),
                expected_partition,
                places=11,
            )
            self.assertEqual(
                model.decode(query, transition_zero=transition_zero),
                expected_path,
            )
        self.assertAlmostEqual(
            model.log_partition(query),
            model.log_partition(query, class_adjusted=True),
        )

    def test_analytic_gradient_matches_central_finite_difference(self) -> None:
        _, problem, _ = _prepare_problem(_cycle_families())
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

    def test_logistic_analytic_gradient_matches_finite_difference(self) -> None:
        _, crf_problem, _ = _prepare_problem(_cycle_families())
        problem = _LogisticProblem(
            crf_problem.examples,
            crf_problem.layout,
        )
        parameters = tuple(
            0.02 * math.cos(index + 1) for index in range(problem.layout.parameter_count)
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

    def test_family_normalized_prior_and_posthoc_adjustment(self) -> None:
        families = (
            _family(("context_only",) * 10, categories=("2",) * 10),
            _family(
                ("quantity", "unit", "person_name", "settlement_name"),
                categories=("3-4",) * 4,
            ),
        )
        model = V4LinearChainCRF.fit(families)
        priors = dict(zip(V3_STRUCTURAL_STATES, model.class_priors, strict=True))
        self.assertAlmostEqual(priors["context_only"], 1.5 / 4.5)
        for state in V3_STRUCTURAL_STATES[1:]:
            self.assertAlmostEqual(priors[state], 0.75 / 4.5)

        query = V4FeatureLine(rows=(_row("UNSEEN"),))
        raw = model.emission_scores(query, class_adjusted=False)[0]
        adjusted = model.emission_scores(query, class_adjusted=True)[0]
        for index, state in enumerate(V3_STRUCTURAL_STATES):
            self.assertAlmostEqual(
                adjusted[index] - raw[index],
                -CLASS_ADJUSTMENT_GAMMA * math.log(priors[state]),
            )

        _, problem, _ = _prepare_problem(families)
        self.assertEqual(
            sorted(example.objective_weight for example in problem.examples),
            [1.0 / 20.0, 1.0 / 8.0],
        )
        self.assertAlmostEqual(
            math.fsum(example.objective_weight * len(example.rows) for example in problem.examples),
            1.0,
        )


class V4CRFOptimizationTests(unittest.TestCase):
    def test_actual_profile_feature_surface_is_accepted(self) -> None:
        corpus = V4ObservationCorpus(
            documents=tuple(
                V4ObservationDocument(
                    lines=(
                        V3ObservationLine(
                            line_ordinal=0,
                            reported_direction=(
                                "known_source_order"
                                if document_index % 2 == 0
                                else "unknown_visual_order"
                            ),
                            tokens=tuple(
                                V3ObservationToken(
                                    observation_id=(
                                        None
                                        if token_index == 2 and document_index == 0
                                        else f"type-{(document_index + token_index) % 4}"
                                    ),
                                    damaged=token_index == 2 and document_index == 0,
                                )
                                for token_index in range(5)
                            ),
                        ),
                    )
                )
                for document_index in range(5)
            )
        )
        features = V4CorpusProfile.fit(corpus).transform_corpus(corpus)
        families = tuple(
            V4LabeledFeatureFamily(
                documents=(
                    V4LabeledFeatureDocument(
                        lines=(
                            V4LabeledFeatureLine(
                                feature_line=document.lines[0],
                                states=V3_STRUCTURAL_STATES,
                            ),
                        ),
                    ),
                )
            )
            for document in features.documents
        )

        model = V4LinearChainCRF.fit(families)

        self.assertGreater(model.feature_count, 24)
        self.assertIsNotNone(
            re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                model.model_state_commitment(),
            )
        )

    def test_fit_is_deterministic_and_receipt_is_complete(self) -> None:
        first = V4LinearChainCRF.fit(_cycle_families())
        second = V4LinearChainCRF.fit(_cycle_families())
        reversed_input = V4LinearChainCRF.fit(tuple(reversed(_cycle_families())))

        self.assertEqual(first.model_state_commitment(), second.model_state_commitment())
        self.assertEqual(
            first.model_state_commitment(),
            reversed_input.model_state_commitment(),
        )
        self.assertEqual(first.optimization_summary(), second.optimization_summary())
        self.assertIn(
            first.termination_reason,
            {"gradient_infinity_norm", "relative_objective_stability"},
        )
        self.assertEqual(
            set(first.optimization_summary()),
            {
                "converged",
                "accepted_iterations",
                "termination_reason",
                "final_objective",
                "final_gradient_infinity_norm",
            },
        )
        self.assertIs(first.optimization_summary()["converged"], True)
        self.assertGreater(first.training_iterations, 0)
        self.assertGreaterEqual(first.training_gradient_infinity_norm, 0.0)
        self.assertEqual(CRF_L2_RHO, 0.01)
        self.assertIsNone(re.fullmatch(r"(?!sha256:)[0-9a-f]{64}", first.model_state_commitment()))
        self.assertIsNotNone(re.fullmatch(r"sha256:[0-9a-f]{64}", first.model_state_commitment()))
        self.assertFalse(hasattr(first, "__dict__"))

    def test_family_document_and_line_container_order_is_canonical(self) -> None:
        first_line = _line(
            ("context_only", "quantity"),
            categories=("1", "2"),
        )
        second_line = _line(
            ("unit", "person_name", "settlement_name"),
            categories=("3-4", "5-8", "9-16"),
        )
        forward_family = V4LabeledFeatureFamily(
            documents=(
                V4LabeledFeatureDocument(lines=(first_line,)),
                V4LabeledFeatureDocument(lines=(second_line,)),
            )
        )
        reversed_family = V4LabeledFeatureFamily(
            documents=(
                V4LabeledFeatureDocument(lines=(second_line,)),
                V4LabeledFeatureDocument(lines=(first_line,)),
            )
        )

        forward = V4LinearChainCRF.fit((forward_family, *_balanced_families()))
        reversed_model = V4LinearChainCRF.fit(
            tuple(reversed((reversed_family, *_balanced_families())))
        )

        self.assertEqual(
            forward.model_state_commitment(),
            reversed_model.model_state_commitment(),
        )

    def test_nonconvergence_and_line_search_failure_fail_closed(self) -> None:
        def quadratic(
            parameters: tuple[float, ...],
        ) -> tuple[float, tuple[float, ...]]:
            difference = parameters[0] - 3.0
            return difference * difference, (2.0 * difference,)

        with self.assertRaisesRegex(V4SequenceError, "did not converge"):
            _lbfgs_minimize(
                quadratic,
                (0.0,),
                settings=_LBFGSSettings(max_iterations=0),
            )

        def inconsistent(
            parameters: tuple[float, ...],
        ) -> tuple[float, tuple[float, ...]]:
            del parameters
            return 0.0, (1.0,)

        with self.assertRaisesRegex(V4SequenceError, "line search failed"):
            _lbfgs_minimize(inconsistent, (0.0,))

        def nonfinite_after_initial(
            parameters: tuple[float, ...],
        ) -> tuple[float, tuple[float, ...]]:
            if parameters == (0.0,):
                return 0.0, (1.0,)
            return math.inf, (1.0,)

        with self.assertRaisesRegex(V4SequenceError, "objective must be finite"):
            _lbfgs_minimize(nonfinite_after_initial, (0.0,))

        def accepts_only_minimum_step(
            parameters: tuple[float, ...],
        ) -> tuple[float, tuple[float, ...]]:
            if parameters == (0.0,):
                return 0.0, (1.0,)
            if abs(parameters[0]) <= LBFGS_MIN_STEP:
                return parameters[0], (0.0,)
            return 0.0, (1.0,)

        minimum_step_result = _lbfgs_minimize(
            accepts_only_minimum_step,
            (0.0,),
        )
        self.assertEqual(minimum_step_result.parameters, (-LBFGS_MIN_STEP,))
        self.assertEqual(
            minimum_step_result.termination_reason,
            "gradient_infinity_norm",
        )

    def test_exact_identifier_categories_are_rejected(self) -> None:
        for identifier in (
            "sha256:" + "a" * 64,
            "mtaac-word-form-sha256-v1:" + "b" * 64,
            "A" * 64,
            "c" * 40,
            "P123456",
            "/private/raw/member.json",
            "raw-lexical-value",
        ):
            families = tuple(
                _family((state,), categories=(identifier,)) for state in V3_STRUCTURAL_STATES
            )
            with (
                self.subTest(identifier=identifier),
                self.assertRaisesRegex(V4SequenceError, "identifiers|surface"),
            ):
                V4LinearChainCRF.fit(families)

    def test_logistic_diagnostic_is_independent_and_deterministic(self) -> None:
        first = V4LogisticEmissionModel.fit(_balanced_families())
        second = V4LogisticEmissionModel.fit(_balanced_families())
        query = V4FeatureLine(rows=(_row("UNSEEN"), _row("5-8")))

        self.assertEqual(first.decode(query), second.decode(query))
        self.assertEqual(first.model_state_commitment(), second.model_state_commitment())
        self.assertIsNotNone(re.fullmatch(r"sha256:[0-9a-f]{64}", first.model_state_commitment()))
        self.assertIn(
            first.termination_reason,
            {"gradient_infinity_norm", "relative_objective_stability"},
        )


if __name__ == "__main__":
    unittest.main()
