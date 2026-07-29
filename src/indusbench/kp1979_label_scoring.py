"""Frozen, source-independent scoring for KP1979 label-position geometry."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

PREDICTION_HEIGHT = 96
PREDICTION_ANCHOR_OFFSET = 48
KP1979_PAGE_HEIGHT = 7010
MAX_EVALUATION_PAGES = 6
MAX_LABELS_PER_LANE = 64
MAX_PARTITION_LABELS = MAX_EVALUATION_PAGES * 2 * MAX_LABELS_PER_LANE
MAX_UNRESOLVED_LANES = MAX_EVALUATION_PAGES * 2

ScoringStatus = Literal["scored", "reference_incomplete", "ambiguous_matching"]
ReferenceUse = Literal[
    "synthetic_control",
    "external_reference_candidate",
    "machine_development",
]


class KP1979LabelScoringError(ValueError):
    """Raised when a label-position scoring contract is structurally invalid."""


@dataclass(frozen=True, order=True, slots=True)
class PageLane:
    """One physical lane on one fixed PDF page."""

    pdf_page_number: int
    lane_index: int


@dataclass(frozen=True, order=True, slots=True)
class LabelPrediction:
    """One detector proposal represented by its vertical interval."""

    pdf_page_number: int
    lane_index: int
    y0: int
    y1: int

    @property
    def anchor_y(self) -> int:
        """Return the frozen vertical anchor for this prediction."""

        return self.y0 + PREDICTION_ANCHOR_OFFSET


@dataclass(frozen=True, order=True, slots=True)
class LabelReferenceInterval:
    """One accepted reference target's half-open vertical interval."""

    pdf_page_number: int
    lane_index: int
    y0: int
    y1: int


@dataclass(frozen=True, slots=True)
class LabelMatch:
    """One unique same-page, same-lane prediction/reference match."""

    prediction: LabelPrediction
    reference: LabelReferenceInterval


@dataclass(frozen=True, slots=True)
class PositivePageScore:
    """Accuracy counts and ratios for one declared positive page."""

    pdf_page_number: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float


@dataclass(frozen=True, slots=True)
class NegativeControlGate:
    """Empty-set gate for one negative page; it deliberately has no ratios."""

    pdf_page_number: int
    prediction_count: int
    reference_count: int
    empty: bool


@dataclass(frozen=True, slots=True)
class LabelPositionScore:
    """Partition result under the frozen KP1979 label-position rules."""

    reference_use: Literal["synthetic_control"]
    status: ScoringStatus
    matches: tuple[LabelMatch, ...]
    positive_pages: tuple[PositivePageScore, ...]
    negative_controls: tuple[NegativeControlGate, ...]
    true_positives: int | None
    false_positives: int | None
    false_negatives: int | None
    micro_precision: float | None
    micro_recall: float | None
    negative_control_empty: bool | None
    reference_eligibility_verified: bool
    evaluation_admissible: bool
    real_accuracy: bool
    decipherment: bool
    prize_submission_eligible: bool


def _score_label_positions(
    predictions: Sequence[LabelPrediction],
    references: Sequence[LabelReferenceInterval],
    *,
    reference_use: ReferenceUse,
    positive_pages: Collection[int],
    negative_pages: Collection[int],
    unresolved_lanes: Collection[PageLane] = (),
) -> LabelPositionScore:
    """Score a complete reference partition without reading pixels or detector state.

    Predictions and references match only within the same PDF page and physical
    lane. A prediction is eligible only when it is exactly 96 pixels high, and
    its fixed anchor ``y0 + 48`` lies inside a reference's half-open interval.
    Within each lane, matching is maximum-cardinality, one-to-one, and
    top-to-bottom order preserving.

    Any unresolved lane suppresses the complete partition score. More than one
    maximum-cardinality matching suppresses accuracy metrics as ambiguous.
    Declared negative pages receive only an empty-set gate and never precision
    or recall.
    """

    accepted_reference_use = _accepted_reference_use(reference_use)
    prediction_values = _prediction_tuple(predictions)
    reference_values = _reference_tuple(references)
    positive_page_values = _page_roster(positive_pages, label="positive")
    negative_page_values = _page_roster(negative_pages, label="negative")
    if not positive_page_values and not negative_page_values:
        raise KP1979LabelScoringError("at least one evaluation page is required")
    overlap = set(positive_page_values) & set(negative_page_values)
    if overlap:
        raise KP1979LabelScoringError("positive and negative page rosters must be disjoint")
    declared_pages = set(positive_page_values) | set(negative_page_values)
    if len(declared_pages) > MAX_EVALUATION_PAGES:
        raise KP1979LabelScoringError("evaluation page roster exceeds its fixed six-page limit")
    unresolved_values = _unresolved_tuple(unresolved_lanes, declared_pages=declared_pages)

    for prediction in prediction_values:
        _validate_prediction(prediction, declared_pages=declared_pages)
    for reference in reference_values:
        _validate_reference(reference, declared_pages=declared_pages)
    _validate_record_rosters(prediction_values, reference_values)

    if unresolved_values:
        return LabelPositionScore(
            reference_use=accepted_reference_use,
            status="reference_incomplete",
            matches=(),
            positive_pages=(),
            negative_controls=(),
            true_positives=None,
            false_positives=None,
            false_negatives=None,
            micro_precision=None,
            micro_recall=None,
            negative_control_empty=None,
            reference_eligibility_verified=False,
            evaluation_admissible=False,
            real_accuracy=False,
            decipherment=False,
            prize_submission_eligible=False,
        )

    predictions_by_page = _group_predictions_by_page(prediction_values)
    references_by_page = _group_references_by_page(reference_values)
    for page in positive_page_values:
        if not references_by_page.get(page):
            raise KP1979LabelScoringError(
                "a complete positive page must contain at least one reference"
            )
    for page in negative_page_values:
        if references_by_page.get(page):
            raise KP1979LabelScoringError(
                "a complete negative-control page must have an empty reference set"
            )

    negative_controls = tuple(
        NegativeControlGate(
            pdf_page_number=page,
            prediction_count=len(predictions_by_page.get(page, ())),
            reference_count=0,
            empty=not predictions_by_page.get(page),
        )
        for page in negative_page_values
    )
    negative_control_empty = (
        all(gate.empty for gate in negative_controls) if negative_controls else None
    )

    matches: list[LabelMatch] = []
    for page in positive_page_values:
        for lane_index in (0, 1):
            lane_predictions = tuple(
                prediction
                for prediction in predictions_by_page.get(page, ())
                if prediction.lane_index == lane_index
            )
            lane_references = tuple(
                reference
                for reference in references_by_page.get(page, ())
                if reference.lane_index == lane_index
            )
            maximum_matchings = _maximum_ordered_matchings(
                lane_predictions,
                lane_references,
            )
            if len(maximum_matchings) > 1:
                return LabelPositionScore(
                    reference_use=accepted_reference_use,
                    status="ambiguous_matching",
                    matches=(),
                    positive_pages=(),
                    negative_controls=negative_controls,
                    true_positives=None,
                    false_positives=None,
                    false_negatives=None,
                    micro_precision=None,
                    micro_recall=None,
                    negative_control_empty=negative_control_empty,
                    reference_eligibility_verified=False,
                    evaluation_admissible=False,
                    real_accuracy=False,
                    decipherment=False,
                    prize_submission_eligible=False,
                )
            unique_matching = maximum_matchings[0] if maximum_matchings else ()
            for prediction_index, reference_index in unique_matching:
                matches.append(
                    LabelMatch(
                        prediction=lane_predictions[prediction_index],
                        reference=lane_references[reference_index],
                    )
                )

    page_scores: list[PositivePageScore] = []
    for page in positive_page_values:
        prediction_count = len(predictions_by_page.get(page, ()))
        reference_count = len(references_by_page[page])
        true_positives = sum(match.prediction.pdf_page_number == page for match in matches)
        false_positives = prediction_count - true_positives
        false_negatives = reference_count - true_positives
        page_scores.append(
            PositivePageScore(
                pdf_page_number=page,
                true_positives=true_positives,
                false_positives=false_positives,
                false_negatives=false_negatives,
                precision=(true_positives / prediction_count if prediction_count else 0.0),
                recall=true_positives / reference_count,
            )
        )

    aggregate_true_positives: int | None
    aggregate_false_positives: int | None
    aggregate_false_negatives: int | None
    micro_precision: float | None
    micro_recall: float | None
    if page_scores:
        aggregate_true_positives = sum(page.true_positives for page in page_scores)
        aggregate_false_positives = sum(page.false_positives for page in page_scores)
        aggregate_false_negatives = sum(page.false_negatives for page in page_scores)
        positive_prediction_count = aggregate_true_positives + aggregate_false_positives
        positive_reference_count = aggregate_true_positives + aggregate_false_negatives
        micro_precision = (
            aggregate_true_positives / positive_prediction_count
            if positive_prediction_count
            else 0.0
        )
        micro_recall = aggregate_true_positives / positive_reference_count
    else:
        aggregate_true_positives = None
        aggregate_false_positives = None
        aggregate_false_negatives = None
        micro_precision = None
        micro_recall = None
    return LabelPositionScore(
        reference_use=accepted_reference_use,
        status="scored",
        matches=tuple(matches),
        positive_pages=tuple(page_scores),
        negative_controls=negative_controls,
        true_positives=aggregate_true_positives,
        false_positives=aggregate_false_positives,
        false_negatives=aggregate_false_negatives,
        micro_precision=micro_precision,
        micro_recall=micro_recall,
        negative_control_empty=negative_control_empty,
        reference_eligibility_verified=False,
        evaluation_admissible=False,
        real_accuracy=False,
        decipherment=False,
        prize_submission_eligible=False,
    )


def _accepted_reference_use(
    reference_use: ReferenceUse,
) -> Literal["synthetic_control"]:
    if reference_use == "machine_development":
        raise KP1979LabelScoringError(
            "machine-development geometry is ineligible for label-position scoring"
        )
    if reference_use == "external_reference_candidate":
        raise KP1979LabelScoringError(
            "external-reference scoring requires an exact-artifact eligibility gate"
        )
    if reference_use != "synthetic_control":
        raise KP1979LabelScoringError("reference use is invalid")
    return "synthetic_control"


def _prediction_tuple(
    predictions: Sequence[LabelPrediction],
) -> tuple[LabelPrediction, ...]:
    if isinstance(predictions, (str, bytes)) or not isinstance(predictions, Sequence):
        raise KP1979LabelScoringError("predictions must be a finite sequence")
    if len(predictions) > MAX_PARTITION_LABELS:
        raise KP1979LabelScoringError("prediction roster exceeds its fixed partition limit")
    if any(not isinstance(prediction, LabelPrediction) for prediction in predictions):
        raise KP1979LabelScoringError("every prediction must be a LabelPrediction")
    return tuple(predictions)


def _reference_tuple(
    references: Sequence[LabelReferenceInterval],
) -> tuple[LabelReferenceInterval, ...]:
    if isinstance(references, (str, bytes)) or not isinstance(references, Sequence):
        raise KP1979LabelScoringError("references must be a finite sequence")
    if len(references) > MAX_PARTITION_LABELS:
        raise KP1979LabelScoringError("reference roster exceeds its fixed partition limit")
    if any(not isinstance(reference, LabelReferenceInterval) for reference in references):
        raise KP1979LabelScoringError("every reference must be a LabelReferenceInterval")
    return tuple(references)


def _page_roster(pages: Collection[int], *, label: str) -> tuple[int, ...]:
    if isinstance(pages, (str, bytes)) or not isinstance(pages, Collection):
        raise KP1979LabelScoringError(f"{label} pages must be a finite collection")
    if len(pages) > MAX_EVALUATION_PAGES:
        raise KP1979LabelScoringError(f"{label} page roster exceeds its fixed six-page limit")
    values = tuple(pages)
    if any(not _is_integer(page) or page < 1 for page in values):
        raise KP1979LabelScoringError(f"{label} page numbers must be positive integers")
    if len(set(values)) != len(values):
        raise KP1979LabelScoringError(f"{label} page roster contains a duplicate")
    return tuple(sorted(values))


def _unresolved_tuple(
    unresolved_lanes: Collection[PageLane],
    *,
    declared_pages: set[int],
) -> tuple[PageLane, ...]:
    if isinstance(unresolved_lanes, (str, bytes)) or not isinstance(unresolved_lanes, Collection):
        raise KP1979LabelScoringError("unresolved lanes must be a finite collection")
    if len(unresolved_lanes) > MAX_UNRESOLVED_LANES:
        raise KP1979LabelScoringError("unresolved lane roster exceeds its fixed partition limit")
    values = tuple(unresolved_lanes)
    if any(not isinstance(value, PageLane) for value in values):
        raise KP1979LabelScoringError("every unresolved lane must be a PageLane")
    for value in values:
        _validate_page_lane(value.pdf_page_number, value.lane_index)
        if value.pdf_page_number not in declared_pages:
            raise KP1979LabelScoringError("an unresolved lane belongs to an undeclared page")
    if len(set(values)) != len(values):
        raise KP1979LabelScoringError("unresolved lane roster contains a duplicate")
    return tuple(sorted(values))


def _validate_prediction(
    prediction: LabelPrediction,
    *,
    declared_pages: set[int],
) -> None:
    _validate_page_lane(prediction.pdf_page_number, prediction.lane_index)
    _validate_interval(prediction.y0, prediction.y1, label="prediction")
    if prediction.pdf_page_number not in declared_pages:
        raise KP1979LabelScoringError("a prediction belongs to an undeclared page")
    if prediction.y1 - prediction.y0 != PREDICTION_HEIGHT:
        raise KP1979LabelScoringError("every prediction must be exactly 96 pixels high")


def _validate_reference(
    reference: LabelReferenceInterval,
    *,
    declared_pages: set[int],
) -> None:
    _validate_page_lane(reference.pdf_page_number, reference.lane_index)
    _validate_interval(reference.y0, reference.y1, label="reference")
    if reference.pdf_page_number not in declared_pages:
        raise KP1979LabelScoringError("a reference belongs to an undeclared page")


def _validate_page_lane(pdf_page_number: int, lane_index: int) -> None:
    if not _is_integer(pdf_page_number) or pdf_page_number < 1:
        raise KP1979LabelScoringError("PDF page number must be a positive integer")
    if not _is_integer(lane_index) or lane_index not in {0, 1}:
        raise KP1979LabelScoringError("physical lane index must be 0 or 1")


def _validate_interval(y0: int, y1: int, *, label: str) -> None:
    if not _is_integer(y0) or not _is_integer(y1) or y0 < 0 or y1 <= y0 or y1 > KP1979_PAGE_HEIGHT:
        raise KP1979LabelScoringError(
            f"{label} interval must be a nonempty half-open integer interval"
        )


def _validate_record_rosters(
    predictions: tuple[LabelPrediction, ...],
    references: tuple[LabelReferenceInterval, ...],
) -> None:
    if len(set(predictions)) != len(predictions):
        raise KP1979LabelScoringError("prediction roster contains a duplicate")
    if len(set(references)) != len(references):
        raise KP1979LabelScoringError("reference roster contains a duplicate")

    pages = sorted(
        {value.pdf_page_number for value in predictions}
        | {value.pdf_page_number for value in references}
    )
    for page in pages:
        for lane_index in (0, 1):
            lane_predictions = tuple(
                value
                for value in predictions
                if value.pdf_page_number == page and value.lane_index == lane_index
            )
            if len(lane_predictions) > MAX_LABELS_PER_LANE:
                raise KP1979LabelScoringError("prediction lane exceeds its fixed label limit")
            lane_references = tuple(
                sorted(
                    (
                        value
                        for value in references
                        if value.pdf_page_number == page and value.lane_index == lane_index
                    ),
                    key=lambda value: (value.y0, value.y1),
                )
            )
            if len(lane_references) > MAX_LABELS_PER_LANE:
                raise KP1979LabelScoringError("reference lane exceeds its fixed label limit")
            for previous, current in pairwise(lane_references):
                if current.y0 < previous.y1:
                    raise KP1979LabelScoringError("same-lane reference intervals must not overlap")


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _group_predictions_by_page(
    predictions: tuple[LabelPrediction, ...],
) -> dict[int, tuple[LabelPrediction, ...]]:
    result: dict[int, tuple[LabelPrediction, ...]] = {}
    for page in sorted({prediction.pdf_page_number for prediction in predictions}):
        result[page] = tuple(
            sorted(
                (prediction for prediction in predictions if prediction.pdf_page_number == page),
                key=lambda value: (
                    value.lane_index,
                    value.anchor_y,
                    value.y0,
                    value.y1,
                ),
            )
        )
    return result


def _group_references_by_page(
    references: tuple[LabelReferenceInterval, ...],
) -> dict[int, tuple[LabelReferenceInterval, ...]]:
    result: dict[int, tuple[LabelReferenceInterval, ...]] = {}
    for page in sorted({reference.pdf_page_number for reference in references}):
        result[page] = tuple(
            sorted(
                (reference for reference in references if reference.pdf_page_number == page),
                key=lambda value: (
                    value.lane_index,
                    value.y0,
                    value.y1,
                ),
            )
        )
    return result


_Matching = tuple[tuple[int, int], ...]


def _maximum_ordered_matchings(
    predictions: tuple[LabelPrediction, ...],
    references: tuple[LabelReferenceInterval, ...],
) -> tuple[_Matching, ...]:
    """Return up to two distinct maximum ordered matchings."""

    prediction_values = tuple(
        sorted(
            predictions,
            key=lambda value: (value.anchor_y, value.y0, value.y1),
        )
    )
    reference_values = tuple(
        sorted(
            references,
            key=lambda value: (value.y0, value.y1),
        )
    )
    prediction_count = len(prediction_values)
    reference_count = len(reference_values)
    empty_matchings: tuple[_Matching, ...] = ((),)
    table: list[list[tuple[_Matching, ...]]] = [
        [empty_matchings for _ in range(reference_count + 1)] for _ in range(prediction_count + 1)
    ]

    for prediction_index in range(prediction_count - 1, -1, -1):
        for reference_index in range(reference_count - 1, -1, -1):
            candidates: set[_Matching] = set(table[prediction_index + 1][reference_index])
            candidates.update(table[prediction_index][reference_index + 1])
            prediction = prediction_values[prediction_index]
            reference = reference_values[reference_index]
            if reference.y0 <= prediction.anchor_y < reference.y1:
                candidates.update(
                    ((prediction_index, reference_index), *tail)
                    for tail in table[prediction_index + 1][reference_index + 1]
                )
            maximum_size = max(len(candidate) for candidate in candidates)
            maximum = sorted(
                candidate for candidate in candidates if len(candidate) == maximum_size
            )
            table[prediction_index][reference_index] = tuple(maximum[:2])

    return table[0][0]


__all__ = [
    "KP1979_PAGE_HEIGHT",
    "MAX_EVALUATION_PAGES",
    "MAX_LABELS_PER_LANE",
    "MAX_PARTITION_LABELS",
    "MAX_UNRESOLVED_LANES",
    "PREDICTION_ANCHOR_OFFSET",
    "PREDICTION_HEIGHT",
    "KP1979LabelScoringError",
    "LabelMatch",
    "LabelPositionScore",
    "LabelPrediction",
    "LabelReferenceInterval",
    "NegativeControlGate",
    "PageLane",
    "PositivePageScore",
    "ReferenceUse",
    "ScoringStatus",
]
