"""Self-auditing manifests for public development partitions.

Version 0.2 deliberately does not model a blind test. Both produced
partitions and their complete membership are public, so the assurance block
is derived as development-only and cannot be promoted by a caller-supplied
boolean.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from indusbench.audit import (
    audit_leakage,
    extract_image_hashes,
    extract_normalized_sequences,
)
from indusbench.io import encode_json, encode_jsonl_record
from indusbench.manifest import corpus_digest, sha256_json

CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class SplitManifestError(ValueError):
    """Raised when a split manifest is internally inconsistent."""


def _checksum(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _require_checksum(value: object, path: str) -> str:
    if not isinstance(value, str) or not CHECKSUM_PATTERN.fullmatch(value):
        raise SplitManifestError(f"{path} must be a lowercase SHA-256 commitment")
    return value


def split_member(record: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the public membership evidence for one exact artifact record."""

    artifact_id = record.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ValueError("split member is missing a non-empty artifact_id")
    family_id = record.get("duplicate_family_id")
    if family_id is not None and (not isinstance(family_id, str) or not family_id):
        raise ValueError(f"{artifact_id}: invalid duplicate_family_id")

    sequence_hashes = sorted(
        _checksum(sha256_json(list(sequence))) for sequence in extract_normalized_sequences(record)
    )
    if not sequence_hashes:
        raise ValueError(f"{artifact_id}: split member has no normalized sign sequence")

    return {
        "artifact_id": artifact_id,
        "duplicate_family_id": family_id,
        "image_hashes": sorted(_checksum(value) for value in extract_image_hashes(record)),
        "normalized_sequence_hashes": sequence_hashes,
    }


def _jsonl_commitment(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    digest = hashlib.sha256()
    byte_count = 0
    for record in records:
        raw = encode_jsonl_record(record)
        digest.update(raw)
        byte_count += len(raw)
    return {
        "sha256": f"sha256:{digest.hexdigest()}",
        "bytes": byte_count,
    }


def _partition(
    partition_id: str,
    role: str,
    file_name: str,
    records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    members = sorted(
        (split_member(record) for record in records),
        key=lambda item: item["artifact_id"],
    )
    return {
        "partition_id": partition_id,
        "role": role,
        "visibility": "public",
        "file": {
            "path": file_name,
            **_jsonl_commitment(records),
        },
        "members": members,
        "artifact_count": len(members),
        "membership_commitment": _checksum(sha256_json(members)),
    }


def split_manifest_digest(value: Mapping[str, Any]) -> str:
    """Commit to every manifest value except the self-commitment."""

    payload = dict(value)
    payload.pop("manifest_sha256", None)
    return _checksum(sha256_json(payload))


def build_split_manifest(
    train: Iterable[Mapping[str, Any]],
    development: Iterable[Mapping[str, Any]],
    *,
    seed: int,
    corpus_file_sha256: str,
    corpus_file_bytes: int,
    source_registry_sha256: str,
    quarantine_manifest_sha256: str,
    test_fraction: float = 0.2,
    strategy_type: str = "grouped_random",
    holdout_values: Iterable[str] = (),
    created_by: str = "indusbench",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a frozen public-development membership manifest.

    Exact JSONL commitments describe the bytes emitted by ``write_jsonl``.
    This manifest is still not a benchmark lock: evaluator and environment
    commitments belong to the separate lock layer.
    """

    train_rows = list(train)
    development_rows = list(development)
    if not train_rows or not development_rows:
        raise ValueError("public train and development partitions must both contain artifacts")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if not math.isfinite(test_fraction) or not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be finite and strictly between 0 and 1")
    if isinstance(corpus_file_bytes, bool) or corpus_file_bytes < 0:
        raise ValueError("corpus_file_bytes must be a non-negative integer")
    _require_checksum(corpus_file_sha256, "corpus_file_sha256")
    _require_checksum(source_registry_sha256, "source_registry_sha256")
    _require_checksum(quarantine_manifest_sha256, "quarantine_manifest_sha256")
    if not created_by.strip():
        raise ValueError("created_by must be non-empty")

    audit = audit_leakage(train_rows, development_rows)
    if audit.has_leakage:
        raise ValueError(f"cannot freeze a leaking split: {audit.as_dict()}")

    holdouts = sorted(set(holdout_values))
    all_rows = train_rows + development_rows
    fingerprint = _checksum(corpus_digest(all_rows))
    audit_value = audit.as_dict()
    audit_bytes = encode_json(audit_value)
    timestamp = created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    partitions = [
        _partition("train", "train", "train.jsonl", train_rows),
        _partition(
            "development",
            "development",
            "development.jsonl",
            development_rows,
        ),
    ]
    split_identity = sha256_json(
        {
            "corpus_file_sha256": corpus_file_sha256,
            "corpus_fingerprint": fingerprint,
            "source_registry_sha256": source_registry_sha256,
            "quarantine_manifest_sha256": quarantine_manifest_sha256,
            "seed": seed,
            "test_fraction": format(test_fraction, ".17g"),
            "strategy": strategy_type,
            "holdout_values": holdouts,
            "partitions": [
                {
                    "partition_id": partition["partition_id"],
                    "membership_commitment": partition["membership_commitment"],
                    "file_sha256": partition["file"]["sha256"],
                }
                for partition in partitions
            ],
            "audit_sha256": f"sha256:{hashlib.sha256(audit_bytes).hexdigest()}",
        }
    )
    manifest: dict[str, Any] = {
        "schema_version": "0.2.0",
        "split_id": f"split:sha256:{split_identity}",
        "created_at": timestamp,
        "created_by": created_by,
        "seed": seed,
        "corpus_fingerprint": fingerprint,
        "corpus_file": {
            "sha256": corpus_file_sha256,
            "bytes": corpus_file_bytes,
            "artifact_count": len(all_rows),
        },
        "source_registry_sha256": source_registry_sha256,
        "quarantine_manifest_sha256": quarantine_manifest_sha256,
        "strategy": {
            "type": strategy_type,
            "holdout_values": holdouts,
            "description": (
                "Connected components over duplicate families, catalog aliases, "
                "image hashes, and exact normalized sign sequences."
            ),
            "implementation": "indusbench.splits:deterministic_leakage_safe_split@0.1",
            "parameters": {
                "seed": str(seed),
                "test_fraction": format(test_fraction, ".17g"),
            },
        },
        "grouping_keys": [
            "duplicate_family_id",
            "image_hash",
            "normalized_sequence_hash",
            "catalog_identifier",
        ],
        "leakage_policy": {
            "duplicate_families_share_partition": True,
            "image_hashes_share_partition": True,
            "exact_sequences_share_partition": True,
            "catalog_crosswalks_share_partition": True,
            "normalization": "reading_order_sign_ids_v0.1",
            "audit_file": {
                "path": "leakage-audit.json",
                "sha256": f"sha256:{hashlib.sha256(audit_bytes).hexdigest()}",
                "bytes": len(audit_bytes),
                "semantic_sha256": _checksum(sha256_json(audit_value)),
            },
            "violations": [],
        },
        "evaluation_assurance": {
            "claim_class": "public_development",
            "test_partition_id": None,
            "development_partition_id": "development",
            "test_visibility": "public",
            "blind_claim_allowed": False,
            "final_evaluation_eligible": False,
            "custodian_commitment": None,
            "reason_codes": [
                "complete_membership_public",
                "no_external_custodian",
            ],
        },
        "partitions": partitions,
        "membership_frozen": True,
        "benchmark_locked": False,
        "notes": (
            "The development partition is fully public. It is not a blind or final "
            "evaluation set; a separate externally anchored benchmark lock and "
            "custodian-held private companion are required for those claims."
        ),
    }
    manifest["manifest_sha256"] = split_manifest_digest(manifest)
    validate_split_manifest(manifest)
    return manifest


def validate_split_manifest(value: Mapping[str, Any]) -> None:
    """Recompute the invariants that JSON Schema cannot express."""

    if value.get("schema_version") != "0.2.0":
        raise SplitManifestError("schema_version must equal '0.2.0'")
    manifest_sha256 = _require_checksum(value.get("manifest_sha256"), "manifest_sha256")
    if manifest_sha256 != split_manifest_digest(value):
        raise SplitManifestError("manifest_sha256 does not match the manifest body")

    assurance = value.get("evaluation_assurance")
    if not isinstance(assurance, Mapping):
        raise SplitManifestError("evaluation_assurance must be an object")
    required_assurance = {
        "claim_class": "public_development",
        "test_partition_id": None,
        "development_partition_id": "development",
        "test_visibility": "public",
        "blind_claim_allowed": False,
        "final_evaluation_eligible": False,
        "custodian_commitment": None,
    }
    for key, expected in required_assurance.items():
        if assurance.get(key) != expected:
            raise SplitManifestError(
                f"evaluation_assurance.{key} must equal {expected!r} for a public split"
            )

    partitions = value.get("partitions")
    if not isinstance(partitions, list) or len(partitions) != 2:
        raise SplitManifestError("partitions must contain train and development")
    partition_ids: set[str] = set()
    artifact_ids: set[str] = set()
    total_artifacts = 0
    roles: set[str] = set()
    for index, partition in enumerate(partitions):
        if not isinstance(partition, Mapping):
            raise SplitManifestError(f"partitions[{index}] must be an object")
        partition_id = partition.get("partition_id")
        role = partition.get("role")
        if not isinstance(partition_id, str) or partition_id in partition_ids:
            raise SplitManifestError("partition_id values must be non-empty and unique")
        if role not in {"train", "development"} or role in roles:
            raise SplitManifestError("partition roles must be unique train and development")
        if partition.get("visibility") != "public":
            raise SplitManifestError("version 0.2 partitions must be public")
        partition_ids.add(partition_id)
        roles.add(str(role))

        members = partition.get("members")
        if not isinstance(members, list) or not members:
            raise SplitManifestError(f"partitions[{index}].members must be non-empty")
        artifact_count = partition.get("artifact_count")
        if artifact_count != len(members):
            raise SplitManifestError(f"partitions[{index}].artifact_count is inconsistent")
        expected_membership = _checksum(sha256_json(members))
        if partition.get("membership_commitment") != expected_membership:
            raise SplitManifestError(f"partitions[{index}].membership_commitment is inconsistent")
        for member in members:
            if not isinstance(member, Mapping) or not isinstance(member.get("artifact_id"), str):
                raise SplitManifestError(f"partitions[{index}] has an invalid member")
            artifact_id = str(member["artifact_id"])
            if artifact_id in artifact_ids:
                raise SplitManifestError(f"artifact {artifact_id!r} appears in two partitions")
            artifact_ids.add(artifact_id)
        total_artifacts += len(members)
    if roles != {"train", "development"}:
        raise SplitManifestError("partitions must contain train and development roles")

    corpus_file = value.get("corpus_file")
    if not isinstance(corpus_file, Mapping):
        raise SplitManifestError("corpus_file must be an object")
    if corpus_file.get("artifact_count") != total_artifacts:
        raise SplitManifestError("corpus_file.artifact_count is inconsistent")
    _require_checksum(corpus_file.get("sha256"), "corpus_file.sha256")
    _require_checksum(value.get("source_registry_sha256"), "source_registry_sha256")
    _require_checksum(
        value.get("quarantine_manifest_sha256"),
        "quarantine_manifest_sha256",
    )
    strategy = value.get("strategy")
    if not isinstance(strategy, Mapping):
        raise SplitManifestError("strategy must be an object")
    parameters = strategy.get("parameters")
    if not isinstance(parameters, Mapping):
        raise SplitManifestError("strategy.parameters must be an object")
    seed = value.get("seed")
    if parameters.get("seed") != str(seed):
        raise SplitManifestError("strategy.parameters.seed is inconsistent")
    test_fraction = parameters.get("test_fraction")
    if not isinstance(test_fraction, str):
        raise SplitManifestError("strategy.parameters.test_fraction must be a string")
    try:
        parsed_fraction = float(test_fraction)
    except ValueError as error:
        raise SplitManifestError("strategy.parameters.test_fraction is not numeric") from error
    if (
        not math.isfinite(parsed_fraction)
        or not 0.0 < parsed_fraction < 1.0
        or format(parsed_fraction, ".17g") != test_fraction
    ):
        raise SplitManifestError("strategy.parameters.test_fraction is not canonical")

    leakage_policy = value.get("leakage_policy")
    if not isinstance(leakage_policy, Mapping):
        raise SplitManifestError("leakage_policy must be an object")
    audit_file = leakage_policy.get("audit_file")
    if not isinstance(audit_file, Mapping):
        raise SplitManifestError("leakage_policy.audit_file must be an object")
    partition_identity: list[dict[str, Any]] = []
    for partition in partitions:
        if not isinstance(partition, Mapping):
            raise SplitManifestError("partition is malformed")
        file_value = partition.get("file")
        if not isinstance(file_value, Mapping):
            raise SplitManifestError("partition.file is malformed")
        partition_identity.append(
            {
                "partition_id": partition.get("partition_id"),
                "membership_commitment": partition.get("membership_commitment"),
                "file_sha256": file_value.get("sha256"),
            }
        )
    split_identity = sha256_json(
        {
            "corpus_file_sha256": corpus_file.get("sha256"),
            "corpus_fingerprint": value.get("corpus_fingerprint"),
            "source_registry_sha256": value.get("source_registry_sha256"),
            "quarantine_manifest_sha256": value.get("quarantine_manifest_sha256"),
            "seed": seed,
            "test_fraction": test_fraction,
            "strategy": strategy.get("type"),
            "holdout_values": strategy.get("holdout_values"),
            "partitions": partition_identity,
            "audit_sha256": audit_file.get("sha256"),
        }
    )
    if value.get("split_id") != f"split:sha256:{split_identity}":
        raise SplitManifestError("split_id is inconsistent with the split commitments")
    if value.get("membership_frozen") is not True:
        raise SplitManifestError("membership_frozen must equal true")
    if value.get("benchmark_locked") is not False:
        raise SplitManifestError("a split manifest cannot claim benchmark_locked")
