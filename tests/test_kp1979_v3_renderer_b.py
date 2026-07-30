from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import indusbench.kp1979_v3_renderer_b as renderer_b
from indusbench.kp1979_v3_canvas import KP1979V3CanvasError, MonochromeCanvas
from indusbench.kp1979_v3_renderer_b import (
    BITMAP_MASK_LIBRARY,
    RENDERER_ID,
    KP1979V3RendererBError,
    render_bitmap_label,
)


class KP1979V3RendererBTests(unittest.TestCase):
    def _render(
        self,
        entropy: bytes,
        *,
        scale: int = 2,
        shear: int = 0,
        qualifier_variant: int = 1,
        damage_percent: int = 0,
        horizontal_alignment: str = "center",
        lane_bounds: tuple[int, int] = (20, 220),
        anchor_y: int = 48,
        max_mutations: int = 512,
    ) -> tuple[MonochromeCanvas, renderer_b.BitmapLabelReceipt]:
        canvas = MonochromeCanvas(240, 96, max_mutations=max_mutations)
        receipt = render_bitmap_label(
            canvas,
            lane_bounds=lane_bounds,
            anchor_y=anchor_y,
            entropy=entropy,
            scale=scale,
            shear=shear,
            qualifier_variant=qualifier_variant,
            damage_percent=damage_percent,
            horizontal_alignment=horizontal_alignment,
        )
        return canvas, receipt

    def test_rendering_is_deterministic_and_receipt_is_frozen(self) -> None:
        first_canvas, first_receipt = self._render(bytes(range(32)), shear=1)
        second_canvas, second_receipt = self._render(bytes(range(32)), shear=1)

        self.assertEqual(first_canvas.to_pbm_bytes(), second_canvas.to_pbm_bytes())
        self.assertEqual(first_receipt, second_receipt)
        self.assertEqual(RENDERER_ID, first_receipt.renderer_id)
        with self.assertRaises(FrozenInstanceError):
            first_receipt.renderer_id = "changed"  # type: ignore[misc]

    def test_distinct_entropy_changes_the_seeded_bitmap(self) -> None:
        first_canvas, first_receipt = self._render(bytes(range(32)), qualifier_variant=3)
        second_canvas, second_receipt = self._render(
            bytes(reversed(range(32))),
            qualifier_variant=3,
        )

        self.assertNotEqual(first_canvas.to_pbm_bytes(), second_canvas.to_pbm_bytes())
        self.assertNotEqual(
            (
                first_receipt.upper_ink_count,
                first_receipt.lower_ink_count,
                first_receipt.ink_bbox,
            ),
            (
                second_receipt.upper_ink_count,
                second_receipt.lower_ink_count,
                second_receipt.ink_bbox,
            ),
        )

    def test_fixed_mask_library_has_at_least_32_distinct_five_by_seven_masks(self) -> None:
        self.assertGreaterEqual(len(BITMAP_MASK_LIBRARY), 32)
        self.assertEqual(len(BITMAP_MASK_LIBRARY), len(set(BITMAP_MASK_LIBRARY)))
        for mask in BITMAP_MASK_LIBRARY:
            self.assertEqual(7, len(mask))
            self.assertTrue(all(type(row) is int and 0 <= row <= 0b11111 for row in mask))

    def test_left_and_right_alignment_support_seeded_two_to_ten_pixel_edges(self) -> None:
        entropy = bytes(range(32))
        _, left_receipt = self._render(
            entropy,
            horizontal_alignment="left",
            lane_bounds=(20, 220),
        )
        _, right_receipt = self._render(
            entropy,
            horizontal_alignment="right",
            lane_bounds=(20, 220),
        )

        self.assertIn(left_receipt.ink_bbox[0] - 20, range(2, 11))
        self.assertIn(220 - right_receipt.ink_bbox[2], range(2, 11))

    def test_damage_is_deterministic_bounded_and_preserves_both_tiers(self) -> None:
        entropy = bytes(range(31, -1, -1))
        clean_canvas, clean_receipt = self._render(
            entropy,
            scale=3,
            shear=-1,
            qualifier_variant=3,
            horizontal_alignment="left",
        )
        damaged_canvas, damaged_receipt = self._render(
            entropy,
            scale=3,
            shear=-1,
            qualifier_variant=3,
            damage_percent=12,
            horizontal_alignment="left",
        )
        repeated_canvas, repeated_receipt = self._render(
            entropy,
            scale=3,
            shear=-1,
            qualifier_variant=3,
            damage_percent=12,
            horizontal_alignment="left",
        )

        clean_ink = clean_receipt.upper_ink_count + clean_receipt.lower_ink_count
        damaged_ink = damaged_receipt.upper_ink_count + damaged_receipt.lower_ink_count
        removed_ink = clean_ink - damaged_ink
        self.assertGreater(removed_ink, 0)
        self.assertLessEqual(removed_ink * 100, clean_ink * 12)
        self.assertGreater(damaged_receipt.upper_ink_count, 0)
        self.assertGreater(damaged_receipt.lower_ink_count, 0)
        self.assertEqual(clean_receipt.ink_bbox, damaged_receipt.ink_bbox)
        self.assertNotEqual(clean_canvas.to_pbm_bytes(), damaged_canvas.to_pbm_bytes())
        self.assertEqual(damaged_canvas.to_pbm_bytes(), repeated_canvas.to_pbm_bytes())
        self.assertEqual(damaged_receipt, repeated_receipt)

    def test_damage_never_clears_preexisting_canvas_ink(self) -> None:
        entropy = bytes(range(31, -1, -1))
        arguments = {
            "lane_bounds": (20, 220),
            "anchor_y": 48,
            "entropy": entropy,
            "scale": 3,
            "shear": -1,
            "qualifier_variant": 3,
            "horizontal_alignment": "left",
        }
        clean = MonochromeCanvas(240, 96, max_mutations=1024)
        render_bitmap_label(clean, damage_percent=0, **arguments)
        damaged = MonochromeCanvas(240, 96, max_mutations=1024)
        render_bitmap_label(damaged, damage_percent=12, **arguments)
        clean_points = set(clean.iter_ink_points(0, 0, clean.width, clean.height))
        damaged_points = set(damaged.iter_ink_points(0, 0, damaged.width, damaged.height))
        removed_points = clean_points - damaged_points
        self.assertTrue(removed_points)
        protected_point = min(removed_points, key=lambda point: (point[1], point[0]))

        prefilled = MonochromeCanvas(240, 96, max_mutations=1024)
        prefilled.set_ink(*protected_point)
        receipt = render_bitmap_label(prefilled, damage_percent=12, **arguments)

        self.assertTrue(prefilled.is_ink(*protected_point))
        self.assertEqual(receipt.mutation_delta + 1, prefilled.mutation_count)

    def test_both_tiers_and_all_ink_stay_inside_lane_and_anchor_support(self) -> None:
        canvas, receipt = self._render(
            b"\xa5" * 32,
            scale=3,
            shear=1,
            qualifier_variant=2,
            damage_percent=12,
            lane_bounds=(6, 234),
            anchor_y=48,
        )
        upper_points = list(canvas.iter_ink_points(6, 20, 234, 48))
        lower_points = list(canvas.iter_ink_points(6, 48, 234, 76))
        all_points = upper_points + lower_points

        self.assertEqual(receipt.upper_ink_count, len(upper_points))
        self.assertEqual(receipt.lower_ink_count, len(lower_points))
        self.assertTrue(upper_points)
        self.assertTrue(lower_points)
        self.assertTrue(all(6 <= x < 234 and 20 <= y < 76 for x, y in all_points))
        self.assertGreaterEqual(receipt.ink_bbox[0], 6)
        self.assertLessEqual(receipt.ink_bbox[2], 234)
        self.assertGreaterEqual(receipt.ink_bbox[1], 20)
        self.assertLessEqual(receipt.ink_bbox[3], 76)

    def test_mutation_budget_is_bounded_and_failure_is_atomic(self) -> None:
        canvas, receipt = self._render(
            b"\xff" * 32,
            scale=3,
            shear=1,
            qualifier_variant=3,
            damage_percent=12,
            horizontal_alignment="left",
        )
        self.assertEqual(receipt.mutation_delta, canvas.mutation_count)
        self.assertLessEqual(receipt.mutation_delta, 512)

        arguments = {
            "lane_bounds": (20, 220),
            "anchor_y": 48,
            "entropy": b"\xff" * 32,
            "scale": 3,
            "shear": 1,
            "qualifier_variant": 3,
            "damage_percent": 12,
            "horizontal_alignment": "left",
        }
        required = receipt.mutation_delta
        self.assertGreater(required, 1)
        for capacity in sorted({1, required // 4, required // 2, required - 1}):
            constrained = MonochromeCanvas(240, 96, max_mutations=capacity)
            before = constrained.to_pbm_bytes()
            with (
                self.subTest(capacity=capacity),
                self.assertRaisesRegex(KP1979V3CanvasError, "budget"),
            ):
                render_bitmap_label(constrained, **arguments)
            self.assertEqual(0, constrained.mutation_count)
            self.assertEqual(before, constrained.to_pbm_bytes())

        prefilled = MonochromeCanvas(240, 96, max_mutations=1)
        prefilled.set_ink(0, 0)
        before = prefilled.to_pbm_bytes()
        with self.assertRaisesRegex(KP1979V3CanvasError, "budget"):
            render_bitmap_label(prefilled, **arguments)
        self.assertEqual(1, prefilled.mutation_count)
        self.assertEqual(before, prefilled.to_pbm_bytes())

    def test_invalid_inputs_fail_before_mutating_the_canvas(self) -> None:
        canvas = MonochromeCanvas(240, 96, max_mutations=512)
        valid = {
            "lane_bounds": (20, 220),
            "anchor_y": 48,
            "entropy": b"\x00" * 32,
            "scale": 2,
            "shear": 0,
            "qualifier_variant": 0,
            "damage_percent": 0,
            "horizontal_alignment": "center",
        }
        invalid_overrides: tuple[dict[str, object], ...] = (
            {"lane_bounds": [20, 220]},
            {"lane_bounds": (True, 220)},
            {"lane_bounds": (-1, 220)},
            {"lane_bounds": (220, 20)},
            {"lane_bounds": (20, 241)},
            {"lane_bounds": (20, 21)},
            {"anchor_y": True},
            {"anchor_y": 27},
            {"anchor_y": 69},
            {"entropy": bytearray(32)},
            {"entropy": b"\x00" * 31},
            {"scale": True},
            {"scale": 1},
            {"scale": 4},
            {"shear": True},
            {"shear": -2},
            {"shear": 2},
            {"qualifier_variant": True},
            {"qualifier_variant": -1},
            {"qualifier_variant": 4},
            {"damage_percent": True},
            {"damage_percent": -1},
            {"damage_percent": 13},
            {"horizontal_alignment": 1},
            {"horizontal_alignment": "justify"},
        )
        for override in invalid_overrides:
            request = valid | override
            with self.subTest(override=override), self.assertRaises(KP1979V3RendererBError):
                render_bitmap_label(canvas, **request)  # type: ignore[arg-type]
            self.assertEqual(0, canvas.mutation_count)

    def test_static_import_and_drawing_independence(self) -> None:
        source_path = Path(renderer_b.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        project_imports: list[ast.ImportFrom] = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("indusbench")
        ]
        self.assertEqual(1, len(project_imports))
        self.assertEqual("indusbench.kp1979_v3_canvas", project_imports[0].module)
        self.assertEqual(["PixelCanvas"], [alias.name for alias in project_imports[0].names])

        lowered = source.casefold()
        for forbidden in (
            "renderer_a",
            "synthetic_control",
            "label_scoring",
            "bresenham",
        ):
            self.assertNotIn(forbidden, lowered)
        canvas_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "canvas"
        }
        self.assertEqual({"fill_ink_rect", "require_mutation_capacity"}, canvas_calls)


if __name__ == "__main__":
    unittest.main()
