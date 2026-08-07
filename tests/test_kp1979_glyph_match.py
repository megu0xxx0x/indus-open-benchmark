from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace
from typing import Any
from unittest.mock import patch

import indusbench.kp1979_glyph_match as matcher_module
from indusbench.kp1979_glyph_match import (
    KP1979GlyphMatchError,
    MatcherConfig,
    TemplateIndex,
    _match_row_sequence_from_workspace,
    _prepare_row_match_workspace,
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

    def test_prepared_workspace_matches_reference_dict_and_path_order_across_boundaries(
        self,
    ) -> None:
        base_index = build_template_index(
            [("cross", 1, CROSS), ("box", 2, BOX), ("bars", 3, TWO_BARS)]
        )
        tied_index = build_template_index(
            [("same-1", 1, CROSS), ("same-2", 2, CROSS), ("box", 3, BOX)]
        )
        combined = pbm(
            "..#.......#####",
            "..#.......#...#",
            "#####.....#...#",
            "..#.......#...#",
            "..#.......#####",
        )
        padded_combined = pbm(
            ".................",
            *[
                f".{row}."
                for row in (
                    "..#.......#####",
                    "..#.......#...#",
                    "#####.....#...#",
                    "..#.......#...#",
                    "..#.......#####",
                )
            ],
            ".................",
        )
        segmentation_index = build_template_index(
            [("cross", 1, CROSS), ("box", 2, BOX), ("combined", 3, combined)]
        )
        blank = pbm(".....", ".....", ".....")
        specked = pbm(
            ".......",
            ".#.....",
            "...#...",
            "...#...",
            ".#####.",
            "...#...",
            "...#...",
            ".......",
        )
        offset_cross = pbm(
            ".........",
            ".........",
            "....#....",
            "....#....",
            "..#####..",
            "....#....",
            "....#....",
            ".........",
            ".........",
        )
        padded_dot = pbm("...", ".#.", "...")
        dot_index = build_template_index([("dot", 1, pbm("#")), ("cross", 2, CROSS)])
        cases = (
            ("prepared-exact", PADDED_CROSS, (0, 0, 7, 7), base_index),
            ("prepared-joint", padded_combined, (0, 0, 17, 7), segmentation_index),
            ("prepared-tie", PADDED_CROSS, (0, 0, 7, 7), tied_index),
            ("prepared-blank", blank, (0, 0, 5, 3), base_index),
            ("prepared-boundary", CROSS, (0, 0, 5, 5), base_index),
            ("prepared-speck", specked, (0, 0, 7, 8), base_index),
            ("prepared-offset", offset_cross, (1, 1, 8, 8), base_index),
            ("prepared-speck-empty", padded_dot, (0, 0, 3, 3), dot_index),
        )
        configs = (
            loose_config(),
            loose_config(
                max_token_cost=0,
                min_different_rank_margin=0,
                min_path_margin=0,
                cut_gap_support_ppm=0,
                max_cut_penalty=0,
                require_speck_stability=True,
                require_shift_stability=True,
            ),
            loose_config(
                max_token_cost=500_000,
                min_different_rank_margin=100_000,
                min_path_margin=100_000,
                require_speck_stability=True,
                require_shift_stability=True,
            ),
        )
        for row_id, row_pbm, bbox, index in cases:
            workspace = _prepare_row_match_workspace(
                row_id=row_id,
                row_pbm=row_pbm,
                sign_region_bbox=bbox,
                index=index,
                config=configs[0],
            )
            for matcher_config in configs:
                with self.subTest(row_id=row_id, config=matcher_config):
                    reference = match_row_sequence(
                        row_id=row_id,
                        row_pbm=row_pbm,
                        sign_region_bbox=bbox,
                        index=index,
                        config=matcher_config,
                    )
                    prepared = _match_row_sequence_from_workspace(
                        workspace,
                        index=index,
                        config=matcher_config,
                    )
                    self.assertEqual(reference, prepared)
                    self.assertEqual(
                        json.dumps(reference, separators=(",", ":"), sort_keys=False),
                        json.dumps(prepared, separators=(",", ":"), sort_keys=False),
                    )
                    if row_id == "prepared-speck-empty" and matcher_config.require_speck_stability:
                        self.assertFalse(prepared["gates"]["speck_ablation_stability_passed"])

    def test_workspace_cache_is_immutable_index_bound_and_aspect_safe(self) -> None:
        near_square_a = pbm(*(["#" * 55] * 56))
        near_square_b = pbm(*(["#" * 56] * 57))
        index = build_template_index(
            [("near-a", 1, near_square_a), ("near-b", 2, near_square_b), ("cross", 3, CROSS)]
        )
        content_rows = ["#" * 55 + "." * 5 + "#" * 56 for _ in range(56)]
        content_rows.append("." * 60 + "#" * 56)
        row = pbm("." * 118, *[f".{value}." for value in content_rows], "." * 118)
        matcher_config = loose_config()
        workspace = _prepare_row_match_workspace(
            row_id="aspect-isolation",
            row_pbm=row,
            sign_region_bbox=(0, 0, 118, 59),
            index=index,
            config=matcher_config,
        )
        reference = match_row_sequence(
            row_id="aspect-isolation",
            row_pbm=row,
            sign_region_bbox=(0, 0, 118, 59),
            index=index,
            config=matcher_config,
        )
        prepared = _match_row_sequence_from_workspace(
            workspace,
            index=index,
            config=matcher_config,
        )
        self.assertEqual(reference, prepared)
        with self.assertRaises(FrozenInstanceError):
            workspace.__setattr__("row_id", "changed")
        forged_workspace = replace(workspace, boundary_contact=not workspace.boundary_contact)
        with self.assertRaisesRegex(KP1979GlyphMatchError, "provenance"):
            _match_row_sequence_from_workspace(
                forged_workspace,
                index=index,
                config=matcher_config,
            )

        equal_but_distinct_index = build_template_index(
            [("near-a", 1, near_square_a), ("near-b", 2, near_square_b), ("cross", 3, CROSS)]
        )
        self.assertEqual(index, equal_but_distinct_index)
        with self.assertRaisesRegex(KP1979GlyphMatchError, "another template index"):
            _match_row_sequence_from_workspace(
                workspace,
                index=equal_but_distinct_index,
                config=matcher_config,
            )
        with self.assertRaisesRegex(KP1979GlyphMatchError, "candidate configuration"):
            _match_row_sequence_from_workspace(
                workspace,
                index=index,
                config=loose_config(candidate_aspect_slack_ppm=0),
            )

    def test_workspace_performs_base_cleaned_and_four_shift_distance_work_once(self) -> None:
        index = build_template_index([("cross", 1, CROSS), ("box", 2, BOX), ("bars", 3, TWO_BARS)])
        matcher_config = loose_config(
            require_speck_stability=True,
            require_shift_stability=True,
        )
        original = matcher_module._rank_candidates
        with patch.object(matcher_module, "_rank_candidates", wraps=original) as scorer:
            workspace = _prepare_row_match_workspace(
                row_id="distance-cache",
                row_pbm=PADDED_CROSS,
                sign_region_bbox=(0, 0, 7, 7),
                index=index,
                config=matcher_config,
            )
            preparation_calls = scorer.call_count
            offsets = {call.kwargs["normalization_offset"] for call in scorer.call_args_list}
            cache_keys = {
                (call.args[0], call.kwargs["normalization_offset"])
                for call in scorer.call_args_list
            }
            self.assertEqual(5, preparation_calls)
            self.assertEqual(preparation_calls, len(cache_keys))
            self.assertEqual(
                {(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)},
                offsets,
            )
            for max_cost, rank_margin, path_margin in (
                (0, 0, 0),
                (500_000, 1, 1),
                (1_250_000, 100_000, 250_000),
            ):
                _match_row_sequence_from_workspace(
                    workspace,
                    index=index,
                    config=loose_config(
                        max_token_cost=max_cost,
                        min_different_rank_margin=rank_margin,
                        min_path_margin=path_margin,
                        require_speck_stability=True,
                        require_shift_stability=True,
                    ),
                )
            self.assertEqual(preparation_calls, scorer.call_count)

    def test_workspace_aspect_prefilter_is_exact_at_the_integer_cutoff(self) -> None:
        index = build_template_index([("square", 1, CROSS)])
        wide_row = pbm(
            ".......",
            ".#####.",
            ".#####.",
            ".#####.",
            ".#####.",
            ".......",
        )
        at_cutoff = loose_config(candidate_aspect_slack_ppm=250_000)
        one_below = loose_config(candidate_aspect_slack_ppm=249_999)
        for label, matcher_config, expected_candidate in (
            ("at-cutoff", at_cutoff, True),
            ("one-ppm-over-cutoff", one_below, False),
        ):
            with self.subTest(label=label):
                workspace = _prepare_row_match_workspace(
                    row_id=f"aspect-{label}",
                    row_pbm=wide_row,
                    sign_region_bbox=(0, 0, 7, 6),
                    index=index,
                    config=matcher_config,
                )
                self.assertEqual(expected_candidate, bool(workspace.candidate_spans[0]))
                self.assertEqual(
                    match_row_sequence(
                        row_id=f"aspect-{label}",
                        row_pbm=wide_row,
                        sign_region_bbox=(0, 0, 7, 6),
                        index=index,
                        config=matcher_config,
                    ),
                    _match_row_sequence_from_workspace(
                        workspace,
                        index=index,
                        config=matcher_config,
                    ),
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
