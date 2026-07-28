"""Pixel-only, abstaining layout proposals for printed concordance pages."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Final

PAGE_SCAN_TOP: Final = 550
PAGE_SCAN_BOTTOM: Final = 6600
ROW_WINDOW_HEIGHT: Final = 96
MIN_ROW_PITCH: Final = 158
MAX_ROW_PITCH: Final = 172
SCORE_SLOT_LIMIT: Final = 24
MIN_SLOT_SIGNAL: Final = 80
MIN_LANE_CANDIDATES: Final = 15
MIN_CONTIGUOUS_RUN: Final = 18
MAX_LANE_PITCH_DIFFERENCE: Final = 3
STRIPE_SCAN_LEFT: Final = 120
STRIPE_SCAN_RIGHT: Final = 4710
STRIPE_WIDTH: Final = 170
MAX_REPEATED_STRIPES: Final = 14


class PrintedConcordanceLayoutError(ValueError):
    """Raised when a bitmap or layout configuration is structurally invalid."""


@dataclass(frozen=True)
class LaneLatticeProposal:
    """One proposal-only vertical label lattice."""

    lane_index: int
    scan_bbox: tuple[int, int, int, int]
    pitch: int
    phase: int
    threshold: int
    longest_contiguous_run: int
    candidate_y: tuple[int, ...]


@dataclass(frozen=True)
class TwoColumnLayoutProposal:
    """A geometry-only detector result which may safely abstain."""

    algorithm_id: str
    detection_status: str
    abstention_codes: tuple[str, ...]
    repeated_stripe_count: int
    lanes: tuple[LaneLatticeProposal, ...]


def detect_two_column_label_lattice(
    page_pbm: bytes,
    *,
    width: int,
    height: int,
    scan_bands: tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
) -> TwoColumnLayoutProposal:
    """Propose two label lattices using only native black/white page pixels.

    The routine does not inspect OCR, identifiers, signs, a corpus, or a page
    role. A regular ten-column sign list and prose-like false positive must
    therefore be rejected by the same pixel tests used for corpus pages.
    """

    payload = _canonical_pbm_payload(page_pbm, width=width, height=height)
    if len(scan_bands) != 2:
        raise PrintedConcordanceLayoutError("exactly two detector scan bands are required")
    for band in scan_bands:
        _validate_scan_band(band, width=width, height=height)

    lanes = tuple(
        _fit_lane(
            payload,
            width=width,
            height=height,
            band=band,
            lane_index=lane_index,
        )
        for lane_index, band in enumerate(scan_bands)
    )
    consensus_pitch = min(lane.pitch for lane in lanes)
    repeated_stripe_count = _count_repeated_stripes(
        payload,
        width=width,
        height=height,
        pitch=consensus_pitch,
        phase=lanes[0].phase,
    )

    abstention_codes: list[str] = []
    if any(len(lane.candidate_y) < MIN_LANE_CANDIDATES for lane in lanes):
        abstention_codes.append("insufficient_lane_signal")
    if any(lane.longest_contiguous_run < MIN_CONTIGUOUS_RUN for lane in lanes):
        abstention_codes.append("insufficient_contiguous_run")
    if abs(lanes[0].pitch - lanes[1].pitch) > MAX_LANE_PITCH_DIFFERENCE:
        abstention_codes.append("lane_pitch_disagreement")
    if repeated_stripe_count > MAX_REPEATED_STRIPES:
        abstention_codes.append("multi_column_confound")

    return TwoColumnLayoutProposal(
        algorithm_id="two-column-label-lattice-v1",
        detection_status="abstained" if abstention_codes else "proposed",
        abstention_codes=tuple(abstention_codes),
        repeated_stripe_count=repeated_stripe_count,
        lanes=lanes,
    )


def _canonical_pbm_payload(page_pbm: bytes, *, width: int, height: int) -> memoryview:
    if not isinstance(page_pbm, bytes):
        raise PrintedConcordanceLayoutError("page bitmap must be supplied as exact bytes")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or width < 1
        or height < 1
    ):
        raise PrintedConcordanceLayoutError("page dimensions are invalid")
    header = f"P4\n{width} {height}\n".encode("ascii")
    if not page_pbm.startswith(header):
        raise PrintedConcordanceLayoutError("page bitmap lacks the canonical raw PBM header")
    payload = memoryview(page_pbm)[len(header) :]
    if len(payload) != ((width + 7) // 8) * height:
        raise PrintedConcordanceLayoutError("page bitmap payload has an invalid byte size")
    return payload


def _validate_scan_band(
    band: tuple[int, int, int, int],
    *,
    width: int,
    height: int,
) -> None:
    if len(band) != 4 or any(
        not isinstance(value, int) or isinstance(value, bool) for value in band
    ):
        raise PrintedConcordanceLayoutError("scan band must contain four integers")
    x0, y0, x1, y1 = band
    if (
        not 0 <= x0 < x1 <= width
        or not 0 <= y0 < y1 <= height
        or y0 != PAGE_SCAN_TOP
        or y1 != PAGE_SCAN_BOTTOM
    ):
        raise PrintedConcordanceLayoutError("scan band is outside the fixed detector space")


def _fit_lane(
    payload: memoryview,
    *,
    width: int,
    height: int,
    band: tuple[int, int, int, int],
    lane_index: int,
) -> LaneLatticeProposal:
    x0, _, x1, _ = band
    profile = _vertical_projection(
        payload,
        width=width,
        height=height,
        x0=x0,
        x1=x1,
    )
    prefix = _prefix_sums(profile)
    best: tuple[tuple[int, int, int], int, int, tuple[int, ...], tuple[int, ...]] | None = None
    for pitch in range(MIN_ROW_PITCH, MAX_ROW_PITCH + 1):
        for phase in range(pitch):
            positions = tuple(
                range(
                    PAGE_SCAN_TOP + ((phase - PAGE_SCAN_TOP) % pitch),
                    PAGE_SCAN_BOTTOM,
                    pitch,
                )
            )
            signals = tuple(_window_sum(prefix, y, height=height) for y in positions)
            score = sum(sorted(signals, reverse=True)[:SCORE_SLOT_LIMIT])
            rank = (score, -pitch, -phase)
            if best is None or rank > best[0]:
                best = (rank, pitch, phase, signals, positions)
    if best is None:
        raise PrintedConcordanceLayoutError("no finite lane lattice could be fitted")

    _, pitch, phase, signals, positions = best
    positive = sorted(signal for signal in signals if signal > 0)
    median_positive = positive[len(positive) // 2] if positive else 0
    threshold = max(MIN_SLOT_SIGNAL, median_positive // 5)
    candidate_y = tuple(
        y for y, signal in zip(positions, signals, strict=True) if signal >= threshold
    )
    return LaneLatticeProposal(
        lane_index=lane_index,
        scan_bbox=band,
        pitch=pitch,
        phase=phase,
        threshold=threshold,
        longest_contiguous_run=_longest_pitch_run(candidate_y, pitch=pitch),
        candidate_y=candidate_y,
    )


def _count_repeated_stripes(
    payload: memoryview,
    *,
    width: int,
    height: int,
    pitch: int,
    phase: int,
) -> int:
    positions = tuple(
        range(
            PAGE_SCAN_TOP + ((phase - PAGE_SCAN_TOP) % pitch),
            PAGE_SCAN_BOTTOM,
            pitch,
        )
    )
    repeated = 0
    for x0 in range(STRIPE_SCAN_LEFT, STRIPE_SCAN_RIGHT, STRIPE_WIDTH):
        profile = _vertical_projection(
            payload,
            width=width,
            height=height,
            x0=x0,
            x1=x0 + STRIPE_WIDTH,
        )
        prefix = _prefix_sums(profile)
        signals = tuple(_window_sum(prefix, y, height=height) for y in positions)
        positive = sorted(signal for signal in signals if signal > 0)
        median_positive = positive[len(positive) // 2] if positive else 0
        threshold = max(MIN_SLOT_SIGNAL, median_positive // 5)
        candidate_y = tuple(
            y for y, signal in zip(positions, signals, strict=True) if signal >= threshold
        )
        if _longest_pitch_run(candidate_y, pitch=pitch) >= MIN_CONTIGUOUS_RUN:
            repeated += 1
    return repeated


def _vertical_projection(
    payload: memoryview,
    *,
    width: int,
    height: int,
    x0: int,
    x1: int,
) -> list[int]:
    row_bytes = (width + 7) // 8
    return [
        _black_count(
            payload[y * row_bytes : (y + 1) * row_bytes],
            x0=x0,
            x1=x1,
        )
        for y in range(height)
    ]


def _black_count(row: memoryview, *, x0: int, x1: int) -> int:
    first_byte = x0 // 8
    end_byte = (x1 + 7) // 8
    packed = int.from_bytes(row[first_byte:end_byte])
    packed >>= end_byte * 8 - x1
    return (packed & ((1 << (x1 - x0)) - 1)).bit_count()


def _prefix_sums(values: list[int]) -> list[int]:
    result = [0]
    for value in values:
        result.append(result[-1] + value)
    return result


def _window_sum(prefix: list[int], y: int, *, height: int) -> int:
    return prefix[min(height, y + ROW_WINDOW_HEIGHT)] - prefix[y]


def _longest_pitch_run(candidate_y: tuple[int, ...], *, pitch: int) -> int:
    if not candidate_y:
        return 0
    longest = 1
    current = 1
    for previous, current_y in pairwise(candidate_y):
        current = current + 1 if current_y - previous == pitch else 1
        longest = max(longest, current)
    return longest
