# MTAAC V5 final group-contrast development protocol

**Status:** completed once; terminal `mtaac_retired`; MTAAC retired

**Scope:** final adaptive use of the reused public known-script development
partition

**Exact plan:** `benchmark/mtaac-v5-development-v1.json`, 15,268 bytes,
SHA-256
`3c4a7c733218fcd0c4e6e25fbd59e5b86c1fd589512e9a88bb243b1d036c10f1`

**Recorded result:** [aggregate V5 result](MTAAC_V5_DEVELOPMENT_RESULT_2026-07-29.md),
59,053 bytes, SHA-256
`9b60b9eb6006efc35cdca90e91fdb07c356a09becc2a1d300ef22ec16393e88f`

## Why one final MTAAC run

V4 improved mild out-of-fold macro-F1 from 0.3243 to 0.3878 and improved
against V3 in all five paired folds. It nevertheless failed its fixed rare
state gates: `unit` recall was 0.3052 and `settlement_name` recall was 0.0429.
The aggregate confusion shows that most missed units were assigned to
`context_only`, while almost every missed settlement was assigned to
`context_only` or `person_name`.

V5 tests one narrow explanation: the two rare roles may need stronger
statistical sharing with their corresponding common roles. It is not another
feature search, architecture search, class-offset search, or threshold search.
MTAAC is retired after this one valid result, whether V5 passes or fails.

## Only model change

V5 keeps the V4 observations, 10 local features, 24 truth-free LOFO profile
features, five states, parameter layout, conditional likelihood, family
weighting, class-prior adjustment, zero initialization, five outer folds, and
deterministic L-BFGS contract.

For every emission feature coefficient and emission bias in each fixed pair
`quantity`/`unit` and `person_name`/`settlement_name`, define:

```text
mu    = (beta_a + beta_b) / 2
kappa = (beta_a - beta_b) / 2
penalty = rho * (mu^2 + 2 * kappa^2), where rho = 0.01
```

This preserves V4's penalty on the pair mean and doubles only the within-pair
contrast penalty. `context_only` emissions and bias, all start weights, and
all transition weights retain the ordinary V4 `rho / 2 * beta^2` penalty.
The parameter count and representable five-state score family are unchanged;
the inductive bias is deliberately different.

The contrast multiplier is exactly 2 and is not a runtime parameter. There is
no grid, alternate grouping, shared-plus-residual parameterization, diagnostic
model, V4 refit, or fallback.

## Exact decision

Every gate is mandatory. A minimum gate passes only when the observed value is
at least `minimum - 1e-12`; a fold improvement is counted only when the
V5-minus-V4 delta is strictly greater than `1e-12`.

| Gate | Minimum |
|---|---:|
| Mild macro-F1 | 0.3977588813953674 |
| Mild `context_only` recall | 0.520654531441017 |
| Mild `quantity` recall | 0.1765055025096581 |
| Mild `unit` recall | 0.3767836311289388 |
| Mild `person_name` recall | 0.4988092152820551 |
| Mild `settlement_name` recall | 0.15 |
| Mild `unit` precision | 0.3512887014608468 |
| Mild `settlement_name` precision | 0.20747537967348736 |
| Clean macro-F1 | 0.4680972874281771 |
| Clean `settlement_name` recall | 0.10 |
| Positive V5−V4 mild macro-F1 folds | 4 of 5 |
| Positive V5−V4 mild `unit` recall folds | 4 of 5 |
| Positive V5−V4 mild `settlement_name` recall folds | 4 of 5 |
| Folds with positive `settlement_name` recall | 5 of 5 |
| Worst-fold mild `unit` recall | 0.18225197064754597 |

The immutable V4 result supplies the exact fold-by-fold comparison vectors.
The V5 report validator reconstructs every fold metric from its 5-by-5
confusion matrix, sums the fold confusions before calculating out-of-fold
metrics, recomputes all three paired vectors and counts, and recomputes every
gate. It does not average fold macro-F1 values or trust reported derived
metrics. Profile commitments and optimizer summaries remain closed-schema
attestations; the aggregate report does not contain enough private detail to
reconstruct them independently.

## Data and publication boundary

Only the reused 271-family V2 training partition is available. The 90-family
V2 holdout is membership-checked by the gateway and then neither exposed to
the model nor scored. The prospective validation source is not loaded.

The public report may contain only family-weighted aggregate confusion
matrices, derived metrics, support counts, profile batch commitments, and
optimizer summaries. It cannot contain document, family, token, form, feature
row, prediction, membership, annotation, archive-member, or local-path data.

## One-shot lifecycle

1. Publish the reviewed V5 code and exact plan as a code-and-plan freeze.
2. Run the one-purpose network-free command once at that implementation
   commit.
3. Validate the closed schema, public boundary, support invariants, confusion
   sums, paired V4 comparisons, gates, and terminal state.
4. Publish the aggregate result separately.

A valid failed result returns `mtaac_retired`, fits no final model, and ends
this feature/model line. A valid passed result returns
`advance_to_prospective_freeze`, fits only the all-development-family V5 model,
and also retires MTAAC. Even a pass permits no prospective execution until a
separate evaluator is publicly frozen.

An optimizer, integrity, input, or report failure is a hard error rather than
a scientific result. A pre-report environmental or I/O failure may be retried
only with the exact same implementation commit, plan bytes, archive bytes, and
CLI arguments, and only when no scientific metric was emitted or exposed. Any
code, plan, data, or argument change—or any exposed partial scientific
metric—retires V5/MTAAC without another MTAAC attempt.

## Recorded outcome

The exact command completed once at public implementation commit
`b0be18d7c317d276dfefd1237c17ec0be6886cd0`. V5 passed 7 of 15 mandatory
gates. Mild macro-F1 was 0.3846, `unit` recall was 0.2937, and
`settlement_name` recall was 0.0575. The terminal result is
`mtaac_retired`; no final development model was fitted. The V2 holdout and
prospective source remained unscored. The predeclared stopping rule prohibits
another MTAAC attempt.

## Non-claims

V5 is result-adaptive known-script method development. A pass would not be
fresh held-out evidence and would not establish an Indus sign value, reading,
language, translation, decipherment, binding confirmation, prize result, or
permission for institutional contact.
