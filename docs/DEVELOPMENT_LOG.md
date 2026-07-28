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
