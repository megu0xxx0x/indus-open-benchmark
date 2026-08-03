from __future__ import annotations

import ast
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast

from indusbench import nmfa_counter_stream as counter_stream

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src/indusbench/nmfa_counter_stream.py"
ZERO_KEY = bytes(32)
SEQUENTIAL_KEY = bytes(range(32))


def fixed_blocks(*values: int | bytes | Exception) -> Callable[[bytes, str, int, int], bytes]:
    iterator = iter(values)

    def source(_key: bytes, _label: str, _run: int, _counter: int) -> bytes:
        value = next(iterator)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, bytes):
            return value
        return value.to_bytes(32, "big")

    return source


class NMFACounterStreamTest(unittest.TestCase):
    def test_frozen_hmac_vectors_and_exact_message_framing(self) -> None:
        vectors = (
            (
                ZERO_KEY,
                "control-n1-v1",
                0,
                0,
                "bdf831d83dd0388424ddf3caebff8f92826c5c3e725a2fe1a46e587863669335",
            ),
            (
                ZERO_KEY,
                "bootstrap-v1",
                0,
                0,
                "796035efff9fa84895ee049e6aaaca77666e2972cce850da3fdd951f8b22bdc9",
            ),
            (
                ZERO_KEY,
                "null-n2-v1",
                0,
                0,
                "a616fc573b1c3a9b436db069b82b90b5cbfad6a75b1f18a9c3cb228e1216c9ff",
            ),
            (
                SEQUENTIAL_KEY,
                "prospective-bootstrap-v1",
                9_999,
                17,
                "72d71f997aef2b012ac498bd2b855b0e87f5ca54d022eeab6ed8cc3470171b46",
            ),
            (
                SEQUENTIAL_KEY,
                "prospective-null-n2-v1",
                99_998,
                31,
                "44a63ee113762c2e15c86203d599e6d56be7ea9ca994a0486541b470e4680552",
            ),
        )
        for key, label, run_index, block_counter, expected in vectors:
            with self.subTest(label=label):
                self.assertEqual(
                    expected,
                    counter_stream.nmfa_hmac_counter_block(
                        key,
                        label,
                        run_index,
                        block_counter,
                    ).hex(),
                )

    def test_labels_are_closed_and_arguments_reject_bool_or_alternate_types(self) -> None:
        self.assertEqual(
            (
                "bootstrap-v1",
                "control-n1-v1",
                "null-n2-v1",
                "prospective-bootstrap-v1",
                "prospective-null-n2-v1",
            ),
            counter_stream.NMFA_COUNTER_STREAM_LABELS,
        )
        invalid_calls = (
            lambda: counter_stream.NMFACounterStream(b"x" * 31, "bootstrap-v1", 0),
            lambda: counter_stream.NMFACounterStream(cast(bytes, bytearray(32)), "bootstrap-v1", 0),
            lambda: counter_stream.NMFACounterStream(ZERO_KEY, "bootstrap-v1\x00", 0),
            lambda: counter_stream.NMFACounterStream(ZERO_KEY, "Bootstrap-v1", 0),
            lambda: counter_stream.NMFACounterStream(ZERO_KEY, "bootstrap-v1", True),
            lambda: counter_stream.NMFACounterStream(ZERO_KEY, "bootstrap-v1", -1),
            lambda: counter_stream.NMFACounterStream(ZERO_KEY, "bootstrap-v1", 1 << 64),
            lambda: counter_stream.nmfa_hmac_counter_block(ZERO_KEY, "bootstrap-v1", 0, True),
            lambda: counter_stream.nmfa_hmac_counter_block(ZERO_KEY, "bootstrap-v1", 0, 1 << 64),
        )
        for call in invalid_calls:
            with self.assertRaisesRegex(
                counter_stream.NMFACounterStreamError,
                "^INVALID_ARGUMENT$",
            ):
                call()

    def test_bound_one_consumes_zero_blocks_but_counts_the_draw(self) -> None:
        stream = counter_stream.NMFACounterStream(ZERO_KEY, "bootstrap-v1", 7)
        self.assertEqual(0, stream.draw_index(1))
        self.assertEqual(0, stream.draw_index(1))
        self.assertEqual(
            counter_stream.NMFACounterStreamStats(
                draws=2,
                blocks_generated=0,
                rejected_blocks=0,
                next_counter=0,
            ),
            stream.stats(),
        )

    def test_full_block_rejection_is_unbiased_and_advances_counter(self) -> None:
        seen_counters: list[int] = []

        def source(_key: bytes, _label: str, _run: int, block_counter: int) -> bytes:
            seen_counters.append(block_counter)
            return ((1 << 256) - 1 if block_counter == 0 else 5).to_bytes(32, "big")

        stream = counter_stream.NMFACounterStream._with_block_source_for_test(
            ZERO_KEY,
            "bootstrap-v1",
            0,
            source,
        )
        self.assertEqual(2, stream.draw_index(3))
        self.assertEqual([0, 1], seen_counters)
        self.assertEqual(
            counter_stream.NMFACounterStreamStats(
                draws=1,
                blocks_generated=2,
                rejected_blocks=1,
                next_counter=2,
            ),
            stream.stats(),
        )

    def test_acceptance_boundary_and_maximum_bound(self) -> None:
        bound = 10
        threshold = (1 << 256) - ((1 << 256) % bound)
        stream = counter_stream.NMFACounterStream._with_block_source_for_test(
            ZERO_KEY,
            "null-n2-v1",
            0,
            fixed_blocks(threshold - 1, threshold, 0),
        )
        self.assertEqual((1 << 256) - 7, threshold - 1)
        self.assertEqual((1 << 256) - 6, threshold)
        self.assertEqual(9, stream.draw_index(bound))
        self.assertEqual(0, stream.draw_index(bound))
        self.assertEqual(1, stream.stats().rejected_blocks)

        maximum = counter_stream.NMFACounterStream._with_block_source_for_test(
            ZERO_KEY,
            "bootstrap-v1",
            0,
            fixed_blocks((1 << 256) - 1),
        )
        self.assertEqual((1 << 128) - 1, maximum.draw_index(1 << 128))

    def test_bounds_are_closed_to_one_through_two_to_128(self) -> None:
        stream = counter_stream.NMFACounterStream(ZERO_KEY, "bootstrap-v1", 0)
        for bound in (0, -1, True, 1.5, 1 << 128 | 1):
            with (
                self.subTest(bound=bound),
                self.assertRaisesRegex(
                    counter_stream.NMFACounterStreamError,
                    "^INVALID_ARGUMENT$",
                ),
            ):
                stream.draw_index(bound)  # type: ignore[arg-type]
        self.assertEqual(0, stream.stats().draws)

    def test_sixteen_rejections_fail_closed_and_poison_stream(self) -> None:
        stream = counter_stream.NMFACounterStream._with_block_source_for_test(
            ZERO_KEY,
            "bootstrap-v1",
            0,
            fixed_blocks(*([(1 << 256) - 1] * 16)),
        )
        with self.assertRaisesRegex(
            counter_stream.NMFACounterStreamError,
            "^COMPUTATION_LIMIT_BLOCKED$",
        ):
            stream.draw_index(3)
        self.assertEqual(
            counter_stream.NMFACounterStreamStats(1, 16, 16, 16),
            stream.stats(),
        )
        with self.assertRaisesRegex(
            counter_stream.NMFACounterStreamError,
            "^STREAM_FAILED$",
        ):
            stream.draw_index(2)

    def test_per_run_block_cap_fails_before_an_extra_source_call(self) -> None:
        source_calls = 0

        def source(_key: bytes, _label: str, _run: int, _counter: int) -> bytes:
            nonlocal source_calls
            source_calls += 1
            return ((1 << 256) - 1).to_bytes(32, "big")

        stream = counter_stream.NMFACounterStream._with_block_source_for_test(
            ZERO_KEY,
            "bootstrap-v1",
            0,
            source,
            max_blocks=1,
        )
        with self.assertRaisesRegex(
            counter_stream.NMFACounterStreamError,
            "^COMPUTATION_LIMIT_BLOCKED$",
        ):
            stream.draw_index(3)
        self.assertEqual(1, source_calls)
        self.assertEqual(
            counter_stream.NMFACounterStreamStats(1, 1, 1, 1),
            stream.stats(),
        )

    def test_counter_overflow_and_bad_injected_blocks_fail_closed(self) -> None:
        overflow = counter_stream.NMFACounterStream._with_block_source_for_test(
            ZERO_KEY,
            "bootstrap-v1",
            0,
            fixed_blocks(0),
        )
        overflow._next_counter = 1 << 64
        with self.assertRaisesRegex(
            counter_stream.NMFACounterStreamError,
            "^COUNTER_EXHAUSTED$",
        ):
            overflow.draw_index(2)

        bad_values: tuple[bytes | Exception, ...] = (
            b"",
            b"x" * 31,
            b"x" * 33,
            ValueError("private detail"),
        )
        for value in bad_values:
            with self.subTest(value=type(value).__name__):
                stream = counter_stream.NMFACounterStream._with_block_source_for_test(
                    ZERO_KEY,
                    "bootstrap-v1",
                    0,
                    fixed_blocks(value),
                )
                with self.assertRaisesRegex(
                    counter_stream.NMFACounterStreamError,
                    "^COUNTER_BLOCK_INVALID$",
                ):
                    stream.draw_index(2)
                self.assertNotIn("private detail", repr(stream))

    def test_stats_and_repr_do_not_disclose_key_material(self) -> None:
        stream = counter_stream.NMFACounterStream(SEQUENTIAL_KEY, "bootstrap-v1", 0)
        stream.draw_index(2)
        rendered = repr(stream)
        self.assertEqual("<NMFACounterStream protected>", rendered)
        self.assertNotIn(SEQUENTIAL_KEY.hex(), rendered)
        self.assertEqual(1, stream.stats().draws)

    def test_module_has_no_external_effect_or_entropy_import(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported_roots.isdisjoint(
                {
                    "asyncio",
                    "datetime",
                    "http",
                    "os",
                    "pathlib",
                    "random",
                    "requests",
                    "secrets",
                    "socket",
                    "subprocess",
                    "tempfile",
                    "time",
                    "urllib",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
