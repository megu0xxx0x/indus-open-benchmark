"""Deterministic MTAAC known-script control evaluator.

The public real-source entry point accepts exact archive and protocol bytes and
performs every source gate before splitting or scoring.  A separate synthetic
fixture entry point exists solely to exercise the instrument without producing
a real ``go``/``no_go`` report.  Neither entry point performs network access,
Git discovery, clock access, or a custody/blindness attestation.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Literal

from indusbench.mtaac import (
    MTAAC_GOLD_CLASSES,
    MTAAC_PINNED_COMMIT,
    GoldClass,
    MTAACCorpus,
    MTAACError,
    MTAACGoldDocument,
    MTAACModelDocument,
    MTAACModelToken,
    MTAACProvenance,
    derive_mtaac_gold_classes,
    opaque_document_key,
    opaque_form_sign_id,
    opaque_token_key,
    parse_mtaac_archive,
    parse_mtaac_directory,
)

MTAAC_CONTROL_PROTOCOL_VERSION = "mtaac-real-control-v1"
# Updated only when the exact normative JSON and implementation are reviewed
# together.  The evaluator refuses any other protocol bytes.
MTAAC_CONTROL_PROTOCOL_SHA256 = (
    "sha256:25fbea943a662144700dfca418927758ad3319817bc42191c4c8e6e45fc518b3"
)
MTAAC_CONTROL_PROTOCOL_ID = "mtaac-known-script-control-v1"
MTAAC_REAL_ARCHIVE_SHA256 = (
    "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091"
)
MTAAC_REAL_SELECTED_MANIFEST_SHA256 = (
    "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e"
)
MTAAC_REAL_EVALUATION_CORPUS_SHA256 = (
    "sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312"
)

Partition = Literal["train", "test"]
ReportedDirection = Literal["known_source_order", "unknown_visual_order"]
TerminalStatus = Literal[
    "fixture_only",
    "not_identifiable",
    "insufficient_evidence",
    "go",
    "no_go",
]

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_TAGGED_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIXTURE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_DETERMINATIVE_PATTERN = re.compile(r"\{[^{}]*\}")
_PLACEHOLDER_STEMS = frozenset(("", "_", "_(_)", "x", "n", "...", "…"))

_SELECTED_MANIFEST_DOMAIN = b"indusbench:mtaac:selected-manifest:v1\x00"
_EVALUATION_CORPUS_DOMAIN = b"indusbench:mtaac:evaluation-corpus:v1\x00"
_CLUSTER_DOMAIN = b"indusbench:mtaac:document-form-sequence:v1\x00"
_SPLIT_DOMAIN = b"indusbench:mtaac:split:v1\x00"
_SPLIT_MANIFEST_DOMAIN = b"indusbench:mtaac:split-manifest:v1\x00"
_LINE_DOMAIN = b"indusbench:mtaac:anonymous-line:v1\x00"
_OBSERVATION_DOMAIN = b"indusbench:mtaac:observation:v1\x00"
_PERMUTATION_DOMAIN = b"indusbench:mtaac:label-vector-permutation:v1\x00"
_EVENT_DOMAINS = {
    "window_anchor": b"indusbench:mtaac:window-anchor:v1\x00",
    "reverse": b"indusbench:mtaac:reverse:v1\x00",
    "direction_unknown": b"indusbench:mtaac:direction-unknown:v1\x00",
    "pseudo_surface_variant_event": (b"indusbench:mtaac:pseudo-surface-variant-event:v1\x00"),
    "pseudo_surface_variant_id": (b"indusbench:mtaac:pseudo-surface-variant-id:v1\x00"),
    "damage": b"indusbench:mtaac:damage:v1\x00",
    "duplicate": b"indusbench:mtaac:duplicate:v1\x00",
}

FULL_FEATURES = (
    "opaque_form_id",
    "position_bucket",
    "previous_opaque_form_id",
    "next_opaque_form_id",
    "line_length_bucket",
    "reported_direction",
)
POSITION_FEATURES = (
    "position_bucket",
    "line_length_bucket",
    "reported_direction",
)
LEXICON_FEATURES = ("opaque_form_id",)


class MTAACControlError(ValueError):
    """Raised before a scientific report when a normative invariant fails."""


@dataclass(frozen=True, slots=True)
class MTAACControlAttestation:
    """Caller declarations; these are commitments, not independently proven facts."""

    protocol_sha256: str
    pre_result_code_commit: str
    data_origin: Literal["fixed_real_source", "project_authored_synthetic_fixture"]
    external_data_used: bool
    fixture_id: str | None = None


@dataclass(frozen=True, slots=True)
class MTAACSplitEntry:
    document_key: str
    cluster_identifier: str
    partition: Partition


@dataclass(frozen=True, slots=True)
class MTAACSplitManifest:
    seed: int
    test_fraction: float
    entries: tuple[MTAACSplitEntry, ...]
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class MTAACRegime:
    name: Literal["clean", "mild", "harsh"]
    max_line_tokens: int | None
    pseudo_surface_variant_rate: float
    damage_rate: float
    reverse_rate: float
    direction_unknown_rate: float
    duplicate_rate: float

    def __post_init__(self) -> None:
        if self.name not in {"clean", "mild", "harsh"}:
            raise MTAACControlError("regime name must be clean, mild, or harsh")
        if self.max_line_tokens is not None and (
            isinstance(self.max_line_tokens, bool)
            or not isinstance(self.max_line_tokens, int)
            or self.max_line_tokens < 1
        ):
            raise MTAACControlError("max_line_tokens must be null or a positive integer")
        for field_name in (
            "pseudo_surface_variant_rate",
            "damage_rate",
            "reverse_rate",
            "direction_unknown_rate",
            "duplicate_rate",
        ):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise MTAACControlError(f"{field_name} must be finite and in [0, 1]")


CLEAN_REGIME = MTAACRegime("clean", None, 0.0, 0.0, 0.0, 0.0, 0.0)
MILD_REGIME = MTAACRegime("mild", 7, 0.3, 0.1, 0.5, 0.15, 0.25)
HARSH_REGIME = MTAACRegime("harsh", 4, 0.5, 0.25, 0.5, 0.4, 0.5)


@dataclass(frozen=True, slots=True)
class MTAACObservedToken:
    """Model-safe degraded occurrence; no raw source or gold field is present."""

    token_key: str
    observed_form_id: str | None
    source_order: int
    visual_index: int
    pseudo_variant_applied: bool
    damaged: bool


@dataclass(frozen=True, slots=True)
class MTAACObservedLine:
    line_ordinal: int
    reported_direction: ReportedDirection
    visual_reversed: bool
    tokens: tuple[MTAACObservedToken, ...]


@dataclass(frozen=True, slots=True)
class MTAACObservedDocument:
    observation_key: str
    document_key: str
    partition: Partition
    replica_index: int
    lines: tuple[MTAACObservedLine, ...]


@dataclass(frozen=True, slots=True)
class MTAACDegradedCorpus:
    protocol_version: str
    seed: int
    regime: MTAACRegime
    split_manifest_sha256: str
    observations: tuple[MTAACObservedDocument, ...]


@dataclass(frozen=True, slots=True)
class _SourceToken:
    model: MTAACModelToken
    source_order: int


@dataclass(frozen=True, slots=True)
class _SourceLine:
    line_ordinal: int
    line_key: str
    tokens: tuple[_SourceToken, ...]
    exact_form_sequence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SourceDocument:
    document_key: str
    lines: tuple[_SourceLine, ...]
    complete_form_sequence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Example:
    document_key: str
    observation_key: str
    replica_index: int
    line_ordinal: int
    model_order: int
    token_key: str
    features: tuple[tuple[str, str], ...]
    true_class: GoldClass
    weight: float


def validate_mtaac_control_protocol(protocol_bytes: bytes) -> dict[str, Any]:
    """Validate the exact normative protocol bytes and implementation binding."""

    if not isinstance(protocol_bytes, bytes) or not protocol_bytes:
        raise MTAACControlError("protocol must be supplied as non-empty bytes")
    actual_digest = _tagged_sha256(protocol_bytes)
    if actual_digest != MTAAC_CONTROL_PROTOCOL_SHA256:
        raise MTAACControlError("protocol bytes do not match MTAAC_CONTROL_PROTOCOL_SHA256")
    try:
        protocol = json.loads(protocol_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MTAACControlError("protocol bytes are not valid UTF-8 JSON") from error
    if not isinstance(protocol, dict):
        raise MTAACControlError("protocol root must be an object")
    if protocol.get("protocol_id") != MTAAC_CONTROL_PROTOCOL_ID:
        raise MTAACControlError("protocol_id does not match the implementation")
    implementation = _mapping(protocol.get("implementation"), "implementation")
    if implementation.get("normative_module") != "indusbench.mtaac_control":
        raise MTAACControlError("protocol normative_module does not match")
    if implementation.get("protocol_version") != MTAAC_CONTROL_PROTOCOL_VERSION:
        raise MTAACControlError("protocol version does not match the implementation")
    source = _mapping(protocol.get("source"), "source")
    if source.get("commit") != MTAAC_PINNED_COMMIT:
        raise MTAACControlError("protocol source commit does not match the adapter")
    if source.get("archive_sha256") != MTAAC_REAL_ARCHIVE_SHA256:
        raise MTAACControlError("protocol source archive digest does not match")
    if source.get("expected_selected_manifest_sha256") != MTAAC_REAL_SELECTED_MANIFEST_SHA256:
        raise MTAACControlError("protocol selected manifest digest does not match")
    if source.get("expected_evaluation_corpus_sha256") != MTAAC_REAL_EVALUATION_CORPUS_SHA256:
        raise MTAACControlError("protocol evaluation-corpus digest does not match")
    return protocol


def validate_mtaac_control_attestation(
    attestation: MTAACControlAttestation,
    *,
    expected_origin: Literal["fixed_real_source", "project_authored_synthetic_fixture"],
) -> None:
    if not isinstance(attestation, MTAACControlAttestation):
        raise MTAACControlError("a typed MTAAC control attestation is required")
    if expected_origin not in {
        "fixed_real_source",
        "project_authored_synthetic_fixture",
    }:
        raise MTAACControlError("expected attestation origin is unsupported")
    if attestation.protocol_sha256 != MTAAC_CONTROL_PROTOCOL_SHA256:
        raise MTAACControlError("attested protocol digest does not match")
    if not isinstance(attestation.external_data_used, bool):
        raise MTAACControlError("external_data_used must be boolean")
    if not isinstance(attestation.pre_result_code_commit, str) or not _COMMIT_PATTERN.fullmatch(
        attestation.pre_result_code_commit
    ):
        raise MTAACControlError("pre_result_code_commit must be caller-declared lowercase 40-hex")
    if attestation.data_origin != expected_origin:
        raise MTAACControlError("attested data origin does not match the entry point")
    if expected_origin == "fixed_real_source":
        if not attestation.external_data_used or attestation.fixture_id is not None:
            raise MTAACControlError("real-source attestation fields are inconsistent")
    elif (
        attestation.external_data_used
        or not isinstance(attestation.fixture_id, str)
        or not _FIXTURE_ID_PATTERN.fullmatch(attestation.fixture_id)
    ):
        raise MTAACControlError("synthetic fixture attestation fields are inconsistent")


def build_mtaac_split(
    corpus: MTAACCorpus,
    *,
    seed: int = 0,
    test_fraction: float = 0.25,
) -> MTAACSplitManifest:
    """Create the exact cluster-safe source-document split."""

    _validate_seed(seed)
    if (
        isinstance(test_fraction, bool)
        or not isinstance(test_fraction, (int, float))
        or not math.isfinite(test_fraction)
        or not 0.0 < test_fraction < 1.0
    ):
        raise MTAACControlError("test_fraction must be finite and strictly between 0 and 1")
    source_documents = _source_documents(corpus)
    clusters: dict[str, list[str]] = defaultdict(list)
    for document in source_documents:
        identifier = _document_cluster_identifier(document.complete_form_sequence)
        clusters[identifier].append(document.document_key)
    if len(clusters) < 2:
        raise MTAACControlError("at least two complete-document clusters are required")
    ranked_clusters = sorted(
        clusters,
        key=lambda identifier: (
            hashlib.sha256(
                _SPLIT_DOMAIN + _u64(seed) + _frame(identifier.encode("ascii"))
            ).digest(),
            identifier,
        ),
    )
    test_count = max(
        1,
        min(
            len(ranked_clusters) - 1,
            math.floor(len(ranked_clusters) * test_fraction + 0.5),
        ),
    )
    test_clusters = set(ranked_clusters[:test_count])
    entries = tuple(
        sorted(
            (
                MTAACSplitEntry(
                    document_key=document_key,
                    cluster_identifier=identifier,
                    partition="test" if identifier in test_clusters else "train",
                )
                for identifier, document_keys in clusters.items()
                for document_key in document_keys
            ),
            key=lambda entry: entry.document_key,
        )
    )
    manifest_sha256 = _split_manifest_digest(seed, test_fraction, entries)
    split = MTAACSplitManifest(seed, float(test_fraction), entries, manifest_sha256)
    validate_mtaac_split(corpus, split)
    return split


def validate_mtaac_split(corpus: MTAACCorpus, split: MTAACSplitManifest) -> None:
    """Re-derive a split and reject partition or cluster leakage."""

    if not isinstance(split, MTAACSplitManifest):
        raise MTAACControlError("split must be an MTAACSplitManifest")
    _validate_seed(split.seed)
    if (
        isinstance(split.test_fraction, bool)
        or not isinstance(split.test_fraction, (int, float))
        or not math.isfinite(split.test_fraction)
        or not 0.0 < split.test_fraction < 1.0
    ):
        raise MTAACControlError("split test_fraction is invalid")
    expected = _build_split_without_validation(
        corpus,
        seed=split.seed,
        test_fraction=split.test_fraction,
    )
    if split != expected:
        raise MTAACControlError("split does not match the deterministic split contract")


def _build_split_without_validation(
    corpus: MTAACCorpus,
    *,
    seed: int,
    test_fraction: float,
) -> MTAACSplitManifest:
    source_documents = _source_documents(corpus)
    clusters: dict[str, list[str]] = defaultdict(list)
    for document in source_documents:
        clusters[_document_cluster_identifier(document.complete_form_sequence)].append(
            document.document_key
        )
    if len(clusters) < 2:
        raise MTAACControlError("at least two complete-document clusters are required")
    ranked = sorted(
        clusters,
        key=lambda identifier: (
            hashlib.sha256(
                _SPLIT_DOMAIN + _u64(seed) + _frame(identifier.encode("ascii"))
            ).digest(),
            identifier,
        ),
    )
    test_count = max(
        1,
        min(len(ranked) - 1, math.floor(len(ranked) * test_fraction + 0.5)),
    )
    test = set(ranked[:test_count])
    entries = tuple(
        sorted(
            (
                MTAACSplitEntry(
                    document_key=document_key,
                    cluster_identifier=identifier,
                    partition="test" if identifier in test else "train",
                )
                for identifier, keys in clusters.items()
                for document_key in keys
            ),
            key=lambda entry: entry.document_key,
        )
    )
    return MTAACSplitManifest(
        seed=seed,
        test_fraction=float(test_fraction),
        entries=entries,
        manifest_sha256=_split_manifest_digest(seed, test_fraction, entries),
    )


def degrade_mtaac_corpus(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    regime: MTAACRegime,
    *,
    seed: int = 0,
) -> MTAACDegradedCorpus:
    """Apply the normative degradation without reading truth-valued fields."""

    _validate_seed(seed)
    validate_mtaac_split(corpus, split)
    if not isinstance(regime, MTAACRegime):
        raise MTAACControlError("regime must be an MTAACRegime")
    return _degrade(corpus, split, regime, seed=seed, form_override=None)


def validate_mtaac_degradation(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    degraded: MTAACDegradedCorpus,
) -> None:
    """Reject observations not exactly re-derived from source and configuration."""

    if not isinstance(degraded, MTAACDegradedCorpus):
        raise MTAACControlError("degraded must be an MTAACDegradedCorpus")
    if not isinstance(degraded.regime, MTAACRegime):
        raise MTAACControlError("degraded regime must be an MTAACRegime")
    _validate_seed(degraded.seed)
    expected = degrade_mtaac_corpus(
        corpus,
        split,
        degraded.regime,
        seed=degraded.seed,
    )
    if degraded != expected:
        raise MTAACControlError("degraded observations do not match the deterministic contract")


def _degrade(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    regime: MTAACRegime,
    *,
    seed: int,
    form_override: Mapping[str, str] | None,
) -> MTAACDegradedCorpus:
    partition_by_document: dict[str, Partition] = {
        entry.document_key: entry.partition for entry in split.entries
    }
    observations: list[MTAACObservedDocument] = []
    for document in _source_documents(corpus):
        lines: list[MTAACObservedLine] = []
        for line in document.lines:
            retained = _retained_source_tokens(document.document_key, line, regime, seed)
            reversed_visual = (
                _event_uniform("reverse", seed, document.document_key, line.line_ordinal)
                < regime.reverse_rate
            )
            unknown_direction = (
                _event_uniform(
                    "direction_unknown",
                    seed,
                    document.document_key,
                    line.line_ordinal,
                )
                < regime.direction_unknown_rate
            )
            visual = list(reversed(retained)) if reversed_visual else list(retained)
            observed_tokens: list[MTAACObservedToken] = []
            for visual_index, source_token in enumerate(visual):
                base_form_id = (
                    source_token.model.sign_id
                    if form_override is None
                    else form_override[source_token.model.token_key]
                )
                pseudo = (
                    _event_uniform(
                        "pseudo_surface_variant_event",
                        seed,
                        document.document_key,
                        line.line_ordinal,
                        source_token.source_order,
                    )
                    < regime.pseudo_surface_variant_rate
                )
                observed_form_id = (
                    _pseudo_variant_id(
                        seed,
                        document.document_key,
                        line.line_ordinal,
                        source_token.source_order,
                        base_form_id,
                    )
                    if pseudo
                    else base_form_id
                )
                damaged = (
                    _event_uniform(
                        "damage",
                        seed,
                        document.document_key,
                        line.line_ordinal,
                        source_token.source_order,
                    )
                    < regime.damage_rate
                )
                observed_tokens.append(
                    MTAACObservedToken(
                        token_key=source_token.model.token_key,
                        observed_form_id=None if damaged else observed_form_id,
                        source_order=source_token.source_order,
                        visual_index=visual_index,
                        pseudo_variant_applied=pseudo,
                        damaged=damaged,
                    )
                )
            lines.append(
                MTAACObservedLine(
                    line_ordinal=line.line_ordinal,
                    reported_direction=(
                        "unknown_visual_order" if unknown_direction else "known_source_order"
                    ),
                    visual_reversed=reversed_visual,
                    tokens=tuple(observed_tokens),
                )
            )
        duplicate = (
            _document_event_uniform("duplicate", seed, document.document_key)
            < regime.duplicate_rate
        )
        replica_count = 2 if duplicate else 1
        for replica_index in range(replica_count):
            observations.append(
                MTAACObservedDocument(
                    observation_key=_observation_key(
                        document.document_key,
                        regime.name,
                        replica_index,
                        seed,
                        split.manifest_sha256,
                    ),
                    document_key=document.document_key,
                    partition=partition_by_document[document.document_key],
                    replica_index=replica_index,
                    lines=tuple(lines),
                )
            )
    return MTAACDegradedCorpus(
        protocol_version=MTAAC_CONTROL_PROTOCOL_VERSION,
        seed=seed,
        regime=regime,
        split_manifest_sha256=split.manifest_sha256,
        observations=tuple(
            sorted(
                observations,
                key=lambda item: (item.document_key, item.replica_index),
            )
        ),
    )


def validate_nested_mtaac_degradations(
    clean: MTAACDegradedCorpus,
    mild: MTAACDegradedCorpus,
    harsh: MTAACDegradedCorpus,
) -> None:
    """Verify cumulative windows and rate-event inclusion before scoring."""

    if not all(isinstance(degraded, MTAACDegradedCorpus) for degraded in (clean, mild, harsh)):
        raise MTAACControlError("nested regimes must be MTAACDegradedCorpus values")
    if (
        clean.seed != mild.seed
        or clean.seed != harsh.seed
        or clean.split_manifest_sha256 != mild.split_manifest_sha256
        or clean.split_manifest_sha256 != harsh.split_manifest_sha256
    ):
        raise MTAACControlError("nested regimes must share seed and split")
    if clean.regime != CLEAN_REGIME or mild.regime != MILD_REGIME or harsh.regime != HARSH_REGIME:
        raise MTAACControlError("nested regimes must equal the frozen configurations")

    representatives = [
        {
            observation.document_key: observation
            for observation in degraded.observations
            if observation.replica_index == 0
        }
        for degraded in (clean, mild, harsh)
    ]
    if not (set(representatives[0]) == set(representatives[1]) == set(representatives[2])):
        raise MTAACControlError("nested regimes do not contain the same source families")
    for document_key in representatives[0]:
        by_regime = [mapping[document_key] for mapping in representatives]
        line_maps = [{line.line_ordinal: line for line in document.lines} for document in by_regime]
        if not (set(line_maps[0]) == set(line_maps[1]) == set(line_maps[2])):
            raise MTAACControlError("nested regimes do not contain the same source lines")
        for line_ordinal in line_maps[0]:
            clean_tokens, mild_tokens, harsh_tokens = (
                {token.token_key: token for token in lines[line_ordinal].tokens}
                for lines in line_maps
            )
            if not set(harsh_tokens) <= set(mild_tokens) <= set(clean_tokens):
                raise MTAACControlError("nested line windows are not cumulative")
            shared_harsh_keys = set(harsh_tokens)
            if {
                key
                for key, token in mild_tokens.items()
                if key in shared_harsh_keys and token.damaged
            } - {key for key, token in harsh_tokens.items() if token.damaged}:
                raise MTAACControlError("mild damage events are not a harsh subset")
            if {
                key
                for key, token in mild_tokens.items()
                if key in shared_harsh_keys and token.pseudo_variant_applied
            } - {key for key, token in harsh_tokens.items() if token.pseudo_variant_applied}:
                raise MTAACControlError("mild pseudo-variant events are not a harsh subset")
            if (
                line_maps[1][line_ordinal].visual_reversed
                != line_maps[2][line_ordinal].visual_reversed
            ):
                raise MTAACControlError("equal reverse rates produced different events")
            if (
                line_maps[1][line_ordinal].reported_direction == "unknown_visual_order"
                and line_maps[2][line_ordinal].reported_direction != "unknown_visual_order"
            ):
                raise MTAACControlError("mild unknown-direction events are not a harsh subset")
    mild_duplicates = _duplicated_families(mild)
    harsh_duplicates = _duplicated_families(harsh)
    if not mild_duplicates <= harsh_duplicates:
        raise MTAACControlError("mild duplicate events are not a harsh subset")


def _derive_selected_manifest_from_metadata(corpus: MTAACCorpus) -> str:
    """Rebuild the parser's selected-member manifest from retained metadata."""

    if not isinstance(corpus, MTAACCorpus) or not isinstance(
        corpus.provenance,
        MTAACProvenance,
    ):
        raise MTAACControlError("corpus provenance is invalid")
    provenance = corpus.provenance
    if (
        len(corpus.gold_documents) != provenance.admitted_document_count
        or len(corpus.quarantined_documents) != provenance.quarantined_document_count
        or len(corpus.gold_documents) + len(corpus.quarantined_documents)
        != provenance.selected_document_count
    ):
        raise MTAACControlError("selected document counts do not match corpus metadata")
    if not isinstance(
        provenance.selected_manifest_sha256,
        str,
    ) or not _TAGGED_SHA256_PATTERN.fullmatch(provenance.selected_manifest_sha256):
        raise MTAACControlError("selected manifest commitment is not tagged SHA-256")

    entries: list[tuple[bytes, int, bytes]] = []
    seen_paths: set[bytes] = set()
    for document in (*corpus.gold_documents, *corpus.quarantined_documents):
        corpus_path = getattr(document, "corpus_path", None)
        source_bytes = getattr(document, "source_bytes", None)
        source_sha256 = getattr(document, "source_sha256", None)
        if not isinstance(corpus_path, str) or not corpus_path:
            raise MTAACControlError("selected document metadata has an invalid path")
        try:
            path_bytes = corpus_path.encode("ascii")
        except UnicodeEncodeError as error:
            raise MTAACControlError("selected document metadata path must be ASCII") from error
        if path_bytes in seen_paths:
            raise MTAACControlError("selected document metadata paths must be unique")
        seen_paths.add(path_bytes)
        if (
            isinstance(source_bytes, bool)
            or not isinstance(source_bytes, int)
            or not 0 <= source_bytes < 1 << 64
        ):
            raise MTAACControlError("selected document metadata has an invalid byte length")
        if not isinstance(
            source_sha256,
            str,
        ) or not _TAGGED_SHA256_PATTERN.fullmatch(source_sha256):
            raise MTAACControlError("selected document metadata has an invalid source digest")
        entries.append(
            (
                path_bytes,
                source_bytes,
                bytes.fromhex(source_sha256.removeprefix("sha256:")),
            )
        )

    digest = hashlib.sha256()
    digest.update(_SELECTED_MANIFEST_DOMAIN)
    for path_bytes, source_bytes, source_digest in sorted(
        entries,
        key=lambda entry: entry[0],
    ):
        digest.update(_frame(path_bytes))
        digest.update(_u64(source_bytes))
        digest.update(source_digest)
    return "sha256:" + digest.hexdigest()


def _validate_selected_manifest_metadata(corpus: MTAACCorpus) -> None:
    if (
        _derive_selected_manifest_from_metadata(corpus)
        != corpus.provenance.selected_manifest_sha256
    ):
        raise MTAACControlError("selected manifest commitment does not match corpus metadata")


def _evaluation_corpus_fingerprint(corpus: MTAACCorpus) -> str:
    """Commit every value that can affect observations, truth, or diagnostics.

    Container formatting and unused annotation columns are excluded. Therefore
    line-ending changes, trailing blank lines, and edits to HEAD/DEPREL/MISC
    cannot disguise the same effective evaluation corpus as a fixture.
    """

    source_by_key = {document.document_key: document for document in _source_documents(corpus)}
    digest = hashlib.sha256(_EVALUATION_CORPUS_DOMAIN)
    documents = sorted(corpus.gold_documents, key=lambda document: document.p_identifier)
    digest.update(_u64(len(documents)))
    seen_identifiers: set[str] = set()
    for document in documents:
        if document.p_identifier in seen_identifiers:
            raise MTAACControlError("evaluation corpus source identifiers must be unique")
        seen_identifiers.add(document.p_identifier)
        source_document = source_by_key[document.document_key]
        gold_by_token = {token.token_key: token for token in document.tokens}
        digest.update(_frame(document.p_identifier.encode("ascii")))
        digest.update(_u64(len(source_document.lines)))
        for line in source_document.lines:
            digest.update(_u64(line.line_ordinal))
            digest.update(_u64(len(line.tokens)))
            for source_token in line.tokens:
                token = gold_by_token[source_token.model.token_key]
                if len(token.classes) > 1:
                    raise MTAACControlError("evaluation corpus gold classes overlap")
                projected_class = token.classes[0] if token.classes else "context_only"
                diagnostic_stem = _diagnostic_stem(token.segm) if token.classes else None
                if diagnostic_stem in _PLACEHOLDER_STEMS:
                    diagnostic_stem = None
                digest.update(_u64(source_token.source_order))
                for value in (token.form, projected_class):
                    digest.update(_frame(value.encode("utf-8")))
                if diagnostic_stem is None:
                    digest.update(b"\x00")
                else:
                    digest.update(b"\x01")
                    digest.update(_frame(diagnostic_stem.encode("utf-8")))
    return "sha256:" + digest.hexdigest()


def _source_documents(corpus: MTAACCorpus) -> tuple[_SourceDocument, ...]:
    if not isinstance(corpus, MTAACCorpus):
        raise MTAACControlError("corpus must be an MTAACCorpus")
    _validate_selected_manifest_metadata(corpus)
    models = {document.document_key: document for document in corpus.model_documents}
    golds = {document.document_key: document for document in corpus.gold_documents}
    if len(models) != len(corpus.model_documents) or len(golds) != len(corpus.gold_documents):
        raise MTAACControlError("document keys must be unique")
    if set(models) != set(golds) or not models:
        raise MTAACControlError("model and gold document views must align exactly")
    output: list[_SourceDocument] = []
    all_model_fields = set(MTAACModelToken.__dataclass_fields__)
    if all_model_fields != {"token_key", "sign_id", "visual_index"}:
        raise MTAACControlError("model token surface contains an undeclared feature field")
    seen_token_keys: set[str] = set()
    for document_key in sorted(models):
        model = models[document_key]
        gold = golds[document_key]
        _validate_document_alignment(model, gold, seen_token_keys)
        lines: list[_SourceLine] = []
        current_raw_key: str | None = None
        current_tokens: list[_SourceToken] = []
        closed_raw_keys: set[str] = set()
        line_ordinal = 0
        for model_token, gold_token in zip(model.tokens, gold.tokens, strict=True):
            raw_key = _raw_line_key(gold_token.position, model_token.visual_index)
            if current_raw_key is None:
                current_raw_key = raw_key
            elif raw_key != current_raw_key:
                closed_raw_keys.add(current_raw_key)
                if raw_key in closed_raw_keys:
                    raise MTAACControlError("a source line key recurs after another line has begun")
                lines.append(
                    _make_source_line(
                        document_key,
                        line_ordinal,
                        current_raw_key,
                        current_tokens,
                    )
                )
                line_ordinal += 1
                current_raw_key = raw_key
                current_tokens = []
            current_tokens.append(
                _SourceToken(
                    model=model_token,
                    source_order=len(current_tokens),
                )
            )
        if current_raw_key is not None:
            lines.append(
                _make_source_line(
                    document_key,
                    line_ordinal,
                    current_raw_key,
                    current_tokens,
                )
            )
        output.append(
            _SourceDocument(
                document_key=document_key,
                lines=tuple(lines),
                complete_form_sequence=tuple(token.sign_id for token in model.tokens),
            )
        )
    return tuple(output)


def _validate_document_alignment(
    model: MTAACModelDocument,
    gold: MTAACGoldDocument,
    seen_token_keys: set[str],
) -> None:
    if model.document_key != gold.document_key or len(model.tokens) != len(gold.tokens):
        raise MTAACControlError("model and gold document views do not align")
    if model.document_key != opaque_document_key(gold.p_identifier):
        raise MTAACControlError("document key is not the gold-independent source-ID key")
    visual_indices = [token.visual_index for token in model.tokens]
    if visual_indices != list(range(len(model.tokens))):
        raise MTAACControlError("model visual indices must be contiguous source order")
    for visual_index, (model_token, gold_token) in enumerate(
        zip(model.tokens, gold.tokens, strict=True)
    ):
        if model_token.token_key != gold_token.token_key:
            raise MTAACControlError("model and gold token keys do not align")
        if model_token.token_key != opaque_token_key(model.document_key, visual_index):
            raise MTAACControlError("token key is not the gold-independent source-order key")
        if model_token.token_key in seen_token_keys:
            raise MTAACControlError("token keys must be globally unique")
        seen_token_keys.add(model_token.token_key)
        if model_token.sign_id != opaque_form_sign_id(gold_token.form):
            raise MTAACControlError("opaque FORM identifier does not match raw FORM")
        if gold_token.classes != derive_mtaac_gold_classes(
            gold_token.segm,
            gold_token.xpostag,
        ):
            raise MTAACControlError("stored gold projection does not match raw annotations")
        if len(gold_token.classes) > 1:
            raise MTAACControlError("gold projection classes overlap")
        if any(gold_class not in MTAAC_GOLD_CLASSES for gold_class in gold_token.classes):
            raise MTAACControlError("gold projection contains an unknown class")


def _make_source_line(
    document_key: str,
    line_ordinal: int,
    raw_key: str,
    tokens: Sequence[_SourceToken],
) -> _SourceLine:
    digest = hashlib.sha256(
        _LINE_DOMAIN
        + _frame(document_key.encode("ascii"))
        + _u64(line_ordinal)
        + _frame(raw_key.encode("utf-8"))
    ).hexdigest()
    return _SourceLine(
        line_ordinal=line_ordinal,
        line_key=f"mtaac-line-sha256-v1:{digest}",
        tokens=tuple(tokens),
        exact_form_sequence=tuple(token.model.sign_id for token in tokens),
    )


def _raw_line_key(position: str, visual_index: int) -> str:
    if "." in position:
        prefix = position.rsplit(".", 1)[0]
        if prefix:
            return f"located:{prefix}"
    return f"unlocated-row:{visual_index}"


def _document_cluster_identifier(sequence: Sequence[str]) -> str:
    digest = hashlib.sha256()
    digest.update(_CLUSTER_DOMAIN)
    digest.update(_u64(len(sequence)))
    for sign_id in sequence:
        digest.update(_frame(sign_id.encode("ascii")))
    return digest.hexdigest()


def _split_manifest_digest(
    seed: int,
    test_fraction: float,
    entries: Sequence[MTAACSplitEntry],
) -> str:
    digest = hashlib.sha256()
    digest.update(_SPLIT_MANIFEST_DOMAIN)
    digest.update(_u64(seed))
    digest.update(float(test_fraction).hex().encode("ascii"))
    for entry in entries:
        digest.update(_frame(entry.document_key.encode("ascii")))
        digest.update(_frame(entry.cluster_identifier.encode("ascii")))
        digest.update(_frame(entry.partition.encode("ascii")))
    return "sha256:" + digest.hexdigest()


def _retained_source_tokens(
    document_key: str,
    line: _SourceLine,
    regime: MTAACRegime,
    seed: int,
) -> tuple[_SourceToken, ...]:
    if regime.max_line_tokens is None or len(line.tokens) <= regime.max_line_tokens:
        return line.tokens
    anchor = min(
        range(len(line.tokens)),
        key=lambda index: (
            _event_digest(
                "window_anchor",
                seed,
                document_key,
                line.line_ordinal,
                index,
            ),
            index,
        ),
    )
    length = min(regime.max_line_tokens, len(line.tokens))
    left = min(
        max(anchor - math.floor((length - 1) / 2), 0),
        len(line.tokens) - length,
    )
    return line.tokens[left : left + length]


def _event_digest(
    event: str,
    seed: int,
    document_key: str,
    line_ordinal: int,
    token_index: int | None = None,
    extra: bytes | None = None,
) -> bytes:
    material = (
        _EVENT_DOMAINS[event]
        + _u64(seed)
        + _frame(document_key.encode("ascii"))
        + _u64(line_ordinal)
    )
    if token_index is not None:
        material += _u64(token_index)
    if extra is not None:
        material += _frame(extra)
    return hashlib.sha256(material).digest()


def _event_uniform(
    event: str,
    seed: int,
    document_key: str,
    line_ordinal: int,
    token_index: int | None = None,
) -> float:
    return int.from_bytes(
        _event_digest(event, seed, document_key, line_ordinal, token_index)[:8],
        "big",
    ) / float(1 << 64)


def _document_event_uniform(event: str, seed: int, document_key: str) -> float:
    digest = hashlib.sha256(
        _EVENT_DOMAINS[event] + _u64(seed) + _frame(document_key.encode("ascii"))
    ).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _pseudo_variant_id(
    seed: int,
    document_key: str,
    line_ordinal: int,
    token_index: int,
    base_form_id: str,
) -> str:
    digest = _event_digest(
        "pseudo_surface_variant_id",
        seed,
        document_key,
        line_ordinal,
        token_index,
        base_form_id.encode("ascii"),
    ).hex()
    return f"mtaac-artificial-word-form-sha256-v1:{digest}"


def _observation_key(
    document_key: str,
    regime: str,
    replica_index: int,
    seed: int,
    split_manifest_sha256: str,
) -> str:
    digest = hashlib.sha256(
        _OBSERVATION_DOMAIN
        + _u64(seed)
        + _frame(split_manifest_sha256.encode("ascii"))
        + _frame(document_key.encode("ascii"))
        + _frame(regime.encode("ascii"))
        + _u64(replica_index)
    ).hexdigest()
    return f"mtaac-observation-sha256-v1:{digest}"


def _duplicated_families(degraded: MTAACDegradedCorpus) -> set[str]:
    counts = Counter(observation.document_key for observation in degraded.observations)
    if any(count not in {1, 2} for count in counts.values()):
        raise MTAACControlError("a degraded family has an invalid replica count")
    return {document_key for document_key, count in counts.items() if count == 2}


def _tagged_sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _u64(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64:
        raise MTAACControlError("framed integer must fit unsigned 64-bit")
    return value.to_bytes(8, "big")


def _frame(value: bytes) -> bytes:
    return _u64(len(value)) + value


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 1 << 64:
        raise MTAACControlError("seed must fit unsigned 64-bit")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MTAACControlError(f"{label} must be an object")
    return value


class _CategoricalNaiveBayes:
    """Dependency-free weighted categorical NB with the frozen smoothing rule."""

    def __init__(self, feature_names: Sequence[str]) -> None:
        self.feature_names = tuple(feature_names)
        if len(set(self.feature_names)) != len(self.feature_names):
            raise MTAACControlError("model feature names must be unique")
        if any(name not in FULL_FEATURES for name in self.feature_names):
            raise MTAACControlError("model requested an undeclared feature")
        self.class_mass: dict[GoldClass, float] = {
            gold_class: 0.0 for gold_class in MTAAC_GOLD_CLASSES
        }
        self.feature_mass: dict[
            GoldClass,
            dict[str, dict[str, float]],
        ] = {gold_class: {} for gold_class in MTAAC_GOLD_CLASSES}
        self.vocabulary: dict[str, set[str]] = {
            feature_name: set() for feature_name in self.feature_names
        }
        self.total_mass = 0.0

    def fit(
        self,
        examples: Sequence[_Example],
        *,
        labels: Sequence[GoldClass] | None = None,
    ) -> _CategoricalNaiveBayes:
        if not examples:
            raise MTAACControlError("at least one weighted training row is required")
        effective_labels = (
            [example.true_class for example in examples] if labels is None else list(labels)
        )
        if len(effective_labels) != len(examples):
            raise MTAACControlError("training rows and labels differ in length")
        self.class_mass = {gold_class: 0.0 for gold_class in MTAAC_GOLD_CLASSES}
        self.feature_mass = {gold_class: {} for gold_class in MTAAC_GOLD_CLASSES}
        self.vocabulary = {feature_name: set() for feature_name in self.feature_names}
        self.total_mass = 0.0
        for example, label in zip(examples, effective_labels, strict=True):
            if label not in MTAAC_GOLD_CLASSES:
                raise MTAACControlError("training label is outside the four classes")
            if not math.isfinite(example.weight) or example.weight <= 0:
                raise MTAACControlError("training weights must be finite and positive")
            values = dict(example.features)
            if set(values) != set(FULL_FEATURES):
                raise MTAACControlError("prediction row feature surface is incomplete")
            self.class_mass[label] += example.weight
            self.total_mass += example.weight
            for feature_name in self.feature_names:
                value = values[feature_name]
                self.vocabulary[feature_name].add(value)
                by_value = self.feature_mass[label].setdefault(feature_name, {})
                by_value[value] = by_value.get(value, 0.0) + example.weight
        return self

    def predict(self, features: Sequence[tuple[str, str]]) -> GoldClass:
        if self.total_mass <= 0:
            raise MTAACControlError("model must be fitted before prediction")
        values = dict(features)
        if set(values) != set(FULL_FEATURES):
            raise MTAACControlError("prediction row feature surface is incomplete")
        best_class: GoldClass = MTAAC_GOLD_CLASSES[0]
        best_score = -math.inf
        for gold_class in MTAAC_GOLD_CLASSES:
            class_mass = self.class_mass[gold_class]
            score = math.log((class_mass + 1.0) / (self.total_mass + 4.0))
            for feature_name in self.feature_names:
                value = values[feature_name]
                vocabulary_size = len(self.vocabulary[feature_name]) + 1
                value_mass = self.feature_mass[gold_class].get(feature_name, {}).get(value, 0.0)
                score += math.log((value_mass + 1.0) / (class_mass + vocabulary_size))
            if score > best_score:
                best_class = gold_class
                best_score = score
        return best_class


def _primary_line_membership(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
) -> set[tuple[str, int]]:
    partition = {entry.document_key: entry.partition for entry in split.entries}
    train_sequences = {
        line.exact_form_sequence
        for document in _source_documents(corpus)
        if partition[document.document_key] == "train"
        for line in document.lines
    }
    return {
        (document.document_key, line.line_ordinal)
        for document in _source_documents(corpus)
        if partition[document.document_key] == "test"
        for line in document.lines
        if line.exact_form_sequence not in train_sequences
    }


def _truth_by_token(corpus: MTAACCorpus) -> dict[str, GoldClass | None]:
    truth: dict[str, GoldClass | None] = {}
    for document in corpus.gold_documents:
        for token in document.tokens:
            if len(token.classes) > 1:
                raise MTAACControlError("gold projection classes overlap")
            truth[token.token_key] = token.classes[0] if token.classes else None
    return truth


def _ordered_observed_tokens(line: MTAACObservedLine) -> list[MTAACObservedToken]:
    if line.reported_direction == "known_source_order":
        return sorted(line.tokens, key=lambda token: token.source_order)
    return sorted(line.tokens, key=lambda token: token.visual_index)


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


def _features(
    line: MTAACObservedLine,
    tokens: Sequence[MTAACObservedToken],
    index: int,
) -> tuple[tuple[str, str], ...]:
    token = tokens[index]
    previous = "BOS" if index == 0 else (tokens[index - 1].observed_form_id or "DAMAGED")
    following = (
        "EOS" if index == len(tokens) - 1 else (tokens[index + 1].observed_form_id or "DAMAGED")
    )
    return (
        ("opaque_form_id", token.observed_form_id or "DAMAGED"),
        ("position_bucket", _position_bucket(index, len(tokens))),
        ("previous_opaque_form_id", previous),
        ("next_opaque_form_id", following),
        ("line_length_bucket", _line_length_bucket(len(tokens))),
        ("reported_direction", line.reported_direction),
    )


def _examples_for_partition(
    degraded: MTAACDegradedCorpus,
    truth: Mapping[str, GoldClass | None],
    primary_lines: set[tuple[str, int]],
    *,
    partition: Partition,
) -> tuple[list[_Example], dict[GoldClass, int]]:
    observations = [
        observation for observation in degraded.observations if observation.partition == partition
    ]
    by_family: dict[str, list[MTAACObservedDocument]] = defaultdict(list)
    for observation in observations:
        by_family[observation.document_key].append(observation)
    examples: list[_Example] = []
    effective_families: dict[GoldClass, set[str]] = {
        gold_class: set() for gold_class in MTAAC_GOLD_CLASSES
    }
    for document_key in sorted(by_family):
        replicas = sorted(
            by_family[document_key],
            key=lambda observation: observation.replica_index,
        )
        if [item.replica_index for item in replicas] != list(range(len(replicas))):
            raise MTAACControlError("replica indices must be contiguous from zero")
        representative_rows = _prediction_rows(
            replicas[0],
            truth,
            primary_lines,
            primary_only=partition == "test",
        )
        readable_target_count = len(representative_rows)
        if readable_target_count == 0:
            continue
        weight = 1.0 / (readable_target_count * len(replicas))
        for observation in replicas:
            rows = _prediction_rows(
                observation,
                truth,
                primary_lines,
                primary_only=partition == "test",
            )
            if [
                (line_ordinal, model_order, token.token_key)
                for line_ordinal, model_order, token, _ in rows
            ] != [
                (line_ordinal, model_order, token.token_key)
                for line_ordinal, model_order, token, _ in representative_rows
            ]:
                raise MTAACControlError("replicas are not exact prediction-row copies")
            for line_ordinal, model_order, token, feature_values in rows:
                label = truth[token.token_key]
                if label is None:
                    raise AssertionError("prediction row has no target class")
                effective_families[label].add(document_key)
                examples.append(
                    _Example(
                        document_key=document_key,
                        observation_key=observation.observation_key,
                        replica_index=observation.replica_index,
                        line_ordinal=line_ordinal,
                        model_order=model_order,
                        token_key=token.token_key,
                        features=feature_values,
                        true_class=label,
                        weight=weight,
                    )
                )
    examples.sort(
        key=lambda example: (
            example.document_key,
            example.replica_index,
            example.line_ordinal,
            example.model_order,
            example.token_key,
        )
    )
    return examples, {
        gold_class: len(effective_families[gold_class]) for gold_class in MTAAC_GOLD_CLASSES
    }


def _prediction_rows(
    observation: MTAACObservedDocument,
    truth: Mapping[str, GoldClass | None],
    primary_lines: set[tuple[str, int]],
    *,
    primary_only: bool,
) -> list[
    tuple[
        int,
        int,
        MTAACObservedToken,
        tuple[tuple[str, str], ...],
    ]
]:
    rows: list[
        tuple[
            int,
            int,
            MTAACObservedToken,
            tuple[tuple[str, str], ...],
        ]
    ] = []
    for line in sorted(observation.lines, key=lambda item: item.line_ordinal):
        if (
            primary_only
            and (
                observation.document_key,
                line.line_ordinal,
            )
            not in primary_lines
        ):
            continue
        ordered = _ordered_observed_tokens(line)
        for model_order, token in enumerate(ordered):
            if token.observed_form_id is None or truth[token.token_key] is None:
                continue
            rows.append(
                (
                    line.line_ordinal,
                    model_order,
                    token,
                    _features(line, ordered, model_order),
                )
            )
    return rows


def _coverage(
    corpus: MTAACCorpus,
    degraded: MTAACDegradedCorpus,
    primary_lines: set[tuple[str, int]],
    truth: Mapping[str, GoldClass | None],
) -> dict[GoldClass, float | None]:
    source_by_document = {document.document_key: document for document in _source_documents(corpus)}
    representatives = {
        observation.document_key: observation
        for observation in degraded.observations
        if observation.partition == "test" and observation.replica_index == 0
    }
    ratios: dict[GoldClass, list[float]] = {gold_class: [] for gold_class in MTAAC_GOLD_CLASSES}
    for document_key, observation in representatives.items():
        denominators: Counter[GoldClass] = Counter()
        eligible_keys: dict[GoldClass, set[str]] = {
            gold_class: set() for gold_class in MTAAC_GOLD_CLASSES
        }
        for line in source_by_document[document_key].lines:
            if (document_key, line.line_ordinal) not in primary_lines:
                continue
            for token in line.tokens:
                label = truth[token.model.token_key]
                if label is not None:
                    denominators[label] += 1
                    eligible_keys[label].add(token.model.token_key)
        readable_keys = {
            token.token_key
            for line in observation.lines
            for token in line.tokens
            if token.observed_form_id is not None
        }
        for gold_class in MTAAC_GOLD_CLASSES:
            if denominators[gold_class] > 0:
                ratios[gold_class].append(
                    len(eligible_keys[gold_class] & readable_keys) / denominators[gold_class]
                )
    return {
        gold_class: (fmean(ratios[gold_class]) if ratios[gold_class] else None)
        for gold_class in MTAAC_GOLD_CLASSES
    }


def _weighted_metrics(
    examples: Sequence[_Example],
    predictions: Sequence[GoldClass],
    *,
    effective_families: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
) -> dict[str, Any]:
    if len(examples) != len(predictions):
        raise MTAACControlError("predictions and metric rows differ in length")
    confusion: dict[GoldClass, dict[GoldClass, float]] = {
        expected: {predicted: 0.0 for predicted in MTAAC_GOLD_CLASSES}
        for expected in MTAAC_GOLD_CLASSES
    }
    for example, prediction in zip(examples, predictions, strict=True):
        if prediction not in MTAAC_GOLD_CLASSES:
            raise MTAACControlError("prediction is outside the four classes")
        if not math.isfinite(example.weight) or example.weight < 0:
            raise MTAACControlError("metric weights must be finite and nonnegative")
        confusion[example.true_class][prediction] += example.weight

    per_class: dict[str, dict[str, float | int | None]] = {}
    f1_values: list[float] = []
    recalls: list[float] = []
    correct = 0.0
    total = 0.0
    aggregate_available = True
    for gold_class in MTAAC_GOLD_CLASSES:
        true_positive = confusion[gold_class][gold_class]
        predicted_mass = sum(confusion[other][gold_class] for other in MTAAC_GOLD_CLASSES)
        truth_mass = sum(confusion[gold_class].values())
        precision = true_positive / predicted_mass if predicted_mass > 0 else 0.0
        recall = true_positive / truth_mass if truth_mass > 0 else None
        if recall is None:
            aggregate_available = False
            f1 = 0.0
        else:
            f1 = 2.0 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
            recalls.append(recall)
        f1_values.append(f1)
        correct += true_positive
        total += truth_mass
        per_class[gold_class] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "truth_mass": truth_mass,
            "effective_source_document_families": effective_families[gold_class],
            "family_mean_readable_coverage": coverage[gold_class],
        }
    return {
        "macro_f1": fmean(f1_values) if aggregate_available else None,
        "weighted_balanced_accuracy": (fmean(recalls) if aggregate_available else None),
        "weighted_accuracy": correct / total if total > 0 else None,
        "per_class": per_class,
        "weighted_confusion_matrix": confusion,
        "evaluated_prediction_rows": len(examples),
    }


def _model_metrics(
    train_examples: Sequence[_Example],
    test_examples: Sequence[_Example],
    *,
    feature_names: Sequence[str],
    effective_families: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
    train_labels: Sequence[GoldClass] | None = None,
) -> dict[str, Any]:
    model = _CategoricalNaiveBayes(feature_names).fit(
        train_examples,
        labels=train_labels,
    )
    predictions: list[GoldClass] = []
    for example in test_examples:
        predictions.append(model.predict(example.features))
    return _weighted_metrics(
        test_examples,
        predictions,
        effective_families=effective_families,
        coverage=coverage,
    )


def _majority_metrics(
    train_examples: Sequence[_Example],
    test_examples: Sequence[_Example],
    *,
    effective_families: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
) -> tuple[GoldClass, dict[str, Any]]:
    class_mass: dict[GoldClass, float] = {gold_class: 0.0 for gold_class in MTAAC_GOLD_CLASSES}
    for example in train_examples:
        class_mass[example.true_class] += example.weight
    majority: GoldClass = MTAAC_GOLD_CLASSES[0]
    for gold_class in MTAAC_GOLD_CLASSES[1:]:
        if class_mass[gold_class] > class_mass[majority]:
            majority = gold_class
    majority_predictions: list[GoldClass] = [majority for _ in test_examples]
    return majority, _weighted_metrics(
        test_examples,
        majority_predictions,
        effective_families=effective_families,
        coverage=coverage,
    )


def _representative_label_vectors(
    train_examples: Sequence[_Example],
) -> dict[str, tuple[GoldClass, ...]]:
    by_family: dict[str, list[_Example]] = defaultdict(list)
    for example in train_examples:
        if example.replica_index == 0:
            by_family[example.document_key].append(example)
    vectors: dict[str, tuple[GoldClass, ...]] = {}
    for document_key, rows in by_family.items():
        rows.sort(
            key=lambda row: (
                row.line_ordinal,
                row.model_order,
                row.token_key,
            )
        )
        vectors[document_key] = tuple(row.true_class for row in rows)
    return vectors


def _permuted_training_labels(
    train_examples: Sequence[_Example],
    *,
    run_seed: int,
) -> tuple[list[GoldClass], int, float]:
    _validate_seed(run_seed)
    vectors = _representative_label_vectors(train_examples)
    if not vectors:
        raise MTAACControlError("permutation requires readable training families")
    families_by_count: dict[int, list[str]] = defaultdict(list)
    for document_key, vector in vectors.items():
        families_by_count[len(vector)].append(document_key)
    assigned: dict[str, tuple[GoldClass, ...]] = {}
    fixed_points = 0
    movable_families = 0
    for readable_count, families in families_by_count.items():
        recipients = sorted(families)
        if len(recipients) >= 2:
            movable_families += len(recipients)
        donors = sorted(
            families,
            key=lambda document_key: (
                hashlib.sha256(
                    _PERMUTATION_DOMAIN
                    + _u64(run_seed)
                    + _u64(readable_count)
                    + _frame(document_key.encode("ascii"))
                ).digest(),
                document_key,
            ),
        )
        for recipient, donor in zip(recipients, donors, strict=True):
            assigned[recipient] = vectors[donor]
            fixed_points += recipient == donor
    index_by_family: dict[str, dict[str, int]] = {}
    representative_rows: dict[str, list[_Example]] = defaultdict(list)
    for example in train_examples:
        if example.replica_index == 0:
            representative_rows[example.document_key].append(example)
    for document_key, rows in representative_rows.items():
        rows.sort(
            key=lambda row: (
                row.line_ordinal,
                row.model_order,
                row.token_key,
            )
        )
        index_by_family[document_key] = {row.token_key: index for index, row in enumerate(rows)}
    output: list[GoldClass] = []
    for example in train_examples:
        vector_index = index_by_family[example.document_key][example.token_key]
        output.append(assigned[example.document_key][vector_index])
    _validate_permutation_invariants(train_examples, output)
    return output, fixed_points, movable_families / len(vectors)


def _validate_permutation_invariants(
    train_examples: Sequence[_Example],
    permuted_labels: Sequence[GoldClass],
) -> None:
    if len(train_examples) != len(permuted_labels):
        raise MTAACControlError("permutation changed training row count")
    original_raw = Counter(
        example.true_class for example in train_examples if example.replica_index == 0
    )
    permuted_raw = Counter(
        label
        for example, label in zip(train_examples, permuted_labels, strict=True)
        if example.replica_index == 0
    )
    if original_raw != permuted_raw:
        raise MTAACControlError("permutation changed global readable class counts")
    original_mass: dict[GoldClass, float] = {gold_class: 0.0 for gold_class in MTAAC_GOLD_CLASSES}
    permuted_mass = dict(original_mass)
    for example, label in zip(train_examples, permuted_labels, strict=True):
        original_mass[example.true_class] += example.weight
        permuted_mass[label] += example.weight
    for gold_class in MTAAC_GOLD_CLASSES:
        if not math.isclose(
            original_mass[gold_class],
            permuted_mass[gold_class],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise MTAACControlError("permutation changed global family-weighted class mass")


def _percentile_95(values: Sequence[float], *, required_runs: int) -> float:
    if len(values) != required_runs:
        raise MTAACControlError("null distribution has a missing or extra run")
    if any(not math.isfinite(value) for value in values):
        raise MTAACControlError("null distribution contains a non-finite macro-F1")
    ordered = sorted(values)
    height = (required_runs - 1) * 0.95
    lower = math.floor(height)
    upper = math.ceil(height)
    if lower == upper:
        return ordered[lower]
    fraction = height - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _permutation_null(
    train_examples: Sequence[_Example],
    test_examples: Sequence[_Example],
    *,
    effective_families: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
    observed_macro_f1: float,
    runs: int,
    seed_start: int,
) -> dict[str, Any]:
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
        raise MTAACControlError("null runs must be a positive integer")
    _validate_seed(seed_start)
    scheduled_seeds = [seed_start + offset for offset in range(runs)]
    if len(set(scheduled_seeds)) != runs or any(seed >= 1 << 64 for seed in scheduled_seeds):
        raise MTAACControlError("null seed schedule is invalid")
    values: list[float] = []
    run_values: list[dict[str, float | int]] = []
    movable_fraction: float | None = None
    for run_seed in scheduled_seeds:
        labels, fixed_points, current_movable = _permuted_training_labels(
            train_examples,
            run_seed=run_seed,
        )
        if movable_fraction is None:
            movable_fraction = current_movable
        elif not math.isclose(
            movable_fraction,
            current_movable,
            rel_tol=0.0,
            abs_tol=0.0,
        ):
            raise MTAACControlError("movable family fraction changed across null runs")
        metrics = _model_metrics(
            train_examples,
            test_examples,
            feature_names=FULL_FEATURES,
            effective_families=effective_families,
            coverage=coverage,
            train_labels=labels,
        )
        macro_f1 = metrics["macro_f1"]
        if not isinstance(macro_f1, (int, float)) or not math.isfinite(macro_f1):
            raise MTAACControlError("null run produced a non-finite macro-F1")
        value = float(macro_f1)
        values.append(value)
        run_values.append(
            {
                "seed": run_seed,
                "macro_f1": value,
                "fixed_point_family_count": fixed_points,
            }
        )
    p95 = _percentile_95(values, required_runs=runs)
    p_value = (1 + sum(value >= observed_macro_f1 for value in values)) / (runs + 1)
    return {
        "runs": runs,
        "seed_start": seed_start,
        "run_values": run_values,
        "macro_f1": {
            "mean": fmean(values),
            "minimum": min(values),
            "maximum": max(values),
            "p95": p95,
        },
        "add_one_empirical_p_greater_or_equal": p_value,
        "movable_family_weight_fraction": movable_fraction,
        "integrity": {
            "distinct_scheduled_seeds": len(set(scheduled_seeds)) == runs,
            "finite_macro_f1_values": len(values) == runs,
            "family_vectors_permuted_within_readable_count": True,
            "test_truth_unchanged": True,
        },
    }


def _support_and_coverage(
    corpus: MTAACCorpus,
    degraded_by_name: Mapping[str, MTAACDegradedCorpus],
    primary_lines: set[tuple[str, int]],
) -> tuple[
    dict[str, dict[GoldClass, int]],
    dict[str, dict[GoldClass, float | None]],
    dict[str, tuple[list[_Example], list[_Example]]],
]:
    truth = _truth_by_token(corpus)
    supports: dict[str, dict[GoldClass, int]] = {}
    coverage_by_regime: dict[str, dict[GoldClass, float | None]] = {}
    examples_by_regime: dict[str, tuple[list[_Example], list[_Example]]] = {}
    for regime_name, degraded in degraded_by_name.items():
        train_examples, train_support = _examples_for_partition(
            degraded,
            truth,
            primary_lines,
            partition="train",
        )
        test_examples, test_support = _examples_for_partition(
            degraded,
            truth,
            primary_lines,
            partition="test",
        )
        coverage = _coverage(
            corpus,
            degraded,
            primary_lines,
            truth,
        )
        supports[f"{regime_name}_train"] = train_support
        supports[f"{regime_name}_test_primary"] = test_support
        coverage_by_regime[regime_name] = coverage
        examples_by_regime[regime_name] = (train_examples, test_examples)
    return supports, coverage_by_regime, examples_by_regime


def _decision_support_passes(
    supports: Mapping[str, Mapping[GoldClass, int]],
    coverage: Mapping[str, Mapping[GoldClass, float | None]],
    examples: Mapping[str, tuple[Sequence[_Example], Sequence[_Example]]],
) -> tuple[bool, dict[str, bool]]:
    mild_train = supports["mild_train"]
    mild_test = supports["mild_test_primary"]
    criteria = {
        "mild_train_effective_families": all(
            mild_train[gold_class] >= 40 for gold_class in MTAAC_GOLD_CLASSES
        ),
        "mild_test_effective_families": all(
            mild_test[gold_class] >= 20 for gold_class in MTAAC_GOLD_CLASSES
        ),
        "clean_positive_four_class_truth": _positive_truth_support(examples["clean"][1]),
        "mild_positive_four_class_truth": _positive_truth_support(examples["mild"][1]),
        "clean_coverage_defined": all(
            coverage["clean"][gold_class] is not None for gold_class in MTAAC_GOLD_CLASSES
        ),
        "mild_coverage_defined": all(
            coverage["mild"][gold_class] is not None for gold_class in MTAAC_GOLD_CLASSES
        ),
    }
    return all(criteria.values()), criteria


def _positive_truth_support(examples: Sequence[_Example]) -> bool:
    return all(
        any(example.true_class == gold_class for example in examples)
        for gold_class in MTAAC_GOLD_CLASSES
    )


def _score_regime(
    train_examples: Sequence[_Example],
    test_examples: Sequence[_Example],
    *,
    test_support: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
    null_runs: int,
    null_seed_start: int,
) -> dict[str, Any]:
    observed = _model_metrics(
        train_examples,
        test_examples,
        feature_names=FULL_FEATURES,
        effective_families=test_support,
        coverage=coverage,
    )
    observed_macro = observed["macro_f1"]
    if not isinstance(observed_macro, (int, float)) or not math.isfinite(observed_macro):
        raise MTAACControlError("observed aggregate metric is unavailable")
    majority_class, majority = _majority_metrics(
        train_examples,
        test_examples,
        effective_families=test_support,
        coverage=coverage,
    )
    position_only = _model_metrics(
        train_examples,
        test_examples,
        feature_names=POSITION_FEATURES,
        effective_families=test_support,
        coverage=coverage,
    )
    lexicon_only = _model_metrics(
        train_examples,
        test_examples,
        feature_names=LEXICON_FEATURES,
        effective_families=test_support,
        coverage=coverage,
    )
    null = _permutation_null(
        train_examples,
        test_examples,
        effective_families=test_support,
        coverage=coverage,
        observed_macro_f1=float(observed_macro),
        runs=null_runs,
        seed_start=null_seed_start,
    )
    reference_values = (
        majority["macro_f1"],
        position_only["macro_f1"],
        null["macro_f1"]["p95"],
    )
    if any(
        not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in reference_values
    ):
        raise MTAACControlError("a decision reference metric is unavailable")
    decision_reference = max(float(value) for value in reference_values)
    return {
        "observed": observed,
        "majority_reference": {
            "predicted_class": majority_class,
            "metrics": majority,
        },
        "position_and_line_structure_only": position_only,
        "opaque_FORM_lexicon_only": lexicon_only,
        "permutation_null": null,
        "decision_reference_macro_f1": decision_reference,
        "observed_minus_decision_reference": float(observed_macro) - decision_reference,
    }


def apply_mtaac_control_decision(
    clean: Mapping[str, Any],
    mild: Mapping[str, Any],
    *,
    support_passed: bool,
    integrity_passed: bool,
) -> dict[str, Any]:
    """Apply the frozen clean/mild thresholds to already computed aggregates."""

    clean_observed = _mapping(clean.get("observed"), "clean observed")
    mild_observed = _mapping(mild.get("observed"), "mild observed")
    clean_per_class = _mapping(clean_observed.get("per_class"), "clean per_class")
    mild_per_class = _mapping(mild_observed.get("per_class"), "mild per_class")
    clean_macro = _finite_float(clean_observed.get("macro_f1"), "clean macro_f1")
    mild_macro = _finite_float(mild_observed.get("macro_f1"), "mild macro_f1")
    clean_delta = _finite_float(
        clean.get("observed_minus_decision_reference"),
        "clean reference delta",
    )
    mild_delta = _finite_float(
        mild.get("observed_minus_decision_reference"),
        "mild reference delta",
    )
    mild_null = _mapping(mild.get("permutation_null"), "mild permutation null")
    mild_p = _finite_float(
        mild_null.get("add_one_empirical_p_greater_or_equal"),
        "mild permutation p-value",
    )
    movable = _finite_float(
        mild_null.get("movable_family_weight_fraction"),
        "mild movable family fraction",
    )

    clean_criteria = {
        "minimum_macro_f1": clean_macro >= 0.60,
        "minimum_observed_minus_decision_reference": clean_delta >= 0.10,
        "minimum_per_class_recall": all(
            _finite_float(
                _mapping(clean_per_class.get(gold_class), gold_class).get("recall"),
                f"clean {gold_class} recall",
            )
            >= 0.35
            for gold_class in MTAAC_GOLD_CLASSES
        ),
        "minimum_per_class_family_mean_readable_coverage": all(
            _finite_float(
                _mapping(clean_per_class.get(gold_class), gold_class).get(
                    "family_mean_readable_coverage"
                ),
                f"clean {gold_class} coverage",
            )
            >= 0.95
            for gold_class in MTAAC_GOLD_CLASSES
        ),
    }
    mild_criteria = {
        "minimum_macro_f1": mild_macro >= 0.60,
        "minimum_observed_minus_decision_reference": mild_delta >= 0.10,
        "maximum_add_one_permutation_p": mild_p <= 0.05,
        "minimum_per_class_recall": all(
            _finite_float(
                _mapping(mild_per_class.get(gold_class), gold_class).get("recall"),
                f"mild {gold_class} recall",
            )
            >= 0.35
            for gold_class in MTAAC_GOLD_CLASSES
        ),
        "minimum_per_class_family_mean_readable_coverage": all(
            _finite_float(
                _mapping(mild_per_class.get(gold_class), gold_class).get(
                    "family_mean_readable_coverage"
                ),
                f"mild {gold_class} coverage",
            )
            >= 0.75
            for gold_class in MTAAC_GOLD_CLASSES
        ),
        "minimum_movable_family_weight_fraction": movable >= 0.80,
        "all_integrity_and_leakage_checks": integrity_passed,
        "decision_bearing_support": support_passed,
    }
    passes = all(clean_criteria.values()) and all(mild_criteria.values())
    return {
        "thresholds": {
            "clean": {
                "minimum_macro_f1": 0.60,
                "minimum_observed_minus_decision_reference": 0.10,
                "minimum_per_class_recall": 0.35,
                "minimum_per_class_family_mean_readable_coverage": 0.95,
            },
            "mild": {
                "minimum_macro_f1": 0.60,
                "minimum_observed_minus_decision_reference": 0.10,
                "maximum_add_one_permutation_p": 0.05,
                "minimum_per_class_recall": 0.35,
                "minimum_per_class_family_mean_readable_coverage": 0.75,
                "minimum_movable_family_weight_fraction": 0.80,
                "minimum_train_effective_families_per_class": 40,
                "minimum_test_effective_families_per_class": 20,
            },
        },
        "clean_criteria": clean_criteria,
        "mild_criteria": mild_criteria,
        "all_thresholds_passed": passes,
        "harsh_can_change_outcome": False,
        "diagnostic_strata_can_change_outcome": False,
    }


def evaluate_mtaac_control_archive(
    archive_bytes: bytes,
    protocol_bytes: bytes,
    *,
    attestation: MTAACControlAttestation,
    anchors_available: bool = True,
) -> dict[str, Any]:
    """Evaluate only the exact fixed real archive under all normative gates.

    This function is intentionally not exercised against real source bytes by
    the repository tests.  It has no run-count override: real execution always
    uses the protocol's 999 scheduled null runs.
    """

    protocol = validate_mtaac_control_protocol(protocol_bytes)
    if protocol.get("protocol_status") != "pre_result_code_frozen":
        raise MTAACControlError(
            "real-source evaluation is disabled until protocol_status is pre_result_code_frozen"
        )
    validate_mtaac_control_attestation(
        attestation,
        expected_origin="fixed_real_source",
    )
    if not isinstance(anchors_available, bool):
        raise MTAACControlError("anchors_available must be boolean")
    source = _mapping(protocol["source"], "source")
    try:
        corpus = parse_mtaac_archive(
            archive_bytes,
            expected_input_sha256=str(source["archive_sha256"]),
        )
    except MTAACError as error:
        raise MTAACControlError(f"real source admission failed: {error}") from error
    _validate_exact_real_source(corpus, protocol)
    return _evaluate_prepared_control(
        corpus,
        protocol,
        attestation=attestation,
        anchors_available=anchors_available,
        null_runs=999,
        fixture_mode=False,
    )


def evaluate_synthetic_mtaac_control_fixture(
    files: Mapping[str, bytes],
    protocol_bytes: bytes,
    *,
    attestation: MTAACControlAttestation,
    anchors_available: bool = True,
    null_runs: int = 19,
) -> dict[str, Any]:
    """Exercise the instrument on raw project-authored files without a real decision.

    This entry point intentionally does not accept a prebuilt ``MTAACCorpus``.
    Parsing the raw mapping here prevents callers from replacing only corpus
    provenance or document metadata to route the fixed real corpus around the
    pre-result freeze gate.
    """

    protocol = validate_mtaac_control_protocol(protocol_bytes)
    validate_mtaac_control_attestation(
        attestation,
        expected_origin="project_authored_synthetic_fixture",
    )
    try:
        corpus = parse_mtaac_directory(files)
    except MTAACError as error:
        raise MTAACControlError(f"synthetic fixture admission failed: {error}") from error
    _reject_real_source_from_synthetic_entry(corpus)
    if not isinstance(anchors_available, bool):
        raise MTAACControlError("anchors_available must be boolean")
    if isinstance(null_runs, bool) or not isinstance(null_runs, int) or null_runs < 1:
        raise MTAACControlError("null_runs must be a positive integer")
    report = _evaluate_prepared_control(
        corpus,
        protocol,
        attestation=attestation,
        anchors_available=anchors_available,
        null_runs=null_runs,
        fixture_mode=True,
    )
    instrument_status = report.pop("terminal_status")
    if instrument_status == "go":
        instrument_status = "thresholds_passed"
    elif instrument_status == "no_go":
        instrument_status = "thresholds_not_passed"
    report["terminal_status"] = "fixture_only"
    report["fixture_instrument_status"] = instrument_status
    report["real_source_decision_suppressed"] = True
    return report


def _reject_real_source_from_synthetic_entry(corpus: MTAACCorpus) -> None:
    """Prevent the fixture-only entry point from laundering a real-source run."""

    if not isinstance(corpus, MTAACCorpus):
        raise MTAACControlError("corpus must be an MTAACCorpus")
    derived_manifest = _derive_selected_manifest_from_metadata(corpus)
    provenance = corpus.provenance
    if (
        provenance.input_sha256 == MTAAC_REAL_ARCHIVE_SHA256
        or provenance.selected_manifest_sha256 == MTAAC_REAL_SELECTED_MANIFEST_SHA256
        or derived_manifest == MTAAC_REAL_SELECTED_MANIFEST_SHA256
    ):
        raise MTAACControlError("synthetic fixture entry rejects real-source commitments")
    if derived_manifest != provenance.selected_manifest_sha256:
        raise MTAACControlError("selected manifest commitment does not match corpus metadata")
    if _evaluation_corpus_fingerprint(corpus) == MTAAC_REAL_EVALUATION_CORPUS_SHA256:
        raise MTAACControlError("synthetic fixture entry rejects real-source commitments")


def _evaluate_prepared_control(
    corpus: MTAACCorpus,
    protocol: Mapping[str, Any],
    *,
    attestation: MTAACControlAttestation,
    anchors_available: bool,
    null_runs: int,
    fixture_mode: bool,
) -> dict[str, Any]:
    _validate_execution_constants(protocol)
    _source_documents(corpus)
    split_spec = _mapping(protocol["split"], "split")
    degradation_spec = _mapping(protocol["degradation"], "degradation")
    split = build_mtaac_split(
        corpus,
        seed=int(split_spec["seed"]),
        test_fraction=float(split_spec["test_fraction"]),
    )
    degradation_seed = int(degradation_spec["seed"])
    clean = degrade_mtaac_corpus(
        corpus,
        split,
        CLEAN_REGIME,
        seed=degradation_seed,
    )
    mild = degrade_mtaac_corpus(
        corpus,
        split,
        MILD_REGIME,
        seed=degradation_seed,
    )
    harsh = degrade_mtaac_corpus(
        corpus,
        split,
        HARSH_REGIME,
        seed=degradation_seed,
    )
    validate_mtaac_degradation(corpus, split, clean)
    validate_mtaac_degradation(corpus, split, mild)
    validate_mtaac_degradation(corpus, split, harsh)
    validate_nested_mtaac_degradations(clean, mild, harsh)
    primary_lines = _primary_line_membership(corpus, split)
    integrity = {
        "protocol_exact_bytes": True,
        "model_gold_views_aligned": True,
        "source_document_split_before_degradation": True,
        "complete_document_clusters_do_not_cross_partitions": True,
        "observations_match_split_manifest": True,
        "degradation_exactly_rederived": True,
        "nested_cumulative_regimes": True,
        "test_truth_not_a_model_feature": True,
        "raw_gold_fields_not_model_features": True,
    }
    report = _base_report(
        corpus,
        split,
        primary_lines,
        attestation=attestation,
        fixture_mode=fixture_mode,
        integrity=integrity,
    )
    if not anchors_available:
        report.update(
            {
                "terminal_status": "not_identifiable",
                "anchors_available": False,
                "reason": (
                    "Without train-side class anchors, named classes are "
                    "label-switching-equivalent; no F1, null, p-value, "
                    "decision reference, GO, or NO_GO metric is emitted."
                ),
            }
        )
        return report

    degraded_by_name = {"clean": clean, "mild": mild, "harsh": harsh}
    supports, coverage, examples = _support_and_coverage(
        corpus,
        degraded_by_name,
        primary_lines,
    )
    support_passed, support_criteria = _decision_support_passes(
        supports,
        coverage,
        examples,
    )
    report["anchors_available"] = True
    report["support"] = {
        "effective_source_document_families": supports,
        "family_mean_readable_coverage": coverage,
        "criteria": support_criteria,
    }
    if not support_passed:
        report.update(
            {
                "terminal_status": "insufficient_evidence",
                "reason": (
                    "Decision-bearing four-class primary support does not meet "
                    "the fixed effective-family or defined-coverage gates."
                ),
            }
        )
        return report

    clean_score = _score_regime(
        *examples["clean"],
        test_support=supports["clean_test_primary"],
        coverage=coverage["clean"],
        null_runs=null_runs,
        null_seed_start=0,
    )
    mild_score = _score_regime(
        *examples["mild"],
        test_support=supports["mild_test_primary"],
        coverage=coverage["mild"],
        null_runs=null_runs,
        null_seed_start=0,
    )
    harsh_score = _diagnostic_regime_score(
        *examples["harsh"],
        test_support=supports["harsh_test_primary"],
        coverage=coverage["harsh"],
    )
    decision = apply_mtaac_control_decision(
        clean_score,
        mild_score,
        support_passed=True,
        integrity_passed=all(integrity.values()),
    )
    report.update(
        {
            "terminal_status": ("go" if decision["all_thresholds_passed"] else "no_go"),
            "regimes": {
                "clean": clean_score,
                "mild": mild_score,
                "harsh_diagnostic_only": harsh_score,
            },
            "decision": decision,
            "null_run_contract": {
                "runs": null_runs,
                "seed_start": 0,
                "normative_real_run_count": 999,
                "fixture_override": fixture_mode and null_runs != 999,
            },
            "cue_ablations": _cue_ablation_diagnostics(
                corpus,
                split,
                primary_lines,
                supports["mild_test_primary"],
                coverage["mild"],
                seed=degradation_seed,
            ),
            "diagnostic_membership": _diagnostic_membership_counts(
                corpus,
                split,
                primary_lines,
            ),
        }
    )
    return report


def _validate_execution_constants(protocol: Mapping[str, Any]) -> None:
    split = _mapping(protocol.get("split"), "split")
    degradation = _mapping(protocol.get("degradation"), "degradation")
    if (
        isinstance(split.get("seed"), bool)
        or split.get("seed") != 0
        or isinstance(split.get("test_fraction"), bool)
        or split.get("test_fraction") != 0.25
    ):
        raise MTAACControlError("protocol split seed/fraction do not match V1")
    if isinstance(degradation.get("seed"), bool) or degradation.get("seed") != 0:
        raise MTAACControlError("protocol degradation seed does not match V1")
    expected_regimes = {
        "clean": {
            "max_line_tokens": None,
            "pseudo_surface_variant_rate": 0.0,
            "damage_rate": 0.0,
            "reverse_rate": 0.0,
            "direction_unknown_rate": 0.0,
            "duplicate_rate": 0.0,
        },
        "mild": {
            "max_line_tokens": 7,
            "pseudo_surface_variant_rate": 0.3,
            "damage_rate": 0.1,
            "reverse_rate": 0.5,
            "direction_unknown_rate": 0.15,
            "duplicate_rate": 0.25,
        },
        "harsh": {
            "max_line_tokens": 4,
            "pseudo_surface_variant_rate": 0.5,
            "damage_rate": 0.25,
            "reverse_rate": 0.5,
            "direction_unknown_rate": 0.4,
            "duplicate_rate": 0.5,
        },
    }
    regimes = _mapping(degradation.get("regimes"), "degradation regimes")
    if regimes != expected_regimes:
        raise MTAACControlError("protocol degradation regimes do not match V1")


def _diagnostic_regime_score(
    train_examples: Sequence[_Example],
    test_examples: Sequence[_Example],
    *,
    test_support: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
) -> dict[str, Any]:
    if not train_examples:
        return {
            "aggregate_available": False,
            "reason": "diagnostic training observations are empty",
            "can_change_overall_outcome": False,
        }
    if not _positive_truth_support(test_examples):
        return {
            "aggregate_available": False,
            "reason": "diagnostic four-class truth support is incomplete",
            "can_change_overall_outcome": False,
        }
    return {
        "aggregate_available": True,
        "observed": _model_metrics(
            train_examples,
            test_examples,
            feature_names=FULL_FEATURES,
            effective_families=test_support,
            coverage=coverage,
        ),
        "permutation_null_run": False,
        "can_change_overall_outcome": False,
    }


def _validate_exact_real_source(
    corpus: MTAACCorpus,
    protocol: Mapping[str, Any],
) -> None:
    source = _mapping(protocol["source"], "source")
    parser = _mapping(protocol["parser"], "parser")
    expected = _mapping(parser["expected_stage_counts"], "expected_stage_counts")
    provenance = corpus.provenance
    actual_stage = {
        "selected_documents": provenance.selected_document_count,
        "seven_column_documents": provenance.row_shape_document_count,
        "seven_column_rows": provenance.row_shape_token_count,
        "strict_unique_id_documents": provenance.admitted_document_count,
        "strict_unique_id_rows": provenance.admitted_token_count,
        "quarantined_documents": provenance.quarantined_document_count,
    }
    for key, actual in actual_stage.items():
        if expected.get(key) != actual:
            raise MTAACControlError(f"real source stage count mismatch: {key}")
    if provenance.input_kind != "archive_tar":
        raise MTAACControlError("real source must be supplied as the fixed TAR archive")
    if provenance.input_sha256 != source.get("archive_sha256"):
        raise MTAACControlError("real source archive digest mismatch")
    if not provenance.caller_digest_verified:
        raise MTAACControlError("real source archive digest was not verified")
    if provenance.selected_manifest_sha256 != source.get("expected_selected_manifest_sha256"):
        raise MTAACControlError("real selected-member manifest digest mismatch")
    if provenance.adapter_target_commit != source.get("commit"):
        raise MTAACControlError("real source commit target mismatch")
    if _evaluation_corpus_fingerprint(corpus) != source.get("expected_evaluation_corpus_sha256"):
        raise MTAACControlError("real evaluation-corpus digest mismatch")
    if dict(corpus.row_shape_class_counts) != dict(
        _mapping(expected["seven_column_class_counts"], "seven_column_class_counts")
    ):
        raise MTAACControlError("seven-column class counts mismatch")
    if dict(corpus.admitted_class_counts) != dict(
        _mapping(expected["strict_class_counts"], "strict_class_counts")
    ):
        raise MTAACControlError("strict class counts mismatch")


def _base_report(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    primary_lines: set[tuple[str, int]],
    *,
    attestation: MTAACControlAttestation,
    fixture_mode: bool,
    integrity: Mapping[str, bool],
) -> dict[str, Any]:
    partition_counts = Counter(entry.partition for entry in split.entries)
    quarantine_counts = Counter(item.reason_code for item in corpus.quarantined_documents)
    libc_name, libc_version = platform.libc_ver()
    return {
        "analysis": "mtaac_known_script_control",
        "protocol_version": MTAAC_CONTROL_PROTOCOL_VERSION,
        "protocol_sha256": MTAAC_CONTROL_PROTOCOL_SHA256,
        "numeric_runtime": {
            "python_implementation": sys.implementation.name,
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "libc": (
                f"{libc_name}-{libc_version}" if libc_name or libc_version else "not_reported"
            ),
            "float_mantissa_bits": sys.float_info.mant_dig,
            "cross_runtime_byte_identity_claimed": False,
        },
        "data_origin": attestation.data_origin,
        "external_data_used": attestation.external_data_used,
        "fixture_mode": fixture_mode,
        "attestation": {
            "pre_result_code_commit": attestation.pre_result_code_commit,
            "declaration_scope": (
                "caller-declared code commit only; evaluator does not infer or "
                "attest Git state, publication time, trusted time, custody, or blindness"
            ),
        },
        "source_commitments": {
            "adapter_target_commit": corpus.provenance.adapter_target_commit,
            "input_sha256": corpus.provenance.input_sha256,
            "selected_manifest_sha256": corpus.provenance.selected_manifest_sha256,
            "evaluation_corpus_sha256": _evaluation_corpus_fingerprint(corpus),
            "license_id": corpus.provenance.license_id,
        },
        "parser_aggregates": {
            "selected_documents": corpus.provenance.selected_document_count,
            "seven_column_documents": corpus.provenance.row_shape_document_count,
            "seven_column_rows": corpus.provenance.row_shape_token_count,
            "strict_unique_id_documents": corpus.provenance.admitted_document_count,
            "strict_unique_id_rows": corpus.provenance.admitted_token_count,
            "quarantined_documents": corpus.provenance.quarantined_document_count,
            "quarantine_reason_counts": dict(sorted(quarantine_counts.items())),
            "seven_column_class_counts": dict(corpus.row_shape_class_counts),
            "strict_class_counts": dict(corpus.admitted_class_counts),
        },
        "split": {
            "seed": split.seed,
            "test_fraction": split.test_fraction,
            "manifest_sha256": split.manifest_sha256,
            "cluster_count": len({entry.cluster_identifier for entry in split.entries}),
            "train_source_documents": partition_counts["train"],
            "test_source_documents": partition_counts["test"],
            "novel_exact_line_sequence_test_lines": len(primary_lines),
        },
        "integrity_and_leakage": dict(integrity),
        "scientific_scope": (
            "known-script word-category instrument only; not evidence for an "
            "Indus sign value, function, language, meaning, translation, "
            "decipherment, or prize eligibility"
        ),
    }


def _cue_ablation_diagnostics(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    primary_lines: set[tuple[str, int]],
    test_support: Mapping[GoldClass, int],
    coverage: Mapping[GoldClass, float | None],
    *,
    seed: int,
) -> dict[str, Any]:
    variants: tuple[
        tuple[str, Callable[[str], str]],
        ...,
    ] = (
        (
            "ascii_digit_mask_only",
            lambda form: re.sub(r"[0-9]", "#", form),
        ),
        (
            "determinative_mask_only",
            lambda form: _DETERMINATIVE_PATTERN.sub("{DET}", form),
        ),
        (
            "ascii_digit_then_determinative_mask",
            lambda form: _DETERMINATIVE_PATTERN.sub(
                "{DET}",
                re.sub(r"[0-9]", "#", form),
            ),
        ),
    )
    truth = _truth_by_token(corpus)
    output: dict[str, Any] = {}
    for name, transform in variants:
        form_override: dict[str, str] = {}
        original_to_masked: dict[str, str] = {}
        for model_document, gold_document in zip(
            corpus.model_documents,
            corpus.gold_documents,
            strict=True,
        ):
            if model_document.document_key != gold_document.document_key:
                raise MTAACControlError("model and gold views lost alignment")
            for model_token, gold_token in zip(
                model_document.tokens,
                gold_document.tokens,
                strict=True,
            ):
                masked_id = opaque_form_sign_id(transform(gold_token.form))
                form_override[model_token.token_key] = masked_id
                previous = original_to_masked.setdefault(
                    model_token.sign_id,
                    masked_id,
                )
                if previous != masked_id:
                    raise MTAACControlError("one exact FORM identifier mapped to two masked values")
        masked = _degrade(
            corpus,
            split,
            MILD_REGIME,
            seed=seed,
            form_override=form_override,
        )
        train_examples, _ = _examples_for_partition(
            masked,
            truth,
            primary_lines,
            partition="train",
        )
        test_examples, _ = _examples_for_partition(
            masked,
            truth,
            primary_lines,
            partition="test",
        )
        distinct_masked = len(set(original_to_masked.values()))
        output[name] = {
            "metrics": _model_metrics(
                train_examples,
                test_examples,
                feature_names=FULL_FEATURES,
                effective_families=test_support,
                coverage=coverage,
            ),
            "distinct_exact_form_categories": len(original_to_masked),
            "distinct_masked_categories": distinct_masked,
            "categorical_collapses": len(original_to_masked) - distinct_masked,
            "can_change_overall_outcome": False,
        }
    return output


def _diagnostic_membership_counts(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    primary_lines: set[tuple[str, int]],
) -> dict[str, Any]:
    partition = {entry.document_key: entry.partition for entry in split.entries}
    gold_by_token = {
        token.token_key: token for document in corpus.gold_documents for token in document.tokens
    }
    train_forms: set[str] = set()
    train_stems: set[str] = set()
    source_documents = _source_documents(corpus)
    for document in source_documents:
        if partition[document.document_key] != "train":
            continue
        for line in document.lines:
            for token in line.tokens:
                gold_token = gold_by_token[token.model.token_key]
                if not gold_token.classes:
                    continue
                train_forms.add(token.model.sign_id)
                stem = _diagnostic_stem(gold_token.segm)
                if stem not in _PLACEHOLDER_STEMS:
                    train_stems.add(stem)

    token_counts: dict[str, Counter[GoldClass]] = {
        "seen_word_FORM": Counter(),
        "unseen_word_FORM": Counter(),
        "seen_SEGM_stem": Counter(),
        "unseen_SEGM_stem": Counter(),
        "omitted_placeholder_SEGM_stem": Counter(),
    }
    family_sets: dict[str, dict[GoldClass, set[str]]] = {
        stratum: {gold_class: set() for gold_class in MTAAC_GOLD_CLASSES}
        for stratum in token_counts
    }
    for document in source_documents:
        if partition[document.document_key] != "test":
            continue
        for line in document.lines:
            if (document.document_key, line.line_ordinal) not in primary_lines:
                continue
            for token in line.tokens:
                gold_token = gold_by_token[token.model.token_key]
                if len(gold_token.classes) != 1:
                    continue
                gold_class = gold_token.classes[0]
                word_stratum = (
                    "seen_word_FORM" if token.model.sign_id in train_forms else "unseen_word_FORM"
                )
                token_counts[word_stratum][gold_class] += 1
                family_sets[word_stratum][gold_class].add(document.document_key)
                stem = _diagnostic_stem(gold_token.segm)
                if stem in _PLACEHOLDER_STEMS:
                    stem_stratum = "omitted_placeholder_SEGM_stem"
                elif stem in train_stems:
                    stem_stratum = "seen_SEGM_stem"
                else:
                    stem_stratum = "unseen_SEGM_stem"
                token_counts[stem_stratum][gold_class] += 1
                family_sets[stem_stratum][gold_class].add(document.document_key)
    return {
        stratum: {
            "target_tokens": {
                gold_class: token_counts[stratum][gold_class] for gold_class in MTAAC_GOLD_CLASSES
            },
            "effective_source_document_families": {
                gold_class: len(family_sets[stratum][gold_class])
                for gold_class in MTAAC_GOLD_CLASSES
            },
            "support_minimum_families_per_class": 20,
            "support_adequate_for_future_aggregate": all(
                len(family_sets[stratum][gold_class]) >= 20 for gold_class in MTAAC_GOLD_CLASSES
            ),
        }
        for stratum in token_counts
    }


def _diagnostic_stem(segm: str) -> str:
    return segm.split("[", 1)[0].casefold()


def _finite_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MTAACControlError(f"{label} must be a finite metric")
    return float(value)


__all__ = [
    "CLEAN_REGIME",
    "HARSH_REGIME",
    "MILD_REGIME",
    "MTAAC_CONTROL_PROTOCOL_ID",
    "MTAAC_CONTROL_PROTOCOL_SHA256",
    "MTAAC_CONTROL_PROTOCOL_VERSION",
    "MTAAC_REAL_ARCHIVE_SHA256",
    "MTAAC_REAL_EVALUATION_CORPUS_SHA256",
    "MTAAC_REAL_SELECTED_MANIFEST_SHA256",
    "MTAACControlAttestation",
    "MTAACControlError",
    "MTAACDegradedCorpus",
    "MTAACObservedDocument",
    "MTAACObservedLine",
    "MTAACObservedToken",
    "MTAACRegime",
    "MTAACSplitEntry",
    "MTAACSplitManifest",
    "apply_mtaac_control_decision",
    "build_mtaac_split",
    "degrade_mtaac_corpus",
    "evaluate_mtaac_control_archive",
    "evaluate_synthetic_mtaac_control_fixture",
    "validate_mtaac_control_attestation",
    "validate_mtaac_control_protocol",
    "validate_mtaac_degradation",
    "validate_mtaac_split",
    "validate_nested_mtaac_degradations",
]
