"""Matched null controls for structural claims."""

from __future__ import annotations

import copy
import random
from collections.abc import Iterable, Mapping
from typing import Any

from indusbench.transcription_admission import require_admitted_transcription_corpus


def _tokens_in_storage_order(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for side in record.get("sides", []):
        for line in side.get("lines", []):
            tokens.extend(token for token in line.get("tokens", []) if isinstance(token, dict))
    return tokens


def global_sign_shuffle(records: Iterable[Mapping[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Return a frequency- and length-preserving shuffled-sign control.

    The nested artifact metadata, token geometry, damage, and confidence are
    preserved. Only ``sign_id`` assignments are permuted. This is a structural
    null control, never a replacement for the observed corpus.
    """

    materialized = list(records)
    require_admitted_transcription_corpus(materialized)
    shuffled_records: list[dict[str, Any]] = [
        copy.deepcopy(dict(record)) for record in materialized
    ]
    tokens = [
        token
        for record in shuffled_records
        for token in _tokens_in_storage_order(record)
        if token.get("sign_id") is not None
    ]
    sign_ids = [token["sign_id"] for token in tokens]
    random.Random(seed).shuffle(sign_ids)
    for token, sign_id in zip(tokens, sign_ids, strict=True):
        token["sign_id"] = sign_id

    for record in shuffled_records:
        extensions = record.get("extensions")
        if not isinstance(extensions, dict):
            extensions = {}
            record["extensions"] = extensions
        extensions["indusbench:control"] = {
            "kind": "global_sign_shuffle",
            "seed": seed,
            "preserves": ["artifact_metadata", "sequence_lengths", "global_unigram_counts"],
            "destroys": ["within_sequence_order", "site_sign_association"],
        }
    return shuffled_records
