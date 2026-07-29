from __future__ import annotations

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from unittest.mock import patch

from indusbench import cli as cli_module
from indusbench.kp1979_synthetic_control import run_synthetic_control


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = cli_module.main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


class KP1979SyntheticControlCliTests(unittest.TestCase):
    def test_cli_reports_the_fixed_synthetic_failure_and_nonclaims(self) -> None:
        result, stdout, stderr = run_cli(["run-kp1979-label-lattice-synthetic-control"])

        self.assertEqual(0, result, stderr)
        self.assertEqual("", stderr)
        report = json.loads(stdout)
        self.assertEqual("not_qualified", report["status"])
        self.assertEqual(
            "two-column-label-lattice-v1",
            report["target_algorithm_id"],
        )
        self.assertEqual("synthetic_control", report["reference_use"])
        self.assertTrue(report["synthetic_only"])
        for nonclaim in (
            "real_accuracy",
            "reference_accepted",
            "future_evaluation_opened",
            "reserved_sources_read",
            "decipherment",
            "prize_submission_eligible",
        ):
            self.assertFalse(report[nonclaim])

    def test_cli_rejects_an_unsafe_claim_state(self) -> None:
        unsafe = replace(run_synthetic_control(), real_accuracy=True)
        with patch.object(
            cli_module,
            "run_synthetic_control",
            return_value=unsafe,
        ):
            result, stdout, stderr = run_cli(["run-kp1979-label-lattice-synthetic-control"])

        self.assertEqual(1, result)
        self.assertEqual("", stdout)
        self.assertEqual(
            "indusbench: KP1979 synthetic control returned an unsafe claim state\n",
            stderr,
        )


if __name__ == "__main__":
    unittest.main()
