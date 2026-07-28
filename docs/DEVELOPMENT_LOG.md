# Public development log

This append-only log records public, reproducible project milestones. Machine
topology, accounts, authentication, private paths, private corpus facts, and
other operator-only details are intentionally excluded.

## 2026-07-29T00:54:12+09:00 — MTAAC V3 development boundary recorded

- V2 remains immutable. Its fixed result is `NO_GO`; V3 neither modifies nor
  reinterprets that result.
- The [V3 development plan](../benchmark/mtaac-v3-development-v1.json) admits
  only the fixed 271-family MTAAC V2 training partition. The 90-family V2
  holdout is verified for exclusion by the gateway and is not exposed to the
  model or scored.
- V3 is a five-state, source-neutral structural sequence baseline: weighted
  categorical naive-Bayes emissions, first-order transitions, and Viterbi
  decoding. `alpha = 1`; the fixed `gamma × lambda` grid is
  `{0, 0.5, 1} × {0, 0.5, 1}`.
- Selection is family-grouped nested `5 × 4` cross-validation using mild
  macro-F1 and the one-standard-error simplest-candidate rule. Clean is a
  guard/diagnostic only. A separate fixed four-fold grouped procedure selects
  the final development configuration over all 271 training families.
- Reports are aggregate only. No source identifier, raw annotation,
  family/fold membership, per-document result, local path, or private
  operational detail may be published.
- ORACC ED3b remains unloaded during V3 development. It is a
  feature-safety-exposed prospective validation source, not untouched or
  binding confirmation evidence.
- Binding confirmation requires a different previously uninspected corpus,
  chosen either under independent custody or by a post-freeze public random
  beacon from a predeclared eligible pool.
- At this timestamp, implementation is in progress and no V3 development,
  ORACC validation, binding-confirmation, Indus reading, translation,
  decipherment, or prize result exists.

The complete method boundary and execution order are documented in
[MTAAC V3 development protocol](MTAAC_V3_DEVELOPMENT.md).

## 2026-07-29T01:19:40+09:00 — MTAAC V3 development result recorded

- The exact code and plan were first published at implementation commit
  `5b39c8ba358ea66e46183cbf02eb07fbc91861e2`.
- The fixed MTAAC run then completed once using only 271 development families.
  The V2 holdout was not exposed to the model or scored, and the reserved
  prospective validation source was not loaded.
- All five outer selections and the final four-fold selection chose
  `gamma = 0.5, lambda = 0`.
- Mild out-of-fold macro-F1 is 0.3243; worst-state recall is 0.0369. The zero
  transition strength and weak rare-state recall reject local equality and
  position as a sufficient baseline.
- The 77,086-byte aggregate
  [result](../benchmark/results/mtaac-v3-development-v1.json) passed the closed
  schema, public-boundary scan, confusion-matrix recomputation, and
  one-standard-error selection recomputation.
- V3 is now immutable. V4 should test preregistered corpus-level,
  source-neutral distributional features before any reserved-source
  performance execution.

## 2026-07-29T02:34:17+09:00 — MTAAC V4 code-and-plan boundary recorded

- V2 and V3 remain byte-for-byte immutable. V4 is a separate
  development-only package, command, plan, schema, and result namespace.
- The exact 10,354-byte
  [V4 development plan](../benchmark/mtaac-v4-development-v1.json) has SHA-256
  `604725a5929b63f578ade07b65ca784eefefefce9b827e1686d4836f668c123b`.
- V4 uses only the reused 271-family MTAAC development partition. Its primary
  features are computed from a truth-free, partition/regime-local target batch
  after removing the current family; exact form identity remains a transient
  equality key and is neither a model feature nor a report field.
- One fixed L2-regularized linear-chain CRF is evaluated on the exact V3 outer
  assignments. Local-only, transition-zero, logistic-emission,
  self-inclusive, and strict-single-family variants are diagnostics only and
  cannot select or rescue the primary method.
- Advance and kill gates were fixed before real execution. A killed result
  prohibits final-development fitting and reserved-source execution under
  this protocol; an advance result still authorizes neither a reserved-source
  run nor an Indus or prize claim.
- Ruff, formatting, Pyright, and the full test suite passed at this checkpoint:
  569 tests passed and 13 environment-specific tests were skipped. Source and
  wheel builds contain the plan, schema, independent command, and V4 modules.
  The local Markdown-link check passed; Gitleaks, Semgrep, and Trivy reported
  no finding.
- Independent pre-freeze review aligned the Armijo contract to 31 trials so
  the declared `2^-30` minimum step is reachable. It also added runtime closed
  schema validation and recomputation of every confusion-derived metric,
  out-of-fold aggregate, paired delta, and gate decision before output.
- The V2 holdout and prospective validation source have not been loaded or
  scored for V4. No real V4 result exists at this checkpoint. The controlled
  next step is to publish this code-and-plan freeze and execute its exact
  MTAAC command once.

The exact feature, optimizer, diagnostic, and decision contracts are recorded
in the [MTAAC V4 development protocol](MTAAC_V4_DEVELOPMENT.md).

## 2026-07-29T03:11:52+09:00 — MTAAC V4 development result recorded

- The code-and-plan freeze was first published at implementation commit
  `304f8b36a32083330b8af02d21a58382c29d8915`.
- The fixed command then completed once. Every optimizer converged, and the
  164,563-byte aggregate
  [result](../benchmark/results/mtaac-v4-development-v1.json) has SHA-256
  `4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897`.
- The closed schema, recursive public boundary, every confusion-derived
  metric, every out-of-fold confusion sum, all five paired V3 deltas, and
  every decision gate were independently recomputed.
- Mild macro-F1 improved from V3's 0.3243 to 0.3878, all five paired fold
  deltas were positive, and the full profile exceeded the local-only
  diagnostic by 0.0608.
- Mild `unit` recall was 0.3052 against its 0.3768 floor, and mild
  `settlement_name` recall was 0.0429 against its 0.15 floor. Because all
  gates were mandatory, the terminal decision is `development_killed`.
- No final all-family model was fitted. The V2 holdout and prospective
  validation source remained unloaded and unscored; this protocol cannot
  execute that source.
- V4 is a material known-script method improvement, not a transferable or
  decipherment result. Any V5 must be separately frozen, be the final MTAAC
  development attempt, and include a stopping rule.
- Post-result publication checks passed: Ruff, formatting, Pyright, all 573
  tests with 13 environment-specific skips, source and wheel builds, local
  Markdown links, runtime/schema result validation, Gitleaks, Semgrep, Trivy,
  and a dedicated deployment-identifier scan.
