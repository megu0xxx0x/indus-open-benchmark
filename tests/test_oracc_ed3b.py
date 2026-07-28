from __future__ import annotations

import hashlib
import io
import json
import stat
import unittest
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import indusbench.oracc_ed3b as oracc_ed3b
from indusbench.oracc_ed3b import (
    ORACCEd3bError,
    canonicalize_oracc_ed3b_observation,
    derive_oracc_ed3b_gold_class,
    derive_oracc_ed3b_truth_state,
    verify_oracc_ed3b_archive,
)

SYNTHETIC_DOCUMENT_ID = "P999999"
SYNTHETIC_FORM = "SYNTHETIC_FORM_SECRET"
SYNTHETIC_GDL_VALUE = "SYNTHETIC_GDL_SECRET"
ROOT = Path(__file__).resolve().parents[1]


def tagged_sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_header(source_type: str) -> dict[str, Any]:
    return {
        "project": oracc_ed3b.ORACC_ED3B_PROJECT,
        "license": oracc_ed3b.ORACC_ED3B_LICENSE_TEXT,
        "license-url": oracc_ed3b.ORACC_ED3B_LICENSE_URL,
        "type": source_type,
    }


def lemma_fields(
    ordinal: int,
    *,
    pos: str,
    guide_word: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "form": f"{SYNTHETIC_FORM}_{ordinal}",
        "pos": pos,
        "gdl": [
            {
                "id": f"synthetic.{ordinal}",
                "v": f"{SYNTHETIC_GDL_VALUE}_{ordinal}",
            }
        ],
    }
    if guide_word is not None:
        fields["gw"] = guide_word
    return fields


def synthetic_entries(
    *,
    catalogue_raw: bytes | None = None,
    unit_entries: list[dict[str, Any]] | None = None,
) -> list[tuple[str, bytes]]:
    project = oracc_ed3b.ORACC_ED3B_PROJECT
    catalogue = {
        **source_header("catalogue"),
        "members": {
            SYNTHETIC_DOCUMENT_ID: {
                "id_text": SYNTHETIC_DOCUMENT_ID,
                "period": oracc_ed3b.ORACC_ED3B_PERIOD,
                "genre": oracc_ed3b.ORACC_ED3B_GENRE,
            }
        },
    }
    metadata = {
        **source_header("metadata"),
        "formats": {"lem": [SYNTHETIC_DOCUMENT_ID]},
    }
    glossary = {
        **source_header("glossary"),
        "entries": (
            [{"cf": "synthetic-unit", "gw": "unit", "pos": "N", "icount": "1"}]
            if unit_entries is None
            else unit_entries
        ),
    }
    document = {
        **source_header("cdl"),
        "textid": SYNTHETIC_DOCUMENT_ID,
        "cdl": [
            {"node": "d", "type": "line-start"},
            {"node": "l", "f": lemma_fields(1, pos="n")},
            {"node": "l", "f": lemma_fields(2, pos="NU")},
            {"node": "l", "f": lemma_fields(3, pos="QN")},
            {
                "node": "l",
                "f": lemma_fields(4, pos="N", guide_word="unit"),
            },
            {"node": "l", "f": lemma_fields(5, pos="PN")},
            {"node": "l", "f": lemma_fields(6, pos="SN")},
            {
                "node": "l",
                "f": lemma_fields(7, pos="N", guide_word="context"),
            },
        ],
    }
    return [
        (
            f"{project}/catalogue.json",
            json_bytes(catalogue) if catalogue_raw is None else catalogue_raw,
        ),
        (f"{project}/metadata.json", json_bytes(metadata)),
        (f"{project}/gloss-sux.json", json_bytes(glossary)),
        (
            f"{project}/corpusjson/{SYNTHETIC_DOCUMENT_ID}.json",
            json_bytes(document),
        ),
    ]


def zip_bytes(
    entries: list[tuple[str, bytes]],
    *,
    symlink_paths: frozenset[str] = frozenset(),
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path, raw in entries:
            member = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.compress_type = zipfile.ZIP_DEFLATED
            mode = stat.S_IFLNK | 0o777 if path in symlink_paths else stat.S_IFREG | 0o644
            member.external_attr = mode << 16
            archive.writestr(member, raw)
    return output.getvalue()


@contextmanager
def synthetic_source_counts(
    *,
    member_count: int,
    catalogue_document_count: int = 1,
    unit_entry_count: int = 1,
    unit_instance_count: int = 1,
) -> Iterator[None]:
    with (
        patch.object(
            oracc_ed3b,
            "ORACC_ED3B_ARCHIVE_MEMBER_COUNT",
            member_count,
        ),
        patch.object(
            oracc_ed3b,
            "ORACC_ED3B_CATALOGUE_DOCUMENT_COUNT",
            catalogue_document_count,
        ),
        patch.object(
            oracc_ed3b,
            "ORACC_ED3B_UNIT_GLOSSARY_ENTRY_COUNT",
            unit_entry_count,
        ),
        patch.object(
            oracc_ed3b,
            "ORACC_ED3B_UNIT_GLOSSARY_INSTANCE_COUNT",
            unit_instance_count,
        ),
        patch.object(
            oracc_ed3b,
            "_AUDIT_EXCLUSION_KEYS",
            frozenset(),
        ),
        patch.object(
            oracc_ed3b,
            "_AUDIT_EXCLUSION_SET_SHA256",
            "sha256:9f6612b24268733b145e03989b10b426c54ad01d555ac2b4f730bdfda57a8a33",
        ),
    ):
        yield


def audit_synthetic_archive(
    archive_bytes: bytes,
    *,
    minimum_tokens_per_class: int = 1,
    minimum_documents_per_class: int = 1,
) -> dict[str, Any]:
    with synthetic_source_counts(member_count=len(synthetic_entries())):
        return oracc_ed3b._audit_oracc_ed3b_archive(
            archive_bytes,
            expected_archive_sha256=tagged_sha256(archive_bytes),
            minimum_tokens_per_class=minimum_tokens_per_class,
            minimum_documents_per_class=minimum_documents_per_class,
        )


class ORACCEd3bSyntheticArchiveTests(unittest.TestCase):
    maxDiff = None

    def test_five_state_projection_is_exact_and_narrow(self) -> None:
        cases = (
            ({"pos": "n"}, "quantity"),
            ({"pos": "NU"}, "context_only"),
            ({"pos": "QN"}, "context_only"),
            ({"pos": "N", "gw": "unit"}, "unit"),
            ({"pos": "PN"}, "person_name"),
            ({"pos": "SN"}, "settlement_name"),
            ({"pos": "N", "gw": "context"}, "context_only"),
            ({}, "context_only"),
        )

        for fields, expected_state in cases:
            with self.subTest(fields=fields):
                label = derive_oracc_ed3b_gold_class(fields)
                state = label if label is not None else "context_only"
                self.assertEqual(expected_state, state)

        self.assertEqual(
            (
                "context_only",
                "quantity",
                "unit",
                "person_name",
                "settlement_name",
            ),
            oracc_ed3b.ORACC_ED3B_STATES,
        )
        self.assertEqual("annotation_unknown", derive_oracc_ed3b_truth_state({}))
        self.assertEqual(
            (*oracc_ed3b.ORACC_ED3B_STATES, "annotation_unknown"),
            oracc_ed3b.ORACC_ED3B_TRUTH_STATES,
        )

    def test_observation_projection_removes_source_key_and_semantic_metadata(self) -> None:
        shared = "SAME-GRAPHEME"
        from_value = canonicalize_oracc_ed3b_observation(
            {
                "gdl": [
                    {
                        "id": "private-id-one",
                        "v": shared,
                        "form": "ignored-linguistic-form",
                        "det": "semantic-determinative-one",
                    }
                ]
            }
        )
        from_numeric_parser = canonicalize_oracc_ed3b_observation(
            {
                "gdl": [
                    {
                        "id": "private-id-two",
                        "n": "n",
                        "form": shared,
                        "det": "semantic-determinative-two",
                        "seq": [{"v": "must-not-be-reached"}],
                    }
                ]
            }
        )
        self.assertEqual(from_value, from_numeric_parser)
        serialized = json.dumps(from_value, sort_keys=True)
        for forbidden in (
            shared,
            "private-id",
            "ignored-linguistic-form",
            "semantic-determinative",
        ):
            self.assertNotIn(forbidden, serialized)

        self.assertEqual(
            from_value,
            canonicalize_oracc_ed3b_observation(
                {
                    "pos": "SN",
                    "gw": "unit",
                    "gdl": [
                        {
                            "id": "different-id",
                            "v": shared,
                            "form": "different-ignored-form",
                            "det": "different-determinative",
                        }
                    ],
                }
            ),
        )
        self.assertEqual(
            "person_name",
            derive_oracc_ed3b_truth_state({"pos": "PN", "gdl": [{"v": "first-observation"}]}),
        )
        self.assertEqual(
            "person_name",
            derive_oracc_ed3b_truth_state({"pos": "PN", "gdl": [{"v": "changed-observation"}]}),
        )

        for forbidden_key in ("role", "unexpected"):
            with (
                self.subTest(forbidden_key=forbidden_key),
                self.assertRaisesRegex(ORACCEd3bError, "unapproved key"),
            ):
                canonicalize_oracc_ed3b_observation({"gdl": [{"v": shared, forbidden_key: "num"}]})

    def test_frozen_source_protocol_is_exact_and_tamper_evident(self) -> None:
        protocol_bytes = (ROOT / "benchmark/oracc-ed3b-validation-source-v1.json").read_bytes()
        self.assertEqual(
            oracc_ed3b.ORACC_ED3B_PROTOCOL_SHA256,
            oracc_ed3b.verify_oracc_ed3b_protocol_bytes(protocol_bytes),
        )
        with self.assertRaisesRegex(ORACCEd3bError, "protocol SHA-256"):
            oracc_ed3b.verify_oracc_ed3b_protocol_bytes(protocol_bytes + b" ")

    def test_v2_implementation_protocol_and_result_remain_byte_immutable(self) -> None:
        expected = {
            ROOT / "src/indusbench/mtaac.py": (
                "aa6d698272f82108cbf3dce40df29bee4905809318cc931ba7f9dbfab9590c10"
            ),
            ROOT / "src/indusbench/mtaac_control.py": (
                "1192e74440a193f784c6c8c5afec267e9bfb125d12241a71cf567c35a24b838a"
            ),
            ROOT / "benchmark/mtaac-known-script-control-v2.json": (
                "25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
            ),
            ROOT / "benchmark/results/mtaac-known-script-control-v2.json": (
                "6bc4ed610862d109b596bdd934f36fd19b99e3cbfcced42882546d0c852a7afe"
            ),
        }
        self.assertEqual(
            expected,
            {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in expected},
        )

    def test_audit_is_deterministic_and_receipt_leaks_no_raw_values(self) -> None:
        entries = synthetic_entries()
        archive_bytes = zip_bytes(entries)

        first = audit_synthetic_archive(archive_bytes)
        second = audit_synthetic_archive(archive_bytes)

        self.assertEqual(first, second)
        self.assertEqual("source_qualified", first["terminal_status"])
        serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)
        corpus_member_path = (
            f"{oracc_ed3b.ORACC_ED3B_PROJECT}/corpusjson/{SYNTHETIC_DOCUMENT_ID}.json"
        )
        for forbidden_value in (
            SYNTHETIC_DOCUMENT_ID,
            SYNTHETIC_FORM,
            SYNTHETIC_GDL_VALUE,
            corpus_member_path,
        ):
            self.assertNotIn(forbidden_value, serialized)

    def test_normative_verifier_cannot_be_rebound_to_a_synthetic_archive(self) -> None:
        archive_bytes = zip_bytes(synthetic_entries())
        with self.assertRaisesRegex(ORACCEd3bError, "SHA-256"):
            verify_oracc_ed3b_archive(archive_bytes)

    def test_bad_archive_digest_is_rejected(self) -> None:
        archive_bytes = zip_bytes(synthetic_entries())
        with (
            synthetic_source_counts(member_count=len(synthetic_entries())),
            self.assertRaisesRegex(ORACCEd3bError, "SHA-256"),
        ):
            oracc_ed3b._audit_oracc_ed3b_archive(
                archive_bytes,
                expected_archive_sha256="sha256:" + ("0" * 64),
            )

    def test_duplicate_json_key_is_rejected(self) -> None:
        duplicate_key_catalogue = (
            b'{"type":"catalogue","type":"catalogue","project":"epsd2/admin/ed3b"}'
        )
        archive_bytes = zip_bytes(synthetic_entries(catalogue_raw=duplicate_key_catalogue))
        with (
            synthetic_source_counts(member_count=len(synthetic_entries())),
            self.assertRaisesRegex(ORACCEd3bError, "duplicate object key"),
        ):
            oracc_ed3b._audit_oracc_ed3b_archive(
                archive_bytes,
                expected_archive_sha256=tagged_sha256(archive_bytes),
            )

    def test_unsafe_member_path_and_symlink_are_rejected(self) -> None:
        unsafe_entries = [*synthetic_entries(), ("../escape.json", b"{}")]
        unsafe_archive = zip_bytes(unsafe_entries)
        with (
            synthetic_source_counts(member_count=len(unsafe_entries)),
            self.assertRaisesRegex(ORACCEd3bError, "path is unsafe"),
        ):
            oracc_ed3b._audit_oracc_ed3b_archive(
                unsafe_archive,
                expected_archive_sha256=tagged_sha256(unsafe_archive),
            )

        symlink_path = f"{oracc_ed3b.ORACC_ED3B_PROJECT}/synthetic-link"
        symlink_entries = [*synthetic_entries(), (symlink_path, b"catalogue.json")]
        symlink_archive = zip_bytes(
            symlink_entries,
            symlink_paths=frozenset({symlink_path}),
        )
        with (
            synthetic_source_counts(member_count=len(symlink_entries)),
            self.assertRaisesRegex(ORACCEd3bError, "Symbolic links|symbolic links"),
        ):
            oracc_ed3b._audit_oracc_ed3b_archive(
                symlink_archive,
                expected_archive_sha256=tagged_sha256(symlink_archive),
            )

    def test_unit_glossary_inconsistency_is_rejected(self) -> None:
        cases = (
            (
                [{"cf": "synthetic-unit", "gw": "unit", "pos": "V", "icount": "1"}],
                "part of speech",
            ),
            (
                [{"cf": "synthetic-unit", "gw": "unit", "pos": "N", "icount": "2"}],
                "instance count",
            ),
        )
        for unit_entries, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                archive_bytes = zip_bytes(synthetic_entries(unit_entries=unit_entries))
                with (
                    synthetic_source_counts(member_count=len(synthetic_entries())),
                    self.assertRaisesRegex(ORACCEd3bError, expected_error),
                ):
                    oracc_ed3b._audit_oracc_ed3b_archive(
                        archive_bytes,
                        expected_archive_sha256=tagged_sha256(archive_bytes),
                    )

    def test_insufficient_class_support_is_a_terminal_status(self) -> None:
        archive_bytes = zip_bytes(synthetic_entries())
        receipt = audit_synthetic_archive(
            archive_bytes,
            minimum_tokens_per_class=2,
            minimum_documents_per_class=2,
        )

        self.assertEqual("insufficient_source_support", receipt["terminal_status"])
        self.assertFalse(receipt["support_gate"]["all_classes_pass"])
        self.assertFalse(receipt["support_gate"]["selected_per_class_counts_listed_in_receipt"])
        self.assertTrue(
            receipt["support_gate"]["upstream_aggregate_class_counts_previously_disclosed"]
        )
        self.assertFalse(receipt["support_gate"]["source_distribution_blindness_claimed"])


if __name__ == "__main__":
    unittest.main()
