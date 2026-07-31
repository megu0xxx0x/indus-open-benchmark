from __future__ import annotations

import ast
import binascii
import gzip
import hashlib
import importlib.util
import inspect
import io
import json
import os
import socket
import stat
import tarfile
import tempfile
import threading
import unittest
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator, ValidationError

from indusbench import kp1979_v3_control_freeze as freeze

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "a" * 40
CORE_WORKFLOW_SHA256 = "9bd93bed5359bd8cb396a0f6be063b5bc6f76ad1b84e1d6338e1edc14ae0300a"
CALLER_WORKFLOW_SHA256 = "aca066fc5df3565af831669b28ab661482dc0a21f319f6759fd912365c3f3442"


@contextmanager
def safe_source_tree() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="indus-control-freeze-source-") as raw:
        source_root = Path(raw) / "source"
        source_root.mkdir(mode=0o700)
        for relative in freeze.PAYLOAD_PATHS:
            source = ROOT / relative
            destination = source_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            cursor = destination.parent
            while cursor != source_root:
                cursor.chmod(0o755)
                cursor = cursor.parent
            destination.write_bytes(source.read_bytes())
            destination.chmod(0o644)
        yield source_root


def build_from(source_root: Path, commit: str = SOURCE_COMMIT) -> bytes:
    module_path = source_root / freeze._MODULE_RELATIVE_PATH
    with (
        mock.patch.object(freeze, "_SOURCE_ROOT", source_root),
        mock.patch.object(freeze, "_MODULE_PATH", module_path),
    ):
        return freeze.build_control_bundle(source_commit=commit)


def decode_subject(subject: bytes) -> tuple[bytes, dict[str, bytes]]:
    tar_bytes = freeze._decode_stored_gzip(subject)
    return tar_bytes, freeze._decode_tar(tar_bytes)


def repack_members(members: Mapping[str, bytes]) -> bytes:
    return freeze._encode_stored_gzip(freeze._encode_tar(members))


def mutate_manifest(
    subject: bytes,
    mutation: Callable[[dict[str, object]], None],
) -> bytes:
    _tar_bytes, members = decode_subject(subject)
    manifest = json.loads(members[freeze.MANIFEST_NAME])
    assert isinstance(manifest, dict)
    mutation(manifest)
    changed = dict(members)
    changed[freeze.MANIFEST_NAME] = freeze._canonical_json_bytes(manifest)
    return repack_members(changed)


def member_offsets(tar_bytes: bytes) -> list[tuple[int, int, int]]:
    offsets: list[tuple[int, int, int]] = []
    position = 0
    terminal = len(tar_bytes) - 1024
    while position < terminal:
        header_offset = position
        size = int(tar_bytes[position + 124 : position + 135], 8)
        position += 512
        data_offset = position
        position += size + ((-size) % 512)
        offsets.append((header_offset, data_offset, size))
    assert position == terminal
    return offsets


def rewrite_header(
    tar_bytes: bytes,
    member_index: int,
    start: int,
    replacement: bytes,
    *,
    repair_checksum: bool = True,
) -> bytes:
    changed = bytearray(tar_bytes)
    header_offset, _data_offset, _size = member_offsets(tar_bytes)[member_index]
    changed[header_offset + start : header_offset + start + len(replacement)] = replacement
    if repair_checksum:
        header = bytearray(changed[header_offset : header_offset + 512])
        header[148:156] = b"        "
        header[148:156] = f"{sum(header):06o}\0 ".encode("ascii")
        changed[header_offset : header_offset + 512] = header
    return bytes(changed)


def arbitrary_stored_gzip(blocks: list[bytes]) -> bytes:
    assert blocks
    output = bytearray(freeze._GZIP_HEADER)
    payload = b"".join(blocks)
    for index, block in enumerate(blocks):
        assert len(block) <= 65_535
        output.append(1 if index == len(blocks) - 1 else 0)
        output.extend(len(block).to_bytes(2, "little"))
        output.extend((len(block) ^ 0xFFFF).to_bytes(2, "little"))
        output.extend(block)
    output.extend((binascii.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "little"))
    output.extend((len(payload) & 0xFFFFFFFF).to_bytes(4, "little"))
    return bytes(output)


class InvalidBundleMixin(unittest.TestCase):
    def assert_invalid_bundle(self, subject: bytes, commit: str = SOURCE_COMMIT) -> None:
        with self.assertRaises(freeze.KP1979V3ControlFreezeError) as caught:
            freeze.verify_control_bundle(subject, expected_source_commit=commit)
        self.assertEqual(freeze.ControlFreezeErrorCode.INVALID_BUNDLE, caught.exception.code)
        self.assertEqual("invalid_bundle", str(caught.exception))


class ControlFreezeCanonicalTests(InvalidBundleMixin):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_context = safe_source_tree()
        cls.source_root = cls.source_context.__enter__()
        cls.subject = build_from(cls.source_root)
        cls.tar_bytes, cls.members = decode_subject(cls.subject)
        cls.manifest = json.loads(cls.members[freeze.MANIFEST_NAME])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_context.__exit__(None, None, None)

    def test_exact_roster_counts_and_manifest_payload(self) -> None:
        self.assertEqual(36, len(freeze.PAYLOAD_PATHS))
        self.assertEqual(tuple(sorted(freeze.PAYLOAD_PATHS)), freeze.PAYLOAD_PATHS)
        self.assertEqual(37, len(self.members))
        self.assertEqual(
            tuple(sorted((freeze.MANIFEST_NAME, *freeze.PAYLOAD_PATHS))),
            tuple(self.members),
        )
        self.assertEqual(36, len(self.manifest["payload"]))
        self.assertNotIn(
            freeze.MANIFEST_NAME,
            [entry["path"] for entry in self.manifest["payload"]],
        )

    def test_manifest_is_compact_ascii_canonical_and_schema_valid(self) -> None:
        raw_manifest = self.members[freeze.MANIFEST_NAME]
        self.assertTrue(raw_manifest.endswith(b"\n"))
        self.assertTrue(raw_manifest.isascii())
        self.assertEqual(freeze._canonical_json_bytes(self.manifest), raw_manifest)
        schema_raw = self.members["schemas/kp1979-v3-control-bundle-manifest.schema.json"]
        schema = json.loads(schema_raw)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.manifest)

    def test_manifest_closed_identity_and_nonoperational_fields(self) -> None:
        expected = {
            "case_invocations": 32,
            "control_identity": freeze.CONTROL_IDENTITY,
            "detector_component": "absent",
            "format": freeze.MANIFEST_FORMAT,
            "integration_binding": "absent",
            "metamorphic_endpoint_invocations": 16,
            "non_operational": True,
            "protocol_identity": freeze.PROTOCOL_IDENTITY,
            "source_commit": SOURCE_COMMIT,
            "source_only": True,
            "target_algorithm_identity": freeze.TARGET_ALGORITHM_IDENTITY,
            "target_round_selected": False,
            "total_worker_invocations": 48,
            "version": 1,
            "worker_identity": freeze.WORKER_IDENTITY,
        }
        for key, value in expected.items():
            self.assertIs(type(value), type(self.manifest[key]))
            self.assertEqual(value, self.manifest[key])

    def test_payload_entries_match_exact_member_bytes(self) -> None:
        for expected_path, entry in zip(
            freeze.PAYLOAD_PATHS,
            self.manifest["payload"],
            strict=True,
        ):
            self.assertEqual(expected_path, entry["path"])
            raw = self.members[expected_path]
            self.assertEqual(len(raw), entry["size"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])

    def test_verification_summary_is_minimal_and_exact(self) -> None:
        summary = freeze.verify_control_bundle(
            self.subject,
            expected_source_commit=SOURCE_COMMIT,
        )
        self.assertEqual(
            {
                "source_commit",
                "member_count",
                "payload_count",
                "uncompressed_size",
                "subject_sha256",
            },
            set(summary.__dataclass_fields__),
        )
        self.assertEqual(37, summary.member_count)
        self.assertEqual(36, summary.payload_count)
        self.assertEqual(len(self.tar_bytes), summary.uncompressed_size)
        self.assertEqual(hashlib.sha256(self.subject).hexdigest(), summary.subject_sha256)

    def test_double_build_is_identical_across_cwd_and_umask(self) -> None:
        previous_cwd = Path.cwd()
        previous_umask = os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-control-cwd-a-") as first_cwd:
                os.chdir(first_cwd)
                first = build_from(self.source_root)
            os.umask(0o027)
            with tempfile.TemporaryDirectory(prefix="indus-control-cwd-b-") as second_cwd:
                os.chdir(second_cwd)
                second = build_from(self.source_root)
        finally:
            os.chdir(previous_cwd)
            os.umask(previous_umask)
        self.assertEqual(self.subject, first)
        self.assertEqual(first, second)

    def test_gzip_is_exact_stored_deflate_profile(self) -> None:
        self.assertEqual(b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff", self.subject[:10])
        self.assertEqual(self.tar_bytes, freeze._decode_stored_gzip(self.subject))
        self.assertEqual(self.subject, freeze._encode_stored_gzip(self.tar_bytes))
        self.assertEqual(
            binascii.crc32(self.tar_bytes) & 0xFFFFFFFF,
            int.from_bytes(self.subject[-8:-4], "little"),
        )
        self.assertEqual(len(self.tar_bytes), int.from_bytes(self.subject[-4:], "little"))

    def test_tar_is_exact_canonical_ustar_profile(self) -> None:
        self.assertEqual(0, len(self.tar_bytes) % 512)
        self.assertEqual(bytes(1024), self.tar_bytes[-1024:])
        offsets = member_offsets(self.tar_bytes)
        self.assertEqual(37, len(offsets))
        for header_offset, data_offset, size in offsets:
            header = self.tar_bytes[header_offset : header_offset + 512]
            self.assertEqual(b"0000644\0", header[100:108])
            self.assertEqual(b"0000000\0", header[108:116])
            self.assertEqual(b"0000000\0", header[116:124])
            self.assertEqual(b"00000000000\0", header[136:148])
            self.assertEqual(b"0", header[156:157])
            self.assertEqual(bytes(100), header[157:257])
            self.assertEqual(b"ustar\0", header[257:263])
            self.assertEqual(b"00", header[263:265])
            self.assertEqual(bytes(247), header[265:512])
            self.assertFalse(
                any(self.tar_bytes[data_offset + size : data_offset + size + ((-size) % 512)])
            )

    def test_exact_reconstruction_matches_subject(self) -> None:
        self.assertEqual(self.tar_bytes, freeze._encode_tar(self.members))
        self.assertEqual(self.subject, repack_members(self.members))

    def test_schema_rejects_extra_fields_bool_as_int_and_wrong_order(self) -> None:
        schema = json.loads(self.members["schemas/kp1979-v3-control-bundle-manifest.schema.json"])
        validator = Draft202012Validator(schema)
        candidates = []
        extra = dict(self.manifest)
        extra["extra"] = None
        candidates.append(extra)
        bool_as_int = dict(self.manifest)
        bool_as_int["source_only"] = 1
        candidates.append(bool_as_int)
        wrong_order = dict(self.manifest)
        wrong_payload = list(self.manifest["payload"])
        wrong_payload[0], wrong_payload[1] = wrong_payload[1], wrong_payload[0]
        wrong_order["payload"] = wrong_payload
        candidates.append(wrong_order)
        for candidate in candidates:
            with self.subTest(candidate=candidate), self.assertRaises(ValidationError):
                validator.validate(candidate)


class ControlFreezeGzipHostileTests(InvalidBundleMixin):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_context = safe_source_tree()
        cls.source_root = cls.source_context.__enter__()
        cls.subject = build_from(cls.source_root)
        cls.tar_bytes, _members = decode_subject(cls.subject)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_context.__exit__(None, None, None)

    def test_rejects_trailing_concatenated_truncated_and_oversized_gzip(self) -> None:
        candidates = (
            self.subject + b"x",
            self.subject + self.subject,
            self.subject[:-1],
            self.subject[:10],
            self.subject + bytes(freeze.MAX_SUBJECT_BYTES),
        )
        for candidate in candidates:
            with self.subTest(size=len(candidate)):
                self.assert_invalid_bundle(candidate)

    def test_rejects_every_noncanonical_gzip_header_field(self) -> None:
        for index, replacement in ((3, 1), (4, 1), (8, 1), (9, 3)):
            changed = bytearray(self.subject)
            changed[index] = replacement
            with self.subTest(index=index):
                self.assert_invalid_bundle(bytes(changed))

    def test_rejects_bad_block_type_length_inverse_crc_and_isize(self) -> None:
        candidates: list[bytes] = []
        bad_type = bytearray(self.subject)
        bad_type[10] = 2
        candidates.append(bytes(bad_type))
        bad_inverse = bytearray(self.subject)
        bad_inverse[13] ^= 1
        candidates.append(bytes(bad_inverse))
        bad_crc = bytearray(self.subject)
        bad_crc[-8] ^= 1
        candidates.append(bytes(bad_crc))
        bad_size = bytearray(self.subject)
        bad_size[-4] ^= 1
        candidates.append(bytes(bad_size))
        for candidate in candidates:
            self.assert_invalid_bundle(candidate)

    def test_rejects_noncanonical_stored_block_framing(self) -> None:
        blocks = [self.tar_bytes[:10]]
        remainder = self.tar_bytes[10:]
        while len(remainder) > 65_535:
            blocks.append(remainder[:65_535])
            remainder = remainder[65_535:]
        blocks.append(remainder)
        self.assert_invalid_bundle(arbitrary_stored_gzip(blocks))

    def test_rejects_stored_deflate_bomb_before_tar_parse(self) -> None:
        payload = bytes(freeze.MAX_UNCOMPRESSED_BYTES + 1)
        blocks = [payload[index : index + 65_535] for index in range(0, len(payload), 65_535)]
        self.assert_invalid_bundle(arbitrary_stored_gzip(blocks))


class ControlFreezeTarHostileTests(InvalidBundleMixin):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_context = safe_source_tree()
        cls.source_root = cls.source_context.__enter__()
        cls.subject = build_from(cls.source_root)
        cls.tar_bytes, cls.members = decode_subject(cls.subject)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_context.__exit__(None, None, None)

    def assert_invalid_tar(self, tar_bytes: bytes) -> None:
        self.assert_invalid_bundle(freeze._encode_stored_gzip(tar_bytes))

    def test_rejects_checksum_and_every_nonregular_type(self) -> None:
        checksum_bad = bytearray(self.tar_bytes)
        checksum_bad[0] ^= 1
        self.assert_invalid_tar(bytes(checksum_bad))
        for typeflag in (b"1", b"2", b"x", b"3", b"4", b"6"):
            with self.subTest(typeflag=typeflag):
                self.assert_invalid_tar(rewrite_header(self.tar_bytes, 0, 156, typeflag))

    def test_rejects_noncanonical_mode_owner_time_and_ustar_metadata(self) -> None:
        mutations = (
            (100, b"0000600\0"),
            (108, b"0000001\0"),
            (116, b"0000001\0"),
            (136, b"00000000001\0"),
            (157, b"x"),
            (257, b"ustar "),
            (263, b"01"),
            (265, b"x"),
            (329, b"0000000\0"),
            (345, b"x"),
            (500, b"x"),
        )
        for start, replacement in mutations:
            with self.subTest(start=start):
                self.assert_invalid_tar(rewrite_header(self.tar_bytes, 0, start, replacement))

    def test_rejects_path_traversal_duplicate_order_and_nonascii_names(self) -> None:
        first_name = b"LICENSE" + bytes(93)
        candidates = (
            rewrite_header(self.tar_bytes, 0, 0, b"../evil" + bytes(93)),
            rewrite_header(self.tar_bytes, 1, 0, first_name),
            rewrite_header(self.tar_bytes, 1, 0, b"A" + bytes(99)),
            rewrite_header(self.tar_bytes, 0, 0, b"\xff" + bytes(99)),
        )
        for candidate in candidates:
            self.assert_invalid_tar(candidate)

    def test_rejects_padding_early_zero_missing_terminator_and_trailing_tar_data(self) -> None:
        offsets = member_offsets(self.tar_bytes)
        _header, data, size = offsets[0]
        padding_offset = data + size
        bad_padding = bytearray(self.tar_bytes)
        bad_padding[padding_offset] = 1
        candidates = (
            bytes(bad_padding),
            bytes(512) + self.tar_bytes[512:],
            self.tar_bytes[:-512],
            self.tar_bytes[:-1024] + bytes(1536),
        )
        for candidate in candidates:
            self.assert_invalid_tar(candidate)

    def test_rejects_missing_extra_or_payload_tampered_members(self) -> None:
        missing = dict(self.members)
        missing.pop("LICENSE")
        extra = dict(self.members)
        extra["extra"] = b"x"
        tampered = dict(self.members)
        tampered["LICENSE"] += b"x"
        for candidate in (missing, extra, tampered):
            self.assert_invalid_bundle(repack_members(candidate))

    def test_independent_gzip_and_tarfile_oracles_match_exact_profile(self) -> None:
        self.assertEqual(self.tar_bytes, gzip.decompress(self.subject))
        with tarfile.open(fileobj=io.BytesIO(self.subject), mode="r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual(list(self.members), [member.name for member in members])
            self.assertEqual(37, len(members))
            for member in members:
                self.assertTrue(member.isreg())
                self.assertEqual(0o644, member.mode)
                self.assertEqual(0, member.uid)
                self.assertEqual(0, member.gid)
                self.assertEqual(0, member.mtime)
                self.assertEqual("", member.uname)
                self.assertEqual("", member.gname)
                self.assertEqual("", member.linkname)
                extracted = archive.extractfile(member)
                self.assertIsNotNone(extracted)
                assert extracted is not None
                self.assertEqual(self.members[member.name], extracted.read())


class ControlFreezeManifestHostileTests(InvalidBundleMixin):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_context = safe_source_tree()
        cls.source_root = cls.source_context.__enter__()
        cls.subject = build_from(cls.source_root)
        _tar_bytes, cls.members = decode_subject(cls.subject)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_context.__exit__(None, None, None)

    def test_rejects_extra_missing_duplicate_and_noncanonical_manifest_keys(self) -> None:
        def remove_format(value: dict[str, object]) -> None:
            value.pop("format")

        extra = mutate_manifest(self.subject, lambda value: value.__setitem__("extra", None))
        missing = mutate_manifest(self.subject, remove_format)
        changed = dict(self.members)
        raw = changed[freeze.MANIFEST_NAME]
        duplicate = b'{"format":"kp1979-v3-control-bundle-manifest",' + raw.removeprefix(b"{")
        changed[freeze.MANIFEST_NAME] = duplicate
        pretty_members = dict(self.members)
        pretty_members[freeze.MANIFEST_NAME] = (
            json.dumps(json.loads(raw), indent=2).encode("ascii") + b"\n"
        )
        for candidate in (extra, missing, repack_members(changed), repack_members(pretty_members)):
            self.assert_invalid_bundle(candidate)

    def test_rejects_every_changed_closed_field_and_bool_as_int(self) -> None:
        replacements: dict[str, object] = {
            "format": "wrong",
            "version": 2,
            "protocol_identity": "wrong",
            "control_identity": "wrong",
            "target_algorithm_identity": "wrong",
            "worker_identity": "wrong",
            "case_invocations": 31,
            "metamorphic_endpoint_invocations": 15,
            "total_worker_invocations": 47,
            "source_only": 1,
            "non_operational": False,
            "target_round_selected": True,
            "detector_component": "present",
            "integration_binding": "present",
        }
        for key, replacement in replacements.items():
            with self.subTest(key=key):
                candidate = mutate_manifest(
                    self.subject,
                    lambda value, key=key, replacement=replacement: value.__setitem__(
                        key,
                        replacement,
                    ),
                )
                self.assert_invalid_bundle(candidate)

    def test_rejects_changed_source_commit_against_expected_commit(self) -> None:
        changed = mutate_manifest(
            self.subject,
            lambda value: value.__setitem__("source_commit", "b" * 40),
        )
        self.assert_invalid_bundle(changed)
        self.assert_invalid_bundle(self.subject, commit="b" * 40)

    def test_rejects_payload_order_count_path_size_hash_and_self_entry(self) -> None:
        def swap(value: dict[str, object]) -> None:
            payload = value["payload"]
            assert isinstance(payload, list)
            payload[0], payload[1] = payload[1], payload[0]

        def remove(value: dict[str, object]) -> None:
            payload = value["payload"]
            assert isinstance(payload, list)
            payload.pop()

        def wrong_path(value: dict[str, object]) -> None:
            payload = value["payload"]
            assert isinstance(payload, list)
            payload[0]["path"] = "wrong"

        def wrong_size(value: dict[str, object]) -> None:
            payload = value["payload"]
            assert isinstance(payload, list)
            payload[0]["size"] = True

        def wrong_hash(value: dict[str, object]) -> None:
            payload = value["payload"]
            assert isinstance(payload, list)
            payload[0]["sha256"] = "A" * 64

        def self_entry(value: dict[str, object]) -> None:
            payload = value["payload"]
            assert isinstance(payload, list)
            payload[0]["path"] = freeze.MANIFEST_NAME

        for mutation in (swap, remove, wrong_path, wrong_size, wrong_hash, self_entry):
            with self.subTest(mutation=mutation.__name__):
                self.assert_invalid_bundle(mutate_manifest(self.subject, mutation))

    def test_rejects_non_utf8_no_newline_and_json_constants(self) -> None:
        candidates: list[bytes] = []
        for manifest_raw in (
            b"\xff\n",
            self.members[freeze.MANIFEST_NAME].rstrip(b"\n"),
            b'{"value":NaN}\n',
        ):
            changed = dict(self.members)
            changed[freeze.MANIFEST_NAME] = manifest_raw
            candidates.append(repack_members(changed))
        for candidate in candidates:
            self.assert_invalid_bundle(candidate)


class ControlFreezeSourceSafetyTests(unittest.TestCase):
    def assert_source_error(
        self,
        source_root: Path,
        expected: freeze.ControlFreezeErrorCode,
    ) -> None:
        with self.assertRaises(freeze.KP1979V3ControlFreezeError) as caught:
            build_from(source_root)
        self.assertEqual(expected, caught.exception.code)
        self.assertEqual(expected.value, str(caught.exception))

    def test_rejects_missing_empty_oversized_writable_and_executable_payloads(self) -> None:
        mutations: tuple[tuple[str, Callable[[Path], object]], ...] = (
            ("missing", lambda path: path.unlink()),
            ("empty", lambda path: path.write_bytes(b"")),
            (
                "oversized",
                lambda path: path.write_bytes(bytes(freeze.MAX_SOURCE_MEMBER_BYTES + 1)),
            ),
            ("group-writable", lambda path: path.chmod(0o664)),
            ("world-writable", lambda path: path.chmod(0o646)),
            ("executable", lambda path: path.chmod(0o744)),
        )
        for name, mutation in mutations:
            with self.subTest(name=name), safe_source_tree() as source_root:
                target = source_root / "LICENSE"
                mutation(target)
                self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)

    def test_rejects_symlink_hardlink_fifo_and_directory_payloads_without_blocking(self) -> None:
        with safe_source_tree() as source_root:
            target = source_root / "LICENSE"
            target.unlink()
            target.symlink_to(source_root / "src/indusbench/__init__.py")
            self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)
        with safe_source_tree() as source_root:
            target = source_root / "LICENSE"
            sibling = source_root / "LICENSE.hardlink"
            os.link(target, sibling)
            self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)
        if hasattr(os, "mkfifo"):
            with safe_source_tree() as source_root:
                target = source_root / "LICENSE"
                target.unlink()
                os.mkfifo(target, 0o600)
                self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)
        with safe_source_tree() as source_root:
            target = source_root / "LICENSE"
            target.unlink()
            target.mkdir(mode=0o700)
            self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)

    def test_rejects_symlinked_or_writable_source_ancestry(self) -> None:
        with safe_source_tree() as source_root:
            source_root.chmod(0o770)
            self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)
        with safe_source_tree() as source_root:
            alias = source_root.parent / "alias"
            alias.symlink_to(source_root, target_is_directory=True)
            with (
                mock.patch.object(freeze, "_SOURCE_ROOT", alias),
                mock.patch.object(
                    freeze,
                    "_MODULE_PATH",
                    alias / freeze._MODULE_RELATIVE_PATH,
                ),
                self.assertRaises(freeze.KP1979V3ControlFreezeError) as caught,
            ):
                freeze.build_control_bundle(source_commit=SOURCE_COMMIT)
            self.assertEqual(freeze.ControlFreezeErrorCode.UNSAFE_SOURCE, caught.exception.code)

    def test_source_root_interrupt_closes_opened_ancestry_descriptors(self) -> None:
        with safe_source_tree() as source_root:
            module_path = source_root / freeze._MODULE_RELATIVE_PATH
            real_open = os.open
            real_fstat = os.fstat
            real_close = os.close
            opened: list[int] = []
            fstat_calls = 0
            interrupt = KeyboardInterrupt()

            def record_open(
                path: str,
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
                opened.append(descriptor)
                return descriptor

            def interrupt_second_fstat(descriptor: int) -> os.stat_result:
                nonlocal fstat_calls
                if descriptor in opened:
                    fstat_calls += 1
                    if fstat_calls == 2:
                        raise interrupt
                return real_fstat(descriptor)

            with (
                mock.patch.object(freeze, "_SOURCE_ROOT", source_root),
                mock.patch.object(freeze, "_MODULE_PATH", module_path),
                mock.patch.object(freeze.os, "open", side_effect=record_open),
                mock.patch.object(
                    freeze.os,
                    "fstat",
                    side_effect=interrupt_second_fstat,
                ),
                mock.patch.object(
                    freeze.os,
                    "close",
                    wraps=real_close,
                ) as close,
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze._open_source_root()
            self.assertIs(interrupt, caught.exception)
            self.assertEqual(2, len(opened))
            self.assertEqual(
                [mock.call(opened[1]), mock.call(opened[0])],
                close.call_args_list,
            )

    def test_rejects_forbidden_controller_detector_integration_or_runner_source(self) -> None:
        for relative in freeze._FORBIDDEN_SOURCE_COMPONENTS:
            with self.subTest(relative=relative), safe_source_tree() as source_root:
                path = source_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.parent.chmod(0o755)
                path.write_text("raise AssertionError\n", encoding="utf-8")
                path.chmod(0o644)
                self.assert_source_error(source_root, freeze.ControlFreezeErrorCode.UNSAFE_SOURCE)

    def test_ignores_unallowlisted_extra_file_and_never_places_it_in_bundle(self) -> None:
        with safe_source_tree() as source_root:
            extra = source_root / "src/indusbench/_vendor/noble/extra.js"
            extra.write_text("throw new Error();\n", encoding="utf-8")
            extra.chmod(0o644)
            subject = build_from(source_root)
        _tar_bytes, members = decode_subject(subject)
        self.assertNotIn("src/indusbench/_vendor/noble/extra.js", members)
        noble_members = [
            path for path in members if path.startswith("src/indusbench/_vendor/noble/")
        ]
        self.assertEqual(20, len(noble_members))

    def test_child_directory_failures_close_every_new_descriptor(self) -> None:
        with safe_source_tree() as source_root:
            real_open = os.open
            real_fstat = os.fstat
            real_close = os.close
            root_descriptor = real_open(source_root, freeze._directory_flags())
            opened: list[int] = []

            def record_open(
                path: str,
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                descriptor = real_open(
                    path,
                    flags,
                    mode,
                    dir_fd=dir_fd,
                )
                opened.append(descriptor)
                return descriptor

            def fail_new_descriptor(descriptor: int) -> os.stat_result:
                if descriptor in opened:
                    raise OSError
                return real_fstat(descriptor)

            try:
                for helper_name in ("open_child", "relative_exists"):
                    with self.subTest(helper_name=helper_name):
                        opened.clear()

                        with (
                            mock.patch.object(
                                freeze.os,
                                "open",
                                side_effect=record_open,
                            ),
                            mock.patch.object(
                                freeze.os,
                                "fstat",
                                side_effect=fail_new_descriptor,
                            ),
                            mock.patch.object(
                                freeze.os,
                                "close",
                                wraps=real_close,
                            ) as close,
                            self.assertRaises(
                                freeze.KP1979V3ControlFreezeError,
                            ) as caught,
                        ):
                            if helper_name == "open_child":
                                freeze._open_source_child_directory(
                                    root_descriptor,
                                    "src",
                                )
                            else:
                                freeze._relative_source_component_exists(
                                    root_descriptor,
                                    "src/indusbench",
                                )
                        self.assertEqual(
                            freeze.ControlFreezeErrorCode.UNSAFE_SOURCE,
                            caught.exception.code,
                        )
                        self.assertEqual(1, len(opened))
                        self.assertIn(mock.call(opened[0]), close.call_args_list)

                unsafe = source_root / "unsafe"
                unsafe.mkdir(mode=0o770)
                unsafe.chmod(0o770)
                opened = []

                def record_unsafe_open(
                    path: str,
                    flags: int,
                    mode: int = 0o777,
                    *,
                    dir_fd: int | None = None,
                ) -> int:
                    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
                    opened.append(descriptor)
                    return descriptor

                with (
                    mock.patch.object(freeze.os, "open", side_effect=record_unsafe_open),
                    mock.patch.object(freeze.os, "close", wraps=real_close) as close,
                    self.assertRaises(freeze.KP1979V3ControlFreezeError),
                ):
                    freeze._open_source_child_directory(root_descriptor, "unsafe")
                self.assertEqual(1, len(opened))
                self.assertIn(mock.call(opened[0]), close.call_args_list)
            finally:
                real_close(root_descriptor)

    def test_detects_file_fingerprint_mutation(self) -> None:
        with safe_source_tree() as source_root:
            real_fingerprint = freeze._stat_fingerprint
            regular_calls = 0

            def changed_fingerprint(value: os.stat_result) -> tuple[int, ...]:
                nonlocal regular_calls
                fingerprint = real_fingerprint(value)
                if stat.S_ISREG(value.st_mode):
                    regular_calls += 1
                    if regular_calls == 2:
                        return (*fingerprint[:-1], fingerprint[-1] + 1)
                return fingerprint

            with mock.patch.object(freeze, "_stat_fingerprint", changed_fingerprint):
                self.assert_source_error(
                    source_root,
                    freeze.ControlFreezeErrorCode.SOURCE_CHANGED,
                )

    def test_detects_deep_directory_and_leaf_namespace_replacement(self) -> None:
        real_stat = os.stat

        def changed_inode(value: os.stat_result) -> os.stat_result:
            return os.stat_result(
                (
                    value.st_mode,
                    value.st_ino + 1,
                    value.st_dev,
                    value.st_nlink,
                    value.st_uid,
                    value.st_gid,
                    value.st_size,
                    value.st_atime,
                    value.st_mtime,
                    value.st_ctime,
                )
            )

        for replaced_name in ("node_modules", "bls12-381.js"):
            with self.subTest(replaced_name=replaced_name), safe_source_tree() as source_root:

                def replace_namespace(
                    path: str | bytes | os.PathLike[str] | os.PathLike[bytes] | int,
                    *,
                    dir_fd: int | None = None,
                    follow_symlinks: bool = True,
                    _replaced_name: str = replaced_name,
                ) -> os.stat_result:
                    value = real_stat(
                        path,
                        dir_fd=dir_fd,
                        follow_symlinks=follow_symlinks,
                    )
                    if path == _replaced_name and dir_fd is not None and not follow_symlinks:
                        return changed_inode(value)
                    return value

                with mock.patch.object(freeze.os, "stat", side_effect=replace_namespace):
                    self.assert_source_error(
                        source_root,
                        freeze.ControlFreezeErrorCode.SOURCE_CHANGED,
                    )

    def test_detects_source_root_namespace_replacement_during_read(self) -> None:
        with safe_source_tree() as source_root:
            moved = source_root.parent / "moved"
            real_read = freeze._read_source_member
            changed = False

            def replace_root(descriptor: int, path: str) -> bytes:
                nonlocal changed
                raw = real_read(descriptor, path)
                if not changed:
                    changed = True
                    source_root.rename(moved)
                    source_root.mkdir(mode=0o700)
                return raw

            with mock.patch.object(freeze, "_read_source_member", replace_root):
                self.assert_source_error(
                    source_root,
                    freeze.ControlFreezeErrorCode.SOURCE_CHANGED,
                )

    def test_detects_forbidden_module_created_during_final_source_read(self) -> None:
        with safe_source_tree() as source_root:
            real_read = freeze._read_source_member
            final_path = freeze.PAYLOAD_PATHS[-1]

            def insert_forbidden(descriptor: int, path: str) -> bytes:
                raw = real_read(descriptor, path)
                if path == final_path:
                    forbidden = source_root / freeze._FORBIDDEN_SOURCE_COMPONENTS[0]
                    forbidden.write_text("raise AssertionError\n", encoding="utf-8")
                    forbidden.chmod(0o644)
                return raw

            with mock.patch.object(freeze, "_read_source_member", insert_forbidden):
                self.assert_source_error(
                    source_root,
                    freeze.ControlFreezeErrorCode.SOURCE_CHANGED,
                )


@contextmanager
def safe_output_parent() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="indus-control-freeze-output-") as raw:
        parent = Path(raw)
        parent.chmod(0o700)
        yield parent


class ControlFreezeOutputSafetyTests(unittest.TestCase):
    def assert_output_error(
        self,
        path: Path,
        expected: freeze.ControlFreezeErrorCode,
        subject: bytes = b"subject",
    ) -> None:
        with self.assertRaises(freeze.KP1979V3ControlFreezeError) as caught:
            freeze._write_subject_no_replace(path, subject)
        self.assertEqual(expected, caught.exception.code)
        self.assertEqual(expected.value, str(caught.exception))

    def test_writes_exact_regular_0600_nlink1_and_syncs_file_and_parent(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            with mock.patch.object(freeze.os, "fsync", wraps=os.fsync) as sync:
                freeze._write_subject_no_replace(output, b"subject")
            value = output.lstat()
            self.assertTrue(stat.S_ISREG(value.st_mode))
            self.assertEqual(0o600, stat.S_IMODE(value.st_mode))
            self.assertEqual(os.geteuid(), value.st_uid)
            self.assertEqual(1, value.st_nlink)
            self.assertEqual(b"subject", output.read_bytes())
            self.assertGreaterEqual(sync.call_count, 2)

    def test_output_is_identical_across_extreme_umasks(self) -> None:
        previous_umask = os.umask(0)
        try:
            with safe_output_parent() as first_parent:
                first = first_parent / freeze.SUBJECT_NAME
                freeze._write_subject_no_replace(first, b"subject")
                first_bytes = first.read_bytes()
                first_mode = stat.S_IMODE(first.stat().st_mode)
            os.umask(0o777)
            with safe_output_parent() as second_parent:
                second = second_parent / freeze.SUBJECT_NAME
                freeze._write_subject_no_replace(second, b"subject")
                second_bytes = second.read_bytes()
                second_mode = stat.S_IMODE(second.stat().st_mode)
        finally:
            os.umask(previous_umask)
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual((0o600, 0o600), (first_mode, second_mode))

    def test_rejects_existing_regular_symlink_hardlink_fifo_and_directory(self) -> None:
        creators: list[tuple[str, Callable[[Path, Path], object]]] = [
            ("regular", lambda output, _parent: output.write_bytes(b"preserve")),
            (
                "symlink",
                lambda output, parent: output.symlink_to(parent / "target"),
            ),
            (
                "directory",
                lambda output, _parent: output.mkdir(mode=0o700),
            ),
        ]
        if hasattr(os, "mkfifo"):
            creators.append(("fifo", lambda output, _parent: os.mkfifo(output, 0o600)))
        for name, create in creators:
            with self.subTest(name=name), safe_output_parent() as parent:
                output = parent / freeze.SUBJECT_NAME
                create(output, parent)
                before = output.lstat()
                self.assert_output_error(output, freeze.ControlFreezeErrorCode.OUTPUT_EXISTS)
                after = output.lstat()
                self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            source = parent / "source"
            source.write_bytes(b"preserve")
            os.link(source, output)
            self.assert_output_error(output, freeze.ControlFreezeErrorCode.OUTPUT_EXISTS)
            self.assertEqual(b"preserve", output.read_bytes())

    def test_rejects_wrong_basename_relative_missing_writable_and_symlink_parent(self) -> None:
        with safe_output_parent() as parent:
            invalid_paths = (
                parent / "wrong.tar.gz",
                Path(freeze.SUBJECT_NAME),
                parent / "missing" / freeze.SUBJECT_NAME,
            )
            for path in invalid_paths:
                with (
                    self.subTest(path=path),
                    self.assertRaises(freeze.KP1979V3ControlFreezeError),
                ):
                    validated = freeze._validated_output_path(str(path))
                    freeze._write_subject_no_replace(validated, b"subject")
        with safe_output_parent() as parent:
            parent.chmod(0o750)
            output = parent / freeze.SUBJECT_NAME
            self.assert_output_error(output, freeze.ControlFreezeErrorCode.UNSAFE_OUTPUT)
        with safe_output_parent() as parent:
            physical = parent / "physical"
            physical.mkdir(mode=0o700)
            alias = parent / "alias"
            alias.symlink_to(physical, target_is_directory=True)
            output = alias / freeze.SUBJECT_NAME
            self.assert_output_error(output, freeze.ControlFreezeErrorCode.UNSAFE_OUTPUT)

    def test_output_parent_interrupt_closes_opened_ancestry_descriptors(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            real_open = os.open
            real_fstat = os.fstat
            real_close = os.close
            opened: list[int] = []
            fstat_calls = 0
            interrupt = KeyboardInterrupt()

            def record_open(
                path: str,
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
                opened.append(descriptor)
                return descriptor

            def interrupt_second_fstat(descriptor: int) -> os.stat_result:
                nonlocal fstat_calls
                if descriptor in opened:
                    fstat_calls += 1
                    if fstat_calls == 2:
                        raise interrupt
                return real_fstat(descriptor)

            with (
                mock.patch.object(freeze.os, "open", side_effect=record_open),
                mock.patch.object(
                    freeze.os,
                    "fstat",
                    side_effect=interrupt_second_fstat,
                ),
                mock.patch.object(
                    freeze.os,
                    "close",
                    wraps=real_close,
                ) as close,
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze._open_output_parent(output)
            self.assertIs(interrupt, caught.exception)
            self.assertEqual(2, len(opened))
            self.assertEqual(
                [mock.call(opened[1]), mock.call(opened[0])],
                close.call_args_list,
            )

    def test_destination_insertion_race_is_no_replace_and_preserves_racer(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            real_link = os.link

            def insert_then_link(
                source: str,
                destination: str,
                *,
                src_dir_fd: int | None = None,
                dst_dir_fd: int | None = None,
                follow_symlinks: bool = True,
            ) -> None:
                assert isinstance(dst_dir_fd, int)
                descriptor = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=dst_dir_fd,
                )
                os.write(descriptor, b"racer")
                os.close(descriptor)
                real_link(
                    source,
                    destination,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                    follow_symlinks=follow_symlinks,
                )

            with mock.patch.object(freeze.os, "link", side_effect=insert_then_link):
                self.assert_output_error(output, freeze.ControlFreezeErrorCode.OUTPUT_EXISTS)
            self.assertEqual(b"racer", output.read_bytes())
            self.assertEqual([freeze.SUBJECT_NAME], [path.name for path in parent.iterdir()])

    def test_partial_writes_are_completed_and_zero_write_fails_cleanly(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            real_write = os.write

            def partial_write(descriptor: int, raw: bytes) -> int:
                return real_write(descriptor, raw[:3])

            with mock.patch.object(freeze.os, "write", side_effect=partial_write):
                freeze._write_subject_no_replace(output, b"long-subject")
            self.assertEqual(b"long-subject", output.read_bytes())
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            with mock.patch.object(freeze.os, "write", return_value=0):
                self.assert_output_error(
                    output,
                    freeze.ControlFreezeErrorCode.OUTPUT_WRITE_FAILED,
                )
            self.assertEqual([], list(parent.iterdir()))

    def test_fchmod_fsync_link_failures_and_interrupt_cleanup_are_bounded(self) -> None:
        failures = (
            ("fchmod", mock.patch.object(freeze.os, "fchmod", side_effect=OSError())),
            ("fsync", mock.patch.object(freeze.os, "fsync", side_effect=OSError())),
            ("link", mock.patch.object(freeze.os, "link", side_effect=OSError())),
        )
        for name, patcher in failures:
            with self.subTest(name=name), safe_output_parent() as parent, patcher:
                output = parent / freeze.SUBJECT_NAME
                self.assert_output_error(
                    output,
                    freeze.ControlFreezeErrorCode.OUTPUT_WRITE_FAILED,
                )
                self.assertEqual([], list(parent.iterdir()))
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            interrupt = KeyboardInterrupt()
            with (
                mock.patch.object(freeze.os, "write", side_effect=interrupt),
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze._write_subject_no_replace(output, b"subject")
            self.assertIs(interrupt, caught.exception)
            self.assertEqual([], list(parent.iterdir()))

        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            real_link = os.link
            interrupt = KeyboardInterrupt()

            def link_then_interrupt(
                source: str,
                destination: str,
                *,
                src_dir_fd: int | None = None,
                dst_dir_fd: int | None = None,
                follow_symlinks: bool = True,
            ) -> None:
                real_link(
                    source,
                    destination,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                    follow_symlinks=follow_symlinks,
                )
                raise interrupt

            with (
                mock.patch.object(
                    freeze.os,
                    "link",
                    side_effect=link_then_interrupt,
                ),
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze._write_subject_no_replace(output, b"subject")
            self.assertIs(interrupt, caught.exception)
            self.assertEqual([], list(parent.iterdir()))

    def test_verify_read_rejects_leaf_replacement_and_preserves_unknown(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            real_read = os.read
            replaced = False

            def replace_after_read(descriptor: int, size: int) -> bytes:
                nonlocal replaced
                raw = real_read(descriptor, size)
                if raw and not replaced:
                    replaced = True
                    output.unlink()
                    output.write_bytes(b"racer")
                    output.chmod(0o600)
                return raw

            with mock.patch.object(
                freeze.os,
                "read",
                side_effect=replace_after_read,
            ):
                self.assert_output_error(
                    output,
                    freeze.ControlFreezeErrorCode.OUTPUT_WRITE_FAILED,
                )
            self.assertTrue(replaced)
            self.assertEqual(b"racer", output.read_bytes())
            self.assertEqual(
                [freeze.SUBJECT_NAME],
                [path.name for path in parent.iterdir()],
            )

    def test_post_link_failure_removes_only_the_owned_output_inode(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            interrupt = KeyboardInterrupt()
            with (
                mock.patch.object(
                    freeze,
                    "_verify_written_output",
                    side_effect=interrupt,
                ),
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze._write_subject_no_replace(output, b"subject")
            self.assertIs(interrupt, caught.exception)
            self.assertEqual([], list(parent.iterdir()))

        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            interrupt = KeyboardInterrupt()

            def replace_with_unknown(
                parent_descriptor: int,
                _expected: bytes,
                _expected_identity: tuple[int, int],
            ) -> None:
                os.unlink(freeze.SUBJECT_NAME, dir_fd=parent_descriptor)
                descriptor = os.open(
                    freeze.SUBJECT_NAME,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=parent_descriptor,
                )
                try:
                    os.write(descriptor, b"racer")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                raise interrupt

            with (
                mock.patch.object(
                    freeze,
                    "_verify_written_output",
                    side_effect=replace_with_unknown,
                ),
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze._write_subject_no_replace(output, b"subject")
            self.assertIs(interrupt, caught.exception)
            self.assertEqual(b"racer", output.read_bytes())
            self.assertEqual([freeze.SUBJECT_NAME], [path.name for path in parent.iterdir()])

    def test_parent_namespace_replacement_fails_closed(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            moved = parent.parent / f"{parent.name}.moved"
            real_write_all = freeze._write_all

            def replace_parent(descriptor: int, raw: bytes) -> None:
                real_write_all(descriptor, raw)
                parent.rename(moved)
                parent.mkdir(mode=0o700)

            with mock.patch.object(freeze, "_write_all", side_effect=replace_parent):
                self.assert_output_error(output, freeze.ControlFreezeErrorCode.UNSAFE_OUTPUT)

    def test_two_concurrent_builders_have_exactly_one_success(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            barrier = threading.Barrier(2)

            def write_once() -> str:
                barrier.wait()
                try:
                    freeze._write_subject_no_replace(output, b"subject")
                except freeze.KP1979V3ControlFreezeError as error:
                    return error.code.value
                return "success"

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _index: write_once(), range(2)))
            self.assertEqual(["output_exists", "success"], sorted(results))
            self.assertEqual(b"subject", output.read_bytes())


def fake_runtime(values: list[str]) -> SimpleNamespace:
    executable = "/opt/kp1979-v3/bin/python"
    return SimpleNamespace(
        argv=[freeze._MODULE_NAME, *values],
        dont_write_bytecode=True,
        executable=executable,
        flags=SimpleNamespace(dont_write_bytecode=1, no_user_site=1),
        implementation=SimpleNamespace(name="cpython"),
        orig_argv=[executable, "-s", "-B", "-m", freeze._MODULE_NAME, *values],
        version_info=(3, 12, 11),
    )


def closed_environment() -> dict[str, str]:
    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/opt/kp1979-v3/bin:/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "SOURCE_COMMIT": SOURCE_COMMIT,
        "SOURCE_DATE_EPOCH": "0",
        "TZ": "UTC",
    }


class ControlFreezeCLITests(unittest.TestCase):
    def test_closed_environment_accepts_only_exact_runtime_and_eight_keys(self) -> None:
        values = ["--output", f"/tmp/safe/{freeze.SUBJECT_NAME}"]
        runtime = fake_runtime(values)
        with (
            mock.patch.object(freeze, "sys", runtime),
            mock.patch.dict(
                os.environ,
                closed_environment(),
                clear=True,
            ),
        ):
            self.assertEqual(SOURCE_COMMIT, freeze._freeze_environment_source_commit())
            self.assertEqual(Path(values[1]), freeze._parse_cli_output(values))

        variants: list[dict[str, str]] = []
        for key in closed_environment():
            missing = closed_environment()
            missing.pop(key)
            variants.append(missing)
        wrong = closed_environment()
        wrong["PATH"] = "/usr/bin:/bin"
        variants.append(wrong)
        extra = closed_environment()
        extra["PYTHONPATH"] = "/tmp"
        variants.append(extra)
        for environment in variants:
            with (
                self.subTest(environment=environment),
                mock.patch.object(freeze, "sys", runtime),
                mock.patch.dict(os.environ, environment, clear=True),
                self.assertRaises(freeze.KP1979V3ControlFreezeError) as caught,
            ):
                freeze._freeze_environment_source_commit()
            self.assertEqual(
                freeze.ControlFreezeErrorCode.INVALID_ENVIRONMENT,
                caught.exception.code,
            )

    def test_rejects_wrong_runtime_flags_version_implementation_and_invocation(self) -> None:
        values = ["--output", f"/tmp/safe/{freeze.SUBJECT_NAME}"]
        runtime_mutations = (
            ("implementation", "name", "pypy"),
            ("flags", "no_user_site", 0),
            ("flags", "dont_write_bytecode", 0),
        )
        for container_name, attribute, replacement in runtime_mutations:
            runtime = fake_runtime(values)
            setattr(getattr(runtime, container_name), attribute, replacement)
            with (
                self.subTest(attribute=attribute),
                mock.patch.object(freeze, "sys", runtime),
                mock.patch.dict(os.environ, closed_environment(), clear=True),
                self.assertRaises(freeze.KP1979V3ControlFreezeError),
            ):
                freeze._freeze_environment_source_commit()
        runtime = fake_runtime(values)
        runtime.version_info = (3, 12, 10)
        with (
            mock.patch.object(freeze, "sys", runtime),
            mock.patch.dict(os.environ, closed_environment(), clear=True),
            self.assertRaises(freeze.KP1979V3ControlFreezeError),
        ):
            freeze._freeze_environment_source_commit()
        bad_invocations = (
            [runtime.executable, "-B", "-m", freeze._MODULE_NAME, *values],
            [runtime.executable, "-sB", "-m", freeze._MODULE_NAME, *values],
            [runtime.executable, "-B", "-s", "-m", freeze._MODULE_NAME, *values],
            [runtime.executable, "-s", "-B", "-I", "-m", freeze._MODULE_NAME, *values],
            [runtime.executable, "-s", "-B", "-m", "wrong", *values],
        )
        for invocation in bad_invocations:
            changed = fake_runtime(values)
            changed.orig_argv = invocation
            with (
                self.subTest(invocation=invocation),
                mock.patch.object(freeze, "sys", changed),
                self.assertRaises(freeze.KP1979V3ControlFreezeError),
            ):
                freeze._parse_cli_output(values)

    def test_main_success_is_silent_exact_and_no_replace(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            values = ["--output", str(output)]
            runtime = fake_runtime(values)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(freeze, "sys", runtime),
                mock.patch.dict(os.environ, closed_environment(), clear=True),
                mock.patch.object(freeze, "build_control_bundle", return_value=b"subject"),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                self.assertEqual(0, freeze.main(values))
            self.assertEqual("", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())
            self.assertEqual(b"subject", output.read_bytes())
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))

    def test_main_collapses_unexpected_exception_but_propagates_baseexception(self) -> None:
        with safe_output_parent() as parent:
            output = parent / freeze.SUBJECT_NAME
            values = ["--output", str(output)]
            runtime = fake_runtime(values)
            for error, expected_return in ((RuntimeError("detail"), 2),):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with (
                    mock.patch.object(freeze, "sys", runtime),
                    mock.patch.dict(os.environ, closed_environment(), clear=True),
                    mock.patch.object(freeze, "build_control_bundle", side_effect=error),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    self.assertEqual(expected_return, freeze.main(values))
                self.assertEqual(("", ""), (stdout.getvalue(), stderr.getvalue()))
            interrupt = KeyboardInterrupt()
            with (
                mock.patch.object(freeze, "sys", runtime),
                mock.patch.dict(os.environ, closed_environment(), clear=True),
                mock.patch.object(freeze, "build_control_bundle", side_effect=interrupt),
                self.assertRaises(KeyboardInterrupt) as caught,
            ):
                freeze.main(values)
            self.assertIs(interrupt, caught.exception)

    def test_cli_rejects_unknown_duplicate_positional_relative_and_wrong_basename(self) -> None:
        candidates = (
            [],
            ["--help"],
            ["--output"],
            ["--output", "/tmp/other"],
            ["--output", freeze.SUBJECT_NAME],
            ["--output", "/tmp/safe/../" + freeze.SUBJECT_NAME],
            ["--output", f"/tmp/safe/{freeze.SUBJECT_NAME}", "extra"],
            ["--output", f"/tmp/safe/{freeze.SUBJECT_NAME}", "--output"],
            ["--seed", "x", "--output", f"/tmp/safe/{freeze.SUBJECT_NAME}"],
            ["--round", "1", "--output", f"/tmp/safe/{freeze.SUBJECT_NAME}"],
        )
        for values in candidates:
            runtime = fake_runtime(values)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                self.subTest(values=values),
                mock.patch.object(freeze, "sys", runtime),
                mock.patch.dict(os.environ, closed_environment(), clear=True),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                self.assertEqual(2, freeze.main(values))
            self.assertEqual(("", ""), (stdout.getvalue(), stderr.getvalue()))


class ControlFreezeArchitectureTests(unittest.TestCase):
    def test_explicit_public_api_is_exact_and_minimal(self) -> None:
        expected = (
            "PAYLOAD_PATHS",
            "SUBJECT_NAME",
            "ControlFreezeErrorCode",
            "KP1979V3ControlFreezeError",
            "VerifiedControlBundle",
            "build_control_bundle",
            "main",
            "verify_control_bundle",
        )
        self.assertEqual(expected, freeze.__all__)
        for name in expected:
            self.assertTrue(hasattr(freeze, name))
        self.assertTrue(
            {
                "Path",
                "hashlib",
                "json",
                "os",
                "secrets",
                "stat",
                "sys",
            }.isdisjoint(freeze.__all__)
        )

    def test_public_api_signatures_have_no_operational_injection_surface(self) -> None:
        signatures = {
            "build": inspect.signature(freeze.build_control_bundle),
            "verify": inspect.signature(freeze.verify_control_bundle),
            "main": inspect.signature(freeze.main),
        }
        self.assertEqual(["source_commit"], list(signatures["build"].parameters))
        self.assertEqual(
            ["subject", "expected_source_commit"],
            list(signatures["verify"].parameters),
        )
        self.assertEqual(["argv"], list(signatures["main"].parameters))
        forbidden = {
            "root",
            "seed",
            "round",
            "target",
            "invoker",
            "factory",
            "detector",
            "runtime",
            "oracle",
            "schedule",
        }
        for signature in signatures.values():
            for parameter in signature.parameters:
                self.assertTrue(forbidden.isdisjoint(parameter.lower().split("_")))

    def test_builder_ast_has_only_closed_stdlib_imports_and_no_execution_calls(self) -> None:
        source = (ROOT / freeze._MODULE_RELATIVE_PATH).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        call_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    call_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    call_names.add(node.func.attr)
        self.assertEqual(
            {
                "__future__",
                "binascii",
                "collections.abc",
                "contextlib",
                "dataclasses",
                "enum",
                "hashlib",
                "json",
                "os",
                "pathlib",
                "secrets",
                "stat",
                "sys",
                "typing",
            },
            imports,
        )
        self.assertTrue(
            {
                "eval",
                "exec",
                "glob",
                "listdir",
                "walk",
                "run_module",
                "Popen",
                "run",
                "call",
                "system",
                "iter_schedule",
                "derive_official_seed",
                "verify_quicknet_beacon",
                "evaluate_c3_suite",
                "execute_one_shot",
            }.isdisjoint(call_names)
        )
        for forbidden_import in (
            "gzip",
            "tarfile",
            "zlib",
            "subprocess",
            "socket",
            "importlib",
            "runpy",
            "urllib",
        ):
            self.assertNotIn(forbidden_import, imports)

    def test_package_init_is_exact_side_effect_free_prefix(self) -> None:
        self.assertEqual(
            (
                '"""Open, rights-aware benchmark tooling for Indus inscription research."""\n'
                "\n"
                '__version__ = "0.1.0"\n'
            ),
            (ROOT / "src/indusbench/__init__.py").read_text(encoding="utf-8"),
        )

    def test_build_never_calls_generator_seed_quicknet_evaluator_sandbox_or_state(self) -> None:
        from indusbench import kp1979_v3_evaluator as evaluator
        from indusbench import kp1979_v3_generator as generator
        from indusbench import kp1979_v3_prf as prf
        from indusbench import kp1979_v3_quicknet as quicknet
        from indusbench import kp1979_v3_sandbox as sandbox
        from indusbench import kp1979_v3_state as state

        trap = AssertionError("operational function called")
        with (
            safe_source_tree() as source_root,
            mock.patch.object(generator, "iter_schedule", side_effect=trap),
            mock.patch.object(prf, "derive_official_seed", side_effect=trap),
            mock.patch.object(quicknet, "verify_quicknet_beacon", side_effect=trap),
            mock.patch.object(evaluator, "evaluate_c3_suite", side_effect=trap),
            mock.patch.object(sandbox.SandboxedWorkerInvoker, "__call__", side_effect=trap),
            mock.patch.object(state, "execute_one_shot", side_effect=trap),
        ):
            subject = build_from(source_root)
        summary = freeze.verify_control_bundle(
            subject,
            expected_source_commit=SOURCE_COMMIT,
        )
        self.assertEqual(37, summary.member_count)

    def test_detector_and_integration_modules_remain_absent(self) -> None:
        for module_name in (
            "indusbench.kp1979_v3_controller",
            "indusbench.kp1979_v3_detector",
            "indusbench.kp1979_v3_detector_freeze",
            "indusbench.kp1979_v3_integration",
            "indusbench.kp1979_v3_integration_freeze",
            "indusbench.kp1979_v3_runner",
        ):
            with self.subTest(module_name=module_name):
                self.assertIsNone(importlib.util.find_spec(module_name))

    def test_workflow_mapping_and_published_workflow_bytes_are_unchanged(self) -> None:
        core = ROOT / ".github/workflows/kp1979-v3-freeze-core.yml"
        caller = ROOT / ".github/workflows/kp1979-v3-freeze.yml"
        core_raw = core.read_bytes()
        caller_raw = caller.read_bytes()
        self.assertEqual(CORE_WORKFLOW_SHA256, hashlib.sha256(core_raw).hexdigest())
        self.assertEqual(CALLER_WORKFLOW_SHA256, hashlib.sha256(caller_raw).hexdigest())
        core_text = core_raw.decode("utf-8")
        self.assertIn("module=indusbench.kp1979_v3_control_freeze", core_text)
        self.assertIn("module=indusbench.kp1979_v3_detector_freeze", core_text)
        self.assertIn("module=indusbench.kp1979_v3_integration_freeze", core_text)
        self.assertIn('"3.12.11"', core_text)
        self.assertIn('python" -s -B -m "$module"', core_text)
        self.assertNotIn("schedule:", caller_raw.decode("utf-8"))

    def test_verifier_rejects_nonbytes_and_invalid_commit_arguments(self) -> None:
        for subject in (bytearray(b"x"), memoryview(b"x"), "x", None):
            with (
                self.subTest(subject=subject),
                self.assertRaises(freeze.KP1979V3ControlFreezeError),
            ):
                freeze.verify_control_bundle(subject, expected_source_commit=SOURCE_COMMIT)  # type: ignore[arg-type]
        for commit in ("A" * 40, "a" * 39, "g" * 40, True, None):
            with (
                self.subTest(commit=commit),
                self.assertRaises(freeze.KP1979V3ControlFreezeError) as caught,
            ):
                freeze.build_control_bundle(source_commit=commit)  # type: ignore[arg-type]
            self.assertEqual(freeze.ControlFreezeErrorCode.INVALID_ARGUMENT, caught.exception.code)


class ControlFreezeAdditionalSourceTypesTests(unittest.TestCase):
    def test_rejects_intermediate_symlink_broken_symlink_and_unix_socket(self) -> None:
        with safe_source_tree() as source_root:
            schemas = source_root / "schemas"
            moved = source_root / "schemas-real"
            schemas.rename(moved)
            schemas.symlink_to(moved, target_is_directory=True)
            with self.assertRaises(freeze.KP1979V3ControlFreezeError):
                build_from(source_root)
        with safe_source_tree() as source_root:
            target = source_root / "LICENSE"
            target.unlink()
            target.symlink_to(source_root / "missing")
            with self.assertRaises(freeze.KP1979V3ControlFreezeError):
                build_from(source_root)
        if hasattr(socket, "AF_UNIX"):
            with safe_source_tree() as source_root:
                target = source_root / "LICENSE"
                target.unlink()
                endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    endpoint.bind(str(target))
                    with self.assertRaises(freeze.KP1979V3ControlFreezeError):
                        build_from(source_root)
                finally:
                    endpoint.close()
