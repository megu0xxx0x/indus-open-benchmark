# MTAAC V4 distributional development result

**Recorded at:** 2026-07-29T03:11:52+09:00

**Scope:** reused public known-script development data only

**Terminal decision:** `development_killed`

**Result:** [aggregate JSON](../benchmark/results/mtaac-v4-development-v1.json)

## Fixed execution

The exact V4 code and 10,354-byte plan were published before execution at
implementation commit
`304f8b36a32083330b8af02d21a58382c29d8915`. The plan SHA-256 is
`604725a5929b63f578ade07b65ca784eefefefce9b827e1686d4836f668c123b`.
The one-purpose command then accepted the exact pinned MTAAC archive and used
only the reused 271-family development partition.

The 90-family V2 holdout was neither exposed to the model nor scored. The
prospective validation source was not loaded. No result from either source was
calculated.

The aggregate report is 164,563 bytes with SHA-256
`4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897`.
It passed the closed Draft 2020-12 schema and runtime public boundary.
Independent validation reconstructed every metric from its confusion matrix,
summed every out-of-fold confusion, recomputed all paired V3 deltas and all
decision gates, and confirmed that every optimizer converged under the frozen
contract.

## Terminal decision

V4 passed every fixed gate except two mild rare-state recall requirements:

| Gate | Observed | Required | Result |
|---|---:|---:|---|
| Mild macro-F1 | 0.3878 | at least 0.3643 | pass |
| Mild `settlement_name` recall | 0.0429 | at least 0.1500 | **fail** |
| Positive paired V3 fold deltas | 5/5 | at least 4/5 | pass |
| Full-profile minus local-only mild macro-F1 | 0.0608 | at least 0.0200 | pass |
| Mild `context_only` recall | 0.7228 | at least 0.5207 | pass |
| Mild `quantity` recall | 0.2425 | at least 0.1765 | pass |
| Mild `unit` recall | 0.3052 | at least 0.3768 | **fail** |
| Mild `person_name` recall | 0.7026 | at least 0.4988 | pass |
| Clean macro-F1 | 0.4781 | at least 0.3600 | pass |
| Clean `settlement_name` recall | 0.1212 | at least 0.1000 | pass |
| Self-inclusive minus LOFO mild macro-F1 | 0.0067 | at most 0.0500 | pass |

Because every gate was required, the terminal state is
`development_killed`. The all-271-family final development model was not
fitted and has no model-state commitment. This protocol cannot execute the
prospective validation source.

## Out-of-fold development metrics

Each regime has total evaluation family mass 271. These are adaptive
development estimates on MTAAC families already used by V3, not fresh held-out
or transferable evidence.

| Metric | Clean | Mild |
|---|---:|---:|
| Weighted accuracy | 0.6427 | 0.5987 |
| Balanced accuracy | 0.5024 | 0.4032 |
| Macro-F1 | 0.4781 | 0.3878 |
| Worst-state recall | 0.1212 | 0.0429 |

Per-state recall:

| State | Clean | Mild |
|---|---:|---:|
| `context_only` | 0.7140 | 0.7228 |
| `quantity` | 0.4352 | 0.2425 |
| `unit` | 0.4907 | 0.3052 |
| `person_name` | 0.7509 | 0.7026 |
| `settlement_name` | 0.1212 | 0.0429 |

## Fixed diagnostics

The primary mild macro-F1 improved over the immutable V3 value in every outer
fold. The five paired deltas were 0.0588, 0.0785, 0.0527, 0.0885, and 0.0610.
The pooled V4 improvement over V3 was approximately 0.0634 macro-F1.

| Mild diagnostic | Macro-F1 | Difference from primary |
|---|---:|---:|
| Primary full-profile CRF | 0.3878 | — |
| Self-inclusive target profile | 0.3944 | +0.0067 |
| Independent logistic emissions | 0.3569 | -0.0308 |
| Primary CRF with transition/start weights zeroed | 0.3443 | -0.0435 |
| Local-only CRF | 0.3270 | -0.0608 |
| Strict single-family profile | 0.2562 | -0.1316 |

These diagnostics do not select or rescue the method. Within this reused
known-script development task, they show that the truth-free target-batch
profile carried material predictive information and that fitted sequence
weights also contributed. The small self-inclusive gain argues against the
primary score being driven by a family seeing its own type counts. The strict
single-family decline confirms that the method is batch-dependent and is not
an individual-inscription decoder.

## Interpretation

V4 is a real methodological improvement over V3, but not a successful transfer
instrument. Overall macro-F1, profile increment, clean integrity, and all five
paired fold comparisons passed. Nevertheless, mild settlement recovery barely
improved over V3 and remained far below the predeclared minimum, while mild
unit recall fell below its floor. Aggregate improvement therefore masks an
unacceptable rare-state trade-off.

This result does not identify an Indus sign value, word, language, reading, or
translation. It is not prospective validation, binding confirmation,
decipherment evidence, a prize result, or permission to contact an
institution.

## Consequence

Do not tune or rerun V4 and do not execute the prospective validation source.
Any result-driven method change belongs to a separately named, pre-frozen
development protocol. Reusing MTAAC again would remain adaptive development,
not additional independent evidence, and must include an explicit stopping
rule rather than an open-ended model search.

## Publication validation

The post-result release check passed Ruff, formatting, Pyright, all 573 tests
with 13 environment-specific skips, source and wheel builds, local Markdown
links, and the aggregate-result runtime/schema verifier. Gitleaks, Semgrep, and
Trivy reported no findings. A separate scan of all publishable files found no
deployment account, network address, SSH locator, or local workstation path.
