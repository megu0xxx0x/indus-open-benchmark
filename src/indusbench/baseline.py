"""Transparent structural baselines for Indus sign sequences.

These models score sign regularities only. They do not infer language,
phonetic values, or translations.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, Self, TypeAlias, cast

ArtifactRecord: TypeAlias = Mapping[str, object]
SignSequence: TypeAlias = tuple[str, ...]
CorpusInput: TypeAlias = ArtifactRecord | Iterable[object]

_BOS = "\0<BOS>"
UNKNOWN_SIGN = "<UNK>"


@dataclass(frozen=True)
class HeldoutScore:
    """Token-level language-model score on held-out sequences."""

    sequence_count: int
    token_count: int
    log_likelihood: float
    mean_negative_log_likelihood: float
    perplexity: float


@dataclass(frozen=True)
class MissingSignScore:
    """Masked-sign prediction metrics over all eligible token positions."""

    sequence_count: int
    evaluated_tokens: int
    skipped_oov_tokens: int
    top1_correct: int
    accuracy: float
    mean_log_probability: float
    mean_reciprocal_rank: float


class ScoringBaseline(Protocol):
    @property
    def vocabulary(self) -> tuple[str, ...]: ...

    def sequence_log_probability(self, sequence: Iterable[object]) -> float: ...

    def predict_missing(
        self,
        sequence: Sequence[object],
        missing_index: int,
    ) -> dict[str, float]: ...


def _stable_sign(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _numeric_index(token: Mapping[str, object], field: str) -> tuple[int, float]:
    value = token.get(field)
    if isinstance(value, bool):
        return 1, 0.0
    if isinstance(value, (int, float)):
        return 0, float(value)
    if isinstance(value, str):
        try:
            return 0, float(value.strip())
        except ValueError:
            pass
    return 1, 0.0


def _normalize_token_slots(
    tokens: Sequence[object],
    *,
    reading_direction: object = None,
) -> tuple[str | None, ...]:
    indexed_tokens = list(enumerate(tokens))
    if indexed_tokens and all(
        isinstance(token, Mapping) and _numeric_index(token, "reading_index")[0] == 0
        for _, token in indexed_tokens
    ):
        indexed_tokens.sort(
            key=lambda item: (
                _numeric_index(item[1], "reading_index")[1]
                if isinstance(item[1], Mapping)
                else 0.0,
                item[0],
            )
        )
    elif indexed_tokens and all(
        isinstance(token, Mapping) and _numeric_index(token, "visual_index")[0] == 0
        for _, token in indexed_tokens
    ):
        indexed_tokens.sort(
            key=lambda item: (
                _numeric_index(item[1], "visual_index")[1] if isinstance(item[1], Mapping) else 0.0,
                item[0],
            )
        )
        if reading_direction in {"right_to_left", "bottom_to_top"}:
            indexed_tokens.reverse()

    signs: list[str | None] = []
    for _, token in indexed_tokens:
        sign = (
            _stable_sign(token.get("sign_id"))
            if isinstance(token, Mapping)
            else _stable_sign(token)
        )
        signs.append(sign)
    return tuple(signs)


def _observed_segments(slots: Sequence[str | None]) -> list[SignSequence]:
    segments: list[SignSequence] = []
    current: list[str] = []
    for sign in slots:
        if sign is None:
            if current:
                segments.append(tuple(current))
                current = []
        else:
            current.append(sign)
    if current:
        segments.append(tuple(current))
    return segments


def _extract_record_sequences(record: ArtifactRecord) -> list[SignSequence]:
    sequences: list[SignSequence] = []

    def add_line(line: object) -> None:
        tokens = line.get("tokens") if isinstance(line, Mapping) else line
        if isinstance(tokens, Sequence) and not isinstance(tokens, (str, bytes)):
            reading_direction = line.get("reading_direction") if isinstance(line, Mapping) else None
            slots = _normalize_token_slots(
                tokens,
                reading_direction=reading_direction,
            )
            sequences.extend(_observed_segments(slots))

    sides = record.get("sides")
    if isinstance(sides, Sequence) and not isinstance(sides, (str, bytes)):
        for side in sides:
            if not isinstance(side, Mapping):
                continue
            lines = side.get("lines")
            if isinstance(lines, Sequence) and not isinstance(lines, (str, bytes)):
                for line in lines:
                    add_line(line)
    else:
        lines = record.get("lines")
        if isinstance(lines, Sequence) and not isinstance(lines, (str, bytes)):
            for line in lines:
                add_line(line)
        elif "tokens" in record:
            add_line(record)
    return sequences


def extract_sequences(data: CorpusInput) -> list[SignSequence]:
    """Extract reading-order sign sequences from records or sequence iterables."""
    if isinstance(data, Mapping):
        return _extract_record_sequences(cast(ArtifactRecord, data))

    materialized: list[object] = list(data)
    if not materialized:
        return []
    if all(isinstance(item, Mapping) for item in materialized):
        sequences: list[SignSequence] = []
        for record in materialized:
            if isinstance(record, Mapping):
                sequences.extend(_extract_record_sequences(cast(ArtifactRecord, record)))
        return sequences
    if all(isinstance(item, str) for item in materialized):
        return _observed_segments(_normalize_token_slots(materialized))

    sequences = []
    for index, sequence in enumerate(materialized):
        if not isinstance(sequence, Sequence) or isinstance(sequence, (str, bytes)):
            raise TypeError(f"sequence {index} is not a non-string sequence")
        sequences.extend(_observed_segments(_normalize_token_slots(sequence)))
    return sequences


def _require_fitted(token_count: int) -> None:
    if token_count == 0:
        raise RuntimeError("baseline is not fitted")


def _validate_missing_index(sequence: Sequence[object], missing_index: int) -> None:
    if not -len(sequence) <= missing_index < len(sequence):
        raise IndexError("missing_index is outside the sequence")


def _score_from_log_likelihoods(
    log_likelihoods: Iterable[float],
    *,
    sequence_count: int,
) -> HeldoutScore:
    values = list(log_likelihoods)
    if not values:
        raise ValueError("held-out data contains no sign tokens")
    log_likelihood = sum(values)
    token_count = len(values)
    if log_likelihood == -math.inf:
        mean_nll = math.inf
        perplexity = math.inf
    else:
        mean_nll = -log_likelihood / token_count
        try:
            perplexity = math.exp(mean_nll)
        except OverflowError:
            perplexity = math.inf
    return HeldoutScore(
        sequence_count=sequence_count,
        token_count=token_count,
        log_likelihood=log_likelihood,
        mean_negative_log_likelihood=mean_nll,
        perplexity=perplexity,
    )


class UnigramBaseline:
    """Maximum-likelihood sign-frequency baseline."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._token_count = 0

    @property
    def vocabulary(self) -> tuple[str, ...]:
        return tuple(sorted(self._counts))

    def fit(self, data: CorpusInput) -> Self:
        sequences = extract_sequences(data)
        counts = Counter(sign for sequence in sequences for sign in sequence)
        if not counts:
            raise ValueError("training data contains no sign tokens")
        self._counts = counts
        self._token_count = counts.total()
        return self

    def token_probability(self, sign: object) -> float:
        _require_fitted(self._token_count)
        normalized = _stable_sign(sign)
        if normalized is None:
            return 0.0
        return self._counts[normalized] / self._token_count

    def sequence_log_probability(self, sequence: Iterable[object]) -> float:
        _require_fitted(self._token_count)
        log_probability = 0.0
        for sign in sequence:
            probability = self.token_probability(sign)
            if probability == 0.0:
                return -math.inf
            log_probability += math.log(probability)
        return log_probability

    def predict_missing(
        self,
        sequence: Sequence[object],
        missing_index: int,
    ) -> dict[str, float]:
        _require_fitted(self._token_count)
        _validate_missing_index(sequence, missing_index)
        return {sign: self._counts[sign] / self._token_count for sign in self.vocabulary}

    def score_heldout(self, data: CorpusInput) -> HeldoutScore:
        sequences = extract_sequences(data)
        token_logs: list[float] = []
        for sequence in sequences:
            for sign in sequence:
                probability = self.token_probability(sign)
                token_logs.append(math.log(probability) if probability else -math.inf)
        return _score_from_log_likelihoods(
            token_logs,
            sequence_count=len(sequences),
        )


class AddOneNGramBaseline:
    """Left-to-right n-gram model with Laplace (add-one) smoothing."""

    def __init__(self, order: int = 2) -> None:
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ValueError("order must be a positive integer")
        self.order = order
        self._vocabulary: tuple[str, ...] = ()
        self._ngram_counts: dict[tuple[str, ...], Counter[str]] = {}
        self._context_counts: Counter[tuple[str, ...]] = Counter()
        self._token_count = 0

    @property
    def vocabulary(self) -> tuple[str, ...]:
        return self._vocabulary

    def _canonical_sign(self, sign: object) -> str:
        normalized = _stable_sign(sign)
        if normalized in self._vocabulary:
            return normalized
        return UNKNOWN_SIGN

    def _context_for(self, prefix: Sequence[object]) -> tuple[str, ...]:
        if self.order == 1:
            return ()
        normalized = [self._canonical_sign(sign) for sign in prefix]
        padded = ([_BOS] * (self.order - 1)) + normalized
        return tuple(padded[-(self.order - 1) :])

    def fit(self, data: CorpusInput) -> Self:
        sequences = extract_sequences(data)
        vocabulary = sorted({sign for sequence in sequences for sign in sequence})
        if not vocabulary:
            raise ValueError("training data contains no sign tokens")
        if UNKNOWN_SIGN in vocabulary or _BOS in vocabulary:
            raise ValueError("training data contains a reserved baseline token")

        self._vocabulary = tuple(vocabulary)
        ngram_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
        context_counts: Counter[tuple[str, ...]] = Counter()
        token_count = 0
        for sequence in sequences:
            prefix: list[str] = []
            for sign in sequence:
                context = self._context_for(prefix)
                ngram_counts[context][sign] += 1
                context_counts[context] += 1
                token_count += 1
                prefix.append(sign)
        self._ngram_counts = dict(ngram_counts)
        self._context_counts = context_counts
        self._token_count = token_count
        return self

    def token_probability(self, sign: object, prefix: Sequence[object] = ()) -> float:
        _require_fitted(self._token_count)
        context = self._context_for(prefix)
        target = self._canonical_sign(sign)
        outcome_count = len(self._vocabulary) + 1
        numerator = self._ngram_counts.get(context, Counter())[target] + 1
        denominator = self._context_counts[context] + outcome_count
        return numerator / denominator

    def sequence_log_probability(self, sequence: Iterable[object]) -> float:
        _require_fitted(self._token_count)
        normalized = [sign for item in sequence if (sign := _stable_sign(item)) is not None]
        log_probability = 0.0
        for index, sign in enumerate(normalized):
            probability = self.token_probability(sign, normalized[:index])
            log_probability += math.log(probability)
        return log_probability

    def predict_missing(
        self,
        sequence: Sequence[object],
        missing_index: int,
    ) -> dict[str, float]:
        """Return candidate probabilities using both affected left/right n-grams."""
        _require_fitted(self._token_count)
        _validate_missing_index(sequence, missing_index)
        normalized = [
            sign if (sign := _stable_sign(item)) is not None else UNKNOWN_SIGN for item in sequence
        ]
        normalized_index = missing_index % len(normalized)
        log_scores: dict[str, float] = {}
        for candidate in self._vocabulary:
            candidate_sequence = normalized.copy()
            candidate_sequence[normalized_index] = candidate
            affected_stop = min(
                len(candidate_sequence),
                normalized_index + self.order,
            )
            log_score = 0.0
            for position in range(normalized_index, affected_stop):
                context_start = max(0, position - (self.order - 1))
                context_values = candidate_sequence[context_start:position]
                context = (
                    tuple([_BOS] * (self.order - 1 - len(context_values)) + context_values)
                    if self.order > 1
                    else ()
                )
                sign = self._canonical_sign(candidate_sequence[position])
                count = self._ngram_counts.get(context, {}).get(sign, 0)
                denominator = self._context_counts.get(context, 0) + len(self._vocabulary) + 1
                log_score += math.log((count + 1) / denominator)
            log_scores[candidate] = log_score

        maximum = max(log_scores.values())
        weights = {sign: math.exp(log_score - maximum) for sign, log_score in log_scores.items()}
        normalizer = sum(weights.values())
        return {sign: weight / normalizer for sign, weight in weights.items()}

    def score_heldout(self, data: CorpusInput) -> HeldoutScore:
        sequences = extract_sequences(data)
        token_logs: list[float] = []
        for sequence in sequences:
            for index, sign in enumerate(sequence):
                token_logs.append(math.log(self.token_probability(sign, sequence[:index])))
        return _score_from_log_likelihoods(
            token_logs,
            sequence_count=len(sequences),
        )


def score_missing_signs(
    model: ScoringBaseline,
    data: CorpusInput,
    *,
    skip_oov: bool = True,
) -> MissingSignScore:
    """Evaluate masked-sign top-1 accuracy, log score, and reciprocal rank."""
    sequences = extract_sequences(data)
    vocabulary = set(model.vocabulary)
    evaluated = 0
    skipped = 0
    correct = 0
    log_probability_sum = 0.0
    reciprocal_rank_sum = 0.0

    for sequence in sequences:
        for missing_index, truth in enumerate(sequence):
            if truth not in vocabulary:
                if skip_oov:
                    skipped += 1
                    continue
                raise ValueError(f"held-out sign {truth!r} is outside the model vocabulary")
            probabilities = model.predict_missing(sequence, missing_index)
            ranked = sorted(probabilities, key=lambda sign: (-probabilities[sign], sign))
            rank = ranked.index(truth) + 1
            truth_probability = probabilities[truth]
            evaluated += 1
            correct += rank == 1
            log_probability_sum += math.log(truth_probability)
            reciprocal_rank_sum += 1.0 / rank

    if evaluated == 0:
        raise ValueError("held-out data contains no in-vocabulary sign tokens")
    return MissingSignScore(
        sequence_count=len(sequences),
        evaluated_tokens=evaluated,
        skipped_oov_tokens=skipped,
        top1_correct=correct,
        accuracy=correct / evaluated,
        mean_log_probability=log_probability_sum / evaluated,
        mean_reciprocal_rank=reciprocal_rank_sum / evaluated,
    )
