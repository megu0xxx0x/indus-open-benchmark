from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from indusbench.kp1979_v3_canvas import KP1979V3CanvasError, MonochromeCanvas
from indusbench.kp1979_v3_renderer_a import (
    OrthogonalLabelReceipt,
    render_orthogonal_label,
)

_DEFAULT_ARGUMENTS = {
    "lane_bounds": (20, 180),
    "anchor_y": 48,
    "entropy": bytes(range(32)),
    "stroke_width": 2,
    "qualifier_variant": 1,
    "damage_percent": 0,
    "horizontal_alignment": "center",
}


def _ink_points(canvas: MonochromeCanvas) -> set[tuple[int, int]]:
    return set(canvas.iter_ink_points(0, 0, canvas.width, canvas.height))


def _component_count(points: set[tuple[int, int]]) -> int:
    remaining = set(points)
    count = 0
    while remaining:
        count += 1
        pending = [remaining.pop()]
        while pending:
            x, y = pending.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
    return count


def _render(
    *,
    entropy: bytes = bytes(range(32)),
    stroke_width: int = 2,
    qualifier_variant: int = 1,
    damage_percent: int = 0,
    horizontal_alignment: str = "center",
    max_mutations: int = 4096,
) -> tuple[MonochromeCanvas, OrthogonalLabelReceipt]:
    canvas = MonochromeCanvas(200, 96, max_mutations=max_mutations)
    receipt = render_orthogonal_label(
        canvas,
        lane_bounds=(20, 180),
        anchor_y=48,
        entropy=entropy,
        stroke_width=stroke_width,
        qualifier_variant=qualifier_variant,
        damage_percent=damage_percent,
        horizontal_alignment=horizontal_alignment,
    )
    return canvas, receipt


class KP1979V3RendererATests(unittest.TestCase):
    def test_render_is_deterministic_and_receipt_is_closed_and_frozen(self) -> None:
        first_canvas, first_receipt = _render()
        second_canvas, second_receipt = _render()

        self.assertEqual(first_canvas.to_pbm_bytes(), second_canvas.to_pbm_bytes())
        self.assertEqual(first_receipt, second_receipt)
        self.assertEqual("orthogonal_graph_v1", first_receipt.renderer_id)
        self.assertFalse(hasattr(first_receipt, "__dict__"))
        renderer_id_field = "renderer_id"
        with self.assertRaises(FrozenInstanceError):
            setattr(first_receipt, renderer_id_field, "changed")

    def test_entropy_and_qualifier_are_visible_but_repeatable(self) -> None:
        first_canvas, _ = _render(entropy=b"\x00" * 32, qualifier_variant=0)
        other_seed_canvas, _ = _render(entropy=b"\xff" * 32, qualifier_variant=0)
        qualifier_canvas, _ = _render(entropy=b"\x00" * 32, qualifier_variant=3)

        self.assertNotEqual(first_canvas.to_pbm_bytes(), other_seed_canvas.to_pbm_bytes())
        self.assertNotEqual(first_canvas.to_pbm_bytes(), qualifier_canvas.to_pbm_bytes())

    def test_each_tier_has_the_required_number_of_separate_seeded_glyphs(self) -> None:
        for entropy in (b"\x00" * 32, bytes(range(32)), b"\xff" * 32):
            with self.subTest(entropy=entropy.hex()[:8]):
                canvas, _ = _render(
                    entropy=entropy,
                    stroke_width=1,
                    qualifier_variant=3,
                )
                points = _ink_points(canvas)
                upper = {point for point in points if point[1] < 48}
                lower = {point for point in points if point[1] > 48}
                self.assertIn(_component_count(upper), {3, 4, 5})
                self.assertIn(_component_count(lower), {2, 3, 4})

    def test_tiers_and_half_open_bbox_stay_inside_the_closed_envelope(self) -> None:
        canvas, receipt = _render(stroke_width=4, qualifier_variant=3)
        points = _ink_points(canvas)
        upper = {point for point in points if point[1] < 48}
        lower = {point for point in points if point[1] > 48}

        self.assertEqual(receipt.upper_ink_count, len(upper))
        self.assertEqual(receipt.lower_ink_count, len(lower))
        self.assertTrue(upper)
        self.assertTrue(lower)
        self.assertLessEqual(20, min(x for x, _ in points))
        self.assertLess(max(x for x, _ in points), 180)
        self.assertGreaterEqual(min(y for _, y in points), 48 - 28)
        self.assertLess(max(y for _, y in points), 48 + 28)
        self.assertLess(max(y for _, y in upper), min(y for _, y in lower))
        self.assertEqual(
            (
                min(x for x, _ in points),
                min(y for _, y in points),
                max(x for x, _ in points) + 1,
                max(y for _, y in points) + 1,
            ),
            receipt.ink_bbox,
        )

    def test_left_and_right_alignments_use_seeded_two_to_ten_pixel_edges(self) -> None:
        for alignment in ("left", "right"):
            for entropy in (bytes(range(32)), b"\x44" * 32, b"\xee" * 32):
                with self.subTest(alignment=alignment, entropy=entropy.hex()[:8]):
                    _, receipt = _render(
                        entropy=entropy,
                        horizontal_alignment=alignment,
                    )
                    if alignment == "left":
                        offset = receipt.ink_bbox[0] - 20
                    else:
                        offset = 180 - receipt.ink_bbox[2]
                    self.assertIn(offset, range(2, 11))

    def test_damage_is_bounded_deterministic_and_preserves_both_tiers(self) -> None:
        clean_canvas, clean = _render(
            entropy=b"\xa5" * 32,
            stroke_width=3,
            qualifier_variant=2,
        )
        damaged_canvas, damaged = _render(
            entropy=b"\xa5" * 32,
            stroke_width=3,
            qualifier_variant=2,
            damage_percent=12,
        )
        damaged_again_canvas, damaged_again = _render(
            entropy=b"\xa5" * 32,
            stroke_width=3,
            qualifier_variant=2,
            damage_percent=12,
        )
        clean_count = clean.upper_ink_count + clean.lower_ink_count
        damaged_count = damaged.upper_ink_count + damaged.lower_ink_count
        removed_count = clean_count - damaged_count

        self.assertGreater(removed_count, 0)
        self.assertLessEqual(removed_count, clean_count * 12 // 100)
        self.assertGreater(damaged.upper_ink_count, 0)
        self.assertGreater(damaged.lower_ink_count, 0)
        self.assertEqual(damaged_count, damaged.mutation_delta)
        self.assertEqual(damaged, damaged_again)
        self.assertEqual(damaged_canvas.to_pbm_bytes(), damaged_again_canvas.to_pbm_bytes())
        self.assertNotEqual(clean_canvas.to_pbm_bytes(), damaged_canvas.to_pbm_bytes())

    def test_damage_never_clears_preexisting_canvas_ink(self) -> None:
        arguments = {
            "lane_bounds": (20, 180),
            "anchor_y": 48,
            "entropy": b"\xa5" * 32,
            "stroke_width": 3,
            "qualifier_variant": 2,
            "horizontal_alignment": "center",
        }
        clean = MonochromeCanvas(200, 96, max_mutations=4096)
        render_orthogonal_label(clean, damage_percent=0, **arguments)
        damaged = MonochromeCanvas(200, 96, max_mutations=4096)
        render_orthogonal_label(damaged, damage_percent=12, **arguments)
        removed_points = _ink_points(clean) - _ink_points(damaged)
        self.assertTrue(removed_points)
        protected_point = min(removed_points, key=lambda point: (point[1], point[0]))

        prefilled = MonochromeCanvas(200, 96, max_mutations=4096)
        prefilled.set_ink(*protected_point)
        receipt = render_orthogonal_label(prefilled, damage_percent=12, **arguments)

        self.assertTrue(prefilled.is_ink(*protected_point))
        self.assertEqual(receipt.mutation_delta + 1, prefilled.mutation_count)

    def test_mutation_receipt_matches_canvas_and_fits_fixed_budget(self) -> None:
        for stroke_width in range(1, 5):
            with self.subTest(stroke_width=stroke_width):
                canvas, receipt = _render(
                    entropy=b"\xff" * 32,
                    stroke_width=stroke_width,
                    qualifier_variant=3,
                    damage_percent=12,
                )
                self.assertEqual(canvas.mutation_count, receipt.mutation_delta)
                self.assertLessEqual(receipt.mutation_delta, 4096)

    def test_validation_rejects_wrong_types_ranges_geometry_and_narrow_lanes(self) -> None:
        canvas = MonochromeCanvas(200, 96, max_mutations=4096)
        invalid_changes = (
            {"lane_bounds": [20, 180]},
            {"lane_bounds": (True, 180)},
            {"lane_bounds": (-1, 180)},
            {"lane_bounds": (20, 201)},
            {"lane_bounds": (20, 45)},
            {"anchor_y": True},
            {"anchor_y": 27},
            {"anchor_y": 69},
            {"entropy": bytearray(32)},
            {"entropy": b"\x00" * 31},
            {"stroke_width": True},
            {"stroke_width": 0},
            {"stroke_width": 5},
            {"qualifier_variant": True},
            {"qualifier_variant": -1},
            {"qualifier_variant": 4},
            {"damage_percent": True},
            {"damage_percent": -1},
            {"damage_percent": 13},
            {"horizontal_alignment": 1},
            {"horizontal_alignment": "middle"},
        )
        for changes in invalid_changes:
            arguments = dict(_DEFAULT_ARGUMENTS)
            arguments.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                render_orthogonal_label(canvas, **arguments)

        self.assertEqual(0, canvas.mutation_count)

    def test_seeded_narrow_lane_is_rejected_before_any_mutation(self) -> None:
        for alignment in ("left", "center", "right"):
            for damage_percent in (0, 12):
                canvas = MonochromeCanvas(300, 96, max_mutations=4096)
                with (
                    self.subTest(
                        alignment=alignment,
                        damage_percent=damage_percent,
                    ),
                    self.assertRaisesRegex(ValueError, "too narrow"),
                ):
                    render_orthogonal_label(
                        canvas,
                        lane_bounds=(100, 133),
                        anchor_y=48,
                        entropy=(2).to_bytes(32, "big"),
                        stroke_width=1,
                        qualifier_variant=0,
                        damage_percent=damage_percent,
                        horizontal_alignment=alignment,
                    )
                self.assertEqual(0, canvas.mutation_count)
                self.assertFalse(_ink_points(canvas))

    def test_canvas_budget_failure_is_atomic_across_remaining_capacities(self) -> None:
        _, successful = _render()
        required = successful.mutation_delta
        self.assertGreater(required, 1)

        for capacity in sorted({1, required // 4, required // 2, required - 1}):
            canvas = MonochromeCanvas(200, 96, max_mutations=capacity)
            before = canvas.to_pbm_bytes()
            with (
                self.subTest(capacity=capacity),
                self.assertRaisesRegex(KP1979V3CanvasError, "budget"),
            ):
                render_orthogonal_label(canvas, **_DEFAULT_ARGUMENTS)
            self.assertEqual(0, canvas.mutation_count)
            self.assertEqual(before, canvas.to_pbm_bytes())

        prefilled = MonochromeCanvas(200, 96, max_mutations=1)
        prefilled.set_ink(0, 0)
        before = prefilled.to_pbm_bytes()
        with self.assertRaisesRegex(KP1979V3CanvasError, "budget"):
            render_orthogonal_label(prefilled, **_DEFAULT_ARGUMENTS)
        self.assertEqual(1, prefilled.mutation_count)
        self.assertEqual(before, prefilled.to_pbm_bytes())

    def test_static_import_boundary_and_self_contained_segment_logic(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1] / "src" / "indusbench" / "kp1979_v3_renderer_a.py"
        )
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_project_names: list[tuple[str | None, tuple[str, ...]]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("indusbench"):
                    imported_project_names.append(
                        (node.module, tuple(alias.name for alias in node.names))
                    )
            elif isinstance(node, ast.Import):
                self.assertFalse(any(alias.name.startswith("indusbench") for alias in node.names))

        self.assertEqual(
            [("indusbench.kp1979_v3_canvas", ("PixelCanvas",))],
            imported_project_names,
        )
        lowered = source.casefold()
        for forbidden in (
            "renderer_b",
            "synthetic_control",
            "label_scoring",
            "bitmap",
            "font",
            "pillow",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)
        self.assertIn("def _bresenham_points(", source)


if __name__ == "__main__":
    unittest.main()
