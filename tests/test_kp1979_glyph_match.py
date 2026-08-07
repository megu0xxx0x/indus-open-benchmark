from __future__ import annotations

import unittest
from typing import Any

from indusbench.kp1979_glyph_match import (
    KP1979GlyphMatchError,
    MatcherConfig,
    TemplateIndex,
    build_template_index,
    match_row_sequence,
    parse_canonical_pbm,
)


def pbm(*rows: str) -> bytes:
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise AssertionError("synthetic PBM rows must be rectangular")
    width = len(rows[0])
    row_bytes = (width + 7) // 8
    payload = bytearray()
    for row in rows:
        value = 0
        for symbol in row:
            value = (value << 1) | (1 if symbol == "#" else 0)
        value <<= row_bytes * 8 - width
        payload.extend(value.to_bytes(row_bytes, "big"))
    return f"P4\n{width} {len(rows)}\n".encode() + bytes(payload)


def loose_config(**changes: Any) -> MatcherConfig:
    values: dict[str, int | bool] = {
        "max_token_cost": 1_250_000,
        "min_different_rank_margin": 1,
        "min_path_margin": 0,
        "unknown_edge_cost": 4_500_000,
        "cut_gap_support_ppm": 125_000,
        "max_cut_penalty": 250_000,
        "candidate_aspect_slack_ppm": 250_000,
        "top_paths": 3,
        "top_ranks_per_span": 3,
        "require_speck_stability": False,
        "require_shift_stability": False,
    }
    values.update(changes)
    return MatcherConfig.from_mapping(values)


CROSS = pbm(
    "..#..",
    "..#..",
    "#####",
    "..#..",
    "..#..",
)
BOX = pbm(
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####",
)
TWO_BARS = pbm(
    "#...#",
    "#...#",
    "#...#",
    "#...#",
    "#...#",
)
PADDED_CROSS = pbm(
    ".......",
    "...#...",
    "...#...",
    ".#####.",
    "...#...",
    "...#...",
    ".......",
)
PADDED_BOX = pbm(
    ".......",
    ".#####.",
    ".#...#.",
    ".#...#.",
    ".#...#.",
    ".#####.",
    ".......",
)


class CanonicalPBMTests(unittest.TestCase):
    def test_parses_exact_raw_pbm_and_rejects_nonzero_padding(self) -> None:
        mask = parse_canonical_pbm(pbm("#..", ".#."))
        self.assertEqual((3, 2), (mask.width, mask.height))
        self.assertEqual((0b100, 0b010), mask.rows)

        malformed = b"P4\n3 1\n" + bytes([0b10000001])
        with self.assertRaisesRegex(KP1979GlyphMatchError, "unused low bits"):
            parse_canonical_pbm(malformed)

    def test_rejects_comments_trailing_bytes_and_empty_templates(self) -> None:
        for malformed in (
            b"P4\n# comment\n3 1\n\x80",
            b"P4\n3 1\n\x80\x00",
            b"P1\n3 1\n1 0 0\n",
        ):
            with self.subTest(malformed=malformed), self.assertRaises(KP1979GlyphMatchError):
                parse_canonical_pbm(malformed)
        with self.assertRaisesRegex(KP1979GlyphMatchError, "iterator is empty"):
            build_template_index([])

    def test_rejects_dimension_text_before_unbounded_integer_conversion(self) -> None:
        with self.assertRaisesRegex(KP1979GlyphMatchError, "dimension text"):
            parse_canonical_pbm(b"P4\n999999 1\n")


class JointGlyphMatchTests(unittest.TestCase):
    def test_exact_shape_is_a_proposal_without_claiming_reading_direction(self) -> None:
        index = build_template_index([("cross", 1, CROSS), ("box", 2, BOX), ("bars", 3, TWO_BARS)])
        result = match_row_sequence(
            row_id="synthetic-row",
            row_pbm=PADDED_CROSS,
            sign_region_bbox=(0, 0, 7, 7),
            index=index,
            config=loose_config(),
        )
        self.assertEqual("proposed", result["proposal_status"])
        self.assertEqual(
            "left_to_right_coordinate_order_not_reading_direction",
            result["visual_order"],
        )
        best = result["candidate_paths"][0]
        self.assertEqual(1, len(best["segments"]))
        self.assertEqual(1, best["segments"][0]["catalog_rank"])
        self.assertEqual(0, best["segments"][0]["emission_cost"])
        self.assertNotIn("accepted_sign_sequence", repr(result))

    def test_internal_white_columns_remain_one_joint_segment(self) -> None:
        index = build_template_index([("bars", 7, TWO_BARS), ("cross", 8, CROSS), ("box", 9, BOX)])
        result = match_row_sequence(
            row_id="disconnected-sign",
            row_pbm=TWO_BARS,
            sign_region_bbox=(0, 0, 5, 5),
            index=index,
            config=loose_config(),
        )
        best_segments = result["candidate_paths"][0]["segments"]
        self.assertEqual(1, len(best_segments))
        self.assertEqual(7, best_segments[0]["catalog_rank"])

    def test_joint_search_segments_two_signs_instead_of_greedy_runs(self) -> None:
        row = pbm(
            "..#.......#####",
            "..#.......#...#",
            "#####.....#...#",
            "..#.......#...#",
            "..#.......#####",
        )
        index = build_template_index([("cross", 1, CROSS), ("box", 2, BOX), ("bars", 3, TWO_BARS)])
        result = match_row_sequence(
            row_id="two-signs",
            row_pbm=row,
            sign_region_bbox=(0, 0, 15, 5),
            index=index,
            config=loose_config(),
        )
        segments = result["candidate_paths"][0]["segments"]
        self.assertEqual([1, 2], [segment["catalog_rank"] for segment in segments])
        self.assertEqual([[0, 0, 5, 5], [10, 0, 15, 5]], [s["segment_bbox"] for s in segments])

    def test_variant_multiplicity_does_not_change_rank_score(self) -> None:
        baseline = build_template_index(
            [("cross-a", 1, CROSS), ("box", 2, BOX), ("bars", 3, TWO_BARS)]
        )
        duplicated = build_template_index(
            [
                ("cross-a", 1, CROSS),
                ("cross-b", 1, CROSS),
                ("cross-c", 1, CROSS),
                ("box", 2, BOX),
                ("bars", 3, TWO_BARS),
            ]
        )
        arguments = {
            "row_id": "multiplicity",
            "row_pbm": CROSS,
            "sign_region_bbox": (0, 0, 5, 5),
            "config": loose_config(),
        }
        first = match_row_sequence(index=baseline, **arguments)
        second = match_row_sequence(index=duplicated, **arguments)
        first_best = first["candidate_paths"][0]["segments"][0]
        second_best = second["candidate_paths"][0]["segments"][0]
        for field in (
            "catalog_rank",
            "overlap_cost",
            "aspect_cost",
            "emission_cost",
            "different_rank_margin",
        ):
            self.assertEqual(first_best[field], second_best[field])
        self.assertEqual(["cross-a"], first_best["best_variant_ids"])
        self.assertEqual(
            ["cross-a", "cross-b", "cross-c"],
            second_best["best_variant_ids"],
        )

    def test_top_three_paths_are_deterministic_and_fourth_is_truncated(self) -> None:
        index = build_template_index([(f"same-{rank}", rank, CROSS) for rank in range(1, 5)])
        self.assertEqual(
            frozenset({"same-1", "same-2", "same-3", "same-4"}),
            index.cross_rank_normalized_variant_ids,
        )
        arguments = {
            "row_id": "tie",
            "row_pbm": PADDED_CROSS,
            "sign_region_bbox": (0, 0, 7, 7),
            "index": index,
            "config": loose_config(),
        }
        first = match_row_sequence(**arguments)
        second = match_row_sequence(**arguments)
        self.assertEqual(first, second)
        self.assertEqual(3, len(first["candidate_paths"]))
        self.assertEqual(
            [1, 2, 3],
            [path["segments"][0]["catalog_rank"] for path in first["candidate_paths"]],
        )
        self.assertEqual("ambiguous", first["proposal_status"])

    def test_close_different_rank_and_strict_absolute_gate_abstain(self) -> None:
        tied = build_template_index([("same-a", 1, CROSS), ("same-b", 2, CROSS)])
        ambiguous = match_row_sequence(
            row_id="close-rank",
            row_pbm=PADDED_CROSS,
            sign_region_bbox=(0, 0, 7, 7),
            index=tied,
            config=loose_config(min_different_rank_margin=1),
        )
        self.assertEqual("ambiguous", ambiguous["proposal_status"])
        self.assertFalse(ambiguous["gates"]["different_rank_margin_passed"])

        distinct = build_template_index([("cross", 1, CROSS), ("box", 2, BOX)])
        strict = match_row_sequence(
            row_id="strict-cost",
            row_pbm=PADDED_BOX,
            sign_region_bbox=(0, 0, 7, 7),
            index=distinct,
            config=loose_config(max_token_cost=0, min_different_rank_margin=0),
        )
        self.assertEqual("proposed", strict["proposal_status"])
        damaged = pbm(
            "#####",
            "#####",
            "#####",
            "#####",
            "#####",
        )
        rejected = match_row_sequence(
            row_id="strict-cost-damaged",
            row_pbm=damaged,
            sign_region_bbox=(0, 0, 5, 5),
            index=distinct,
            config=loose_config(max_token_cost=0, min_different_rank_margin=0),
        )
        self.assertNotEqual("proposed", rejected["proposal_status"])

    def test_blank_region_is_no_match(self) -> None:
        index = build_template_index([("cross", 1, CROSS)])
        blank = pbm(".....", ".....", ".....")
        result = match_row_sequence(
            row_id="blank",
            row_pbm=blank,
            sign_region_bbox=(0, 0, 5, 3),
            index=index,
            config=loose_config(),
        )
        self.assertEqual("no_match", result["proposal_status"])
        self.assertEqual([], result["candidate_paths"])

    def test_aspect_rejection_of_partial_span_does_not_hide_later_exact_span(self) -> None:
        sparse_rows = ["#...#....#", ".........#"] + [".........#"] * 8
        sparse = pbm(*sparse_rows)
        padded = pbm(
            "............",
            *[f".{row}." for row in sparse_rows],
            "............",
        )
        index = build_template_index([("sparse", 1, sparse), ("box", 2, BOX)])
        result = match_row_sequence(
            row_id="aspect-recovery",
            row_pbm=padded,
            sign_region_bbox=(0, 0, 12, 12),
            index=index,
            config=loose_config(),
        )
        best = result["candidate_paths"][0]["segments"]
        self.assertEqual(1, len(best))
        self.assertEqual(1, best[0]["catalog_rank"])
        self.assertEqual(0, best[0]["emission_cost"])

    def test_rank_tie_and_segmentation_tie_have_different_abstentions(self) -> None:
        rank_tie = build_template_index([("same-1", 1, CROSS), ("same-2", 2, CROSS)])
        rank_result = match_row_sequence(
            row_id="rank-tie",
            row_pbm=PADDED_CROSS,
            sign_region_bbox=(0, 0, 7, 7),
            index=rank_tie,
            config=loose_config(min_different_rank_margin=0, min_path_margin=1),
        )
        self.assertEqual("ambiguous", rank_result["proposal_status"])
        self.assertEqual("joint_rank_path_margin_gate_failed", rank_result["abstention_code"])

        combined_rows = (
            "..#.......#####",
            "..#.......#...#",
            "#####.....#...#",
            "..#.......#...#",
            "..#.......#####",
        )
        combined = pbm(*combined_rows)
        padded_combined = pbm(
            ".................",
            *[f".{row}." for row in combined_rows],
            ".................",
        )
        segmentation_tie = build_template_index(
            [("cross", 1, CROSS), ("box", 2, BOX), ("combined", 3, combined)]
        )
        segmentation_result = match_row_sequence(
            row_id="segmentation-tie",
            row_pbm=padded_combined,
            sign_region_bbox=(0, 0, 17, 7),
            index=segmentation_tie,
            config=loose_config(
                min_path_margin=1,
                cut_gap_support_ppm=0,
                max_cut_penalty=0,
            ),
        )
        self.assertEqual("segmentation_ambiguous", segmentation_result["proposal_status"])
        self.assertEqual(
            "joint_segmentation_path_margin_gate_failed",
            segmentation_result["abstention_code"],
        )

    def test_edge_touch_is_damage_and_excessive_runs_fail_closed(self) -> None:
        index = build_template_index([("cross", 1, CROSS), ("box", 2, BOX)])
        edge_touch = match_row_sequence(
            row_id="edge-touch",
            row_pbm=CROSS,
            sign_region_bbox=(0, 0, 5, 5),
            index=index,
            config=loose_config(),
        )
        self.assertEqual("unknown_damage", edge_touch["proposal_status"])
        self.assertEqual(
            "sign_region_boundary_contains_ink",
            edge_touch["abstention_code"],
        )
        excessive = "#." * 129 + "#"
        wide_row = pbm("." * len(excessive), excessive, "." * len(excessive))
        with self.assertRaisesRegex(KP1979GlyphMatchError, "too many separated"):
            match_row_sequence(
                row_id="excessive-runs",
                row_pbm=wide_row,
                sign_region_bbox=(0, 0, len(excessive), 3),
                index=index,
                config=loose_config(),
            )

    def test_forged_template_index_derived_bound_is_rejected(self) -> None:
        index = build_template_index([("cross", 1, CROSS), ("box", 2, BOX)])
        with self.assertRaisesRegex(KP1979GlyphMatchError, "derived bounds"):
            TemplateIndex(
                index.templates,
                index.max_internal_white_runs,
                index.max_aspect_ppm + 1,
            )


if __name__ == "__main__":
    unittest.main()
