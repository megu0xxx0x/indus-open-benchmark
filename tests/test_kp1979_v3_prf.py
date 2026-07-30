from __future__ import annotations

import unittest
from collections.abc import Iterator

from indusbench.kp1979_v3_prf import (
    DeterministicStream,
    KP1979V3PRFError,
    derive_official_seed,
    derive_subseed,
)

SEED = bytes(range(32))


class _SpoofedText(str):
    def __len__(self) -> int:
        return 40

    def __iter__(self) -> Iterator[str]:
        return iter("0" * 40)

    def encode(self, encoding: str = "utf-8", errors: str = "strict") -> bytes:
        del encoding, errors
        return b"substituted"


class KP1979V3PRFTests(unittest.TestCase):
    def test_stream_is_deterministic_domain_separated_and_chunk_stable(self) -> None:
        whole = DeterministicStream(SEED, "case/a").read(80)
        chunked_stream = DeterministicStream(SEED, "case/a")
        chunked = (
            chunked_stream.read(1)
            + chunked_stream.read(31)
            + chunked_stream.read(33)
            + chunked_stream.read(15)
        )
        different = DeterministicStream(SEED, "case/b").read(80)

        self.assertEqual(whole, chunked)
        self.assertNotEqual(whole, different)
        self.assertEqual(3, chunked_stream.block_counter)
        self.assertEqual(32, len(derive_subseed(SEED, "renderer/a")))
        self.assertNotEqual(
            derive_subseed(SEED, "renderer/a"),
            derive_subseed(SEED, "renderer/b"),
        )

    def test_version_stability_exact_vectors(self) -> None:
        official_seed = derive_official_seed(
            chain_hash=b"c" * 32,
            round_number=42,
            signature=b"s" * 48,
            plan_sha256=b"p" * 32,
            control_bundle_sha256=b"b" * 32,
            detector_artifact_sha256=b"d" * 32,
            control_commit="1" * 40,
            detector_commit="2" * 40,
            integration_commit="3" * 40,
        )
        self.assertEqual(
            bytes.fromhex("06e9cae57722635af0cf2ba11afcb000a58743a804efc2bf135e7e5b18df99d7"),
            official_seed,
        )
        self.assertEqual(
            bytes.fromhex("0ee70e52d9407949074651b24af1f26b3f6be3cfb0536933f52013a207e8d09d"),
            derive_subseed(SEED, "renderer/a"),
        )
        self.assertEqual(
            bytes.fromhex(
                "3e868a2e79aa98729830e43dc7a00f85547a55fd6640c489"
                "012a332ca901c31798584cde2deff104952539e636a131188"
                "b985bb6587a9fec44cb8b204f892e0f1811a7fdfbd35df0a"
                "f7fe861352209e8"
            ),
            DeterministicStream(SEED, "case/a").read(80),
        )

    def test_integer_choice_shuffle_and_sample_are_bounded_and_reproducible(self) -> None:
        first = DeterministicStream(SEED, "integer-contract")
        second = DeterministicStream(SEED, "integer-contract")
        first_values = tuple(first.randint(-5, 9) for _ in range(128))
        second_values = tuple(second.randint(-5, 9) for _ in range(128))

        self.assertEqual(first_values, second_values)
        self.assertTrue(all(-5 <= value <= 9 for value in first_values))

        values = tuple(range(16))
        shuffled = DeterministicStream(SEED, "shuffle").shuffled(values)
        self.assertEqual(set(values), set(shuffled))
        self.assertEqual(
            shuffled,
            DeterministicStream(SEED, "shuffle").shuffled(values),
        )
        sampled = DeterministicStream(SEED, "sample").sample(values, 7)
        self.assertEqual(7, len(sampled))
        self.assertEqual(7, len(set(sampled)))
        self.assertIn(
            DeterministicStream(SEED, "choice").choice(values),
            values,
        )

    def test_official_seed_binds_every_public_commitment(self) -> None:
        arguments = {
            "chain_hash": b"c" * 32,
            "round_number": 42,
            "signature": b"s" * 48,
            "plan_sha256": b"p" * 32,
            "control_bundle_sha256": b"b" * 32,
            "detector_artifact_sha256": b"d" * 32,
            "control_commit": "1" * 40,
            "detector_commit": "2" * 40,
            "integration_commit": "3" * 40,
        }
        seed = derive_official_seed(**arguments)
        self.assertEqual(32, len(seed))
        self.assertEqual(seed, derive_official_seed(**arguments))

        for field, replacement in (
            ("chain_hash", b"C" * 32),
            ("round_number", 43),
            ("signature", b"S" * 48),
            ("plan_sha256", b"P" * 32),
            ("control_bundle_sha256", b"B" * 32),
            ("detector_artifact_sha256", b"D" * 32),
            ("control_commit", "4" * 40),
            ("detector_commit", "5" * 40),
            ("integration_commit", "6" * 40),
        ):
            with self.subTest(field=field):
                changed = dict(arguments)
                changed[field] = replacement
                self.assertNotEqual(seed, derive_official_seed(**changed))

    def test_text_subclasses_cannot_spoof_commit_or_label_bytes(self) -> None:
        spoofed = _SpoofedText("00")
        with self.assertRaises(KP1979V3PRFError):
            DeterministicStream(SEED, spoofed)
        with self.assertRaises(KP1979V3PRFError):
            derive_subseed(SEED, spoofed)

        arguments = {
            "chain_hash": b"c" * 32,
            "round_number": 42,
            "signature": b"s" * 48,
            "plan_sha256": b"p" * 32,
            "control_bundle_sha256": b"b" * 32,
            "detector_artifact_sha256": b"d" * 32,
            "control_commit": "1" * 40,
            "detector_commit": "2" * 40,
            "integration_commit": "3" * 40,
        }
        for field in ("control_commit", "detector_commit", "integration_commit"):
            with self.subTest(field=field), self.assertRaises(KP1979V3PRFError):
                changed = dict(arguments)
                changed[field] = spoofed
                derive_official_seed(**changed)

        arguments["round_number"] = True
        with self.assertRaises(KP1979V3PRFError):
            derive_official_seed(**arguments)

    def test_invalid_types_lengths_ranges_and_labels_fail_closed(self) -> None:
        invalid_streams = (
            lambda: DeterministicStream(b"x" * 31, "label"),
            lambda: DeterministicStream(SEED, ""),
            lambda: DeterministicStream(SEED, "é"),
            lambda: DeterministicStream(SEED, "x" * 256),
        )
        for operation in invalid_streams:
            with self.subTest(operation=operation), self.assertRaises(KP1979V3PRFError):
                operation()

        stream = DeterministicStream(SEED, "invalid-operations")
        invalid_operations = (
            lambda: stream.read(True),
            lambda: stream.read(-1),
            lambda: stream.randbelow(True),
            lambda: stream.randbelow(0),
            lambda: stream.randint(2, 1),
            lambda: stream.choice(()),
            lambda: stream.choice("text"),
            lambda: stream.sample((1, 2), True),
            lambda: stream.sample((1, 2), 3),
        )
        for operation in invalid_operations:
            with self.subTest(operation=operation), self.assertRaises(KP1979V3PRFError):
                operation()

        with self.assertRaises(KP1979V3PRFError):
            derive_official_seed(
                chain_hash=b"x" * 31,
                round_number=1,
                signature=b"s" * 48,
                plan_sha256=b"p" * 32,
                control_bundle_sha256=b"b" * 32,
                detector_artifact_sha256=b"d" * 32,
                control_commit="1" * 40,
                detector_commit="2" * 40,
                integration_commit="3" * 40,
            )


if __name__ == "__main__":
    unittest.main()
