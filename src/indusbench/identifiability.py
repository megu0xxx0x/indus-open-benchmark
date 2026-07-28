"""Known-truth identifiability stress test under Indus-like constraints.

This module deliberately uses only project-authored synthetic data.  It asks a
limited methodological question: can a simple, preregisterable classifier
recover *known* functional classes after short-text, allograph, damage,
direction, and duplicate-family degradation?  A positive result is not
evidence for an Indus language, reading, meaning, translation, or
decipherment.

Truth and observations are represented by different frozen data classes.
Observed tokens never contain a canonical sign or functional-class field.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Any, Literal

FunctionalClass = Literal["issuer", "commodity", "quantity", "unit"]
Partition = Literal["train", "test"]
ReadingDirection = Literal["left_to_right", "right_to_left", "unknown"]
GateStatus = Literal["go", "no_go", "insufficient_evidence", "not_identifiable"]

FUNCTIONAL_CLASSES: tuple[FunctionalClass, ...] = (
    "issuer",
    "commodity",
    "quantity",
    "unit",
)

GENERATOR_VERSION = "synthetic-known-script-v1"
DEGRADATION_VERSION = "indus-like-degradation-v1"

_SITES = ("site-a", "site-b", "site-c")
_OBJECT_TYPES = ("seal", "tablet", "token")
_CLASS_TEMPLATES: tuple[tuple[FunctionalClass, ...], ...] = (
    ("issuer", "commodity", "quantity", "unit"),
    ("quantity", "unit", "commodity", "issuer"),
    ("commodity", "issuer", "unit", "quantity"),
    ("unit", "quantity", "issuer", "commodity"),
)
_CANONICAL_SIGNS: dict[FunctionalClass, tuple[str, ...]] = {
    functional_class: tuple(f"K{class_index * 8 + sign_index + 1:03d}" for sign_index in range(8))
    for class_index, functional_class in enumerate(FUNCTIONAL_CLASSES)
}


@dataclass(frozen=True, slots=True)
class TruthToken:
    """A token in the private-to-the-evaluator known-truth sidecar."""

    token_key: str
    canonical_sign: str
    functional_class: FunctionalClass
    word_index: int


@dataclass(frozen=True, slots=True)
class TruthFamily:
    """One independent inscription family before duplicate creation."""

    family_id: str
    site: str
    object_type: str
    tokens: tuple[TruthToken, ...]


@dataclass(frozen=True, slots=True)
class SyntheticKnownScript:
    """Project-authored known truth; it contains no third-party corpus data."""

    generator_version: str
    seed: int
    license_id: str
    rights_statement: str
    external_data_used: bool
    families: tuple[TruthFamily, ...]


@dataclass(frozen=True, slots=True)
class ObservedToken:
    """A degraded observation with no canonical-sign or class-valued field."""

    token_key: str
    sign_id: str | None
    visual_index: int
    reading_index: int | None
    condition: Literal["clear", "damaged"]


@dataclass(frozen=True, slots=True)
class ObservedArtifact:
    """One observed row, possibly an exact duplicate of its family peer."""

    artifact_id: str
    family_id: str
    partition: Partition
    site: str
    object_type: str
    reading_direction: ReadingDirection
    tokens: tuple[ObservedToken, ...]


@dataclass(frozen=True, slots=True)
class DegradationConfig:
    """Cumulative, deterministic Indus-like degradation settings."""

    max_sequence_length: int = 7
    allograph_rate: float = 0.30
    damage_rate: float = 0.10
    right_to_left_rate: float = 0.50
    direction_unknown_rate: float = 0.15
    duplicate_rate: float = 0.25
    test_fraction: float = 0.25
    seed: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_sequence_length, bool)
            or not isinstance(self.max_sequence_length, int)
            or self.max_sequence_length < 1
        ):
            raise ValueError("max_sequence_length must be an integer of at least 1")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        for name in (
            "allograph_rate",
            "damage_rate",
            "right_to_left_rate",
            "direction_unknown_rate",
            "duplicate_rate",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number in [0, 1]")
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be a finite number in [0, 1]")
        if (
            isinstance(self.test_fraction, bool)
            or not isinstance(self.test_fraction, (int, float))
            or not math.isfinite(self.test_fraction)
            or not 0.0 < self.test_fraction < 1.0
        ):
            raise ValueError("test_fraction must be a finite number strictly between 0 and 1")


@dataclass(frozen=True, slots=True)
class DegradedKnownScript:
    """Observation-only degradation result plus a truth-free split manifest."""

    generator_version: str
    degradation_version: str
    config: DegradationConfig
    observations: tuple[ObservedArtifact, ...]
    family_partitions: tuple[tuple[str, Partition], ...]


@dataclass(frozen=True, slots=True)
class _Example:
    family_id: str
    token_key: str
    ordinal: int
    features: tuple[tuple[str, str], ...]
    true_class: FunctionalClass
    weight: float


class _CategoricalNaiveBayes:
    """Small dependency-free categorical baseline with add-one smoothing."""

    def __init__(self) -> None:
        self._class_counts: dict[FunctionalClass, float] = {
            functional_class: 0.0 for functional_class in FUNCTIONAL_CLASSES
        }
        self._feature_counts: dict[
            FunctionalClass,
            dict[str, dict[str, float]],
        ] = {functional_class: {} for functional_class in FUNCTIONAL_CLASSES}
        self._vocabulary: dict[str, set[str]] = defaultdict(set)
        self._total = 0.0

    def fit(
        self,
        examples: Sequence[_Example],
        labels: Sequence[FunctionalClass] | None = None,
    ) -> _CategoricalNaiveBayes:
        if not examples:
            raise ValueError("at least one readable training token is required")
        effective_labels = (
            [example.true_class for example in examples] if labels is None else list(labels)
        )
        if len(examples) != len(effective_labels):
            raise ValueError("examples and labels must have the same length")

        self._class_counts = {functional_class: 0.0 for functional_class in FUNCTIONAL_CLASSES}
        self._feature_counts = {functional_class: {} for functional_class in FUNCTIONAL_CLASSES}
        self._vocabulary.clear()
        self._total = 0.0
        for example, label in zip(examples, effective_labels, strict=True):
            if label not in FUNCTIONAL_CLASSES:
                raise ValueError(f"unknown functional class: {label}")
            if not math.isfinite(example.weight) or example.weight <= 0.0:
                raise ValueError("example weights must be finite and positive")
            self._class_counts[label] += example.weight
            self._total += example.weight
            for name, value in example.features:
                counts = self._feature_counts[label].setdefault(name, {})
                counts[value] = counts.get(value, 0.0) + example.weight
                self._vocabulary[name].add(value)
        return self

    def predict(self, features: Sequence[tuple[str, str]]) -> FunctionalClass:
        if self._total < 1:
            raise ValueError("model must be fitted before prediction")
        scores: dict[FunctionalClass, float] = {}
        class_total = len(FUNCTIONAL_CLASSES)
        for functional_class in FUNCTIONAL_CLASSES:
            class_count = self._class_counts[functional_class]
            score = math.log((class_count + 1) / (self._total + class_total))
            for name, value in features:
                vocabulary_size = len(self._vocabulary.get(name, set())) + 1
                value_count = self._feature_counts[functional_class].get(name, {}).get(value, 0.0)
                score += math.log((value_count + 1) / (class_count + vocabulary_size))
            scores[functional_class] = score
        return max(
            FUNCTIONAL_CLASSES,
            key=lambda item: (scores[item], -FUNCTIONAL_CLASSES.index(item)),
        )


def _seed_value(seed: int, *parts: object) -> int:
    material = "\x1f".join((str(seed), *(str(part) for part in parts))).encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _uniform(seed: int, *parts: object) -> float:
    return _seed_value(seed, *parts) / float(1 << 64)


def _observed_base_sign(canonical_sign: str) -> str:
    if not canonical_sign.startswith("K") or not canonical_sign[1:].isdigit():
        raise ValueError(f"unsupported synthetic canonical sign: {canonical_sign}")
    return f"G{canonical_sign[1:]}"


def _position_bucket(index: int, length: int) -> str:
    if length == 1:
        return "singleton"
    if index == 0:
        return "initial"
    if index == length - 1:
        return "final"
    return "medial"


def _length_bucket(length: int) -> str:
    return str(length) if length <= 7 else "8_plus"


def generate_synthetic_known_script(
    *,
    seed: int = 0,
    family_count: int = 96,
) -> SyntheticKnownScript:
    """Generate deterministic, project-authored functional ground truth.

    The canonical inscriptions contain six to eleven tokens and explicit word
    groupings.  The degradation layer later truncates them and removes the
    grouping information from every observation.
    """

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(family_count, bool) or not isinstance(family_count, int) or family_count < 2:
        raise ValueError("family_count must be an integer of at least 2")

    families: list[TruthFamily] = []
    for family_index in range(family_count):
        family_id = f"SYN-KS-F{family_index:04d}"
        rng = random.Random(_seed_value(seed, "truth-family", family_id))
        site = _SITES[rng.randrange(len(_SITES))]
        object_type = _OBJECT_TYPES[rng.randrange(len(_OBJECT_TYPES))]
        class_sequence = list(_CLASS_TEMPLATES[rng.randrange(len(_CLASS_TEMPLATES))])
        target_length = 6 + rng.randrange(6)
        while len(class_sequence) < target_length:
            class_sequence.append(FUNCTIONAL_CLASSES[rng.randrange(len(FUNCTIONAL_CLASSES))])

        word_index = 0
        next_boundary = 1 + rng.randrange(3)
        tokens: list[TruthToken] = []
        for token_index, functional_class in enumerate(class_sequence):
            if token_index >= next_boundary:
                word_index += 1
                next_boundary += 1 + rng.randrange(3)
            inventory = _CANONICAL_SIGNS[functional_class]
            canonical_sign = inventory[rng.randrange(len(inventory))]
            tokens.append(
                TruthToken(
                    token_key=f"{family_id}:T{token_index:02d}",
                    canonical_sign=canonical_sign,
                    functional_class=functional_class,
                    word_index=word_index,
                )
            )
        families.append(
            TruthFamily(
                family_id=family_id,
                site=site,
                object_type=object_type,
                tokens=tuple(tokens),
            )
        )

    return SyntheticKnownScript(
        generator_version=GENERATOR_VERSION,
        seed=seed,
        license_id="CC0-1.0",
        rights_statement="Project-authored deterministic synthetic fixture; no external data.",
        external_data_used=False,
        families=tuple(families),
    )


def _family_split(
    families: Sequence[TruthFamily],
    *,
    test_fraction: float,
    seed: int,
) -> dict[str, Partition]:
    ranked = sorted(
        families,
        key=lambda family: (_seed_value(seed, "family-split", family.family_id), family.family_id),
    )
    test_count = max(1, min(len(ranked) - 1, int(len(ranked) * test_fraction + 0.5)))
    test_ids = {family.family_id for family in ranked[:test_count]}
    return {
        family.family_id: ("test" if family.family_id in test_ids else "train")
        for family in sorted(families, key=lambda item: item.family_id)
    }


def _degrade_family(
    family: TruthFamily,
    *,
    partition: Partition,
    config: DegradationConfig,
) -> ObservedArtifact:
    selected = list(family.tokens[: config.max_sequence_length])
    right_to_left = (
        _uniform(config.seed, "right-to-left", family.family_id) < config.right_to_left_rate
    )
    direction_unknown = (
        _uniform(config.seed, "direction-unknown", family.family_id) < config.direction_unknown_rate
    )
    reading_direction: ReadingDirection
    if direction_unknown:
        reading_direction = "unknown"
    elif right_to_left:
        reading_direction = "right_to_left"
    else:
        reading_direction = "left_to_right"

    reading_order = list(enumerate(selected))
    visual_order = list(reversed(reading_order)) if right_to_left else reading_order
    observed_tokens: list[ObservedToken] = []
    for visual_index, (reading_index, truth_token) in enumerate(visual_order):
        damaged = (
            _uniform(config.seed, "damage", family.family_id, truth_token.token_key)
            < config.damage_rate
        )
        sign_id: str | None = None
        if not damaged:
            sign_id = _observed_base_sign(truth_token.canonical_sign)
            if (
                _uniform(config.seed, "allograph", family.family_id, truth_token.token_key)
                < config.allograph_rate
            ):
                variant = (
                    "a"
                    if _seed_value(config.seed, "allograph-variant", truth_token.token_key) % 2 == 0
                    else "b"
                )
                sign_id = f"{sign_id}{variant}"
        observed_tokens.append(
            ObservedToken(
                token_key=truth_token.token_key,
                sign_id=sign_id,
                visual_index=visual_index,
                reading_index=None if direction_unknown else reading_index,
                condition="damaged" if damaged else "clear",
            )
        )

    return ObservedArtifact(
        artifact_id=f"{family.family_id}:A0",
        family_id=family.family_id,
        partition=partition,
        site=family.site,
        object_type=family.object_type,
        reading_direction=reading_direction,
        tokens=tuple(observed_tokens),
    )


def degrade_fixture(
    fixture: SyntheticKnownScript,
    config: DegradationConfig | None = None,
) -> DegradedKnownScript:
    """Apply cumulative degradation after a family-safe deterministic split."""

    effective_config = config or DegradationConfig(seed=fixture.seed)
    if fixture.generator_version != GENERATOR_VERSION:
        raise ValueError(f"unsupported generator_version: {fixture.generator_version}")
    if fixture.external_data_used:
        raise ValueError("the built-in identifiability fixture must not use external data")
    family_ids = [family.family_id for family in fixture.families]
    if len(set(family_ids)) != len(family_ids):
        raise ValueError("truth family ids must be unique")
    if len(family_ids) < 2:
        raise ValueError("at least two truth families are required")

    partition_by_family = _family_split(
        fixture.families,
        test_fraction=effective_config.test_fraction,
        seed=effective_config.seed,
    )
    observations: list[ObservedArtifact] = []
    for family in sorted(fixture.families, key=lambda item: item.family_id):
        base = _degrade_family(
            family,
            partition=partition_by_family[family.family_id],
            config=effective_config,
        )
        observations.append(base)
        if (
            _uniform(effective_config.seed, "duplicate", family.family_id)
            < effective_config.duplicate_rate
        ):
            observations.append(
                ObservedArtifact(
                    artifact_id=f"{family.family_id}:A1",
                    family_id=base.family_id,
                    partition=base.partition,
                    site=base.site,
                    object_type=base.object_type,
                    reading_direction=base.reading_direction,
                    tokens=base.tokens,
                )
            )

    return DegradedKnownScript(
        generator_version=fixture.generator_version,
        degradation_version=DEGRADATION_VERSION,
        config=effective_config,
        observations=tuple(observations),
        family_partitions=tuple(
            (family_id, partition) for family_id, partition in sorted(partition_by_family.items())
        ),
    )


def _truth_index(
    fixture: SyntheticKnownScript,
) -> tuple[dict[str, TruthFamily], dict[str, TruthToken]]:
    families: dict[str, TruthFamily] = {}
    tokens: dict[str, TruthToken] = {}
    for family in fixture.families:
        if family.family_id in families:
            raise ValueError(f"duplicate truth family id: {family.family_id}")
        families[family.family_id] = family
        for token in family.tokens:
            if token.functional_class not in FUNCTIONAL_CLASSES:
                raise ValueError(f"unknown functional class: {token.functional_class}")
            if token.token_key in tokens:
                raise ValueError(f"duplicate truth token key: {token.token_key}")
            tokens[token.token_key] = token
    return families, tokens


def _validate_alignment(
    fixture: SyntheticKnownScript,
    degraded: DegradedKnownScript,
) -> tuple[dict[str, TruthFamily], dict[str, TruthToken], dict[str, Partition]]:
    if degraded.generator_version != fixture.generator_version:
        raise ValueError("fixture and degradation generator versions do not match")
    if degraded.degradation_version != DEGRADATION_VERSION:
        raise ValueError(f"unsupported degradation_version: {degraded.degradation_version}")
    truth_families, truth_tokens = _truth_index(fixture)
    canonical_signs = {token.canonical_sign for token in truth_tokens.values()}

    partition_by_family: dict[str, Partition] = {}
    for family_id, partition in degraded.family_partitions:
        if family_id in partition_by_family:
            raise ValueError(f"duplicate split entry for family: {family_id}")
        if partition not in {"train", "test"}:
            raise ValueError(f"invalid partition for family {family_id}: {partition}")
        partition_by_family[family_id] = partition
    if set(partition_by_family) != set(truth_families):
        raise ValueError("split manifest must contain every truth family exactly once")
    if set(partition_by_family.values()) != {"train", "test"}:
        raise ValueError("split manifest must contain both train and test families")

    artifact_ids: set[str] = set()
    observations_by_family: dict[str, list[ObservedArtifact]] = defaultdict(list)
    for artifact in degraded.observations:
        if artifact.artifact_id in artifact_ids:
            raise ValueError(f"duplicate observed artifact id: {artifact.artifact_id}")
        artifact_ids.add(artifact.artifact_id)
        if artifact.family_id not in truth_families:
            raise ValueError(f"unknown observed family: {artifact.family_id}")
        if partition_by_family[artifact.family_id] != artifact.partition:
            raise ValueError(f"duplicate-family partition leakage: {artifact.family_id}")
        if artifact.site != truth_families[artifact.family_id].site:
            raise ValueError(f"site mismatch for family: {artifact.family_id}")
        if artifact.object_type != truth_families[artifact.family_id].object_type:
            raise ValueError(f"object_type mismatch for family: {artifact.family_id}")

        visual_indices = [token.visual_index for token in artifact.tokens]
        if sorted(visual_indices) != list(range(len(artifact.tokens))):
            raise ValueError(f"visual indices are not a permutation: {artifact.artifact_id}")
        reading_indices = [token.reading_index for token in artifact.tokens]
        if artifact.reading_direction == "unknown":
            if any(index is not None for index in reading_indices):
                raise ValueError("unknown direction must not expose reading indices")
        elif any(index is None for index in reading_indices) or sorted(
            index for index in reading_indices if index is not None
        ) != list(range(len(artifact.tokens))):
            raise ValueError(f"reading indices are not a permutation: {artifact.artifact_id}")

        token_keys: set[str] = set()
        for token in artifact.tokens:
            if token.token_key in token_keys:
                raise ValueError(f"duplicate observed token key: {token.token_key}")
            token_keys.add(token.token_key)
            truth_token = truth_tokens.get(token.token_key)
            if truth_token is None or not token.token_key.startswith(f"{artifact.family_id}:"):
                raise ValueError(
                    f"observed token does not align to its truth family: {token.token_key}"
                )
            if token.sign_id in canonical_signs:
                raise ValueError("observation exposes a canonical truth sign")
            if (token.sign_id is None) != (token.condition == "damaged"):
                raise ValueError(f"damage state is inconsistent: {token.token_key}")
        observations_by_family[artifact.family_id].append(artifact)

    if set(observations_by_family) != set(truth_families):
        raise ValueError("every truth family must have at least one observation")
    for family_id, artifacts in observations_by_family.items():
        signatures = {
            (
                artifact.partition,
                artifact.site,
                artifact.object_type,
                artifact.reading_direction,
                artifact.tokens,
            )
            for artifact in artifacts
        }
        if len(signatures) != 1:
            raise ValueError(f"duplicate observations are not exact family copies: {family_id}")

    expected_degradation = degrade_fixture(fixture, degraded.config)
    if degraded != expected_degradation:
        raise ValueError(
            "degraded observations do not exactly match the deterministic degradation contract"
        )

    return truth_families, truth_tokens, partition_by_family


def _ordered_tokens(artifact: ObservedArtifact) -> list[ObservedToken]:
    if artifact.tokens and all(token.reading_index is not None for token in artifact.tokens):
        return sorted(
            artifact.tokens,
            key=lambda token: (
                token.reading_index if token.reading_index is not None else 0,
                token.visual_index,
            ),
        )
    return sorted(artifact.tokens, key=lambda token: token.visual_index)


def _token_features(
    artifact: ObservedArtifact,
    ordered_tokens: Sequence[ObservedToken],
    index: int,
) -> tuple[tuple[str, str], ...]:
    token = ordered_tokens[index]
    previous = "<BOS>" if index == 0 else (ordered_tokens[index - 1].sign_id or "<DAMAGED>")
    following = (
        "<EOS>"
        if index == len(ordered_tokens) - 1
        else (ordered_tokens[index + 1].sign_id or "<DAMAGED>")
    )
    return (
        ("sign", token.sign_id or "<DAMAGED>"),
        ("position", _position_bucket(index, len(ordered_tokens))),
        ("previous", previous),
        ("following", following),
        ("length", _length_bucket(len(ordered_tokens))),
        ("site", artifact.site),
        ("object_type", artifact.object_type),
        ("direction", artifact.reading_direction),
    )


def _examples(
    degraded: DegradedKnownScript,
    truth_tokens: dict[str, TruthToken],
    *,
    partition: Partition,
    representatives_only: bool,
) -> tuple[list[_Example], float, int]:
    artifacts = sorted(
        (artifact for artifact in degraded.observations if artifact.partition == partition),
        key=lambda artifact: (artifact.family_id, artifact.artifact_id),
    )
    replicas_by_family = Counter(artifact.family_id for artifact in artifacts)
    if representatives_only:
        representatives: dict[str, ObservedArtifact] = {}
        for artifact in artifacts:
            representatives.setdefault(artifact.family_id, artifact)
        artifacts = list(representatives.values())
        replicas_by_family = Counter({family_id: 1 for family_id in representatives})

    examples: list[_Example] = []
    covered_token_fraction = 0.0
    family_ids = set(replicas_by_family)
    for artifact in artifacts:
        ordered = _ordered_tokens(artifact)
        if not ordered:
            continue
        readable_count = sum(token.sign_id is not None for token in ordered)
        covered_token_fraction += readable_count / (
            replicas_by_family[artifact.family_id] * len(ordered)
        )
        if readable_count == 0:
            continue
        per_token_weight = 1.0 / (replicas_by_family[artifact.family_id] * readable_count)
        for ordinal, token in enumerate(ordered):
            if token.sign_id is None:
                continue
            truth = truth_tokens[token.token_key]
            examples.append(
                _Example(
                    family_id=artifact.family_id,
                    token_key=token.token_key,
                    ordinal=ordinal,
                    features=_token_features(artifact, ordered, ordinal),
                    true_class=truth.functional_class,
                    weight=per_token_weight,
                )
            )
    coverage = covered_token_fraction / len(family_ids) if family_ids else 0.0
    return examples, coverage, len(family_ids)


def _weighted_metrics(
    examples: Sequence[_Example],
    predictions: Sequence[FunctionalClass],
    *,
    coverage: float,
    family_count: int,
) -> dict[str, Any]:
    if len(examples) != len(predictions):
        raise ValueError("examples and predictions must have the same length")
    confusion: dict[FunctionalClass, dict[FunctionalClass, float]] = {
        expected: {predicted: 0.0 for predicted in FUNCTIONAL_CLASSES}
        for expected in FUNCTIONAL_CLASSES
    }
    for example, prediction in zip(examples, predictions, strict=True):
        confusion[example.true_class][prediction] += example.weight

    f1_values: list[float] = []
    recalls: list[float] = []
    correct = 0.0
    total = 0.0
    for functional_class in FUNCTIONAL_CLASSES:
        true_positive = confusion[functional_class][functional_class]
        false_positive = sum(
            confusion[other][functional_class]
            for other in FUNCTIONAL_CLASSES
            if other != functional_class
        )
        false_negative = sum(
            confusion[functional_class][other]
            for other in FUNCTIONAL_CLASSES
            if other != functional_class
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive > 0
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative > 0
            else 0.0
        )
        f1_values.append(
            2.0 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
        )
        recalls.append(recall)
        correct += true_positive
        total += sum(confusion[functional_class].values())

    return {
        "macro_f1": fmean(f1_values),
        "balanced_accuracy": fmean(recalls),
        "accuracy": correct / total if total > 0 else 0.0,
        "coverage": coverage,
        "evaluated_token_instances": len(examples),
        "effective_family_count": family_count,
        "confusion_matrix": confusion,
    }


def _predict_metrics(
    model: _CategoricalNaiveBayes,
    examples: Sequence[_Example],
    *,
    coverage: float,
    family_count: int,
) -> dict[str, Any]:
    predictions: list[FunctionalClass] = []
    for example in examples:
        predictions.append(model.predict(example.features))
    return _weighted_metrics(
        examples,
        predictions,
        coverage=coverage,
        family_count=family_count,
    )


def _permuted_family_labels(
    examples: Sequence[_Example],
    *,
    seed: int,
) -> list[FunctionalClass]:
    by_family: dict[str, list[tuple[int, _Example]]] = defaultdict(list)
    for input_index, example in enumerate(examples):
        by_family[example.family_id].append((input_index, example))
    for rows in by_family.values():
        rows.sort(key=lambda item: (item[1].ordinal, item[1].token_key))

    families_by_length: dict[int, list[str]] = defaultdict(list)
    for family_id, rows in by_family.items():
        families_by_length[len(rows)].append(family_id)

    output: list[FunctionalClass | None] = [None] * len(examples)
    rng = random.Random(seed)
    for length, recipient_ids in sorted(families_by_length.items()):
        del length
        recipients = sorted(recipient_ids)
        donors = list(recipients)
        rng.shuffle(donors)
        for recipient_id, donor_id in zip(recipients, donors, strict=True):
            recipient_rows = by_family[recipient_id]
            donor_labels: list[FunctionalClass] = []
            for _, row in by_family[donor_id]:
                donor_labels.append(row.true_class)
            for (input_index, _), label in zip(recipient_rows, donor_labels, strict=True):
                output[input_index] = label

    result: list[FunctionalClass] = []
    for label in output:
        if label is None:
            raise RuntimeError("family-label permutation left an example unassigned")
        result.append(label)
    if Counter(result) != Counter(example.true_class for example in examples):
        raise RuntimeError("family-label permutation did not preserve global class counts")
    return result


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot summarize an empty distribution")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _null_summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean": fmean(values),
        "minimum": min(values),
        "maximum": max(values),
        "p05": _percentile(values, 0.05),
        "p95": _percentile(values, 0.95),
    }


def _validate_gate_arguments(
    *,
    runs: int,
    min_macro_f1: float,
    min_null_delta: float,
    alpha: float,
    min_coverage: float,
) -> None:
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
        raise ValueError("runs must be an integer of at least 1")
    for name, value in (
        ("min_macro_f1", min_macro_f1),
        ("min_null_delta", min_null_delta),
        ("alpha", alpha),
        ("min_coverage", min_coverage),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{name} must be a finite number")
    if not 0.0 <= min_macro_f1 <= 1.0:
        raise ValueError("min_macro_f1 must be in [0, 1]")
    if not 0.0 <= min_null_delta <= 1.0:
        raise ValueError("min_null_delta must be in [0, 1]")
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    if not 0.0 <= min_coverage <= 1.0:
        raise ValueError("min_coverage must be in [0, 1]")


def _split_digest(degraded: DegradedKnownScript) -> str:
    material = "\n".join(
        f"{family_id}\t{partition}" for family_id, partition in degraded.family_partitions
    )
    return f"sha256:{hashlib.sha256(material.encode()).hexdigest()}"


def _degradation_counts(degraded: DegradedKnownScript) -> dict[str, int]:
    family_counts = Counter(artifact.partition for artifact in degraded.observations)
    unique_families = {
        partition: {
            artifact.family_id
            for artifact in degraded.observations
            if artifact.partition == partition
        }
        for partition in ("train", "test")
    }
    tokens = [token for artifact in degraded.observations for token in artifact.tokens]
    return {
        "families": len(degraded.family_partitions),
        "train_families": len(unique_families["train"]),
        "test_families": len(unique_families["test"]),
        "artifacts": len(degraded.observations),
        "duplicate_artifacts": len(degraded.observations) - len(degraded.family_partitions),
        "train_artifacts": family_counts["train"],
        "test_artifacts": family_counts["test"],
        "token_instances": len(tokens),
        "damaged_token_instances": sum(token.sign_id is None for token in tokens),
        "allograph_token_instances": sum(
            token.sign_id is not None and token.sign_id.endswith(("a", "b")) for token in tokens
        ),
        "unknown_direction_artifacts": sum(
            artifact.reading_direction == "unknown" for artifact in degraded.observations
        ),
    }


def _base_report(
    degraded: DegradedKnownScript,
    *,
    anchors_available: bool,
    gate_status: GateStatus,
) -> dict[str, Any]:
    return {
        "analysis": "synthetic_known_script_identifiability_gate",
        "generator_version": degraded.generator_version,
        "degradation_version": degraded.degradation_version,
        "synthetic_rights": {
            "license_id": "CC0-1.0",
            "external_data_used": False,
        },
        "degradation": asdict(degraded.config),
        "split": {
            "unit": "duplicate_family",
            "performed_before_degradation_and_duplication": True,
            "digest": _split_digest(degraded),
        },
        "observation_contract": {
            "word_boundaries_present": False,
            "canonical_sign_field_present": False,
            "functional_class_field_present": False,
        },
        "counts": _degradation_counts(degraded),
        "anchors_available": anchors_available,
        "gate_status": gate_status,
        "scientific_scope": (
            "method-eligibility test on project-authored synthetic known truth only; "
            "does not identify an Indus language, phonetic value, semantic value, "
            "translation, decipherment, authorship, or prize eligibility"
        ),
    }


def evaluate_identifiability(
    fixture: SyntheticKnownScript,
    degraded: DegradedKnownScript,
    *,
    anchors_available: bool = True,
    runs: int = 99,
    seed: int = 0,
    min_macro_f1: float = 0.60,
    min_null_delta: float = 0.10,
    alpha: float = 0.05,
    min_coverage: float = 0.80,
) -> dict[str, Any]:
    """Evaluate named functional-class recovery against a family-label null.

    Functional labels are supplied only for readable training occurrences.
    Test labels remain evaluator-side ground truth.  If training anchors are
    unavailable, named classes are label-switching-equivalent; the function
    returns ``not_identifiable`` and intentionally emits no F1 metric.
    """

    if not isinstance(anchors_available, bool):
        raise ValueError("anchors_available must be a boolean")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    _validate_gate_arguments(
        runs=runs,
        min_macro_f1=min_macro_f1,
        min_null_delta=min_null_delta,
        alpha=alpha,
        min_coverage=min_coverage,
    )
    _, truth_tokens, _ = _validate_alignment(fixture, degraded)

    if not anchors_available:
        report = _base_report(
            degraded,
            anchors_available=False,
            gate_status="not_identifiable",
        )
        report["identifiability_status"] = "named_classes_not_identifiable_without_anchors"
        report["reason"] = (
            "Without train-side class anchors, arbitrary permutations of class names are "
            "observationally equivalent; named-class F1 is therefore not computed."
        )
        return report

    train_examples, train_coverage, train_family_count = _examples(
        degraded,
        truth_tokens,
        partition="train",
        representatives_only=True,
    )
    test_examples, test_coverage, test_family_count = _examples(
        degraded,
        truth_tokens,
        partition="test",
        representatives_only=True,
    )
    if not train_examples or not test_examples:
        report = _base_report(
            degraded,
            anchors_available=True,
            gate_status="insufficient_evidence",
        )
        report["identifiability_status"] = "insufficient_readable_tokens"
        report["reason"] = (
            "Readable anchored train tokens and readable held-out test tokens are required."
        )
        report["coverage"] = {
            "train": train_coverage,
            "test": test_coverage,
        }
        return report

    observed_model = _CategoricalNaiveBayes().fit(train_examples)
    observed_metrics = _predict_metrics(
        observed_model,
        test_examples,
        coverage=test_coverage,
        family_count=test_family_count,
    )

    class_weights: dict[FunctionalClass, float] = {
        functional_class: 0.0 for functional_class in FUNCTIONAL_CLASSES
    }
    for example in train_examples:
        class_weights[example.true_class] += example.weight
    majority_class: FunctionalClass = FUNCTIONAL_CLASSES[0]
    for candidate in FUNCTIONAL_CLASSES[1:]:
        if class_weights[candidate] > class_weights[majority_class]:
            majority_class = candidate
    majority_predictions: list[FunctionalClass] = []
    for _ in test_examples:
        majority_predictions.append(majority_class)
    majority_metrics = _weighted_metrics(
        test_examples,
        majority_predictions,
        coverage=test_coverage,
        family_count=test_family_count,
    )

    null_macro_f1: list[float] = []
    run_values: list[dict[str, float | int]] = []
    for offset in range(runs):
        run_seed = seed + offset
        permuted_labels = _permuted_family_labels(train_examples, seed=run_seed)
        null_model = _CategoricalNaiveBayes().fit(train_examples, permuted_labels)
        null_metrics = _predict_metrics(
            null_model,
            test_examples,
            coverage=test_coverage,
            family_count=test_family_count,
        )
        macro_f1 = float(null_metrics["macro_f1"])
        null_macro_f1.append(macro_f1)
        run_values.append({"seed": run_seed, "macro_f1": macro_f1})

    observed_macro_f1 = float(observed_metrics["macro_f1"])
    permutation_p = (1 + sum(value >= observed_macro_f1 for value in null_macro_f1)) / (runs + 1)
    permutation_summary = _null_summary(null_macro_f1)
    strongest_null = max(
        permutation_summary["p95"],
        float(majority_metrics["macro_f1"]),
    )
    null_delta = observed_macro_f1 - strongest_null
    criteria = {
        "macro_f1": observed_macro_f1 >= min_macro_f1,
        "null_delta": null_delta >= min_null_delta,
        "permutation_p_value": permutation_p <= alpha,
        "coverage": test_coverage >= min_coverage,
    }
    gate_status: GateStatus = "go" if all(criteria.values()) else "no_go"

    report = _base_report(
        degraded,
        anchors_available=True,
        gate_status=gate_status,
    )
    report.update(
        {
            "identifiability_status": (
                "recoverable_under_synthetic_known_truth"
                if gate_status == "go"
                else "not_recoverable_at_configured_thresholds"
            ),
            "model": {
                "kind": "laplace_smoothed_categorical_naive_bayes",
                "features": [
                    "observed_sign",
                    "position_bucket",
                    "adjacent_observed_signs",
                    "sequence_length",
                    "site",
                    "object_type",
                    "reported_direction",
                ],
                "train_unit": "one_observation_per_duplicate_family",
                "test_unit": "one_observation_per_duplicate_family",
                "weighting": "equal_total_weight_per_readable_duplicate_family",
            },
            "coverage": {
                "train": train_coverage,
                "test": test_coverage,
                "train_family_count": train_family_count,
                "test_family_count": test_family_count,
            },
            "observed": observed_metrics,
            "majority_null": {
                "predicted_class": majority_class,
                "metrics": majority_metrics,
            },
            "permutation_null": {
                "kind": "train_label_vector_permutation_within_family_length_strata",
                "preserves": [
                    "train_test_partition",
                    "duplicate_family_boundary",
                    "family_readable_token_count",
                    "whole_family_label_vectors_within_each_length_stratum",
                    "global_functional_class_counts",
                ],
                "randomization_scope": (
                    "uniform whole-family-vector reassignment within each readable-length "
                    "stratum; permutation fixed points are allowed and singleton strata "
                    "necessarily remain unchanged"
                ),
                "runs": runs,
                "seed_start": seed,
                "seed_schedule": "seed_start + zero_based_run_index",
                "macro_f1": permutation_summary,
                "empirical_p_value_greater_or_equal": permutation_p,
                "run_values": run_values,
            },
            "decision": {
                "thresholds": {
                    "min_macro_f1": min_macro_f1,
                    "min_null_delta": min_null_delta,
                    "alpha": alpha,
                    "min_coverage": min_coverage,
                },
                "threshold_provenance": (
                    "current code defaults or caller-supplied values; not an independently "
                    "preregistered threshold set"
                ),
                "null_reference": "maximum_of_majority_macro_f1_and_permutation_p95",
                "strongest_null_macro_f1": strongest_null,
                "observed_minus_strongest_null": null_delta,
                "criteria": criteria,
            },
        }
    )
    return report


def run_identifiability_gate(
    *,
    seed: int = 0,
    family_count: int = 96,
    config: DegradationConfig | None = None,
    anchors_available: bool = True,
    runs: int = 99,
    null_seed: int | None = None,
    min_macro_f1: float = 0.60,
    min_null_delta: float = 0.10,
    alpha: float = 0.05,
    min_coverage: float = 0.80,
) -> dict[str, Any]:
    """Generate, degrade, and evaluate the built-in known-truth fixture."""

    fixture = generate_synthetic_known_script(seed=seed, family_count=family_count)
    degraded = degrade_fixture(fixture, config or DegradationConfig(seed=seed))
    return evaluate_identifiability(
        fixture,
        degraded,
        anchors_available=anchors_available,
        runs=runs,
        seed=seed if null_seed is None else null_seed,
        min_macro_f1=min_macro_f1,
        min_null_delta=min_null_delta,
        alpha=alpha,
        min_coverage=min_coverage,
    )
