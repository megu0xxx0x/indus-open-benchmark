"""Deterministic, aggregate-only execution for MTAAC V3 development.

This module can consume only the narrow training bundle produced by the V2
gateway.  Model selection uses mild observations inside family-disjoint
cross-validation.  Clean observations are reported only as a diagnostic.
No document, token, member, or family identifier crosses the report boundary.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from indusbench.mtaac import (
    MTAAC_PINNED_ARCHIVE_SHA256,
    MTAAC_PINNED_COMMIT,
    MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
)
from indusbench.mtaac_control import (
    MTAAC_CONTROL_PROTOCOL_SHA256,
    MTAAC_REAL_EVALUATION_CORPUS_SHA256,
)
from indusbench.v3dev.contracts import (
    MTAAC_TRAINING_GATEWAY_VERSION,
    V3_STRUCTURAL_STATES,
    MTAACTrainingBundle,
    MTAACTrainingDocument,
    MTAACTrainingView,
    V3StructuralState,
)
from indusbench.v3dev.folds import (
    CandidateScore,
    FamilySupport,
    FoldSupportSummary,
    GroupedFold,
    build_grouped_folds,
    build_nested_grouped_folds,
    select_one_standard_error,
)
from indusbench.v3dev.metrics import (
    WeightedStatePrediction,
    add_confusion_matrices,
    metrics_from_confusion,
    weighted_state_metrics,
)
from indusbench.v3dev.mtaac_training import (
    MTAAC_V2_FREEZE_COMMIT,
    MTAAC_V2_HOLDOUT_FAMILY_COUNT,
    MTAAC_V2_SPLIT_MANIFEST_SHA256,
    MTAAC_V2_SPLIT_SEED,
    MTAAC_V2_TEST_FRACTION,
    MTAAC_V2_TRAINING_FAMILY_COUNT,
)
from indusbench.v3dev.plan import (
    V3_DEVELOPMENT_PLAN_SHA256,
    validate_v3_development_plan,
)
from indusbench.v3dev.sequence import (
    LAPLACE_ALPHA,
    STRUCTURAL_FEATURE_NAMES,
    V3_SEQUENCE_MODEL_VERSION,
    V3SequenceModel,
)

V3_DEVELOPMENT_REPORT_VERSION = "mtaac-v3-development-report-v1"
V3_FINAL_SELECTION_DOMAIN = "indusbench-v3dev:full-selection:v1"
_IMPLEMENTATION_COMMIT = re.compile(r"[0-9a-f]{40}")


class V3DevelopmentError(ValueError):
    """Raised when fixed development execution cannot be completed."""


@dataclass(frozen=True, slots=True)
class V3Candidate:
    """One member of the fixed nine-candidate grid."""

    candidate_id: str
    gamma: float
    transition_strength: float
    complexity_rank: int


V3_CANDIDATES: tuple[V3Candidate, ...] = tuple(
    V3Candidate(
        candidate_id=f"gamma-{gamma:g}__lambda-{transition_strength:g}",
        gamma=gamma,
        transition_strength=transition_strength,
        complexity_rank=(gamma_index * 3) + transition_index,
    )
    for gamma_index, gamma in enumerate((0.0, 0.5, 1.0))
    for transition_index, transition_strength in enumerate((0.0, 0.5, 1.0))
)


def run_v3_development(
    bundle: MTAACTrainingBundle,
    *,
    plan_bytes: bytes,
    implementation_commit: str,
) -> dict[str, Any]:
    """Run the closed V3 development protocol and return aggregate JSON data."""

    validate_v3_development_plan(plan_bytes)
    _validate_bundle_commitments(bundle)
    if (
        not isinstance(implementation_commit, str)
        or _IMPLEMENTATION_COMMIT.fullmatch(implementation_commit) is None
    ):
        raise V3DevelopmentError("implementation commit must be lowercase 40-hex")

    families = _family_support(bundle.clean)
    nested_plan = build_nested_grouped_folds(families)
    outer_reports: list[dict[str, Any]] = []
    clean_outer_confusions: list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]] = []
    mild_outer_confusions: list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]] = []

    for nested in nested_plan.outer_folds:
        inner_scores = _score_candidates(bundle, nested.inner_folds)
        selected_score = select_one_standard_error(inner_scores)
        selected = _candidate_by_id(selected_score.candidate_id)
        outer_model = _fit_model(
            bundle,
            nested.outer.train_family_ids,
            gamma=selected.gamma,
        )
        clean_metrics = _evaluate_view(
            outer_model,
            bundle.clean,
            nested.outer.validation_family_ids,
            transition_strength=selected.transition_strength,
        )
        mild_metrics = _evaluate_view(
            outer_model,
            bundle.mild,
            nested.outer.validation_family_ids,
            transition_strength=selected.transition_strength,
        )
        clean_outer_confusions.append(_metric_confusion(clean_metrics))
        mild_outer_confusions.append(_metric_confusion(mild_metrics))
        outer_reports.append(
            {
                "outer_fold_index": nested.outer.index,
                "support": _support_report(nested.outer.support_summary()),
                "inner_selection": {
                    "selection_metric": "family_weighted_mild_macro_f1",
                    "rule": "one_standard_error_simplest_lower_gamma_then_lambda",
                    "candidates": [
                        _candidate_score_report(score)
                        for score in sorted(inner_scores, key=lambda value: value.complexity_rank)
                    ],
                    "selected_candidate": _candidate_report(selected),
                },
                "diagnostics": {
                    "clean": clean_metrics,
                    "clean_role": "diagnostic_not_used_for_selection",
                    "mild": mild_metrics,
                    "mild_role": "outer_development_estimate",
                },
            }
        )

    full_folds = build_grouped_folds(
        families,
        fold_count=4,
        domain=V3_FINAL_SELECTION_DOMAIN,
    )
    final_scores = _score_candidates(bundle, full_folds)
    final_selected_score = select_one_standard_error(final_scores)
    final_selected = _candidate_by_id(final_selected_score.candidate_id)
    all_family_ids = tuple(sorted(family.family_id for family in families))
    final_model = _fit_model(bundle, all_family_ids, gamma=final_selected.gamma)

    clean_oof = metrics_from_confusion(add_confusion_matrices(clean_outer_confusions))
    mild_oof = metrics_from_confusion(add_confusion_matrices(mild_outer_confusions))
    return {
        "analysis": "mtaac_v3_structural_development",
        "report_version": V3_DEVELOPMENT_REPORT_VERSION,
        "terminal_status": "development_complete",
        "development_only": True,
        "model_executed": True,
        "scientific_metrics_emitted": True,
        "plan_sha256": V3_DEVELOPMENT_PLAN_SHA256,
        "implementation_commit": implementation_commit,
        "parent_commitments": {
            "gateway_version": bundle.gateway_version,
            "mtaac_source_commit": bundle.source_commit,
            "v2_freeze_commit": bundle.v2_freeze_commit,
            "source_archive_sha256": bundle.source_archive_sha256,
            "selected_manifest_sha256": bundle.selected_manifest_sha256,
            "evaluation_corpus_sha256": bundle.evaluation_corpus_sha256,
            "v2_protocol_sha256": bundle.v2_protocol_sha256,
            "v2_split_manifest_sha256": bundle.split_manifest_sha256,
        },
        "data_boundary": {
            "model_training_family_count": bundle.training_family_count,
            "v2_holdout_family_count_excluded": bundle.excluded_holdout_family_count,
            "v2_holdout_exposed_to_model": False,
            "v2_holdout_scored": False,
            "reserved_validation_source_loaded": False,
            "regimes_used": ["clean", "mild"],
            "replica_index_used": 0,
        },
        "model_contract": {
            "version": V3_SEQUENCE_MODEL_VERSION,
            "states": list(V3_STRUCTURAL_STATES),
            "structural_features": list(STRUCTURAL_FEATURE_NAMES),
            "laplace_alpha": LAPLACE_ALPHA,
            "candidate_grid": [_candidate_report(candidate) for candidate in V3_CANDIDATES],
            "selection_regime": "mild",
            "clean_role": "diagnostic_not_used_for_selection",
            "family_weighting": "equal_total_mass_per_family_per_evaluation_regime",
        },
        "nested_development": {
            "outer_fold_count": 5,
            "inner_fold_count": 4,
            "outer_folds": outer_reports,
            "out_of_fold_metrics": {
                "clean": clean_oof,
                "mild": mild_oof,
            },
        },
        "final_development_model": {
            "selection_fold_count": 4,
            "selection_domain": V3_FINAL_SELECTION_DOMAIN,
            "selection_metric": "family_weighted_mild_macro_f1",
            "selection_rule": "one_standard_error_simplest_lower_gamma_then_lambda",
            "candidates": [
                _candidate_score_report(score)
                for score in sorted(final_scores, key=lambda value: value.complexity_rank)
            ],
            "selected_candidate": _candidate_report(final_selected),
            "model_state_commitment": final_model.model_state_commitment(
                transition_strength=final_selected.transition_strength
            ),
        },
        "claim_scope": {
            "class": "development_only",
            "eligible_as_reserved_validation_result": False,
            "eligible_as_v2_holdout_result": False,
            "individual_predictions_published": False,
        },
    }


def _validate_bundle_commitments(bundle: MTAACTrainingBundle) -> None:
    if not isinstance(bundle, MTAACTrainingBundle):
        raise V3DevelopmentError("runner requires the typed MTAAC training bundle")
    expected: dict[str, object] = {
        "gateway_version": MTAAC_TRAINING_GATEWAY_VERSION,
        "source_commit": MTAAC_PINNED_COMMIT,
        "v2_freeze_commit": MTAAC_V2_FREEZE_COMMIT,
        "source_archive_sha256": MTAAC_PINNED_ARCHIVE_SHA256,
        "selected_manifest_sha256": MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
        "evaluation_corpus_sha256": MTAAC_REAL_EVALUATION_CORPUS_SHA256,
        "v2_protocol_sha256": MTAAC_CONTROL_PROTOCOL_SHA256,
        "split_manifest_sha256": MTAAC_V2_SPLIT_MANIFEST_SHA256,
        "split_seed": MTAAC_V2_SPLIT_SEED,
        "split_test_fraction": MTAAC_V2_TEST_FRACTION,
        "training_family_count": MTAAC_V2_TRAINING_FAMILY_COUNT,
        "excluded_holdout_family_count": MTAAC_V2_HOLDOUT_FAMILY_COUNT,
        "states": V3_STRUCTURAL_STATES,
    }
    if any(getattr(bundle, name) != value for name, value in expected.items()):
        raise V3DevelopmentError("training bundle does not match the fixed V2 parent boundary")


def _family_support(view: MTAACTrainingView) -> tuple[FamilySupport, ...]:
    families: list[FamilySupport] = []
    for document in view.documents:
        counts = tuple(
            sum(token.state == state for line in document.lines for token in line.tokens)
            for state in V3_STRUCTURAL_STATES
        )
        families.append(
            FamilySupport(
                family_id=document.cluster_identifier,
                state_counts=cast(tuple[int, int, int, int, int], counts),
            )
        )
    return tuple(families)


def _documents_for_families(
    bundle: MTAACTrainingBundle,
    family_ids: Sequence[str],
) -> tuple[MTAACTrainingDocument, ...]:
    selected = set(family_ids)
    documents = tuple(
        document
        for view in (bundle.clean, bundle.mild)
        for document in view.documents
        if document.cluster_identifier in selected
    )
    observed = {document.cluster_identifier for document in documents}
    if observed != selected:
        raise V3DevelopmentError("fold family selection is incomplete")
    return documents


def _fit_model(
    bundle: MTAACTrainingBundle,
    family_ids: Sequence[str],
    *,
    gamma: float,
) -> V3SequenceModel:
    family_tuple = tuple(family_ids)
    return V3SequenceModel.fit(
        _documents_for_families(bundle, family_tuple),
        base_family_weights={family_id: 1.0 for family_id in family_tuple},
        gamma=gamma,
    )


def _evaluate_view(
    model: V3SequenceModel,
    view: MTAACTrainingView,
    family_ids: Sequence[str],
    *,
    transition_strength: float,
) -> dict[str, Any]:
    selected = set(family_ids)
    documents = tuple(
        document for document in view.documents if document.cluster_identifier in selected
    )
    if {document.cluster_identifier for document in documents} != selected:
        raise V3DevelopmentError("evaluation family selection is incomplete")

    rows: list[WeightedStatePrediction] = []
    for document in documents:
        token_count = sum(len(line.tokens) for line in document.lines)
        if token_count <= 0:
            raise V3DevelopmentError("evaluation family has no retained token")
        token_weight = 1.0 / token_count
        for line in document.lines:
            predicted = model.decode(
                line.to_observation(),
                transition_strength=transition_strength,
            )
            if len(predicted) != len(line.tokens):
                raise V3DevelopmentError("decoded sequence length does not match truth")
            rows.extend(
                WeightedStatePrediction(
                    truth=token.state,
                    predicted=predicted_state,
                    weight=token_weight,
                )
                for token, predicted_state in zip(line.tokens, predicted, strict=True)
            )
    return weighted_state_metrics(rows)


def _score_candidates(
    bundle: MTAACTrainingBundle,
    folds: Sequence[GroupedFold],
) -> tuple[CandidateScore, ...]:
    scores: dict[str, list[float]] = {candidate.candidate_id: [] for candidate in V3_CANDIDATES}
    for fold in folds:
        models = {
            gamma: _fit_model(bundle, fold.train_family_ids, gamma=gamma)
            for gamma in (0.0, 0.5, 1.0)
        }
        for candidate in V3_CANDIDATES:
            metric = _evaluate_view(
                models[candidate.gamma],
                bundle.mild,
                fold.validation_family_ids,
                transition_strength=candidate.transition_strength,
            )
            scores[candidate.candidate_id].append(float(metric["macro_f1"]))
    return tuple(
        CandidateScore(
            candidate_id=candidate.candidate_id,
            complexity_rank=candidate.complexity_rank,
            fold_scores=tuple(scores[candidate.candidate_id]),
        )
        for candidate in V3_CANDIDATES
    )


def _candidate_by_id(candidate_id: str) -> V3Candidate:
    matches = tuple(
        candidate for candidate in V3_CANDIDATES if candidate.candidate_id == candidate_id
    )
    if len(matches) != 1:
        raise V3DevelopmentError("selected candidate is outside the fixed grid")
    return matches[0]


def _candidate_report(candidate: V3Candidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "gamma": candidate.gamma,
        "transition_strength": candidate.transition_strength,
        "complexity_rank": candidate.complexity_rank,
    }


def _candidate_score_report(score: CandidateScore) -> dict[str, Any]:
    summary = score.summary()
    return {
        **_candidate_report(_candidate_by_id(score.candidate_id)),
        "mild_macro_f1_by_fold": list(score.fold_scores),
        "mean": summary.mean,
        "standard_error": summary.standard_error,
        "fold_count": summary.fold_count,
    }


def _support_report(summary: FoldSupportSummary) -> dict[str, Any]:
    return {
        "train_family_count": summary.train_family_count,
        "validation_family_count": summary.validation_family_count,
        "train_state_support": dict(
            zip(V3_STRUCTURAL_STATES, summary.train_state_support, strict=True)
        ),
        "validation_state_support": dict(
            zip(V3_STRUCTURAL_STATES, summary.validation_state_support, strict=True)
        ),
    }


def _metric_confusion(
    metrics: Mapping[str, Any],
) -> Mapping[V3StructuralState, Mapping[V3StructuralState, float]]:
    value = metrics.get("weighted_confusion_matrix")
    if not isinstance(value, Mapping):
        raise V3DevelopmentError("metric report is missing its aggregate confusion matrix")
    return cast(
        Mapping[V3StructuralState, Mapping[V3StructuralState, float]],
        value,
    )


__all__ = [
    "V3_CANDIDATES",
    "V3_DEVELOPMENT_REPORT_VERSION",
    "V3_FINAL_SELECTION_DOMAIN",
    "V3Candidate",
    "V3DevelopmentError",
    "run_v3_development",
]
