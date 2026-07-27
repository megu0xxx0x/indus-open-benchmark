from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import indusbench.private_readiness as private_readiness_module
import indusbench.private_review_bundle as private_review_module
from indusbench.private_readiness import AuditLimits, audit_private_corpus
from indusbench.private_review_bundle import (
    PrivateReviewBundle,
    build_private_review_bundle,
    publish_private_review_bundle,
    read_private_review_bundle,
)
from indusbench.schema_validation import validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = "2026-07-27T09:00:00Z"
INTENDED_USE = "local_nonpublic_normalization"
POLICY_SCHEMA = ROOT / "schemas/private-corpus-policy.schema.json"
STRUCTURAL_QUARANTINE_SCHEMA = ROOT / "schemas/private-structural-quarantine.schema.json"
REVIEW_BUNDLE_SCHEMA = ROOT / "schemas/private-review-bundle.schema.json"
ENTRY_KEYS = {
    "relative_path",
    "content_sha256",
    "curation_status",
    "content_layer",
    "source_id",
    "source_locator",
    "source_revision",
    "provenance_status",
    "rights_status",
    "rights_evidence_status",
    "permitted_uses",
}


def make_owner_only(path: Path) -> None:
    # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    os.chmod(path, 0o700)


def write_private(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    os.chmod(path, 0o600)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_json(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for key, item in value.items():
            values.extend(walk_json(key))
            values.extend(walk_json(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(walk_json(item))
    return values


def values_for_keys(value: Any, names: set[str]) -> list[Any]:
    values: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in names:
                values.append(item)
            values.extend(values_for_keys(item, names))
    elif isinstance(value, list):
        for item in value:
            values.extend(values_for_keys(item, names))
    return values


class FindForbiddenBytes(bytes):
    def find(self, *_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("JSONL iterator performed a repeated bytes.find")


def private_tree_snapshot(path: Path) -> dict[str, tuple[str, int, bytes | None]]:
    snapshot: dict[str, tuple[str, int, bytes | None]] = {}
    if not path.exists():
        return snapshot
    pending = [path]
    while pending:
        current = pending.pop()
        relative = "." if current == path else current.relative_to(path).as_posix()
        metadata = current.lstat()
        if current.is_dir():
            snapshot[relative] = ("directory", metadata.st_mode, None)
            pending.extend(sorted(current.iterdir(), reverse=True))
        else:
            snapshot[relative] = ("file", metadata.st_mode, current.read_bytes())
    return snapshot


def corpus_snapshot(
    path: Path,
) -> dict[str, tuple[int, int, int, int, int, int, bytes | None]]:
    snapshot: dict[str, tuple[int, int, int, int, int, int, bytes | None]] = {}
    pending = [path]
    while pending:
        current = pending.pop()
        relative = "." if current == path else current.relative_to(path).as_posix()
        metadata = current.lstat()
        content = current.read_bytes() if current.is_file() else None
        snapshot[relative] = (
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_uid,
            metadata.st_gid,
            metadata.st_size,
            metadata.st_mtime_ns,
            content,
        )
        if current.is_dir():
            pending.extend(sorted(current.iterdir(), reverse=True))
    return snapshot


class PrivateReviewBundleTests(unittest.TestCase):
    maxDiff = None

    def test_generated_policy_is_deny_all_content_bound_and_schema_valid(
        self,
    ) -> None:
        private_filename = "PRIVATE_PATH_SENTINEL.json"
        private_value = "PRIVATE_VALUE_SENTINEL"
        raw = json.dumps(
            {"private_value": private_value},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        known_source_ids = {
            source["source_id"] for source in load_json(ROOT / "registry/sources.json")["sources"]
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / private_filename, raw)
            source_before = corpus_snapshot(corpus)

            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"K" * 32,
            )
            source_after = corpus_snapshot(corpus)

            policy = bundle.policy
            structural_quarantine = bundle.structural_quarantine
            bundle_document = bundle.as_dict()

        self.assertEqual(source_before, source_after)
        self.assertEqual("0.2.0", policy["schema_version"])
        self.assertEqual("private_corpus_use_policy", policy["policy_kind"])
        self.assertEqual(
            [],
            validate_schema_instance(policy, POLICY_SCHEMA),
        )
        self.assertEqual(
            [],
            validate_schema_instance(
                structural_quarantine,
                STRUCTURAL_QUARANTINE_SCHEMA,
            ),
        )
        self.assertEqual(
            [],
            validate_schema_instance(bundle_document, REVIEW_BUNDLE_SCHEMA),
        )
        self.assertEqual(1, len(policy["entries"]))
        entry = policy["entries"][0]
        self.assertEqual(ENTRY_KEYS, set(entry))
        self.assertEqual(private_filename, entry["relative_path"])
        self.assertEqual(
            "sha256:" + hashlib.sha256(raw).hexdigest(),
            entry["content_sha256"],
        )
        self.assertEqual("pending", entry["curation_status"])
        self.assertEqual("unknown", entry["content_layer"])
        self.assertNotIn(entry["source_id"], known_source_ids)
        self.assertIsNone(entry["source_locator"])
        self.assertIsNone(entry["source_revision"])
        self.assertEqual("unknown", entry["provenance_status"])
        self.assertEqual("unknown", entry["rights_status"])
        self.assertEqual("missing", entry["rights_evidence_status"])
        self.assertEqual([], entry["permitted_uses"])

        # These are private module documents: the exact path and binding digest
        # belong in the restricted policy, while raw corpus values belong in
        # neither generated document.
        policy_text = json.dumps(policy, ensure_ascii=False, sort_keys=True)
        quarantine_text = json.dumps(
            structural_quarantine,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertIn(private_filename, policy_text)
        self.assertIn(hashlib.sha256(raw).hexdigest(), policy_text)
        self.assertNotIn(private_value, policy_text)
        self.assertNotIn(private_value, quarantine_text)

        source_registry = load_json(ROOT / "registry/sources.json")
        quarantine_manifest = load_json(ROOT / "registry/quarantine.json")
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / private_filename, raw)
            result = audit_private_corpus(
                corpus.resolve(),
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=policy,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
                key=b"K" * 32,
            )

        self.assertFalse(result.summary["ready"])
        self.assertTrue(result.summary["reason_codes"])

    def test_content_replacement_is_rejected_by_policy_binding(self) -> None:
        original = b'{"private":"AAAA"}\n'
        replacement = b'{"private":"BBBB"}\n'
        self.assertEqual(len(original), len(replacement))
        source_registry = load_json(ROOT / "registry/sources.json")
        quarantine_manifest = load_json(ROOT / "registry/quarantine.json")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            source = corpus / "record.json"
            write_private(source, original)
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"B" * 32,
            )

            before = audit_private_corpus(
                corpus.resolve(),
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=bundle.policy,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
                key=b"B" * 32,
            )
            write_private(source, replacement)
            after = audit_private_corpus(
                corpus.resolve(),
                intended_use=INTENDED_USE,
                created_at=CREATED_AT,
                policy=bundle.policy,
                source_registry=source_registry,
                quarantine_manifest=quarantine_manifest,
                key=b"B" * 32,
            )

        self.assertNotIn(
            "POLICY_CONTENT_BINDING_MISMATCH",
            before.summary["reason_codes"],
        )
        self.assertIn(
            "POLICY_CONTENT_BINDING_MISMATCH",
            after.summary["reason_codes"],
        )
        self.assertFalse(after.summary["ready"])
        aggregate_text = json.dumps(
            after.report,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn("record.json", aggregate_text)
        self.assertNotIn(hashlib.sha256(original).hexdigest(), aggregate_text)
        self.assertNotIn(hashlib.sha256(replacement).hexdigest(), aggregate_text)

    def test_ragged_csv_ledger_uses_one_based_record_numbers_without_raw_values(
        self,
    ) -> None:
        private_filename = "PRIVATE_RAGGED_PATH_SENTINEL.csv"
        private_header = "PRIVATE_HEADER_SENTINEL"
        private_value = "PRIVATE_CELL_VALUE_SENTINEL"
        private_ragged_value = "PRIVATE_RAGGED_VALUE_SENTINEL"
        raw = (
            f'{private_header},second\n"{private_value}\ncontinued",ok\n{private_ragged_value}\n'
        ).encode()

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / private_filename, raw)

            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"R" * 32,
            )
            ledger = bundle.structural_quarantine

        self.assertEqual("0.1.0", ledger["schema_version"])
        self.assertEqual(
            [],
            validate_schema_instance(
                ledger,
                STRUCTURAL_QUARANTINE_SCHEMA,
            ),
        )
        ledger_text = json.dumps(ledger, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(private_filename, ledger_text)
        self.assertIn(hashlib.sha256(raw).hexdigest(), ledger_text)
        for raw_value in (
            private_header,
            private_value,
            "continued",
            private_ragged_value,
        ):
            self.assertNotIn(raw_value, ledger_text)

        record_numbers = values_for_keys(
            ledger,
            {
                "logical_record_number",
                "logical_record_numbers",
                "logical_row_number",
                "logical_row_numbers",
                "record_number",
                "record_numbers",
                "row_number",
                "row_numbers",
            },
        )
        flattened_record_numbers = walk_json(record_numbers)
        self.assertIn(3, flattened_record_numbers)
        self.assertNotIn(2, flattened_record_numbers)
        self.assertTrue(
            any(
                isinstance(value, str)
                and value
                in {
                    "CSV_RAGGED_RECORDS",
                    "CSV_RAGGED_ROW",
                    "CSV_ROW_WIDTH_MISMATCH",
                }
                for value in walk_json(ledger)
            )
        )

    def test_csv_preflight_bounds_records_before_csv_reader_materializes_them(
        self,
    ) -> None:
        cases = (
            (
                "columns",
                b"a,b,c,d,e\n",
                AuditLimits(
                    max_csv_bytes=256,
                    max_csv_columns=4,
                    max_csv_record_bytes=128,
                ),
                "CSV_COLUMN_LIMIT_EXCEEDED",
            ),
            (
                "record_bytes",
                b"A" * 65 + b"\n",
                AuditLimits(
                    max_csv_bytes=256,
                    max_csv_columns=4,
                    max_csv_record_bytes=64,
                ),
                "CSV_RECORD_LIMIT_EXCEEDED",
            ),
        )
        for case, raw, limits, expected_code in cases:
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                temporary = Path(temporary_directory)
                make_owner_only(temporary)
                corpus = temporary / "corpus"
                corpus.mkdir(mode=0o700)
                source = corpus / "bounded.csv"
                write_private(source, raw)
                descriptor = os.open(
                    source,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                )
                try:
                    finding = private_readiness_module._preflight_csv_structure(
                        descriptor,
                        limits,
                    )
                finally:
                    os.close(descriptor)
                self.assertIsNotNone(finding)
                assert finding is not None
                self.assertEqual(expected_code, finding.code)

                with (
                    patch.object(
                        private_readiness_module.csv,
                        "reader",
                        side_effect=AssertionError(
                            "bounded input reached csv.reader",
                        ),
                    ),
                    self.assertRaises(ValueError) as raised,
                ):
                    build_private_review_bundle(
                        corpus.resolve(),
                        CREATED_AT,
                        key=b"L" * 32,
                        limits=limits,
                    )
                self.assertEqual(
                    "RESOURCE_LIMIT_EXCEEDED",
                    str(raised.exception),
                )

    def test_csv_parser_pins_and_restores_its_declared_field_limit(self) -> None:
        raw = b"A" * 32 + b"\n"
        limits = AuditLimits(
            max_csv_bytes=256,
            max_csv_columns=4,
            max_csv_record_bytes=64,
        )
        previous_limit = private_readiness_module.csv.field_size_limit()
        try:
            private_readiness_module.csv.field_size_limit(8)
            with tempfile.TemporaryDirectory() as temporary_directory:
                temporary = Path(temporary_directory)
                make_owner_only(temporary)
                corpus = temporary / "corpus"
                corpus.mkdir(mode=0o700)
                write_private(corpus / "field.csv", raw)

                bundle = build_private_review_bundle(
                    corpus.resolve(),
                    CREATED_AT,
                    key=b"G" * 32,
                    limits=limits,
                )

                self.assertEqual([], bundle.structural_quarantine["entries"])
                self.assertEqual(
                    8,
                    private_readiness_module.csv.field_size_limit(),
                )
        finally:
            private_readiness_module.csv.field_size_limit(previous_limit)

    def test_json_complexity_limits_apply_before_json_materialization(self) -> None:
        cases = (
            (
                "nodes",
                b"[" + (b"[]," * 100) + b"[]]",
                AuditLimits(max_json_nodes=50),
            ),
            (
                "depth",
                (b"[" * 6) + b"0" + (b"]" * 6),
                AuditLimits(max_json_depth=4),
            ),
            (
                "number_bytes",
                b'{"n":' + (b"1" * 513) + b"}",
                AuditLimits(),
            ),
        )
        for case, raw, limits in cases:
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                temporary = Path(temporary_directory)
                make_owner_only(temporary)
                corpus = temporary / "corpus"
                corpus.mkdir(mode=0o700)
                write_private(corpus / "bounded.json", raw)

                with (
                    patch.object(
                        private_readiness_module.json,
                        "loads",
                        side_effect=AssertionError(
                            "over-limit JSON reached json.loads",
                        ),
                    ),
                    self.assertRaises(ValueError) as raised,
                ):
                    build_private_review_bundle(
                        corpus.resolve(),
                        CREATED_AT,
                        key=b"J" * 32,
                        limits=limits,
                    )

                self.assertEqual(
                    "RESOURCE_LIMIT_EXCEEDED",
                    str(raised.exception),
                )

    def test_jsonl_record_iteration_is_linear_and_streaming(self) -> None:
        raw = FindForbiddenBytes(
            (b"{}\n" * 2000) + (b"{}\r" * 2000) + (b"{}\r\n" * 2000),
        )

        records = list(private_readiness_module._iter_json_lines(raw))

        self.assertEqual(6000, len(records))
        self.assertEqual(list(range(1, 6001)), [number for number, _ in records])
        self.assertTrue(all(line == b"{}" for _, line in records))

    def test_duplicate_content_is_quarantined_by_unambiguous_policy_indices(
        self,
    ) -> None:
        raw = b"first,second\nPRIVATE_DUPLICATE_VALUE_SENTINEL\n"
        expected_digest = "sha256:" + hashlib.sha256(raw).hexdigest()

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "a.csv", raw)
            write_private(corpus / "b.csv", raw)

            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"D" * 32,
            )

        self.assertEqual(
            ["a.csv", "b.csv"],
            [entry["relative_path"] for entry in bundle.policy["entries"]],
        )
        self.assertEqual(
            [expected_digest, expected_digest],
            [entry["content_sha256"] for entry in bundle.policy["entries"]],
        )
        policy_entry_indices = values_for_keys(
            bundle.structural_quarantine,
            {"policy_entry_index"},
        )
        self.assertEqual({0, 1}, set(policy_entry_indices))
        self.assertNotIn(
            "PRIVATE_DUPLICATE_VALUE_SENTINEL",
            json.dumps(
                bundle.structural_quarantine,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    def test_empty_corpus_is_rejected_without_disclosing_its_path(self) -> None:
        corpus_name = "PRIVATE_EMPTY_CORPUS_SENTINEL"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / corpus_name
            corpus.mkdir(mode=0o700)

            with self.assertRaises(ValueError) as raised:
                build_private_review_bundle(
                    corpus.resolve(),
                    CREATED_AT,
                    key=b"E" * 32,
                )

        message = str(raised.exception)
        self.assertNotIn(corpus_name, message)
        self.assertNotIn(str(corpus.resolve()), message)
        self.assertIsNotNone(re.fullmatch(r"[A-Z][A-Z0-9_]*", message))

    def test_bidi_control_in_path_is_rejected_without_disclosure(self) -> None:
        private_filename = "safe-\u202ePRIVATE_BIDI_SENTINEL.json"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / private_filename, b"{}\n")

            with self.assertRaises(ValueError) as raised:
                build_private_review_bundle(
                    corpus.resolve(),
                    CREATED_AT,
                    key=b"U" * 32,
                )

        message = str(raised.exception)
        self.assertEqual("PATH_PROFILE_INVALID_OR_COLLISION", message)
        self.assertNotIn(private_filename, message)

    def test_publication_is_atomic_and_never_replaces_existing_destination(
        self,
    ) -> None:
        existing_sentinel = b"EXISTING_PRIVATE_DESTINATION_SENTINEL\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            output_parent = temporary / "private-output"
            output_parent.mkdir(mode=0o700)
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"P" * 32,
            )
            source_before_publication = corpus_snapshot(corpus)

            destination = output_parent / "review-bundle.json"
            publication = publish_private_review_bundle(
                corpus.resolve(),
                destination.resolve(strict=False),
                bundle,
            )
            self.assertEqual(
                "committed_and_verified",
                publication.write_state,
            )
            self.assertEqual(source_before_publication, corpus_snapshot(corpus))
            first_snapshot = private_tree_snapshot(destination)
            self.assertTrue(first_snapshot)

            with self.assertRaises(ValueError) as repeated:
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    bundle,
                )
            self.assertEqual("OUTPUT_ALREADY_EXISTS", str(repeated.exception))
            self.assertNotIn(str(destination), str(repeated.exception))
            self.assertEqual(first_snapshot, private_tree_snapshot(destination))

            occupied = output_parent / "occupied-bundle.json"
            write_private(occupied, existing_sentinel)
            with self.assertRaises(ValueError) as occupied_error:
                publish_private_review_bundle(
                    corpus.resolve(),
                    occupied.resolve(strict=False),
                    bundle,
                )
            self.assertEqual("OUTPUT_ALREADY_EXISTS", str(occupied_error.exception))
            self.assertNotIn(str(occupied), str(occupied_error.exception))
            self.assertNotIn(
                existing_sentinel.decode().strip(),
                str(occupied_error.exception),
            )
            self.assertEqual(existing_sentinel, occupied.read_bytes())

    def test_output_inside_corpus_or_through_symlink_parent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"O" * 32,
            )

            with self.assertRaises(ValueError) as overlap:
                publish_private_review_bundle(
                    corpus.resolve(),
                    (corpus / "private-review.json").resolve(strict=False),
                    bundle,
                )
            self.assertEqual("OUTPUT_BOUNDARY_INVALID", str(overlap.exception))
            self.assertFalse((corpus / "private-review.json").exists())

            output_parent = temporary / "output"
            output_parent.mkdir(mode=0o700)
            linked_parent = temporary / "linked-output"
            linked_parent.symlink_to(output_parent, target_is_directory=True)
            with self.assertRaises(ValueError) as linked:
                publish_private_review_bundle(
                    corpus.resolve(),
                    linked_parent / "private-review.json",
                    bundle,
                )
            self.assertIn(
                str(linked.exception),
                {
                    "OUTPUT_BOUNDARY_INVALID",
                    "ROOT_BOUNDARY_INVALID",
                },
            )
            self.assertFalse((output_parent / "private-review.json").exists())

    def test_replaced_scan_root_is_rejected_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"S" * 32,
            )

            moved_corpus = temporary / "moved-corpus"
            corpus.rename(moved_corpus)
            corpus.mkdir(mode=0o700)
            destination = moved_corpus / "private-review.json"

            with self.assertRaises(ValueError) as raised:
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    bundle,
                )

            self.assertEqual(
                "CONCURRENT_MUTATION_DETECTED",
                str(raised.exception),
            )
            self.assertFalse(destination.exists())

    def test_schema_invalid_bundle_is_rejected_by_direct_read_and_publish_apis(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            output_parent = temporary / "output"
            output_parent.mkdir(mode=0o700)
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"V" * 32,
            )
            invalid_policy = copy.deepcopy(bundle.policy)
            invalid_policy["entries"][0]["ready"] = True
            invalid_bundle = PrivateReviewBundle(
                policy=invalid_policy,
                structural_quarantine=copy.deepcopy(
                    bundle.structural_quarantine,
                ),
                source_root_identity=bundle.source_root_identity,
            )
            destination = output_parent / "rejected.json"

            with self.assertRaises(ValueError) as publish_error:
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    invalid_bundle,
                )
            self.assertEqual(
                "ARTIFACT_VALIDATION_FAILED",
                str(publish_error.exception),
            )
            self.assertFalse(destination.exists())

            malformed_path = output_parent / "malformed.json"
            malformed_document = invalid_bundle.as_dict()
            write_private(
                malformed_path,
                (
                    json.dumps(
                        malformed_document,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode(),
            )
            with self.assertRaises(ValueError) as read_error:
                read_private_review_bundle(malformed_path.resolve())
            self.assertEqual(
                "ARTIFACT_VALIDATION_FAILED",
                str(read_error.exception),
            )

    def test_publish_rechecks_each_normative_document_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            output_parent = temporary / "output"
            output_parent.mkdir(mode=0o700)
            destination = output_parent / "private-review.json"
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"Z" * 32,
            )

            with (
                patch.object(
                    private_review_module,
                    "MAX_POLICY_BYTES",
                    1,
                ),
                self.assertRaises(ValueError) as raised,
            ):
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    bundle,
                )

            self.assertEqual(
                "RESOURCE_LIMIT_EXCEEDED",
                str(raised.exception),
            )
            self.assertFalse(destination.exists())

    def test_write_failure_removes_unpublished_staging_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            output_parent = temporary / "output"
            output_parent.mkdir(mode=0o700)
            destination = output_parent / "private-review.json"
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"W" * 32,
            )

            with (
                patch.object(
                    private_review_module,
                    "_write_all",
                    side_effect=OSError("simulated write failure"),
                ),
                self.assertRaises(ValueError) as raised,
            ):
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    bundle,
                )

            self.assertEqual("OUTPUT_WRITE_FAILED", str(raised.exception))
            self.assertFalse(destination.exists())
            self.assertEqual(
                [],
                list(output_parent.glob(".private-review-*.tmp")),
            )

    def test_parent_fsync_failure_preserves_committed_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            output_parent = temporary / "output"
            output_parent.mkdir(mode=0o700)
            destination = output_parent / "private-review.json"
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"F" * 32,
            )
            real_fsync = private_review_module.os.fsync

            def fail_directory_fsync(descriptor: int) -> None:
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise OSError("simulated directory fsync failure")
                real_fsync(descriptor)

            with patch.object(
                private_review_module.os,
                "fsync",
                side_effect=fail_directory_fsync,
            ):
                publication = publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    bundle,
                )

            self.assertEqual(
                "committed_durability_unknown",
                publication.write_state,
            )
            self.assertEqual(
                "OUTPUT_COMMIT_STATE_UNKNOWN",
                publication.reason_code,
            )
            self.assertTrue(destination.is_file())
            with self.assertRaises(ValueError) as repeated:
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(),
                    bundle,
                )
            self.assertEqual("OUTPUT_ALREADY_EXISTS", str(repeated.exception))

    def test_destination_insertion_race_is_no_replace(self) -> None:
        inserted = b"INSERTED_DESTINATION_SENTINEL\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            make_owner_only(temporary)
            corpus = temporary / "corpus"
            corpus.mkdir(mode=0o700)
            write_private(corpus / "record.json", b"{}\n")
            output_parent = temporary / "output"
            output_parent.mkdir(mode=0o700)
            destination = output_parent / "private-review.json"
            bundle = build_private_review_bundle(
                corpus.resolve(),
                CREATED_AT,
                key=b"I" * 32,
            )
            real_link = private_review_module._link_no_replace

            def insert_destination(
                source_name: str,
                destination_name: str,
                *,
                parent_descriptor: int,
            ) -> None:
                descriptor = os.open(
                    destination_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_descriptor,
                )
                try:
                    os.write(descriptor, inserted)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                real_link(
                    source_name,
                    destination_name,
                    parent_descriptor=parent_descriptor,
                )

            with (
                patch.object(
                    private_review_module,
                    "_link_no_replace",
                    side_effect=insert_destination,
                ),
                self.assertRaises(ValueError) as raised,
            ):
                publish_private_review_bundle(
                    corpus.resolve(),
                    destination.resolve(strict=False),
                    bundle,
                )

            self.assertEqual("OUTPUT_ALREADY_EXISTS", str(raised.exception))
            self.assertEqual(inserted, destination.read_bytes())

    def test_staging_tamper_and_requested_parent_swap_never_report_success(
        self,
    ) -> None:
        for case in ("staging_tamper", "parent_swap"):
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                temporary = Path(temporary_directory)
                make_owner_only(temporary)
                corpus = temporary / "corpus"
                corpus.mkdir(mode=0o700)
                write_private(corpus / "record.json", b"{}\n")
                output_parent = temporary / "output"
                output_parent.mkdir(mode=0o700)
                destination = output_parent / "private-review.json"
                bundle = build_private_review_bundle(
                    corpus.resolve(),
                    CREATED_AT,
                    key=b"T" * 32,
                )
                real_link = private_review_module._link_no_replace
                moved_parent = temporary / "moved-output"
                decoy_parent = temporary / "decoy-output"

                def interfere(
                    source_name: str,
                    destination_name: str,
                    *,
                    parent_descriptor: int,
                    active_case: str = case,
                    link: Any = real_link,
                    output: Path = output_parent,
                    moved: Path = moved_parent,
                    decoy: Path = decoy_parent,
                ) -> None:
                    if active_case == "staging_tamper":
                        descriptor = os.open(
                            source_name,
                            os.O_WRONLY | os.O_NOFOLLOW,
                            dir_fd=parent_descriptor,
                        )
                        try:
                            os.lseek(descriptor, 0, os.SEEK_SET)
                            os.write(descriptor, b"X")
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                    link(
                        source_name,
                        destination_name,
                        parent_descriptor=parent_descriptor,
                    )
                    if active_case == "parent_swap":
                        output.rename(moved)
                        decoy.mkdir(mode=0o700)
                        output.symlink_to(
                            decoy,
                            target_is_directory=True,
                        )

                with patch.object(
                    private_review_module,
                    "_link_no_replace",
                    side_effect=interfere,
                ):
                    publication = publish_private_review_bundle(
                        corpus.resolve(),
                        destination.resolve(strict=False),
                        bundle,
                    )

                self.assertEqual("outcome_unknown", publication.write_state)
                self.assertIsNotNone(publication.reason_code)
                if case == "parent_swap":
                    output_parent.unlink()
                    moved_parent.rename(output_parent)
                    decoy_parent.rmdir()
                self.assertTrue(destination.is_file())
                with self.assertRaises(ValueError) as repeated:
                    publish_private_review_bundle(
                        corpus.resolve(),
                        destination.resolve(),
                        bundle,
                    )
                self.assertEqual(
                    "OUTPUT_ALREADY_EXISTS",
                    str(repeated.exception),
                )


if __name__ == "__main__":
    unittest.main()
