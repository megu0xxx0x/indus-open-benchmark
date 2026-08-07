"""Deterministic, language-blind glyph matching for private KP1979 development rows.

The matcher deliberately knows nothing about readings, meanings, languages, sign
frequencies, or neighbouring signs.  It compares only binary shape and searches
segmentation and template-rank choices jointly.  Callers remain responsible for
the source-pixel and development-partition boundary.
"""

from __future__ import annotations

import hashlib
import re
import weakref
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SCORE_SCALE = 1_000_000
NORMALIZED_CANVAS_SIZE = 64
NORMALIZED_PADDING = 4
TOP_PATH_COUNT = 3
TOP_RANKS_PER_SPAN = 3
MAX_PBM_BYTES = 16 * 1024 * 1024
MAX_BITMAP_DIMENSION = 16_384
MAX_ROW_WIDTH = 4_096
MAX_ROW_HEIGHT = 512
MAX_ROW_PBM_BYTES = 1024 * 1024
MAX_TEMPLATE_DIMENSION = 512
MAX_TEMPLATE_PBM_BYTES = 256 * 1024
MAX_TEMPLATE_COUNT = 1_024
MAX_CATALOG_RANKS = 512
MAX_TEMPLATE_COLUMN_RUNS = 16
MAX_PRIMITIVE_RUNS = 128
MAX_CANDIDATE_RUN_SPAN = 16
MATCHER_ALGORITHM_ID = "kp1979-shape-only-joint-segmentation-v1"
_STABILITY_NORMALIZATION_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))

_PBM_HEADER = re.compile(rb"\AP4\n([1-9][0-9]*) ([1-9][0-9]*)\n")
_VARIANT_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:._-]{0,127}\Z")
_ROW_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:._-]{0,159}\Z")


class KP1979GlyphMatchError(ValueError):
    """Raised when a glyph, matcher configuration, or row is invalid."""


@dataclass(frozen=True, slots=True)
class BinaryMask:
    """A compact binary image whose leftmost pixel is the highest used row bit."""

    width: int
    height: int
    rows: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 1 <= self.width <= MAX_BITMAP_DIMENSION:
            raise KP1979GlyphMatchError("binary mask width is outside its limit")
        if not 1 <= self.height <= MAX_BITMAP_DIMENSION:
            raise KP1979GlyphMatchError("binary mask height is outside its limit")
        if len(self.rows) != self.height:
            raise KP1979GlyphMatchError("binary mask row count differs from its height")
        row_limit = 1 << self.width
        if any(
            not isinstance(row, int) or isinstance(row, bool) or row < 0 or row >= row_limit
            for row in self.rows
        ):
            raise KP1979GlyphMatchError("binary mask contains an invalid packed row")

    @property
    def ink_count(self) -> int:
        return sum(row.bit_count() for row in self.rows)

    def tight_bbox(self) -> tuple[int, int, int, int] | None:
        ink_rows = [index for index, row in enumerate(self.rows) if row]
        if not ink_rows:
            return None
        y0 = ink_rows[0]
        y1 = ink_rows[-1] + 1
        x0 = self.width
        x1 = 0
        for row in self.rows[y0:y1]:
            if not row:
                continue
            highest_bit = row.bit_length() - 1
            lowest_bit = (row & -row).bit_length() - 1
            x0 = min(x0, self.width - 1 - highest_bit)
            x1 = max(x1, self.width - lowest_bit)
        return x0, y0, x1, y1

    def crop(self, bbox: Sequence[int]) -> BinaryMask:
        if len(bbox) != 4 or any(
            not isinstance(value, int) or isinstance(value, bool) for value in bbox
        ):
            raise KP1979GlyphMatchError("binary crop bbox must contain four integers")
        x0, y0, x1, y1 = bbox
        if not 0 <= x0 < x1 <= self.width or not 0 <= y0 < y1 <= self.height:
            raise KP1979GlyphMatchError("binary crop bbox lies outside its mask")
        crop_width = x1 - x0
        crop_mask = (1 << crop_width) - 1
        shift = self.width - x1
        rows = tuple((row >> shift) & crop_mask for row in self.rows[y0:y1])
        return BinaryMask(crop_width, y1 - y0, rows)


@dataclass(frozen=True, slots=True)
class MatcherConfig:
    """Frozen integer-only acceptance gates selected outside development rows."""

    max_token_cost: int
    min_different_rank_margin: int
    min_path_margin: int
    unknown_edge_cost: int
    cut_gap_support_ppm: int
    max_cut_penalty: int
    candidate_aspect_slack_ppm: int = 250_000
    top_paths: int = TOP_PATH_COUNT
    top_ranks_per_span: int = TOP_RANKS_PER_SPAN
    require_speck_stability: bool = True
    require_shift_stability: bool = True

    def __post_init__(self) -> None:
        integer_fields = (
            self.max_token_cost,
            self.min_different_rank_margin,
            self.min_path_margin,
            self.unknown_edge_cost,
            self.cut_gap_support_ppm,
            self.max_cut_penalty,
            self.candidate_aspect_slack_ppm,
            self.top_paths,
            self.top_ranks_per_span,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) for value in integer_fields):
            raise KP1979GlyphMatchError("matcher configuration must use integers")
        if not 0 <= self.max_token_cost <= 5 * SCORE_SCALE:
            raise KP1979GlyphMatchError("maximum token cost is outside its range")
        if not 0 <= self.min_different_rank_margin <= 5 * SCORE_SCALE:
            raise KP1979GlyphMatchError("rank margin is outside its range")
        if not 0 <= self.min_path_margin <= 100 * SCORE_SCALE:
            raise KP1979GlyphMatchError("path margin is outside its range")
        if not 0 < self.unknown_edge_cost <= 5 * SCORE_SCALE:
            raise KP1979GlyphMatchError("unknown-edge cost is outside its range")
        if not 0 <= self.cut_gap_support_ppm <= SCORE_SCALE:
            raise KP1979GlyphMatchError("cut-gap support is outside its range")
        if not 0 <= self.max_cut_penalty <= 5 * SCORE_SCALE:
            raise KP1979GlyphMatchError("cut penalty is outside its range")
        if not 0 <= self.candidate_aspect_slack_ppm <= SCORE_SCALE:
            raise KP1979GlyphMatchError("candidate aspect slack is outside its range")
        if self.top_paths != TOP_PATH_COUNT or self.top_ranks_per_span != TOP_RANKS_PER_SPAN:
            raise KP1979GlyphMatchError("matcher top-k values are fixed by the algorithm")
        if not isinstance(self.require_speck_stability, bool) or not isinstance(
            self.require_shift_stability, bool
        ):
            raise KP1979GlyphMatchError("matcher stability gates must be booleans")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MatcherConfig:
        required = {
            "max_token_cost",
            "min_different_rank_margin",
            "min_path_margin",
            "unknown_edge_cost",
            "cut_gap_support_ppm",
            "max_cut_penalty",
            "candidate_aspect_slack_ppm",
            "top_paths",
            "top_ranks_per_span",
            "require_speck_stability",
            "require_shift_stability",
        }
        if set(value) != required:
            raise KP1979GlyphMatchError("matcher configuration fields are not exact")
        try:
            return cls(**{key: value[key] for key in required})
        except TypeError as error:
            raise KP1979GlyphMatchError("matcher configuration has invalid values") from error

    def to_mapping(self) -> dict[str, int | bool]:
        return {
            "candidate_aspect_slack_ppm": self.candidate_aspect_slack_ppm,
            "cut_gap_support_ppm": self.cut_gap_support_ppm,
            "max_cut_penalty": self.max_cut_penalty,
            "max_token_cost": self.max_token_cost,
            "min_different_rank_margin": self.min_different_rank_margin,
            "min_path_margin": self.min_path_margin,
            "require_shift_stability": self.require_shift_stability,
            "require_speck_stability": self.require_speck_stability,
            "top_paths": self.top_paths,
            "top_ranks_per_span": self.top_ranks_per_span,
            "unknown_edge_cost": self.unknown_edge_cost,
        }


@dataclass(frozen=True, slots=True)
class _Template:
    variant_id: str
    catalog_rank: int
    source_width: int
    source_height: int
    normalized: BinaryMask
    dilated: BinaryMask
    normalized_ink_count: int
    internal_white_runs: int


@dataclass(frozen=True, slots=True)
class TemplateIndex:
    """Validated, normalized templates grouped without a rank-frequency prior."""

    templates: tuple[_Template, ...]
    max_internal_white_runs: int
    max_aspect_ppm: int
    cross_rank_normalized_variant_ids: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.templates or len(self.templates) > MAX_TEMPLATE_COUNT:
            raise KP1979GlyphMatchError("template index must not be empty")
        seen_variants: set[str] = set()
        ranks: set[int] = set()
        normalized_groups: dict[tuple[int, ...], list[_Template]] = {}
        observed_white_runs = 0
        observed_aspect = 0
        for template in self.templates:
            if _VARIANT_ID.fullmatch(template.variant_id) is None:
                raise KP1979GlyphMatchError("template index contains an invalid variant ID")
            if template.variant_id in seen_variants:
                raise KP1979GlyphMatchError("template index contains a duplicate variant ID")
            if not 1 <= template.catalog_rank <= 1_000_000:
                raise KP1979GlyphMatchError("template index contains an invalid rank")
            if not 1 <= template.source_width <= MAX_TEMPLATE_DIMENSION or not (
                1 <= template.source_height <= MAX_TEMPLATE_DIMENSION
            ):
                raise KP1979GlyphMatchError("template index contains invalid source dimensions")
            if (
                template.normalized.width != NORMALIZED_CANVAS_SIZE
                or template.normalized.height != NORMALIZED_CANVAS_SIZE
                or template.dilated != _dilate(template.normalized)
                or template.normalized_ink_count != template.normalized.ink_count
                or not template.normalized_ink_count
            ):
                raise KP1979GlyphMatchError("template index contains invalid normalized pixels")
            seen_variants.add(template.variant_id)
            ranks.add(template.catalog_rank)
            normalized_groups.setdefault(template.normalized.rows, []).append(template)
            observed_aspect = max(
                observed_aspect,
                template.source_width * SCORE_SCALE // template.source_height,
            )
            if not 0 <= template.internal_white_runs < MAX_TEMPLATE_COLUMN_RUNS:
                raise KP1979GlyphMatchError("template index contains an invalid white-run count")
            observed_white_runs = max(observed_white_runs, template.internal_white_runs)
        if len(ranks) > MAX_CATALOG_RANKS:
            raise KP1979GlyphMatchError("template index rank count exceeds its limit")
        if not 0 <= self.max_internal_white_runs <= MAX_TEMPLATE_COLUMN_RUNS - 1:
            raise KP1979GlyphMatchError("template index white-run bound is invalid")
        if (
            self.max_internal_white_runs != observed_white_runs
            or self.max_aspect_ppm != observed_aspect
        ):
            raise KP1979GlyphMatchError("template index derived bounds are inconsistent")
        cross_rank_variants: set[str] = set()
        for group in normalized_groups.values():
            if len({template.catalog_rank for template in group}) > 1:
                cross_rank_variants.update(template.variant_id for template in group)
        object.__setattr__(
            self,
            "cross_rank_normalized_variant_ids",
            frozenset(cross_rank_variants),
        )


@dataclass(frozen=True, slots=True)
class _RankCandidate:
    catalog_rank: int
    best_variant_ids: tuple[str, ...]
    overlap_cost: int
    aspect_cost: int
    emission_cost: int
    different_rank_margin: int


@dataclass(frozen=True, slots=True)
class _StabilityEvidence:
    cleaned_candidates: tuple[_RankCandidate, ...]
    shifted_candidates: tuple[tuple[_RankCandidate, ...], ...]


@dataclass(frozen=True, slots=True)
class _PreparedUnknownSpan:
    bbox: tuple[int, int, int, int]
    source_mask: BinaryMask


@dataclass(frozen=True, slots=True)
class _PreparedCandidateSpan:
    end: int
    bbox: tuple[int, int, int, int]
    source_mask: BinaryMask
    candidates: tuple[_RankCandidate, ...]
    stability: _StabilityEvidence


class _WorkspaceProvenance:
    """Bind one prepared workspace to the exact object created by this module."""

    __slots__ = ("_owner",)

    def __init__(self) -> None:
        self._owner: weakref.ReferenceType[Any] | None = None

    def bind(self, workspace: _RowMatchWorkspace) -> None:
        if self._owner is not None:
            raise KP1979GlyphMatchError("row match workspace provenance is already bound")
        self._owner = weakref.ref(workspace)

    def owns(self, workspace: _RowMatchWorkspace) -> bool:
        return self._owner is not None and self._owner() is workspace


@dataclass(frozen=True, slots=True, weakref_slot=True)
class _RowMatchWorkspace:
    """One immutable, index-bound cache of all distance work for one row."""

    row_id: str
    row_pbm_sha256: bytes
    region_bbox: tuple[int, int, int, int]
    boundary_contact: bool
    tight_mask: BinaryMask | None
    runs: tuple[tuple[int, int], ...]
    offset_x: int
    offset_y: int
    gap_reference_height: int
    unknown_spans: tuple[_PreparedUnknownSpan, ...]
    candidate_spans: tuple[tuple[_PreparedCandidateSpan, ...], ...]
    index: TemplateIndex = field(repr=False)
    candidate_aspect_slack_ppm: int
    top_ranks_per_span: int
    _provenance: _WorkspaceProvenance = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class _Segment:
    bbox: tuple[int, int, int, int]
    candidate: _RankCandidate | None
    source_mask: BinaryMask
    segment_cost: int
    stability: _StabilityEvidence | None = None


@dataclass(frozen=True, slots=True)
class _Path:
    total_loss: int
    segments: tuple[_Segment, ...]


def parse_canonical_pbm(raw_bytes: bytes) -> BinaryMask:
    """Parse one exact canonical raw PBM and reject ambiguous encodings."""

    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > MAX_PBM_BYTES:
        raise KP1979GlyphMatchError("PBM byte length is invalid")
    header = _PBM_HEADER.match(raw_bytes)
    if header is None:
        raise KP1979GlyphMatchError("PBM does not use the canonical raw header")
    if len(header.group(1)) > 5 or len(header.group(2)) > 5:
        raise KP1979GlyphMatchError("PBM dimension text exceeds its limit")
    width = int(header.group(1))
    height = int(header.group(2))
    if width > MAX_BITMAP_DIMENSION or height > MAX_BITMAP_DIMENSION:
        raise KP1979GlyphMatchError("PBM dimensions exceed their limit")
    row_bytes = (width + 7) // 8
    payload = raw_bytes[header.end() :]
    if len(payload) != row_bytes * height:
        raise KP1979GlyphMatchError("PBM payload byte size is invalid")
    unused_bits = row_bytes * 8 - width
    unused_mask = (1 << unused_bits) - 1
    rows: list[int] = []
    for y in range(height):
        start = y * row_bytes
        packed = int.from_bytes(payload[start : start + row_bytes], "big")
        if unused_bits and packed & unused_mask:
            raise KP1979GlyphMatchError("PBM unused low bits are not zero")
        rows.append(packed >> unused_bits)
    return BinaryMask(width, height, tuple(rows))


def build_template_index(
    template_pbms: Iterable[tuple[str, int, bytes]],
) -> TemplateIndex:
    """Build a shape-only index; each catalog rank receives one best-variant score."""

    templates: list[_Template] = []
    seen_variant_ids: set[str] = set()
    max_internal_white_runs = 0
    max_aspect_ppm = 0
    for value in template_pbms:
        if len(templates) >= MAX_TEMPLATE_COUNT:
            raise KP1979GlyphMatchError("template count exceeds its limit")
        if not isinstance(value, tuple) or len(value) != 3:
            raise KP1979GlyphMatchError("template iterator yielded an invalid item")
        variant_id, catalog_rank, pbm_bytes = value
        if not isinstance(variant_id, str) or _VARIANT_ID.fullmatch(variant_id) is None:
            raise KP1979GlyphMatchError("template variant ID is invalid")
        if variant_id in seen_variant_ids:
            raise KP1979GlyphMatchError("template variant ID is duplicated")
        if (
            not isinstance(catalog_rank, int)
            or isinstance(catalog_rank, bool)
            or not 1 <= catalog_rank <= 1_000_000
        ):
            raise KP1979GlyphMatchError("template catalog rank is invalid")
        if not isinstance(pbm_bytes, bytes):
            raise KP1979GlyphMatchError("template PBM must be bytes")
        if len(pbm_bytes) > MAX_TEMPLATE_PBM_BYTES:
            raise KP1979GlyphMatchError("template PBM byte size exceeds its limit")
        mask = parse_canonical_pbm(pbm_bytes)
        if mask.width > MAX_TEMPLATE_DIMENSION or mask.height > MAX_TEMPLATE_DIMENSION:
            raise KP1979GlyphMatchError("template PBM dimensions exceed their limit")
        tight = _tight_mask(mask)
        if tight is None:
            raise KP1979GlyphMatchError("template PBM contains no ink")
        normalized = _normalize_mask(tight)
        internal_white_runs = max(0, len(_ink_column_runs(tight)) - 1)
        if internal_white_runs >= MAX_TEMPLATE_COLUMN_RUNS:
            raise KP1979GlyphMatchError("template contains too many separated column runs")
        templates.append(
            _Template(
                variant_id=variant_id,
                catalog_rank=catalog_rank,
                source_width=tight.width,
                source_height=tight.height,
                normalized=normalized,
                dilated=_dilate(normalized),
                normalized_ink_count=normalized.ink_count,
                internal_white_runs=internal_white_runs,
            )
        )
        seen_variant_ids.add(variant_id)
        max_internal_white_runs = max(max_internal_white_runs, internal_white_runs)
        max_aspect_ppm = max(
            max_aspect_ppm,
            tight.width * SCORE_SCALE // tight.height,
        )
    if not templates:
        raise KP1979GlyphMatchError("template iterator is empty")
    if len({template.catalog_rank for template in templates}) > MAX_CATALOG_RANKS:
        raise KP1979GlyphMatchError("template catalog-rank count exceeds its limit")
    templates.sort(key=lambda item: (item.catalog_rank, item.variant_id))
    return TemplateIndex(tuple(templates), max_internal_white_runs, max_aspect_ppm)


def _prepare_row_match_workspace(
    *,
    row_id: str,
    row_pbm: bytes,
    sign_region_bbox: Sequence[int] | None,
    index: TemplateIndex,
    config: MatcherConfig,
) -> _RowMatchWorkspace:
    """Prepare one immutable, case-local cache for repeated threshold probes."""

    if not isinstance(row_id, str) or _ROW_ID.fullmatch(row_id) is None:
        raise KP1979GlyphMatchError("row ID is invalid")
    if len(row_pbm) > MAX_ROW_PBM_BYTES:
        raise KP1979GlyphMatchError("row PBM byte size exceeds its limit")
    row_mask = parse_canonical_pbm(row_pbm)
    row_pbm_sha256 = hashlib.sha256(row_pbm).digest()
    if row_mask.width > MAX_ROW_WIDTH or row_mask.height > MAX_ROW_HEIGHT:
        raise KP1979GlyphMatchError("row PBM dimensions exceed their limit")
    if sign_region_bbox is None:
        region_bbox = (0, 0, row_mask.width, row_mask.height)
    else:
        if len(sign_region_bbox) != 4 or any(
            not isinstance(value, int) or isinstance(value, bool) for value in sign_region_bbox
        ):
            raise KP1979GlyphMatchError("sign-region bbox must contain four integers")
        x0, y0, x1, y1 = sign_region_bbox
        region_bbox = (x0, y0, x1, y1)
    x0, y0, x1, y1 = region_bbox
    if not 0 <= x0 < x1 <= row_mask.width or not 0 <= y0 < y1 <= row_mask.height:
        raise KP1979GlyphMatchError("sign-region bbox lies outside the row crop")
    region = row_mask.crop(region_bbox)
    boundary_contact = _has_boundary_ink(region)
    tight_bbox = region.tight_bbox()
    if tight_bbox is None:
        workspace = _RowMatchWorkspace(
            row_id=row_id,
            row_pbm_sha256=row_pbm_sha256,
            region_bbox=region_bbox,
            boundary_contact=boundary_contact,
            tight_mask=None,
            runs=(),
            offset_x=0,
            offset_y=0,
            gap_reference_height=region.height,
            unknown_spans=(),
            candidate_spans=(),
            index=index,
            candidate_aspect_slack_ppm=config.candidate_aspect_slack_ppm,
            top_ranks_per_span=config.top_ranks_per_span,
            _provenance=_WorkspaceProvenance(),
        )
        workspace._provenance.bind(workspace)
        return workspace

    tight = region.crop(tight_bbox)
    runs = tuple(_ink_column_runs(tight))
    if len(runs) > MAX_PRIMITIVE_RUNS:
        raise KP1979GlyphMatchError("row contains too many separated column runs")
    offset_x = x0 + tight_bbox[0]
    offset_y = y0 + tight_bbox[1]
    max_span_runs = min(index.max_internal_white_runs + 3, MAX_CANDIDATE_RUN_SPAN)
    max_candidate_aspect = index.max_aspect_ppm + (
        index.max_aspect_ppm * config.candidate_aspect_slack_ppm // SCORE_SCALE
    )
    distance_cache: dict[tuple[BinaryMask, tuple[int, int]], tuple[_RankCandidate, ...]] = {}

    def cached_candidates(
        mask: BinaryMask,
        *,
        limit: int,
        normalization_offset: tuple[int, int] = (0, 0),
    ) -> tuple[_RankCandidate, ...]:
        key = (mask, normalization_offset)
        cached = distance_cache.get(key)
        if cached is None:
            cached = tuple(
                _rank_candidates(
                    mask,
                    index=index,
                    limit=config.top_ranks_per_span,
                    normalization_offset=normalization_offset,
                )
            )
            distance_cache[key] = cached
        return cached[:limit]

    unknown_spans: list[_PreparedUnknownSpan] = []
    candidate_spans: list[tuple[_PreparedCandidateSpan, ...]] = []
    for start in range(len(runs)):
        unknown_bbox = _tight_span_bbox(tight, runs[start][0], runs[start][1])
        unknown_spans.append(
            _PreparedUnknownSpan(
                bbox=_offset_bbox(unknown_bbox, offset_x, offset_y),
                source_mask=tight.crop(unknown_bbox),
            )
        )
        prepared_for_start: list[_PreparedCandidateSpan] = []
        for end in range(start + 1, min(len(runs), start + max_span_runs) + 1):
            span_bbox = _tight_span_bbox(tight, runs[start][0], runs[end - 1][1])
            span_mask = tight.crop(span_bbox)
            aspect_ppm = span_mask.width * SCORE_SCALE // span_mask.height
            if aspect_ppm > max_candidate_aspect:
                continue
            candidates = cached_candidates(span_mask, limit=config.top_ranks_per_span)
            cleaned_tight = _tight_mask(_drop_isolated_pixels(span_mask))
            cleaned_candidates = (
                () if cleaned_tight is None else cached_candidates(cleaned_tight, limit=1)
            )
            shifted_candidates = tuple(
                cached_candidates(span_mask, limit=1, normalization_offset=offset)
                for offset in _STABILITY_NORMALIZATION_OFFSETS
            )
            prepared_for_start.append(
                _PreparedCandidateSpan(
                    end=end,
                    bbox=_offset_bbox(span_bbox, offset_x, offset_y),
                    source_mask=span_mask,
                    candidates=candidates,
                    stability=_StabilityEvidence(
                        cleaned_candidates=cleaned_candidates,
                        shifted_candidates=shifted_candidates,
                    ),
                )
            )
        candidate_spans.append(tuple(prepared_for_start))
    workspace = _RowMatchWorkspace(
        row_id=row_id,
        row_pbm_sha256=row_pbm_sha256,
        region_bbox=region_bbox,
        boundary_contact=boundary_contact,
        tight_mask=tight,
        runs=runs,
        offset_x=offset_x,
        offset_y=offset_y,
        gap_reference_height=region.height,
        unknown_spans=tuple(unknown_spans),
        candidate_spans=tuple(candidate_spans),
        index=index,
        candidate_aspect_slack_ppm=config.candidate_aspect_slack_ppm,
        top_ranks_per_span=config.top_ranks_per_span,
        _provenance=_WorkspaceProvenance(),
    )
    workspace._provenance.bind(workspace)
    return workspace


def _match_row_sequence_from_workspace(
    workspace: _RowMatchWorkspace,
    *,
    index: TemplateIndex,
    config: MatcherConfig,
) -> dict[str, Any]:
    """Match one row using exact distance evidence bound to its source index."""

    if not isinstance(workspace, _RowMatchWorkspace):
        raise KP1979GlyphMatchError("row match workspace has an invalid type")
    if not workspace._provenance.owns(workspace):
        raise KP1979GlyphMatchError("row match workspace provenance is invalid")
    if workspace.index is not index:
        raise KP1979GlyphMatchError("row match workspace belongs to another template index")
    if (
        workspace.candidate_aspect_slack_ppm != config.candidate_aspect_slack_ppm
        or workspace.top_ranks_per_span != config.top_ranks_per_span
    ):
        raise KP1979GlyphMatchError("row match workspace differs from candidate configuration")
    base = {
        "row_id": workspace.row_id,
        "visual_order": "left_to_right_coordinate_order_not_reading_direction",
        "sign_region_bbox": list(workspace.region_bbox),
    }
    if workspace.tight_mask is None:
        return {
            **base,
            "proposal_status": "no_match",
            "abstention_code": "no_ink_in_sign_region",
            "candidate_paths": [],
            "gates": _gate_mapping(False, False, False, False, False),
        }
    paths = _joint_paths_from_workspace(workspace, config=config)
    return _finalize_match_result(
        base=base,
        paths=paths,
        total_row_ink=workspace.tight_mask.ink_count,
        boundary_contact=workspace.boundary_contact,
        index=index,
        config=config,
        prepared_stability=True,
    )


def match_row_sequence(
    *,
    row_id: str,
    row_pbm: bytes,
    sign_region_bbox: Sequence[int],
    index: TemplateIndex,
    config: MatcherConfig,
) -> dict[str, Any]:
    """Return up to three private shape-only candidate paths for one row crop."""

    if not isinstance(row_id, str) or _ROW_ID.fullmatch(row_id) is None:
        raise KP1979GlyphMatchError("row ID is invalid")
    if len(row_pbm) > MAX_ROW_PBM_BYTES:
        raise KP1979GlyphMatchError("row PBM byte size exceeds its limit")
    row_mask = parse_canonical_pbm(row_pbm)
    if row_mask.width > MAX_ROW_WIDTH or row_mask.height > MAX_ROW_HEIGHT:
        raise KP1979GlyphMatchError("row PBM dimensions exceed their limit")
    if len(sign_region_bbox) != 4 or any(
        not isinstance(value, int) or isinstance(value, bool) for value in sign_region_bbox
    ):
        raise KP1979GlyphMatchError("sign-region bbox must contain four integers")
    region_bbox = tuple(sign_region_bbox)
    x0, y0, x1, y1 = region_bbox
    if not 0 <= x0 < x1 <= row_mask.width or not 0 <= y0 < y1 <= row_mask.height:
        raise KP1979GlyphMatchError("sign-region bbox lies outside the row crop")
    region = row_mask.crop(region_bbox)
    boundary_contact = _has_boundary_ink(region)
    tight_bbox = region.tight_bbox()
    base = {
        "row_id": row_id,
        "visual_order": "left_to_right_coordinate_order_not_reading_direction",
        "sign_region_bbox": list(region_bbox),
    }
    if tight_bbox is None:
        return {
            **base,
            "proposal_status": "no_match",
            "abstention_code": "no_ink_in_sign_region",
            "candidate_paths": [],
            "gates": _gate_mapping(False, False, False, False, False),
        }
    tight = region.crop(tight_bbox)
    region_offset_x = x0 + tight_bbox[0]
    region_offset_y = y0 + tight_bbox[1]
    runs = _ink_column_runs(tight)
    paths = _joint_paths(
        tight,
        runs=runs,
        index=index,
        config=config,
        offset_x=region_offset_x,
        offset_y=region_offset_y,
        gap_reference_height=region.height,
    )
    return _finalize_match_result(
        base=base,
        paths=paths,
        total_row_ink=tight.ink_count,
        boundary_contact=boundary_contact,
        index=index,
        config=config,
        prepared_stability=False,
    )


def _finalize_match_result(
    *,
    base: dict[str, Any],
    paths: Sequence[_Path],
    total_row_ink: int,
    boundary_contact: bool,
    index: TemplateIndex,
    config: MatcherConfig,
    prepared_stability: bool,
) -> dict[str, Any]:
    if not paths:
        return {
            **base,
            "proposal_status": "no_match",
            "abstention_code": "no_candidate_path",
            "candidate_paths": [],
            "gates": _gate_mapping(False, False, False, False, False),
        }

    best = paths[0]
    next_margin = (
        (paths[1].total_loss - best.total_loss) // total_row_ink
        if len(paths) > 1
        else 100 * SCORE_SCALE
    )
    matched_segments = [segment for segment in best.segments if segment.candidate is not None]
    contains_unknown = len(matched_segments) != len(best.segments)
    absolute_gate = bool(matched_segments) and all(
        segment.candidate is not None and segment.candidate.emission_cost <= config.max_token_cost
        for segment in matched_segments
    )
    rank_margin_gate = bool(matched_segments) and all(
        segment.candidate is not None
        and segment.candidate.different_rank_margin >= config.min_different_rank_margin
        for segment in matched_segments
    )
    path_margin_gate = next_margin >= config.min_path_margin
    if prepared_stability:
        speck_gate, shift_gate = _stability_gates_from_evidence(best, config=config)
    else:
        speck_gate, shift_gate = _stability_gates(best, index=index, config=config)
    if contains_unknown or boundary_contact:
        proposal_status = "unknown_damage"
        abstention_code = (
            "sign_region_boundary_contains_ink"
            if boundary_contact
            else "best_path_contains_unmatched_ink"
        )
    elif not absolute_gate or not rank_margin_gate or not speck_gate or not shift_gate:
        proposal_status = "ambiguous"
        abstention_code = "shape_or_rank_stability_gate_failed"
    elif not path_margin_gate:
        if len(paths) > 1 and _segmentation_signature(paths[0]) != _segmentation_signature(
            paths[1]
        ):
            proposal_status = "segmentation_ambiguous"
            abstention_code = "joint_segmentation_path_margin_gate_failed"
        else:
            proposal_status = "ambiguous"
            abstention_code = "joint_rank_path_margin_gate_failed"
    else:
        proposal_status = "proposed"
        abstention_code = "none"

    output_paths = [
        _path_mapping(
            path,
            path_index=path_index,
            margin_from_best=(path.total_loss - best.total_loss) // total_row_ink,
            total_row_ink=total_row_ink,
        )
        for path_index, path in enumerate(paths)
    ]
    return {
        **base,
        "proposal_status": proposal_status,
        "abstention_code": abstention_code,
        "candidate_paths": output_paths,
        "gates": _gate_mapping(
            absolute_gate,
            rank_margin_gate,
            path_margin_gate,
            speck_gate,
            shift_gate,
            not boundary_contact,
        ),
    }


def _joint_paths_from_workspace(
    workspace: _RowMatchWorkspace,
    *,
    config: MatcherConfig,
) -> list[_Path]:
    mask = workspace.tight_mask
    if mask is None:
        raise KP1979GlyphMatchError("row match workspace has no ink")
    runs = workspace.runs
    paths_at: list[list[_Path]] = [[] for _ in range(len(runs) + 1)]
    paths_at[0] = [_Path(0, ())]
    total_row_ink = mask.ink_count
    for start in range(len(runs)):
        if not paths_at[start]:
            continue
        boundary_cost = _boundary_cut_cost(
            workspace.gap_reference_height,
            runs,
            start,
            config,
        )
        unknown = workspace.unknown_spans[start]
        unknown_segment = _Segment(
            unknown.bbox,
            None,
            unknown.source_mask,
            config.unknown_edge_cost,
        )
        _extend_paths(
            paths_at[start + 1],
            paths_at[start],
            segment=unknown_segment,
            edge_loss=(
                config.unknown_edge_cost * unknown.source_mask.ink_count
                + boundary_cost * total_row_ink
            ),
            keep=config.top_paths,
        )
        for prepared in workspace.candidate_spans[start]:
            for candidate in prepared.candidates:
                if candidate.emission_cost > config.max_token_cost:
                    continue
                segment = _Segment(
                    prepared.bbox,
                    candidate,
                    prepared.source_mask,
                    candidate.emission_cost,
                    prepared.stability,
                )
                _extend_paths(
                    paths_at[prepared.end],
                    paths_at[start],
                    segment=segment,
                    edge_loss=(
                        candidate.emission_cost * prepared.source_mask.ink_count
                        + boundary_cost * total_row_ink
                    ),
                    keep=config.top_paths,
                )
    distinct: dict[tuple[object, ...], _Path] = {}
    for path in sorted(paths_at[-1], key=_path_sort_key):
        key = _path_distinct_key(path)
        if key not in distinct:
            distinct[key] = path
    return sorted(distinct.values(), key=_path_sort_key)[: config.top_paths]


def _joint_paths(
    mask: BinaryMask,
    *,
    runs: Sequence[tuple[int, int]],
    index: TemplateIndex,
    config: MatcherConfig,
    offset_x: int,
    offset_y: int,
    gap_reference_height: int,
) -> list[_Path]:
    paths_at: list[list[_Path]] = [[] for _ in range(len(runs) + 1)]
    paths_at[0] = [_Path(0, ())]
    total_row_ink = mask.ink_count
    if len(runs) > MAX_PRIMITIVE_RUNS:
        raise KP1979GlyphMatchError("row contains too many separated column runs")
    max_span_runs = min(index.max_internal_white_runs + 3, MAX_CANDIDATE_RUN_SPAN)
    max_candidate_aspect = index.max_aspect_ppm + (
        index.max_aspect_ppm * config.candidate_aspect_slack_ppm // SCORE_SCALE
    )
    for start in range(len(runs)):
        if not paths_at[start]:
            continue
        boundary_cost = _boundary_cut_cost(
            gap_reference_height,
            runs,
            start,
            config,
        )
        unknown_bbox = _tight_span_bbox(mask, runs[start][0], runs[start][1])
        unknown_mask = mask.crop(unknown_bbox)
        unknown_segment = _Segment(
            _offset_bbox(unknown_bbox, offset_x, offset_y),
            None,
            unknown_mask,
            config.unknown_edge_cost,
        )
        _extend_paths(
            paths_at[start + 1],
            paths_at[start],
            segment=unknown_segment,
            edge_loss=(
                config.unknown_edge_cost * unknown_mask.ink_count + boundary_cost * total_row_ink
            ),
            keep=config.top_paths,
        )
        for end in range(start + 1, min(len(runs), start + max_span_runs) + 1):
            span_bbox = _tight_span_bbox(mask, runs[start][0], runs[end - 1][1])
            span_mask = mask.crop(span_bbox)
            aspect_ppm = span_mask.width * SCORE_SCALE // span_mask.height
            if aspect_ppm > max_candidate_aspect:
                continue
            candidates = _rank_candidates(span_mask, index=index, limit=config.top_ranks_per_span)
            for candidate in candidates:
                if candidate.emission_cost > config.max_token_cost:
                    continue
                segment = _Segment(
                    _offset_bbox(span_bbox, offset_x, offset_y),
                    candidate,
                    span_mask,
                    candidate.emission_cost,
                )
                _extend_paths(
                    paths_at[end],
                    paths_at[start],
                    segment=segment,
                    edge_loss=(
                        candidate.emission_cost * span_mask.ink_count
                        + boundary_cost * total_row_ink
                    ),
                    keep=config.top_paths,
                )
    distinct: dict[tuple[object, ...], _Path] = {}
    for path in sorted(paths_at[-1], key=_path_sort_key):
        key = _path_distinct_key(path)
        if key not in distinct:
            distinct[key] = path
    return sorted(distinct.values(), key=_path_sort_key)[: config.top_paths]


def _extend_paths(
    destination: list[_Path],
    prefixes: Sequence[_Path],
    *,
    segment: _Segment,
    edge_loss: int,
    keep: int,
) -> None:
    for prefix in prefixes:
        destination.append(_Path(prefix.total_loss + edge_loss, (*prefix.segments, segment)))
    destination.sort(key=_path_sort_key)
    distinct: dict[tuple[object, ...], _Path] = {}
    for path in destination:
        key = _path_distinct_key(path)
        if key not in distinct:
            distinct[key] = path
    destination[:] = list(distinct.values())[:keep]


def _rank_candidates(
    candidate_mask: BinaryMask,
    *,
    index: TemplateIndex,
    limit: int,
    normalization_offset: tuple[int, int] = (0, 0),
) -> list[_RankCandidate]:
    normalized = _normalize_mask(
        candidate_mask,
        offset_x=normalization_offset[0],
        offset_y=normalization_offset[1],
    )
    dilated = _dilate(normalized)
    normalized_ink_count = normalized.ink_count
    best_by_rank: dict[int, tuple[int, int, int, list[str]]] = {}
    for template in index.templates:
        overlap_cost = _symmetric_overlap_cost(
            normalized,
            dilated,
            normalized_ink_count,
            template.normalized,
            template.dilated,
            template.normalized_ink_count,
        )
        aspect_cost = _aspect_cost(
            candidate_mask.width,
            candidate_mask.height,
            template.source_width,
            template.source_height,
        )
        emission_cost = 4 * overlap_cost + aspect_cost
        previous = best_by_rank.get(template.catalog_rank)
        score = (emission_cost, overlap_cost, aspect_cost)
        if previous is None or score < previous[:3]:
            best_by_rank[template.catalog_rank] = (*score, [template.variant_id])
        elif score == previous[:3]:
            previous[3].append(template.variant_id)
    ranked = sorted(
        (
            emission,
            rank,
            tuple(sorted(variant_ids)),
            overlap,
            aspect,
        )
        for rank, (emission, overlap, aspect, variant_ids) in best_by_rank.items()
    )
    output: list[_RankCandidate] = []
    for position, (emission, rank, variant_ids, overlap, aspect) in enumerate(ranked[:limit]):
        other_emissions = [
            other[0]
            for other_index, other in enumerate(ranked)
            if other_index != position and other[1] != rank
        ]
        margin = min(other_emissions) - emission if other_emissions else 5 * SCORE_SCALE
        if any(variant_id in index.cross_rank_normalized_variant_ids for variant_id in variant_ids):
            margin = 0
        output.append(
            _RankCandidate(
                catalog_rank=rank,
                best_variant_ids=variant_ids,
                overlap_cost=overlap,
                aspect_cost=aspect,
                emission_cost=emission,
                different_rank_margin=max(0, margin),
            )
        )
    return output


def _stability_gates(
    path: _Path,
    *,
    index: TemplateIndex,
    config: MatcherConfig,
) -> tuple[bool, bool]:
    speck_stable = True
    shift_stable = True
    for segment in path.segments:
        if segment.candidate is None:
            continue
        expected_rank = segment.candidate.catalog_rank
        if config.require_speck_stability:
            cleaned = _drop_isolated_pixels(segment.source_mask)
            cleaned_tight = _tight_mask(cleaned)
            if cleaned_tight is None:
                speck_stable = False
            else:
                cleaned_candidates = _rank_candidates(cleaned_tight, index=index, limit=1)
                if not _stable_rank_candidate(
                    cleaned_candidates,
                    expected_rank=expected_rank,
                    config=config,
                ):
                    speck_stable = False
        if config.require_shift_stability:
            for offset in _STABILITY_NORMALIZATION_OFFSETS:
                shifted = _rank_candidates(
                    segment.source_mask,
                    index=index,
                    limit=1,
                    normalization_offset=offset,
                )
                if not _stable_rank_candidate(
                    shifted,
                    expected_rank=expected_rank,
                    config=config,
                ):
                    shift_stable = False
                    break
    return speck_stable, shift_stable


def _stability_gates_from_evidence(
    path: _Path,
    *,
    config: MatcherConfig,
) -> tuple[bool, bool]:
    speck_stable = True
    shift_stable = True
    for segment in path.segments:
        if segment.candidate is None:
            continue
        if segment.stability is None:
            raise KP1979GlyphMatchError("matched segment lacks prepared stability evidence")
        expected_rank = segment.candidate.catalog_rank
        if config.require_speck_stability and not _stable_rank_candidate(
            segment.stability.cleaned_candidates,
            expected_rank=expected_rank,
            config=config,
        ):
            speck_stable = False
        if config.require_shift_stability:
            for shifted in segment.stability.shifted_candidates:
                if not _stable_rank_candidate(
                    shifted,
                    expected_rank=expected_rank,
                    config=config,
                ):
                    shift_stable = False
                    break
    return speck_stable, shift_stable


def _path_mapping(
    path: _Path,
    *,
    path_index: int,
    margin_from_best: int,
    total_row_ink: int,
) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    for segment in path.segments:
        if segment.candidate is None:
            segments.append(
                {
                    "segment_kind": "unmatched_ink",
                    "segment_bbox": list(segment.bbox),
                    "unknown_cost": segment.segment_cost,
                }
            )
            continue
        candidate = segment.candidate
        segments.append(
            {
                "segment_kind": "rank_proposal",
                "segment_bbox": list(segment.bbox),
                "catalog_rank": candidate.catalog_rank,
                "best_variant_ids": list(candidate.best_variant_ids),
                "overlap_cost": candidate.overlap_cost,
                "aspect_cost": candidate.aspect_cost,
                "emission_cost": candidate.emission_cost,
                "different_rank_margin": candidate.different_rank_margin,
            }
        )
    return {
        "path_index": path_index,
        "total_cost": path.total_loss // total_row_ink,
        "margin_from_best": margin_from_best,
        "segments": segments,
    }


def _gate_mapping(
    absolute: bool,
    rank_margin: bool,
    path_margin: bool,
    speck: bool,
    shift: bool,
    boundary_clear: bool = True,
) -> dict[str, bool]:
    return {
        "absolute_shape_cost_passed": absolute,
        "different_rank_margin_passed": rank_margin,
        "joint_path_margin_passed": path_margin,
        "speck_ablation_stability_passed": speck,
        "normalization_shift_stability_passed": shift,
        "sign_region_boundary_clear": boundary_clear,
    }


def _normalize_mask(
    mask: BinaryMask,
    *,
    offset_x: int = 0,
    offset_y: int = 0,
) -> BinaryMask:
    tight = _tight_mask(mask)
    if tight is None:
        raise KP1979GlyphMatchError("cannot normalize an empty mask")
    inner = NORMALIZED_CANVAS_SIZE - 2 * NORMALIZED_PADDING
    if tight.width >= tight.height:
        target_width = inner
        target_height = max(1, (tight.height * inner + tight.width // 2) // tight.width)
    else:
        target_height = inner
        target_width = max(1, (tight.width * inner + tight.height // 2) // tight.height)
    origin_x = (NORMALIZED_CANVAS_SIZE - target_width) // 2 + offset_x
    origin_y = (NORMALIZED_CANVAS_SIZE - target_height) // 2 + offset_y
    if origin_x < 0 or origin_x + target_width > NORMALIZED_CANVAS_SIZE:
        raise KP1979GlyphMatchError("normalization x offset leaves the fixed canvas")
    if origin_y < 0 or origin_y + target_height > NORMALIZED_CANVAS_SIZE:
        raise KP1979GlyphMatchError("normalization y offset leaves the fixed canvas")
    output_rows = [0] * NORMALIZED_CANVAS_SIZE
    for source_y, source_row in enumerate(tight.rows):
        if not source_row:
            continue
        dy0 = origin_y + source_y * target_height // tight.height
        dy1 = origin_y + ((source_y + 1) * target_height + tight.height - 1) // tight.height
        dy1 = max(dy0 + 1, dy1)
        for source_x in range(tight.width):
            source_bit = 1 << (tight.width - 1 - source_x)
            if not source_row & source_bit:
                continue
            dx0 = origin_x + source_x * target_width // tight.width
            dx1 = origin_x + (((source_x + 1) * target_width + tight.width - 1) // tight.width)
            dx1 = max(dx0 + 1, dx1)
            destination_bits = ((1 << (dx1 - dx0)) - 1) << (NORMALIZED_CANVAS_SIZE - dx1)
            for destination_y in range(dy0, dy1):
                output_rows[destination_y] |= destination_bits
    return BinaryMask(
        NORMALIZED_CANVAS_SIZE,
        NORMALIZED_CANVAS_SIZE,
        tuple(output_rows),
    )


def _dilate(mask: BinaryMask) -> BinaryMask:
    bit_limit = (1 << mask.width) - 1
    horizontal = tuple((row | (row << 1) | (row >> 1)) & bit_limit for row in mask.rows)
    output: list[int] = []
    for y, row in enumerate(horizontal):
        value = row
        if y:
            value |= horizontal[y - 1]
        if y + 1 < mask.height:
            value |= horizontal[y + 1]
        output.append(value & bit_limit)
    return BinaryMask(mask.width, mask.height, tuple(output))


def _symmetric_overlap_cost(
    candidate: BinaryMask,
    candidate_dilated: BinaryMask,
    candidate_ink: int,
    template: BinaryMask,
    template_dilated: BinaryMask,
    template_ink: int,
) -> int:
    if not candidate_ink or not template_ink:
        return SCORE_SCALE
    candidate_covered = sum(
        (candidate_row & template_row).bit_count()
        for candidate_row, template_row in zip(
            candidate.rows,
            template_dilated.rows,
            strict=True,
        )
    )
    template_covered = sum(
        (template_row & candidate_row).bit_count()
        for template_row, candidate_row in zip(
            template.rows,
            candidate_dilated.rows,
            strict=True,
        )
    )
    similarity = (
        candidate_covered * SCORE_SCALE // candidate_ink
        + template_covered * SCORE_SCALE // template_ink
    ) // 2
    return SCORE_SCALE - similarity


def _aspect_cost(
    candidate_width: int,
    candidate_height: int,
    template_width: int,
    template_height: int,
) -> int:
    left = candidate_width * template_height
    right = template_width * candidate_height
    return abs(left - right) * SCORE_SCALE // max(left, right)


def _tight_mask(mask: BinaryMask) -> BinaryMask | None:
    bbox = mask.tight_bbox()
    return None if bbox is None else mask.crop(bbox)


def _ink_column_runs(mask: BinaryMask) -> list[tuple[int, int]]:
    columns = [False] * mask.width
    for row in mask.rows:
        value = row
        while value:
            bit = value.bit_length() - 1
            columns[mask.width - 1 - bit] = True
            value ^= 1 << bit
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x, has_ink in enumerate(columns):
        if has_ink and start is None:
            start = x
        elif not has_ink and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, mask.width))
    return runs


def _tight_span_bbox(mask: BinaryMask, x0: int, x1: int) -> tuple[int, int, int, int]:
    span = mask.crop((x0, 0, x1, mask.height))
    tight = span.tight_bbox()
    if tight is None:
        raise KP1979GlyphMatchError("ink span unexpectedly contains no ink")
    _, y0, _, y1 = tight
    return x0, y0, x1, y1


def _boundary_cut_cost(
    reference_height: int,
    runs: Sequence[tuple[int, int]],
    start: int,
    config: MatcherConfig,
) -> int:
    if start == 0:
        return 0
    gap_width = runs[start][0] - runs[start - 1][1]
    gap_ppm = gap_width * SCORE_SCALE // max(1, reference_height)
    if gap_ppm >= config.cut_gap_support_ppm or config.cut_gap_support_ppm == 0:
        return 0
    return (
        (config.cut_gap_support_ppm - gap_ppm)
        * config.max_cut_penalty
        // config.cut_gap_support_ppm
    )


def _drop_isolated_pixels(mask: BinaryMask) -> BinaryMask:
    bit_limit = (1 << mask.width) - 1
    rows: list[int] = []
    for y, row in enumerate(mask.rows):
        neighbors = ((row << 1) | (row >> 1)) & bit_limit
        if y:
            above = mask.rows[y - 1]
            neighbors |= above | (above << 1) | (above >> 1)
        if y + 1 < mask.height:
            below = mask.rows[y + 1]
            neighbors |= below | (below << 1) | (below >> 1)
        rows.append(row & neighbors & bit_limit)
    return BinaryMask(mask.width, mask.height, tuple(rows))


def _offset_bbox(
    bbox: tuple[int, int, int, int],
    offset_x: int,
    offset_y: int,
) -> tuple[int, int, int, int]:
    return (
        bbox[0] + offset_x,
        bbox[1] + offset_y,
        bbox[2] + offset_x,
        bbox[3] + offset_y,
    )


def _path_distinct_key(path: _Path) -> tuple[object, ...]:
    return tuple(
        (
            segment.candidate.catalog_rank if segment.candidate is not None else None,
            segment.bbox,
        )
        for segment in path.segments
    )


def _path_sort_key(path: _Path) -> tuple[object, ...]:
    return (
        path.total_loss,
        len(path.segments),
        tuple(
            (
                segment.candidate.catalog_rank if segment.candidate is not None else 1_000_001,
                segment.candidate.best_variant_ids
                if segment.candidate is not None
                else ("~unknown",),
                segment.bbox,
            )
            for segment in path.segments
        ),
    )


def _has_boundary_ink(mask: BinaryMask) -> bool:
    edge_bits = (1 << (mask.width - 1)) | 1
    return bool(mask.rows[0] or mask.rows[-1] or any(row & edge_bits for row in mask.rows))


def _stable_rank_candidate(
    candidates: Sequence[_RankCandidate],
    *,
    expected_rank: int,
    config: MatcherConfig,
) -> bool:
    if not candidates:
        return False
    candidate = candidates[0]
    return (
        candidate.catalog_rank == expected_rank
        and candidate.emission_cost <= config.max_token_cost
        and candidate.different_rank_margin >= config.min_different_rank_margin
    )


def _segmentation_signature(path: _Path) -> tuple[tuple[int, int, int, int], ...]:
    return tuple(segment.bbox for segment in path.segments)
