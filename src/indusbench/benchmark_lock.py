"""Exact-byte benchmark definition locks for public development evaluation.

This module creates and verifies only the benchmark-definition layer. It does
not claim external timestamping, submission custody, hidden membership, an
isolated runtime, or a blind/final evaluation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from indusbench.audit import audit_leakage
from indusbench.io import CorpusFormatError
from indusbench.manifest import corpus_digest, sha256_json
from indusbench.quarantine import (
    quarantine_manifest_digest,
    registry_digest,
    require_corpus_permitted,
    validate_quarantine_manifest,
)
from indusbench.schema_validation import validate_artifact_rows, validate_schema_instance
from indusbench.split_manifest import (
    split_manifest_digest,
    split_member,
    validate_split_manifest,
)
from indusbench.validation import has_errors, validate_corpus

CANONICALIZATION = "indus-json-c14n-v1"
DEFINITION_DOMAIN = b"indusbench:benchmark-definition:v0.1\0"
SCIENTIFIC_SCOPE = (
    "public structural development evaluation only; no phonetic, semantic, "
    "translation, decipherment, blind-test, or final-evaluation inference"
)
ASSURANCE_REASON_CODES = [
    "development_membership_public",
    "definition_digest_not_externally_anchored",
    "no_submission_custody_receipt",
    "dependency_lock_without_oci_runtime",
    "evaluator_dependency_closure_not_attested",
]
CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_CORPUS_BYTES = 512 * 1024 * 1024
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
MAX_ENVIRONMENT_LOCK_BYTES = 256 * 1024 * 1024
MAX_EVALUATOR_FILES = 128
MAX_EVALUATOR_TOTAL_BYTES = 256 * 1024 * 1024


class BenchmarkLockError(ValueError):
    """Raised when a definition cannot be built or safely interpreted."""


@dataclass(frozen=True)
class BenchmarkVerificationReport:
    valid: bool
    self_consistent: bool
    inputs_match: bool
    expected_digest_match: bool
    externally_anchored: bool
    definition_sha256: str
    expected_definition_sha256: str | None
    checked_file_count: int
    mismatches: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "self_consistent": self.self_consistent,
            "inputs_match": self.inputs_match,
            "expected_digest_match": self.expected_digest_match,
            "externally_anchored": self.externally_anchored,
            "definition_sha256": self.definition_sha256,
            "expected_definition_sha256": self.expected_definition_sha256,
            "checked_file_count": self.checked_file_count,
            "mismatches": list(self.mismatches),
            "claim_class": "development_reproducibility",
            "blind_claim_allowed": False,
            "final_evaluation_eligible": False,
        }


def _reject_floats(value: object, path: str = "$") -> None:
    if isinstance(value, float):
        raise BenchmarkLockError(f"{path}: benchmark lock values cannot contain floats")
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_floats(child, f"{path}[{index}]")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise BenchmarkLockError(f"{path}: benchmark lock keys must be strings")
            _reject_floats(child, f"{path}.{key}")


def canonical_lock_json(value: Mapping[str, Any]) -> bytes:
    """Apply the lock's strict, no-float canonical JSON profile."""

    _reject_floats(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def benchmark_definition_digest(value: Mapping[str, Any]) -> str:
    """Return the domain-separated definition digest without self fields."""

    body = dict(value)
    body.pop("definition_id", None)
    body.pop("definition_sha256", None)
    return "sha256:" + hashlib.sha256(DEFINITION_DOMAIN + canonical_lock_json(body)).hexdigest()


def _strict_json_bytes(raw: bytes, logical_path: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CorpusFormatError(f"{logical_path}: invalid UTF-8: {error}") from error

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in pairs:
            if key in result:
                raise BenchmarkLockError(f"{logical_path}: duplicate JSON key {key!r}")
            result[key] = child
        return result

    def reject_constant(value: str) -> None:
        raise BenchmarkLockError(f"{logical_path}: non-finite JSON number {value!r}")

    def reject_nonfinite_float(value: str) -> float:
        parsed = float(value)
        if parsed in {float("inf"), float("-inf")}:
            raise BenchmarkLockError(f"{logical_path}: non-finite JSON number {value!r}")
        return parsed

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
            parse_float=reject_nonfinite_float,
        )
    except json.JSONDecodeError as error:
        raise CorpusFormatError(f"{logical_path}: invalid JSON: {error}") from error


def _strict_jsonl_bytes(raw: bytes, logical_path: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        if not raw_line.strip():
            continue
        value = _strict_json_bytes(raw_line, f"{logical_path}:{line_number}")
        if not isinstance(value, dict):
            raise CorpusFormatError(
                f"{logical_path}:{line_number}: each JSONL row must be an object"
            )
        records.append(value)
    return records


def _safe_regular_file(path: Path, *, max_bytes: int, logical_path: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as error:
        raise BenchmarkLockError(f"{logical_path}: cannot stat input: {error}") from error
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise BenchmarkLockError(f"{logical_path}: input must be a single-link regular file")
    if before.st_size <= 0 or before.st_size > max_bytes:
        raise BenchmarkLockError(
            f"{logical_path}: input size must be between 1 and {max_bytes} bytes"
        )

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_size != before.st_size
        ):
            raise BenchmarkLockError(f"{logical_path}: input changed before it was opened")
        chunks: list[bytes] = []
        byte_count = 0
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            while chunk := handle.read(min(1024 * 1024, max_bytes + 1 - byte_count)):
                chunks.append(chunk)
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise BenchmarkLockError(f"{logical_path}: input exceeds size limit")
            after = os.fstat(handle.fileno())
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ):
            raise BenchmarkLockError(f"{logical_path}: input changed while it was read")
        return b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _file_binding(logical_path: str, raw: bytes) -> dict[str, Any]:
    path = PurePosixPath(logical_path)
    if path.is_absolute() or ".." in path.parts or not path.parts or str(path) != logical_path:
        raise BenchmarkLockError(f"unsafe logical path {logical_path!r}")
    return {
        "path": logical_path,
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _schema_issues(instance: Any, schema: Mapping[str, Any], label: str) -> None:
    issues = validate_schema_instance(instance, schema)
    if issues:
        preview = "; ".join(f"{issue.path}: {issue.message}" for issue in issues[:5])
        raise BenchmarkLockError(f"{label} failed schema validation: {preview}")


def _reject_remote_schema_refs(value: object, label: str, path: str = "$") -> None:
    if isinstance(value, Mapping):
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#/"):
            raise BenchmarkLockError(
                f"{label} {path} contains a non-local $ref; network resolution is forbidden"
            )
        for key, child in value.items():
            _reject_remote_schema_refs(child, label, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_remote_schema_refs(child, label, f"{path}[{index}]")


def _default_benchmark_lock_schema() -> dict[str, Any]:
    candidates = (
        Path(__file__).resolve().parents[2] / "schemas" / "benchmark-lock.schema.json",
        Path(__file__).resolve().parent / "schemas" / "benchmark-lock.schema.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            raw = _safe_regular_file(
                candidate,
                max_bytes=MAX_DOCUMENT_BYTES,
                logical_path="schemas/benchmark-lock.schema.json",
            )
            value = _strict_json_bytes(raw, "schemas/benchmark-lock.schema.json")
            if not isinstance(value, dict):
                raise BenchmarkLockError("benchmark lock schema must be a JSON object")
            _reject_remote_schema_refs(value, "benchmark lock schema")
            return value
    raise BenchmarkLockError("benchmark-lock.schema.json is unavailable")


def _load_inputs(
    *,
    corpus_path: Path,
    split_dir: Path,
    evaluator_config_path: Path,
    evaluator_files: Iterable[Path],
    environment_lock_path: Path,
    project_manifest_path: Path,
    artifact_schema_path: Path,
    source_registry_path: Path,
    source_schema_path: Path,
    quarantine_registry_path: Path,
    quarantine_schema_path: Path,
    split_schema_path: Path,
    evaluator_schema_path: Path,
    benchmark_lock_schema_path: Path,
) -> tuple[dict[str, Any], int, dict[str, Any]]:
    raw: dict[str, bytes] = {}
    path_specs = {
        "corpus/input.jsonl": (corpus_path, MAX_CORPUS_BYTES),
        "schemas/artifact.schema.json": (artifact_schema_path, MAX_DOCUMENT_BYTES),
        "schemas/source-registry.schema.json": (source_schema_path, MAX_DOCUMENT_BYTES),
        "schemas/quarantine-manifest.schema.json": (
            quarantine_schema_path,
            MAX_DOCUMENT_BYTES,
        ),
        "schemas/split-manifest.schema.json": (split_schema_path, MAX_DOCUMENT_BYTES),
        "schemas/evaluator-config.schema.json": (
            evaluator_schema_path,
            MAX_DOCUMENT_BYTES,
        ),
        "schemas/benchmark-lock.schema.json": (
            benchmark_lock_schema_path,
            MAX_DOCUMENT_BYTES,
        ),
        "registry/sources.json": (source_registry_path, MAX_DOCUMENT_BYTES),
        "registry/quarantine.json": (quarantine_registry_path, MAX_DOCUMENT_BYTES),
        "split/split-manifest.json": (
            split_dir / "split-manifest.json",
            MAX_DOCUMENT_BYTES,
        ),
        "split/train.jsonl": (split_dir / "train.jsonl", MAX_CORPUS_BYTES),
        "split/development.jsonl": (
            split_dir / "development.jsonl",
            MAX_CORPUS_BYTES,
        ),
        "split/leakage-audit.json": (
            split_dir / "leakage-audit.json",
            MAX_DOCUMENT_BYTES,
        ),
        "evaluator/config.json": (evaluator_config_path, MAX_DOCUMENT_BYTES),
        "environment/dependency.lock": (
            environment_lock_path,
            MAX_ENVIRONMENT_LOCK_BYTES,
        ),
        "environment/project.toml": (project_manifest_path, MAX_DOCUMENT_BYTES),
    }
    for logical_path, (physical_path, limit) in path_specs.items():
        raw[logical_path] = _safe_regular_file(
            physical_path,
            max_bytes=limit,
            logical_path=logical_path,
        )

    evaluator_paths = list(evaluator_files)
    if not evaluator_paths or len(evaluator_paths) > MAX_EVALUATOR_FILES:
        raise BenchmarkLockError(f"provide between 1 and {MAX_EVALUATOR_FILES} evaluator files")
    evaluator_total = 0
    evaluator_bindings: list[dict[str, Any]] = []
    evaluator_names: set[str] = set()
    for evaluator_path in evaluator_paths:
        logical_path = f"evaluator/files/{evaluator_path.name}"
        collision_key = logical_path.casefold()
        if collision_key in evaluator_names:
            raise BenchmarkLockError(f"duplicate evaluator filename {evaluator_path.name!r}")
        evaluator_names.add(collision_key)
        evaluator_raw = _safe_regular_file(
            evaluator_path,
            max_bytes=MAX_DOCUMENT_BYTES,
            logical_path=logical_path,
        )
        evaluator_total += len(evaluator_raw)
        if evaluator_total > MAX_EVALUATOR_TOTAL_BYTES:
            raise BenchmarkLockError("evaluator files exceed the aggregate size limit")
        evaluator_bindings.append(_file_binding(logical_path, evaluator_raw))

    artifact_schema = _strict_json_bytes(
        raw["schemas/artifact.schema.json"],
        "schemas/artifact.schema.json",
    )
    source_schema = _strict_json_bytes(
        raw["schemas/source-registry.schema.json"],
        "schemas/source-registry.schema.json",
    )
    quarantine_schema = _strict_json_bytes(
        raw["schemas/quarantine-manifest.schema.json"],
        "schemas/quarantine-manifest.schema.json",
    )
    split_schema = _strict_json_bytes(
        raw["schemas/split-manifest.schema.json"],
        "schemas/split-manifest.schema.json",
    )
    evaluator_schema = _strict_json_bytes(
        raw["schemas/evaluator-config.schema.json"],
        "schemas/evaluator-config.schema.json",
    )
    benchmark_lock_schema = _strict_json_bytes(
        raw["schemas/benchmark-lock.schema.json"],
        "schemas/benchmark-lock.schema.json",
    )
    source_registry = _strict_json_bytes(
        raw["registry/sources.json"],
        "registry/sources.json",
    )
    quarantine_registry = _strict_json_bytes(
        raw["registry/quarantine.json"],
        "registry/quarantine.json",
    )
    split_manifest = _strict_json_bytes(
        raw["split/split-manifest.json"],
        "split/split-manifest.json",
    )
    leakage_audit = _strict_json_bytes(
        raw["split/leakage-audit.json"],
        "split/leakage-audit.json",
    )
    evaluator_config = _strict_json_bytes(
        raw["evaluator/config.json"],
        "evaluator/config.json",
    )
    for label, value in (
        ("artifact schema", artifact_schema),
        ("source schema", source_schema),
        ("quarantine schema", quarantine_schema),
        ("split schema", split_schema),
        ("evaluator schema", evaluator_schema),
        ("benchmark lock schema", benchmark_lock_schema),
        ("source registry", source_registry),
        ("quarantine registry", quarantine_registry),
        ("split manifest", split_manifest),
        ("leakage audit", leakage_audit),
        ("evaluator config", evaluator_config),
    ):
        if not isinstance(value, dict):
            raise BenchmarkLockError(f"{label} must be a JSON object")

    for label, schema in (
        ("artifact schema", artifact_schema),
        ("source schema", source_schema),
        ("quarantine schema", quarantine_schema),
        ("split schema", split_schema),
        ("evaluator schema", evaluator_schema),
        ("benchmark lock schema", benchmark_lock_schema),
    ):
        _reject_remote_schema_refs(schema, label)
    _schema_issues(source_registry, source_schema, "source registry")
    _schema_issues(quarantine_registry, quarantine_schema, "quarantine registry")
    _schema_issues(split_manifest, split_schema, "split manifest")
    _schema_issues(evaluator_config, evaluator_schema, "evaluator config")
    validate_quarantine_manifest(quarantine_registry)
    validate_split_manifest(split_manifest)

    corpus = _strict_jsonl_bytes(raw["corpus/input.jsonl"], "corpus/input.jsonl")
    train = _strict_jsonl_bytes(raw["split/train.jsonl"], "split/train.jsonl")
    development = _strict_jsonl_bytes(
        raw["split/development.jsonl"],
        "split/development.jsonl",
    )
    corpus_issues = validate_corpus(corpus)
    corpus_issues.extend(validate_artifact_rows(corpus, artifact_schema))
    if has_errors(corpus_issues):
        preview = "; ".join(
            f"{issue.path}: {issue.message}" for issue in corpus_issues if issue.severity == "error"
        )
        raise BenchmarkLockError(f"corpus validation failed: {preview[:2000]}")
    require_corpus_permitted(
        corpus,
        source_registry=source_registry,
        quarantine_manifest=quarantine_registry,
        purpose="corpus_ingestion",
    )

    corpus_binding = _file_binding("corpus/input.jsonl", raw["corpus/input.jsonl"])
    split_corpus = split_manifest.get("corpus_file")
    if not isinstance(split_corpus, Mapping):
        raise BenchmarkLockError("split manifest corpus_file is malformed")
    if (
        split_corpus.get("sha256") != corpus_binding["sha256"]
        or split_corpus.get("bytes") != corpus_binding["bytes"]
        or split_corpus.get("artifact_count") != len(corpus)
    ):
        raise BenchmarkLockError("split manifest does not bind the exact corpus input")
    semantic_corpus_sha256 = "sha256:" + corpus_digest(corpus)
    if split_manifest.get("corpus_fingerprint") != semantic_corpus_sha256:
        raise BenchmarkLockError("split manifest corpus_fingerprint is inconsistent")
    if split_manifest.get("source_registry_sha256") != registry_digest(source_registry):
        raise BenchmarkLockError("split manifest source registry commitment is inconsistent")
    if split_manifest.get("quarantine_manifest_sha256") != quarantine_manifest_digest(
        quarantine_registry
    ):
        raise BenchmarkLockError("split manifest quarantine commitment is inconsistent")

    partition_rows = {
        "train": train,
        "development": development,
    }
    partitions = split_manifest.get("partitions")
    if not isinstance(partitions, list):
        raise BenchmarkLockError("split manifest partitions are malformed")
    for partition in partitions:
        if not isinstance(partition, Mapping):
            raise BenchmarkLockError("split manifest partition is malformed")
        role = partition.get("role")
        if role not in partition_rows:
            raise BenchmarkLockError(f"unsupported split partition role {role!r}")
        file_value = partition.get("file")
        if not isinstance(file_value, Mapping):
            raise BenchmarkLockError(f"{role}: split file commitment is malformed")
        logical_path = f"split/{file_value.get('path')}"
        actual_binding = _file_binding(logical_path, raw[logical_path])
        if dict(file_value) != {
            "path": str(file_value.get("path")),
            "sha256": actual_binding["sha256"],
            "bytes": actual_binding["bytes"],
        }:
            raise BenchmarkLockError(f"{role}: split file bytes do not match the manifest")

        expected_members = partition.get("members")
        if not isinstance(expected_members, list):
            raise BenchmarkLockError(f"{role}: split members are malformed")
        actual_members = sorted(
            (split_member(record) for record in partition_rows[str(role)]),
            key=lambda item: item["artifact_id"],
        )
        if actual_members != expected_members:
            raise BenchmarkLockError(
                f"{role}: split file membership evidence differs from the manifest"
            )

    corpus_by_id = {str(record.get("artifact_id")): sha256_json(record) for record in corpus}
    split_by_id = {
        str(record.get("artifact_id")): sha256_json(record) for record in train + development
    }
    if corpus_by_id != split_by_id or len(corpus_by_id) != len(corpus):
        raise BenchmarkLockError("split rows are not an exact partition of the corpus")

    actual_audit = audit_leakage(train, development).as_dict()
    if leakage_audit != actual_audit:
        raise BenchmarkLockError("leakage audit file is not reproducible from the split")
    audit_commitment = split_manifest.get("leakage_policy")
    if not isinstance(audit_commitment, Mapping) or not isinstance(
        audit_commitment.get("audit_file"),
        Mapping,
    ):
        raise BenchmarkLockError("split manifest audit commitment is malformed")
    audit_file = audit_commitment["audit_file"]
    audit_binding = _file_binding(
        "split/leakage-audit.json",
        raw["split/leakage-audit.json"],
    )
    if (
        audit_file.get("sha256") != audit_binding["sha256"]
        or audit_file.get("bytes") != audit_binding["bytes"]
        or audit_file.get("semantic_sha256") != "sha256:" + sha256_json(actual_audit)
    ):
        raise BenchmarkLockError("leakage audit commitment is inconsistent")

    schema_bindings = {
        name: _file_binding(
            f"schemas/{name}.schema.json",
            raw[f"schemas/{name}.schema.json"],
        )
        for name in (
            "artifact",
            "source-registry",
            "quarantine-manifest",
            "split-manifest",
            "evaluator-config",
            "benchmark-lock",
        )
    }
    split_file_bindings = [
        _file_binding("split/train.jsonl", raw["split/train.jsonl"]),
        _file_binding("split/development.jsonl", raw["split/development.jsonl"]),
        audit_binding,
    ]
    evaluator_bindings.sort(key=lambda item: str(item["path"]))
    evaluator_inventory_sha256 = (
        "sha256:"
        + hashlib.sha256(
            b"indusbench:evaluator-inventory:v0.1\0"
            + canonical_lock_json({"files": evaluator_bindings})
        ).hexdigest()
    )
    inputs = {
        "corpus": {
            "file": corpus_binding,
            "semantic_sha256": semantic_corpus_sha256,
            "artifact_count": len(corpus),
        },
        "schemas": schema_bindings,
        "registries": {
            "sources": {
                "file": _file_binding("registry/sources.json", raw["registry/sources.json"]),
                "canonical_sha256": registry_digest(source_registry),
            },
            "quarantine": {
                "file": _file_binding(
                    "registry/quarantine.json",
                    raw["registry/quarantine.json"],
                ),
                "manifest_sha256": quarantine_manifest_digest(quarantine_registry),
            },
        },
        "split": {
            "manifest": {
                "file": _file_binding(
                    "split/split-manifest.json",
                    raw["split/split-manifest.json"],
                ),
                "split_id": split_manifest["split_id"],
                "manifest_sha256": split_manifest_digest(split_manifest),
            },
            "files": split_file_bindings,
            "claim_class": "public_development",
        },
        "evaluator": {
            "config": _file_binding(
                "evaluator/config.json",
                raw["evaluator/config.json"],
            ),
            "files": evaluator_bindings,
            "inventory_sha256": evaluator_inventory_sha256,
        },
        "environment": {
            "dependency_lock": _file_binding(
                "environment/dependency.lock",
                raw["environment/dependency.lock"],
            ),
            "project_manifest": _file_binding(
                "environment/project.toml",
                raw["environment/project.toml"],
            ),
            "reproducibility_class": "dependency_lock_only",
            "oci_image_digest": None,
            "network_isolation_enforced": False,
        },
    }
    checked_file_count = len(path_specs) + len(evaluator_bindings)
    return inputs, checked_file_count, benchmark_lock_schema


def build_benchmark_definition(
    *,
    corpus_path: Path,
    split_dir: Path,
    evaluator_config_path: Path,
    evaluator_files: Iterable[Path],
    environment_lock_path: Path,
    project_manifest_path: Path,
    artifact_schema_path: Path,
    source_registry_path: Path,
    source_schema_path: Path,
    quarantine_registry_path: Path,
    quarantine_schema_path: Path,
    split_schema_path: Path,
    evaluator_schema_path: Path,
    benchmark_lock_schema_path: Path,
    created_by: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a self-consistent but explicitly unanchored definition lock."""

    if not created_by.strip():
        raise BenchmarkLockError("created_by must be non-empty")
    inputs, _, benchmark_lock_schema = _load_inputs(
        corpus_path=corpus_path,
        split_dir=split_dir,
        evaluator_config_path=evaluator_config_path,
        evaluator_files=evaluator_files,
        environment_lock_path=environment_lock_path,
        project_manifest_path=project_manifest_path,
        artifact_schema_path=artifact_schema_path,
        source_registry_path=source_registry_path,
        source_schema_path=source_schema_path,
        quarantine_registry_path=quarantine_registry_path,
        quarantine_schema_path=quarantine_schema_path,
        split_schema_path=split_schema_path,
        evaluator_schema_path=evaluator_schema_path,
        benchmark_lock_schema_path=benchmark_lock_schema_path,
    )
    lock: dict[str, Any] = {
        "schema_version": "0.1.0",
        "canonicalization": CANONICALIZATION,
        "definition_id": "",
        "definition_sha256": "",
        "created_at": created_at
        or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "created_by": created_by,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "assurance": {
            "claim_class": "development_reproducibility",
            "blind_claim_allowed": False,
            "final_evaluation_eligible": False,
            "externally_anchored": False,
            "reason_codes": ASSURANCE_REASON_CODES,
        },
        "inputs": inputs,
        "external_anchor": {
            "status": "unanchored_local",
            "receipt": None,
        },
    }
    digest = benchmark_definition_digest(lock)
    lock["definition_sha256"] = digest
    lock["definition_id"] = f"benchmark-definition:{digest}"
    validate_benchmark_definition(lock, schema=benchmark_lock_schema)
    return lock


def validate_benchmark_definition(
    value: Mapping[str, Any],
    *,
    schema: Mapping[str, Any] | None = None,
) -> None:
    """Validate closed assurance and the domain-separated self-commitment."""

    required_keys = {
        "schema_version",
        "canonicalization",
        "definition_id",
        "definition_sha256",
        "created_at",
        "created_by",
        "scientific_scope",
        "assurance",
        "inputs",
        "external_anchor",
    }
    if set(value) != required_keys:
        raise BenchmarkLockError("benchmark definition has missing or unknown top-level fields")
    if value.get("schema_version") != "0.1.0":
        raise BenchmarkLockError("schema_version must equal '0.1.0'")
    if value.get("canonicalization") != CANONICALIZATION:
        raise BenchmarkLockError(f"canonicalization must equal {CANONICALIZATION!r}")
    if value.get("scientific_scope") != SCIENTIFIC_SCOPE:
        raise BenchmarkLockError("scientific_scope is not the closed development-only statement")
    created_by = value.get("created_by")
    if not isinstance(created_by, str) or not created_by.strip():
        raise BenchmarkLockError("created_by must be a non-empty string")
    created_at = value.get("created_at")
    if not isinstance(created_at, str):
        raise BenchmarkLockError("created_at must be an RFC 3339 string")
    normalized_created_at = created_at[:-1] + "+00:00" if created_at.endswith("Z") else created_at
    try:
        parsed_created_at = datetime.fromisoformat(normalized_created_at)
    except ValueError as error:
        raise BenchmarkLockError("created_at must be a valid RFC 3339 date-time") from error
    if parsed_created_at.tzinfo is None or parsed_created_at.utcoffset() is None:
        raise BenchmarkLockError("created_at must include a UTC offset")
    expected = benchmark_definition_digest(value)
    if value.get("definition_sha256") != expected:
        raise BenchmarkLockError("definition_sha256 does not match the definition body")
    if value.get("definition_id") != f"benchmark-definition:{expected}":
        raise BenchmarkLockError("definition_id does not match definition_sha256")
    assurance = value.get("assurance")
    if not isinstance(assurance, Mapping) or dict(assurance) != {
        "claim_class": "development_reproducibility",
        "blind_claim_allowed": False,
        "final_evaluation_eligible": False,
        "externally_anchored": False,
        "reason_codes": ASSURANCE_REASON_CODES,
    }:
        raise BenchmarkLockError("assurance block cannot claim blind, final, or anchored status")
    anchor = value.get("external_anchor")
    if not isinstance(anchor, Mapping) or dict(anchor) != {
        "status": "unanchored_local",
        "receipt": None,
    }:
        raise BenchmarkLockError("local definition must remain explicitly unanchored")
    inputs = value.get("inputs")
    if not isinstance(inputs, Mapping):
        raise BenchmarkLockError("inputs must be an object")
    split = inputs.get("split")
    environment = inputs.get("environment")
    if not isinstance(split, Mapping) or split.get("claim_class") != "public_development":
        raise BenchmarkLockError("definition must bind a public-development split")
    if (
        not isinstance(environment, Mapping)
        or dict(environment).get("reproducibility_class") != "dependency_lock_only"
    ):
        raise BenchmarkLockError("definition must disclose dependency-lock-only environment")
    effective_schema = schema if schema is not None else _default_benchmark_lock_schema()
    _schema_issues(value, effective_schema, "benchmark definition")
    _reject_floats(value)


def verify_benchmark_definition(
    value: Mapping[str, Any],
    *,
    corpus_path: Path,
    split_dir: Path,
    evaluator_config_path: Path,
    evaluator_files: Iterable[Path],
    environment_lock_path: Path,
    project_manifest_path: Path,
    artifact_schema_path: Path,
    source_registry_path: Path,
    source_schema_path: Path,
    quarantine_registry_path: Path,
    quarantine_schema_path: Path,
    split_schema_path: Path,
    evaluator_schema_path: Path,
    benchmark_lock_schema_path: Path,
    expected_definition_sha256: str | None = None,
) -> BenchmarkVerificationReport:
    """Recompute every local input and optionally compare an external digest."""

    mismatches: list[str] = []
    actual_digest = benchmark_definition_digest(value)
    actual_inputs, checked_file_count, benchmark_lock_schema = _load_inputs(
        corpus_path=corpus_path,
        split_dir=split_dir,
        evaluator_config_path=evaluator_config_path,
        evaluator_files=evaluator_files,
        environment_lock_path=environment_lock_path,
        project_manifest_path=project_manifest_path,
        artifact_schema_path=artifact_schema_path,
        source_registry_path=source_registry_path,
        source_schema_path=source_schema_path,
        quarantine_registry_path=quarantine_registry_path,
        quarantine_schema_path=quarantine_schema_path,
        split_schema_path=split_schema_path,
        evaluator_schema_path=evaluator_schema_path,
        benchmark_lock_schema_path=benchmark_lock_schema_path,
    )
    try:
        validate_benchmark_definition(value, schema=benchmark_lock_schema)
        self_consistent = True
    except BenchmarkLockError as error:
        self_consistent = False
        mismatches.append(str(error))
    inputs_match = value.get("inputs") == actual_inputs
    if not inputs_match:
        mismatches.append("current input commitments differ from the definition")

    expected_digest_match = False
    if expected_definition_sha256 is not None:
        if not CHECKSUM_PATTERN.fullmatch(expected_definition_sha256):
            mismatches.append("externally supplied definition digest is malformed")
        else:
            expected_digest_match = expected_definition_sha256 == actual_digest
        if not expected_digest_match:
            mismatches.append("externally supplied definition digest does not match")
    externally_anchored = False
    return BenchmarkVerificationReport(
        valid=self_consistent and inputs_match and not mismatches,
        self_consistent=self_consistent,
        inputs_match=inputs_match,
        expected_digest_match=expected_digest_match,
        externally_anchored=externally_anchored,
        definition_sha256=actual_digest,
        expected_definition_sha256=expected_definition_sha256,
        checked_file_count=checked_file_count,
        mismatches=tuple(mismatches),
    )
