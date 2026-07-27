from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from indusbench.cli import main
from indusbench.io import encode_json
from indusbench.kp1982_bootstrap import (
    EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE,
    EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
    KP1982BootstrapError,
    build_bootstrap_assignment,
    verify_bootstrap_assignment_bytes,
)
from indusbench.kp1982_layout import build_layout_proposal
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = ROOT / "registry" / "kp1982_batch0.json"
LAYOUT_SEED = ROOT / "registry" / "kp1982_batch0_layout_seed.json"
ASSIGNMENT_SCHEMA = ROOT / "schemas" / "kp1982-bootstrap-assignment.schema.json"
REAL_PAGE_ENV = (
    "INDUSBENCH_KP1982_PAGE20_PBM",
    "INDUSBENCH_KP1982_PAGE21_PBM",
)
CELL_KEYS = {
    "cell_id",
    "page_index",
    "lane_index",
    "row_index",
    "proposed_cell_bbox",
    "proposed_context_bbox",
    "cell_crop_sha256",
    "cell_crop_byte_size",
    "context_crop_sha256",
    "context_crop_byte_size",
}
FORBIDDEN_KEYS = {
    "accepted_occupancy",
    "accepted_observation",
    "canonical_digits",
    "identifier_proposal",
    "lower_primary_identifier",
    "machine_identifier_proposal",
    "occupancy",
    "occupancy_proposal",
    "ocr_output",
    "raw_text",
    "upper_catalog_rank",
}


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


def recursively_collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for child in value.values():
            keys.update(recursively_collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(recursively_collect_keys(child))
    return keys


def real_page_bytes() -> list[bytes]:
    return [Path(os.environ[name]).read_bytes() for name in REAL_PAGE_ENV]


class KP1982BootstrapAssignmentTests(unittest.TestCase):
    def test_v1_assignment_golden_is_an_independent_test_sentinel(self) -> None:
        self.assertEqual(415621, EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE)
        self.assertEqual(
            "sha256:0f927340763084329be3c25c25f9bfd51e2b03e6c3177a66780e9320c8bf3761",
            EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
        )

    def test_schema_fixes_a_closed_value_stripped_roster(self) -> None:
        schema = json.loads(ASSIGNMENT_SCHEMA.read_text(encoding="utf-8"))
        self.assertNotIn("blind", schema["title"].lower())
        self.assertNotIn("blind", schema["properties"]["status"]["const"])
        self.assertNotIn("blind", schema["properties"]["scientific_scope"]["const"])
        cells = schema["properties"]["cells"]
        cell = schema["$defs"]["cell"]
        self.assertEqual(700, cells["minItems"])
        self.assertEqual(700, cells["maxItems"])
        self.assertTrue(cells["uniqueItems"])
        self.assertFalse(cell["additionalProperties"])
        self.assertEqual(CELL_KEYS, set(cell["required"]))
        self.assertEqual(CELL_KEYS, set(cell["properties"]))
        self.assertTrue(FORBIDDEN_KEYS.isdisjoint(cell["properties"]))

        assurances = schema["properties"]["assurances"]["properties"]
        self.assertEqual(
            {
                "source_contract_exact_bytes_verified",
                "layout_seed_exact_bytes_verified",
                "layout_proposal_exact_bytes_verified",
                "canonical_page_bitmaps_verified",
            },
            {key for key, contract in assurances.items() if contract.get("const") is True},
        )
        self.assertTrue(
            all(
                assurances[key]["const"] is False
                for key in (
                    "cell_geometry_accepted",
                    "occupancy_accepted",
                    "human_review_complete",
                    "reviewer_independence_verified",
                    "reviewer_blinding_verified",
                    "identifiers_transcribed",
                    "public_release_authorized",
                    "evaluation_admissible",
                    "decipherment",
                )
            )
        )

    def test_nonfixed_layout_proposal_is_rejected_before_assignment_build(self) -> None:
        with self.assertRaisesRegex(KP1982BootstrapError, "fixed V1 bytes"):
            build_bootstrap_assignment(
                SOURCE_CONTRACT.read_bytes(),
                LAYOUT_SEED.read_bytes(),
                [b"", b""],
                b"{}",
            )

    @unittest.skipUnless(
        all(os.environ.get(name) for name in REAL_PAGE_ENV),
        "set both INDUSBENCH_KP1982_PAGE*_PBM paths",
    )
    def test_fixed_pages_build_deterministic_value_stripped_assignment(self) -> None:
        source_bytes = SOURCE_CONTRACT.read_bytes()
        seed_bytes = LAYOUT_SEED.read_bytes()
        page_bytes = real_page_bytes()
        proposal = build_layout_proposal(source_bytes, seed_bytes, page_bytes)
        proposal_bytes = encode_json(proposal)

        first = build_bootstrap_assignment(
            source_bytes,
            seed_bytes,
            page_bytes,
            proposal_bytes,
        )
        second = build_bootstrap_assignment(
            source_bytes,
            seed_bytes,
            page_bytes,
            proposal_bytes,
        )
        self.assertEqual(first, second)
        self.assertEqual(700, len(first["cells"]))
        self.assertEqual([], validate_schema_instance(first, ASSIGNMENT_SCHEMA))
        self.assertTrue(FORBIDDEN_KEYS.isdisjoint(recursively_collect_keys(first)))
        self.assertTrue(all(set(cell) == CELL_KEYS for cell in first["cells"]))
        for proposed, assigned in zip(proposal["cells"], first["cells"], strict=True):
            self.assertEqual(proposed["cell_id"], assigned["cell_id"])
            self.assertEqual(proposed["cell_bbox"], assigned["proposed_cell_bbox"])
            self.assertEqual(
                proposed["context_bbox"],
                assigned["proposed_context_bbox"],
            )
            self.assertNotIn("occupancy_proposal", assigned)
            self.assertNotIn("accepted_occupancy", assigned)

        canonical = encode_json(first)
        self.assertEqual(EXPECTED_BOOTSTRAP_ASSIGNMENT_BYTE_SIZE, len(canonical))
        self.assertEqual(
            EXPECTED_BOOTSTRAP_ASSIGNMENT_SHA256,
            "sha256:" + hashlib.sha256(canonical).hexdigest(),
        )
        verification = verify_bootstrap_assignment_bytes(
            source_bytes,
            seed_bytes,
            page_bytes,
            proposal_bytes,
            canonical,
        )
        self.assertTrue(verification["assignment_canonical_bytes_verified"])
        self.assertTrue(verification["machine_answer_values_withheld"])
        self.assertFalse(verification["human_review_complete"])
        self.assertFalse(verification["reviewer_independence_verified"])
        self.assertFalse(verification["reviewer_blinding_verified"])
        self.assertFalse(verification["public_release_authorized"])
        self.assertFalse(verification["evaluation_admissible"])
        self.assertFalse(verification["decipherment"])

        tampered = deepcopy(first)
        tampered["cells"][0]["cell_crop_sha256"] = f"sha256:{'0' * 64}"
        with self.assertRaisesRegex(KP1982BootstrapError, "pixel recomputation"):
            verify_bootstrap_assignment_bytes(
                source_bytes,
                seed_bytes,
                page_bytes,
                proposal_bytes,
                encode_json(tampered),
            )

        noncanonical = canonical.replace(b"{", b"{ ", 1)
        with self.assertRaisesRegex(KP1982BootstrapError, "pixel recomputation"):
            verify_bootstrap_assignment_bytes(
                source_bytes,
                seed_bytes,
                page_bytes,
                proposal_bytes,
                noncanonical,
            )

    def test_cli_failure_is_sanitized_and_does_not_create_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            temporary.chmod(0o700)
            page20 = temporary / "PRIVATE-PAGE-20.pbm"
            page21 = temporary / "PRIVATE-PAGE-21.pbm"
            proposal = temporary / "PRIVATE-PROPOSAL.json"
            output = temporary / "PRIVATE-ASSIGNMENT.json"
            page20.write_bytes(b"P4\n8 1\n\x80")
            page21.write_bytes(b"P4\n8 1\n\x80")
            proposal.write_bytes(b"{}")
            proposal.chmod(0o600)

            result, stdout, stderr = run_cli(
                [
                    "prepare-kp1982-bootstrap-assignment",
                    str(page20),
                    str(page21),
                    str(proposal),
                    str(output),
                ]
            )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1982 bootstrap assignment preparation failed\n",
                stderr,
            )
            for path in (page20, page21, proposal, output):
                self.assertNotIn(path.name, stderr)
            self.assertFalse(output.exists())

    def test_cli_does_not_claim_unknown_published_content_is_canonical(self) -> None:
        with (
            patch("indusbench.cli._read_regular_bytes", return_value=b"fixed"),
            patch("indusbench.cli._read_private_regular_bytes", return_value=b"proposal"),
            patch("indusbench.cli.build_bootstrap_assignment", return_value={"fixed": True}),
            patch("indusbench.cli._write_private_json_no_replace", return_value=(False, False)),
        ):
            result, stdout, stderr = run_cli(
                [
                    "prepare-kp1982-bootstrap-assignment",
                    "page-20.pbm",
                    "page-21.pbm",
                    "proposal.json",
                    "assignment.json",
                ]
            )
        self.assertEqual(1, result)
        self.assertEqual("", stderr)
        summary = json.loads(stdout)
        self.assertFalse(summary["valid"])
        self.assertFalse(summary["written"])
        self.assertTrue(summary["destination_may_exist"])
        self.assertEqual("committed_content_unknown", summary["postcondition"])
        self.assertFalse(summary["output_content_verified"])
        self.assertFalse(summary["assignment_canonical_bytes_verified"])
        self.assertFalse(summary["machine_answer_values_withheld"])
        self.assertFalse(summary["private_storage_verified"])
        self.assertFalse(summary["human_review_complete"])
        self.assertFalse(summary["decipherment"])

    def test_cli_private_io_contract_with_mocked_scientific_boundary(self) -> None:
        fake_assignment = {
            "claim_class": "synthetic_private_io_fixture",
            "decipherment": False,
        }
        fake_verification = {
            "valid": True,
            "claim_class": "private_bootstrap_assignment_only",
            "assignment_canonical_bytes_verified": True,
            "machine_answer_values_withheld": True,
            "human_review_complete": False,
            "decipherment": False,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            temporary.chmod(0o700)
            page20 = temporary / "page-20.pbm"
            page21 = temporary / "page-21.pbm"
            proposal = temporary / "proposal.json"
            output = temporary / "assignment.json"
            page20.write_bytes(b"synthetic page 20")
            page21.write_bytes(b"synthetic page 21")
            proposal.write_bytes(b"synthetic private proposal")
            proposal.chmod(0o600)
            prepare_args = [
                "prepare-kp1982-bootstrap-assignment",
                str(page20),
                str(page21),
                str(proposal),
                str(output),
            ]

            with patch(
                "indusbench.cli.build_bootstrap_assignment",
                return_value=fake_assignment,
            ):
                result, stdout, stderr = run_cli(prepare_args)
            self.assertEqual(0, result, stderr)
            self.assertTrue(json.loads(stdout)["private_storage_verified"])
            self.assertEqual(encode_json(fake_assignment), output.read_bytes())
            self.assertEqual(0o600, output.stat().st_mode & 0o777)

            with patch(
                "indusbench.cli.build_bootstrap_assignment",
                return_value=fake_assignment,
            ):
                result, stdout, stderr = run_cli(prepare_args)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertNotIn(output.name, stderr)
            self.assertEqual(encode_json(fake_assignment), output.read_bytes())

            verify_args = [
                "verify-kp1982-bootstrap-assignment",
                str(page20),
                str(page21),
                str(proposal),
                str(output),
            ]
            with patch(
                "indusbench.cli.verify_bootstrap_assignment_bytes",
                return_value=fake_verification,
            ):
                result, stdout, stderr = run_cli(verify_args)
            self.assertEqual(0, result, stderr)
            self.assertTrue(json.loads(stdout)["private_storage_verified"])

            output.chmod(0o644)
            with patch(
                "indusbench.cli.verify_bootstrap_assignment_bytes",
                return_value=fake_verification,
            ):
                result, stdout, stderr = run_cli(verify_args)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertNotIn(output.name, stderr)

    @unittest.skipUnless(
        all(os.environ.get(name) for name in REAL_PAGE_ENV),
        "set both INDUSBENCH_KP1982_PAGE*_PBM paths",
    )
    def test_cli_private_modes_no_overwrite_and_verification(self) -> None:
        source_bytes = SOURCE_CONTRACT.read_bytes()
        seed_bytes = LAYOUT_SEED.read_bytes()
        page_bytes = real_page_bytes()
        proposal_bytes = encode_json(build_layout_proposal(source_bytes, seed_bytes, page_bytes))

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory).resolve()
            temporary.chmod(0o700)
            proposal = temporary / "proposal.json"
            output = temporary / "assignment.json"
            proposal.write_bytes(proposal_bytes)
            proposal.chmod(0o600)
            prepare_args = [
                "prepare-kp1982-bootstrap-assignment",
                os.environ[REAL_PAGE_ENV[0]],
                os.environ[REAL_PAGE_ENV[1]],
                str(proposal),
                str(output),
            ]

            result, stdout, stderr = run_cli(prepare_args)
            self.assertEqual(0, result, stderr)
            summary = json.loads(stdout)
            self.assertTrue(summary["written"])
            self.assertFalse(summary["counts_disclosed"])
            self.assertTrue(summary["machine_answer_values_withheld"])
            self.assertTrue(summary["private_storage_verified"])
            self.assertFalse(summary["cell_geometry_accepted"])
            self.assertFalse(summary["reviewer_independence_verified"])
            self.assertFalse(summary["reviewer_blinding_verified"])
            self.assertFalse(summary["public_release_authorized"])
            self.assertFalse(summary["evaluation_admissible"])
            self.assertFalse(summary["decipherment"])
            self.assertEqual(0o600, output.stat().st_mode & 0o777)
            original = output.read_bytes()
            assignment = json.loads(original)
            self.assertEqual([], validate_schema_instance(assignment, ASSIGNMENT_SCHEMA))
            self.assertTrue(FORBIDDEN_KEYS.isdisjoint(recursively_collect_keys(assignment)))

            result, stdout, stderr = run_cli(prepare_args)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertNotIn(output.name, stderr)
            self.assertEqual(original, output.read_bytes())
            self.assertEqual(0o600, output.stat().st_mode & 0o777)

            result, stdout, stderr = run_cli(
                [
                    "verify-kp1982-bootstrap-assignment",
                    os.environ[REAL_PAGE_ENV[0]],
                    os.environ[REAL_PAGE_ENV[1]],
                    str(proposal),
                    str(output),
                ]
            )
            self.assertEqual(0, result, stderr)
            verification = json.loads(stdout)
            self.assertTrue(verification["assignment_canonical_bytes_verified"])
            self.assertTrue(verification["machine_answer_values_withheld"])
            self.assertTrue(verification["private_storage_verified"])
            self.assertFalse(verification["human_review_complete"])
            self.assertFalse(verification["reviewer_independence_verified"])
            self.assertFalse(verification["reviewer_blinding_verified"])
            self.assertFalse(verification["public_release_authorized"])
            self.assertFalse(verification["evaluation_admissible"])
            self.assertFalse(verification["decipherment"])

            output.chmod(0o644)
            result, stdout, stderr = run_cli(
                [
                    "verify-kp1982-bootstrap-assignment",
                    os.environ[REAL_PAGE_ENV[0]],
                    os.environ[REAL_PAGE_ENV[1]],
                    str(proposal),
                    str(output),
                ]
            )
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertNotIn(output.name, stderr)


if __name__ == "__main__":
    unittest.main()
