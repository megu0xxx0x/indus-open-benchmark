"""One-way admission gateway from the frozen MTAAC V2 source to V3 training.

Only the exact pinned archive is accepted.  The gateway re-derives the frozen
V2 split and then projects representative clean and mild observations for the
training partition.  Neither the parsed corpus nor any holdout key, token, or
truth object is returned.
"""

from __future__ import annotations

import hashlib

from indusbench.mtaac import (
    MTAAC_GOLD_CLASSES,
    MTAAC_PINNED_ARCHIVE_SHA256,
    MTAAC_PINNED_COMMIT,
    MTAAC_PINNED_ROW_SHAPE_CLASS_COUNTS,
    MTAAC_PINNED_ROW_SHAPE_DOCUMENT_COUNT,
    MTAAC_PINNED_ROW_SHAPE_TOKEN_COUNT,
    MTAAC_PINNED_SELECTED_DOCUMENT_COUNT,
    MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
    MTAAC_PINNED_STRICT_CLASS_COUNTS,
    MTAAC_PINNED_STRICT_DOCUMENT_COUNT,
    MTAAC_PINNED_STRICT_TOKEN_COUNT,
    MTAACCorpus,
    MTAACError,
    parse_mtaac_archive,
)
from indusbench.mtaac_control import (
    CLEAN_REGIME,
    MILD_REGIME,
    MTAAC_CONTROL_PROTOCOL_SHA256,
    MTAAC_CONTROL_PROTOCOL_VERSION,
    MTAAC_REAL_ARCHIVE_SHA256,
    MTAAC_REAL_EVALUATION_CORPUS_SHA256,
    MTAAC_REAL_SELECTED_MANIFEST_SHA256,
    MTAACControlError,
    MTAACDegradedCorpus,
    MTAACObservedLine,
    MTAACSplitManifest,
    build_mtaac_split,
    degrade_mtaac_corpus,
)
from indusbench.v3dev.contracts import (
    MTAAC_TRAINING_GATEWAY_VERSION,
    V3_STRUCTURAL_STATES,
    MTAACTrainingBundle,
    MTAACTrainingDocument,
    MTAACTrainingLine,
    MTAACTrainingRegime,
    MTAACTrainingToken,
    MTAACTrainingView,
    V3ContractError,
    V3StructuralState,
)

MTAAC_V2_FREEZE_COMMIT = "37157f1411a55ffd91b7327afaca8fc1080fa708"
MTAAC_V2_SPLIT_SEED = 0
MTAAC_V2_TEST_FRACTION = 0.25
MTAAC_V2_SPLIT_MANIFEST_SHA256 = (
    "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30"
)
MTAAC_V2_TRAINING_FAMILY_COUNT = 271
MTAAC_V2_HOLDOUT_FAMILY_COUNT = 90


class MTAACTrainingGatewayError(V3ContractError):
    """Raised before a training bundle crosses the exact V2 boundary."""


def build_mtaac_v2_training_bundle(archive_bytes: bytes) -> MTAACTrainingBundle:
    """Return the only model-facing V3 development projection of MTAAC V2.

    The archive digest is verified here before the archive parser is invoked.
    This duplicates the parser's own digest check deliberately: even a changed
    or mocked parser cannot make the public gateway inspect a non-pinned
    container.
    """

    if not isinstance(archive_bytes, bytes):
        raise MTAACTrainingGatewayError("MTAAC V3 training input must be archive bytes")
    if _tagged_sha256(archive_bytes) != MTAAC_PINNED_ARCHIVE_SHA256:
        raise MTAACTrainingGatewayError(
            "MTAAC V3 training archive does not match the pinned SHA-256"
        )
    if (
        MTAAC_PINNED_ARCHIVE_SHA256 != MTAAC_REAL_ARCHIVE_SHA256
        or MTAAC_PINNED_SELECTED_MANIFEST_SHA256 != MTAAC_REAL_SELECTED_MANIFEST_SHA256
    ):
        raise MTAACTrainingGatewayError("MTAAC V2 source commitments disagree")

    try:
        corpus = parse_mtaac_archive(
            archive_bytes,
            expected_input_sha256=MTAAC_PINNED_ARCHIVE_SHA256,
        )
        _validate_exact_source(corpus)
        split = build_mtaac_split(
            corpus,
            seed=MTAAC_V2_SPLIT_SEED,
            test_fraction=MTAAC_V2_TEST_FRACTION,
        )
        _validate_exact_split(split)
        clean = degrade_mtaac_corpus(
            corpus,
            split,
            CLEAN_REGIME,
            seed=MTAAC_V2_SPLIT_SEED,
        )
        mild = degrade_mtaac_corpus(
            corpus,
            split,
            MILD_REGIME,
            seed=MTAAC_V2_SPLIT_SEED,
        )
        clean_view, mild_view = _project_training_views(
            corpus,
            split,
            clean,
            mild,
            expected_training_family_count=MTAAC_V2_TRAINING_FAMILY_COUNT,
            expected_holdout_family_count=MTAAC_V2_HOLDOUT_FAMILY_COUNT,
        )
        return MTAACTrainingBundle(
            gateway_version=MTAAC_TRAINING_GATEWAY_VERSION,
            source_commit=MTAAC_PINNED_COMMIT,
            v2_freeze_commit=MTAAC_V2_FREEZE_COMMIT,
            source_archive_sha256=MTAAC_PINNED_ARCHIVE_SHA256,
            selected_manifest_sha256=MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
            evaluation_corpus_sha256=MTAAC_REAL_EVALUATION_CORPUS_SHA256,
            v2_protocol_sha256=MTAAC_CONTROL_PROTOCOL_SHA256,
            split_manifest_sha256=MTAAC_V2_SPLIT_MANIFEST_SHA256,
            split_seed=MTAAC_V2_SPLIT_SEED,
            split_test_fraction=MTAAC_V2_TEST_FRACTION,
            training_family_count=MTAAC_V2_TRAINING_FAMILY_COUNT,
            excluded_holdout_family_count=MTAAC_V2_HOLDOUT_FAMILY_COUNT,
            states=V3_STRUCTURAL_STATES,
            clean=clean_view,
            mild=mild_view,
        )
    except MTAACTrainingGatewayError:
        raise
    except (MTAACError, MTAACControlError, V3ContractError) as error:
        raise MTAACTrainingGatewayError(
            "fixed MTAAC V2 source failed the V3 training boundary"
        ) from error


def _validate_exact_source(corpus: MTAACCorpus) -> None:
    if not isinstance(corpus, MTAACCorpus):
        raise MTAACTrainingGatewayError("MTAAC parser did not return a typed corpus")
    provenance = corpus.provenance
    expected_provenance = {
        "adapter_target_commit": MTAAC_PINNED_COMMIT,
        "input_kind": "archive_tar",
        "input_sha256": MTAAC_PINNED_ARCHIVE_SHA256,
        "caller_digest_verified": True,
        "selected_manifest_sha256": MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
        "selected_document_count": MTAAC_PINNED_SELECTED_DOCUMENT_COUNT,
        "row_shape_document_count": MTAAC_PINNED_ROW_SHAPE_DOCUMENT_COUNT,
        "row_shape_token_count": MTAAC_PINNED_ROW_SHAPE_TOKEN_COUNT,
        "admitted_document_count": MTAAC_PINNED_STRICT_DOCUMENT_COUNT,
        "admitted_token_count": MTAAC_PINNED_STRICT_TOKEN_COUNT,
        "quarantined_document_count": (
            MTAAC_PINNED_SELECTED_DOCUMENT_COUNT - MTAAC_PINNED_STRICT_DOCUMENT_COUNT
        ),
        "revision_attestation": "target_only_caller_bytes_not_git_attested",
    }
    if any(
        getattr(provenance, field_name, None) != expected
        for field_name, expected in expected_provenance.items()
    ):
        raise MTAACTrainingGatewayError("MTAAC parser provenance is not the fixed source")
    if (
        len(corpus.model_documents) != MTAAC_PINNED_STRICT_DOCUMENT_COUNT
        or len(corpus.gold_documents) != MTAAC_PINNED_STRICT_DOCUMENT_COUNT
        or len(corpus.quarantined_documents)
        != MTAAC_PINNED_SELECTED_DOCUMENT_COUNT - MTAAC_PINNED_STRICT_DOCUMENT_COUNT
        or sum(len(document.tokens) for document in corpus.model_documents)
        != MTAAC_PINNED_STRICT_TOKEN_COUNT
        or sum(len(document.tokens) for document in corpus.gold_documents)
        != MTAAC_PINNED_STRICT_TOKEN_COUNT
        or corpus.row_shape_class_counts != MTAAC_PINNED_ROW_SHAPE_CLASS_COUNTS
        or corpus.admitted_class_counts != MTAAC_PINNED_STRICT_CLASS_COUNTS
    ):
        raise MTAACTrainingGatewayError("MTAAC parser counts are not the fixed source")


def _validate_exact_split(split: MTAACSplitManifest) -> None:
    if not isinstance(split, MTAACSplitManifest):
        raise MTAACTrainingGatewayError("MTAAC V2 splitter did not return a typed manifest")
    if (
        split.seed != MTAAC_V2_SPLIT_SEED
        or split.test_fraction != MTAAC_V2_TEST_FRACTION
        or split.manifest_sha256 != MTAAC_V2_SPLIT_MANIFEST_SHA256
    ):
        raise MTAACTrainingGatewayError("MTAAC split is not the exact frozen V2 split")
    train_entries = tuple(entry for entry in split.entries if entry.partition == "train")
    holdout_entries = tuple(entry for entry in split.entries if entry.partition == "test")
    if (
        len(train_entries) != MTAAC_V2_TRAINING_FAMILY_COUNT
        or len(holdout_entries) != MTAAC_V2_HOLDOUT_FAMILY_COUNT
        or len(split.entries) != MTAAC_V2_TRAINING_FAMILY_COUNT + MTAAC_V2_HOLDOUT_FAMILY_COUNT
        or len({entry.document_key for entry in split.entries}) != len(split.entries)
        or len({entry.cluster_identifier for entry in train_entries})
        != MTAAC_V2_TRAINING_FAMILY_COUNT
        or len({entry.cluster_identifier for entry in holdout_entries})
        != MTAAC_V2_HOLDOUT_FAMILY_COUNT
        or len({entry.cluster_identifier for entry in split.entries}) != len(split.entries)
    ):
        raise MTAACTrainingGatewayError(
            "MTAAC split does not contain exactly 271 train and 90 holdout families"
        )


def _project_training_views(
    corpus: MTAACCorpus,
    split: MTAACSplitManifest,
    clean: MTAACDegradedCorpus,
    mild: MTAACDegradedCorpus,
    *,
    expected_training_family_count: int,
    expected_holdout_family_count: int,
) -> tuple[MTAACTrainingView, MTAACTrainingView]:
    """Project already-validated observations without traversing holdout gold.

    This isolated helper exists so the one-way membership boundary can be
    tested independently of the exact-archive and deterministic-split gates.
    Public callers must use :func:`build_mtaac_v2_training_bundle`.
    """

    train_entries = tuple(entry for entry in split.entries if entry.partition == "train")
    holdout_entries = tuple(entry for entry in split.entries if entry.partition == "test")
    if (
        len(train_entries) != expected_training_family_count
        or len(holdout_entries) != expected_holdout_family_count
        or len(train_entries) + len(holdout_entries) != len(split.entries)
    ):
        raise MTAACTrainingGatewayError("training projection split counts disagree")
    for degraded, expected_regime in (
        (clean, CLEAN_REGIME),
        (mild, MILD_REGIME),
    ):
        if (
            not isinstance(degraded, MTAACDegradedCorpus)
            or degraded.regime != expected_regime
            or degraded.seed != split.seed
            or degraded.split_manifest_sha256 != split.manifest_sha256
            or degraded.protocol_version != MTAAC_CONTROL_PROTOCOL_VERSION
        ):
            raise MTAACTrainingGatewayError(
                "training projection degradation is not bound to the split and regime"
            )
    train_clusters = {entry.document_key: entry.cluster_identifier for entry in train_entries}
    if (
        len(train_clusters) != expected_training_family_count
        or len(set(train_clusters.values())) != expected_training_family_count
    ):
        raise MTAACTrainingGatewayError("training projection families are not unique")

    truth_by_token = _training_truth_by_token(
        corpus,
        frozenset(train_clusters),
        expected_training_family_count=expected_training_family_count,
    )
    clean_view = _project_training_view(
        clean,
        regime="clean",
        train_clusters=train_clusters,
        truth_by_token=truth_by_token,
    )
    mild_view = _project_training_view(
        mild,
        regime="mild",
        train_clusters=train_clusters,
        truth_by_token=truth_by_token,
    )

    clean_token_keys = {
        token.token_key
        for document in clean_view.documents
        for line in document.lines
        for token in line.tokens
    }
    mild_token_keys = {
        token.token_key
        for document in mild_view.documents
        for line in document.lines
        for token in line.tokens
    }
    if clean_token_keys != set(truth_by_token):
        raise MTAACTrainingGatewayError(
            "clean representatives do not contain every and only training token"
        )
    if not mild_token_keys <= clean_token_keys:
        raise MTAACTrainingGatewayError("mild representatives contain a non-training token")
    return clean_view, mild_view


def _training_truth_by_token(
    corpus: MTAACCorpus,
    training_document_keys: frozenset[str],
    *,
    expected_training_family_count: int,
) -> dict[str, V3StructuralState]:
    truth_by_token: dict[str, V3StructuralState] = {}
    seen_documents: set[str] = set()
    for document in corpus.gold_documents:
        if document.document_key not in training_document_keys:
            continue
        if document.document_key in seen_documents:
            raise MTAACTrainingGatewayError("a training gold document is duplicated")
        seen_documents.add(document.document_key)
        for token in document.tokens:
            if token.token_key in truth_by_token:
                raise MTAACTrainingGatewayError("a training gold token is duplicated")
            if len(token.classes) > 1:
                raise MTAACTrainingGatewayError("a training gold token has overlapping classes")
            if not token.classes:
                state: V3StructuralState = "context_only"
            else:
                state = token.classes[0]
                if state not in MTAAC_GOLD_CLASSES:
                    raise MTAACTrainingGatewayError("a training gold token has an unknown class")
            truth_by_token[token.token_key] = state
    if len(seen_documents) != expected_training_family_count or not truth_by_token:
        raise MTAACTrainingGatewayError("training gold documents do not match split membership")
    return truth_by_token


def _project_training_view(
    degraded: MTAACDegradedCorpus,
    *,
    regime: MTAACTrainingRegime,
    train_clusters: dict[str, str],
    truth_by_token: dict[str, V3StructuralState],
) -> MTAACTrainingView:
    if degraded.regime.name != regime:
        raise MTAACTrainingGatewayError("degraded corpus regime does not match projection")
    representatives = {}
    for observation in degraded.observations:
        if observation.document_key not in train_clusters:
            continue
        if observation.partition != "train":
            raise MTAACTrainingGatewayError("training family is marked as holdout")
        if observation.replica_index != 0:
            continue
        if observation.document_key in representatives:
            raise MTAACTrainingGatewayError("training family has duplicate representatives")
        representatives[observation.document_key] = observation
    if set(representatives) != set(train_clusters):
        raise MTAACTrainingGatewayError("degradation lacks a representative training family")

    documents = tuple(
        MTAACTrainingDocument(
            document_key=document_key,
            cluster_identifier=train_clusters[document_key],
            regime=regime,
            replica_index=0,
            lines=tuple(
                _project_training_line(line, truth_by_token)
                for line in representatives[document_key].lines
            ),
        )
        for document_key in sorted(representatives)
    )
    return MTAACTrainingView(regime=regime, documents=documents)


def _project_training_line(
    line: MTAACObservedLine,
    truth_by_token: dict[str, V3StructuralState],
) -> MTAACTrainingLine:
    if line.reported_direction == "known_source_order":
        ordered = sorted(line.tokens, key=lambda token: (token.source_order, token.token_key))
    elif line.reported_direction == "unknown_visual_order":
        ordered = sorted(line.tokens, key=lambda token: (token.visual_index, token.token_key))
    else:
        raise MTAACTrainingGatewayError("degraded line has an unsupported direction")
    if (
        len({token.token_key for token in ordered}) != len(ordered)
        or len({token.source_order for token in ordered}) != len(ordered)
        or {token.visual_index for token in ordered} != set(range(len(ordered)))
    ):
        raise MTAACTrainingGatewayError("degraded line token order is ambiguous")
    projected: list[MTAACTrainingToken] = []
    for token in ordered:
        state = truth_by_token.get(token.token_key)
        if state is None:
            raise MTAACTrainingGatewayError("degraded token has no training-side truth")
        projected.append(
            MTAACTrainingToken(
                token_key=token.token_key,
                observed_form_id=token.observed_form_id,
                state=state,
                damaged=token.damaged,
            )
        )
    return MTAACTrainingLine(
        line_ordinal=line.line_ordinal,
        reported_direction=line.reported_direction,
        tokens=tuple(projected),
    )


def _tagged_sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


__all__ = [
    "MTAAC_V2_FREEZE_COMMIT",
    "MTAAC_V2_HOLDOUT_FAMILY_COUNT",
    "MTAAC_V2_SPLIT_MANIFEST_SHA256",
    "MTAAC_V2_SPLIT_SEED",
    "MTAAC_V2_TEST_FRACTION",
    "MTAAC_V2_TRAINING_FAMILY_COUNT",
    "MTAACTrainingGatewayError",
    "build_mtaac_v2_training_bundle",
]
