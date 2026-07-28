# MTAAC V3 development protocol

**Protocol status:** development only; no V3 result has been executed or
published

**Recorded at:** 2026-07-29T00:54:12+09:00

**Normative plan:** [mtaac-v3-development-v1.json](../benchmark/mtaac-v3-development-v1.json)

## Purpose and nonclaim

V3 is a post-result method-development instrument. It tests whether a
source-neutral structural sequence model can recover five mechanically
projected states in a known script without receiving the V2 target-eligibility
oracle. It is not an Indus-script reading, translation, decipherment,
confirmation, prize result, or evidence that the same labels exist in Indus
inscriptions.

The V2 implementation, protocol, split, and published `NO_GO` result remain
immutable. V3 is separate work and must not rewrite or reinterpret V2.

## Fixed development-data boundary

The gateway accepts only the exact MTAAC archive and the exact V2 split
commitments. It verifies fixed split membership and exposes only the 271 V2
training families to V3. The 90 V2 holdout families are excluded before the
model-visible training views are built: they receive no prediction, score,
candidate selection, tuning, debugging, or feature-design role in V3.

The model receives only the fixed clean and mild development views of those
271 families. Clean is a guard and diagnostic regime. Mild is the sole
candidate-selection regime and the primary development-evaluation regime.
Each training family has total base mass one across its clean and mild
occurrences. During evaluation, each validation family has total mass one
within each reported regime.

## Task and observation boundary

V3 predicts one of these states for every retained token, including damaged
tokens:

1. `context_only`
2. `quantity`
3. `unit`
4. `person_name`
5. `settlement_name`

An empty mechanical gold projection maps to `context_only`. Gold labels and
training-family identifiers are unavailable to the prediction interface.
Opaque observation identifiers may be used only to derive equality structure
within a line and are then discarded. Exact MTAAC or ORACC lexical identities,
raw annotation values, external embeddings, tokenizers, and pretrained
language models are not model features.

The exact source-neutral feature surface is:

- token-position and line-length buckets;
- reported direction and damage state;
- observation-presence state;
- equality with the previous and next token;
- within-line frequency;
- whether an equal observation has appeared before or will appear later; and
- a canonical equality-and-damage line template.

These features describe local form repetition and sequence position. They do
not provide a sign reading, lemma, language, translation, or archaeological
context.

## Fixed model and selection

The first V3 baseline combines weighted categorical naive-Bayes emissions,
first-order transition counts, and Viterbi decoding. Laplace smoothing is
fixed at `alpha = 1`. Transition counts use unadjusted family weights.
Unknown feature values contribute neutral rather than adverse evidence.

There are exactly nine candidates:

- class-balance exponent `gamma ∈ {0, 0.5, 1}`; and
- transition strength `lambda ∈ {0, 0.5, 1}`.

Development uses family-grouped nested cross-validation with five outer folds
and four inner folds. A complete sequence family can never cross a fold
boundary. Every training and validation partition must have positive support
for all five states. There is no seed search and no fallback split.

Inner selection uses family-weighted mild macro-F1. The one-standard-error
rule chooses the simplest eligible candidate, ordered by lower `gamma` and
then lower `lambda`. Clean results remain diagnostics and cannot select a
candidate. After nested development, the final development configuration is
selected by a separately domain-separated fixed four-fold family-grouped
procedure over all 271 development families, using mild only, before fitting
the aggregate development model.

## Public report boundary

Any V3 development report is aggregate only. It may contain parent
commitments, family/fold/support totals, the fixed candidate configurations,
aggregate fold metrics and confusion matrices, the selected configuration,
and a model commitment.

It must not contain source-document or token identifiers, family or fold
membership, per-document or per-family predictions or metrics, archive-member
or local paths, raw source annotations, private operational details, or ORACC
counts or results. It must state that the report is development only, that the
V2 holdout was not scored, and that the reserved validation source was not
loaded.

## Validation and binding-confirmation boundary

The fixed ORACC ED3b administrative corpus is a
**feature-safety-exposed prospective validation source**, not binding
confirmation. Rights/schema inspection, aggregate class inspection, and
gold-conditioned safety analysis informed its observation sanitizer. Those
exposures cannot be undone. ORACC remains prohibited from V3 fitting,
selection, tuning, debugging, and further feature design.

A binding confirmation must use a different, previously uninspected corpus
whose selection cannot be cherry-picked by the project. The admissible paths
are:

- independent custody that reserves the source before project access; or
- selection by a public random beacon after complete model/evaluator freeze
  from a predeclared ordered eligible pool, with support failure and fallback
  behavior fixed in advance.

No post-hoc ORACC subdivision can create binding confirmation.

## Current execution state

At the timestamp above, the machine-readable V3 development plan exists and
implementation work is in progress. No V3 development result file exists, no
reserved ORACC validation has been executed, and no binding-confirmation
source has been selected. The next controlled sequence is to complete and
verify the isolated V3 implementation, freeze and publish the code and
protocol, execute the exact MTAAC development run once, and publish only its
aggregate development report.

Related records:

- [MTAAC V2 result](MTAAC_KNOWN_SCRIPT_CONTROL_V2_RESULT_2026-07-28.md)
- [ORACC ED3b source audit](ORACC_ED3B_VALIDATION_SOURCE_2026-07-28.md)
- [ORACC aggregate source-qualification receipt](../benchmark/results/oracc-ed3b-validation-source-v1.json)
- [global known-script source audit](V3_GLOBAL_KNOWN_SCRIPT_SOURCE_AUDIT_2026-07-28.md)
