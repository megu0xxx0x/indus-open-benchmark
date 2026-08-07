from __future__ import annotations

import unittest
from typing import Any

from indusbench.kp1979_glyph_match import MatcherConfig, build_template_index
from indusbench.kp1979_row_separator import (
    ROW_SEPARATOR_METHOD,
    KP1979RowSeparatorError,
    match_row_with_separator,
)

Glyph = tuple[str, ...]


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


def row_pbm(
    glyphs: tuple[Glyph, ...],
    *,
    gaps: tuple[int, ...],
    left_padding: int = 1,
    right_padding: int = 1,
) -> bytes:
    if len(gaps) != len(glyphs) - 1:
        raise AssertionError("one synthetic gap is required between adjacent glyphs")
    height = len(glyphs[0])
    if any(len(glyph) != height for glyph in glyphs):
        raise AssertionError("synthetic glyph heights must agree")
    rows = ["." * left_padding for _ in range(height)]
    for glyph_index, glyph in enumerate(glyphs):
        rows = [left + right for left, right in zip(rows, glyph, strict=True)]
        if glyph_index < len(gaps):
            rows = [row + "." * gaps[glyph_index] for row in rows]
    rows = [row + "." * right_padding for row in rows]
    blank = "." * len(rows[0])
    return pbm(blank, *rows, blank)


def loose_config(**changes: Any) -> MatcherConfig:
    values: dict[str, int | bool] = {
        "max_token_cost": 1_250_000,
        "min_different_rank_margin": 1,
        "min_path_margin": 1,
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


CROSS: Glyph = (
    "..#..",
    "..#..",
    "#####",
    "..#..",
    "..#..",
)
BOX: Glyph = (
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####",
)
TWO_BARS: Glyph = (
    "#...#",
    "#...#",
    "#...#",
    "#...#",
    "#...#",
)
VERTICAL_BAR: Glyph = ("#", "#", "#", "#", "#")
DAMAGED_TWO_BARS: Glyph = (
    "#...#",
    "#....",
    "#...#",
    "#...#",
    "#...#",
)


class RowSeparatorTests(unittest.TestCase):
    def test_locator_x0_crosses_final_glyph_but_is_never_used_as_cut(self) -> None:
        row = row_pbm((CROSS, BOX), gaps=(3,))
        index = build_template_index([("cross", 1, pbm(*CROSS)), ("box", 2, pbm(*BOX))])
        locator = (3, 1, 14, 6)
        result = match_row_with_separator(
            row_id="locator-crosses-final-glyph",
            row_pbm=row,
            proposed_label_bbox=locator,
            index=index,
            config=loose_config(),
        )

        self.assertEqual("proposed", result["proposal_status"])
        self.assertEqual("none", result["abstention_code"])
        self.assertEqual(ROW_SEPARATOR_METHOD, result["separator_method"])
        best = result["candidate_paths"][0]
        provenance = best["separator_provenance"]
        self.assertEqual(
            {
                "candidate_index",
                "full_height_white_gap_bbox",
                "locator_relation",
                "locator_intersection_bbox",
                "cut_x",
            },
            set(provenance),
        )
        self.assertEqual([6, 0, 9, 7], provenance["full_height_white_gap_bbox"])
        self.assertEqual("positive_overlap", provenance["locator_relation"])
        self.assertEqual([6, 1, 9, 6], provenance["locator_intersection_bbox"])
        self.assertEqual(9, provenance["cut_x"])
        self.assertNotEqual(locator[0], provenance["cut_x"])
        self.assertEqual(1, best["segments"][0]["catalog_rank"])
        self.assertEqual(
            {
                "row_id",
                "visual_order",
                "proposed_label_bbox",
                "separator_method",
                "proposal_status",
                "abstention_code",
                "candidate_paths",
                "gates",
            },
            set(result),
        )

    def test_final_glyph_large_internal_gap_is_compared_not_blindly_cut(self) -> None:
        row = row_pbm((TWO_BARS, BOX), gaps=(3,))
        index = build_template_index([("two-bars", 7, pbm(*TWO_BARS)), ("box", 2, pbm(*BOX))])
        result = match_row_with_separator(
            row_id="internal-gap",
            row_pbm=row,
            # This locator intersects both the sign's internal gap [2,5) and
            # the actual sign/label whitespace [6,9).
            proposed_label_bbox=(3, 1, 14, 6),
            index=index,
            config=loose_config(),
        )

        self.assertEqual("segmentation_ambiguous", result["proposal_status"])
        self.assertEqual("competing_separator_alternatives", result["abstention_code"])
        self.assertFalse(result["gates"]["separator_consensus_passed"])
        best = result["candidate_paths"][0]
        self.assertEqual(1, best["separator_provenance"]["candidate_index"])
        self.assertEqual(
            [6, 0, 9, 7],
            best["separator_provenance"]["full_height_white_gap_bbox"],
        )
        self.assertEqual(7, best["segments"][0]["catalog_rank"])
        observed_gaps = {
            tuple(path["separator_provenance"]["full_height_white_gap_bbox"])
            for path in result["candidate_paths"]
        }
        self.assertIn((2, 0, 5, 7), observed_gaps)

    def test_internal_gap_only_locator_also_compares_nearest_right_boundary(self) -> None:
        row = row_pbm((TWO_BARS, BOX), gaps=(3,))
        index = build_template_index(
            [
                ("two-bars", 7, pbm(*TWO_BARS)),
                ("vertical-bar", 8, pbm(*VERTICAL_BAR)),
                ("box", 2, pbm(*BOX)),
            ]
        )
        result = match_row_with_separator(
            row_id="internal-only-locator",
            row_pbm=row,
            # Only the TWO_BARS internal gap overlaps this locator.  The true
            # sign/label boundary must be added as the nearest gap on its right.
            proposed_label_bbox=(3, 1, 4, 6),
            index=index,
            config=loose_config(),
        )

        self.assertEqual("segmentation_ambiguous", result["proposal_status"])
        self.assertEqual("competing_separator_alternatives", result["abstention_code"])
        by_relation = {
            path["separator_provenance"]["locator_relation"]: path
            for path in result["candidate_paths"]
        }
        self.assertIn("positive_overlap", by_relation)
        self.assertIn("nearest_right", by_relation)
        nearest = by_relation["nearest_right"]["separator_provenance"]
        self.assertEqual([6, 0, 9, 7], nearest["full_height_white_gap_bbox"])
        self.assertIsNone(nearest["locator_intersection_bbox"])

    def test_zero_cost_truncated_prefix_conflicts_with_damaged_full_sign(self) -> None:
        row = row_pbm((DAMAGED_TWO_BARS, BOX), gaps=(3,))
        index = build_template_index(
            [
                ("two-bars", 7, pbm(*TWO_BARS)),
                ("vertical-bar", 8, pbm(*VERTICAL_BAR)),
                ("box", 2, pbm(*BOX)),
            ]
        )
        result = match_row_with_separator(
            row_id="damaged-final-stroke",
            row_pbm=row,
            proposed_label_bbox=(3, 1, 4, 6),
            index=index,
            config=loose_config(),
        )

        self.assertEqual(0, result["candidate_paths"][0]["total_cost"])
        self.assertEqual(
            "positive_overlap",
            result["candidate_paths"][0]["separator_provenance"]["locator_relation"],
        )
        self.assertEqual(8, result["candidate_paths"][0]["segments"][0]["catalog_rank"])
        self.assertEqual("segmentation_ambiguous", result["proposal_status"])
        self.assertEqual("competing_separator_alternatives", result["abstention_code"])
        self.assertFalse(result["gates"]["separator_consensus_passed"])
        self.assertTrue(
            any(
                path["separator_provenance"]["locator_relation"] == "nearest_right"
                for path in result["candidate_paths"]
            )
        )

    def test_observed_gap_contacting_tight_locator_left_edge_is_used(self) -> None:
        row = row_pbm((CROSS, BOX), gaps=(3,))
        index = build_template_index([("cross", 1, pbm(*CROSS)), ("box", 2, pbm(*BOX))])
        # The tight locator begins on the first label-ink column.  The maximal
        # observed white gap ends exactly there, so its geometric intersection
        # with the locator has zero width without becoming an x0-derived cut.
        locator = (9, 1, 14, 6)
        result = match_row_with_separator(
            row_id="left-contact",
            row_pbm=row,
            proposed_label_bbox=locator,
            index=index,
            config=loose_config(),
        )

        self.assertEqual("proposed", result["proposal_status"])
        provenance = result["candidate_paths"][0]["separator_provenance"]
        self.assertEqual([6, 0, 9, 7], provenance["full_height_white_gap_bbox"])
        self.assertEqual("left_edge_contact", provenance["locator_relation"])
        self.assertEqual([9, 1, 9, 6], provenance["locator_intersection_bbox"])
        self.assertEqual(locator[0], provenance["cut_x"])
        self.assertEqual(ROW_SEPARATOR_METHOD, result["separator_method"])

        right_contact_only = match_row_with_separator(
            row_id="right-contact-is-not-intersection",
            row_pbm=row,
            proposed_label_bbox=(1, 1, 6, 6),
            index=index,
            config=loose_config(),
        )
        self.assertEqual("proposed", right_contact_only["proposal_status"])
        self.assertEqual(
            "right_edge_contact",
            right_contact_only["candidate_paths"][0]["separator_provenance"]["locator_relation"],
        )
        self.assertEqual(
            [6, 1, 6, 6],
            right_contact_only["candidate_paths"][0]["separator_provenance"][
                "locator_intersection_bbox"
            ],
        )

        nearest_left_only = match_row_with_separator(
            row_id="nearest-left",
            row_pbm=row,
            proposed_label_bbox=(10, 1, 13, 6),
            index=index,
            config=loose_config(),
        )
        nearest_left_provenance = nearest_left_only["candidate_paths"][0]["separator_provenance"]
        self.assertEqual("nearest_left", nearest_left_provenance["locator_relation"])
        self.assertIsNone(nearest_left_provenance["locator_intersection_bbox"])

    def test_suffix_digits_that_resemble_glyphs_force_safe_abstention(self) -> None:
        row = row_pbm((BOX, CROSS, CROSS), gaps=(3, 3))
        index = build_template_index([("cross", 1, pbm(*CROSS)), ("box", 2, pbm(*BOX))])
        result = match_row_with_separator(
            row_id="glyph-like-suffix",
            row_pbm=row,
            proposed_label_bbox=(7, 1, 21, 6),
            index=index,
            config=loose_config(),
        )

        self.assertEqual("segmentation_ambiguous", result["proposal_status"])
        self.assertEqual("competing_separator_alternatives", result["abstention_code"])
        self.assertFalse(result["gates"]["separator_consensus_passed"])
        self.assertEqual(
            [[2], [2, 1]],
            [
                [segment["catalog_rank"] for segment in path["segments"]]
                for path in result["candidate_paths"][:2]
            ],
        )

    def test_multiple_conflicting_gaps_retain_deterministic_global_top_three(self) -> None:
        row = row_pbm((CROSS, BOX, CROSS, BOX), gaps=(3, 3, 3))
        index = build_template_index([("cross", 1, pbm(*CROSS)), ("box", 2, pbm(*BOX))])
        arguments = {
            "row_id": "global-top-three",
            "row_pbm": row,
            "proposed_label_bbox": (7, 1, 29, 6),
            "index": index,
            "config": loose_config(),
        }
        first = match_row_with_separator(**arguments)
        second = match_row_with_separator(**arguments)

        self.assertEqual(first, second)
        self.assertEqual("segmentation_ambiguous", first["proposal_status"])
        self.assertEqual(3, len(first["candidate_paths"]))
        self.assertEqual(
            [0, 1, 2],
            [path["separator_provenance"]["candidate_index"] for path in first["candidate_paths"]],
        )
        self.assertEqual([0, 0, 0], [path["total_cost"] for path in first["candidate_paths"]])
        self.assertEqual([0, 0, 0], [path["margin_from_best"] for path in first["candidate_paths"]])

    def test_no_observed_separator_fails_closed(self) -> None:
        row = row_pbm((CROSS, BOX), gaps=(0,))
        index = build_template_index([("cross", 1, pbm(*CROSS)), ("box", 2, pbm(*BOX))])
        result = match_row_with_separator(
            row_id="no-separator",
            row_pbm=row,
            proposed_label_bbox=(3, 1, 11, 6),
            index=index,
            config=loose_config(),
        )

        self.assertEqual("no_match", result["proposal_status"])
        self.assertEqual(
            "no_full_height_white_gap_intersects_locator",
            result["abstention_code"],
        )
        self.assertEqual([], result["candidate_paths"])
        self.assertFalse(result["gates"]["separator_found"])

    def test_edge_contact_is_preserved_as_unknown_damage(self) -> None:
        row = row_pbm((CROSS, BOX), gaps=(3,), left_padding=0)
        index = build_template_index([("cross", 1, pbm(*CROSS)), ("box", 2, pbm(*BOX))])
        result = match_row_with_separator(
            row_id="edge-contact",
            row_pbm=row,
            proposed_label_bbox=(4, 1, 12, 6),
            index=index,
            config=loose_config(),
        )

        self.assertEqual("unknown_damage", result["proposal_status"])
        self.assertEqual("sign_region_boundary_contains_ink", result["abstention_code"])
        self.assertFalse(result["gates"]["best_matcher_proposed"])
        best = result["candidate_paths"][0]
        self.assertEqual("unknown_damage", best["matcher_proposal_status"])
        self.assertFalse(best["matcher_gates"]["sign_region_boundary_clear"])

    def test_invalid_row_relative_locator_is_rejected(self) -> None:
        row = row_pbm((CROSS, BOX), gaps=(3,))
        index = build_template_index([("cross", 1, pbm(*CROSS))])
        with self.assertRaisesRegex(KP1979RowSeparatorError, "outside the row crop"):
            match_row_with_separator(
                row_id="invalid-locator",
                row_pbm=row,
                proposed_label_bbox=(3, 1, 10_000, 6),
                index=index,
                config=loose_config(),
            )


if __name__ == "__main__":
    unittest.main()
