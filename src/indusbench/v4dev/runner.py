"""Deterministic aggregate-only execution for MTAAC V4 development.

V4 reuses only the fixed V2 training gateway and the immutable V3 outer-fold
assignment.  Profile construction receives truth-free observation objects;
models receive identifier-free feature objects; truth is joined only in this
runner after feature transformation.  No item or family identifier crosses
the returned report boundary.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

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
    FamilySupport,
    FoldSupportSummary,
    GroupedFold,
    build_grouped_folds,
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
from indusbench.v4dev.contracts import (
    V4FeatureDocument,
    V4FeatureLine,
    V4LabeledFeatureDocument,
    V4LabeledFeatureFamily,
    V4LabeledFeatureLine,
    V4ObservationCorpus,
    V4ObservationDocument,
)
from indusbench.v4dev.corpus_statistics import (
    LOCAL_FEATURE_NAMES,
    PROFILE_FEATURE_NAMES,
    V4_CORPUS_PROFILE_VERSION,
    V4CorpusProfile,
)
from indusbench.v4dev.plan import (
    V4_DEVELOPMENT_PLAN_SHA256,
    validate_v4_development_plan,
)
from indusbench.v4dev.sequence import (
    CLASS_ADJUSTMENT_GAMMA,
    CRF_L2_RHO,
    LBFGS_ARMIJO_C1,
    LBFGS_BACKTRACK_FACTOR,
    LBFGS_GRADIENT_TOLERANCE,
    LBFGS_HISTORY_SIZE,
    LBFGS_MAX_ITERATIONS,
    LBFGS_MAX_LINE_SEARCH_TRIALS,
    LBFGS_MIN_STEP,
    LBFGS_RELATIVE_OBJECTIVE_TOLERANCE,
    LBFGS_STABLE_ITERATIONS,
    LBFGS_STALLED_GRADIENT_TOLERANCE,
    V4_CRF_MODEL_VERSION,
    V4LinearChainCRF,
    V4LogisticEmissionModel,
)

V4_DEVELOPMENT_REPORT_VERSION: Final = "mtaac-v4-development-report-v1"
V4_OUTER_FOLD_DOMAIN: Final = "primary-outer-v1"
V4_OUTER_FOLD_COUNT: Final = 5

V3_FREEZE_COMMIT: Final = "5b39c8ba358ea66e46183cbf02eb07fbc91861e2"
V3_RESULT_COMMIT: Final = "9f70679d0c0138d67d000e65ac71e258bcf439e0"
V3_PLAN_SHA256: Final = "sha256:b2100318fa0e958d741fd25d7b9263ae1574967f4585f4609c118b1bd16880dd"
V3_RESULT_SHA256: Final = "sha256:e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2"
V3_MODEL_STATE_COMMITMENT: Final = (
    "sha256:d2b332f6d9b2b6acae206f7f0b8db07d7e2431b5995168f7228a374e4f134158"
)
V3_MILD_MACRO_F1: Final = 0.32432759235715436
V3_MILD_MACRO_F1_BY_OUTER_FOLD: Final = (
    0.31683351626900313,
    0.32138764286827887,
    0.3088289319784221,
    0.30447569487308923,
    0.33797633693780393,
)

MILD_MACRO_F1_MINIMUM: Final = V3_MILD_MACRO_F1 + 0.04
MILD_SETTLEMENT_RECALL_MINIMUM: Final = 0.15
PAIRED_POSITIVE_FOLD_MINIMUM: Final = 4
FULL_MINUS_LOCAL_MINIMUM: Final = 0.02
MILD_RECALL_FLOORS: Final = {
    "context_only": 0.520654531441017,
    "quantity": 0.1765055025096581,
    "unit": 0.3767836311289388,
    "person_name": 0.4988092152820551,
}
CLEAN_MACRO_F1_MINIMUM: Final = 0.36
CLEAN_SETTLEMENT_RECALL_MINIMUM: Final = 0.10
SELF_INFORMATION_DELTA_MAXIMUM: Final = 0.05

_IMPLEMENTATION_COMMIT = re.compile(r"[0-9a-f]{40}")


class V4DevelopmentError(ValueError):
    """Raised when fixed V4 development execution cannot complete safely."""


@dataclass(frozen=True, slots=True)
class _PreparedDocument:
    source: MTAACTrainingDocument
    features: V4FeatureDocument


@dataclass(frozen=True, slots=True)
class _PreparedPartition:
    documents: tuple[_PreparedDocument, ...]
    profile_commitment: str


def run_v4_development(
    bundle: MTAACTrainingBundle,
    *,
    plan_bytes: bytes,
    implementation_commit: str,
) -> dict[str, Any]:
    """Run the closed, single-candidate V4 development protocol."""

    validate_v4_development_plan(plan_bytes)
    _validate_bundle_commitments(bundle)
    if (
        not isinstance(implementation_commit, str)
        or _IMPLEMENTATION_COMMIT.fullmatch(implementation_commit) is None
    ):
        raise V4DevelopmentError("implementation commit must be lowercase 40-hex")

    families = _family_support(bundle.clean)
    outer_folds = build_grouped_folds(
        families,
        fold_count=V4_OUTER_FOLD_COUNT,
        domain=V4_OUTER_FOLD_DOMAIN,
    )
    outer_reports: list[dict[str, Any]] = []
    confusion_sets: dict[
        str,
        list[Mapping[V3StructuralState, Mapping[V3StructuralState, float]]],
    ] = {
        name: []
        for name in (
            "primary_clean",
            "primary_mild",
            "no_corpus_profile",
            "transition_zero",
            "logistic_emission",
            "self_inclusive_target_profile",
            "strict_single_family_profile",
        )
    }
    v4_mild_by_outer_fold: list[float] = []

    for fold in outer_folds:
        prepared = _prepare_outer_fold(bundle, fold)
        primary_model = V4LinearChainCRF.fit(prepared["full_train_families"])
        local_model = V4LinearChainCRF.fit(prepared["local_train_families"])
        logistic_model = V4LogisticEmissionModel.fit(prepared["full_train_families"])

        primary_clean = _evaluate_model(
            primary_model,
            prepared["validation_clean"],
        )
        primary_mild = _evaluate_model(
            primary_model,
            prepared["validation_mild"],
        )
        no_profile = _evaluate_model(
            local_model,
            prepared["validation_mild_local"],
        )
        transition_zero = _evaluate_model(
            primary_model,
            prepared["validation_mild"],
            transition_zero=True,
        )
        logistic = _evaluate_model(
            logistic_model,
            prepared["validation_mild"],
        )
        self_inclusive = _evaluate_model(
            primary_model,
            prepared["validation_mild_self_inclusive"],
        )
        strict_single = _evaluate_model(
            primary_model,
            prepared["validation_mild_strict_single"],
        )

        metrics_by_key = {
            "primary_clean": primary_clean,
            "primary_mild": primary_mild,
            "no_corpus_profile": no_profile,
            "transition_zero": transition_zero,
            "logistic_emission": logistic,
            "self_inclusive_target_profile": self_inclusive,
            "strict_single_family_profile": strict_single,
        }
        for name, metrics in metrics_by_key.items():
            confusion_sets[name].append(_metric_confusion(metrics))
        v4_mild_by_outer_fold.append(float(primary_mild["macro_f1"]))

        outer_reports.append(
            {
                "outer_fold_index": fold.index,
                "support": _support_report(fold.support_summary()),
                "profile_batch_commitments": prepared["profile_commitments"],
                "optimizer": {
                    "primary": primary_model.optimization_summary(),
                    "no_corpus_profile": local_model.optimization_summary(),
                    "logistic_emission": logistic_model.optimization_summary(),
                },
                "metrics": {
                    "primary": {
                        "clean": primary_clean,
                        "mild": primary_mild,
                    },
                    "diagnostics": {
                        "no_corpus_profile": no_profile,
                        "transition_zero": transition_zero,
                        "logistic_emission": logistic,
                        "self_inclusive_target_profile": self_inclusive,
                        "strict_single_family_profile": strict_single,
                    },
                },
            }
        )

    oof = {
        name: metrics_from_confusion(add_confusion_matrices(matrices))
        for name, matrices in confusion_sets.items()
    }
    delta_by_outer = [
        current - baseline
        for current, baseline in zip(
            v4_mild_by_outer_fold,
            V3_MILD_MACRO_F1_BY_OUTER_FOLD,
            strict=True,
        )
    ]
    positive_delta_fold_count = sum(delta > 0.0 for delta in delta_by_outer)
    gate_decision = _gate_decision(
        primary_clean=oof["primary_clean"],
        primary_mild=oof["primary_mild"],
        no_profile=oof["no_corpus_profile"],
        self_inclusive=oof["self_inclusive_target_profile"],
        positive_delta_fold_count=positive_delta_fold_count,
    )

    all_family_ids = tuple(sorted(family.family_id for family in families))
    final_model: V4LinearChainCRF | None = None
    if gate_decision["all_passed"] is True:
        final_full = _prepare_training_families(
            bundle,
            all_family_ids,
        )
        final_model = V4LinearChainCRF.fit(final_full["families"])

    return {
        "analysis": "mtaac_v4_distributional_crf_development",
        "report_version": V4_DEVELOPMENT_REPORT_VERSION,
        "terminal_status": gate_decision["terminal_status"],
        "development_only": True,
        "model_executed": True,
        "scientific_metrics_emitted": True,
        "plan_sha256": V4_DEVELOPMENT_PLAN_SHA256,
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
            "v3_freeze_commit": V3_FREEZE_COMMIT,
            "v3_result_commit": V3_RESULT_COMMIT,
            "v3_plan_sha256": V3_PLAN_SHA256,
            "v3_result_sha256": V3_RESULT_SHA256,
            "v3_model_state_commitment": V3_MODEL_STATE_COMMITMENT,
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
        "profile_contract": {
            "version": V4_CORPUS_PROFILE_VERSION,
            "inference_mode": ("target_batch_partition_regime_local_document_leave_one_family_out"),
            "local_features": list(LOCAL_FEATURE_NAMES),
            "profile_features": list(PROFILE_FEATURE_NAMES),
            "feature_value_types": {
                "local": "fixed_categorical",
                "type_support": "fixed_categorical",
                "profile_numeric": "direct_float64_in_closed_unit_interval",
                "missing_or_boundary": "fixed_categorical_marker",
            },
            "line_template_used": False,
            "gold_used": False,
            "identity_serialized": False,
            "train_validation_shared": False,
            "clean_mild_shared": False,
            "leave_one_family_out": True,
        },
        "model_contract": {
            "version": V4_CRF_MODEL_VERSION,
            "states": list(V3_STRUCTURAL_STATES),
            "candidate_count": 1,
            "candidate_selection": "none_fixed_method",
            "l2_rho": CRF_L2_RHO,
            "class_adjustment_gamma": CLASS_ADJUSTMENT_GAMMA,
            "class_prior_smoothing": "family_weighted_jeffreys_alpha_0.5",
            "optimizer": _optimizer_contract(),
            "family_weighting": "inverse_total_clean_mild_family_tokens",
            "diagnostics": [
                "no_corpus_profile",
                "transition_zero",
                "logistic_emission",
                "self_inclusive_target_profile",
                "strict_single_family_profile",
            ],
        },
        "outer_development": {
            "outer_fold_count": V4_OUTER_FOLD_COUNT,
            "fold_assignment_parent": "exact_v3_five_outer_fold_assignments",
            "outer_folds": outer_reports,
            "out_of_fold_metrics": {
                "primary": {
                    "clean": oof["primary_clean"],
                    "mild": oof["primary_mild"],
                },
                "diagnostics": {
                    "no_corpus_profile": oof["no_corpus_profile"],
                    "transition_zero": oof["transition_zero"],
                    "logistic_emission": oof["logistic_emission"],
                    "self_inclusive_target_profile": oof["self_inclusive_target_profile"],
                    "strict_single_family_profile": oof["strict_single_family_profile"],
                },
            },
            "paired_v3": {
                "v3_mild_macro_f1": V3_MILD_MACRO_F1,
                "v3_mild_macro_f1_by_outer_fold": list(V3_MILD_MACRO_F1_BY_OUTER_FOLD),
                "v4_mild_macro_f1_by_outer_fold": v4_mild_by_outer_fold,
                "delta_by_outer_fold": delta_by_outer,
                "positive_delta_fold_count": positive_delta_fold_count,
            },
        },
        "gate_decision": gate_decision,
        "final_development_model": {
            "fitted": final_model is not None,
            "fit_rule": "fit_all_271_families_only_after_advance",
            "model_state_commitment": (
                None if final_model is None else final_model.model_state_commitment()
            ),
            "optimizer": (None if final_model is None else final_model.optimization_summary()),
        },
        "claim_scope": {
            "class": "development_only",
            "eligible_as_reserved_validation_result": False,
            "eligible_as_v2_holdout_result": False,
            "eligible_as_binding_confirmation": False,
            "eligible_as_decipherment": False,
            "individual_predictions_published": False,
        },
    }


def _prepare_outer_fold(
    bundle: MTAACTrainingBundle,
    fold: GroupedFold,
) -> dict[str, Any]:
    train_clean = _prepare_partition_variants(
        bundle.clean,
        fold.train_family_ids,
    )
    train_mild = _prepare_partition_variants(
        bundle.mild,
        fold.train_family_ids,
    )
    validation_clean_views = _prepare_partition_variants(
        bundle.clean,
        fold.validation_family_ids,
    )
    validation_mild_views = _prepare_partition_variants(
        bundle.mild,
        fold.validation_family_ids,
        include_self_inclusive=True,
    )
    validation_mild_strict = _prepare_strict_single_family(
        bundle.mild,
        fold.validation_family_ids,
    )
    return {
        "full_train_families": _labeled_families(
            train_clean["full"],
            train_mild["full"],
            fold.train_family_ids,
        ),
        "local_train_families": _labeled_families(
            train_clean["local"],
            train_mild["local"],
            fold.train_family_ids,
        ),
        "validation_clean": validation_clean_views["full"],
        "validation_mild": validation_mild_views["full"],
        "validation_mild_local": validation_mild_views["local"],
        "validation_mild_self_inclusive": validation_mild_views["self_inclusive"],
        "validation_mild_strict_single": validation_mild_strict,
        "profile_commitments": {
            "train_clean": train_clean["full"].profile_commitment,
            "train_mild": train_mild["full"].profile_commitment,
            "validation_clean": validation_clean_views["full"].profile_commitment,
            "validation_mild": validation_mild_views["full"].profile_commitment,
        },
    }


def _prepare_training_families(
    bundle: MTAACTrainingBundle,
    family_ids: Sequence[str],
) -> dict[str, Any]:
    clean = _prepare_partition_variants(
        bundle.clean,
        family_ids,
    )
    mild = _prepare_partition_variants(
        bundle.mild,
        family_ids,
    )
    return {
        "families": _labeled_families(
            clean["full"],
            mild["full"],
            family_ids,
        ),
        "clean_commitment": clean["full"].profile_commitment,
        "mild_commitment": mild["full"].profile_commitment,
    }


def _labeled_families(
    clean: _PreparedPartition,
    mild: _PreparedPartition,
    family_ids: Sequence[str],
) -> tuple[V4LabeledFeatureFamily, ...]:
    clean_by_family = {item.source.cluster_identifier: item for item in clean.documents}
    mild_by_family = {item.source.cluster_identifier: item for item in mild.documents}
    family_set = set(family_ids)
    if set(clean_by_family) != family_set or set(mild_by_family) != family_set:
        raise V4DevelopmentError("prepared training views do not cover the fold families")
    return tuple(
        V4LabeledFeatureFamily(
            documents=(
                _labeled_document(clean_by_family[family_id]),
                _labeled_document(mild_by_family[family_id]),
            )
        )
        for family_id in sorted(family_set)
    )


def _prepare_partition_variants(
    view: MTAACTrainingView,
    family_ids: Sequence[str],
    *,
    include_self_inclusive: bool = False,
) -> dict[str, _PreparedPartition]:
    selected = set(family_ids)
    source_documents = tuple(
        document for document in view.documents if document.cluster_identifier in selected
    )
    if {document.cluster_identifier for document in source_documents} != selected:
        raise V4DevelopmentError("partition family selection is incomplete")
    corpus = _observation_corpus(source_documents)
    profile = V4CorpusProfile.fit(corpus)
    full_corpus = profile.transform_corpus(
        corpus,
        ablation="full",
    )
    if len(full_corpus.documents) != len(source_documents):
        raise V4DevelopmentError("profile transform changed the document count")
    full = _PreparedPartition(
        documents=tuple(
            _PreparedDocument(source=source, features=features)
            for source, features in zip(
                source_documents,
                full_corpus.documents,
                strict=True,
            )
        ),
        profile_commitment=profile.corpus_commitment,
    )
    variants = {
        "full": full,
        "local": _localize_partition(full),
    }
    if include_self_inclusive:
        self_corpus = profile.transform_corpus(
            corpus,
            ablation="full",
            profile_mode="self_inclusive",
        )
        variants["self_inclusive"] = _PreparedPartition(
            documents=tuple(
                _PreparedDocument(source=source, features=features)
                for source, features in zip(
                    source_documents,
                    self_corpus.documents,
                    strict=True,
                )
            ),
            profile_commitment=profile.corpus_commitment,
        )
    return variants


def _localize_partition(partition: _PreparedPartition) -> _PreparedPartition:
    local_count = len(LOCAL_FEATURE_NAMES)
    return _PreparedPartition(
        documents=tuple(
            _PreparedDocument(
                source=item.source,
                features=V4FeatureDocument(
                    lines=tuple(
                        V4FeatureLine(rows=tuple(row[:local_count] for row in line.rows))
                        for line in item.features.lines
                    )
                ),
            )
            for item in partition.documents
        ),
        profile_commitment=partition.profile_commitment,
    )


def _prepare_strict_single_family(
    view: MTAACTrainingView,
    family_ids: Sequence[str],
) -> _PreparedPartition:
    selected = set(family_ids)
    source_documents = tuple(
        document for document in view.documents if document.cluster_identifier in selected
    )
    prepared: list[_PreparedDocument] = []
    commitments: list[str] = []
    for source in source_documents:
        corpus = _observation_corpus((source,))
        profile = V4CorpusProfile.fit(corpus)
        features = profile.transform_corpus(corpus, ablation="full")
        prepared.append(
            _PreparedDocument(
                source=source,
                features=features.documents[0],
            )
        )
        commitments.append(profile.corpus_commitment)
    if len(prepared) != len(selected):
        raise V4DevelopmentError("strict single-family preparation is incomplete")
    return _PreparedPartition(
        documents=tuple(prepared),
        profile_commitment=_combine_commitments(commitments),
    )


def _observation_corpus(
    documents: Sequence[MTAACTrainingDocument],
) -> V4ObservationCorpus:
    return V4ObservationCorpus(
        documents=tuple(
            V4ObservationDocument(lines=tuple(line.to_observation() for line in document.lines))
            for document in documents
        )
    )


def _labeled_document(prepared: _PreparedDocument) -> V4LabeledFeatureDocument:
    if len(prepared.source.lines) != len(prepared.features.lines):
        raise V4DevelopmentError("feature and truth line counts do not align")
    return V4LabeledFeatureDocument(
        lines=tuple(
            V4LabeledFeatureLine(
                feature_line=feature_line,
                states=tuple(token.state for token in source_line.tokens),
            )
            for source_line, feature_line in zip(
                prepared.source.lines,
                prepared.features.lines,
                strict=True,
            )
        )
    )


def _evaluate_model(
    model: V4LinearChainCRF | V4LogisticEmissionModel,
    partition: _PreparedPartition,
    *,
    transition_zero: bool = False,
) -> dict[str, Any]:
    rows: list[WeightedStatePrediction] = []
    for prepared in partition.documents:
        if len(prepared.source.lines) != len(prepared.features.lines):
            raise V4DevelopmentError("evaluation feature and truth lines do not align")
        token_count = sum(len(line.tokens) for line in prepared.source.lines)
        if token_count <= 0:
            raise V4DevelopmentError("evaluation family has no retained token")
        token_weight = 1.0 / token_count
        for source_line, feature_line in zip(
            prepared.source.lines,
            prepared.features.lines,
            strict=True,
        ):
            if transition_zero and isinstance(model, V4LinearChainCRF):
                predicted = model.decode(feature_line, transition_zero=True)
            elif transition_zero:
                raise V4DevelopmentError("transition-zero diagnostic requires the primary CRF")
            else:
                predicted = model.decode(feature_line)
            if len(predicted) != len(source_line.tokens):
                raise V4DevelopmentError("decoded sequence length does not match truth")
            rows.extend(
                WeightedStatePrediction(
                    truth=token.state,
                    predicted=predicted_state,
                    weight=token_weight,
                )
                for token, predicted_state in zip(
                    source_line.tokens,
                    predicted,
                    strict=True,
                )
            )
    return weighted_state_metrics(rows)


def _gate_decision(
    *,
    primary_clean: Mapping[str, Any],
    primary_mild: Mapping[str, Any],
    no_profile: Mapping[str, Any],
    self_inclusive: Mapping[str, Any],
    positive_delta_fold_count: int,
) -> dict[str, Any]:
    mild_macro = float(primary_mild["macro_f1"])
    clean_macro = float(primary_clean["macro_f1"])
    mild_per_state = cast(Mapping[str, Mapping[str, float]], primary_mild["per_state"])
    clean_per_state = cast(Mapping[str, Mapping[str, float]], primary_clean["per_state"])
    local_macro = float(no_profile["macro_f1"])
    self_inclusive_delta = float(self_inclusive["macro_f1"]) - mild_macro

    checks: dict[str, Any] = {
        "mild_macro_f1": _minimum_check(mild_macro, MILD_MACRO_F1_MINIMUM),
        "mild_settlement_name_recall": _minimum_check(
            mild_per_state["settlement_name"]["recall"],
            MILD_SETTLEMENT_RECALL_MINIMUM,
        ),
        "positive_paired_delta_outer_fold_count": _minimum_check(
            positive_delta_fold_count,
            PAIRED_POSITIVE_FOLD_MINIMUM,
        ),
        "profile_increment_mild_macro_f1": _minimum_check(
            mild_macro - local_macro,
            FULL_MINUS_LOCAL_MINIMUM,
        ),
        "mild_recall_floors": {
            state: _minimum_check(
                mild_per_state[state]["recall"],
                minimum,
            )
            for state, minimum in MILD_RECALL_FLOORS.items()
        },
        "clean_macro_f1": _minimum_check(clean_macro, CLEAN_MACRO_F1_MINIMUM),
        "clean_settlement_name_recall": _minimum_check(
            clean_per_state["settlement_name"]["recall"],
            CLEAN_SETTLEMENT_RECALL_MINIMUM,
        ),
        "self_inclusive_minus_lofo_mild_macro_f1": _maximum_check(
            self_inclusive_delta,
            SELF_INFORMATION_DELTA_MAXIMUM,
        ),
    }
    flat_passes = [
        checks["mild_macro_f1"]["passed"],
        checks["mild_settlement_name_recall"]["passed"],
        checks["positive_paired_delta_outer_fold_count"]["passed"],
        checks["profile_increment_mild_macro_f1"]["passed"],
        *(value["passed"] for value in checks["mild_recall_floors"].values()),
        checks["clean_macro_f1"]["passed"],
        checks["clean_settlement_name_recall"]["passed"],
        checks["self_inclusive_minus_lofo_mild_macro_f1"]["passed"],
    ]
    all_passed = all(flat_passes)
    return {
        "terminal_status": "advance" if all_passed else "development_killed",
        "all_passed": all_passed,
        "self_information_sensitive": not checks["self_inclusive_minus_lofo_mild_macro_f1"][
            "passed"
        ],
        "checks": checks,
    }


def _minimum_check(observed: float | int, minimum: float | int) -> dict[str, Any]:
    return {
        "observed": observed,
        "minimum": minimum,
        "passed": observed >= minimum,
    }


def _maximum_check(observed: float, maximum: float) -> dict[str, Any]:
    return {
        "observed": observed,
        "maximum": maximum,
        "passed": observed <= maximum,
    }


def _optimizer_contract() -> dict[str, Any]:
    return {
        "numeric_type": "float64",
        "batch": "full",
        "stable_logsumexp": "maximum_shift",
        "summation": "sorted_math_fsum",
        "history_size": LBFGS_HISTORY_SIZE,
        "maximum_accepted_iterations": LBFGS_MAX_ITERATIONS,
        "direction": "deterministic_lbfgs_two_loop_recursion",
        "non_descent_policy": (
            "clear_history_once_then_use_negative_gradient_repeat_is_hard_error"
        ),
        "curvature_pair_acceptance": (
            "s_dot_y_strictly_greater_than_1e-12_times_norm_s_times_norm_y"
        ),
        "armijo": {
            "initial_step": 1.0,
            "c1": LBFGS_ARMIJO_C1,
            "contraction_factor": LBFGS_BACKTRACK_FACTOR,
            "maximum_trials": LBFGS_MAX_LINE_SEARCH_TRIALS,
            "minimum_step": LBFGS_MIN_STEP,
        },
        "convergence": {
            "gradient_infinity_norm": LBFGS_GRADIENT_TOLERANCE,
            "relative_objective": LBFGS_RELATIVE_OBJECTIVE_TOLERANCE,
            "consecutive_relative_objective_iterations": LBFGS_STABLE_ITERATIONS,
            "secondary_gradient_infinity_norm": LBFGS_STALLED_GRADIENT_TOLERANCE,
        },
        "fallback": False,
    }


def _validate_bundle_commitments(bundle: MTAACTrainingBundle) -> None:
    if not isinstance(bundle, MTAACTrainingBundle):
        raise V4DevelopmentError("runner requires the typed MTAAC training bundle")
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
        raise V4DevelopmentError("training bundle does not match the fixed V2 parent boundary")


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
        raise V4DevelopmentError("metric report lacks its aggregate confusion matrix")
    return cast(
        Mapping[V3StructuralState, Mapping[V3StructuralState, float]],
        value,
    )


def _combine_commitments(values: Sequence[str]) -> str:
    import hashlib

    digest = hashlib.sha256(b"indusbench:v4:combined-profile-commitment:v1\x00")
    for value in values:
        encoded = value.encode("ascii")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return f"sha256:{digest.hexdigest()}"


__all__ = [
    "CLEAN_MACRO_F1_MINIMUM",
    "CLEAN_SETTLEMENT_RECALL_MINIMUM",
    "FULL_MINUS_LOCAL_MINIMUM",
    "MILD_MACRO_F1_MINIMUM",
    "MILD_RECALL_FLOORS",
    "MILD_SETTLEMENT_RECALL_MINIMUM",
    "PAIRED_POSITIVE_FOLD_MINIMUM",
    "SELF_INFORMATION_DELTA_MAXIMUM",
    "V3_MILD_MACRO_F1",
    "V3_MILD_MACRO_F1_BY_OUTER_FOLD",
    "V4_DEVELOPMENT_REPORT_VERSION",
    "V4DevelopmentError",
    "run_v4_development",
]
