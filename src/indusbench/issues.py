"""Machine-readable validation and audit issues."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Issue:
    """A stable, serializable problem found in a corpus or benchmark."""

    code: str
    path: str
    message: str
    severity: Severity = "error"

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-compatible representation."""

        return asdict(self)
