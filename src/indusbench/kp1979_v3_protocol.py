"""Closed, answer-free protocol spine for the KP1979 V3 synthetic control.

This module freezes identifiers, geometry, the ordered case taxonomy,
metamorphic relations, invocation accounting, and the scientific claim
boundary.  It deliberately contains no fixture generator, generator-known
reference, random-beacon material, detector implementation, or evaluator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class KP1979V3ProtocolError(ValueError):
    """Raised when the closed V3 protocol contract is invalid."""


class CaseCategory(StrEnum):
    """Closed synthetic-case taxonomy."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    OUT_OF_CONTRACT = "out_of_contract"


class InputErrorCode(StrEnum):
    """Closed worker rejection codes for malformed synthetic inputs."""

    INVALID_PBM_PAYLOAD_SIZE = "invalid_pbm_payload_size"
    INVALID_PBM_HEADER = "invalid_pbm_header"
    INVALID_DIMENSIONS = "invalid_dimensions"
    INVALID_SCAN_BANDS = "invalid_scan_bands"


class MetamorphicKind(StrEnum):
    """Closed set of predeclared two-endpoint relations."""

    IDENTICAL = "identical"
    UNREAD_MARGIN = "unread-margin"
    VERTICAL_PLUS_11 = "vertical-plus-11"
    HORIZONTAL_TRANSLATION = "horizontal-translation"
    STROKE_WIDTH = "stroke-width"
    RENDERER_SUBSTITUTION = "renderer-substitution"
    LANE_SWAP = "lane-swap"
    GAP_DELETION = "gap-deletion"


class AuthorizationCondition(StrEnum):
    """The sole condition under which the provisional-use grant applies."""

    C3_PASS = "c3-pass"


class AuthorizedUse(StrEnum):
    """The sole downstream use a C3 pass may authorize."""

    OWNER_ONLY_PROVISIONAL_CANDIDATES = "owner-only-provisional-candidates"


class ClaimName(StrEnum):
    """Public claims that remain false regardless of a C3 pass."""

    PAGE_78 = "page_78"
    ACCURACY = "accuracy"
    IDENTIFIER = "identifier"
    SEQUENCE = "sequence"
    LANGUAGE = "language"
    MEANING = "meaning"
    TRANSLATION = "translation"
    DECIPHERMENT = "decipherment"
    PRIZE = "prize"
    CORPUS_CLAIM = "corpus_claim"


_LOWER_KEBAB_RE: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)


def _require_exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise KP1979V3ProtocolError(f"{name} must be an integer and not a boolean")
    assert isinstance(value, int)
    if value < minimum:
        raise KP1979V3ProtocolError(f"{name} is below its closed minimum")
    return value


def _require_lower_kebab(name: str, value: object) -> str:
    if type(value) is not str:
        raise KP1979V3ProtocolError(f"{name} must be a string")
    assert isinstance(value, str)
    if not value.isascii() or _LOWER_KEBAB_RE.fullmatch(value) is None:
        raise KP1979V3ProtocolError(f"{name} must be ASCII lower-kebab")
    return value


def _require_exact_enum(name: str, value: object, enum_type: type[StrEnum]) -> None:
    if type(value) is not enum_type:
        raise KP1979V3ProtocolError(f"{name} must use the closed {enum_type.__name__} enum")


@dataclass(frozen=True, slots=True)
class RawP4Contract:
    """Exact raw-P4 dimensions, byte framing, and answer-free scan bands."""

    width: int
    height: int
    row_bytes: int
    header: bytes
    payload_byte_size: int
    pbm_byte_size: int
    scan_bands: tuple[tuple[int, int, int, int], ...]

    def __post_init__(self) -> None:
        width = _require_exact_int("width", self.width, minimum=1)
        height = _require_exact_int("height", self.height, minimum=1)
        row_bytes = _require_exact_int("row_bytes", self.row_bytes, minimum=1)
        payload_size = _require_exact_int(
            "payload_byte_size",
            self.payload_byte_size,
            minimum=1,
        )
        pbm_size = _require_exact_int("pbm_byte_size", self.pbm_byte_size, minimum=1)
        if type(self.header) is not bytes:
            raise KP1979V3ProtocolError("header must be exact bytes")
        if type(self.scan_bands) is not tuple or len(self.scan_bands) != 2:
            raise KP1979V3ProtocolError("scan_bands must be an exact two-item tuple")
        if width % 8 != 0 or row_bytes != width // 8:
            raise KP1979V3ProtocolError("raw P4 row-byte geometry is inconsistent")
        canonical_header = f"P4\n{width} {height}\n".encode("ascii")
        if self.header != canonical_header:
            raise KP1979V3ProtocolError("raw P4 header is not canonical")
        if payload_size != row_bytes * height:
            raise KP1979V3ProtocolError("raw P4 payload size is inconsistent")
        if pbm_size != len(self.header) + payload_size:
            raise KP1979V3ProtocolError("raw P4 total byte size is inconsistent")

        previous_x1: int | None = None
        for index, band in enumerate(self.scan_bands):
            if type(band) is not tuple or len(band) != 4:
                raise KP1979V3ProtocolError("each scan band must be an exact four-item tuple")
            x0, y0, x1, y1 = (
                _require_exact_int(f"scan_bands[{index}][{coordinate}]", value)
                for coordinate, value in enumerate(band)
            )
            if not (x0 < x1 <= width and y0 < y1 <= height):
                raise KP1979V3ProtocolError("scan band is outside the raw P4 geometry")
            if previous_x1 is not None and x0 < previous_x1:
                raise KP1979V3ProtocolError("scan bands must not overlap")
            previous_x1 = x1


@dataclass(frozen=True, slots=True)
class CaseSpec:
    """One ordered case identity without pixels, truth, or generation logic."""

    case_id: str
    category: CaseCategory
    expected_error_code: InputErrorCode | None

    def __post_init__(self) -> None:
        _require_lower_kebab("case_id", self.case_id)
        _require_exact_enum("category", self.category, CaseCategory)
        if self.category is CaseCategory.OUT_OF_CONTRACT:
            _require_exact_enum(
                "expected_error_code",
                self.expected_error_code,
                InputErrorCode,
            )
        elif self.expected_error_code is not None:
            raise KP1979V3ProtocolError(
                "only out-of-contract cases may declare an expected error code"
            )


@dataclass(frozen=True, slots=True)
class MetamorphicRelationSpec:
    """One ordered relation identity and its fixed endpoint accounting."""

    relation_id: str
    kind: MetamorphicKind
    endpoint_invocations: int
    vertical_delta: int | None

    def __post_init__(self) -> None:
        _require_lower_kebab("relation_id", self.relation_id)
        _require_exact_enum("kind", self.kind, MetamorphicKind)
        invocations = _require_exact_int(
            "endpoint_invocations",
            self.endpoint_invocations,
            minimum=1,
        )
        if invocations != 2:
            raise KP1979V3ProtocolError(
                "every metamorphic relation must invoke both endpoints exactly once"
            )
        if self.kind is MetamorphicKind.VERTICAL_PLUS_11:
            if type(self.vertical_delta) is not int or self.vertical_delta != 11:
                raise KP1979V3ProtocolError("vertical-plus-11 must declare delta 11")
        elif self.vertical_delta is not None:
            raise KP1979V3ProtocolError("only vertical-plus-11 may declare a vertical delta")


@dataclass(frozen=True, slots=True)
class ClaimPermission:
    """One immutable public-claim permission, which is always false."""

    claim: ClaimName
    allowed: bool

    def __post_init__(self) -> None:
        _require_exact_enum("claim", self.claim, ClaimName)
        if type(self.allowed) is not bool:
            raise KP1979V3ProtocolError("claim permission must be an exact boolean")
        if self.allowed is not False:
            raise KP1979V3ProtocolError("the V3 control cannot authorize a public claim")


@dataclass(frozen=True, slots=True)
class C3PassAuthorization:
    """Narrow conditional authorization created by a future C3 pass."""

    condition: AuthorizationCondition
    authorized_use: AuthorizedUse
    first_page: int
    last_page: int
    owner_only: bool
    provisional_candidates_only: bool
    page_78_allowed: bool

    def __post_init__(self) -> None:
        _require_exact_enum("condition", self.condition, AuthorizationCondition)
        _require_exact_enum("authorized_use", self.authorized_use, AuthorizedUse)
        first_page = _require_exact_int("first_page", self.first_page, minimum=1)
        last_page = _require_exact_int("last_page", self.last_page, minimum=1)
        for name, value in (
            ("owner_only", self.owner_only),
            ("provisional_candidates_only", self.provisional_candidates_only),
            ("page_78_allowed", self.page_78_allowed),
        ):
            if type(value) is not bool:
                raise KP1979V3ProtocolError(f"{name} must be an exact boolean")
        if self.condition is not AuthorizationCondition.C3_PASS:
            raise KP1979V3ProtocolError("the authorization condition must be c3-pass")
        if self.authorized_use is not AuthorizedUse.OWNER_ONLY_PROVISIONAL_CANDIDATES:
            raise KP1979V3ProtocolError("the authorized use exceeds the closed boundary")
        if (first_page, last_page) != (22, 77):
            raise KP1979V3ProtocolError("the provisional page interval must be 22 through 77")
        if self.owner_only is not True or self.provisional_candidates_only is not True:
            raise KP1979V3ProtocolError("C3 may authorize only owner-only provisional candidates")
        if self.page_78_allowed is not False:
            raise KP1979V3ProtocolError("page 78 is outside the C3 authorization")


@dataclass(frozen=True, slots=True)
class KP1979V3Protocol:
    """Complete immutable protocol spine, still without an executable control."""

    control_id: str
    target_algorithm_id: str
    worker_id: str
    raw_p4: RawP4Contract
    intended_prediction_height: int
    maximum_prediction_height: int
    maximum_predictions_per_invocation: int
    true_reference_half_height: int
    cases: tuple[CaseSpec, ...]
    metamorphic_relations: tuple[MetamorphicRelationSpec, ...]
    case_invocations: int
    metamorphic_endpoint_invocations: int
    total_worker_invocations: int
    c3_pass_authorization: C3PassAuthorization
    public_claim_permissions: tuple[ClaimPermission, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("control_id", self.control_id),
            ("target_algorithm_id", self.target_algorithm_id),
            ("worker_id", self.worker_id),
        ):
            _require_lower_kebab(name, value)
        if type(self.raw_p4) is not RawP4Contract:
            raise KP1979V3ProtocolError("raw_p4 must use the closed RawP4Contract")
        for name, value in (
            ("intended_prediction_height", self.intended_prediction_height),
            ("maximum_prediction_height", self.maximum_prediction_height),
            (
                "maximum_predictions_per_invocation",
                self.maximum_predictions_per_invocation,
            ),
            ("true_reference_half_height", self.true_reference_half_height),
            ("case_invocations", self.case_invocations),
            (
                "metamorphic_endpoint_invocations",
                self.metamorphic_endpoint_invocations,
            ),
            ("total_worker_invocations", self.total_worker_invocations),
        ):
            _require_exact_int(name, value, minimum=1)
        if type(self.cases) is not tuple or any(
            type(value) is not CaseSpec for value in self.cases
        ):
            raise KP1979V3ProtocolError("cases must be an exact tuple of CaseSpec values")
        if type(self.metamorphic_relations) is not tuple or any(
            type(value) is not MetamorphicRelationSpec for value in self.metamorphic_relations
        ):
            raise KP1979V3ProtocolError(
                "metamorphic_relations must be an exact tuple of MetamorphicRelationSpec values"
            )
        if type(self.c3_pass_authorization) is not C3PassAuthorization:
            raise KP1979V3ProtocolError(
                "c3_pass_authorization must use the closed C3PassAuthorization"
            )
        if type(self.public_claim_permissions) is not tuple or any(
            type(value) is not ClaimPermission for value in self.public_claim_permissions
        ):
            raise KP1979V3ProtocolError(
                "public_claim_permissions must be an exact tuple of ClaimPermission values"
            )


CONTROL_ID: Final = "kp1979-label-lattice-synthetic-control-v3"
TARGET_ALGORITHM_ID: Final = "two-column-glyph-lattice-v3"
WORKER_ID: Final = "kp1979-label-detector-v3-worker-v1"

SYNTHETIC_PAGE_WIDTH: Final = 4880
SYNTHETIC_PAGE_HEIGHT: Final = 7010
SYNTHETIC_ROW_BYTES: Final = 610
SYNTHETIC_PBM_HEADER: Final = b"P4\n4880 7010\n"
SYNTHETIC_PBM_PAYLOAD_BYTE_SIZE: Final = 4_276_100
SYNTHETIC_PBM_BYTE_SIZE: Final = 4_276_113
SYNTHETIC_SCAN_BANDS: Final = (
    (2056, 550, 2316, 6600),
    (4232, 550, 4492, 6600),
)

INTENDED_PREDICTION_HEIGHT: Final = 96
MAXIMUM_PREDICTION_HEIGHT: Final = 128
MAXIMUM_PREDICTIONS_PER_INVOCATION: Final = 128
TRUE_REFERENCE_HALF_HEIGHT: Final = 28

POSITIVE_CASE_IDS: Final = (
    "positive-renderer-a-clean",
    "positive-renderer-b-clean",
    "positive-renderer-a-pitch-158",
    "positive-renderer-b-pitch-172",
    "positive-mixed-asymmetric",
    "positive-gaps-jitter",
    "positive-double-gaps",
    "positive-unequal-partial-lanes",
    "positive-bounded-damage",
    "positive-stroke-qualifier",
    "positive-horizontal-offsets",
    "positive-sparse-distractors",
)

NEGATIVE_CASE_IDS: Final = (
    "negative-blank",
    "negative-single-lane",
    "negative-cross-lane-pitch-conflict",
    "negative-periodic-single-tier",
    "negative-periodic-two-tier-paired-segments",
    "negative-periodic-paired-dashes",
    "negative-ruled-form",
    "negative-table-grid",
    "negative-repeated-boxes",
    "negative-decorative-border",
    "negative-repeated-stamp",
    "negative-dense-multicolumn",
    "negative-mixed-label-confound",
    "negative-staggered-single-tiers",
)

OUT_OF_CONTRACT_CASE_ERRORS: Final = (
    (
        "out-of-contract-truncated-payload",
        InputErrorCode.INVALID_PBM_PAYLOAD_SIZE,
    ),
    (
        "out-of-contract-extended-payload",
        InputErrorCode.INVALID_PBM_PAYLOAD_SIZE,
    ),
    (
        "out-of-contract-noncanonical-header",
        InputErrorCode.INVALID_PBM_HEADER,
    ),
    (
        "out-of-contract-dimension-mismatch",
        InputErrorCode.INVALID_DIMENSIONS,
    ),
    (
        "out-of-contract-wrong-scan-extent",
        InputErrorCode.INVALID_SCAN_BANDS,
    ),
    (
        "out-of-contract-overlapping-scan-bands",
        InputErrorCode.INVALID_SCAN_BANDS,
    ),
)

EXPECTED_CASE_IDS: Final = (
    *POSITIVE_CASE_IDS,
    *NEGATIVE_CASE_IDS,
    *(case_id for case_id, _ in OUT_OF_CONTRACT_CASE_ERRORS),
)

CASE_ROSTER: Final = (
    *(CaseSpec(case_id, CaseCategory.POSITIVE, None) for case_id in POSITIVE_CASE_IDS),
    *(CaseSpec(case_id, CaseCategory.NEGATIVE, None) for case_id in NEGATIVE_CASE_IDS),
    *(
        CaseSpec(case_id, CaseCategory.OUT_OF_CONTRACT, error_code)
        for case_id, error_code in OUT_OF_CONTRACT_CASE_ERRORS
    ),
)

EXPECTED_METAMORPHIC_RELATIONS: Final = (
    ("identical", MetamorphicKind.IDENTICAL, None),
    ("unread-margin", MetamorphicKind.UNREAD_MARGIN, None),
    ("vertical-plus-11", MetamorphicKind.VERTICAL_PLUS_11, 11),
    ("horizontal-translation", MetamorphicKind.HORIZONTAL_TRANSLATION, None),
    ("stroke-width", MetamorphicKind.STROKE_WIDTH, None),
    ("renderer-substitution", MetamorphicKind.RENDERER_SUBSTITUTION, None),
    ("lane-swap", MetamorphicKind.LANE_SWAP, None),
    ("gap-deletion", MetamorphicKind.GAP_DELETION, None),
)

METAMORPHIC_RELATIONS: Final = tuple(
    MetamorphicRelationSpec(
        relation_id=relation_id,
        kind=kind,
        endpoint_invocations=2,
        vertical_delta=vertical_delta,
    )
    for relation_id, kind, vertical_delta in EXPECTED_METAMORPHIC_RELATIONS
)

PUBLIC_CLAIM_PERMISSIONS: Final = tuple(
    ClaimPermission(claim=claim, allowed=False) for claim in ClaimName
)
PUBLIC_CLAIM_BOUNDARY: Final = MappingProxyType(
    {permission.claim.value: permission.allowed for permission in PUBLIC_CLAIM_PERMISSIONS}
)

RAW_P4_CONTRACT: Final = RawP4Contract(
    width=SYNTHETIC_PAGE_WIDTH,
    height=SYNTHETIC_PAGE_HEIGHT,
    row_bytes=SYNTHETIC_ROW_BYTES,
    header=SYNTHETIC_PBM_HEADER,
    payload_byte_size=SYNTHETIC_PBM_PAYLOAD_BYTE_SIZE,
    pbm_byte_size=SYNTHETIC_PBM_BYTE_SIZE,
    scan_bands=SYNTHETIC_SCAN_BANDS,
)

C3_PASS_AUTHORIZATION: Final = C3PassAuthorization(
    condition=AuthorizationCondition.C3_PASS,
    authorized_use=AuthorizedUse.OWNER_ONLY_PROVISIONAL_CANDIDATES,
    first_page=22,
    last_page=77,
    owner_only=True,
    provisional_candidates_only=True,
    page_78_allowed=False,
)

CASE_INVOCATIONS: Final = len(CASE_ROSTER)
METAMORPHIC_ENDPOINT_INVOCATIONS: Final = sum(
    relation.endpoint_invocations for relation in METAMORPHIC_RELATIONS
)
TOTAL_WORKER_INVOCATIONS: Final = CASE_INVOCATIONS + METAMORPHIC_ENDPOINT_INVOCATIONS


def validate_protocol(protocol: KP1979V3Protocol) -> None:
    """Fail closed unless *protocol* is exactly the frozen public contract."""

    if type(protocol) is not KP1979V3Protocol:
        raise KP1979V3ProtocolError("protocol must use the closed KP1979V3Protocol")
    if (
        protocol.control_id,
        protocol.target_algorithm_id,
        protocol.worker_id,
    ) != (CONTROL_ID, TARGET_ALGORITHM_ID, WORKER_ID):
        raise KP1979V3ProtocolError("protocol identifiers differ from the frozen values")
    if protocol.raw_p4 != RAW_P4_CONTRACT:
        raise KP1979V3ProtocolError("raw P4 contract differs from the frozen geometry")
    if (
        protocol.intended_prediction_height,
        protocol.maximum_prediction_height,
        protocol.maximum_predictions_per_invocation,
        protocol.true_reference_half_height,
    ) != (
        INTENDED_PREDICTION_HEIGHT,
        MAXIMUM_PREDICTION_HEIGHT,
        MAXIMUM_PREDICTIONS_PER_INVOCATION,
        TRUE_REFERENCE_HALF_HEIGHT,
    ):
        raise KP1979V3ProtocolError("prediction or reference bounds differ from the freeze")

    case_ids = tuple(case.case_id for case in protocol.cases)
    if case_ids != EXPECTED_CASE_IDS:
        raise KP1979V3ProtocolError("case roster count or order differs from the freeze")
    expected_categories = (
        *((case_id, CaseCategory.POSITIVE, None) for case_id in POSITIVE_CASE_IDS),
        *((case_id, CaseCategory.NEGATIVE, None) for case_id in NEGATIVE_CASE_IDS),
        *(
            (case_id, CaseCategory.OUT_OF_CONTRACT, error_code)
            for case_id, error_code in OUT_OF_CONTRACT_CASE_ERRORS
        ),
    )
    actual_categories = tuple(
        (case.case_id, case.category, case.expected_error_code) for case in protocol.cases
    )
    if actual_categories != expected_categories:
        raise KP1979V3ProtocolError("case taxonomy or error-code mapping differs from the freeze")

    relation_values = tuple(
        (relation.relation_id, relation.kind, relation.vertical_delta)
        for relation in protocol.metamorphic_relations
    )
    if relation_values != EXPECTED_METAMORPHIC_RELATIONS:
        raise KP1979V3ProtocolError("metamorphic roster count or order differs from the freeze")
    all_ids = case_ids + tuple(relation.relation_id for relation in protocol.metamorphic_relations)
    if len(all_ids) != len(set(all_ids)):
        raise KP1979V3ProtocolError("case and relation identifiers must be globally unique")
    if any(not value.isascii() or _LOWER_KEBAB_RE.fullmatch(value) is None for value in all_ids):
        raise KP1979V3ProtocolError("case and relation identifiers must be ASCII lower-kebab")

    case_invocations = len(protocol.cases)
    metamorphic_invocations = sum(
        relation.endpoint_invocations for relation in protocol.metamorphic_relations
    )
    total_invocations = case_invocations + metamorphic_invocations
    if (
        protocol.case_invocations,
        protocol.metamorphic_endpoint_invocations,
        protocol.total_worker_invocations,
    ) != (case_invocations, metamorphic_invocations, total_invocations):
        raise KP1979V3ProtocolError("worker invocation accounting is inconsistent")
    if (case_invocations, metamorphic_invocations, total_invocations) != (32, 16, 48):
        raise KP1979V3ProtocolError("worker invocation accounting differs from the freeze")

    if protocol.c3_pass_authorization != C3_PASS_AUTHORIZATION:
        raise KP1979V3ProtocolError("C3 pass authorization differs from the closed boundary")
    if protocol.public_claim_permissions != PUBLIC_CLAIM_PERMISSIONS:
        raise KP1979V3ProtocolError("public claim boundary differs from the closed false tuple")
    claims = tuple(permission.claim for permission in protocol.public_claim_permissions)
    if claims != tuple(ClaimName) or len(claims) != len(set(claims)):
        raise KP1979V3ProtocolError("public claim names are missing, duplicated, or reordered")
    if any(permission.allowed is not False for permission in protocol.public_claim_permissions):
        raise KP1979V3ProtocolError("every public claim permission must remain false")


V3_PROTOCOL: Final = KP1979V3Protocol(
    control_id=CONTROL_ID,
    target_algorithm_id=TARGET_ALGORITHM_ID,
    worker_id=WORKER_ID,
    raw_p4=RAW_P4_CONTRACT,
    intended_prediction_height=INTENDED_PREDICTION_HEIGHT,
    maximum_prediction_height=MAXIMUM_PREDICTION_HEIGHT,
    maximum_predictions_per_invocation=MAXIMUM_PREDICTIONS_PER_INVOCATION,
    true_reference_half_height=TRUE_REFERENCE_HALF_HEIGHT,
    cases=CASE_ROSTER,
    metamorphic_relations=METAMORPHIC_RELATIONS,
    case_invocations=CASE_INVOCATIONS,
    metamorphic_endpoint_invocations=METAMORPHIC_ENDPOINT_INVOCATIONS,
    total_worker_invocations=TOTAL_WORKER_INVOCATIONS,
    c3_pass_authorization=C3_PASS_AUTHORIZATION,
    public_claim_permissions=PUBLIC_CLAIM_PERMISSIONS,
)

validate_protocol(V3_PROTOCOL)
