# MTAAC known-script control V2 result

**Result date:** 2026-07-28

**Terminal status:** `NO_GO`

**Scientific scope:** known-script word-category method instrument only; not
evidence for an Indus sign value, function, language, meaning, translation,
decipherment, or prize eligibility

## Immutable commitments

- Public pre-result code freeze:
  `37157f1411a55ffd91b7327afaca8fc1080fa708`
- Protocol: `mtaac-known-script-control-v2`
- Protocol SHA-256:
  `sha256:25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892`
- Aggregate [result JSON](../benchmark/results/mtaac-known-script-control-v2.json)
  SHA-256:
  `sha256:6bc4ed610862d109b596bdd934f36fd19b99e3cbfcced42882546d0c852a7afe`
- Fixed null schedule: 999 runs, seeds 0 through 998
- Runtime recorded in the result: CPython 3.12.3, Linux x86-64,
  glibc 2.39, 53-bit binary-float mantissa

The public freeze commit and exact V2 protocol bytes were publicly visible
before this invocation. The command used the fixed source archive, default
frozen protocol, fixed split/degradation seeds, fixed 999-run null, and no
override. The operator record states that the output target did not exist,
was created once, and was byte-identical to stdout.

V1 remains preserved separately. Its first invocation emitted only the
[recorded fail-closed error](../benchmark/results/mtaac-known-script-control-v1-attempt-1-error.json).
No V1 metric value was emitted or inspected. V2 is a separately frozen
numerical-integrity correction, not an overwritten V1 result.

## Primary decision

All decision-bearing acceptance gates passed except one:

| Gate | Frozen requirement | V2 result | Status |
|---|---:|---:|---|
| Clean macro-F1 | ≥ 0.60 | 0.840360 | pass |
| Clean observed − reference | ≥ 0.10 | 0.232282 | pass |
| Clean minimum class recall | ≥ 0.35 | 0.654134 (`settlement_name`) | pass |
| Clean minimum class coverage | ≥ 0.95 | 1.000000 | pass |
| Mild macro-F1 | ≥ 0.60 | 0.649244 | pass |
| Mild observed − reference | ≥ 0.10 | 0.179967 | pass |
| Mild add-one permutation p | ≤ 0.05 | 0.001000 | pass |
| Mild movable-family fraction | ≥ 0.80 | 0.893939 | pass |
| Mild minimum train families | ≥ 40 | 125 | pass |
| Mild minimum test families | ≥ 20 | 30 | pass |
| Mild minimum class coverage | ≥ 0.75 | 0.857912 (`unit`) | pass |
| Mild minimum class recall | ≥ 0.35 | 0.193553 (`settlement_name`) | **fail** |
| Integrity and leakage checks | all true | all true | pass |

The mild `settlement_name` recall missed its frozen threshold by 0.156447.
Its precision was 0.784591 and F1 was 0.310507. The other mild recalls were
0.865843 for `quantity`, 0.551024 for `unit`, and 0.861998 for
`person_name`.

The clean permutation-null p95 was 0.608078 and the mild p95 was 0.469277.
No one of the 999 null macro-F1 values reached the corresponding observed
macro-F1, yielding the add-one value 0.001 in both regimes. The nonbinding
harsh diagnostic macro-F1 was 0.452078; its `settlement_name` recall was zero.

## Interpretation

V2 shows that the frozen categorical method learns substantial signal in the
known script, but it does not maintain the required four-class robustness
under the declared mild damage, direction, truncation, and replica stress.
The failure is class-specific rather than a decision-bearing support, leakage,
coverage, null, or overall-macro failure. Some explicitly nonbinding diagnostic
strata have inadequate class support; they cannot change the V2 outcome.

Under the frozen rule, this is a method-control failure. The V2 method must
not be transferred unchanged to Indus data and must not support a reading,
translation, decipherment, or prize submission. It does not show that Indus
is undecipherable; it shows that this particular method has not cleared its
known-script safety gate.

## Consequence for the next method

The V2 result is immutable and must not be rescued by changing its seed,
threshold, split, class set, or decision rule. Any improvement is explicitly
post-result work and requires a V3 protocol.

A V3 candidate may use V2 only as development evidence. Because the V2
aggregate has now exposed the weak class, the same holdout cannot serve as a
fresh confirmatory test for V3. Efficient next work is therefore:

1. diagnose the settlement failure using train-side or separately declared
   development analyses without rewriting V2;
2. test structured sequence, uncertainty-aware, and class-balanced candidates
   under fixed training-only cross-validation;
3. add a rights-cleared context-bearing and preferably native-glyph
   known-script control; and
4. commit or otherwise seal a genuinely untouched confirmatory partition
   before V3 development, then freeze the chosen V3 method before evaluating
   that partition or a separate untouched source.

This ordering protects the project from optimizing directly against the only
known failure and mistaking repair of one exposed aggregate for general
decipherment capability.
