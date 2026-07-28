"""Truth-free observation and ID-free feature contracts for V4 development."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, TypeAlias

from indusbench.v3dev.contracts import (
    V3_STRUCTURAL_STATES,
    V3ObservationLine,
    V3StructuralState,
)

V4FeatureAblation = Literal["local", "full"]
V4_FEATURE_ABLATIONS: tuple[V4FeatureAblation, ...] = ("local", "full")
V4ProfileMode = Literal["lofo", "self_inclusive"]
V4_PROFILE_MODES: tuple[V4ProfileMode, ...] = ("lofo", "self_inclusive")

FeatureValue: TypeAlias = str | float
FeatureRow: TypeAlias = tuple[tuple[str, FeatureValue], ...]


class V4ContractError(ValueError):
    """Raised when a V4 boundary object violates its closed contract."""


def _is_nonempty_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and all(ord(character) >= 0x21 and ord(character) != 0x7F for character in value)
    )


def _validate_feature_row(row: object) -> None:
    if not isinstance(row, tuple) or not row:
        raise V4ContractError("feature row must be a non-empty tuple")
    names: list[str] = []
    for item in row:
        if not isinstance(item, tuple) or len(item) != 2:
            raise V4ContractError("feature row entries must be name-category pairs")
        name, category = item
        if not _is_nonempty_text(name):
            raise V4ContractError("feature name must be a non-empty visible string")
        if isinstance(category, str):
            if not _is_nonempty_text(category):
                raise V4ContractError("feature category must be a non-empty visible string")
        elif (
            isinstance(category, bool)
            or not isinstance(category, float)
            or not math.isfinite(category)
            or not 0.0 <= category <= 1.0
        ):
            raise V4ContractError(
                "numeric feature value must be a finite float in the closed unit interval"
            )
        names.append(name)
    if len(set(names)) != len(names):
        raise V4ContractError("feature names must be unique within a row")


@dataclass(frozen=True, slots=True)
class V4ObservationDocument:
    """One anonymous document containing only ordered truth-free V3 lines."""

    lines: tuple[V3ObservationLine, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.lines, tuple) or not self.lines:
            raise V4ContractError("observation document lines must be a non-empty tuple")
        if any(not isinstance(line, V3ObservationLine) for line in self.lines):
            raise V4ContractError("observation document may contain only V3 observation lines")
        ordinals = [line.line_ordinal for line in self.lines]
        if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
            raise V4ContractError("observation line ordinals must be unique and ordered")


@dataclass(frozen=True, slots=True)
class V4ObservationCorpus:
    """One anonymous, target-local corpus used for truth-free profiling."""

    documents: tuple[V4ObservationDocument, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.documents, tuple) or not self.documents:
            raise V4ContractError("observation corpus documents must be a non-empty tuple")
        if any(not isinstance(document, V4ObservationDocument) for document in self.documents):
            raise V4ContractError("observation corpus may contain only V4 observation documents")


@dataclass(frozen=True, slots=True)
class V4FeatureLine:
    """ID-free categorical and unit-scalar features for one ordered line."""

    rows: tuple[FeatureRow, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple) or not self.rows:
            raise V4ContractError("feature line rows must be a non-empty tuple")
        for row in self.rows:
            _validate_feature_row(row)


@dataclass(frozen=True, slots=True)
class V4FeatureDocument:
    """ID-free feature lines for one anonymous document."""

    lines: tuple[V4FeatureLine, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.lines, tuple) or not self.lines:
            raise V4ContractError("feature document lines must be a non-empty tuple")
        if any(not isinstance(line, V4FeatureLine) for line in self.lines):
            raise V4ContractError("feature document may contain only V4 feature lines")


@dataclass(frozen=True, slots=True)
class V4FeatureCorpus:
    """ID-free features preserving corpus/document/line order."""

    documents: tuple[V4FeatureDocument, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.documents, tuple) or not self.documents:
            raise V4ContractError("feature corpus documents must be a non-empty tuple")
        if any(not isinstance(document, V4FeatureDocument) for document in self.documents):
            raise V4ContractError("feature corpus may contain only V4 feature documents")


@dataclass(frozen=True, slots=True)
class V4LabeledFeatureLine:
    """One ID-free feature line paired positionally with development states."""

    feature_line: V4FeatureLine
    states: tuple[V3StructuralState, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.feature_line, V4FeatureLine):
            raise V4ContractError("labeled feature line requires a V4 feature line")
        if not isinstance(self.states, tuple):
            raise V4ContractError("labeled feature states must be a tuple")
        if len(self.states) != len(self.feature_line.rows):
            raise V4ContractError("feature rows and labeled states must have equal length")
        if any(state not in V3_STRUCTURAL_STATES for state in self.states):
            raise V4ContractError("labeled feature state is outside the five-state space")


@dataclass(frozen=True, slots=True)
class V4LabeledFeatureDocument:
    """ID-free labeled lines for one anonymous development document."""

    lines: tuple[V4LabeledFeatureLine, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.lines, tuple) or not self.lines:
            raise V4ContractError("labeled feature document lines must be a non-empty tuple")
        if any(not isinstance(line, V4LabeledFeatureLine) for line in self.lines):
            raise V4ContractError(
                "labeled feature document may contain only V4 labeled feature lines"
            )


@dataclass(frozen=True, slots=True)
class V4LabeledFeatureFamily:
    """One anonymous family of clean/mild labeled feature documents."""

    documents: tuple[V4LabeledFeatureDocument, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.documents, tuple) or not self.documents:
            raise V4ContractError("labeled feature family documents must be a non-empty tuple")
        if any(not isinstance(document, V4LabeledFeatureDocument) for document in self.documents):
            raise V4ContractError(
                "labeled feature family may contain only V4 labeled feature documents"
            )


__all__ = [
    "V4_FEATURE_ABLATIONS",
    "V4_PROFILE_MODES",
    "FeatureRow",
    "FeatureValue",
    "V4ContractError",
    "V4FeatureAblation",
    "V4FeatureCorpus",
    "V4FeatureDocument",
    "V4FeatureLine",
    "V4LabeledFeatureDocument",
    "V4LabeledFeatureFamily",
    "V4LabeledFeatureLine",
    "V4ObservationCorpus",
    "V4ObservationDocument",
    "V4ProfileMode",
]
