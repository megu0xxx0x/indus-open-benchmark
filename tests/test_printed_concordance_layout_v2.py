from __future__ import annotations

import ast
import unittest
from pathlib import Path

from indusbench.kp1979_synthetic_control import (
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_SCAN_BANDS,
    build_synthetic_fixture,
)
from indusbench.printed_concordance_layout_v2 import (
    DETECTOR_ALGORITHM_ID,
    PrintedConcordanceLayoutV2Error,
    detect_two_column_label_lattice_v2,
)

ROOT = Path(__file__).resolve().parents[1]
HEADER = b"P4\n4880 7010\n"
ROW_BYTES = SYNTHETIC_PAGE_WIDTH // 8

POSITIVE_V1_REGRESSIONS = (
    "positive_clean",
    "positive_pitch_158",
    "positive_pitch_172",
    "positive_phase_shift",
    "positive_y_jitter",
    "positive_thin_strokes",
    "positive_partial_lanes",
)
NEGATIVE_V1_REGRESSIONS = (
    "negative_blank",
    "negative_single_lane",
    "negative_pitch_mismatch",
    "negative_discontinuous_lane",
    "negative_multi_column",
    "negative_periodic_non_label_bands",
)


def _detect(pbm_bytes: bytes):
    return detect_two_column_label_lattice_v2(
        pbm_bytes,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )


def _paint_rectangle(
    payload: bytearray,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> None:
    for y in range(y0, y1):
        row_offset = y * ROW_BYTES
        for x in range(x0, x1):
            payload[row_offset + x // 8] |= 128 >> (x % 8)


def _copy_ink_column(
    payload: bytearray,
    source_pbm: bytes,
    *,
    source_x0: int,
    target_x0: int,
) -> None:
    source_payload = source_pbm[len(HEADER) :]
    for y in range(550, 6600):
        source_offset = y * ROW_BYTES
        target_offset = y * ROW_BYTES
        for delta_x in range(100):
            source_x = source_x0 + delta_x
            if source_payload[source_offset + source_x // 8] & (128 >> (source_x % 8)):
                target_x = target_x0 + delta_x
                payload[target_offset + target_x // 8] |= 128 >> (target_x % 8)


class PrintedConcordanceLayoutV2Tests(unittest.TestCase):
    def test_algorithm_identity_and_output_are_deterministic(self) -> None:
        fixture = build_synthetic_fixture("positive_clean")
        first = _detect(fixture.pbm_bytes)
        second = _detect(fixture.pbm_bytes)
        self.assertEqual(first, second)
        self.assertEqual("two-column-label-lattice-v2", DETECTOR_ALGORITHM_ID)
        self.assertEqual(DETECTOR_ALGORITHM_ID, first.algorithm_id)
        self.assertEqual("proposed", first.detection_status)

    def test_exposed_v1_positive_cases_have_exact_anchor_coverage(self) -> None:
        for case_id in POSITIVE_V1_REGRESSIONS:
            with self.subTest(case_id=case_id):
                fixture = build_synthetic_fixture(case_id)
                result = _detect(fixture.pbm_bytes)
                self.assertEqual("proposed", result.detection_status)
                for lane_index, lane in enumerate(result.lanes):
                    references = tuple(
                        reference
                        for reference in fixture.references
                        if reference.lane_index == lane_index
                    )
                    anchors = tuple(y0 + 48 for y0 in lane.candidate_y)
                    self.assertEqual(len(references), len(anchors))
                    for reference in references:
                        self.assertEqual(
                            1,
                            sum(reference.y0 <= anchor < reference.y1 for anchor in anchors),
                        )
                    for anchor in anchors:
                        self.assertEqual(
                            1,
                            sum(reference.y0 <= anchor < reference.y1 for reference in references),
                        )

    def test_thin_strokes_preserve_structure_without_an_ink_mass_threshold(self) -> None:
        clean = _detect(build_synthetic_fixture("positive_clean").pbm_bytes)
        thin = _detect(build_synthetic_fixture("positive_thin_strokes").pbm_bytes)
        self.assertEqual("proposed", thin.detection_status)
        self.assertEqual(
            tuple(lane.two_tier_evidence_count for lane in clean.lanes),
            tuple(lane.two_tier_evidence_count for lane in thin.lanes),
        )
        self.assertEqual(
            tuple(lane.aligned_evidence_count for lane in clean.lanes),
            tuple(lane.aligned_evidence_count for lane in thin.lanes),
        )

    def test_exposed_v1_negative_cases_all_abstain(self) -> None:
        for case_id in NEGATIVE_V1_REGRESSIONS:
            with self.subTest(case_id=case_id):
                result = _detect(build_synthetic_fixture(case_id).pbm_bytes)
                self.assertEqual("abstained", result.detection_status)

        periodic = _detect(build_synthetic_fixture("negative_periodic_non_label_bands").pbm_bytes)
        self.assertIn("insufficient_two_tier_evidence", periodic.abstention_codes)
        self.assertTrue(all(not lane.candidate_y for lane in periodic.lanes))

    def test_periodic_solid_two_tier_bars_are_not_glyph_like_evidence(self) -> None:
        blank = build_synthetic_fixture("negative_blank").pbm_bytes
        payload = bytearray(blank[len(HEADER) :])
        for x0, _, _, _ in SYNTHETIC_SCAN_BANDS:
            for y in range(620, 6500, 165):
                _paint_rectangle(
                    payload,
                    x0=x0 + 20,
                    y0=y,
                    x1=x0 + 70,
                    y1=y + 10,
                )
                _paint_rectangle(
                    payload,
                    x0=x0 + 35,
                    y0=y + 16,
                    x1=x0 + 85,
                    y1=y + 26,
                )
        result = _detect(HEADER + bytes(payload))
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("insufficient_two_tier_evidence", result.abstention_codes)
        self.assertTrue(all(not lane.candidate_y for lane in result.lanes))

    def test_many_label_like_columns_are_a_hard_layout_confound(self) -> None:
        clean = build_synthetic_fixture("positive_clean").pbm_bytes
        blank = build_synthetic_fixture("negative_blank").pbm_bytes
        payload = bytearray(blank[len(HEADER) :])
        for target_x0 in (
            200,
            650,
            1100,
            1550,
            2056,
            2500,
            2950,
            3400,
            3850,
            4232,
        ):
            _copy_ink_column(payload, clean, source_x0=2056, target_x0=target_x0)
        result = _detect(HEADER + bytes(payload))
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("multi_column_confound", result.abstention_codes)
        self.assertGreater(result.structured_stripe_count, 6)
        self.assertTrue(all(lane.aligned_evidence_count >= 15 for lane in result.lanes))

    def test_fragmented_input_hits_the_explicit_work_bound(self) -> None:
        blank = build_synthetic_fixture("negative_blank").pbm_bytes
        payload = bytearray(blank[len(HEADER) :])
        for x0, _, _, _ in SYNTHETIC_SCAN_BANDS:
            for y in range(550, 550 + 2 * 514, 2):
                _paint_rectangle(
                    payload,
                    x0=x0 + 20,
                    y0=y,
                    x1=x0 + 22,
                    y1=y + 1,
                )
        result = _detect(HEADER + bytes(payload))
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("excessive_tier_fragmentation", result.abstention_codes)
        self.assertTrue(all(not lane.candidate_y for lane in result.lanes))

    def test_invalid_bitmap_and_scan_geometry_fail_closed(self) -> None:
        page = build_synthetic_fixture("positive_clean").pbm_bytes
        with self.assertRaisesRegex(PrintedConcordanceLayoutV2Error, "PBM header"):
            _detect(page.replace(b"P4\n", b"P1\n", 1))
        with self.assertRaisesRegex(PrintedConcordanceLayoutV2Error, "dimensions"):
            detect_two_column_label_lattice_v2(
                page,
                width=SYNTHETIC_PAGE_WIDTH - 1,
                height=SYNTHETIC_PAGE_HEIGHT,
                scan_bands=SYNTHETIC_SCAN_BANDS,
            )
        with self.assertRaisesRegex(PrintedConcordanceLayoutV2Error, "overlap"):
            detect_two_column_label_lattice_v2(
                page,
                width=SYNTHETIC_PAGE_WIDTH,
                height=SYNTHETIC_PAGE_HEIGHT,
                scan_bands=(
                    SYNTHETIC_SCAN_BANDS[0],
                    (2200, 550, 2460, 6600),
                ),
            )

    def test_module_has_no_real_or_reserved_source_import_surface(self) -> None:
        module_path = ROOT / "src" / "indusbench" / "printed_concordance_layout_v2.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertTrue(all(not module.startswith("indusbench") for module in imported_modules))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"open", "exec", "eval", "__import__"}.isdisjoint(called_names))


if __name__ == "__main__":
    unittest.main()
