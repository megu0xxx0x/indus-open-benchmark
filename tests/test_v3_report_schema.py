from __future__ import annotations

import copy
import unittest
from pathlib import Path

from indusbench.schema_validation import validate_schema_instance
from tests.test_v3_runner import _bundle, _run_synthetic

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/mtaac-v3-development-report.schema.json"


class V3DevelopmentReportSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = _run_synthetic(_bundle())
        # The fast synthetic runner test temporarily substitutes 25 families
        # for the exact production boundary of 271.
        cls.report["data_boundary"]["model_training_family_count"] = 271

    def test_aggregate_report_matches_closed_schema(self) -> None:
        self.assertEqual([], validate_schema_instance(self.report, SCHEMA))

    def test_schema_rejects_identifier_detail_and_boundary_changes(self) -> None:
        leaked = copy.deepcopy(self.report)
        leaked["document_id"] = "forbidden"
        self.assertTrue(validate_schema_instance(leaked, SCHEMA))

        changed = copy.deepcopy(self.report)
        changed["data_boundary"]["v2_holdout_scored"] = True
        self.assertTrue(validate_schema_instance(changed, SCHEMA))


if __name__ == "__main__":
    unittest.main()
