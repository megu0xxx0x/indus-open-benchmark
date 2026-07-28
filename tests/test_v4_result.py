from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path
from typing import Any

from indusbench.schema_validation import validate_schema_instance
from indusbench.v4dev.plan import V4_DEVELOPMENT_PLAN_SHA256
from indusbench.v4dev_cli import validate_public_development_report

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmark/results/mtaac-v4-development-v1.json"
SCHEMA = ROOT / "schemas/mtaac-v4-development-report.schema.json"
RESULT_SHA256 = "4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897"
IMPLEMENTATION_COMMIT = "304f8b36a32083330b8af02d21a58382c29d8915"


class MTAACV4PublishedDevelopmentResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = RESULT.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != RESULT_SHA256:
            raise AssertionError("published MTAAC V4 development result bytes changed")
        cls.report: dict[str, Any] = json.loads(cls.raw)

    def test_result_matches_schema_plan_and_runtime_public_boundary(self) -> None:
        self.assertEqual([], validate_schema_instance(self.report, SCHEMA))
        self.assertIs(
            self.report,
            validate_public_development_report(
                self.report,
                expected_implementation_commit=IMPLEMENTATION_COMMIT,
            ),
        )
        self.assertEqual(V4_DEVELOPMENT_PLAN_SHA256, self.report["plan_sha256"])
        self.assertEqual(IMPLEMENTATION_COMMIT, self.report["implementation_commit"])
        self.assertTrue(self.report["development_only"])
        self.assertFalse(self.report["data_boundary"]["v2_holdout_exposed_to_model"])
        self.assertFalse(self.report["data_boundary"]["v2_holdout_scored"])
        self.assertFalse(self.report["data_boundary"]["reserved_validation_source_loaded"])

    def test_terminal_decision_and_primary_metrics_are_exact(self) -> None:
        self.assertEqual("development_killed", self.report["terminal_status"])
        decision = self.report["gate_decision"]
        self.assertFalse(decision["all_passed"])
        self.assertFalse(decision["self_information_sensitive"])

        primary = self.report["outer_development"]["out_of_fold_metrics"]["primary"]
        self.assertAlmostEqual(0.4780972874281771, primary["clean"]["macro_f1"])
        self.assertAlmostEqual(0.3877588813953674, primary["mild"]["macro_f1"])
        self.assertAlmostEqual(
            0.042941913609110954,
            primary["mild"]["per_state"]["settlement_name"]["recall"],
        )
        self.assertAlmostEqual(
            0.30521567409297784,
            primary["mild"]["per_state"]["unit"]["recall"],
        )

        final_model = self.report["final_development_model"]
        self.assertFalse(final_model["fitted"])
        self.assertIsNone(final_model["model_state_commitment"])
        self.assertIsNone(final_model["optimizer"])

    def test_paired_comparison_diagnostics_and_gates_are_preserved(self) -> None:
        outer = self.report["outer_development"]
        paired = outer["paired_v3"]
        self.assertEqual(5, paired["positive_delta_fold_count"])
        self.assertTrue(all(delta > 0.0 for delta in paired["delta_by_outer_fold"]))

        diagnostics = outer["out_of_fold_metrics"]["diagnostics"]
        expected_macro_f1 = {
            "logistic_emission": 0.35693883963428447,
            "no_corpus_profile": 0.3269776696636399,
            "self_inclusive_target_profile": 0.3944211657294819,
            "strict_single_family_profile": 0.25619767750439115,
            "transition_zero": 0.3443050588317761,
        }
        for name, expected in expected_macro_f1.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(expected, diagnostics[name]["macro_f1"])

        checks = self.report["gate_decision"]["checks"]
        failed = {
            "mild_settlement_name_recall",
            "mild_recall_floors.unit",
        }
        observed_failed: set[str] = set()
        for name, check in checks.items():
            if name == "mild_recall_floors":
                observed_failed.update(
                    f"{name}.{state}"
                    for state, state_check in check.items()
                    if not state_check["passed"]
                )
            elif not check["passed"]:
                observed_failed.add(name)
        self.assertEqual(failed, observed_failed)

    def test_result_contains_no_item_identity_private_path_or_reserved_result(self) -> None:
        text = self.raw.decode("utf-8")
        forbidden_patterns = (
            r"\bP[0-9]{6}\b",
            r"(?<![0-9])(?:[0-9]{1,3}[.]){3}[0-9]{1,3}(?![0-9])",
            r"/(?:home|Users|private/tmp|tmp)/",
            r"\bssh://",
            r"\b(?:FORM|SEGM|XPOSTAG)\b",
            r"\boracc\b",
            r'"(?:host|account|username)"\s*:',
            r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY",
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}",
        )
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
