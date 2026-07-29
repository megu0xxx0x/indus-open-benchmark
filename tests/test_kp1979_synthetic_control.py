from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from pathlib import Path

from indusbench.kp1979_synthetic_control import (
    SYNTHETIC_CASE_COUNT,
    SYNTHETIC_METAMORPHIC_CHECK_COUNT,
    SYNTHETIC_NEGATIVE_CASE_COUNT,
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_PBM_BYTE_SIZE,
    SYNTHETIC_POSITIVE_CASE_COUNT,
    TARGET_ALGORITHM_ID,
    KP1979SyntheticControlError,
    build_synthetic_fixture,
    evaluate_synthetic_fixture,
    run_synthetic_control,
    synthetic_case_ids,
)

ROOT = Path(__file__).resolve().parents[1]
HEADER = b"P4\n4880 7010\n"
ROW_BYTES = SYNTHETIC_PAGE_WIDTH // 8
SCAN_X = ((2056, 2316), (4232, 4492))


def row_has_black(pbm: bytes, y: int, x0: int, x1: int) -> bool:
    payload = pbm[len(HEADER) :]
    row = payload[y * ROW_BYTES : (y + 1) * ROW_BYTES]
    return any(row[x // 8] & (128 >> (x % 8)) for x in range(x0, x1))


class KP1979SyntheticControlTests(unittest.TestCase):
    def test_fixed_case_roster_is_complete_and_scientifically_minimal(self) -> None:
        case_ids = synthetic_case_ids()
        self.assertEqual(SYNTHETIC_CASE_COUNT, len(case_ids))
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(7, SYNTHETIC_POSITIVE_CASE_COUNT)
        self.assertEqual(6, SYNTHETIC_NEGATIVE_CASE_COUNT)
        self.assertEqual(
            {
                "positive_clean",
                "positive_pitch_158",
                "positive_pitch_172",
                "positive_phase_shift",
                "positive_y_jitter",
                "positive_thin_strokes",
                "positive_partial_lanes",
                "negative_blank",
                "negative_single_lane",
                "negative_pitch_mismatch",
                "negative_discontinuous_lane",
                "negative_multi_column",
                "negative_periodic_non_label_bands",
            },
            set(case_ids),
        )

    def test_every_fixture_is_a_canonical_native_size_raw_pbm(self) -> None:
        for case_id in synthetic_case_ids():
            with self.subTest(case_id=case_id):
                fixture = build_synthetic_fixture(case_id)
                self.assertEqual(SYNTHETIC_PBM_BYTE_SIZE, len(fixture.pbm_bytes))
                self.assertTrue(fixture.pbm_bytes.startswith(HEADER))
                self.assertEqual(
                    ROW_BYTES * SYNTHETIC_PAGE_HEIGHT,
                    len(fixture.pbm_bytes) - len(HEADER),
                )
                if fixture.case_class == "positive":
                    self.assertGreater(len(fixture.references), 0)
                else:
                    self.assertEqual((), fixture.references)

    def test_positive_reference_intervals_are_tight_to_generated_ink(self) -> None:
        fixture = build_synthetic_fixture("positive_clean")
        for target in fixture.references:
            with self.subTest(lane=target.lane_index, y0=target.y0):
                x0, x1 = SCAN_X[target.lane_index]
                self.assertTrue(row_has_black(fixture.pbm_bytes, target.y0, x0, x1))
                self.assertTrue(row_has_black(fixture.pbm_bytes, target.y1 - 1, x0, x1))
                self.assertFalse(row_has_black(fixture.pbm_bytes, target.y0 - 1, x0, x1))
                self.assertFalse(row_has_black(fixture.pbm_bytes, target.y1, x0, x1))

    def test_canonical_fixture_evaluation_passes_clean_and_preserves_thin_failure(
        self,
    ) -> None:
        clean = evaluate_synthetic_fixture(build_synthetic_fixture("positive_clean"))
        thin = evaluate_synthetic_fixture(build_synthetic_fixture("positive_thin_strokes"))
        self.assertTrue(clean.passed)
        self.assertEqual(1.0, clean.micro_precision)
        self.assertEqual(1.0, clean.micro_recall)
        self.assertFalse(thin.passed)
        self.assertEqual(0.3611111111111111, thin.micro_precision)
        self.assertEqual(0.3611111111111111, thin.micro_recall)

    def test_noncanonical_or_unknown_fixture_fails_closed(self) -> None:
        fixture = build_synthetic_fixture("positive_clean")
        with self.assertRaisesRegex(
            KP1979SyntheticControlError,
            "differs from the canonical generator",
        ):
            evaluate_synthetic_fixture(replace(fixture, pbm_bytes=fixture.pbm_bytes[:-1]))
        with self.assertRaisesRegex(
            KP1979SyntheticControlError,
            "not in the fixed roster",
        ):
            build_synthetic_fixture("unregistered_case")

    def test_current_v1_negative_result_is_preserved_without_retuning(self) -> None:
        report = run_synthetic_control()
        self.assertEqual("not_qualified", report.status)
        self.assertEqual(TARGET_ALGORITHM_ID, report.target_algorithm_id)
        self.assertEqual(SYNTHETIC_CASE_COUNT, report.case_count)
        self.assertEqual(SYNTHETIC_POSITIVE_CASE_COUNT, report.positive_case_count)
        self.assertEqual(SYNTHETIC_NEGATIVE_CASE_COUNT, report.negative_case_count)
        self.assertEqual(11, report.passed_case_count)
        self.assertEqual(
            {
                "positive_thin_strokes",
                "negative_periodic_non_label_bands",
            },
            {case.case_id for case in report.cases if not case.passed},
        )
        periodic = next(
            case for case in report.cases if case.case_id == "negative_periodic_non_label_bands"
        )
        self.assertEqual("proposed", periodic.detector_status)
        self.assertFalse(periodic.negative_control_empty)
        self.assertEqual(62, periodic.prediction_count)

    def test_all_metamorphic_relations_pass_and_report_is_reproducible(self) -> None:
        first = run_synthetic_control()
        second = run_synthetic_control()
        self.assertEqual(first, second)
        self.assertEqual(
            SYNTHETIC_METAMORPHIC_CHECK_COUNT,
            len(first.metamorphic_checks),
        )
        self.assertTrue(all(check.passed for check in first.metamorphic_checks))
        self.assertEqual(
            {
                "identical_input_reproducibility",
                "unread_top_margin_invariance",
                "vertical_translation_equivariance",
            },
            {check.relation_id for check in first.metamorphic_checks},
        )

    def test_report_nonclaims_are_fixed_false(self) -> None:
        report = run_synthetic_control()
        self.assertEqual("synthetic_control", report.reference_use)
        self.assertTrue(report.synthetic_only)
        self.assertFalse(report.real_accuracy)
        self.assertFalse(report.reference_accepted)
        self.assertFalse(report.future_evaluation_opened)
        self.assertFalse(report.reserved_sources_read)
        self.assertFalse(report.decipherment)
        self.assertFalse(report.prize_submission_eligible)
        self.assertTrue(
            all(case.detector_algorithm_id == TARGET_ALGORITHM_ID for case in report.cases)
        )

    def test_module_import_boundary_excludes_real_and_reserved_sources(self) -> None:
        module_path = ROOT / "src" / "indusbench" / "kp1979_synthetic_control.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.setdefault(node.module, set()).update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.setdefault(alias.name, set())

        self.assertEqual(
            {
                "LaneLatticeProposal",
                "TwoColumnLayoutProposal",
                "detect_two_column_label_lattice",
            },
            imported["indusbench.printed_concordance_layout"],
        )
        forbidden_modules = {
            "indusbench.kp1979",
            "indusbench.kp1979_label_reference",
            "indusbench.kp1979_row_assignment",
            "indusbench.mtaac",
            "indusbench.mtaac_control",
            "indusbench.oracc_ed3b",
            "indusbench.v3dev",
            "indusbench.v4dev",
            "indusbench.v5dev",
        }
        self.assertTrue(forbidden_modules.isdisjoint(imported))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"open", "exec", "eval", "__import__"}.isdisjoint(called_names))


if __name__ == "__main__":
    unittest.main()
