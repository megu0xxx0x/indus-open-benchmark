"""Streaming, aggregate-only evaluator for the KP1979 V3 synthetic control.

The evaluator builds and validates one controller-side generator object at a
time.  Only its answer-free ``request_bytes`` cross the worker boundary.
Generated objects, truth, responses, digests, and schedule meaning remain
ephemeral and are never represented in the aggregate result.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Final, NoReturn, Protocol

from .kp1979_v3_generator import (
    GeneratedCase,
    GeneratedRelation,
    build_case,
    build_relation,
    validate_generated_case,
    validate_generated_relation,
)
from .kp1979_v3_grammar import PageLatticeCertificate, TruthSlot
from .kp1979_v3_protocol import (
    C3_PASS_AUTHORIZATION,
    CASE_INVOCATIONS,
    CASE_ROSTER,
    CONTROL_ID,
    INTENDED_PREDICTION_HEIGHT,
    METAMORPHIC_ENDPOINT_INVOCATIONS,
    METAMORPHIC_RELATIONS,
    PUBLIC_CLAIM_PERMISSIONS,
    TOTAL_WORKER_INVOCATIONS,
    V3_PROTOCOL,
    C3PassAuthorization,
    CaseCategory,
    ClaimPermission,
    MetamorphicKind,
    WorkerStatus,
    validate_protocol,
)
from .kp1979_v3_sandbox import (
    MAX_STDOUT_BYTES,
    MINIMUM_LANDLOCK_ABI,
    SandboxInvocationResult,
)
from .kp1979_v3_state import TerminalStatus
from .kp1979_v3_wire import Prediction, WorkerResponse, decode_worker_response

RESULT_VERSION: Final = 1
_CLOSED_PROTOCOL: Final = V3_PROTOCOL

_POSITIVE_CASE_COUNT: Final = 12
_NEGATIVE_CASE_COUNT: Final = 14
_OUT_OF_CONTRACT_CASE_COUNT: Final = 6
_METAMORPHIC_RELATION_COUNT: Final = 8
_PREDICTION_ANCHOR_OFFSET: Final = _CLOSED_PROTOCOL.intended_prediction_height // 2
_INVARIANT_RELATIONS: Final = frozenset(
    {
        MetamorphicKind.IDENTICAL,
        MetamorphicKind.UNREAD_MARGIN,
        MetamorphicKind.HORIZONTAL_TRANSLATION,
        MetamorphicKind.STROKE_WIDTH,
        MetamorphicKind.RENDERER_SUBSTITUTION,
    }
)


class KP1979V3EvaluatorError(ValueError):
    """A detail-free evaluator contract rejection."""

    def __init__(self) -> None:
        super().__init__("kp1979-v3 evaluator contract rejected")


class _TechnicalFailure(Exception):
    """Internal marker collapsed to one aggregate execution-failed result."""


class C3WorkerInvoker(Protocol):
    """Fresh sandbox invoker receiving only one answer-free request."""

    started_process_count: int
    verified_invocation_count: int

    def __call__(self, request_bytes: bytes, /) -> SandboxInvocationResult:
        """Dispatch exactly one request and return its redacted sandbox result."""

        ...


@dataclass(frozen=True, slots=True, repr=False)
class C3AggregateResult:
    """Closed aggregate result without item-level evaluation material."""

    result_version: int
    control_id: str
    terminal_status: TerminalStatus
    worker_invocation_count: int | None
    positive_case_pass_count: int | None
    negative_case_pass_count: int | None
    out_of_contract_case_pass_count: int | None
    metamorphic_relation_pass_count: int | None
    authorization: C3PassAuthorization | None
    public_claim_permissions: tuple[ClaimPermission, ...]

    def __post_init__(self) -> None:
        if (
            type(self.result_version) is not int
            or self.result_version != RESULT_VERSION
            or type(self.control_id) is not str
            or self.control_id != _CLOSED_PROTOCOL.control_id
            or type(self.terminal_status) is not TerminalStatus
            or type(self.public_claim_permissions) is not tuple
            or self.public_claim_permissions != _CLOSED_PROTOCOL.public_claim_permissions
            or any(
                type(permission) is not ClaimPermission or permission.allowed is not False
                for permission in self.public_claim_permissions
            )
        ):
            _raise_evaluator_error()

        counts = (
            self.worker_invocation_count,
            self.positive_case_pass_count,
            self.negative_case_pass_count,
            self.out_of_contract_case_pass_count,
            self.metamorphic_relation_pass_count,
        )
        if self.terminal_status is TerminalStatus.EXECUTION_FAILED:
            if any(value is not None for value in counts) or self.authorization is not None:
                _raise_evaluator_error()
            return
        if self.terminal_status not in {
            TerminalStatus.QUALIFIED,
            TerminalStatus.NOT_QUALIFIED,
        }:
            _raise_evaluator_error()
        if (
            not _is_count(
                self.worker_invocation_count,
                _CLOSED_PROTOCOL.total_worker_invocations,
            )
            or self.worker_invocation_count != _CLOSED_PROTOCOL.total_worker_invocations
            or not _is_count(self.positive_case_pass_count, _POSITIVE_CASE_COUNT)
            or not _is_count(self.negative_case_pass_count, _NEGATIVE_CASE_COUNT)
            or not _is_count(
                self.out_of_contract_case_pass_count,
                _OUT_OF_CONTRACT_CASE_COUNT,
            )
            or not _is_count(
                self.metamorphic_relation_pass_count,
                _METAMORPHIC_RELATION_COUNT,
            )
        ):
            _raise_evaluator_error()

        all_scientific_gates_passed = (
            self.positive_case_pass_count == _POSITIVE_CASE_COUNT
            and self.negative_case_pass_count == _NEGATIVE_CASE_COUNT
            and self.out_of_contract_case_pass_count == _OUT_OF_CONTRACT_CASE_COUNT
            and self.metamorphic_relation_pass_count == _METAMORPHIC_RELATION_COUNT
        )
        if self.terminal_status is TerminalStatus.QUALIFIED:
            if (
                not all_scientific_gates_passed
                or type(self.authorization) is not C3PassAuthorization
                or self.authorization != _CLOSED_PROTOCOL.c3_pass_authorization
            ):
                _raise_evaluator_error()
        elif all_scientific_gates_passed or self.authorization is not None:
            _raise_evaluator_error()


def _raise_evaluator_error() -> NoReturn:
    raise KP1979V3EvaluatorError from None


def _is_count(value: object, maximum: int) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _technical_result() -> C3AggregateResult:
    return C3AggregateResult(
        result_version=RESULT_VERSION,
        control_id=_CLOSED_PROTOCOL.control_id,
        terminal_status=TerminalStatus.EXECUTION_FAILED,
        worker_invocation_count=None,
        positive_case_pass_count=None,
        negative_case_pass_count=None,
        out_of_contract_case_pass_count=None,
        metamorphic_relation_pass_count=None,
        authorization=None,
        public_claim_permissions=_CLOSED_PROTOCOL.public_claim_permissions,
    )


def _completed_result(
    *,
    positive_case_pass_count: int,
    negative_case_pass_count: int,
    out_of_contract_case_pass_count: int,
    metamorphic_relation_pass_count: int,
) -> C3AggregateResult:
    qualified = (
        positive_case_pass_count == _POSITIVE_CASE_COUNT
        and negative_case_pass_count == _NEGATIVE_CASE_COUNT
        and out_of_contract_case_pass_count == _OUT_OF_CONTRACT_CASE_COUNT
        and metamorphic_relation_pass_count == _METAMORPHIC_RELATION_COUNT
    )
    return C3AggregateResult(
        result_version=RESULT_VERSION,
        control_id=_CLOSED_PROTOCOL.control_id,
        terminal_status=(TerminalStatus.QUALIFIED if qualified else TerminalStatus.NOT_QUALIFIED),
        worker_invocation_count=_CLOSED_PROTOCOL.total_worker_invocations,
        positive_case_pass_count=positive_case_pass_count,
        negative_case_pass_count=negative_case_pass_count,
        out_of_contract_case_pass_count=out_of_contract_case_pass_count,
        metamorphic_relation_pass_count=metamorphic_relation_pass_count,
        authorization=_CLOSED_PROTOCOL.c3_pass_authorization if qualified else None,
        public_claim_permissions=_CLOSED_PROTOCOL.public_claim_permissions,
    )


def _require_counter(value: object, expected: int) -> None:
    if type(value) is not int or value != expected:
        raise _TechnicalFailure


def _validate_completed_sandbox_result(result: object) -> SandboxInvocationResult:
    if (
        type(result) is not SandboxInvocationResult
        or type(result.disposition) is not str
        or result.disposition != "completed"
        or type(result.worker_stdout) is not bytes
        or not result.worker_stdout
        or result.failure_code is not None
        or result.handshake_verified is not True
        or type(result.landlock_abi) is not int
        or result.landlock_abi < MINIMUM_LANDLOCK_ABI
        or result.process_started is not True
        or result.timed_out is not False
        or type(result.captured_stdout_bytes) is not int
        or result.captured_stdout_bytes != len(result.worker_stdout)
        or result.captured_stdout_bytes > MAX_STDOUT_BYTES
        or type(result.captured_stderr_bytes) is not int
        or result.captured_stderr_bytes != 0
    ):
        raise _TechnicalFailure
    return result


@dataclass(slots=True, repr=False)
class _InvocationCursor:
    invoker: C3WorkerInvoker
    next_index: int = 0

    def require_initial(self) -> None:
        _require_counter(self.invoker.started_process_count, 0)
        _require_counter(self.invoker.verified_invocation_count, 0)

    def dispatch(
        self,
        *,
        expected_index: int,
        request_bytes: bytes,
        request_sha256: str,
    ) -> WorkerResponse:
        if (
            type(expected_index) is not int
            or expected_index != self.next_index
            or type(request_bytes) is not bytes
            or not request_bytes
            or not _is_sha256(request_sha256)
            or sha256(request_bytes).hexdigest() != request_sha256
        ):
            raise _TechnicalFailure
        _require_counter(self.invoker.started_process_count, expected_index)
        _require_counter(self.invoker.verified_invocation_count, expected_index)

        sandbox_result = self.invoker(request_bytes)

        _require_counter(self.invoker.started_process_count, expected_index + 1)
        _require_counter(self.invoker.verified_invocation_count, expected_index + 1)
        completed = _validate_completed_sandbox_result(sandbox_result)
        response = decode_worker_response(completed.worker_stdout)
        self.next_index += 1
        return response

    def require_complete(self) -> None:
        if self.next_index != _CLOSED_PROTOCOL.total_worker_invocations:
            raise _TechnicalFailure
        _require_counter(
            self.invoker.started_process_count,
            _CLOSED_PROTOCOL.total_worker_invocations,
        )
        _require_counter(
            self.invoker.verified_invocation_count,
            _CLOSED_PROTOCOL.total_worker_invocations,
        )


_PositiveMatches = dict[tuple[int, int], Prediction]


def _positive_matches(
    response: WorkerResponse,
    certificate: PageLatticeCertificate,
) -> _PositiveMatches | None:
    if type(response) is not WorkerResponse or response.status is not WorkerStatus.PROPOSED:
        return None
    if type(certificate) is not PageLatticeCertificate:
        raise _TechnicalFailure
    if any(
        prediction.y1 - prediction.y0 != _CLOSED_PROTOCOL.intended_prediction_height
        for prediction in response.predictions
    ):
        return None
    truth_slots = certificate.truth_slots
    if type(truth_slots) is not tuple or any(type(slot) is not TruthSlot for slot in truth_slots):
        raise _TechnicalFailure

    matches: _PositiveMatches = {}
    for lane in (0, 1):
        predictions = tuple(
            prediction for prediction in response.predictions if prediction.lane == lane
        )
        references = tuple(
            sorted(
                (slot for slot in truth_slots if slot.lane == lane),
                key=lambda slot: (slot.anchor_y, slot.grid_index),
            )
        )
        if len(predictions) != len(references):
            return None
        for prediction, reference in zip(predictions, references, strict=True):
            anchor_y = prediction.y0 + _PREDICTION_ANCHOR_OFFSET
            if not reference.y0 <= anchor_y < reference.y1:
                return None
            key = (reference.lane, reference.grid_index)
            if key in matches:
                raise _TechnicalFailure
            matches[key] = prediction
    if len(matches) != len(truth_slots):
        return None
    return matches


def _case_passed(case: GeneratedCase, response: WorkerResponse) -> bool:
    if type(case) is not GeneratedCase or type(response) is not WorkerResponse:
        raise _TechnicalFailure
    if case.category is CaseCategory.POSITIVE:
        if case.positive is None:
            raise _TechnicalFailure
        return _positive_matches(response, case.positive) is not None
    if case.category is CaseCategory.NEGATIVE:
        return response.status is WorkerStatus.ABSTAINED
    if case.category is CaseCategory.OUT_OF_CONTRACT:
        return (
            response.status is WorkerStatus.REJECTED
            and response.error_code is case.expected_error_code
        )
    raise _TechnicalFailure


def _prediction_triples(response: WorkerResponse) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (prediction.lane, prediction.y0, prediction.y1) for prediction in response.predictions
    )


def _relation_passed(
    relation: GeneratedRelation,
    first_response: WorkerResponse,
    second_response: WorkerResponse,
    first_matches: _PositiveMatches | None,
    second_matches: _PositiveMatches | None,
) -> bool:
    if (
        type(relation) is not GeneratedRelation
        or type(first_response) is not WorkerResponse
        or type(second_response) is not WorkerResponse
    ):
        raise _TechnicalFailure
    if first_matches is None or second_matches is None:
        return False

    first_predictions = _prediction_triples(first_response)
    second_predictions = _prediction_triples(second_response)
    if relation.kind in _INVARIANT_RELATIONS:
        return first_predictions == second_predictions
    if relation.kind is MetamorphicKind.VERTICAL_PLUS_11:
        return (
            tuple((lane, y0 + 11, y1 + 11) for lane, y0, y1 in first_predictions)
            == second_predictions
        )
    if relation.kind is MetamorphicKind.LANE_SWAP:
        return (
            tuple(sorted((lane ^ 1, y0, y1) for lane, y0, y1 in first_predictions))
            == second_predictions
        )
    if relation.kind is MetamorphicKind.GAP_DELETION:
        if relation.omitted_layer is None:
            raise _TechnicalFailure
        omitted_witnesses = tuple(
            witness
            for witness in relation.endpoints[0].positive.witnesses
            if witness.layer == relation.omitted_layer
        )
        if len(omitted_witnesses) != 1:
            raise _TechnicalFailure
        omitted_witness = omitted_witnesses[0]
        omitted_prediction = first_matches.get((omitted_witness.lane, omitted_witness.grid_index))
        if omitted_prediction is None:
            return False
        return (
            tuple(
                prediction
                for prediction in first_response.predictions
                if prediction != omitted_prediction
            )
            == second_response.predictions
        )
    raise _TechnicalFailure


def _require_closed_roster() -> None:
    validate_protocol(_CLOSED_PROTOCOL)
    categories = tuple(case.category for case in CASE_ROSTER)
    if (
        V3_PROTOCOL is not _CLOSED_PROTOCOL
        or CASE_ROSTER is not _CLOSED_PROTOCOL.cases
        or METAMORPHIC_RELATIONS is not _CLOSED_PROTOCOL.metamorphic_relations
        or _CLOSED_PROTOCOL.case_invocations != CASE_INVOCATIONS
        or _CLOSED_PROTOCOL.metamorphic_endpoint_invocations != METAMORPHIC_ENDPOINT_INVOCATIONS
        or _CLOSED_PROTOCOL.total_worker_invocations != TOTAL_WORKER_INVOCATIONS
        or _CLOSED_PROTOCOL.control_id != CONTROL_ID
        or _CLOSED_PROTOCOL.intended_prediction_height != INTENDED_PREDICTION_HEIGHT
        or _CLOSED_PROTOCOL.c3_pass_authorization != C3_PASS_AUTHORIZATION
        or _CLOSED_PROTOCOL.public_claim_permissions != PUBLIC_CLAIM_PERMISSIONS
        or CASE_INVOCATIONS != 32
        or METAMORPHIC_ENDPOINT_INVOCATIONS != 16
        or TOTAL_WORKER_INVOCATIONS != 48
        or len(METAMORPHIC_RELATIONS) != _METAMORPHIC_RELATION_COUNT
        or categories
        != (
            *(CaseCategory.POSITIVE for _ in range(_POSITIVE_CASE_COUNT)),
            *(CaseCategory.NEGATIVE for _ in range(_NEGATIVE_CASE_COUNT)),
            *(CaseCategory.OUT_OF_CONTRACT for _ in range(_OUT_OF_CONTRACT_CASE_COUNT)),
        )
    ):
        raise _TechnicalFailure


def _evaluate_complete_suite(
    *,
    suite_seed: bytes,
    invoker: C3WorkerInvoker,
) -> C3AggregateResult:
    if type(suite_seed) is not bytes or len(suite_seed) != 32 or not callable(invoker):
        raise _TechnicalFailure
    _require_closed_roster()
    cursor = _InvocationCursor(invoker)
    cursor.require_initial()

    positive_case_pass_count = 0
    negative_case_pass_count = 0
    out_of_contract_case_pass_count = 0
    metamorphic_relation_pass_count = 0

    for ordinal, spec in enumerate(_CLOSED_PROTOCOL.cases):
        case = build_case(suite_seed, ordinal)
        validate_generated_case(case, seed=suite_seed)
        if (
            type(case) is not GeneratedCase
            or case.ordinal != ordinal
            or case.case_id != spec.case_id
            or case.category is not spec.category
            or case.expected_error_code is not spec.expected_error_code
        ):
            raise _TechnicalFailure
        response = cursor.dispatch(
            expected_index=ordinal,
            request_bytes=case.request_bytes,
            request_sha256=case.request_sha256,
        )
        passed = _case_passed(case, response)
        if case.category is CaseCategory.POSITIVE:
            positive_case_pass_count += int(passed)
        elif case.category is CaseCategory.NEGATIVE:
            negative_case_pass_count += int(passed)
        elif case.category is CaseCategory.OUT_OF_CONTRACT:
            out_of_contract_case_pass_count += int(passed)
        else:
            raise _TechnicalFailure

    for ordinal, spec in enumerate(_CLOSED_PROTOCOL.metamorphic_relations):
        relation = build_relation(suite_seed, ordinal)
        validate_generated_relation(relation, seed=suite_seed)
        if (
            type(relation) is not GeneratedRelation
            or relation.ordinal != ordinal
            or relation.relation_id != spec.relation_id
            or relation.kind is not spec.kind
            or tuple(endpoint.endpoint for endpoint in relation.endpoints) != ("a", "b")
        ):
            raise _TechnicalFailure
        first, second = relation.endpoints
        first_index = _CLOSED_PROTOCOL.case_invocations + 2 * ordinal
        first_response = cursor.dispatch(
            expected_index=first_index,
            request_bytes=first.request_bytes,
            request_sha256=first.request_sha256,
        )
        first_matches = _positive_matches(first_response, first.positive)
        second_response = cursor.dispatch(
            expected_index=first_index + 1,
            request_bytes=second.request_bytes,
            request_sha256=second.request_sha256,
        )
        second_matches = _positive_matches(second_response, second.positive)
        metamorphic_relation_pass_count += int(
            _relation_passed(
                relation,
                first_response,
                second_response,
                first_matches,
                second_matches,
            )
        )

    cursor.require_complete()
    return _completed_result(
        positive_case_pass_count=positive_case_pass_count,
        negative_case_pass_count=negative_case_pass_count,
        out_of_contract_case_pass_count=out_of_contract_case_pass_count,
        metamorphic_relation_pass_count=metamorphic_relation_pass_count,
    )


def evaluate_c3_suite(
    *,
    suite_seed: bytes,
    invoker: C3WorkerInvoker,
) -> C3AggregateResult:
    """Stream and evaluate all 48 calls, collapsing technical exceptions."""

    try:
        return _evaluate_complete_suite(suite_seed=suite_seed, invoker=invoker)
    except Exception:
        return _technical_result()


__all__ = [
    "RESULT_VERSION",
    "C3AggregateResult",
    "C3WorkerInvoker",
    "KP1979V3EvaluatorError",
    "evaluate_c3_suite",
]
