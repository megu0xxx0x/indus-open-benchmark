"""Known-truth synthetic qualification for the KP1979 V1 label-lattice detector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from indusbench.kp1979_label_scoring import (
    LabelPositionScore,
    LabelPrediction,
    LabelReferenceInterval,
    _score_label_positions,
)
from indusbench.printed_concordance_layout import (
    LaneLatticeProposal,
    TwoColumnLayoutProposal,
    detect_two_column_label_lattice,
)

CONTROL_ID = "kp1979-label-lattice-synthetic-control-v1"
TARGET_ALGORITHM_ID = "two-column-label-lattice-v1"

# These are independent protocol literals. No detector constant is imported.
SYNTHETIC_PAGE_WIDTH = 4880
SYNTHETIC_PAGE_HEIGHT = 7010
SYNTHETIC_ROW_BYTES = 610
SYNTHETIC_PBM_HEADER = b"P4\n4880 7010\n"
SYNTHETIC_PBM_BYTE_SIZE = 4_276_113
SYNTHETIC_SCAN_BANDS = (
    (2056, 550, 2316, 6600),
    (4232, 550, 4492, 6600),
)

CaseClass = Literal["positive", "negative"]
ControlStatus = Literal["qualified", "not_qualified"]


class KP1979SyntheticControlError(ValueError):
    """Raised when a synthetic-control input differs from the fixed protocol."""


@dataclass(frozen=True, slots=True)
class SyntheticFixture:
    """One canonical synthetic page and its generator-known reference intervals."""

    case_id: str
    case_class: CaseClass
    pdf_page_number: int
    pbm_bytes: bytes
    references: tuple[LabelReferenceInterval, ...]


@dataclass(frozen=True, slots=True)
class SyntheticCaseResult:
    """One detector/scorer result on a fixed synthetic case."""

    case_id: str
    case_class: CaseClass
    passed: bool
    detector_algorithm_id: str
    detector_status: str
    scorer_status: str
    prediction_count: int
    reference_count: int
    micro_precision: float | None
    micro_recall: float | None
    negative_control_empty: bool | None


@dataclass(frozen=True, slots=True)
class MetamorphicResult:
    """One deterministic or equivariant synthetic relation."""

    relation_id: str
    passed: bool


@dataclass(frozen=True, slots=True)
class SyntheticControlReport:
    """Complete fail-closed qualification report for the current V1 detector."""

    control_id: str
    target_algorithm_id: str
    status: ControlStatus
    case_count: int
    positive_case_count: int
    negative_case_count: int
    passed_case_count: int
    cases: tuple[SyntheticCaseResult, ...]
    metamorphic_checks: tuple[MetamorphicResult, ...]
    reference_use: Literal["synthetic_control"]
    synthetic_only: bool
    real_accuracy: bool
    reference_accepted: bool
    future_evaluation_opened: bool
    reserved_sources_read: bool
    decipherment: bool
    prize_submission_eligible: bool


@dataclass(frozen=True, slots=True)
class _CaseDefinition:
    case_id: str
    case_class: CaseClass
    renderer: str
    pdf_page_number: int
    left_pitch: int = 165
    right_pitch: int = 165
    start_y: int = 620
    scale: int = 4
    jitter: tuple[int, ...] = (0,)
    lane_limits: tuple[int | None, int | None] = (None, None)


_CASE_DEFINITIONS = (
    _CaseDefinition("positive_clean", "positive", "labels", 1),
    _CaseDefinition(
        "positive_pitch_158",
        "positive",
        "labels",
        2,
        left_pitch=158,
        right_pitch=158,
    ),
    _CaseDefinition(
        "positive_pitch_172",
        "positive",
        "labels",
        3,
        left_pitch=172,
        right_pitch=172,
    ),
    _CaseDefinition("positive_phase_shift", "positive", "labels", 4, start_y=651),
    _CaseDefinition(
        "positive_y_jitter",
        "positive",
        "labels",
        5,
        jitter=(0, 4, -4, 2, -2),
    ),
    _CaseDefinition("positive_thin_strokes", "positive", "labels", 6, scale=2),
    _CaseDefinition(
        "positive_partial_lanes",
        "positive",
        "labels",
        7,
        lane_limits=(27, 31),
    ),
    _CaseDefinition("negative_blank", "negative", "blank", 8),
    _CaseDefinition("negative_single_lane", "negative", "single_lane", 9),
    _CaseDefinition(
        "negative_pitch_mismatch",
        "negative",
        "pitch_mismatch",
        10,
        left_pitch=165,
        right_pitch=172,
    ),
    _CaseDefinition("negative_discontinuous_lane", "negative", "discontinuous", 11),
    _CaseDefinition("negative_multi_column", "negative", "multi_column", 12),
    _CaseDefinition(
        "negative_periodic_non_label_bands",
        "negative",
        "periodic_non_label",
        13,
    ),
)

SYNTHETIC_CASE_COUNT = 13
SYNTHETIC_POSITIVE_CASE_COUNT = 7
SYNTHETIC_NEGATIVE_CASE_COUNT = 6
SYNTHETIC_METAMORPHIC_CHECK_COUNT = 3

_GLYPHS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "'": ("010", "010", "000", "000", "000"),
    "?": ("111", "001", "011", "000", "010"),
}


class _Bitmap:
    def __init__(self) -> None:
        self.payload = bytearray(SYNTHETIC_ROW_BYTES * SYNTHETIC_PAGE_HEIGHT)

    def rectangle(self, x0: int, y0: int, x1: int, y1: int) -> None:
        if not (0 <= x0 < x1 <= SYNTHETIC_PAGE_WIDTH and 0 <= y0 < y1 <= SYNTHETIC_PAGE_HEIGHT):
            raise KP1979SyntheticControlError("synthetic rectangle is outside the page")
        first_byte = x0 // 8
        last_byte = (x1 - 1) // 8
        first_mask = 0xFF >> (x0 % 8)
        last_mask = (0xFF << (7 - ((x1 - 1) % 8))) & 0xFF
        for y in range(y0, y1):
            offset = y * SYNTHETIC_ROW_BYTES
            if first_byte == last_byte:
                self.payload[offset + first_byte] |= first_mask & last_mask
                continue
            self.payload[offset + first_byte] |= first_mask
            if last_byte > first_byte + 1:
                self.payload[offset + first_byte + 1 : offset + last_byte] = b"\xff" * (
                    last_byte - first_byte - 1
                )
            self.payload[offset + last_byte] |= last_mask

    def pbm_bytes(self) -> bytes:
        result = SYNTHETIC_PBM_HEADER + bytes(self.payload)
        if len(result) != SYNTHETIC_PBM_BYTE_SIZE:
            raise KP1979SyntheticControlError("synthetic PBM size is not canonical")
        return result


def synthetic_case_ids() -> tuple[str, ...]:
    """Return the fixed, public case roster in canonical order."""

    return tuple(definition.case_id for definition in _CASE_DEFINITIONS)


def build_synthetic_fixture(case_id: str) -> SyntheticFixture:
    """Build one exact fixed synthetic fixture by public case identifier."""

    definition = _definition(case_id)
    return _build_fixture(definition, vertical_offset=0, top_margin_marks=False)


def evaluate_synthetic_fixture(fixture: SyntheticFixture) -> SyntheticCaseResult:
    """Evaluate one fixture only if it equals its canonical generated bytes."""

    if not isinstance(fixture, SyntheticFixture):
        raise KP1979SyntheticControlError("fixture must be a SyntheticFixture")
    canonical = build_synthetic_fixture(fixture.case_id)
    if fixture != canonical:
        raise KP1979SyntheticControlError("fixture differs from the canonical generator")
    return _evaluate_fixture(fixture)


def run_synthetic_control() -> SyntheticControlReport:
    """Run every fixed case and metamorphic relation without external inputs."""

    if (
        len(_CASE_DEFINITIONS) != SYNTHETIC_CASE_COUNT
        or sum(case.case_class == "positive" for case in _CASE_DEFINITIONS)
        != SYNTHETIC_POSITIVE_CASE_COUNT
        or sum(case.case_class == "negative" for case in _CASE_DEFINITIONS)
        != SYNTHETIC_NEGATIVE_CASE_COUNT
    ):
        raise KP1979SyntheticControlError("synthetic case roster differs from its freeze")

    cases = tuple(
        _evaluate_fixture(_build_fixture(definition, 0, False)) for definition in _CASE_DEFINITIONS
    )
    metamorphic_checks = _metamorphic_checks()
    if len(metamorphic_checks) != SYNTHETIC_METAMORPHIC_CHECK_COUNT:
        raise KP1979SyntheticControlError("synthetic metamorphic roster differs from its freeze")
    qualified = all(case.passed for case in cases) and all(
        check.passed for check in metamorphic_checks
    )
    return SyntheticControlReport(
        control_id=CONTROL_ID,
        target_algorithm_id=TARGET_ALGORITHM_ID,
        status="qualified" if qualified else "not_qualified",
        case_count=len(cases),
        positive_case_count=sum(case.case_class == "positive" for case in cases),
        negative_case_count=sum(case.case_class == "negative" for case in cases),
        passed_case_count=sum(case.passed for case in cases),
        cases=cases,
        metamorphic_checks=metamorphic_checks,
        reference_use="synthetic_control",
        synthetic_only=True,
        real_accuracy=False,
        reference_accepted=False,
        future_evaluation_opened=False,
        reserved_sources_read=False,
        decipherment=False,
        prize_submission_eligible=False,
    )


def _definition(case_id: str) -> _CaseDefinition:
    if not isinstance(case_id, str) or not case_id:
        raise KP1979SyntheticControlError("synthetic case id must be a nonempty string")
    matches = tuple(case for case in _CASE_DEFINITIONS if case.case_id == case_id)
    if len(matches) != 1:
        raise KP1979SyntheticControlError("synthetic case id is not in the fixed roster")
    return matches[0]


def _build_fixture(
    definition: _CaseDefinition,
    vertical_offset: int,
    top_margin_marks: bool,
) -> SyntheticFixture:
    bitmap = _Bitmap()
    references: list[LabelReferenceInterval] = []
    if definition.renderer == "labels":
        for lane_index in (0, 1):
            _draw_label_lattice(
                bitmap,
                page=definition.pdf_page_number,
                lane_index=lane_index,
                pitch=(definition.left_pitch if lane_index == 0 else definition.right_pitch),
                start_y=definition.start_y + vertical_offset,
                scale=definition.scale,
                jitter=definition.jitter,
                limit=definition.lane_limits[lane_index],
                every=1,
                references=references,
            )
    elif definition.renderer == "single_lane":
        _draw_label_lattice(
            bitmap,
            page=definition.pdf_page_number,
            lane_index=0,
            pitch=165,
            start_y=620 + vertical_offset,
            scale=4,
            jitter=(0,),
            limit=None,
            every=1,
            references=None,
        )
    elif definition.renderer == "pitch_mismatch":
        for lane_index, pitch in enumerate((definition.left_pitch, definition.right_pitch)):
            _draw_label_lattice(
                bitmap,
                page=definition.pdf_page_number,
                lane_index=lane_index,
                pitch=pitch,
                start_y=620 + vertical_offset,
                scale=4,
                jitter=(0,),
                limit=None,
                every=1,
                references=None,
            )
    elif definition.renderer == "discontinuous":
        for lane_index, every in enumerate((2, 1)):
            _draw_label_lattice(
                bitmap,
                page=definition.pdf_page_number,
                lane_index=lane_index,
                pitch=165,
                start_y=620 + vertical_offset,
                scale=4,
                jitter=(0,),
                limit=None,
                every=every,
                references=None,
            )
    elif definition.renderer == "multi_column":
        for x0 in range(200, 4700, 190):
            for y in range(620 + vertical_offset, 6500 + vertical_offset, 165):
                bitmap.rectangle(x0, y, x0 + 150, y + 24)
                bitmap.rectangle(x0 + 18, y + 48, x0 + 150, y + 72)
    elif definition.renderer == "periodic_non_label":
        for x0, _, x1, _ in SYNTHETIC_SCAN_BANDS:
            for y in range(620 + vertical_offset, 6500 + vertical_offset, 165):
                bitmap.rectangle(x0 + 20, y, x1 - 20, y + 18)
    elif definition.renderer != "blank":
        raise KP1979SyntheticControlError("synthetic renderer is invalid")

    if top_margin_marks:
        for y in range(40, 400, 17):
            bitmap.rectangle(100, y, 4700, y + 3)
    return SyntheticFixture(
        case_id=definition.case_id,
        case_class=definition.case_class,
        pdf_page_number=definition.pdf_page_number,
        pbm_bytes=bitmap.pbm_bytes(),
        references=tuple(sorted(references)),
    )


def _draw_label_lattice(
    bitmap: _Bitmap,
    *,
    page: int,
    lane_index: int,
    pitch: int,
    start_y: int,
    scale: int,
    jitter: tuple[int, ...],
    limit: int | None,
    every: int,
    references: list[LabelReferenceInterval] | None,
) -> None:
    x0 = SYNTHETIC_SCAN_BANDS[lane_index][0] + 20
    for row_index, base_y in enumerate(range(start_y, 6500, pitch)):
        if limit is not None and row_index >= limit:
            break
        if row_index % every:
            continue
        y = base_y + jitter[row_index % len(jitter)]
        upper = f"{(row_index * 7 + lane_index * 3) % 1000:03d}"
        lower = f"{(row_index * 11 + 5) % 100:02d}"
        lower += "?" if row_index % 7 == 0 else "'"
        _draw_text(bitmap, upper, x0, y, scale)
        _draw_text(bitmap, lower, x0 + 15, y + 8 * scale, scale)
        y1 = y + 13 * scale
        if references is not None:
            references.append(LabelReferenceInterval(page, lane_index, y, y1))


def _draw_text(bitmap: _Bitmap, text: str, x0: int, y0: int, scale: int) -> None:
    x = x0
    for character in text:
        glyph = _GLYPHS[character]
        for row_index, row in enumerate(glyph):
            for column_index, value in enumerate(row):
                if value == "1":
                    bitmap.rectangle(
                        x + column_index * scale,
                        y0 + row_index * scale,
                        x + (column_index + 1) * scale,
                        y0 + (row_index + 1) * scale,
                    )
        x += 4 * scale


def _evaluate_fixture(fixture: SyntheticFixture) -> SyntheticCaseResult:
    _require_canonical_pbm(fixture.pbm_bytes)
    proposal = detect_two_column_label_lattice(
        fixture.pbm_bytes,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )
    predictions = _predictions(fixture, proposal.detection_status, proposal.lanes)
    score = _score_fixture(fixture, predictions)
    algorithm_matches = proposal.algorithm_id == TARGET_ALGORITHM_ID
    if fixture.case_class == "positive":
        passed = (
            algorithm_matches
            and score.status == "scored"
            and score.micro_precision == 1.0
            and score.micro_recall == 1.0
        )
    else:
        passed = (
            algorithm_matches and score.status == "scored" and score.negative_control_empty is True
        )
    return SyntheticCaseResult(
        case_id=fixture.case_id,
        case_class=fixture.case_class,
        passed=passed,
        detector_algorithm_id=proposal.algorithm_id,
        detector_status=proposal.detection_status,
        scorer_status=score.status,
        prediction_count=len(predictions),
        reference_count=len(fixture.references),
        micro_precision=score.micro_precision,
        micro_recall=score.micro_recall,
        negative_control_empty=score.negative_control_empty,
    )


def _predictions(
    fixture: SyntheticFixture,
    detection_status: str,
    lanes: tuple[LaneLatticeProposal, ...],
) -> tuple[LabelPrediction, ...]:
    if detection_status != "proposed":
        return ()
    result: list[LabelPrediction] = []
    for lane in lanes:
        for y0 in lane.candidate_y:
            result.append(
                LabelPrediction(
                    fixture.pdf_page_number,
                    lane.lane_index,
                    y0,
                    y0 + 96,
                )
            )
    return tuple(result)


def _score_fixture(
    fixture: SyntheticFixture,
    predictions: tuple[LabelPrediction, ...],
) -> LabelPositionScore:
    return _score_label_positions(
        predictions,
        fixture.references,
        reference_use="synthetic_control",
        positive_pages=([fixture.pdf_page_number] if fixture.case_class == "positive" else []),
        negative_pages=([fixture.pdf_page_number] if fixture.case_class == "negative" else []),
    )


def _metamorphic_checks() -> tuple[MetamorphicResult, ...]:
    clean = _definition("positive_clean")
    base = _build_fixture(clean, 0, False)
    base_proposal = detect_two_column_label_lattice(
        base.pbm_bytes,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )
    repeated_proposal = detect_two_column_label_lattice(
        base.pbm_bytes,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )
    margin = _build_fixture(clean, 0, True)
    margin_proposal = detect_two_column_label_lattice(
        margin.pbm_bytes,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )
    shifted = _build_fixture(clean, 7, False)
    shifted_proposal = detect_two_column_label_lattice(
        shifted.pbm_bytes,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )
    return (
        MetamorphicResult(
            "identical_input_reproducibility",
            base_proposal == repeated_proposal
            and _evaluate_fixture(base) == _evaluate_fixture(base),
        ),
        MetamorphicResult(
            "unread_top_margin_invariance",
            base.references == margin.references and base_proposal == margin_proposal,
        ),
        MetamorphicResult(
            "vertical_translation_equivariance",
            _vertically_equivalent(base_proposal, shifted_proposal, delta=7)
            and tuple(
                LabelReferenceInterval(
                    reference.pdf_page_number,
                    reference.lane_index,
                    reference.y0 + 7,
                    reference.y1 + 7,
                )
                for reference in base.references
            )
            == shifted.references
            and _evaluate_fixture(base).passed == _evaluate_fixture(shifted).passed,
        ),
    )


def _vertically_equivalent(
    base: TwoColumnLayoutProposal,
    shifted: TwoColumnLayoutProposal,
    *,
    delta: int,
) -> bool:
    if (
        base.algorithm_id != shifted.algorithm_id
        or base.detection_status != shifted.detection_status
        or base.abstention_codes != shifted.abstention_codes
        or base.repeated_stripe_count != shifted.repeated_stripe_count
        or len(base.lanes) != len(shifted.lanes)
    ):
        return False
    for base_lane, shifted_lane in zip(base.lanes, shifted.lanes, strict=True):
        if (
            base_lane.lane_index != shifted_lane.lane_index
            or base_lane.scan_bbox != shifted_lane.scan_bbox
            or base_lane.pitch != shifted_lane.pitch
            or base_lane.threshold != shifted_lane.threshold
            or base_lane.longest_contiguous_run != shifted_lane.longest_contiguous_run
            or tuple(y + delta for y in base_lane.candidate_y) != shifted_lane.candidate_y
        ):
            return False
    return True


def _require_canonical_pbm(pbm_bytes: bytes) -> None:
    if (
        not isinstance(pbm_bytes, bytes)
        or len(pbm_bytes) != SYNTHETIC_PBM_BYTE_SIZE
        or not pbm_bytes.startswith(SYNTHETIC_PBM_HEADER)
    ):
        raise KP1979SyntheticControlError("synthetic PBM is not canonical")


__all__ = [
    "CONTROL_ID",
    "SYNTHETIC_CASE_COUNT",
    "SYNTHETIC_METAMORPHIC_CHECK_COUNT",
    "SYNTHETIC_NEGATIVE_CASE_COUNT",
    "SYNTHETIC_PAGE_HEIGHT",
    "SYNTHETIC_PAGE_WIDTH",
    "SYNTHETIC_PBM_BYTE_SIZE",
    "SYNTHETIC_POSITIVE_CASE_COUNT",
    "TARGET_ALGORITHM_ID",
    "KP1979SyntheticControlError",
    "MetamorphicResult",
    "SyntheticCaseResult",
    "SyntheticControlReport",
    "SyntheticFixture",
    "build_synthetic_fixture",
    "evaluate_synthetic_fixture",
    "run_synthetic_control",
    "synthetic_case_ids",
]
