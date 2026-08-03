"""Deterministic HMAC counter stream for source-free NMFA resampling.

The stream implements only the frozen byte framing and unbiased bounded-index
draw.  It performs no random, clock, network, subprocess, or filesystem
operation.  A key supplied here is caller-bound material; this module does not
authenticate its origin, trusted time, one-use status, or custody.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Never, Self

__all__ = (
    "NMFA_COUNTER_STREAM_LABELS",
    "NMFACounterStream",
    "NMFACounterStreamError",
    "NMFACounterStreamErrorCode",
    "NMFACounterStreamStats",
    "nmfa_hmac_counter_block",
)

NMFA_COUNTER_STREAM_LABELS = (
    "bootstrap-v1",
    "control-n1-v1",
    "null-n2-v1",
    "prospective-bootstrap-v1",
    "prospective-null-n2-v1",
)

_KEY_BYTES = 32
_BLOCK_BYTES = 32
_BLOCK_SPACE = 1 << (_BLOCK_BYTES * 8)
_MAX_BOUND = 1 << 128
_MAX_U64 = (1 << 64) - 1
_MAX_ATTEMPTS_PER_DRAW = 16
_MAX_BLOCKS_PER_RUN = 320_000

_BlockSource = Callable[[bytes, str, int, int], bytes]


class NMFACounterStreamErrorCode(StrEnum):
    """Stable errors that never interpolate caller material."""

    COMPUTATION_LIMIT_BLOCKED = "COMPUTATION_LIMIT_BLOCKED"
    COUNTER_BLOCK_INVALID = "COUNTER_BLOCK_INVALID"
    COUNTER_EXHAUSTED = "COUNTER_EXHAUSTED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    STREAM_FAILED = "STREAM_FAILED"


class NMFACounterStreamError(ValueError):
    """Fixed-code local counter-stream error."""

    def __init__(self, code: NMFACounterStreamErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _fail(code: NMFACounterStreamErrorCode) -> Never:
    raise NMFACounterStreamError(code)


def _valid_u64(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_U64


def _validate_stream_identity(key: object, label: object, run_index: object) -> None:
    if (
        type(key) is not bytes
        or len(key) != _KEY_BYTES
        or type(label) is not str
        or label not in NMFA_COUNTER_STREAM_LABELS
        or not _valid_u64(run_index)
    ):
        _fail(NMFACounterStreamErrorCode.INVALID_ARGUMENT)


def _counter_message(label: str, run_index: int, counter: int) -> bytes:
    return (
        label.encode("ascii")
        + b"\x00"
        + run_index.to_bytes(8, "big")
        + b"\x00"
        + counter.to_bytes(8, "big")
    )


def _hmac_counter_block_unchecked(
    key: bytes,
    label: str,
    run_index: int,
    counter: int,
) -> bytes:
    return hmac.new(
        key,
        _counter_message(label, run_index, counter),
        hashlib.sha256,
    ).digest()


def nmfa_hmac_counter_block(
    key: bytes,
    label: str,
    run_index: int,
    counter: int,
) -> bytes:
    """Return one exactly framed HMAC-SHA256 counter block."""

    _validate_stream_identity(key, label, run_index)
    if not _valid_u64(counter):
        _fail(NMFACounterStreamErrorCode.INVALID_ARGUMENT)
    return _hmac_counter_block_unchecked(key, label, run_index, counter)


@dataclass(frozen=True)
class NMFACounterStreamStats:
    """Non-value-bearing deterministic consumption counters."""

    draws: int
    blocks_generated: int
    rejected_blocks: int
    next_counter: int


class NMFACounterStream:
    """One run-scoped deterministic stream of unbiased bounded indices."""

    __slots__ = (
        "_block_source",
        "_blocks_generated",
        "_draws",
        "_failed",
        "_key",
        "_label",
        "_max_blocks",
        "_next_counter",
        "_rejected_blocks",
        "_run_index",
    )

    def __init__(self, key: bytes, label: str, run_index: int) -> None:
        self._initialize(
            key,
            label,
            run_index,
            block_source=_hmac_counter_block_unchecked,
            max_blocks=_MAX_BLOCKS_PER_RUN,
        )

    def __repr__(self) -> str:
        return "<NMFACounterStream protected>"

    def _initialize(
        self,
        key: bytes,
        label: str,
        run_index: int,
        *,
        block_source: _BlockSource,
        max_blocks: int,
    ) -> None:
        _validate_stream_identity(key, label, run_index)
        if (
            not callable(block_source)
            or type(max_blocks) is not int
            or max_blocks < 1
            or max_blocks > _MAX_BLOCKS_PER_RUN
        ):
            _fail(NMFACounterStreamErrorCode.INVALID_ARGUMENT)
        self._key = key
        self._label = label
        self._run_index = run_index
        self._block_source = block_source
        self._max_blocks = max_blocks
        self._draws = 0
        self._blocks_generated = 0
        self._rejected_blocks = 0
        self._next_counter = 0
        self._failed = False

    @classmethod
    def _with_block_source_for_test(
        cls,
        key: bytes,
        label: str,
        run_index: int,
        block_source: _BlockSource,
        *,
        max_blocks: int = _MAX_BLOCKS_PER_RUN,
    ) -> Self:
        """Construct with a deterministic injected block source for tests."""

        instance = cls.__new__(cls)
        instance._initialize(
            key,
            label,
            run_index,
            block_source=block_source,
            max_blocks=max_blocks,
        )
        return instance

    def stats(self) -> NMFACounterStreamStats:
        """Return immutable consumption counters without key material."""

        return NMFACounterStreamStats(
            draws=self._draws,
            blocks_generated=self._blocks_generated,
            rejected_blocks=self._rejected_blocks,
            next_counter=self._next_counter,
        )

    def _poison(self, code: NMFACounterStreamErrorCode) -> Never:
        self._failed = True
        _fail(code)

    def _next_block(self) -> bytes:
        if self._blocks_generated >= self._max_blocks:
            self._poison(NMFACounterStreamErrorCode.COMPUTATION_LIMIT_BLOCKED)
        if self._next_counter > _MAX_U64:
            self._poison(NMFACounterStreamErrorCode.COUNTER_EXHAUSTED)
        counter = self._next_counter
        try:
            block = self._block_source(
                self._key,
                self._label,
                self._run_index,
                counter,
            )
        except Exception:
            self._poison(NMFACounterStreamErrorCode.COUNTER_BLOCK_INVALID)
        if type(block) is not bytes or len(block) != _BLOCK_BYTES:
            self._poison(NMFACounterStreamErrorCode.COUNTER_BLOCK_INVALID)
        self._next_counter = counter + 1
        self._blocks_generated += 1
        return block

    def draw_index(self, bound: int) -> int:
        """Draw uniformly from ``range(bound)`` without modulo bias.

        Bound one is fixed to return zero without consuming a counter block.
        Every other draw uses a complete unsigned 256-bit HMAC block per
        rejection attempt and permits at most 16 attempts.
        """

        if self._failed:
            _fail(NMFACounterStreamErrorCode.STREAM_FAILED)
        if type(bound) is not int or bound < 1 or bound > _MAX_BOUND:
            _fail(NMFACounterStreamErrorCode.INVALID_ARGUMENT)
        self._draws += 1
        if bound == 1:
            return 0
        threshold = _BLOCK_SPACE - (_BLOCK_SPACE % bound)
        for _ in range(_MAX_ATTEMPTS_PER_DRAW):
            candidate = int.from_bytes(self._next_block(), "big")
            if candidate < threshold:
                return candidate % bound
            self._rejected_blocks += 1
        self._poison(NMFACounterStreamErrorCode.COMPUTATION_LIMIT_BLOCKED)
