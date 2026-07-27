from __future__ import annotations

import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from indusbench.audit import (
    audit_leakage,
    extract_catalog_crosswalks,
    extract_image_hashes,
    extract_normalized_sequences,
)
from indusbench.baseline import UnigramBaseline, extract_sequences
from indusbench.cli import main
from indusbench.controls import global_sign_shuffle
from indusbench.io import write_jsonl
from indusbench.manifest import build_manifest
from indusbench.null_evaluation import evaluate_shuffle_null
from indusbench.split_manifest import split_member
from indusbench.splits import (
    deterministic_family_split,
    deterministic_leakage_safe_split,
    duplicate_family_key,
    leave_one_site_out,
)
from indusbench.transcription_admission import (
    UNADMITTED_TRANSCRIPTION_MESSAGE,
    TranscriptionAdmissionError,
    has_unadmitted_transcription_bridge,
)
from indusbench.treewidth_audit import extract_treewidth_sequences
from tests.test_validation import valid_artifact


def _marked_artifact(marker: Any) -> dict[str, Any]:
    record = valid_artifact("SYN:A999")
    record["duplicate_family_id"] = "SYN:F999"
    record["extensions"] = {"indusbench:transcription_bridge": marker}
    return record


class TranscriptionAdmissionTests(unittest.TestCase):
    MARKERS = ({}, None, "caller-asserted-admission")

    def assert_fixed_rejection(self, operation: Callable[[], object]) -> None:
        with self.assertRaises(TranscriptionAdmissionError) as raised:
            operation()
        self.assertEqual(UNADMITTED_TRANSCRIPTION_MESSAGE, str(raised.exception))
        self.assertNotIn("SYN:A999", str(raised.exception))
        self.assertNotIn("SYN:001", str(raised.exception))

    def test_marker_presence_is_unadmitted_regardless_of_value(self) -> None:
        for marker in self.MARKERS:
            with self.subTest(marker=marker):
                record = _marked_artifact(marker)
                self.assertTrue(has_unadmitted_transcription_bridge(record))
                self.assertEqual([], extract_sequences([record]))
                self.assert_fixed_rejection(lambda record=record: UnigramBaseline().fit([record]))

    def test_treewidth_canonical_and_artifact_flat_reject_marked_records(self) -> None:
        for marker in self.MARKERS:
            for sequence_unit in ("canonical_line", "artifact_flat"):
                with self.subTest(marker=marker, sequence_unit=sequence_unit):
                    record = _marked_artifact(marker)
                    self.assert_fixed_rejection(
                        lambda record=record, sequence_unit=sequence_unit: (
                            extract_treewidth_sequences(
                                [record],
                                sequence_unit=sequence_unit,
                            )
                        )
                    )

    def test_leakage_extractors_and_audit_reject_marked_records(self) -> None:
        extractors = (
            extract_image_hashes,
            extract_catalog_crosswalks,
            extract_normalized_sequences,
        )
        for marker in self.MARKERS:
            record = _marked_artifact(marker)
            for extractor in extractors:
                with self.subTest(marker=marker, extractor=extractor.__name__):
                    self.assert_fixed_rejection(
                        lambda extractor=extractor, record=record: extractor(record)
                    )
            with self.subTest(marker=marker, extractor="audit_leakage"):
                self.assert_fixed_rejection(lambda record=record: audit_leakage([record], []))

    def test_public_split_flows_reject_marked_records(self) -> None:
        for marker in self.MARKERS:
            record = _marked_artifact(marker)
            operations = (
                lambda record=record: split_member(record),
                lambda record=record: duplicate_family_key(record),
                lambda record=record: deterministic_family_split([record], test_fraction=0.0),
                lambda record=record: deterministic_leakage_safe_split([record], test_fraction=0.0),
                lambda record=record: leave_one_site_out([record]),
            )
            for operation in operations:
                with self.subTest(marker=marker, operation=operation):
                    self.assert_fixed_rejection(operation)

    def test_evaluation_transform_and_manifest_reject_marked_records(self) -> None:
        clean = valid_artifact("SYN:CLEAN")
        for marker in self.MARKERS:
            record = _marked_artifact(marker)
            operations = (
                lambda record=record: evaluate_shuffle_null([record], [clean], runs=1),
                lambda record=record: global_sign_shuffle([record], seed=1),
                lambda record=record: build_manifest([record], schema_version="0.1.0"),
            )
            for operation in operations:
                with self.subTest(marker=marker, operation=operation):
                    self.assert_fixed_rejection(operation)

    def test_control_shuffle_cli_does_not_write_marked_sentinel(self) -> None:
        for marker in self.MARKERS:
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                corpus = directory / "private.jsonl"
                output = directory / "must-not-exist.jsonl"
                record = _marked_artifact(marker)
                record["artifact_id"] = "DO-NOT-DISCLOSE"
                record["source_records"][0]["source_id"] = "external-indusbench"
                record["source_records"][0]["locator"] = "https://invalid.example/private-record"
                write_jsonl(corpus, [record])

                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = main(
                        [
                            "control-shuffle",
                            str(corpus),
                            str(output),
                            "--seed",
                            "1",
                        ]
                    )

                self.assertEqual(1, result)
                self.assertFalse(output.exists())
                self.assertEqual("", stdout.getvalue())
                self.assertEqual(
                    f"indusbench: {UNADMITTED_TRANSCRIPTION_MESSAGE}\n",
                    stderr.getvalue(),
                )
                self.assertNotIn("DO-NOT-DISCLOSE", stderr.getvalue())
                self.assertNotIn("private-record", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
