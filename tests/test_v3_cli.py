from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from indusbench.v3dev.plan import V3_DEVELOPMENT_PLAN_SHA256
from indusbench.v3dev_cli import (
    MTAAC_V3_REPORT_VERSION,
    V3DevelopmentCLIError,
    _write_no_replace,
    main,
    validate_public_development_report,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_BYTES = (ROOT / "benchmark/mtaac-v3-development-v1.json").read_bytes()
IMPLEMENTATION_COMMIT = "a" * 40


def _report() -> dict[str, Any]:
    return {
        "analysis": "mtaac_v3_structural_development",
        "report_version": MTAAC_V3_REPORT_VERSION,
        "terminal_status": "development_complete",
        "development_only": True,
        "model_executed": True,
        "scientific_metrics_emitted": True,
        "plan_sha256": V3_DEVELOPMENT_PLAN_SHA256,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "parent_commitments": {
            "gateway_version": "mtaac-v2-training-gateway-v1",
            "mtaac_source_commit": "66e0643efd230401210e27db353ebb6d7228b1bb",
            "v2_freeze_commit": "37157f1411a55ffd91b7327afaca8fc1080fa708",
            "source_archive_sha256": (
                "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091"
            ),
            "selected_manifest_sha256": (
                "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e"
            ),
            "evaluation_corpus_sha256": (
                "sha256:e7d6f8c9a8c090bb33ef4ba3703c1b36fe0519086efa75ff70d1ba53a8bf9312"
            ),
            "v2_protocol_sha256": (
                "sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
            ),
            "v2_split_manifest_sha256": (
                "sha256:7249c8fe1d3efc95b42cc9e0a9378550addb64f5b992f89af99dd852b83c5c30"
            ),
        },
        "data_boundary": {
            "model_training_family_count": 271,
            "v2_holdout_family_count_excluded": 90,
            "v2_holdout_exposed_to_model": False,
            "reserved_validation_source_loaded": False,
            "v2_holdout_scored": False,
            "regimes_used": ["clean", "mild"],
            "replica_index_used": 0,
        },
        "model_contract": {
            "candidate_count": 9,
            "states": [
                "context_only",
                "quantity",
                "unit",
                "person_name",
                "settlement_name",
            ],
        },
        "nested_development": {
            "outer_fold_count": 5,
            "inner_fold_count": 4,
            "outer_support": [
                {
                    "index": 0,
                    "train_family_count": 216,
                    "validation_family_count": 55,
                    "validation_state_support": [100, 20, 20, 20, 5],
                }
            ],
            "mild_metrics": {
                "macro_f1": 0.5,
                "weighted_confusion_matrix": {
                    "context_only": {"context_only": 1.0},
                },
            },
        },
        "final_development_model": {
            "class_balance_gamma": 0.5,
            "transition_strength": 0.0,
            "model_sha256": "sha256:" + "e" * 64,
        },
        "claim_scope": {
            "binding_confirmation": False,
            "indus_decipherment": False,
            "prize_submission": False,
        },
    }


def _run(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


class V3DevelopmentCLITests(unittest.TestCase):
    def test_exact_inputs_reach_gateway_and_runner_then_write_canonical_report(self) -> None:
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
                    "indusbench.v3dev_cli._build_training_bundle",
                    return_value=bundle,
                ) as gateway,
                patch(
                    "indusbench.v3dev_cli._run_v3_development",
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

    def test_existing_output_stops_before_any_input_or_model_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "private-output.json"
            output.write_text("preserve me\n", encoding="utf-8")
            with (
                patch("indusbench.v3dev_cli._read_regular_bytes") as reader,
                patch("indusbench.v3dev_cli._build_training_bundle") as gateway,
                patch("indusbench.v3dev_cli._run_v3_development") as runner,
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
                patch("indusbench.v3dev_cli._build_training_bundle") as gateway,
                patch("indusbench.v3dev_cli._run_v3_development") as runner,
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

    def test_unreadable_paths_and_invalid_commit_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            output = temporary / "result.json"
            private_plan = temporary / "private-topology" / "plan.json"
            result, stdout, stderr = _run(
                [
                    str(temporary / "private-source.tar.gz"),
                    "--plan",
                    str(private_plan),
                    "--implementation-commit",
                    IMPLEMENTATION_COMMIT,
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(2, result, stderr)
            self.assertEqual("plan_unreadable", json.loads(stdout)["error_code"])
            self.assertNotIn("private-topology", stdout)

            invalid_result, invalid_stdout, invalid_stderr = _run(
                [
                    "source.tar.gz",
                    "--plan",
                    "plan.json",
                    "--implementation-commit",
                    "NOT-A-COMMIT/private",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(2, invalid_result, invalid_stderr)
            self.assertEqual(
                "implementation_commit_invalid",
                json.loads(invalid_stdout)["error_code"],
            )
            self.assertNotIn("NOT-A-COMMIT", invalid_stdout)

    def test_public_report_boundary_allows_aggregates_and_rejects_item_data(self) -> None:
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
            ("member_path", "corpus/item"),
            ("raw_form", "value"),
            ("source_identifier", "P123456"),
            ("local_path", "/private/topology/source"),
            ("reserved_name", "ORACC validation result"),
            ("opaque_leak", "mtaac-token-source-order-sha256-v1:" + "f" * 64),
        )
        for key, value in forbidden_cases:
            changed = _report()
            changed["nested_development"]["unexpected"] = {key: value}
            with self.subTest(key=key), self.assertRaises(V3DevelopmentCLIError):
                validate_public_development_report(changed)

    def test_public_report_rechecks_parent_data_and_implementation_commitments(self) -> None:
        cases = []

        changed_parent = _report()
        changed_parent["parent_commitments"]["source_archive_sha256"] = "sha256:" + "f" * 64
        cases.append(changed_parent)

        changed_count = _report()
        changed_count["data_boundary"]["model_training_family_count"] = 270
        cases.append(changed_count)

        changed_exposure = _report()
        changed_exposure["data_boundary"]["v2_holdout_exposed_to_model"] = True
        cases.append(changed_exposure)

        changed_regimes = _report()
        changed_regimes["data_boundary"]["regimes_used"] = ["mild", "clean"]
        cases.append(changed_regimes)

        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(V3DevelopmentCLIError):
                validate_public_development_report(changed)

        with self.assertRaises(V3DevelopmentCLIError):
            validate_public_development_report(
                _report(),
                expected_implementation_commit="f" * 40,
            )

    def test_rejected_report_is_never_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            archive = temporary / "source.tar.gz"
            plan = temporary / "plan.json"
            output = temporary / "result.json"
            archive.write_bytes(b"synthetic exact archive")
            plan.write_bytes(PLAN_BYTES)
            report = _report()
            report["nested_development"]["per_family_metrics"] = {"secret": 1.0}
            with (
                patch("indusbench.v3dev_cli._build_training_bundle", return_value=object()),
                patch(
                    "indusbench.v3dev_cli._run_v3_development",
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
            patch("indusbench.v3dev_cli.os.fsync"),
        ):
            _write_no_replace(destination, b"{}\n")
        opener.assert_called_once_with("xb")
        handle.write.assert_called_once_with(b"{}\n")


if __name__ == "__main__":
    unittest.main()
