"""Fail-closed source quarantine for normal corpus and evaluation paths."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit

NORMAL_PURPOSES = frozenset(
    {
        "corpus_ingestion",
        "training",
        "development_evaluation",
        "final_evaluation",
        "redistribution",
    }
)
PURPOSES = NORMAL_PURPOSES | {"schema_validation", "audit_only"}
CHECKSUM_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_SCAN_NODES_PER_RECORD = 100_000

_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "registry_id",
        "generated_at",
        "default_policy",
        "trusted_internal_source_ids",
        "rules",
        "manifest_sha256",
    }
)
_RULE_KEYS = frozenset(
    {
        "rule_id",
        "entity_ids",
        "status",
        "match",
        "reason_codes",
        "prohibited_purposes",
        "audit_use_allowed",
        "evidence_entry_id",
        "reviewed_on",
        "next_review_on",
        "notes",
    }
)
_MATCH_KEYS = frozenset({"source_ids", "locator_prefixes", "revisions"})


class QuarantineManifestError(ValueError):
    """Raised when a quarantine manifest is not self-consistent."""


class CorpusQuarantineError(ValueError):
    """Raised when a normal data path encounters quarantined material."""

    def __init__(self, report: QuarantineReport) -> None:
        super().__init__(
            f"corpus is blocked by {len(report.findings)} quarantine finding(s) "
            f"for purpose {report.purpose!r}"
        )
        self.report = report


@dataclass(frozen=True)
class QuarantineFinding:
    code: str
    artifact_id: str
    path: str
    source_id: str | None
    rule_id: str | None
    matched_by: str
    reason_codes: tuple[str, ...]
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "artifact_id": self.artifact_id,
            "path": self.path,
            "source_id": self.source_id,
            "rule_id": self.rule_id,
            "matched_by": self.matched_by,
            "reason_codes": list(self.reason_codes),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class QuarantineReport:
    purpose: str
    manifest_sha256: str
    source_registry_sha256: str
    artifact_count: int
    findings: tuple[QuarantineFinding, ...]

    @property
    def allowed(self) -> bool:
        return self.purpose == "audit_only" or not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "purpose": self.purpose,
            "manifest_sha256": self.manifest_sha256,
            "source_registry_sha256": self.source_registry_sha256,
            "artifact_count": self.artifact_count,
            "finding_count": len(self.findings),
            "audit_only_override": self.purpose == "audit_only",
            "findings": [finding.as_dict() for finding in self.findings],
        }


def quarantine_manifest_digest(value: Mapping[str, Any]) -> str:
    """Hash every manifest field except the self-commitment."""

    payload = dict(value)
    payload.pop("manifest_sha256", None)
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def registry_digest(value: Mapping[str, Any]) -> str:
    """Return a deterministic commitment to a complete JSON registry."""

    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def validate_quarantine_manifest(value: Mapping[str, Any]) -> None:
    """Validate closed fields, uniqueness, URL safety, dates, and the self-hash."""

    _require_exact_keys(value, _TOP_LEVEL_KEYS, "$")
    if value.get("schema_version") != "0.1.0":
        raise QuarantineManifestError("$.schema_version must equal '0.1.0'")
    if value.get("registry_id") != "indus-open-benchmark:quarantine":
        raise QuarantineManifestError("$.registry_id is not the quarantine registry")
    if value.get("default_policy") != "deny_unknown_sources":
        raise QuarantineManifestError("$.default_policy must deny unknown sources")

    trusted = _string_list(
        value.get("trusted_internal_source_ids"),
        "$.trusted_internal_source_ids",
        minimum=1,
    )
    _require_unique(trusted, "$.trusted_internal_source_ids")

    rules = value.get("rules")
    if not isinstance(rules, list) or not rules or len(rules) > 256:
        raise QuarantineManifestError("$.rules must contain between 1 and 256 rules")
    rule_ids: list[str] = []
    for index, raw_rule in enumerate(rules):
        path = f"$.rules[{index}]"
        if not isinstance(raw_rule, Mapping):
            raise QuarantineManifestError(f"{path} must be an object")
        _require_exact_keys(raw_rule, _RULE_KEYS, path)
        rule_id = _nonempty_string(raw_rule.get("rule_id"), f"{path}.rule_id")
        rule_ids.append(rule_id)
        if raw_rule.get("status") != "quarantined":
            raise QuarantineManifestError(f"{path}.status must equal 'quarantined'")
        if raw_rule.get("audit_use_allowed") is not True:
            raise QuarantineManifestError(f"{path}.audit_use_allowed must equal true")
        _nonempty_string(raw_rule.get("evidence_entry_id"), f"{path}.evidence_entry_id")
        _string_list(raw_rule.get("entity_ids"), f"{path}.entity_ids", minimum=1)
        _string_list(raw_rule.get("reason_codes"), f"{path}.reason_codes", minimum=1)
        prohibited = _string_list(
            raw_rule.get("prohibited_purposes"),
            f"{path}.prohibited_purposes",
            minimum=1,
        )
        if not set(prohibited).issubset(NORMAL_PURPOSES):
            raise QuarantineManifestError(f"{path}.prohibited_purposes is invalid")

        match = raw_rule.get("match")
        if not isinstance(match, Mapping):
            raise QuarantineManifestError(f"{path}.match must be an object")
        _require_exact_keys(match, _MATCH_KEYS, f"{path}.match")
        source_ids = _string_list(match.get("source_ids"), f"{path}.match.source_ids")
        locators = _string_list(
            match.get("locator_prefixes"),
            f"{path}.match.locator_prefixes",
        )
        revisions = _string_list(match.get("revisions"), f"{path}.match.revisions")
        if not source_ids and not locators and not revisions:
            raise QuarantineManifestError(f"{path}.match must contain a matcher")
        for locator_index, locator in enumerate(locators):
            parsed = urlsplit(locator)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise QuarantineManifestError(
                    f"{path}.match.locator_prefixes[{locator_index}] "
                    "must be a credential-free HTTPS prefix"
                )

        reviewed = _iso_date(raw_rule.get("reviewed_on"), f"{path}.reviewed_on")
        next_review = raw_rule.get("next_review_on")
        if next_review is not None:
            parsed_next = _iso_date(next_review, f"{path}.next_review_on")
            if parsed_next <= reviewed:
                raise QuarantineManifestError(
                    f"{path}.next_review_on must be later than reviewed_on"
                )
        _nonempty_string(raw_rule.get("notes"), f"{path}.notes")
    _require_unique(rule_ids, "$.rules[*].rule_id")

    manifest_sha256 = value.get("manifest_sha256")
    if not isinstance(manifest_sha256, str) or not CHECKSUM_PATTERN.fullmatch(manifest_sha256):
        raise QuarantineManifestError("$.manifest_sha256 must be a SHA-256 commitment")
    expected = quarantine_manifest_digest(value)
    if manifest_sha256 != expected:
        raise QuarantineManifestError(
            "$.manifest_sha256 does not match the canonical manifest payload"
        )


def inspect_corpus_quarantine(
    records: Iterable[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Any],
    quarantine_manifest: Mapping[str, Any],
    purpose: str,
) -> QuarantineReport:
    """Inspect provenance and rights before a corpus enters a normal data path."""

    if purpose not in PURPOSES:
        raise ValueError(f"unsupported quarantine purpose: {purpose!r}")
    validate_quarantine_manifest(quarantine_manifest)
    source_index = _source_registry_index(source_registry)
    internal_ids = frozenset(
        _string_list(
            quarantine_manifest.get("trusted_internal_source_ids"),
            "$.trusted_internal_source_ids",
            minimum=1,
        )
    )
    rules = quarantine_manifest["rules"]
    if not isinstance(rules, list):
        raise QuarantineManifestError("$.rules must be an array")

    rows = list(records)
    findings: list[QuarantineFinding] = []
    for record_index, record in enumerate(rows):
        artifact_id = _artifact_id(record, record_index)
        references = list(_source_references(record))
        reference_ids = {
            source_id for _, source_id in references if isinstance(source_id, str) and source_id
        }
        for path, source_id in references:
            if not isinstance(source_id, str) or not source_id:
                findings.append(
                    _finding(
                        "source_id_missing",
                        artifact_id,
                        path,
                        None,
                        detail="every source record and image must name a source_id",
                    )
                )
                continue
            if source_id in internal_ids:
                if not _is_attested_synthetic(record, reference_ids, internal_ids):
                    findings.append(
                        _finding(
                            "internal_source_attestation_failed",
                            artifact_id,
                            path,
                            source_id,
                            detail=(
                                "an internal synthetic source_id requires synthetic artifact, "
                                "sign, locator, and rights attestations"
                            ),
                        )
                    )
            elif source_id not in source_index:
                findings.append(
                    _finding(
                        "unknown_source_id",
                        artifact_id,
                        path,
                        source_id,
                        detail=(
                            "source_id is absent from the supplied source registry; "
                            "deny_unknown_sources is active"
                        ),
                    )
                )
            elif purpose not in {"schema_validation", "audit_only"}:
                findings.extend(
                    _rights_findings(
                        source_index[source_id].get("rights"),
                        artifact_id=artifact_id,
                        path=f"$source_registry.sources[{source_id!r}].rights",
                        source_id=source_id,
                        purpose=purpose,
                    )
                )

        string_nodes = tuple(_walk_strings(record))
        for raw_rule in rules:
            if not isinstance(raw_rule, Mapping):
                continue
            matched = _match_rule(raw_rule, references, string_nodes)
            if matched is None:
                continue
            matched_by, path, source_id = matched
            prohibited = raw_rule.get("prohibited_purposes")
            if purpose not in {"audit_only", "schema_validation"} and (
                not isinstance(prohibited, list) or purpose not in prohibited
            ):
                continue
            findings.append(
                QuarantineFinding(
                    code="quarantine_rule_match",
                    artifact_id=artifact_id,
                    path=path,
                    source_id=source_id,
                    rule_id=str(raw_rule.get("rule_id")),
                    matched_by=matched_by,
                    reason_codes=tuple(
                        str(reason)
                        for reason in raw_rule.get("reason_codes", [])
                        if isinstance(reason, str)
                    ),
                    detail=(
                        "matched a content-addressed quarantine rule; only an explicit "
                        "audit_only path may inspect this material"
                    ),
                )
            )

        if purpose not in {"schema_validation", "audit_only"}:
            findings.extend(
                _rights_findings(
                    record.get("rights"),
                    artifact_id=artifact_id,
                    path=f"$record[{record_index}].rights",
                    source_id=None,
                    purpose=purpose,
                )
            )
            images = record.get("images")
            if isinstance(images, list):
                for image_index, image in enumerate(images):
                    if isinstance(image, Mapping):
                        findings.extend(
                            _rights_findings(
                                image.get("rights"),
                                artifact_id=artifact_id,
                                path=(f"$record[{record_index}].images[{image_index}].rights"),
                                source_id=(
                                    image.get("source_id")
                                    if isinstance(image.get("source_id"), str)
                                    else None
                                ),
                                purpose=purpose,
                            )
                        )

    unique = {
        (
            finding.code,
            finding.artifact_id,
            finding.path,
            finding.source_id,
            finding.rule_id,
            finding.matched_by,
        ): finding
        for finding in findings
    }
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda finding: (
                finding.artifact_id,
                finding.path,
                finding.code,
                finding.rule_id or "",
                finding.source_id or "",
            ),
        )
    )
    return QuarantineReport(
        purpose=purpose,
        manifest_sha256=str(quarantine_manifest["manifest_sha256"]),
        source_registry_sha256=registry_digest(source_registry),
        artifact_count=len(rows),
        findings=ordered,
    )


def require_corpus_permitted(
    records: Iterable[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Any],
    quarantine_manifest: Mapping[str, Any],
    purpose: str,
) -> QuarantineReport:
    """Return the report or raise with its structured findings."""

    report = inspect_corpus_quarantine(
        records,
        source_registry=source_registry,
        quarantine_manifest=quarantine_manifest,
        purpose=purpose,
    )
    if not report.allowed:
        raise CorpusQuarantineError(report)
    return report


def _source_registry_index(
    source_registry: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    sources = source_registry.get("sources")
    if not isinstance(sources, list):
        raise QuarantineManifestError("$source_registry.sources must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise QuarantineManifestError(f"$source_registry.sources[{index}] must be an object")
        source_id = _nonempty_string(
            source.get("source_id"),
            f"$source_registry.sources[{index}].source_id",
        )
        if source_id in result:
            raise QuarantineManifestError(
                f"$source_registry contains duplicate source_id {source_id!r}"
            )
        result[source_id] = source
    return result


def _source_references(
    record: Mapping[str, Any],
) -> Iterator[tuple[str, object]]:
    source_records = record.get("source_records")
    if isinstance(source_records, list):
        for index, source in enumerate(source_records):
            if isinstance(source, Mapping):
                yield f"$.source_records[{index}].source_id", source.get("source_id")
            else:
                yield f"$.source_records[{index}]", None
    else:
        yield "$.source_records", None
    images = record.get("images")
    if isinstance(images, list):
        for index, image in enumerate(images):
            if isinstance(image, Mapping):
                yield f"$.images[{index}].source_id", image.get("source_id")
            else:
                yield f"$.images[{index}]", None
    elif images is not None:
        yield "$.images", None


def _walk_strings(value: object) -> Iterator[tuple[str, str]]:
    stack: list[tuple[str, object]] = [("$", value)]
    nodes = 0
    while stack:
        path, current = stack.pop()
        nodes += 1
        if nodes > MAX_SCAN_NODES_PER_RECORD:
            raise ValueError(
                f"{path} exceeds the {MAX_SCAN_NODES_PER_RECORD}-node quarantine scan limit"
            )
        if isinstance(current, str):
            yield path, current
        elif isinstance(current, list):
            stack.extend(
                (f"{path}[{index}]", item) for index, item in reversed(list(enumerate(current)))
            )
        elif isinstance(current, Mapping):
            for key in sorted(current, reverse=True):
                if isinstance(key, str):
                    stack.append((f"{path}.{key}", current[key]))


def _match_rule(
    rule: Mapping[str, Any],
    references: list[tuple[str, object]],
    string_nodes: tuple[tuple[str, str], ...],
) -> tuple[str, str, str | None] | None:
    match = rule.get("match")
    if not isinstance(match, Mapping):
        return None
    source_ids = {value for value in match.get("source_ids", []) if isinstance(value, str)}
    for path, source_id in references:
        if isinstance(source_id, str) and source_id in source_ids:
            return "source_id", path, source_id

    locator_prefixes = tuple(
        value.casefold() for value in match.get("locator_prefixes", []) if isinstance(value, str)
    )
    revisions = {value.casefold() for value in match.get("revisions", []) if isinstance(value, str)}
    for path, value in string_nodes:
        normalized = unicodedata.normalize("NFKC", value).strip().casefold()
        if any(normalized.startswith(prefix) for prefix in locator_prefixes):
            return "locator_prefix", path, None
        if normalized in revisions:
            return "revision", path, None
    return None


def _rights_findings(
    rights: object,
    *,
    artifact_id: str,
    path: str,
    source_id: str | None,
    purpose: str,
) -> list[QuarantineFinding]:
    if not isinstance(rights, Mapping):
        return [
            _finding(
                "rights_missing_or_malformed",
                artifact_id,
                path,
                source_id,
                detail="normal data paths require a structured rights record",
            )
        ]
    status = rights.get("status")
    if status in {"restricted", "unknown"} or not isinstance(status, str):
        return [
            _finding(
                "rights_status_not_permitted",
                artifact_id,
                f"{path}.status",
                source_id,
                detail=f"rights status {status!r} is not permitted for {purpose}",
            )
        ]
    if purpose == "final_evaluation":
        return []
    if rights.get("derivatives") is not True:
        return [
            _finding(
                "derivatives_not_permitted",
                artifact_id,
                f"{path}.derivatives",
                source_id,
                detail=f"derivative use is not permitted for {purpose}",
            )
        ]
    if (
        purpose in {"corpus_ingestion", "training", "redistribution"}
        and rights.get("redistribution") is not True
    ):
        return [
            _finding(
                "redistribution_not_permitted",
                artifact_id,
                f"{path}.redistribution",
                source_id,
                detail=f"redistribution is not permitted for {purpose}",
            )
        ]
    return []


def _is_attested_synthetic(
    record: Mapping[str, Any],
    reference_ids: set[str],
    internal_ids: frozenset[str],
) -> bool:
    artifact_id = record.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.casefold().startswith(
        ("syn:", "synthetic:")
    ):
        return False
    if not reference_ids or not reference_ids.issubset(internal_ids):
        return False
    statements: list[str] = []
    rights = record.get("rights")
    if isinstance(rights, Mapping) and isinstance(rights.get("statement"), str):
        statements.append(str(rights["statement"]))
    images = record.get("images")
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, Mapping):
                return False
            image_rights = image.get("rights")
            if isinstance(image_rights, Mapping) and isinstance(image_rights.get("statement"), str):
                statements.append(str(image_rights["statement"]))
    if not statements or any(
        not {"synthetic", "fixture"}.intersection(
            unicodedata.normalize("NFKC", statement).casefold().split()
        )
        for statement in statements
    ):
        return False
    for path, value in _walk_strings(record):
        if path.endswith(".sign_id") and value and not value.startswith("SYN:"):
            return False
        if path.endswith((".locator", ".uri")) and (
            value.startswith("urn:synthetic:") or urlsplit(value).hostname == "example.invalid"
        ):
            continue
        if path.endswith((".locator", ".uri")):
            return False
    return True


def _artifact_id(record: Mapping[str, Any], index: int) -> str:
    artifact_id = record.get("artifact_id")
    return artifact_id if isinstance(artifact_id, str) and artifact_id else f"<row:{index}>"


def _finding(
    code: str,
    artifact_id: str,
    path: str,
    source_id: str | None,
    *,
    detail: str,
) -> QuarantineFinding:
    return QuarantineFinding(
        code=code,
        artifact_id=artifact_id,
        path=path,
        source_id=source_id,
        rule_id=None,
        matched_by="policy",
        reason_codes=(),
        detail=detail,
    )


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: frozenset[str],
    path: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise QuarantineManifestError(
            f"{path} has invalid keys; missing={sorted(expected - actual)!r}, "
            f"unexpected={sorted(actual - expected)!r}"
        )


def _nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuarantineManifestError(f"{path} must be a nonempty string")
    return value


def _string_list(
    value: object,
    path: str,
    *,
    minimum: int = 0,
) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise QuarantineManifestError(f"{path} must be an array of nonempty strings")
    if len(value) < minimum:
        raise QuarantineManifestError(f"{path} must contain at least {minimum} item(s)")
    _require_unique(value, path)
    return list(value)


def _require_unique(values: list[str], path: str) -> None:
    if len(values) != len(set(values)):
        raise QuarantineManifestError(f"{path} must not contain duplicates")


def _iso_date(value: object, path: str) -> date:
    string = _nonempty_string(value, path)
    try:
        return date.fromisoformat(string)
    except ValueError as error:
        raise QuarantineManifestError(f"{path} must be an ISO date") from error
