"""Cross-partition leakage auditing for artifact records."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias, TypeVar

ArtifactRecord: TypeAlias = Mapping[str, object]

_DIRECT_IMAGE_HASH_FIELDS = frozenset({"image_hash", "image_sha256"})
_IMAGE_CONTAINER_FIELDS = frozenset(
    {"image", "images", "media", "photograph", "photographs", "scan", "scans"}
)
_UNREADABLE_SIGN = "<unreadable>"
_Key = TypeVar("_Key", bound=Hashable)


@dataclass(frozen=True)
class LeakageFinding:
    """One key that occurs in both benchmark partitions."""

    value: str
    train_artifact_ids: tuple[str, ...]
    test_artifact_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "train_artifact_ids": list(self.train_artifact_ids),
            "test_artifact_ids": list(self.test_artifact_ids),
        }


@dataclass(frozen=True)
class LeakageReport:
    """Leakage findings grouped by independent detection mechanism."""

    family_leakage: tuple[LeakageFinding, ...] = ()
    image_hash_leakage: tuple[LeakageFinding, ...] = ()
    sequence_leakage: tuple[LeakageFinding, ...] = ()
    catalog_crosswalk_leakage: tuple[LeakageFinding, ...] = ()

    @property
    def has_leakage(self) -> bool:
        return bool(
            self.family_leakage
            or self.image_hash_leakage
            or self.sequence_leakage
            or self.catalog_crosswalk_leakage
        )

    @property
    def is_clean(self) -> bool:
        return not self.has_leakage

    def as_dict(self) -> dict[str, object]:
        return {
            "has_leakage": self.has_leakage,
            "family_leakage": [finding.as_dict() for finding in self.family_leakage],
            "image_hash_leakage": [finding.as_dict() for finding in self.image_hash_leakage],
            "sequence_leakage": [finding.as_dict() for finding in self.sequence_leakage],
            "catalog_crosswalk_leakage": [
                finding.as_dict() for finding in self.catalog_crosswalk_leakage
            ],
        }


def _stable_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _artifact_id(record: ArtifactRecord, fallback: str) -> str:
    return _stable_text(record.get("artifact_id")) or fallback


def _family_key(record: ArtifactRecord) -> str:
    family_id = _stable_text(record.get("duplicate_family_id"))
    if family_id is not None:
        return f"family:{family_id}"
    artifact_id = _stable_text(record.get("artifact_id"))
    return f"artifact:{artifact_id}" if artifact_id is not None else ""


def _normalize_hash(value: object) -> str | None:
    text = _stable_text(value)
    if text is None:
        return None
    normalized = text.casefold()
    for prefix in ("sha256:", "sha-256:"):
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix).strip()
    return normalized or None


def _extract_image_hashes(record: ArtifactRecord) -> set[str]:
    hashes: set[str] = set()

    def visit(node: object, *, image_context: bool = False) -> None:
        if isinstance(node, Mapping):
            for raw_key, value in node.items():
                key = str(raw_key).casefold().replace("-", "_")
                next_image_context = image_context or key in _IMAGE_CONTAINER_FIELDS
                if key in _DIRECT_IMAGE_HASH_FIELDS or (
                    next_image_context and key in {"sha256", "checksum"}
                ):
                    image_hash = _normalize_hash(value)
                    if image_hash is not None:
                        hashes.add(image_hash)
                elif isinstance(value, (Mapping, list, tuple)):
                    visit(value, image_context=next_image_context)
        elif isinstance(node, (list, tuple)):
            for value in node:
                visit(value, image_context=image_context)

    visit(record)
    return hashes


def extract_image_hashes(record: ArtifactRecord) -> frozenset[str]:
    """Return normalized image hashes attached anywhere below an artifact."""
    return frozenset(_extract_image_hashes(record))


def extract_catalog_crosswalks(
    record: ArtifactRecord,
) -> frozenset[tuple[str, str]]:
    """Return complete catalog/identifier aliases attached to an artifact."""
    aliases: set[tuple[str, str]] = set()
    crosswalk = record.get("catalog_crosswalk")
    if not isinstance(crosswalk, Sequence) or isinstance(crosswalk, (str, bytes)):
        return frozenset()
    for entry in crosswalk:
        if not isinstance(entry, Mapping):
            continue
        catalog = _stable_text(entry.get("catalog"))
        identifier = _stable_text(entry.get("identifier"))
        if catalog is not None and identifier is not None:
            aliases.add((catalog, identifier))
    return frozenset(aliases)


def _numeric_index(token: Mapping[str, object], field: str) -> tuple[int, float]:
    value = token.get(field)
    if isinstance(value, bool):
        return 1, 0.0
    if isinstance(value, (int, float)):
        return 0, float(value)
    if isinstance(value, str):
        try:
            return 0, float(value.strip())
        except ValueError:
            pass
    return 1, 0.0


def _normalize_token_sequence(
    tokens: Sequence[object],
    *,
    reading_direction: object = None,
) -> tuple[str, ...]:
    indexed_tokens = list(enumerate(tokens))
    if indexed_tokens and all(
        isinstance(token, Mapping) and _numeric_index(token, "reading_index")[0] == 0
        for _, token in indexed_tokens
    ):
        indexed_tokens.sort(
            key=lambda item: (
                _numeric_index(item[1], "reading_index")[1]
                if isinstance(item[1], Mapping)
                else 0.0,
                item[0],
            )
        )
    elif indexed_tokens and all(
        isinstance(token, Mapping) and _numeric_index(token, "visual_index")[0] == 0
        for _, token in indexed_tokens
    ):
        indexed_tokens.sort(
            key=lambda item: (
                _numeric_index(item[1], "visual_index")[1] if isinstance(item[1], Mapping) else 0.0,
                item[0],
            )
        )
        if reading_direction in {"right_to_left", "bottom_to_top"}:
            indexed_tokens.reverse()

    signs: list[str] = []
    has_readable_sign = False
    for _, token in indexed_tokens:
        if isinstance(token, Mapping):
            sign = _stable_text(token.get("sign_id"))
        else:
            sign = _stable_text(token)
        if sign is None:
            signs.append(_UNREADABLE_SIGN)
        else:
            signs.append(sign)
            has_readable_sign = True
    return tuple(signs) if has_readable_sign else ()


def _extract_sequences(record: ArtifactRecord) -> set[tuple[str, ...]]:
    sequences: set[tuple[str, ...]] = set()

    def add_line(line: object) -> None:
        tokens = line.get("tokens") if isinstance(line, Mapping) else line
        if isinstance(tokens, Sequence) and not isinstance(tokens, (str, bytes)):
            reading_direction = line.get("reading_direction") if isinstance(line, Mapping) else None
            normalized = _normalize_token_sequence(
                tokens,
                reading_direction=reading_direction,
            )
            if normalized:
                sequences.add(normalized)

    sides = record.get("sides")
    if isinstance(sides, Sequence) and not isinstance(sides, (str, bytes)):
        for side in sides:
            if not isinstance(side, Mapping):
                continue
            lines = side.get("lines")
            if isinstance(lines, Sequence) and not isinstance(lines, (str, bytes)):
                for line in lines:
                    add_line(line)
    else:
        lines = record.get("lines")
        if isinstance(lines, Sequence) and not isinstance(lines, (str, bytes)):
            for line in lines:
                add_line(line)
        elif "tokens" in record:
            add_line(record)
    return sequences


def extract_normalized_sequences(
    record: ArtifactRecord,
) -> frozenset[tuple[str, ...]]:
    """Return exact, reading-order line fingerprints for leakage grouping."""
    return frozenset(_extract_sequences(record))


def _partition_index(
    records: Iterable[ArtifactRecord],
    *,
    partition_name: str,
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[tuple[str, ...], set[str]],
    dict[tuple[str, str], set[str]],
]:
    families: dict[str, set[str]] = defaultdict(set)
    image_hashes: dict[str, set[str]] = defaultdict(set)
    sequences: dict[tuple[str, ...], set[str]] = defaultdict(set)
    catalog_crosswalks: dict[tuple[str, str], set[str]] = defaultdict(set)
    for index, record in enumerate(records):
        artifact_id = _artifact_id(record, f"<{partition_name}:{index}>")
        family_key = _family_key(record)
        if family_key:
            families[family_key].add(artifact_id)
        for image_hash in _extract_image_hashes(record):
            image_hashes[image_hash].add(artifact_id)
        for sequence in _extract_sequences(record):
            sequences[sequence].add(artifact_id)
        for catalog_alias in extract_catalog_crosswalks(record):
            catalog_crosswalks[catalog_alias].add(artifact_id)
    return families, image_hashes, sequences, catalog_crosswalks


def _find_overlaps(
    train_index: Mapping[_Key, set[str]],
    test_index: Mapping[_Key, set[str]],
    *,
    render_value: Callable[[_Key], str],
) -> tuple[LeakageFinding, ...]:
    findings = [
        LeakageFinding(
            value=render_value(value),
            train_artifact_ids=tuple(sorted(train_index[value])),
            test_artifact_ids=tuple(sorted(test_index[value])),
        )
        for value in train_index.keys() & test_index.keys()
    ]
    return tuple(sorted(findings, key=lambda finding: finding.value))


def audit_leakage(
    train_records: Iterable[ArtifactRecord],
    test_records: Iterable[ArtifactRecord],
) -> LeakageReport:
    """Audit family, image, sequence, and catalog-alias leakage."""
    train_families, train_hashes, train_sequences, train_crosswalks = _partition_index(
        train_records,
        partition_name="train",
    )
    test_families, test_hashes, test_sequences, test_crosswalks = _partition_index(
        test_records,
        partition_name="test",
    )
    return LeakageReport(
        family_leakage=_find_overlaps(
            train_families,
            test_families,
            render_value=str,
        ),
        image_hash_leakage=_find_overlaps(
            train_hashes,
            test_hashes,
            render_value=str,
        ),
        sequence_leakage=_find_overlaps(
            train_sequences,
            test_sequences,
            render_value=lambda sequence: json.dumps(
                sequence,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
        catalog_crosswalk_leakage=_find_overlaps(
            train_crosswalks,
            test_crosswalks,
            render_value=lambda alias: json.dumps(
                alias,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
    )
