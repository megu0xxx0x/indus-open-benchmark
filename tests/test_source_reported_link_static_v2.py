from __future__ import annotations

import copy
import http.client
import inspect
import os
import shutil
import socket
import stat
import tempfile
import unittest
import urllib.request
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.source_reported_link_static as v1_module
import indusbench.source_reported_link_static_v2 as v2_module
from indusbench.source_reported_link_static import (
    SourceLinkStaticError,
    SourceLinkStaticErrorCode,
)
from indusbench.source_reported_link_static_v2 import (
    SourceFreeStaticProfileV2Snapshot,
    load_installed_source_link_static_profile_v2,
)

ROOT = Path(__file__).resolve().parents[1]
CANARY_SECRET = "STATIC_V2_SECRET_8d21"

EXPECTED_EXTENSION_RESOURCES = {
    "registry/source-reported-link-protected-ephemeral-custody-contract-v2.json": (
        16981,
        "a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c",
    ),
    "schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json": (
        17694,
        "1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671",
    ),
}
EXPECTED_SNAPSHOT = {
    "artifact_schema_set_sha256": (
        "sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f"
    ),
    "compatibility_profile_id": "source-reported-link-exact-two-static-byte-compatibility-v2",
    "compatibility_wrapper_sha256": (
        "sha256:a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c"
    ),
    "compatibility_wrapper_schema_sha256": (
        "sha256:1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671"
    ),
    "incorporated_v1_custody_contract_sha256": (
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


def _copy_installed_layout(parent: Path, *, include_v2: bool = True) -> Path:
    package_root = parent / "indusbench"
    for directory in ("registry", "schemas"):
        (package_root / directory).mkdir(parents=True, exist_ok=True, mode=0o755)
    package_root.chmod(0o755)
    specs = v2_module._RESOURCE_SPECS if include_v2 else v1_module._RESOURCE_SPECS
    for spec in specs:
        destination = package_root / spec.package_path
        shutil.copyfile(ROOT / spec.package_path, destination)
        destination.chmod(0o644)
    return package_root


def _decoded_values() -> dict[Any, Any]:
    return {
        spec.key: v2_module._decode_v2_static_resource(
            (ROOT / spec.package_path).read_bytes(),
            spec.key,
        )
        for spec in v2_module._RESOURCE_SPECS
    }


def _v1_snapshot_projection(snapshot: Any) -> dict[str, Any]:
    names = (
        "artifact_schema_set_sha256",
        "custody_contract_sha256",
        "ordered_source_roster_sha256",
        "source_contract_sha256",
        "source_policy_sha256",
        "source_registry_sha256",
        "missing_binding_fields",
        "strict_v1_resolver_eligible",
        "strict_v1_resolver_blockers",
        "resource_count",
    )
    return {name: getattr(snapshot, name) for name in names}


class SourceReportedLinkStaticV2Tests(unittest.TestCase):
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

    def test_exact_sixteen_order_count_total_and_each_raw_identity_are_frozen(self) -> None:
        v1_paths = [spec.package_path for spec in v1_module._RESOURCE_SPECS]
        v2_paths = [spec.package_path for spec in v2_module._RESOURCE_SPECS]
        self.assertEqual(
            [*v1_paths, *EXPECTED_EXTENSION_RESOURCES],
            v2_paths,
        )
        self.assertEqual(14, len(v1_module._RESOURCE_SPECS))
        self.assertEqual(16, len(v2_module._RESOURCE_SPECS))
        self.assertEqual(16, len(v2_module._SPEC_BY_KEY))
        self.assertEqual(1_069_631, sum(spec.size for spec in v2_module._RESOURCE_SPECS))
        for relative_path, (size, sha256) in EXPECTED_EXTENSION_RESOURCES.items():
            spec = next(
                spec for spec in v2_module._RESOURCE_SPECS if spec.package_path == relative_path
            )
            self.assertEqual((size, sha256), (spec.size, spec.sha256))

    def test_each_exact_sixteen_resource_is_independently_pinned(self) -> None:
        for spec in v2_module._RESOURCE_SPECS:
            with (
                self.subTest(relative_path=spec.package_path),
                tempfile.TemporaryDirectory() as raw_directory,
            ):
                package_root = _copy_installed_layout(Path(raw_directory))
                resource = package_root / spec.package_path
                raw = resource.read_bytes()
                resource.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_HASH_MISMATCH,
                    lambda package_root=package_root: (
                        v2_module._load_source_link_static_profile_v2_from_root(package_root)
                    ),
                )

    def test_valid_snapshot_is_closed_package_local_and_v1_ineligible(self) -> None:
        with tempfile.TemporaryDirectory(prefix=f"{CANARY_SECRET}-") as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            snapshot = v2_module._load_source_link_static_profile_v2_from_root(package_root)

        self.assertIs(type(snapshot), SourceFreeStaticProfileV2Snapshot)
        for name, expected in EXPECTED_SNAPSHOT.items():
            self.assertEqual(expected, getattr(snapshot, name))
        self.assertEqual(16, snapshot.resource_count)
        self.assertEqual(
            "validated_package_local_exact16_only",
            snapshot.package_local_static_prevalidation_status,
        )
        self.assertIs(snapshot.package_local_v2_static_profile_conformant, True)
        self.assertIs(snapshot.strict_v1_resolver_eligible, False)
        self.assertEqual(
            (
                "source_registry_noncanonical_raw_bytes",
                "source_registry_schema_noncanonical_raw_bytes",
            ),
            snapshot.strict_v1_resolver_blockers,
        )
        self.assertEqual(
            (
                "runtime_distribution_sha256",
                "transitive_runtime_input_manifest_sha256",
            ),
            snapshot.missing_binding_fields,
        )
        self.assertEqual("not_authorized", snapshot.authority_status)
        self.assertEqual("not_validated", snapshot.runtime_status)
        self.assertEqual("not_performed", snapshot.source_access_status)
        self.assertEqual("not_established", snapshot.result_status)
        self.assertEqual(
            "blocked_external_prerequisites_absent",
            snapshot.activation_status,
        )
        self.assertEqual(
            {
                *EXPECTED_SNAPSHOT,
                "missing_binding_fields",
                "package_local_static_prevalidation_status",
                "package_local_v2_static_profile_conformant",
                "strict_v1_resolver_eligible",
                "strict_v1_resolver_blockers",
                "authority_status",
                "runtime_status",
                "source_access_status",
                "result_status",
                "activation_status",
                "resource_count",
            },
            {field.name for field in fields(snapshot)},
        )
        for absent in (
            "custody_contract_sha256",
            "eligible",
            "authorized",
            "runtime_distribution_sha256",
            "transitive_runtime_input_manifest_sha256",
            "protected_bytes",
            "decoded_wrapper",
        ):
            self.assertFalse(hasattr(snapshot, absent), absent)
        with self.assertRaises(FrozenInstanceError):
            cast(Any, snapshot).resource_count = 0
        rendered = repr(snapshot)
        self.assertNotIn("sha256:", rendered)
        self.assertNotIn(CANARY_SECRET, rendered)

    def test_snapshot_constructor_rejects_caller_token(self) -> None:
        self._expect_error(
            SourceLinkStaticErrorCode.INVALID_ARGUMENT_TYPE,
            lambda: SourceFreeStaticProfileV2Snapshot(
                _token=object(),
                artifact_schema_set_sha256=EXPECTED_SNAPSHOT["artifact_schema_set_sha256"],
                compatibility_wrapper_sha256=EXPECTED_SNAPSHOT["compatibility_wrapper_sha256"],
                compatibility_wrapper_schema_sha256=EXPECTED_SNAPSHOT[
                    "compatibility_wrapper_schema_sha256"
                ],
                incorporated_v1_custody_contract_sha256=EXPECTED_SNAPSHOT[
                    "incorporated_v1_custody_contract_sha256"
                ],
                ordered_source_roster_sha256=EXPECTED_SNAPSHOT["ordered_source_roster_sha256"],
                source_contract_sha256=EXPECTED_SNAPSHOT["source_contract_sha256"],
                source_policy_sha256=EXPECTED_SNAPSHOT["source_policy_sha256"],
                source_registry_sha256=EXPECTED_SNAPSHOT["source_registry_sha256"],
            ),
        )

    def test_v1_snapshot_is_golden_before_and_after_v2_and_ignores_extension(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            before = v1_module._load_source_link_static_from_root(package_root)
            v2_module._load_source_link_static_profile_v2_from_root(package_root)
            after = v1_module._load_source_link_static_from_root(package_root)
            for extension_path in EXPECTED_EXTENSION_RESOURCES:
                (package_root / extension_path).write_text(CANARY_SECRET, encoding="utf-8")
            after_hostile_extension = v1_module._load_source_link_static_from_root(package_root)

        self.assertEqual(_v1_snapshot_projection(before), _v1_snapshot_projection(after))
        self.assertEqual(
            _v1_snapshot_projection(before),
            _v1_snapshot_projection(after_hostile_extension),
        )
        self.assertEqual(14, before.resource_count)
        self.assertIs(before.strict_v1_resolver_eligible, False)
        self.assertEqual(
            (
                "source_registry_noncanonical_raw_bytes",
                "source_registry_schema_noncanonical_raw_bytes",
            ),
            before.strict_v1_resolver_blockers,
        )
        self.assertEqual(
            "SourceFreeStaticSnapshot(resource_count=14, "
            "missing_binding_fields=('runtime_distribution_sha256', "
            "'transitive_runtime_input_manifest_sha256'), "
            "strict_v1_resolver_eligible=False)",
            repr(before),
        )

    def test_v1_succeeds_without_v2_but_v2_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory), include_v2=False)
            v1_snapshot = v1_module._load_source_link_static_from_root(package_root)
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
            )
        self.assertEqual(14, v1_snapshot.resource_count)

    def test_exact_two_canaries_and_all_other_canonical_resources_are_separate(self) -> None:
        self.assertEqual(
            set(v1_module._LEGACY_EXACT_BYTE_JSON_KEYS),
            set(v2_module._CANARY_BY_KEY),
        )
        for canary in v2_module._LEGACY_CANARIES:
            spec = v2_module._SPEC_BY_KEY[canary.key]
            raw = (ROOT / spec.package_path).read_bytes()
            value = v2_module._decode_v2_static_resource(raw, canary.key)
            canonical = v2_module.encode_json(value)
            self.assertNotEqual(raw, canonical)
            self.assertEqual(canary.canonical_size, len(canonical))
            self.assertEqual(
                canary.canonical_sha256, v2_module.hashlib.sha256(canonical).hexdigest()
            )

            changed = copy.copy(canary)
            object.__setattr__(changed, "canonical_sha256", "0" * 64)
            canaries = dict(v2_module._CANARY_BY_KEY)
            canaries[canary.key] = changed
            with patch.object(v2_module, "_CANARY_BY_KEY", canaries):
                self._expect_error(
                    SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH,
                    lambda raw=raw, key=canary.key: v2_module._decode_v2_static_resource(raw, key),
                )

        wrapper_raw = (ROOT / v2_module._WRAPPER_SPEC.package_path).read_bytes()
        self.assertIsInstance(
            v2_module._decode_v2_static_resource(
                wrapper_raw,
                v1_module._ResourceKey.CUSTODY_CONTRACT_V2,
            ),
            dict,
        )
        compact = b'{"a":1}\n'
        self._expect_error(
            SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH,
            lambda: v2_module._decode_v2_static_resource(
                compact,
                v1_module._ResourceKey.CUSTODY_CONTRACT_V2,
            ),
        )

    def test_v2_schema_const_and_profile_cross_bindings_are_closed(self) -> None:
        values = _decoded_values()
        v2_module._validate_v2_wrapper_schema(values)
        v2_module._verify_v2_cross_bindings(values)

        mutations: list[tuple[str, dict[Any, Any]]] = []
        for label, operation in (
            (
                "selected order",
                lambda wrapper: wrapper["resolver_successor"][
                    "selected_static_resources_after_implementation_exact"
                ].reverse(),
            ),
            (
                "compatibility id",
                lambda wrapper: wrapper["resolver_successor"].__setitem__(
                    "compatibility_profile_id", "caller-selected"
                ),
            ),
            (
                "default precedence",
                lambda wrapper: wrapper["resolver_successor"].__setitem__(
                    "default_and_exception_precedence", "expanded"
                ),
            ),
            (
                "canonical canary",
                lambda wrapper: wrapper["resolver_successor"][
                    "legacy_noncanonical_static_resources_exact"
                ][0].__setitem__("canonical_reencoding_sha256", "sha256:" + "0" * 64),
            ),
            (
                "binding source",
                lambda wrapper: wrapper["resolver_successor"][
                    "legacy_noncanonical_static_resources_exact"
                ][0]["binding_sources"].pop(),
            ),
            (
                "composition",
                lambda wrapper: wrapper["resolver_successor"][
                    "canonical_byte_check_splice"
                ].__setitem__("base_token_occurrence_count_exact", 2),
            ),
            (
                "supersession",
                lambda wrapper: wrapper["historical_parent_incorporation"][
                    "superseded_parent_rules_exact"
                ][0].__setitem__("scope", "expanded"),
            ),
            (
                "incorporated raw identity",
                lambda wrapper: wrapper["historical_parent_incorporation"][
                    "incorporated_artifacts"
                ]["source_contract_v1"].__setitem__("sha256", "sha256:" + "0" * 64),
            ),
            (
                "exact eight",
                lambda wrapper: wrapper["future_external_binding"][
                    "existing_exact_eight_field_names_unchanged"
                ].reverse(),
            ),
            (
                "self cycle",
                lambda wrapper: wrapper["future_external_binding"][
                    "self_cycle_exclusion"
                ].__setitem__("custody_const_schema_forbidden_count_exact", 1),
            ),
            (
                "authority status",
                lambda wrapper: wrapper["authorization_boundary"].__setitem__(
                    "status", "authorized"
                ),
            ),
            (
                "historical wrapper status",
                lambda wrapper: wrapper.__setitem__("contract_status", "activated"),
            ),
        ):
            changed = copy.deepcopy(values)
            wrapper = changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]
            operation(wrapper)
            mutations.append((label, changed))

        frozen_wrapper = values[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]
        for field_name in frozen_wrapper["authorization_boundary"]:
            changed = copy.deepcopy(values)
            del changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]["authorization_boundary"][
                field_name
            ]
            mutations.append((f"authorization field removed: {field_name}", changed))
        for field_name in v2_module._AUTHORIZATION_FALSE_FIELDS:
            changed = copy.deepcopy(values)
            changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]["authorization_boundary"][
                field_name
            ] = 0
            mutations.append((f"authorization bool type changed: {field_name}", changed))
        for field_name in frozen_wrapper["nonclaims"]:
            changed = copy.deepcopy(values)
            del changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]["nonclaims"][field_name]
            mutations.append((f"nonclaim removed: {field_name}", changed))

            changed = copy.deepcopy(values)
            changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]["nonclaims"][field_name] = 0
            mutations.append((f"nonclaim bool type changed: {field_name}", changed))
        for operation_label, operation in (
            (
                "successor conformance status removed",
                lambda successor: successor.pop("successor_static_profile_conformance_status"),
            ),
            (
                "successor conformance status changed",
                lambda successor: successor.__setitem__(
                    "successor_static_profile_conformance_status",
                    "evaluated",
                ),
            ),
        ):
            changed = copy.deepcopy(values)
            operation(changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2]["resolver_successor"])
            mutations.append((operation_label, changed))

        for label, changed in mutations:
            with self.subTest(label=label):
                self._expect_error(
                    SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH,
                    lambda changed=changed: v2_module._verify_v2_cross_bindings(changed),
                )

    def test_v2_schema_rejects_const_id_and_external_reference_mutations(self) -> None:
        values = _decoded_values()

        changed = copy.deepcopy(values)
        changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2_SCHEMA]["const"] = {}
        self._expect_error(
            SourceLinkStaticErrorCode.SCHEMA_INVALID,
            lambda: v2_module._validate_v2_wrapper_schema(changed),
        )

        changed = copy.deepcopy(values)
        changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2_SCHEMA]["$id"] = "wrong.json"
        self._expect_error(
            SourceLinkStaticErrorCode.SCHEMA_INVALID,
            lambda: v2_module._validate_v2_wrapper_schema(changed),
        )

        changed = copy.deepcopy(values)
        changed[v1_module._ResourceKey.CUSTODY_CONTRACT_V2_SCHEMA]["$ref"] = (
            "https://example.invalid/forbidden"
        )
        self._expect_error(
            SourceLinkStaticErrorCode.SCHEMA_REFERENCE_FORBIDDEN,
            lambda: v2_module._validate_v2_wrapper_schema(changed),
        )

    def test_v2_extension_size_hash_mode_link_symlink_and_fifo_fail_closed(self) -> None:
        relative_path = next(iter(EXPECTED_EXTENSION_RESOURCES))

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            resource = package_root / relative_path
            resource.write_bytes(resource.read_bytes() + b"x")
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH,
                lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            resource = package_root / relative_path
            resource.chmod(0o744)
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            resource = package_root / relative_path
            os.link(resource, parent / "hardlink")
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
            )

        with tempfile.TemporaryDirectory() as raw_directory:
            parent = Path(raw_directory)
            package_root = _copy_installed_layout(parent)
            resource = package_root / relative_path
            outside = parent / "outside.json"
            resource.rename(outside)
            resource.symlink_to(outside)
            self._expect_error(
                SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
            )

        if hasattr(os, "mkfifo"):
            with tempfile.TemporaryDirectory() as raw_directory:
                package_root = _copy_installed_layout(Path(raw_directory))
                resource = package_root / relative_path
                resource.unlink()
                os.mkfifo(resource, mode=0o600)
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                    lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
                )

    def test_public_v2_api_is_zero_argument_and_uses_one_exact_sixteen_traversal(self) -> None:
        self.assertEqual(
            (),
            tuple(inspect.signature(load_installed_source_link_static_profile_v2).parameters),
        )
        # Load jsonschema's own package resources before replacing the shared
        # importlib.resources.files function for this public-loader boundary.
        __import__("jsonschema")
        calls: list[tuple[Path, tuple[Any, ...]]] = []
        real_read = v2_module._read_static_package_exact

        def record_read(root: Path, specs: tuple[Any, ...]) -> dict[Any, bytes]:
            calls.append((root, specs))
            return real_read(root, specs)

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            with (
                patch.object(v2_module.importlib.resources, "files", return_value=package_root),
                patch.object(v2_module, "_read_static_package_exact", side_effect=record_read),
            ):
                snapshot = load_installed_source_link_static_profile_v2()

        self.assertEqual(16, snapshot.resource_count)
        self.assertEqual(1, len(calls))
        self.assertEqual(package_root, calls[0][0])
        self.assertIs(v2_module._RESOURCE_SPECS, calls[0][1])
        self.assertEqual(16, len(calls[0][1]))

    def test_v2_last_extension_read_fstat_and_close_races_fail_closed(self) -> None:
        target_relative = v2_module._WRAPPER_SCHEMA_SPEC.package_path

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            target = package_root / target_relative
            target_metadata = target.stat()
            real_fstat = v1_module.os.fstat
            target_fstat_count = 0

            def mutate_on_after_read_fstat(descriptor: int) -> os.stat_result:
                nonlocal target_fstat_count
                metadata = real_fstat(descriptor)
                if stat.S_ISREG(metadata.st_mode) and (metadata.st_dev, metadata.st_ino) == (
                    target_metadata.st_dev,
                    target_metadata.st_ino,
                ):
                    target_fstat_count += 1
                    if target_fstat_count == 2:
                        os.fchmod(descriptor, 0o600)
                        metadata = real_fstat(descriptor)
                return metadata

            with patch.object(v1_module.os, "fstat", new=mutate_on_after_read_fstat):
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_CHANGED,
                    lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
                )
            self.assertEqual(2, target_fstat_count)

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            target = package_root / target_relative
            target_metadata = target.stat()
            real_read = v1_module.os.read
            real_fstat = v1_module.os.fstat
            changed = False

            def append_before_target_read(descriptor: int, amount: int) -> bytes:
                nonlocal changed
                metadata = real_fstat(descriptor)
                if (
                    not changed
                    and stat.S_ISREG(metadata.st_mode)
                    and (metadata.st_dev, metadata.st_ino)
                    == (target_metadata.st_dev, target_metadata.st_ino)
                ):
                    changed = True
                    with target.open("ab") as handle:
                        handle.write(b"x")
                return real_read(descriptor, amount)

            with patch.object(v1_module.os, "read", new=append_before_target_read):
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH,
                    lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
                )
            self.assertTrue(changed)

        with tempfile.TemporaryDirectory() as raw_directory:
            package_root = _copy_installed_layout(Path(raw_directory))
            target = package_root / target_relative
            target_metadata = target.stat()
            real_close = v1_module.os.close
            real_fstat = v1_module.os.fstat
            failed = False

            def close_target_then_report_failure(descriptor: int) -> None:
                nonlocal failed
                metadata = real_fstat(descriptor)
                is_target = stat.S_ISREG(metadata.st_mode) and (
                    metadata.st_dev,
                    metadata.st_ino,
                ) == (target_metadata.st_dev, target_metadata.st_ino)
                real_close(descriptor)
                if is_target and not failed:
                    failed = True
                    raise OSError(CANARY_SECRET)

            with patch.object(v1_module.os, "close", new=close_target_then_report_failure):
                self._expect_error(
                    SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID,
                    lambda: v2_module._load_source_link_static_profile_v2_from_root(package_root),
                )
            self.assertTrue(failed)

    def test_public_v2_loader_rejects_checkout_and_nonfilesystem_traversable(self) -> None:
        with patch.object(
            v2_module.importlib.resources,
            "files",
            return_value=ROOT / "src" / "indusbench",
        ):
            self._expect_error(
                SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID,
                load_installed_source_link_static_profile_v2,
            )
        with patch.object(v2_module.importlib.resources, "files", return_value=object()):
            self._expect_error(
                SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED,
                load_installed_source_link_static_profile_v2,
            )

    def test_v2_load_opens_no_network(self) -> None:
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
                snapshot = v2_module._load_source_link_static_profile_v2_from_root(package_root)
        self.assertEqual(16, snapshot.resource_count)
        socket_open.assert_not_called()
        create_connection.assert_not_called()
        http_connect.assert_not_called()
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
