from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TypedDict
from unittest.mock import patch

import indusbench.cli as cli_module
from indusbench.cli import build_parser, main
from indusbench.io import encode_json
from indusbench.kp1979_sign_template_roster import KP1979SignTemplateRosterError
from tests.test_kp1979_sign_template_roster import OCCUPIED_ID, inputs


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        result = main(arguments)
    return result, stdout.getvalue(), stderr.getvalue()


def write_private(path: Path, raw_bytes: bytes) -> None:
    path.write_bytes(raw_bytes)
    path.chmod(0o600)


class InputPaths(TypedDict):
    catalog: Path
    geometry: Path
    glyph_dir: Path
    private: Path


class KP1979SignTemplateRosterCLITests(unittest.TestCase):
    def make_inputs(self, root: Path) -> InputPaths:
        catalog_bytes, geometry_bytes, glyphs = inputs()
        private = root / "private"
        private.mkdir(mode=0o700)
        private.chmod(0o700)
        glyph_dir = root / "glyphs"
        glyph_dir.mkdir(mode=0o700)
        glyph_dir.chmod(0o700)
        catalog = private / "PRIVATE-CATALOG.json"
        geometry = private / "PRIVATE-GEOMETRY.json"
        write_private(catalog, catalog_bytes)
        write_private(geometry, geometry_bytes)
        for variant_id, glyph_bytes in glyphs.items():
            write_private(glyph_dir / f"{variant_id}.pbm", glyph_bytes)
        return {
            "catalog": catalog,
            "geometry": geometry,
            "glyph_dir": glyph_dir,
            "private": private,
        }

    @staticmethod
    def prepare_arguments(paths: InputPaths, output: Path) -> list[str]:
        return [
            "prepare-kp1979-sign-template-roster",
            str(paths["catalog"]),
            str(paths["geometry"]),
            str(paths["glyph_dir"]),
            str(output),
        ]

    @staticmethod
    def verify_arguments(paths: InputPaths, roster: Path) -> list[str]:
        return [
            "verify-kp1979-sign-template-roster",
            str(paths["catalog"]),
            str(paths["geometry"]),
            str(paths["glyph_dir"]),
            str(roster),
        ]

    def assert_safe_summary(self, summary: dict[str, object]) -> None:
        self.assertEqual(
            "private_kp1979_sign_template_roster_only",
            summary["claim_class"],
        )
        self.assertFalse(summary["counts_disclosed"])
        self.assertFalse(summary["private_values_disclosed"])
        self.assertFalse(summary["record_ids_disclosed"])
        self.assertFalse(summary["digests_disclosed"])
        self.assertFalse(summary["paths_disclosed"])
        self.assertFalse(summary["catalog_values_accepted"])
        self.assertFalse(summary["sign_identity_accepted"])
        self.assertFalse(summary["human_review_complete"])
        self.assertFalse(summary["public_release_authorized"])
        self.assertFalse(summary["evaluation_admissible"])
        self.assertFalse(summary["decipherment"])
        self.assertFalse(summary["prize_submission_eligible"])

    def test_parser_exposes_only_closed_prepare_and_verify_surfaces(self) -> None:
        parser = build_parser()
        prepared = parser.parse_args(
            [
                "prepare-kp1979-sign-template-roster",
                "catalog.json",
                "geometry.json",
                "glyphs",
                "roster.json",
            ]
        )
        self.assertEqual(Path("catalog.json"), prepared.catalog)
        self.assertEqual(Path("geometry.json"), prepared.geometry_manifest)
        self.assertEqual(Path("glyphs"), prepared.glyph_pbm_dir)
        self.assertEqual(Path("roster.json"), prepared.output)
        self.assertIs(cli_module._command_prepare_kp1979_sign_template_roster, prepared.handler)

        verified = parser.parse_args(
            [
                "verify-kp1979-sign-template-roster",
                "catalog.json",
                "geometry.json",
                "glyphs",
                "roster.json",
            ]
        )
        self.assertEqual(Path("roster.json"), verified.roster)
        self.assertIs(cli_module._command_verify_kp1979_sign_template_roster, verified.handler)

        with (
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            parser.parse_args(
                [
                    "prepare-kp1979-sign-template-roster",
                    "catalog.json",
                    "geometry.json",
                    "glyphs",
                    "roster.json",
                    "--partition",
                    "future_evaluation",
                ]
            )

    def test_prepare_and_verify_are_private_count_free_and_no_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            output = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            pbm_reads: list[str] = []
            original_reader = cli_module._read_private_regular_bytes_at

            def read_at(parent_descriptor: int, name: str, *, max_bytes: int) -> bytes:
                if name.endswith(".pbm"):
                    pbm_reads.append(name)
                return original_reader(parent_descriptor, name, max_bytes=max_bytes)

            with patch.object(
                cli_module,
                "_read_private_regular_bytes_at",
                side_effect=read_at,
            ):
                result, stdout, stderr = run_cli(self.prepare_arguments(paths, output))

            self.assertEqual(0, result, stderr)
            self.assertEqual("", stderr)
            self.assertEqual([f"{OCCUPIED_ID}.pbm"], pbm_reads)
            summary = json.loads(stdout)
            self.assertTrue(summary["valid"])
            self.assertTrue(summary["written"])
            self.assertTrue(summary["private_storage_verified"])
            self.assertTrue(summary["glyph_crop_commitments_verified"])
            self.assertTrue(summary["roster_canonical_bytes_verified"])
            self.assertTrue(summary["machine_provisional_graphic_identity_only"])
            self.assert_safe_summary(summary)
            self.assertNotIn("PRIVATE-CATALOG", stdout)
            self.assertNotIn("PRIVATE-GEOMETRY", stdout)
            self.assertNotIn("sha256:", stdout)
            self.assertEqual(0o600, output.stat().st_mode & 0o777)

            original_output = output.read_bytes()
            second_result, second_stdout, second_stderr = run_cli(
                self.prepare_arguments(paths, output)
            )
            self.assertEqual(1, second_result)
            self.assertEqual("", second_stdout)
            self.assertEqual(
                "indusbench: private KP1979 sign-template roster could not be created safely\n",
                second_stderr,
            )
            self.assertNotIn(output.name, second_stderr)
            self.assertEqual(original_output, output.read_bytes())

            verify_result, verify_stdout, verify_stderr = run_cli(
                self.verify_arguments(paths, output)
            )
            self.assertEqual(0, verify_result, verify_stderr)
            self.assertEqual("", verify_stderr)
            verify_summary = json.loads(verify_stdout)
            self.assertTrue(verify_summary["valid"])
            self.assertTrue(verify_summary["private_storage_verified"])
            self.assertTrue(verify_summary["roster_canonical_bytes_verified"])
            self.assertNotIn("written", verify_summary)
            self.assert_safe_summary(verify_summary)

    def test_glyph_directory_and_file_must_be_owner_only_physical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            output = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            glyph = Path(paths["glyph_dir"]) / f"{OCCUPIED_ID}.pbm"
            glyph.chmod(0o644)
            result, stdout, stderr = run_cli(self.prepare_arguments(paths, output))
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 sign-template roster preparation failed\n",
                stderr,
            )
            self.assertNotIn(glyph.name, stderr)
            self.assertFalse(output.exists())

        if not hasattr(os, "symlink"):
            return
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            linked = root / "PRIVATE-LINKED-GLYPHS"
            linked.symlink_to(Path(paths["glyph_dir"]), target_is_directory=True)
            output = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            arguments = self.prepare_arguments(paths, output)
            arguments[3] = str(linked)
            result, stdout, stderr = run_cli(arguments)
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 sign-template roster preparation failed\n",
                stderr,
            )
            self.assertNotIn(linked.name, stderr)
            self.assertFalse(output.exists())

    def test_private_json_inputs_and_verification_failures_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            output = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            Path(paths["catalog"]).chmod(0o644)
            with patch.object(cli_module, "build_sign_template_roster") as builder:
                result, stdout, stderr = run_cli(self.prepare_arguments(paths, output))
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 sign-template roster preparation failed\n",
                stderr,
            )
            builder.assert_not_called()
            self.assertFalse(output.exists())

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            roster = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            write_private(roster, encode_json({"PRIVATE-VALUE": True}))
            with patch.object(
                cli_module,
                "verify_sign_template_roster_bytes",
                side_effect=KP1979SignTemplateRosterError("PRIVATE-DETAIL"),
            ):
                result, stdout, stderr = run_cli(self.verify_arguments(paths, roster))
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 sign-template roster verification failed\n",
                stderr,
            )
            self.assertNotIn("PRIVATE-DETAIL", stderr)
            self.assertNotIn(roster.name, stderr)

    def test_unknown_durability_never_upgrades_private_assurances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            output = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            with (
                patch.object(
                    cli_module,
                    "build_sign_template_roster",
                    return_value={"synthetic": True},
                ),
                patch.object(
                    cli_module,
                    "_write_private_json_no_replace",
                    return_value=(False, True),
                ),
            ):
                result, stdout, stderr = run_cli(self.prepare_arguments(paths, output))
            self.assertEqual(1, result, stderr)
            self.assertEqual("", stderr)
            summary = json.loads(stdout)
            self.assertFalse(summary["valid"])
            self.assertFalse(summary["written"])
            self.assertFalse(summary["private_storage_verified"])
            self.assertTrue(summary["output_content_verified"])
            self.assertFalse(summary["durability_confirmed"])
            self.assertTrue(summary["destination_may_exist"])
            self.assertEqual(
                "committed_content_verified_durability_unknown",
                summary["postcondition"],
            )
            self.assert_safe_summary(summary)

    def test_safe_summary_and_verifier_state_cannot_be_upgraded(self) -> None:
        with self.assertRaisesRegex(
            KP1979SignTemplateRosterError,
            "cannot replace a fixed assurance",
        ):
            cli_module._kp1979_sign_template_roster_summary(
                valid=True,
                private_storage_verified=True,
                roster_canonical_bytes_verified=True,
                decipherment=True,
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            paths = self.make_inputs(root)
            roster = Path(paths["private"]) / "PRIVATE-ROSTER.json"
            write_private(roster, encode_json({"synthetic": True}))
            unsafe_summary = {
                "valid": True,
                "catalog_geometry_raw_bytes_bound": True,
                "catalog_geometry_item_join_verified": True,
                "glyph_crop_commitments_verified": True,
                "roster_canonical_bytes_verified": True,
                "catalog_values_accepted": True,
                "human_review_complete": False,
                "public_release_authorized": False,
                "evaluation_admissible": False,
                "decipherment": False,
                "prize_submission_eligible": False,
            }
            with patch.object(
                cli_module,
                "verify_sign_template_roster_bytes",
                return_value=unsafe_summary,
            ):
                result, stdout, stderr = run_cli(self.verify_arguments(paths, roster))
            self.assertEqual(1, result)
            self.assertEqual("", stdout)
            self.assertEqual(
                "indusbench: KP1979 sign-template roster verification failed\n",
                stderr,
            )


if __name__ == "__main__":
    unittest.main()
