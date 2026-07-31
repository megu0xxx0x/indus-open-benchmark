from __future__ import annotations

import ast
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from inspect import isgenerator
from pathlib import Path
from unittest.mock import patch

import indusbench.kp1979_v3_generator as generator_module
import indusbench.kp1979_v3_grammar as grammar_module
from indusbench.kp1979_v3_generator import (
    SUITE_DOMAIN_LABEL,
    GeneratedEndpoint,
    KP1979V3GeneratorError,
    build_case,
    build_relation,
    iter_schedule,
    validate_generated_case,
    validate_generated_relation,
)
from indusbench.kp1979_v3_grammar import (
    GENERATOR_MAXIMUM_JITTER,
    MAXIMUM_PAGE_LAYERS,
    NEGATIVE_FAILURE_BY_CASE_ID,
    InkLayer,
    InkLayerKind,
    KP1979V3GrammarError,
    NegativeFailure,
    PageLatticeCertificate,
    _validate_negative_certificate_structure,
    compose_pbm,
    validate_page_composition,
    validate_page_lattice,
)
from indusbench.kp1979_v3_prf import derive_subseed
from indusbench.kp1979_v3_protocol import (
    CASE_ROSTER,
    METAMORPHIC_RELATIONS,
    RAW_P4_CONTRACT,
    SYNTHETIC_SCAN_BANDS,
    TOTAL_WORKER_INVOCATIONS,
    CaseCategory,
    InputErrorCode,
)
from indusbench.kp1979_v3_wire import (
    KP1979V3WorkerInputError,
    decode_worker_request,
    decode_worker_request_envelope,
    encode_worker_request,
)

SEED = bytes(range(32))
REQUEST_KEYS = {
    "height",
    "interface_version",
    "pbm_base64",
    "scan_bands",
    "width",
}
NEGATIVE_PBM_SHA256 = (
    "a85bc5797a8097f7d6c91f47a834f9f9f5ce15faf53e8626fd612e79cc3bc5ce",
    "f0412598fd6f2bcb2796183d96d74d2d633459fe72848dd195962272100bbc56",
    "93644648d1a16fec4d5e81e9fda657b16809ccf740541896a42751fb48dc8d87",
    "aefbeee15bcea539dd1c66a08fae190211732a40357baf7396233f74a3698125",
    "1ce8f1a9438626e1859bf9d4d56d28ed8a1f573b7ee89fe3f8b76949016c3055",
    "94e4e3ca85b040fe55346028655c6457c7d4d33f60f24055a6ec3dec5f4ff581",
    "3f85a9842c93bf3f0bc2df6e180516d3bd9408a88f0f025a606fa188131d1c4b",
    "91eafd5f2e3a8b65b7c386b45ef0d86f10a346e8f275a347e705d5d3d2268156",
    "02939fde2c0358445d49bac46bb22df1213e407ad58519b21a7476d99d6117ab",
    "28482f91aded83c3c5163efbb246293037b06081febbfb656e5f58aee4b3415e",
    "a94880ab0d0ec6196172a8ac72e2816fee58eb8b310d6c1073d29fe6c8c3f3bf",
    "7fa4c1ef25dda0c533ff5b7e871fe55e17388d684799633ee9f6b4b0a1ebc5b1",
    "3d33af100102c7a4fae510b4932abba7605bda0d62bd478afbfd829f0a739439",
    "614570e4b450b7c7993274a3fd236de161e2a2979ccb101383ad919bc6197498",
)


def _request_pbm(request_bytes: bytes) -> bytes:
    return decode_worker_request(request_bytes).pbm


def _ink_points(pbm: bytes) -> frozenset[tuple[int, int]]:
    payload = pbm[len(RAW_P4_CONTRACT.header) :]
    points: set[tuple[int, int]] = set()
    for byte_index, value in enumerate(payload):
        if not value:
            continue
        y, x_byte = divmod(byte_index, RAW_P4_CONTRACT.row_bytes)
        for bit in range(8):
            if value & (0x80 >> bit):
                points.add((8 * x_byte + bit, y))
    return frozenset(points)


def _band_points(pbm: bytes, lane: int) -> frozenset[tuple[int, int]]:
    x0, y0, x1, y1 = SYNTHETIC_SCAN_BANDS[lane]
    return frozenset((x - x0, y - y0) for x, y in _ink_points(pbm) if x0 <= x < x1 and y0 <= y < y1)


def _layer_points(layer: InkLayer) -> frozenset[tuple[int, int]]:
    row_bytes = (layer.width + 7) // 8
    return frozenset(
        (layer.x0 + x, layer.y0 + y)
        for y in range(layer.height)
        for x in range(layer.width)
        if layer.packed[y * row_bytes + x // 8] & (0x80 >> (x % 8))
    )


class KP1979V3GeneratorTests(unittest.TestCase):
    def test_domain_separation_vectors_are_exact(self) -> None:
        suite_seed = derive_subseed(SEED, SUITE_DOMAIN_LABEL)
        case_seed = derive_subseed(
            suite_seed,
            "case/00/positive-renderer-a-clean",
        )
        relation_seed = derive_subseed(suite_seed, "relation/07/gap-deletion")
        slot_seed = derive_subseed(
            case_seed,
            "slot/0/00/orthogonal_graph_v1",
        )
        self.assertEqual(
            suite_seed.hex(),
            "2bb2d87c0b3d096631e615080f01878eed7a627ee908f5aaf7c4a4839a12871f",
        )
        self.assertEqual(
            case_seed.hex(),
            "78d49f53df82d62feeb1f2784c6e87b8a021132c55faef06b89aea163dcca497",
        )
        self.assertEqual(
            relation_seed.hex(),
            "f3b12bc1d40e41e2374cdf7dee599f5987f7b34f896e6a7fbdd716b2cb0e9d64",
        )
        self.assertEqual(
            slot_seed.hex(),
            "e6edb0236a6ef581927c6bf68dd8d598c1e28f83685e4a6b433aa7a315b25672",
        )

    def test_case_zero_request_vector_is_exact_and_answer_free(self) -> None:
        case = build_case(SEED, 0)
        duplicate = build_case(SEED, 0)
        independent = build_case(SEED, 1)
        self.assertEqual(case.request_bytes, duplicate.request_bytes)
        self.assertEqual(case.positive, duplicate.positive)
        self.assertNotEqual(case.request_bytes, independent.request_bytes)
        self.assertEqual(
            case.request_sha256,
            "c7f01b8fcc94954a8fc146c43693a8c6fb40398bdacc2081db77beafdedea4fe",
        )
        self.assertEqual(
            case.pbm_sha256,
            "9ad346f14696f3058295896f24fa5f34b44bc474d48a8f619dea4c3b23213e44",
        )
        parsed = json.loads(case.request_bytes)
        self.assertEqual(set(parsed), REQUEST_KEYS)
        self.assertNotIn("case_id", parsed)
        self.assertNotIn("seed", parsed)
        self.assertNotIn("oracle", parsed)
        self.assertNotIn("expected", parsed)

    def test_all_32_recipes_validate_exhaustively(self) -> None:
        positive_shapes = (
            (166, 68),
            (166, 68),
            (158, 72),
            (172, 66),
            (164, 64),
            (160, 66),
            (162, 64),
            (166, 58),
            (168, 68),
            (166, 68),
            (170, 68),
            (174, 66),
        )
        positive_hashes: list[str] = []
        negative_hashes: list[str] = []
        for ordinal, spec in enumerate(CASE_ROSTER):
            with self.subTest(case_id=spec.case_id):
                case = build_case(SEED, ordinal)
                self.assertEqual(case.case_id, spec.case_id)
                self.assertEqual(case.category, spec.category)
                self.assertEqual(sha256(case.request_bytes).hexdigest(), case.request_sha256)
                envelope = decode_worker_request_envelope(case.request_bytes)
                self.assertEqual(sha256(envelope.pbm).hexdigest(), case.pbm_sha256)
                self.assertEqual(set(json.loads(case.request_bytes)), REQUEST_KEYS)
                if spec.category is CaseCategory.POSITIVE:
                    positive_hashes.append(case.pbm_sha256)
                    assert case.positive is not None
                    pitch, count = positive_shapes[ordinal]
                    self.assertEqual(case.positive.pitch, pitch)
                    self.assertEqual(len(case.positive.truth_slots), count)
                    self.assertTrue(
                        all(abs(witness.jitter) <= 6 for witness in case.positive.witnesses)
                    )
                    validate_page_lattice(
                        case.positive,
                        maximum_jitter=GENERATOR_MAXIMUM_JITTER,
                    )
                    validate_page_composition(envelope.pbm, case.positive.layers)
                elif spec.category is CaseCategory.NEGATIVE:
                    negative_hashes.append(case.pbm_sha256)
                    assert case.negative is not None
                    self.assertEqual(
                        case.negative.failure,
                        NEGATIVE_FAILURE_BY_CASE_ID[case.case_id],
                    )
                    _validate_negative_certificate_structure(case.negative)
                    validate_page_composition(envelope.pbm, case.negative.layers)
                else:
                    with self.assertRaises(KP1979V3WorkerInputError) as caught:
                        decode_worker_request(case.request_bytes)
                    self.assertIs(caught.exception.error_code, spec.expected_error_code)
        self.assertEqual(tuple(negative_hashes), NEGATIVE_PBM_SHA256)
        self.assertEqual(len(set(negative_hashes)), 14)
        self.assertFalse(set(negative_hashes) & set(positive_hashes))

    def test_positive_recipe_indices_are_exact(self) -> None:
        expected = {
            0: (set(range(34)), set(range(34))),
            1: (set(range(34)), set(range(34))),
            2: (set(range(36)), set(range(36))),
            3: (set(range(33)), set(range(33))),
            4: (set(range(35)), set(range(3, 32))),
            5: (
                set(range(36)) - {6, 14, 27},
                set(range(36)) - {4, 18, 30},
            ),
            6: (
                set(range(36)) - {9, 10, 25, 26},
                set(range(36)) - {7, 8, 20, 21},
            ),
            7: (set(range(36)), set(range(8, 30))),
            8: (set(range(34)), set(range(34))),
            9: (set(range(34)), set(range(34))),
            10: (set(range(34)), set(range(34))),
            11: (set(range(33)), set(range(33))),
        }
        for ordinal, expected_lanes in expected.items():
            case = build_case(SEED, ordinal)
            assert case.positive is not None
            actual = tuple(
                {witness.grid_index for witness in case.positive.witnesses if witness.lane == lane}
                for lane in (0, 1)
            )
            self.assertEqual(actual, expected_lanes)

    def test_complete_witness_rerender_and_inventory_tampering_fail(self) -> None:
        case = build_case(SEED, 0)
        assert case.positive is not None
        certificate = case.positive
        first = certificate.witnesses[0]

        bad_receipt = replace(first.receipt, lower_ink_count=31)
        bad_witness = replace(first, receipt=bad_receipt)
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(
                    certificate,
                    witnesses=(bad_witness, *certificate.witnesses[1:]),
                ),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )

        changed = bytes([first.layer.packed[0] ^ 0x80]) + first.layer.packed[1:]
        bad_layer = replace(first.layer, packed=changed)
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(
                    certificate,
                    witnesses=(replace(first, layer=bad_layer), *certificate.witnesses[1:]),
                ),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )

        injected = replace(
            first.layer,
            layer_id="injected-incomplete-layer",
            kind=InkLayerKind.INCOMPLETE_PRIMITIVE,
        )
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(certificate, layers=(*certificate.layers, injected)),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )

        excess = tuple(
            replace(
                first.layer,
                layer_id=f"excess-distractor-{index:03d}",
                kind=InkLayerKind.DISTRACTOR,
            )
            for index in range(MAXIMUM_PAGE_LAYERS - len(certificate.layers) + 1)
        )
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(certificate, layers=(*certificate.layers, *excess)),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )

    def test_lattice_bounds_missing_run_and_unaccounted_ink_fail(self) -> None:
        case = build_case(SEED, 0)
        assert case.positive is not None
        certificate = case.positive
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(certificate, pitch=153),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(certificate, phase=603),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )

        removed_keys = {(0, 10), (0, 11), (0, 12)}
        witnesses = tuple(
            witness
            for witness in certificate.witnesses
            if (witness.lane, witness.grid_index) not in removed_keys
        )
        layers = tuple(
            layer
            for witness, layer in zip(
                certificate.witnesses,
                certificate.layers,
                strict=True,
            )
            if (witness.lane, witness.grid_index) not in removed_keys
        )
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_lattice(
                replace(
                    certificate,
                    witnesses=witnesses,
                    truth_slots=tuple(
                        slot
                        for slot in certificate.truth_slots
                        if (slot.lane, slot.grid_index) not in removed_keys
                    ),
                    layers=layers,
                ),
                maximum_jitter=GENERATOR_MAXIMUM_JITTER,
            )

        pbm = bytearray(_request_pbm(case.request_bytes))
        pbm[len(RAW_P4_CONTRACT.header)] ^= 0x80
        with self.assertRaises(KP1979V3GrammarError):
            validate_page_composition(bytes(pbm), certificate.layers)

    def test_negative_certificates_reject_wrong_failure_and_witness_inventory(self) -> None:
        gaps = build_case(SEED, 5)
        blank = build_case(SEED, 12)
        single = build_case(SEED, 13)
        conflict = build_case(SEED, 14)
        assert gaps.positive is not None
        assert blank.negative is not None
        assert single.negative is not None
        assert conflict.negative is not None
        _validate_negative_certificate_structure(conflict.negative)

        with self.assertRaises(KP1979V3GrammarError):
            _validate_negative_certificate_structure(
                replace(blank.negative, failure=NegativeFailure.INSUFFICIENT_LANES)
            )
        with self.assertRaises(KP1979V3GrammarError):
            _validate_negative_certificate_structure(
                replace(
                    blank.negative,
                    complete_witnesses=(single.negative.complete_witnesses[0],),
                    layers=(single.negative.complete_witnesses[0].layer,),
                )
            )
        lane_zero = tuple(
            witness for witness in conflict.negative.complete_witnesses if witness.lane == 0
        )
        with self.assertRaises(KP1979V3GrammarError):
            _validate_negative_certificate_structure(
                replace(
                    conflict.negative,
                    complete_witnesses=lane_zero,
                    layers=tuple(witness.layer for witness in lane_zero),
                )
            )

        positive_witnesses = tuple(
            witness
            for witness in gaps.positive.witnesses
            if (witness.lane, witness.grid_index) != (0, 0)
        )
        positive_keys = {(witness.lane, witness.grid_index) for witness in positive_witnesses}
        reduced_positive = replace(
            gaps.positive,
            witnesses=positive_witnesses,
            truth_slots=tuple(
                slot
                for slot in gaps.positive.truth_slots
                if (slot.lane, slot.grid_index) in positive_keys
            ),
            layers=tuple(witness.layer for witness in positive_witnesses),
        )
        validate_page_lattice(reduced_positive)
        false_pitch_conflict = replace(
            conflict.negative,
            complete_witnesses=positive_witnesses,
            layers=tuple(witness.layer for witness in positive_witnesses),
        )
        with self.assertRaisesRegex(
            KP1979V3GrammarError,
            "admits a common legal pitch",
        ):
            _validate_negative_certificate_structure(false_pitch_conflict)

    def test_all_ooc_envelopes_start_outer_wire_and_fail_exact_semantics(self) -> None:
        for ordinal in range(26, 32):
            case = build_case(SEED, ordinal)
            decode_worker_request_envelope(case.request_bytes)
            with self.assertRaises(KP1979V3WorkerInputError) as caught:
                decode_worker_request(case.request_bytes)
            self.assertIs(caught.exception.error_code, case.expected_error_code)

        compound = encode_worker_request(
            pbm=b"not-p4",
            width=1,
            height=1,
            scan_bands=((0, 0, 0, 0),),
        )
        decode_worker_request_envelope(compound)
        with self.assertRaises(KP1979V3WorkerInputError) as caught:
            decode_worker_request(compound)
        self.assertIs(caught.exception.error_code, InputErrorCode.INVALID_PBM_HEADER)

        dimensions_before_size = encode_worker_request(
            pbm=RAW_P4_CONTRACT.header,
            width=4879,
            height=RAW_P4_CONTRACT.height,
            scan_bands=RAW_P4_CONTRACT.scan_bands,
        )
        with self.assertRaises(KP1979V3WorkerInputError) as caught:
            decode_worker_request(dimensions_before_size)
        self.assertIs(caught.exception.error_code, InputErrorCode.INVALID_DIMENSIONS)

    def test_case_validator_fails_closed_for_malformed_dataclasses(self) -> None:
        positive = build_case(SEED, 0)
        negative = build_case(SEED, 12)
        out_of_contract = build_case(SEED, 26)
        assert positive.positive is not None
        assert negative.negative is not None

        malformed_cases = (
            ("root-type", object()),
            ("ordinal-bool", replace(positive, ordinal=True)),
            ("case-id-type", replace(positive, case_id=b"case")),  # type: ignore[arg-type]
            ("category-type", replace(positive, category="positive")),  # type: ignore[arg-type]
            (
                "generation-commitment-type",
                replace(positive, generation_commitment=True),  # type: ignore[arg-type]
            ),
            (
                "generation-commitment-length",
                replace(positive, generation_commitment=bytes(31)),
            ),
            ("request-type", replace(positive, request_bytes="request")),  # type: ignore[arg-type]
            ("request-digest-type", replace(positive, request_sha256=True)),  # type: ignore[arg-type]
            ("pbm-digest-type", replace(positive, pbm_sha256=[])),  # type: ignore[arg-type]
            ("positive-oracle-type", replace(positive, positive=object())),  # type: ignore[arg-type]
            ("negative-oracle-type", replace(negative, negative=object())),  # type: ignore[arg-type]
            ("positive-surplus", replace(negative, positive=positive.positive)),
            ("negative-surplus", replace(positive, negative=negative.negative)),
            ("ooc-surplus", replace(out_of_contract, positive=positive.positive)),
            (
                "expected-error-type",
                replace(out_of_contract, expected_error_code="invalid-pbm-size"),  # type: ignore[arg-type]
            ),
        )
        for mutation, malformed in malformed_cases:
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(KP1979V3GeneratorError) as caught,
            ):
                validate_generated_case(malformed, seed=SEED)  # type: ignore[arg-type]
            self.assertIs(type(caught.exception), KP1979V3GeneratorError)

        malformed_wire = b"{}"
        with self.assertRaises(KP1979V3GeneratorError) as caught:
            validate_generated_case(
                replace(
                    positive,
                    request_bytes=malformed_wire,
                    request_sha256=sha256(malformed_wire).hexdigest(),
                ),
                seed=SEED,
            )
        self.assertIs(type(caught.exception), KP1979V3GeneratorError)

        malformed_oracle = replace(positive.positive, pitch=153)
        with self.assertRaises(KP1979V3GeneratorError) as caught:
            validate_generated_case(
                replace(positive, positive=malformed_oracle),
                seed=SEED,
            )
        self.assertIs(type(caught.exception), KP1979V3GeneratorError)

    def test_authoritative_case_validator_rejects_cross_recipe_transplants(self) -> None:
        first_positive = build_case(SEED, 0)
        second_positive = build_case(SEED, 1)
        positive_transplant = replace(
            first_positive,
            request_bytes=second_positive.request_bytes,
            request_sha256=second_positive.request_sha256,
            pbm_sha256=second_positive.pbm_sha256,
            positive=second_positive.positive,
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_case(positive_transplant, seed=SEED)

        primitive_donor = build_case(SEED, 15)
        primitive_target = build_case(SEED, 16)
        assert primitive_donor.negative is not None
        negative_transplant = replace(
            primitive_target,
            request_bytes=primitive_donor.request_bytes,
            request_sha256=primitive_donor.request_sha256,
            pbm_sha256=primitive_donor.pbm_sha256,
            negative=primitive_donor.negative,
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_case(negative_transplant, seed=SEED)

        ooc_cases = tuple(build_case(SEED, ordinal) for ordinal in range(26, 32))
        ooc_target, ooc_donor = next(
            (target, donor)
            for target in ooc_cases
            for donor in ooc_cases
            if target.ordinal < donor.ordinal
            and target.expected_error_code is donor.expected_error_code
        )
        ooc_transplant = replace(
            ooc_target,
            request_bytes=ooc_donor.request_bytes,
            request_sha256=ooc_donor.request_sha256,
            pbm_sha256=ooc_donor.pbm_sha256,
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_case(ooc_transplant, seed=SEED)

    def test_positive_layers_cannot_forge_an_authoritative_negative(self) -> None:
        positive = build_case(SEED, 0)
        mixed_ordinal = next(
            ordinal
            for ordinal, spec in enumerate(CASE_ROSTER)
            if spec.case_id == "negative-mixed-label-confound"
        )
        target = build_case(SEED, mixed_ordinal)
        assert positive.positive is not None
        assert target.negative is not None
        retagged_layers = tuple(
            replace(layer, kind=InkLayerKind.INCOMPLETE_PRIMITIVE)
            for layer in positive.positive.layers
        )
        forged_certificate = replace(
            target.negative,
            complete_witnesses=(),
            layers=retagged_layers,
        )
        _validate_negative_certificate_structure(forged_certificate)
        forged_pbm = compose_pbm(retagged_layers)
        forged_request = encode_worker_request(
            pbm=forged_pbm,
            width=RAW_P4_CONTRACT.width,
            height=RAW_P4_CONTRACT.height,
            scan_bands=SYNTHETIC_SCAN_BANDS,
        )
        self.assertEqual(set(json.loads(forged_request)), REQUEST_KEYS)
        self.assertNotIn("seed", json.loads(forged_request))
        forged_case = replace(
            target,
            request_bytes=forged_request,
            request_sha256=sha256(forged_request).hexdigest(),
            pbm_sha256=sha256(forged_pbm).hexdigest(),
            negative=forged_certificate,
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_case(forged_case, seed=SEED)

    def test_authoritative_validators_require_the_exact_suite_seed(self) -> None:
        wrong_seed = bytes(reversed(SEED))
        seed_dependent_case = build_case(SEED, 0)
        seed_independent_blank = build_case(SEED, 12)
        negative_case = build_case(SEED, 15)
        seed_independent_wire_case = build_case(SEED, 26)
        relation = build_relation(SEED, 0)
        for case in (
            seed_dependent_case,
            seed_independent_blank,
            negative_case,
            seed_independent_wire_case,
        ):
            with self.subTest(case=case.case_id), self.assertRaises(KP1979V3GeneratorError):
                validate_generated_case(case, seed=wrong_seed)
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(relation, seed=wrong_seed)

        alternate_relation = build_relation(wrong_seed, 0)
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(alternate_relation, seed=SEED)

        case_commitment = seed_dependent_case.generation_commitment
        relation_commitment = relation.generation_commitment
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_case(
                replace(
                    seed_dependent_case,
                    generation_commitment=bytes([case_commitment[0] ^ 1]) + case_commitment[1:],
                ),
                seed=SEED,
            )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(
                replace(
                    relation,
                    generation_commitment=bytes([relation_commitment[0] ^ 1])
                    + relation_commitment[1:],
                ),
                seed=SEED,
            )

        invalid_seeds: tuple[object, ...] = (
            b"",
            bytes(31),
            bytes(33),
            True,
        )
        for invalid_seed in invalid_seeds:
            with self.subTest(seed=invalid_seed), self.assertRaises(KP1979V3GeneratorError):
                validate_generated_case(
                    seed_dependent_case,
                    seed=invalid_seed,  # type: ignore[arg-type]
                )
            with self.assertRaises(KP1979V3GeneratorError):
                validate_generated_relation(
                    relation,
                    seed=invalid_seed,  # type: ignore[arg-type]
                )

    def test_relation_vectors_and_exact_transformations(self) -> None:
        gap = build_relation(SEED, 7)
        self.assertEqual(
            tuple(endpoint.request_sha256 for endpoint in gap.endpoints),
            (
                "6465edf812bdc08404efc5c4b8a973a51d501ab4548d1de2d631b348c8a2ca18",
                "40d2f2e3b57449b314c2778db61a829d7422087e573caa75a9a5b90a5d1eb021",
            ),
        )
        assert gap.omitted_layer is not None
        self.assertEqual(gap.omitted_layer.layer_id, "gap-deletion/slot/1/13")
        self.assertEqual(
            gap.omitted_layer.packed_sha256,
            "1c766f24ff54129f7783ea13dd34fc5c62023027c7b78ad2a3a325b5ae9d896b",
        )
        first_gap = _ink_points(_request_pbm(gap.endpoints[0].request_bytes))
        second_gap = _ink_points(_request_pbm(gap.endpoints[1].request_bytes))
        self.assertEqual(first_gap ^ second_gap, _layer_points(gap.omitted_layer))

        vertical = build_relation(SEED, 2)
        first_vertical = _ink_points(_request_pbm(vertical.endpoints[0].request_bytes))
        second_vertical = _ink_points(_request_pbm(vertical.endpoints[1].request_bytes))
        self.assertEqual(
            frozenset((x, y + 11) for x, y in first_vertical),
            second_vertical,
        )

        horizontal = build_relation(SEED, 3)
        first_horizontal = _ink_points(_request_pbm(horizontal.endpoints[0].request_bytes))
        second_horizontal = _ink_points(_request_pbm(horizontal.endpoints[1].request_bytes))
        self.assertEqual(
            frozenset((x + 17, y) for x, y in first_horizontal),
            second_horizontal,
        )

        stroke = build_relation(SEED, 4)
        self.assertTrue(
            all(
                first.invocation.entropy == second.invocation.entropy
                and first.layer.packed != second.layer.packed
                for first, second in zip(
                    stroke.endpoints[0].positive.witnesses,
                    stroke.endpoints[1].positive.witnesses,
                    strict=True,
                )
            )
        )

        renderer = build_relation(SEED, 5)
        self.assertTrue(
            all(
                first.invocation.entropy != second.invocation.entropy
                and first.layer.packed != second.layer.packed
                for first, second in zip(
                    renderer.endpoints[0].positive.witnesses,
                    renderer.endpoints[1].positive.witnesses,
                    strict=True,
                )
            )
        )

        lane_swap = build_relation(SEED, 6)
        first_swap = _request_pbm(lane_swap.endpoints[0].request_bytes)
        second_swap = _request_pbm(lane_swap.endpoints[1].request_bytes)
        self.assertEqual(_band_points(first_swap, 0), _band_points(second_swap, 1))
        self.assertEqual(_band_points(first_swap, 1), _band_points(second_swap, 0))

    def test_all_relation_kinds_build_and_remain_positive(self) -> None:
        for ordinal, spec in enumerate(METAMORPHIC_RELATIONS):
            with self.subTest(relation_id=spec.relation_id):
                relation = build_relation(SEED, ordinal)
                self.assertIs(relation.kind, spec.kind)
                self.assertEqual(
                    tuple(endpoint.endpoint for endpoint in relation.endpoints),
                    ("a", "b"),
                )
                for endpoint in relation.endpoints:
                    validate_page_lattice(
                        endpoint.positive,
                        maximum_jitter=GENERATOR_MAXIMUM_JITTER,
                    )

    def test_relation_validator_rejects_wrong_endpoint(self) -> None:
        vertical = build_relation(SEED, 2)
        malformed_relations = (
            ("root-type", object()),
            ("ordinal-bool", replace(vertical, ordinal=True)),
            ("relation-id-type", replace(vertical, relation_id=[])),  # type: ignore[arg-type]
            ("kind-type", replace(vertical, kind="vertical-plus-11")),  # type: ignore[arg-type]
            (
                "generation-commitment-type",
                replace(vertical, generation_commitment=True),  # type: ignore[arg-type]
            ),
            (
                "generation-commitment-length",
                replace(vertical, generation_commitment=bytes(31)),
            ),
            ("endpoints-type", replace(vertical, endpoints=list(vertical.endpoints))),  # type: ignore[arg-type]
        )
        for mutation, malformed in malformed_relations:
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(KP1979V3GeneratorError) as caught,
            ):
                validate_generated_relation(malformed, seed=SEED)  # type: ignore[arg-type]
            self.assertIs(type(caught.exception), KP1979V3GeneratorError)

        bad = replace(
            vertical,
            endpoints=(vertical.endpoints[0], replace(vertical.endpoints[0], endpoint="b")),
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(bad, seed=SEED)

        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(
                replace(vertical, omitted_layer=vertical.endpoints[0].positive.layers[0]),
                seed=SEED,
            )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(
                replace(
                    vertical,
                    endpoints=(object(), vertical.endpoints[1]),  # type: ignore[arg-type]
                ),
                seed=SEED,
            )

        malformed_endpoints = (
            (
                "request_bytes",
                replace(
                    vertical.endpoints[0],
                    request_bytes="not-bytes",  # type: ignore[arg-type]
                ),
            ),
            (
                "request_sha256",
                replace(
                    vertical.endpoints[0],
                    request_sha256=True,  # type: ignore[arg-type]
                ),
            ),
            (
                "pbm_sha256",
                replace(
                    vertical.endpoints[0],
                    pbm_sha256=[],  # type: ignore[arg-type]
                ),
            ),
            (
                "positive",
                replace(
                    vertical.endpoints[0],
                    positive=object(),  # type: ignore[arg-type]
                ),
            ),
        )
        for field_name, endpoint in malformed_endpoints:
            with self.subTest(field=field_name), self.assertRaises(KP1979V3GeneratorError):
                validate_generated_relation(
                    replace(vertical, endpoints=(endpoint, vertical.endpoints[1])),
                    seed=SEED,
                )

    def test_relation_validator_rejects_every_cross_kind_endpoint_swap(self) -> None:
        relations = tuple(
            build_relation(SEED, ordinal) for ordinal in range(len(METAMORPHIC_RELATIONS))
        )

        def relabel_endpoint(
            endpoint: GeneratedEndpoint,
            relation_id: str,
        ) -> GeneratedEndpoint:
            witnesses = tuple(
                replace(
                    witness,
                    layer=replace(
                        witness.layer,
                        layer_id=(f"{relation_id}/slot/{witness.lane}/{witness.grid_index:02d}"),
                    ),
                )
                for witness in endpoint.positive.witnesses
            )
            extra_layers = endpoint.positive.layers[len(endpoint.positive.witnesses) :]
            certificate = replace(
                endpoint.positive,
                witnesses=witnesses,
                layers=tuple(witness.layer for witness in witnesses) + extra_layers,
            )
            return replace(endpoint, positive=certificate)

        def endpoint_with_certificate(
            endpoint: GeneratedEndpoint,
            certificate: PageLatticeCertificate,
        ) -> GeneratedEndpoint:
            pbm = compose_pbm(certificate.layers)
            request = encode_worker_request(
                pbm=pbm,
                width=RAW_P4_CONTRACT.width,
                height=RAW_P4_CONTRACT.height,
                scan_bands=SYNTHETIC_SCAN_BANDS,
            )
            return GeneratedEndpoint(
                endpoint=endpoint.endpoint,
                request_bytes=request,
                request_sha256=sha256(request).hexdigest(),
                pbm_sha256=sha256(pbm).hexdigest(),
                positive=certificate,
            )

        previously_accepted_style_swaps = frozenset(
            {
                (4, 1),
                (4, 3),
                (4, 5),
                (5, 1),
                (5, 3),
                (5, 4),
            }
        )
        for target_ordinal, relation in enumerate(relations):
            for donor_ordinal, donor in enumerate(relations):
                if target_ordinal == donor_ordinal:
                    continue
                relabeled = tuple(
                    relabel_endpoint(endpoint, relation.relation_id) for endpoint in donor.endpoints
                )
                with (
                    self.subTest(
                        target=relation.kind,
                        donor=donor.kind,
                        historical_old_tip_accept=(
                            target_ordinal,
                            donor_ordinal,
                        )
                        in previously_accepted_style_swaps,
                    ),
                    self.assertRaises(KP1979V3GeneratorError),
                ):
                    validate_generated_relation(
                        replace(relation, endpoints=relabeled),
                        seed=SEED,
                    )

        unread = relations[1]
        unread_second = unread.endpoints[1]
        unread_distractor = unread_second.positive.layers[-1]
        second_distractor = replace(
            unread_distractor,
            layer_id=f"{unread.relation_id}/unread-margin-second",
            x0=unread_distractor.x0 + 400,
        )
        unread_certificate = replace(
            unread_second.positive,
            layers=(*unread_second.positive.layers, second_distractor),
        )
        validate_page_lattice(unread_certificate)
        unread_attack = endpoint_with_certificate(
            unread_second,
            unread_certificate,
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(
                replace(
                    unread,
                    endpoints=(unread.endpoints[0], unread_attack),
                ),
                seed=SEED,
            )

        lane_swap = relations[6]
        lane_second = lane_swap.endpoints[1]
        lane_distractor = replace(
            unread_distractor,
            layer_id=f"{lane_swap.relation_id}/unexpected-outside",
        )
        lane_certificate = replace(
            lane_second.positive,
            layers=(*lane_second.positive.layers, lane_distractor),
        )
        validate_page_lattice(lane_certificate)
        lane_attack = endpoint_with_certificate(
            lane_second,
            lane_certificate,
        )
        with self.assertRaises(KP1979V3GeneratorError):
            validate_generated_relation(
                replace(
                    lane_swap,
                    endpoints=(lane_swap.endpoints[0], lane_attack),
                ),
                seed=SEED,
            )

        gap = relations[7]
        assert gap.omitted_layer is not None
        tampered_layers = (
            replace(gap.omitted_layer, layer_id=f"{gap.omitted_layer.layer_id}-tampered"),
            replace(gap.omitted_layer, kind=InkLayerKind.DISTRACTOR),
            replace(gap.omitted_layer, ink_count=gap.omitted_layer.ink_count + 1),
        )
        for mutation, omitted_layer in zip(
            ("layer-id", "kind", "ink-count"),
            tampered_layers,
            strict=True,
        ):
            with self.subTest(gap_mutation=mutation), self.assertRaises(KP1979V3GeneratorError):
                validate_generated_relation(
                    replace(gap, omitted_layer=omitted_layer),
                    seed=SEED,
                )

    def test_schedule_is_lazy_fixed_and_controller_private(self) -> None:
        self.assertNotIn("ManifestEntry", generator_module.__dict__)
        self.assertNotIn("SuiteManifest", generator_module.__dict__)
        self.assertNotIn("build_suite_manifest", generator_module.__dict__)
        self.assertNotIn("ScheduledInvocation", generator_module.__dict__)
        self.assertNotIn("build_suite_manifest", generator_module.__all__)
        self.assertNotIn("validate_negative_certificate", grammar_module.__dict__)
        self.assertNotIn(
            "_validate_negative_certificate_structure",
            grammar_module.__all__,
        )
        assert iter_schedule.__doc__ is not None
        self.assertIn("controller-private", iter_schedule.__doc__)
        self.assertIn("MUST NOT be persisted", iter_schedule.__doc__)
        self.assertIn("MUST NOT be passed to a worker", iter_schedule.__doc__)

        schedule = iter_schedule(SEED)
        self.assertTrue(isgenerator(schedule))
        first = next(schedule)
        self.assertEqual(first.invocation_index, 0)
        self.assertEqual(first.source_id, CASE_ROSTER[0].case_id)
        self.assertFalse(hasattr(first, "generation_commitment"))
        del schedule

        hidden_case = build_case(SEED, 0)
        hidden_relation = build_relation(SEED, 0)
        hidden_objects = (
            hidden_case,
            hidden_relation,
            *hidden_relation.endpoints,
            next(iter_schedule(SEED)),
        )
        for hidden in hidden_objects:
            with self.subTest(hidden_type=type(hidden).__name__):
                self.assertNotIn("generation_commitment", repr(hidden))
                self.assertNotIn(hidden_case.generation_commitment.hex(), repr(hidden))
                self.assertNotIn(hidden_relation.generation_commitment.hex(), repr(hidden))

        count = 0
        for invocation in iter_schedule(SEED):
            self.assertEqual(invocation.invocation_index, count)
            self.assertEqual(set(json.loads(invocation.request_bytes)), REQUEST_KEYS)
            count += 1
        self.assertEqual(count, TOTAL_WORKER_INVOCATIONS)

    def test_every_public_build_entry_reaches_its_final_validator(self) -> None:
        class FinalValidatorReached(RuntimeError):
            pass

        with (
            patch(
                "indusbench.kp1979_v3_generator.validate_generated_case",
                side_effect=FinalValidatorReached,
            ),
            self.assertRaises(FinalValidatorReached),
        ):
            build_case(SEED, 0)
        with (
            patch(
                "indusbench.kp1979_v3_generator.validate_generated_relation",
                side_effect=FinalValidatorReached,
            ),
            self.assertRaises(FinalValidatorReached),
        ):
            build_relation(SEED, 0)
        with (
            patch(
                "indusbench.kp1979_v3_generator.validate_generated_case",
                side_effect=FinalValidatorReached,
            ),
            self.assertRaises(FinalValidatorReached),
        ):
            next(iter_schedule(SEED))

    def test_generated_types_are_frozen(self) -> None:
        case = build_case(SEED, 0)
        with self.assertRaises(FrozenInstanceError):
            case.ordinal = 1  # type: ignore[misc]
        assert case.positive is not None
        with self.assertRaises(FrozenInstanceError):
            case.positive.pitch = 170  # type: ignore[misc]

    def test_seed_and_ordinal_bounds_fail_closed(self) -> None:
        for seed in (b"", bytes(31), bytes(33)):
            with self.subTest(length=len(seed)), self.assertRaises(KP1979V3GeneratorError):
                build_case(seed, 0)
        for ordinal in (-1, 32, True):
            with self.subTest(ordinal=ordinal), self.assertRaises(KP1979V3GeneratorError):
                build_case(SEED, ordinal)
        for ordinal in (-1, 8, True):
            with self.subTest(relation_ordinal=ordinal), self.assertRaises(KP1979V3GeneratorError):
                build_relation(SEED, ordinal)

    def test_generator_ast_has_no_external_state_or_retired_source_imports(self) -> None:
        package = Path(__file__).resolve().parents[1] / "src" / "indusbench"
        forbidden_roots = {
            "httpx",
            "os",
            "pathlib",
            "random",
            "requests",
            "shutil",
            "socket",
            "subprocess",
            "tempfile",
            "time",
            "urllib",
        }
        forbidden_fragments = (
            "_v2",
            "private",
            "real_source",
            "row_assignment",
            "oracc",
        )
        for filename in ("kp1979_v3_grammar.py", "kp1979_v3_generator.py"):
            source = (package / filename).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    imported.append(node.module)
            self.assertFalse(
                {name.split(".", 1)[0] for name in imported} & forbidden_roots,
                filename,
            )
            lowered = "\n".join(imported).lower()
            self.assertFalse(
                any(fragment in lowered for fragment in forbidden_fragments),
                filename,
            )


if __name__ == "__main__":
    unittest.main()
