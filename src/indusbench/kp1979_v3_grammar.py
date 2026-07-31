"""Page grammar and controller-side construction records for KP1979 C3.

The grammar is deliberately page-level: an eligible positive page contains a
single two-lane lattice. A complete rendered label is only a witness inside
that lattice, never sufficient evidence on its own. Negative records describe
synthetic structure and make no claim about real glyphs; they are authoritative
only inside the generator's suite-seed-bound top-level case validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Final

from .kp1979_v3_canvas import MonochromeCanvas
from .kp1979_v3_protocol import (
    RAW_P4_CONTRACT,
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_SCAN_BANDS,
    TRUE_REFERENCE_HALF_HEIGHT,
)
from .kp1979_v3_renderer_a import render_orthogonal_label
from .kp1979_v3_renderer_b import RENDERER_ID as BITMAP_RENDERER_ID
from .kp1979_v3_renderer_b import render_bitmap_label

ORTHOGONAL_RENDERER_ID: Final = "orthogonal_graph_v1"
RENDERER_IDS: Final = frozenset({ORTHOGONAL_RENDERER_ID, BITMAP_RENDERER_ID})

MINIMUM_PITCH: Final = 154
MAXIMUM_PITCH: Final = 176
MINIMUM_PHASE: Final = 604
PHASE_BOTTOM_ALLOWANCE: Final = 54
GENERATOR_MAXIMUM_JITTER: Final = 6
CHECKER_MAXIMUM_JITTER: Final = 8
MINIMUM_COMPLETE_WITNESSES_PER_LANE: Final = 20
MAXIMUM_TOTAL_WITNESSES: Final = 128
MINIMUM_GRID_SPAN_INTERSECTION: Final = 20
MAXIMUM_MISSING_RUN: Final = 2
MINIMUM_TIER_INK: Final = 32
LABEL_LAYER_WIDTH: Final = 260
LABEL_LAYER_HEIGHT: Final = 56
LABEL_LAYER_ROW_BYTES: Final = 33
LABEL_LAYER_BYTE_SIZE: Final = LABEL_LAYER_ROW_BYTES * LABEL_LAYER_HEIGHT
MAXIMUM_LAYER_BYTE_SIZE: Final = 200_000
MAXIMUM_PAGE_LAYERS: Final = 136


class KP1979V3GrammarError(ValueError):
    """Raised when a C3 grammar object or construction certificate is invalid."""


class InkLayerKind(StrEnum):
    """Closed provenance type for every declared synthetic ink layer."""

    COMPLETE_LABEL = "complete-label"
    INCOMPLETE_PRIMITIVE = "incomplete-primitive"
    DISTRACTOR = "distractor"


class NegativeFailure(StrEnum):
    """Closed generator-known reason a synthetic negative is outside the grammar."""

    INSUFFICIENT_LANES = "insufficient-lanes"
    NO_COMMON_LEGAL_LATTICE = "no-common-legal-lattice"
    NO_COMPLETE_WITNESS = "no-complete-witness"


NEGATIVE_FAILURE_BY_CASE_ID: Final = {
    "negative-blank": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-single-lane": NegativeFailure.INSUFFICIENT_LANES,
    "negative-cross-lane-pitch-conflict": NegativeFailure.NO_COMMON_LEGAL_LATTICE,
    "negative-periodic-single-tier": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-periodic-two-tier-paired-segments": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-periodic-paired-dashes": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-ruled-form": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-table-grid": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-repeated-boxes": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-decorative-border": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-repeated-stamp": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-dense-multicolumn": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-mixed-label-confound": NegativeFailure.NO_COMPLETE_WITNESS,
    "negative-staggered-single-tiers": NegativeFailure.NO_COMPLETE_WITNESS,
}
NEGATIVE_LAYER_COUNT_BY_CASE_ID: Final = {
    "negative-blank": 0,
    "negative-single-lane": 34,
    "negative-cross-lane-pitch-conflict": 65,
    "negative-periodic-single-tier": 2,
    "negative-periodic-two-tier-paired-segments": 2,
    "negative-periodic-paired-dashes": 2,
    "negative-ruled-form": 2,
    "negative-table-grid": 2,
    "negative-repeated-boxes": 2,
    "negative-decorative-border": 2,
    "negative-repeated-stamp": 2,
    "negative-dense-multicolumn": 2,
    "negative-mixed-label-confound": 68,
    "negative-staggered-single-tiers": 2,
}
_NEGATIVE_CROSS_LANE_GRID_INDICES: Final = (
    tuple(range(36)),
    tuple(range(29)),
)


@dataclass(frozen=True, slots=True)
class InkLayer:
    """One bounded packed one-bit layer positioned on the synthetic page."""

    layer_id: str
    kind: InkLayerKind
    x0: int
    y0: int
    width: int
    height: int
    packed: bytes
    packed_sha256: str
    ink_count: int


@dataclass(frozen=True, slots=True)
class RendererInvocation:
    """Exact inputs needed to independently rerender one complete witness."""

    renderer_id: str
    entropy: bytes
    lane_x0: int
    lane_x1: int
    stroke_width: int | None
    scale: int | None
    shear: int | None
    qualifier_variant: int
    damage_percent: int
    horizontal_alignment: str


@dataclass(frozen=True, slots=True)
class RendererReceipt:
    """Renderer receipt normalized to the 260-by-56 layer coordinates."""

    renderer_id: str
    ink_bbox: tuple[int, int, int, int]
    upper_ink_count: int
    lower_ink_count: int
    mutation_delta: int


@dataclass(frozen=True, slots=True)
class CompleteWitness:
    """One exact rerenderable complete two-tier label witness."""

    lane: int
    grid_index: int
    jitter: int
    anchor_y: int
    invocation: RendererInvocation
    receipt: RendererReceipt
    layer: InkLayer


@dataclass(frozen=True, slots=True)
class TruthSlot:
    """One exact half-open reference interval in a positive-page oracle."""

    lane: int
    grid_index: int
    anchor_y: int
    y0: int
    y1: int
    renderer_id: str
    layer_sha256: str


@dataclass(frozen=True, slots=True)
class PageLatticeCertificate:
    """Machine-checkable positive page-lattice certificate."""

    pitch: int
    phase: int
    witnesses: tuple[CompleteWitness, ...]
    truth_slots: tuple[TruthSlot, ...]
    layers: tuple[InkLayer, ...]


@dataclass(frozen=True, slots=True)
class NegativeCertificate:
    """Controller-side record, authoritative only in a seed-validated case."""

    case_id: str
    failure: NegativeFailure
    complete_witnesses: tuple[CompleteWitness, ...]
    layers: tuple[InkLayer, ...]


def _strict_int(name: str, value: object, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise KP1979V3GrammarError(f"{name} is outside its closed integer range")
    return value


def _require_digest(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise KP1979V3GrammarError(f"{name} is not a lowercase SHA-256")
    return value


def _packed_ink_count(packed: bytes, *, width: int, height: int) -> int:
    row_bytes = (width + 7) // 8
    if len(packed) != row_bytes * height:
        raise KP1979V3GrammarError("packed layer byte length is inconsistent")
    unused_bits = row_bytes * 8 - width
    if unused_bits:
        trailing_mask = (1 << unused_bits) - 1
        if any(packed[row * row_bytes + row_bytes - 1] & trailing_mask for row in range(height)):
            raise KP1979V3GrammarError("packed layer has non-zero trailing bits")
    return sum(byte.bit_count() for byte in packed)


def validate_ink_layer(layer: InkLayer) -> None:
    """Validate one canonical bounded layer independently of its scene."""

    if type(layer) is not InkLayer:
        raise KP1979V3GrammarError("ink layer must use the frozen type")
    if (
        type(layer.layer_id) is not str
        or not layer.layer_id
        or len(layer.layer_id) > 255
        or not layer.layer_id.isascii()
    ):
        raise KP1979V3GrammarError("layer identity must be non-empty ASCII")
    if type(layer.kind) is not InkLayerKind:
        raise KP1979V3GrammarError("layer kind must use the closed enum")
    x0 = _strict_int("layer x0", layer.x0, 0, SYNTHETIC_PAGE_WIDTH - 1)
    y0 = _strict_int("layer y0", layer.y0, 0, SYNTHETIC_PAGE_HEIGHT - 1)
    width = _strict_int("layer width", layer.width, 1, SYNTHETIC_PAGE_WIDTH)
    height = _strict_int("layer height", layer.height, 1, SYNTHETIC_PAGE_HEIGHT)
    if x0 + width > SYNTHETIC_PAGE_WIDTH or y0 + height > SYNTHETIC_PAGE_HEIGHT:
        raise KP1979V3GrammarError("ink layer exceeds the synthetic page")
    if type(layer.packed) is not bytes:
        raise KP1979V3GrammarError("packed layer must be exact bytes")
    if len(layer.packed) > MAXIMUM_LAYER_BYTE_SIZE:
        raise KP1979V3GrammarError("packed layer exceeds the fixed byte bound")
    digest = _require_digest("packed layer digest", layer.packed_sha256)
    if sha256(layer.packed).hexdigest() != digest:
        raise KP1979V3GrammarError("packed layer digest does not match its bytes")
    ink_count = _packed_ink_count(layer.packed, width=width, height=height)
    if type(layer.ink_count) is not int or layer.ink_count != ink_count:
        raise KP1979V3GrammarError("ink layer count does not match its packed bytes")
    if ink_count == 0:
        raise KP1979V3GrammarError("a declared construction layer must contain ink")


def _render_invocation(invocation: RendererInvocation) -> tuple[RendererReceipt, bytes]:
    if type(invocation) is not RendererInvocation:
        raise KP1979V3GrammarError("renderer invocation must use the frozen type")
    if invocation.renderer_id not in RENDERER_IDS:
        raise KP1979V3GrammarError("renderer identity is outside the frozen pair")
    if type(invocation.entropy) is not bytes or len(invocation.entropy) != 32:
        raise KP1979V3GrammarError("renderer entropy must be exactly 32 bytes")
    lane_x0 = _strict_int("relative lane x0", invocation.lane_x0, 0, LABEL_LAYER_WIDTH - 1)
    lane_x1 = _strict_int("relative lane x1", invocation.lane_x1, 1, LABEL_LAYER_WIDTH)
    if lane_x0 >= lane_x1:
        raise KP1979V3GrammarError("relative lane bounds are empty")
    if (
        type(invocation.qualifier_variant) is not int
        or not 0 <= invocation.qualifier_variant <= 3
        or type(invocation.damage_percent) is not int
        or not 0 <= invocation.damage_percent <= 12
        or type(invocation.horizontal_alignment) is not str
        or invocation.horizontal_alignment not in {"left", "center", "right"}
    ):
        raise KP1979V3GrammarError("renderer style is outside the frozen bounds")

    canvas = MonochromeCanvas(LABEL_LAYER_WIDTH, LABEL_LAYER_HEIGHT, max_mutations=16_384)
    if invocation.renderer_id == ORTHOGONAL_RENDERER_ID:
        if (
            type(invocation.stroke_width) is not int
            or not 1 <= invocation.stroke_width <= 4
            or invocation.scale is not None
            or invocation.shear is not None
        ):
            raise KP1979V3GrammarError("Renderer A invocation parameters are inconsistent")
        receipt = render_orthogonal_label(
            canvas,
            lane_bounds=(lane_x0, lane_x1),
            anchor_y=TRUE_REFERENCE_HALF_HEIGHT,
            entropy=invocation.entropy,
            stroke_width=invocation.stroke_width,
            qualifier_variant=invocation.qualifier_variant,
            damage_percent=invocation.damage_percent,
            horizontal_alignment=invocation.horizontal_alignment,
        )
    else:
        if (
            invocation.stroke_width is not None
            or type(invocation.scale) is not int
            or not 2 <= invocation.scale <= 3
            or type(invocation.shear) is not int
            or not -1 <= invocation.shear <= 1
        ):
            raise KP1979V3GrammarError("Renderer B invocation parameters are inconsistent")
        receipt = render_bitmap_label(
            canvas,
            lane_bounds=(lane_x0, lane_x1),
            anchor_y=TRUE_REFERENCE_HALF_HEIGHT,
            entropy=invocation.entropy,
            scale=invocation.scale,
            shear=invocation.shear,
            qualifier_variant=invocation.qualifier_variant,
            damage_percent=invocation.damage_percent,
            horizontal_alignment=invocation.horizontal_alignment,
        )
    normalized = RendererReceipt(
        renderer_id=receipt.renderer_id,
        ink_bbox=receipt.ink_bbox,
        upper_ink_count=receipt.upper_ink_count,
        lower_ink_count=receipt.lower_ink_count,
        mutation_delta=receipt.mutation_delta,
    )
    return normalized, canvas.packed_crop(0, 0, LABEL_LAYER_WIDTH, LABEL_LAYER_HEIGHT)


def validate_complete_witness(witness: CompleteWitness, *, maximum_jitter: int) -> None:
    """Rerender and validate one complete witness from its frozen invocation."""

    if type(witness) is not CompleteWitness:
        raise KP1979V3GrammarError("complete witness must use the frozen type")
    lane = _strict_int("witness lane", witness.lane, 0, 1)
    _strict_int("witness grid index", witness.grid_index, 0, 99)
    jitter = _strict_int("witness jitter", witness.jitter, -maximum_jitter, maximum_jitter)
    _strict_int("witness anchor", witness.anchor_y, 0, SYNTHETIC_PAGE_HEIGHT)
    if witness.jitter != jitter:
        raise KP1979V3GrammarError("witness jitter is not canonical")
    if type(witness.receipt) is not RendererReceipt:
        raise KP1979V3GrammarError("renderer receipt must use the frozen type")
    if witness.receipt.renderer_id != witness.invocation.renderer_id:
        raise KP1979V3GrammarError("renderer receipt identity differs from its invocation")
    if (
        type(witness.receipt.upper_ink_count) is not int
        or witness.receipt.upper_ink_count < MINIMUM_TIER_INK
        or type(witness.receipt.lower_ink_count) is not int
        or witness.receipt.lower_ink_count < MINIMUM_TIER_INK
        or type(witness.receipt.mutation_delta) is not int
        or witness.receipt.mutation_delta <= 0
    ):
        raise KP1979V3GrammarError("complete witness lacks the minimum two-tier ink")
    bbox = witness.receipt.ink_bbox
    if (
        type(bbox) is not tuple
        or len(bbox) != 4
        or any(type(value) is not int for value in bbox)
        or not 0 <= bbox[0] < bbox[2] <= LABEL_LAYER_WIDTH
        or not 0 <= bbox[1] < bbox[3] <= LABEL_LAYER_HEIGHT
        or not witness.invocation.lane_x0 <= bbox[0] < bbox[2] <= witness.invocation.lane_x1
    ):
        raise KP1979V3GrammarError("renderer receipt bounding box exceeds its support")

    validate_ink_layer(witness.layer)
    band = SYNTHETIC_SCAN_BANDS[lane]
    if (
        witness.layer.kind is not InkLayerKind.COMPLETE_LABEL
        or witness.layer.x0 != band[0]
        or witness.layer.y0 != witness.anchor_y - TRUE_REFERENCE_HALF_HEIGHT
        or witness.layer.width != LABEL_LAYER_WIDTH
        or witness.layer.height != LABEL_LAYER_HEIGHT
        or witness.layer.x0 + witness.layer.width != band[2]
        or witness.layer.y0 < band[1]
        or witness.layer.y0 + witness.layer.height > band[3]
    ):
        raise KP1979V3GrammarError("complete witness layer is outside its page scan band")

    rerendered_receipt, rerendered_packed = _render_invocation(witness.invocation)
    if rerendered_receipt != witness.receipt or rerendered_packed != witness.layer.packed:
        raise KP1979V3GrammarError("complete witness does not exactly rerender")
    if witness.layer.ink_count != (
        witness.receipt.upper_ink_count + witness.receipt.lower_ink_count
    ):
        raise KP1979V3GrammarError("receipt tier counts do not cover the exact layer ink")


def _maximum_missing_run(indices: tuple[int, ...]) -> int:
    index_set = set(indices)
    longest = 0
    current = 0
    for grid_index in range(min(indices), max(indices) + 1):
        if grid_index in index_set:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def _validate_positive_lane_grid_structure(
    witnesses: tuple[CompleteWitness, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not 2 * MINIMUM_COMPLETE_WITNESSES_PER_LANE <= len(witnesses) <= MAXIMUM_TOTAL_WITNESSES:
        raise KP1979V3GrammarError("page witness total is outside the grammar")
    lane_indices = (
        tuple(witness.grid_index for witness in witnesses if witness.lane == 0),
        tuple(witness.grid_index for witness in witnesses if witness.lane == 1),
    )
    spans: list[tuple[int, int]] = []
    for indices in lane_indices:
        if len(indices) < MINIMUM_COMPLETE_WITNESSES_PER_LANE:
            raise KP1979V3GrammarError("both lanes require at least twenty complete witnesses")
        span_length = max(indices) - min(indices) + 1
        missing = span_length - len(indices)
        if 5 * missing > span_length:
            raise KP1979V3GrammarError("a lane exceeds the one-in-five missing-slot bound")
        if _maximum_missing_run(indices) > MAXIMUM_MISSING_RUN:
            raise KP1979V3GrammarError("a lane exceeds the two-slot missing-run bound")
        spans.append((min(indices), max(indices)))
    intersection = min(spans[0][1], spans[1][1]) - max(spans[0][0], spans[1][0]) + 1
    if intersection < MINIMUM_GRID_SPAN_INTERSECTION:
        raise KP1979V3GrammarError("the two lane grid spans intersect in fewer than twenty slots")
    return lane_indices


def validate_page_lattice(
    certificate: PageLatticeCertificate,
    *,
    maximum_jitter: int = CHECKER_MAXIMUM_JITTER,
) -> None:
    """Validate the complete page-level two-lane grammar certificate."""

    if type(certificate) is not PageLatticeCertificate:
        raise KP1979V3GrammarError("page lattice must use the frozen certificate type")
    pitch = _strict_int("pitch", certificate.pitch, MINIMUM_PITCH, MAXIMUM_PITCH)
    if maximum_jitter not in {GENERATOR_MAXIMUM_JITTER, CHECKER_MAXIMUM_JITTER}:
        raise KP1979V3GrammarError("jitter checker bound is outside the frozen choices")
    if type(certificate.witnesses) is not tuple or type(certificate.truth_slots) is not tuple:
        raise KP1979V3GrammarError("witnesses and truth slots must be exact tuples")
    if (
        not 2 * MINIMUM_COMPLETE_WITNESSES_PER_LANE
        <= len(certificate.witnesses)
        <= MAXIMUM_TOTAL_WITNESSES
    ):
        raise KP1979V3GrammarError("page witness total is outside the grammar")
    if len(certificate.truth_slots) != len(certificate.witnesses):
        raise KP1979V3GrammarError("truth-slot and complete-witness counts differ")

    keys = tuple((witness.lane, witness.grid_index) for witness in certificate.witnesses)
    if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
        raise KP1979V3GrammarError("complete witnesses are duplicated or not canonically ordered")
    maximum_grid_index = max(witness.grid_index for witness in certificate.witnesses)
    maximum_phase = SYNTHETIC_SCAN_BANDS[0][3] - PHASE_BOTTOM_ALLOWANCE - maximum_grid_index * pitch
    phase = _strict_int("phase", certificate.phase, MINIMUM_PHASE, maximum_phase)

    expected_truth: list[TruthSlot] = []
    for witness in certificate.witnesses:
        validate_complete_witness(witness, maximum_jitter=maximum_jitter)
        if witness.anchor_y != phase + witness.grid_index * pitch + witness.jitter:
            raise KP1979V3GrammarError("witness anchor differs from phase + grid*pitch + jitter")
        expected_truth.append(
            TruthSlot(
                lane=witness.lane,
                grid_index=witness.grid_index,
                anchor_y=witness.anchor_y,
                y0=witness.anchor_y - TRUE_REFERENCE_HALF_HEIGHT,
                y1=witness.anchor_y + TRUE_REFERENCE_HALF_HEIGHT,
                renderer_id=witness.invocation.renderer_id,
                layer_sha256=witness.layer.packed_sha256,
            )
        )
    if certificate.truth_slots != tuple(expected_truth):
        raise KP1979V3GrammarError("truth slots are not the exact witness references")
    _validate_positive_lane_grid_structure(certificate.witnesses)

    if type(certificate.layers) is not tuple:
        raise KP1979V3GrammarError("page layers must be an exact tuple")
    if not len(certificate.witnesses) <= len(certificate.layers) <= MAXIMUM_PAGE_LAYERS:
        raise KP1979V3GrammarError("positive page layer inventory is outside the fixed bound")
    for layer in certificate.layers:
        validate_ink_layer(layer)
    complete_layers = tuple(
        layer for layer in certificate.layers if layer.kind is InkLayerKind.COMPLETE_LABEL
    )
    if complete_layers != tuple(witness.layer for witness in certificate.witnesses):
        raise KP1979V3GrammarError("complete witness layers do not exactly cover page label layers")
    if any(
        layer.kind is not InkLayerKind.DISTRACTOR
        for layer in certificate.layers
        if layer.kind is not InkLayerKind.COMPLETE_LABEL
    ):
        raise KP1979V3GrammarError("positive pages permit only complete labels and distractors")
    layer_ids = tuple(layer.layer_id for layer in certificate.layers)
    if len(layer_ids) != len(set(layer_ids)):
        raise KP1979V3GrammarError("page layer identities must be unique")


def _layer_into_payload(payload: bytearray, layer: InkLayer) -> None:
    layer_row_bytes = (layer.width + 7) // 8
    for relative_y in range(layer.height):
        for relative_x in range(layer.width):
            source = layer.packed[relative_y * layer_row_bytes + relative_x // 8]
            if source & (0x80 >> (relative_x % 8)):
                x = layer.x0 + relative_x
                y = layer.y0 + relative_y
                payload[y * RAW_P4_CONTRACT.row_bytes + x // 8] |= 0x80 >> (x % 8)


def compose_pbm(layers: tuple[InkLayer, ...]) -> bytes:
    """Compose the canonical raw-P4 page from the complete declared layer set."""

    if type(layers) is not tuple:
        raise KP1979V3GrammarError("page layers must be an exact tuple")
    if len(layers) > MAXIMUM_PAGE_LAYERS:
        raise KP1979V3GrammarError("page layer inventory exceeds the fixed bound")
    payload = bytearray(RAW_P4_CONTRACT.payload_byte_size)
    identities: set[str] = set()
    for layer in layers:
        validate_ink_layer(layer)
        if layer.layer_id in identities:
            raise KP1979V3GrammarError("page layer identities must be unique")
        identities.add(layer.layer_id)
        _layer_into_payload(payload, layer)
    return RAW_P4_CONTRACT.header + bytes(payload)


def validate_page_composition(pbm: bytes, layers: tuple[InkLayer, ...]) -> None:
    """Reject any page byte not accounted for by the declared construction layers."""

    if type(pbm) is not bytes or len(pbm) != RAW_P4_CONTRACT.pbm_byte_size:
        raise KP1979V3GrammarError("page PBM has the wrong exact byte size")
    if pbm != compose_pbm(layers):
        raise KP1979V3GrammarError("page contains missing or unaccounted synthetic ink")


def _possible_legal_pitches(witnesses: tuple[CompleteWitness, ...]) -> frozenset[int]:
    maximum_grid_index = max(witness.grid_index for witness in witnesses)
    possible: set[int] = set()
    for pitch in range(MINIMUM_PITCH, MAXIMUM_PITCH + 1):
        phase_lower = MINIMUM_PHASE
        phase_upper = (
            SYNTHETIC_SCAN_BANDS[0][3] - PHASE_BOTTOM_ALLOWANCE - maximum_grid_index * pitch
        )
        for witness in witnesses:
            implied_phase = witness.anchor_y - witness.grid_index * pitch
            phase_lower = max(phase_lower, implied_phase - CHECKER_MAXIMUM_JITTER)
            phase_upper = min(phase_upper, implied_phase + CHECKER_MAXIMUM_JITTER)
            if phase_lower > phase_upper:
                break
        if phase_lower <= phase_upper:
            possible.add(pitch)
    return frozenset(possible)


def _validate_negative_certificate_structure(certificate: NegativeCertificate) -> None:
    """Validate structure only, without proving canonical source generation.

    Authoritative negative acceptance belongs to the suite-seed-bound
    ``validate_generated_case`` boundary in the generator module.
    """

    if type(certificate) is not NegativeCertificate:
        raise KP1979V3GrammarError("negative certificate must use the frozen type")
    expected = NEGATIVE_FAILURE_BY_CASE_ID.get(certificate.case_id)
    if expected is None or type(certificate.failure) is not NegativeFailure:
        raise KP1979V3GrammarError("negative certificate identity is outside the roster")
    if certificate.failure is not expected:
        raise KP1979V3GrammarError("negative failure differs from the fixed recipe")
    if type(certificate.complete_witnesses) is not tuple or type(certificate.layers) is not tuple:
        raise KP1979V3GrammarError("negative witnesses and layers must be exact tuples")
    if len(certificate.layers) != NEGATIVE_LAYER_COUNT_BY_CASE_ID[certificate.case_id]:
        raise KP1979V3GrammarError("negative layer inventory differs from the fixed recipe")
    keys = tuple((witness.lane, witness.grid_index) for witness in certificate.complete_witnesses)
    if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
        raise KP1979V3GrammarError("negative complete witnesses are not canonical")
    for witness in certificate.complete_witnesses:
        validate_complete_witness(witness, maximum_jitter=GENERATOR_MAXIMUM_JITTER)
    for layer in certificate.layers:
        validate_ink_layer(layer)
    layer_ids = tuple(layer.layer_id for layer in certificate.layers)
    if len(layer_ids) != len(set(layer_ids)):
        raise KP1979V3GrammarError("negative layer identities must be unique")
    complete_layers = tuple(
        layer for layer in certificate.layers if layer.kind is InkLayerKind.COMPLETE_LABEL
    )
    if complete_layers != tuple(witness.layer for witness in certificate.complete_witnesses):
        raise KP1979V3GrammarError("negative complete layers differ from their witnesses")

    lane_counts = tuple(
        sum(witness.lane == lane for witness in certificate.complete_witnesses) for lane in (0, 1)
    )
    if certificate.failure is NegativeFailure.INSUFFICIENT_LANES:
        if sorted(lane_counts) != [0, max(lane_counts)] or max(lane_counts) < 20:
            raise KP1979V3GrammarError("single-lane certificate does not prove insufficient lanes")
    elif certificate.failure is NegativeFailure.NO_COMMON_LEGAL_LATTICE:
        lane_indices = _validate_positive_lane_grid_structure(certificate.complete_witnesses)
        if _possible_legal_pitches(certificate.complete_witnesses):
            raise KP1979V3GrammarError("pitch-conflict certificate admits a common legal pitch")
        if lane_indices != _NEGATIVE_CROSS_LANE_GRID_INDICES:
            raise KP1979V3GrammarError(
                "pitch-conflict grid inventory differs from the fixed recipe"
            )
    elif certificate.failure is NegativeFailure.NO_COMPLETE_WITNESS:
        if certificate.complete_witnesses or complete_layers:
            raise KP1979V3GrammarError("no-complete-witness certificate contains a complete label")
        if certificate.case_id != "negative-blank" and not certificate.layers:
            raise KP1979V3GrammarError("nonblank primitive recipe contains no construction layer")
    else:
        raise KP1979V3GrammarError("negative failure is outside the closed vocabulary")


__all__ = [
    "BITMAP_RENDERER_ID",
    "CHECKER_MAXIMUM_JITTER",
    "GENERATOR_MAXIMUM_JITTER",
    "LABEL_LAYER_BYTE_SIZE",
    "LABEL_LAYER_HEIGHT",
    "LABEL_LAYER_WIDTH",
    "MAXIMUM_LAYER_BYTE_SIZE",
    "MAXIMUM_PAGE_LAYERS",
    "MAXIMUM_PITCH",
    "MINIMUM_PHASE",
    "MINIMUM_PITCH",
    "NEGATIVE_FAILURE_BY_CASE_ID",
    "NEGATIVE_LAYER_COUNT_BY_CASE_ID",
    "ORTHOGONAL_RENDERER_ID",
    "CompleteWitness",
    "InkLayer",
    "InkLayerKind",
    "KP1979V3GrammarError",
    "NegativeCertificate",
    "NegativeFailure",
    "PageLatticeCertificate",
    "RendererInvocation",
    "RendererReceipt",
    "TruthSlot",
    "compose_pbm",
    "validate_complete_witness",
    "validate_ink_layer",
    "validate_page_composition",
    "validate_page_lattice",
]
