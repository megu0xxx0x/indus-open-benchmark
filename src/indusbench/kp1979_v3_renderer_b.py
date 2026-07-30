"""Independent bitmap-mask positive renderer for the KP1979 V3 control."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Final, Literal

from indusbench.kp1979_v3_canvas import PixelCanvas

RENDERER_ID: Final = "bitmap_mask_v1"

_SELECTION_DOMAIN: Final = b"indusbench.kp1979.v3.renderer-b.selection.v1\x00"
_EDGE_DOMAIN: Final = b"indusbench.kp1979.v3.renderer-b.edge.v1\x00"
_DAMAGE_DOMAIN: Final = b"indusbench.kp1979.v3.renderer-b.damage.v1\x00"

# Fixed five-by-seven masks for 0-9 and A-Z. Rows are stored most-significant
# bit first in the low five bits of each integer.
BITMAP_MASK_LIBRARY: Final[tuple[tuple[int, ...], ...]] = (
    (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111),
    (0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110),
    (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    (0b11111, 0b10000, 0b10000, 0b11110, 0b00001, 0b00001, 0b11110),
    (0b01110, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110),
    (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    (0b01111, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b01111),
    (0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110),
    (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    (0b01111, 0b10000, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    (0b00111, 0b00010, 0b00010, 0b00010, 0b10010, 0b10010, 0b01100),
    (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
)

_QUALIFIER_CELLS: Final[tuple[tuple[tuple[int, int], ...], ...]] = (
    (),
    ((0, 3),),
    ((0, 1), (0, 5)),
    ((0, 1), (0, 3), (0, 5), (1, 3)),
)

if (
    len(BITMAP_MASK_LIBRARY) < 32
    or len(set(BITMAP_MASK_LIBRARY)) != len(BITMAP_MASK_LIBRARY)
    or any(
        len(mask) != 7 or any(type(row) is not int or not 0 <= row <= 0b11111 for row in mask)
        for mask in BITMAP_MASK_LIBRARY
    )
):
    raise RuntimeError("the fixed Renderer B mask library is invalid")


class KP1979V3RendererBError(ValueError):
    """Raised when a Renderer B request violates its closed contract."""


@dataclass(frozen=True, slots=True)
class BitmapLabelReceipt:
    """Answer-free geometry summary for one completed bitmap rendering."""

    renderer_id: str
    ink_bbox: tuple[int, int, int, int]
    upper_ink_count: int
    lower_ink_count: int
    mutation_delta: int


_Tier = Literal["upper", "lower"]


@dataclass(frozen=True, slots=True)
class _Cell:
    tier: _Tier
    glyph_index: int
    x0: int
    y0: int
    x1: int
    y1: int


def _require_int(name: str, value: object, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise KP1979V3RendererBError(f"{name} is outside its closed integer range")
    return value


def _validate_request(
    canvas: PixelCanvas,
    *,
    lane_bounds: tuple[int, int],
    anchor_y: int,
    entropy: bytes,
    scale: int,
    shear: int,
    qualifier_variant: int,
    damage_percent: int,
    horizontal_alignment: str,
) -> tuple[int, int]:
    if not isinstance(canvas, PixelCanvas):
        raise KP1979V3RendererBError("canvas does not implement PixelCanvas")
    if (
        type(canvas.width) is not int
        or type(canvas.height) is not int
        or canvas.width <= 0
        or canvas.height <= 0
    ):
        raise KP1979V3RendererBError("canvas dimensions are invalid")
    if type(lane_bounds) is not tuple or len(lane_bounds) != 2:
        raise KP1979V3RendererBError("lane_bounds must be an exact two-integer tuple")
    lane_left = _require_int("lane left", lane_bounds[0], 0, canvas.width)
    lane_right = _require_int("lane right", lane_bounds[1], 0, canvas.width)
    if lane_left >= lane_right:
        raise KP1979V3RendererBError("lane_bounds must describe a non-empty interval")
    _require_int("anchor_y", anchor_y, 0, canvas.height)
    if anchor_y - 28 < 0 or anchor_y + 28 > canvas.height:
        raise KP1979V3RendererBError("anchor_y support window is outside the canvas")
    if type(entropy) is not bytes or len(entropy) != 32:
        raise KP1979V3RendererBError("entropy must be exactly 32 bytes")
    _require_int("scale", scale, 2, 3)
    _require_int("shear", shear, -1, 1)
    _require_int("qualifier_variant", qualifier_variant, 0, 3)
    _require_int("damage_percent", damage_percent, 0, 12)
    if type(horizontal_alignment) is not str or horizontal_alignment not in {
        "left",
        "center",
        "right",
    }:
        raise KP1979V3RendererBError("horizontal_alignment is outside the closed vocabulary")
    return lane_left, lane_right


def _select_mask_indices(entropy: bytes, tier: _Tier, count: int) -> tuple[int, ...]:
    tier_tag = tier.encode("ascii") + b"\x00"
    ranked = sorted(
        range(len(BITMAP_MASK_LIBRARY)),
        key=lambda index: (
            sha256(_SELECTION_DOMAIN + entropy + tier_tag + index.to_bytes(2, "big")).digest(),
            index,
        ),
    )
    return tuple(ranked[:count])


def _plan_tier(
    *,
    tier: _Tier,
    mask_indices: tuple[int, ...],
    top_y: int,
    scale: int,
    shear: int,
    qualifier_variant: int,
) -> tuple[tuple[_Cell, ...], int]:
    shear_padding = 3 * abs(shear)
    glyph_width = 5 * scale + 2 * shear_padding
    cursor = 0
    cells: list[_Cell] = []

    for glyph_index, mask_index in enumerate(mask_indices):
        mask = BITMAP_MASK_LIBRARY[mask_index]
        for row_index, row_bits in enumerate(mask):
            row_shift = shear * (row_index - 3) + shear_padding
            for column_index in range(5):
                if row_bits & (1 << (4 - column_index)):
                    x0 = cursor + row_shift + column_index * scale
                    y0 = top_y + row_index * scale
                    cells.append(
                        _Cell(
                            tier=tier,
                            glyph_index=glyph_index,
                            x0=x0,
                            y0=y0,
                            x1=x0 + scale,
                            y1=y0 + scale,
                        )
                    )
        cursor += glyph_width
        if glyph_index + 1 < len(mask_indices):
            cursor += scale

    if qualifier_variant:
        qualifier_x = cursor + scale
        for column_index, row_index in _QUALIFIER_CELLS[qualifier_variant]:
            x0 = qualifier_x + column_index * scale
            y0 = top_y + row_index * scale
            cells.append(
                _Cell(
                    tier=tier,
                    glyph_index=-1,
                    x0=x0,
                    y0=y0,
                    x1=x0 + scale,
                    y1=y0 + scale,
                )
            )

    if not cells:
        raise RuntimeError("Renderer B produced an empty tier")
    minimum_x = min(cell.x0 for cell in cells)
    maximum_x = max(cell.x1 for cell in cells)
    normalized = tuple(
        _Cell(
            tier=cell.tier,
            glyph_index=cell.glyph_index,
            x0=cell.x0 - minimum_x,
            y0=cell.y0,
            x1=cell.x1 - minimum_x,
            y1=cell.y1,
        )
        for cell in cells
    )
    return normalized, maximum_x - minimum_x


def _tier_offset(alignment: str, block_width: int, tier_width: int) -> int:
    if alignment == "left":
        return 0
    if alignment == "right":
        return block_width - tier_width
    return (block_width - tier_width) // 2


def _translate_cells(cells: tuple[_Cell, ...], x_offset: int) -> tuple[_Cell, ...]:
    return tuple(
        _Cell(
            tier=cell.tier,
            glyph_index=cell.glyph_index,
            x0=cell.x0 + x_offset,
            y0=cell.y0,
            x1=cell.x1 + x_offset,
            y1=cell.y1,
        )
        for cell in cells
    )


def _damage_indices(
    cells: tuple[_Cell, ...],
    *,
    entropy: bytes,
    damage_percent: int,
) -> frozenset[int]:
    target_count = len(cells) * damage_percent // 100
    if target_count == 0:
        return frozenset()

    protected = {index for index, cell in enumerate(cells) if cell.glyph_index == 0}
    minimum_x = min(cell.x0 for cell in cells)
    maximum_x = max(cell.x1 for cell in cells)
    protected.add(next(index for index, cell in enumerate(cells) if cell.x0 == minimum_x))
    protected.add(next(index for index, cell in enumerate(cells) if cell.x1 == maximum_x))

    candidates = [index for index in range(len(cells)) if index not in protected]
    if target_count > len(candidates):
        raise RuntimeError("Renderer B damage guards exceed the fixed budget")
    candidates.sort(
        key=lambda index: (
            sha256(_DAMAGE_DOMAIN + entropy + index.to_bytes(4, "big")).digest(),
            index,
        )
    )
    return frozenset(candidates[:target_count])


def render_bitmap_label(
    canvas: PixelCanvas,
    *,
    lane_bounds: tuple[int, int],
    anchor_y: int,
    entropy: bytes,
    scale: int,
    shear: int,
    qualifier_variant: int,
    damage_percent: int,
    horizontal_alignment: str,
) -> BitmapLabelReceipt:
    """Render one deterministic two-tier bitmap label inside a lane."""

    lane_left, lane_right = _validate_request(
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

    selection_digest = sha256(_SELECTION_DOMAIN + entropy).digest()
    upper_count = 3 + selection_digest[0] % 3
    lower_count = 2 + selection_digest[1] % 3
    upper_masks = _select_mask_indices(entropy, "upper", upper_count)
    lower_masks = _select_mask_indices(entropy, "lower", lower_count)

    glyph_height = 7 * scale
    upper_top = anchor_y - 3 - glyph_height
    lower_top = anchor_y + 3
    upper_cells, upper_width = _plan_tier(
        tier="upper",
        mask_indices=upper_masks,
        top_y=upper_top,
        scale=scale,
        shear=shear,
        qualifier_variant=qualifier_variant,
    )
    lower_cells, lower_width = _plan_tier(
        tier="lower",
        mask_indices=lower_masks,
        top_y=lower_top,
        scale=scale,
        shear=shear,
        qualifier_variant=0,
    )

    block_width = max(upper_width, lower_width)
    lane_width = lane_right - lane_left
    edge_offset = 2 + sha256(_EDGE_DOMAIN + entropy).digest()[0] % 9
    if horizontal_alignment == "left":
        block_left = lane_left + edge_offset
    elif horizontal_alignment == "right":
        block_left = lane_right - edge_offset - block_width
    else:
        block_left = lane_left + (lane_width - block_width) // 2
    if block_width > lane_width or block_left < lane_left or block_left + block_width > lane_right:
        raise KP1979V3RendererBError("rendered label does not fit inside lane_bounds")

    planned_cells = _translate_cells(
        upper_cells,
        block_left + _tier_offset(horizontal_alignment, block_width, upper_width),
    ) + _translate_cells(
        lower_cells,
        block_left + _tier_offset(horizontal_alignment, block_width, lower_width),
    )
    support_top = anchor_y - 28
    support_bottom = anchor_y + 28
    if any(
        not (
            lane_left <= cell.x0 < cell.x1 <= lane_right
            and support_top <= cell.y0 < cell.y1 <= support_bottom
        )
        for cell in planned_cells
    ):
        raise RuntimeError("Renderer B planned ink outside its fixed support")

    damaged_indices = _damage_indices(
        planned_cells,
        entropy=entropy,
        damage_percent=damage_percent,
    )
    remaining_cells = tuple(
        cell for index, cell in enumerate(planned_cells) if index not in damaged_indices
    )
    upper_ink_count = sum(
        (cell.x1 - cell.x0) * (cell.y1 - cell.y0)
        for cell in remaining_cells
        if cell.tier == "upper"
    )
    lower_ink_count = sum(
        (cell.x1 - cell.x0) * (cell.y1 - cell.y0)
        for cell in remaining_cells
        if cell.tier == "lower"
    )
    if upper_ink_count <= 0 or lower_ink_count <= 0:
        raise RuntimeError("Renderer B damage removed a complete tier")

    ink_bbox = (
        min(cell.x0 for cell in remaining_cells),
        min(cell.y0 for cell in remaining_cells),
        max(cell.x1 for cell in remaining_cells),
        max(cell.y1 for cell in remaining_cells),
    )
    canvas.require_mutation_capacity(len(remaining_cells))
    for cell in remaining_cells:
        canvas.fill_ink_rect(cell.x0, cell.y0, cell.x1, cell.y1)

    return BitmapLabelReceipt(
        renderer_id=RENDERER_ID,
        ink_bbox=ink_bbox,
        upper_ink_count=upper_ink_count,
        lower_ink_count=lower_ink_count,
        mutation_delta=len(remaining_cells),
    )


__all__ = [
    "BITMAP_MASK_LIBRARY",
    "RENDERER_ID",
    "BitmapLabelReceipt",
    "KP1979V3RendererBError",
    "render_bitmap_label",
]
