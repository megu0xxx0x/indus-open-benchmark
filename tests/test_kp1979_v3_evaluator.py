from __future__ import annotations

import ast
import base64
import json
import unittest
from collections.abc import Sequence
from dataclasses import fields, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.kp1979_v3_evaluator as evaluator
from indusbench.kp1979_v3_evaluator import (
    C3AggregateResult,
    KP1979V3EvaluatorError,
    evaluate_c3_suite,
)
from indusbench.kp1979_v3_generator import (
    GeneratedCase,
    GeneratedEndpoint,
    GeneratedRelation,
    build_case,
    build_relation,
)
from indusbench.kp1979_v3_grammar import (
    NEGATIVE_FAILURE_BY_CASE_ID,
    CompleteWitness,
    InkLayer,
    InkLayerKind,
    NegativeCertificate,
    PageLatticeCertificate,
    RendererInvocation,
    RendererReceipt,
    TruthSlot,
)
from indusbench.kp1979_v3_protocol import (
    C3_PASS_AUTHORIZATION,
    CASE_ROSTER,
    CONTROL_ID,
    METAMORPHIC_RELATIONS,
    PUBLIC_CLAIM_PERMISSIONS,
    RAW_P4_CONTRACT,
    TOTAL_WORKER_INVOCATIONS,
    CaseCategory,
    InputErrorCode,
    MetamorphicKind,
    WorkerStatus,
)
from indusbench.kp1979_v3_sandbox import (
    MAX_STDOUT_BYTES,
    MINIMUM_LANDLOCK_ABI,
    SandboxInvocationResult,
)
from indusbench.kp1979_v3_state import ObservedStatus, TerminalStatus
from indusbench.kp1979_v3_wire import (
    REQUEST_KEYS,
    WORKER_INTERFACE_VERSION,
    Prediction,
    WorkerResponse,
    encode_worker_response,
)

SEED = bytes(range(32))
MODULE_PATH = Path(evaluator.__file__)


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def _request(token: int) -> bytes:
    return _canonical_json(
        {
            "interface_version": WORKER_INTERFACE_VERSION,
            "pbm_base64": base64.b64encode(token.to_bytes(2, "big")).decode("ascii"),
            "width": RAW_P4_CONTRACT.width,
            "height": RAW_P4_CONTRACT.height,
            "scan_bands": [list(band) for band in RAW_P4_CONTRACT.scan_bands],
        }
    )


def _slot(lane: int, grid_index: int, anchor_y: int) -> TruthSlot:
    return TruthSlot(
        lane=lane,
        grid_index=grid_index,
        anchor_y=anchor_y,
        y0=anchor_y - 28,
        y1=anchor_y + 28,
        renderer_id="orthogonal_graph_v1",
        layer_sha256=f"{lane + grid_index + 1:064x}"[-64:],
    )


def _certificate(
    slots: tuple[TruthSlot, ...],
    *,
    witnesses: tuple[CompleteWitness, ...] = (),
    layers: tuple[InkLayer, ...] = (),
) -> PageLatticeCertificate:
    return PageLatticeCertificate(
        pitch=166,
        phase=800,
        witnesses=witnesses,
        truth_slots=slots,
        layers=layers,
    )


def _predictions(certificate: PageLatticeCertificate) -> tuple[Prediction, ...]:
    return tuple(
        sorted(
            (
                Prediction(
                    lane=slot.lane,
                    y0=slot.anchor_y - 48,
                    y1=slot.anchor_y + 48,
                )
                for slot in certificate.truth_slots
            ),
            key=lambda value: (value.lane, value.y0, value.y1),
        )
    )


def _proposed(certificate: PageLatticeCertificate) -> WorkerResponse:
    return WorkerResponse(
        status=WorkerStatus.PROPOSED,
        error_code=None,
        predictions=_predictions(certificate),
    )


def _minimal_layer(layer_id: str) -> InkLayer:
    packed = b"\x80"
    return InkLayer(
        layer_id=layer_id,
        kind=InkLayerKind.COMPLETE_LABEL,
        x0=0,
        y0=0,
        width=1,
        height=1,
        packed=packed,
        packed_sha256=sha256(packed).hexdigest(),
        ink_count=1,
    )


def _minimal_witness(
    *,
    lane: int,
    grid_index: int,
    anchor_y: int,
    layer: InkLayer,
) -> CompleteWitness:
    return CompleteWitness(
        lane=lane,
        grid_index=grid_index,
        jitter=0,
        anchor_y=anchor_y,
        invocation=RendererInvocation(
            renderer_id="orthogonal_graph_v1",
            entropy=bytes(32),
            lane_x0=0,
            lane_x1=260,
            stroke_width=1,
            scale=None,
            shear=None,
            qualifier_variant=0,
            damage_percent=0,
            horizontal_alignment="left",
        ),
        receipt=RendererReceipt(
            renderer_id="orthogonal_graph_v1",
            ink_bbox=(0, 0, 1, 1),
            upper_ink_count=1,
            lower_ink_count=1,
            mutation_delta=0,
        ),
        layer=layer,
    )


def _generated_case(ordinal: int) -> GeneratedCase:
    spec = CASE_ROSTER[ordinal]
    request = _request(ordinal)
    positive: PageLatticeCertificate | None = None
    negative: NegativeCertificate | None = None
    if spec.category is CaseCategory.POSITIVE:
        anchor = 900 + ordinal * 220
        positive = _certificate((_slot(0, 0, anchor), _slot(1, 0, anchor + 70)))
    elif spec.category is CaseCategory.NEGATIVE:
        negative = NegativeCertificate(
            case_id=spec.case_id,
            failure=NEGATIVE_FAILURE_BY_CASE_ID[spec.case_id],
            complete_witnesses=(),
            layers=(),
        )
    return GeneratedCase(
        ordinal=ordinal,
        case_id=spec.case_id,
        category=spec.category,
        generation_commitment=bytes([ordinal]) * 32,
        request_bytes=request,
        request_sha256=sha256(request).hexdigest(),
        pbm_sha256=sha256(ordinal.to_bytes(2, "big")).hexdigest(),
        positive=positive,
        negative=negative,
        expected_error_code=spec.expected_error_code,
    )


def _endpoint(
    relation_ordinal: int,
    endpoint_ordinal: int,
    certificate: PageLatticeCertificate,
) -> GeneratedEndpoint:
    request = _request(100 + relation_ordinal * 2 + endpoint_ordinal)
    return GeneratedEndpoint(
        endpoint=("a", "b")[endpoint_ordinal],
        request_bytes=request,
        request_sha256=sha256(request).hexdigest(),
        pbm_sha256=sha256(bytes([relation_ordinal, endpoint_ordinal])).hexdigest(),
        positive=certificate,
    )


def _generated_relation(ordinal: int) -> GeneratedRelation:
    spec = METAMORPHIC_RELATIONS[ordinal]
    first_anchor = 1100 + ordinal * 300
    first_slots = (_slot(0, 0, first_anchor), _slot(1, 0, first_anchor + 90))
    omitted_layer: InkLayer | None = None
    first_witnesses: tuple[CompleteWitness, ...] = ()
    if spec.kind is MetamorphicKind.VERTICAL_PLUS_11:
        second_slots = tuple(
            _slot(slot.lane, slot.grid_index, slot.anchor_y + 11) for slot in first_slots
        )
    elif spec.kind is MetamorphicKind.LANE_SWAP:
        second_slots = tuple(
            sorted(
                (_slot(slot.lane ^ 1, slot.grid_index, slot.anchor_y) for slot in first_slots),
                key=lambda slot: (slot.lane, slot.grid_index),
            )
        )
    elif spec.kind is MetamorphicKind.GAP_DELETION:
        omitted_layer = _minimal_layer("gap-deletion/slot/0/00")
        first_witnesses = (
            _minimal_witness(
                lane=first_slots[0].lane,
                grid_index=first_slots[0].grid_index,
                anchor_y=first_slots[0].anchor_y,
                layer=omitted_layer,
            ),
        )
        second_slots = (first_slots[1],)
    else:
        second_slots = first_slots
    first_certificate = _certificate(
        first_slots,
        witnesses=first_witnesses,
        layers=((omitted_layer,) if omitted_layer is not None else ()),
    )
    second_certificate = _certificate(second_slots)
    return GeneratedRelation(
        ordinal=ordinal,
        relation_id=spec.relation_id,
        kind=spec.kind,
        generation_commitment=bytes([ordinal + 1]) * 32,
        endpoints=(
            _endpoint(ordinal, 0, first_certificate),
            _endpoint(ordinal, 1, second_certificate),
        ),
        omitted_layer=omitted_layer,
    )


def _synthetic_suite() -> tuple[tuple[GeneratedCase, ...], tuple[GeneratedRelation, ...]]:
    return (
        tuple(_generated_case(ordinal) for ordinal in range(len(CASE_ROSTER))),
        tuple(_generated_relation(ordinal) for ordinal in range(len(METAMORPHIC_RELATIONS))),
    )


def _perfect_responses(
    cases: tuple[GeneratedCase, ...],
    relations: tuple[GeneratedRelation, ...],
) -> list[WorkerResponse]:
    responses: list[WorkerResponse] = []
    for case in cases:
        if case.category is CaseCategory.POSITIVE:
            assert case.positive is not None
            responses.append(_proposed(case.positive))
        elif case.category is CaseCategory.NEGATIVE:
            responses.append(
                WorkerResponse(
                    status=WorkerStatus.ABSTAINED,
                    error_code=None,
                    predictions=(),
                )
            )
        else:
            assert case.expected_error_code is not None
            responses.append(
                WorkerResponse(
                    status=WorkerStatus.REJECTED,
                    error_code=case.expected_error_code,
                    predictions=(),
                )
            )
    for relation in relations:
        responses.extend(_proposed(endpoint.positive) for endpoint in relation.endpoints)
    return responses


def _completed_raw(raw: bytes, **changes: object) -> SandboxInvocationResult:
    values: dict[str, object] = {
        "disposition": "completed",
        "worker_stdout": raw,
        "failure_code": None,
        "handshake_verified": True,
        "landlock_abi": MINIMUM_LANDLOCK_ABI,
        "process_started": True,
        "timed_out": False,
        "captured_stdout_bytes": len(raw),
        "captured_stderr_bytes": 0,
    }
    values.update(changes)
    return SandboxInvocationResult(**cast(Any, values))


def _completed(response: WorkerResponse) -> SandboxInvocationResult:
    return _completed_raw(encode_worker_response(response))


class RecordingInvoker:
    def __init__(
        self,
        outcomes: Sequence[object],
        *,
        events: list[tuple[str, int]] | None = None,
        started_step: int = 1,
        verified_step: int = 1,
    ) -> None:
        self._outcomes = list(outcomes)
        self._events = events
        self._started_step = started_step
        self._verified_step = verified_step
        self.started_process_count = 0
        self.verified_invocation_count = 0
        self.requests: list[bytes] = []

    def __call__(self, request_bytes: bytes, /) -> SandboxInvocationResult:
        index = len(self.requests)
        if self._events is not None:
            self._events.append(("dispatch", index))
        self.requests.append(request_bytes)
        self.started_process_count += self._started_step
        self.verified_invocation_count += self._verified_step
        outcome = self._outcomes.pop(0)
        if type(outcome) is WorkerResponse:
            return _completed(outcome)
        return cast(Any, outcome)


def _run_patched_suite(
    cases: tuple[GeneratedCase, ...],
    relations: tuple[GeneratedRelation, ...],
    invoker: object,
    *,
    events: list[tuple[str, int]] | None = None,
) -> C3AggregateResult:
    def fake_build_case(seed: bytes, ordinal: int) -> GeneratedCase:
        if events is not None:
            events.append(("build_case", ordinal))
        if seed != SEED:
            raise AssertionError
        return cases[ordinal]

    def fake_validate_case(case: GeneratedCase, *, seed: bytes) -> None:
        if events is not None:
            events.append(("validate_case", case.ordinal))
        if seed != SEED:
            raise AssertionError

    def fake_build_relation(seed: bytes, ordinal: int) -> GeneratedRelation:
        if events is not None:
            events.append(("build_relation", ordinal))
        if seed != SEED:
            raise AssertionError
        return relations[ordinal]

    def fake_validate_relation(relation: GeneratedRelation, *, seed: bytes) -> None:
        if events is not None:
            events.append(("validate_relation", relation.ordinal))
        if seed != SEED:
            raise AssertionError

    with (
        patch.object(evaluator, "build_case", side_effect=fake_build_case),
        patch.object(
            evaluator,
            "validate_generated_case",
            side_effect=fake_validate_case,
        ),
        patch.object(
            evaluator,
            "build_relation",
            side_effect=fake_build_relation,
        ),
        patch.object(
            evaluator,
            "validate_generated_relation",
            side_effect=fake_validate_relation,
        ),
    ):
        return evaluate_c3_suite(
            suite_seed=SEED,
            invoker=cast(Any, invoker),
        )


class KP1979V3EvaluatorOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases, self.relations = _synthetic_suite()
        self.responses = _perfect_responses(self.cases, self.relations)

    def test_all_pass_streams_exactly_48_and_qualifies_narrowly(self) -> None:
        events: list[tuple[str, int]] = []
        invoker = RecordingInvoker(self.responses, events=events)
        result = _run_patched_suite(
            self.cases,
            self.relations,
            invoker,
            events=events,
        )

        self.assertIs(TerminalStatus.QUALIFIED, result.terminal_status)
        self.assertEqual(TOTAL_WORKER_INVOCATIONS, result.worker_invocation_count)
        self.assertEqual(12, result.positive_case_pass_count)
        self.assertEqual(14, result.negative_case_pass_count)
        self.assertEqual(6, result.out_of_contract_case_pass_count)
        self.assertEqual(8, result.metamorphic_relation_pass_count)
        self.assertEqual(C3_PASS_AUTHORIZATION, result.authorization)
        self.assertEqual(PUBLIC_CLAIM_PERMISSIONS, result.public_claim_permissions)
        self.assertTrue(
            all(permission.allowed is False for permission in result.public_claim_permissions)
        )
        self.assertEqual(TOTAL_WORKER_INVOCATIONS, len(invoker.requests))
        self.assertEqual(TOTAL_WORKER_INVOCATIONS, invoker.started_process_count)
        self.assertEqual(TOTAL_WORKER_INVOCATIONS, invoker.verified_invocation_count)
        expected_requests = (
            *(case.request_bytes for case in self.cases),
            *(
                endpoint.request_bytes
                for relation in self.relations
                for endpoint in relation.endpoints
            ),
        )
        self.assertEqual(expected_requests, tuple(invoker.requests))

        for request in invoker.requests:
            parsed = json.loads(request)
            self.assertEqual(REQUEST_KEYS, frozenset(parsed))
            self.assertTrue(
                {
                    "seed",
                    "case_id",
                    "relation_id",
                    "truth",
                    "generation_commitment",
                }.isdisjoint(parsed)
            )

        for ordinal in range(32):
            offset = ordinal * 3
            self.assertEqual(
                [
                    ("build_case", ordinal),
                    ("validate_case", ordinal),
                    ("dispatch", ordinal),
                ],
                events[offset : offset + 3],
            )
        relation_offset = 32 * 3
        for ordinal in range(8):
            offset = relation_offset + ordinal * 4
            first_index = 32 + 2 * ordinal
            self.assertEqual(
                [
                    ("build_relation", ordinal),
                    ("validate_relation", ordinal),
                    ("dispatch", first_index),
                    ("dispatch", first_index + 1),
                ],
                events[offset : offset + 4],
            )

    def test_scientific_failure_continues_all_48_and_is_not_qualified(self) -> None:
        self.responses[0] = WorkerResponse(
            status=WorkerStatus.ABSTAINED,
            error_code=None,
            predictions=(),
        )
        invoker = RecordingInvoker(self.responses)
        result = _run_patched_suite(self.cases, self.relations, invoker)

        self.assertIs(TerminalStatus.NOT_QUALIFIED, result.terminal_status)
        self.assertEqual(11, result.positive_case_pass_count)
        self.assertEqual(14, result.negative_case_pass_count)
        self.assertEqual(6, result.out_of_contract_case_pass_count)
        self.assertEqual(8, result.metamorphic_relation_pass_count)
        self.assertIsNone(result.authorization)
        self.assertEqual(48, len(invoker.requests))

    def test_relation_scientific_failure_still_consumes_all_48(self) -> None:
        first_relation_response = self.responses[32]
        first_prediction = first_relation_response.predictions[0]
        self.responses[32] = replace(
            first_relation_response,
            predictions=(
                replace(first_prediction, y1=first_prediction.y1 - 1),
                *first_relation_response.predictions[1:],
            ),
        )
        invoker = RecordingInvoker(self.responses)
        result = _run_patched_suite(self.cases, self.relations, invoker)

        self.assertIs(TerminalStatus.NOT_QUALIFIED, result.terminal_status)
        self.assertEqual(12, result.positive_case_pass_count)
        self.assertEqual(14, result.negative_case_pass_count)
        self.assertEqual(6, result.out_of_contract_case_pass_count)
        self.assertEqual(7, result.metamorphic_relation_pass_count)
        self.assertIsNone(result.authorization)
        self.assertEqual(48, len(invoker.requests))

    def test_later_technical_failure_overrides_scientific_failure(self) -> None:
        self.responses[0] = WorkerResponse(
            status=WorkerStatus.ABSTAINED,
            error_code=None,
            predictions=(),
        )
        outcomes: list[object] = [*self.responses[:-1], _completed_raw(b"{}\n")]
        invoker = RecordingInvoker(outcomes)
        result = _run_patched_suite(self.cases, self.relations, invoker)

        self.assertIs(TerminalStatus.EXECUTION_FAILED, result.terminal_status)
        self.assertEqual(48, len(invoker.requests))
        self.assertTrue(
            all(
                value is None
                for value in (
                    result.worker_invocation_count,
                    result.positive_case_pass_count,
                    result.negative_case_pass_count,
                    result.out_of_contract_case_pass_count,
                    result.metamorphic_relation_pass_count,
                    result.authorization,
                )
            )
        )

    def test_base_exception_propagates_without_dispatch(self) -> None:
        invoker = RecordingInvoker([])
        with (
            patch.object(evaluator, "build_case", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            evaluate_c3_suite(suite_seed=SEED, invoker=invoker)
        self.assertEqual([], invoker.requests)


class KP1979V3EvaluatorCaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases, _ = _synthetic_suite()

    def test_positive_requires_proposed_height_96_and_complete_matching(self) -> None:
        case = self.cases[0]
        assert case.positive is not None
        perfect = _proposed(case.positive)
        self.assertTrue(evaluator._case_passed(case, perfect))

        first = perfect.predictions[0]
        non96 = replace(
            perfect,
            predictions=(
                replace(first, y1=first.y1 - 1),
                *perfect.predictions[1:],
            ),
        )
        missing = replace(perfect, predictions=perfect.predictions[:-1])
        extra = replace(
            perfect,
            predictions=(
                *perfect.predictions,
                Prediction(lane=1, y0=4000, y1=4096),
            ),
        )
        wrong_lane = replace(
            perfect,
            predictions=(
                replace(first, lane=1),
                *perfect.predictions[1:],
            ),
        )
        abstained = WorkerResponse(WorkerStatus.ABSTAINED, None, ())
        rejected = WorkerResponse(
            WorkerStatus.REJECTED,
            InputErrorCode.INVALID_DIMENSIONS,
            (),
        )
        for label, response in (
            ("non96", non96),
            ("missing", missing),
            ("extra", extra),
            ("wrong-lane", wrong_lane),
            ("abstained", abstained),
            ("rejected", rejected),
        ):
            with self.subTest(label=label):
                self.assertFalse(evaluator._case_passed(case, response))

    def test_anchor_uses_half_open_truth_interval(self) -> None:
        case = self.cases[0]
        assert case.positive is not None
        first_slot, second_slot = case.positive.truth_slots
        accepted = WorkerResponse(
            WorkerStatus.PROPOSED,
            None,
            (
                Prediction(0, first_slot.y1 - 1 - 48, first_slot.y1 - 1 + 48),
                Prediction(1, second_slot.y0 - 48, second_slot.y0 + 48),
            ),
        )
        outside = replace(
            accepted,
            predictions=(
                Prediction(0, first_slot.y1 - 48, first_slot.y1 + 48),
                accepted.predictions[1],
            ),
        )
        self.assertTrue(evaluator._case_passed(case, accepted))
        self.assertFalse(evaluator._case_passed(case, outside))

    def test_negative_requires_exact_abstention(self) -> None:
        case = self.cases[12]
        self.assertTrue(
            evaluator._case_passed(
                case,
                WorkerResponse(WorkerStatus.ABSTAINED, None, ()),
            )
        )
        self.assertFalse(
            evaluator._case_passed(
                case,
                WorkerResponse(
                    WorkerStatus.PROPOSED,
                    None,
                    (Prediction(0, 100, 196),),
                ),
            )
        )
        self.assertFalse(
            evaluator._case_passed(
                case,
                WorkerResponse(
                    WorkerStatus.REJECTED,
                    InputErrorCode.INVALID_DIMENSIONS,
                    (),
                ),
            )
        )

    def test_each_ooc_requires_its_exact_rejection_code(self) -> None:
        for case in self.cases[26:32]:
            assert case.expected_error_code is not None
            with self.subTest(case=case.case_id):
                self.assertTrue(
                    evaluator._case_passed(
                        case,
                        WorkerResponse(
                            WorkerStatus.REJECTED,
                            case.expected_error_code,
                            (),
                        ),
                    )
                )
                wrong_code = next(
                    code for code in InputErrorCode if code is not case.expected_error_code
                )
                self.assertFalse(
                    evaluator._case_passed(
                        case,
                        WorkerResponse(WorkerStatus.REJECTED, wrong_code, ()),
                    )
                )
                self.assertFalse(
                    evaluator._case_passed(
                        case,
                        WorkerResponse(WorkerStatus.ABSTAINED, None, ()),
                    )
                )
                self.assertFalse(
                    evaluator._case_passed(
                        case,
                        WorkerResponse(
                            WorkerStatus.PROPOSED,
                            None,
                            (Prediction(0, 100, 196),),
                        ),
                    )
                )


class KP1979V3EvaluatorRelationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        _, self.relations = _synthetic_suite()

    def _evaluate(
        self,
        relation: GeneratedRelation,
        first_response: WorkerResponse,
        second_response: WorkerResponse,
    ) -> bool:
        return evaluator._relation_passed(
            relation,
            first_response,
            second_response,
            evaluator._positive_matches(
                first_response,
                relation.endpoints[0].positive,
            ),
            evaluator._positive_matches(
                second_response,
                relation.endpoints[1].positive,
            ),
        )

    def test_all_eight_exact_relations_pass(self) -> None:
        for relation in self.relations:
            with self.subTest(kind=relation.kind):
                self.assertTrue(
                    self._evaluate(
                        relation,
                        _proposed(relation.endpoints[0].positive),
                        _proposed(relation.endpoints[1].positive),
                    )
                )

    def test_each_relation_rejects_an_endpoint_valid_off_by_one(self) -> None:
        for relation in self.relations:
            first_response = _proposed(relation.endpoints[0].positive)
            second_response = _proposed(relation.endpoints[1].positive)
            first_prediction = second_response.predictions[0]
            shifted = replace(
                second_response,
                predictions=(
                    replace(
                        first_prediction,
                        y0=first_prediction.y0 + 1,
                        y1=first_prediction.y1 + 1,
                    ),
                    *second_response.predictions[1:],
                ),
            )
            with self.subTest(kind=relation.kind):
                self.assertIsNotNone(
                    evaluator._positive_matches(
                        shifted,
                        relation.endpoints[1].positive,
                    )
                )
                self.assertFalse(self._evaluate(relation, first_response, shifted))

    def test_paired_noncentral_predictions_can_satisfy_an_exact_relation(self) -> None:
        relation = self.relations[0]
        first_response = _proposed(relation.endpoints[0].positive)
        shifted = replace(
            first_response,
            predictions=tuple(
                replace(
                    prediction,
                    y0=prediction.y0 + 1,
                    y1=prediction.y1 + 1,
                )
                for prediction in first_response.predictions
            ),
        )
        self.assertIsNotNone(
            evaluator._positive_matches(
                shifted,
                relation.endpoints[0].positive,
            )
        )
        self.assertIsNotNone(
            evaluator._positive_matches(
                shifted,
                relation.endpoints[1].positive,
            )
        )
        self.assertTrue(self._evaluate(relation, shifted, shifted))

    def test_equal_non96_or_equal_abstention_cannot_pass_identical(self) -> None:
        relation = self.relations[0]
        first = _proposed(relation.endpoints[0].positive)
        prediction = first.predictions[0]
        non96 = replace(
            first,
            predictions=(
                replace(prediction, y1=prediction.y1 - 1),
                *first.predictions[1:],
            ),
        )
        abstained = WorkerResponse(WorkerStatus.ABSTAINED, None, ())
        self.assertFalse(self._evaluate(relation, non96, non96))
        self.assertFalse(self._evaluate(relation, abstained, abstained))


class KP1979V3EvaluatorTechnicalFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases, self.relations = _synthetic_suite()
        self.responses = _perfect_responses(self.cases, self.relations)

    def _assert_execution_failed(self, result: C3AggregateResult) -> None:
        self.assertIs(TerminalStatus.EXECUTION_FAILED, result.terminal_status)
        self.assertEqual(CONTROL_ID, result.control_id)
        self.assertEqual(PUBLIC_CLAIM_PERMISSIONS, result.public_claim_permissions)
        self.assertFalse(any(item.allowed for item in result.public_claim_permissions))
        self.assertIsNone(result.worker_invocation_count)
        self.assertIsNone(result.positive_case_pass_count)
        self.assertIsNone(result.negative_case_pass_count)
        self.assertIsNone(result.out_of_contract_case_pass_count)
        self.assertIsNone(result.metamorphic_relation_pass_count)
        self.assertIsNone(result.authorization)

    def test_invalid_seed_or_invoker_fails_before_dispatch(self) -> None:
        for seed in (b"", bytes(31), bytes(33), True):
            invoker = RecordingInvoker([])
            with self.subTest(seed=seed):
                result = evaluate_c3_suite(
                    suite_seed=cast(Any, seed),
                    invoker=invoker,
                )
                self._assert_execution_failed(result)
                self.assertEqual([], invoker.requests)
        result = evaluate_c3_suite(
            suite_seed=SEED,
            invoker=cast(Any, object()),
        )
        self._assert_execution_failed(result)

    def test_closed_schedule_and_initial_counters_are_required(self) -> None:
        invoker = RecordingInvoker(self.responses)
        with patch.object(evaluator, "CASE_INVOCATIONS", 31):
            result = _run_patched_suite(self.cases, self.relations, invoker)
        self._assert_execution_failed(result)
        self.assertEqual([], invoker.requests)

        for field in ("started_process_count", "verified_invocation_count"):
            for value in (1, True):
                invoker = RecordingInvoker(self.responses)
                setattr(invoker, field, value)
                with self.subTest(field=field, value=value):
                    result = _run_patched_suite(self.cases, self.relations, invoker)
                    self._assert_execution_failed(result)
                    self.assertEqual([], invoker.requests)

    def test_protocol_aliases_and_frozen_taxonomy_fail_closed(self) -> None:
        alias_attacks = (
            (
                "case-roster-copy",
                "CASE_ROSTER",
                tuple(list(evaluator.CASE_ROSTER)),
            ),
            (
                "relation-roster-copy",
                "METAMORPHIC_RELATIONS",
                tuple(list(evaluator.METAMORPHIC_RELATIONS)),
            ),
            ("case-count", "CASE_INVOCATIONS", 31),
            ("endpoint-count", "METAMORPHIC_ENDPOINT_INVOCATIONS", 15),
            ("total-count", "TOTAL_WORKER_INVOCATIONS", 47),
            ("prediction-height", "INTENDED_PREDICTION_HEIGHT", 95),
            ("control-id", "CONTROL_ID", "unexpected-control"),
            ("authorization", "C3_PASS_AUTHORIZATION", object()),
            ("claim-boundary", "PUBLIC_CLAIM_PERMISSIONS", ()),
        )
        for label, attribute, value in alias_attacks:
            invoker = RecordingInvoker(self.responses)
            with self.subTest(label=label), patch.object(evaluator, attribute, value):
                result = _run_patched_suite(self.cases, self.relations, invoker)
                self._assert_execution_failed(result)
                self.assertEqual([], invoker.requests)

        wrong_ooc_code = next(
            code
            for code in InputErrorCode
            if code is not evaluator.V3_PROTOCOL.cases[26].expected_error_code
        )
        changed_cases = (
            *evaluator.V3_PROTOCOL.cases[:26],
            replace(
                evaluator.V3_PROTOCOL.cases[26],
                expected_error_code=wrong_ooc_code,
            ),
            *evaluator.V3_PROTOCOL.cases[27:],
        )
        first_relation = evaluator.V3_PROTOCOL.metamorphic_relations[0]
        vertical_relation = evaluator.V3_PROTOCOL.metamorphic_relations[2]
        protocol_attacks = (
            (
                "ooc-error-map",
                replace(evaluator.V3_PROTOCOL, cases=changed_cases),
            ),
            (
                "relation-kind",
                replace(
                    evaluator.V3_PROTOCOL,
                    metamorphic_relations=(
                        replace(
                            first_relation,
                            kind=MetamorphicKind.UNREAD_MARGIN,
                        ),
                        *evaluator.V3_PROTOCOL.metamorphic_relations[1:],
                    ),
                ),
            ),
            (
                "vertical-delta",
                replace(
                    evaluator.V3_PROTOCOL,
                    metamorphic_relations=(
                        *evaluator.V3_PROTOCOL.metamorphic_relations[:2],
                        replace(
                            vertical_relation,
                            kind=MetamorphicKind.IDENTICAL,
                            vertical_delta=None,
                        ),
                        *evaluator.V3_PROTOCOL.metamorphic_relations[3:],
                    ),
                ),
            ),
        )
        for label, protocol in protocol_attacks:
            invoker = RecordingInvoker(self.responses)
            with (
                self.subTest(label=label),
                patch.object(
                    evaluator,
                    "V3_PROTOCOL",
                    protocol,
                ),
            ):
                result = _run_patched_suite(self.cases, self.relations, invoker)
                self._assert_execution_failed(result)
                self.assertEqual([], invoker.requests)

    def test_generator_and_validator_exceptions_are_detail_free(self) -> None:
        invoker = RecordingInvoker(self.responses)
        with patch.object(
            evaluator,
            "build_case",
            side_effect=RuntimeError("generator-secret-detail"),
        ):
            result = evaluate_c3_suite(suite_seed=SEED, invoker=invoker)
        self._assert_execution_failed(result)
        self.assertNotIn("generator-secret-detail", repr(result))

        with (
            patch.object(evaluator, "build_case", return_value=self.cases[0]),
            patch.object(
                evaluator,
                "validate_generated_case",
                side_effect=RuntimeError("validator-secret-detail"),
            ),
        ):
            result = evaluate_c3_suite(
                suite_seed=SEED,
                invoker=RecordingInvoker(self.responses),
            )
        self._assert_execution_failed(result)
        self.assertNotIn("validator-secret-detail", repr(result))

    def test_invoker_exception_is_detail_free(self) -> None:
        class RaisingInvoker:
            started_process_count = 0
            verified_invocation_count = 0

            def __init__(self) -> None:
                self.requests: list[bytes] = []

            def __call__(self, request_bytes: bytes, /) -> SandboxInvocationResult:
                self.requests.append(request_bytes)
                self.started_process_count += 1
                self.verified_invocation_count += 1
                raise RuntimeError("invoker-secret-detail")

        invoker = RaisingInvoker()
        result = _run_patched_suite(self.cases, self.relations, invoker)
        self._assert_execution_failed(result)
        self.assertEqual(1, len(invoker.requests))
        self.assertNotIn("invoker-secret-detail", repr(result))

    def test_case_identity_and_digest_are_independently_exact(self) -> None:
        first = self.cases[0]
        mutations: tuple[tuple[str, object], ...] = (
            ("wrong-type", object()),
            ("ordinal", replace(first, ordinal=1)),
            ("case-id", replace(first, case_id="unexpected-case")),
            ("category", replace(first, category=CaseCategory.NEGATIVE)),
            (
                "expected-code",
                replace(
                    first,
                    expected_error_code=InputErrorCode.INVALID_DIMENSIONS,
                ),
            ),
            ("request-type", replace(first, request_bytes=cast(Any, "not-bytes"))),
            ("request-digest", replace(first, request_sha256="0" * 64)),
        )
        for label, case in mutations:
            changed = cast(tuple[GeneratedCase, ...], (case, *self.cases[1:]))
            invoker = RecordingInvoker(self.responses)
            with self.subTest(label=label):
                result = _run_patched_suite(changed, self.relations, invoker)
                self._assert_execution_failed(result)
                self.assertEqual([], invoker.requests)

    def test_relation_identity_endpoints_and_digests_are_independently_exact(
        self,
    ) -> None:
        first = self.relations[0]
        first_endpoint, second_endpoint = first.endpoints
        different_kind = METAMORPHIC_RELATIONS[1].kind
        mutations: tuple[tuple[str, object, int], ...] = (
            ("wrong-type", object(), 32),
            ("ordinal", replace(first, ordinal=1), 32),
            ("relation-id", replace(first, relation_id="unexpected-relation"), 32),
            ("kind", replace(first, kind=different_kind), 32),
            (
                "endpoint-order",
                replace(first, endpoints=(second_endpoint, first_endpoint)),
                32,
            ),
            (
                "endpoint-name",
                replace(
                    first,
                    endpoints=(
                        replace(first_endpoint, endpoint="unexpected"),
                        second_endpoint,
                    ),
                ),
                32,
            ),
            (
                "endpoint-type",
                replace(
                    first,
                    endpoints=cast(
                        Any,
                        (object(), second_endpoint),
                    ),
                ),
                32,
            ),
            (
                "first-request-digest",
                replace(
                    first,
                    endpoints=(
                        replace(first_endpoint, request_sha256="0" * 64),
                        second_endpoint,
                    ),
                ),
                32,
            ),
            (
                "second-request-digest",
                replace(
                    first,
                    endpoints=(
                        first_endpoint,
                        replace(second_endpoint, request_sha256="0" * 64),
                    ),
                ),
                33,
            ),
        )
        for label, relation, request_count in mutations:
            changed = cast(
                tuple[GeneratedRelation, ...],
                (relation, *self.relations[1:]),
            )
            invoker = RecordingInvoker(self.responses)
            with self.subTest(label=label):
                result = _run_patched_suite(self.cases, changed, invoker)
                self._assert_execution_failed(result)
                self.assertEqual(request_count, len(invoker.requests))

    def test_every_sandbox_result_field_is_strictly_validated(self) -> None:
        raw = encode_worker_response(self.responses[0])
        valid = _completed_raw(raw)
        oversize = b"x" * (MAX_STDOUT_BYTES + 1)
        invalid_results: tuple[tuple[str, object], ...] = (
            ("result-type", object()),
            ("disposition-type", replace(valid, disposition=cast(Any, 1))),
            ("disposition-value", replace(valid, disposition="transport_failure")),
            ("stdout-type", replace(valid, worker_stdout=cast(Any, "not-bytes"))),
            (
                "stdout-empty",
                replace(valid, worker_stdout=b"", captured_stdout_bytes=0),
            ),
            ("failure-code", replace(valid, failure_code="timeout")),
            ("handshake", replace(valid, handshake_verified=False)),
            ("landlock-none", replace(valid, landlock_abi=None)),
            (
                "landlock-below-minimum",
                replace(valid, landlock_abi=MINIMUM_LANDLOCK_ABI - 1),
            ),
            ("landlock-bool", replace(valid, landlock_abi=True)),
            ("process-started", replace(valid, process_started=False)),
            ("timed-out", replace(valid, timed_out=True)),
            (
                "stdout-count-bool",
                replace(valid, captured_stdout_bytes=cast(Any, True)),
            ),
            (
                "stdout-count-mismatch",
                replace(valid, captured_stdout_bytes=len(raw) - 1),
            ),
            (
                "stdout-oversize",
                replace(
                    valid,
                    worker_stdout=oversize,
                    captured_stdout_bytes=len(oversize),
                ),
            ),
            (
                "stderr-count-bool",
                replace(valid, captured_stderr_bytes=cast(Any, False)),
            ),
            ("stderr-count", replace(valid, captured_stderr_bytes=1)),
        )
        for label, invalid in invalid_results:
            with self.subTest(label=label):
                invoker = RecordingInvoker([invalid])
                result = _run_patched_suite(self.cases, self.relations, invoker)
                self._assert_execution_failed(result)
                self.assertEqual(1, len(invoker.requests))

    def test_malformed_worker_response_representatives_are_technical(self) -> None:
        valid_raw = encode_worker_response(self.responses[0])
        valid_payload = json.loads(valid_raw)
        wrong_algorithm = _canonical_json({**valid_payload, "algorithm_id": "unexpected-algorithm"})
        wrong_interface = _canonical_json(
            {**valid_payload, "interface_version": "unexpected-interface"}
        )
        extra_field = _canonical_json({**valid_payload, "unexpected": 1})
        duplicate_key = valid_raw[:-2] + b',"status":"proposed"}\n'
        malformed = (
            b"{}\n",
            wrong_algorithm,
            wrong_interface,
            extra_field,
            duplicate_key,
        )
        for raw in malformed:
            with self.subTest(raw=raw[:40]):
                invoker = RecordingInvoker([_completed_raw(raw)])
                result = _run_patched_suite(self.cases, self.relations, invoker)
                self._assert_execution_failed(result)
                self.assertEqual(1, len(invoker.requests))

    def test_each_post_call_counter_and_final_counter_are_exact(self) -> None:
        for field, invoker in (
            (
                "started",
                RecordingInvoker(self.responses, started_step=0),
            ),
            (
                "verified",
                RecordingInvoker(self.responses, verified_step=0),
            ),
        ):
            with self.subTest(field=field):
                result = _run_patched_suite(self.cases, self.relations, invoker)
                self._assert_execution_failed(result)
                self.assertEqual(1, len(invoker.requests))

        class FinalCounterTamperInvoker:
            def __init__(self, responses: Sequence[WorkerResponse]) -> None:
                self._responses = list(responses)
                self._started_process_count = 0
                self._final_started_reads = 0
                self.verified_invocation_count = 0
                self.requests: list[bytes] = []

            @property
            def started_process_count(self) -> int:
                if self._started_process_count == TOTAL_WORKER_INVOCATIONS:
                    self._final_started_reads += 1
                    if self._final_started_reads > 1:
                        return TOTAL_WORKER_INVOCATIONS - 1
                return self._started_process_count

            def __call__(self, request_bytes: bytes, /) -> SandboxInvocationResult:
                self.requests.append(request_bytes)
                self._started_process_count += 1
                self.verified_invocation_count += 1
                return _completed(self._responses.pop(0))

        final_invoker = FinalCounterTamperInvoker(self.responses)
        result = _run_patched_suite(
            self.cases,
            self.relations,
            final_invoker,
        )
        self._assert_execution_failed(result)
        self.assertEqual(48, len(final_invoker.requests))

    def test_aggregate_dataclass_rejects_inconsistent_closed_states(self) -> None:
        qualified = _run_patched_suite(
            self.cases,
            self.relations,
            RecordingInvoker(self.responses),
        )
        base: dict[str, object] = {
            field.name: getattr(qualified, field.name) for field in fields(C3AggregateResult)
        }
        invalid_overrides = (
            {"result_version": True},
            {"terminal_status": ObservedStatus.ABSENT},
            {"terminal_status": cast(Any, "started")},
            {"terminal_status": TerminalStatus.CONSUMED_INCOMPLETE},
            {"positive_case_pass_count": 11},
            {"positive_case_pass_count": True},
            {"positive_case_pass_count": -1},
            {"positive_case_pass_count": 13},
            {"negative_case_pass_count": True},
            {"negative_case_pass_count": -1},
            {"negative_case_pass_count": 15},
            {"out_of_contract_case_pass_count": True},
            {"out_of_contract_case_pass_count": -1},
            {"out_of_contract_case_pass_count": 7},
            {"metamorphic_relation_pass_count": True},
            {"metamorphic_relation_pass_count": -1},
            {"metamorphic_relation_pass_count": 9},
            {"worker_invocation_count": True},
            {"worker_invocation_count": 47},
            {"worker_invocation_count": 49},
            {"authorization": None},
            {"authorization": cast(Any, object())},
            {"public_claim_permissions": ()},
            {"terminal_status": TerminalStatus.EXECUTION_FAILED},
        )
        for override in invalid_overrides:
            values = {**base, **override}
            with self.subTest(override=override), self.assertRaises(KP1979V3EvaluatorError):
                C3AggregateResult(**cast(Any, values))

        not_qualified = {
            **base,
            "terminal_status": TerminalStatus.NOT_QUALIFIED,
            "positive_case_pass_count": 11,
            "authorization": None,
        }
        C3AggregateResult(**cast(Any, not_qualified))
        for override in (
            {"positive_case_pass_count": 12},
            {"authorization": C3_PASS_AUTHORIZATION},
        ):
            with (
                self.subTest(not_qualified_override=override),
                self.assertRaises(KP1979V3EvaluatorError),
            ):
                C3AggregateResult(
                    **cast(
                        Any,
                        {
                            **not_qualified,
                            **override,
                        },
                    )
                )

        with (
            patch.object(evaluator, "CONTROL_ID", "unexpected-control"),
            patch.object(evaluator, "TOTAL_WORKER_INVOCATIONS", 47),
            patch.object(evaluator, "C3_PASS_AUTHORIZATION", object()),
            patch.object(evaluator, "PUBLIC_CLAIM_PERMISSIONS", ()),
        ):
            rebuilt = C3AggregateResult(**cast(Any, base))
            self.assertIs(TerminalStatus.QUALIFIED, rebuilt.terminal_status)
            self.assertEqual(CONTROL_ID, rebuilt.control_id)
            self.assertEqual(
                PUBLIC_CLAIM_PERMISSIONS,
                rebuilt.public_claim_permissions,
            )
            with self.assertRaises(KP1979V3EvaluatorError):
                C3AggregateResult(
                    **cast(
                        Any,
                        {
                            **base,
                            "worker_invocation_count": 47,
                        },
                    )
                )


class KP1979V3EvaluatorBoundaryTests(unittest.TestCase):
    def test_public_result_has_only_aggregate_and_policy_fields(self) -> None:
        self.assertEqual(
            {
                "result_version",
                "control_id",
                "terminal_status",
                "worker_invocation_count",
                "positive_case_pass_count",
                "negative_case_pass_count",
                "out_of_contract_case_pass_count",
                "metamorphic_relation_pass_count",
                "authorization",
                "public_claim_permissions",
            },
            {field.name for field in fields(C3AggregateResult)},
        )
        forbidden = (
            "case_id",
            "relation_id",
            "prediction",
            "truth",
            "stdout",
            "request",
            "pbm",
            "seed",
            "digest",
            "error_code",
            "generation_commitment",
        )
        for field in fields(C3AggregateResult):
            for fragment in forbidden:
                self.assertNotIn(fragment, field.name)

    def test_qualified_authorization_and_claim_boundary_are_exact(self) -> None:
        cases, relations = _synthetic_suite()
        result = _run_patched_suite(
            cases,
            relations,
            RecordingInvoker(_perfect_responses(cases, relations)),
        )
        assert result.authorization is not None
        self.assertEqual(
            (22, 77), (result.authorization.first_page, result.authorization.last_page)
        )
        self.assertTrue(result.authorization.owner_only)
        self.assertTrue(result.authorization.provisional_candidates_only)
        self.assertFalse(result.authorization.page_78_allowed)
        self.assertEqual(PUBLIC_CLAIM_PERMISSIONS, result.public_claim_permissions)
        self.assertFalse(any(permission.allowed for permission in result.public_claim_permissions))
        rendered = repr(result)
        for fragment in (
            "prediction",
            "truth",
            "stdout",
            "request",
            "seed",
            "digest",
            "generation_commitment",
        ):
            self.assertNotIn(fragment, rendered)

    def test_module_has_no_persistence_or_forbidden_dependency(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        for fragment in (
            "detector",
            "freeze",
            "quicknet",
            "kp1979_v2",
            "real_source",
            "label_scoring",
        ):
            self.assertNotIn(fragment, source.lower())
        self.assertTrue(
            {
                "json",
                "os",
                "pathlib",
                "socket",
                "subprocess",
                "tempfile",
            }.isdisjoint(imports)
        )
        self.assertNotIn("iter_schedule", source)
        self.assertNotIn("build_suite_manifest", source)
        self.assertNotIn("SuiteManifest", source)
        self.assertIn("self.invoker(request_bytes)", source)


class KP1979V3EvaluatorRealGeneratorSmokeTests(unittest.TestCase):
    def test_real_case_categories_and_vertical_relation_feed_science_helpers(self) -> None:
        positive = build_case(SEED, 0)
        negative = build_case(SEED, 12)
        ooc = build_case(SEED, 26)
        relation = build_relation(SEED, 2)
        lane_swap = build_relation(SEED, 6)
        gap_deletion = build_relation(SEED, 7)
        assert positive.positive is not None
        assert ooc.expected_error_code is not None

        self.assertTrue(evaluator._case_passed(positive, _proposed(positive.positive)))
        self.assertTrue(
            evaluator._case_passed(
                negative,
                WorkerResponse(WorkerStatus.ABSTAINED, None, ()),
            )
        )
        self.assertTrue(
            evaluator._case_passed(
                ooc,
                WorkerResponse(WorkerStatus.REJECTED, ooc.expected_error_code, ()),
            )
        )
        first_response = _proposed(relation.endpoints[0].positive)
        second_response = _proposed(relation.endpoints[1].positive)
        self.assertTrue(
            evaluator._relation_passed(
                relation,
                first_response,
                second_response,
                evaluator._positive_matches(
                    first_response,
                    relation.endpoints[0].positive,
                ),
                evaluator._positive_matches(
                    second_response,
                    relation.endpoints[1].positive,
                ),
            )
        )
        for relation in (lane_swap, gap_deletion):
            first_response = _proposed(relation.endpoints[0].positive)
            second_response = _proposed(relation.endpoints[1].positive)
            with self.subTest(kind=relation.kind):
                self.assertTrue(
                    evaluator._relation_passed(
                        relation,
                        first_response,
                        second_response,
                        evaluator._positive_matches(
                            first_response,
                            relation.endpoints[0].positive,
                        ),
                        evaluator._positive_matches(
                            second_response,
                            relation.endpoints[1].positive,
                        ),
                    )
                )


if __name__ == "__main__":
    unittest.main()
