from __future__ import annotations

import math
import unittest
from dataclasses import fields

from indusbench.v3dev.contracts import V3ObservationLine, V3ObservationToken
from indusbench.v4dev.contracts import (
    V4ContractError,
    V4FeatureCorpus,
    V4FeatureDocument,
    V4FeatureLine,
    V4LabeledFeatureDocument,
    V4LabeledFeatureFamily,
    V4LabeledFeatureLine,
    V4ObservationCorpus,
    V4ObservationDocument,
)


def _line(ordinal: int = 0) -> V3ObservationLine:
    return V3ObservationLine(
        line_ordinal=ordinal,
        reported_direction="known_source_order",
        tokens=(V3ObservationToken(observation_id="opaque-a", damaged=False),),
    )


class V4ObservationContractTests(unittest.TestCase):
    def test_observation_objects_have_no_identity_or_truth_field(self) -> None:
        document = V4ObservationDocument(lines=(_line(),))
        corpus = V4ObservationCorpus(documents=(document,))

        self.assertEqual([field.name for field in fields(V4ObservationDocument)], ["lines"])
        self.assertEqual([field.name for field in fields(V4ObservationCorpus)], ["documents"])
        self.assertIs(corpus.documents[0].lines[0], document.lines[0])

    def test_observation_lines_must_be_uniquely_ordered(self) -> None:
        with self.assertRaisesRegex(V4ContractError, "unique and ordered"):
            V4ObservationDocument(lines=(_line(1), _line(0)))
        with self.assertRaisesRegex(V4ContractError, "unique and ordered"):
            V4ObservationDocument(lines=(_line(0), _line(0)))


class V4FeatureContractTests(unittest.TestCase):
    def test_feature_objects_are_id_free_and_preserve_shape(self) -> None:
        feature_line = V4FeatureLine(
            rows=(
                (
                    ("category", "known"),
                    ("numeric", 0.25),
                ),
            )
        )
        feature_document = V4FeatureDocument(lines=(feature_line,))
        feature_corpus = V4FeatureCorpus(documents=(feature_document,))

        self.assertEqual([field.name for field in fields(V4FeatureLine)], ["rows"])
        self.assertEqual([field.name for field in fields(V4FeatureDocument)], ["lines"])
        self.assertEqual([field.name for field in fields(V4FeatureCorpus)], ["documents"])
        self.assertEqual(feature_corpus.documents[0].lines[0].rows[0][1][1], 0.25)

    def test_numeric_feature_values_are_finite_unit_floats(self) -> None:
        invalid = (-0.01, 1.01, math.inf, math.nan, 1, True)
        for value in invalid:
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(V4ContractError, "numeric feature"),
            ):
                V4FeatureLine(rows=((("numeric", value),),))  # type: ignore[arg-type]

    def test_feature_names_are_unique(self) -> None:
        with self.assertRaisesRegex(V4ContractError, "unique"):
            V4FeatureLine(rows=((("same", "a"), ("same", "b")),))

    def test_labeled_types_validate_positional_lengths_and_states(self) -> None:
        feature_line = V4FeatureLine(rows=((("feature", 0.5),),))
        labeled_line = V4LabeledFeatureLine(
            feature_line=feature_line,
            states=("quantity",),
        )
        document = V4LabeledFeatureDocument(lines=(labeled_line,))
        family = V4LabeledFeatureFamily(documents=(document,))

        self.assertEqual(family.documents[0].lines[0].states, ("quantity",))
        with self.assertRaisesRegex(V4ContractError, "equal length"):
            V4LabeledFeatureLine(feature_line=feature_line, states=())
        with self.assertRaisesRegex(V4ContractError, "five-state"):
            V4LabeledFeatureLine(
                feature_line=feature_line,
                states=("unsupported",),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
