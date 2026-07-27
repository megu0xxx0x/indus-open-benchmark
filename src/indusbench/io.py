"""Small, dependency-free readers and writers for benchmark records."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


class CorpusFormatError(ValueError):
    """Raised when a corpus file is not valid JSONL."""


class _StrictJsonError(ValueError):
    """Internal marker for JSON constructs that the standard parser accepts."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJsonError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> None:
    raise _StrictJsonError(f"non-finite number {value!r}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _StrictJsonError(f"non-finite number {value!r}")
    return parsed


def _strict_json_loads(value: str) -> Any:
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite_constant,
        parse_float=_parse_finite_float,
    )


def decode_json(value: str | bytes, *, source: str = "<bytes>") -> Any:
    """Decode one strict finite UTF-8 JSON document."""

    try:
        text = value.decode("utf-8") if isinstance(value, bytes) else value
        return _strict_json_loads(text)
    except (json.JSONDecodeError, UnicodeError, _StrictJsonError) as error:
        raise CorpusFormatError(f"{source}: invalid JSON: {error}") from error


def read_json(path: str | Path) -> Any:
    """Read one strict UTF-8 JSON document."""

    source = Path(path)
    with source.open("rb") as handle:
        return decode_json(handle.read(), source=str(source))


def encode_json(value: Any) -> bytes:
    """Return the exact deterministic bytes emitted by :func:`write_json`."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def encode_jsonl_record(record: Mapping[str, Any]) -> bytes:
    """Return one exact deterministic JSONL record, including its LF."""

    return (
        json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: str | Path, value: Any) -> None:
    """Write one deterministic, human-readable UTF-8 JSON document."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        handle.write(encode_json(value))


def iter_jsonl(path: str | Path) -> Iterator[JsonObject]:
    """Yield JSON objects from a UTF-8 JSON Lines file."""

    source = Path(path)
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = _strict_json_loads(line)
            except (json.JSONDecodeError, UnicodeError, _StrictJsonError) as error:
                raise CorpusFormatError(f"{source}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(value, dict):
                raise CorpusFormatError(f"{source}:{line_number}: each JSONL row must be an object")
            yield value


def read_jsonl(path: str | Path) -> list[JsonObject]:
    """Read all records from a JSON Lines file."""

    return list(iter_jsonl(path))


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> None:
    """Write deterministic JSON objects, one per line."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        for record in records:
            handle.write(encode_jsonl_record(record))
