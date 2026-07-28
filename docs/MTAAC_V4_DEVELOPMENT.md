# MTAAC V4 distributional development protocol

**Status:** executed once; terminal decision `development_killed`

**Scope:** reused known-script development data only

**Result:** [aggregate result and interpretation](MTAAC_V4_DEVELOPMENT_RESULT_2026-07-29.md)

**Exact plan:** `benchmark/mtaac-v4-development-v1.json`, 10,354 bytes,
SHA-256
`604725a5929b63f578ade07b65ca784eefefefce9b827e1686d4836f668c123b`

## Question

V3 showed that low-cardinality position and within-line equality features were
not sufficient for the five-state structural task. V4 asks one narrower
question: can a fixed, truth-free corpus profile and one regularized
linear-chain model improve rare-state recovery without learning source or form
identity?

This is not a decipherment experiment. It predicts mechanically projected
MTAAC roles and cannot establish an Indus language, sound, sign value, word,
reading, or translation.

## Immutable parent boundary

V4 is a new package, command, plan, schema, and result namespace. It does not
modify the V2 or V3 implementation, protocol, schema, or result.

Only the fixed 271-family V2 training partition may enter V4. The 90-family V2
holdout is reverified for exclusion by the existing one-way gateway, then is
neither exposed to the model nor scored. The feature-safety-exposed
prospective validation source is not loaded. Its code is outside the V4 import
closure.

V4 adaptively reuses development families already examined by V3. Its
out-of-fold estimates are method-development evidence, not fresh confirmation.

## Truth-free target-batch profile

The primary inference mode is
`target_batch_partition_regime_local_document_leave_one_family_out`, shortened
below to target-batch LOFO.

For each outer-fold side and each degradation regime independently, the
complete unlabeled side is first treated as a fixed target batch. When
features for one family are produced, that family's complete contribution is
removed before any type statistic is calculated. Therefore:

- training and validation statistics never mix;
- clean and mild statistics never mix;
- no token, line, or family defines its own type profile;
- gold state is unavailable to profile code; and
- an opaque form fingerprint is only a transient equality/join key.

The same rule is intended for a future target script: a precommitted unlabeled
batch supplies the profile, and each predicted family is excluded from its own
statistics. Predictions are therefore batch-dependent and explicitly
transductive.

The public batch commitment hashes only a canonically relabeled equality and
damage structure. It is invariant to a bijective renaming of opaque form
fingerprints. Raw fingerprints, profile maps, feature rows, and family
membership do not cross the report boundary.

## Fixed feature surface

V4 keeps the ten low-cardinality V3 local features and drops the
high-cardinality equality-template digest:

1. position bucket;
2. line-length bucket;
3. reported direction;
4. damage;
5. observation status;
6. previous equality;
7. next equality;
8. within-line frequency bucket;
9. seen before; and
10. seen after.

For an observed type with leave-one-family-out support `m`, V4 adds:

- categorical support (`UNSEEN`, `1`, `2`, `3-4`, `5-8`, `9-16`, `17+`);
- log-normalized occurrence, family-dispersion, and line-dispersion values;
- support-aware family entropy;
- initial tendency, final tendency, mean normalized position, and four times
  positional variance, shrunk toward truth-free batch priors using
  `r = m / (m + 4)`;
- left and right excess context diversity and normalized context entropy,
  multiplied by `r_div = (m - 1) / (m + 3)` when `m > 1`;
- repeated-in-line, same-left, and same-right rates with the same shrinkage;
- left and right neighbor commonness, including fixed boundary, damage, and
  unseen categories;
- the two evidence values `r` and `r_div`; and
- four fixed local/profile interactions for initial tendency, final tendency,
  position agreement, and neighbor-equality/repetition agreement.

Except for declared categorical values, profile values are finite numbers in
the closed unit interval. There is no learned quantile, scaler, embedding,
sign vocabulary, or source-specific threshold. Damaged observations receive a
neutral type profile, while their clear neighbors may still supply
truth-free neighbor-commonness evidence.

## One fixed model

There is exactly one primary candidate and no inner model selection: an
L2-regularized first-order linear-chain conditional random field.

- regularization `rho = 0.01`;
- all-zero initialization;
- one emission bias and numeric/categorical feature weights per state;
- learned start and first-order transition weights;
- family-normalized conditional negative log-likelihood;
- fixed post-training emission adjustment `-0.5 * log(pi_state)`;
- Jeffreys-smoothed family-weighted class prior
  `(mass + 0.5) / (total_mass + 2.5)`; and
- deterministic state order for every tie.

The pure-Python optimizer is full-batch L-BFGS with history 10 and at most 100
accepted iterations. It uses a max-shifted forward-backward calculation,
two-loop recursion, and Armijo backtracking with initial step 1, `c1 = 1e-4`,
factor 0.5, at most 31 trials, and minimum step `2^-30`. A curvature pair is
accepted only when
`s dot y > 1e-12 * norm(s) * norm(y)`.

Convergence requires either gradient infinity norm at most `1e-5`, or five
consecutive accepted iterations with relative objective change at most
`1e-9` and gradient infinity norm at most `1e-3`. A non-finite value,
non-descent direction after one history reset, failed line search, or maximum
iteration without convergence invalidates the run. There is no optimizer
fallback.

## Paired outer development

V4 reuses the exact five deterministic V3 outer family assignments. No family
crosses a side, every required partition has positive support for all five
states, and no seed or replacement split is searched.

Primary clean and mild confusion matrices are aggregated with equal total
evaluation mass per family. Clean remains an integrity diagnostic. Mild
macro-F1 is the main development quantity. The V4 and immutable V3 mild
macro-F1 values are also compared fold by fold.

No candidate is selected from the following fixed diagnostics:

- the same CRF refitted with local features only;
- the primary CRF decoded with start and transition weights zeroed;
- an independently fitted multinomial logistic-emission model;
- the primary model evaluated with a self-inclusive target profile; and
- a strict single-family profile, whose leave-one-family-out support is empty.

Diagnostics cannot change the primary configuration or rescue a failed gate.

## Predeclared decision

An integrity violation or optimizer failure is a hard error and produces no
scientific result.

A valid run returns `advance` only if every condition passes:

- mild out-of-fold macro-F1 is at least `0.36432759235715436`;
- mild `settlement_name` recall is at least `0.15`;
- mild macro-F1 improves over V3 in at least four of five paired outer folds;
- the full-profile CRF exceeds the local-only CRF by at least `0.02` mild
  macro-F1;
- mild recall is at least `0.520654531441017` for `context_only`,
  `0.1765055025096581` for `quantity`, `0.3767836311289388` for `unit`, and
  `0.4988092152820551` for `person_name`;
- clean macro-F1 is at least `0.36`;
- clean `settlement_name` recall is at least `0.10`; and
- the self-inclusive minus leave-one-family-out mild macro-F1 difference is
  at most `0.05`.

Any other valid result is `development_killed`. A killed result prohibits a
full-development model fit and further reserved-source execution under this
protocol. An advance result permits only a final model fit over the same 271
development families. It still does not authorize a reserved-source run,
binding-confirmation claim, Indus reading, prize submission, or contact with
an institution.

## Freeze and execution order

1. Implement the independent V4 package, exact-byte plan verifier, closed
   schema, no-replace command, tests, and public documentation.
2. Verify V2 and V3 bytes remain unchanged.
3. Run lint, format, type, full tests, package-content, secret, static
   analysis, dependency, link, and public-boundary checks.
4. Publish the code-and-plan freeze.
5. Execute the fixed MTAAC V4 command once at that public implementation
   commit.
6. Validate and publish only the aggregate result in a separate commit.

All result-driven method changes belong to a separately named future
protocol.
