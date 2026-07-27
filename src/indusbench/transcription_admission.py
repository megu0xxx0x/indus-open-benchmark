"""Central fail-closed boundary for transcription-bridge artifacts.

The v0.1 transcription bridge produces private staging artifacts only.  No
bridge receipt currently proves admission to public, evaluation, or transform
flows, so presence of the extension key is sufficient to reject a record.
Keeping that rule here gives a future admission protocol one explicit boundary
to replace.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

TRANSCRIPTION_BRIDGE_EXTENSION = "indusbench:transcription_bridge"
UNADMITTED_TRANSCRIPTION_MESSAGE = (
    "transcription-bridge artifacts are not admitted to this operation"
)


class TranscriptionAdmissionError(ValueError):
    """Raised when a private transcription artifact reaches a public boundary."""

    def __init__(self) -> None:
        super().__init__(UNADMITTED_TRANSCRIPTION_MESSAGE)


def has_unadmitted_transcription_bridge(record: Mapping[str, Any]) -> bool:
    """Return whether ``record`` carries any v0.1 transcription-bridge marker.

    Marker contents are deliberately ignored.  Empty, null, malformed, or
    caller-asserted values are all unadmitted until an explicit verifier exists.
    """

    extensions = record.get("extensions")
    return isinstance(extensions, Mapping) and TRANSCRIPTION_BRIDGE_EXTENSION in extensions


def require_admitted_transcription_artifact(record: Mapping[str, Any]) -> None:
    """Reject a marked artifact with a fixed, non-sensitive error."""

    if has_unadmitted_transcription_bridge(record):
        raise TranscriptionAdmissionError


def require_admitted_transcription_corpus(
    records: Iterable[Mapping[str, Any]],
) -> None:
    """Reject a corpus if any artifact carries the private bridge marker."""

    for record in records:
        require_admitted_transcription_artifact(record)
