"""Minimal one-bit canvas shared by the independent KP1979 V3 renderers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable


class KP1979V3CanvasError(ValueError):
    """Raised when a renderer exceeds the closed canvas contract."""


@runtime_checkable
class PixelCanvas(Protocol):
    """The complete drawing surface available to a V3 renderer."""

    width: int
    height: int

    def require_mutation_capacity(self, operations: int) -> None:
        """Fail without mutation unless all requested operations can complete."""

    def set_ink(self, x: int, y: int) -> None:
        """Set one pixel to black."""

    def clear_ink(self, x: int, y: int) -> None:
        """Set one pixel to white."""

    def fill_ink_rect(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Fill one non-empty half-open rectangle with black pixels."""

    def clear_rect(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Fill one non-empty half-open rectangle with white pixels."""


class MonochromeCanvas:
    """Bounded packed-PBM canvas with no image-library dependency."""

    __slots__ = ("_data", "_max_mutations", "_mutation_count", "height", "row_bytes", "width")

    def __init__(self, width: int, height: int, *, max_mutations: int) -> None:
        if (
            type(width) is not int
            or type(height) is not int
            or type(max_mutations) is not int
            or width <= 0
            or height <= 0
            or max_mutations <= 0
        ):
            raise KP1979V3CanvasError("invalid canvas dimensions or mutation budget")
        self.width = width
        self.height = height
        self.row_bytes = (width + 7) // 8
        self._data = bytearray(self.row_bytes * height)
        self._max_mutations = max_mutations
        self._mutation_count = 0

    @property
    def mutation_count(self) -> int:
        """Return the number of bounded drawing operations performed."""

        return self._mutation_count

    @property
    def remaining_mutations(self) -> int:
        """Return the exact number of drawing operations still available."""

        return self._max_mutations - self._mutation_count

    def require_mutation_capacity(self, operations: int) -> None:
        """Fail before drawing when ``operations`` cannot complete atomically."""

        if type(operations) is not int or operations < 0:
            raise KP1979V3CanvasError(
                "mutation capacity request must be a non-negative strict integer"
            )
        if operations > self.remaining_mutations:
            raise KP1979V3CanvasError("canvas mutation budget exceeded")

    def _consume_mutation(self) -> None:
        self.require_mutation_capacity(1)
        self._mutation_count += 1

    def _require_point(self, x: int, y: int) -> None:
        if (
            type(x) is not int
            or type(y) is not int
            or not 0 <= x < self.width
            or not 0 <= y < self.height
        ):
            raise KP1979V3CanvasError("pixel is outside the canvas")

    def _require_rect(self, x0: int, y0: int, x1: int, y1: int) -> None:
        if (
            any(type(value) is not int for value in (x0, y0, x1, y1))
            or not 0 <= x0 < x1 <= self.width
            or not 0 <= y0 < y1 <= self.height
        ):
            raise KP1979V3CanvasError("rectangle is outside the canvas")

    def _pixel_location(self, x: int, y: int) -> tuple[int, int]:
        return y * self.row_bytes + x // 8, 0x80 >> (x % 8)

    def set_ink(self, x: int, y: int) -> None:
        self._require_point(x, y)
        self._consume_mutation()
        index, mask = self._pixel_location(x, y)
        self._data[index] |= mask

    def clear_ink(self, x: int, y: int) -> None:
        self._require_point(x, y)
        self._consume_mutation()
        index, mask = self._pixel_location(x, y)
        self._data[index] &= ~mask

    def fill_ink_rect(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._require_rect(x0, y0, x1, y1)
        self._consume_mutation()
        for y in range(y0, y1):
            row_offset = y * self.row_bytes
            for x in range(x0, x1):
                index = row_offset + x // 8
                self._data[index] |= 0x80 >> (x % 8)

    def clear_rect(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._require_rect(x0, y0, x1, y1)
        self._consume_mutation()
        for y in range(y0, y1):
            row_offset = y * self.row_bytes
            for x in range(x0, x1):
                index = row_offset + x // 8
                self._data[index] &= ~(0x80 >> (x % 8))

    def is_ink(self, x: int, y: int) -> bool:
        """Return whether one in-bounds pixel is black without mutating it."""

        self._require_point(x, y)
        index, mask = self._pixel_location(x, y)
        return bool(self._data[index] & mask)

    def iter_ink_points(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> Iterator[tuple[int, int]]:
        """Yield black pixels from one bounded rectangle in row-major order."""

        self._require_rect(x0, y0, x1, y1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if self.is_ink(x, y):
                    yield x, y

    def packed_crop(self, x0: int, y0: int, x1: int, y1: int) -> bytes:
        """Return a canonical row-packed crop with zeroed trailing bits."""

        self._require_rect(x0, y0, x1, y1)
        crop_width = x1 - x0
        crop_row_bytes = (crop_width + 7) // 8
        output = bytearray(crop_row_bytes * (y1 - y0))
        for x, y in self.iter_ink_points(x0, y0, x1, y1):
            relative_x = x - x0
            relative_y = y - y0
            output[relative_y * crop_row_bytes + relative_x // 8] |= 0x80 >> (relative_x % 8)
        return bytes(output)

    def to_pbm_bytes(self) -> bytes:
        """Return canonical raw-PBM bytes for the complete canvas."""

        header = f"P4\n{self.width} {self.height}\n".encode("ascii")
        return header + bytes(self._data)

    def clone(self) -> MonochromeCanvas:
        """Return an independent canvas with identical pixels and budget state."""

        duplicate = MonochromeCanvas(
            self.width,
            self.height,
            max_mutations=self._max_mutations,
        )
        duplicate._data[:] = self._data
        duplicate._mutation_count = self._mutation_count
        return duplicate


__all__ = [
    "KP1979V3CanvasError",
    "MonochromeCanvas",
    "PixelCanvas",
]
