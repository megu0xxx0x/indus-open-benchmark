"""Target-local, truth-free corpus profiling for V4 development.

The primary transform is leave-one-family-out (LOFO). Each gateway family is
represented by one observation document, and its features are derived from
every other document in the same fitted corpus.
Opaque observation IDs are used only as internal equality keys.  Returned
values are either closed categories or finite unit scalars; no identity is
serialized.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, TypeAlias, cast

from indusbench.v3dev.contracts import V3ObservationLine
from indusbench.v3dev.sequence import structural_feature_rows
from indusbench.v4dev.contracts import (
    V4_FEATURE_ABLATIONS,
    V4_PROFILE_MODES,
    FeatureRow,
    FeatureValue,
    V4FeatureAblation,
    V4FeatureCorpus,
    V4FeatureDocument,
    V4FeatureLine,
    V4ObservationCorpus,
    V4ObservationDocument,
    V4ProfileMode,
)

V4_CORPUS_PROFILE_VERSION: Final = "v4-truth-free-lofo-profile-v1"

LOCAL_FEATURE_NAMES: Final = (
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
)

PROFILE_FEATURE_NAMES: Final = (
    "type_support",
    "type_frequency",
    "family_dispersion",
    "line_dispersion",
    "family_entropy",
    "type_initial_tendency",
    "type_final_tendency",
    "type_mean_position",
    "type_position_variance",
    "left_context_excess_diversity",
    "left_context_entropy",
    "right_context_excess_diversity",
    "right_context_entropy",
    "type_repeat_in_line_rate",
    "type_same_left_rate",
    "type_same_right_rate",
    "left_neighbor_commonness",
    "right_neighbor_commonness",
    "type_evidence",
    "type_diversity_evidence",
    "initial_tendency_interaction",
    "final_tendency_interaction",
    "position_agreement",
    "neighbor_equality_repetition_interaction",
)

FEATURE_NAMES_BY_ABLATION: Final = {
    "local": LOCAL_FEATURE_NAMES,
    "full": LOCAL_FEATURE_NAMES + PROFILE_FEATURE_NAMES,
}

_PUBLIC_COMMITMENT_DOMAIN = b"indusbench:v4:truth-free-corpus-commitment:v1\x00"
_DAMAGED_NEUTRAL = "DAMAGED_NEUTRAL"
_UNSEEN = "UNSEEN"

_ContextKey: TypeAlias = tuple[str, str]


class V4CorpusStatisticsError(ValueError):
    """Raised when V4 truth-free profiling violates its closed contract."""


@dataclass(frozen=True, slots=True)
class _Occurrence:
    document_index: int
    line_index: int
    token_index: int
    line_length: int
    position: float
    initial: bool
    final: bool
    left_context: _ContextKey
    right_context: _ContextKey
    repeated_in_line: bool


@dataclass(frozen=True, slots=True)
class _GlobalPriors:
    initial: float
    final: float
    mean_position: float
    four_position_variance: float
    repeated_in_line: float
    same_left: float
    same_right: float


@dataclass(frozen=True, slots=True)
class _ProfileStatistics:
    document_count: int
    line_count: int
    token_count: int
    occurrences: Mapping[str, tuple[_Occurrence, ...]]
    priors: _GlobalPriors


def _validate_ablation(ablation: object) -> V4FeatureAblation:
    if ablation not in V4_FEATURE_ABLATIONS:
        raise V4CorpusStatisticsError("V4 feature ablation must be local or full")
    return cast(V4FeatureAblation, ablation)


def _validate_profile_mode(profile_mode: object) -> V4ProfileMode:
    if profile_mode not in V4_PROFILE_MODES:
        raise V4CorpusStatisticsError("V4 profile mode must be lofo or self_inclusive")
    return cast(V4ProfileMode, profile_mode)


def _position(index: int, length: int) -> float:
    return 0.5 if length == 1 else index / (length - 1)


def _context(
    tokens: Sequence[object],
    index: int,
    neighbor_index: int,
    boundary: str,
) -> _ContextKey:
    if neighbor_index < 0 or neighbor_index >= len(tokens):
        return ("boundary", boundary)
    neighbor = tokens[neighbor_index]
    observation_id = getattr(neighbor, "observation_id", None)
    damaged = getattr(neighbor, "damaged", None)
    if damaged is True or observation_id is None:
        return ("damaged", "DAMAGED")
    if not isinstance(observation_id, str):
        raise V4CorpusStatisticsError("neighbor observation ID violates the V3 contract")
    return ("observed", observation_id)


def _population_variance(values: Sequence[float], mean: float) -> float:
    if not values:
        return 0.0
    return math.fsum((value - mean) ** 2 for value in values) / len(values)


def _clamp_unit(value: float) -> float:
    if not math.isfinite(value):
        raise V4CorpusStatisticsError("profile scalar must be finite")
    return min(1.0, max(0.0, value))


def _support_bucket(count: int) -> str:
    if count <= 0:
        return _UNSEEN
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 4:
        return "3-4"
    if count <= 8:
        return "5-8"
    if count <= 16:
        return "9-16"
    return "17+"


def _entropy(counts: Iterable[int]) -> float:
    positive = tuple(count for count in counts if count > 0)
    total = sum(positive)
    if total <= 0:
        return 0.0
    return -math.fsum((count / total) * math.log(count / total) for count in positive)


def _canonical_payload(corpus: V4ObservationCorpus) -> object:
    equality_codes: dict[str, int] = {}
    documents: list[object] = []
    for document in corpus.documents:
        lines: list[object] = []
        for line in document.lines:
            tokens: list[object] = []
            for token in line.tokens:
                if token.observation_id is None:
                    rendered_id: object = None
                else:
                    rendered_id = equality_codes.setdefault(
                        token.observation_id, len(equality_codes)
                    )
                tokens.append((rendered_id, token.damaged))
            lines.append((line.line_ordinal, line.reported_direction, tokens))
        documents.append(lines)
    return documents


def _commitment(corpus: V4ObservationCorpus) -> str:
    payload = json.dumps(
        _canonical_payload(corpus),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(_PUBLIC_COMMITMENT_DOMAIN)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def _build_statistics(documents: Sequence[V4ObservationDocument]) -> _ProfileStatistics:
    occurrences: dict[str, list[_Occurrence]] = defaultdict(list)
    all_positions: list[float] = []
    observed_tokens = 0
    initial_count = 0
    final_count = 0
    repeated_count = 0
    same_left_count = 0
    same_right_count = 0
    line_count = 0

    for document_index, document in enumerate(documents):
        for line_index, line in enumerate(document.lines):
            line_count += 1
            tokens = line.tokens
            line_counts = Counter(
                token.observation_id
                for token in tokens
                if token.observation_id is not None and not token.damaged
            )
            for token_index, token in enumerate(tokens):
                observation_id = token.observation_id
                if observation_id is None or token.damaged:
                    continue
                position = _position(token_index, len(tokens))
                left = _context(tokens, token_index, token_index - 1, "BOS")
                right = _context(tokens, token_index, token_index + 1, "EOS")
                repeated = line_counts[observation_id] > 1
                occurrence = _Occurrence(
                    document_index=document_index,
                    line_index=line_index,
                    token_index=token_index,
                    line_length=len(tokens),
                    position=position,
                    initial=token_index == 0,
                    final=token_index == len(tokens) - 1,
                    left_context=left,
                    right_context=right,
                    repeated_in_line=repeated,
                )
                occurrences[observation_id].append(occurrence)
                observed_tokens += 1
                all_positions.append(position)
                initial_count += occurrence.initial
                final_count += occurrence.final
                repeated_count += repeated
                same_left_count += left == ("observed", observation_id)
                same_right_count += right == ("observed", observation_id)

    if observed_tokens:
        mean_position = math.fsum(all_positions) / observed_tokens
        priors = _GlobalPriors(
            initial=initial_count / observed_tokens,
            final=final_count / observed_tokens,
            mean_position=mean_position,
            four_position_variance=_clamp_unit(
                4.0 * _population_variance(all_positions, mean_position)
            ),
            repeated_in_line=repeated_count / observed_tokens,
            same_left=same_left_count / observed_tokens,
            same_right=same_right_count / observed_tokens,
        )
    else:
        priors = _GlobalPriors(
            initial=0.0,
            final=0.0,
            mean_position=0.5,
            four_position_variance=0.0,
            repeated_in_line=0.0,
            same_left=0.0,
            same_right=0.0,
        )

    return _ProfileStatistics(
        document_count=len(documents),
        line_count=line_count,
        token_count=observed_tokens,
        occurrences={observation_id: tuple(items) for observation_id, items in occurrences.items()},
        priors=priors,
    )


def _shrunk(raw: float, global_prior: float, reliability: float) -> float:
    return _clamp_unit(global_prior + reliability * (raw - global_prior))


def _context_metrics(
    occurrences: Sequence[_Occurrence],
    *,
    side: str,
    diversity_reliability: float,
) -> tuple[float, float]:
    if side == "left":
        contexts = tuple(occurrence.left_context for occurrence in occurrences)
    elif side == "right":
        contexts = tuple(occurrence.right_context for occurrence in occurrences)
    else:
        raise AssertionError("context side must be left or right")
    count = len(contexts)
    if count <= 1:
        return 0.0, 0.0
    context_counts = Counter(contexts)
    excess_diversity = diversity_reliability * (len(context_counts) - 1) / (count - 1)
    normalized_entropy = diversity_reliability * _entropy(context_counts.values()) / math.log(count)
    return _clamp_unit(excess_diversity), _clamp_unit(normalized_entropy)


def _type_scalars(
    observation_id: str,
    statistics: _ProfileStatistics,
) -> Mapping[str, float] | None:
    occurrences = statistics.occurrences.get(observation_id)
    if not occurrences:
        return None

    count = len(occurrences)
    document_counts = Counter(occurrence.document_index for occurrence in occurrences)
    line_keys = {(occurrence.document_index, occurrence.line_index) for occurrence in occurrences}
    document_support = len(document_counts)
    line_support = len(line_keys)
    reliability = count / (count + 4)
    diversity_reliability = (count - 1) / (count + 3) if count > 1 else 0.0

    positions = tuple(occurrence.position for occurrence in occurrences)
    mean_position = math.fsum(positions) / count
    raw_four_variance = _clamp_unit(4.0 * _population_variance(positions, mean_position))
    raw_initial = sum(occurrence.initial for occurrence in occurrences) / count
    raw_final = sum(occurrence.final for occurrence in occurrences) / count
    raw_repeated = sum(occurrence.repeated_in_line for occurrence in occurrences) / count
    raw_same_left = (
        sum(occurrence.left_context == ("observed", observation_id) for occurrence in occurrences)
        / count
    )
    raw_same_right = (
        sum(occurrence.right_context == ("observed", observation_id) for occurrence in occurrences)
        / count
    )

    family_entropy = 0.0
    entropy_denominator_support = min(count, document_support)
    if entropy_denominator_support > 1:
        family_entropy = (
            diversity_reliability
            * _entropy(document_counts.values())
            / math.log(entropy_denominator_support)
        )
    left_diversity, left_entropy = _context_metrics(
        occurrences,
        side="left",
        diversity_reliability=diversity_reliability,
    )
    right_diversity, right_entropy = _context_metrics(
        occurrences,
        side="right",
        diversity_reliability=diversity_reliability,
    )

    token_denominator = math.log1p(max(statistics.token_count, 2))
    document_denominator = math.log1p(max(statistics.document_count, 2))
    line_denominator = math.log1p(max(statistics.line_count, 2))
    priors = statistics.priors
    return {
        "frequency": _clamp_unit(math.log1p(count) / token_denominator),
        "family_dispersion": _clamp_unit(math.log1p(document_support) / document_denominator),
        "line_dispersion": _clamp_unit(math.log1p(line_support) / line_denominator),
        "family_entropy": _clamp_unit(family_entropy),
        "initial": _shrunk(raw_initial, priors.initial, reliability),
        "final": _shrunk(raw_final, priors.final, reliability),
        "mean_position": _shrunk(mean_position, priors.mean_position, reliability),
        "position_variance": _shrunk(
            raw_four_variance,
            priors.four_position_variance,
            reliability,
        ),
        "left_context_diversity": left_diversity,
        "left_context_entropy": left_entropy,
        "right_context_diversity": right_diversity,
        "right_context_entropy": right_entropy,
        "repeat_in_line": _shrunk(
            raw_repeated,
            priors.repeated_in_line,
            reliability,
        ),
        "same_left": _shrunk(raw_same_left, priors.same_left, reliability),
        "same_right": _shrunk(raw_same_right, priors.same_right, reliability),
        "evidence": reliability,
        "diversity_evidence": diversity_reliability,
    }


def _neighbor_commonness(
    line: V3ObservationLine,
    token_index: int,
    neighbor_index: int,
    boundary: str,
    statistics: _ProfileStatistics,
) -> FeatureValue:
    if neighbor_index < 0 or neighbor_index >= len(line.tokens):
        return boundary
    neighbor = line.tokens[neighbor_index]
    if neighbor.observation_id is None or neighbor.damaged:
        return "DAMAGED"
    scalars = _type_scalars(neighbor.observation_id, statistics)
    return _UNSEEN if scalars is None else scalars["frequency"]


def _profile_pairs(
    line: V3ObservationLine,
    token_index: int,
    statistics: _ProfileStatistics,
) -> tuple[tuple[str, FeatureValue], ...]:
    token = line.tokens[token_index]
    if token.observation_id is None or token.damaged:
        categories: dict[str, FeatureValue] = {
            name: _DAMAGED_NEUTRAL for name in PROFILE_FEATURE_NAMES
        }
        categories["left_neighbor_commonness"] = _neighbor_commonness(
            line, token_index, token_index - 1, "BOS", statistics
        )
        categories["right_neighbor_commonness"] = _neighbor_commonness(
            line, token_index, token_index + 1, "EOS", statistics
        )
        return tuple((name, categories[name]) for name in PROFILE_FEATURE_NAMES)

    occurrences = statistics.occurrences.get(token.observation_id)
    count = 0 if occurrences is None else len(occurrences)
    scalars = _type_scalars(token.observation_id, statistics)
    if scalars is None:
        profile_categories: dict[str, FeatureValue] = {
            name: _UNSEEN for name in PROFILE_FEATURE_NAMES
        }
        profile_categories["type_support"] = _UNSEEN
        profile_categories["left_neighbor_commonness"] = _neighbor_commonness(
            line, token_index, token_index - 1, "BOS", statistics
        )
        profile_categories["right_neighbor_commonness"] = _neighbor_commonness(
            line, token_index, token_index + 1, "EOS", statistics
        )
        return tuple((name, profile_categories[name]) for name in PROFILE_FEATURE_NAMES)

    current_position = _position(token_index, len(line.tokens))
    local_initial = 1.0 if token_index == 0 else 0.0
    local_final = 1.0 if token_index == len(line.tokens) - 1 else 0.0
    left_same = (
        token_index > 0
        and line.tokens[token_index - 1].observation_id == token.observation_id
        and not line.tokens[token_index - 1].damaged
    )
    right_same = (
        token_index + 1 < len(line.tokens)
        and line.tokens[token_index + 1].observation_id == token.observation_id
        and not line.tokens[token_index + 1].damaged
    )
    neighbor_equal = 1.0 if left_same or right_same else 0.0
    categories: dict[str, FeatureValue] = {
        "type_support": _support_bucket(count),
        "type_frequency": scalars["frequency"],
        "family_dispersion": scalars["family_dispersion"],
        "line_dispersion": scalars["line_dispersion"],
        "family_entropy": scalars["family_entropy"],
        "type_initial_tendency": scalars["initial"],
        "type_final_tendency": scalars["final"],
        "type_mean_position": scalars["mean_position"],
        "type_position_variance": scalars["position_variance"],
        "left_context_excess_diversity": scalars["left_context_diversity"],
        "left_context_entropy": scalars["left_context_entropy"],
        "right_context_excess_diversity": scalars["right_context_diversity"],
        "right_context_entropy": scalars["right_context_entropy"],
        "type_repeat_in_line_rate": scalars["repeat_in_line"],
        "type_same_left_rate": scalars["same_left"],
        "type_same_right_rate": scalars["same_right"],
        "left_neighbor_commonness": _neighbor_commonness(
            line, token_index, token_index - 1, "BOS", statistics
        ),
        "right_neighbor_commonness": _neighbor_commonness(
            line, token_index, token_index + 1, "EOS", statistics
        ),
        "type_evidence": scalars["evidence"],
        "type_diversity_evidence": scalars["diversity_evidence"],
        "initial_tendency_interaction": local_initial * scalars["initial"],
        "final_tendency_interaction": local_final * scalars["final"],
        "position_agreement": scalars["evidence"]
        * (1.0 - abs(current_position - scalars["mean_position"])),
        "neighbor_equality_repetition_interaction": neighbor_equal * scalars["repeat_in_line"],
    }
    return tuple((name, categories[name]) for name in PROFILE_FEATURE_NAMES)


def _local_rows(line: V3ObservationLine) -> tuple[FeatureRow, ...]:
    rows: list[FeatureRow] = []
    for row in structural_feature_rows(line):
        local_row = tuple((name, category) for name, category in row if name != "line_template")
        if tuple(name for name, _ in local_row) != LOCAL_FEATURE_NAMES:
            raise V4CorpusStatisticsError("V3 local feature surface no longer matches V4 freeze")
        rows.append(local_row)
    return tuple(rows)


class V4CorpusProfile:
    """Fitted target-local profile with opaque identities hidden internally."""

    __slots__ = (
        "_corpus",
        "corpus_commitment",
    )

    def __init__(
        self,
        *,
        corpus: V4ObservationCorpus,
        corpus_commitment: str,
    ) -> None:
        self._corpus = corpus
        self.corpus_commitment = corpus_commitment

    def __repr__(self) -> str:
        return (
            "V4CorpusProfile("
            f"version={V4_CORPUS_PROFILE_VERSION!r}, "
            f"corpus_commitment={self.corpus_commitment!r})"
        )

    @classmethod
    def fit(cls, corpus: V4ObservationCorpus) -> V4CorpusProfile:
        """Fit an identity-internal profile to one truth-free target partition."""

        if not isinstance(corpus, V4ObservationCorpus):
            raise V4CorpusStatisticsError("profile fit requires a V4 observation corpus")
        return cls(
            corpus=corpus,
            corpus_commitment=_commitment(corpus),
        )

    def transform_corpus(
        self,
        corpus: V4ObservationCorpus,
        *,
        ablation: V4FeatureAblation = "full",
        profile_mode: V4ProfileMode = "lofo",
    ) -> V4FeatureCorpus:
        """Transform the fitted corpus under LOFO or diagnostic self-inclusion."""

        selected_ablation = _validate_ablation(ablation)
        selected_profile_mode = _validate_profile_mode(profile_mode)
        if not isinstance(corpus, V4ObservationCorpus):
            raise V4CorpusStatisticsError("profile transform requires a V4 observation corpus")
        if corpus is not self._corpus and corpus != self._corpus:
            raise V4CorpusStatisticsError("profile may transform only its exact fitted corpus")

        feature_documents: list[V4FeatureDocument] = []
        for held_out_index, document in enumerate(corpus.documents):
            if selected_profile_mode == "lofo":
                remaining = tuple(
                    candidate
                    for index, candidate in enumerate(self._corpus.documents)
                    if index != held_out_index
                )
            else:
                remaining = self._corpus.documents
            statistics = _build_statistics(remaining)
            feature_lines: list[V4FeatureLine] = []
            for line in document.lines:
                local_rows = _local_rows(line)
                if selected_ablation == "local":
                    rows = local_rows
                else:
                    rows = tuple(
                        local_row + _profile_pairs(line, token_index, statistics)
                        for token_index, local_row in enumerate(local_rows)
                    )
                feature_lines.append(V4FeatureLine(rows=rows))
            feature_documents.append(V4FeatureDocument(lines=tuple(feature_lines)))
        return V4FeatureCorpus(documents=tuple(feature_documents))


def fit_corpus_profile(corpus: V4ObservationCorpus) -> V4CorpusProfile:
    """Fit the closed V4 truth-free LOFO profile."""

    return V4CorpusProfile.fit(corpus)


__all__ = [
    "FEATURE_NAMES_BY_ABLATION",
    "LOCAL_FEATURE_NAMES",
    "PROFILE_FEATURE_NAMES",
    "V4_CORPUS_PROFILE_VERSION",
    "V4CorpusProfile",
    "V4CorpusStatisticsError",
    "fit_corpus_profile",
]
