# MTAAC V5 group-contrast development result

**Execution completed:** 2026-07-29T04:23:53+09:00

**Result document recorded:** 2026-07-29T04:27:26+09:00

**Scope:** reused public known-script development data only

**Terminal decision:** `mtaac_retired`

**Result:** [aggregate JSON](../benchmark/results/mtaac-v5-development-v1.json)

## Fixed execution

The V5 implementation and plan were frozen before execution at implementation
commit `b0be18d7c317d276dfefd1237c17ec0be6886cd0`. The plan SHA-256 is
`3c4a7c733218fcd0c4e6e25fbd59e5b86c1fd589512e9a88bb243b1d036c10f1`.
V5 had one fixed candidate and no result-dependent model selection. It retained
the V4 likelihood and applied the predeclared stronger contrast penalty to the
`quantity`/`unit` and `person_name`/`settlement_name` emission pairs.

The aggregate report is 59,053 bytes with SHA-256
`9b60b9eb6006efc35cdca90e91fdb07c356a09becc2a1d300ef22ec16393e88f`.
It passed the closed schema and runtime public-boundary validator against the
exact implementation commit. All five outer-fold optimizers converged under
the frozen contract.

The post-result publication audit passed all 44 focused V5 tests and all 617
repository tests (604 passed and 13 environment-specific tests skipped),
independent confusion/metric/gate recomputation, source and wheel builds,
local link checks, and the Gitleaks, Semgrep, and Trivy scans.

The model used only the reused 271-family MTAAC development partition. The
90-family V2 holdout was neither exposed to the model nor scored. The
prospective reserved source was not loaded or executed. No result from either
source was calculated, and no item-level predictions are published.

## Terminal gate decision

V5 passed 7 of 15 mandatory gates and failed 8. The table displays decimals
rounded to six places; the pass/fail decisions use the full-precision values in
the aggregate JSON. A minimum gate passes when the observed value is at least
the minimum minus `1e-12`. A positive delta is counted only when it is strictly
greater than `1e-12`.

| # | Mandatory gate | Observed | Required | Result |
|---:|---|---:|---:|---|
| 1 | Mild macro-F1 | 0.384553 | at least 0.397759 | **fail** |
| 2 | Mild `context_only` recall | 0.721152 | at least 0.520655 | pass |
| 3 | Mild `quantity` recall | 0.227511 | at least 0.176506 | pass |
| 4 | Mild `unit` recall | 0.293690 | at least 0.376784 | **fail** |
| 5 | Mild `person_name` recall | 0.690892 | at least 0.498809 | pass |
| 6 | Mild `settlement_name` recall | 0.057466 | at least 0.150000 | **fail** |
| 7 | Mild `unit` precision | 0.346242 | at least 0.351289 | **fail** |
| 8 | Mild `settlement_name` precision | 0.213849 | at least 0.207475 | pass |
| 9 | Clean macro-F1 | 0.478498 | at least 0.468097 | pass |
| 10 | Clean `settlement_name` recall | 0.149507 | at least 0.100000 | pass |
| 11 | Outer folds with positive V5-minus-V4 mild macro-F1 | 1/5 | at least 4/5 | **fail** |
| 12 | Outer folds with positive V5-minus-V4 mild `unit` recall | 0/5 | at least 4/5 | **fail** |
| 13 | Outer folds with positive V5-minus-V4 mild `settlement_name` recall | 3/5 | at least 4/5 | **fail** |
| 14 | Outer folds with positive mild `settlement_name` recall | 5/5 | 5/5 | pass |
| 15 | Worst-fold mild `unit` recall | 0.168498 | at least 0.182252 | **fail** |

Because every gate was required, the terminal state is `mtaac_retired`.
Passing clean-data integrity gates and some state-level floors cannot rescue
the failed decision. The all-271-family final development model was not fitted:
its model-state commitment and optimizer record are both null.

## Out-of-fold development metrics

Each regime has total evaluation family mass 271. These are adaptive estimates
from a development corpus already reused by earlier MTAAC versions, not fresh
held-out or transferable evidence.

| Metric | Clean | Mild |
|---|---:|---:|
| Weighted accuracy | 0.641453 | 0.593628 |
| Balanced accuracy | 0.502749 | 0.398142 |
| Macro-F1 | 0.478498 | 0.384553 |
| Worst-state recall | 0.149507 | 0.057466 |

Per-state recall:

| State | Clean | Mild |
|---|---:|---:|
| `context_only` | 0.717125 | 0.721152 |
| `quantity` | 0.410895 | 0.227511 |
| `unit` | 0.485722 | 0.293690 |
| `person_name` | 0.750498 | 0.690892 |
| `settlement_name` | 0.149507 | 0.057466 |

## Fixed V4 comparison

The pooled mild comparison moved `settlement_name` in the intended direction,
but moved overall macro-F1 and `unit` recall in the wrong direction:

| Mild metric | V4 | V5 | V5 minus V4 |
|---|---:|---:|---:|
| Macro-F1 | 0.387759 | 0.384553 | -0.003206 |
| `unit` recall | 0.305216 | 0.293690 | -0.011526 |
| `settlement_name` recall | 0.042942 | 0.057466 | +0.014524 |
| `unit` precision | 0.351289 | 0.346242 | -0.005047 |
| `settlement_name` precision | 0.207475 | 0.213849 | +0.006373 |

The predeclared paired comparison was not supported consistently across outer
folds:

| Outer fold | Macro-F1 delta | `unit` recall delta | `settlement_name` recall delta |
|---:|---:|---:|---:|
| 0 | -0.002758 | -0.013754 | +0.023012 |
| 1 | +0.002187 | -0.003225 | +0.023979 |
| 2 | -0.007052 | -0.023824 | approximately 0 |
| 3 | -0.008965 | -0.018882 | 0 |
| 4 | -0.000376 | -0.001322 | +0.024888 |

Thus only 1/5 macro-F1 deltas and 0/5 `unit` recall deltas were positive.
`settlement_name` recall was strictly positive in all five V5 folds, but
improved over V4 in only 3/5; the other two folds were unchanged within the
fixed comparison tolerance.

## Scientific interpretation

The fixed stronger pairwise contrast penalty produced modest pooled gains in
mild `settlement_name` recall and precision. Those gains were insufficient:
the recall remained far below its absolute floor, and its improvement was not
present in the required four folds. At the same time, mild `unit` recall and
precision declined, every fold's `unit` recall was worse than V4, and the
worst-fold result also deteriorated. Mild macro-F1 declined overall and
improved in only one fold.

The predeclared operational hypothesis therefore failed: this particular fixed
form and strength of pairwise group-contrast regularization did not rescue both
rare roles without an unacceptable trade-off on the reused MTAAC development
task. This does not establish that group sharing in general is ineffective,
nor does it isolate a universal linguistic or archaeological mechanism.
Paired folds share the adaptive development history and are descriptive
comparisons, not independent significance or generalization evidence.

## Claim boundary

This result does not identify an Indus sign value, word, language, reading, or
translation. It is not V2 holdout evidence, prospective or reserved-source
validation, binding confirmation, decipherment evidence, a prize result, or
permission to contact an institution. Clean-data performance does not change
that boundary.

## MTAAC termination

V5 was the predeclared final MTAAC attempt. MTAAC is retired after this valid
result, independently of the direction of any individual metric. Do not tune
or rerun V5, fit its final development model, expose the V2 holdout, execute
the prospective source under this protocol, or return to another MTAAC
iteration on this feature/model line.

Any future empirical work must be a separately named and publicly frozen
protocol with a genuinely different evidential basis or control structure.
It must not present another adaptive reuse of MTAAC as independent
confirmation.
