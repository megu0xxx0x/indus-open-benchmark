from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "benchmark/results/oracc-ed3b-validation-source-v1.json"
SCHEMA_PATH = ROOT / "schemas/oracc-ed3b-source-receipt.schema.json"
RESULT_SHA256 = "bdcf01a1a04dee7f14b64b396de4240f40c8ab0826e19096f113e091b94c3bd3"
SOURCE_FREEZE_COMMIT = "2537dd099e708039c49d96598ad6b379eddeafd8"
PROTOCOL_SHA256 = "sha256:ff495b0f9da96153c428614b7677c4099c35ea3035f414999473e2c807d07ba3"


class ORACCEd3bPublishedSourceReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = RESULT_PATH.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != RESULT_SHA256:
            raise AssertionError("published ORACC ED3b source receipt bytes changed")
        cls.receipt = json.loads(cls.raw)

    def test_receipt_matches_closed_schema_and_source_freeze(self) -> None:
        self.assertEqual([], validate_schema_instance(self.receipt, SCHEMA_PATH))
        self.assertEqual("source_qualified", self.receipt["terminal_status"])
        self.assertEqual(SOURCE_FREEZE_COMMIT, self.receipt["source_freeze_commit"])
        self.assertEqual(PROTOCOL_SHA256, self.receipt["protocol_sha256"])
        self.assertFalse(self.receipt["model_executed"])
        self.assertFalse(self.receipt["scientific_metrics_emitted"])
        self.assertEqual(3_338, self.receipt["selection"]["qualified_document_count"])
        self.assertEqual(
            226_618,
            self.receipt["projection"]["qualified_lemma_token_count"],
        )
        self.assertEqual(
            226_610,
            self.receipt["projection"]["scorable_lemma_token_count"],
        )
        self.assertEqual(8, self.receipt["projection"]["annotation_unknown_token_count"])
        self.assertTrue(self.receipt["support_gate"]["all_classes_pass"])

    def test_receipt_contains_no_private_topology_or_source_identifier(self) -> None:
        text = self.raw.decode("utf-8")
        forbidden_patterns = (
            r"\bP[0-9]{6}\b",
            r"(?<![0-9])(?:[0-9]{1,3}[.]){3}[0-9]{1,3}(?![0-9])",
            r"/(?:home|Users|private/tmp)/",
            r"\bssh://",
            r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY",
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}",
        )
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
