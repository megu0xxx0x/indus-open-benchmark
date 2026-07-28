from __future__ import annotations

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from indusbench.v3dev.metrics import add_confusion_matrices, metrics_from_confusion
from indusbench.v5dev_cli import (
    V5DevelopmentCLIError,
    _recomputed_gate,
    _validate_public_value,
    _write_no_replace,
    main,
    validate_public_development_report,
)
from tests.test_v5_report_schema import (
    COMPARISON_TOLERANCE,
    STATES,
    V4_MACRO_BY_FOLD,
    V4_SETTLEMENT_RECALL_BY_FOLD,
    V4_UNIT_RECALL_BY_FOLD,
)
from tests.test_v5_report_schema import (
    _report as _schema_report,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_BYTES = (ROOT / "benchmark" / "mtaac-v5-development-v1.json").read_bytes()
IMPLEMENTATION_COMMIT = "a" * 40
VALIDATION_FAMILY_COUNTS = (52, 54, 55, 53, 57)
TRAIN_FAMILY_COUNTS = (219, 217, 216, 218, 214)


def _metrics(*, score: float, total_mass: int) -> dict[str, Any]:
    state_mass = total_mass / len(STATES)
    confusion: dict[str, dict[str, float]] = {
        truth: {predicted: 0.0 for predicted in STATES} for truth in STATES
    }
    for state_index, truth in enumerate(STATES):
        confusion[truth][truth] = score * state_mass
        confusion[truth][STATES[(state_index + 1) % len(STATES)]] = (1.0 - score) * state_mass
    return metrics_from_confusion(confusion)  # type: ignore[arg-type]


def _aggregate(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return metrics_from_confusion(  # type: ignore[arg-type]
        add_confusion_matrices([report["weighted_confusion_matrix"] for report in reports])
    )


def _valid_report(
    terminal_status: str = "advance_to_prospective_freeze",
) -> dict[str, Any]:
    report = _schema_report(terminal_status=terminal_status)
    score = 0.6 if terminal_status == "advance_to_prospective_freeze" else 0.3
    folds = report["outer_development"]["outer_folds"]
    for fold_index, fold in enumerate(folds):
        fold["support"] = {
            "train_family_count": TRAIN_FAMILY_COUNTS[fold_index],
            "validation_family_count": VALIDATION_FAMILY_COUNTS[fold_index],
            "train_state_support": {state: 80 for state in STATES},
            "validation_state_support": {state: 20 for state in STATES},
        }
        fold["metrics"] = {
            regime: _metrics(
                score=score,
                total_mass=VALIDATION_FAMILY_COUNTS[fold_index],
            )
            for regime in ("clean", "mild")
        }

    out_of_fold = {
        regime: _aggregate([fold["metrics"][regime] for fold in folds])
        for regime in ("clean", "mild")
    }
    report["outer_development"]["out_of_fold_metrics"] = out_of_fold
    v5_macro = [float(fold["metrics"]["mild"]["macro_f1"]) for fold in folds]
    v5_unit = [float(fold["metrics"]["mild"]["per_state"]["unit"]["recall"]) for fold in folds]
    v5_settlement = [
        float(fold["metrics"]["mild"]["per_state"]["settlement_name"]["recall"]) for fold in folds
    ]
    macro_deltas = [
        current - baseline for current, baseline in zip(v5_macro, V4_MACRO_BY_FOLD, strict=True)
    ]
    unit_deltas = [
        current - baseline
        for current, baseline in zip(
            v5_unit,
            V4_UNIT_RECALL_BY_FOLD,
            strict=True,
        )
    ]
    settlement_deltas = [
        current - baseline
        for current, baseline in zip(
            v5_settlement,
            V4_SETTLEMENT_RECALL_BY_FOLD,
            strict=True,
        )
    ]
    paired = {
        "v4_mild_macro_f1": 0.3877588813953674,
        "v4_mild_macro_f1_by_outer_fold": list(V4_MACRO_BY_FOLD),
        "v5_mild_macro_f1_by_outer_fold": v5_macro,
        "mild_macro_f1_delta_by_outer_fold": macro_deltas,
        "positive_mild_macro_f1_delta_fold_count": sum(
            delta > COMPARISON_TOLERANCE for delta in macro_deltas
        ),
        "v4_mild_unit_recall": 0.30521567409297784,
        "v4_mild_unit_recall_by_outer_fold": list(V4_UNIT_RECALL_BY_FOLD),
        "v5_mild_unit_recall_by_outer_fold": v5_unit,
        "mild_unit_recall_delta_by_outer_fold": unit_deltas,
        "positive_mild_unit_recall_delta_fold_count": sum(
            delta > COMPARISON_TOLERANCE for delta in unit_deltas
        ),
        "v4_mild_settlement_name_recall": 0.042941913609110954,
        "v4_mild_settlement_name_recall_by_outer_fold": list(V4_SETTLEMENT_RECALL_BY_FOLD),
        "v5_mild_settlement_name_recall_by_outer_fold": v5_settlement,
        "mild_settlement_name_recall_delta_by_outer_fold": settlement_deltas,
        "positive_mild_settlement_name_recall_delta_fold_count": sum(
            delta > COMPARISON_TOLERANCE for delta in settlement_deltas
        ),
    }
    report["outer_development"]["paired_v4"] = paired
    report["gate_decision"] = _recomputed_gate(
        clean=out_of_fold["clean"],
        mild=out_of_fold["mild"],
        paired=paired,
    )
    if report["gate_decision"]["terminal_status"] != terminal_status:
        raise AssertionError("test fixture does not match its requested terminal state")
    return report


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


class V5CLIValidationTests(unittest.TestCase):
    def test_advance_and_retired_reports_pass_all_runtime_checks(self) -> None:
        for status in ("advance_to_prospective_freeze", "mtaac_retired"):
            with self.subTest(status=status):
                report = _valid_report(status)
                self.assertIs(
                    report,
                    validate_public_development_report(
                        report,
                        expected_implementation_commit=IMPLEMENTATION_COMMIT,
                    ),
                )

    def test_metric_oof_pair_gate_and_terminal_tampering_is_rejected(self) -> None:
        cases: list[dict[str, Any]] = []

        metric = _valid_report()
        metric["outer_development"]["outer_folds"][0]["metrics"]["mild"]["macro_f1"] -= 0.01
        cases.append(metric)

        oof = _valid_report()
        oof["outer_development"]["out_of_fold_metrics"]["mild"]["weighted_accuracy"] -= 0.01
        cases.append(oof)

        paired = _valid_report()
        paired["outer_development"]["paired_v4"]["mild_unit_recall_delta_by_outer_fold"][0] += 0.01
        cases.append(paired)

        gate = _valid_report()
        gate["gate_decision"]["checks"]["mild_macro_f1"]["observed"] -= 0.01
        cases.append(gate)

        terminal = _valid_report()
        terminal["terminal_status"] = "mtaac_retired"
        cases.append(terminal)

        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(V5DevelopmentCLIError):
                validate_public_development_report(changed)

    def test_support_mass_unknown_field_and_public_boundary_tampering_is_rejected(
        self,
    ) -> None:
        changed_support = _valid_report()
        changed_support["outer_development"]["outer_folds"][0]["support"][
            "validation_state_support"
        ]["unit"] += 1
        with self.assertRaises(V5DevelopmentCLIError):
            validate_public_development_report(changed_support)

        changed_mass = _valid_report()
        changed_mass["outer_development"]["outer_folds"][0]["support"][
            "validation_family_count"
        ] += 1
        with self.assertRaises(V5DevelopmentCLIError):
            validate_public_development_report(changed_mass)

        unknown = _valid_report()
        unknown["outer_development"]["outer_folds"][0]["optimizer"]["host"] = "internal"
        with self.assertRaises(V5DevelopmentCLIError):
            validate_public_development_report(unknown)

        false_convergence = _valid_report()
        false_convergence["outer_development"]["outer_folds"][0]["optimizer"][
            "final_gradient_infinity_norm"
        ] = 0.1
        with self.assertRaises(V5DevelopmentCLIError):
            validate_public_development_report(false_convergence)

        with self.assertRaises(V5DevelopmentCLIError):
            _validate_public_value({"note": "/private/item/P123456"})
        with self.assertRaises(V5DevelopmentCLIError):
            _validate_public_value({"nested": {"account_name": "internal"}})

    def test_no_replace_writer_preserves_existing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "result.json"
            _write_no_replace(target, b"first")
            with self.assertRaises(FileExistsError):
                _write_no_replace(target, b"second")
            self.assertEqual(b"first", target.read_bytes())


class V5CLIMainTests(unittest.TestCase):
    def test_invalid_plan_stops_before_archive_gateway_or_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "private-archive-name.tar.gz"
            plan = root / "private-invalid-plan.json"
            output = root / "private-output.json"
            archive.write_bytes(b"not inspected")
            plan.write_bytes(PLAN_BYTES + b" ")
            with (
                patch("indusbench.v5dev_cli._build_training_bundle") as gateway,
                patch("indusbench.v5dev_cli._run_v5_development") as model,
            ):
                status, stdout, stderr = _run_cli(
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
            self.assertEqual(2, status)
            gateway.assert_not_called()
            model.assert_not_called()
            self.assertFalse(output.exists())
            self.assertIn('"error_code": "plan_rejected"', stdout)
            self.assertNotIn(str(root), stdout + stderr)

    def test_archive_gateway_rejection_stops_before_model_with_redacted_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "private-invalid-archive.tar.gz"
            plan = root / "plan.json"
            output = root / "output.json"
            archive.write_bytes(b"invalid")
            plan.write_bytes(PLAN_BYTES)
            with (
                patch(
                    "indusbench.v5dev_cli._build_training_bundle",
                    side_effect=ValueError(str(archive)),
                ),
                patch("indusbench.v5dev_cli._run_v5_development") as model,
            ):
                status, stdout, stderr = _run_cli(
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
            self.assertEqual(2, status)
            model.assert_not_called()
            self.assertFalse(output.exists())
            self.assertIn('"error_code": "archive_rejected"', stdout)
            self.assertNotIn(str(root), stdout + stderr)

    def test_success_writes_once_and_second_invocation_cannot_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.tar.gz"
            plan = root / "plan.json"
            output = root / "result.json"
            archive.write_bytes(b"gateway mocked")
            plan.write_bytes(PLAN_BYTES)
            report = _valid_report()
            argv = [
                str(archive),
                "--plan",
                str(plan),
                "--implementation-commit",
                IMPLEMENTATION_COMMIT,
                "--output",
                str(output),
            ]
            with (
                patch(
                    "indusbench.v5dev_cli._build_training_bundle",
                    return_value=object(),
                ),
                patch(
                    "indusbench.v5dev_cli._run_v5_development",
                    return_value=report,
                ),
            ):
                status, stdout, stderr = _run_cli(argv)
            self.assertEqual(0, status)
            self.assertEqual("", stderr)
            self.assertEqual(stdout.encode("utf-8"), output.read_bytes())

            original = output.read_bytes()
            status, stdout, stderr = _run_cli(argv)
            self.assertEqual(1, status)
            self.assertIn('"error_code": "output_exists"', stdout)
            self.assertNotIn(str(root), stdout + stderr)
            self.assertEqual(original, output.read_bytes())

    def test_semantically_invalid_report_is_rejected_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.tar.gz"
            plan = root / "plan.json"
            output = root / "result.json"
            archive.write_bytes(b"gateway mocked")
            plan.write_bytes(PLAN_BYTES)
            report = copy.deepcopy(_valid_report())
            report["gate_decision"]["checks"]["mild_macro_f1"]["passed"] = False
            with (
                patch(
                    "indusbench.v5dev_cli._build_training_bundle",
                    return_value=object(),
                ),
                patch(
                    "indusbench.v5dev_cli._run_v5_development",
                    return_value=report,
                ),
            ):
                status, stdout, stderr = _run_cli(
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
            self.assertEqual(2, status)
            self.assertIn('"error_code": "report_rejected"', stdout)
            for scientific_field in (
                "macro_f1",
                "weighted_confusion_matrix",
                "gate_decision",
                "outer_development",
            ):
                self.assertNotIn(scientific_field, stdout)
            self.assertNotIn(str(root), stdout + stderr)
            self.assertFalse(output.exists())

    def test_gateway_helper_delegates_to_the_exact_v2_training_gateway(self) -> None:
        marker = object()
        with patch(
            "indusbench.v3dev.mtaac_training.build_mtaac_v2_training_bundle",
            return_value=marker,
        ) as gateway:
            from indusbench.v5dev_cli import _build_training_bundle

            self.assertIs(marker, _build_training_bundle(b"exact archive bytes"))
        gateway.assert_called_once_with(b"exact archive bytes")


if __name__ == "__main__":
    unittest.main()
