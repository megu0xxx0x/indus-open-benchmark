"""Fixed group-contrast CRF for the final V5 MTAAC development attempt.

V5 deliberately reuses the immutable V4 likelihood, feature encoder, class
adjustment, parameter layout, and deterministic optimizer.  Its only model
change is a fixed multiplier of ``2`` on the within-pair emission contrasts for
``quantity``/``unit`` and ``person_name``/``settlement_name``.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Sequence
from typing import Final, Self

from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES
from indusbench.v4dev.contracts import V4LabeledFeatureFamily
from indusbench.v4dev.sequence import (
    CLASS_ADJUSTMENT_GAMMA,
    CRF_L2_RHO,
    JEFFREYS_ALPHA,
    V4LinearChainCRF,
    _CRFProblem,
    _lbfgs_minimize,
    _ParameterLayout,
    _prepare_problem,
)

V5_CRF_MODEL_VERSION: Final = "v5-fixed-group-contrast-linear-chain-crf-v1"
EMISSION_CONTRAST_MULTIPLIER: Final = 2.0

_MODEL_COMMITMENT_DOMAIN: Final = (
    b"indusbench:v5:fixed-group-contrast-linear-chain-crf:model-state:v1\x00"
)
_PAIRED_STATE_INDICES: Final = (
    (
        V3_STRUCTURAL_STATES.index("quantity"),
        V3_STRUCTURAL_STATES.index("unit"),
    ),
    (
        V3_STRUCTURAL_STATES.index("person_name"),
        V3_STRUCTURAL_STATES.index("settlement_name"),
    ),
)
_CONTEXT_STATE_INDEX: Final = V3_STRUCTURAL_STATES.index("context_only")


def _group_contrast_regularizer(
    parameters: tuple[float, ...],
    layout: _ParameterLayout,
    *,
    contrast_multiplier: float,
) -> tuple[float, tuple[float, ...]]:
    """Return the exact V5 regularizer and analytic gradient.

    ``contrast_multiplier`` is private mathematical test support.  The
    production objective below always supplies
    :data:`EMISSION_CONTRAST_MULTIPLIER`;
    ``1`` exists only to prove equivalence with the immutable V4 L2 objective.
    """

    if len(parameters) != layout.parameter_count:
        raise ValueError("group-contrast parameter vector has the wrong length")
    if layout.state_count != len(V3_STRUCTURAL_STATES):
        raise ValueError("group-contrast layout must contain the fixed five states")
    if any(not math.isfinite(value) for value in parameters):
        raise ValueError("group-contrast parameters must be finite")
    if not math.isfinite(contrast_multiplier) or contrast_multiplier <= 0.0:
        raise ValueError("contrast multiplier must be finite and positive")

    gradient = [0.0] * layout.parameter_count
    penalty_terms: list[float] = []

    ordinary_indices = [
        *(
            layout.emission_index(_CONTEXT_STATE_INDEX, feature_index)
            for feature_index in range(layout.feature_count)
        ),
        layout.bias_index(_CONTEXT_STATE_INDEX),
        *(layout.start_index(state_index) for state_index in range(layout.state_count)),
        *(
            layout.transition_index(previous_index, current_index)
            for previous_index in range(layout.state_count)
            for current_index in range(layout.state_count)
        ),
    ]
    for index in ordinary_indices:
        value = parameters[index]
        penalty_terms.append(0.5 * CRF_L2_RHO * value * value)
        gradient[index] = CRF_L2_RHO * value

    for first_state, second_state in _PAIRED_STATE_INDICES:
        paired_indices = [
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
        for first_index, second_index in paired_indices:
            first_value = parameters[first_index]
            second_value = parameters[second_index]
            mean = 0.5 * (first_value + second_value)
            contrast = 0.5 * (first_value - second_value)
            penalty_terms.append(
                CRF_L2_RHO * (mean * mean + contrast_multiplier * contrast * contrast)
            )
            gradient[first_index] = CRF_L2_RHO * (mean + contrast_multiplier * contrast)
            gradient[second_index] = CRF_L2_RHO * (mean - contrast_multiplier * contrast)

    penalty = math.fsum(penalty_terms)
    if not math.isfinite(penalty) or any(not math.isfinite(value) for value in gradient):
        raise ValueError("group-contrast regularizer produced a non-finite value")
    return penalty, tuple(gradient)


def _evaluate_group_contrast_objective(
    base_problem: _CRFProblem,
    parameters: tuple[float, ...],
    *,
    contrast_multiplier: float,
) -> tuple[float, tuple[float, ...]]:
    """Replace only V4's ordinary L2 term with the group-contrast penalty."""

    base_objective, base_gradient = base_problem.evaluate(parameters)
    regularizer, regularizer_gradient = _group_contrast_regularizer(
        parameters,
        base_problem.layout,
        contrast_multiplier=contrast_multiplier,
    )
    v4_regularizer = 0.5 * CRF_L2_RHO * math.fsum(value * value for value in parameters)
    objective = base_objective - v4_regularizer + regularizer
    gradient = tuple(
        base_value - CRF_L2_RHO * parameter + replacement
        for base_value, parameter, replacement in zip(
            base_gradient,
            parameters,
            regularizer_gradient,
            strict=True,
        )
    )
    if not math.isfinite(objective) or any(not math.isfinite(value) for value in gradient):
        raise ValueError("group-contrast objective produced a non-finite value")
    return objective, gradient


class _V5CRFProblem:
    """The single fixed V5 objective; no contrast-weight choice is exposed."""

    __slots__ = ("base_problem", "layout")

    def __init__(self, base_problem: _CRFProblem) -> None:
        if not math.isclose(
            base_problem.rho,
            CRF_L2_RHO,
            rel_tol=0.0,
            abs_tol=0.0,
        ):
            raise ValueError("V5 requires the frozen V4 L2 coefficient")
        self.base_problem = base_problem
        self.layout = base_problem.layout

    def evaluate(
        self,
        parameters: tuple[float, ...],
    ) -> tuple[float, tuple[float, ...]]:
        return _evaluate_group_contrast_objective(
            self.base_problem,
            parameters,
            contrast_multiplier=EMISSION_CONTRAST_MULTIPLIER,
        )


class V5GroupContrastLinearChainCRF(V4LinearChainCRF):
    """The one fixed V5 candidate with paired emission contrast shrinkage."""

    __slots__ = ()

    def __repr__(self) -> str:
        return (
            "V5GroupContrastLinearChainCRF("
            f"version={V5_CRF_MODEL_VERSION!r}, "
            f"feature_count={self.feature_count}, "
            f"training_iterations={self.training_iterations})"
        )

    @classmethod
    def fit(cls, families: Sequence[V4LabeledFeatureFamily]) -> Self:
        """Fit the fixed contrast-multiplier-2 candidate from an exact zero vector."""

        encoder, v4_problem, class_priors = _prepare_problem(families)
        problem = _V5CRFProblem(v4_problem)
        initial = (0.0,) * problem.layout.parameter_count
        result = _lbfgs_minimize(problem.evaluate, initial)
        return cls(
            encoder=encoder,
            parameters=result.parameters,
            class_priors=class_priors,
            training_iterations=result.accepted_iterations,
            training_gradient_infinity_norm=result.gradient_infinity_norm,
            termination_reason=result.termination_reason,
            objective=result.objective,
        )

    @property
    def parameter_count(self) -> int:
        """Return the unchanged five-state V4 parameter count."""

        return self._layout.parameter_count

    def model_state_commitment(self) -> str:
        """Commit the complete model under a V5-specific domain and contract."""

        digest = hashlib.sha256(_MODEL_COMMITMENT_DOMAIN)

        def update_frame(value: bytes) -> None:
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)

        for value in (
            V5_CRF_MODEL_VERSION,
            f"rho={CRF_L2_RHO:.17g}",
            f"gamma={CLASS_ADJUSTMENT_GAMMA:.17g}",
            f"jeffreys={JEFFREYS_ALPHA:.17g}",
            f"emission_contrast_multiplier={EMISSION_CONTRAST_MULTIPLIER:.17g}",
            "quantity/unit",
            "person_name/settlement_name",
        ):
            update_frame(value.encode("ascii"))
        for state in V3_STRUCTURAL_STATES:
            update_frame(state.encode("ascii"))
        for spec in self._encoder.specs:
            update_frame(spec.kind.encode("ascii"))
            update_frame(spec.name.encode("utf-8"))
            if spec.category is None:
                digest.update(b"\x00")
            else:
                digest.update(b"\x01")
                update_frame(spec.category.encode("utf-8"))
        for value in (*self._class_priors, *self._parameters):
            digest.update(struct.pack(">d", value))
        return f"sha256:{digest.hexdigest()}"


__all__ = [
    "CLASS_ADJUSTMENT_GAMMA",
    "CRF_L2_RHO",
    "EMISSION_CONTRAST_MULTIPLIER",
    "JEFFREYS_ALPHA",
    "V5_CRF_MODEL_VERSION",
    "V5GroupContrastLinearChainCRF",
]
