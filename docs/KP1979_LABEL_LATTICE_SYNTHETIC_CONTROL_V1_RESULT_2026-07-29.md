# KP1979 V1 label-lattice synthetic-control result

## Result

The fixed `two-column-label-lattice-v1` detector is **not qualified** by the
source-independent synthetic control.

- 13 fixed cases were run: 7 positive geometry cases and 6 negative or
  out-of-contract layout cases.
- 11 cases passed.
- All 3 limited metamorphic checks passed.
- `positive_thin_strokes` failed with synthetic precision and recall both
  `0.3611111111111111`.
- `negative_periodic_non_label_bands` failed because V1 proposed 62 positions
  on periodic horizontal ink that contains no generated two-tier labels.

The failure is retained as `not_qualified`; V1 was not retuned after observing
it.

Reproduce the fixed diagnostic with:

```bash
uv run indusbench run-kp1979-label-lattice-synthetic-control
```

The command returns a successful execution status while its JSON scientific
status remains `not_qualified`.

## What the counterexamples establish

The thin-stroke case directly shows sensitivity to generated ink mass and
scale. The periodic-band case directly shows that periodicity alone can
trigger V1 without label-specific two-tier evidence. V1 must therefore not be
promoted to a trusted automatic label detector, accepted-corpus admission
gate, or external-reference scoring input.

This does not prohibit explicitly exposed, provisional development
extraction. Such output must remain machine-authored, unresolved where
ambiguous, and ineligible as accepted external reference evidence.

## Protocol boundary

The control constructs canonical 4880 by 7010 raw PBMs and generator-known
vertical reference intervals without reading the KP1979 source, its page map,
either label-reference partition, MTAAC material, ORACC material, or any
reserved source. The frozen scorer requires 96-pixel predictions, uses the
`y0 + 48` anchor, matches only within the same page and physical lane, and
rejects ambiguous maximum matchings.

The low-level scorer is an internal synthetic arithmetic core over intervals
and declared page roles. It is not exported as a supported generic scorer and
does not verify reference provenance, custody, authorship, adjudication,
detector freeze, or evaluation eligibility. Its outputs fix
`reference_eligibility_verified`, `evaluation_admissible`, `real_accuracy`,
`decipherment`, and `prize_submission_eligible` to false. Machine-development
and external-reference-candidate uses are both rejected. The supported
synthetic evaluator first requires exact equality with a canonical generated
fixture. An eventual real evaluation requires a separate entry point that
verifies and binds exact eligible review and adjudication artifacts before
invoking the frozen matching arithmetic.

## Retrospective and representativeness limits

This is a retrospective white-box development control. Its scan geometry and
case design were created with knowledge of V1, and exploratory work had
already exposed the two failure mechanisms. It is reproducible regression and
qualification evidence, not a preregistered blind result.

Several negative cases contain label-like glyphs in a one-lane, mismatched,
discontinuous, or multi-column layout. They test required page-level
abstention, not absence of all label-like ink. The thin glyphs and periodic
bands are mechanistic counterexamples; their prevalence in the real KP1979
print is unmeasured. The metamorphic checks cover only same-process
determinism, an unread top-margin change, and one clean vertical translation.
They do not establish robustness to noise, skew, damage, horizontal movement,
or other typography.

Any successor tuned using these cases must use a new KP1979 label-detector
algorithm identifier. These 13 exposed cases may remain regression tests, but
they cannot be that successor's sole qualification set.
