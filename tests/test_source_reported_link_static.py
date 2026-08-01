from __future__ import annotations

import copy
import http.client
import os
import shutil
import socket
import stat
import tempfile
import unittest
import urllib.request
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.source_reported_link_static as static_module
from indusbench.io import encode_json
from indusbench.source_reported_link_static import (
    SourceFreeStaticSnapshot,
    SourceLinkStaticError,
    SourceLinkStaticErrorCode,
    load_installed_source_link_static,
)

ROOT = Path(__file__).resolve().parents[1]
CANARY_SECRET = "STATIC_SECRET_7b19"

EXPECTED_RESOURCES = {
    "registry/chanhu-daro-helsinki-gate-v1.json": (
        6955,
        "43c0fae1a8558fbffeb062725e401e0c3c1de570e5f8f7eef610ca2616cbfb3d",
    ),
    "registry/sources.json": (
        43235,
        "e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584",
    ),
    "registry/source-reported-link-policy-v1.json": (
        7967,
        "c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90",
    ),
    "registry/source-reported-link-source-contract-v1.json": (
        29059,
        "e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f",
    ),
    "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json": (
        426824,
        "917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914",
    ),
    "schemas/context-source-link-gate.schema.json": (
        9216,
        "72109818eb55aca008b0f34b1d6c627efd0e38bdbaff8c500cb3c60dc74e3002",
    ),
    "schemas/source-registry.schema.json": (
        8295,
        "6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3",
    ),
    "schemas/source-reported-link-policy.schema.json": (
        8589,
        "d951541892bb6a5ef092d44e9a5564da2261f960e52e3e84a95ecd5ef8e61aff",
    ),
    "schemas/source-reported-link-source-contract.schema.json": (
        30752,
        "e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78",
    ),
    "schemas/source-reported-link-protected-ephemeral-custody-contract.schema.json": (
        440116,
        "5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b",
    ),
    "schemas/source-reported-link-source-revision-receipt.schema.json": (
        9316,
        "6d0451ed9471315b11689e6cabe8bf7b15e6b5d31f0064d5a364c9ac73789375",
    ),
    "schemas/source-reported-link-receipt-commitment-envelope.schema.json": (
        2546,
        "f4e316c5542c5ea9c57a91fc5006a10550c2dbbd08436e165d997e265570c2d4",
    ),
    "schemas/source-reported-link-source-revision-set.schema.json": (
        6459,
        "15d64ee72ea7a147bcde22a2c28330b67c1eae4d299e272296a53a2ef25d17bb",
    ),
    "schemas/source-reported-link-completeness-attestation.schema.json": (
        5627,
        "a8ae0f32fbda8cd1bb7e29db3d3444ec0659ffa9f9818ea85331288d0f018c02",
    ),
}

EXPECTED_SNAPSHOT = {
    "artifact_schema_set_sha256": (
        "sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f"
    ),
    "custody_contract_sha256": (
        "sha256:917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914"
    ),
    "ordered_source_roster_sha256": (
        "sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f"
    ),
    "source_contract_sha256": (
        "sha256:e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f"
    ),
    "source_policy_sha256": (
        "sha256:c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90"
    ),
    "source_registry_sha256": (
        "sha256:e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584"
    ),
}


def _copy_installed_layout(parent: Path) -> Path:
    package_root = parent / "indusbench"
    for directory in ("registry", "schemas"):
        (package_root / directory).mkdir(parents=True, exist_ok=True, mode=0o755)
    package_root.chmod(0o755)
    for relative_path in EXPECTED_RESOURCES:
        destination = package_root / relative_path
        shutil.copyfile(ROOT / relative_path, destination)
        destination.chmod(0o644)
    return package_root


def _decoded_values() -> dict[Any, Any]:
    return {
        spec.key: static_module._decode_static_resource(
            (ROOT / spec.package_path).read_bytes(),
            spec.key,
        )
        for spec in static_module._RESOURCE_SPECS
    }


class SourceReportedLinkStaticTests(unittest.TestCase):
    def _expect_error(
        self,
        code: SourceLinkStaticErrorCode,
        operation: Callable[[], object],
    ) -> SourceLinkStaticError:
        with self.assertRaises(SourceLinkStaticError) as caught:
            operation()
        error = caught.exception
        message = f"source_reported_link_static:{code.value}"
        self.assertIs(code, error.code)
        self.assertEqual(message, str(error))
        self.assertEqual((message,), error.args)
        self.assertEqual({"code"}, set(vars(error)))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        public_surface = "\n".join((str(error), repr(error), repr(error.args), repr(vars(error))))
        self.assertNotIn(CANARY_SECRET, public_surface)
        self.assertNotIn(tempfile.gettempdir(), public_surface)
        return error

    def test_exact_closed_resource_table_and_legacy_exception_are_frozen(self) -> None:
        observed = {
            spec.package_path: (spec.size, spec.sha256) for spec in static_module._RESOURCE_SPECS
        }
        self.assertEqual(EXPECTED_RESOURCES, observed)
        self.assertEqual(tuple(EXPECTED_RESOURCES), tuple(observed))
        self.assertEqual(14, len(static_module._RESOURCE_SPECS))
        self.assertEqual(14, len(static_module._SPEC_BY_KEY))
        self.assertEqual(1_034_956, sum(size for size, _ in observed.values()))
        self.assertEqual(
            {
                static_module._ResourceKey.SOURCE_REGISTRY,
                static_module._ResourceKey.SOURCE_REGISTRY_SCHEMA,
            },
            set(static_module._LEGACY_EXACT_BYTE_JSON_KEYS),
        )

    def test_each_of_the_exact_fourteen_resources_is_independently_pinned(self) -> None:
        for relative_path in EXPECTED_RESOURCES:
            with (
                self.subTest(relative_path=relative_path),
                tempfile.TemporaryDirectory() as raw_directory,
            ):
                package_root = _copy_installed_layout(Path(raw_directory))
                resource = package_root / relative_path
                raw = resource.read_bytes()
                resource.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_HASH_MISMATCH,
                    lambda package_root=package_root: (
                        static_module._load_source_link_static_from_root(package_root)
                    ),
                )

    def test_valid_layout_returns_only_the_six_static_identities(self) -> None:
        with tempfile.TemporaryDirectory(prefix=f"{CANARY_SECRET}-") as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            snapshot = static_module._load_source_link_static_from_root(package_root)

        self.assertIs(type(snapshot), SourceFreeStaticSnapshot)
        for field, expected in EXPECTED_SNAPSHOT.items():
            self.assertEqual(expected, getattr(snapshot, field))
        self.assertEqual(14, snapshot.resource_count)
        self.assertEqual(
            (
                "runtime_distribution_sha256",
                "transitive_runtime_input_manifest_sha256",
            ),
            snapshot.missing_binding_fields,
        )
        self.assertIs(False, snapshot.strict_v1_resolver_eligible)
        self.assertEqual(
            (
                "source_registry_noncanonical_raw_bytes",
                "source_registry_schema_noncanonical_raw_bytes",
            ),
            snapshot.strict_v1_resolver_blockers,
        )
        for absent in (
            "authority",
            "authorized",
            "source_access",
            "runtime_distribution_sha256",
            "transitive_runtime_input_manifest_sha256",
        ):
            self.assertFalse(hasattr(snapshot, absent))
        with self.assertRaises(FrozenInstanceError):
            cast(Any, snapshot).resource_count = 0
        rendered = repr(snapshot)
        self.assertNotIn("sha256:", rendered)
        self.assertNotIn(CANARY_SECRET, rendered)

    def test_snapshot_constructor_rejects_a_caller_token(self) -> None:
        self._expect_error(
            SourceLinkStaticErrorCode.INVALID_ARGUMENT_TYPE,
            lambda: SourceFreeStaticSnapshot(
                _token=object(),
                **EXPECTED_SNAPSHOT,
                missing_binding_fields=(
                    "runtime_distribution_sha256",
                    "transitive_runtime_input_manifest_sha256",
                ),
                resource_count=14,
            ),
        )

    def test_public_loader_rejects_source_checkout_and_nonfilesystem_traversable(self) -> None:
        with patch.object(
            static_module.importlib.resources,
            "files",
            return_value=ROOT / "src" / "indusbench",
        ):
            self._expect_error(
                SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID,
                load_installed_source_link_static,
            )
        with patch.object(
            static_module.importlib.resources,
            "files",
            return_value=object(),
        ):
            self._expect_error(
                SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED,
                load_installed_source_link_static,
            )

    def test_hash_size_mode_link_and_fifo_boundaries_fail_closed(self) -> None:
        first_relative = next(iter(EXPECTED_RESOURCES))

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            resource = package_root / first_relative
            raw = resource.read_bytes()
            resource.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_HASH_MISMATCH,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            resource = package_root / first_relative
            resource.write_bytes(resource.read_bytes() + b"x")
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            resource = package_root / first_relative
            resource.chmod(0o744)
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            resource = package_root / first_relative
            os.link(resource, parent / "hardlink")
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

        if hasattr(os, "mkfifo"):
            with tempfile.TemporaryDirectory() as raw_directory:
                package_root = _copy_installed_layout(Path(raw_directory))
                resource = package_root / first_relative
                resource.unlink()
                os.mkfifo(resource, mode=0o600)
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                    lambda: static_module._load_source_link_static_from_root(package_root),
                )

    def test_root_directory_and_resource_symlinks_fail_closed(self) -> None:
        first_relative = next(iter(EXPECTED_RESOURCES))
        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            real_root = parent / "real-indusbench"
            package_root.rename(real_root)
            package_root.symlink_to(real_root, target_is_directory=True)
            self._expect_error(
                SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            registry = package_root / "registry"
            real_registry = parent / "real-registry"
            registry.rename(real_registry)
            registry.symlink_to(real_registry, target_is_directory=True)
            self._expect_error(
                SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            resource = package_root / first_relative
            outside = parent / "outside.json"
            resource.rename(outside)
            resource.symlink_to(outside)
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

    def test_writable_parent_and_unsupported_platform_hard_block(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            parent.chmod(0o777)
            try:
                self._expect_error(
                    SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID,
                    lambda: static_module._load_source_link_static_from_root(package_root),
                )
            finally:
                parent.chmod(0o700)

        with (
            tempfile.TemporaryDirectory() as raw_directory,
            patch.object(static_module.sys, "platform", "win32"),
        ):
            package_root = _copy_installed_layout(Path(raw_directory))
            self._expect_error(
                SourceLinkStaticErrorCode.PLATFORM_UNSUPPORTED,
                lambda: static_module._load_source_link_static_from_root(package_root),
            )

    def test_read_time_metadata_change_and_append_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            real_fstat = static_module.os.fstat
            changed = False

            def mutate_first_resource(descriptor: int) -> os.stat_result:
                nonlocal changed
                metadata = real_fstat(descriptor)
                if not changed and stat.S_ISREG(metadata.st_mode):
                    changed = True
                    os.fchmod(descriptor, 0o600)
                    metadata = real_fstat(descriptor)
                return metadata

            with patch.object(static_module.os, "fstat", new=mutate_first_resource):
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_CHANGED,
                    lambda: static_module._load_source_link_static_from_root(package_root),
                )
            self.assertTrue(changed)

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            target = package_root / next(iter(EXPECTED_RESOURCES))
            real_read = static_module.os.read
            changed = False

            def append_before_first_read(descriptor: int, amount: int) -> bytes:
                nonlocal changed
                if not changed:
                    changed = True
                    with target.open("ab") as handle:
                        handle.write(b"x")
                return real_read(descriptor, amount)

            with patch.object(static_module.os, "read", new=append_before_first_read):
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH,
                    lambda: static_module._load_source_link_static_from_root(package_root),
                )
            self.assertTrue(changed)

    def test_resource_descriptor_close_failure_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            real_close = static_module.os.close
            real_fstat = static_module.os.fstat
            failed = False

            def close_then_report_failure(descriptor: int) -> None:
                nonlocal failed
                is_resource = stat.S_ISREG(real_fstat(descriptor).st_mode)
                real_close(descriptor)
                if is_resource and not failed:
                    failed = True
                    raise OSError(CANARY_SECRET)

            with patch.object(static_module.os, "close", new=close_then_report_failure):
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                    lambda: static_module._load_source_link_static_from_root(package_root),
                )
            self.assertTrue(failed)

    def test_strict_json_and_closed_legacy_exception_are_separate(self) -> None:
        canonical_key = static_module._ResourceKey.SOURCE_POLICY
        legacy_key = static_module._ResourceKey.SOURCE_REGISTRY
        canonical = encode_json({"a": 1})
        self.assertEqual(
            {"a": 1},
            static_module._decode_static_resource(canonical, canonical_key),
        )
        compact = b'{"a":1}\n'
        self._expect_error(
            SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH,
            lambda: static_module._decode_static_resource(compact, canonical_key),
        )
        self._expect_error(
            SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH,
            lambda: static_module._decode_static_resource(compact, legacy_key),
        )
        for exact_legacy_key in static_module._LEGACY_EXACT_BYTE_JSON_KEYS:
            spec = static_module._SPEC_BY_KEY[exact_legacy_key]
            raw = (ROOT / spec.package_path).read_bytes()
            self.assertIsInstance(
                static_module._decode_static_resource(raw, exact_legacy_key),
                dict,
            )
            same_size_valid_json = b"{ " + raw[2:]
            self.assertEqual(len(raw), len(same_size_valid_json))
            self._expect_error(
                SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH,
                lambda raw=same_size_valid_json, key=exact_legacy_key: (
                    static_module._decode_static_resource(raw, key)
                ),
            )
        for malformed in (b'{"a":1,"a":2}\n', b"1.0\n", b"\xef\xbb\xbfnull\n"):
            with self.subTest(raw=malformed):
                self._expect_error(
                    SourceLinkStaticErrorCode.JSON_INVALID,
                    lambda malformed=malformed: static_module._decode_static_resource(
                        malformed,
                        legacy_key,
                    ),
                )

    def test_schema_reference_format_validation_and_cross_bindings_are_closed(self) -> None:
        self._expect_error(
            SourceLinkStaticErrorCode.SCHEMA_REFERENCE_FORBIDDEN,
            lambda: static_module._inspect_schema_keywords({"$ref": "https://example.invalid/x"}),
        )
        self._expect_error(
            SourceLinkStaticErrorCode.SCHEMA_FORMAT_FORBIDDEN,
            lambda: static_module._inspect_schema_keywords({"format": "unknown"}),
        )

        values = _decoded_values()
        static_module._validate_schemas_and_instances(values)
        schema_set, roster = static_module._verify_cross_bindings(values)
        self.assertEqual(EXPECTED_SNAPSHOT["artifact_schema_set_sha256"], schema_set)
        self.assertEqual(EXPECTED_SNAPSHOT["ordered_source_roster_sha256"], roster)

        roster_mutation = copy.deepcopy(values)
        roster_mutation[static_module._ResourceKey.SOURCE_CONTRACT]["ordered_inspection_roster"][
            "ordered_source_roster_sha256"
        ] = "sha256:" + "0" * 64
        self._expect_error(
            SourceLinkStaticErrorCode.DIGEST_MISMATCH,
            lambda: static_module._verify_cross_bindings(roster_mutation),
        )

        schema_set_mutation = copy.deepcopy(values)
        schemas = schema_set_mutation[static_module._ResourceKey.CUSTODY_CONTRACT][
            "artifact_schema_commitments"
        ]["schemas"]
        schemas[0], schemas[1] = schemas[1], schemas[0]
        self._expect_error(
            SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH,
            lambda: static_module._verify_cross_bindings(schema_set_mutation),
        )

    def test_static_load_opens_no_network(self) -> None:
        network_failure = AssertionError(CANARY_SECRET)
        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            with (
                patch.object(socket, "socket", side_effect=network_failure) as socket_open,
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=network_failure,
                ) as create_connection,
                patch.object(
                    http.client.HTTPConnection,
                    "connect",
                    side_effect=network_failure,
                ) as http_connect,
                patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=network_failure,
                ) as urlopen,
            ):
                snapshot = static_module._load_source_link_static_from_root(package_root)
        self.assertEqual(14, snapshot.resource_count)
        socket_open.assert_not_called()
        create_connection.assert_not_called()
        http_connect.assert_not_called()
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
