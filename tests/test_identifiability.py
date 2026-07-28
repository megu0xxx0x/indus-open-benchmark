from __future__ import annotations

import random
import unittest
from dataclasses import asdict, replace

from indusbench.identifiability import (
    FUNCTIONAL_CLASSES,
    DegradationConfig,
    TruthFamily,
    TruthToken,
    _Example,
    _permuted_family_labels,
    degrade_fixture,
    evaluate_identifiability,
    generate_synthetic_known_script,
    run_identifiability_gate,
)


class SyntheticKnownScriptTests(unittest.TestCase):
    def test_generator_is_deterministic_legal_and_seed_sensitive(self) -> None:
        first = generate_synthetic_known_script(seed=17, family_count=12)
        second = generate_synthetic_known_script(seed=17, family_count=12)
        different = generate_synthetic_known_script(seed=18, family_count=12)

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertEqual(first.license_id, "CC0-1.0")
        self.assertFalse(first.external_data_used)
        self.assertIn("no external data", first.rights_statement)
        self.assertTrue(all(6 <= len(family.tokens) <= 11 for family in first.families))
        self.assertTrue(
            all(
                set(token.functional_class for token in family.tokens) == set(FUNCTIONAL_CLASSES)
                for family in first.families
            )
        )

    def test_generator_rejects_invalid_seed_and_family_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "seed"):
            generate_synthetic_known_script(seed=True)
        with self.assertRaisesRegex(ValueError, "family_count"):
            generate_synthetic_known_script(family_count=1)


class IndusLikeDegradationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = generate_synthetic_known_script(seed=31, family_count=16)

    def test_cumulative_degradation_preserves_truth_and_hides_truth_fields(self) -> None:
        original = self.fixture
        degraded = degrade_fixture(
            self.fixture,
            DegradationConfig(
                max_sequence_length=4,
                allograph_rate=1.0,
                damage_rate=0.0,
                right_to_left_rate=1.0,
                direction_unknown_rate=1.0,
                duplicate_rate=1.0,
                test_fraction=0.25,
                seed=9,
            ),
        )

        self.assertEqual(self.fixture, original)
        self.assertEqual(len(degraded.observations), 2 * len(self.fixture.families))
        truth_by_family = {family.family_id: family for family in self.fixture.families}
        canonical_signs = {
            token.canonical_sign for family in self.fixture.families for token in family.tokens
        }
        observations_by_family: dict[str, list] = {}
        for artifact in degraded.observations:
            observations_by_family.setdefault(artifact.family_id, []).append(artifact)
            self.assertEqual(len(artifact.tokens), 4)
            self.assertEqual(artifact.reading_direction, "unknown")
            self.assertTrue(all(token.reading_index is None for token in artifact.tokens))
            expected_keys = [
                token.token_key
                for token in reversed(truth_by_family[artifact.family_id].tokens[:4])
            ]
            self.assertEqual([token.token_key for token in artifact.tokens], expected_keys)
            for token in artifact.tokens:
                token_record = asdict(token)
                self.assertNotIn("canonical_sign", token_record)
                self.assertNotIn("functional_class", token_record)
                self.assertNotIn("true_class", token_record)
                self.assertNotIn("word_index", token_record)
                self.assertNotIn(token.sign_id, canonical_signs)
                self.assertTrue(token.sign_id and token.sign_id.endswith(("a", "b")))

        partitions = dict(degraded.family_partitions)
        self.assertEqual(set(partitions.values()), {"train", "test"})
        for family_id, artifacts in observations_by_family.items():
            self.assertEqual(len(artifacts), 2)
            self.assertEqual(
                {artifact.partition for artifact in artifacts},
                {partitions[family_id]},
            )
            self.assertEqual(artifacts[0].tokens, artifacts[1].tokens)

    def test_damage_and_known_rtl_are_explicit_and_deterministic(self) -> None:
        config = DegradationConfig(
            max_sequence_length=5,
            allograph_rate=0.0,
            damage_rate=1.0,
            right_to_left_rate=1.0,
            direction_unknown_rate=0.0,
            duplicate_rate=0.0,
            seed=41,
        )
        first = degrade_fixture(self.fixture, config)
        second = degrade_fixture(self.fixture, config)
        self.assertEqual(first, second)
        for artifact in first.observations:
            self.assertEqual(artifact.reading_direction, "right_to_left")
            self.assertEqual(
                [token.reading_index for token in artifact.tokens],
                list(reversed(range(len(artifact.tokens)))),
            )
            self.assertTrue(
                all(
                    token.sign_id is None and token.condition == "damaged"
                    for token in artifact.tokens
                )
            )

    def test_degradation_seed_changes_observations(self) -> None:
        first = degrade_fixture(self.fixture, DegradationConfig(seed=1))
        second = degrade_fixture(self.fixture, DegradationConfig(seed=2))
        self.assertNotEqual(first, second)

    def test_invalid_degradation_rates_and_lengths_are_rejected(self) -> None:
        for invalid_length in (0, True, 1.5, "2", None):
            with (
                self.subTest(max_sequence_length=invalid_length),
                self.assertRaisesRegex(ValueError, "max_sequence_length"),
            ):
                DegradationConfig(max_sequence_length=invalid_length)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "damage_rate"):
            DegradationConfig(damage_rate=1.1)
        with self.assertRaisesRegex(ValueError, "test_fraction"):
            DegradationConfig(test_fraction=0.0)


class FunctionalIdentifiabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = generate_synthetic_known_script(seed=23, family_count=96)
        self.degraded = degrade_fixture(self.fixture, DegradationConfig(seed=23))

    def test_planted_classes_recover_above_family_permutation_null(self) -> None:
        report = evaluate_identifiability(
            self.fixture,
            self.degraded,
            runs=19,
            seed=700,
        )

        self.assertEqual(report["gate_status"], "go")
        self.assertGreater(report["observed"]["macro_f1"], 0.60)
        self.assertGreaterEqual(report["observed"]["coverage"], 0.80)
        self.assertGreater(report["decision"]["observed_minus_strongest_null"], 0.10)
        self.assertLessEqual(
            report["permutation_null"]["empirical_p_value_greater_or_equal"],
            0.05,
        )
        self.assertEqual(
            report["model"]["test_unit"],
            "one_observation_per_duplicate_family",
        )
        self.assertEqual(
            report["model"]["weighting"],
            "equal_total_weight_per_readable_duplicate_family",
        )
        self.assertEqual(
            report["decision"]["null_reference"],
            "maximum_of_majority_macro_f1_and_permutation_p95",
        )
        self.assertIn("does not identify an Indus language", report["scientific_scope"])

    def test_evaluation_and_null_runs_are_deterministic(self) -> None:
        first = evaluate_identifiability(
            self.fixture,
            self.degraded,
            runs=9,
            seed=101,
            alpha=0.10,
        )
        second = evaluate_identifiability(
            self.fixture,
            self.degraded,
            runs=9,
            seed=101,
            alpha=0.10,
        )
        self.assertEqual(first, second)
        self.assertEqual(
            [run["seed"] for run in first["permutation_null"]["run_values"]],
            list(range(101, 110)),
        )
        null_values = [run["macro_f1"] for run in first["permutation_null"]["run_values"]]
        observed = first["observed"]["macro_f1"]
        expected_p = (1 + sum(value >= observed for value in null_values)) / 10
        self.assertEqual(
            first["permutation_null"]["empirical_p_value_greater_or_equal"],
            expected_p,
        )

    def test_family_permutation_preserves_complete_label_vectors(self) -> None:
        vectors = {
            "F0": ("issuer", "commodity", "quantity"),
            "F1": ("unit", "quantity", "commodity"),
            "F2": ("commodity", "unit", "issuer"),
            "S0": ("quantity",),
        }
        examples = [
            _Example(
                family_id=family_id,
                token_key=f"{family_id}:T{ordinal}",
                ordinal=ordinal,
                features=(("sign", f"G{family_id}{ordinal}"),),
                true_class=functional_class,
                weight=1.0 / len(vector),
            )
            for family_id, vector in vectors.items()
            for ordinal, functional_class in enumerate(vector)
        ]
        allowed_by_length = {
            length: {vector for vector in vectors.values() if len(vector) == length}
            for length in {len(vector) for vector in vectors.values()}
        }

        for seed in range(50):
            permuted = _permuted_family_labels(examples, seed=seed)
            offset = 0
            for family_id, vector in vectors.items():
                reassigned = tuple(permuted[offset : offset + len(vector)])
                self.assertIn(reassigned, allowed_by_length[len(vector)])
                if family_id == "S0":
                    self.assertEqual(reassigned, vector)
                offset += len(vector)

    def test_anchor_free_named_classes_are_not_scored(self) -> None:
        report = evaluate_identifiability(
            self.fixture,
            self.degraded,
            anchors_available=False,
            runs=3,
        )

        self.assertEqual(report["gate_status"], "not_identifiable")
        self.assertEqual(
            report["identifiability_status"],
            "named_classes_not_identifiable_without_anchors",
        )
        self.assertNotIn("observed", report)
        self.assertNotIn("majority_null", report)
        self.assertNotIn("permutation_null", report)
        self.assertNotIn("macro_f1", repr(report))

    def test_randomized_truth_does_not_pass_the_gate(self) -> None:
        rng = random.Random(808)
        all_labels = [
            token.functional_class for family in self.fixture.families for token in family.tokens
        ]
        rng.shuffle(all_labels)
        label_iterator = iter(all_labels)
        randomized_families: list[TruthFamily] = []
        for family in self.fixture.families:
            randomized_tokens: list[TruthToken] = []
            for token in family.tokens:
                randomized_tokens.append(replace(token, functional_class=next(label_iterator)))
            randomized_families.append(replace(family, tokens=tuple(randomized_tokens)))
        randomized_truth = replace(self.fixture, families=tuple(randomized_families))

        report = evaluate_identifiability(
            randomized_truth,
            self.degraded,
            runs=19,
            seed=313,
        )
        self.assertEqual(report["gate_status"], "no_go")
        self.assertLess(report["observed"]["macro_f1"], 0.60)

    def test_duplicate_rows_do_not_change_family_weighted_metrics(self) -> None:
        without_duplicates = degrade_fixture(
            self.fixture,
            DegradationConfig(seed=77, duplicate_rate=0.0),
        )
        all_duplicated = degrade_fixture(
            self.fixture,
            DegradationConfig(seed=77, duplicate_rate=1.0),
        )
        first = evaluate_identifiability(
            self.fixture,
            without_duplicates,
            runs=9,
            seed=500,
            alpha=0.10,
        )
        second = evaluate_identifiability(
            self.fixture,
            all_duplicated,
            runs=9,
            seed=500,
            alpha=0.10,
        )

        self.assertEqual(first["observed"]["macro_f1"], second["observed"]["macro_f1"])
        self.assertEqual(
            first["observed"]["balanced_accuracy"],
            second["observed"]["balanced_accuracy"],
        )
        self.assertEqual(first["observed"]["coverage"], second["observed"]["coverage"])
        self.assertLess(first["counts"]["artifacts"], second["counts"]["artifacts"])

    def test_family_partition_leakage_fails_closed(self) -> None:
        target = self.degraded.observations[0]
        opposite = "test" if target.partition == "train" else "train"
        tampered = replace(
            self.degraded,
            observations=(
                replace(target, partition=opposite),
                *self.degraded.observations[1:],
            ),
        )
        with self.assertRaisesRegex(ValueError, "partition leakage"):
            evaluate_identifiability(self.fixture, tampered, runs=1)

    def test_observation_tampering_fails_exact_degradation_contract(self) -> None:
        target = next(
            artifact
            for artifact in self.degraded.observations
            if sum(
                candidate.family_id == artifact.family_id
                for candidate in self.degraded.observations
            )
            == 1
        )
        token_index = next(
            index for index, token in enumerate(target.tokens) if token.sign_id is not None
        )
        changed_tokens = list(target.tokens)
        changed_tokens[token_index] = replace(changed_tokens[token_index], sign_id="G999")
        tampered = replace(
            self.degraded,
            observations=tuple(
                replace(artifact, tokens=tuple(changed_tokens))
                if artifact.artifact_id == target.artifact_id
                else artifact
                for artifact in self.degraded.observations
            ),
        )

        with self.assertRaisesRegex(ValueError, "deterministic degradation contract"):
            evaluate_identifiability(self.fixture, tampered, runs=1)

    def test_all_damage_is_insufficient_evidence(self) -> None:
        all_damaged = degrade_fixture(
            self.fixture,
            DegradationConfig(seed=19, damage_rate=1.0),
        )
        report = evaluate_identifiability(self.fixture, all_damaged, runs=3)
        self.assertEqual(report["gate_status"], "insufficient_evidence")
        self.assertNotIn("observed", report)

    def test_gate_argument_validation_and_convenience_runner(self) -> None:
        with self.assertRaisesRegex(ValueError, "runs"):
            evaluate_identifiability(self.fixture, self.degraded, runs=0)
        with self.assertRaisesRegex(ValueError, "alpha"):
            evaluate_identifiability(self.fixture, self.degraded, alpha=0.0)

        report = run_identifiability_gate(
            seed=5,
            family_count=64,
            runs=9,
            alpha=0.10,
        )
        self.assertIn(report["gate_status"], {"go", "no_go"})
        self.assertFalse(report["synthetic_rights"]["external_data_used"])


if __name__ == "__main__":
    unittest.main()
