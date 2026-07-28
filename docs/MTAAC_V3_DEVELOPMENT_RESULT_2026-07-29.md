# MTAAC V3 structural development result

**Recorded at:** 2026-07-29T01:19:40+09:00

**Scope:** public known-script development only

**Result:** [aggregate JSON](../benchmark/results/mtaac-v3-development-v1.json)

## Fixed execution

The exact V3 plan was published before execution. The one-purpose command then
accepted the pinned MTAAC archive and plan at implementation commit
`5b39c8ba358ea66e46183cbf02eb07fbc91861e2`. It used only the 271 V2 training
families. The 90-family V2 holdout was not exposed to the model and was not
scored. The reserved prospective validation source was not loaded.

The aggregate report is 77,086 bytes with SHA-256
`e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2`.
It passed the closed report schema, the independent public-output boundary,
and recomputation of every outer-fold aggregate confusion matrix and
one-standard-error selection. The final identifier-free model-state
commitment is
`sha256:d2b332f6d9b2b6acae206f7f0b8db07d7e2431b5995168f7228a374e4f134158`.

## Selection

All five outer folds selected the same candidate:

- class-balance exponent `gamma = 0.5`;
- transition strength `lambda = 0`; and
- complexity rank `3` in the fixed nine-candidate grid.

The separate four-fold final-development selection chose the same candidate.
The zero transition strength is scientifically important: under this feature
surface and selection rule, the first-order sequence component did not improve
over the structural emission model.

## Out-of-fold development metrics

Each regime has total family mass 271. These are development estimates on the
already declared MTAAC training partition, not a held-out or transferable
result.

| Metric | Clean | Mild |
|---|---:|---:|
| Weighted accuracy | 0.5402 | 0.4895 |
| Balanced accuracy | 0.3679 | 0.3619 |
| Macro-F1 | 0.3296 | 0.3243 |
| Worst-state recall | 0.0000 | 0.0369 |

Per-state recall:

| State | Clean | Mild |
|---|---:|---:|
| `context_only` | 0.6606 | 0.5707 |
| `quantity` | 0.1872 | 0.2265 |
| `unit` | 0.4302 | 0.4268 |
| `person_name` | 0.5618 | 0.5488 |
| `settlement_name` | 0.0000 | 0.0369 |

## Interpretation

V3 established a leak-resistant, family-weighted five-state baseline and
removed the V2 target-eligibility oracle. It did not establish a sufficiently
informative cross-script structural model. The low quantity recall, near-zero
settlement-name recall, and rejection of the transition component show that
within-line equality and local positional features alone are too weak for the
project goal.

The result does not identify an Indus sign value, word, language, reading, or
translation. It is not a reserved validation result, binding confirmation,
prize result, or evidence of decipherment.

## Highest-value next method change

Do not tune the frozen V3 result. A separate V4 development plan should first
add corpus-level, source-neutral distributional features derived without gold:

- frequency and document/line-dispersion buckets;
- initial, final, and normalized-position tendencies;
- left/right context diversity and entropy;
- repetition and neighbor-frequency profiles; and
- fixed conjunctions of these statistics with the existing local structure.

Exact lexical identities remain unavailable to the classifier; they may be
used transiently only to calculate equality and aggregate distributional
statistics. Fold computation must prevent training-label or family leakage,
and all feature formulas must be frozen before any reserved-source
performance run.

A discriminative linear-chain model can then test whether those features make
transitions useful. If it still cannot recover rare structural states under
the same grouped development design, the efficient conclusion is that this
known-script transfer task lacks sufficient observable structure, not that a
larger opaque model should be tried indefinitely.
