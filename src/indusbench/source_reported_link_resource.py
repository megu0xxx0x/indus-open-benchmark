"""Bounded canonical-JSON preflight for future source-reported-link artifacts.

This module performs only the raw-resource and canonical-JSON checks that
precede schema, domain-digest, authority, attempt, lifecycle, and parent
binding validation. A returned value is not evidence, an execution
attestation, or permission to access a source.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, Never, TypeAlias, cast

from .io import encode_json

MAXIMUM_NESTING_DEPTH: Final = 32
MAXIMUM_NODE_COUNT: Final = 4096
MAXIMUM_STRING_LENGTH: Final = 8192
MAXIMUM_INTEGER_DIGITS: Final = 10
AUTHENTICATED_CONTROL_STAGING_MAXIMUM_BYTES: Final = 16384


class RawArtifactRole(StrEnum):
    """The exact 21 typed raw-resource roles in the V8 custody contract."""

    AUTHORITY_PROOF_BUNDLE = "authority_proof_bundle"
    TRANSITIVE_RUNTIME_INPUT_MANIFEST = "transitive_runtime_input_manifest"
    ONE_TIME_ATTEMPT_RESERVATION = "one_time_attempt_reservation"
    ATTEMPT_REGISTRY_GENERATION = "attempt_registry_generation"
    ATTEMPT_LEDGER_GENERATION = "attempt_ledger_generation"
    PRE_ACQUISITION_ATTESTATION = "pre_acquisition_attestation"
    SOURCE_REVISION_RECEIPT_PAYLOAD = "source_revision_receipt_payload"
    RECEIPT_COMMITMENT_ENVELOPE = "receipt_commitment_envelope"
    SOURCE_REVISION_SET_PAYLOAD = "source_revision_set_payload"
    ACQUISITION_CORE_GRAPH = "acquisition_core_graph"
    POST_ACQUISITION_EXECUTION_ATTESTATION = "post_acquisition_execution_attestation"
    COMPLETENESS_ATTESTATION_PAYLOAD = "completeness_attestation_payload"
    PASS_PROOF_BUNDLE_ORDINAL_1 = "pass_proof_bundle_ordinal_1"
    PASS_PROOF_BUNDLE_ORDINAL_2 = "pass_proof_bundle_ordinal_2"
    EXACT6_TERMINAL_DECISION = "exact6_terminal_decision"
    CUSTODY_DELETION_RECORD = "custody_deletion_record"
    PRE_MANAGEMENT_CLOSURE_TERMINAL_ARTIFACT_GRAPH = (
        "pre_management_closure_terminal_artifact_graph"
    )
    MANAGEMENT_DESCRIPTOR_CLOSURE_OBSERVATION = "management_descriptor_closure_observation"
    INTERNAL_RETENTION_REVIEW_PROOF_BUNDLE = "internal_retention_review_proof_bundle"
    OWNER_ONLY_RETENTION_BATCH_MANIFEST = "owner_only_retention_batch_manifest"
    OWNER_ONLY_RETENTION_BATCH_RECEIPT = "owner_only_retention_batch_receipt"


_ROLE_MAXIMUM_BYTES: Final[Mapping[RawArtifactRole, int]] = MappingProxyType(
    {
        RawArtifactRole.AUTHORITY_PROOF_BUNDLE: 16384,
        RawArtifactRole.TRANSITIVE_RUNTIME_INPUT_MANIFEST: 65536,
        RawArtifactRole.ONE_TIME_ATTEMPT_RESERVATION: 16384,
        RawArtifactRole.ATTEMPT_REGISTRY_GENERATION: 16384,
        RawArtifactRole.ATTEMPT_LEDGER_GENERATION: 16384,
        RawArtifactRole.PRE_ACQUISITION_ATTESTATION: 16384,
        RawArtifactRole.SOURCE_REVISION_RECEIPT_PAYLOAD: 65536,
        RawArtifactRole.RECEIPT_COMMITMENT_ENVELOPE: 4096,
        RawArtifactRole.SOURCE_REVISION_SET_PAYLOAD: 16384,
        RawArtifactRole.ACQUISITION_CORE_GRAPH: 16384,
        RawArtifactRole.POST_ACQUISITION_EXECUTION_ATTESTATION: 32768,
        RawArtifactRole.COMPLETENESS_ATTESTATION_PAYLOAD: 8192,
        RawArtifactRole.PASS_PROOF_BUNDLE_ORDINAL_1: 16384,
        RawArtifactRole.PASS_PROOF_BUNDLE_ORDINAL_2: 16384,
        RawArtifactRole.EXACT6_TERMINAL_DECISION: 32768,
        RawArtifactRole.CUSTODY_DELETION_RECORD: 8192,
        RawArtifactRole.PRE_MANAGEMENT_CLOSURE_TERMINAL_ARTIFACT_GRAPH: 16384,
        RawArtifactRole.MANAGEMENT_DESCRIPTOR_CLOSURE_OBSERVATION: 4096,
        RawArtifactRole.INTERNAL_RETENTION_REVIEW_PROOF_BUNDLE: 16384,
        RawArtifactRole.OWNER_ONLY_RETENTION_BATCH_MANIFEST: 65536,
        RawArtifactRole.OWNER_ONLY_RETENTION_BATCH_RECEIPT: 16384,
    }
)


class SourceLinkResourceErrorCode(StrEnum):
    """Stable, content-free failure codes for the raw preflight."""

    INVALID_ARGUMENT_TYPE = "invalid_argument_type"
    RAW_SIZE_OUT_OF_RANGE = "raw_size_out_of_range"
    UTF8_OR_BOM_INVALID = "utf8_or_bom_invalid"
    JSON_SYNTAX_INVALID = "json_syntax_invalid"
    JSON_DUPLICATE_KEY = "json_duplicate_key"
    JSON_FLOAT_FORBIDDEN = "json_float_forbidden"
    JSON_INTEGER_DIGITS_EXCEEDED = "json_integer_digits_exceeded"
    JSON_DEPTH_EXCEEDED = "json_depth_exceeded"
    JSON_NODE_COUNT_EXCEEDED = "json_node_count_exceeded"
    JSON_STRING_LENGTH_EXCEEDED = "json_string_length_exceeded"
    CANONICAL_BYTES_MISMATCH = "canonical_bytes_mismatch"


class SourceLinkResourceError(ValueError):
    """A path-free, source-value-free raw-resource preflight failure."""

    def __init__(self, code: SourceLinkResourceErrorCode) -> None:
        self.code = code
        super().__init__(f"source_reported_link_resource:{code.value}")


FrozenJson: TypeAlias = (
    None | bool | int | str | tuple["FrozenJson", ...] | Mapping[str, "FrozenJson"]
)

_CONSTRUCTION_TOKEN: Final = object()
_PARSE_FAILED: Final = object()
_NUMBER_RE: Final = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_SCANSTRING: Final[Any] = cast(Any, json.decoder).scanstring


@dataclass(frozen=True, slots=True, repr=False)
class PreflightedCanonicalResource:
    """An immutable in-process canonical-byte result, not a trusted handle."""

    role: RawArtifactRole
    canonical_size: int
    _raw: bytes = field(repr=False, compare=False)
    _value: FrozenJson = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        _token: object,
        role: RawArtifactRole,
        canonical_size: int,
        raw: bytes,
        value: FrozenJson,
    ) -> None:
        if _token is not _CONSTRUCTION_TOKEN:
            _fail(SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "canonical_size", canonical_size)
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_value", value)

    @property
    def raw_bytes(self) -> bytes:
        """Return caller-owned canonical bytes without adding an evidence claim."""

        return self._raw

    @property
    def value(self) -> FrozenJson:
        """Return a recursively immutable view of the parsed JSON value."""

        return self._value

    def __repr__(self) -> str:
        return (
            "PreflightedCanonicalResource("
            f"role={self.role.value!r}, canonical_size={self.canonical_size})"
        )


def _fail(code: SourceLinkResourceErrorCode) -> Never:
    raise SourceLinkResourceError(code)


def maximum_bytes_for_role(role: RawArtifactRole) -> int:
    """Return the closed raw-byte maximum for one exact role."""

    if type(role) is not RawArtifactRole:
        _fail(SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE)
    return _ROLE_MAXIMUM_BYTES[role]


def _decoded_string_length(value: str) -> int:
    """Count Unicode scalar values, treating one valid surrogate pair as one."""

    count = 0
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(value) or not 0xDC00 <= ord(value[index + 1]) <= 0xDFFF:
                _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
            index += 2
        elif 0xDC00 <= codepoint <= 0xDFFF:
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
        else:
            index += 1
        count += 1
    return count


class _JsonLimitScanner:
    """Validate JSON grammar and structural limits without materializing its tree."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._index = 0
        self._nodes = 0

    def scan(self) -> None:
        self._skip_whitespace()
        self._scan_value(depth=0)
        self._skip_whitespace()
        if self._index != len(self._text):
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)

    def _skip_whitespace(self) -> None:
        while self._index < len(self._text) and self._text[self._index] in " \t\r\n":
            self._index += 1

    def _add_node(self, depth: int) -> None:
        if depth > MAXIMUM_NESTING_DEPTH:
            _fail(SourceLinkResourceErrorCode.JSON_DEPTH_EXCEEDED)
        self._nodes += 1
        if self._nodes > MAXIMUM_NODE_COUNT:
            _fail(SourceLinkResourceErrorCode.JSON_NODE_COUNT_EXCEEDED)

    def _scan_value(self, *, depth: int) -> None:
        self._add_node(depth)
        if self._index >= len(self._text):
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
        character = self._text[self._index]
        if character == "{":
            self._scan_object(depth=depth)
        elif character == "[":
            self._scan_array(depth=depth)
        elif character == '"':
            self._scan_string()
        elif any(
            self._text.startswith(token, self._index) for token in ("NaN", "Infinity", "-Infinity")
        ):
            _fail(SourceLinkResourceErrorCode.JSON_FLOAT_FORBIDDEN)
        elif character in "-0123456789":
            self._scan_number()
        elif self._text.startswith("true", self._index):
            self._index += 4
        elif self._text.startswith("false", self._index):
            self._index += 5
        elif self._text.startswith("null", self._index):
            self._index += 4
        else:
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)

    def _scan_string(self) -> str:
        scanned: tuple[str, int] | None = None
        try:
            value, end = cast(tuple[str, int], _SCANSTRING(self._text, self._index + 1, True))
            scanned = (value, end)
        except (OverflowError, UnicodeDecodeError, ValueError):
            pass
        if scanned is None:
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
        value, end = scanned
        if _decoded_string_length(value) > MAXIMUM_STRING_LENGTH:
            _fail(SourceLinkResourceErrorCode.JSON_STRING_LENGTH_EXCEEDED)
        self._index = end
        return value

    def _scan_object(self, *, depth: int) -> None:
        self._index += 1
        self._skip_whitespace()
        if self._consume("}"):
            return
        keys: set[str] = set()
        while True:
            if self._index >= len(self._text) or self._text[self._index] != '"':
                _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
            key = self._scan_string()
            if key in keys:
                _fail(SourceLinkResourceErrorCode.JSON_DUPLICATE_KEY)
            keys.add(key)
            self._skip_whitespace()
            if not self._consume(":"):
                _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
            self._skip_whitespace()
            self._scan_value(depth=depth + 1)
            self._skip_whitespace()
            if self._consume("}"):
                return
            if not self._consume(","):
                _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
            self._skip_whitespace()

    def _scan_array(self, *, depth: int) -> None:
        self._index += 1
        self._skip_whitespace()
        if self._consume("]"):
            return
        while True:
            self._scan_value(depth=depth + 1)
            self._skip_whitespace()
            if self._consume("]"):
                return
            if not self._consume(","):
                _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
            self._skip_whitespace()

    def _scan_number(self) -> None:
        match = _NUMBER_RE.match(self._text, self._index)
        if match is None:
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
        token = match.group(0)
        self._index = match.end()
        if self._index < len(self._text) and self._text[self._index] not in " \t\r\n,]}":
            _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
        if "." in token or "e" in token.lower():
            _fail(SourceLinkResourceErrorCode.JSON_FLOAT_FORBIDDEN)
        if len(token.removeprefix("-")) > MAXIMUM_INTEGER_DIGITS:
            _fail(SourceLinkResourceErrorCode.JSON_INTEGER_DIGITS_EXCEEDED)

    def _consume(self, expected: str) -> bool:
        if self._index < len(self._text) and self._text[self._index] == expected:
            self._index += 1
            return True
        return False


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail(SourceLinkResourceErrorCode.JSON_DUPLICATE_KEY)
        value[key] = child
    return value


def _reject_float(_: str) -> Never:
    _fail(SourceLinkResourceErrorCode.JSON_FLOAT_FORBIDDEN)


def _parse_integer(token: str) -> int:
    if len(token.removeprefix("-")) > MAXIMUM_INTEGER_DIGITS:
        _fail(SourceLinkResourceErrorCode.JSON_INTEGER_DIGITS_EXCEEDED)
    return int(token)


def _deep_freeze(value: Any) -> FrozenJson:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, list):
        return tuple(_deep_freeze(child) for child in value)
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(child) for key, child in value.items()})
    _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)


def preflight_canonical_resource(
    raw: bytes,
    *,
    role: RawArtifactRole,
) -> PreflightedCanonicalResource:
    """Apply steps 1-5 of the frozen raw-resource verification order.

    Measurement rules are fixed here as follows: root depth is zero; every JSON
    value or container counts as one node while object keys do not; key and
    string-value length counts decoded Unicode scalar values; and an integer's
    optional minus sign is excluded from its digit count.
    """

    if type(raw) is not bytes or type(role) is not RawArtifactRole:
        _fail(SourceLinkResourceErrorCode.INVALID_ARGUMENT_TYPE)
    maximum_bytes = _ROLE_MAXIMUM_BYTES[role]
    if not raw or len(raw) > maximum_bytes:
        _fail(SourceLinkResourceErrorCode.RAW_SIZE_OUT_OF_RANGE)
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail(SourceLinkResourceErrorCode.UTF8_OR_BOM_INVALID)
    text: str | None = None
    with suppress(UnicodeDecodeError):
        text = raw.decode("utf-8", errors="strict")
    if text is None:
        _fail(SourceLinkResourceErrorCode.UTF8_OR_BOM_INVALID)
    value: Any = _PARSE_FAILED
    try:
        _JsonLimitScanner(text).scan()
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_float,
            parse_float=_reject_float,
            parse_int=_parse_integer,
        )
    except SourceLinkResourceError:
        raise
    except (json.JSONDecodeError, OverflowError, RecursionError, UnicodeError, ValueError):
        pass
    if value is _PARSE_FAILED:
        _fail(SourceLinkResourceErrorCode.JSON_SYNTAX_INVALID)
    canonical: bytes | None = None
    with suppress(OverflowError, RecursionError, TypeError, UnicodeError, ValueError):
        canonical = encode_json(value)
    if canonical is None:
        _fail(SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH)
    if canonical != raw:
        _fail(SourceLinkResourceErrorCode.CANONICAL_BYTES_MISMATCH)
    return PreflightedCanonicalResource(
        _token=_CONSTRUCTION_TOKEN,
        role=role,
        canonical_size=len(raw),
        raw=raw,
        value=_deep_freeze(value),
    )
