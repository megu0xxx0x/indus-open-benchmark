from __future__ import annotations

import hashlib
import json
import math
import re
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "benchmark/results/mtaac-known-script-control-v2.json"
PROTOCOL_PATH = ROOT / "benchmark/mtaac-known-script-control-v2.json"
RESULT_SHA256 = "6bc4ed610862d109b596bdd934f36fd19b99e3cbfcced42882546d0c852a7afe"
PROTOCOL_SHA256 = "sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
FREEZE_COMMIT = "37157f1411a55ffd91b7327afaca8fc1080fa708"
CLASSES = ("person_name", "quantity", "settlement_name", "unit")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    height = (len(ordered) - 1) * 0.95
    lower = math.floor(height)
    upper = math.ceil(height)
    fraction = height - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


class MTAACV2PublishedResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        raw = RESULT_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != RESULT_SHA256:
            raise AssertionError("published MTAAC V2 result bytes changed")
        cls.report = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
        protocol_raw = PROTOCOL_PATH.read_bytes()
        if f"sha256:{hashlib.sha256(protocol_raw).hexdigest()}" != PROTOCOL_SHA256:
            raise AssertionError("published MTAAC V2 protocol bytes changed")
        cls.protocol = json.loads(
            protocol_raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )

    def _assert_close(self, actual: float, expected: float, label: str) -> None:
        self.assertTrue(
            math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15),
            f"{label}: {actual!r} != {expected!r}",
        )

    def _assert_metrics_recompute(
        self,
        label: str,
        metrics: dict[str, Any],
    ) -> None:
        matrix = metrics["weighted_confusion_matrix"]
        self.assertEqual(tuple(matrix), CLASSES, label)
        self.assertTrue(
            all(tuple(matrix[truth]) == CLASSES for truth in CLASSES),
            label,
        )

        truth_mass = {
            truth: math.fsum(matrix[truth][predicted] for predicted in CLASSES) for truth in CLASSES
        }
        predicted_mass = {
            predicted: math.fsum(matrix[truth][predicted] for truth in CLASSES)
            for predicted in CLASSES
        }
        total_mass = math.fsum(truth_mass.values())
        recalls: list[float] = []
        f1_values: list[float] = []
        for class_name in CLASSES:
            true_positive = matrix[class_name][class_name]
            precision = (
                true_positive / predicted_mass[class_name]
                if predicted_mass[class_name] > 0.0
                else 0.0
            )
            recall = true_positive / truth_mass[class_name] if truth_mass[class_name] > 0.0 else 0.0
            f1 = (
                2.0 * precision * recall / (precision + recall) if precision + recall > 0.0 else 0.0
            )
            reported = metrics["per_class"][class_name]
            self._assert_close(
                reported["truth_mass"],
                truth_mass[class_name],
                f"{label}.{class_name}.truth_mass",
            )
            self._assert_close(
                reported["precision"],
                precision,
                f"{label}.{class_name}.precision",
            )
            self._assert_close(
                reported["recall"],
                recall,
                f"{label}.{class_name}.recall",
            )
            self._assert_close(
                reported["f1"],
                f1,
                f"{label}.{class_name}.f1",
            )
            recalls.append(recall)
            f1_values.append(f1)

        self._assert_close(
            metrics["weighted_accuracy"],
            math.fsum(matrix[class_name][class_name] for class_name in CLASSES) / total_mass,
            f"{label}.weighted_accuracy",
        )
        self._assert_close(
            metrics["weighted_balanced_accuracy"],
            math.fsum(recalls) / len(CLASSES),
            f"{label}.weighted_balanced_accuracy",
        )
        self._assert_close(
            metrics["macro_f1"],
            math.fsum(f1_values) / len(CLASSES),
            f"{label}.macro_f1",
        )

    def test_exact_commitments_and_terminal_decision(self) -> None:
        report = self.report
        protocol = self.protocol
        self.assertEqual(report["protocol_version"], "mtaac-real-control-v2")
        self.assertEqual(report["protocol_sha256"], PROTOCOL_SHA256)
        self.assertEqual(
            protocol["implementation"]["protocol_version"],
            report["protocol_version"],
        )
        self.assertEqual(
            protocol["lineage"]["superseded_protocol_sha256"],
            "sha256:25fbea943a662144700dfca418927758ad3319817bc42191c4c8e6e45fc518b3",
        )
        self.assertEqual(
            protocol["lineage"]["superseded_freeze_commit"],
            "57db0949f6542429d2f05b1bf935ee586bdf3699",
        )
        self.assertEqual(
            report["attestation"]["pre_result_code_commit"],
            FREEZE_COMMIT,
        )
        source = protocol["source"]
        self.assertEqual(
            report["source_commitments"],
            {
                "adapter_target_commit": source["commit"],
                "evaluation_corpus_sha256": source["expected_evaluation_corpus_sha256"],
                "input_sha256": source["archive_sha256"],
                "license_id": source["license_id"],
                "selected_manifest_sha256": source["expected_selected_manifest_sha256"],
            },
        )
        self.assertEqual(
            report["numeric_runtime"],
            {
                "cross_runtime_byte_identity_claimed": False,
                "float_mantissa_bits": 53,
                "libc": "glibc-2.39",
                "platform_machine": "x86_64",
                "platform_system": "Linux",
                "python_implementation": "cpython",
                "python_version": "3.12.3",
            },
        )
        self.assertEqual(
            report["null_run_contract"],
            {
                "fixture_override": False,
                "normative_real_run_count": 999,
                "runs": 999,
                "seed_start": 0,
            },
        )

        expected_thresholds = {
            "clean": {
                key.replace("F1", "f1"): value
                for key, value in protocol["decision"]["clean_requirements"].items()
            },
            "mild": {
                key.replace("F1", "f1"): value
                for key, value in protocol["decision"]["mild_requirements"].items()
                if key != "all_integrity_and_leakage_checks"
            },
        }
        decision = report["decision"]
        self.assertEqual(decision["thresholds"], expected_thresholds)
        support = report["support"]
        mild_thresholds = expected_thresholds["mild"]
        expected_support = {
            "clean_coverage_defined": all(
                math.isfinite(value)
                for value in support["family_mean_readable_coverage"]["clean"].values()
            ),
            "clean_positive_four_class_truth": all(
                report["regimes"]["clean"]["observed"]["per_class"][class_name]["truth_mass"] > 0.0
                for class_name in CLASSES
            ),
            "mild_coverage_defined": all(
                math.isfinite(value)
                for value in support["family_mean_readable_coverage"]["mild"].values()
            ),
            "mild_positive_four_class_truth": all(
                report["regimes"]["mild"]["observed"]["per_class"][class_name]["truth_mass"] > 0.0
                for class_name in CLASSES
            ),
            "mild_test_effective_families": all(
                value >= mild_thresholds["minimum_test_effective_families_per_class"]
                for value in support["effective_source_document_families"][
                    "mild_test_primary"
                ].values()
            ),
            "mild_train_effective_families": all(
                value >= mild_thresholds["minimum_train_effective_families_per_class"]
                for value in support["effective_source_document_families"]["mild_train"].values()
            ),
        }
        self.assertEqual(support["criteria"], expected_support)

        clean = report["regimes"]["clean"]
        mild = report["regimes"]["mild"]
        clean_thresholds = expected_thresholds["clean"]
        expected_clean_criteria = {
            "minimum_macro_f1": clean["observed"]["macro_f1"]
            >= clean_thresholds["minimum_macro_f1"],
            "minimum_observed_minus_decision_reference": clean["observed_minus_decision_reference"]
            >= clean_thresholds["minimum_observed_minus_decision_reference"],
            "minimum_per_class_family_mean_readable_coverage": min(
                support["family_mean_readable_coverage"]["clean"].values()
            )
            >= clean_thresholds["minimum_per_class_family_mean_readable_coverage"],
            "minimum_per_class_recall": min(
                value["recall"] for value in clean["observed"]["per_class"].values()
            )
            >= clean_thresholds["minimum_per_class_recall"],
        }
        all_integrity = all(report["integrity_and_leakage"].values()) and all(
            all(report["regimes"][regime]["permutation_null"]["integrity"].values())
            for regime in ("clean", "mild")
        )
        expected_mild_criteria = {
            "all_integrity_and_leakage_checks": all_integrity,
            "decision_bearing_support": all(expected_support.values()),
            "maximum_add_one_permutation_p": mild["permutation_null"][
                "add_one_empirical_p_greater_or_equal"
            ]
            <= mild_thresholds["maximum_add_one_permutation_p"],
            "minimum_macro_f1": mild["observed"]["macro_f1"] >= mild_thresholds["minimum_macro_f1"],
            "minimum_movable_family_weight_fraction": mild["permutation_null"][
                "movable_family_weight_fraction"
            ]
            >= mild_thresholds["minimum_movable_family_weight_fraction"],
            "minimum_observed_minus_decision_reference": mild["observed_minus_decision_reference"]
            >= mild_thresholds["minimum_observed_minus_decision_reference"],
            "minimum_per_class_family_mean_readable_coverage": min(
                support["family_mean_readable_coverage"]["mild"].values()
            )
            >= mild_thresholds["minimum_per_class_family_mean_readable_coverage"],
            "minimum_per_class_recall": min(
                value["recall"] for value in mild["observed"]["per_class"].values()
            )
            >= mild_thresholds["minimum_per_class_recall"],
        }
        self.assertEqual(decision["clean_criteria"], expected_clean_criteria)
        self.assertEqual(decision["mild_criteria"], expected_mild_criteria)
        expected_all = all(expected_clean_criteria.values()) and all(
            expected_mild_criteria.values()
        )
        self.assertEqual(decision["all_thresholds_passed"], expected_all)
        self.assertEqual(report["terminal_status"], "go" if expected_all else "no_go")

        failed = [
            (regime, criterion)
            for regime in ("clean", "mild")
            for criterion, passed in decision[f"{regime}_criteria"].items()
            if not passed
        ]
        self.assertEqual(failed, [("mild", "minimum_per_class_recall")])
        self.assertLess(
            report["regimes"]["mild"]["observed"]["per_class"]["settlement_name"]["recall"],
            report["decision"]["thresholds"]["mild"]["minimum_per_class_recall"],
        )

    def test_null_summaries_p_values_and_references_recompute(self) -> None:
        metric_reports = [
            (
                f"{regime_name}.{metric_name}",
                self.report["regimes"][regime_name][metric_name],
            )
            for regime_name in ("clean", "mild")
            for metric_name in (
                "observed",
                "opaque_FORM_lexicon_only",
                "position_and_line_structure_only",
            )
        ]
        metric_reports.extend(
            (
                f"{regime_name}.majority_reference",
                self.report["regimes"][regime_name]["majority_reference"]["metrics"],
            )
            for regime_name in ("clean", "mild")
        )
        metric_reports.append(
            (
                "harsh_diagnostic_only.observed",
                self.report["regimes"]["harsh_diagnostic_only"]["observed"],
            )
        )
        metric_reports.extend(
            (f"cue_ablations.{name}", ablation["metrics"])
            for name, ablation in self.report["cue_ablations"].items()
        )
        self.assertEqual(len(metric_reports), 12)
        for label, metrics in metric_reports:
            self._assert_metrics_recompute(label, metrics)

        support = self.report["support"]
        for regime_name, support_name, family_name in (
            ("clean", "clean", "clean_test_primary"),
            ("mild", "mild", "mild_test_primary"),
            ("harsh_diagnostic_only", "harsh", "harsh_test_primary"),
        ):
            observed = self.report["regimes"][regime_name]["observed"]["per_class"]
            for class_name in CLASSES:
                self.assertEqual(
                    observed[class_name]["effective_source_document_families"],
                    support["effective_source_document_families"][family_name][class_name],
                )
                self._assert_close(
                    observed[class_name]["family_mean_readable_coverage"],
                    support["family_mean_readable_coverage"][support_name][class_name],
                    f"{regime_name}.{class_name}.coverage",
                )

        for regime_name in ("clean", "mild"):
            regime = self.report["regimes"][regime_name]
            null = regime["permutation_null"]
            run_values = null["run_values"]
            self.assertEqual(
                [run["seed"] for run in run_values],
                list(range(999)),
            )
            values = [run["macro_f1"] for run in run_values]
            self.assertTrue(all(math.isfinite(value) for value in values))
            observed = regime["observed"]["macro_f1"]
            expected_p95 = _p95(values)
            expected_p = (1 + sum(value >= observed for value in values)) / 1000
            self._assert_close(
                null["macro_f1"]["minimum"],
                min(values),
                f"{regime_name}.null.minimum",
            )
            self._assert_close(
                null["macro_f1"]["maximum"],
                max(values),
                f"{regime_name}.null.maximum",
            )
            self._assert_close(
                null["macro_f1"]["mean"],
                math.fsum(values) / len(values),
                f"{regime_name}.null.mean",
            )
            self.assertEqual(null["macro_f1"]["p95"], expected_p95)
            self.assertEqual(
                null["add_one_empirical_p_greater_or_equal"],
                expected_p,
            )

            expected_reference = max(
                regime["majority_reference"]["metrics"]["macro_f1"],
                regime["position_and_line_structure_only"]["macro_f1"],
                expected_p95,
            )
            self.assertEqual(
                regime["decision_reference_macro_f1"],
                expected_reference,
            )
            self.assertEqual(
                regime["observed_minus_decision_reference"],
                observed - expected_reference,
            )

    def test_public_result_contains_no_forbidden_identity_or_path(self) -> None:
        forbidden_keys = {
            "account",
            "deprel",
            "document_key",
            "form",
            "head",
            "host",
            "local_path",
            "member_path",
            "misc",
            "observation_key",
            "p_identifier",
            "raw_token_id",
            "segm",
            "source_document_id",
            "token_key",
            "xpostag",
        }
        forbidden_value = re.compile(
            r"(?:/(?:home|Users|tmp)/[A-Za-z0-9._-]+|"
            r"[A-Za-z]:[\\/]|"
            r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)|"
            r"(?:^|[^A-Za-z0-9])P[0-9]{6}(?:[^A-Za-z0-9]|$))"
        )
        bad_keys: list[str] = []
        bad_values: list[str] = []

        def walk(value: Any, path: str = "$") -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    child = f"{path}.{key}"
                    if key.casefold() in forbidden_keys:
                        bad_keys.append(child)
                    walk(item, child)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]")
            elif (isinstance(value, str) and forbidden_value.search(value)) or (
                isinstance(value, float) and not math.isfinite(value)
            ):
                bad_values.append(path)

        walk(self.report)
        self.assertEqual(bad_keys, [])
        self.assertEqual(bad_values, [])


if __name__ == "__main__":
    unittest.main()
