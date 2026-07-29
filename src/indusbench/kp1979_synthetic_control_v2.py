"""Pre-result, source-independent synthetic-control freeze for KP1979 V2.

This module deliberately has no dependency on a V2 detector implementation.
The adapter boundary exposes only exact PBM bytes, dimensions, and scan bands.
Generator truth, case identity, case class, and the case roster remain on the
control side of that boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Final, Literal, Protocol, TypeAlias

from indusbench.kp1979_label_scoring import (
    LabelPrediction,
    LabelReferenceInterval,
    _score_label_positions,
)

CONTROL_ID: Final = "kp1979-label-lattice-synthetic-control-v2"
TARGET_ALGORITHM_ID: Final = "two-column-label-lattice-v2"
FREEZE_VERSION: Final = 1
FREEZE_RESULT_STATE: Final[Literal["not_run"]] = "not_run"
FREEZE_MANIFEST_PATH: Final = "benchmark/kp1979-label-lattice-synthetic-control-v2.json"
FREEZE_MANIFEST_BYTE_SIZE: Final = 11_807
FREEZE_MANIFEST_SHA256: Final = "ee368613138f2ccb89686872ff127504f0627b2df662edef3b5a0486583f870f"

SYNTHETIC_PAGE_WIDTH: Final = 4880
SYNTHETIC_PAGE_HEIGHT: Final = 7010
SYNTHETIC_ROW_BYTES: Final = 610
SYNTHETIC_PBM_HEADER: Final = b"P4\n4880 7010\n"
SYNTHETIC_PBM_BYTE_SIZE: Final = 4_276_113
SYNTHETIC_SCAN_TOP: Final = 550
SYNTHETIC_SCAN_BOTTOM: Final = 6600
SYNTHETIC_SCAN_BANDS: Final = (
    (2056, SYNTHETIC_SCAN_TOP, 2316, SYNTHETIC_SCAN_BOTTOM),
    (4232, SYNTHETIC_SCAN_TOP, 4492, SYNTHETIC_SCAN_BOTTOM),
)
SYNTHETIC_PAGE_NUMBER_BASE: Final = 9000
SYNTHETIC_PREDICTION_HEIGHT: Final = 96

MAX_SYNTHETIC_CASES: Final = 32
MAX_METAMORPHIC_RELATIONS: Final = 8
MAX_PBM_BYTES: Final = SYNTHETIC_PBM_BYTE_SIZE + 32
MAX_SCAN_BANDS: Final = 2
MAX_REFERENCES_PER_FIXTURE: Final = 128
MAX_PREDICTIONS_PER_PROPOSAL: Final = 128

CaseClass = Literal["positive", "negative", "out_of_contract"]
CaseOrigin = Literal["independent_v2", "exposed_v1_regression"]
ContractViolation = Literal[
    "none",
    "truncated_payload",
    "noncanonical_header",
    "dimension_mismatch",
    "invalid_scan_bands",
]
DetectionStatus = Literal["proposed", "abstained"]
ControlStatus = Literal["qualified", "not_qualified"]


class KP1979V2SyntheticControlError(ValueError):
    """Raised when the frozen V2 synthetic-control contract is violated."""


@dataclass(frozen=True, order=True, slots=True)
class SyntheticPrediction:
    """One adapter-normalized detector interval, without generator truth."""

    lane_index: int
    y0: int
    y1: int


@dataclass(frozen=True, slots=True)
class SyntheticDetectorInput:
    """The complete and deliberately answer-free detector adapter input."""

    pbm_bytes: bytes
    width: int
    height: int
    scan_bands: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True, slots=True)
class SyntheticDetectorProposal:
    """A closed, implementation-neutral proposal returned by an adapter."""

    algorithm_id: str
    detection_status: DetectionStatus
    predictions: tuple[SyntheticPrediction, ...]


@dataclass(frozen=True, slots=True)
class SyntheticInputRejection:
    """An adapter-normalized fail-closed rejection of malformed input."""

    algorithm_id: str


SyntheticDetectorOutcome: TypeAlias = SyntheticDetectorProposal | SyntheticInputRejection


class SyntheticDetectorAdapter(Protocol):
    """Normalize a future detector to the frozen answer-free input contract."""

    def __call__(
        self,
        detector_input: SyntheticDetectorInput,
        /,
    ) -> SyntheticDetectorOutcome:
        """Return a closed proposal or normalized structural rejection."""

        ...


@dataclass(frozen=True, slots=True)
class SyntheticFixture:
    """One exact generated fixture and control-side known references."""

    case_id: str
    case_class: CaseClass
    case_origin: CaseOrigin
    contract_violation: ContractViolation
    pdf_page_number: int
    pbm_bytes: bytes
    width: int
    height: int
    scan_bands: tuple[tuple[int, int, int, int], ...]
    references: tuple[LabelReferenceInterval, ...]


@dataclass(frozen=True, slots=True)
class FrozenFixtureCommitment:
    """Exact public commitment to one canonical generated fixture."""

    case_id: str
    case_class: CaseClass
    case_origin: CaseOrigin
    contract_violation: ContractViolation
    pbm_byte_size: int
    pbm_sha256: str
    detector_input_sha256: str
    reference_count: int
    references_sha256: str


@dataclass(frozen=True, slots=True)
class MetamorphicFixturePair:
    """Two answer-free inputs related by one frozen transformation."""

    relation_id: str
    base_input: SyntheticDetectorInput
    transformed_input: SyntheticDetectorInput
    vertical_delta: int | None


@dataclass(frozen=True, slots=True)
class FrozenMetamorphicCommitment:
    """Exact input commitments for one predeclared metamorphic relation."""

    relation_id: str
    base_input_sha256: str
    transformed_input_sha256: str
    vertical_delta: int | None


@dataclass(frozen=True, slots=True)
class SyntheticControlFreeze:
    """The immutable pre-execution state and its explicit nonclaims."""

    control_id: str
    target_algorithm_id: str
    freeze_version: int
    result_state: Literal["not_run"]
    qualification_status: None
    case_count: int
    positive_case_count: int
    negative_case_count: int
    out_of_contract_case_count: int
    case_commitments: tuple[FrozenFixtureCommitment, ...]
    metamorphic_commitments: tuple[FrozenMetamorphicCommitment, ...]
    max_synthetic_cases: int
    max_metamorphic_relations: int
    max_pbm_bytes: int
    max_scan_bands: int
    max_references_per_fixture: int
    max_predictions_per_proposal: int
    detector_executed: bool
    evaluator_executed: bool
    result_recorded: bool
    synthetic_only: bool
    source_independent: bool
    real_accuracy: bool
    reference_accepted: bool
    future_evaluation_opened: bool
    reserved_sources_read: bool
    full_row_segmentation_validated: bool
    identifier_transcription_validated: bool
    decipherment: bool
    prize_submission_eligible: bool


@dataclass(frozen=True, slots=True)
class SyntheticCaseResult:
    """One future adapter outcome evaluated against generator-known truth."""

    case_id: str
    case_class: CaseClass
    passed: bool
    outcome_status: Literal["proposed", "abstained", "rejected"]
    prediction_count: int
    reference_count: int
    scorer_status: str | None
    micro_precision: float | None
    micro_recall: float | None
    negative_control_empty: bool | None


@dataclass(frozen=True, slots=True)
class MetamorphicResult:
    """One future result for a frozen relation."""

    relation_id: str
    passed: bool


@dataclass(frozen=True, slots=True)
class SyntheticControlReport:
    """An in-memory future result; the freeze does not create one."""

    control_id: str
    target_algorithm_id: str
    status: ControlStatus
    case_count: int
    positive_case_count: int
    negative_case_count: int
    out_of_contract_case_count: int
    passed_case_count: int
    cases: tuple[SyntheticCaseResult, ...]
    metamorphic_checks: tuple[MetamorphicResult, ...]
    reference_use: Literal["synthetic_control"]
    synthetic_only: bool
    source_independent: bool
    real_accuracy: bool
    reference_accepted: bool
    future_evaluation_opened: bool
    reserved_sources_read: bool
    full_row_segmentation_validated: bool
    identifier_transcription_validated: bool
    decipherment: bool
    prize_submission_eligible: bool


@dataclass(frozen=True, slots=True)
class _CaseDefinition:
    case_id: str
    case_class: CaseClass
    case_origin: CaseOrigin
    renderer: str
    pdf_page_number: int
    contract_violation: ContractViolation = "none"
    lane_pitches: tuple[int, int] = (163, 163)
    lane_starts: tuple[int, int] = (677, 677)
    jitter: tuple[int, ...] = (0,)
    strokes: tuple[int, ...] = (2,)
    lane_limits: tuple[int | None, int | None] = (None, None)
    missing_rows: tuple[int, ...] = ()
    x_offsets: tuple[int, int] = (24, 24)
    qualifier_period: int | None = None


_CASE_DEFINITIONS: Final = (
    _CaseDefinition(
        "positive_independent_clean",
        "positive",
        "independent_v2",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 1,
    ),
    _CaseDefinition(
        "positive_asymmetric_phase",
        "positive",
        "independent_v2",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 2,
        lane_pitches=(167, 167),
        lane_starts=(611, 644),
        strokes=(2, 3),
    ),
    _CaseDefinition(
        "positive_lower_pitch_boundary_regression",
        "positive",
        "exposed_v1_regression",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 3,
        lane_pitches=(158, 158),
        lane_starts=(633, 633),
    ),
    _CaseDefinition(
        "positive_upper_pitch_boundary_regression",
        "positive",
        "exposed_v1_regression",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 4,
        lane_pitches=(172, 172),
        lane_starts=(629, 629),
    ),
    _CaseDefinition(
        "positive_thin_two_tier_regression",
        "positive",
        "exposed_v1_regression",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 5,
        lane_pitches=(164, 164),
        lane_starts=(671, 671),
        strokes=(1,),
    ),
    _CaseDefinition(
        "positive_bounded_jitter_with_gaps",
        "positive",
        "independent_v2",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 6,
        lane_pitches=(161, 161),
        lane_starts=(618, 618),
        jitter=(0, 5, -3, 2, -5, 4),
        strokes=(1, 2, 3),
        missing_rows=(6, 17, 29),
    ),
    _CaseDefinition(
        "positive_partial_lane_regression",
        "positive",
        "exposed_v1_regression",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 7,
        lane_pitches=(169, 169),
        lane_starts=(604, 604),
        lane_limits=(25, 30),
    ),
    _CaseDefinition(
        "positive_edge_and_qualifier_variation",
        "positive",
        "independent_v2",
        "labels",
        SYNTHETIC_PAGE_NUMBER_BASE + 8,
        lane_pitches=(165, 165),
        lane_starts=(657, 657),
        strokes=(1, 3, 2),
        x_offsets=(8, 108),
        qualifier_period=4,
    ),
    _CaseDefinition(
        "negative_blank_regression",
        "negative",
        "exposed_v1_regression",
        "blank",
        SYNTHETIC_PAGE_NUMBER_BASE + 9,
    ),
    _CaseDefinition(
        "negative_periodic_single_tier_regression",
        "negative",
        "exposed_v1_regression",
        "periodic_single_tier",
        SYNTHETIC_PAGE_NUMBER_BASE + 10,
    ),
    _CaseDefinition(
        "negative_single_lane_regression",
        "negative",
        "exposed_v1_regression",
        "single_lane",
        SYNTHETIC_PAGE_NUMBER_BASE + 11,
    ),
    _CaseDefinition(
        "negative_cross_lane_pitch_conflict",
        "negative",
        "independent_v2",
        "pitch_conflict",
        SYNTHETIC_PAGE_NUMBER_BASE + 12,
        lane_pitches=(159, 171),
        lane_starts=(641, 641),
    ),
    _CaseDefinition(
        "negative_dense_multicolumn_regression",
        "negative",
        "exposed_v1_regression",
        "dense_multicolumn",
        SYNTHETIC_PAGE_NUMBER_BASE + 13,
    ),
    _CaseDefinition(
        "negative_aperiodic_fragments",
        "negative",
        "independent_v2",
        "aperiodic_fragments",
        SYNTHETIC_PAGE_NUMBER_BASE + 14,
    ),
    _CaseDefinition(
        "negative_staggered_single_tiers",
        "negative",
        "independent_v2",
        "staggered_single_tiers",
        SYNTHETIC_PAGE_NUMBER_BASE + 15,
    ),
    _CaseDefinition(
        "out_of_contract_truncated_payload",
        "out_of_contract",
        "independent_v2",
        "blank",
        SYNTHETIC_PAGE_NUMBER_BASE + 16,
        contract_violation="truncated_payload",
    ),
    _CaseDefinition(
        "out_of_contract_noncanonical_header",
        "out_of_contract",
        "independent_v2",
        "blank",
        SYNTHETIC_PAGE_NUMBER_BASE + 17,
        contract_violation="noncanonical_header",
    ),
    _CaseDefinition(
        "out_of_contract_dimension_mismatch",
        "out_of_contract",
        "independent_v2",
        "blank",
        SYNTHETIC_PAGE_NUMBER_BASE + 18,
        contract_violation="dimension_mismatch",
    ),
    _CaseDefinition(
        "out_of_contract_invalid_scan_bands",
        "out_of_contract",
        "independent_v2",
        "blank",
        SYNTHETIC_PAGE_NUMBER_BASE + 19,
        contract_violation="invalid_scan_bands",
    ),
)

SYNTHETIC_CASE_COUNT: Final = 19
SYNTHETIC_POSITIVE_CASE_COUNT: Final = 8
SYNTHETIC_NEGATIVE_CASE_COUNT: Final = 7
SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT: Final = 4
SYNTHETIC_METAMORPHIC_RELATION_COUNT: Final = 3

# Populated only with values computed from this independently authored
# generator before any target detector execution.
_FIXTURE_COMMITMENTS: Final = {
    "positive_independent_clean": FrozenFixtureCommitment(
        case_id="positive_independent_clean",
        case_class="positive",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="3e44b6a5852ce10f2ae66367112a7ee36cfe7270bab900a55626ea89c262552c",
        detector_input_sha256="65f50eea2436add4337b0ad4580d28f4f599cbf0b73b682a07ed3946ea688b25",
        reference_count=72,
        references_sha256="211a2023db1163f1239bcdd24a670117c15f05aa4a6245fe1f13c0d29f053aab",
    ),
    "positive_asymmetric_phase": FrozenFixtureCommitment(
        case_id="positive_asymmetric_phase",
        case_class="positive",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="ba5fdfc17039e17dbf252feae5753d7e4da56cc14c5ebce6be71a0d47a2b914d",
        detector_input_sha256="cfb55ad37c5439f3bb6a97bceda7d0ca62e65242e903686324ad8e2a121451f1",
        reference_count=72,
        references_sha256="63a15372c491c2c49dc8a32c043607f763575c751d730c678425e3e26553fc7e",
    ),
    "positive_lower_pitch_boundary_regression": FrozenFixtureCommitment(
        case_id="positive_lower_pitch_boundary_regression",
        case_class="positive",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="56aff02b3bb8be3a2c383a37ee56518b7ef881c284be9fadaa3a32441f5ed489",
        detector_input_sha256="d26c9ec861f34f4fe2acb4ba8a895a668013ba7afaae03d67166510067eb5e0d",
        reference_count=76,
        references_sha256="d554c3aa2a4072260cf134cfcda6970dbee63a583f186dc85c3ad96571cb4e41",
    ),
    "positive_upper_pitch_boundary_regression": FrozenFixtureCommitment(
        case_id="positive_upper_pitch_boundary_regression",
        case_class="positive",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="56ec6093aebc8e759ed7ccbef7db8f0c7327667941976bd2d44a1c5e02bb22d3",
        detector_input_sha256="0789a8ead55f04f3d873b2f330051b5dc74ff413d61ea0bf73267f2d47954281",
        reference_count=70,
        references_sha256="c637e5a66e27d26b40a57a6363aeffb702b746254ceed4bbd62138bb63454a92",
    ),
    "positive_thin_two_tier_regression": FrozenFixtureCommitment(
        case_id="positive_thin_two_tier_regression",
        case_class="positive",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="a8405502584544a4a2802cf94a6d00135e38903a7df24ac37af4718dedde385b",
        detector_input_sha256="83f2a4b83b9f32aed066a68d5d72b04ad920e24201f951b3834a0d94f3fd34f7",
        reference_count=72,
        references_sha256="af1b311d71023bb8660d9f57dc1113a3c5d31ff4b0f66ce48af9c2b980835758",
    ),
    "positive_bounded_jitter_with_gaps": FrozenFixtureCommitment(
        case_id="positive_bounded_jitter_with_gaps",
        case_class="positive",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="cef0c9d0dfc0482cfe990627becd7c0143f9c1eed41f46a19751e1af442da702",
        detector_input_sha256="fb2e8e54a3bd2d332abecf5625cc6f33d1fa12b13e7e9d77246c2b5a0853902e",
        reference_count=68,
        references_sha256="35d354a49720b3bcf48d55a7ef6abb26a37833aedce9124e73e12dae56c3ac2b",
    ),
    "positive_partial_lane_regression": FrozenFixtureCommitment(
        case_id="positive_partial_lane_regression",
        case_class="positive",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="fd0be1c75841183f0d6dc8b6e7d6bee571c161a1c87a3602d4fb59f534def7b3",
        detector_input_sha256="e37434a319c57646b34978e9bfc98be5cd13f282ed6e6ab2a99f8a71f9457327",
        reference_count=55,
        references_sha256="f9e827f632d95e399457eaa1708dcd20a11d7d3238e587cb70ca80fa4e184398",
    ),
    "positive_edge_and_qualifier_variation": FrozenFixtureCommitment(
        case_id="positive_edge_and_qualifier_variation",
        case_class="positive",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="29721c0366c6ab022fb6e7335cdac7ab0af0d4de9e5a27fe22eedc6ad595cb58",
        detector_input_sha256="5aaf0625e51827b3f05b092408aa94f16d366b7b155c01c39777655f59fd85b8",
        reference_count=72,
        references_sha256="5267dc0e16380a50ab84db7bb7455f32906b7764e4694d4e35f00c9b67a01b35",
    ),
    "negative_blank_regression": FrozenFixtureCommitment(
        case_id="negative_blank_regression",
        case_class="negative",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="a85bc5797a8097f7d6c91f47a834f9f9f5ce15faf53e8626fd612e79cc3bc5ce",
        detector_input_sha256="758e2ad427be086e64dcfa9c8f4d9b58a9b0bba192279f542cb03028149290a0",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "negative_periodic_single_tier_regression": FrozenFixtureCommitment(
        case_id="negative_periodic_single_tier_regression",
        case_class="negative",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="327606dae685e66c333e5483351cb2c24b2f949d40eb3cb5f804bf896aa33df8",
        detector_input_sha256="fca2cdf87d49ff27d9216da94422bb762b181f33ccb625f0de2c8e4ac3cd5c68",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "negative_single_lane_regression": FrozenFixtureCommitment(
        case_id="negative_single_lane_regression",
        case_class="negative",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="b253351b5e2c7c4a5e7e6888e9c5e6b6f725c0f14e6c6371eaa37e2214b430f9",
        detector_input_sha256="d5306174ff4380198adfb2399694d3197bc7e7c63423742f2e6789fb40623f6f",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "negative_cross_lane_pitch_conflict": FrozenFixtureCommitment(
        case_id="negative_cross_lane_pitch_conflict",
        case_class="negative",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="721a89a275ea8d00434cd85f70616a62b5305fec1593161bdc2258c3e4d6978c",
        detector_input_sha256="48580201338bfacb9f7193479a80d865036c7c648fe0eb5a88864eaed5475cbe",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "negative_dense_multicolumn_regression": FrozenFixtureCommitment(
        case_id="negative_dense_multicolumn_regression",
        case_class="negative",
        case_origin="exposed_v1_regression",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="08f6292a17a98bca311c216af1a14afe7185b0c60f0fec3431ff62817af64f8a",
        detector_input_sha256="73edc80d9f74c0826efd9b715641f0770e6e3684bb4c41b6b9874c3d44c6fb79",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "negative_aperiodic_fragments": FrozenFixtureCommitment(
        case_id="negative_aperiodic_fragments",
        case_class="negative",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="21d6b8c1903f62ac2575cde9d3429c7602700eb3700a72c1a269d16eff278a08",
        detector_input_sha256="4dc3d9ebc8001e822ff409ff4cccbdaab8095a1d0724002945ac385dfe360f5a",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "negative_staggered_single_tiers": FrozenFixtureCommitment(
        case_id="negative_staggered_single_tiers",
        case_class="negative",
        case_origin="independent_v2",
        contract_violation="none",
        pbm_byte_size=4_276_113,
        pbm_sha256="09e73551b0f19655ab347cecc34cec5ad4fc202df87de7bd0da319637f8123a4",
        detector_input_sha256="f5954b31d8f4825e446b01881c1aa094732bc2eef0dd8ba4bb84cd785ecdd8ee",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "out_of_contract_truncated_payload": FrozenFixtureCommitment(
        case_id="out_of_contract_truncated_payload",
        case_class="out_of_contract",
        case_origin="independent_v2",
        contract_violation="truncated_payload",
        pbm_byte_size=4_276_096,
        pbm_sha256="654c4907fc7065ec8c51457357400ada71caf1a7acbde6a3bbeedebb4e3ec714",
        detector_input_sha256="dbe705663dbe9c46676921680fdf16e262b6433fe84cb5238550b9ce3ff1f307",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "out_of_contract_noncanonical_header": FrozenFixtureCommitment(
        case_id="out_of_contract_noncanonical_header",
        case_class="out_of_contract",
        case_origin="independent_v2",
        contract_violation="noncanonical_header",
        pbm_byte_size=4_276_114,
        pbm_sha256="d915be6259e06228aa2b84bab82783c13b96e0fd1873bdeef7e904a5ad2015ce",
        detector_input_sha256="5a7dc574d8ac4dd9034c3a938670f70f3781b75e727aadd2f7e1b04d50c990a3",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "out_of_contract_dimension_mismatch": FrozenFixtureCommitment(
        case_id="out_of_contract_dimension_mismatch",
        case_class="out_of_contract",
        case_origin="independent_v2",
        contract_violation="dimension_mismatch",
        pbm_byte_size=4_276_113,
        pbm_sha256="a85bc5797a8097f7d6c91f47a834f9f9f5ce15faf53e8626fd612e79cc3bc5ce",
        detector_input_sha256="ec281e29b0550e5eb78892ffb11e81378c18c4a9779554d0ece8875d256d4f68",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
    "out_of_contract_invalid_scan_bands": FrozenFixtureCommitment(
        case_id="out_of_contract_invalid_scan_bands",
        case_class="out_of_contract",
        case_origin="independent_v2",
        contract_violation="invalid_scan_bands",
        pbm_byte_size=4_276_113,
        pbm_sha256="a85bc5797a8097f7d6c91f47a834f9f9f5ce15faf53e8626fd612e79cc3bc5ce",
        detector_input_sha256="cfae08713c309811a8eb8548bb7a0d0b9f18b75f737eef35bfb03ef49b531400",
        reference_count=0,
        references_sha256="18f319a612278099c71360e2580eb159d320ce5758178fe43a0a3273232a998c",
    ),
}
_METAMORPHIC_COMMITMENTS: Final = {
    "identical_input_reproducibility": FrozenMetamorphicCommitment(
        relation_id="identical_input_reproducibility",
        base_input_sha256="65f50eea2436add4337b0ad4580d28f4f599cbf0b73b682a07ed3946ea688b25",
        transformed_input_sha256=(
            "65f50eea2436add4337b0ad4580d28f4f599cbf0b73b682a07ed3946ea688b25"
        ),
        vertical_delta=None,
    ),
    "unread_margin_invariance": FrozenMetamorphicCommitment(
        relation_id="unread_margin_invariance",
        base_input_sha256="65f50eea2436add4337b0ad4580d28f4f599cbf0b73b682a07ed3946ea688b25",
        transformed_input_sha256=(
            "5b0dc679b67edc57d95ada54b3a2739e66f2c6c0a81dcf7e41b5405457622de4"
        ),
        vertical_delta=None,
    ),
    "vertical_translation_equivariance": FrozenMetamorphicCommitment(
        relation_id="vertical_translation_equivariance",
        base_input_sha256="65f50eea2436add4337b0ad4580d28f4f599cbf0b73b682a07ed3946ea688b25",
        transformed_input_sha256=(
            "2bd5159be3bab042a29a8b66cd7025212ba7625a936c447226d1d05a49bce8c0"
        ),
        vertical_delta=11,
    ),
}


class _Bitmap:
    def __init__(self) -> None:
        self.payload = bytearray(SYNTHETIC_ROW_BYTES * SYNTHETIC_PAGE_HEIGHT)

    def rectangle(self, x0: int, y0: int, x1: int, y1: int) -> None:
        if not (0 <= x0 < x1 <= SYNTHETIC_PAGE_WIDTH and 0 <= y0 < y1 <= SYNTHETIC_PAGE_HEIGHT):
            raise KP1979V2SyntheticControlError("synthetic rectangle is outside the page")
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
        value = SYNTHETIC_PBM_HEADER + bytes(self.payload)
        if len(value) != SYNTHETIC_PBM_BYTE_SIZE:
            raise KP1979V2SyntheticControlError("synthetic PBM size is not canonical")
        return value


def synthetic_case_ids() -> tuple[str, ...]:
    """Return the frozen public case roster in canonical order."""

    return tuple(definition.case_id for definition in _CASE_DEFINITIONS)


def build_synthetic_fixture(case_id: str) -> SyntheticFixture:
    """Rebuild and exact-commitment-check one canonical fixture."""

    definition = _definition(case_id)
    fixture = _render_synthetic_fixture(definition)
    _verify_fixture_commitment(fixture)
    return fixture


def detector_input_for_fixture(fixture: SyntheticFixture) -> SyntheticDetectorInput:
    """Strip all control-side metadata after exact canonical equality."""

    if not isinstance(fixture, SyntheticFixture):
        raise KP1979V2SyntheticControlError("fixture must be a SyntheticFixture")
    canonical = build_synthetic_fixture(fixture.case_id)
    if fixture != canonical:
        raise KP1979V2SyntheticControlError("fixture differs from the frozen generator")
    return _answer_free_input(fixture)


def frozen_synthetic_control() -> SyntheticControlFreeze:
    """Return the pre-result freeze without constructing or running an adapter."""

    _require_roster_freeze()
    case_commitments = tuple(
        _FIXTURE_COMMITMENTS[definition.case_id] for definition in _CASE_DEFINITIONS
    )
    metamorphic_commitments = tuple(
        _METAMORPHIC_COMMITMENTS[relation_id]
        for relation_id in (
            "identical_input_reproducibility",
            "unread_margin_invariance",
            "vertical_translation_equivariance",
        )
    )
    return SyntheticControlFreeze(
        control_id=CONTROL_ID,
        target_algorithm_id=TARGET_ALGORITHM_ID,
        freeze_version=FREEZE_VERSION,
        result_state="not_run",
        qualification_status=None,
        case_count=len(case_commitments),
        positive_case_count=SYNTHETIC_POSITIVE_CASE_COUNT,
        negative_case_count=SYNTHETIC_NEGATIVE_CASE_COUNT,
        out_of_contract_case_count=SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT,
        case_commitments=case_commitments,
        metamorphic_commitments=metamorphic_commitments,
        max_synthetic_cases=MAX_SYNTHETIC_CASES,
        max_metamorphic_relations=MAX_METAMORPHIC_RELATIONS,
        max_pbm_bytes=MAX_PBM_BYTES,
        max_scan_bands=MAX_SCAN_BANDS,
        max_references_per_fixture=MAX_REFERENCES_PER_FIXTURE,
        max_predictions_per_proposal=MAX_PREDICTIONS_PER_PROPOSAL,
        detector_executed=False,
        evaluator_executed=False,
        result_recorded=False,
        synthetic_only=True,
        source_independent=True,
        real_accuracy=False,
        reference_accepted=False,
        future_evaluation_opened=False,
        reserved_sources_read=False,
        full_row_segmentation_validated=False,
        identifier_transcription_validated=False,
        decipherment=False,
        prize_submission_eligible=False,
    )


def metamorphic_fixture_pairs() -> tuple[MetamorphicFixturePair, ...]:
    """Rebuild every relation input and exact-check its frozen commitment."""

    pairs = _render_metamorphic_pairs()
    if len(pairs) != SYNTHETIC_METAMORPHIC_RELATION_COUNT:
        raise KP1979V2SyntheticControlError("metamorphic roster differs from its freeze")
    for pair in pairs:
        actual = _metamorphic_commitment(pair)
        expected = _METAMORPHIC_COMMITMENTS.get(pair.relation_id)
        if actual != expected:
            raise KP1979V2SyntheticControlError(
                "metamorphic fixture bytes differ from their freeze"
            )
    return pairs


def evaluate_synthetic_fixture(
    fixture: SyntheticFixture,
    outcome: SyntheticDetectorOutcome,
) -> SyntheticCaseResult:
    """Evaluate one closed proposal/rejection only for an exact frozen fixture."""

    detector_input_for_fixture(fixture)
    return _evaluate_canonical_fixture_outcome(fixture, outcome)


def evaluate_frozen_synthetic_control(
    adapter: SyntheticDetectorAdapter
    | Callable[[SyntheticDetectorInput], SyntheticDetectorOutcome],
) -> SyntheticControlReport:
    """Evaluate a future adapter entirely in memory, without recording a result."""

    if not callable(adapter):
        raise KP1979V2SyntheticControlError("detector adapter must be callable")
    _require_roster_freeze()
    cases = tuple(
        _evaluate_fixture_with_adapter(build_synthetic_fixture(definition.case_id), adapter)
        for definition in _CASE_DEFINITIONS
    )
    metamorphic_checks = tuple(
        _evaluate_metamorphic_pair(pair, adapter) for pair in metamorphic_fixture_pairs()
    )
    qualified = all(case.passed for case in cases) and all(
        relation.passed for relation in metamorphic_checks
    )
    return SyntheticControlReport(
        control_id=CONTROL_ID,
        target_algorithm_id=TARGET_ALGORITHM_ID,
        status="qualified" if qualified else "not_qualified",
        case_count=len(cases),
        positive_case_count=sum(case.case_class == "positive" for case in cases),
        negative_case_count=sum(case.case_class == "negative" for case in cases),
        out_of_contract_case_count=sum(case.case_class == "out_of_contract" for case in cases),
        passed_case_count=sum(case.passed for case in cases),
        cases=cases,
        metamorphic_checks=metamorphic_checks,
        reference_use="synthetic_control",
        synthetic_only=True,
        source_independent=True,
        real_accuracy=False,
        reference_accepted=False,
        future_evaluation_opened=False,
        reserved_sources_read=False,
        full_row_segmentation_validated=False,
        identifier_transcription_validated=False,
        decipherment=False,
        prize_submission_eligible=False,
    )


def _definition(case_id: str) -> _CaseDefinition:
    if not isinstance(case_id, str) or not case_id:
        raise KP1979V2SyntheticControlError("synthetic case id must be a nonempty string")
    matches = tuple(value for value in _CASE_DEFINITIONS if value.case_id == case_id)
    if len(matches) != 1:
        raise KP1979V2SyntheticControlError("synthetic case id is not in the frozen roster")
    return matches[0]


def _render_synthetic_fixture(
    definition: _CaseDefinition,
    *,
    vertical_offset: int = 0,
    top_margin_marks: bool = False,
) -> SyntheticFixture:
    bitmap = _Bitmap()
    references: list[LabelReferenceInterval] = []
    if definition.renderer == "labels":
        for lane_index in (0, 1):
            _draw_label_lattice(
                bitmap,
                page=definition.pdf_page_number,
                lane_index=lane_index,
                pitch=definition.lane_pitches[lane_index],
                start_y=definition.lane_starts[lane_index] + vertical_offset,
                jitter=definition.jitter,
                strokes=definition.strokes,
                limit=definition.lane_limits[lane_index],
                missing_rows=definition.missing_rows,
                x_offset=definition.x_offsets[lane_index],
                qualifier_period=definition.qualifier_period,
                references=references,
            )
    elif definition.renderer == "single_lane":
        _draw_label_lattice(
            bitmap,
            page=definition.pdf_page_number,
            lane_index=0,
            pitch=164,
            start_y=639 + vertical_offset,
            jitter=(0,),
            strokes=(2,),
            limit=None,
            missing_rows=(),
            x_offset=24,
            qualifier_period=None,
            references=None,
        )
    elif definition.renderer == "pitch_conflict":
        for lane_index in (0, 1):
            _draw_label_lattice(
                bitmap,
                page=definition.pdf_page_number,
                lane_index=lane_index,
                pitch=definition.lane_pitches[lane_index],
                start_y=definition.lane_starts[lane_index] + vertical_offset,
                jitter=(0,),
                strokes=(2,),
                limit=None,
                missing_rows=(),
                x_offset=24,
                qualifier_period=None,
                references=None,
            )
    elif definition.renderer == "periodic_single_tier":
        for lane_index, band in enumerate(SYNTHETIC_SCAN_BANDS):
            x0 = band[0] + 18 + lane_index * 7
            for row_index, y in enumerate(range(633 + vertical_offset, 6500, 164)):
                _draw_symbol_line(
                    bitmap,
                    x0=x0,
                    y0=y,
                    symbol_count=4,
                    stroke=1 + row_index % 2,
                    seed=row_index + lane_index * 41,
                )
    elif definition.renderer == "dense_multicolumn":
        for column_index, x0 in enumerate(range(160, 4720, 228)):
            for row_index, y in enumerate(range(622 + vertical_offset, 6510, 164)):
                _draw_symbol_line(
                    bitmap,
                    x0=x0,
                    y0=y,
                    symbol_count=4,
                    stroke=2,
                    seed=row_index + column_index * 13,
                )
                _draw_symbol_line(
                    bitmap,
                    x0=x0 + 9,
                    y0=y + 34,
                    symbol_count=3,
                    stroke=2,
                    seed=row_index * 5 + column_index,
                )
    elif definition.renderer == "aperiodic_fragments":
        y = 571 + vertical_offset
        for fragment_index in range(38):
            y += 61 + ((fragment_index * 47 + 19) % 131)
            if y + 20 >= SYNTHETIC_SCAN_BOTTOM:
                break
            for lane_index, band in enumerate(SYNTHETIC_SCAN_BANDS):
                x0 = band[0] + 10 + ((fragment_index * 23 + lane_index * 17) % 106)
                _draw_symbol_line(
                    bitmap,
                    x0=x0,
                    y0=y,
                    symbol_count=2 + fragment_index % 3,
                    stroke=1 + fragment_index % 3,
                    seed=fragment_index * 17 + lane_index,
                )
    elif definition.renderer == "staggered_single_tiers":
        for lane_index, band in enumerate(SYNTHETIC_SCAN_BANDS):
            x0 = band[0] + 22
            for row_index, y in enumerate(range(615 + vertical_offset, 6500, 163)):
                tier_y = y if (row_index + lane_index) % 2 == 0 else y + 34
                _draw_symbol_line(
                    bitmap,
                    x0=x0,
                    y0=tier_y,
                    symbol_count=3,
                    stroke=2,
                    seed=row_index * 29 + lane_index,
                )
    elif definition.renderer != "blank":
        raise KP1979V2SyntheticControlError("synthetic renderer is invalid")

    if top_margin_marks:
        for mark_index, y in enumerate(range(47, 430, 19)):
            x0 = 120 + (mark_index * 71) % 700
            bitmap.rectangle(x0, y, min(x0 + 3300, 4700), y + 2)

    pbm_bytes = bitmap.pbm_bytes()
    width = SYNTHETIC_PAGE_WIDTH
    height = SYNTHETIC_PAGE_HEIGHT
    scan_bands: tuple[tuple[int, int, int, int], ...] = SYNTHETIC_SCAN_BANDS
    if definition.contract_violation == "truncated_payload":
        pbm_bytes = pbm_bytes[:-17]
    elif definition.contract_violation == "noncanonical_header":
        pbm_bytes = b"P4\n4880 7010 \n" + pbm_bytes[len(SYNTHETIC_PBM_HEADER) :]
    elif definition.contract_violation == "dimension_mismatch":
        width = SYNTHETIC_PAGE_WIDTH - 1
    elif definition.contract_violation == "invalid_scan_bands":
        scan_bands = (
            SYNTHETIC_SCAN_BANDS[0],
            (SYNTHETIC_SCAN_BANDS[1][0], SYNTHETIC_SCAN_TOP, 5001, SYNTHETIC_SCAN_BOTTOM),
        )
    elif definition.contract_violation != "none":
        raise KP1979V2SyntheticControlError("contract violation renderer is invalid")

    return SyntheticFixture(
        case_id=definition.case_id,
        case_class=definition.case_class,
        case_origin=definition.case_origin,
        contract_violation=definition.contract_violation,
        pdf_page_number=definition.pdf_page_number,
        pbm_bytes=pbm_bytes,
        width=width,
        height=height,
        scan_bands=scan_bands,
        references=tuple(sorted(references)),
    )


def _draw_label_lattice(
    bitmap: _Bitmap,
    *,
    page: int,
    lane_index: int,
    pitch: int,
    start_y: int,
    jitter: tuple[int, ...],
    strokes: tuple[int, ...],
    limit: int | None,
    missing_rows: tuple[int, ...],
    x_offset: int,
    qualifier_period: int | None,
    references: list[LabelReferenceInterval] | None,
) -> None:
    band = SYNTHETIC_SCAN_BANDS[lane_index]
    x0 = band[0] + x_offset
    for row_index, base_y in enumerate(range(start_y, SYNTHETIC_SCAN_BOTTOM - 60, pitch)):
        if limit is not None and row_index >= limit:
            break
        if row_index in missing_rows:
            continue
        y0 = base_y + jitter[row_index % len(jitter)]
        _draw_two_tier_label(
            bitmap,
            x0=x0,
            y0=y0,
            stroke=strokes[row_index % len(strokes)],
            seed=row_index * 37 + lane_index * 101,
            qualifier=qualifier_period is not None and row_index % qualifier_period == 0,
        )
        if references is not None:
            references.append(
                LabelReferenceInterval(
                    pdf_page_number=page,
                    lane_index=lane_index,
                    y0=y0,
                    y1=y0 + 54,
                )
            )


def _draw_two_tier_label(
    bitmap: _Bitmap,
    *,
    x0: int,
    y0: int,
    stroke: int,
    seed: int,
    qualifier: bool,
) -> None:
    _draw_symbol_line(
        bitmap,
        x0=x0,
        y0=y0,
        symbol_count=4,
        stroke=stroke,
        seed=seed,
    )
    _draw_symbol_line(
        bitmap,
        x0=x0 + 11,
        y0=y0 + 34,
        symbol_count=3,
        stroke=stroke,
        seed=seed ^ 0x5A,
    )
    if qualifier:
        bitmap.rectangle(x0 + 58, y0 + 34, x0 + 58 + stroke, y0 + 41)
        bitmap.rectangle(x0 + 58, y0 + 49, x0 + 58 + stroke, y0 + 54)


def _draw_symbol_line(
    bitmap: _Bitmap,
    *,
    x0: int,
    y0: int,
    symbol_count: int,
    stroke: int,
    seed: int,
) -> None:
    if stroke not in {1, 2, 3}:
        raise KP1979V2SyntheticControlError("synthetic stroke width is invalid")
    for symbol_index in range(symbol_count):
        glyph_x = x0 + symbol_index * 14
        pattern = (seed * 73 + symbol_index * 29 + 0x35) & 0xFF
        bitmap.rectangle(glyph_x, y0, glyph_x + 10, y0 + stroke)
        bitmap.rectangle(glyph_x, y0 + 20 - stroke, glyph_x + 10, y0 + 20)
        bitmap.rectangle(glyph_x, y0, glyph_x + stroke, y0 + 20)
        if pattern & 1:
            bitmap.rectangle(glyph_x + 10 - stroke, y0, glyph_x + 10, y0 + 20)
        if pattern & 2:
            bitmap.rectangle(glyph_x, y0 + 9, glyph_x + 10, y0 + 9 + stroke)
        if pattern & 4:
            bitmap.rectangle(glyph_x + 4, y0 + 3, glyph_x + 4 + stroke, y0 + 10)
        if pattern & 8:
            bitmap.rectangle(glyph_x + 5, y0 + 10, glyph_x + 5 + stroke, y0 + 17)


def _answer_free_input(fixture: SyntheticFixture) -> SyntheticDetectorInput:
    return SyntheticDetectorInput(
        pbm_bytes=fixture.pbm_bytes,
        width=fixture.width,
        height=fixture.height,
        scan_bands=fixture.scan_bands,
    )


def _render_metamorphic_pairs() -> tuple[MetamorphicFixturePair, ...]:
    definition = _definition("positive_independent_clean")
    base_fixture = _render_synthetic_fixture(definition)
    repeated_fixture = _render_synthetic_fixture(definition)
    margin_fixture = _render_synthetic_fixture(definition, top_margin_marks=True)
    shifted_fixture = _render_synthetic_fixture(definition, vertical_offset=11)
    return (
        MetamorphicFixturePair(
            relation_id="identical_input_reproducibility",
            base_input=_answer_free_input(base_fixture),
            transformed_input=_answer_free_input(repeated_fixture),
            vertical_delta=None,
        ),
        MetamorphicFixturePair(
            relation_id="unread_margin_invariance",
            base_input=_answer_free_input(base_fixture),
            transformed_input=_answer_free_input(margin_fixture),
            vertical_delta=None,
        ),
        MetamorphicFixturePair(
            relation_id="vertical_translation_equivariance",
            base_input=_answer_free_input(base_fixture),
            transformed_input=_answer_free_input(shifted_fixture),
            vertical_delta=11,
        ),
    )


def _fixture_commitment(fixture: SyntheticFixture) -> FrozenFixtureCommitment:
    return FrozenFixtureCommitment(
        case_id=fixture.case_id,
        case_class=fixture.case_class,
        case_origin=fixture.case_origin,
        contract_violation=fixture.contract_violation,
        pbm_byte_size=len(fixture.pbm_bytes),
        pbm_sha256=sha256(fixture.pbm_bytes).hexdigest(),
        detector_input_sha256=_detector_input_digest(_answer_free_input(fixture)),
        reference_count=len(fixture.references),
        references_sha256=_reference_digest(fixture.references),
    )


def _metamorphic_commitment(
    pair: MetamorphicFixturePair,
) -> FrozenMetamorphicCommitment:
    return FrozenMetamorphicCommitment(
        relation_id=pair.relation_id,
        base_input_sha256=_detector_input_digest(pair.base_input),
        transformed_input_sha256=_detector_input_digest(pair.transformed_input),
        vertical_delta=pair.vertical_delta,
    )


def _detector_input_digest(detector_input: SyntheticDetectorInput) -> str:
    digest = sha256(b"KP1979-V2-SYNTHETIC-DETECTOR-INPUT\x00")
    digest.update(detector_input.width.to_bytes(4, "big", signed=True))
    digest.update(detector_input.height.to_bytes(4, "big", signed=True))
    digest.update(len(detector_input.scan_bands).to_bytes(2, "big"))
    for band in detector_input.scan_bands:
        digest.update(len(band).to_bytes(1, "big"))
        for value in band:
            digest.update(value.to_bytes(4, "big", signed=True))
    digest.update(len(detector_input.pbm_bytes).to_bytes(8, "big"))
    digest.update(detector_input.pbm_bytes)
    return digest.hexdigest()


def _reference_digest(references: tuple[LabelReferenceInterval, ...]) -> str:
    digest = sha256(b"KP1979-V2-SYNTHETIC-REFERENCES\x00")
    digest.update(len(references).to_bytes(4, "big"))
    for reference in references:
        digest.update(reference.pdf_page_number.to_bytes(4, "big"))
        digest.update(reference.lane_index.to_bytes(1, "big"))
        digest.update(reference.y0.to_bytes(4, "big"))
        digest.update(reference.y1.to_bytes(4, "big"))
    return digest.hexdigest()


def _verify_fixture_commitment(fixture: SyntheticFixture) -> None:
    if len(fixture.pbm_bytes) > MAX_PBM_BYTES:
        raise KP1979V2SyntheticControlError("synthetic PBM exceeds its fixed byte limit")
    if len(fixture.scan_bands) > MAX_SCAN_BANDS:
        raise KP1979V2SyntheticControlError("scan-band roster exceeds its fixed limit")
    if len(fixture.references) > MAX_REFERENCES_PER_FIXTURE:
        raise KP1979V2SyntheticControlError("reference roster exceeds its fixed limit")
    actual = _fixture_commitment(fixture)
    expected = _FIXTURE_COMMITMENTS.get(fixture.case_id)
    if actual != expected:
        raise KP1979V2SyntheticControlError("synthetic fixture bytes differ from their freeze")


def _require_roster_freeze() -> None:
    if (
        len(_CASE_DEFINITIONS) != SYNTHETIC_CASE_COUNT
        or len(_CASE_DEFINITIONS) > MAX_SYNTHETIC_CASES
        or len({value.case_id for value in _CASE_DEFINITIONS}) != len(_CASE_DEFINITIONS)
        or sum(value.case_class == "positive" for value in _CASE_DEFINITIONS)
        != SYNTHETIC_POSITIVE_CASE_COUNT
        or sum(value.case_class == "negative" for value in _CASE_DEFINITIONS)
        != SYNTHETIC_NEGATIVE_CASE_COUNT
        or sum(value.case_class == "out_of_contract" for value in _CASE_DEFINITIONS)
        != SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT
        or len(_FIXTURE_COMMITMENTS) != SYNTHETIC_CASE_COUNT
        or len(_METAMORPHIC_COMMITMENTS) != SYNTHETIC_METAMORPHIC_RELATION_COUNT
        or SYNTHETIC_METAMORPHIC_RELATION_COUNT > MAX_METAMORPHIC_RELATIONS
    ):
        raise KP1979V2SyntheticControlError("synthetic-control roster differs from its freeze")


def _normalize_outcome(outcome: SyntheticDetectorOutcome) -> SyntheticDetectorOutcome:
    if isinstance(outcome, SyntheticInputRejection):
        if not isinstance(outcome.algorithm_id, str) or not outcome.algorithm_id:
            raise KP1979V2SyntheticControlError("rejection algorithm id is invalid")
        return outcome
    if not isinstance(outcome, SyntheticDetectorProposal):
        raise KP1979V2SyntheticControlError("adapter returned an invalid outcome")
    if not isinstance(outcome.algorithm_id, str) or not outcome.algorithm_id:
        raise KP1979V2SyntheticControlError("proposal algorithm id is invalid")
    if outcome.detection_status not in {"proposed", "abstained"}:
        raise KP1979V2SyntheticControlError("proposal detection status is invalid")
    if not isinstance(outcome.predictions, tuple):
        raise KP1979V2SyntheticControlError("proposal predictions must be a tuple")
    if len(outcome.predictions) > MAX_PREDICTIONS_PER_PROPOSAL:
        raise KP1979V2SyntheticControlError("proposal exceeds its fixed prediction limit")
    if any(not isinstance(value, SyntheticPrediction) for value in outcome.predictions):
        raise KP1979V2SyntheticControlError("proposal contains an invalid prediction")
    if len(set(outcome.predictions)) != len(outcome.predictions):
        raise KP1979V2SyntheticControlError("proposal contains a duplicate prediction")
    for prediction in outcome.predictions:
        if (
            not _is_integer(prediction.lane_index)
            or prediction.lane_index not in {0, 1}
            or not _is_integer(prediction.y0)
            or not _is_integer(prediction.y1)
            or prediction.y0 < 0
            or prediction.y1 > SYNTHETIC_PAGE_HEIGHT
            or prediction.y1 - prediction.y0 != SYNTHETIC_PREDICTION_HEIGHT
        ):
            raise KP1979V2SyntheticControlError("proposal prediction is outside its contract")
    if outcome.detection_status == "abstained" and outcome.predictions:
        raise KP1979V2SyntheticControlError("abstained proposal must not contain predictions")
    return SyntheticDetectorProposal(
        algorithm_id=outcome.algorithm_id,
        detection_status=outcome.detection_status,
        predictions=tuple(
            sorted(
                outcome.predictions,
                key=lambda value: (value.lane_index, value.y0, value.y1),
            )
        ),
    )


def _evaluate_fixture_with_adapter(
    fixture: SyntheticFixture,
    adapter: SyntheticDetectorAdapter
    | Callable[[SyntheticDetectorInput], SyntheticDetectorOutcome],
) -> SyntheticCaseResult:
    detector_input = detector_input_for_fixture(fixture)
    return _evaluate_canonical_fixture_outcome(fixture, adapter(detector_input))


def _evaluate_canonical_fixture_outcome(
    fixture: SyntheticFixture,
    candidate_outcome: SyntheticDetectorOutcome,
) -> SyntheticCaseResult:
    outcome = _normalize_outcome(candidate_outcome)
    algorithm_matches = outcome.algorithm_id == TARGET_ALGORITHM_ID
    if isinstance(outcome, SyntheticInputRejection):
        return SyntheticCaseResult(
            case_id=fixture.case_id,
            case_class=fixture.case_class,
            passed=algorithm_matches and fixture.case_class == "out_of_contract",
            outcome_status="rejected",
            prediction_count=0,
            reference_count=len(fixture.references),
            scorer_status=None,
            micro_precision=None,
            micro_recall=None,
            negative_control_empty=None,
        )
    if fixture.case_class == "out_of_contract":
        return SyntheticCaseResult(
            case_id=fixture.case_id,
            case_class=fixture.case_class,
            passed=False,
            outcome_status=outcome.detection_status,
            prediction_count=len(outcome.predictions),
            reference_count=0,
            scorer_status=None,
            micro_precision=None,
            micro_recall=None,
            negative_control_empty=None,
        )
    predictions = tuple(
        LabelPrediction(
            pdf_page_number=fixture.pdf_page_number,
            lane_index=value.lane_index,
            y0=value.y0,
            y1=value.y1,
        )
        for value in outcome.predictions
    )
    score = _score_label_positions(
        predictions,
        fixture.references,
        reference_use="synthetic_control",
        positive_pages=((fixture.pdf_page_number,) if fixture.case_class == "positive" else ()),
        negative_pages=((fixture.pdf_page_number,) if fixture.case_class == "negative" else ()),
    )
    if (
        score.reference_use != "synthetic_control"
        or score.reference_eligibility_verified
        or score.evaluation_admissible
        or score.real_accuracy
        or score.decipherment
        or score.prize_submission_eligible
    ):
        raise KP1979V2SyntheticControlError("internal synthetic scorer returned unsafe claims")
    if fixture.case_class == "positive":
        passed = (
            algorithm_matches
            and outcome.detection_status == "proposed"
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
        outcome_status=outcome.detection_status,
        prediction_count=len(outcome.predictions),
        reference_count=len(fixture.references),
        scorer_status=score.status,
        micro_precision=score.micro_precision,
        micro_recall=score.micro_recall,
        negative_control_empty=score.negative_control_empty,
    )


def _evaluate_metamorphic_pair(
    pair: MetamorphicFixturePair,
    adapter: SyntheticDetectorAdapter
    | Callable[[SyntheticDetectorInput], SyntheticDetectorOutcome],
) -> MetamorphicResult:
    base = _normalize_outcome(adapter(pair.base_input))
    transformed = _normalize_outcome(adapter(pair.transformed_input))
    if (
        isinstance(base, SyntheticInputRejection)
        or isinstance(transformed, SyntheticInputRejection)
        or base.algorithm_id != TARGET_ALGORITHM_ID
        or transformed.algorithm_id != TARGET_ALGORITHM_ID
    ):
        return MetamorphicResult(pair.relation_id, False)
    if pair.vertical_delta is None:
        passed = base == transformed
    else:
        passed = (
            base.algorithm_id == transformed.algorithm_id
            and base.detection_status == transformed.detection_status
            and tuple(
                SyntheticPrediction(
                    lane_index=value.lane_index,
                    y0=value.y0 + pair.vertical_delta,
                    y1=value.y1 + pair.vertical_delta,
                )
                for value in base.predictions
            )
            == transformed.predictions
        )
    return MetamorphicResult(pair.relation_id, passed)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


__all__ = [
    "CONTROL_ID",
    "FREEZE_MANIFEST_BYTE_SIZE",
    "FREEZE_MANIFEST_PATH",
    "FREEZE_MANIFEST_SHA256",
    "FREEZE_RESULT_STATE",
    "FREEZE_VERSION",
    "MAX_METAMORPHIC_RELATIONS",
    "MAX_PBM_BYTES",
    "MAX_PREDICTIONS_PER_PROPOSAL",
    "MAX_REFERENCES_PER_FIXTURE",
    "MAX_SCAN_BANDS",
    "MAX_SYNTHETIC_CASES",
    "SYNTHETIC_CASE_COUNT",
    "SYNTHETIC_METAMORPHIC_RELATION_COUNT",
    "SYNTHETIC_NEGATIVE_CASE_COUNT",
    "SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT",
    "SYNTHETIC_PAGE_HEIGHT",
    "SYNTHETIC_PAGE_NUMBER_BASE",
    "SYNTHETIC_PAGE_WIDTH",
    "SYNTHETIC_PBM_BYTE_SIZE",
    "SYNTHETIC_POSITIVE_CASE_COUNT",
    "SYNTHETIC_SCAN_BANDS",
    "TARGET_ALGORITHM_ID",
    "FrozenFixtureCommitment",
    "FrozenMetamorphicCommitment",
    "KP1979V2SyntheticControlError",
    "MetamorphicFixturePair",
    "MetamorphicResult",
    "SyntheticCaseResult",
    "SyntheticControlFreeze",
    "SyntheticControlReport",
    "SyntheticDetectorAdapter",
    "SyntheticDetectorInput",
    "SyntheticDetectorOutcome",
    "SyntheticDetectorProposal",
    "SyntheticFixture",
    "SyntheticInputRejection",
    "SyntheticPrediction",
    "build_synthetic_fixture",
    "detector_input_for_fixture",
    "evaluate_frozen_synthetic_control",
    "evaluate_synthetic_fixture",
    "frozen_synthetic_control",
    "metamorphic_fixture_pairs",
    "synthetic_case_ids",
]
