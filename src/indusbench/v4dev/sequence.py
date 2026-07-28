"""Deterministic, dependency-free linear-chain CRF for V4 development.

The model consumes only the ID-free feature contracts in :mod:`v4dev.contracts`.
It has one frozen regularization/class-adjustment configuration and therefore
does not expose a development-time hyperparameter search surface.
"""

from __future__ import annotations

import hashlib
import math
import re
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final, Literal, Self, cast

from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES, V3StructuralState
from indusbench.v4dev.contracts import (
    FeatureRow,
    V4FeatureLine,
    V4LabeledFeatureFamily,
    V4LabeledFeatureLine,
)
from indusbench.v4dev.corpus_statistics import (
    LOCAL_FEATURE_NAMES,
    PROFILE_FEATURE_NAMES,
)

V4_CRF_MODEL_VERSION: Final = "v4-distributional-linear-chain-crf-v1"
V4_LOGISTIC_MODEL_VERSION: Final = "v4-logistic-emission-diagnostic-v1"
CRF_L2_RHO: Final = 0.01
CLASS_ADJUSTMENT_GAMMA: Final = 0.5
JEFFREYS_ALPHA: Final = 0.5

LBFGS_HISTORY_SIZE: Final = 10
LBFGS_MAX_ITERATIONS: Final = 100
LBFGS_ARMIJO_C1: Final = 1e-4
LBFGS_BACKTRACK_FACTOR: Final = 0.5
LBFGS_MAX_LINE_SEARCH_TRIALS: Final = 31
LBFGS_MIN_STEP: Final = 2.0**-30
LBFGS_CURVATURE_RELATIVE_MINIMUM: Final = 1e-12
LBFGS_GRADIENT_TOLERANCE: Final = 1e-5
LBFGS_STALLED_GRADIENT_TOLERANCE: Final = 1e-3
LBFGS_RELATIVE_OBJECTIVE_TOLERANCE: Final = 1e-9
LBFGS_STABLE_ITERATIONS: Final = 5

_MODEL_COMMITMENT_DOMAIN = b"indusbench:v4:linear-chain-crf:model-state:v1\x00"
_LOGISTIC_COMMITMENT_DOMAIN = b"indusbench:v4:logistic-emission:model-state:v1\x00"
_TAGGED_DIGEST = re.compile(r"sha256:[0-9a-f]{64}", re.ASCII | re.IGNORECASE)
_BARE_DIGEST = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}", re.ASCII | re.IGNORECASE)
_PREFIXED_DIGEST = re.compile(
    r"[^:\s]+:(?:[0-9a-f]{40}|[0-9a-f]{64})",
    re.ASCII | re.IGNORECASE,
)
_STATE_TO_INDEX = {state: index for index, state in enumerate(V3_STRUCTURAL_STATES)}

_LOCAL_CATEGORIES: Final = {
    "position_bucket": frozenset({"singleton", "initial", "final", "medial"}),
    "line_length_bucket": frozenset({"1", "2", "3", "4", "5", "6", "7", "8_plus"}),
    "reported_direction": frozenset({"known", "unknown"}),
    "damage": frozenset({"damaged", "clear"}),
    "observation_status": frozenset({"missing", "observed"}),
    "previous_equality": frozenset(
        {"BOS", "current_missing", "neighbor_missing", "same", "different"}
    ),
    "next_equality": frozenset({"EOS", "current_missing", "neighbor_missing", "same", "different"}),
    "line_frequency_bucket": frozenset({"missing", "once", "twice", "three_plus"}),
    "seen_before": frozenset({"missing", "yes", "no"}),
    "seen_after": frozenset({"missing", "yes", "no"}),
}
_PROFILE_SENTINELS: Final = frozenset({"UNSEEN", "DAMAGED_NEUTRAL"})
_PROFILE_CATEGORIES: Final = {
    name: (
        _PROFILE_SENTINELS
        | (
            frozenset({"1", "2", "3-4", "5-8", "9-16", "17+"})
            if name == "type_support"
            else frozenset()
        )
        | (
            frozenset({"BOS", "EOS", "DAMAGED"})
            if name in {"left_neighbor_commonness", "right_neighbor_commonness"}
            else frozenset()
        )
    )
    for name in PROFILE_FEATURE_NAMES
}
_CATEGORICAL_VALUES: Final = {**_LOCAL_CATEGORIES, **_PROFILE_CATEGORIES}
_NUMERIC_FEATURE_NAMES: Final = frozenset(PROFILE_FEATURE_NAMES) - {"type_support"}
_CLOSED_FEATURE_NAMES: Final = frozenset(LOCAL_FEATURE_NAMES + PROFILE_FEATURE_NAMES)


class V4SequenceError(ValueError):
    """Raised when V4 model fitting or decoding violates the frozen contract."""


SparseFeatureRow = tuple[tuple[int, float], ...]
ObjectiveFunction = Callable[
    [tuple[float, ...]],
    tuple[float, tuple[float, ...]],
]
OptimizationTerminationReason = Literal[
    "gradient_infinity_norm",
    "relative_objective_stability",
]


@dataclass(frozen=True, slots=True)
class _FeatureSpec:
    name: str
    category: str | None

    @property
    def kind(self) -> str:
        return "numeric" if self.category is None else "categorical"


class _FeatureEncoder:
    """A deterministic mixed numeric/categorical sparse encoder."""

    __slots__ = ("_categorical_indices", "_numeric_indices", "specs")

    def __init__(self, specs: tuple[_FeatureSpec, ...]) -> None:
        self.specs = specs
        self._numeric_indices = {
            spec.name: index for index, spec in enumerate(specs) if spec.category is None
        }
        self._categorical_indices = {
            (spec.name, cast(str, spec.category)): index
            for index, spec in enumerate(specs)
            if spec.category is not None
        }

    @classmethod
    def fit(cls, rows: Sequence[FeatureRow]) -> Self:
        if not rows:
            raise V4SequenceError("at least one feature row is required")
        specs: set[_FeatureSpec] = set()
        for row in rows:
            _validate_feature_row(row)
            for name, value in row:
                if isinstance(value, str):
                    specs.add(_FeatureSpec(name=name, category=value))
                else:
                    specs.add(_FeatureSpec(name=name, category=None))
        ordered = tuple(
            sorted(
                specs,
                key=lambda spec: (
                    spec.name,
                    0 if spec.category is None else 1,
                    "" if spec.category is None else spec.category,
                ),
            )
        )
        if not ordered:
            raise V4SequenceError("feature vocabulary may not be empty")
        return cls(ordered)

    def transform_row(self, row: FeatureRow) -> SparseFeatureRow:
        _validate_feature_row(row)
        encoded: list[tuple[int, float]] = []
        for name, value in row:
            if isinstance(value, str):
                index = self._categorical_indices.get((name, value))
                if index is not None:
                    encoded.append((index, 1.0))
            else:
                index = self._numeric_indices.get(name)
                if index is not None:
                    encoded.append((index, float(value)))
        return tuple(sorted(encoded))

    def transform_line(self, line: V4FeatureLine) -> tuple[SparseFeatureRow, ...]:
        if not isinstance(line, V4FeatureLine):
            raise V4SequenceError("decoding requires a V4 feature line")
        return tuple(self.transform_row(row) for row in line.rows)


@dataclass(frozen=True, slots=True)
class _ParameterLayout:
    feature_count: int
    state_count: int = len(V3_STRUCTURAL_STATES)

    @property
    def emission_size(self) -> int:
        return self.state_count * self.feature_count

    @property
    def bias_offset(self) -> int:
        return self.emission_size

    @property
    def start_offset(self) -> int:
        return self.bias_offset + self.state_count

    @property
    def transition_offset(self) -> int:
        return self.start_offset + self.state_count

    @property
    def parameter_count(self) -> int:
        return self.transition_offset + self.state_count * self.state_count

    def emission_index(self, state_index: int, feature_index: int) -> int:
        return state_index * self.feature_count + feature_index

    def bias_index(self, state_index: int) -> int:
        return self.bias_offset + state_index

    def start_index(self, state_index: int) -> int:
        return self.start_offset + state_index

    def transition_index(self, previous_index: int, current_index: int) -> int:
        return self.transition_offset + previous_index * self.state_count + current_index


@dataclass(frozen=True, slots=True)
class _TrainingLine:
    rows: tuple[SparseFeatureRow, ...]
    states: tuple[int, ...]
    objective_weight: float


@dataclass(frozen=True, slots=True)
class _LBFGSSettings:
    history_size: int = LBFGS_HISTORY_SIZE
    max_iterations: int = LBFGS_MAX_ITERATIONS
    armijo_c1: float = LBFGS_ARMIJO_C1
    backtrack_factor: float = LBFGS_BACKTRACK_FACTOR
    max_line_search_trials: int = LBFGS_MAX_LINE_SEARCH_TRIALS
    min_step: float = LBFGS_MIN_STEP
    curvature_relative_minimum: float = LBFGS_CURVATURE_RELATIVE_MINIMUM
    gradient_tolerance: float = LBFGS_GRADIENT_TOLERANCE
    stalled_gradient_tolerance: float = LBFGS_STALLED_GRADIENT_TOLERANCE
    relative_objective_tolerance: float = LBFGS_RELATIVE_OBJECTIVE_TOLERANCE
    stable_iterations: int = LBFGS_STABLE_ITERATIONS


@dataclass(frozen=True, slots=True)
class _LBFGSResult:
    parameters: tuple[float, ...]
    objective: float
    gradient_infinity_norm: float
    accepted_iterations: int
    termination_reason: OptimizationTerminationReason


_DEFAULT_LBFGS_SETTINGS = _LBFGSSettings()


class _CRFProblem:
    """Frozen weighted CRF objective used by fitting and gradient tests."""

    __slots__ = ("examples", "layout", "rho")

    def __init__(
        self,
        examples: tuple[_TrainingLine, ...],
        layout: _ParameterLayout,
        *,
        rho: float = CRF_L2_RHO,
    ) -> None:
        if not examples:
            raise V4SequenceError("CRF objective requires training lines")
        if not math.isfinite(rho) or rho <= 0.0:
            raise V4SequenceError("CRF L2 rho must be finite and positive")
        self.examples = examples
        self.layout = layout
        self.rho = rho

    def evaluate(
        self,
        parameters: tuple[float, ...],
    ) -> tuple[float, tuple[float, ...]]:
        if len(parameters) != self.layout.parameter_count:
            raise V4SequenceError("CRF parameter vector has the wrong length")
        if any(not math.isfinite(value) for value in parameters):
            raise V4SequenceError("CRF parameters must be finite")

        gradient = [0.0] * self.layout.parameter_count
        losses: list[float] = []
        for example in self.examples:
            emissions = _emission_scores(parameters, self.layout, example.rows)
            forward, log_partition = _forward(
                parameters,
                self.layout,
                emissions,
                transition_zero=False,
            )
            backward = _backward(
                parameters,
                self.layout,
                emissions,
                transition_zero=False,
            )
            gold_score = _indexed_path_score(
                parameters,
                self.layout,
                emissions,
                example.states,
                transition_zero=False,
            )
            weight = example.objective_weight
            losses.append(weight * (log_partition - gold_score))

            for token_index, (row, gold_state) in enumerate(
                zip(example.rows, example.states, strict=True)
            ):
                for state_index in range(self.layout.state_count):
                    marginal = math.exp(
                        forward[token_index][state_index]
                        + backward[token_index][state_index]
                        - log_partition
                    )
                    signed_mass = weight * (marginal - (1.0 if state_index == gold_state else 0.0))
                    gradient[self.layout.bias_index(state_index)] += signed_mass
                    for feature_index, feature_value in row:
                        gradient[self.layout.emission_index(state_index, feature_index)] += (
                            signed_mass * feature_value
                        )

            for state_index in range(self.layout.state_count):
                start_marginal = math.exp(
                    forward[0][state_index] + backward[0][state_index] - log_partition
                )
                gradient[self.layout.start_index(state_index)] += weight * (
                    start_marginal - (1.0 if state_index == example.states[0] else 0.0)
                )

            for token_index in range(1, len(example.rows)):
                for previous_index in range(self.layout.state_count):
                    for current_index in range(self.layout.state_count):
                        transition_marginal = math.exp(
                            forward[token_index - 1][previous_index]
                            + parameters[
                                self.layout.transition_index(
                                    previous_index,
                                    current_index,
                                )
                            ]
                            + emissions[token_index][current_index]
                            + backward[token_index][current_index]
                            - log_partition
                        )
                        is_gold = (
                            previous_index == example.states[token_index - 1]
                            and current_index == example.states[token_index]
                        )
                        gradient[self.layout.transition_index(previous_index, current_index)] += (
                            weight * (transition_marginal - (1.0 if is_gold else 0.0))
                        )

        regularization = 0.5 * self.rho * math.fsum(value * value for value in parameters)
        for index, value in enumerate(parameters):
            gradient[index] += self.rho * value
        objective = math.fsum(losses) + regularization
        if not math.isfinite(objective) or any(not math.isfinite(value) for value in gradient):
            raise V4SequenceError("CRF objective produced a non-finite value")
        return objective, tuple(gradient)


class _LogisticProblem:
    """Independent token-emission diagnostic with the CRF feature surface."""

    __slots__ = ("examples", "layout", "rho")

    def __init__(
        self,
        examples: tuple[_TrainingLine, ...],
        layout: _ParameterLayout,
        *,
        rho: float = CRF_L2_RHO,
    ) -> None:
        if not examples:
            raise V4SequenceError("logistic objective requires training lines")
        self.examples = examples
        self.layout = layout
        self.rho = rho

    def evaluate(
        self,
        parameters: tuple[float, ...],
    ) -> tuple[float, tuple[float, ...]]:
        if len(parameters) != self.layout.parameter_count:
            raise V4SequenceError("logistic parameter vector has the wrong length")
        if any(not math.isfinite(value) for value in parameters):
            raise V4SequenceError("logistic parameters must be finite")

        gradient = [0.0] * self.layout.parameter_count
        losses: list[float] = []
        for example in self.examples:
            emissions = _emission_scores(parameters, self.layout, example.rows)
            for row, state_scores, gold_state in zip(
                example.rows,
                emissions,
                example.states,
                strict=True,
            ):
                log_normalizer = _logsumexp(state_scores)
                losses.append(
                    example.objective_weight * (log_normalizer - state_scores[gold_state])
                )
                for state_index in range(self.layout.state_count):
                    probability = math.exp(state_scores[state_index] - log_normalizer)
                    signed_mass = example.objective_weight * (
                        probability - (1.0 if state_index == gold_state else 0.0)
                    )
                    gradient[self.layout.bias_index(state_index)] += signed_mass
                    for feature_index, feature_value in row:
                        gradient[self.layout.emission_index(state_index, feature_index)] += (
                            signed_mass * feature_value
                        )

        regularization = 0.5 * self.rho * math.fsum(value * value for value in parameters)
        for index, value in enumerate(parameters):
            gradient[index] += self.rho * value
        objective = math.fsum(losses) + regularization
        if not math.isfinite(objective) or any(not math.isfinite(value) for value in gradient):
            raise V4SequenceError("logistic objective produced a non-finite value")
        return objective, tuple(gradient)


class V4LinearChainCRF:
    """One fixed, anonymous five-state discriminative sequence model."""

    __slots__ = (
        "_class_priors",
        "_encoder",
        "_layout",
        "_objective",
        "_parameters",
        "_termination_reason",
        "_training_gradient_infinity_norm",
        "_training_iterations",
    )

    def __init__(
        self,
        *,
        encoder: _FeatureEncoder,
        parameters: tuple[float, ...],
        class_priors: tuple[float, ...],
        training_iterations: int,
        training_gradient_infinity_norm: float,
        termination_reason: OptimizationTerminationReason,
        objective: float,
    ) -> None:
        layout = _ParameterLayout(feature_count=len(encoder.specs))
        if len(parameters) != layout.parameter_count:
            raise V4SequenceError("model parameter vector has the wrong length")
        if len(class_priors) != len(V3_STRUCTURAL_STATES):
            raise V4SequenceError("model class priors have the wrong length")
        if any(not math.isfinite(value) for value in parameters):
            raise V4SequenceError("model parameters must be finite")
        if any(not math.isfinite(value) or value <= 0.0 for value in class_priors):
            raise V4SequenceError("model class priors must be finite and positive")
        if not math.isclose(math.fsum(class_priors), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise V4SequenceError("model class priors must sum to one")
        if (
            isinstance(training_iterations, bool)
            or not isinstance(training_iterations, int)
            or training_iterations < 0
        ):
            raise V4SequenceError("training iterations must be a non-negative integer")
        if not math.isfinite(objective):
            raise V4SequenceError("training objective must be finite")
        if (
            not math.isfinite(training_gradient_infinity_norm)
            or training_gradient_infinity_norm < 0.0
        ):
            raise V4SequenceError("training gradient infinity norm must be finite and non-negative")
        if termination_reason not in {
            "gradient_infinity_norm",
            "relative_objective_stability",
        }:
            raise V4SequenceError("model termination reason is outside the closed vocabulary")
        self._encoder = encoder
        self._layout = layout
        self._parameters = parameters
        self._class_priors = class_priors
        self._training_iterations = training_iterations
        self._training_gradient_infinity_norm = training_gradient_infinity_norm
        self._termination_reason = termination_reason
        self._objective = objective

    def __repr__(self) -> str:
        return (
            "V4LinearChainCRF("
            f"version={V4_CRF_MODEL_VERSION!r}, "
            f"feature_count={self.feature_count}, "
            f"training_iterations={self.training_iterations})"
        )

    @classmethod
    def fit(cls, families: Sequence[V4LabeledFeatureFamily]) -> Self:
        """Fit the single frozen CRF candidate with no IDs or tuning surface."""

        encoder, problem, class_priors = _prepare_problem(families)
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
    def feature_count(self) -> int:
        return self._layout.feature_count

    @property
    def training_iterations(self) -> int:
        return self._training_iterations

    @property
    def training_objective(self) -> float:
        return self._objective

    @property
    def training_gradient_infinity_norm(self) -> float:
        return self._training_gradient_infinity_norm

    @property
    def termination_reason(self) -> OptimizationTerminationReason:
        return cast(OptimizationTerminationReason, self._termination_reason)

    def optimization_summary(self) -> dict[str, bool | float | int | str]:
        """Return the aggregate, identifier-free optimizer receipt."""

        return {
            "converged": True,
            "accepted_iterations": self.training_iterations,
            "final_objective": self.training_objective,
            "final_gradient_infinity_norm": self.training_gradient_infinity_norm,
            "termination_reason": self.termination_reason,
        }

    @property
    def class_priors(self) -> tuple[float, ...]:
        return self._class_priors

    def emission_scores(
        self,
        line: V4FeatureLine,
        *,
        class_adjusted: bool = True,
    ) -> tuple[tuple[float, ...], ...]:
        """Return ordered state emissions, optionally with frozen prior adjustment."""

        rows = self._encoder.transform_line(line)
        emissions = _emission_scores(self._parameters, self._layout, rows)
        if not class_adjusted:
            return emissions
        adjustments = tuple(
            -CLASS_ADJUSTMENT_GAMMA * math.log(prior) for prior in self._class_priors
        )
        return tuple(
            tuple(value + adjustments[state_index] for state_index, value in enumerate(row))
            for row in emissions
        )

    def sequence_score(
        self,
        line: V4FeatureLine,
        states: Sequence[V3StructuralState],
        *,
        class_adjusted: bool = True,
        transition_zero: bool = False,
    ) -> float:
        """Score one complete state path under the frozen model."""

        indexed_states = _state_indices(states, expected_length=len(line.rows))
        emissions = self.emission_scores(line, class_adjusted=class_adjusted)
        return _indexed_path_score(
            self._parameters,
            self._layout,
            emissions,
            indexed_states,
            transition_zero=transition_zero,
        )

    def log_partition(
        self,
        line: V4FeatureLine,
        *,
        class_adjusted: bool = True,
        transition_zero: bool = False,
    ) -> float:
        """Return the exact forward log partition for one feature line."""

        emissions = self.emission_scores(line, class_adjusted=class_adjusted)
        _, value = _forward(
            self._parameters,
            self._layout,
            emissions,
            transition_zero=transition_zero,
        )
        return value

    def decode(
        self,
        line: V4FeatureLine,
        *,
        transition_zero: bool = False,
    ) -> tuple[V3StructuralState, ...]:
        """Viterbi-decode with deterministic state-order ties.

        ``transition_zero`` is the frozen non-selecting diagnostic: it removes
        both start and transition scores without refitting the primary model.
        """

        emissions = self.emission_scores(line, class_adjusted=True)
        if not emissions:
            raise V4SequenceError("decoded feature line may not be empty")
        state_count = self._layout.state_count
        previous_scores = tuple(
            emissions[0][state_index]
            + (0.0 if transition_zero else self._parameters[self._layout.start_index(state_index)])
            for state_index in range(state_count)
        )
        backpointers: list[tuple[int, ...]] = []
        for token_index in range(1, len(emissions)):
            current_scores: list[float] = []
            current_pointers: list[int] = []
            for current_index in range(state_count):
                best_previous = 0
                best_score = previous_scores[0] + (
                    0.0
                    if transition_zero
                    else self._parameters[self._layout.transition_index(0, current_index)]
                )
                for previous_index in range(1, state_count):
                    candidate = previous_scores[previous_index] + (
                        0.0
                        if transition_zero
                        else self._parameters[
                            self._layout.transition_index(
                                previous_index,
                                current_index,
                            )
                        ]
                    )
                    if candidate > best_score:
                        best_previous = previous_index
                        best_score = candidate
                current_scores.append(best_score + emissions[token_index][current_index])
                current_pointers.append(best_previous)
            previous_scores = tuple(current_scores)
            backpointers.append(tuple(current_pointers))

        best_final = 0
        for state_index in range(1, state_count):
            if previous_scores[state_index] > previous_scores[best_final]:
                best_final = state_index
        path = [best_final]
        for pointers in reversed(backpointers):
            path.append(pointers[path[-1]])
        path.reverse()
        return tuple(V3_STRUCTURAL_STATES[index] for index in path)

    def model_state_commitment(self) -> str:
        """Commit the complete ID-free model state without serializing it."""

        digest = hashlib.sha256(_MODEL_COMMITMENT_DOMAIN)
        for value in (
            V4_CRF_MODEL_VERSION,
            f"rho={CRF_L2_RHO:.17g}",
            f"gamma={CLASS_ADJUSTMENT_GAMMA:.17g}",
            f"jeffreys={JEFFREYS_ALPHA:.17g}",
        ):
            _update_frame(digest, value.encode("ascii"))
        for state in V3_STRUCTURAL_STATES:
            _update_frame(digest, state.encode("ascii"))
        for spec in self._encoder.specs:
            _update_frame(digest, spec.kind.encode("ascii"))
            _update_frame(digest, spec.name.encode("utf-8"))
            if spec.category is None:
                digest.update(b"\x00")
            else:
                digest.update(b"\x01")
                _update_frame(digest, spec.category.encode("utf-8"))
        for value in (*self._class_priors, *self._parameters):
            digest.update(struct.pack(">d", value))
        return f"sha256:{digest.hexdigest()}"


class V4LogisticEmissionModel:
    """Frozen independent-emission diagnostic; never a selectable candidate."""

    __slots__ = ("_model",)

    def __init__(self, model: V4LinearChainCRF) -> None:
        self._model = model

    def __repr__(self) -> str:
        return (
            "V4LogisticEmissionModel("
            f"version={V4_LOGISTIC_MODEL_VERSION!r}, "
            f"feature_count={self.feature_count}, "
            f"training_iterations={self.training_iterations})"
        )

    @classmethod
    def fit(cls, families: Sequence[V4LabeledFeatureFamily]) -> Self:
        """Fit the fixed independent-emission diagnostic."""

        encoder, crf_problem, class_priors = _prepare_problem(families)
        problem = _LogisticProblem(
            crf_problem.examples,
            crf_problem.layout,
        )
        initial = (0.0,) * problem.layout.parameter_count
        result = _lbfgs_minimize(problem.evaluate, initial)
        model = V4LinearChainCRF(
            encoder=encoder,
            parameters=result.parameters,
            class_priors=class_priors,
            training_iterations=result.accepted_iterations,
            training_gradient_infinity_norm=result.gradient_infinity_norm,
            termination_reason=result.termination_reason,
            objective=result.objective,
        )
        return cls(model)

    @property
    def feature_count(self) -> int:
        return self._model.feature_count

    @property
    def training_iterations(self) -> int:
        return self._model.training_iterations

    @property
    def training_objective(self) -> float:
        return self._model.training_objective

    @property
    def training_gradient_infinity_norm(self) -> float:
        return self._model.training_gradient_infinity_norm

    @property
    def termination_reason(self) -> OptimizationTerminationReason:
        return self._model.termination_reason

    @property
    def class_priors(self) -> tuple[float, ...]:
        return self._model.class_priors

    def optimization_summary(self) -> dict[str, bool | float | int | str]:
        return self._model.optimization_summary()

    def emission_scores(
        self,
        line: V4FeatureLine,
        *,
        class_adjusted: bool = True,
    ) -> tuple[tuple[float, ...], ...]:
        return self._model.emission_scores(
            line,
            class_adjusted=class_adjusted,
        )

    def decode(self, line: V4FeatureLine) -> tuple[V3StructuralState, ...]:
        """Independently argmax each token with deterministic state-order ties."""

        emissions = self.emission_scores(line, class_adjusted=True)
        output: list[V3StructuralState] = []
        for row in emissions:
            best = 0
            for state_index in range(1, len(V3_STRUCTURAL_STATES)):
                if row[state_index] > row[best]:
                    best = state_index
            output.append(V3_STRUCTURAL_STATES[best])
        return tuple(output)

    def model_state_commitment(self) -> str:
        """Commit the ID-free diagnostic state under a distinct domain."""

        digest = hashlib.sha256(_LOGISTIC_COMMITMENT_DOMAIN)
        _update_frame(digest, V4_LOGISTIC_MODEL_VERSION.encode("ascii"))
        _update_frame(
            digest,
            self._model.model_state_commitment().encode("ascii"),
        )
        return f"sha256:{digest.hexdigest()}"


def _validate_feature_row(row: object) -> None:
    if not isinstance(row, tuple) or not row:
        raise V4SequenceError("feature row must be a non-empty tuple")
    names: set[str] = set()
    for item in row:
        if not isinstance(item, tuple) or len(item) != 2:
            raise V4SequenceError("feature entries must be name-value pairs")
        name, value = item
        if not isinstance(name, str) or not name:
            raise V4SequenceError("feature name must be a non-empty string")
        if _looks_like_identifier(name):
            raise V4SequenceError("opaque identifiers may not enter the feature vocabulary")
        if name not in _CLOSED_FEATURE_NAMES:
            raise V4SequenceError("feature name is outside the frozen V4 surface")
        if name in names:
            raise V4SequenceError("feature names must be unique within a row")
        names.add(name)
        if isinstance(value, str):
            if not value:
                raise V4SequenceError("categorical feature values may not be empty")
            if _looks_like_identifier(value):
                raise V4SequenceError("opaque identifiers may not enter the feature vocabulary")
            if value not in _CATEGORICAL_VALUES[name]:
                raise V4SequenceError("categorical feature value is outside the frozen V4 surface")
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0.0 <= float(value) <= 1.0
        ):
            raise V4SequenceError("numeric feature values must be finite and in [0, 1]")
        elif name not in _NUMERIC_FEATURE_NAMES:
            raise V4SequenceError("categorical-only V4 feature received a numeric value")


def _looks_like_identifier(value: str) -> bool:
    return any(
        pattern.fullmatch(value) is not None
        for pattern in (_TAGGED_DIGEST, _BARE_DIGEST, _PREFIXED_DIGEST)
    )


def _canonical_feature_value(value: object) -> str:
    if isinstance(value, str):
        return f"s{len(value)}:{value}"
    if isinstance(value, float):
        return f"f:{value.hex()}"
    raise V4SequenceError("canonical feature value is outside the V4 contract")


def _canonical_row_key(row: FeatureRow) -> str:
    _validate_feature_row(row)
    return "\x1f".join(
        f"{len(name)}:{name}={_canonical_feature_value(value)}" for name, value in sorted(row)
    )


def _canonical_line_key(line: V4LabeledFeatureLine) -> str:
    if not isinstance(line, V4LabeledFeatureLine):
        raise V4SequenceError("training lines must satisfy the V4 labeled contract")
    state_frame = "\x1f".join(line.states)
    row_frame = "\x1e".join(_canonical_row_key(row) for row in line.feature_line.rows)
    return f"{state_frame}\x1d{row_frame}"


def _ordered_family_lines(
    family: V4LabeledFeatureFamily,
) -> tuple[V4LabeledFeatureLine, ...]:
    return tuple(
        sorted(
            (line for document in family.documents for line in document.lines),
            key=_canonical_line_key,
        )
    )


def _canonical_family_key(family: V4LabeledFeatureFamily) -> str:
    return "\x1c".join(_canonical_line_key(line) for line in _ordered_family_lines(family))


def _prepare_problem(
    families: Sequence[V4LabeledFeatureFamily],
) -> tuple[_FeatureEncoder, _CRFProblem, tuple[float, ...]]:
    family_values = tuple(families)
    if not family_values:
        raise V4SequenceError("at least one labeled feature family is required")
    if any(not isinstance(family, V4LabeledFeatureFamily) for family in family_values):
        raise V4SequenceError("fit accepts only V4 labeled feature families")
    family_values = tuple(sorted(family_values, key=_canonical_family_key))

    rows: list[FeatureRow] = []
    for family in family_values:
        for line in _ordered_family_lines(family):
            rows.extend(line.feature_line.rows)
    encoder = _FeatureEncoder.fit(rows)
    layout = _ParameterLayout(feature_count=len(encoder.specs))

    family_count = len(family_values)
    examples: list[_TrainingLine] = []
    prior_contributions: list[list[float]] = [[] for _ in range(layout.state_count)]
    for family in family_values:
        ordered_lines = _ordered_family_lines(family)
        token_count = sum(len(line.states) for line in ordered_lines)
        if token_count <= 0:
            raise V4SequenceError("every training family must contain a token")
        objective_weight = 1.0 / (family_count * token_count)
        prior_weight = 1.0 / token_count
        family_state_counts = [0] * layout.state_count
        for line in ordered_lines:
            if len(line.states) != len(line.feature_line.rows) or not line.states:
                raise V4SequenceError("feature lines and state truth must align")
            indexed_states = _state_indices(
                line.states,
                expected_length=len(line.feature_line.rows),
            )
            for state_index in indexed_states:
                family_state_counts[state_index] += 1
            examples.append(
                _TrainingLine(
                    rows=tuple(encoder.transform_row(row) for row in line.feature_line.rows),
                    states=indexed_states,
                    objective_weight=objective_weight,
                )
            )
        for state_index, count in enumerate(family_state_counts):
            prior_contributions[state_index].append(count * prior_weight)

    prior_masses = tuple(math.fsum(contributions) for contributions in prior_contributions)
    if any(mass <= 0.0 for mass in prior_masses):
        raise V4SequenceError("every structural state needs positive training support")
    total_mass = math.fsum(prior_masses)
    denominator = total_mass + JEFFREYS_ALPHA * layout.state_count
    priors = tuple((mass + JEFFREYS_ALPHA) / denominator for mass in prior_masses)
    return encoder, _CRFProblem(tuple(examples), layout), priors


def _state_indices(
    states: Sequence[V3StructuralState],
    *,
    expected_length: int,
) -> tuple[int, ...]:
    state_values = tuple(states)
    if len(state_values) != expected_length or not state_values:
        raise V4SequenceError("state path length must match the non-empty feature line")
    try:
        return tuple(_STATE_TO_INDEX[state] for state in state_values)
    except KeyError as error:
        raise V4SequenceError("state path contains a value outside the five-state space") from error


def _emission_scores(
    parameters: Sequence[float],
    layout: _ParameterLayout,
    rows: Sequence[SparseFeatureRow],
) -> tuple[tuple[float, ...], ...]:
    output: list[tuple[float, ...]] = []
    for row in rows:
        state_scores: list[float] = []
        for state_index in range(layout.state_count):
            state_scores.append(
                parameters[layout.bias_index(state_index)]
                + math.fsum(
                    parameters[layout.emission_index(state_index, feature_index)] * feature_value
                    for feature_index, feature_value in row
                )
            )
        output.append(tuple(state_scores))
    return tuple(output)


def _forward(
    parameters: Sequence[float],
    layout: _ParameterLayout,
    emissions: Sequence[Sequence[float]],
    *,
    transition_zero: bool,
) -> tuple[tuple[tuple[float, ...], ...], float]:
    if not emissions:
        raise V4SequenceError("CRF lines may not be empty")
    rows: list[tuple[float, ...]] = [
        tuple(
            emissions[0][state_index]
            + (0.0 if transition_zero else parameters[layout.start_index(state_index)])
            for state_index in range(layout.state_count)
        )
    ]
    for token_index in range(1, len(emissions)):
        previous = rows[-1]
        current: list[float] = []
        for current_index in range(layout.state_count):
            transition_total = _logsumexp(
                tuple(
                    previous[previous_index]
                    + (
                        0.0
                        if transition_zero
                        else parameters[layout.transition_index(previous_index, current_index)]
                    )
                    for previous_index in range(layout.state_count)
                )
            )
            current.append(transition_total + emissions[token_index][current_index])
        rows.append(tuple(current))
    return tuple(rows), _logsumexp(rows[-1])


def _backward(
    parameters: Sequence[float],
    layout: _ParameterLayout,
    emissions: Sequence[Sequence[float]],
    *,
    transition_zero: bool,
) -> tuple[tuple[float, ...], ...]:
    if not emissions:
        raise V4SequenceError("CRF lines may not be empty")
    rows: list[tuple[float, ...] | None] = [None] * len(emissions)
    rows[-1] = (0.0,) * layout.state_count
    for token_index in range(len(emissions) - 2, -1, -1):
        following = cast(tuple[float, ...], rows[token_index + 1])
        current: list[float] = []
        for previous_index in range(layout.state_count):
            current.append(
                _logsumexp(
                    tuple(
                        (
                            0.0
                            if transition_zero
                            else parameters[layout.transition_index(previous_index, current_index)]
                        )
                        + emissions[token_index + 1][current_index]
                        + following[current_index]
                        for current_index in range(layout.state_count)
                    )
                )
            )
        rows[token_index] = tuple(current)
    return tuple(cast(tuple[float, ...], row) for row in rows)


def _indexed_path_score(
    parameters: Sequence[float],
    layout: _ParameterLayout,
    emissions: Sequence[Sequence[float]],
    states: Sequence[int],
    *,
    transition_zero: bool,
) -> float:
    if len(emissions) != len(states) or not states:
        raise V4SequenceError("emissions and path must have equal non-zero length")
    contributions = [emissions[index][state] for index, state in enumerate(states)]
    if not transition_zero:
        contributions.append(parameters[layout.start_index(states[0])])
        contributions.extend(
            parameters[layout.transition_index(previous, current)]
            for previous, current in pairwise(states)
        )
    return math.fsum(contributions)


def _logsumexp(values: Sequence[float]) -> float:
    if not values:
        raise V4SequenceError("log-sum-exp requires at least one value")
    maximum = max(values)
    if not math.isfinite(maximum):
        raise V4SequenceError("log-sum-exp received a non-finite value")
    return maximum + math.log(math.fsum(math.exp(value - maximum) for value in values))


def _lbfgs_minimize(
    objective: ObjectiveFunction,
    initial_parameters: Sequence[float],
    *,
    settings: _LBFGSSettings | None = None,
) -> _LBFGSResult:
    selected_settings = _DEFAULT_LBFGS_SETTINGS if settings is None else settings
    parameters = tuple(float(value) for value in initial_parameters)
    if not parameters:
        raise V4SequenceError("L-BFGS requires a non-empty parameter vector")
    if any(not math.isfinite(value) for value in parameters):
        raise V4SequenceError("initial L-BFGS parameters must be finite")

    value, gradient = objective(parameters)
    _validate_objective_result(value, gradient, len(parameters))
    history_s: list[tuple[float, ...]] = []
    history_y: list[tuple[float, ...]] = []
    history_inverse_curvature: list[float] = []
    stable_count = 0
    reset_used = False

    if _infinity_norm(gradient) <= selected_settings.gradient_tolerance:
        return _LBFGSResult(
            parameters=parameters,
            objective=value,
            gradient_infinity_norm=_infinity_norm(gradient),
            accepted_iterations=0,
            termination_reason="gradient_infinity_norm",
        )

    for iteration in range(1, selected_settings.max_iterations + 1):
        direction = _lbfgs_direction(
            gradient,
            history_s,
            history_y,
            history_inverse_curvature,
        )
        directional_derivative = _dot(gradient, direction)
        if not math.isfinite(directional_derivative) or directional_derivative >= 0.0:
            if reset_used:
                raise V4SequenceError("L-BFGS produced repeated non-descent directions")
            history_s.clear()
            history_y.clear()
            history_inverse_curvature.clear()
            reset_used = True
            direction = tuple(-component for component in gradient)
            directional_derivative = -_dot(gradient, gradient)
            if not math.isfinite(directional_derivative) or directional_derivative >= 0.0:
                raise V4SequenceError("L-BFGS could not construct a descent direction")

        step = 1.0
        accepted: tuple[tuple[float, ...], float, tuple[float, ...]] | None = None
        for trial_index in range(selected_settings.max_line_search_trials):
            candidate = tuple(
                parameter + step * component
                for parameter, component in zip(parameters, direction, strict=True)
            )
            candidate_value, candidate_gradient = objective(candidate)
            _validate_objective_result(
                candidate_value,
                candidate_gradient,
                len(parameters),
            )
            if candidate_value <= (
                value + selected_settings.armijo_c1 * step * directional_derivative
            ):
                accepted = (candidate, candidate_value, candidate_gradient)
                break
            if trial_index + 1 == selected_settings.max_line_search_trials:
                break
            step *= selected_settings.backtrack_factor
            if step < selected_settings.min_step:
                break
        if accepted is None:
            raise V4SequenceError("L-BFGS Armijo line search failed")

        candidate, candidate_value, candidate_gradient = accepted
        displacement = tuple(
            current - previous for current, previous in zip(candidate, parameters, strict=True)
        )
        gradient_change = tuple(
            current - previous
            for current, previous in zip(candidate_gradient, gradient, strict=True)
        )
        curvature = _dot(displacement, gradient_change)
        curvature_floor = (
            selected_settings.curvature_relative_minimum
            * _euclidean_norm(displacement)
            * _euclidean_norm(gradient_change)
        )
        if curvature > curvature_floor:
            history_s.append(displacement)
            history_y.append(gradient_change)
            history_inverse_curvature.append(1.0 / curvature)
            if len(history_s) > selected_settings.history_size:
                history_s.pop(0)
                history_y.pop(0)
                history_inverse_curvature.pop(0)

        relative_change = abs(value - candidate_value) / max(1.0, abs(value))
        gradient_norm = _infinity_norm(candidate_gradient)
        if (
            relative_change <= selected_settings.relative_objective_tolerance
            and gradient_norm <= selected_settings.stalled_gradient_tolerance
        ):
            stable_count += 1
        else:
            stable_count = 0

        parameters = candidate
        value = candidate_value
        gradient = candidate_gradient
        if (
            gradient_norm <= selected_settings.gradient_tolerance
            or stable_count >= selected_settings.stable_iterations
        ):
            return _LBFGSResult(
                parameters=parameters,
                objective=value,
                gradient_infinity_norm=gradient_norm,
                accepted_iterations=iteration,
                termination_reason=(
                    "gradient_infinity_norm"
                    if gradient_norm <= selected_settings.gradient_tolerance
                    else "relative_objective_stability"
                ),
            )

    raise V4SequenceError("L-BFGS did not converge within 100 accepted iterations")


def _lbfgs_direction(
    gradient: Sequence[float],
    history_s: Sequence[tuple[float, ...]],
    history_y: Sequence[tuple[float, ...]],
    history_inverse_curvature: Sequence[float],
) -> tuple[float, ...]:
    if not history_s:
        return tuple(-component for component in gradient)
    work = tuple(gradient)
    alphas: list[float] = []
    for displacement, gradient_change, inverse_curvature in reversed(
        tuple(zip(history_s, history_y, history_inverse_curvature, strict=True))
    ):
        alpha = inverse_curvature * _dot(displacement, work)
        alphas.append(alpha)
        work = tuple(
            component - alpha * change
            for component, change in zip(work, gradient_change, strict=True)
        )
    latest_s = history_s[-1]
    latest_y = history_y[-1]
    yy = _dot(latest_y, latest_y)
    scale = _dot(latest_s, latest_y) / yy if yy > 0.0 else 1.0
    result = tuple(scale * component for component in work)
    for (
        displacement,
        gradient_change,
        inverse_curvature,
    ), alpha in zip(
        zip(history_s, history_y, history_inverse_curvature, strict=True),
        reversed(alphas),
        strict=True,
    ):
        beta = inverse_curvature * _dot(gradient_change, result)
        result = tuple(
            component + displacement_component * (alpha - beta)
            for component, displacement_component in zip(
                result,
                displacement,
                strict=True,
            )
        )
    return tuple(-component for component in result)


def _validate_objective_result(
    value: float,
    gradient: Sequence[float],
    expected_length: int,
) -> None:
    if not math.isfinite(value):
        raise V4SequenceError("optimizer objective must be finite")
    if len(gradient) != expected_length:
        raise V4SequenceError("optimizer gradient has the wrong length")
    if any(not math.isfinite(component) for component in gradient):
        raise V4SequenceError("optimizer gradient must be finite")


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise V4SequenceError("vector lengths do not match")
    return math.fsum(first * second for first, second in zip(left, right, strict=True))


def _euclidean_norm(values: Sequence[float]) -> float:
    return math.sqrt(math.fsum(value * value for value in values))


def _infinity_norm(values: Sequence[float]) -> float:
    return max((abs(value) for value in values), default=0.0)


def _update_frame(digest: object, value: bytes) -> None:
    updater = cast("hashlib._Hash", digest)
    updater.update(len(value).to_bytes(8, "big"))
    updater.update(value)


__all__ = [
    "CLASS_ADJUSTMENT_GAMMA",
    "CRF_L2_RHO",
    "JEFFREYS_ALPHA",
    "LBFGS_ARMIJO_C1",
    "LBFGS_BACKTRACK_FACTOR",
    "LBFGS_CURVATURE_RELATIVE_MINIMUM",
    "LBFGS_GRADIENT_TOLERANCE",
    "LBFGS_HISTORY_SIZE",
    "LBFGS_MAX_ITERATIONS",
    "LBFGS_MAX_LINE_SEARCH_TRIALS",
    "LBFGS_MIN_STEP",
    "LBFGS_RELATIVE_OBJECTIVE_TOLERANCE",
    "LBFGS_STABLE_ITERATIONS",
    "LBFGS_STALLED_GRADIENT_TOLERANCE",
    "V4_CRF_MODEL_VERSION",
    "V4_LOGISTIC_MODEL_VERSION",
    "V4LinearChainCRF",
    "V4LogisticEmissionModel",
    "V4SequenceError",
]
