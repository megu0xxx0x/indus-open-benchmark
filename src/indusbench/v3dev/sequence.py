"""Five-state structural sequence model for V3 development.

The model deliberately learns no lexical identity.  Opaque form fingerprints
are consulted only while deriving within-line equality and repetition
categories; neither a fingerprint nor a token, document, or family key is
retained in the fitted model or emitted as a feature.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Final, Self, cast

from indusbench.v3dev.contracts import (
    V3_STRUCTURAL_STATES,
    MTAACTrainingDocument,
    V3ObservationLine,
    V3StructuralState,
)

CLASS_BALANCE_GAMMAS: Final = (0.0, 0.5, 1.0)
TRANSITION_STRENGTHS: Final = (0.0, 0.5, 1.0)
LAPLACE_ALPHA: Final = 1.0
V3_SEQUENCE_MODEL_VERSION: Final = "v3-structural-sequence-v1"

STRUCTURAL_FEATURE_NAMES: Final = (
    "position_bucket",
    "line_length_bucket",
    "reported_direction",
    "damage",
    "observation_status",
    "previous_equality",
    "next_equality",
    "line_frequency_bucket",
    "seen_before",
    "seen_after",
    "line_template",
)

_TEMPLATE_DOMAIN = b"indusbench:v3:structural-line-template:v1\x00"

FeatureRow = tuple[tuple[str, str], ...]


class V3SequenceError(ValueError):
    """Raised when structural training or decoding violates the V3 contract."""


def _position_bucket(index: int, length: int) -> str:
    if length == 1:
        return "singleton"
    if index == 0:
        return "initial"
    if index == length - 1:
        return "final"
    return "medial"


def _line_length_bucket(length: int) -> str:
    return str(length) if length <= 7 else "8_plus"


def _frequency_bucket(count: int) -> str:
    if count <= 1:
        return "once"
    if count == 2:
        return "twice"
    return "three_plus"


def _direction_category(value: str) -> str:
    if value == "known_source_order":
        return "known"
    if value == "unknown_visual_order":
        return "unknown"
    raise V3SequenceError("line direction is outside the closed structural contract")


def _neighbor_equality(
    fingerprints: Sequence[str | None],
    index: int,
    neighbor_index: int,
    boundary: str,
) -> str:
    if neighbor_index < 0 or neighbor_index >= len(fingerprints):
        return boundary
    current = fingerprints[index]
    neighbor = fingerprints[neighbor_index]
    if current is None:
        return "current_missing"
    if neighbor is None:
        return "neighbor_missing"
    return "same" if current == neighbor else "different"


def _line_template_category(
    fingerprints: Sequence[str | None],
    damaged: Sequence[bool],
) -> str:
    """Hash only a canonical equality/damage pattern, never a fingerprint."""

    equality_codes: dict[str, int] = {}
    framed_categories: list[str] = []
    for fingerprint, is_damaged in zip(fingerprints, damaged, strict=True):
        if fingerprint is None:
            equality = "missing"
        else:
            equality = str(equality_codes.setdefault(fingerprint, len(equality_codes)))
        framed_categories.append(f"{'damaged' if is_damaged else 'clear'}:{equality}")

    digest = hashlib.sha256()
    digest.update(_TEMPLATE_DOMAIN)
    digest.update(len(framed_categories).to_bytes(8, "big"))
    for category in framed_categories:
        raw = category.encode("ascii")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return f"template-sha256:{digest.hexdigest()}"


def structural_feature_rows(line: V3ObservationLine) -> tuple[FeatureRow, ...]:
    """Return source-neutral feature rows for every retained token in ``line``."""

    tokens = tuple(line.tokens)
    if not tokens:
        raise V3SequenceError("a structural line must contain at least one token")
    fingerprints = tuple(token.observation_id for token in tokens)
    damaged = tuple(token.damaged for token in tokens)
    if any(
        fingerprint is not None and (not isinstance(fingerprint, str) or not fingerprint)
        for fingerprint in fingerprints
    ):
        raise V3SequenceError("form fingerprints must be non-empty strings or null")
    if any(not isinstance(value, bool) for value in damaged):
        raise V3SequenceError("damage categories must be boolean")

    counts = Counter(fingerprint for fingerprint in fingerprints if fingerprint is not None)
    template = _line_template_category(fingerprints, damaged)
    direction = _direction_category(line.reported_direction)
    length = len(tokens)
    rows: list[FeatureRow] = []
    for index, (fingerprint, is_damaged) in enumerate(zip(fingerprints, damaged, strict=True)):
        if fingerprint is None:
            frequency = "missing"
            seen_before = "missing"
            seen_after = "missing"
        else:
            frequency = _frequency_bucket(counts[fingerprint])
            seen_before = "yes" if fingerprint in fingerprints[:index] else "no"
            seen_after = "yes" if fingerprint in fingerprints[index + 1 :] else "no"
        rows.append(
            (
                ("position_bucket", _position_bucket(index, length)),
                ("line_length_bucket", _line_length_bucket(length)),
                ("reported_direction", direction),
                ("damage", "damaged" if is_damaged else "clear"),
                (
                    "observation_status",
                    "missing" if fingerprint is None else "observed",
                ),
                (
                    "previous_equality",
                    _neighbor_equality(fingerprints, index, index - 1, "BOS"),
                ),
                (
                    "next_equality",
                    _neighbor_equality(fingerprints, index, index + 1, "EOS"),
                ),
                ("line_frequency_bucket", frequency),
                ("seen_before", seen_before),
                ("seen_after", seen_after),
                ("line_template", template),
            )
        )
    return tuple(rows)


def _validate_closed_choice(value: float, choices: tuple[float, ...], label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or float(value) not in choices
    ):
        rendered = ", ".join(str(choice) for choice in choices)
        raise V3SequenceError(f"{label} must be one of {rendered}")
    return float(value)


class V3SequenceModel:
    """Weighted categorical emissions plus a first-order Viterbi decoder."""

    __slots__ = (
        "_class_log_priors",
        "_class_masses",
        "_feature_log_probabilities",
        "_gamma",
        "_start_log_probabilities",
        "_transition_log_probabilities",
        "_vocabulary",
    )

    def __init__(
        self,
        *,
        gamma: float,
        class_masses: Mapping[V3StructuralState, float],
        class_log_priors: Mapping[V3StructuralState, float],
        vocabulary: Mapping[str, frozenset[str]],
        feature_log_probabilities: Mapping[
            V3StructuralState,
            Mapping[str, Mapping[str, float]],
        ],
        start_log_probabilities: Mapping[V3StructuralState, float],
        transition_log_probabilities: Mapping[
            V3StructuralState,
            Mapping[V3StructuralState, float],
        ],
    ) -> None:
        self._gamma = gamma
        self._class_masses = dict(class_masses)
        self._class_log_priors = dict(class_log_priors)
        self._vocabulary = dict(vocabulary)
        self._feature_log_probabilities = {
            state: {name: dict(values) for name, values in by_feature.items()}
            for state, by_feature in feature_log_probabilities.items()
        }
        self._start_log_probabilities = dict(start_log_probabilities)
        self._transition_log_probabilities = {
            state: dict(values) for state, values in transition_log_probabilities.items()
        }

    @classmethod
    def fit(
        cls,
        documents: Sequence[MTAACTrainingDocument],
        *,
        base_family_weights: Mapping[str, float],
        gamma: float,
    ) -> Self:
        """Fit using only caller-weighted families.

        Family keys are used transiently to distribute the caller's mass over
        all clean/mild occurrences.  They are discarded before the model is
        returned.  Class adjustment affects emissions only; transition and
        line-start counts retain the unadjusted family weights.
        """

        effective_gamma = _validate_closed_choice(
            gamma, CLASS_BALANCE_GAMMAS, "class-balance gamma"
        )
        document_values = tuple(documents)
        if not document_values:
            raise V3SequenceError("at least one training document is required")

        by_family: dict[str, list[MTAACTrainingDocument]] = defaultdict(list)
        for document in document_values:
            by_family[document.cluster_identifier].append(document)
        if set(base_family_weights) != set(by_family):
            raise V3SequenceError("base family weights must exactly cover the training family set")

        checked_family_weights: dict[str, float] = {}
        for family, value in base_family_weights.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise V3SequenceError("base family weights must be finite and strictly positive")
            checked_family_weights[family] = float(value)

        emission_rows: list[tuple[V3StructuralState, FeatureRow, float]] = []
        start_contributions: dict[V3StructuralState, list[float]] = {
            state: [] for state in V3_STRUCTURAL_STATES
        }
        transition_contributions: dict[
            V3StructuralState,
            dict[V3StructuralState, list[float]],
        ] = {
            previous: {following: [] for following in V3_STRUCTURAL_STATES}
            for previous in V3_STRUCTURAL_STATES
        }

        for family in sorted(by_family):
            family_documents = by_family[family]
            family_weight = checked_family_weights[family]
            family_lines = [line for document in family_documents for line in document.lines]
            if not family_lines:
                raise V3SequenceError("each training family must contain a line")
            token_count = sum(len(line.tokens) for line in family_lines)
            if token_count <= 0:
                raise V3SequenceError("each training family must contain a token")
            token_weight = family_weight / token_count
            start_weight = family_weight / len(family_lines)
            transition_count = sum(max(0, len(line.tokens) - 1) for line in family_lines)
            transition_weight = family_weight / transition_count if transition_count > 0 else None

            for line in family_lines:
                feature_rows = structural_feature_rows(line.to_observation())
                raw_states = tuple(token.state for token in line.tokens)
                states: tuple[V3StructuralState, ...] = tuple(
                    cast(V3StructuralState, state) for state in raw_states
                )
                if len(states) != len(feature_rows):
                    raise V3SequenceError("training truth and observations do not align")
                if any(state not in V3_STRUCTURAL_STATES for state in states):
                    raise V3SequenceError("training truth is outside the five-state space")
                start_contributions[states[0]].append(start_weight)
                for state, features in zip(states, feature_rows, strict=True):
                    emission_rows.append((state, features, token_weight))
                if transition_weight is not None:
                    for previous, following in pairwise(states):
                        transition_contributions[previous][following].append(transition_weight)

        base_class_contributions: dict[V3StructuralState, list[float]] = {
            state: [] for state in V3_STRUCTURAL_STATES
        }
        for state, _, weight in emission_rows:
            base_class_contributions[state].append(weight)
        base_class_masses: dict[V3StructuralState, float] = {
            state: math.fsum(base_class_contributions[state]) for state in V3_STRUCTURAL_STATES
        }
        if any(mass <= 0 for mass in base_class_masses.values()):
            raise V3SequenceError("every state requires positive fold-training support")
        total_base_mass = math.fsum(base_class_masses.values())
        target_mass = total_base_mass / len(V3_STRUCTURAL_STATES)
        class_multipliers: dict[V3StructuralState, float] = {
            state: (target_mass / base_class_masses[state]) ** effective_gamma
            for state in V3_STRUCTURAL_STATES
        }
        unscaled_adjusted_total = math.fsum(
            weight * class_multipliers[state] for state, _, weight in emission_rows
        )
        adjustment_scale = total_base_mass / unscaled_adjusted_total

        vocabulary_sets: dict[str, set[str]] = {name: set() for name in STRUCTURAL_FEATURE_NAMES}
        class_contributions: dict[V3StructuralState, list[float]] = {
            state: [] for state in V3_STRUCTURAL_STATES
        }
        feature_contributions: dict[
            V3StructuralState,
            dict[str, dict[str, list[float]]],
        ] = {
            state: {name: defaultdict(list) for name in STRUCTURAL_FEATURE_NAMES}
            for state in V3_STRUCTURAL_STATES
        }
        for state, features, base_weight in emission_rows:
            adjusted_weight = base_weight * class_multipliers[state] * adjustment_scale
            class_contributions[state].append(adjusted_weight)
            values = dict(features)
            if tuple(values) != STRUCTURAL_FEATURE_NAMES:
                raise V3SequenceError("structural feature surface is incomplete or reordered")
            for name, value in features:
                vocabulary_sets[name].add(value)
                feature_contributions[state][name][value].append(adjusted_weight)

        class_masses: dict[V3StructuralState, float] = {
            state: math.fsum(class_contributions[state]) for state in V3_STRUCTURAL_STATES
        }
        total_adjusted_mass = math.fsum(class_masses.values())
        state_count = len(V3_STRUCTURAL_STATES)
        class_log_priors: dict[V3StructuralState, float] = {
            state: math.log(
                (class_masses[state] + LAPLACE_ALPHA)
                / (total_adjusted_mass + LAPLACE_ALPHA * state_count)
            )
            for state in V3_STRUCTURAL_STATES
        }
        vocabulary = {name: frozenset(values) for name, values in vocabulary_sets.items()}
        feature_log_probabilities: dict[
            V3StructuralState,
            dict[str, dict[str, float]],
        ] = {state: {} for state in V3_STRUCTURAL_STATES}
        for state in V3_STRUCTURAL_STATES:
            for name in STRUCTURAL_FEATURE_NAMES:
                vocabulary_size = len(vocabulary[name])
                if vocabulary_size < 1:
                    raise V3SequenceError("each structural feature needs a vocabulary")
                denominator = class_masses[state] + LAPLACE_ALPHA * vocabulary_size
                feature_log_probabilities[state][name] = {
                    value: math.log(
                        (
                            math.fsum(feature_contributions[state][name].get(value, ()))
                            + LAPLACE_ALPHA
                        )
                        / denominator
                    )
                    for value in sorted(vocabulary[name])
                }

        start_masses: dict[V3StructuralState, float] = {
            state: math.fsum(start_contributions[state]) for state in V3_STRUCTURAL_STATES
        }
        total_start_mass = math.fsum(start_masses.values())
        start_log_probabilities: dict[V3StructuralState, float] = {
            state: math.log(
                (start_masses[state] + LAPLACE_ALPHA)
                / (total_start_mass + LAPLACE_ALPHA * state_count)
            )
            for state in V3_STRUCTURAL_STATES
        }
        transition_masses: dict[
            V3StructuralState,
            dict[V3StructuralState, float],
        ] = {
            previous: {
                following: math.fsum(transition_contributions[previous][following])
                for following in V3_STRUCTURAL_STATES
            }
            for previous in V3_STRUCTURAL_STATES
        }
        transition_log_probabilities: dict[
            V3StructuralState,
            dict[V3StructuralState, float],
        ] = {}
        for previous in V3_STRUCTURAL_STATES:
            row_mass = math.fsum(transition_masses[previous].values())
            denominator = row_mass + LAPLACE_ALPHA * state_count
            transition_log_probabilities[previous] = {
                following: math.log(
                    (transition_masses[previous][following] + LAPLACE_ALPHA) / denominator
                )
                for following in V3_STRUCTURAL_STATES
            }

        return cls(
            gamma=effective_gamma,
            class_masses=class_masses,
            class_log_priors=class_log_priors,
            vocabulary=vocabulary,
            feature_log_probabilities=feature_log_probabilities,
            start_log_probabilities=start_log_probabilities,
            transition_log_probabilities=transition_log_probabilities,
        )

    @property
    def gamma(self) -> float:
        return self._gamma

    @property
    def class_masses(self) -> tuple[tuple[V3StructuralState, float], ...]:
        return tuple((state, self._class_masses[state]) for state in V3_STRUCTURAL_STATES)

    @property
    def start_log_probabilities(self) -> tuple[float, ...]:
        return tuple(self._start_log_probabilities[state] for state in V3_STRUCTURAL_STATES)

    @property
    def transition_log_probabilities(self) -> tuple[tuple[float, ...], ...]:
        return tuple(
            tuple(
                self._transition_log_probabilities[previous][following]
                for following in V3_STRUCTURAL_STATES
            )
            for previous in V3_STRUCTURAL_STATES
        )

    def _emission_scores(self, features: Sequence[tuple[str, str]]) -> tuple[float, ...]:
        feature_values = tuple(features)
        if tuple(name for name, _ in feature_values) != STRUCTURAL_FEATURE_NAMES:
            raise V3SequenceError(
                "emission row must contain the complete ordered structural feature surface"
            )

        scores: list[float] = []
        for state in V3_STRUCTURAL_STATES:
            contributions = [self._class_log_priors[state]]
            for name, value in feature_values:
                # A value absent from this fold's training vocabulary carries
                # exactly zero evidence for every state.
                if value in self._vocabulary[name]:
                    contributions.append(self._feature_log_probabilities[state][name][value])
            scores.append(math.fsum(contributions))
        return tuple(scores)

    def emission_log_scores(
        self,
        line: V3ObservationLine,
    ) -> tuple[tuple[float, ...], ...]:
        """Return five ordered emission scores for every retained token."""

        return tuple(self._emission_scores(features) for features in structural_feature_rows(line))

    def decode(
        self,
        line: V3ObservationLine,
        *,
        transition_strength: float,
    ) -> tuple[V3StructuralState, ...]:
        """Decode one complete line with fixed-order deterministic ties."""

        strength = _validate_closed_choice(
            transition_strength,
            TRANSITION_STRENGTHS,
            "transition strength",
        )
        emissions = self.emission_log_scores(line)
        if not emissions:
            raise V3SequenceError("a decoded line must contain at least one token")

        previous_scores = tuple(
            emissions[0][state_index]
            + strength * self._start_log_probabilities[V3_STRUCTURAL_STATES[state_index]]
            for state_index in range(len(V3_STRUCTURAL_STATES))
        )
        backpointers: list[tuple[int, ...]] = []
        for token_index in range(1, len(emissions)):
            current_scores: list[float] = []
            current_backpointers: list[int] = []
            for current_index, current_state in enumerate(V3_STRUCTURAL_STATES):
                best_previous_index = 0
                best_transition_score = (
                    previous_scores[0]
                    + strength
                    * self._transition_log_probabilities[V3_STRUCTURAL_STATES[0]][current_state]
                )
                for previous_index in range(1, len(V3_STRUCTURAL_STATES)):
                    candidate = (
                        previous_scores[previous_index]
                        + strength
                        * self._transition_log_probabilities[V3_STRUCTURAL_STATES[previous_index]][
                            current_state
                        ]
                    )
                    if candidate > best_transition_score:
                        best_previous_index = previous_index
                        best_transition_score = candidate
                current_scores.append(best_transition_score + emissions[token_index][current_index])
                current_backpointers.append(best_previous_index)
            previous_scores = tuple(current_scores)
            backpointers.append(tuple(current_backpointers))

        best_final_index = 0
        best_final_score = previous_scores[0]
        for state_index in range(1, len(V3_STRUCTURAL_STATES)):
            if previous_scores[state_index] > best_final_score:
                best_final_index = state_index
                best_final_score = previous_scores[state_index]

        path = [best_final_index]
        for pointers in reversed(backpointers):
            path.append(pointers[path[-1]])
        path.reverse()
        return tuple(V3_STRUCTURAL_STATES[index] for index in path)

    def model_state_commitment(self, *, transition_strength: float) -> str:
        """Commit the selected model and decoder without a source identifier."""

        strength = _validate_closed_choice(
            transition_strength,
            TRANSITION_STRENGTHS,
            "transition strength",
        )

        payload = {
            "alpha": LAPLACE_ALPHA.hex(),
            "class_log_priors": {
                state: self._class_log_priors[state].hex() for state in V3_STRUCTURAL_STATES
            },
            "class_masses": {
                state: self._class_masses[state].hex() for state in V3_STRUCTURAL_STATES
            },
            "feature_log_probabilities": {
                state: {
                    name: {
                        value: score.hex()
                        for value, score in sorted(
                            self._feature_log_probabilities[state][name].items()
                        )
                    }
                    for name in STRUCTURAL_FEATURE_NAMES
                }
                for state in V3_STRUCTURAL_STATES
            },
            "feature_names": list(STRUCTURAL_FEATURE_NAMES),
            "gamma": self._gamma.hex(),
            "start_log_probabilities": {
                state: self._start_log_probabilities[state].hex() for state in V3_STRUCTURAL_STATES
            },
            "states": list(V3_STRUCTURAL_STATES),
            "transition_strength": strength.hex(),
            "transition_log_probabilities": {
                previous: {
                    following: self._transition_log_probabilities[previous][following].hex()
                    for following in V3_STRUCTURAL_STATES
                }
                for previous in V3_STRUCTURAL_STATES
            },
            "version": V3_SEQUENCE_MODEL_VERSION,
            "vocabulary": {
                name: sorted(self._vocabulary[name]) for name in STRUCTURAL_FEATURE_NAMES
            },
        }
        raw = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return f"sha256:{hashlib.sha256(raw).hexdigest()}"


__all__ = [
    "CLASS_BALANCE_GAMMAS",
    "LAPLACE_ALPHA",
    "STRUCTURAL_FEATURE_NAMES",
    "TRANSITION_STRENGTHS",
    "V3_SEQUENCE_MODEL_VERSION",
    "V3SequenceError",
    "V3SequenceModel",
    "structural_feature_rows",
]
