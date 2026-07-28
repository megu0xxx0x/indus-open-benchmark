"""Immutable, leakage-minimizing contracts for V3 development.

The MTAAC contracts intentionally expose only opaque identifiers, neutral
structure, degraded observations, and the mechanically projected five-state
training truth.  Raw source identifiers, archive paths, FORM/SEGM values, and
the V2 holdout have no field in this object graph.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

V3StructuralState = Literal[
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
]
V3ReportedDirection = Literal["known_source_order", "unknown_visual_order"]
MTAACTrainingRegime = Literal["clean", "mild"]

V3_STRUCTURAL_STATES: tuple[V3StructuralState, ...] = (
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
)
MTAAC_TRAINING_GATEWAY_VERSION = "mtaac-v2-training-gateway-v1"

_TAGGED_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_DOCUMENT_KEY = re.compile(r"^mtaac-document-source-id-sha256-v1:[0-9a-f]{64}$")
_TOKEN_KEY = re.compile(r"^mtaac-token-source-order-sha256-v1:[0-9a-f]{64}$")
_FORM_ID = re.compile(
    r"^(?:mtaac-word-form-sha256-v1|mtaac-artificial-word-form-sha256-v1):"
    r"[0-9a-f]{64}$"
)
_CLUSTER_IDENTIFIER = re.compile(r"^[0-9a-f]{64}$")


class V3ContractError(ValueError):
    """Raised when a V3 boundary object violates its public contract."""


@dataclass(frozen=True, slots=True)
class V3ObservationToken:
    """Truth-free source-neutral token presented to features and prediction."""

    observation_id: str | None
    damaged: bool

    def __post_init__(self) -> None:
        if self.observation_id is not None and (
            not isinstance(self.observation_id, str)
            or not self.observation_id
            or any(
                ord(character) < 0x21 or ord(character) == 0x7F for character in self.observation_id
            )
        ):
            raise V3ContractError("observation ID must be a non-empty opaque identifier or null")
        if not isinstance(self.damaged, bool):
            raise V3ContractError("observation damaged marker must be boolean")
        if self.damaged != (self.observation_id is None):
            raise V3ContractError("observation damage marker and null identifier disagree")


@dataclass(frozen=True, slots=True)
class V3ObservationLine:
    """Truth-free ordered sequence accepted by feature and prediction code."""

    line_ordinal: int
    reported_direction: V3ReportedDirection
    tokens: tuple[V3ObservationToken, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.line_ordinal, bool)
            or not isinstance(self.line_ordinal, int)
            or self.line_ordinal < 0
        ):
            raise V3ContractError("observation line ordinal must be a non-negative integer")
        if self.reported_direction not in {
            "known_source_order",
            "unknown_visual_order",
        }:
            raise V3ContractError("observation line direction is unsupported")
        if not isinstance(self.tokens, tuple) or not self.tokens:
            raise V3ContractError("observation line tokens must be a non-empty tuple")


@dataclass(frozen=True, slots=True)
class MTAACTrainingToken:
    """One retained token in canonical model order.

    ``observed_form_id`` is absent exactly when the degradation marked the
    retained token as damaged.  Damaged tokens are observations, not dropped
    rows.
    """

    token_key: str
    observed_form_id: str | None
    state: V3StructuralState
    damaged: bool

    def __post_init__(self) -> None:
        if not isinstance(self.token_key, str) or _TOKEN_KEY.fullmatch(self.token_key) is None:
            raise V3ContractError("training token key must be an opaque MTAAC token hash")
        if self.observed_form_id is not None and (
            not isinstance(self.observed_form_id, str)
            or _FORM_ID.fullmatch(self.observed_form_id) is None
        ):
            raise V3ContractError("training form ID must be an opaque MTAAC form hash or null")
        if self.state not in V3_STRUCTURAL_STATES:
            raise V3ContractError("training state is outside the joint five-state space")
        if not isinstance(self.damaged, bool):
            raise V3ContractError("training damaged marker must be boolean")
        if self.damaged != (self.observed_form_id is None):
            raise V3ContractError("training damage marker and null form observation disagree")


@dataclass(frozen=True, slots=True)
class MTAACTrainingLine:
    """One source-neutral line whose token tuple is already in model order."""

    line_ordinal: int
    reported_direction: V3ReportedDirection
    tokens: tuple[MTAACTrainingToken, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.line_ordinal, bool)
            or not isinstance(self.line_ordinal, int)
            or self.line_ordinal < 0
        ):
            raise V3ContractError("training line ordinal must be a non-negative integer")
        if self.reported_direction not in {
            "known_source_order",
            "unknown_visual_order",
        }:
            raise V3ContractError("training line direction is unsupported")
        if not isinstance(self.tokens, tuple) or not self.tokens:
            raise V3ContractError("training line tokens must be a non-empty tuple")
        token_keys = [token.token_key for token in self.tokens]
        if len(set(token_keys)) != len(token_keys):
            raise V3ContractError("training line token keys must be unique")

    def to_observation(self) -> V3ObservationLine:
        """Remove token identity and truth before feature extraction."""

        return V3ObservationLine(
            line_ordinal=self.line_ordinal,
            reported_direction=self.reported_direction,
            tokens=tuple(
                V3ObservationToken(
                    observation_id=token.observed_form_id,
                    damaged=token.damaged,
                )
                for token in self.tokens
            ),
        )


@dataclass(frozen=True, slots=True)
class MTAACTrainingDocument:
    """One representative training family under one frozen degradation."""

    document_key: str
    cluster_identifier: str
    regime: MTAACTrainingRegime
    replica_index: Literal[0]
    lines: tuple[MTAACTrainingLine, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.document_key, str)
            or _DOCUMENT_KEY.fullmatch(self.document_key) is None
        ):
            raise V3ContractError("training document key must be an opaque MTAAC document hash")
        if (
            not isinstance(self.cluster_identifier, str)
            or _CLUSTER_IDENTIFIER.fullmatch(self.cluster_identifier) is None
        ):
            raise V3ContractError("training cluster identifier must be a SHA-256 digest")
        if self.regime not in {"clean", "mild"}:
            raise V3ContractError("training regime must be clean or mild")
        if isinstance(self.replica_index, bool) or self.replica_index != 0:
            raise V3ContractError("only representative replica zero may enter training")
        if not isinstance(self.lines, tuple) or not self.lines:
            raise V3ContractError("training document lines must be a non-empty tuple")
        line_ordinals = [line.line_ordinal for line in self.lines]
        if line_ordinals != sorted(line_ordinals) or len(set(line_ordinals)) != len(line_ordinals):
            raise V3ContractError("training line ordinals must be unique and ordered")
        token_keys = [token.token_key for line in self.lines for token in line.tokens]
        if len(set(token_keys)) != len(token_keys):
            raise V3ContractError("training document token keys must be unique")


@dataclass(frozen=True, slots=True)
class MTAACTrainingView:
    """All representative training families for one degradation regime."""

    regime: MTAACTrainingRegime
    documents: tuple[MTAACTrainingDocument, ...]

    def __post_init__(self) -> None:
        if self.regime not in {"clean", "mild"}:
            raise V3ContractError("training view regime must be clean or mild")
        if not isinstance(self.documents, tuple) or not self.documents:
            raise V3ContractError("training view documents must be a non-empty tuple")
        if any(document.regime != self.regime for document in self.documents):
            raise V3ContractError("training document regime does not match its view")
        document_keys = [document.document_key for document in self.documents]
        if document_keys != sorted(document_keys) or len(set(document_keys)) != len(document_keys):
            raise V3ContractError("training documents must be uniquely key-sorted")
        cluster_identifiers = [document.cluster_identifier for document in self.documents]
        if len(set(cluster_identifiers)) != len(cluster_identifiers):
            raise V3ContractError("each training document must be its own complete-sequence family")


@dataclass(frozen=True, slots=True)
class MTAACTrainingBundle:
    """One-way V3 training output with no corpus or holdout object."""

    gateway_version: str
    source_commit: str
    v2_freeze_commit: str
    source_archive_sha256: str
    selected_manifest_sha256: str
    evaluation_corpus_sha256: str
    v2_protocol_sha256: str
    split_manifest_sha256: str
    split_seed: int
    split_test_fraction: float
    training_family_count: int
    excluded_holdout_family_count: int
    states: tuple[V3StructuralState, ...]
    clean: MTAACTrainingView
    mild: MTAACTrainingView

    def __post_init__(self) -> None:
        if self.gateway_version != MTAAC_TRAINING_GATEWAY_VERSION:
            raise V3ContractError("training gateway version is unsupported")
        for field_name in ("source_commit", "v2_freeze_commit"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or _GIT_COMMIT.fullmatch(value) is None:
                raise V3ContractError(f"{field_name} must be a lowercase 40-hex commit")
        for field_name in (
            "source_archive_sha256",
            "selected_manifest_sha256",
            "evaluation_corpus_sha256",
            "v2_protocol_sha256",
            "split_manifest_sha256",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or _TAGGED_SHA256.fullmatch(value) is None:
                raise V3ContractError(f"{field_name} must be tagged SHA-256")
        if isinstance(self.split_seed, bool) or not isinstance(self.split_seed, int):
            raise V3ContractError("training split seed must be an integer")
        if (
            isinstance(self.split_test_fraction, bool)
            or not isinstance(self.split_test_fraction, (int, float))
            or not math.isfinite(self.split_test_fraction)
            or not 0.0 < self.split_test_fraction < 1.0
        ):
            raise V3ContractError("training split fraction must be finite and in (0, 1)")
        for field_name in ("training_family_count", "excluded_holdout_family_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise V3ContractError(f"{field_name} must be a positive integer")
        if self.states != V3_STRUCTURAL_STATES:
            raise V3ContractError("training bundle must declare the exact five-state order")
        if self.clean.regime != "clean" or self.mild.regime != "mild":
            raise V3ContractError("training bundle views must be clean then mild")
        if (
            len(self.clean.documents) != self.training_family_count
            or len(self.mild.documents) != self.training_family_count
        ):
            raise V3ContractError("training view counts do not match the family commitment")
        clean_families = {
            document.document_key: document.cluster_identifier for document in self.clean.documents
        }
        mild_families = {
            document.document_key: document.cluster_identifier for document in self.mild.documents
        }
        if clean_families != mild_families:
            raise V3ContractError("clean and mild views must contain the same training families")


__all__ = [
    "MTAAC_TRAINING_GATEWAY_VERSION",
    "V3_STRUCTURAL_STATES",
    "MTAACTrainingBundle",
    "MTAACTrainingDocument",
    "MTAACTrainingLine",
    "MTAACTrainingRegime",
    "MTAACTrainingToken",
    "MTAACTrainingView",
    "V3ContractError",
    "V3ObservationLine",
    "V3ObservationToken",
    "V3ReportedDirection",
    "V3StructuralState",
]
