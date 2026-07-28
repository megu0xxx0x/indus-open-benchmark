from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from indusbench.schema_validation import validate_schema_instance
from indusbench.v3dev.contracts import V3StructuralState
from indusbench.v3dev.folds import CandidateScore, select_one_standard_error
from indusbench.v3dev.metrics import (
    add_confusion_matrices,
    metrics_from_confusion,
)
from indusbench.v3dev.plan import V3_DEVELOPMENT_PLAN_SHA256
from indusbench.v3dev_cli import validate_public_development_report

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmark/results/mtaac-v3-development-v1.json"
SCHEMA = ROOT / "schemas/mtaac-v3-development-report.schema.json"
RESULT_SHA256 = "e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2"
IMPLEMENTATION_COMMIT = "5b39c8ba358ea66e46183cbf02eb07fbc91861e2"


def _candidate_scores(rows: list[dict[str, Any]]) -> tuple[CandidateScore, ...]:
    return tuple(
        CandidateScore(
            candidate_id=row["candidate_id"],
            complexity_rank=row["complexity_rank"],
            fold_scores=tuple(row["mild_macro_f1_by_fold"]),
        )
        for row in rows
    )


class MTAACV3PublishedDevelopmentResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = RESULT.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != RESULT_SHA256:
            raise AssertionError("published MTAAC V3 development result bytes changed")
        cls.report: dict[str, Any] = json.loads(cls.raw)

    def test_result_matches_schema_plan_and_public_boundary(self) -> None:
        self.assertEqual([], validate_schema_instance(self.report, SCHEMA))
        self.assertIs(
            self.report,
            validate_public_development_report(
                self.report,
                expected_implementation_commit=IMPLEMENTATION_COMMIT,
            ),
        )
        self.assertEqual(V3_DEVELOPMENT_PLAN_SHA256, self.report["plan_sha256"])
        self.assertEqual(IMPLEMENTATION_COMMIT, self.report["implementation_commit"])
        self.assertTrue(self.report["development_only"])
        self.assertFalse(self.report["data_boundary"]["v2_holdout_exposed_to_model"])
        self.assertFalse(self.report["data_boundary"]["v2_holdout_scored"])
        self.assertFalse(self.report["data_boundary"]["reserved_validation_source_loaded"])

    def test_one_standard_error_selection_recomputes_for_every_fold(self) -> None:
        outer = self.report["nested_development"]["outer_folds"]
        for fold in outer:
            selection = fold["inner_selection"]
            recomputed = select_one_standard_error(_candidate_scores(selection["candidates"]))
            self.assertEqual(
                recomputed.candidate_id,
                selection["selected_candidate"]["candidate_id"],
            )

        final = self.report["final_development_model"]
        recomputed = select_one_standard_error(_candidate_scores(final["candidates"]))
        self.assertEqual(recomputed.candidate_id, final["selected_candidate"]["candidate_id"])
        self.assertEqual("gamma-0.5__lambda-0", recomputed.candidate_id)
        self.assertEqual(
            {"gamma-0.5__lambda-0"},
            {fold["inner_selection"]["selected_candidate"]["candidate_id"] for fold in outer},
        )

    def test_out_of_fold_metrics_recompute_from_outer_confusions(self) -> None:
        nested = self.report["nested_development"]
        for regime in ("clean", "mild"):
            matrices = [
                cast(
                    Mapping[
                        V3StructuralState,
                        Mapping[V3StructuralState, float],
                    ],
                    fold["diagnostics"][regime]["weighted_confusion_matrix"],
                )
                for fold in nested["outer_folds"]
            ]
            recomputed = metrics_from_confusion(add_confusion_matrices(matrices))
            self.assertEqual(recomputed, nested["out_of_fold_metrics"][regime])
            self.assertEqual(271.0, recomputed["total_family_mass"])

        mild = nested["out_of_fold_metrics"]["mild"]
        self.assertAlmostEqual(0.32432759235715436, mild["macro_f1"])
        self.assertAlmostEqual(0.03694018545983599, mild["worst_state_recall"])
        self.assertAlmostEqual(
            0.03694018545983599,
            mild["per_state"]["settlement_name"]["recall"],
        )

    def test_result_contains_no_item_identity_private_path_or_reserved_result(self) -> None:
        text = self.raw.decode("utf-8")
        forbidden_patterns = (
            r"\bP[0-9]{6}\b",
            r"(?<![0-9])(?:[0-9]{1,3}[.]){3}[0-9]{1,3}(?![0-9])",
            r"/(?:home|Users|private/tmp)/",
            r"\bssh://",
            r"\b(?:FORM|SEGM|XPOSTAG)\b",
            r"\boracc\b",
            r"\b(?:go|no_go|confirmation|decipherment)\b",
            r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY",
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}",
        )
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
