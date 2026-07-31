"""Deterministic fixture generator for the KP1979 C3 control.

Each five-key worker request is answer-free. Generated cases, relation oracles,
and schedule metadata are controller-private: they must not be published or
persisted before execution and must never cross the worker boundary. The
generator retains no suite-sized raster collection and performs no I/O.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Final, Literal

from .kp1979_v3_canvas import MonochromeCanvas
from .kp1979_v3_grammar import (
    BITMAP_RENDERER_ID,
    GENERATOR_MAXIMUM_JITTER,
    LABEL_LAYER_HEIGHT,
    LABEL_LAYER_WIDTH,
    MINIMUM_PHASE,
    NEGATIVE_FAILURE_BY_CASE_ID,
    ORTHOGONAL_RENDERER_ID,
    CompleteWitness,
    InkLayer,
    InkLayerKind,
    KP1979V3GrammarError,
    NegativeCertificate,
    PageLatticeCertificate,
    RendererInvocation,
    RendererReceipt,
    TruthSlot,
    _validate_negative_certificate_structure,
    compose_pbm,
    validate_page_composition,
    validate_page_lattice,
)
from .kp1979_v3_prf import DeterministicStream, derive_subseed
from .kp1979_v3_protocol import (
    CASE_ROSTER,
    METAMORPHIC_RELATIONS,
    RAW_P4_CONTRACT,
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_SCAN_BANDS,
    TOTAL_WORKER_INVOCATIONS,
    TRUE_REFERENCE_HALF_HEIGHT,
    CaseCategory,
    InputErrorCode,
    MetamorphicKind,
)
from .kp1979_v3_renderer_a import render_orthogonal_label
from .kp1979_v3_renderer_b import render_bitmap_label
from .kp1979_v3_wire import (
    KP1979V3WireError,
    KP1979V3WorkerInputError,
    decode_worker_request,
    decode_worker_request_envelope,
    encode_worker_request,
)

GENERATOR_ID: Final = "c3-generator-v1"
SUITE_DOMAIN_LABEL: Final = "c3-generator-v1/suite"
LAYOUT_LABEL: Final = "layout"
JITTER_LABEL: Final = "jitter"
STYLE_LABEL: Final = "style"
DISTRACTOR_LABEL: Final = "distractor"
GAP_LABEL: Final = "gap"
ENDPOINT_NAMES: Final = ("a", "b")
ALIGNMENTS: Final = ("left", "center", "right")
_CASE_GENERATION_COMMITMENT_DOMAIN: Final = b"KP1979-V3-CASE-GENERATION-COMMITMENT-V1\x00"
_RELATION_GENERATION_COMMITMENT_DOMAIN: Final = b"KP1979-V3-RELATION-GENERATION-COMMITMENT-V1\x00"

_LaneIndices = tuple[tuple[int, ...], tuple[int, ...]]
_RendererMode = Literal["a", "b", "mixed"]


class KP1979V3GeneratorError(ValueError):
    """Raised when deterministic fixture generation violates the closed plan."""


@dataclass(frozen=True, slots=True, repr=False)
class GeneratedCase:
    """One protocol case with exact request bytes and private generator oracle."""

    ordinal: int
    case_id: str
    category: CaseCategory
    generation_commitment: bytes
    request_bytes: bytes
    request_sha256: str
    pbm_sha256: str
    positive: PageLatticeCertificate | None
    negative: NegativeCertificate | None
    expected_error_code: InputErrorCode | None


@dataclass(frozen=True, slots=True, repr=False)
class GeneratedEndpoint:
    """One positive metamorphic endpoint."""

    endpoint: str
    request_bytes: bytes
    request_sha256: str
    pbm_sha256: str
    positive: PageLatticeCertificate


@dataclass(frozen=True, slots=True, repr=False)
class GeneratedRelation:
    """One fixed two-endpoint metamorphic scene and its exact relation oracle."""

    ordinal: int
    relation_id: str
    kind: MetamorphicKind
    generation_commitment: bytes
    endpoints: tuple[GeneratedEndpoint, GeneratedEndpoint]
    omitted_layer: InkLayer | None


@dataclass(frozen=True, slots=True, repr=False)
class _ScheduledInvocation:
    """Controller-private metadata for one worker invocation."""

    invocation_index: int
    source_kind: str
    source_ordinal: int
    source_id: str
    endpoint: str | None
    category: CaseCategory
    expected_error_code: InputErrorCode | None
    request_bytes: bytes
    request_sha256: str
    pbm_sha256: str


def _require_seed(seed: bytes) -> bytes:
    if type(seed) is not bytes or len(seed) != 32:
        raise KP1979V3GeneratorError("generator seed must be exactly 32 bytes")
    return seed


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _generation_commitment(domain: bytes, item_seed: bytes) -> bytes:
    if (
        domain
        not in {
            _CASE_GENERATION_COMMITMENT_DOMAIN,
            _RELATION_GENERATION_COMMITMENT_DOMAIN,
        }
        or type(item_seed) is not bytes
        or len(item_seed) != 32
    ):
        raise KP1979V3GeneratorError("generation commitment input is invalid")
    return sha256(domain + item_seed).digest()


def _suite_seed(seed: bytes) -> bytes:
    return derive_subseed(_require_seed(seed), SUITE_DOMAIN_LABEL)


def _case_seed(seed: bytes, ordinal: int, case_id: str) -> bytes:
    return derive_subseed(_suite_seed(seed), f"case/{ordinal:02d}/{case_id}")


def _relation_seed(seed: bytes, ordinal: int, relation_id: str) -> bytes:
    return derive_subseed(_suite_seed(seed), f"relation/{ordinal:02d}/{relation_id}")


def _stream(seed: bytes, label: str) -> DeterministicStream:
    return DeterministicStream(seed, label)


def _renderer_for(mode: _RendererMode, lane: int, grid_index: int) -> str:
    if mode == "a":
        return ORTHOGONAL_RENDERER_ID
    if mode == "b":
        return BITMAP_RENDERER_ID
    return ORTHOGONAL_RENDERER_ID if (lane + grid_index) % 2 == 0 else BITMAP_RENDERER_ID


def _ink_count(packed: bytes) -> int:
    return sum(byte.bit_count() for byte in packed)


def _make_layer(
    *,
    layer_id: str,
    kind: InkLayerKind,
    x0: int,
    y0: int,
    width: int,
    height: int,
    packed: bytes,
) -> InkLayer:
    return InkLayer(
        layer_id=layer_id,
        kind=kind,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        packed=packed,
        packed_sha256=sha256(packed).hexdigest(),
        ink_count=_ink_count(packed),
    )


def _renderer_invocation(
    *,
    item_seed: bytes,
    seed_lane: int,
    grid_index: int,
    renderer_id: str,
    mode: str,
    lane_x0: int,
    lane_x1: int,
    stroke_override: int | None,
) -> RendererInvocation:
    entropy = derive_subseed(
        item_seed,
        f"slot/{seed_lane}/{grid_index:02d}/{renderer_id}",
    )
    style = _stream(item_seed, f"{STYLE_LABEL}/{seed_lane}/{grid_index:02d}")
    qualifier = style.randbelow(4)
    alignment = ALIGNMENTS[style.randbelow(len(ALIGNMENTS))]
    damage = 0
    if mode == "damage":
        damage = 8 + style.randbelow(5)
    if mode == "stroke":
        qualifier = grid_index % 4
        alignment = ALIGNMENTS[grid_index % len(ALIGNMENTS)]

    if renderer_id == ORTHOGONAL_RENDERER_ID:
        stroke_width = stroke_override
        if stroke_width is None:
            stroke_width = 1 + style.randbelow(4) if mode == "stroke" else 2
        return RendererInvocation(
            renderer_id=renderer_id,
            entropy=entropy,
            lane_x0=lane_x0,
            lane_x1=lane_x1,
            stroke_width=stroke_width,
            scale=None,
            shear=None,
            qualifier_variant=qualifier,
            damage_percent=damage,
            horizontal_alignment=alignment,
        )
    return RendererInvocation(
        renderer_id=renderer_id,
        entropy=entropy,
        lane_x0=lane_x0,
        lane_x1=lane_x1,
        stroke_width=None,
        scale=2 + style.randbelow(2),
        shear=style.randint(-1, 1),
        qualifier_variant=qualifier,
        damage_percent=damage,
        horizontal_alignment=alignment,
    )


def _render_witness(
    *,
    item_seed: bytes,
    scene_id: str,
    output_lane: int,
    seed_lane: int,
    grid_index: int,
    jitter: int,
    anchor_y: int,
    renderer_id: str,
    mode: str,
    lane_x0: int = 0,
    lane_x1: int = LABEL_LAYER_WIDTH,
    stroke_override: int | None = None,
) -> CompleteWitness:
    invocation = _renderer_invocation(
        item_seed=item_seed,
        seed_lane=seed_lane,
        grid_index=grid_index,
        renderer_id=renderer_id,
        mode=mode,
        lane_x0=lane_x0,
        lane_x1=lane_x1,
        stroke_override=stroke_override,
    )
    canvas = MonochromeCanvas(LABEL_LAYER_WIDTH, LABEL_LAYER_HEIGHT, max_mutations=16_384)
    if renderer_id == ORTHOGONAL_RENDERER_ID:
        assert invocation.stroke_width is not None
        raw_receipt = render_orthogonal_label(
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
        assert invocation.scale is not None and invocation.shear is not None
        raw_receipt = render_bitmap_label(
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
    receipt = RendererReceipt(
        renderer_id=raw_receipt.renderer_id,
        ink_bbox=raw_receipt.ink_bbox,
        upper_ink_count=raw_receipt.upper_ink_count,
        lower_ink_count=raw_receipt.lower_ink_count,
        mutation_delta=raw_receipt.mutation_delta,
    )
    packed = canvas.packed_crop(0, 0, LABEL_LAYER_WIDTH, LABEL_LAYER_HEIGHT)
    layer = _make_layer(
        layer_id=f"{scene_id}/slot/{output_lane}/{grid_index:02d}",
        kind=InkLayerKind.COMPLETE_LABEL,
        x0=SYNTHETIC_SCAN_BANDS[output_lane][0],
        y0=anchor_y - TRUE_REFERENCE_HALF_HEIGHT,
        width=LABEL_LAYER_WIDTH,
        height=LABEL_LAYER_HEIGHT,
        packed=packed,
    )
    return CompleteWitness(
        lane=output_lane,
        grid_index=grid_index,
        jitter=jitter,
        anchor_y=anchor_y,
        invocation=invocation,
        receipt=receipt,
        layer=layer,
    )


def _truth_slots(witnesses: tuple[CompleteWitness, ...]) -> tuple[TruthSlot, ...]:
    return tuple(
        TruthSlot(
            lane=witness.lane,
            grid_index=witness.grid_index,
            anchor_y=witness.anchor_y,
            y0=witness.anchor_y - TRUE_REFERENCE_HALF_HEIGHT,
            y1=witness.anchor_y + TRUE_REFERENCE_HALF_HEIGHT,
            renderer_id=witness.invocation.renderer_id,
            layer_sha256=witness.layer.packed_sha256,
        )
        for witness in witnesses
    )


def _phase(
    item_seed: bytes,
    *,
    pitch: int,
    maximum_grid_index: int,
    bottom_delta: int = 0,
) -> int:
    maximum = SYNTHETIC_SCAN_BANDS[0][3] - 54 - maximum_grid_index * pitch - bottom_delta
    if maximum < MINIMUM_PHASE:
        raise KP1979V3GeneratorError("scene has no legal phase interval")
    return _stream(item_seed, LAYOUT_LABEL).randint(MINIMUM_PHASE, maximum)


def _jitter(item_seed: bytes, lane: int, grid_index: int, enabled: bool) -> int:
    if not enabled:
        return 0
    return _stream(item_seed, f"{JITTER_LABEL}/{lane}/{grid_index:02d}").randint(
        -GENERATOR_MAXIMUM_JITTER,
        GENERATOR_MAXIMUM_JITTER,
    )


def _build_scene(
    *,
    item_seed: bytes,
    scene_id: str,
    pitch: int,
    phase: int,
    lane_indices: _LaneIndices,
    renderer_mode: _RendererMode,
    style_mode: str,
    jitter_enabled: bool,
    vertical_delta: int = 0,
    horizontal_delta: int = 0,
    horizontal_width: int = LABEL_LAYER_WIDTH,
    source_lane_for_output: tuple[int, int] = (0, 1),
    omitted: tuple[int, int] | None = None,
    stroke_override: int | None = None,
) -> PageLatticeCertificate:
    witnesses: list[CompleteWitness] = []
    for output_lane in (0, 1):
        seed_lane = source_lane_for_output[output_lane]
        for grid_index in lane_indices[seed_lane]:
            if omitted == (seed_lane, grid_index):
                continue
            jitter = _jitter(item_seed, seed_lane, grid_index, jitter_enabled)
            anchor_y = phase + grid_index * pitch + jitter + vertical_delta
            renderer_id = _renderer_for(renderer_mode, seed_lane, grid_index)
            witnesses.append(
                _render_witness(
                    item_seed=item_seed,
                    scene_id=scene_id,
                    output_lane=output_lane,
                    seed_lane=seed_lane,
                    grid_index=grid_index,
                    jitter=jitter,
                    anchor_y=anchor_y,
                    renderer_id=renderer_id,
                    mode=style_mode,
                    lane_x0=horizontal_delta,
                    lane_x1=horizontal_delta + horizontal_width,
                    stroke_override=stroke_override,
                )
            )
    ordered = tuple(sorted(witnesses, key=lambda witness: (witness.lane, witness.grid_index)))
    certificate = PageLatticeCertificate(
        pitch=pitch,
        phase=phase + vertical_delta,
        witnesses=ordered,
        truth_slots=_truth_slots(ordered),
        layers=tuple(witness.layer for witness in ordered),
    )
    return certificate


def _canvas_layer(
    *,
    layer_id: str,
    kind: InkLayerKind,
    lane: int,
    draw: str,
    seed: bytes,
) -> InkLayer:
    band = SYNTHETIC_SCAN_BANDS[lane]
    height = band[3] - band[1]
    canvas = MonochromeCanvas(LABEL_LAYER_WIDTH, height, max_mutations=20_000)
    stream = _stream(seed, f"{DISTRACTOR_LABEL}/{lane}/{draw}")

    if draw == "single-tier":
        for anchor in range(100, height - 50, 166):
            x0 = 12 + stream.randbelow(36)
            canvas.fill_ink_rect(x0, anchor - 22, x0 + 56, anchor - 17)
            canvas.fill_ink_rect(x0 + 72, anchor - 22, x0 + 116, anchor - 17)
    elif draw == "long-bars":
        for anchor in range(100, height - 50, 166):
            canvas.fill_ink_rect(22, anchor - 20, 222, anchor - 15)
            canvas.fill_ink_rect(38, anchor + 12, 238, anchor + 17)
    elif draw == "dashes":
        for anchor in range(100, height - 50, 166):
            for offset in (12, 54, 96, 138, 180):
                canvas.fill_ink_rect(offset, anchor - 18, offset + 16, anchor - 14)
                canvas.fill_ink_rect(offset + 8, anchor + 12, offset + 24, anchor + 16)
    elif draw == "ruled":
        for y in range(54, height - 20, 154):
            canvas.fill_ink_rect(4, y, 256, y + 3)
    elif draw == "table":
        for x in (8, 58, 108, 158, 208, 256):
            canvas.fill_ink_rect(max(0, x - 2), 12, min(260, x + 1), height - 12)
        for y in range(12, height - 12, 132):
            canvas.fill_ink_rect(4, y, 256, y + 3)
    elif draw == "boxes":
        for anchor in range(60, height - 60, 150):
            canvas.fill_ink_rect(34, anchor - 24, 226, anchor - 20)
            canvas.fill_ink_rect(34, anchor + 20, 226, anchor + 24)
            canvas.fill_ink_rect(34, anchor - 24, 38, anchor + 24)
            canvas.fill_ink_rect(222, anchor - 24, 226, anchor + 24)
    elif draw == "border":
        canvas.fill_ink_rect(5, 5, 9, height - 5)
        canvas.fill_ink_rect(251, 5, 255, height - 5)
        canvas.fill_ink_rect(5, 5, 255, 9)
        canvas.fill_ink_rect(5, height - 9, 255, height - 5)
        for y in range(40, height - 40, 93):
            canvas.fill_ink_rect(9, y, 27, y + 3)
            canvas.fill_ink_rect(233, y, 251, y + 3)
    elif draw == "stamp":
        for anchor in range(70, height - 70, 170):
            canvas.fill_ink_rect(88, anchor - 24, 172, anchor - 20)
            canvas.fill_ink_rect(88, anchor + 20, 172, anchor + 24)
            canvas.fill_ink_rect(88, anchor - 24, 92, anchor + 24)
            canvas.fill_ink_rect(168, anchor - 24, 172, anchor + 24)
            canvas.fill_ink_rect(126, anchor - 13, 134, anchor + 13)
    elif draw == "dense":
        for x in range(8, 256, 24):
            canvas.fill_ink_rect(x, 8, x + 3, height - 8)
        for y in range(20, height - 20, 38):
            canvas.fill_ink_rect(4, y, 256, y + 2)
    elif draw == "staggered":
        offset = 0 if lane == 0 else 77
        for index, anchor in enumerate(range(90 + offset, height - 50, 158)):
            if index % 2:
                canvas.fill_ink_rect(34, anchor + 6, 212, anchor + 13)
            else:
                canvas.fill_ink_rect(48, anchor - 22, 226, anchor - 15)
    else:
        raise KP1979V3GeneratorError("primitive recipe is outside the closed roster")
    packed = canvas.packed_crop(0, 0, LABEL_LAYER_WIDTH, height)
    return _make_layer(
        layer_id=layer_id,
        kind=kind,
        x0=band[0],
        y0=band[1],
        width=LABEL_LAYER_WIDTH,
        height=height,
        packed=packed,
    )


def _partial_renderer_layers(item_seed: bytes, case_id: str) -> tuple[InkLayer, ...]:
    layers: list[InkLayer] = []
    for lane in (0, 1):
        band = SYNTHETIC_SCAN_BANDS[lane]
        for grid_index in range(34):
            renderer_id = ORTHOGONAL_RENDERER_ID if grid_index % 2 == 0 else BITMAP_RENDERER_ID
            invocation = _renderer_invocation(
                item_seed=item_seed,
                seed_lane=lane,
                grid_index=grid_index,
                renderer_id=renderer_id,
                mode="clean",
                lane_x0=0,
                lane_x1=LABEL_LAYER_WIDTH,
                stroke_override=None,
            )
            canvas = MonochromeCanvas(
                LABEL_LAYER_WIDTH,
                LABEL_LAYER_HEIGHT,
                max_mutations=16_384,
            )
            if renderer_id == ORTHOGONAL_RENDERER_ID:
                assert invocation.stroke_width is not None
                render_orthogonal_label(
                    canvas,
                    lane_bounds=(0, LABEL_LAYER_WIDTH),
                    anchor_y=TRUE_REFERENCE_HALF_HEIGHT,
                    entropy=invocation.entropy,
                    stroke_width=invocation.stroke_width,
                    qualifier_variant=invocation.qualifier_variant,
                    damage_percent=0,
                    horizontal_alignment=invocation.horizontal_alignment,
                )
            else:
                assert invocation.scale is not None and invocation.shear is not None
                render_bitmap_label(
                    canvas,
                    lane_bounds=(0, LABEL_LAYER_WIDTH),
                    anchor_y=TRUE_REFERENCE_HALF_HEIGHT,
                    entropy=invocation.entropy,
                    scale=invocation.scale,
                    shear=invocation.shear,
                    qualifier_variant=invocation.qualifier_variant,
                    damage_percent=0,
                    horizontal_alignment=invocation.horizontal_alignment,
                )
            if grid_index % 2 == 0:
                canvas.clear_rect(0, TRUE_REFERENCE_HALF_HEIGHT, LABEL_LAYER_WIDTH, 56)
            else:
                canvas.clear_rect(0, 0, LABEL_LAYER_WIDTH, TRUE_REFERENCE_HALF_HEIGHT)
            packed = canvas.packed_crop(0, 0, LABEL_LAYER_WIDTH, LABEL_LAYER_HEIGHT)
            anchor_y = 650 + grid_index * 166
            layers.append(
                _make_layer(
                    layer_id=f"{case_id}/partial/{lane}/{grid_index:02d}",
                    kind=InkLayerKind.INCOMPLETE_PRIMITIVE,
                    x0=band[0],
                    y0=anchor_y - TRUE_REFERENCE_HALF_HEIGHT,
                    width=LABEL_LAYER_WIDTH,
                    height=LABEL_LAYER_HEIGHT,
                    packed=packed,
                )
            )
    return tuple(layers)


def _small_distractor_layers(
    item_seed: bytes,
    scene_id: str,
    certificate: PageLatticeCertificate,
) -> tuple[InkLayer, ...]:
    layers: list[InkLayer] = []
    for lane in (0, 1):
        lane_slots = [slot for slot in certificate.truth_slots if slot.lane == lane]
        for number, slot in enumerate(lane_slots[:4]):
            stream = _stream(item_seed, f"{DISTRACTOR_LABEL}/{lane}/{number:02d}")
            width = 10 + stream.randbelow(10)
            height = 3 + stream.randbelow(4)
            canvas = MonochromeCanvas(width, height, max_mutations=4)
            canvas.fill_ink_rect(0, 0, width, height)
            y0 = slot.y1 + 22
            band = SYNTHETIC_SCAN_BANDS[lane]
            x0 = band[0] + 12 + stream.randbelow(LABEL_LAYER_WIDTH - width - 24)
            packed = canvas.packed_crop(0, 0, width, height)
            layers.append(
                _make_layer(
                    layer_id=f"{scene_id}/distractor/{lane}/{number:02d}",
                    kind=InkLayerKind.DISTRACTOR,
                    x0=x0,
                    y0=y0,
                    width=width,
                    height=height,
                    packed=packed,
                )
            )
    return tuple(layers)


def _positive_recipe(case_id: str) -> tuple[int, _LaneIndices, _RendererMode, str, bool]:
    recipes: dict[str, tuple[int, _LaneIndices, _RendererMode, str, bool]] = {
        "positive-renderer-a-clean": (
            166,
            (tuple(range(34)), tuple(range(34))),
            "a",
            "clean",
            False,
        ),
        "positive-renderer-b-clean": (
            166,
            (tuple(range(34)), tuple(range(34))),
            "b",
            "clean",
            False,
        ),
        "positive-renderer-a-pitch-158": (
            158,
            (tuple(range(36)), tuple(range(36))),
            "a",
            "clean",
            False,
        ),
        "positive-renderer-b-pitch-172": (
            172,
            (tuple(range(33)), tuple(range(33))),
            "b",
            "clean",
            False,
        ),
        "positive-mixed-asymmetric": (
            164,
            (tuple(range(35)), tuple(range(3, 32))),
            "mixed",
            "clean",
            True,
        ),
        "positive-gaps-jitter": (
            160,
            (
                tuple(index for index in range(36) if index not in {6, 14, 27}),
                tuple(index for index in range(36) if index not in {4, 18, 30}),
            ),
            "mixed",
            "clean",
            True,
        ),
        "positive-double-gaps": (
            162,
            (
                tuple(index for index in range(36) if index not in {9, 10, 25, 26}),
                tuple(index for index in range(36) if index not in {7, 8, 20, 21}),
            ),
            "mixed",
            "clean",
            True,
        ),
        "positive-unequal-partial-lanes": (
            166,
            (tuple(range(36)), tuple(range(8, 30))),
            "mixed",
            "clean",
            True,
        ),
        "positive-bounded-damage": (
            168,
            (tuple(range(34)), tuple(range(34))),
            "mixed",
            "damage",
            True,
        ),
        "positive-stroke-qualifier": (
            166,
            (tuple(range(34)), tuple(range(34))),
            "a",
            "stroke",
            True,
        ),
        "positive-horizontal-offsets": (
            170,
            (tuple(range(34)), tuple(range(34))),
            "mixed",
            "horizontal",
            True,
        ),
        "positive-sparse-distractors": (
            174,
            (tuple(range(33)), tuple(range(33))),
            "mixed",
            "clean",
            True,
        ),
    }
    try:
        return recipes[case_id]
    except KeyError:
        raise KP1979V3GeneratorError("positive recipe is outside the closed roster") from None


def _build_positive(item_seed: bytes, case_id: str) -> tuple[bytes, PageLatticeCertificate]:
    pitch, indices, renderer_mode, style_mode, jitter_enabled = _positive_recipe(case_id)
    phase = _phase(
        item_seed,
        pitch=pitch,
        maximum_grid_index=max(max(indices[0]), max(indices[1])),
    )
    certificate = _build_scene(
        item_seed=item_seed,
        scene_id=case_id,
        pitch=pitch,
        phase=phase,
        lane_indices=indices,
        renderer_mode=renderer_mode,
        style_mode=style_mode,
        jitter_enabled=jitter_enabled,
    )
    if case_id == "positive-horizontal-offsets":
        # Keep the exact pitch/anchors while varying horizontal support per slot.
        witnesses: list[CompleteWitness] = []
        for witness in certificate.witnesses:
            offset = _stream(
                item_seed,
                f"{DISTRACTOR_LABEL}/{witness.lane}/{witness.grid_index:02d}",
            ).randbelow(21)
            witnesses.append(
                _render_witness(
                    item_seed=item_seed,
                    scene_id=case_id,
                    output_lane=witness.lane,
                    seed_lane=witness.lane,
                    grid_index=witness.grid_index,
                    jitter=witness.jitter,
                    anchor_y=witness.anchor_y,
                    renderer_id=witness.invocation.renderer_id,
                    mode="horizontal",
                    lane_x0=offset,
                    lane_x1=offset + 235,
                )
            )
        ordered = tuple(sorted(witnesses, key=lambda value: (value.lane, value.grid_index)))
        certificate = PageLatticeCertificate(
            pitch=pitch,
            phase=phase,
            witnesses=ordered,
            truth_slots=_truth_slots(ordered),
            layers=tuple(witness.layer for witness in ordered),
        )
    if case_id == "positive-sparse-distractors":
        distractors = _small_distractor_layers(item_seed, case_id, certificate)
        certificate = replace(certificate, layers=certificate.layers + distractors)
    pbm = compose_pbm(certificate.layers)
    return pbm, certificate


def _negative_complete_witnesses(
    *,
    item_seed: bytes,
    case_id: str,
    pitch_by_lane: tuple[int | None, int | None],
    indices_by_lane: _LaneIndices,
    phase: int,
) -> tuple[CompleteWitness, ...]:
    witnesses: list[CompleteWitness] = []
    for lane in (0, 1):
        pitch = pitch_by_lane[lane]
        if pitch is None:
            continue
        for grid_index in indices_by_lane[lane]:
            witnesses.append(
                _render_witness(
                    item_seed=item_seed,
                    scene_id=case_id,
                    output_lane=lane,
                    seed_lane=lane,
                    grid_index=grid_index,
                    jitter=0,
                    anchor_y=phase + grid_index * pitch,
                    renderer_id=_renderer_for("mixed", lane, grid_index),
                    mode="clean",
                )
            )
    return tuple(sorted(witnesses, key=lambda value: (value.lane, value.grid_index)))


def _build_negative(item_seed: bytes, case_id: str) -> tuple[bytes, NegativeCertificate]:
    witnesses: tuple[CompleteWitness, ...] = ()
    layers: tuple[InkLayer, ...] = ()
    if case_id == "negative-single-lane":
        witnesses = _negative_complete_witnesses(
            item_seed=item_seed,
            case_id=case_id,
            pitch_by_lane=(166, None),
            indices_by_lane=(tuple(range(34)), ()),
            phase=650,
        )
        layers = tuple(witness.layer for witness in witnesses)
    elif case_id == "negative-cross-lane-pitch-conflict":
        witnesses = _negative_complete_witnesses(
            item_seed=item_seed,
            case_id=case_id,
            pitch_by_lane=(158, 193),
            indices_by_lane=(tuple(range(36)), tuple(range(29))),
            phase=650,
        )
        layers = tuple(witness.layer for witness in witnesses)
    elif case_id == "negative-blank":
        layers = ()
    elif case_id == "negative-periodic-single-tier":
        layers = tuple(
            _canvas_layer(
                layer_id=f"{case_id}/{lane}",
                kind=InkLayerKind.INCOMPLETE_PRIMITIVE,
                lane=lane,
                draw="single-tier",
                seed=item_seed,
            )
            for lane in (0, 1)
        )
    elif case_id == "negative-periodic-two-tier-paired-segments":
        layers = tuple(
            _canvas_layer(
                layer_id=f"{case_id}/{lane}",
                kind=InkLayerKind.INCOMPLETE_PRIMITIVE,
                lane=lane,
                draw="long-bars",
                seed=item_seed,
            )
            for lane in (0, 1)
        )
    elif case_id == "negative-periodic-paired-dashes":
        layers = tuple(
            _canvas_layer(
                layer_id=f"{case_id}/{lane}",
                kind=InkLayerKind.INCOMPLETE_PRIMITIVE,
                lane=lane,
                draw="dashes",
                seed=item_seed,
            )
            for lane in (0, 1)
        )
    elif case_id in {
        "negative-ruled-form",
        "negative-table-grid",
        "negative-repeated-boxes",
        "negative-decorative-border",
        "negative-repeated-stamp",
        "negative-dense-multicolumn",
        "negative-staggered-single-tiers",
    }:
        draw_by_case = {
            "negative-ruled-form": "ruled",
            "negative-table-grid": "table",
            "negative-repeated-boxes": "boxes",
            "negative-decorative-border": "border",
            "negative-repeated-stamp": "stamp",
            "negative-dense-multicolumn": "dense",
            "negative-staggered-single-tiers": "staggered",
        }
        draw = draw_by_case[case_id]
        layers = tuple(
            _canvas_layer(
                layer_id=f"{case_id}/{lane}",
                kind=InkLayerKind.INCOMPLETE_PRIMITIVE,
                lane=lane,
                draw=draw,
                seed=item_seed,
            )
            for lane in (0, 1)
        )
    elif case_id == "negative-mixed-label-confound":
        layers = _partial_renderer_layers(item_seed, case_id)
    else:
        raise KP1979V3GeneratorError("negative recipe is outside the closed roster")

    certificate = NegativeCertificate(
        case_id=case_id,
        failure=NEGATIVE_FAILURE_BY_CASE_ID[case_id],
        complete_witnesses=witnesses,
        layers=layers,
    )
    pbm = compose_pbm(layers)
    return pbm, certificate


def _request(pbm: bytes) -> bytes:
    return encode_worker_request(
        pbm=pbm,
        width=SYNTHETIC_PAGE_WIDTH,
        height=SYNTHETIC_PAGE_HEIGHT,
        scan_bands=SYNTHETIC_SCAN_BANDS,
    )


def _out_of_contract_request(
    case_id: str,
    expected_error_code: InputErrorCode,
) -> tuple[bytes, bytes]:
    pbm = compose_pbm(())
    width = SYNTHETIC_PAGE_WIDTH
    height = SYNTHETIC_PAGE_HEIGHT
    bands = SYNTHETIC_SCAN_BANDS
    if case_id == "out-of-contract-truncated-payload":
        pbm = pbm[:-1]
    elif case_id == "out-of-contract-extended-payload":
        pbm += b"\x00"
    elif case_id == "out-of-contract-noncanonical-header":
        pbm = b"P4\t4880 7010\n" + pbm[len(RAW_P4_CONTRACT.header) :]
    elif case_id == "out-of-contract-dimension-mismatch":
        width = 4879
    elif case_id == "out-of-contract-wrong-scan-extent":
        first, second = bands
        bands = ((first[0], first[1], first[2] - 1, first[3]), second)
    elif case_id == "out-of-contract-overlapping-scan-bands":
        first, second = bands
        bands = (first, (first[2] - 1, second[1], second[2], second[3]))
    else:
        raise KP1979V3GeneratorError("out-of-contract recipe is outside the closed roster")
    request = encode_worker_request(pbm=pbm, width=width, height=height, scan_bands=bands)
    decode_worker_request_envelope(request)
    try:
        decode_worker_request(request)
    except KP1979V3WorkerInputError as exc:
        if exc.error_code is not expected_error_code:
            raise KP1979V3GeneratorError(
                "out-of-contract semantic error precedence changed"
            ) from None
    else:
        raise KP1979V3GeneratorError("out-of-contract request passed semantic validation")
    return request, pbm


def _build_case_unvalidated(seed: bytes, ordinal: int) -> GeneratedCase:
    """Build one canonical case without entering the public validation boundary."""

    if type(ordinal) is not int or not 0 <= ordinal < len(CASE_ROSTER):
        raise KP1979V3GeneratorError("case ordinal is outside the frozen roster")
    spec = CASE_ROSTER[ordinal]
    item_seed = _case_seed(seed, ordinal, spec.case_id)
    positive: PageLatticeCertificate | None = None
    negative: NegativeCertificate | None = None
    if spec.category is CaseCategory.POSITIVE:
        pbm, positive = _build_positive(item_seed, spec.case_id)
        request = _request(pbm)
    elif spec.category is CaseCategory.NEGATIVE:
        pbm, negative = _build_negative(item_seed, spec.case_id)
        request = _request(pbm)
    else:
        assert spec.expected_error_code is not None
        request, pbm = _out_of_contract_request(spec.case_id, spec.expected_error_code)
    return GeneratedCase(
        ordinal=ordinal,
        case_id=spec.case_id,
        category=spec.category,
        generation_commitment=_generation_commitment(
            _CASE_GENERATION_COMMITMENT_DOMAIN,
            item_seed,
        ),
        request_bytes=request,
        request_sha256=sha256(request).hexdigest(),
        pbm_sha256=sha256(pbm).hexdigest(),
        positive=positive,
        negative=negative,
        expected_error_code=spec.expected_error_code,
    )


def build_case(seed: bytes, ordinal: int) -> GeneratedCase:
    """Build and suite-seed-validate one protocol case by zero-based ordinal."""

    generated = _build_case_unvalidated(seed, ordinal)
    validate_generated_case(generated, seed=seed)
    return generated


def validate_generated_case(case: GeneratedCase, *, seed: bytes) -> None:
    """Authoritatively validate one case against its suite-seed canonical object."""

    _require_seed(seed)
    if (
        type(case) is not GeneratedCase
        or type(case.ordinal) is not int
        or not 0 <= case.ordinal < len(CASE_ROSTER)
    ):
        raise KP1979V3GeneratorError("generated case identity is invalid")
    if (
        type(case.case_id) is not str
        or type(case.category) is not CaseCategory
        or type(case.generation_commitment) is not bytes
        or len(case.generation_commitment) != 32
        or (
            case.expected_error_code is not None
            and type(case.expected_error_code) is not InputErrorCode
        )
        or type(case.request_bytes) is not bytes
        or not case.request_bytes
        or not _is_sha256(case.request_sha256)
        or not _is_sha256(case.pbm_sha256)
        or (case.positive is not None and type(case.positive) is not PageLatticeCertificate)
        or (case.negative is not None and type(case.negative) is not NegativeCertificate)
    ):
        raise KP1979V3GeneratorError("generated case closed fields are invalid")
    spec = CASE_ROSTER[case.ordinal]
    if (
        case.case_id,
        case.category,
        case.expected_error_code,
    ) != (spec.case_id, spec.category, spec.expected_error_code):
        raise KP1979V3GeneratorError("generated case differs from its protocol slot")
    if case.category is CaseCategory.POSITIVE:
        if type(case.positive) is not PageLatticeCertificate or case.negative is not None:
            raise KP1979V3GeneratorError("positive oracle union is invalid")
    elif case.category is CaseCategory.NEGATIVE:
        if type(case.negative) is not NegativeCertificate or case.positive is not None:
            raise KP1979V3GeneratorError("negative oracle union is invalid")
    elif case.positive is not None or case.negative is not None:
        raise KP1979V3GeneratorError("out-of-contract case carries an oracle")
    if sha256(case.request_bytes).hexdigest() != case.request_sha256:
        raise KP1979V3GeneratorError("generated request commitment is invalid")
    try:
        envelope = decode_worker_request_envelope(case.request_bytes)
    except (KP1979V3WireError, KP1979V3WorkerInputError):
        raise KP1979V3GeneratorError("generated request envelope is invalid") from None
    if sha256(envelope.pbm).hexdigest() != case.pbm_sha256:
        raise KP1979V3GeneratorError("generated PBM commitment is invalid")
    if case.category is CaseCategory.POSITIVE:
        assert type(case.positive) is PageLatticeCertificate
        try:
            decode_worker_request(case.request_bytes)
            validate_page_lattice(case.positive, maximum_jitter=GENERATOR_MAXIMUM_JITTER)
            validate_page_composition(envelope.pbm, case.positive.layers)
        except (KP1979V3GrammarError, KP1979V3WireError, KP1979V3WorkerInputError):
            raise KP1979V3GeneratorError("positive case request or oracle is invalid") from None
    elif case.category is CaseCategory.NEGATIVE:
        assert type(case.negative) is NegativeCertificate
        try:
            decode_worker_request(case.request_bytes)
            _validate_negative_certificate_structure(case.negative)
            validate_page_composition(envelope.pbm, case.negative.layers)
        except (KP1979V3GrammarError, KP1979V3WireError, KP1979V3WorkerInputError):
            raise KP1979V3GeneratorError("negative case request or oracle is invalid") from None
    else:
        try:
            decode_worker_request(case.request_bytes)
        except KP1979V3WorkerInputError as exc:
            if exc.error_code is not case.expected_error_code:
                raise KP1979V3GeneratorError("out-of-contract error code changed") from None
        except KP1979V3WireError:
            raise KP1979V3GeneratorError("out-of-contract request is invalid") from None
        else:
            raise KP1979V3GeneratorError("out-of-contract case passed semantic validation")
    if case != _build_case_unvalidated(seed, case.ordinal):
        raise KP1979V3GeneratorError("generated case differs from its suite-seed canonical object")


def _endpoint(endpoint: str, certificate: PageLatticeCertificate) -> GeneratedEndpoint:
    pbm = compose_pbm(certificate.layers)
    request = _request(pbm)
    return GeneratedEndpoint(
        endpoint=endpoint,
        request_bytes=request,
        request_sha256=sha256(request).hexdigest(),
        pbm_sha256=sha256(pbm).hexdigest(),
        positive=certificate,
    )


def _relation_base(
    item_seed: bytes,
    relation_id: str,
    *,
    renderer_mode: _RendererMode = "a",
    style_mode: str = "clean",
    bottom_delta: int = 11,
    vertical_delta: int = 0,
    horizontal_delta: int = 0,
    horizontal_width: int = LABEL_LAYER_WIDTH,
    source_lane_for_output: tuple[int, int] = (0, 1),
    omitted: tuple[int, int] | None = None,
    stroke_override: int | None = None,
) -> PageLatticeCertificate:
    indices: _LaneIndices = (tuple(range(34)), tuple(range(34)))
    phase = _phase(item_seed, pitch=166, maximum_grid_index=33, bottom_delta=bottom_delta)
    return _build_scene(
        item_seed=item_seed,
        scene_id=relation_id,
        pitch=166,
        phase=phase,
        lane_indices=indices,
        renderer_mode=renderer_mode,
        style_mode=style_mode,
        jitter_enabled=True,
        vertical_delta=vertical_delta,
        horizontal_delta=horizontal_delta,
        horizontal_width=horizontal_width,
        source_lane_for_output=source_lane_for_output,
        omitted=omitted,
        stroke_override=stroke_override,
    )


def _with_unread_margin(
    item_seed: bytes,
    relation_id: str,
    certificate: PageLatticeCertificate,
) -> PageLatticeCertificate:
    stream = _stream(item_seed, DISTRACTOR_LABEL)
    width = 23 + stream.randbelow(9)
    height = 11 + stream.randbelow(7)
    canvas = MonochromeCanvas(width, height, max_mutations=2)
    canvas.fill_ink_rect(0, 0, width, height)
    packed = canvas.packed_crop(0, 0, width, height)
    layer = _make_layer(
        layer_id=f"{relation_id}/unread-margin",
        kind=InkLayerKind.DISTRACTOR,
        x0=100 + stream.randbelow(300),
        y0=100 + stream.randbelow(200),
        width=width,
        height=height,
        packed=packed,
    )
    result = replace(certificate, layers=(*certificate.layers, layer))
    return result


def _build_relation_unvalidated(seed: bytes, ordinal: int) -> GeneratedRelation:
    """Build one canonical relation without entering the public validation boundary."""

    if type(ordinal) is not int or not 0 <= ordinal < len(METAMORPHIC_RELATIONS):
        raise KP1979V3GeneratorError("relation ordinal is outside the frozen roster")
    spec = METAMORPHIC_RELATIONS[ordinal]
    item_seed = _relation_seed(seed, ordinal, spec.relation_id)
    omitted_layer: InkLayer | None = None

    if spec.kind is MetamorphicKind.IDENTICAL:
        first_certificate = _relation_base(item_seed, spec.relation_id)
        first = _endpoint("a", first_certificate)
        second = replace(first, endpoint="b")
    elif spec.kind is MetamorphicKind.UNREAD_MARGIN:
        first_certificate = _relation_base(item_seed, spec.relation_id)
        second_certificate = _with_unread_margin(item_seed, spec.relation_id, first_certificate)
        first = _endpoint("a", first_certificate)
        second = _endpoint("b", second_certificate)
    elif spec.kind is MetamorphicKind.VERTICAL_PLUS_11:
        first = _endpoint("a", _relation_base(item_seed, spec.relation_id))
        second = _endpoint(
            "b",
            _relation_base(item_seed, spec.relation_id, vertical_delta=11),
        )
    elif spec.kind is MetamorphicKind.HORIZONTAL_TRANSLATION:
        first = _endpoint(
            "a",
            _relation_base(
                item_seed,
                spec.relation_id,
                horizontal_width=240,
            ),
        )
        second = _endpoint(
            "b",
            _relation_base(
                item_seed,
                spec.relation_id,
                horizontal_delta=17,
                horizontal_width=240,
            ),
        )
    elif spec.kind is MetamorphicKind.STROKE_WIDTH:
        first = _endpoint(
            "a",
            _relation_base(
                item_seed,
                spec.relation_id,
                style_mode="stroke",
                stroke_override=1,
            ),
        )
        second = _endpoint(
            "b",
            _relation_base(
                item_seed,
                spec.relation_id,
                style_mode="stroke",
                stroke_override=4,
            ),
        )
    elif spec.kind is MetamorphicKind.RENDERER_SUBSTITUTION:
        first = _endpoint(
            "a",
            _relation_base(item_seed, spec.relation_id, renderer_mode="a"),
        )
        second = _endpoint(
            "b",
            _relation_base(item_seed, spec.relation_id, renderer_mode="b"),
        )
    elif spec.kind is MetamorphicKind.LANE_SWAP:
        first = _endpoint(
            "a",
            _relation_base(item_seed, spec.relation_id, renderer_mode="mixed"),
        )
        second = _endpoint(
            "b",
            _relation_base(
                item_seed,
                spec.relation_id,
                renderer_mode="mixed",
                source_lane_for_output=(1, 0),
            ),
        )
    elif spec.kind is MetamorphicKind.GAP_DELETION:
        gap = _stream(item_seed, GAP_LABEL)
        omitted = (gap.randbelow(2), 2 + gap.randbelow(30))
        first_certificate = _relation_base(
            item_seed,
            spec.relation_id,
            renderer_mode="mixed",
        )
        second_certificate = _relation_base(
            item_seed,
            spec.relation_id,
            renderer_mode="mixed",
            omitted=omitted,
        )
        omitted_layer = next(
            witness.layer
            for witness in first_certificate.witnesses
            if (witness.lane, witness.grid_index) == omitted
        )
        first = _endpoint("a", first_certificate)
        second = _endpoint("b", second_certificate)
    else:
        raise KP1979V3GeneratorError("metamorphic kind is outside the closed roster")

    return GeneratedRelation(
        ordinal=ordinal,
        relation_id=spec.relation_id,
        kind=spec.kind,
        generation_commitment=_generation_commitment(
            _RELATION_GENERATION_COMMITMENT_DOMAIN,
            item_seed,
        ),
        endpoints=(first, second),
        omitted_layer=omitted_layer,
    )


def build_relation(seed: bytes, ordinal: int) -> GeneratedRelation:
    """Build and suite-seed-validate one two-endpoint metamorphic relation."""

    relation = _build_relation_unvalidated(seed, ordinal)
    validate_generated_relation(relation, seed=seed)
    return relation


def _request_pbm(endpoint: GeneratedEndpoint) -> bytes:
    request = decode_worker_request(endpoint.request_bytes)
    if sha256(request.pbm).hexdigest() != endpoint.pbm_sha256:
        raise KP1979V3GeneratorError("relation endpoint PBM commitment differs")
    return request.pbm


def _truth_geometry(certificate: PageLatticeCertificate) -> tuple[tuple[int, int, int, int], ...]:
    return tuple((slot.lane, slot.grid_index, slot.y0, slot.y1) for slot in certificate.truth_slots)


def _ink_points(pbm: bytes) -> frozenset[tuple[int, int]]:
    payload = pbm[len(RAW_P4_CONTRACT.header) :]
    points: set[tuple[int, int]] = set()
    for byte_index, value in enumerate(payload):
        if not value:
            continue
        y, x_byte = divmod(byte_index, RAW_P4_CONTRACT.row_bytes)
        for bit in range(8):
            if value & (0x80 >> bit):
                points.add((x_byte * 8 + bit, y))
    return frozenset(points)


def _band_crop(pbm: bytes, lane: int) -> bytes:
    band = SYNTHETIC_SCAN_BANDS[lane]
    payload = pbm[len(RAW_P4_CONTRACT.header) :]
    output = bytearray()
    for y in range(band[1], band[3]):
        row = payload[y * RAW_P4_CONTRACT.row_bytes : (y + 1) * RAW_P4_CONTRACT.row_bytes]
        canvas = MonochromeCanvas(LABEL_LAYER_WIDTH, 1, max_mutations=LABEL_LAYER_WIDTH + 1)
        for x in range(band[0], band[2]):
            if row[x // 8] & (0x80 >> (x % 8)):
                canvas.set_ink(x - band[0], 0)
        output.extend(canvas.packed_crop(0, 0, LABEL_LAYER_WIDTH, 1))
    return bytes(output)


def _layer_page_points(layer: InkLayer) -> frozenset[tuple[int, int]]:
    row_bytes = (layer.width + 7) // 8
    return frozenset(
        (layer.x0 + x, layer.y0 + y)
        for y in range(layer.height)
        for x in range(layer.width)
        if layer.packed[y * row_bytes + x // 8] & (0x80 >> (x % 8))
    )


def _complete_only(certificate: PageLatticeCertificate) -> bool:
    return certificate.layers == tuple(witness.layer for witness in certificate.witnesses)


def _witness_keys(
    certificate: PageLatticeCertificate,
) -> tuple[tuple[int, int], ...]:
    return tuple((witness.lane, witness.grid_index) for witness in certificate.witnesses)


def _same_witness_support(first: CompleteWitness, second: CompleteWitness) -> bool:
    return (
        first.lane,
        first.grid_index,
        first.jitter,
        first.anchor_y,
        first.layer.layer_id,
        first.layer.kind,
        first.layer.x0,
        first.layer.y0,
        first.layer.width,
        first.layer.height,
    ) == (
        second.lane,
        second.grid_index,
        second.jitter,
        second.anchor_y,
        second.layer.layer_id,
        second.layer.kind,
        second.layer.x0,
        second.layer.y0,
        second.layer.width,
        second.layer.height,
    )


def _renderer_common_fields(invocation: RendererInvocation) -> tuple[object, ...]:
    return (
        invocation.lane_x0,
        invocation.lane_x1,
        invocation.qualifier_variant,
        invocation.damage_percent,
        invocation.horizontal_alignment,
    )


def _layer_support_is_outside_scan_bands(layer: InkLayer) -> bool:
    layer_x1 = layer.x0 + layer.width
    layer_y1 = layer.y0 + layer.height
    return all(
        layer_x1 <= x0 or x1 <= layer.x0 or layer_y1 <= y0 or y1 <= layer.y0
        for x0, y0, x1, y1 in SYNTHETIC_SCAN_BANDS
    )


def _relation_slot_layer_ids_are_exact(
    relation_id: str,
    certificate: PageLatticeCertificate,
) -> bool:
    if type(certificate.witnesses) is not tuple:
        return False
    return all(
        type(witness) is CompleteWitness
        and type(witness.lane) is int
        and type(witness.grid_index) is int
        and type(witness.layer) is InkLayer
        and type(witness.layer.layer_id) is str
        and witness.layer.layer_id == f"{relation_id}/slot/{witness.lane}/{witness.grid_index:02d}"
        for witness in certificate.witnesses
    )


def validate_generated_relation(relation: GeneratedRelation, *, seed: bytes) -> None:
    """Authoritatively validate a relation against its suite-seed canonical object."""

    _require_seed(seed)
    if (
        type(relation) is not GeneratedRelation
        or type(relation.ordinal) is not int
        or not 0 <= relation.ordinal < len(METAMORPHIC_RELATIONS)
    ):
        raise KP1979V3GeneratorError("generated relation identity is invalid")
    if (
        type(relation.relation_id) is not str
        or type(relation.kind) is not MetamorphicKind
        or type(relation.generation_commitment) is not bytes
        or len(relation.generation_commitment) != 32
    ):
        raise KP1979V3GeneratorError("generated relation closed fields are invalid")
    spec = METAMORPHIC_RELATIONS[relation.ordinal]
    if (relation.relation_id, relation.kind) != (spec.relation_id, spec.kind):
        raise KP1979V3GeneratorError("generated relation differs from its protocol slot")
    if (
        type(relation.endpoints) is not tuple
        or len(relation.endpoints) != 2
        or any(type(endpoint) is not GeneratedEndpoint for endpoint in relation.endpoints)
    ):
        raise KP1979V3GeneratorError("relation endpoints do not use the exact closed type")
    if tuple(endpoint.endpoint for endpoint in relation.endpoints) != ENDPOINT_NAMES:
        raise KP1979V3GeneratorError("relation endpoints are not exact A/B values")
    if relation.kind is MetamorphicKind.GAP_DELETION:
        if type(relation.omitted_layer) is not InkLayer:
            raise KP1979V3GeneratorError("gap deletion lacks one exact omitted layer")
    elif relation.omitted_layer is not None:
        raise KP1979V3GeneratorError("only gap deletion may carry an omitted layer")
    for endpoint in relation.endpoints:
        if (
            type(endpoint.request_bytes) is not bytes
            or not endpoint.request_bytes
            or not _is_sha256(endpoint.request_sha256)
            or not _is_sha256(endpoint.pbm_sha256)
            or type(endpoint.positive) is not PageLatticeCertificate
        ):
            raise KP1979V3GeneratorError("relation endpoint closed fields are invalid")

    first, second = relation.endpoints
    if not _relation_slot_layer_ids_are_exact(
        relation.relation_id,
        first.positive,
    ) or not _relation_slot_layer_ids_are_exact(
        relation.relation_id,
        second.positive,
    ):
        raise KP1979V3GeneratorError("relation witness layer identities are not exact")
    for endpoint in relation.endpoints:
        if sha256(endpoint.request_bytes).hexdigest() != endpoint.request_sha256:
            raise KP1979V3GeneratorError("relation endpoint commitment is invalid")
        try:
            validate_page_lattice(
                endpoint.positive,
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )
        except KP1979V3GrammarError:
            raise KP1979V3GeneratorError("relation endpoint oracle is invalid") from None

    try:
        first_pbm = _request_pbm(first)
        second_pbm = _request_pbm(second)
        validate_page_composition(first_pbm, first.positive.layers)
        validate_page_composition(second_pbm, second.positive.layers)
    except (KP1979V3GrammarError, KP1979V3WireError, KP1979V3WorkerInputError):
        raise KP1979V3GeneratorError("relation endpoint request is invalid") from None
    first_points = _ink_points(first_pbm)
    second_points = _ink_points(second_pbm)
    first_truth = _truth_geometry(first.positive)
    second_truth = _truth_geometry(second.positive)

    if relation.kind is MetamorphicKind.IDENTICAL:
        if (
            not _complete_only(first.positive)
            or first.request_bytes != second.request_bytes
            or first.positive != second.positive
        ):
            raise KP1979V3GeneratorError("identical endpoints differ")
    elif relation.kind is MetamorphicKind.UNREAD_MARGIN:
        if (
            not _complete_only(first.positive)
            or first.positive.pitch != second.positive.pitch
            or first.positive.phase != second.positive.phase
            or first.positive.witnesses != second.positive.witnesses
            or first.positive.truth_slots != second.positive.truth_slots
            or len(second.positive.layers) != len(first.positive.layers) + 1
            or second.positive.layers[:-1] != first.positive.layers
        ):
            raise KP1979V3GeneratorError("unread-margin relation changed its base certificate")
        distractor = second.positive.layers[-1]
        if (
            distractor.kind is not InkLayerKind.DISTRACTOR
            or distractor.layer_id != f"{relation.relation_id}/unread-margin"
            or not _layer_support_is_outside_scan_bands(distractor)
            or first_pbm == second_pbm
            or first_truth != second_truth
            or first_points ^ second_points != _layer_page_points(distractor)
        ):
            raise KP1979V3GeneratorError("unread-margin addition is not one exact unread layer")
    elif relation.kind is MetamorphicKind.VERTICAL_PLUS_11:
        expected_witnesses = tuple(
            replace(
                witness,
                anchor_y=witness.anchor_y + 11,
                layer=replace(witness.layer, y0=witness.layer.y0 + 11),
            )
            for witness in first.positive.witnesses
        )
        if (
            not _complete_only(first.positive)
            or not _complete_only(second.positive)
            or first.positive.pitch != second.positive.pitch
            or second.positive.phase != first.positive.phase + 11
            or second.positive.witnesses != expected_witnesses
            or frozenset((x, y + 11) for x, y in first_points) != second_points
            or tuple((lane, grid, y0 + 11, y1 + 11) for lane, grid, y0, y1 in first_truth)
            != second_truth
        ):
            raise KP1979V3GeneratorError("vertical-plus-11 is not an exact pixel/truth shift")
    elif relation.kind is MetamorphicKind.HORIZONTAL_TRANSLATION:
        if (
            not _complete_only(first.positive)
            or not _complete_only(second.positive)
            or first.positive.pitch != second.positive.pitch
            or first.positive.phase != second.positive.phase
            or _witness_keys(first.positive) != _witness_keys(second.positive)
            or frozenset((x + 17, y) for x, y in first_points) != second_points
            or first_truth != second_truth
        ):
            raise KP1979V3GeneratorError("horizontal relation is not an exact +17 pixel shift")
    elif relation.kind is MetamorphicKind.STROKE_WIDTH:
        paired_witnesses = tuple(
            zip(first.positive.witnesses, second.positive.witnesses, strict=False)
        )
        if (
            not _complete_only(first.positive)
            or not _complete_only(second.positive)
            or first.positive.pitch != second.positive.pitch
            or first.positive.phase != second.positive.phase
            or _witness_keys(first.positive) != _witness_keys(second.positive)
            or first_pbm == second_pbm
            or first_truth != second_truth
            or any(
                not _same_witness_support(first_witness, second_witness)
                or first_witness.invocation.renderer_id != ORTHOGONAL_RENDERER_ID
                or first_witness.invocation.stroke_width != 1
                or second_witness.invocation != replace(first_witness.invocation, stroke_width=4)
                or first_witness.layer.packed == second_witness.layer.packed
                for first_witness, second_witness in paired_witnesses
            )
        ):
            raise KP1979V3GeneratorError("stroke relation is not exact Renderer A width 1-to-4")
    elif relation.kind is MetamorphicKind.RENDERER_SUBSTITUTION:
        paired_witnesses = tuple(
            zip(first.positive.witnesses, second.positive.witnesses, strict=False)
        )
        if (
            not _complete_only(first.positive)
            or not _complete_only(second.positive)
            or first.positive.pitch != second.positive.pitch
            or first.positive.phase != second.positive.phase
            or _witness_keys(first.positive) != _witness_keys(second.positive)
            or first_pbm == second_pbm
            or first_truth != second_truth
            or any(
                not _same_witness_support(first_witness, second_witness)
                or first_witness.invocation.renderer_id != ORTHOGONAL_RENDERER_ID
                or second_witness.invocation.renderer_id != BITMAP_RENDERER_ID
                or first_witness.invocation.entropy == second_witness.invocation.entropy
                or _renderer_common_fields(first_witness.invocation)
                != _renderer_common_fields(second_witness.invocation)
                or first_witness.layer.packed == second_witness.layer.packed
                for first_witness, second_witness in paired_witnesses
            )
        ):
            raise KP1979V3GeneratorError("renderer substitution is not an exact A-to-B relation")
    elif relation.kind is MetamorphicKind.LANE_SWAP:
        expected_witnesses = tuple(
            sorted(
                (
                    replace(
                        witness,
                        lane=witness.lane ^ 1,
                        layer=replace(
                            witness.layer,
                            layer_id=(
                                f"{relation.relation_id}/slot/"
                                f"{witness.lane ^ 1}/{witness.grid_index:02d}"
                            ),
                            x0=SYNTHETIC_SCAN_BANDS[witness.lane ^ 1][0],
                        ),
                    )
                    for witness in first.positive.witnesses
                ),
                key=lambda witness: (witness.lane, witness.grid_index),
            )
        )
        swapped_truth = tuple(
            sorted(
                ((lane ^ 1, grid, y0, y1) for lane, grid, y0, y1 in first_truth),
                key=lambda value: (value[0], value[1]),
            )
        )
        if (
            not _complete_only(first.positive)
            or not _complete_only(second.positive)
            or first.positive.pitch != second.positive.pitch
            or first.positive.phase != second.positive.phase
            or second.positive.witnesses != expected_witnesses
            or _band_crop(first_pbm, 0) != _band_crop(second_pbm, 1)
            or _band_crop(first_pbm, 1) != _band_crop(second_pbm, 0)
            or swapped_truth != second_truth
        ):
            raise KP1979V3GeneratorError("lane swap is not an exact crop/truth permutation")
    elif relation.kind is MetamorphicKind.GAP_DELETION:
        if relation.omitted_layer is None:
            raise KP1979V3GeneratorError("gap deletion lacks its omitted layer")
        omitted_witnesses = tuple(
            witness
            for witness in first.positive.witnesses
            if witness.layer == relation.omitted_layer
        )
        if len(omitted_witnesses) != 1:
            raise KP1979V3GeneratorError(
                "gap deletion omitted layer is not one exact first witness"
            )
        omitted_witness = omitted_witnesses[0]
        expected_witnesses = tuple(
            witness for witness in first.positive.witnesses if witness != omitted_witness
        )
        expected_truth = tuple(
            slot
            for slot in first.positive.truth_slots
            if (slot.lane, slot.grid_index) != (omitted_witness.lane, omitted_witness.grid_index)
        )
        difference = first_points ^ second_points
        if (
            not _complete_only(first.positive)
            or not _complete_only(second.positive)
            or first.positive.pitch != second.positive.pitch
            or first.positive.phase != second.positive.phase
            or second.positive.witnesses != expected_witnesses
            or second.positive.truth_slots != expected_truth
            or relation.omitted_layer in second.positive.layers
            or difference != _layer_page_points(relation.omitted_layer)
        ):
            raise KP1979V3GeneratorError("gap deletion is not one exact witness removal")
    else:
        raise KP1979V3GeneratorError("relation validator reached an unknown kind")
    if relation != _build_relation_unvalidated(seed, relation.ordinal):
        raise KP1979V3GeneratorError(
            "generated relation differs from its suite-seed canonical object"
        )


def iter_schedule(seed: bytes) -> Iterator[_ScheduledInvocation]:
    """Yield the controller-private fixed 48-call execution schedule.

    Schedule objects contain evaluation meaning and MUST NOT be persisted or
    published before execution, and MUST NOT be passed to a worker. A
    controller may dispatch only ``request_bytes`` across the worker boundary.
    """

    _require_seed(seed)
    invocation_index = 0
    for ordinal, _spec in enumerate(CASE_ROSTER):
        case = build_case(seed, ordinal)
        yield _ScheduledInvocation(
            invocation_index=invocation_index,
            source_kind="case",
            source_ordinal=ordinal,
            source_id=case.case_id,
            endpoint=None,
            category=case.category,
            expected_error_code=case.expected_error_code,
            request_bytes=case.request_bytes,
            request_sha256=case.request_sha256,
            pbm_sha256=case.pbm_sha256,
        )
        invocation_index += 1
    for ordinal, spec in enumerate(METAMORPHIC_RELATIONS):
        relation = build_relation(seed, ordinal)
        for endpoint in relation.endpoints:
            yield _ScheduledInvocation(
                invocation_index=invocation_index,
                source_kind="relation",
                source_ordinal=ordinal,
                source_id=spec.relation_id,
                endpoint=endpoint.endpoint,
                category=CaseCategory.POSITIVE,
                expected_error_code=None,
                request_bytes=endpoint.request_bytes,
                request_sha256=endpoint.request_sha256,
                pbm_sha256=endpoint.pbm_sha256,
            )
            invocation_index += 1
    if invocation_index != TOTAL_WORKER_INVOCATIONS:
        raise KP1979V3GeneratorError("fixed schedule invocation accounting changed")


__all__ = [
    "DISTRACTOR_LABEL",
    "ENDPOINT_NAMES",
    "GAP_LABEL",
    "GENERATOR_ID",
    "JITTER_LABEL",
    "LAYOUT_LABEL",
    "STYLE_LABEL",
    "SUITE_DOMAIN_LABEL",
    "GeneratedCase",
    "GeneratedEndpoint",
    "GeneratedRelation",
    "KP1979V3GeneratorError",
    "build_case",
    "build_relation",
    "iter_schedule",
    "validate_generated_case",
    "validate_generated_relation",
]
