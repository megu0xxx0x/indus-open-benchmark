from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from indusbench.v3dev.metrics import add_confusion_matrices, metrics_from_confusion
from indusbench.v4dev.plan import V4_DEVELOPMENT_PLAN_SHA256
from indusbench.v4dev_cli import (
    _EXPECTED_CLAIM_SCOPE,
    _EXPECTED_DATA_BOUNDARY,
    _EXPECTED_MODEL_CONTRACT,
    _EXPECTED_PARENT_COMMITMENTS,
    _EXPECTED_PROFILE_CONTRACT,
    MTAAC_V4_REPORT_VERSION,
    V4DevelopmentCLIError,
    _write_no_replace,
    main,
    validate_public_development_report,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_BYTES = (ROOT / "benchmark" / "mtaac-v4-development-v1.json").read_bytes()
IMPLEMENTATION_COMMIT = "a" * 40
STATES = [
    "context_only",
    "quantity",
    "unit",
    "person_name",
    "settlement_name",
]
V3_OUTER_MACRO_F1 = [
    0.31683351626900313,
    0.32138764286827887,
    0.3088289319784221,
    0.30447569487308923,
    0.33797633693780393,
]


def _optimizer_run() -> dict[str, Any]:
    return {
        "accepted_iterations": 12,
        "converged": True,
        "final_gradient_infinity_norm": 0.00001,
        "final_objective": 1.25,
        "termination_reason": "gradient_infinity_norm",
    }


def _metrics(*, macro_f1: float = 0.6) -> dict[str, Any]:
    confusion: dict[str, dict[str, float]] = {
        truth: {predicted: 0.0 for predicted in STATES} for truth in STATES
    }
    for state_index, truth in enumerate(STATES):
        confusion[truth][truth] = macro_f1
        confusion[truth][STATES[(state_index + 1) % len(STATES)]] = 1.0 - macro_f1
    return metrics_from_confusion(confusion)  # type: ignore[arg-type]


def _aggregate_metric_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    matrices = [report["weighted_confusion_matrix"] for report in reports]
    return metrics_from_confusion(add_confusion_matrices(matrices))  # type: ignore[arg-type]


def _minimum_check(observed: float | int, minimum: float | int) -> dict[str, Any]:
    return {"minimum": minimum, "observed": observed, "passed": observed >= minimum}


def _report(*, terminal_status: str = "advance") -> dict[str, Any]:
    advanced = terminal_status == "advance"
    primary_metrics = {
        "clean": _metrics(),
        "mild": _metrics(),
    }
    diagnostics = {
        "no_corpus_profile": _metrics(macro_f1=0.55 if advanced else 0.6),
        "transition_zero": _metrics(macro_f1=0.58),
        "logistic_emission": _metrics(macro_f1=0.57),
        "self_inclusive_target_profile": _metrics(macro_f1=0.61),
        "strict_single_family_profile": _metrics(macro_f1=0.4),
    }
    fold_metrics = {"primary": primary_metrics, "diagnostics": diagnostics}
    optimizer = {
        "primary": _optimizer_run(),
        "no_corpus_profile": _optimizer_run(),
        "logistic_emission": _optimizer_run(),
    }
    folds = []
    for fold_index in range(5):
        folds.append(
            {
                "outer_fold_index": fold_index,
                "support": {
                    "train_family_count": 216,
                    "validation_family_count": 55,
                    "train_state_support": {state: 10 for state in STATES},
                    "validation_state_support": {state: 2 for state in STATES},
                },
                "profile_batch_commitments": {
                    "train_clean": "sha256:" + f"{fold_index + 1:x}" * 64,
                    "train_mild": "sha256:" + f"{fold_index + 2:x}" * 64,
                    "validation_clean": "sha256:" + f"{fold_index + 3:x}" * 64,
                    "validation_mild": "sha256:" + f"{fold_index + 4:x}" * 64,
                },
                "optimizer": copy.deepcopy(optimizer),
                "metrics": copy.deepcopy(fold_metrics),
            }
        )

    out_of_fold_metrics = {
        "primary": {
            regime: _aggregate_metric_reports(
                [fold["metrics"]["primary"][regime] for fold in folds]
            )
            for regime in ("clean", "mild")
        },
        "diagnostics": {
            name: _aggregate_metric_reports(
                [fold["metrics"]["diagnostics"][name] for fold in folds]
            )
            for name in diagnostics
        },
    }
    v4_mild_by_outer_fold = [
        float(fold["metrics"]["primary"]["mild"]["macro_f1"]) for fold in folds
    ]
    delta_by_outer_fold = [
        current - baseline
        for current, baseline in zip(
            v4_mild_by_outer_fold,
            V3_OUTER_MACRO_F1,
            strict=True,
        )
    ]
    positive_delta_fold_count = sum(delta > 0.0 for delta in delta_by_outer_fold)
    mild = out_of_fold_metrics["primary"]["mild"]
    clean = out_of_fold_metrics["primary"]["clean"]
    no_profile = out_of_fold_metrics["diagnostics"]["no_corpus_profile"]
    self_inclusive = out_of_fold_metrics["diagnostics"]["self_inclusive_target_profile"]
    mild_per_state = mild["per_state"]
    clean_per_state = clean["per_state"]
    self_inclusive_delta = float(self_inclusive["macro_f1"]) - float(mild["macro_f1"])
    checks = {
        "mild_macro_f1": _minimum_check(
            float(mild["macro_f1"]),
            0.36432759235715436,
        ),
        "mild_settlement_name_recall": _minimum_check(
            float(mild_per_state["settlement_name"]["recall"]),
            0.15,
        ),
        "positive_paired_delta_outer_fold_count": _minimum_check(
            positive_delta_fold_count,
            4,
        ),
        "profile_increment_mild_macro_f1": _minimum_check(
            float(mild["macro_f1"]) - float(no_profile["macro_f1"]),
            0.02,
        ),
        "mild_recall_floors": {
            "context_only": _minimum_check(
                float(mild_per_state["context_only"]["recall"]),
                0.520654531441017,
            ),
            "quantity": _minimum_check(
                float(mild_per_state["quantity"]["recall"]),
                0.1765055025096581,
            ),
            "unit": _minimum_check(
                float(mild_per_state["unit"]["recall"]),
                0.3767836311289388,
            ),
            "person_name": _minimum_check(
                float(mild_per_state["person_name"]["recall"]),
                0.4988092152820551,
            ),
        },
        "clean_macro_f1": _minimum_check(float(clean["macro_f1"]), 0.36),
        "clean_settlement_name_recall": _minimum_check(
            float(clean_per_state["settlement_name"]["recall"]),
            0.1,
        ),
        "self_inclusive_minus_lofo_mild_macro_f1": {
            "observed": self_inclusive_delta,
            "maximum": 0.05,
            "passed": self_inclusive_delta <= 0.05,
        },
    }
    all_passed = all(
        (
            checks["mild_macro_f1"]["passed"],
            checks["mild_settlement_name_recall"]["passed"],
            checks["positive_paired_delta_outer_fold_count"]["passed"],
            checks["profile_increment_mild_macro_f1"]["passed"],
            *(value["passed"] for value in checks["mild_recall_floors"].values()),
            checks["clean_macro_f1"]["passed"],
            checks["clean_settlement_name_recall"]["passed"],
            checks["self_inclusive_minus_lofo_mild_macro_f1"]["passed"],
        )
    )
    expected_terminal = "advance" if all_passed else "development_killed"
    if expected_terminal != terminal_status:
        raise AssertionError("test report terminal status does not match its frozen gates")
    return {
        "analysis": "mtaac_v4_distributional_crf_development",
        "report_version": MTAAC_V4_REPORT_VERSION,
        "terminal_status": terminal_status,
        "development_only": True,
        "model_executed": True,
        "scientific_metrics_emitted": True,
        "plan_sha256": V4_DEVELOPMENT_PLAN_SHA256,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "parent_commitments": copy.deepcopy(_EXPECTED_PARENT_COMMITMENTS),
        "data_boundary": copy.deepcopy(_EXPECTED_DATA_BOUNDARY),
        "profile_contract": copy.deepcopy(_EXPECTED_PROFILE_CONTRACT),
        "model_contract": copy.deepcopy(_EXPECTED_MODEL_CONTRACT),
        "outer_development": {
            "outer_fold_count": 5,
            "fold_assignment_parent": "exact_v3_five_outer_fold_assignments",
            "outer_folds": folds,
            "out_of_fold_metrics": out_of_fold_metrics,
            "paired_v3": {
                "v3_mild_macro_f1": 0.32432759235715436,
                "v3_mild_macro_f1_by_outer_fold": V3_OUTER_MACRO_F1,
                "v4_mild_macro_f1_by_outer_fold": v4_mild_by_outer_fold,
                "delta_by_outer_fold": delta_by_outer_fold,
                "positive_delta_fold_count": positive_delta_fold_count,
            },
        },
        "gate_decision": {
            "terminal_status": terminal_status,
            "all_passed": all_passed,
            "self_information_sensitive": False,
            "checks": checks,
        },
        "final_development_model": {
            "fitted": advanced,
            "fit_rule": "fit_all_271_families_only_after_advance",
            "model_state_commitment": "sha256:" + "e" * 64 if advanced else None,
            "optimizer": _optimizer_run() if advanced else None,
        },
        "claim_scope": copy.deepcopy(_EXPECTED_CLAIM_SCOPE),
    }


def _run(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


class V4DevelopmentCLITests(unittest.TestCase):
    def test_exact_inputs_reach_gateway_and_runner_then_write_advance_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            archive = temporary / "source.tar.gz"
            plan = temporary / "plan.json"
            output = temporary / "result.json"
            archive_bytes = b"synthetic exact archive"
            archive.write_bytes(archive_bytes)
            plan.write_bytes(PLAN_BYTES)
            bundle = object()
            report = _report()

            with (
                patch(
                    "indusbench.v4dev_cli._build_training_bundle",
                    return_value=bundle,
                ) as gateway,
                patch(
                    "indusbench.v4dev_cli._run_v4_development",
                    return_value=report,
                ) as runner,
            ):
                result, stdout, stderr = _run(
                    [
                        str(archive),
                        "--plan",
                        str(plan),
                        "--implementation-commit",
                        IMPLEMENTATION_COMMIT,
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(0, result, stderr)
            gateway.assert_called_once_with(archive_bytes)
            runner.assert_called_once_with(
                bundle,
                plan_bytes=PLAN_BYTES,
                implementation_commit=IMPLEMENTATION_COMMIT,
            )
            expected = (
                json.dumps(
                    report,
                    allow_nan=False,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            self.assertEqual(expected, stdout)
            self.assertEqual(expected.encode("utf-8"), output.read_bytes())

    def test_killed_report_is_a_valid_terminal_scientific_result(self) -> None:
        report = _report(terminal_status="development_killed")
        self.assertIs(report, validate_public_development_report(report))
        self.assertFalse(report["final_development_model"]["fitted"])
        self.assertIsNone(report["final_development_model"]["model_state_commitment"])

    def test_existing_output_stops_before_any_input_or_model_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "private-output.json"
            output.write_text("preserve me\n", encoding="utf-8")
            with (
                patch("indusbench.v4dev_cli._read_regular_bytes") as reader,
                patch("indusbench.v4dev_cli._build_training_bundle") as gateway,
                patch("indusbench.v4dev_cli._run_v4_development") as runner,
            ):
                result, stdout, stderr = _run(
                    [
                        "unreadable-source.tar.gz",
                        "--plan",
                        "unreadable-plan.json",
                        "--implementation-commit",
                        IMPLEMENTATION_COMMIT,
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(1, result, stderr)
            self.assertEqual("output_exists", json.loads(stdout)["error_code"])
            self.assertNotIn(str(output), stdout)
            self.assertEqual("preserve me\n", output.read_text(encoding="utf-8"))
            reader.assert_not_called()
            gateway.assert_not_called()
            runner.assert_not_called()

    def test_plan_is_verified_before_archive_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            plan = temporary / "changed-plan.json"
            output = temporary / "result.json"
            plan.write_bytes(PLAN_BYTES + b" ")
            with (
                patch("indusbench.v4dev_cli._build_training_bundle") as gateway,
                patch("indusbench.v4dev_cli._run_v4_development") as runner,
            ):
                result, stdout, stderr = _run(
                    [
                        str(temporary / "private-source.tar.gz"),
                        "--plan",
                        str(plan),
                        "--implementation-commit",
                        IMPLEMENTATION_COMMIT,
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(2, result, stderr)
            self.assertEqual("plan_rejected", json.loads(stdout)["error_code"])
            self.assertNotIn(str(plan), stdout)
            self.assertNotIn("private-source", stdout)
            self.assertFalse(output.exists())
            gateway.assert_not_called()
            runner.assert_not_called()

    def test_public_report_boundary_rejects_item_data_and_terminal_mismatch(self) -> None:
        report = _report()
        self.assertIs(report, validate_public_development_report(report))
        self.assertIs(
            report,
            validate_public_development_report(
                report,
                expected_implementation_commit=IMPLEMENTATION_COMMIT,
            ),
        )

        forbidden_cases: tuple[tuple[str, object], ...] = (
            ("document_key", "opaque"),
            ("family_ids", ["f" * 64]),
            ("fold_membership", {"0": ["f" * 64]}),
            ("feature_rows", [["secret"]]),
            ("identity_map", {"secret": 1}),
            ("member_path", "corpus/item"),
            ("raw_form", "value"),
            ("source_identifier", "P123456"),
            ("local_path", "/private/topology/source"),
            ("reserved_name", "ORACC validation result"),
            ("opaque_leak", "mtaac-token-source-order-sha256-v1:" + "f" * 64),
        )
        for key, value in forbidden_cases:
            changed = _report()
            changed["outer_development"]["unexpected"] = {key: value}
            with self.subTest(key=key), self.assertRaises(V4DevelopmentCLIError):
                validate_public_development_report(changed)

        mismatched = _report()
        mismatched["gate_decision"]["terminal_status"] = "development_killed"
        with self.assertRaisesRegex(V4DevelopmentCLIError, "terminal"):
            validate_public_development_report(mismatched)

    def test_public_report_rechecks_parent_profile_model_and_claim_contracts(self) -> None:
        cases = []

        changed_parent = _report()
        changed_parent["parent_commitments"]["v3_result_sha256"] = "sha256:" + "f" * 64
        cases.append(changed_parent)

        changed_count = _report()
        changed_count["data_boundary"]["model_training_family_count"] = 270
        cases.append(changed_count)

        changed_profile = _report()
        changed_profile["profile_contract"]["gold_used"] = True
        cases.append(changed_profile)

        changed_model = _report()
        changed_model["model_contract"]["candidate_count"] = 2
        cases.append(changed_model)

        changed_claim = _report()
        changed_claim["claim_scope"]["eligible_as_decipherment"] = True
        cases.append(changed_claim)

        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(V4DevelopmentCLIError):
                validate_public_development_report(changed)

        with self.assertRaises(V4DevelopmentCLIError):
            validate_public_development_report(
                _report(),
                expected_implementation_commit="f" * 40,
            )

    def test_public_report_recomputes_metrics_pairing_and_every_gate(self) -> None:
        changed_fold_metric = _report()
        changed_fold_metric["outer_development"]["outer_folds"][0]["metrics"]["primary"]["mild"][
            "macro_f1"
        ] += 0.01

        changed_diagnostic_metric = _report()
        changed_diagnostic_metric["outer_development"]["outer_folds"][2]["metrics"]["diagnostics"][
            "logistic_emission"
        ]["per_state"]["unit"]["recall"] += 0.01

        changed_oof = _report()
        changed_oof["outer_development"]["out_of_fold_metrics"]["primary"]["mild"] = _metrics(
            macro_f1=0.7
        )

        changed_paired_delta = _report()
        changed_paired_delta["outer_development"]["paired_v3"]["delta_by_outer_fold"][0] += 0.01

        changed_paired_count = _report()
        changed_paired_count["outer_development"]["paired_v3"]["positive_delta_fold_count"] = 4

        changed_gate_observed = _report()
        changed_gate_observed["gate_decision"]["checks"]["profile_increment_mild_macro_f1"][
            "observed"
        ] += 0.01

        changed_gate_pass = _report()
        changed_gate_pass["gate_decision"]["checks"]["mild_macro_f1"]["passed"] = False

        changed_gate_summary = _report()
        changed_gate_summary["gate_decision"]["all_passed"] = False

        cases = {
            "fold metric": changed_fold_metric,
            "diagnostic metric": changed_diagnostic_metric,
            "out-of-fold aggregate": changed_oof,
            "paired delta": changed_paired_delta,
            "paired positive count": changed_paired_count,
            "gate observation": changed_gate_observed,
            "gate pass": changed_gate_pass,
            "gate summary": changed_gate_summary,
        }
        for name, changed in cases.items():
            with self.subTest(name=name), self.assertRaises(V4DevelopmentCLIError):
                validate_public_development_report(changed)

    def test_public_report_runtime_schema_rejects_unknown_nested_fields(self) -> None:
        benign = _report()
        benign["outer_development"]["unexpected"] = {"note": "aggregate only"}

        host = _report()
        host["outer_development"]["outer_folds"][0]["support"]["host"] = "internal-host"

        account = _report()
        account["final_development_model"]["account"] = "internal-account"

        for name, changed in {
            "benign": benign,
            "host": host,
            "account": account,
        }.items():
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(
                    V4DevelopmentCLIError,
                    "closed schema",
                ),
            ):
                validate_public_development_report(changed)

    def test_rejected_report_is_never_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            archive = temporary / "source.tar.gz"
            plan = temporary / "plan.json"
            output = temporary / "result.json"
            archive.write_bytes(b"synthetic exact archive")
            plan.write_bytes(PLAN_BYTES)
            report = _report()
            report["outer_development"]["per_family_metrics"] = {"secret": 1.0}
            with (
                patch("indusbench.v4dev_cli._build_training_bundle", return_value=object()),
                patch(
                    "indusbench.v4dev_cli._run_v4_development",
                    return_value=report,
                ),
            ):
                result, stdout, stderr = _run(
                    [
                        str(archive),
                        "--plan",
                        str(plan),
                        "--implementation-commit",
                        IMPLEMENTATION_COMMIT,
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(2, result, stderr)
            self.assertEqual("report_rejected", json.loads(stdout)["error_code"])
            self.assertFalse(output.exists())

    def test_writer_uses_exclusive_binary_creation(self) -> None:
        handle = MagicMock()
        handle.__enter__.return_value = handle
        destination = Path("aggregate-result.json")
        with (
            patch.object(Path, "mkdir"),
            patch.object(Path, "open", return_value=handle) as opener,
            patch("indusbench.v4dev_cli.os.fsync"),
        ):
            _write_no_replace(destination, b"{}\n")
        opener.assert_called_once_with("xb")
        handle.write.assert_called_once_with(b"{}\n")


if __name__ == "__main__":
    unittest.main()
