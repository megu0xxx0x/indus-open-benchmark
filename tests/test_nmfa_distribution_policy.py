from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.verify_nmfa_measurement_installed_distribution import (
    metadata_preserves_exact_requirements as measurement_requirements_valid,
)
from tests.verify_nmfa_preflight_installed_distribution import (
    metadata_preserves_exact_requirements as preflight_requirements_valid,
)
from tests.verify_nmfa_preregistration_installed_distribution import (
    metadata_preserves_exact_requirements as preregistration_requirements_valid,
)
from tests.verify_nmfa_resampling_installed_distribution import (
    metadata_preserves_exact_requirements as resampling_requirements_valid,
)
from tests.verify_nmfa_selector_installed_distribution import (
    metadata_preserves_exact_requirements as selector_requirements_valid,
)

ROOT = Path(__file__).resolve().parents[1]


class NMFADistributionPolicyTest(unittest.TestCase):
    def test_exact_requirement_parser_allows_only_unrelated_additions(self) -> None:
        expected = (
            "attrs==26.1.0",
            "typing-extensions==4.16.0; python_version < '3.13'",
        )
        valid = (
            "Metadata-Version: 2.4\n"
            "Requires-Dist: attrs==26.1.0\n"
            "Requires-Dist: cryptography==50.0.0\n"
            "Requires-Dist: typing-extensions==4.16.0; python_version < '3.13'\n\n"
        )
        invalid = (
            valid,
            valid.replace("Requires-Dist: attrs==26.1.0\n", ""),
            valid.replace(
                "Requires-Dist: attrs==26.1.0\n",
                "Requires-Dist: attrs==26.1.0\nRequires-Dist: attrs>=0\n",
            ),
            valid.replace("attrs==26.1.0", "attrs==26.1.0,!=26.1.0"),
            valid.replace(
                "Requires-Dist: attrs==26.1.0\n",
                "Requires-Dist: attrs==26.1.0\nRequires-Dist: attrs==26.1.0\n",
            ),
        )
        for validator in (
            preflight_requirements_valid,
            preregistration_requirements_valid,
            selector_requirements_valid,
            measurement_requirements_valid,
            resampling_requirements_valid,
        ):
            self.assertTrue(validator(valid, expected))
            for metadata in invalid[1:]:
                self.assertFalse(validator(metadata, expected))

    def test_legacy_ci_only_rows_remain_historical_bundle_commitments(self) -> None:
        bundle = json.loads(
            (
                ROOT / "benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json"
            ).read_text()
        )
        historical = {
            row["path"]: (row["bytes"], row["sha256"])
            for row in bundle["files"]
            if row["verification"] == "ci_only"
        }
        self.assertEqual(
            historical,
            {
                "pyproject.toml": (
                    5175,
                    "sha256:c81b01d0ceccf915932a6c238de2a28794e569f12f675773702847ee169f8e15",
                ),
                "uv.lock": (
                    49644,
                    "sha256:d9401bcbec41dcb3ca6091192f91e4cf197c6f78fd1bc7dac474db3da01510cf",
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
