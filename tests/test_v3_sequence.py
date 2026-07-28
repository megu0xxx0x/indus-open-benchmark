from __future__ import annotations

import hashlib
import re
import unittest

from indusbench.v3dev.contracts import (
    V3_STRUCTURAL_STATES,
    MTAACTrainingDocument,
    MTAACTrainingLine,
    MTAACTrainingToken,
    V3ReportedDirection,
    V3StructuralState,
)
from indusbench.v3dev.sequence import (
    V3SequenceError,
    V3SequenceModel,
    structural_feature_rows,
)


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _document_key(label: str) -> str:
    return f"mtaac-document-source-id-sha256-v1:{_hex(f'document:{label}')}"


def _token_key(label: str) -> str:
    return f"mtaac-token-source-order-sha256-v1:{_hex(f'token:{label}')}"


def _form_id(label: str) -> str:
    return f"mtaac-word-form-sha256-v1:{_hex(f'form:{label}')}"


def _cluster_id(label: str) -> str:
    return _hex(f"cluster:{label}")


def _line(
    label: str,
    states: tuple[V3StructuralState, ...],
    *,
    equality_pattern: tuple[int | None, ...] | None = None,
    direction: V3ReportedDirection = "known_source_order",
) -> MTAACTrainingLine:
    if equality_pattern is None:
        equality_pattern = tuple(range(len(states)))
    tokens = []
    for index, (state, equality_code) in enumerate(zip(states, equality_pattern, strict=True)):
        damaged = equality_code is None
        tokens.append(
            MTAACTrainingToken(
                token_key=_token_key(f"{label}:{index}"),
                observed_form_id=(
                    None if damaged else _form_id(f"{label}:equality:{equality_code}")
                ),
                state=state,
                damaged=damaged,
            )
        )
    return MTAACTrainingLine(
        line_ordinal=0,
        reported_direction=direction,
        tokens=tuple(tokens),
    )


def _document(
    label: str,
    states: tuple[V3StructuralState, ...],
    *,
    equality_pattern: tuple[int | None, ...] | None = None,
    family_label: str | None = None,
) -> MTAACTrainingDocument:
    return MTAACTrainingDocument(
        document_key=_document_key(label),
        cluster_identifier=_cluster_id(family_label or label),
        regime="clean",
        replica_index=0,
        lines=(
            _line(
                label,
                states,
                equality_pattern=equality_pattern,
            ),
        ),
    )


def _balanced_singletons(prefix: str) -> tuple[MTAACTrainingDocument, ...]:
    return tuple(_document(f"{prefix}:{state}", (state,)) for state in V3_STRUCTURAL_STATES)


def _unit_weights(
    documents: tuple[MTAACTrainingDocument, ...],
) -> dict[str, float]:
    return {document.cluster_identifier: 1.0 for document in documents}


class V3StructuralFeatureTests(unittest.TestCase):
    def test_features_depend_on_equality_not_exact_fingerprints(self) -> None:
        first = _line(
            "first",
            ("context_only", "quantity", "settlement_name"),
            equality_pattern=(0, 0, None),
            direction="unknown_visual_order",
        )
        second = _line(
            "second",
            ("context_only", "quantity", "settlement_name"),
            equality_pattern=(7, 7, None),
            direction="unknown_visual_order",
        )

        first_rows = structural_feature_rows(first.to_observation())
        second_rows = structural_feature_rows(second.to_observation())

        self.assertEqual(first_rows, second_rows)
        self.assertEqual(len(first_rows), 3)
        self.assertEqual(dict(first_rows[2])["damage"], "damaged")
        self.assertEqual(dict(first_rows[0])["next_equality"], "same")
        rendered = repr(first_rows)
        for token in first.tokens:
            if token.observed_form_id is not None:
                self.assertNotIn(token.observed_form_id, rendered)
            self.assertNotIn(token.token_key, rendered)


class V3SequenceModelTests(unittest.TestCase):
    def test_fixed_ties_predict_every_token_including_damage(self) -> None:
        documents = _balanced_singletons("tie")
        model = V3SequenceModel.fit(
            documents,
            base_family_weights=_unit_weights(documents),
            gamma=0.0,
        )
        query = _line(
            "query",
            ("context_only", "context_only", "context_only"),
            equality_pattern=(0, None, 1),
        )

        predictions = model.decode(
            query.to_observation(),
            transition_strength=0.0,
        )

        self.assertEqual(
            predictions,
            ("context_only", "context_only", "context_only"),
        )
        self.assertEqual(len(predictions), len(query.tokens))

    def test_gamma_balances_emissions_but_not_transitions(self) -> None:
        documents = _balanced_singletons("balance")
        base_weights = {
            document.cluster_identifier: (
                8.0 if document.lines[0].tokens[0].state == "context_only" else 1.0
            )
            for document in documents
        }

        unbalanced = V3SequenceModel.fit(
            documents,
            base_family_weights=base_weights,
            gamma=0.0,
        )
        balanced = V3SequenceModel.fit(
            documents,
            base_family_weights=base_weights,
            gamma=1.0,
        )

        self.assertGreater(
            dict(unbalanced.class_masses)["context_only"],
            dict(unbalanced.class_masses)["settlement_name"],
        )
        masses = [mass for _, mass in balanced.class_masses]
        for mass in masses[1:]:
            self.assertAlmostEqual(mass, masses[0])
        self.assertEqual(
            unbalanced.start_log_probabilities,
            balanced.start_log_probabilities,
        )
        self.assertEqual(
            unbalanced.transition_log_probabilities,
            balanced.transition_log_probabilities,
        )

    def test_viterbi_transition_strength_changes_the_path(self) -> None:
        cycle = tuple(
            _document(
                f"cycle:{index}",
                (state, V3_STRUCTURAL_STATES[(index + 1) % len(V3_STRUCTURAL_STATES)]),
            )
            for index, state in enumerate(V3_STRUCTURAL_STATES)
        )
        model = V3SequenceModel.fit(
            cycle,
            base_family_weights=_unit_weights(cycle),
            gamma=0.0,
        )
        query = _line(
            "cycle-query",
            ("context_only", "context_only"),
        )

        observation = query.to_observation()
        independent = model.decode(observation, transition_strength=0.0)
        sequenced = model.decode(observation, transition_strength=1.0)

        self.assertEqual(independent, ("context_only", "context_only"))
        self.assertEqual(sequenced, ("settlement_name", "context_only"))

    def test_unknown_feature_value_is_neutral_for_every_state(self) -> None:
        documents = _balanced_singletons("unknown")
        model = V3SequenceModel.fit(
            documents,
            base_family_weights=_unit_weights(documents),
            gamma=0.5,
        )

        features = list(structural_feature_rows(documents[0].lines[0].to_observation())[0])
        original_value = features[0][1]
        original_scores = model._emission_scores(features)
        features[0] = ("position_bucket", "never-observed-in-this-fold")
        unknown_scores = model._emission_scores(features)

        for state_index, state in enumerate(V3_STRUCTURAL_STATES):
            expected = (
                original_scores[state_index]
                - model._feature_log_probabilities[state]["position_bucket"][original_value]
            )
            self.assertAlmostEqual(unknown_scores[state_index], expected)
        with self.assertRaisesRegex(V3SequenceError, "complete ordered"):
            model._emission_scores(())

    def test_commitment_is_identifier_free_and_identity_invariant(self) -> None:
        first = _balanced_singletons("commitment-a")
        second = _balanced_singletons("commitment-b")
        first_model = V3SequenceModel.fit(
            first,
            base_family_weights=_unit_weights(first),
            gamma=0.5,
        )
        second_model = V3SequenceModel.fit(
            second,
            base_family_weights=_unit_weights(second),
            gamma=0.5,
        )

        first_commitment = first_model.model_state_commitment(transition_strength=0.5)
        second_commitment = second_model.model_state_commitment(transition_strength=0.5)

        self.assertEqual(first_commitment, second_commitment)
        self.assertIsNotNone(re.fullmatch(r"sha256:[0-9a-f]{64}", first_commitment))
        self.assertFalse(hasattr(first_model, "__dict__"))
        for document in first:
            self.assertNotIn(document.document_key, first_commitment)
            self.assertNotIn(document.cluster_identifier, first_commitment)
        self.assertNotEqual(
            first_commitment,
            first_model.model_state_commitment(transition_strength=1.0),
        )
        with self.assertRaisesRegex(V3SequenceError, "transition strength"):
            first_model.model_state_commitment(transition_strength=0.25)

    def test_closed_grid_and_exact_family_weights_fail_closed(self) -> None:
        documents = _balanced_singletons("invalid")
        weights = _unit_weights(documents)

        with self.assertRaisesRegex(V3SequenceError, "gamma"):
            V3SequenceModel.fit(
                documents,
                base_family_weights=weights,
                gamma=0.25,
            )
        with self.assertRaisesRegex(V3SequenceError, "exactly cover"):
            V3SequenceModel.fit(
                documents,
                base_family_weights={},
                gamma=0.0,
            )
        model = V3SequenceModel.fit(
            documents,
            base_family_weights=weights,
            gamma=0.0,
        )
        with self.assertRaisesRegex(V3SequenceError, "transition strength"):
            model.decode(
                documents[0].lines[0].to_observation(),
                transition_strength=0.25,
            )


if __name__ == "__main__":
    unittest.main()
