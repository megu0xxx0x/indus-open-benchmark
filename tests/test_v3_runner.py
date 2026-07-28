from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.v3dev.runner as runner
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
    MTAACTrainingLine,
    MTAACTrainingRegime,
    MTAACTrainingToken,
    MTAACTrainingView,
    V3StructuralState,
)
from indusbench.v3dev.folds import build_nested_grouped_folds
from indusbench.v3dev.mtaac_training import (
    MTAAC_V2_FREEZE_COMMIT,
    MTAAC_V2_HOLDOUT_FAMILY_COUNT,
    MTAAC_V2_SPLIT_MANIFEST_SHA256,
    MTAAC_V2_SPLIT_SEED,
    MTAAC_V2_TEST_FRACTION,
)
from indusbench.v3dev.sequence import V3SequenceModel
from indusbench.v3dev_cli import validate_public_development_report

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PLAN_BYTES = (_PROJECT_ROOT / "benchmark" / "mtaac-v3-development-v1.json").read_bytes()
_IMPLEMENTATION_COMMIT = "c" * 40
_SYNTHETIC_FAMILY_COUNT = 25


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _document_key(family_index: int) -> str:
    return f"mtaac-document-source-id-sha256-v1:{_hex(f'document:{family_index}')}"


def _cluster_identifier(family_index: int) -> str:
    return _hex(f"cluster:{family_index}")


def _token_key(family_index: int, token_index: int) -> str:
    return f"mtaac-token-source-order-sha256-v1:{_hex(f'token:{family_index}:{token_index}')}"


def _form_id(family_index: int, state: V3StructuralState) -> str:
    return f"mtaac-word-form-sha256-v1:{_hex(f'form:{family_index}:{state}')}"


def _document(
    family_index: int,
    regime: MTAACTrainingRegime,
    *,
    state_repetitions: int = 1,
) -> MTAACTrainingDocument:
    states = cast(
        tuple[V3StructuralState, ...],
        tuple(state for _ in range(state_repetitions) for state in V3_STRUCTURAL_STATES),
    )
    tokens: list[MTAACTrainingToken] = []
    for token_index, state in enumerate(states):
        damaged = regime == "mild" and (family_index + token_index) % 7 == 0
        tokens.append(
            MTAACTrainingToken(
                token_key=_token_key(family_index, token_index),
                observed_form_id=None if damaged else _form_id(family_index, state),
                state=state,
                damaged=damaged,
            )
        )
    return MTAACTrainingDocument(
        document_key=_document_key(family_index),
        cluster_identifier=_cluster_identifier(family_index),
        regime=regime,
        replica_index=0,
        lines=(
            MTAACTrainingLine(
                line_ordinal=0,
                reported_direction=(
                    "known_source_order" if family_index % 2 == 0 else "unknown_visual_order"
                ),
                tokens=tuple(tokens),
            ),
        ),
    )


def _view(
    regime: MTAACTrainingRegime,
    state_repetitions: tuple[int, ...],
) -> MTAACTrainingView:
    documents = tuple(
        sorted(
            (
                _document(
                    family_index,
                    regime,
                    state_repetitions=repetitions,
                )
                for family_index, repetitions in enumerate(state_repetitions)
            ),
            key=lambda document: document.document_key,
        )
    )
    return MTAACTrainingView(regime=regime, documents=documents)


def _bundle(family_count: int = _SYNTHETIC_FAMILY_COUNT) -> MTAACTrainingBundle:
    repetitions = (1,) * family_count
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
        training_family_count=family_count,
        excluded_holdout_family_count=MTAAC_V2_HOLDOUT_FAMILY_COUNT,
        states=V3_STRUCTURAL_STATES,
        clean=_view("clean", repetitions),
        mild=_view("mild", repetitions),
    )


def _run_synthetic(bundle: MTAACTrainingBundle) -> dict[str, Any]:
    # The production boundary remains 271 families.  Only this project-authored
    # test fixture substitutes its smaller count so nested execution stays fast.
    with patch.object(
        runner,
        "MTAAC_V2_TRAINING_FAMILY_COUNT",
        bundle.training_family_count,
    ):
        return runner.run_v3_development(
            bundle,
            plan_bytes=_PLAN_BYTES,
            implementation_commit=_IMPLEMENTATION_COMMIT,
        )


def _mapping_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key
            for nested_value in value.values()
            for nested_key in _mapping_keys(nested_value)
        }
    if isinstance(value, list):
        return {nested_key for nested_value in value for nested_key in _mapping_keys(nested_value)}
    return set()


class _AlwaysContextModel:
    def decode(
        self,
        line: Any,
        *,
        transition_strength: float,
    ) -> tuple[V3StructuralState, ...]:
        del transition_strength
        return ("context_only",) * len(line.tokens)


class V3RunnerBoundaryTests(unittest.TestCase):
    bundle: MTAACTrainingBundle
    report: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = _bundle()
        cls.report = _run_synthetic(cls.bundle)

    def test_revalidates_exact_plan_bytes_and_implementation_commit(self) -> None:
        with (
            patch.object(
                runner,
                "MTAAC_V2_TRAINING_FAMILY_COUNT",
                self.bundle.training_family_count,
            ),
            patch.object(
                runner,
                "validate_v3_development_plan",
                wraps=runner.validate_v3_development_plan,
            ) as validator,
            self.assertRaisesRegex(runner.V3DevelopmentError, "lowercase 40-hex"),
        ):
            runner.run_v3_development(
                self.bundle,
                plan_bytes=_PLAN_BYTES,
                implementation_commit="C" * 40,
            )
        validator.assert_called_once_with(_PLAN_BYTES)

        with (
            patch.object(
                runner,
                "MTAAC_V2_TRAINING_FAMILY_COUNT",
                self.bundle.training_family_count,
            ),
            self.assertRaisesRegex(ValueError, "SHA-256"),
        ):
            runner.run_v3_development(
                self.bundle,
                plan_bytes=_PLAN_BYTES + b" ",
                implementation_commit=_IMPLEMENTATION_COMMIT,
            )

    def test_production_parent_boundary_rejects_substituted_family_count(self) -> None:
        with self.assertRaisesRegex(
            runner.V3DevelopmentError,
            "fixed V2 parent boundary",
        ):
            runner.run_v3_development(
                self.bundle,
                plan_bytes=_PLAN_BYTES,
                implementation_commit=_IMPLEMENTATION_COMMIT,
            )

    def test_candidate_grid_and_five_state_task_are_closed(self) -> None:
        expected_pairs = [
            (gamma, transition_strength)
            for gamma in (0.0, 0.5, 1.0)
            for transition_strength in (0.0, 0.5, 1.0)
        ]
        model_contract = self.report["model_contract"]
        candidate_grid = model_contract["candidate_grid"]

        self.assertEqual(list(V3_STRUCTURAL_STATES), model_contract["states"])
        self.assertEqual(9, len(candidate_grid))
        self.assertEqual(
            expected_pairs,
            [
                (candidate["gamma"], candidate["transition_strength"])
                for candidate in candidate_grid
            ],
        )
        self.assertEqual(
            list(range(9)),
            [candidate["complexity_rank"] for candidate in candidate_grid],
        )
        self.assertEqual(
            [candidate.candidate_id for candidate in runner.V3_CANDIDATES],
            [candidate["candidate_id"] for candidate in candidate_grid],
        )

    def test_nested_report_is_aggregate_family_weighted_and_mild_selected(self) -> None:
        nested = self.report["nested_development"]
        outer_folds = nested["outer_folds"]
        self.assertEqual(5, nested["outer_fold_count"])
        self.assertEqual(4, nested["inner_fold_count"])
        self.assertEqual(5, len(outer_folds))

        for index, outer in enumerate(outer_folds):
            support = outer["support"]
            validation_count = support["validation_family_count"]
            self.assertEqual(index, outer["outer_fold_index"])
            self.assertEqual(
                _SYNTHETIC_FAMILY_COUNT,
                support["train_family_count"] + validation_count,
            )
            for state in V3_STRUCTURAL_STATES:
                self.assertEqual(
                    _SYNTHETIC_FAMILY_COUNT,
                    support["train_state_support"][state]
                    + support["validation_state_support"][state],
                )

            selection = outer["inner_selection"]
            self.assertEqual(
                "family_weighted_mild_macro_f1",
                selection["selection_metric"],
            )
            self.assertEqual(9, len(selection["candidates"]))
            for candidate in selection["candidates"]:
                self.assertEqual(4, candidate["fold_count"])
                self.assertEqual(4, len(candidate["mild_macro_f1_by_fold"]))

            diagnostics = outer["diagnostics"]
            self.assertEqual(
                "diagnostic_not_used_for_selection",
                diagnostics["clean_role"],
            )
            self.assertEqual(
                "outer_development_estimate",
                diagnostics["mild_role"],
            )
            self.assertAlmostEqual(
                float(validation_count),
                diagnostics["clean"]["total_family_mass"],
            )
            self.assertAlmostEqual(
                float(validation_count),
                diagnostics["mild"]["total_family_mass"],
            )

        for regime in ("clean", "mild"):
            self.assertAlmostEqual(
                float(_SYNTHETIC_FAMILY_COUNT),
                nested["out_of_fold_metrics"][regime]["total_family_mass"],
            )
        final = self.report["final_development_model"]
        self.assertEqual(4, final["selection_fold_count"])
        self.assertEqual("family_weighted_mild_macro_f1", final["selection_metric"])
        self.assertEqual(9, len(final["candidates"]))
        self.assertRegex(final["model_state_commitment"], r"^sha256:[0-9a-f]{64}$")

    def test_candidate_scoring_uses_only_mild_family_disjoint_partitions(self) -> None:
        nested = build_nested_grouped_folds(runner._family_support(self.bundle.clean))
        inner_folds = nested.outer_folds[0].inner_folds
        fit_calls: list[tuple[frozenset[str], float]] = []
        evaluation_calls: list[frozenset[str]] = []

        class SelectionModel:
            def __init__(self, family_ids: tuple[str, ...], gamma: float) -> None:
                self.family_ids = frozenset(family_ids)
                self.gamma = gamma

        def fake_fit(
            supplied_bundle: MTAACTrainingBundle,
            family_ids: tuple[str, ...],
            *,
            gamma: float,
        ) -> Any:
            self.assertIs(self.bundle, supplied_bundle)
            model = SelectionModel(family_ids, gamma)
            fit_calls.append((model.family_ids, gamma))
            return model

        def fake_evaluate(
            model: SelectionModel,
            view: MTAACTrainingView,
            family_ids: tuple[str, ...],
            *,
            transition_strength: float,
        ) -> dict[str, Any]:
            self.assertIs(self.bundle.mild, view)
            validation_ids = frozenset(family_ids)
            self.assertTrue(model.family_ids.isdisjoint(validation_ids))
            self.assertIn(transition_strength, {0.0, 0.5, 1.0})
            evaluation_calls.append(validation_ids)
            return {"macro_f1": 0.5}

        with (
            patch.object(runner, "_fit_model", side_effect=fake_fit),
            patch.object(runner, "_evaluate_view", side_effect=fake_evaluate),
        ):
            scores = runner._score_candidates(self.bundle, inner_folds)

        self.assertEqual(12, len(fit_calls))
        self.assertEqual(36, len(evaluation_calls))
        self.assertEqual(9, len(scores))
        self.assertTrue(all(len(score.fold_scores) == 4 for score in scores))
        self.assertEqual({0.0, 0.5, 1.0}, {gamma for _, gamma in fit_calls})

    def test_evaluation_assigns_equal_total_mass_to_unequal_families(self) -> None:
        view = _view("clean", (1, 3))
        family_ids = tuple(document.cluster_identifier for document in view.documents)

        metrics = runner._evaluate_view(
            cast(V3SequenceModel, _AlwaysContextModel()),
            view,
            family_ids,
            transition_strength=0.0,
        )

        self.assertAlmostEqual(2.0, metrics["total_family_mass"])
        confusion = metrics["weighted_confusion_matrix"]
        for state in V3_STRUCTURAL_STATES:
            self.assertAlmostEqual(0.4, confusion[state]["context_only"])
            self.assertAlmostEqual(
                0.0,
                sum(
                    confusion[state][predicted]
                    for predicted in V3_STRUCTURAL_STATES
                    if predicted != "context_only"
                ),
            )

    def test_report_is_aggregate_only_and_excludes_both_reserved_sources(self) -> None:
        report = self.report
        production_boundary_report = {
            **report,
            "data_boundary": {
                **report["data_boundary"],
                "model_training_family_count": 271,
            },
        }
        self.assertIs(
            production_boundary_report,
            validate_public_development_report(production_boundary_report),
        )
        self.assertTrue(report["development_only"])
        self.assertEqual("development_complete", report["terminal_status"])
        self.assertTrue(report["model_executed"])
        self.assertTrue(report["scientific_metrics_emitted"])
        self.assertFalse(report["data_boundary"]["v2_holdout_exposed_to_model"])
        self.assertFalse(report["data_boundary"]["v2_holdout_scored"])
        self.assertFalse(report["data_boundary"]["reserved_validation_source_loaded"])
        self.assertFalse(report["claim_scope"]["eligible_as_reserved_validation_result"])
        self.assertFalse(report["claim_scope"]["eligible_as_v2_holdout_result"])
        self.assertFalse(report["claim_scope"]["individual_predictions_published"])

        keys = _mapping_keys(report)
        forbidden_keys = {
            "document_id",
            "document_key",
            "family_id",
            "family_ids",
            "fold_membership",
            "form",
            "local_path",
            "member_path",
            "p_id",
            "pid",
            "raw_annotation",
            "segm",
            "source_identifier",
            "token_id",
            "token_key",
            "xpostag",
        }
        self.assertTrue(forbidden_keys.isdisjoint(keys))

        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("oracc", rendered.casefold())
        self.assertNotIn("mtaac-document-source-id", rendered)
        self.assertNotIn("mtaac-token-source-order", rendered)
        self.assertNotIn("mtaac-word-form", rendered)
        for document in (*self.bundle.clean.documents, *self.bundle.mild.documents):
            self.assertNotIn(document.document_key, rendered)
            self.assertNotIn(document.cluster_identifier, rendered)
            for line in document.lines:
                for token in line.tokens:
                    self.assertNotIn(token.token_key, rendered)
                    if token.observed_form_id is not None:
                        self.assertNotIn(token.observed_form_id, rendered)

        bundle_fields = set(MTAACTrainingBundle.__dataclass_fields__)
        self.assertTrue({"corpus", "gold", "holdout", "split"}.isdisjoint(bundle_fields))
        source = Path(cast(str, runner.__file__)).read_text(encoding="utf-8")
        imported_modules = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        self.assertFalse(any(module.startswith("indusbench.oracc") for module in imported_modules))

    def test_execution_is_byte_for_byte_deterministic(self) -> None:
        repeated = _run_synthetic(self.bundle)
        self.assertEqual(self.report, repeated)
        self.assertEqual(
            json.dumps(self.report, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(repeated, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )


if __name__ == "__main__":
    unittest.main()
