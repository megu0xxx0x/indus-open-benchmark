from __future__ import annotations

import unittest

from indusbench.printed_concordance_layout import (
    MAX_REPEATED_STRIPES,
    PrintedConcordanceLayoutError,
    detect_two_column_label_lattice,
)

WIDTH = 4880
HEIGHT = 7010
ROW_BYTES = WIDTH // 8
SCAN_BANDS = ((2056, 550, 2316, 6600), (4232, 550, 4492, 6600))


def synthetic_pbm(
    *,
    left_pitch: int = 165,
    right_pitch: int = 165,
    left_every: int = 1,
    extra_columns: tuple[tuple[int, int], ...] = (),
) -> bytes:
    payload = bytearray(ROW_BYTES * HEIGHT)

    def black_rectangle(x0: int, y0: int, x1: int, y1: int) -> None:
        for y in range(y0, y1):
            row_offset = y * ROW_BYTES
            for x in range(x0, x1):
                payload[row_offset + x // 8] |= 128 >> (x % 8)

    def label_lattice(x0: int, x1: int, pitch: int, *, every: int = 1) -> None:
        for index, y in enumerate(range(620, 6500, pitch)):
            if index % every:
                continue
            black_rectangle(x0, y, x1, y + 34)
            black_rectangle(x0 + 18, y + 48, x1, y + 82)

    label_lattice(2110, 2280, left_pitch, every=left_every)
    label_lattice(4310, 4480, right_pitch)
    for x0, x1 in extra_columns:
        label_lattice(x0, x1, left_pitch)
    return f"P4\n{WIDTH} {HEIGHT}\n".encode("ascii") + bytes(payload)


class PrintedConcordanceLayoutTests(unittest.TestCase):
    def test_regular_two_column_lattice_is_proposed_deterministically(self) -> None:
        page = synthetic_pbm()
        first = detect_two_column_label_lattice(
            page,
            width=WIDTH,
            height=HEIGHT,
            scan_bands=SCAN_BANDS,
        )
        second = detect_two_column_label_lattice(
            page,
            width=WIDTH,
            height=HEIGHT,
            scan_bands=SCAN_BANDS,
        )
        self.assertEqual(first, second)
        self.assertEqual("proposed", first.detection_status)
        self.assertEqual(2, len(first.lanes))
        self.assertTrue(all(len(lane.candidate_y) >= 35 for lane in first.lanes))

    def test_blank_page_abstains(self) -> None:
        page = f"P4\n{WIDTH} {HEIGHT}\n".encode("ascii") + bytes(ROW_BYTES * HEIGHT)
        result = detect_two_column_label_lattice(
            page,
            width=WIDTH,
            height=HEIGHT,
            scan_bands=SCAN_BANDS,
        )
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("insufficient_lane_signal", result.abstention_codes)

    def test_different_lane_pitches_abstain(self) -> None:
        result = detect_two_column_label_lattice(
            synthetic_pbm(left_pitch=165, right_pitch=172),
            width=WIDTH,
            height=HEIGHT,
            scan_bands=SCAN_BANDS,
        )
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("lane_pitch_disagreement", result.abstention_codes)

    def test_each_lane_needs_a_contiguous_run(self) -> None:
        result = detect_two_column_label_lattice(
            synthetic_pbm(left_every=2),
            width=WIDTH,
            height=HEIGHT,
            scan_bands=SCAN_BANDS,
        )
        self.assertGreaterEqual(len(result.lanes[0].candidate_y), 15)
        self.assertLess(result.lanes[0].longest_contiguous_run, 18)
        self.assertGreaterEqual(result.lanes[1].longest_contiguous_run, 18)
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("insufficient_contiguous_run", result.abstention_codes)

    def test_many_repeated_columns_are_a_hard_confound(self) -> None:
        extra_columns = tuple((x, min(x + 150, WIDTH)) for x in range(200, 4700, 190))
        result = detect_two_column_label_lattice(
            synthetic_pbm(extra_columns=extra_columns),
            width=WIDTH,
            height=HEIGHT,
            scan_bands=SCAN_BANDS,
        )
        self.assertEqual("abstained", result.detection_status)
        self.assertIn("multi_column_confound", result.abstention_codes)
        self.assertGreater(result.repeated_stripe_count, MAX_REPEATED_STRIPES)

    def test_noncanonical_pbm_and_wrong_scan_space_fail_closed(self) -> None:
        page = synthetic_pbm()
        with self.assertRaisesRegex(PrintedConcordanceLayoutError, "PBM header"):
            detect_two_column_label_lattice(
                page.replace(b"P4\n", b"P1\n", 1),
                width=WIDTH,
                height=HEIGHT,
                scan_bands=SCAN_BANDS,
            )
        with self.assertRaisesRegex(PrintedConcordanceLayoutError, "scan band"):
            detect_two_column_label_lattice(
                page,
                width=WIDTH,
                height=HEIGHT,
                scan_bands=((2056, 0, 2316, 6600), SCAN_BANDS[1]),
            )


if __name__ == "__main__":
    unittest.main()
