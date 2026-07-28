from __future__ import annotations

import hashlib
import io
import json
import tarfile
import unittest
import warnings
import zipfile
from dataclasses import asdict
from unittest.mock import patch

from indusbench.mtaac import (
    MTAAC_COLUMNS,
    MTAAC_LICENSE_ID,
    MTAAC_PINNED_ARCHIVE_SHA256,
    MTAAC_PINNED_ARCHIVE_URL,
    MTAAC_PINNED_COMMIT,
    MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
    MTAAC_REPOSITORY_URL,
    MTAACError,
    derive_mtaac_gold_classes,
    opaque_form_sign_id,
    parse_mtaac_archive,
    parse_mtaac_directory,
)


def conll_document(
    p_identifier: str,
    rows: list[tuple[str, str, str, str, str, str, str]],
    *,
    trailing_directive_tabs: int = 0,
    newline: str = "\n",
) -> bytes:
    directive = f"#new_text={p_identifier}" + ("\t" * trailing_directive_tabs)
    header = "# " + "\t".join(MTAAC_COLUMNS)
    lines = [directive, header, *("\t".join(row) for row in rows)]
    return (newline.join(lines) + newline).encode()


def one_row_document(
    p_identifier: str,
    *,
    position: str = "o.1.1",
    form: str = "FORM_ALPHA",
    segm: str = "STEM_ALPHA[meaning_alpha]",
    xpostag: str = "N",
) -> bytes:
    return conll_document(
        p_identifier,
        [(position, form, segm, xpostag, "_", "_", "_")],
    )


def zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with (
        zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive,
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore", UserWarning)
        for path, raw in entries:
            archive.writestr(path, raw)
    return output.getvalue()


def tar_bytes(path: str, raw: bytes) -> bytes:
    return tar_entries_bytes([(path, raw)])


def tar_entries_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for path, raw in entries:
            member = tarfile.TarInfo(path)
            member.size = len(raw)
            member.mtime = 0
            archive.addfile(member, io.BytesIO(raw))
    return output.getvalue()


class MTAACSourceFactsTests(unittest.TestCase):
    def test_public_source_revision_and_license_are_pinned(self) -> None:
        self.assertEqual(
            MTAAC_PINNED_COMMIT,
            "66e0643efd230401210e27db353ebb6d7228b1bb",
        )
        self.assertEqual(MTAAC_LICENSE_ID, "CC0-1.0")
        self.assertEqual(
            MTAAC_REPOSITORY_URL,
            "https://github.com/cdli-gh/mtaac_gold_corpus",
        )
        self.assertEqual(
            MTAAC_PINNED_ARCHIVE_URL,
            "https://github.com/cdli-gh/mtaac_gold_corpus/archive/"
            "66e0643efd230401210e27db353ebb6d7228b1bb.tar.gz",
        )
        self.assertEqual(
            MTAAC_PINNED_ARCHIVE_SHA256,
            "sha256:2698293080ed8fe6244ec9191010030d2928fd639002ae25d3a05867c22be091",
        )
        self.assertEqual(
            MTAAC_PINNED_SELECTED_MANIFEST_SHA256,
            "sha256:1a7e7bbfeae6b833bf90ee20eecb8a0be712dbbdc85a88e5de10cacfd7b0464e",
        )


class MTAACDirectoryParserTests(unittest.TestCase):
    def test_strict_parse_preserves_raw_gold_and_separates_model_view(self) -> None:
        p_identifier = "P900001"
        rows = [
            (
                "o.1.1",
                "FORM_QUANTITY_SECRET",
                "_(_)[quantity_secret]",
                "NU.GEN",
                "HEAD_SECRET",
                "REL_SECRET",
                "MISC_SECRET",
            ),
            (
                "o.1.2",
                "FORM_UNIT_SECRET",
                "STEM_SECRET[unit]",
                "N",
                "_",
                "_",
                "_",
            ),
            (
                "o.1.3",
                "FORM_PERSON_SECRET",
                "[1]",
                "PN.ERG",
                "_",
                "_",
                "_",
            ),
            (
                "o.1.4",
                "FORM_SETTLEMENT_SECRET",
                "STEM_PLACE[1]",
                "SN.ABS",
                "_",
                "_",
                "_",
            ),
            (
                "_",
                "FORM_UNLABELED_SECRET",
                "",
                "",
                "_",
                "_",
                "_",
            ),
        ]
        raw = conll_document(
            p_identifier,
            rows,
            trailing_directive_tabs=3,
            newline="\r\n",
        )
        result = parse_mtaac_directory(
            {
                f"snapshot-root/morph/to_dict/{p_identifier}.conll": raw,
                "snapshot-root/morph/external/P900099.conll": b"ignored",
                "snapshot-root/morph/to_dict/helper.sh": b"ignored",
            }
        )

        self.assertEqual(result.provenance.selected_document_count, 1)
        self.assertEqual(result.provenance.row_shape_document_count, 1)
        self.assertEqual(result.provenance.row_shape_token_count, 5)
        self.assertEqual(result.provenance.admitted_document_count, 1)
        self.assertEqual(result.provenance.admitted_token_count, 5)
        self.assertFalse(result.provenance.caller_digest_verified)
        self.assertEqual(
            result.provenance.revision_attestation,
            "target_only_caller_bytes_not_git_attested",
        )
        self.assertEqual(
            dict(result.admitted_class_counts),
            {
                "quantity": 1,
                "unit": 1,
                "person_name": 1,
                "settlement_name": 1,
            },
        )

        gold = result.gold_documents[0]
        model = result.model_documents[0]
        self.assertEqual(gold.p_identifier, p_identifier)
        self.assertEqual(gold.input_path, f"snapshot-root/morph/to_dict/{p_identifier}.conll")
        self.assertRegex(gold.source_sha256, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(gold.source_bytes, len(raw))
        self.assertEqual(gold.document_key, model.document_key)
        self.assertEqual(
            [token.token_key for token in gold.tokens],
            [token.token_key for token in model.tokens],
        )
        self.assertEqual(gold.tokens[0].form, rows[0][1])
        self.assertEqual(gold.tokens[0].segm, rows[0][2])
        self.assertEqual(gold.tokens[0].xpostag, rows[0][3])
        self.assertEqual(gold.tokens[0].head, rows[0][4])
        self.assertEqual(gold.tokens[0].deprel, rows[0][5])
        self.assertEqual(gold.tokens[0].misc, rows[0][6])
        self.assertEqual(gold.tokens[4].position, "_")
        self.assertEqual(gold.tokens[4].segm, "")
        self.assertEqual(gold.tokens[4].xpostag, "")

        model_json = json.dumps(asdict(model), sort_keys=True)
        for forbidden_value in (
            p_identifier,
            "FORM_QUANTITY_SECRET",
            "quantity_secret",
            "NU.GEN",
            "HEAD_SECRET",
            "REL_SECRET",
            "MISC_SECRET",
            "STEM_SECRET",
            "PN.ERG",
            "SN.ABS",
        ):
            self.assertNotIn(forbidden_value, model_json)
        self.assertEqual(
            set(asdict(model.tokens[0])),
            {"token_key", "sign_id", "visual_index"},
        )

    def test_input_and_manifest_digests_are_deterministic_and_committed(self) -> None:
        first_raw = one_row_document("P900001", form="FORM_ALPHA")
        second_raw = one_row_document("P900002", form="FORM_BETA")
        first_mapping = {
            "root/morph/to_dict/P900002.conll": second_raw,
            "root/morph/to_dict/P900001.conll": first_raw,
            "root/README": b"ignored but input-committed",
        }
        second_mapping = dict(reversed(tuple(first_mapping.items())))

        first = parse_mtaac_directory(first_mapping)
        second = parse_mtaac_directory(second_mapping)
        self.assertEqual(first, second)
        expected = first.provenance.input_sha256
        digest = hashlib.sha256(b"indusbench:mtaac:directory-mapping:v1\x00")
        for path, raw in sorted(first_mapping.items()):
            path_bytes = path.encode("utf-8")
            digest.update(len(path_bytes).to_bytes(8, "big"))
            digest.update(path_bytes)
            digest.update(len(raw).to_bytes(8, "big"))
            digest.update(raw)
        self.assertEqual(expected, "sha256:" + digest.hexdigest())
        verified = parse_mtaac_directory(
            first_mapping,
            expected_input_sha256=expected,
        )
        self.assertTrue(verified.provenance.caller_digest_verified)
        self.assertEqual(
            verified.provenance.selected_manifest_sha256,
            first.provenance.selected_manifest_sha256,
        )

        changed_ignored = dict(first_mapping)
        changed_ignored["root/README"] = b"changed ignored bytes"
        changed = parse_mtaac_directory(changed_ignored)
        self.assertNotEqual(changed.provenance.input_sha256, expected)
        self.assertEqual(
            changed.provenance.selected_manifest_sha256,
            first.provenance.selected_manifest_sha256,
        )
        with self.assertRaisesRegex(MTAACError, "does not match"):
            parse_mtaac_directory(
                first_mapping,
                expected_input_sha256="sha256:" + ("0" * 64),
            )
        with self.assertRaisesRegex(MTAACError, "tagged lowercase"):
            parse_mtaac_directory(first_mapping, expected_input_sha256="bad")

    def test_only_exact_to_dict_conll_scope_is_selected(self) -> None:
        raw = one_row_document("P900001")
        result = parse_mtaac_directory(
            {
                "root/morph/to_dict/P900001.conll": raw,
                "root/morph/to_dict/nested/P900002.conll": one_row_document("P900002"),
                "root/morph/external/P900003.conll": one_row_document("P900003"),
                "root/morph/to_dict/P900004.CONLL": one_row_document("P900004"),
            }
        )
        self.assertEqual(result.provenance.selected_document_count, 1)
        self.assertEqual(result.gold_documents[0].p_identifier, "P900001")

    def test_mixed_archive_roots_and_unsafe_paths_fail_closed(self) -> None:
        raw = one_row_document("P900001")
        with self.assertRaisesRegex(MTAACError, "multiple corpus roots"):
            parse_mtaac_directory(
                {
                    "root-a/morph/to_dict/P900001.conll": raw,
                    "root-b/morph/to_dict/P900002.conll": one_row_document("P900002"),
                }
            )
        for unsafe_path in (
            "../morph/to_dict/P900001.conll",
            "/morph/to_dict/P900001.conll",
            "root//morph/to_dict/P900001.conll",
            r"root\morph\to_dict\P900001.conll",
        ):
            with (
                self.subTest(path=unsafe_path),
                self.assertRaisesRegex(MTAACError, "safe relative POSIX"),
            ):
                parse_mtaac_directory({unsafe_path: raw})
        with self.assertRaisesRegex(MTAACError, "no files matching"):
            parse_mtaac_directory({"morph/external/P900001.conll": raw})


class MTAACArchiveParserTests(unittest.TestCase):
    def test_zip_and_tar_are_supported_without_networking(self) -> None:
        raw = one_row_document("P900001")
        zip_raw = zip_bytes(
            [
                ("snapshot/", b""),
                ("snapshot/morph/to_dict/P900001.conll", raw),
                ("snapshot/README.md", b"not selected"),
            ]
        )
        parsed_zip = parse_mtaac_archive(
            zip_raw,
            expected_input_sha256="sha256:" + hashlib.sha256(zip_raw).hexdigest(),
        )
        self.assertEqual(parsed_zip.provenance.input_kind, "archive_zip")
        self.assertTrue(parsed_zip.provenance.caller_digest_verified)
        self.assertEqual(parsed_zip.provenance.admitted_document_count, 1)

        tar_raw = tar_bytes("snapshot/morph/to_dict/P900001.conll", raw)
        parsed_tar = parse_mtaac_archive(tar_raw)
        self.assertEqual(parsed_tar.provenance.input_kind, "archive_tar")
        self.assertEqual(parsed_tar.provenance.admitted_document_count, 1)
        self.assertEqual(
            parsed_tar.provenance.selected_manifest_sha256,
            parsed_zip.provenance.selected_manifest_sha256,
        )

    def test_invalid_duplicate_and_traversal_archives_fail_closed(self) -> None:
        with self.assertRaisesRegex(MTAACError, "neither a valid ZIP nor TAR"):
            parse_mtaac_archive(b"not an archive")

        raw = one_row_document("P900001")
        duplicate = zip_bytes(
            [
                ("root/morph/to_dict/P900001.conll", raw),
                ("root/morph/to_dict/P900001.conll", raw),
            ]
        )
        with self.assertRaisesRegex(MTAACError, "duplicate member"):
            parse_mtaac_archive(duplicate)

        traversal = zip_bytes([("../morph/to_dict/P900001.conll", raw)])
        with self.assertRaisesRegex(MTAACError, "safe relative POSIX"):
            parse_mtaac_archive(traversal)

    def test_archive_reader_rejects_selected_aggregate_before_decompression(self) -> None:
        first = one_row_document("P900001")
        second = one_row_document("P900002")
        entries = [
            ("root/morph/to_dict/P900001.conll", first),
            ("root/morph/to_dict/P900002.conll", second),
        ]
        limit = len(first) + len(second) - 1
        for archive_bytes in (zip_bytes(entries), tar_entries_bytes(entries)):
            with (
                self.subTest(archive_magic=archive_bytes[:4]),
                patch("indusbench.mtaac.MAX_SELECTED_TOTAL_BYTES", limit),
                self.assertRaisesRegex(MTAACError, "selected corpus exceeds"),
            ):
                parse_mtaac_archive(archive_bytes)


class MTAACQuarantineTests(unittest.TestCase):
    def test_non_seven_column_document_is_wholly_quarantined(self) -> None:
        bad = (
            b"#new_text=P900001\n"
            b"# ID\tFORM\tSEGM\tXPOSTAG\tHEAD\tDEPREL\tMISC\n"
            b"o.1.1\tFORM_ALPHA\tSTEM[unit]\tN\n"
            b"o.1.2\tFORM_BETA\tSTEM_BETA\tPN\t_\t_\t_\n"
        )
        good = one_row_document("P900002", xpostag="SN")
        result = parse_mtaac_directory(
            {
                "morph/to_dict/P900001.conll": bad,
                "morph/to_dict/P900002.conll": good,
            }
        )
        self.assertEqual(result.provenance.selected_document_count, 2)
        self.assertEqual(result.provenance.row_shape_document_count, 1)
        self.assertEqual(result.provenance.row_shape_token_count, 1)
        self.assertEqual(result.provenance.admitted_document_count, 1)
        self.assertEqual(result.provenance.admitted_token_count, 1)
        self.assertEqual(len(result.quarantined_documents), 1)
        quarantine = result.quarantined_documents[0]
        self.assertEqual(quarantine.reason_code, "non_7_column_row")
        self.assertEqual(quarantine.source_line_number, 3)
        self.assertNotIn("FORM_ALPHA", repr(quarantine))
        self.assertNotIn("STEM", repr(quarantine))
        self.assertEqual(dict(result.row_shape_class_counts)["unit"], 0)

    def test_duplicate_positions_are_shape_valid_but_not_admitted(self) -> None:
        duplicate = conll_document(
            "P900001",
            [
                ("o.1.1", "FORM_ALPHA", "STEM[unit]", "N", "_", "_", "_"),
                ("o.1.1", "FORM_BETA", "STEM_BETA", "NU", "_", "_", "_"),
            ],
        )
        result = parse_mtaac_directory({"morph/to_dict/P900001.conll": duplicate})

        self.assertEqual(result.provenance.row_shape_document_count, 1)
        self.assertEqual(result.provenance.row_shape_token_count, 2)
        self.assertEqual(
            dict(result.row_shape_class_counts),
            {
                "quantity": 1,
                "unit": 1,
                "person_name": 0,
                "settlement_name": 0,
            },
        )
        self.assertEqual(result.provenance.admitted_document_count, 0)
        self.assertEqual(result.provenance.admitted_token_count, 0)
        self.assertEqual(result.quarantined_documents[0].reason_code, "duplicate_token_position")
        self.assertEqual(dict(result.admitted_class_counts)["quantity"], 0)

    def test_new_text_filename_header_and_comment_contracts(self) -> None:
        cases = {
            "leading_space_new_text": (
                one_row_document("P900001").replace(
                    b"#new_text=P900001",
                    b" #new_text=P900001",
                ),
                "non_7_column_row",
            ),
            "mismatched_new_text": (
                one_row_document("P900002"),
                "p_identifier_mismatch",
            ),
            "invalid_filename": (
                one_row_document("P900001"),
                "invalid_p_identifier",
            ),
            "invalid_header": (
                one_row_document("P900001").replace(b"# ID\tFORM", b"# ID\tRAW_FORM"),
                "invalid_column_header",
            ),
            "extra_comment": (
                one_row_document("P900001").replace(
                    b"# ID\tFORM\tSEGM\tXPOSTAG\tHEAD\tDEPREL\tMISC\n",
                    b"# ID\tFORM\tSEGM\tXPOSTAG\tHEAD\tDEPREL\tMISC\n# note\n",
                ),
                "unsupported_comment",
            ),
        }
        paths = {
            "leading_space_new_text": "morph/to_dict/P900001.conll",
            "mismatched_new_text": "morph/to_dict/P900001.conll",
            "invalid_filename": "morph/to_dict/not-a-p-id.conll",
            "invalid_header": "morph/to_dict/P900001.conll",
            "extra_comment": "morph/to_dict/P900001.conll",
        }
        for name, (raw, expected_reason) in cases.items():
            with self.subTest(case=name):
                result = parse_mtaac_directory({paths[name]: raw})
                self.assertEqual(result.provenance.admitted_document_count, 0)
                self.assertEqual(
                    result.quarantined_documents[0].reason_code,
                    expected_reason,
                )

    def test_encoding_line_endings_controls_empty_form_and_no_rows_are_quarantined(self) -> None:
        valid = one_row_document("P900001")
        header_only = b"#new_text=P900001\n# ID\tFORM\tSEGM\tXPOSTAG\tHEAD\tDEPREL\tMISC\n"
        cases = {
            "invalid_utf8": (valid + b"\xff", "invalid_utf8"),
            "lone_cr": (valid.replace(b"\n", b"\r", 1), "invalid_line_ending"),
            "nul": (valid + b"\x00", "forbidden_nul_byte"),
            "empty_form": (valid.replace(b"\tFORM_ALPHA\t", b"\t\t"), "invalid_form"),
            "no_rows": (header_only, "no_token_rows"),
        }
        for name, (raw, expected_reason) in cases.items():
            with self.subTest(case=name):
                result = parse_mtaac_directory({"morph/to_dict/P900001.conll": raw})
                self.assertEqual(result.provenance.admitted_document_count, 0)
                self.assertEqual(
                    result.quarantined_documents[0].reason_code,
                    expected_reason,
                )


class MTAACGoldAndLeakageTests(unittest.TestCase):
    def test_mechanical_class_markers_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            derive_mtaac_gold_classes("STEM[unit]", "NU.PN.SN"),
            ("quantity", "unit"),
        )
        self.assertEqual(derive_mtaac_gold_classes("STEM", "PN.GEN"), ("person_name",))
        self.assertEqual(derive_mtaac_gold_classes("STEM", "SN.ABS"), ("settlement_name",))
        self.assertEqual(derive_mtaac_gold_classes("STEM[units]", "XNU"), ())
        self.assertEqual(derive_mtaac_gold_classes("STEM[unit_type]", "N"), ())
        self.assertEqual(derive_mtaac_gold_classes("STEM", "NUN"), ())
        self.assertEqual(derive_mtaac_gold_classes("STEM", "PNAME"), ())
        self.assertEqual(derive_mtaac_gold_classes("STEM", "SNA"), ())
        self.assertEqual(derive_mtaac_gold_classes("_(_)", "NU"), ("quantity",))
        self.assertEqual(derive_mtaac_gold_classes("", "PN"), ("person_name",))

    def test_overlapping_gold_rules_quarantine_the_complete_document(self) -> None:
        raw = one_row_document(
            "P900001",
            segm="STEM[unit]",
            xpostag="NU",
        )
        result = parse_mtaac_directory({"morph/to_dict/P900001.conll": raw})

        self.assertEqual(result.provenance.row_shape_document_count, 1)
        self.assertEqual(dict(result.row_shape_class_counts)["quantity"], 1)
        self.assertEqual(dict(result.row_shape_class_counts)["unit"], 1)
        self.assertEqual(result.provenance.admitted_document_count, 0)
        self.assertEqual(
            result.quarantined_documents[0].reason_code,
            "overlapping_gold_classes",
        )

    def test_opaque_form_ids_are_exact_deterministic_and_not_sign_segmentation(self) -> None:
        first = opaque_form_sign_id("FORM-{A}.1")
        second = opaque_form_sign_id("FORM-{A}.1")
        different = opaque_form_sign_id("FORM-{A}.2")
        composed = opaque_form_sign_id("\N{LATIN SMALL LETTER E WITH ACUTE}")
        decomposed = opaque_form_sign_id("e\N{COMBINING ACUTE ACCENT}")

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertNotEqual(composed, decomposed)
        self.assertRegex(first, r"^mtaac-word-form-sha256-v1:[0-9a-f]{64}$")
        self.assertNotIn("FORM", first)
        with self.assertRaisesRegex(MTAACError, "non-empty"):
            opaque_form_sign_id("")
        with self.assertRaisesRegex(MTAACError, "control"):
            opaque_form_sign_id("FORM\nINJECTION")

    def test_identical_forms_share_sign_ids_but_tokens_and_documents_do_not(self) -> None:
        first = one_row_document("P900001", form="FORM_SHARED")
        second = one_row_document("P900002", form="FORM_SHARED")
        result = parse_mtaac_directory(
            {
                "morph/to_dict/P900001.conll": first,
                "morph/to_dict/P900002.conll": second,
            }
        )
        model_a, model_b = result.model_documents
        self.assertNotEqual(model_a.document_key, model_b.document_key)
        self.assertNotEqual(model_a.tokens[0].token_key, model_b.tokens[0].token_key)
        self.assertEqual(model_a.tokens[0].sign_id, model_b.tokens[0].sign_id)

    def test_model_identity_is_independent_of_gold_and_unused_annotations(self) -> None:
        path = "morph/to_dict/P900001.conll"
        first = parse_mtaac_directory(
            {
                path: conll_document(
                    "P900001",
                    [
                        (
                            "o.1.1",
                            "FORM_SHARED",
                            "ROOT[first_gloss]",
                            "NU",
                            "_",
                            "_",
                            "_",
                        )
                    ],
                )
            }
        )
        second = parse_mtaac_directory(
            {
                path: conll_document(
                    "P900001",
                    [
                        (
                            "o.1.1",
                            "FORM_SHARED",
                            "ROOT[second_gloss]",
                            "NU.detail",
                            "UNUSED_HEAD",
                            "UNUSED_REL",
                            "UNUSED_MISC",
                        )
                    ],
                )
            }
        )

        self.assertEqual(first.model_documents, second.model_documents)
        self.assertEqual(
            first.gold_documents[0].tokens[0].classes,
            second.gold_documents[0].tokens[0].classes,
        )
        self.assertNotEqual(
            first.gold_documents[0].source_sha256,
            second.gold_documents[0].source_sha256,
        )
        self.assertNotEqual(
            first.provenance.selected_manifest_sha256,
            second.provenance.selected_manifest_sha256,
        )
        self.assertRegex(
            first.model_documents[0].document_key,
            r"^mtaac-document-source-id-sha256-v1:[0-9a-f]{64}$",
        )
        self.assertRegex(
            first.model_documents[0].tokens[0].token_key,
            r"^mtaac-token-source-order-sha256-v1:[0-9a-f]{64}$",
        )


if __name__ == "__main__":
    unittest.main()
