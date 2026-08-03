from __future__ import annotations

import random
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
from fractions import Fraction
from math import isqrt
from typing import Any, cast

from indusbench import nmfa_exact_order as exact_order
from indusbench.nmfa_exact_order import (
    ExactLengthMaximum,
    ExactPairedDelta,
    ExactRho,
    ExactRhoKind,
    LengthSource,
    NMFAExactOrderError,
    compare_exact_paired_delta,
    compare_exact_rho,
    exact_paired_delta_sign,
    make_exact_paired_delta,
    select_exact_length_maximum,
)


def sign(value: int | Fraction | Decimal) -> int:
    return (value > 0) - (value < 0)


def rational_rho(numerator: int, square_root: int) -> ExactRho:
    return ExactRho.defined(numerator, square_root * square_root)


def direct_delta(primary: ExactRho, length: ExactRho) -> ExactPairedDelta:
    return make_exact_paired_delta(primary, length, ExactRho.sentinel(0))


class ExactRhoTests(unittest.TestCase):
    def test_scaled_radicands_compare_equal(self) -> None:
        self.assertEqual(0, compare_exact_rho(ExactRho.defined(1, 2), ExactRho.defined(2, 8)))
        self.assertEqual(
            0,
            compare_exact_rho(ExactRho.defined(-1, 2), ExactRho.defined(-2, 8)),
        )

    def test_positive_negative_zero_and_sentinel_order(self) -> None:
        values = (
            ExactRho.sentinel(-1),
            ExactRho.defined(-1, 2),
            ExactRho.sentinel(0),
            ExactRho.defined(1, 2),
            ExactRho.sentinel(1),
        )
        for left_index, left in enumerate(values):
            for right_index, right in enumerate(values):
                self.assertEqual(sign(left_index - right_index), compare_exact_rho(left, right))
        self.assertEqual(0, compare_exact_rho(ExactRho.sentinel(1), ExactRho.defined(2, 4)))
        self.assertEqual(0, compare_exact_rho(ExactRho.sentinel(-1), ExactRho.defined(-3, 9)))

    def test_length_maximum_uses_zero_total_distinct_tie_precedence(self) -> None:
        zero = ExactRho.defined(0, 17)
        selected = select_exact_length_maximum(zero, ExactRho.sentinel(0))
        self.assertIs(LengthSource.ZERO, selected.source)
        self.assertIs(ExactRhoKind.SENTINEL, selected.rho.kind)

        total = ExactRho.defined(1, 2)
        equal_distinct = ExactRho.defined(2, 8)
        selected = select_exact_length_maximum(total, equal_distinct)
        self.assertIs(LengthSource.TOTAL, selected.source)
        self.assertIs(total, selected.rho)

        larger_distinct = ExactRho.defined(3, 16)
        selected = select_exact_length_maximum(total, larger_distinct)
        self.assertIs(LengthSource.DISTINCT, selected.source)
        self.assertIs(larger_distinct, selected.rho)

        selected = select_exact_length_maximum(ExactRho.defined(-1, 2), ExactRho.defined(-1, 3))
        self.assertIs(LengthSource.ZERO, selected.source)

    def test_representations_are_immutable(self) -> None:
        rho = ExactRho.defined(1, 2)
        maximum = select_exact_length_maximum(rho, ExactRho.sentinel(0))
        delta = ExactPairedDelta(rho, maximum)
        with self.assertRaises(FrozenInstanceError):
            rho.covariance_c = 2  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            maximum.source = LengthSource.ZERO  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            delta.primary = ExactRho.sentinel(0)  # type: ignore[misc]

    def test_closed_validation_and_operand_limit(self) -> None:
        invalid = (
            lambda: ExactRho.defined(True, 1),
            lambda: ExactRho.defined(1, False),
            lambda: ExactRho.defined(1, 0),
            lambda: ExactRho.defined(2, 1),
            lambda: ExactRho.defined(1, 1 << 2_048),
            lambda: ExactRho(1, 2, "defined"),  # type: ignore[arg-type]
            lambda: ExactRho(1, 2, ExactRhoKind.SENTINEL),
            lambda: ExactRho.sentinel(2),
        )
        for invocation in invalid:
            with (
                self.subTest(invocation=invocation),
                self.assertRaisesRegex(NMFAExactOrderError, "^NMFA_EXACT_ORDER_INVALID$"),
            ):
                invocation()
        with self.assertRaises(TypeError):
            cast(Any, ExactLengthMaximum)(
                LengthSource.TOTAL,
                ExactRho.defined(1, 2),
            )

    def test_repr_redacts_exact_values_and_factory_owns_length_provenance(self) -> None:
        rho = ExactRho.defined(17, 1_024)
        maximum = select_exact_length_maximum(rho, ExactRho.sentinel(0))
        delta = ExactPairedDelta(rho, maximum)
        self.assertEqual("<ExactRho protected>", repr(rho))
        self.assertEqual("<ExactLengthMaximum protected>", repr(maximum))
        self.assertEqual("<ExactPairedDelta protected>", repr(delta))
        self.assertNotIn("17", repr((rho, maximum, delta)))

    def test_randomized_rational_reference(self) -> None:
        generator = random.Random(0x4E4D4641)
        for _ in range(2_000):
            left_root = generator.randint(1, 100)
            right_root = generator.randint(1, 100)
            left_numerator = generator.randint(-left_root, left_root)
            right_numerator = generator.randint(-right_root, right_root)
            left = rational_rho(left_numerator, left_root)
            right = rational_rho(right_numerator, right_root)
            expected = sign(
                Fraction(left_numerator, left_root) - Fraction(right_numerator, right_root)
            )
            self.assertEqual(expected, compare_exact_rho(left, right))


class ExactPairedDeltaTests(unittest.TestCase):
    def test_exact_two_radical_order(self) -> None:
        # 1/sqrt(2) - 1/sqrt(3) < 1/sqrt(3) - 1/sqrt(5).
        left = direct_delta(ExactRho.defined(1, 2), ExactRho.defined(1, 3))
        right = direct_delta(ExactRho.defined(1, 3), ExactRho.defined(1, 5))
        self.assertEqual(-1, compare_exact_paired_delta(left, right))
        self.assertEqual(1, compare_exact_paired_delta(right, left))

    def test_component_and_derived_operand_caps_are_distinct(self) -> None:
        first_radicand = (1 << 2_047) + 1
        second_radicand = (1 << 2_047) + 3
        self.assertEqual(2_048, first_radicand.bit_length())
        self.assertGreater((first_radicand * second_radicand).bit_length(), 2_048)
        value = direct_delta(
            ExactRho.defined(1, first_radicand),
            ExactRho.defined(1, second_radicand),
        )
        self.assertEqual(0, compare_exact_paired_delta(value, value))
        with self.assertRaises(NMFAExactOrderError):
            exact_order._require_derived_bounds(1 << 262_144)

    def test_scaled_radicand_delta_equality_and_zero(self) -> None:
        left = direct_delta(ExactRho.defined(1, 2), ExactRho.sentinel(0))
        right = direct_delta(ExactRho.defined(2, 8), ExactRho.defined(0, 13))
        self.assertEqual(0, compare_exact_paired_delta(left, right))

        zero = direct_delta(ExactRho.defined(1, 2), ExactRho.defined(2, 8))
        self.assertEqual(0, exact_paired_delta_sign(zero))
        self.assertEqual(0, compare_exact_paired_delta(zero, zero))

    def test_negative_order_reverses_squared_magnitude(self) -> None:
        outer_negative = direct_delta(ExactRho.defined(-1, 2), ExactRho.defined(1, 3))
        inner_negative = direct_delta(ExactRho.defined(1, 3), ExactRho.defined(1, 2))
        self.assertEqual(-1, exact_paired_delta_sign(outer_negative))
        self.assertEqual(-1, exact_paired_delta_sign(inner_negative))
        self.assertEqual(-1, compare_exact_paired_delta(outer_negative, inner_negative))

    def test_sentinel_values_are_exact(self) -> None:
        minus_one = direct_delta(ExactRho.sentinel(-1), ExactRho.sentinel(0))
        zero = direct_delta(ExactRho.sentinel(0), ExactRho.sentinel(0))
        plus_one = direct_delta(ExactRho.sentinel(1), ExactRho.sentinel(0))
        self.assertEqual(-1, compare_exact_paired_delta(minus_one, zero))
        self.assertEqual(-1, compare_exact_paired_delta(zero, plus_one))
        self.assertEqual(0, compare_exact_paired_delta(minus_one, minus_one))

    def test_factory_preserves_selected_length_source(self) -> None:
        value = make_exact_paired_delta(
            ExactRho.defined(3, 16),
            ExactRho.defined(1, 2),
            ExactRho.defined(2, 8),
        )
        self.assertIs(LengthSource.TOTAL, value.length_maximum.source)
        self.assertEqual(1, exact_paired_delta_sign(value))

    def test_randomized_fraction_delta_reference(self) -> None:
        generator = random.Random(0x44454C5441)
        cases: list[tuple[ExactPairedDelta, Fraction]] = []
        for _ in range(1_000):
            primary_root = generator.randint(1, 50)
            total_root = generator.randint(1, 50)
            distinct_root = generator.randint(1, 50)
            primary_numerator = generator.randint(-primary_root, primary_root)
            total_numerator = generator.randint(-total_root, total_root)
            distinct_numerator = generator.randint(-distinct_root, distinct_root)
            primary = rational_rho(primary_numerator, primary_root)
            total = rational_rho(total_numerator, total_root)
            distinct = rational_rho(distinct_numerator, distinct_root)
            exact = make_exact_paired_delta(primary, total, distinct)
            reference = Fraction(primary_numerator, primary_root) - max(
                Fraction(0),
                Fraction(total_numerator, total_root),
                Fraction(distinct_numerator, distinct_root),
            )
            self.assertEqual(sign(reference), exact_paired_delta_sign(exact))
            cases.append((exact, reference))

        for _ in range(4_000):
            left, left_reference = generator.choice(cases)
            right, right_reference = generator.choice(cases)
            self.assertEqual(
                sign(left_reference - right_reference),
                compare_exact_paired_delta(left, right),
            )

    def test_randomized_irrational_delta_high_precision_oracle(self) -> None:
        """Cross-check non-square radicands; exact ties have separate vectors."""

        generator = random.Random(0x4952524154494F4E414C)

        def sampled_rho() -> ExactRho:
            radicand = generator.randint(1, 400)
            covariance = generator.randint(-isqrt(radicand), isqrt(radicand))
            return ExactRho.defined(covariance, radicand)

        with localcontext() as context:
            context.prec = 120

            def decimal_rho(value: ExactRho) -> Decimal:
                return Decimal(value.covariance_c) / Decimal(value.denominator_radicand).sqrt()

            cases: list[tuple[ExactPairedDelta, Decimal]] = []
            for _ in range(400):
                primary = sampled_rho()
                total = sampled_rho()
                distinct = sampled_rho()
                cases.append(
                    (
                        make_exact_paired_delta(primary, total, distinct),
                        decimal_rho(primary)
                        - max(Decimal(0), decimal_rho(total), decimal_rho(distinct)),
                    )
                )

            checked = 0
            for _ in range(4_000):
                left, left_reference = generator.choice(cases)
                right, right_reference = generator.choice(cases)
                difference = left_reference - right_reference
                # Decimal is an independent test oracle, not evaluator logic.
                # Near-zero cases are covered by the exact equality vectors.
                if abs(difference) < Decimal("1e-100"):
                    continue
                self.assertEqual(
                    sign(difference),
                    compare_exact_paired_delta(left, right),
                )
                checked += 1
            self.assertGreater(checked, 3_900)


if __name__ == "__main__":
    unittest.main()
