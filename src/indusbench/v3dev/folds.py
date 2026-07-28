"""Deterministic family-grouped folds for V3 development.

The primary plan is fixed at five outer folds and four inner folds.  Family
identifiers are carried only as opaque in-memory membership keys; aggregate
support summaries intentionally omit them so they are safe for report-facing
code.  There is no seed, seed search, retry, or alternate-fold fallback.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Final, TypeAlias

from indusbench.v3dev.contracts import V3_STRUCTURAL_STATES, V3StructuralState

V3_STATES: Final = V3_STRUCTURAL_STATES
PRIMARY_OUTER_FOLD_COUNT: Final = 5
PRIMARY_INNER_FOLD_COUNT: Final = 4

StateCounts: TypeAlias = tuple[int, ...]

_FAMILY_RANK_DOMAIN: Final = b"indusbench:v3dev:fold-family-rank:v1\x00"
_PRIMARY_OUTER_DOMAIN: Final = "primary-outer-v1"
_PRIMARY_INNER_DOMAIN_PREFIX: Final = "primary-inner-v1"


class V3FoldError(ValueError):
    """Raised when deterministic grouped folding cannot satisfy its contract."""


def _validate_printable_ascii(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.isascii()
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise V3FoldError(f"{field_name} must be a non-empty printable ASCII string")
    return value


def _validate_state_counts(
    counts: object,
    *,
    require_total: bool,
    require_each_state: bool,
) -> StateCounts:
    if not isinstance(counts, tuple) or len(counts) != len(V3_STATES):
        raise V3FoldError("state counts must be a tuple aligned with V3_STRUCTURAL_STATES")
    if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in counts):
        raise V3FoldError("state counts must contain non-negative integers")
    if require_total and sum(counts) <= 0:
        raise V3FoldError("a family must contain at least one scored state occurrence")
    if require_each_state and any(count <= 0 for count in counts):
        raise V3FoldError("every fold partition must have positive support for all five states")
    return counts


@dataclass(frozen=True, slots=True)
class FamilySupport:
    """Five-state token support for one exact opaque family."""

    family_id: str = field(repr=False)
    state_counts: StateCounts

    def __post_init__(self) -> None:
        _validate_printable_ascii(self.family_id, field_name="family_id")
        _validate_state_counts(
            self.state_counts,
            require_total=True,
            require_each_state=False,
        )

    def count(self, state: V3StructuralState) -> int:
        """Return this family's token support for ``state``."""
        return self.state_counts[V3_STATES.index(state)]


def make_family_support(
    family_id: str,
    state_counts: Mapping[str, int],
) -> FamilySupport:
    """Build an immutable family support vector from an exact-key mapping."""
    if not isinstance(state_counts, Mapping) or set(state_counts) != set(V3_STATES):
        raise V3FoldError("state_counts must contain exactly V3_STRUCTURAL_STATES")
    return FamilySupport(
        family_id=family_id,
        state_counts=tuple(state_counts[state] for state in V3_STATES),
    )


@dataclass(frozen=True, slots=True)
class FoldSupportSummary:
    """Aggregate-only support suitable for report-facing code."""

    index: int
    train_family_count: int
    validation_family_count: int
    train_state_support: StateCounts
    validation_state_support: StateCounts


@dataclass(frozen=True, slots=True)
class GroupedFold:
    """One family-disjoint training/validation fold."""

    index: int
    train_family_ids: tuple[str, ...] = field(repr=False)
    validation_family_ids: tuple[str, ...] = field(repr=False)
    train_state_support: StateCounts
    validation_state_support: StateCounts

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise V3FoldError("fold index must be a non-negative integer")
        _validate_family_id_tuple(self.train_family_ids, field_name="train_family_ids")
        _validate_family_id_tuple(
            self.validation_family_ids,
            field_name="validation_family_ids",
        )
        if set(self.train_family_ids) & set(self.validation_family_ids):
            raise V3FoldError("a family cannot occur in both fold partitions")
        _validate_state_counts(
            self.train_state_support,
            require_total=True,
            require_each_state=True,
        )
        _validate_state_counts(
            self.validation_state_support,
            require_total=True,
            require_each_state=True,
        )

    def support_summary(self) -> FoldSupportSummary:
        """Return an aggregate summary that contains no family identifiers."""
        return FoldSupportSummary(
            index=self.index,
            train_family_count=len(self.train_family_ids),
            validation_family_count=len(self.validation_family_ids),
            train_state_support=self.train_state_support,
            validation_state_support=self.validation_state_support,
        )


@dataclass(frozen=True, slots=True)
class NestedOuterFold:
    """One outer fold and its four training-only inner folds."""

    outer: GroupedFold
    inner_folds: tuple[GroupedFold, ...]


@dataclass(frozen=True, slots=True)
class NestedFoldSupportSummary:
    """Aggregate-only nested support summary."""

    outer: FoldSupportSummary
    inner_folds: tuple[FoldSupportSummary, ...]


@dataclass(frozen=True, slots=True)
class NestedFoldPlan:
    """The fixed five-by-four primary nested development plan."""

    outer_folds: tuple[NestedOuterFold, ...]

    def __post_init__(self) -> None:
        _validate_nested_plan(self.outer_folds)

    def support_summaries(self) -> tuple[NestedFoldSupportSummary, ...]:
        """Return nested aggregate support without family identifiers."""
        return tuple(
            NestedFoldSupportSummary(
                outer=nested.outer.support_summary(),
                inner_folds=tuple(fold.support_summary() for fold in nested.inner_folds),
            )
            for nested in self.outer_folds
        )


def _validate_family_id_tuple(values: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise V3FoldError(f"{field_name} must be a non-empty tuple")
    for value in values:
        _validate_printable_ascii(value, field_name=field_name)
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise V3FoldError(f"{field_name} must contain unique ASCII-sorted identifiers")
    return values


def _validate_fold_count(fold_count: object) -> int:
    if isinstance(fold_count, bool) or not isinstance(fold_count, int) or fold_count < 2:
        raise V3FoldError("fold_count must be an integer of at least two")
    return fold_count


def _materialize_families(families: Iterable[FamilySupport]) -> tuple[FamilySupport, ...]:
    materialized = tuple(families)
    if not materialized:
        raise V3FoldError("at least one family is required")
    if any(not isinstance(family, FamilySupport) for family in materialized):
        raise V3FoldError("families must contain only FamilySupport values")
    family_ids = [family.family_id for family in materialized]
    if len(set(family_ids)) != len(family_ids):
        raise V3FoldError("family identifiers must be unique")
    return tuple(sorted(materialized, key=lambda family: family.family_id))


def _frame(raw: bytes) -> bytes:
    return len(raw).to_bytes(8, "big") + raw


def _family_rank(domain: str, family_id: str) -> bytes:
    payload = bytearray(_FAMILY_RANK_DOMAIN)
    payload.extend(_frame(domain.encode("ascii")))
    payload.extend(_frame(family_id.encode("ascii")))
    return hashlib.sha256(payload).digest()


def _sum_state_counts(families: Iterable[FamilySupport]) -> StateCounts:
    totals = [0] * len(V3_STATES)
    for family in families:
        for state_index, count in enumerate(family.state_counts):
            totals[state_index] += count
    return tuple(totals)


def _supporting_family_counts(families: Iterable[FamilySupport]) -> StateCounts:
    totals = [0] * len(V3_STATES)
    for family in families:
        for state_index, count in enumerate(family.state_counts):
            if count > 0:
                totals[state_index] += 1
    return tuple(totals)


def _family_order_key(
    family: FamilySupport,
    *,
    token_totals: StateCounts,
    supporting_family_totals: StateCounts,
    domain: str,
) -> tuple[int, Fraction, Fraction, int, int, bytes, str]:
    positive_indexes = [
        state_index for state_index, count in enumerate(family.state_counts) if count > 0
    ]
    rarity = min(supporting_family_totals[state_index] for state_index in positive_indexes)
    shares = [
        Fraction(family.state_counts[state_index], token_totals[state_index])
        for state_index in positive_indexes
    ]
    return (
        rarity,
        -max(shares),
        -sum(shares, start=Fraction()),
        -len(positive_indexes),
        -sum(family.state_counts),
        _family_rank(domain, family.family_id),
        family.family_id,
    )


def _normalized_imbalance(
    matrix: list[list[int]],
    totals: StateCounts,
    fold_count: int,
    *,
    candidate_fold: int,
    added: StateCounts,
    presence: bool,
) -> tuple[Fraction, Fraction]:
    maximum = Fraction()
    squared_sum = Fraction()
    for fold_index in range(fold_count):
        for state_index, total in enumerate(totals):
            increment = int(added[state_index] > 0) if presence else added[state_index]
            value = matrix[fold_index][state_index]
            if fold_index == candidate_fold:
                value += increment
            delta = abs((value * fold_count) - total)
            relative = Fraction(delta, total)
            maximum = max(maximum, relative)
            squared_sum += relative * relative
    return maximum, squared_sum


def _fold_size_imbalance(
    fold_sizes: list[int],
    family_count: int,
    fold_count: int,
    candidate_fold: int,
) -> tuple[Fraction, Fraction]:
    maximum = Fraction()
    squared_sum = Fraction()
    for fold_index, size in enumerate(fold_sizes):
        value = size + int(fold_index == candidate_fold)
        relative = Fraction(abs((value * fold_count) - family_count), family_count)
        maximum = max(maximum, relative)
        squared_sum += relative * relative
    return maximum, squared_sum


def _candidate_preserves_future_coverage(
    token_matrix: list[list[int]],
    family: FamilySupport,
    *,
    candidate_fold: int,
    remaining_supporters: StateCounts,
) -> bool:
    for state_index in range(len(V3_STATES)):
        missing_after = sum(
            1
            for fold_index, fold_counts in enumerate(token_matrix)
            if fold_counts[state_index] == 0
            and not (fold_index == candidate_fold and family.state_counts[state_index] > 0)
        )
        if missing_after > remaining_supporters[state_index]:
            return False
    return True


def _allocation_cost(
    token_matrix: list[list[int]],
    presence_matrix: list[list[int]],
    fold_sizes: list[int],
    family: FamilySupport,
    *,
    candidate_fold: int,
    token_totals: StateCounts,
    supporting_family_totals: StateCounts,
    family_count: int,
    fold_count: int,
) -> tuple[int, Fraction, Fraction, Fraction, Fraction, Fraction, Fraction, int]:
    missing_after = sum(
        1
        for fold_index, fold_counts in enumerate(token_matrix)
        for state_index, count in enumerate(fold_counts)
        if count == 0
        and not (fold_index == candidate_fold and family.state_counts[state_index] > 0)
    )
    token_maximum, token_squared = _normalized_imbalance(
        token_matrix,
        token_totals,
        fold_count,
        candidate_fold=candidate_fold,
        added=family.state_counts,
        presence=False,
    )
    presence_maximum, presence_squared = _normalized_imbalance(
        presence_matrix,
        supporting_family_totals,
        fold_count,
        candidate_fold=candidate_fold,
        added=family.state_counts,
        presence=True,
    )
    size_maximum, size_squared = _fold_size_imbalance(
        fold_sizes,
        family_count,
        fold_count,
        candidate_fold,
    )
    return (
        missing_after,
        token_maximum,
        token_squared,
        presence_maximum,
        presence_squared,
        size_maximum,
        size_squared,
        candidate_fold,
    )


def build_grouped_folds(
    families: Iterable[FamilySupport],
    *,
    fold_count: int,
    domain: str,
) -> tuple[GroupedFold, ...]:
    """Greedily allocate exact families without a seed or retry path.

    ``domain`` is a fixed protocol-purpose separator, not a tunable seed.
    Candidate folds are chosen by a lexicographic objective: preserve enough
    unassigned families to complete five-state coverage, fill uncovered
    state/fold cells, balance token support, balance family support, and then
    balance fold size.  Integer fold index is the final stable tie-break.
    """
    fold_count = _validate_fold_count(fold_count)
    domain = _validate_printable_ascii(domain, field_name="domain")
    materialized = _materialize_families(families)
    if len(materialized) < fold_count:
        raise V3FoldError("folding requires at least one family per fold")

    token_totals = _sum_state_counts(materialized)
    supporting_family_totals = _supporting_family_counts(materialized)
    if any(total < fold_count for total in supporting_family_totals):
        raise V3FoldError("each state must occur in at least fold_count distinct families")

    ordered = sorted(
        materialized,
        key=lambda family: _family_order_key(
            family,
            token_totals=token_totals,
            supporting_family_totals=supporting_family_totals,
            domain=domain,
        ),
    )
    assignments: list[list[FamilySupport]] = [[] for _ in range(fold_count)]
    token_matrix = [[0] * len(V3_STATES) for _ in range(fold_count)]
    presence_matrix = [[0] * len(V3_STATES) for _ in range(fold_count)]
    fold_sizes = [0] * fold_count
    remaining_supporters = list(supporting_family_totals)

    for family in ordered:
        for state_index, count in enumerate(family.state_counts):
            if count > 0:
                remaining_supporters[state_index] -= 1
        remaining = tuple(remaining_supporters)
        candidate_costs = [
            _allocation_cost(
                token_matrix,
                presence_matrix,
                fold_sizes,
                family,
                candidate_fold=fold_index,
                token_totals=token_totals,
                supporting_family_totals=supporting_family_totals,
                family_count=len(materialized),
                fold_count=fold_count,
            )
            for fold_index in range(fold_count)
            if _candidate_preserves_future_coverage(
                token_matrix,
                family,
                candidate_fold=fold_index,
                remaining_supporters=remaining,
            )
        ]
        if not candidate_costs:
            raise V3FoldError(
                "deterministic greedy allocation cannot preserve five-state fold support"
            )
        chosen_fold = min(candidate_costs)[-1]
        assignments[chosen_fold].append(family)
        fold_sizes[chosen_fold] += 1
        for state_index, count in enumerate(family.state_counts):
            token_matrix[chosen_fold][state_index] += count
            presence_matrix[chosen_fold][state_index] += int(count > 0)

    all_family_ids = tuple(family.family_id for family in materialized)
    all_family_id_set = set(all_family_ids)
    folds: list[GroupedFold] = []
    for fold_index, validation_families in enumerate(assignments):
        validation_family_ids = tuple(sorted(family.family_id for family in validation_families))
        validation_family_id_set = set(validation_family_ids)
        train_family_ids = tuple(sorted(all_family_id_set - validation_family_id_set))
        validation_state_support = tuple(token_matrix[fold_index])
        train_state_support = tuple(
            total - validation
            for total, validation in zip(
                token_totals,
                validation_state_support,
                strict=True,
            )
        )
        folds.append(
            GroupedFold(
                index=fold_index,
                train_family_ids=train_family_ids,
                validation_family_ids=validation_family_ids,
                train_state_support=train_state_support,
                validation_state_support=validation_state_support,
            )
        )
    _validate_partitioning(tuple(folds), all_family_id_set)
    return tuple(folds)


def _validate_partitioning(
    folds: tuple[GroupedFold, ...],
    expected_family_ids: set[str],
) -> None:
    validation_memberships: list[str] = []
    expected_indexes = tuple(range(len(folds)))
    if tuple(fold.index for fold in folds) != expected_indexes:
        raise V3FoldError("fold indexes must be contiguous and ordered")
    for fold in folds:
        train_ids = set(fold.train_family_ids)
        validation_ids = set(fold.validation_family_ids)
        if train_ids | validation_ids != expected_family_ids:
            raise V3FoldError("each fold must partition the complete family set")
        validation_memberships.extend(fold.validation_family_ids)
    if (
        len(validation_memberships) != len(expected_family_ids)
        or set(validation_memberships) != expected_family_ids
    ):
        raise V3FoldError("every family must occur in exactly one validation fold")


def build_nested_grouped_folds(
    families: Iterable[FamilySupport],
) -> NestedFoldPlan:
    """Build the fixed five-outer/four-inner primary fold plan."""
    materialized = _materialize_families(families)
    family_by_id = {family.family_id: family for family in materialized}
    outer_folds = build_grouped_folds(
        materialized,
        fold_count=PRIMARY_OUTER_FOLD_COUNT,
        domain=_PRIMARY_OUTER_DOMAIN,
    )
    nested: list[NestedOuterFold] = []
    for outer in outer_folds:
        inner_families = tuple(family_by_id[family_id] for family_id in outer.train_family_ids)
        inner_folds = build_grouped_folds(
            inner_families,
            fold_count=PRIMARY_INNER_FOLD_COUNT,
            domain=f"{_PRIMARY_INNER_DOMAIN_PREFIX}:outer-{outer.index:02d}",
        )
        nested.append(NestedOuterFold(outer=outer, inner_folds=inner_folds))
    return NestedFoldPlan(outer_folds=tuple(nested))


def _validate_nested_plan(outer_folds: tuple[NestedOuterFold, ...]) -> None:
    if not isinstance(outer_folds, tuple) or len(outer_folds) != PRIMARY_OUTER_FOLD_COUNT:
        raise V3FoldError("the primary plan must contain exactly five outer folds")
    if tuple(item.outer.index for item in outer_folds) != tuple(range(PRIMARY_OUTER_FOLD_COUNT)):
        raise V3FoldError("outer folds must be contiguous and ordered")
    outer_validation_memberships: list[str] = []
    complete_family_ids: set[str] | None = None
    for item in outer_folds:
        outer = item.outer
        current_complete = set(outer.train_family_ids) | set(outer.validation_family_ids)
        if complete_family_ids is None:
            complete_family_ids = current_complete
        elif current_complete != complete_family_ids:
            raise V3FoldError("outer folds do not share one complete family universe")
        outer_validation_memberships.extend(outer.validation_family_ids)
        if len(item.inner_folds) != PRIMARY_INNER_FOLD_COUNT:
            raise V3FoldError("each outer fold must contain exactly four inner folds")
        _validate_partitioning(item.inner_folds, set(outer.train_family_ids))
        if any(
            set(inner.train_family_ids) & set(outer.validation_family_ids)
            or set(inner.validation_family_ids) & set(outer.validation_family_ids)
            for inner in item.inner_folds
        ):
            raise V3FoldError("outer validation families cannot enter inner folds")
    if complete_family_ids is None or (
        len(outer_validation_memberships) != len(complete_family_ids)
        or set(outer_validation_memberships) != complete_family_ids
    ):
        raise V3FoldError("each family must occur in exactly one outer validation fold")


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    """Mean and standard error over independent outer-fold scores."""

    mean: float
    standard_error: float
    fold_count: int


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """Outer-fold scores and an a-priori model-complexity rank."""

    candidate_id: str
    complexity_rank: int
    fold_scores: tuple[float, ...] = field(repr=False)

    def __post_init__(self) -> None:
        _validate_printable_ascii(self.candidate_id, field_name="candidate_id")
        if (
            isinstance(self.complexity_rank, bool)
            or not isinstance(self.complexity_rank, int)
            or self.complexity_rank < 0
        ):
            raise V3FoldError("complexity_rank must be a non-negative integer")
        if not isinstance(self.fold_scores, tuple):
            raise V3FoldError("fold_scores must be an immutable tuple")
        summarize_scores(self.fold_scores)

    def summary(self) -> ScoreSummary:
        """Summarize this candidate's fixed outer-fold scores."""
        return summarize_scores(self.fold_scores)


def summarize_scores(scores: Iterable[float]) -> ScoreSummary:
    """Return the sample mean and standard error for two or more folds."""
    materialized = tuple(scores)
    if len(materialized) < 2:
        raise V3FoldError("at least two fold scores are required")
    if any(
        isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
        for score in materialized
    ):
        raise V3FoldError("fold scores must be finite real numbers")
    float_scores = tuple(float(score) for score in materialized)
    mean = math.fsum(float_scores) / len(float_scores)
    squared_deviations = math.fsum((score - mean) ** 2 for score in float_scores)
    sample_variance = squared_deviations / (len(float_scores) - 1)
    standard_error = math.sqrt(sample_variance / len(float_scores))
    return ScoreSummary(
        mean=mean,
        standard_error=standard_error,
        fold_count=len(float_scores),
    )


def select_one_standard_error(
    candidates: Iterable[CandidateScore],
) -> CandidateScore:
    """Select the simplest higher-is-better candidate within one best-model SE."""
    materialized = tuple(candidates)
    if not materialized:
        raise V3FoldError("at least one candidate score is required")
    candidate_ids = [candidate.candidate_id for candidate in materialized]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise V3FoldError("candidate identifiers must be unique")
    summaries = {candidate.candidate_id: candidate.summary() for candidate in materialized}
    best = min(
        materialized,
        key=lambda candidate: (
            -summaries[candidate.candidate_id].mean,
            candidate.candidate_id,
        ),
    )
    best_summary = summaries[best.candidate_id]
    cutoff = best_summary.mean - best_summary.standard_error
    eligible = [
        candidate for candidate in materialized if summaries[candidate.candidate_id].mean >= cutoff
    ]
    return min(
        eligible,
        key=lambda candidate: (
            candidate.complexity_rank,
            -summaries[candidate.candidate_id].mean,
            candidate.candidate_id,
        ),
    )


__all__ = [
    "PRIMARY_INNER_FOLD_COUNT",
    "PRIMARY_OUTER_FOLD_COUNT",
    "V3_STATES",
    "CandidateScore",
    "FamilySupport",
    "FoldSupportSummary",
    "GroupedFold",
    "NestedFoldPlan",
    "NestedFoldSupportSummary",
    "NestedOuterFold",
    "ScoreSummary",
    "V3FoldError",
    "build_grouped_folds",
    "build_nested_grouped_folds",
    "make_family_support",
    "select_one_standard_error",
    "summarize_scores",
]
