"""Exact ordering primitives for NMFA rank correlations and paired deltas.

The module is deliberately standalone.  It uses only integer and rational
arithmetic and does not depend on the packaged NMFA plans, receipt types, or
error vocabulary.  A later orchestration layer can therefore adapt the one
closed local error without creating a dependency from this arithmetic core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Never, final

__all__ = (
    "ExactLengthMaximum",
    "ExactPairedDelta",
    "ExactRho",
    "ExactRhoKind",
    "LengthSource",
    "NMFAExactOrderError",
    "compare_exact_paired_delta",
    "compare_exact_rho",
    "exact_paired_delta_sign",
    "make_exact_paired_delta",
    "select_exact_length_maximum",
)

_MAX_RHO_COMPONENT_BITS = 2_048
_MAX_DERIVED_OPERAND_BITS = 262_144
_ERROR_CODE = "NMFA_EXACT_ORDER_INVALID"


@final
class NMFAExactOrderError(ValueError):
    """Closed, detail-free failure raised by this local arithmetic core."""

    code = _ERROR_CODE

    def __init__(self) -> None:
        super().__init__(self.code)


def _fail() -> Never:
    raise NMFAExactOrderError


def _sign(value: int | Fraction) -> int:
    return (value > 0) - (value < 0)


def _require_derived_bounds(*values: int | Fraction) -> None:
    """Fail closed if a derived exact sign-kernel operand exceeds its cap."""

    for value in values:
        if type(value) is int:
            if abs(value).bit_length() > _MAX_DERIVED_OPERAND_BITS:
                _fail()
        elif type(value) is Fraction:
            if (
                abs(value.numerator).bit_length() > _MAX_DERIVED_OPERAND_BITS
                or value.denominator.bit_length() > _MAX_DERIVED_OPERAND_BITS
            ):
                _fail()
        else:
            _fail()


class ExactRhoKind(StrEnum):
    """Whether a rho is a measured state or a protocol substitution."""

    DEFINED = "defined"
    SENTINEL = "sentinel"


@final
@dataclass(frozen=True, slots=True, repr=False)
class ExactRho:
    """One exact value ``covariance_c / sqrt(denominator_radicand)``.

    Sentinel values are restricted to the protocol's exact rational values
    -1, 0, and +1.  Defined values retain their original radicand so receipt
    verification can preserve the measurement state; numeric comparison does
    not require a canonical square-free representation.
    """

    covariance_c: int
    denominator_radicand: int
    kind: ExactRhoKind = ExactRhoKind.DEFINED

    def __repr__(self) -> str:
        return "<ExactRho protected>"

    def __post_init__(self) -> None:
        if (
            type(self.covariance_c) is not int
            or type(self.denominator_radicand) is not int
            or type(self.kind) is not ExactRhoKind
            or self.denominator_radicand <= 0
            or abs(self.covariance_c).bit_length() > _MAX_RHO_COMPONENT_BITS
            or self.denominator_radicand.bit_length() > _MAX_RHO_COMPONENT_BITS
            or self.covariance_c * self.covariance_c > self.denominator_radicand
        ):
            _fail()
        if self.kind is ExactRhoKind.SENTINEL and (
            self.denominator_radicand != 1 or self.covariance_c not in {-1, 0, 1}
        ):
            _fail()

    @classmethod
    def defined(cls, covariance_c: int, denominator_radicand: int) -> ExactRho:
        """Construct a defined exact rank-correlation state."""

        return cls(covariance_c, denominator_radicand, ExactRhoKind.DEFINED)

    @classmethod
    def sentinel(cls, value: int) -> ExactRho:
        """Construct the exact protocol substitution -1, 0, or +1."""

        if type(value) is not int or value not in {-1, 0, 1}:
            _fail()
        return cls(value, 1, ExactRhoKind.SENTINEL)


class LengthSource(StrEnum):
    """Closed provenance for the selected nonnegative length reference."""

    ZERO = "zero"
    TOTAL = "l_total"
    DISTINCT = "l_distinct"


@final
@dataclass(frozen=True, slots=True, repr=False, init=False)
class ExactLengthMaximum:
    """The exact ``max(0, rho_total, rho_distinct)`` and its tie winner."""

    source: LengthSource
    rho: ExactRho

    def __repr__(self) -> str:
        return "<ExactLengthMaximum protected>"


@final
@dataclass(frozen=True, slots=True, repr=False)
class ExactPairedDelta:
    """One exact paired value ``primary.rho - length_max.rho``."""

    primary: ExactRho
    length_maximum: ExactLengthMaximum

    def __repr__(self) -> str:
        return "<ExactPairedDelta protected>"

    def __post_init__(self) -> None:
        if (
            type(self.primary) is not ExactRho
            or type(self.length_maximum) is not ExactLengthMaximum
        ):
            _fail()


def compare_exact_rho(left: ExactRho, right: ExactRho) -> int:
    """Return -1, 0, or +1 from an exact numeric rho comparison."""

    if type(left) is not ExactRho or type(right) is not ExactRho:
        _fail()
    left_sign = _sign(left.covariance_c)
    right_sign = _sign(right.covariance_c)
    if left_sign != right_sign:
        return _sign(left_sign - right_sign)
    if left_sign == 0:
        return 0
    squared_cross = (
        left.covariance_c * left.covariance_c * right.denominator_radicand
        - right.covariance_c * right.covariance_c * left.denominator_radicand
    )
    magnitude_order = _sign(squared_cross)
    return magnitude_order if left_sign > 0 else -magnitude_order


def _make_length_maximum(source: LengthSource, rho: ExactRho) -> ExactLengthMaximum:
    if (
        type(source) is not LengthSource
        or type(rho) is not ExactRho
        or compare_exact_rho(rho, ExactRho.sentinel(0)) < 0
        or (source is LengthSource.ZERO and compare_exact_rho(rho, ExactRho.sentinel(0)) != 0)
    ):
        _fail()
    result = object.__new__(ExactLengthMaximum)
    object.__setattr__(result, "source", source)
    object.__setattr__(result, "rho", rho)
    return result


def select_exact_length_maximum(
    total: ExactRho,
    distinct: ExactRho,
) -> ExactLengthMaximum:
    """Select ``max(0, total, distinct)`` with zero/total/distinct tie order."""

    if type(total) is not ExactRho or type(distinct) is not ExactRho:
        _fail()
    selected = _make_length_maximum(LengthSource.ZERO, ExactRho.sentinel(0))
    for source, candidate in (
        (LengthSource.TOTAL, total),
        (LengthSource.DISTINCT, distinct),
    ):
        if compare_exact_rho(candidate, selected.rho) > 0:
            selected = _make_length_maximum(source, candidate)
    return selected


def make_exact_paired_delta(
    primary: ExactRho,
    total: ExactRho,
    distinct: ExactRho,
) -> ExactPairedDelta:
    """Construct one paired delta after the frozen length-reference choice."""

    if type(primary) is not ExactRho:
        _fail()
    return ExactPairedDelta(primary, select_exact_length_maximum(total, distinct))


def exact_paired_delta_sign(value: ExactPairedDelta) -> int:
    """Return the exact sign of ``primary - length_maximum``."""

    if type(value) is not ExactPairedDelta:
        _fail()
    return compare_exact_rho(value.primary, value.length_maximum.rho)


def _sign_one_radical(rational: Fraction, coefficient: Fraction, radicand: int) -> int:
    """Return the exact sign of ``rational + coefficient * sqrt(radicand)``."""

    if type(rational) is not Fraction or type(coefficient) is not Fraction:
        _fail()
    if type(radicand) is not int or radicand <= 0:
        _fail()
    _require_derived_bounds(rational, coefficient, radicand)
    if coefficient == 0:
        return _sign(rational)
    square_root = math.isqrt(radicand)
    if square_root * square_root == radicand:
        return _sign(rational + coefficient * square_root)
    rational_sign = _sign(rational)
    coefficient_sign = _sign(coefficient)
    if rational_sign == 0:
        return coefficient_sign
    if rational_sign == coefficient_sign:
        return rational_sign
    magnitude_order = _sign(rational * rational - coefficient * coefficient * radicand)
    if magnitude_order == 0:
        return 0
    return rational_sign if magnitude_order > 0 else coefficient_sign


def _sign_two_radicals(
    rational: Fraction,
    first_coefficient: Fraction,
    first_radicand: int,
    second_coefficient: Fraction,
    second_radicand: int,
) -> int:
    """Return the exact sign of ``R + P*sqrt(A) + Q*sqrt(B)``.

    Treat ``R + P*sqrt(A)`` as one exact operand.  If it opposes the
    remaining radical, compare their squared magnitudes; that reduction has
    only one radical and is handled by :func:`_sign_one_radical`.
    """

    if type(second_coefficient) is not Fraction:
        _fail()
    if type(second_radicand) is not int or second_radicand <= 0:
        _fail()
    _require_derived_bounds(
        rational,
        first_coefficient,
        first_radicand,
        second_coefficient,
        second_radicand,
    )
    if second_coefficient == 0:
        return _sign_one_radical(rational, first_coefficient, first_radicand)
    first_sign = _sign_one_radical(rational, first_coefficient, first_radicand)
    second_sign = _sign(second_coefficient)
    if first_sign == 0:
        return second_sign
    if first_sign == second_sign:
        return first_sign
    squared_magnitude_order = _sign_one_radical(
        rational * rational
        + first_coefficient * first_coefficient * first_radicand
        - second_coefficient * second_coefficient * second_radicand,
        2 * rational * first_coefficient,
        first_radicand,
    )
    if squared_magnitude_order == 0:
        return 0
    return first_sign if squared_magnitude_order > 0 else second_sign


def _compare_squared_delta_magnitudes(
    left: ExactPairedDelta,
    right: ExactPairedDelta,
) -> int:
    """Compare ``left**2`` and ``right**2`` through at most two radicals."""

    left_primary = left.primary
    left_length = left.length_maximum.rho
    right_primary = right.primary
    right_length = right.length_maximum.rho

    rational = (
        Fraction(
            left_primary.covariance_c * left_primary.covariance_c,
            left_primary.denominator_radicand,
        )
        + Fraction(
            left_length.covariance_c * left_length.covariance_c,
            left_length.denominator_radicand,
        )
        - Fraction(
            right_primary.covariance_c * right_primary.covariance_c,
            right_primary.denominator_radicand,
        )
        - Fraction(
            right_length.covariance_c * right_length.covariance_c,
            right_length.denominator_radicand,
        )
    )
    left_cross_radicand = left_primary.denominator_radicand * left_length.denominator_radicand
    right_cross_radicand = right_primary.denominator_radicand * right_length.denominator_radicand
    left_cross_coefficient = Fraction(
        -2 * left_primary.covariance_c * left_length.covariance_c,
        left_cross_radicand,
    )
    right_cross_coefficient = Fraction(
        2 * right_primary.covariance_c * right_length.covariance_c,
        right_cross_radicand,
    )
    return _sign_two_radicals(
        rational,
        left_cross_coefficient,
        left_cross_radicand,
        right_cross_coefficient,
        right_cross_radicand,
    )


def compare_exact_paired_delta(left: ExactPairedDelta, right: ExactPairedDelta) -> int:
    """Return -1, 0, or +1 from an exact numeric paired-delta comparison."""

    if type(left) is not ExactPairedDelta or type(right) is not ExactPairedDelta:
        _fail()
    left_sign = exact_paired_delta_sign(left)
    right_sign = exact_paired_delta_sign(right)
    if left_sign != right_sign:
        return _sign(left_sign - right_sign)
    if left_sign == 0:
        return 0
    magnitude_order = _compare_squared_delta_magnitudes(left, right)
    return magnitude_order if left_sign > 0 else -magnitude_order
