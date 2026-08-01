"""Fail-closed loading of the frozen source-reported-link static resources.

The loader in this module resolves only installed, exact-byte package data.  It
does not accept a caller-selected path or digest, complete the future eight-way
binding set, or consume any dynamic artifact.  Its result records the six
static identities that can be established without source access.  Two legacy
V1 resources predate the canonical key-order profile; their frozen raw hashes
remain authoritative and they are never rewritten or treated as canonical.
That conflict fixes the snapshot as ineligible for the frozen strict V1
resolver; two later runtime identities alone cannot promote it.
Here, "source-free" means independent of a repository checkout.  Package-local
hash and schema agreement does not authenticate the package, establish rights
or external truth, grant authority, validate a runtime, or permit source
access.
"""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import os
import stat
import sys
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal, Never

from .io import encode_json

_READ_CHUNK_BYTES: Final = 64 * 1024
_STATIC_JSON_MAX_DEPTH: Final = 16
_STATIC_JSON_MAX_NODES: Final = 8192
_STATIC_JSON_MAX_STRING_LENGTH: Final = 2048
_STATIC_JSON_MAX_INTEGER_DIGITS: Final = 10
_STATIC_RESOURCE_COUNT: Final = 14
_STATIC_TOTAL_BYTES: Final = 1_034_956

_ORDERED_ROSTER_DOMAIN: Final = "indusbench:source-reported-link:ordered-inspection-roster:v1"
_SCHEMA_SET_DOMAIN: Final = "indusbench:source-reported-link:artifact-schema-set:v1"
_CANONICAL_JSON_PROFILE_ID: Final = "indusbench-io-encode-json-v1"
_EXPECTED_ARTIFACT_SCHEMA_SET_SHA256: Final = (
    "sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f"
)
_EXPECTED_ORDERED_SOURCE_ROSTER_SHA256: Final = (
    "sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f"
)
_MISSING_BINDING_FIELDS: Final = (
    "runtime_distribution_sha256",
    "transitive_runtime_input_manifest_sha256",
)
_STRICT_V1_RESOLVER_BLOCKERS: Final = (
    "source_registry_noncanonical_raw_bytes",
    "source_registry_schema_noncanonical_raw_bytes",
)
_ALLOWED_SCHEMA_FORMATS: Final = frozenset({"date-time", "uri"})
_FORMAT_CANARIES: Final[Mapping[str, tuple[str, tuple[str, ...]]]] = MappingProxyType(
    {
        "date-time": (
            "2026-08-01T04:14:13+09:00",
            ("not-a-date-time", "2026-08-01T04:14:13"),
        ),
        "uri": ("https://example.invalid/static", ("not a uri",)),
    }
)


class SourceLinkStaticErrorCode(StrEnum):
    """Stable, path-free error codes emitted by the static loader."""

    INVALID_ARGUMENT_TYPE = "invalid_argument_type"
    PLATFORM_UNSUPPORTED = "platform_unsupported"
    PACKAGE_LAYOUT_UNSUPPORTED = "package_layout_unsupported"
    ROOT_BOUNDARY_INVALID = "root_boundary_invalid"
    DIRECTORY_BOUNDARY_INVALID = "directory_boundary_invalid"
    RESOURCE_BOUNDARY_INVALID = "resource_boundary_invalid"
    RESOURCE_SIZE_MISMATCH = "resource_size_mismatch"
    RESOURCE_HASH_MISMATCH = "resource_hash_mismatch"
    RESOURCE_CHANGED = "resource_changed"
    JSON_INVALID = "json_invalid"
    CANONICAL_BYTES_MISMATCH = "canonical_bytes_mismatch"
    SCHEMA_DEPENDENCY_MISSING = "schema_dependency_missing"
    SCHEMA_INVALID = "schema_invalid"
    SCHEMA_REFERENCE_FORBIDDEN = "schema_reference_forbidden"
    SCHEMA_FORMAT_FORBIDDEN = "schema_format_forbidden"
    SCHEMA_FORMAT_CHECKER_INVALID = "schema_format_checker_invalid"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    CROSS_BINDING_MISMATCH = "cross_binding_mismatch"
    DIGEST_MISMATCH = "digest_mismatch"


class SourceLinkStaticError(ValueError):
    """A static-resource failure with no path, value, or validator detail."""

    def __init__(self, code: SourceLinkStaticErrorCode) -> None:
        self.code = code
        super().__init__(f"source_reported_link_static:{code.value}")


class _ResourceKey(StrEnum):
    PRESELECTION_REGISTRY = "preselection_registry"
    SOURCE_REGISTRY = "source_registry"
    SOURCE_POLICY = "source_policy"
    SOURCE_CONTRACT = "source_contract"
    CUSTODY_CONTRACT = "custody_contract"
    PRESELECTION_SCHEMA = "preselection_schema"
    SOURCE_REGISTRY_SCHEMA = "source_registry_schema"
    SOURCE_POLICY_SCHEMA = "source_policy_schema"
    SOURCE_CONTRACT_SCHEMA = "source_contract_schema"
    CUSTODY_CONTRACT_SCHEMA = "custody_contract_schema"
    REVISION_RECEIPT_SCHEMA = "revision_receipt_schema"
    RECEIPT_ENVELOPE_SCHEMA = "receipt_envelope_schema"
    REVISION_SET_SCHEMA = "revision_set_schema"
    COMPLETENESS_SCHEMA = "completeness_schema"


# Re-freezing these two exact V1 byte resources would invalidate frozen parent
# commitments.  They retain every strict decode check except encode_json byte
# equality, and the decoded/re-encoded bytes are never adopted or returned.
_LEGACY_EXACT_BYTE_JSON_KEYS: Final = frozenset(
    {
        _ResourceKey.SOURCE_REGISTRY,
        _ResourceKey.SOURCE_REGISTRY_SCHEMA,
    }
)


@dataclass(frozen=True, slots=True)
class _StaticResourceSpec:
    key: _ResourceKey
    directory: str
    name: str
    size: int
    sha256: str

    @property
    def package_path(self) -> str:
        return f"{self.directory}/{self.name}"

    @property
    def tagged_sha256(self) -> str:
        return f"sha256:{self.sha256}"


_RESOURCE_SPECS: Final = (
    _StaticResourceSpec(
        _ResourceKey.PRESELECTION_REGISTRY,
        "registry",
        "chanhu-daro-helsinki-gate-v1.json",
        6955,
        "43c0fae1a8558fbffeb062725e401e0c3c1de570e5f8f7eef610ca2616cbfb3d",
    ),
    _StaticResourceSpec(
        _ResourceKey.SOURCE_REGISTRY,
        "registry",
        "sources.json",
        43235,
        "e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584",
    ),
    _StaticResourceSpec(
        _ResourceKey.SOURCE_POLICY,
        "registry",
        "source-reported-link-policy-v1.json",
        7967,
        "c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90",
    ),
    _StaticResourceSpec(
        _ResourceKey.SOURCE_CONTRACT,
        "registry",
        "source-reported-link-source-contract-v1.json",
        29059,
        "e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f",
    ),
    _StaticResourceSpec(
        _ResourceKey.CUSTODY_CONTRACT,
        "registry",
        "source-reported-link-protected-ephemeral-custody-contract-v1.json",
        426824,
        "917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914",
    ),
    _StaticResourceSpec(
        _ResourceKey.PRESELECTION_SCHEMA,
        "schemas",
        "context-source-link-gate.schema.json",
        9216,
        "72109818eb55aca008b0f34b1d6c627efd0e38bdbaff8c500cb3c60dc74e3002",
    ),
    _StaticResourceSpec(
        _ResourceKey.SOURCE_REGISTRY_SCHEMA,
        "schemas",
        "source-registry.schema.json",
        8295,
        "6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3",
    ),
    _StaticResourceSpec(
        _ResourceKey.SOURCE_POLICY_SCHEMA,
        "schemas",
        "source-reported-link-policy.schema.json",
        8589,
        "d951541892bb6a5ef092d44e9a5564da2261f960e52e3e84a95ecd5ef8e61aff",
    ),
    _StaticResourceSpec(
        _ResourceKey.SOURCE_CONTRACT_SCHEMA,
        "schemas",
        "source-reported-link-source-contract.schema.json",
        30752,
        "e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78",
    ),
    _StaticResourceSpec(
        _ResourceKey.CUSTODY_CONTRACT_SCHEMA,
        "schemas",
        "source-reported-link-protected-ephemeral-custody-contract.schema.json",
        440116,
        "5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b",
    ),
    _StaticResourceSpec(
        _ResourceKey.REVISION_RECEIPT_SCHEMA,
        "schemas",
        "source-reported-link-source-revision-receipt.schema.json",
        9316,
        "6d0451ed9471315b11689e6cabe8bf7b15e6b5d31f0064d5a364c9ac73789375",
    ),
    _StaticResourceSpec(
        _ResourceKey.RECEIPT_ENVELOPE_SCHEMA,
        "schemas",
        "source-reported-link-receipt-commitment-envelope.schema.json",
        2546,
        "f4e316c5542c5ea9c57a91fc5006a10550c2dbbd08436e165d997e265570c2d4",
    ),
    _StaticResourceSpec(
        _ResourceKey.REVISION_SET_SCHEMA,
        "schemas",
        "source-reported-link-source-revision-set.schema.json",
        6459,
        "15d64ee72ea7a147bcde22a2c28330b67c1eae4d299e272296a53a2ef25d17bb",
    ),
    _StaticResourceSpec(
        _ResourceKey.COMPLETENESS_SCHEMA,
        "schemas",
        "source-reported-link-completeness-attestation.schema.json",
        5627,
        "a8ae0f32fbda8cd1bb7e29db3d3444ec0659ffa9f9818ea85331288d0f018c02",
    ),
)
_SPEC_BY_KEY: Final[Mapping[_ResourceKey, _StaticResourceSpec]] = MappingProxyType(
    {spec.key: spec for spec in _RESOURCE_SPECS}
)
_SCHEMA_KEYS: Final = (
    _ResourceKey.PRESELECTION_SCHEMA,
    _ResourceKey.SOURCE_REGISTRY_SCHEMA,
    _ResourceKey.SOURCE_POLICY_SCHEMA,
    _ResourceKey.SOURCE_CONTRACT_SCHEMA,
    _ResourceKey.CUSTODY_CONTRACT_SCHEMA,
    _ResourceKey.REVISION_RECEIPT_SCHEMA,
    _ResourceKey.RECEIPT_ENVELOPE_SCHEMA,
    _ResourceKey.REVISION_SET_SCHEMA,
    _ResourceKey.COMPLETENESS_SCHEMA,
)
_INSTANCE_SCHEMA_PAIRS: Final = (
    (_ResourceKey.PRESELECTION_REGISTRY, _ResourceKey.PRESELECTION_SCHEMA),
    (_ResourceKey.SOURCE_REGISTRY, _ResourceKey.SOURCE_REGISTRY_SCHEMA),
    (_ResourceKey.SOURCE_POLICY, _ResourceKey.SOURCE_POLICY_SCHEMA),
    (_ResourceKey.SOURCE_CONTRACT, _ResourceKey.SOURCE_CONTRACT_SCHEMA),
    (_ResourceKey.CUSTODY_CONTRACT, _ResourceKey.CUSTODY_CONTRACT_SCHEMA),
)
_ARTIFACT_SCHEMA_KEYS: Final = (
    _ResourceKey.REVISION_RECEIPT_SCHEMA,
    _ResourceKey.RECEIPT_ENVELOPE_SCHEMA,
    _ResourceKey.REVISION_SET_SCHEMA,
    _ResourceKey.COMPLETENESS_SCHEMA,
)

_SNAPSHOT_CONSTRUCTION_TOKEN: Final = object()


@dataclass(frozen=True, slots=True, repr=False, init=False)
class SourceFreeStaticSnapshot:
    """Immutable package-local snapshot that is ineligible for strict V1."""

    artifact_schema_set_sha256: str
    custody_contract_sha256: str
    ordered_source_roster_sha256: str
    source_contract_sha256: str
    source_policy_sha256: str
    source_registry_sha256: str
    missing_binding_fields: tuple[str, str]
    strict_v1_resolver_eligible: Literal[False]
    strict_v1_resolver_blockers: tuple[str, str]
    resource_count: int

    def __init__(
        self,
        *,
        _token: object,
        artifact_schema_set_sha256: str,
        custody_contract_sha256: str,
        ordered_source_roster_sha256: str,
        source_contract_sha256: str,
        source_policy_sha256: str,
        source_registry_sha256: str,
        missing_binding_fields: tuple[str, str],
        resource_count: int,
    ) -> None:
        if _token is not _SNAPSHOT_CONSTRUCTION_TOKEN:
            _fail(SourceLinkStaticErrorCode.INVALID_ARGUMENT_TYPE)
        object.__setattr__(self, "artifact_schema_set_sha256", artifact_schema_set_sha256)
        object.__setattr__(self, "custody_contract_sha256", custody_contract_sha256)
        object.__setattr__(self, "ordered_source_roster_sha256", ordered_source_roster_sha256)
        object.__setattr__(self, "source_contract_sha256", source_contract_sha256)
        object.__setattr__(self, "source_policy_sha256", source_policy_sha256)
        object.__setattr__(self, "source_registry_sha256", source_registry_sha256)
        object.__setattr__(self, "missing_binding_fields", missing_binding_fields)
        object.__setattr__(self, "strict_v1_resolver_eligible", False)
        object.__setattr__(
            self,
            "strict_v1_resolver_blockers",
            _STRICT_V1_RESOLVER_BLOCKERS,
        )
        object.__setattr__(self, "resource_count", resource_count)

    def __repr__(self) -> str:
        return (
            "SourceFreeStaticSnapshot("
            f"resource_count={self.resource_count}, "
            f"missing_binding_fields={self.missing_binding_fields!r}, "
            "strict_v1_resolver_eligible=False)"
        )


class _StaticJsonViolation(ValueError):
    pass


def _fail(code: SourceLinkStaticErrorCode) -> Never:
    raise SourceLinkStaticError(code) from None


def _close_descriptor(descriptor: int) -> bool:
    try:
        os.close(descriptor)
    except OSError:
        return False
    return True


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_supported_platform() -> None:
    constants = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    if (
        os.name != "posix"
        or sys.platform not in {"darwin", "linux"}
        or not hasattr(os, "geteuid")
        or any(not getattr(os, name, 0) for name in constants)
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
        or os.stat not in os.supports_follow_symlinks
    ):
        _fail(SourceLinkStaticErrorCode.PLATFORM_UNSUPPORTED)


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _allowed_owner(metadata: os.stat_result) -> bool:
    return metadata.st_uid in {0, os.geteuid()}


def _valid_directory(metadata: os.stat_result, *, device: int | None = None) -> bool:
    mode = metadata.st_mode
    return (
        stat.S_ISDIR(mode)
        and metadata.st_nlink >= 1
        and _allowed_owner(metadata)
        and not mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
        and not mode & 0o022
        and mode & 0o500 == 0o500
        and (device is None or metadata.st_dev == device)
    )


def _valid_resource_file(
    metadata: os.stat_result,
    *,
    device: int,
) -> bool:
    mode = metadata.st_mode
    return (
        stat.S_ISREG(mode)
        and metadata.st_nlink == 1
        and metadata.st_dev == device
        and _allowed_owner(metadata)
        and not mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
        and not mode & (0o022 | 0o111)
        and bool(mode & 0o400)
    )


def _validate_root_argument(root: Path) -> Path:
    if not isinstance(root, Path):
        _fail(SourceLinkStaticErrorCode.INVALID_ARGUMENT_TYPE)
    argument_failed = False
    try:
        raw = os.fspath(root)
        encoded = os.fsencode(raw)
    except (TypeError, ValueError, UnicodeError):
        argument_failed = True
    if argument_failed:
        _fail(SourceLinkStaticErrorCode.INVALID_ARGUMENT_TYPE)
    if (
        type(raw) is not str
        or not raw
        or not encoded
        or b"\0" in encoded
        or not root.is_absolute()
        or root.anchor != "/"
        or root == Path("/")
        or str(root) != raw
        or root.name != "indusbench"
        or any(part in {"", ".", ".."} for part in raw.split("/")[1:])
    ):
        _fail(SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED)
    return root


def _open_child_directory(
    parent_descriptor: int,
    name: str,
    *,
    device: int,
) -> tuple[int, tuple[int, ...]]:
    descriptor: int | None = None
    namespace_failed = False
    try:
        namespace = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError:
        namespace_failed = True
    if namespace_failed:
        _fail(SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID)
    if not _valid_directory(namespace, device=device):
        _fail(SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID)

    open_failed = False
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
    except OSError:
        open_failed = True
    if open_failed:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        _fail(SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID)
    if descriptor is None:
        _fail(SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID)
    if _fingerprint(opened) != _fingerprint(namespace) or not _valid_directory(
        opened, device=device
    ):
        with suppress(OSError):
            os.close(descriptor)
        _fail(SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID)
    return descriptor, _fingerprint(opened)


def _read_exact_resource(
    parent_descriptor: int,
    spec: _StaticResourceSpec,
    *,
    device: int,
) -> bytes:
    descriptor: int | None = None
    namespace_failed = False
    try:
        parent_before = os.fstat(parent_descriptor)
        namespace_before = os.stat(
            spec.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except OSError:
        namespace_failed = True
    if namespace_failed:
        _fail(SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID)
    if not _valid_resource_file(namespace_before, device=device):
        _fail(SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID)
    if namespace_before.st_size != spec.size:
        _fail(SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH)

    read_failed = False
    try:
        descriptor = os.open(spec.name, _file_flags(), dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if _fingerprint(opened) != _fingerprint(namespace_before) or not _valid_resource_file(
            opened, device=device
        ):
            _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
        chunks: list[bytes] = []
        byte_count = 0
        while True:
            chunk = os.read(
                descriptor,
                min(_READ_CHUNK_BYTES, spec.size + 1 - byte_count),
            )
            if not chunk:
                break
            chunks.append(chunk)
            byte_count += len(chunk)
            if byte_count > spec.size:
                _fail(SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    except SourceLinkStaticError:
        raise
    except OSError:
        read_failed = True
    finally:
        close_failed = False
        if descriptor is not None:
            close_failed = not _close_descriptor(descriptor)
    if close_failed:
        _fail(SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID)
    if read_failed:
        _fail(SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID)

    if len(raw) != spec.size:
        _fail(SourceLinkStaticErrorCode.RESOURCE_SIZE_MISMATCH)
    if _fingerprint(after) != _fingerprint(opened):
        _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
    revalidation_failed = False
    try:
        namespace_after = os.stat(
            spec.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        parent_after = os.fstat(parent_descriptor)
    except OSError:
        revalidation_failed = True
    if revalidation_failed:
        _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
    if _fingerprint(namespace_after) != _fingerprint(opened) or _fingerprint(
        parent_after
    ) != _fingerprint(parent_before):
        _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
    if hashlib.sha256(raw).hexdigest() != spec.sha256:
        _fail(SourceLinkStaticErrorCode.RESOURCE_HASH_MISMATCH)
    return raw


def _read_static_package(root: Path) -> dict[_ResourceKey, bytes]:
    _require_supported_platform()
    root = _validate_root_argument(root)
    parent_descriptor: int | None = None
    root_descriptor: int | None = None
    registry_descriptor: int | None = None
    schemas_descriptor: int | None = None
    try:
        parent_open_failed = False
        try:
            parent_descriptor = os.open(root.parent, _directory_flags())
            parent_opened = os.fstat(parent_descriptor)
        except OSError:
            parent_open_failed = True
        if parent_open_failed:
            _fail(SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID)
        if parent_descriptor is None:
            _fail(SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID)
        if not _valid_directory(parent_opened):
            _fail(SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID)
        parent_fingerprint = _fingerprint(parent_opened)

        root_open_failed = False
        try:
            root_namespace = os.stat(
                root.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            root_descriptor = os.open(root.name, _directory_flags(), dir_fd=parent_descriptor)
            root_opened = os.fstat(root_descriptor)
        except OSError:
            root_open_failed = True
        if root_open_failed:
            _fail(SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID)
        if root_descriptor is None:
            _fail(SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID)
        if _fingerprint(root_namespace) != _fingerprint(root_opened) or not _valid_directory(
            root_opened, device=parent_opened.st_dev
        ):
            _fail(SourceLinkStaticErrorCode.ROOT_BOUNDARY_INVALID)
        root_fingerprint = _fingerprint(root_opened)
        device = root_opened.st_dev

        registry_descriptor, registry_fingerprint = _open_child_directory(
            root_descriptor,
            "registry",
            device=device,
        )
        schemas_descriptor, schemas_fingerprint = _open_child_directory(
            root_descriptor,
            "schemas",
            device=device,
        )
        if registry_descriptor is None or schemas_descriptor is None:
            _fail(SourceLinkStaticErrorCode.DIRECTORY_BOUNDARY_INVALID)
        directory_descriptors = {
            "registry": registry_descriptor,
            "schemas": schemas_descriptor,
        }
        raw_resources: dict[_ResourceKey, bytes] = {}
        for spec in _RESOURCE_SPECS:
            raw_resources[spec.key] = _read_exact_resource(
                directory_descriptors[spec.directory],
                spec,
                device=device,
            )

        fingerprint_failed = False
        try:
            directory_fingerprints_unchanged = (
                _fingerprint(os.fstat(registry_descriptor)) == registry_fingerprint
                and _fingerprint(os.fstat(schemas_descriptor)) == schemas_fingerprint
                and _fingerprint(os.fstat(root_descriptor)) == root_fingerprint
                and _fingerprint(os.fstat(parent_descriptor)) == parent_fingerprint
            )
        except OSError:
            fingerprint_failed = True
        if fingerprint_failed:
            _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
        if not directory_fingerprints_unchanged:
            _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
        namespace_revalidation_failed = False
        try:
            registry_namespace = os.stat("registry", dir_fd=root_descriptor, follow_symlinks=False)
            schemas_namespace = os.stat("schemas", dir_fd=root_descriptor, follow_symlinks=False)
            root_namespace_after = os.stat(
                root.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError:
            namespace_revalidation_failed = True
        if namespace_revalidation_failed:
            _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
        if (
            _fingerprint(registry_namespace) != registry_fingerprint
            or _fingerprint(schemas_namespace) != schemas_fingerprint
            or _fingerprint(root_namespace_after) != root_fingerprint
        ):
            _fail(SourceLinkStaticErrorCode.RESOURCE_CHANGED)
        return raw_resources
    finally:
        close_failed = False
        for descriptor in (
            schemas_descriptor,
            registry_descriptor,
            root_descriptor,
            parent_descriptor,
        ):
            if descriptor is not None and not _close_descriptor(descriptor):
                close_failed = True
        if close_failed:
            _fail(SourceLinkStaticErrorCode.RESOURCE_BOUNDARY_INVALID)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StaticJsonViolation
        result[key] = value
    return result


def _reject_float(_value: str) -> Never:
    raise _StaticJsonViolation


def _parse_integer(value: str) -> int:
    digits = value[1:] if value.startswith("-") else value
    if len(digits) > _STATIC_JSON_MAX_INTEGER_DIGITS:
        raise _StaticJsonViolation
    return int(value)


def _check_static_json_complexity(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    node_count = 0
    while stack:
        current, depth = stack.pop()
        node_count += 1
        if node_count > _STATIC_JSON_MAX_NODES or depth > _STATIC_JSON_MAX_DEPTH:
            _fail(SourceLinkStaticErrorCode.JSON_INVALID)
        if isinstance(current, dict):
            for key, child in current.items():
                if len(key) > _STATIC_JSON_MAX_STRING_LENGTH:
                    _fail(SourceLinkStaticErrorCode.JSON_INVALID)
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str):
            if len(current) > _STATIC_JSON_MAX_STRING_LENGTH:
                _fail(SourceLinkStaticErrorCode.JSON_INVALID)
        elif current is None or type(current) in {bool, int}:
            continue
        else:
            _fail(SourceLinkStaticErrorCode.JSON_INVALID)


def _decode_static_resource(raw: bytes, key: _ResourceKey) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail(SourceLinkStaticErrorCode.JSON_INVALID)
    decode_failed = False
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_float,
            parse_float=_reject_float,
            parse_int=_parse_integer,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
        _StaticJsonViolation,
        ValueError,
    ):
        decode_failed = True
    if decode_failed:
        _fail(SourceLinkStaticErrorCode.JSON_INVALID)
    _check_static_json_complexity(value)
    encode_failed = False
    try:
        canonical = encode_json(value)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        encode_failed = True
    if encode_failed:
        _fail(SourceLinkStaticErrorCode.JSON_INVALID)
    if key in _LEGACY_EXACT_BYTE_JSON_KEYS:
        spec = _SPEC_BY_KEY[key]
        if len(raw) != spec.size or hashlib.sha256(raw).hexdigest() != spec.sha256:
            _fail(SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH)
    elif canonical != raw:
        _fail(SourceLinkStaticErrorCode.CANONICAL_BYTES_MISMATCH)
    return value


def _require_object(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH)
    return value


def _inspect_schema_keywords(schema: dict[str, Any]) -> None:
    stack: list[Any] = [schema]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                if key == "$ref" and (type(child) is not str or not child.startswith("#/")):
                    _fail(SourceLinkStaticErrorCode.SCHEMA_REFERENCE_FORBIDDEN)
                if key == "format" and (
                    type(child) is not str or child not in _ALLOWED_SCHEMA_FORMATS
                ):
                    _fail(SourceLinkStaticErrorCode.SCHEMA_FORMAT_FORBIDDEN)
                stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)


def _validate_schemas_and_instances(values: dict[_ResourceKey, Any]) -> None:
    dependency_missing = False
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError
    except ImportError:
        dependency_missing = True
    if dependency_missing:
        _fail(SourceLinkStaticErrorCode.SCHEMA_DEPENDENCY_MISSING)

    format_checker_failed = False
    try:
        checker = FormatChecker()
        for name, (valid, invalid_values) in _FORMAT_CANARIES.items():
            if not checker.conforms(valid, name) or any(
                checker.conforms(invalid, name) for invalid in invalid_values
            ):
                _fail(SourceLinkStaticErrorCode.SCHEMA_FORMAT_CHECKER_INVALID)
    except SourceLinkStaticError:
        raise
    except Exception:
        format_checker_failed = True
    if format_checker_failed:
        _fail(SourceLinkStaticErrorCode.SCHEMA_FORMAT_CHECKER_INVALID)

    validators: dict[_ResourceKey, Any] = {}
    for key in _SCHEMA_KEYS:
        schema = _require_object(values[key])
        _inspect_schema_keywords(schema)
        if (
            schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
            or schema.get("$id") != _SPEC_BY_KEY[key].name
        ):
            _fail(SourceLinkStaticErrorCode.SCHEMA_INVALID)
        schema_failed = False
        try:
            Draft202012Validator.check_schema(schema)
            validators[key] = Draft202012Validator(schema, format_checker=checker)
        except SchemaError:
            schema_failed = True
        except Exception:
            schema_failed = True
        if schema_failed:
            _fail(SourceLinkStaticErrorCode.SCHEMA_INVALID)

    for instance_key, schema_key in _INSTANCE_SCHEMA_PAIRS:
        validation_failed = False
        try:
            error = next(validators[schema_key].iter_errors(values[instance_key]), None)
        except Exception:
            validation_failed = True
        if validation_failed:
            _fail(SourceLinkStaticErrorCode.SCHEMA_VALIDATION_FAILED)
        if error is not None:
            _fail(SourceLinkStaticErrorCode.SCHEMA_VALIDATION_FAILED)


def _tagged_digest(domain: str, payload: Any) -> str:
    encode_failed = False
    try:
        framed = domain.encode("utf-8") + b"\0" + encode_json(payload)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        encode_failed = True
    if encode_failed:
        _fail(SourceLinkStaticErrorCode.DIGEST_MISMATCH)
    return "sha256:" + hashlib.sha256(framed).hexdigest()


def _expected_tasks(preselection: dict[str, Any]) -> list[dict[str, Any]]:
    binding_failed = False
    try:
        rows = preselection["links"]
        if type(rows) is not list:
            raise TypeError
        tasks: list[dict[str, Any]] = []
        for index, row_value in enumerate(rows):
            row = _require_object(row_value)
            identifiers = row["identifiers"]
            if type(identifiers) is not list or len(identifiers) != 3:
                raise TypeError
            mackay = _require_object(identifiers[0])
            official = _require_object(identifiers[1])
            accession = _require_object(identifiers[2])
            tasks.append(
                {
                    "collision_group": row["collision_group"],
                    "index": index,
                    "link_id": row["link_id"],
                    "mackay_locator": {
                        "identifier": mackay["identifier"],
                        "identifier_namespace": mackay["identifier_namespace"],
                        "resource_id": "source-resource-v1:mackay-report",
                    },
                    "penn_locators": [
                        {
                            "identifier": official["identifier"],
                            "identifier_namespace": official["identifier_namespace"],
                        },
                        {
                            "identifier": accession["identifier"],
                            "identifier_namespace": accession["identifier_namespace"],
                        },
                    ],
                    "penn_resource_id": (
                        f"source-resource-v1:penn-object-{official['identifier']}"
                    ),
                    "role": row["role"],
                    "unresolved_axis": row["unresolved_axis"],
                }
            )
        return tasks
    except SourceLinkStaticError:
        raise
    except (KeyError, IndexError, TypeError):
        binding_failed = True
    if binding_failed:
        _fail(SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH)
    _fail(SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH)


def _binding_entry(spec: _StaticResourceSpec, identifier: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "sha256": spec.tagged_sha256,
        "size": spec.size,
    }


def _verify_cross_bindings(values: dict[_ResourceKey, Any]) -> tuple[str, str]:
    preselection = _require_object(values[_ResourceKey.PRESELECTION_REGISTRY])
    sources = _require_object(values[_ResourceKey.SOURCE_REGISTRY])
    policy = _require_object(values[_ResourceKey.SOURCE_POLICY])
    source_contract = _require_object(values[_ResourceKey.SOURCE_CONTRACT])
    custody = _require_object(values[_ResourceKey.CUSTODY_CONTRACT])
    binding_failed = False
    try:
        if len(_RESOURCE_SPECS) != _STATIC_RESOURCE_COUNT or len(_SPEC_BY_KEY) != len(
            _RESOURCE_SPECS
        ):
            raise ValueError
        if sum(spec.size for spec in _RESOURCE_SPECS) != _STATIC_TOTAL_BYTES:
            raise ValueError

        link_ids = [row["link_id"] for row in preselection["links"]]
        policy_parent = policy["parent"]
        preselection_spec = _SPEC_BY_KEY[_ResourceKey.PRESELECTION_REGISTRY]
        preselection_schema_spec = _SPEC_BY_KEY[_ResourceKey.PRESELECTION_SCHEMA]
        if policy_parent["ordered_link_ids"] != link_ids:
            raise ValueError
        if policy_parent["registry"] != {
            "id": preselection["registry_id"],
            "sha256": preselection_spec.sha256,
            "size": preselection_spec.size,
        }:
            raise ValueError
        if policy_parent["schema"] != {
            "id": preselection_schema_spec.name,
            "sha256": preselection_schema_spec.sha256,
            "size": preselection_schema_spec.size,
        }:
            raise ValueError

        expected_tasks = _expected_tasks(preselection)
        expected_slots = [
            {
                "collision_group": task["collision_group"],
                "index": task["index"],
                "link_id": task["link_id"],
                "role": task["role"],
                "unresolved_axis": task["unresolved_axis"],
            }
            for task in expected_tasks
        ]
        if (
            policy["ordering"]["attempt_order"] != link_ids
            or policy["result_slots"] != expected_slots
        ):
            raise ValueError

        source_specs = {
            "policy": (
                _ResourceKey.SOURCE_POLICY,
                policy["policy_id"],
            ),
            "policy_schema": (
                _ResourceKey.SOURCE_POLICY_SCHEMA,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_POLICY_SCHEMA].name,
            ),
            "preselection_registry": (
                _ResourceKey.PRESELECTION_REGISTRY,
                preselection["registry_id"],
            ),
            "preselection_schema": (
                _ResourceKey.PRESELECTION_SCHEMA,
                _SPEC_BY_KEY[_ResourceKey.PRESELECTION_SCHEMA].name,
            ),
            "source_registry": (
                _ResourceKey.SOURCE_REGISTRY,
                sources["registry_id"],
            ),
            "source_registry_schema": (
                _ResourceKey.SOURCE_REGISTRY_SCHEMA,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY_SCHEMA].name,
            ),
        }
        contract_parents = source_contract["parent_commitments"]
        for binding_name, (resource_key, identifier) in source_specs.items():
            if contract_parents[binding_name] != _binding_entry(
                _SPEC_BY_KEY[resource_key], identifier
            ):
                raise ValueError

        roster = source_contract["ordered_inspection_roster"]
        if (
            roster["canonical_json_profile_id"] != _CANONICAL_JSON_PROFILE_ID
            or roster["hash_domain"] != _ORDERED_ROSTER_DOMAIN
            or roster["ordered_source_roster_count"] != len(expected_tasks)
            or roster["tasks"] != expected_tasks
        ):
            raise ValueError
        roster_sha256 = _tagged_digest(_ORDERED_ROSTER_DOMAIN, expected_tasks)
        if (
            roster_sha256 != _EXPECTED_ORDERED_SOURCE_ROSTER_SHA256
            or roster["ordered_source_roster_sha256"] != roster_sha256
        ):
            _fail(SourceLinkStaticErrorCode.DIGEST_MISMATCH)

        custody_parent_specs = {
            "source_contract": (
                _ResourceKey.SOURCE_CONTRACT,
                source_contract["contract_id"],
            ),
            "source_contract_schema": (
                _ResourceKey.SOURCE_CONTRACT_SCHEMA,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_CONTRACT_SCHEMA].name,
            ),
            "source_policy": (
                _ResourceKey.SOURCE_POLICY,
                policy["policy_id"],
            ),
            "source_policy_schema": (
                _ResourceKey.SOURCE_POLICY_SCHEMA,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_POLICY_SCHEMA].name,
            ),
            "source_registry": (
                _ResourceKey.SOURCE_REGISTRY,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY].name,
            ),
        }
        custody_parents = custody["parent_commitments"]
        for binding_name, (resource_key, identifier) in custody_parent_specs.items():
            if custody_parents[binding_name] != _binding_entry(
                _SPEC_BY_KEY[resource_key], identifier
            ):
                raise ValueError

        source_contract_sha256 = _SPEC_BY_KEY[_ResourceKey.SOURCE_CONTRACT].tagged_sha256
        transition = custody["historical_transition"]
        if (
            transition["historical_contract_sha256"] != source_contract_sha256
            or transition["future_authority_binding"]["source_contract_sha256"]
            != source_contract_sha256
        ):
            raise ValueError

        commitments = custody["artifact_schema_commitments"]
        schema_entries = [
            {
                "id": _SPEC_BY_KEY[key].name,
                "index": index,
                "path": _SPEC_BY_KEY[key].package_path,
                "sha256": _SPEC_BY_KEY[key].tagged_sha256,
                "size": _SPEC_BY_KEY[key].size,
            }
            for index, key in enumerate(_ARTIFACT_SCHEMA_KEYS)
        ]
        if (
            commitments["canonical_json_profile_id"] != _CANONICAL_JSON_PROFILE_ID
            or commitments["digest_domain"] != _SCHEMA_SET_DOMAIN
            or commitments["schema_count"] != len(schema_entries)
            or commitments["schemas"] != schema_entries
        ):
            raise ValueError
        schema_set_payload = {
            "schema_count": len(schema_entries),
            "schema_set_version": commitments["schema_set_version"],
            "schemas": schema_entries,
        }
        schema_set_sha256 = _tagged_digest(_SCHEMA_SET_DOMAIN, schema_set_payload)
        if (
            schema_set_sha256 != _EXPECTED_ARTIFACT_SCHEMA_SET_SHA256
            or commitments["schema_set_sha256"] != schema_set_sha256
            or transition["future_authority_binding"]["schema_set_sha256"] != schema_set_sha256
        ):
            _fail(SourceLinkStaticErrorCode.DIGEST_MISMATCH)

        resolver = custody["cross_artifact_verifier_contract"]["static_file_binding_resolver"]
        static_files = resolver["exact_authority_bound_static_files"]
        resolver_expected = {
            "parent_source_registry": (
                _ResourceKey.SOURCE_REGISTRY,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY].tagged_sha256,
            ),
            "source_contract": (
                _ResourceKey.SOURCE_CONTRACT,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_CONTRACT].tagged_sha256,
            ),
            "source_policy": (
                _ResourceKey.SOURCE_POLICY,
                _SPEC_BY_KEY[_ResourceKey.SOURCE_POLICY].tagged_sha256,
            ),
        }
        for binding_name, (resource_key, digest) in resolver_expected.items():
            if static_files[binding_name] != {
                "path": _SPEC_BY_KEY[resource_key].package_path,
                "sha256": digest,
            }:
                raise ValueError
        if (
            static_files["custody_contract"]["path"]
            != _SPEC_BY_KEY[_ResourceKey.CUSTODY_CONTRACT].package_path
        ):
            raise ValueError
        roster_binding = resolver["ordered_inspection_roster_binding"]
        if (
            roster_binding["digest_domain"] != _ORDERED_ROSTER_DOMAIN
            or roster_binding["ordered_source_roster_sha256"] != roster_sha256
        ):
            raise ValueError

        source_ids = [row["source_id"] for row in sources["sources"]]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError
        transition_registration = source_contract["registration_transition"]
        if (
            transition_registration["bulk_metadata_source_id"] not in source_ids
            or transition_registration["item_source_id"] not in source_ids
            or transition_registration["new_source_registry_binding"]
            != f"{sources['registry_id']}#{transition_registration['item_source_id']}"
        ):
            raise ValueError
        return schema_set_sha256, roster_sha256
    except SourceLinkStaticError:
        raise
    except (KeyError, IndexError, TypeError, ValueError):
        binding_failed = True
    if binding_failed:
        _fail(SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH)
    _fail(SourceLinkStaticErrorCode.CROSS_BINDING_MISMATCH)


def _load_source_link_static_from_root(root: Path) -> SourceFreeStaticSnapshot:
    """Load an installed-layout root; private API reserved for adversarial tests."""

    try:
        raw_resources = _read_static_package(root)
        values = {key: _decode_static_resource(raw, key) for key, raw in raw_resources.items()}
        _validate_schemas_and_instances(values)
        schema_set_sha256, roster_sha256 = _verify_cross_bindings(values)
        return SourceFreeStaticSnapshot(
            _token=_SNAPSHOT_CONSTRUCTION_TOKEN,
            artifact_schema_set_sha256=schema_set_sha256,
            custody_contract_sha256=(_SPEC_BY_KEY[_ResourceKey.CUSTODY_CONTRACT].tagged_sha256),
            ordered_source_roster_sha256=roster_sha256,
            source_contract_sha256=(_SPEC_BY_KEY[_ResourceKey.SOURCE_CONTRACT].tagged_sha256),
            source_policy_sha256=_SPEC_BY_KEY[_ResourceKey.SOURCE_POLICY].tagged_sha256,
            source_registry_sha256=(_SPEC_BY_KEY[_ResourceKey.SOURCE_REGISTRY].tagged_sha256),
            missing_binding_fields=_MISSING_BINDING_FIELDS,
            resource_count=_STATIC_RESOURCE_COUNT,
        )
    except SourceLinkStaticError as error:
        error_code = error.code
    _fail(error_code)


def load_installed_source_link_static() -> SourceFreeStaticSnapshot:
    """Load the exact 14 resources from a real installed package directory."""

    package_lookup_failed = False
    try:
        traversable = importlib.resources.files("indusbench")
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        package_lookup_failed = True
    if package_lookup_failed:
        _fail(SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED)
    if not isinstance(traversable, Path):
        _fail(SourceLinkStaticErrorCode.PACKAGE_LAYOUT_UNSUPPORTED)
    return _load_source_link_static_from_root(traversable)
