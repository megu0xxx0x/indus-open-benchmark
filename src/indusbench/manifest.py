"""Deterministic corpus fingerprints and release manifests."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from indusbench.transcription_admission import require_admitted_transcription_corpus


def canonical_json(value: Any) -> bytes:
    """Serialize JSON-compatible data deterministically."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def sha256_json(value: Any) -> str:
    """Return the SHA-256 digest of canonical JSON."""

    return hashlib.sha256(canonical_json(value)).hexdigest()


def corpus_digest(records: Iterable[Mapping[str, Any]]) -> str:
    """Hash a corpus independently of JSONL row order."""

    rows = sorted(
        (dict(record) for record in records),
        key=lambda record: (str(record.get("artifact_id", "")), sha256_json(record)),
    )
    return sha256_json(rows)


def build_manifest(
    records: Iterable[Mapping[str, Any]],
    *,
    schema_version: str,
    source_registry: Mapping[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic release description plus environment metadata."""

    materialized = list(records)
    require_admitted_transcription_corpus(materialized)
    rows = [dict(record) for record in materialized]
    sites: Counter[str] = Counter()
    periods: Counter[str] = Counter()
    object_types: Counter[str] = Counter()
    tokens = 0
    lines = 0
    for record in rows:
        site = record.get("site")
        if isinstance(site, Mapping):
            sites[str(site.get("site_id", "unknown"))] += 1
        period = record.get("period")
        if isinstance(period, Mapping):
            period_key = period.get("phase") or period.get("label") or "unknown"
        else:
            period_key = period or "unknown"
        periods[str(period_key)] += 1
        object_record = record.get("object")
        if isinstance(object_record, Mapping):
            object_types[str(object_record.get("object_type", "unknown"))] += 1
        for side in record.get("sides", []):
            for line in side.get("lines", []):
                lines += 1
                tokens += len(line.get("tokens", []))

    return {
        "manifest_version": "0.1.0",
        "schema_version": schema_version,
        "corpus_sha256": corpus_digest(rows),
        "source_registry_sha256": (
            sha256_json(source_registry) if source_registry is not None else None
        ),
        "counts": {
            "artifacts": len(rows),
            "lines": lines,
            "tokens": tokens,
            "sites": dict(sorted(sites.items())),
            "periods": dict(sorted(periods.items())),
            "object_types": dict(sorted(object_types.items())),
        },
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.system(),
        },
    }
