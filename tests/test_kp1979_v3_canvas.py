from __future__ import annotations

import unittest

from indusbench.kp1979_v3_canvas import KP1979V3CanvasError, MonochromeCanvas


class KP1979V3CanvasTests(unittest.TestCase):
    def test_packed_pbm_rectangles_points_and_crops_are_canonical(self) -> None:
        canvas = MonochromeCanvas(10, 4, max_mutations=8)
        canvas.set_ink(0, 0)
        canvas.set_ink(9, 0)
        canvas.fill_ink_rect(2, 1, 6, 3)
        canvas.clear_rect(3, 2, 5, 3)
        canvas.clear_ink(2, 1)

        self.assertEqual(5, canvas.mutation_count)
        self.assertEqual(3, canvas.remaining_mutations)
        self.assertEqual(
            b"P4\n10 4\n\x80\x40\x1c\x00\x24\x00\x00\x00",
            canvas.to_pbm_bytes(),
        )
        self.assertEqual(
            [(9, 0), (3, 1), (4, 1), (5, 1), (2, 2), (5, 2)],
            list(canvas.iter_ink_points(1, 0, 10, 4)),
        )
        self.assertEqual(b"\x00\x38\x48\x00", canvas.packed_crop(1, 0, 9, 4))

    def test_clone_is_independent_and_preserves_mutation_state(self) -> None:
        canvas = MonochromeCanvas(8, 2, max_mutations=4)
        canvas.set_ink(1, 1)
        duplicate = canvas.clone()
        duplicate.set_ink(2, 1)

        self.assertTrue(canvas.is_ink(1, 1))
        self.assertFalse(canvas.is_ink(2, 1))
        self.assertTrue(duplicate.is_ink(2, 1))
        self.assertEqual(1, canvas.mutation_count)
        self.assertEqual(3, canvas.remaining_mutations)
        self.assertEqual(2, duplicate.mutation_count)
        self.assertEqual(2, duplicate.remaining_mutations)

    def test_invalid_geometry_boolean_coordinates_and_budget_fail_closed(self) -> None:
        with self.assertRaisesRegex(KP1979V3CanvasError, "dimensions"):
            MonochromeCanvas(True, 2, max_mutations=4)

        canvas = MonochromeCanvas(8, 2, max_mutations=1)
        invalid_operations = (
            lambda: canvas.set_ink(True, 0),
            lambda: canvas.set_ink(8, 0),
            lambda: canvas.fill_ink_rect(0, 0, 0, 1),
            lambda: canvas.clear_rect(0, 0, 9, 1),
        )
        for operation in invalid_operations:
            with self.subTest(operation=operation), self.assertRaises(KP1979V3CanvasError):
                operation()

        for operations in (True, -1):
            with (
                self.subTest(operations=operations),
                self.assertRaisesRegex(KP1979V3CanvasError, "non-negative strict integer"),
            ):
                canvas.require_mutation_capacity(operations)
        canvas.require_mutation_capacity(0)
        canvas.require_mutation_capacity(1)
        self.assertEqual(0, canvas.mutation_count)

        canvas.set_ink(0, 0)
        self.assertEqual(0, canvas.remaining_mutations)
        with self.assertRaisesRegex(KP1979V3CanvasError, "budget"):
            canvas.require_mutation_capacity(1)
        with self.assertRaisesRegex(KP1979V3CanvasError, "budget"):
            canvas.set_ink(1, 0)
        self.assertEqual(1, canvas.mutation_count)
        self.assertFalse(canvas.is_ink(1, 0))


if __name__ == "__main__":
    unittest.main()
