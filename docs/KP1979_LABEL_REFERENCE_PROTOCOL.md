# KP1979 label-reference protocol

Status: implementation protocol; no manual reference values have been created
or accepted. The implemented machine-development geometry remains provisional
and is not accepted external reference evidence.

## Purpose and scientific boundary

This protocol defines the external manual evidence needed to test the V1
KP1979 two-column label-lattice detector. It is deliberately separate from
the 57-page proposal-only row assignment. That assignment contains detector
geometry and therefore must never be shown to a person creating reference
labels.

The selected page identities and pixels are public. If manual label values
are later created, only those values can be withheld. The later check is
therefore a
**label-withheld check**, not an unseen-page, blind-source, external,
independent, or decipherment evaluation.

A valid label reference records geometry only. It contains no printed
identifier value, lower catalog code, OCR result, sign value, occupancy
decision, reading direction, language, meaning, translation, or proposed
decipherment.

Two genuinely separate human passes are not a prerequisite for continuing
machine-assisted research or provisional corpus extraction. They are the
later promotion gate for treating geometry as externally grounded reference
evidence and for any detector score against that evidence. The absence of
human reviewers therefore limits the claim class; it does not require the
research pipeline to stop.

## Fixed partitions

The two partitions are stored and distributed as separate assignments and
separate review files.

| Partition | PDF pages |
| --- | --- |
| Development | 20, 22, 79, 129, 131, 180 |
| Future evaluation | 8, 78, 99, 128, 130, 175 |

Opening the development reference must not expose any future-evaluation
manual value. If future-evaluation values are later created, they must remain
with a genuinely separate custodian until the detector, scorer, runtime, and
entry point have been frozen. This implementation creates no manual values,
custodian, custody receipt, trusted time, or freeze evidence.

The machine-development path is restricted to the development assignment and
development page pixels. It does not open, generate, verify, compare, or score
the future-evaluation reference. Future-evaluation label values therefore
remain unopened.

## Proposal-free reviewer assignment

Each assignment binds exactly one partition to:

- the exact public source-contract and page-map bytes;
- the exact fixed source PDF;
- exactly six canonical 4880 by 7010 raw PBMs, in the fixed page order; and
- the coordinate, target, crop, and ordering rules below.

The assignment omits page roles, expected positive or negative classes,
layout classes, label sides, scan bands, detector windows, pitch, phase,
thresholds, candidate counts, candidate positions, machine crops, OCR, and
the digest of any proposal-bearing assignment. This omission prevents the
assignment itself from supplying the answers it is meant to measure.

## Manual observation rule

The target is one complete visible printed row-label block attached to a row
in a two-column corpus rendering. The block consists of the upper printed
identifier plus the lower source-local code or qualifier line or lines.
Include punctuation, primes, and question marks typographically attached to
those label lines. If part of the label is not visible, bound only its visible
ink and record the structured uncertainty.

A visible row-label block remains a geometry target even when the associated
sign region is damaged, fully hatched, broken, uninscribed, auxiliary, or
otherwise excluded later from linguistic-sequence analysis. The geometry
review does not decide row occupancy or linguistic admissibility.

Do not treat any of the following as a target:

- adjacent sign drawings, hatching, damage blocks, or row baselines;
- headings, running page labels, prose, or other editorial text;
- numbers or identifiers in a sign-list table; or
- cells or numbers in a multi-column auxiliary catalog grid.

Record the target's tightest rectangular extent in the native PBM coordinate
space:

- origin: top left;
- rectangle: half-open integer `[x0, y0, x1, y1)`;
- physical lane 0: the left page half;
- physical lane 1: the right page half; and
- order: top to bottom within each physical lane, independent of reading
  direction.

For an observed target, visible black ink must touch all four bbox edges; the
bbox may be no wider than 320 pixels and no taller than 128 pixels. These are
anti-inflation limits, not matching tolerances. Same-lane target intervals
must not overlap. If target membership or a tight boundary cannot be defended,
mark the observation or lane unresolved instead of padding the bbox.

The reference value used for y-position scoring is the label's half-open
vertical interval `[y0, y1)`. The review also commits the exact canonical PBM
crop for the same rectangle by SHA-256 and byte size. The verifier rebuilds
that crop from the supplied fixed page pixels.

Do not invent rows to fill an expected count. A partial lane remains partial.
If the existence or boundary of any target cannot be resolved, mark the
affected page unresolved. An explicitly completed page may contain zero
observations. The review schema permits both zero and nonzero observations on
every page: expected negative-control behavior is tested later and is not
made true by schema construction.

## Exposed AI-only development lane

When human reviewers are unavailable, the deterministic machine-development
path may be used to continue provisional extraction work. It creates a
`machine_development_pass` with declared machine authorship from the fixed
development assignment and exact development page pixels. Its method is
machine-bound as `kp1979-machine-development-projection-v1`, and its only
permitted evidence use is `provisional_extraction_development_only`.

This is deliberately an **exposed** development instrument, not a blind
reference creator. Its access declaration records exposure to detector output,
OCR, page-role expectations, and scoring expectations. Consequently:

- its geometry may be used to debug and advance provisional development
  extraction;
- every ambiguous observation or lane remains `unresolved` rather than being
  filled from an expected count;
- a continuous target-side column run crossing the fixed scan band is followed
  within the physical lane until a bounded ink terminus is found; a detached
  band-external run reached across at most 40 blank pixels is retained as
  evidence but records `boundary_ambiguous`; an unbounded or oversized result
  fails closed;
- sign-side ink continuing across the fixed scan band within the same 40-pixel
  separation is excluded from the crop and records `boundary_ambiguous`;
- a target association lying within the 30-pixel clustering distance of a
  vertical scan-band edge records `boundary_ambiguous`;
- an observed target requires a blank vertical split of at least 6 pixels with
  at least 15 pixels of active row-projection span on each side; insufficient
  two-tier evidence records `missing_label_tier`, while an internal horizontal
  gap alone does not invalidate that evidence;
- exact assignment, source-pixel, roster, bbox, and crop verification proves
  only that the declared machine output was reproduced from the bound bytes;
- it is ineligible as a human reference and ineligible for detector scoring;
- repeating the same method, using another AI agent, or assigning different
  opaque identifiers does not create independent evidence; and
- it must never be passed into the frozen comparison and scoring rule below.

Scoring the detector against labels created through this exposed path would
be circular. The machine pass also does not accept rows, identifiers, codes,
sign sequences, reading direction, language, meaning, translation, or a
decipherment. It may reduce engineering uncertainty and unblock extraction,
but it cannot measure detector precision or recall.

Create and then separately recompute the private machine-development record
with:

```bash
uv run indusbench prepare-kp1979-machine-development-review \
  "$KP1979_PDF" "$KP1979_PBM_DIR" \
  "$KP1979_DEVELOPMENT_ASSIGNMENT" "$KP1979_MACHINE_REVIEW"
uv run indusbench verify-kp1979-machine-development-review \
  "$KP1979_PDF" "$KP1979_PBM_DIR" \
  "$KP1979_DEVELOPMENT_ASSIGNMENT" "$KP1979_MACHINE_REVIEW"
```

Both commands are development-only. They create or verify no future-evaluation
value and emit no permission to treat the machine record as accepted
reference evidence.

## Independent human-reference procedure

This procedure is not required before provisional machine development can
continue. It is required before the project upgrades label geometry to
externally grounded reference evidence or reports detector performance
against that evidence.

Two different human reviewers should each receive a fresh proposal-free
assignment. The reviewer-facing packet should contain only the assignment,
assigned PBMs, and the manual-observation rule above; it should not contain
the scoring expectations or named negative-control roles below. Before either
pass is opened for comparison, each reviewer should:

1. inspect only the assigned page pixels and this target definition;
2. avoid detector output, OCR, the 57-page row assignment, the other review,
   and any pre-existing reference;
3. record every visible target or explicitly leave the page unresolved;
4. seal the canonical review bytes; and
5. return the bytes and the separate custody evidence to the custodian.

Each private pass records a declared authorship class and whether the reviewer
declares having seen detector output, the 57-page proposal-bearing assignment,
OCR, a peer pass, a pre-existing reference, page-role expectations, or scoring
expectations. A pass exposed to one of those inputs remains valid evidence of
what was entered but is ineligible for later independent comparison. Opaque
actor, assignment, and review identifiers and access declarations are useful
audit records. They do not prove that the author is human, that the people are
different, that access was isolated, or that custody was independent. Those
claims require external identity, distribution, return, signature, access-log,
and conflict-of-interest evidence.

Codex agents, repeated passes by one person, or different identifier strings
do not satisfy this human-reference promotion gate. Their honestly declared
machine output remains useful only in the provisional development lane above.

## Frozen comparison and scoring rule

This rule applies only after eligible human-reference evidence exists. A
`machine_development_pass` is structurally ineligible for it. The matching
rule must be frozen before future-evaluation manual values are opened:

1. A prediction contract is invalid unless every detector proposal is exactly
   96 pixels high. A valid prediction's anchor is `prediction_y0 + 48`.
2. A prediction may match a reference only on the same PDF page and physical
   lane and only when its anchor lies inside the reference `[y0, y1)`.
3. Select a maximum-cardinality, one-to-one matching that preserves
   top-to-bottom order.
4. If more than one maximum-cardinality matching exists, the page result is
   `ambiguous_matching` and no accuracy score is emitted.
5. Unmatched predictions are false positives; unmatched references are false
   negatives.
6. If any page or target remains unresolved, the partition result is
   `reference_incomplete` and no score is emitted.

No extra pixel tolerance is added after observing results.

The four predeclared hard-negative pages are 8, 20, 129, and 130. Their final
accepted target sets and detector outputs must both be empty. This is reported
as a separate `negative_control_empty` gate, not as invented precision or
recall for an empty set.

For a predeclared positive page, the accepted reference must be nonempty.
Precision is `TP / (TP + FP)` and recall is `TP / (TP + FN)`. A positive page
with no predictions has precision and recall 0; detector abstention is
therefore a failed positive-page result. For a negative-control page, neither
ratio is created and detector abstention is an empty prediction set. On the
positive pages, both micro and per-page precision and recall must be 1.0.
Passing establishes only that the V1 label-lattice geometry worked on the
selected pages. It does not accept full-row segmentation, the other 57 pages,
identifier or code transcription, sign sequences, reading direction,
language, meaning, translation, decipherment, or prize eligibility.

The source-independent matching arithmetic is implemented as an internal core
in `kp1979_label_scoring.py`. It requires an explicit use declaration, rejects
`machine_development` and `external_reference_candidate`, bounds its input
before matching, and fixes reference eligibility, evaluation admissibility,
real accuracy, decipherment, and prize eligibility false. It is not exported
as a supported generic scorer. The current supported entry point accepts only
a canonical generator-equal synthetic fixture. A future real evaluation
requires a separate entry point that binds and verifies exact eligible review
and adjudication artifacts before invoking the same frozen matching
arithmetic.

The synthetic V1 control is implemented separately and currently returns
`not_qualified`. Its known thin-stroke and periodic non-label counterexamples,
retrospective exposure, representativeness limits, and restricted metamorphic
checks are recorded in
[`KP1979_LABEL_LATTICE_SYNTHETIC_CONTROL_V1_RESULT_2026-07-29.md`](KP1979_LABEL_LATTICE_SYNTHETIC_CONTROL_V1_RESULT_2026-07-29.md).
That control reads no real or future-evaluation source. Passing a future
synthetic control would still not establish real-page accuracy.

```bash
uv run indusbench run-kp1979-label-lattice-synthetic-control
```

## Adjudication rule for the next implementation stage

After two complete eligible human pass files are sealed, comparison and
adjudication may be implemented. A safe minimal adjudication operates on whole
physical lanes: the final lane must equal pass A, equal pass B, equal their
already-identical value, or remain unresolved. It must not average coordinates
or create a third observation. All 12 lanes in a partition must be resolved
before a final reference is eligible for scoring. Machine-development output
cannot be substituted for either input.

This comparison, no-invention adjudication, detector freeze, and evaluator
are intentionally downstream of the proposal-free assignment and exact-pixel
review verifier.
