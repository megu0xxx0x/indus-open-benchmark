from __future__ import annotations

import itertools
import json
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

import indusbench.mtaac_control as mtaac_control_module
from indusbench.mtaac import MTAAC_COLUMNS, parse_mtaac_directory
from indusbench.mtaac_control import (
    CLEAN_REGIME,
    HARSH_REGIME,
    MILD_REGIME,
    MTAAC_CONTROL_PROTOCOL_SHA256,
    MTAAC_REAL_ARCHIVE_SHA256,
    MTAAC_REAL_SELECTED_MANIFEST_SHA256,
    MTAACControlAttestation,
    MTAACControlError,
    MTAACObservedDocument,
    apply_mtaac_control_decision,
    build_mtaac_split,
    degrade_mtaac_corpus,
    evaluate_mtaac_control_archive,
    evaluate_synthetic_mtaac_control_fixture,
    validate_mtaac_control_attestation,
    validate_mtaac_control_protocol,
    validate_mtaac_degradation,
    validate_mtaac_split,
    validate_nested_mtaac_degradations,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_BYTES = (ROOT / "benchmark/mtaac-known-script-control-v1.json").read_bytes()

TARGET_ROWS = {
    "quantity": ("SYNTHETIC_QUANTITY_FORM", "synthetic_quantity[one]", "NU"),
    "unit": ("SYNTHETIC_UNIT_FORM", "synthetic_measure[unit]", "N"),
    "person_name": ("SYNTHETIC_PERSON_FORM", "SyntheticPerson[1]", "PN"),
    "settlement_name": (
        "SYNTHETIC_SETTLEMENT_FORM",
        "SyntheticSettlement[1]",
        "SN",
    ),
}
PERMUTATIONS = tuple(itertools.permutations(TARGET_ROWS))


def synthetic_conll(
    p_identifier: str,
    document_index: int,
    *,
    context_count: int = 2,
    shared_context: bool = False,
) -> bytes:
    target_order = PERMUTATIONS[document_index % len(PERMUTATIONS)]
    values: list[tuple[str, str, str]] = []
    context_prefix = "SHARED" if shared_context else f"DOC-{document_index:04d}"
    before = context_count // 2
    after = context_count - before
    for index in range(before):
        values.append(
            (
                f"SYNTHETIC_CONTEXT_{context_prefix}_A{index}",
                f"context_a_{index}[synthetic]",
                "N",
            )
        )
    values.extend(TARGET_ROWS[gold_class] for gold_class in target_order)
    for index in range(after):
        values.append(
            (
                f"SYNTHETIC_CONTEXT_{context_prefix}_B{index}",
                f"context_b_{index}[synthetic]",
                "N",
            )
        )
    rows = [
        "\t".join(
            (
                f"o.1.{token_index + 1}",
                form,
                segm,
                xpostag,
                "_",
                "_",
                "_",
            )
        )
        for token_index, (form, segm, xpostag) in enumerate(values)
    ]
    return (
        "\n".join(
            (
                f"#new_text={p_identifier}",
                "# " + "\t".join(MTAAC_COLUMNS),
                *rows,
                "",
            )
        )
    ).encode()


def synthetic_files(
    document_count: int = 128,
    *,
    context_count: int = 2,
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for index in range(document_count):
        p_identifier = f"P{800000 + index:06d}"
        files[f"fixture/morph/to_dict/{p_identifier}.conll"] = synthetic_conll(
            p_identifier,
            index,
            context_count=context_count,
        )
    return files


def synthetic_corpus(
    document_count: int = 128,
    *,
    context_count: int = 2,
):
    return parse_mtaac_directory(synthetic_files(document_count, context_count=context_count))


def synthetic_attestation(**changes: object) -> MTAACControlAttestation:
    values: dict[str, object] = {
        "protocol_sha256": MTAAC_CONTROL_PROTOCOL_SHA256,
        "pre_result_code_commit": "a" * 40,
        "data_origin": "project_authored_synthetic_fixture",
        "external_data_used": False,
        "fixture_id": "project-authored-mtaac-control-test-v1",
    }
    values.update(changes)
    return MTAACControlAttestation(**values)  # type: ignore[arg-type]


class ProtocolAndAttestationTests(unittest.TestCase):
    def test_exact_protocol_and_caller_commit_are_required(self) -> None:
        protocol = validate_mtaac_control_protocol(PROTOCOL_BYTES)
        self.assertEqual(protocol["protocol_id"], "mtaac-known-script-control-v1")
        self.assertEqual(protocol["protocol_status"], "pre_result_code_frozen")
        validate_mtaac_control_attestation(
            synthetic_attestation(),
            expected_origin="project_authored_synthetic_fixture",
        )

        with self.assertRaisesRegex(MTAACControlError, "protocol bytes"):
            validate_mtaac_control_protocol(PROTOCOL_BYTES + b"\n")
        with self.assertRaisesRegex(MTAACControlError, "pre_result_code_commit"):
            validate_mtaac_control_attestation(
                synthetic_attestation(pre_result_code_commit="main"),
                expected_origin="project_authored_synthetic_fixture",
            )
        with self.assertRaisesRegex(MTAACControlError, "fixture attestation"):
            validate_mtaac_control_attestation(
                synthetic_attestation(external_data_used=True),
                expected_origin="project_authored_synthetic_fixture",
            )
        with self.assertRaisesRegex(MTAACControlError, "fixture attestation"):
            validate_mtaac_control_attestation(
                synthetic_attestation(fixture_id="../private"),
                expected_origin="project_authored_synthetic_fixture",
            )

    def test_real_entry_rejects_wrong_archive_before_split_or_scoring(self) -> None:
        real_attestation = MTAACControlAttestation(
            protocol_sha256=MTAAC_CONTROL_PROTOCOL_SHA256,
            pre_result_code_commit="b" * 40,
            data_origin="fixed_real_source",
            external_data_used=True,
        )
        with self.assertRaisesRegex(
            MTAACControlError,
            "real source admission failed",
        ):
            evaluate_mtaac_control_archive(
                b"not-the-fixed-archive",
                PROTOCOL_BYTES,
                attestation=real_attestation,
            )

    def test_real_entry_stops_before_parse_when_protocol_is_not_frozen(self) -> None:
        protocol = json.loads(PROTOCOL_BYTES)
        protocol["protocol_status"] = "candidate_for_pre_result_code_freeze"
        real_attestation = MTAACControlAttestation(
            protocol_sha256=MTAAC_CONTROL_PROTOCOL_SHA256,
            pre_result_code_commit="b" * 40,
            data_origin="fixed_real_source",
            external_data_used=True,
        )
        with (
            patch(
                "indusbench.mtaac_control.validate_mtaac_control_protocol",
                return_value=protocol,
            ),
            patch("indusbench.mtaac_control.parse_mtaac_archive") as parser,
            self.assertRaisesRegex(
                MTAACControlError,
                "pre_result_code_frozen",
            ),
        ):
            evaluate_mtaac_control_archive(
                b"must-not-be-parsed",
                PROTOCOL_BYTES,
                attestation=real_attestation,
            )
        parser.assert_not_called()

    def test_synthetic_entry_rejects_real_source_commitments(self) -> None:
        corpus = synthetic_corpus(4)
        for field_name, fixed_value in (
            ("input_sha256", MTAAC_REAL_ARCHIVE_SHA256),
            (
                "selected_manifest_sha256",
                MTAAC_REAL_SELECTED_MANIFEST_SHA256,
            ),
        ):
            with self.subTest(field_name=field_name):
                forged = replace(
                    corpus,
                    provenance=replace(
                        corpus.provenance,
                        **{field_name: fixed_value},
                    ),
                )
                with (
                    self.assertRaisesRegex(
                        MTAACControlError,
                        "rejects real-source commitments",
                    ),
                    patch(
                        "indusbench.mtaac_control.parse_mtaac_directory",
                        return_value=forged,
                    ),
                ):
                    evaluate_synthetic_mtaac_control_fixture(
                        synthetic_files(4),
                        PROTOCOL_BYTES,
                        attestation=synthetic_attestation(),
                        anchors_available=False,
                    )

    def test_synthetic_entry_checks_derived_manifest_despite_forged_provenance(
        self,
    ) -> None:
        corpus = synthetic_corpus(4)
        forged = replace(
            corpus,
            provenance=replace(
                corpus.provenance,
                selected_manifest_sha256="sha256:" + "0" * 64,
            ),
        )
        with (
            patch(
                "indusbench.mtaac_control.parse_mtaac_directory",
                return_value=forged,
            ),
            patch(
                "indusbench.mtaac_control._derive_selected_manifest_from_metadata",
                return_value=MTAAC_REAL_SELECTED_MANIFEST_SHA256,
            ),
            self.assertRaisesRegex(
                MTAACControlError,
                "rejects real-source commitments",
            ),
        ):
            evaluate_synthetic_mtaac_control_fixture(
                synthetic_files(4),
                PROTOCOL_BYTES,
                attestation=synthetic_attestation(),
                anchors_available=False,
            )

    def test_synthetic_entry_rejects_a_prebuilt_corpus(self) -> None:
        with self.assertRaisesRegex(
            MTAACControlError,
            "synthetic fixture admission failed",
        ):
            evaluate_synthetic_mtaac_control_fixture(
                synthetic_corpus(4),  # type: ignore[arg-type]
                PROTOCOL_BYTES,
                attestation=synthetic_attestation(),
                anchors_available=False,
            )


class SplitAndDegradationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = synthetic_corpus(40, context_count=6)

    def test_split_is_deterministic_balanced_and_tamper_evident(self) -> None:
        first = build_mtaac_split(self.corpus)
        second = build_mtaac_split(self.corpus)
        self.assertEqual(first, second)
        self.assertEqual(
            sum(entry.partition == "test" for entry in first.entries),
            10,
        )
        cluster_partitions: dict[str, set[str]] = {}
        for entry in first.entries:
            cluster_partitions.setdefault(entry.cluster_identifier, set()).add(entry.partition)
        self.assertTrue(all(len(values) == 1 for values in cluster_partitions.values()))

        tampered_entry = replace(
            first.entries[0],
            partition="test" if first.entries[0].partition == "train" else "train",
        )
        tampered = replace(first, entries=(tampered_entry, *first.entries[1:]))
        with self.assertRaisesRegex(MTAACControlError, "deterministic split"):
            validate_mtaac_split(self.corpus, tampered)

    def test_degradation_is_deterministic_nested_and_tamper_evident(self) -> None:
        split = build_mtaac_split(self.corpus)
        clean = degrade_mtaac_corpus(self.corpus, split, CLEAN_REGIME)
        mild = degrade_mtaac_corpus(self.corpus, split, MILD_REGIME)
        harsh = degrade_mtaac_corpus(self.corpus, split, HARSH_REGIME)
        self.assertEqual(
            mild,
            degrade_mtaac_corpus(self.corpus, split, MILD_REGIME),
        )
        validate_nested_mtaac_degradations(clean, mild, harsh)
        self.assertTrue(
            all(len(line.tokens) <= 7 for doc in mild.observations for line in doc.lines)
        )
        self.assertTrue(
            all(len(line.tokens) <= 4 for doc in harsh.observations for line in doc.lines)
        )

        document = mild.observations[0]
        line = document.lines[0]
        token = line.tokens[0]
        tampered_token = replace(token, observed_form_id="FORGED")
        tampered_line = replace(line, tokens=(tampered_token, *line.tokens[1:]))
        tampered_document = replace(
            document,
            lines=(tampered_line, *document.lines[1:]),
        )
        tampered = replace(
            mild,
            observations=(tampered_document, *mild.observations[1:]),
        )
        with self.assertRaisesRegex(MTAACControlError, "deterministic contract"):
            validate_mtaac_degradation(self.corpus, split, tampered)

    def test_observations_expose_no_raw_or_gold_columns(self) -> None:
        degraded = degrade_mtaac_corpus(
            self.corpus,
            build_mtaac_split(self.corpus),
            MILD_REGIME,
        )
        observation = degraded.observations[0]
        self.assertIsInstance(observation, MTAACObservedDocument)
        serialized = json.dumps(asdict(observation), sort_keys=True)
        for forbidden in (
            "P800",
            "SYNTHETIC_QUANTITY_FORM",
            "synthetic_measure",
            "xpostag",
            "segm",
            "true_class",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_gold_only_edits_do_not_change_split_or_degradation(self) -> None:
        first_files = synthetic_files(40, context_count=6)
        second_files = dict(first_files)
        changed_path = sorted(second_files)[0]
        second_files[changed_path] = second_files[changed_path].replace(
            b"synthetic_quantity[one]\tNU\t_\t_\t_",
            b"synthetic_quantity[alternate]\tNU.detail\tHEAD\tREL\tMISC",
        )
        self.assertNotEqual(first_files[changed_path], second_files[changed_path])
        first = parse_mtaac_directory(first_files)
        second = parse_mtaac_directory(second_files)

        self.assertEqual(first.model_documents, second.model_documents)
        self.assertEqual(
            [document.tokens[0].classes for document in first.gold_documents],
            [document.tokens[0].classes for document in second.gold_documents],
        )
        first_split = build_mtaac_split(first)
        second_split = build_mtaac_split(second)
        self.assertEqual(first_split, second_split)
        for regime in (CLEAN_REGIME, MILD_REGIME, HARSH_REGIME):
            with self.subTest(regime=regime.name):
                self.assertEqual(
                    degrade_mtaac_corpus(first, first_split, regime),
                    degrade_mtaac_corpus(second, second_split, regime),
                )


class EvaluationCorpusFingerprintTests(unittest.TestCase):
    def test_formatting_and_unused_annotation_edits_cannot_launder_a_corpus(
        self,
    ) -> None:
        first_files = synthetic_files(8)
        second_files = {path: raw.replace(b"\n", b"\r\n") for path, raw in first_files.items()}
        changed_path = sorted(second_files)[0]
        second_files[changed_path] = second_files[changed_path].replace(
            b"synthetic_quantity[one]\tNU\t_\t_\t_\r\n",
            b"synthetic_quantity[alternate]\tNU.detail\tHEAD\tREL\tMISC\r\n",
        )
        second_files[changed_path] = second_files[changed_path].replace(
            b"o.1.1\t",
            b"o.1.99\t",
            1,
        )
        first = parse_mtaac_directory(first_files)
        second = parse_mtaac_directory(second_files)
        first_fingerprint = mtaac_control_module._evaluation_corpus_fingerprint(first)
        self.assertEqual(
            first_fingerprint,
            mtaac_control_module._evaluation_corpus_fingerprint(second),
        )
        self.assertNotEqual(
            first.provenance.selected_manifest_sha256,
            second.provenance.selected_manifest_sha256,
        )
        with (
            patch(
                "indusbench.mtaac_control.MTAAC_REAL_EVALUATION_CORPUS_SHA256",
                first_fingerprint,
            ),
            self.assertRaisesRegex(
                MTAACControlError,
                "rejects real-source commitments",
            ),
        ):
            mtaac_control_module._reject_real_source_from_synthetic_entry(second)


class SyntheticInstrumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.files = synthetic_files(128)

    def test_strong_synthetic_fixture_exercises_full_instrument_without_real_go(self) -> None:
        report = evaluate_synthetic_mtaac_control_fixture(
            self.files,
            PROTOCOL_BYTES,
            attestation=synthetic_attestation(),
            null_runs=19,
        )

        self.assertEqual(report["terminal_status"], "fixture_only")
        self.assertTrue(report["real_source_decision_suppressed"])
        self.assertEqual(report["fixture_instrument_status"], "thresholds_passed")
        self.assertTrue(report["decision"]["all_thresholds_passed"])
        self.assertGreaterEqual(
            report["regimes"]["mild"]["observed"]["macro_f1"],
            0.60,
        )
        self.assertEqual(
            report["regimes"]["mild"]["permutation_null"]["runs"],
            19,
        )
        self.assertEqual(
            len(report["regimes"]["mild"]["permutation_null"]["run_values"]),
            19,
        )
        self.assertEqual(
            report["regimes"]["mild"]["permutation_null"]["add_one_empirical_p_greater_or_equal"],
            0.05,
        )
        self.assertEqual(
            report["attestation"]["pre_result_code_commit"],
            "a" * 40,
        )
        self.assertFalse(report["numeric_runtime"]["cross_runtime_byte_identity_claimed"])
        self.assertNotIn("host", report["numeric_runtime"])
        self.assertNotIn("fixture_id", report["attestation"])
        for membership in report["diagnostic_membership"].values():
            self.assertNotIn("metrics", membership)
            self.assertNotIn("aggregate_available", membership)
            self.assertIn(
                "support_adequate_for_future_aggregate",
                membership,
            )
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("P800000", serialized)
        self.assertNotIn("SYNTHETIC_QUANTITY_FORM", serialized)
        self.assertNotIn("SyntheticPerson", serialized)
        self.assertNotIn("document_key", serialized)
        self.assertNotIn("token_key", serialized)

    def test_nonfeature_gold_edits_leave_null_and_metrics_unchanged(self) -> None:
        first_files = synthetic_files(128)
        second_files = dict(first_files)
        changed_path = sorted(second_files)[0]
        second_files[changed_path] = second_files[changed_path].replace(
            b"synthetic_quantity[one]\tNU\t_\t_\t_",
            b"synthetic_quantity[alternate]\tNU.detail\tHEAD\tREL\tMISC",
        )
        first = evaluate_synthetic_mtaac_control_fixture(
            first_files,
            PROTOCOL_BYTES,
            attestation=synthetic_attestation(fixture_id="gold-independence-first-v1"),
            null_runs=3,
        )
        second = evaluate_synthetic_mtaac_control_fixture(
            second_files,
            PROTOCOL_BYTES,
            attestation=synthetic_attestation(fixture_id="gold-independence-second-v1"),
            null_runs=3,
        )
        self.assertNotEqual(
            first["source_commitments"]["input_sha256"],
            second["source_commitments"]["input_sha256"],
        )
        self.assertNotEqual(
            first["source_commitments"]["selected_manifest_sha256"],
            second["source_commitments"]["selected_manifest_sha256"],
        )
        self.assertEqual(
            first["source_commitments"]["evaluation_corpus_sha256"],
            second["source_commitments"]["evaluation_corpus_sha256"],
        )
        for report in (first, second):
            del report["source_commitments"]["input_sha256"]
            del report["source_commitments"]["selected_manifest_sha256"]
        self.assertEqual(first, second)

    def test_anchor_free_fixture_emits_no_scientific_metric_or_decision(self) -> None:
        report = evaluate_synthetic_mtaac_control_fixture(
            self.files,
            PROTOCOL_BYTES,
            attestation=synthetic_attestation(),
            anchors_available=False,
            null_runs=3,
        )
        self.assertEqual(report["terminal_status"], "fixture_only")
        self.assertEqual(report["fixture_instrument_status"], "not_identifiable")
        self.assertNotIn("regimes", report)
        self.assertNotIn("decision", report)
        self.assertNotIn("macro_f1", repr(report))
        self.assertNotIn("permutation_null", repr(report))

    def test_small_fixture_is_insufficient_without_searching_another_split(self) -> None:
        report = evaluate_synthetic_mtaac_control_fixture(
            synthetic_files(24),
            PROTOCOL_BYTES,
            attestation=synthetic_attestation(fixture_id="small-fixture-v1"),
            null_runs=3,
        )
        self.assertEqual(report["terminal_status"], "fixture_only")
        self.assertEqual(report["fixture_instrument_status"], "insufficient_evidence")
        self.assertNotIn("regimes", report)
        self.assertNotIn("decision", report)

    def test_decision_function_fails_when_a_frozen_threshold_is_missed(self) -> None:
        report = evaluate_synthetic_mtaac_control_fixture(
            self.files,
            PROTOCOL_BYTES,
            attestation=synthetic_attestation(fixture_id="decision-fixture-v1"),
            null_runs=19,
        )
        clean = report["regimes"]["clean"]
        mild = json.loads(json.dumps(report["regimes"]["mild"]))
        mild["observed_minus_decision_reference"] = 0.0
        decision = apply_mtaac_control_decision(
            clean,
            mild,
            support_passed=True,
            integrity_passed=True,
        )
        self.assertFalse(decision["all_thresholds_passed"])
        self.assertFalse(decision["mild_criteria"]["minimum_observed_minus_decision_reference"])


if __name__ == "__main__":
    unittest.main()
