from __future__ import annotations

import copy
import unittest
from pathlib import Path

from indusbench.schema_validation import validate_schema_instance
from tests.test_v4_cli import _report

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "mtaac-v4-development-report.schema.json"


class V4DevelopmentReportSchemaTests(unittest.TestCase):
    def test_advance_and_killed_reports_match_the_closed_schema(self) -> None:
        for terminal_status in ("advance", "development_killed"):
            with self.subTest(terminal_status=terminal_status):
                self.assertEqual(
                    [],
                    validate_schema_instance(
                        _report(terminal_status=terminal_status),
                        SCHEMA,
                    ),
                )

    def test_schema_rejects_identifier_detail_and_boundary_changes(self) -> None:
        leaked = _report()
        leaked["document_id"] = "forbidden"
        self.assertTrue(validate_schema_instance(leaked, SCHEMA))

        changed = _report()
        changed["data_boundary"]["v2_holdout_scored"] = True
        self.assertTrue(validate_schema_instance(changed, SCHEMA))

        changed_profile = _report()
        changed_profile["profile_contract"]["identity_serialized"] = True
        self.assertTrue(validate_schema_instance(changed_profile, SCHEMA))

    def test_schema_enforces_terminal_model_consistency(self) -> None:
        advance_without_model = _report()
        advance_without_model["final_development_model"] = {
            "fitted": False,
            "fit_rule": "fit_all_271_families_only_after_advance",
            "model_state_commitment": None,
            "optimizer": None,
        }
        self.assertTrue(validate_schema_instance(advance_without_model, SCHEMA))

        killed_with_model = _report(terminal_status="development_killed")
        killed_with_model["final_development_model"] = copy.deepcopy(
            _report()["final_development_model"]
        )
        self.assertTrue(validate_schema_instance(killed_with_model, SCHEMA))


if __name__ == "__main__":
    unittest.main()
