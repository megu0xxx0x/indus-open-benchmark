from __future__ import annotations

import ast
import json
import unittest
from dataclasses import asdict, fields, replace
from hashlib import sha256
from itertools import pairwise
from pathlib import Path

from indusbench.kp1979_synthetic_control_v2 import (
    CONTROL_ID,
    FREEZE_MANIFEST_BYTE_SIZE,
    FREEZE_MANIFEST_PATH,
    FREEZE_MANIFEST_SHA256,
    FREEZE_RESULT_STATE,
    MAX_METAMORPHIC_RELATIONS,
    MAX_PBM_BYTES,
    MAX_PREDICTIONS_PER_PROPOSAL,
    MAX_REFERENCES_PER_FIXTURE,
    MAX_SCAN_BANDS,
    MAX_SYNTHETIC_CASES,
    SYNTHETIC_CASE_COUNT,
    SYNTHETIC_METAMORPHIC_RELATION_COUNT,
    SYNTHETIC_NEGATIVE_CASE_COUNT,
    SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT,
    SYNTHETIC_PAGE_HEIGHT,
    SYNTHETIC_PAGE_NUMBER_BASE,
    SYNTHETIC_PAGE_WIDTH,
    SYNTHETIC_PBM_BYTE_SIZE,
    SYNTHETIC_POSITIVE_CASE_COUNT,
    SYNTHETIC_SCAN_BANDS,
    TARGET_ALGORITHM_ID,
    KP1979V2SyntheticControlError,
    SyntheticDetectorInput,
    build_synthetic_fixture,
    detector_input_for_fixture,
    evaluate_synthetic_fixture,
    frozen_synthetic_control,
    metamorphic_fixture_pairs,
    synthetic_case_ids,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "indusbench" / "kp1979_synthetic_control_v2.py"
HEADER = b"P4\n4880 7010\n"
ROW_BYTES = SYNTHETIC_PAGE_WIDTH // 8


def row_has_black(pbm_bytes: bytes, y: int, x0: int, x1: int) -> bool:
    payload = pbm_bytes[len(HEADER) :]
    row = payload[y * ROW_BYTES : (y + 1) * ROW_BYTES]
    return any(row[x // 8] & (128 >> (x % 8)) for x in range(x0, x1))


def scan_band_row_bytes(detector_input: SyntheticDetectorInput, lane_index: int, y: int) -> bytes:
    x0, _, x1, _ = SYNTHETIC_SCAN_BANDS[lane_index]
    payload = detector_input.pbm_bytes[len(HEADER) :]
    row = payload[y * ROW_BYTES : (y + 1) * ROW_BYTES]
    return row[x0 // 8 : (x1 + 7) // 8]


class KP1979V2SyntheticControlFreezeTests(unittest.TestCase):
    def test_case_roster_and_taxonomy_are_exactly_frozen(self) -> None:
        case_ids = synthetic_case_ids()
        self.assertEqual(SYNTHETIC_CASE_COUNT, len(case_ids))
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(8, SYNTHETIC_POSITIVE_CASE_COUNT)
        self.assertEqual(7, SYNTHETIC_NEGATIVE_CASE_COUNT)
        self.assertEqual(4, SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT)
        self.assertEqual(
            {
                "positive_independent_clean",
                "positive_asymmetric_phase",
                "positive_lower_pitch_boundary_regression",
                "positive_upper_pitch_boundary_regression",
                "positive_thin_two_tier_regression",
                "positive_bounded_jitter_with_gaps",
                "positive_partial_lane_regression",
                "positive_edge_and_qualifier_variation",
                "negative_blank_regression",
                "negative_periodic_single_tier_regression",
                "negative_single_lane_regression",
                "negative_cross_lane_pitch_conflict",
                "negative_dense_multicolumn_regression",
                "negative_aperiodic_fragments",
                "negative_staggered_single_tiers",
                "out_of_contract_truncated_payload",
                "out_of_contract_noncanonical_header",
                "out_of_contract_dimension_mismatch",
                "out_of_contract_invalid_scan_bands",
            },
            set(case_ids),
        )

        freeze = frozen_synthetic_control()
        self.assertEqual(CONTROL_ID, freeze.control_id)
        self.assertEqual(TARGET_ALGORITHM_ID, freeze.target_algorithm_id)
        self.assertEqual(SYNTHETIC_CASE_COUNT, freeze.case_count)
        self.assertEqual(SYNTHETIC_POSITIVE_CASE_COUNT, freeze.positive_case_count)
        self.assertEqual(SYNTHETIC_NEGATIVE_CASE_COUNT, freeze.negative_case_count)
        self.assertEqual(
            SYNTHETIC_OUT_OF_CONTRACT_CASE_COUNT,
            freeze.out_of_contract_case_count,
        )
        self.assertEqual(case_ids, tuple(value.case_id for value in freeze.case_commitments))
        self.assertGreater(
            sum(value.case_origin == "independent_v2" for value in freeze.case_commitments),
            0,
        )
        self.assertGreater(
            sum(value.case_origin == "exposed_v1_regression" for value in freeze.case_commitments),
            0,
        )

    def test_every_fixture_rebuilds_to_exact_committed_bytes(self) -> None:
        freeze = frozen_synthetic_control()
        commitments = {value.case_id: value for value in freeze.case_commitments}
        input_digests: set[str] = set()
        for case_id in synthetic_case_ids():
            with self.subTest(case_id=case_id):
                fixture = build_synthetic_fixture(case_id)
                commitment = commitments[case_id]
                self.assertEqual(commitment.pbm_byte_size, len(fixture.pbm_bytes))
                self.assertEqual(commitment.pbm_sha256, sha256(fixture.pbm_bytes).hexdigest())
                self.assertEqual(commitment.reference_count, len(fixture.references))
                self.assertEqual(commitment.case_class, fixture.case_class)
                self.assertEqual(commitment.case_origin, fixture.case_origin)
                self.assertEqual(commitment.contract_violation, fixture.contract_violation)
                self.assertGreaterEqual(fixture.pdf_page_number, SYNTHETIC_PAGE_NUMBER_BASE)
                self.assertLessEqual(len(fixture.pbm_bytes), MAX_PBM_BYTES)
                self.assertLessEqual(len(fixture.scan_bands), MAX_SCAN_BANDS)
                self.assertLessEqual(len(fixture.references), MAX_REFERENCES_PER_FIXTURE)
                input_digests.add(commitment.detector_input_sha256)
        self.assertEqual(SYNTHETIC_CASE_COUNT, len(input_digests))

    def test_valid_and_out_of_contract_inputs_have_predeclared_boundaries(self) -> None:
        for case_id in synthetic_case_ids():
            fixture = build_synthetic_fixture(case_id)
            with self.subTest(case_id=case_id):
                if fixture.contract_violation == "none":
                    self.assertEqual(SYNTHETIC_PAGE_WIDTH, fixture.width)
                    self.assertEqual(SYNTHETIC_PAGE_HEIGHT, fixture.height)
                    self.assertEqual(SYNTHETIC_SCAN_BANDS, fixture.scan_bands)
                    self.assertEqual(SYNTHETIC_PBM_BYTE_SIZE, len(fixture.pbm_bytes))
                    self.assertTrue(fixture.pbm_bytes.startswith(HEADER))
                elif fixture.contract_violation == "truncated_payload":
                    self.assertTrue(fixture.pbm_bytes.startswith(HEADER))
                    self.assertLess(len(fixture.pbm_bytes), SYNTHETIC_PBM_BYTE_SIZE)
                elif fixture.contract_violation == "noncanonical_header":
                    self.assertFalse(fixture.pbm_bytes.startswith(HEADER))
                    self.assertEqual(SYNTHETIC_PBM_BYTE_SIZE + 1, len(fixture.pbm_bytes))
                elif fixture.contract_violation == "dimension_mismatch":
                    self.assertTrue(fixture.pbm_bytes.startswith(HEADER))
                    self.assertNotEqual(SYNTHETIC_PAGE_WIDTH, fixture.width)
                elif fixture.contract_violation == "invalid_scan_bands":
                    self.assertTrue(any(band[2] > fixture.width for band in fixture.scan_bands))
                else:
                    self.fail(f"unexpected violation: {fixture.contract_violation}")

    def test_generator_references_are_tight_ordered_and_control_side_only(self) -> None:
        for case_id in synthetic_case_ids():
            fixture = build_synthetic_fixture(case_id)
            with self.subTest(case_id=case_id):
                if fixture.case_class != "positive":
                    self.assertEqual((), fixture.references)
                    continue
                self.assertGreater(len(fixture.references), 0)
                for lane_index in (0, 1):
                    lane_references = tuple(
                        value for value in fixture.references if value.lane_index == lane_index
                    )
                    self.assertGreater(len(lane_references), 0)
                    for previous, current in pairwise(lane_references):
                        self.assertLessEqual(previous.y1, current.y0)
                    x0, _, x1, _ = SYNTHETIC_SCAN_BANDS[lane_index]
                    for reference in lane_references:
                        self.assertEqual(fixture.pdf_page_number, reference.pdf_page_number)
                        self.assertTrue(row_has_black(fixture.pbm_bytes, reference.y0, x0, x1))
                        self.assertTrue(row_has_black(fixture.pbm_bytes, reference.y1 - 1, x0, x1))
                        self.assertFalse(row_has_black(fixture.pbm_bytes, reference.y0 - 1, x0, x1))
                        self.assertFalse(row_has_black(fixture.pbm_bytes, reference.y1, x0, x1))

    def test_adapter_input_is_closed_and_fixture_mutation_fails_closed(self) -> None:
        fixture = build_synthetic_fixture("positive_independent_clean")
        detector_input = detector_input_for_fixture(fixture)
        self.assertEqual(
            ("pbm_bytes", "width", "height", "scan_bands"),
            tuple(field.name for field in fields(SyntheticDetectorInput)),
        )
        self.assertEqual(fixture.pbm_bytes, detector_input.pbm_bytes)
        self.assertEqual(fixture.width, detector_input.width)
        self.assertEqual(fixture.height, detector_input.height)
        self.assertEqual(fixture.scan_bands, detector_input.scan_bands)
        for forbidden_name in (
            "case_id",
            "case_class",
            "case_origin",
            "contract_violation",
            "pdf_page_number",
            "references",
            "order",
            "truth",
        ):
            self.assertFalse(hasattr(detector_input, forbidden_name))

        with self.assertRaisesRegex(
            KP1979V2SyntheticControlError,
            "differs from the frozen generator",
        ):
            detector_input_for_fixture(replace(fixture, pbm_bytes=fixture.pbm_bytes[:-1]))

    def test_metamorphic_inputs_and_relations_are_exactly_frozen(self) -> None:
        pairs = metamorphic_fixture_pairs()
        self.assertEqual(SYNTHETIC_METAMORPHIC_RELATION_COUNT, len(pairs))
        self.assertEqual(
            {
                "identical_input_reproducibility",
                "unread_margin_invariance",
                "vertical_translation_equivariance",
            },
            {pair.relation_id for pair in pairs},
        )
        by_id = {pair.relation_id: pair for pair in pairs}
        identical = by_id["identical_input_reproducibility"]
        self.assertEqual(identical.base_input, identical.transformed_input)

        margin = by_id["unread_margin_invariance"]
        self.assertNotEqual(margin.base_input.pbm_bytes, margin.transformed_input.pbm_bytes)
        for lane_index in (0, 1):
            for y in range(
                SYNTHETIC_SCAN_BANDS[lane_index][1], SYNTHETIC_SCAN_BANDS[lane_index][3]
            ):
                self.assertEqual(
                    scan_band_row_bytes(margin.base_input, lane_index, y),
                    scan_band_row_bytes(margin.transformed_input, lane_index, y),
                )

        shifted = by_id["vertical_translation_equivariance"]
        self.assertEqual(11, shifted.vertical_delta)
        for lane_index in (0, 1):
            for y in range(550, 6589):
                self.assertEqual(
                    scan_band_row_bytes(shifted.base_input, lane_index, y),
                    scan_band_row_bytes(shifted.transformed_input, lane_index, y + 11),
                )

    def test_bounds_and_nonclaims_are_frozen_before_execution(self) -> None:
        freeze = frozen_synthetic_control()
        self.assertEqual(FREEZE_RESULT_STATE, freeze.result_state)
        self.assertEqual("not_run", freeze.result_state)
        self.assertIsNone(freeze.qualification_status)
        self.assertEqual(MAX_SYNTHETIC_CASES, freeze.max_synthetic_cases)
        self.assertEqual(
            MAX_METAMORPHIC_RELATIONS,
            freeze.max_metamorphic_relations,
        )
        self.assertEqual(MAX_PBM_BYTES, freeze.max_pbm_bytes)
        self.assertEqual(MAX_SCAN_BANDS, freeze.max_scan_bands)
        self.assertEqual(
            MAX_REFERENCES_PER_FIXTURE,
            freeze.max_references_per_fixture,
        )
        self.assertEqual(
            MAX_PREDICTIONS_PER_PROPOSAL,
            freeze.max_predictions_per_proposal,
        )
        self.assertFalse(freeze.detector_executed)
        self.assertFalse(freeze.evaluator_executed)
        self.assertFalse(freeze.result_recorded)
        self.assertTrue(freeze.synthetic_only)
        self.assertTrue(freeze.source_independent)
        for nonclaim in (
            "real_accuracy",
            "reference_accepted",
            "future_evaluation_opened",
            "reserved_sources_read",
            "full_row_segmentation_validated",
            "identifier_transcription_validated",
            "decipherment",
            "prize_submission_eligible",
        ):
            self.assertFalse(getattr(freeze, nonclaim))

    def test_machine_readable_manifest_is_canonical_and_generator_equal(self) -> None:
        manifest_path = ROOT / FREEZE_MANIFEST_PATH
        manifest_bytes = manifest_path.read_bytes()
        self.assertEqual(FREEZE_MANIFEST_BYTE_SIZE, len(manifest_bytes))
        self.assertEqual(FREEZE_MANIFEST_SHA256, sha256(manifest_bytes).hexdigest())
        manifest = json.loads(manifest_bytes)
        expected = json.loads(json.dumps(asdict(frozen_synthetic_control()), sort_keys=True))
        self.assertEqual(expected, manifest)
        self.assertEqual(
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
            manifest_bytes,
        )

    def test_module_is_source_independent_and_scorer_use_is_synthetic_only(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertEqual(
            {
                "__future__",
                "collections.abc",
                "dataclasses",
                "hashlib",
                "typing",
                "indusbench.kp1979_label_scoring",
            },
            imported_modules,
        )
        forbidden_modules = {
            "indusbench.kp1979",
            "indusbench.kp1979_label_reference",
            "indusbench.kp1979_row_assignment",
            "indusbench.kp1979_synthetic_control",
            "indusbench.printed_concordance_layout",
            "indusbench.mtaac",
            "indusbench.oracc_ed3b",
            "indusbench.v3dev",
            "indusbench.v4dev",
            "indusbench.v5dev",
        }
        self.assertTrue(forbidden_modules.isdisjoint(imported_modules))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"open", "exec", "eval", "__import__"}.isdisjoint(called_names))

        scorer_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_score_label_positions"
        ]
        self.assertEqual(1, len(scorer_calls))
        reference_use = next(
            keyword.value for keyword in scorer_calls[0].keywords if keyword.arg == "reference_use"
        )
        self.assertIsInstance(reference_use, ast.Constant)
        assert isinstance(reference_use, ast.Constant)
        self.assertEqual("synthetic_control", reference_use.value)

    def test_no_v2_detector_or_control_result_has_been_run_or_recorded(self) -> None:
        freeze = frozen_synthetic_control()
        self.assertFalse(freeze.detector_executed)
        self.assertFalse(freeze.evaluator_executed)
        self.assertFalse(freeze.result_recorded)
        self.assertIsNone(freeze.qualification_status)

        results_dir = ROOT / "benchmark" / "results"
        recorded_results = (
            tuple(results_dir.glob("*kp1979*synthetic*control*v2*")) if results_dir.exists() else ()
        )
        self.assertEqual((), recorded_results)

        cli_source = (ROOT / "src" / "indusbench" / "cli.py").read_text(encoding="utf-8")
        self.assertNotIn("kp1979_synthetic_control_v2", cli_source)
        self.assertNotIn(TARGET_ALGORITHM_ID, cli_source)

        test_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        test_calls = {
            node.func.id
            for node in ast.walk(test_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(callable(evaluate_synthetic_fixture))
        self.assertTrue(
            {
                "evaluate_frozen_synthetic_control",
                "evaluate_synthetic_fixture",
            }.isdisjoint(test_calls)
        )


if __name__ == "__main__":
    unittest.main()
