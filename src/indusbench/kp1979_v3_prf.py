"""Version-stable seed derivation and counter PRF for KP1979 V3."""

from __future__ import annotations

import hmac
from collections.abc import Sequence
from hashlib import sha256
from typing import Final, TypeVar

OFFICIAL_SEED_DOMAIN: Final = b"indus-open-benchmark\0kp1979-v3\0fixture-seed-v1\0"
PRF_BLOCK_DOMAIN: Final = b"KP1979-V3-PRF-BLOCK-V1\0"
SUBSEED_DOMAIN: Final = b"KP1979-V3-SUBSEED-V1\0"
MAX_LABEL_BYTES: Final = 255
MAX_REJECTION_ATTEMPTS: Final = 256
MAX_RANDOM_BOUND: Final = 2**32

_T = TypeVar("_T")


class KP1979V3PRFError(ValueError):
    """Raised when deterministic randomness inputs violate the closed contract."""


def _require_fixed_bytes(name: str, value: bytes, length: int) -> bytes:
    if type(value) is not bytes or len(value) != length:
        raise KP1979V3PRFError(f"{name} must be exactly {length} bytes")
    return value


def _commit_bytes(name: str, value: str) -> bytes:
    if (
        type(value) is not str
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise KP1979V3PRFError(f"{name} must be a full lowercase commit")
    return bytes.fromhex(value)


def _label_bytes(label: str) -> bytes:
    if type(label) is not str:
        raise KP1979V3PRFError("PRF label must be text")
    try:
        encoded = label.encode("ascii")
    except UnicodeEncodeError as exc:
        raise KP1979V3PRFError("PRF label must be ASCII") from exc
    if not encoded or len(encoded) > MAX_LABEL_BYTES:
        raise KP1979V3PRFError("PRF label length is outside the contract")
    return bytes([len(encoded)]) + encoded


def derive_official_seed(
    *,
    chain_hash: bytes,
    round_number: int,
    signature: bytes,
    plan_sha256: bytes,
    control_bundle_sha256: bytes,
    detector_artifact_sha256: bytes,
    control_commit: str,
    detector_commit: str,
    integration_commit: str,
) -> bytes:
    """Derive the official 32-byte fixture seed from fixed public commitments."""

    if type(round_number) is not int or not 1 <= round_number < 2**64:
        raise KP1979V3PRFError("round number is outside uint64")
    chain = _require_fixed_bytes("chain hash", chain_hash, 32)
    beacon_signature = _require_fixed_bytes("beacon signature", signature, 48)
    plan_digest = _require_fixed_bytes("plan digest", plan_sha256, 32)
    control_digest = _require_fixed_bytes(
        "control bundle digest",
        control_bundle_sha256,
        32,
    )
    detector_digest = _require_fixed_bytes(
        "detector artifact digest",
        detector_artifact_sha256,
        32,
    )
    payload = b"".join(
        (
            OFFICIAL_SEED_DOMAIN,
            chain,
            round_number.to_bytes(8, "big"),
            sha256(beacon_signature).digest(),
            plan_digest,
            control_digest,
            detector_digest,
            _commit_bytes("control commit", control_commit),
            _commit_bytes("detector commit", detector_commit),
            _commit_bytes("integration commit", integration_commit),
        )
    )
    return sha256(payload).digest()


def derive_subseed(seed: bytes, label: str) -> bytes:
    """Derive an independent fixed-length seed for one labeled stream."""

    root = _require_fixed_bytes("seed", seed, 32)
    return hmac.digest(root, SUBSEED_DOMAIN + _label_bytes(label), "sha256")


class DeterministicStream:
    """HMAC-SHA256 byte stream with fixed rejection-sampling semantics."""

    __slots__ = ("_buffer", "_counter", "_label", "_seed")

    def __init__(self, seed: bytes, label: str) -> None:
        self._seed = _require_fixed_bytes("seed", seed, 32)
        self._label = _label_bytes(label)
        self._counter = 0
        self._buffer = b""

    @property
    def block_counter(self) -> int:
        """Return the number of HMAC blocks materialized so far."""

        return self._counter

    def _next_block(self) -> bytes:
        if self._counter >= 2**64:
            raise KP1979V3PRFError("PRF counter exhausted")
        block = hmac.digest(
            self._seed,
            PRF_BLOCK_DOMAIN + self._label + self._counter.to_bytes(8, "big"),
            "sha256",
        )
        self._counter += 1
        return block

    def read(self, length: int) -> bytes:
        """Read exactly ``length`` deterministic bytes."""

        if type(length) is not int or not 0 <= length <= 1_048_576:
            raise KP1979V3PRFError("requested byte length is outside the contract")
        while len(self._buffer) < length:
            self._buffer += self._next_block()
        result = self._buffer[:length]
        self._buffer = self._buffer[length:]
        return result

    def randbelow(self, bound: int) -> int:
        """Return an unbiased integer in ``range(bound)``."""

        if type(bound) is not int or not 1 <= bound <= MAX_RANDOM_BOUND:
            raise KP1979V3PRFError("random bound is outside the contract")
        byte_length = max(1, (bound.bit_length() + 7) // 8)
        sample_space = 1 << (8 * byte_length)
        acceptance_limit = sample_space - sample_space % bound
        for _ in range(MAX_REJECTION_ATTEMPTS):
            candidate = int.from_bytes(self.read(byte_length), "big")
            if candidate < acceptance_limit:
                return candidate % bound
        raise KP1979V3PRFError("rejection-sampling attempt bound exceeded")

    def randint(self, lower: int, upper: int) -> int:
        """Return an unbiased integer in the inclusive closed interval."""

        if type(lower) is not int or type(upper) is not int or lower > upper:
            raise KP1979V3PRFError("integer interval is invalid")
        width = upper - lower + 1
        if width > MAX_RANDOM_BOUND:
            raise KP1979V3PRFError("integer interval is too wide")
        return lower + self.randbelow(width)

    def choice(self, values: Sequence[_T]) -> _T:
        """Select one element from a non-empty stable sequence."""

        if isinstance(values, (str, bytes, bytearray)) or not isinstance(
            values,
            Sequence,
        ):
            raise KP1979V3PRFError("choice input must be a non-text sequence")
        if not values:
            raise KP1979V3PRFError("choice input must not be empty")
        return values[self.randbelow(len(values))]

    def shuffled(self, values: Sequence[_T]) -> tuple[_T, ...]:
        """Return a deterministic Fisher-Yates permutation."""

        if isinstance(values, (str, bytes, bytearray)) or not isinstance(
            values,
            Sequence,
        ):
            raise KP1979V3PRFError("shuffle input must be a non-text sequence")
        output = list(values)
        for index in range(len(output) - 1, 0, -1):
            replacement = self.randbelow(index + 1)
            output[index], output[replacement] = (
                output[replacement],
                output[index],
            )
        return tuple(output)

    def sample(self, values: Sequence[_T], count: int) -> tuple[_T, ...]:
        """Select ``count`` distinct values without replacement."""

        if type(count) is not int:
            raise KP1979V3PRFError("sample count must be an integer")
        if isinstance(values, (str, bytes, bytearray)) or not isinstance(
            values,
            Sequence,
        ):
            raise KP1979V3PRFError("sample input must be a non-text sequence")
        if not 0 <= count <= len(values):
            raise KP1979V3PRFError("sample count is outside the sequence")
        return self.shuffled(values)[:count]


__all__ = [
    "MAX_LABEL_BYTES",
    "MAX_RANDOM_BOUND",
    "MAX_REJECTION_ATTEMPTS",
    "OFFICIAL_SEED_DOMAIN",
    "PRF_BLOCK_DOMAIN",
    "SUBSEED_DOMAIN",
    "DeterministicStream",
    "KP1979V3PRFError",
    "derive_official_seed",
    "derive_subseed",
]
