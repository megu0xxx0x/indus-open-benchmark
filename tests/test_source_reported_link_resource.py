from __future__ import annotations

import ast
import http.client
import json
import socket
import unittest
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import indusbench.source_reported_link_resource as resource_module
from indusbench.io import encode_json
from indusbench.source_reported_link_resource import (
    AUTHENTICATED_CONTROL_STAGING_MAXIMUM_BYTES,
    MAXIMUM_INTEGER_DIGITS,
    MAXIMUM_NESTING_DEPTH,
    MAXIMUM_NODE_COUNT,
    MAXIMUM_STRING_LENGTH,
    PreflightedCanonicalResource,
    RawArtifactRole,
    SourceLinkResourceError,
    SourceLinkResourceErrorCode,
    maximum_bytes_for_role,
    preflight_canonical_resource,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "indusbench" / "source_reported_link_resource.py"

DEFAULT_ROLE = RawArtifactRole.AUTHORITY_PROOF_BUNDLE
LARGE_ROLE = RawArtifactRole.TRANSITIVE_RUNTIME_INPUT_MANIFEST
CANARY_RAW = "CANARY_RAW_7f29"
CANARY_PATH = "/synthetic/canary/source.json"
CANARY_SECRET = "SECRET_DO_NOT_DISCLOSE_8b41"
FORBIDDEN_DISCLOSURES = (CANARY_RAW, CANARY_PATH, CANARY_SECRET)

EXPECTED_ROLE_LIMITS = (
    (RawArtifactRole.AUTHORITY_PROOF_BUNDLE, 16384),
    (RawArtifactRole.TRANSITIVE_RUNTIME_INPUT_MANIFEST, 65536),
    (RawArtifactRole.ONE_TIME_ATTEMPT_RESERVATION, 16384),
    (RawArtifactRole.ATTEMPT_REGISTRY_GENERATION, 16384),
    (RawArtifactRole.ATTEMPT_LEDGER_GENERATION, 16384),
    (RawArtifactRole.PRE_ACQUISITION_ATTESTATION, 16384),
    (RawArtifactRole.SOURCE_REVISION_RECEIPT_PAYLOAD, 65536),
    (RawArtifactRole.RECEIPT_COMMITMENT_ENVELOPE, 4096),
    (RawArtifactRole.SOURCE_REVISION_SET_PAYLOAD, 16384),
    (RawArtifactRole.ACQUISITION_CORE_GRAPH, 16384),
    (RawArtifactRole.POST_ACQUISITION_EXECUTION_ATTESTATION, 32768),
    (RawArtifactRole.COMPLETENESS_ATTESTATION_PAYLOAD, 8192),
    (RawArtifactRole.PASS_PROOF_BUNDLE_ORDINAL_1, 16384),
    (RawArtifactRole.PASS_PROOF_BUNDLE_ORDINAL_2, 16384),
    (RawArtifactRole.EXACT6_TERMINAL_DECISION, 32768),
    (RawArtifactRole.CUSTODY_DELETION_RECORD, 8192),
    (RawArtifactRole.PRE_MANAGEMENT_CLOSURE_TERMINAL_ARTIFACT_GRAPH, 16384),
    (RawArtifactRole.MANAGEMENT_DESCRIPTOR_CLOSURE_OBSERVATION, 4096),
    (RawArtifactRole.INTERNAL_RETENTION_REVIEW_PROOF_BUNDLE, 16384),
    (RawArtifactRole.OWNER_ONLY_RETENTION_BATCH_MANIFEST, 65536),
    (RawArtifactRole.OWNER_ONLY_RETENTION_BATCH_RECEIPT, 16384),
)

EXPECTED_ERROR_CODES = (
    SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE,
    SourceLinkResourceErrorCode.RAW_SIZE_OUT_OF_RANGE,
    SourceLinkResourceErrorCode.UTF8_OR_BOM_INVALID,
    SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID,
    SourceLinkResourceErrorCode.JSON_DUPLICATE_KEY,
    SourceLinkResourceErrorCode.JSON_FLOAT_FORBIDDEN,
    SourceLinkResourceErrorCode.JSON_INTEGER_DIGITS_EXCEEDED,
    SourceLinkResourceErrorCode.JSON_DEPTH_EXCEEDED,
    SourceLinkResourceErrorCode.JSON_NODE_COUNT_EXCEEDED,
    SourceLinkResourceErrorCode.JSON_STRING_LENGTH_EXCEEDED,
    SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH,
)


def _nested_array(levels: int) -> object:
    value: object = None
    for _ in range(levels):
        value = [value]
    return value


class SourceReportedLinkResourceTests(unittest.TestCase):
    def _expect_error(
        self,
        expected_code: SourceLinkResourceErrorCode,
        operation: Callable[[], object],
    ) -> SourceLinkResourceError:
        with self.assertRaises(SourceLinkResourceError) as caught:
            operation()
        error = caught.exception
        expected_message = f"source_reported_link_resource:{expected_code.value}"
        self.assertIs(expected_code, error.code)
        self.assertEqual(expected_message, str(error))
        self.assertEqual((expected_message,), error.args)
        self.assertEqual({"code"}, set(vars(error)))
        self.assertFalse(hasattr(error, "path"))
        self.assertFalse(hasattr(error, "raw"))
        self.assertFalse(hasattr(error, "detail"))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        public_surface = "\n".join(
            (
                error.code.value,
                str(error),
                repr(error),
                repr(error.args),
                repr(vars(error)),
            )
        )
        for forbidden in FORBIDDEN_DISCLOSURES:
            self.assertNotIn(forbidden, public_surface)
        return error

    def test_exact_role_roster_and_per_role_byte_limits(self) -> None:
        self.assertEqual(21, len(EXPECTED_ROLE_LIMITS))
        self.assertEqual(
            tuple(role for role, _ in EXPECTED_ROLE_LIMITS),
            tuple(RawArtifactRole),
        )
        self.assertEqual(21, len({role.value for role, _ in EXPECTED_ROLE_LIMITS}))
        for role, expected_limit in EXPECTED_ROLE_LIMITS:
            with self.subTest(role=role.value):
                self.assertEqual(expected_limit, maximum_bytes_for_role(role))

    def test_error_code_roster_and_shared_structural_limits_are_exact(self) -> None:
        self.assertEqual(EXPECTED_ERROR_CODES, tuple(SourceLinkResourceErrorCode))
        self.assertEqual(32, MAXIMUM_NESTING_DEPTH)
        self.assertEqual(4096, MAXIMUM_NODE_COUNT)
        self.assertEqual(8192, MAXIMUM_STRING_LENGTH)
        self.assertEqual(10, MAXIMUM_INTEGER_DIGITS)
        self.assertEqual(16384, AUTHENTICATED_CONTROL_STAGING_MAXIMUM_BYTES)

    def test_canonical_null_succeeds_for_every_exact_role(self) -> None:
        raw = b"null\n"
        for role in RawArtifactRole:
            with self.subTest(role=role.value):
                handle = preflight_canonical_resource(raw, role=role)
                self.assertIs(role, handle.role)
                self.assertEqual(len(raw), handle.canonical_size)
                self.assertIs(raw, handle.raw_bytes)
                self.assertIsNone(handle.value)

    def test_canonical_complex_value_is_recursively_immutable_and_repr_is_redacted(
        self,
    ) -> None:
        source_value = {
            "canary": f"{CANARY_RAW}:{CANARY_PATH}:{CANARY_SECRET}",
            "nested": [None, True, False, -1234567890, "café 😀", {"z": 0}],
        }
        raw = encode_json(source_value)
        handle = preflight_canonical_resource(raw, role=DEFAULT_ROLE)

        self.assertIs(DEFAULT_ROLE, handle.role)
        self.assertEqual(len(raw), handle.canonical_size)
        self.assertIs(raw, handle.raw_bytes)
        frozen = cast(Mapping[str, object], handle.value)
        self.assertEqual(source_value["canary"], frozen["canary"])
        nested = cast(tuple[object, ...], frozen["nested"])
        self.assertIsInstance(nested, tuple)
        self.assertEqual((None, True, False, -1234567890, "café 😀"), nested[:5])
        self.assertIsInstance(nested[5], Mapping)

        with self.assertRaises(TypeError):
            cast(Any, frozen)["new"] = None
        with self.assertRaises(TypeError):
            cast(Any, nested[5])["z"] = 1
        with self.assertRaises(AttributeError):
            cast(Any, nested).append(None)
        with self.assertRaises(FrozenInstanceError):
            cast(Any, handle).canonical_size = 0

        rendered = repr(handle)
        self.assertEqual(
            "PreflightedCanonicalResource("
            "role='authority_proof_bundle', canonical_size="
            f"{len(raw)})",
            rendered,
        )
        self.assertEqual(rendered, str(handle))
        for forbidden in FORBIDDEN_DISCLOSURES:
            self.assertNotIn(forbidden, rendered)

    def test_direct_handle_construction_rejects_a_caller_supplied_token(self) -> None:
        raw = encode_json(f"{CANARY_RAW}:{CANARY_PATH}:{CANARY_SECRET}")
        self._expect_error(
            SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE,
            lambda: PreflightedCanonicalResource(
                _token=object(),
                role=DEFAULT_ROLE,
                canonical_size=len(raw),
                raw=raw,
                value=None,
            ),
        )

    def test_raw_and_role_types_are_exact_not_coercible(self) -> None:
        class BytesSubclass(bytes):
            pass

        invalid_raw_values: tuple[object, ...] = (
            "null\n",
            bytearray(b"null\n"),
            memoryview(b"null\n"),
            BytesSubclass(b"null\n"),
            True,
            None,
        )
        for invalid_raw in invalid_raw_values:
            with self.subTest(raw_type=type(invalid_raw).__name__):
                self._expect_error(
                    SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE,
                    lambda invalid_raw=invalid_raw: preflight_canonical_resource(
                        cast(Any, invalid_raw),
                        role=DEFAULT_ROLE,
                    ),
                )

        invalid_roles: tuple[object, ...] = (DEFAULT_ROLE.value, 0, None)
        for invalid_role in invalid_roles:
            with self.subTest(role_type=type(invalid_role).__name__):
                self._expect_error(
                    SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE,
                    lambda invalid_role=invalid_role: preflight_canonical_resource(
                        b"null\n",
                        role=cast(Any, invalid_role),
                    ),
                )
                self._expect_error(
                    SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE,
                    lambda invalid_role=invalid_role: maximum_bytes_for_role(
                        cast(Any, invalid_role)
                    ),
                )

    def test_empty_and_over_limit_raw_bytes_reject_before_json_parsing(self) -> None:
        for role in (
            RawArtifactRole.RECEIPT_COMMITMENT_ENVELOPE,
            RawArtifactRole.MANAGEMENT_DESCRIPTOR_CLOSURE_OBSERVATION,
        ):
            with self.subTest(role=role.value, boundary="empty"):
                self._expect_error(
                    SourceLinkResourceErrorCode.RAW_SIZE_OUT_OF_RANGE,
                    lambda role=role: preflight_canonical_resource(b"", role=role),
                )

            exact_limit_raw = encode_json("a" * 4093)
            self.assertEqual(4096, len(exact_limit_raw))
            self.assertEqual(
                exact_limit_raw,
                preflight_canonical_resource(exact_limit_raw, role=role).raw_bytes,
            )

            over_limit_raw = encode_json("a" * 4094)
            self.assertEqual(4097, len(over_limit_raw))
            with self.subTest(role=role.value, boundary="over"):
                self._expect_error(
                    SourceLinkResourceErrorCode.RAW_SIZE_OUT_OF_RANGE,
                    lambda role=role, raw=over_limit_raw: preflight_canonical_resource(
                        raw, role=role
                    ),
                )

    def test_bom_and_invalid_utf8_have_one_closed_error(self) -> None:
        malformed = (
            b"\xef\xbb\xbfnull\n",
            b'"\xff"\n',
            b'"\xc0\xaf"\n',
            b'"\xed\xa0\x80"\n',
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.UTF8_OR_BOM_INVALID,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

    def test_isolated_surrogates_are_syntax_errors_and_valid_pair_escape_is_noncanonical(
        self,
    ) -> None:
        for raw in (b'"\\ud800"\n', b'"\\udc00"\n', b'"\\ud800\\ud800"\n'):
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

        escaped_pair = b'"\\ud83d\\ude00"\n'
        self._expect_error(
            SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH,
            lambda: preflight_canonical_resource(escaped_pair, role=DEFAULT_ROLE),
        )
        literal_pair = encode_json("😀")
        self.assertEqual(
            "😀",
            preflight_canonical_resource(literal_pair, role=DEFAULT_ROLE).value,
        )

    def test_nul_multidocument_and_non_whitespace_trailing_bytes_are_syntax_errors(
        self,
    ) -> None:
        malformed = (
            b'"\x00"\n',
            b"null\x00\n",
            b"null\nnull\n",
            b"null/",
            b'{"x":null,}\n',
            b'{"x":]\n',
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

    def test_nested_and_escape_equivalent_duplicate_keys_reject(self) -> None:
        malformed = (
            b'{"outer":{"a":1,"a":2}}\n',
            b'{"outer":{"a":1,"\\u0061":2}}\n',
            b'{"a":1,"\\u0061":2,"other":3}\n',
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_DUPLICATE_KEY,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

    def test_floats_and_exponents_reject_before_materialization(self) -> None:
        for raw in (b"0.0\n", b"-1.5\n", b"1e0\n", b"-2E+9\n", b"1e999\n"):
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_FLOAT_FORBIDDEN,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

    def test_nonfinite_numbers_use_float_error_and_negative_zero_is_noncanonical(self) -> None:
        for raw in (b"NaN\n", b"Infinity\n", b"-Infinity\n"):
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_FLOAT_FORBIDDEN,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )
        self._expect_error(
            SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH,
            lambda: preflight_canonical_resource(b"-0\n", role=DEFAULT_ROLE),
        )

    def test_integer_digit_limit_excludes_the_optional_minus_sign(self) -> None:
        for raw, expected_value in (
            (b"1234567890\n", 1234567890),
            (b"-1234567890\n", -1234567890),
        ):
            with self.subTest(raw=raw):
                handle = preflight_canonical_resource(raw, role=DEFAULT_ROLE)
                self.assertEqual(expected_value, handle.value)

        for raw in (b"12345678901\n", b"-12345678901\n"):
            with self.subTest(raw=raw):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_INTEGER_DIGITS_EXCEEDED,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

    def test_depth_32_passes_and_depth_33_rejects_with_root_at_depth_zero(self) -> None:
        accepted_raw = encode_json(_nested_array(32))
        accepted = preflight_canonical_resource(accepted_raw, role=DEFAULT_ROLE)
        current: object = accepted.value
        for _ in range(32):
            self.assertIsInstance(current, tuple)
            current = cast(tuple[object, ...], current)[0]
        self.assertIsNone(current)

        rejected_raw = encode_json(_nested_array(33))
        self._expect_error(
            SourceLinkResourceErrorCode.JSON_DEPTH_EXCEEDED,
            lambda: preflight_canonical_resource(rejected_raw, role=DEFAULT_ROLE),
        )

    def test_node_limit_counts_root_and_values_but_not_object_keys(self) -> None:
        accepted_list_raw = encode_json([None] * 4095)
        self.assertLessEqual(len(accepted_list_raw), maximum_bytes_for_role(LARGE_ROLE))
        accepted_list = preflight_canonical_resource(accepted_list_raw, role=LARGE_ROLE)
        self.assertEqual(4095, len(cast(tuple[object, ...], accepted_list.value)))

        rejected_list_raw = encode_json([None] * 4096)
        self.assertLessEqual(len(rejected_list_raw), maximum_bytes_for_role(LARGE_ROLE))
        self._expect_error(
            SourceLinkResourceErrorCode.JSON_NODE_COUNT_EXCEEDED,
            lambda: preflight_canonical_resource(rejected_list_raw, role=LARGE_ROLE),
        )

        accepted_object_raw = encode_json({str(index): None for index in range(4095)})
        self.assertLessEqual(len(accepted_object_raw), maximum_bytes_for_role(LARGE_ROLE))
        accepted_object = preflight_canonical_resource(accepted_object_raw, role=LARGE_ROLE)
        self.assertEqual(4095, len(cast(Mapping[str, object], accepted_object.value)))

        rejected_object_raw = encode_json({str(index): None for index in range(4096)})
        self.assertLessEqual(len(rejected_object_raw), maximum_bytes_for_role(LARGE_ROLE))
        self._expect_error(
            SourceLinkResourceErrorCode.JSON_NODE_COUNT_EXCEEDED,
            lambda: preflight_canonical_resource(rejected_object_raw, role=LARGE_ROLE),
        )

    def test_key_and_value_limits_count_decoded_unicode_scalars(self) -> None:
        accepted_value = "😀" * 8192
        accepted_value_raw = encode_json(accepted_value)
        self.assertGreater(len(accepted_value_raw), MAXIMUM_STRING_LENGTH)
        self.assertEqual(
            accepted_value,
            preflight_canonical_resource(accepted_value_raw, role=LARGE_ROLE).value,
        )

        rejected_value_raw = encode_json("😀" * 8193)
        self._expect_error(
            SourceLinkResourceErrorCode.JSON_STRING_LENGTH_EXCEEDED,
            lambda: preflight_canonical_resource(rejected_value_raw, role=LARGE_ROLE),
        )

        accepted_key = "😀" * 8192
        accepted_key_raw = encode_json({accepted_key: None})
        accepted_mapping = cast(
            Mapping[str, object],
            preflight_canonical_resource(accepted_key_raw, role=LARGE_ROLE).value,
        )
        self.assertEqual((accepted_key,), tuple(accepted_mapping))

        rejected_key_raw = encode_json({"😀" * 8193: None})
        self._expect_error(
            SourceLinkResourceErrorCode.JSON_STRING_LENGTH_EXCEEDED,
            lambda: preflight_canonical_resource(rejected_key_raw, role=LARGE_ROLE),
        )

    def test_valid_but_noncanonical_byte_variants_reject(self) -> None:
        canary_value = encode_json(f"{CANARY_RAW}:{CANARY_PATH}:{CANARY_SECRET}")
        variants = (
            b"null",
            b"null\r\n",
            b" null\n",
            b"null \n",
            b"null\n\n",
            b'{"a":1}\n',
            b'{\n  "b": 1,\n  "a": 2\n}\n',
            b'"\\u0061"\n',
            canary_value + b" ",
        )
        for raw in variants:
            with self.subTest(raw=raw[:40]):
                self._expect_error(
                    SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH,
                    lambda raw=raw: preflight_canonical_resource(raw, role=DEFAULT_ROLE),
                )

    def test_parser_exceptions_are_normalized_without_detail_on_the_public_surface(self) -> None:
        exception_factories: tuple[tuple[str, Callable[[], BaseException]], ...] = (
            (
                "json_decode",
                lambda: json.JSONDecodeError(CANARY_SECRET, CANARY_PATH, 0),
            ),
            ("overflow", lambda: OverflowError(f"{CANARY_RAW}:{CANARY_PATH}")),
            ("recursion", lambda: RecursionError(f"{CANARY_RAW}:{CANARY_PATH}")),
            ("unicode", lambda: UnicodeError(f"{CANARY_SECRET}:{CANARY_PATH}")),
            ("value", lambda: ValueError(f"{CANARY_RAW}:{CANARY_SECRET}")),
        )
        for label, exception_factory in exception_factories:
            with (
                self.subTest(exception=label),
                patch.object(
                    resource_module.json,
                    "loads",
                    side_effect=exception_factory(),
                ),
            ):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID,
                    lambda: preflight_canonical_resource(b"null\n", role=DEFAULT_ROLE),
                )

    def test_scanner_exceptions_are_normalized_without_an_exception_chain(self) -> None:
        exception_factories: tuple[tuple[str, Callable[[], BaseException]], ...] = (
            ("overflow", lambda: OverflowError(f"{CANARY_RAW}:{CANARY_PATH}")),
            ("unicode", lambda: UnicodeError(f"{CANARY_SECRET}:{CANARY_PATH}")),
            ("value", lambda: ValueError(f"{CANARY_RAW}:{CANARY_SECRET}")),
        )
        for label, exception_factory in exception_factories:
            with (
                self.subTest(exception=label),
                patch.object(
                    resource_module,
                    "_SCANSTRING",
                    side_effect=exception_factory(),
                ),
            ):
                self._expect_error(
                    SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID,
                    lambda: preflight_canonical_resource(b'"value"\n', role=DEFAULT_ROLE),
                )

    def test_encoder_exceptions_are_normalized_without_detail_on_the_public_surface(self) -> None:
        exception_factories: tuple[tuple[str, Callable[[], BaseException]], ...] = (
            ("overflow", lambda: OverflowError(f"{CANARY_RAW}:{CANARY_PATH}")),
            ("recursion", lambda: RecursionError(f"{CANARY_RAW}:{CANARY_PATH}")),
            ("type", lambda: TypeError(f"{CANARY_SECRET}:{CANARY_PATH}")),
            ("unicode", lambda: UnicodeError(f"{CANARY_SECRET}:{CANARY_PATH}")),
            ("value", lambda: ValueError(f"{CANARY_RAW}:{CANARY_SECRET}")),
        )
        for label, exception_factory in exception_factories:
            with (
                self.subTest(exception=label),
                patch.object(
                    resource_module,
                    "encode_json",
                    side_effect=exception_factory(),
                ),
            ):
                self._expect_error(
                    SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH,
                    lambda: preflight_canonical_resource(b"null\n", role=DEFAULT_ROLE),
                )

    def test_preflight_has_no_network_import_or_runtime_network_call(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.partition(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_roots.add(node.module.partition(".")[0])
        self.assertTrue(
            imported_roots.isdisjoint(
                {"aiohttp", "http", "requests", "socket", "subprocess", "urllib"}
            )
        )

        network_failure = AssertionError(f"{CANARY_SECRET}:{CANARY_PATH}")
        with (
            patch.object(socket, "socket", side_effect=network_failure) as socket_constructor,
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
            handle = preflight_canonical_resource(b"null\n", role=DEFAULT_ROLE)

        self.assertIsNone(handle.value)
        socket_constructor.assert_not_called()
        create_connection.assert_not_called()
        http_connect.assert_not_called()
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
