"""Scale-normalized, label-specific layout proposals for KP1979 pages.

This module is deliberately separate from ``printed_concordance_layout``.
It neither changes the V1 detector nor reads page roles, OCR, identifiers,
reference values, or any corpus.  V2 first requires local two-tier label
structure and only then fits the surviving evidence to a two-lane lattice.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Final

DETECTOR_ALGORITHM_ID: Final = "two-column-label-lattice-v2"

PAGE_WIDTH: Final = 4880
PAGE_HEIGHT: Final = 7010
PAGE_SCAN_TOP: Final = 550
PAGE_SCAN_BOTTOM: Final = 6600
ROW_WINDOW_HEIGHT: Final = 96

MIN_ROW_PITCH: Final = 158
MAX_ROW_PITCH: Final = 172
MAX_LANE_PITCH_DIFFERENCE: Final = 3
MIN_LANE_CANDIDATES: Final = 15
MIN_CONTIGUOUS_RUN: Final = 18

MIN_SCAN_BAND_WIDTH: Final = 32
MAX_SCAN_BAND_WIDTH: Final = 512
MAX_TIER_RUNS: Final = 512
MIN_TIER_HEIGHT: Final = 3
MAX_TIER_HEIGHT: Final = 48
MIN_TIER_WIDTH: Final = 6
MAX_LABEL_SPAN: Final = ROW_WINDOW_HEIGHT
MIN_COLUMN_RUNS: Final = 2
MAX_COLUMN_RUNS: Final = 12

# Residual tolerance is ceil(pitch / 25), or about four percent of pitch.
PHASE_TOLERANCE_DENOMINATOR: Final = 25

STRIPE_SCAN_LEFT: Final = 120
STRIPE_SCAN_RIGHT: Final = 4710
STRIPE_WIDTH: Final = 170
MAX_STRUCTURED_STRIPES: Final = 6


class PrintedConcordanceLayoutV2Error(ValueError):
    """Raised when a bitmap or detector geometry is structurally invalid."""


@dataclass(frozen=True, slots=True)
class LaneLatticeProposalV2:
    """One evidence-first vertical label lattice.

    ``phase`` is the fitted phase of the label-evidence anchor.  Each returned
    candidate is a 96-pixel window whose ``candidate_y + 48`` anchor is the
    center of one independently observed two-tier block.
    """

    lane_index: int
    scan_bbox: tuple[int, int, int, int]
    pitch: int | None
    phase: int | None
    phase_tolerance: int
    two_tier_evidence_count: int
    aligned_evidence_count: int
    longest_contiguous_run: int
    candidate_y: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TwoColumnLayoutProposalV2:
    """A deterministic geometry-only V2 result which may safely abstain."""

    algorithm_id: str
    detection_status: str
    abstention_codes: tuple[str, ...]
    structured_stripe_count: int
    lanes: tuple[LaneLatticeProposalV2, ...]


@dataclass(frozen=True, slots=True)
class _TierSignature:
    y0: int
    y1: int
    x0: int
    x1: int
    ink: int
    column_runs: int


@dataclass(frozen=True, slots=True)
class _TwoTierEvidence:
    y0: int
    y1: int
    anchor_y: int


@dataclass(frozen=True, slots=True)
class _LatticeFit:
    pitch: int
    phase: int
    phase_tolerance: int
    longest_contiguous_run: int
    candidate_y: tuple[int, ...]


def detect_two_column_label_lattice_v2(
    page_pbm: bytes,
    *,
    width: int,
    height: int,
    scan_bands: tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
) -> TwoColumnLayoutProposalV2:
    """Propose two label lattices using bounded, scale-normalized evidence.

    A lane candidate must contain two vertically separated, horizontally
    associated, glyph-like tiers.  Tier height, gap, width, fill, overlap, and
    alignment are compared as ratios or relative bounds; total ink mass does
    not select a candidate.  Only those local candidates may vote for pitch
    and phase.
    """

    payload = _canonical_pbm_payload(page_pbm, width=width, height=height)
    _validate_scan_bands(scan_bands, width=width, height=height)

    lane_results = tuple(
        _analyse_lane(
            payload,
            width=width,
            height=height,
            band=band,
            lane_index=lane_index,
        )
        for lane_index, band in enumerate(scan_bands)
    )
    lanes = (lane_results[0][0], lane_results[1][0])
    structured_stripe_count, stripe_fragmented = _count_structured_stripes(
        payload,
        width=width,
        height=height,
    )

    abstention_codes: list[str] = []
    if any(fragmented for _, fragmented in lane_results) or stripe_fragmented:
        abstention_codes.append("excessive_tier_fragmentation")
    if any(lane.aligned_evidence_count < MIN_LANE_CANDIDATES for lane in lanes):
        abstention_codes.append("insufficient_two_tier_evidence")
    if any(lane.longest_contiguous_run < MIN_CONTIGUOUS_RUN for lane in lanes):
        abstention_codes.append("insufficient_contiguous_label_run")
    if (
        lanes[0].pitch is not None
        and lanes[1].pitch is not None
        and abs(lanes[0].pitch - lanes[1].pitch) > MAX_LANE_PITCH_DIFFERENCE
    ):
        abstention_codes.append("lane_pitch_disagreement")
    if structured_stripe_count > MAX_STRUCTURED_STRIPES:
        abstention_codes.append("multi_column_confound")

    return TwoColumnLayoutProposalV2(
        algorithm_id=DETECTOR_ALGORITHM_ID,
        detection_status="abstained" if abstention_codes else "proposed",
        abstention_codes=tuple(abstention_codes),
        structured_stripe_count=structured_stripe_count,
        lanes=lanes,
    )


def _canonical_pbm_payload(page_pbm: bytes, *, width: int, height: int) -> memoryview:
    if not isinstance(page_pbm, bytes):
        raise PrintedConcordanceLayoutV2Error("page bitmap must be supplied as exact bytes")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or (width, height) != (PAGE_WIDTH, PAGE_HEIGHT)
    ):
        raise PrintedConcordanceLayoutV2Error(
            "page dimensions differ from the fixed detector space"
        )
    header = f"P4\n{width} {height}\n".encode("ascii")
    if not page_pbm.startswith(header):
        raise PrintedConcordanceLayoutV2Error("page bitmap lacks the canonical raw PBM header")
    payload = memoryview(page_pbm)[len(header) :]
    if len(payload) != ((width + 7) // 8) * height:
        raise PrintedConcordanceLayoutV2Error("page bitmap payload has an invalid byte size")
    return payload


def _validate_scan_bands(
    scan_bands: tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
    *,
    width: int,
    height: int,
) -> None:
    if not isinstance(scan_bands, tuple) or len(scan_bands) != 2:
        raise PrintedConcordanceLayoutV2Error("exactly two detector scan bands are required")
    for band in scan_bands:
        if (
            not isinstance(band, tuple)
            or len(band) != 4
            or any(not isinstance(value, int) or isinstance(value, bool) for value in band)
        ):
            raise PrintedConcordanceLayoutV2Error("scan band must contain four integers")
        x0, y0, x1, y1 = band
        if (
            not 0 <= x0 < x1 <= width
            or not 0 <= y0 < y1 <= height
            or y0 != PAGE_SCAN_TOP
            or y1 != PAGE_SCAN_BOTTOM
            or not MIN_SCAN_BAND_WIDTH <= x1 - x0 <= MAX_SCAN_BAND_WIDTH
        ):
            raise PrintedConcordanceLayoutV2Error("scan band is outside the fixed detector space")
    if scan_bands[0][2] > scan_bands[1][0]:
        raise PrintedConcordanceLayoutV2Error("physical lane scan bands overlap")


def _analyse_lane(
    payload: memoryview,
    *,
    width: int,
    height: int,
    band: tuple[int, int, int, int],
    lane_index: int,
) -> tuple[LaneLatticeProposalV2, bool]:
    x0, y0, x1, y1 = band
    row_threshold = max(2, (x1 - x0 + 199) // 200)
    profile = _vertical_projection(
        payload,
        width=width,
        height=height,
        x0=x0,
        x1=x1,
    )
    runs, fragmented = _active_row_runs(
        profile,
        y0=y0,
        y1=y1,
        threshold=row_threshold,
    )
    if fragmented:
        return _empty_lane(lane_index=lane_index, band=band), True

    signatures = tuple(
        _tier_signature(
            payload,
            width=width,
            x0=x0,
            x1=x1,
            y0=run_y0,
            y1=run_y1,
        )
        for run_y0, run_y1 in runs
    )
    evidence = _two_tier_evidence(signatures, band_width=x1 - x0)
    fit = _fit_lattice(evidence)
    if fit is None:
        return (
            LaneLatticeProposalV2(
                lane_index=lane_index,
                scan_bbox=band,
                pitch=None,
                phase=None,
                phase_tolerance=0,
                two_tier_evidence_count=len(evidence),
                aligned_evidence_count=0,
                longest_contiguous_run=0,
                candidate_y=(),
            ),
            False,
        )
    return (
        LaneLatticeProposalV2(
            lane_index=lane_index,
            scan_bbox=band,
            pitch=fit.pitch,
            phase=fit.phase,
            phase_tolerance=fit.phase_tolerance,
            two_tier_evidence_count=len(evidence),
            aligned_evidence_count=len(fit.candidate_y),
            longest_contiguous_run=fit.longest_contiguous_run,
            candidate_y=fit.candidate_y,
        ),
        False,
    )


def _empty_lane(
    *,
    lane_index: int,
    band: tuple[int, int, int, int],
) -> LaneLatticeProposalV2:
    return LaneLatticeProposalV2(
        lane_index=lane_index,
        scan_bbox=band,
        pitch=None,
        phase=None,
        phase_tolerance=0,
        two_tier_evidence_count=0,
        aligned_evidence_count=0,
        longest_contiguous_run=0,
        candidate_y=(),
    )


def _active_row_runs(
    profile: list[int],
    *,
    y0: int,
    y1: int,
    threshold: int,
) -> tuple[tuple[tuple[int, int], ...], bool]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for y in range(y0, y1):
        if profile[y] >= threshold:
            if start is None:
                start = y
        elif start is not None:
            runs.append((start, y))
            if len(runs) > MAX_TIER_RUNS:
                return (), True
            start = None
    if start is not None:
        runs.append((start, y1))
    if len(runs) > MAX_TIER_RUNS:
        return (), True
    return tuple(runs), False


def _tier_signature(
    payload: memoryview,
    *,
    width: int,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
) -> _TierSignature:
    row_bytes = (width + 7) // 8
    active_columns = [False] * (x1 - x0)
    ink = 0
    for y in range(y0, y1):
        row = payload[y * row_bytes : (y + 1) * row_bytes]
        for local_x, x in enumerate(range(x0, x1)):
            if row[x // 8] & (128 >> (x % 8)):
                ink += 1
                active_columns[local_x] = True

    active_indices = tuple(index for index, active in enumerate(active_columns) if active)
    if not active_indices:
        return _TierSignature(y0, y1, x0, x0, 0, 0)
    first = active_indices[0]
    last = active_indices[-1]
    return _TierSignature(
        y0=y0,
        y1=y1,
        x0=x0 + first,
        x1=x0 + last + 1,
        ink=ink,
        column_runs=_column_run_count(active_columns[first : last + 1]),
    )


def _column_run_count(active_columns: list[bool]) -> int:
    count = 0
    previous = False
    for active in active_columns:
        if active and not previous:
            count += 1
        previous = active
    return count


def _two_tier_evidence(
    signatures: tuple[_TierSignature, ...],
    *,
    band_width: int,
) -> tuple[_TwoTierEvidence, ...]:
    plausible = tuple(
        signature for signature in signatures if _plausible_tier(signature, band_width=band_width)
    )
    result: list[_TwoTierEvidence] = []
    for index, (upper, lower) in enumerate(pairwise(plausible)):
        if not _isolated_pair(plausible, index=index):
            continue
        if not _plausible_pair(upper, lower):
            continue
        result.append(
            _TwoTierEvidence(
                y0=upper.y0,
                y1=lower.y1,
                anchor_y=(upper.y0 + lower.y1) // 2,
            )
        )
    return tuple(result)


def _plausible_tier(signature: _TierSignature, *, band_width: int) -> bool:
    height = signature.y1 - signature.y0
    width = signature.x1 - signature.x0
    area = height * width
    return (
        MIN_TIER_HEIGHT <= height <= MAX_TIER_HEIGHT
        and width >= MIN_TIER_WIDTH
        and width * 5 <= band_width * 4
        and MIN_COLUMN_RUNS <= signature.column_runs <= MAX_COLUMN_RUNS
        and signature.ink * 10 >= area
        and signature.ink * 20 <= area * 17
    )


def _isolated_pair(signatures: tuple[_TierSignature, ...], *, index: int) -> bool:
    upper = signatures[index]
    lower = signatures[index + 1]
    if index > 0 and upper.y0 - signatures[index - 1].y1 <= MAX_LABEL_SPAN:
        return False
    return not (
        index + 2 < len(signatures) and signatures[index + 2].y0 - lower.y1 <= MAX_LABEL_SPAN
    )


def _plausible_pair(upper: _TierSignature, lower: _TierSignature) -> bool:
    upper_height = upper.y1 - upper.y0
    lower_height = lower.y1 - lower.y0
    smaller_height = min(upper_height, lower_height)
    larger_height = max(upper_height, lower_height)
    gap = lower.y0 - upper.y1
    if (
        gap <= 0
        or lower.y1 - upper.y0 > MAX_LABEL_SPAN
        or larger_height > smaller_height * 2
        or gap * 5 < smaller_height
        or gap * 2 > larger_height * 3
    ):
        return False

    upper_width = upper.x1 - upper.x0
    lower_width = lower.x1 - lower.x0
    smaller_width = min(upper_width, lower_width)
    larger_width = max(upper_width, lower_width)
    overlap = min(upper.x1, lower.x1) - max(upper.x0, lower.x0)
    return (
        larger_width <= smaller_width * 2
        and overlap > 0
        and overlap * 4 >= smaller_width
        and abs(upper.x0 - lower.x0) <= max(20, smaller_width * 3 // 4)
    )


def _fit_lattice(evidence: tuple[_TwoTierEvidence, ...]) -> _LatticeFit | None:
    if not evidence:
        return None

    best: tuple[tuple[int, int, int, int, int], _LatticeFit] | None = None
    for pitch in range(MIN_ROW_PITCH, MAX_ROW_PITCH + 1):
        tolerance = (pitch + PHASE_TOLERANCE_DENOMINATOR - 1) // (PHASE_TOLERANCE_DENOMINATOR)
        for phase in range(pitch):
            selected: dict[int, tuple[int, _TwoTierEvidence]] = {}
            for item in evidence:
                residual = _phase_residual(item.anchor_y, pitch=pitch, phase=phase)
                if residual > tolerance:
                    continue
                slot = _nearest_slot(item.anchor_y, pitch=pitch, phase=phase)
                current = selected.get(slot)
                if current is None or (residual, item.anchor_y) < (
                    current[0],
                    current[1].anchor_y,
                ):
                    selected[slot] = (residual, item)

            slots = tuple(sorted(selected))
            longest = _longest_slot_run(slots)
            residual_sum = sum(selected[slot][0] for slot in slots)
            candidate_y = tuple(selected[slot][1].anchor_y - 48 for slot in slots)
            fit = _LatticeFit(
                pitch=pitch,
                phase=phase,
                phase_tolerance=tolerance,
                longest_contiguous_run=longest,
                candidate_y=candidate_y,
            )
            rank = (
                len(candidate_y),
                longest,
                -residual_sum,
                -pitch,
                -phase,
            )
            if best is None or rank > best[0]:
                best = (rank, fit)
    if best is None:
        return None
    return best[1]


def _phase_residual(value: int, *, pitch: int, phase: int) -> int:
    remainder = (value - phase) % pitch
    return min(remainder, pitch - remainder)


def _nearest_slot(value: int, *, pitch: int, phase: int) -> int:
    quotient, remainder = divmod(value - phase, pitch)
    if remainder * 2 >= pitch:
        quotient += 1
    return quotient


def _longest_slot_run(slots: tuple[int, ...]) -> int:
    if not slots:
        return 0
    longest = 1
    current = 1
    for previous, current_slot in pairwise(slots):
        current = current + 1 if current_slot - previous == 1 else 1
        longest = max(longest, current)
    return longest


def _count_structured_stripes(
    payload: memoryview,
    *,
    width: int,
    height: int,
) -> tuple[int, bool]:
    count = 0
    fragmented = False
    scan_right = min(width, STRIPE_SCAN_RIGHT)
    for stripe_index, x0 in enumerate(range(STRIPE_SCAN_LEFT, scan_right, STRIPE_WIDTH)):
        x1 = min(x0 + STRIPE_WIDTH, scan_right)
        if x1 - x0 < MIN_SCAN_BAND_WIDTH:
            continue
        lane, lane_fragmented = _analyse_lane(
            payload,
            width=width,
            height=height,
            band=(x0, PAGE_SCAN_TOP, x1, PAGE_SCAN_BOTTOM),
            lane_index=stripe_index,
        )
        fragmented = fragmented or lane_fragmented
        if (
            lane.aligned_evidence_count >= MIN_LANE_CANDIDATES
            and lane.longest_contiguous_run >= MIN_CONTIGUOUS_RUN
        ):
            count += 1
    return count, fragmented


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


__all__ = [
    "DETECTOR_ALGORITHM_ID",
    "LaneLatticeProposalV2",
    "PrintedConcordanceLayoutV2Error",
    "TwoColumnLayoutProposalV2",
    "detect_two_column_label_lattice_v2",
]
