"""Independent orthogonal-graph positive renderer for the KP1979 V3 control."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from indusbench.kp1979_v3_canvas import PixelCanvas

_RENDERER_ID = "orthogonal_graph_v1"
_ENTROPY_DOMAIN = b"indusbench/kp1979/v3/renderer-a/orthogonal-graph-v1\x00"
_UPPER_TIER_OFFSETS = (-26, -4)
_LOWER_TIER_OFFSETS = (4, 26)
_MAX_MUTATION_DELTA = 4096


@dataclass(frozen=True, slots=True)
class OrthogonalLabelReceipt:
    """Closed summary of the pixels written by Renderer A."""

    renderer_id: str
    ink_bbox: tuple[int, int, int, int]
    upper_ink_count: int
    lower_ink_count: int
    mutation_delta: int


def _entropy_material(entropy: bytes, length: int) -> bytes:
    material = bytearray()
    counter = 0
    while len(material) < length:
        material.extend(sha256(_ENTROPY_DOMAIN + counter.to_bytes(4, "big") + entropy).digest())
        counter += 1
    return bytes(material[:length])


def _bresenham_points(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> tuple[tuple[int, int], ...]:
    """Return an inclusive integer segment without using a shared drawing helper."""

    points: list[tuple[int, int]] = []
    delta_x = abs(x1 - x0)
    step_x = 1 if x0 < x1 else -1
    delta_y = -abs(y1 - y0)
    step_y = 1 if y0 < y1 else -1
    error = delta_x + delta_y
    x = x0
    y = y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            return tuple(points)
        doubled_error = 2 * error
        if doubled_error >= delta_y:
            error += delta_y
            x += step_x
        if doubled_error <= delta_x:
            error += delta_x
            y += step_y


def _segment_ink(
    segment: tuple[int, int, int, int],
    stroke_width: int,
) -> set[tuple[int, int]]:
    x0, y0, x1, y1 = segment
    negative_radius = (stroke_width - 1) // 2
    positive_radius = stroke_width - 1 - negative_radius
    points: set[tuple[int, int]] = set()
    for x, y in _bresenham_points(x0, y0, x1, y1):
        for offset_y in range(-negative_radius, positive_radius + 1):
            for offset_x in range(-negative_radius, positive_radius + 1):
                points.add((x + offset_x, y + offset_y))
    return points


def _glyph_ink(
    *,
    cell_x0: int,
    cell_width: int,
    tier_y0: int,
    tier_y1: int,
    stroke_width: int,
    token: int,
    qualifier_variant: int,
) -> tuple[set[tuple[int, int]], tuple[int, int]]:
    negative_radius = (stroke_width - 1) // 2
    positive_radius = stroke_width - 1 - negative_radius
    x_left = cell_x0 + negative_radius
    x_right = cell_x0 + cell_width - 1 - positive_radius
    x_middle = (x_left + x_right) // 2
    y_top = tier_y0 + negative_radius
    y_bottom = tier_y1 - 1 - positive_radius
    y_middle = (y_top + y_bottom) // 2

    top_goes_left = bool(token & 0b0001)
    bottom_goes_left = bool(token & 0b0010)
    outer_side = x_left if token & 0b0100 else x_right
    segments = [
        (x_middle, y_top, x_middle, y_bottom),
        (
            x_left if top_goes_left else x_middle,
            y_top,
            x_middle if top_goes_left else x_right,
            y_top,
        ),
        (
            x_middle if top_goes_left else x_left,
            y_middle,
            x_right if top_goes_left else x_middle,
            y_middle,
        ),
        (
            x_left if bottom_goes_left else x_middle,
            y_bottom,
            x_middle if bottom_goes_left else x_right,
            y_bottom,
        ),
        (outer_side, y_top, outer_side, y_middle),
    ]

    if token & 0b1000:
        quarter_y = y_top + (y_middle - y_top) // 2
        segments.append((x_left, quarter_y, x_right, quarter_y))

    if qualifier_variant in (1, 3):
        three_quarter_y = y_middle + (y_bottom - y_middle) // 2
        segments.append((x_left, three_quarter_y, x_right, three_quarter_y))
    if qualifier_variant in (2, 3):
        middle_side = x_right if top_goes_left else x_left
        segments.append((middle_side, y_middle, middle_side, y_bottom))

    points: set[tuple[int, int]] = set()
    for segment in segments:
        points.update(_segment_ink(segment, stroke_width))
    return points, (x_middle, y_middle)


def _tier_start(
    *,
    lane_x0: int,
    lane_x1: int,
    group_width: int,
    edge_offset: int,
    horizontal_alignment: str,
    jitter_token: int,
) -> int:
    minimum_margin = edge_offset if horizontal_alignment in {"left", "right"} else 2
    if group_width > lane_x1 - lane_x0 - 2 * minimum_margin:
        raise ValueError("lane is too narrow for the seeded orthogonal tier")
    if horizontal_alignment == "left":
        return lane_x0 + edge_offset
    if horizontal_alignment == "right":
        return lane_x1 - edge_offset - group_width

    centered = (lane_x0 + lane_x1 - group_width) // 2
    minimum = lane_x0 + 2
    maximum = lane_x1 - 2 - group_width
    jitter_limit = min(4, max(0, (maximum - minimum) // 2))
    if jitter_limit:
        centered += jitter_token % (2 * jitter_limit + 1) - jitter_limit
    return min(max(centered, minimum), maximum)


def _build_tier(
    *,
    count: int,
    lane_x0: int,
    lane_x1: int,
    tier_y0: int,
    tier_y1: int,
    cell_width: int,
    gap: int,
    edge_offset: int,
    horizontal_alignment: str,
    stroke_width: int,
    qualifier_variant: int,
    material: bytes,
    material_offset: int,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    group_width = count * cell_width + (count - 1) * gap
    start_x = _tier_start(
        lane_x0=lane_x0,
        lane_x1=lane_x1,
        group_width=group_width,
        edge_offset=edge_offset,
        horizontal_alignment=horizontal_alignment,
        jitter_token=material[material_offset],
    )
    points: set[tuple[int, int]] = set()
    protected: set[tuple[int, int]] = set()
    for index in range(count):
        cell_x0 = start_x + index * (cell_width + gap)
        glyph_points, core_point = _glyph_ink(
            cell_x0=cell_x0,
            cell_width=cell_width,
            tier_y0=tier_y0,
            tier_y1=tier_y1,
            stroke_width=stroke_width,
            token=material[material_offset + 1 + index],
            qualifier_variant=qualifier_variant,
        )
        points.update(glyph_points)
        protected.add(core_point)
    return points, protected


def _damage_points(
    *,
    points: set[tuple[int, int]],
    protected: set[tuple[int, int]],
    entropy: bytes,
    tier_tag: bytes,
    damage_percent: int,
) -> set[tuple[int, int]]:
    removal_count = len(points) * damage_percent // 100
    if removal_count == 0:
        return set()
    candidates = points - protected
    removal_count = min(removal_count, len(candidates), len(points) - 1)

    def damage_rank(point: tuple[int, int]) -> bytes:
        x, y = point
        return sha256(
            _ENTROPY_DOMAIN
            + b"damage\x00"
            + tier_tag
            + entropy
            + x.to_bytes(8, "big")
            + y.to_bytes(8, "big")
        ).digest()

    return set(sorted(candidates, key=damage_rank)[:removal_count])


def _validate_inputs(
    canvas: PixelCanvas,
    *,
    lane_bounds: tuple[int, int],
    anchor_y: int,
    entropy: bytes,
    stroke_width: int,
    qualifier_variant: int,
    damage_percent: int,
    horizontal_alignment: str,
) -> tuple[int, int]:
    width = getattr(canvas, "width", None)
    height = getattr(canvas, "height", None)
    if (
        type(width) is not int
        or type(height) is not int
        or width <= 0
        or height <= 0
        or not callable(getattr(canvas, "set_ink", None))
        or not callable(getattr(canvas, "clear_ink", None))
        or not callable(getattr(canvas, "require_mutation_capacity", None))
    ):
        raise ValueError("canvas does not satisfy the PixelCanvas contract")
    if (
        type(lane_bounds) is not tuple
        or len(lane_bounds) != 2
        or any(type(value) is not int for value in lane_bounds)
    ):
        raise ValueError("lane_bounds must be a pair of strict integers")
    lane_x0, lane_x1 = lane_bounds
    if not 0 <= lane_x0 < lane_x1 <= width:
        raise ValueError("lane_bounds are outside the canvas")
    if type(anchor_y) is not int or anchor_y - 28 < 0 or anchor_y + 28 > height:
        raise ValueError("anchor_y cannot contain the complete label envelope")
    if type(entropy) is not bytes or len(entropy) != 32:
        raise ValueError("entropy must contain exactly 32 bytes")
    if type(stroke_width) is not int or not 1 <= stroke_width <= 4:
        raise ValueError("stroke_width must be a strict integer from 1 through 4")
    if type(qualifier_variant) is not int or not 0 <= qualifier_variant <= 3:
        raise ValueError("qualifier_variant must be a strict integer from 0 through 3")
    if type(damage_percent) is not int or not 0 <= damage_percent <= 12:
        raise ValueError("damage_percent must be a strict integer from 0 through 12")
    if type(horizontal_alignment) is not str or horizontal_alignment not in {
        "left",
        "center",
        "right",
    }:
        raise ValueError("horizontal_alignment must be left, center, or right")
    return lane_x0, lane_x1


def render_orthogonal_label(
    canvas: PixelCanvas,
    *,
    lane_bounds: tuple[int, int],
    anchor_y: int,
    entropy: bytes,
    stroke_width: int,
    qualifier_variant: int,
    damage_percent: int,
    horizontal_alignment: str,
) -> OrthogonalLabelReceipt:
    """Render one deterministic two-tier orthogonal label inside a lane."""

    lane_x0, lane_x1 = _validate_inputs(
        canvas,
        lane_bounds=lane_bounds,
        anchor_y=anchor_y,
        entropy=entropy,
        stroke_width=stroke_width,
        qualifier_variant=qualifier_variant,
        damage_percent=damage_percent,
        horizontal_alignment=horizontal_alignment,
    )
    material = _entropy_material(entropy, 32)
    upper_count = 3 + material[0] % 3
    lower_count = 2 + material[1] % 3
    edge_offset = 2 + material[2] % 9
    gap = stroke_width + 2 + material[3] % 3
    minimum_cell_width = stroke_width + 4
    desired_cell_width = max(minimum_cell_width, 9 + material[4] % 5)
    available_width = lane_x1 - lane_x0 - 2 * edge_offset
    maximum_count = max(upper_count, lower_count)
    maximum_cell_width = (available_width - (maximum_count - 1) * gap) // maximum_count
    if maximum_cell_width < minimum_cell_width:
        raise ValueError("lane is too narrow for the seeded orthogonal label")
    cell_width = min(desired_cell_width, maximum_cell_width)

    upper_points, upper_protected = _build_tier(
        count=upper_count,
        lane_x0=lane_x0,
        lane_x1=lane_x1,
        tier_y0=anchor_y + _UPPER_TIER_OFFSETS[0],
        tier_y1=anchor_y + _UPPER_TIER_OFFSETS[1],
        cell_width=cell_width,
        gap=gap,
        edge_offset=edge_offset,
        horizontal_alignment=horizontal_alignment,
        stroke_width=stroke_width,
        qualifier_variant=qualifier_variant,
        material=material,
        material_offset=8,
    )
    lower_points, lower_protected = _build_tier(
        count=lower_count,
        lane_x0=lane_x0,
        lane_x1=lane_x1,
        tier_y0=anchor_y + _LOWER_TIER_OFFSETS[0],
        tier_y1=anchor_y + _LOWER_TIER_OFFSETS[1],
        cell_width=cell_width,
        gap=gap,
        edge_offset=edge_offset,
        horizontal_alignment=horizontal_alignment,
        stroke_width=stroke_width,
        qualifier_variant=qualifier_variant,
        material=material,
        material_offset=16,
    )
    planned_points = upper_points | lower_points
    if (
        not upper_points
        or not lower_points
        or any(
            not (lane_x0 <= x < lane_x1 and anchor_y - 28 <= y < anchor_y + 28)
            for x, y in planned_points
        )
    ):
        raise RuntimeError("Renderer A planned ink outside its fixed support")

    upper_damage = _damage_points(
        points=upper_points,
        protected=upper_protected,
        entropy=entropy,
        tier_tag=b"upper\x00",
        damage_percent=damage_percent,
    )
    lower_damage = _damage_points(
        points=lower_points,
        protected=lower_protected,
        entropy=entropy,
        tier_tag=b"lower\x00",
        damage_percent=damage_percent,
    )
    final_upper = upper_points - upper_damage
    final_lower = lower_points - lower_damage
    if not final_upper or not final_lower:
        raise RuntimeError("internal damage invariant removed a complete tier")

    final_points = final_upper | final_lower
    mutation_delta = len(final_points)
    if mutation_delta > _MAX_MUTATION_DELTA:
        raise RuntimeError("internal renderer mutation budget exceeded")
    canvas.require_mutation_capacity(mutation_delta)
    for x, y in sorted(final_points, key=lambda point: (point[1], point[0])):
        canvas.set_ink(x, y)

    x_values = [point[0] for point in final_points]
    y_values = [point[1] for point in final_points]
    return OrthogonalLabelReceipt(
        renderer_id=_RENDERER_ID,
        ink_bbox=(
            min(x_values),
            min(y_values),
            max(x_values) + 1,
            max(y_values) + 1,
        ),
        upper_ink_count=len(final_upper),
        lower_ink_count=len(final_lower),
        mutation_delta=mutation_delta,
    )


__all__ = ["OrthogonalLabelReceipt", "render_orthogonal_label"]
