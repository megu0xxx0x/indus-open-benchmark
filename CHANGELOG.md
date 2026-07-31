# Changelog

All notable changes are documented here. The project follows semantic versioning for software and
immutable content-addressed identifiers for corpus and split releases.

## Unreleased

### Added

- A deterministic, non-operational KP1979 V3 control source-bundle builder at
  commit `2e81afef7e188f9dd70059c60b9f1123019b3753`. Its exact allowlist has
  36 payload files and produces a 37-member canonical source-only subject
  after adding `MANIFEST.json`. The closed manifest fixes all protocol,
  control, target-algorithm, and worker identities; 32 case, 16
  relation-endpoint, and 48 total invocations; `source_only=true`;
  `non_operational=true`; `target_round_selected=false`; and absent detector
  and integration components. A bounded verifier requires compact canonical
  ASCII JSON, canonical regular-file-only USTAR, project-owned
  stored-DEFLATE gzip, exact roster, byte sizes and SHA-256 values, and exact
  byte reconstruction.
  Source reads are descriptor-relative and namespace-revalidated. Output uses
  a private parent, owner-only staging, sync, no-replace hard-link publication,
  and inode-and-byte verification. On failure, cleanup rechecks that the output
  name identifies the builder-owned inode and otherwise preserves an unknown
  entry; that check is best effort and not atomic against same-UID or root
  replacement. These controls cannot prove
  authenticity, custody, trusted time, or the absence of every race. The
  supplied `source_commit` requires external authentication; it is not a Git
  attestation.
  The complete 63-test focused suite passed under exact CPython 3.12.11 in
  2.017s, and all 1,047 repository tests completed in 1002.306s with 19
  environment-specific skips. Ruff lint, Ruff format over 181 files, Pyright
  with zero findings, sdist and wheel builds, Gitleaks, and public-boundary
  checks passed. Two independent source audits each reported zero blockers,
  zero major findings, and zero minor findings.
  Public CI run `30615528575` succeeded in 16m23s at exact source commit
  `2e81afef7e188f9dd70059c60b9f1123019b3753`:
  - Python 3.11 passed Quicknet 6/6 in 520.428152ms and all 1,047 tests with
    22 environment-specific skips in 848.443s; its job completed in 14m35s;
  - Python 3.13 passed Quicknet 6/6 in 537.327487ms and all 1,047 tests with
    22 environment-specific skips in 943.488s; its job completed in 16m13s;
    and
  - Python 3.14 passed Quicknet 6/6 in 410.523122ms and all 1,047 tests with
    22 environment-specific skips in 675.542s; its job completed in 11m48s.
  Every matrix job passed Ruff, accepted all 181 checked files as formatted,
  reported zero Pyright errors, warnings, or information messages, and built
  both the sdist and wheel.
  Exact CPython 3.12.11 is installed locally, but no real control bundle,
  freeze artifact, or subject digest was generated or retained. The evaluator
  still accepts an injected
  invoker and remains a non-attestation. Same-UID/root race and custody
  limitations, Quicknet repeated-interrupt cleanup, sandbox
  `BaseException` cleanup, and the supported host-runtime policy remain open.
  Node 18.19.1 remains end-of-life and qualification-only.
  No freeze was dispatched; no target or real-run seed, schedule, truth,
  worker execution, detector, integration, official runner, real-source
  access or result, decipherment evidence, or prize claim exists. KP1979 V2
  remains retired and immutable.
- Quicknet interruption cleanup hardened at commit
  `eda8af5791ed3ad6073d80308fa0696434ab89b6`. A `BaseException` from the
  initial verifier `communicate` now starts bounded best-effort cleanup:
  process-group termination attempts, bounded `communicate`, bounded `wait`,
  and a bare re-raise preserving the original exception object. After an
  timeout, `OSError`, or `SubprocessError`, the first cleanup
  `BaseException` from kill, `communicate`, or `wait` is retained; every
  bounded cleanup stage still runs; an interrupted first kill is retried; an
  interrupted wait is retried once boundedly; and the exact first cleanup
  exception object is then re-raised. Ordinary public Quicknet failures remain
  path-free and detail-free.
  Cleanup is bounded best effort and does not claim guaranteed termination
  under repeated hostile interrupts. Local evidence passed all 9 focused
  interruption tests, including a 27-case ordinary-primary × cleanup-location
  × `BaseException`-wrapper matrix, and all 23 Quicknet tests. The
  real-process regression specifically interrupts the first kill and verifies
  the second kill/reap path; not every matrix combination is represented as a
  real-process test. All 984 repository tests completed with 19
  environment-specific skips in 976.360s. Ruff, formatting, Pyright,
  Gitleaks, and an exact two-file source/test scope check passed; independent
  audit reported zero blockers, zero major findings, and zero minor findings.
  Public CI run `30608426512` succeeded in 16m27s:
  - Python 3.11 passed Quicknet 6/6 in 448.623633ms and all 984 tests with 22
    environment-specific skips in 640.818s; its job completed in 11m11s;
  - Python 3.13 passed Quicknet 6/6 in 527.92177ms and all 984 tests with 22
    environment-specific skips in 950.240s; its job completed in 16m17s; and
  - Python 3.14 passed Quicknet 6/6 in 546.222152ms and all 984 tests with 22
    environment-specific skips in 925.641s; its job completed in 16m05s.
  Every matrix job passed Ruff, checked all 179 files as formatted, reported
  zero Pyright errors, warnings, or information messages, and built both the
  sdist and wheel. Portable semantic CI remains exact Node 24.18.0. The fixed
  Node 18.19.1 host wrapper remains end-of-life and qualification-only; the
  supported runtime policy is unresolved before an official runner. At that
  checkpoint no official C3 runner, controller, or freeze builder existed; no
  freeze had been dispatched; and no target round, detector, real-source
  access or result, decipherment evidence, or prize result existed. The
  evaluator's injected-invoker result remained a non-attestation. KP1979 V2
  remained immutable. Next was a non-operational, source-only control-bundle
  builder and supported runtime policy, with no target selection.
- A streaming, aggregate-only KP1979 V3 evaluator at commit
  `ee847035867fe92dbca8b3e0aa9422dcfd43f138`. It builds and
  same-seed-validates one canonical case or relation at a time and passes only
  `request_bytes` to the supplied invoker for all 48 sequential worker calls.
  Positive cases require exact 96-pixel predictions and
  zero-false-positive/zero-false-negative same-lane matching; negative cases
  require `abstained`; out-of-contract cases require the expected `rejected`
  code; and all eight fixed metamorphic relations are checked exactly.
  Scientific gate failures still complete all 48 calls and return
  `not_qualified`. Technical faults collapse to `execution_failed` with no
  detail, counts, or authorization, while `BaseException` propagates for a
  future one-shot runner to record `consumed_incomplete`. The closed
  ten-field aggregate permits only owner-only provisional candidates on
  pages 22–77 after a complete pass; page 78 authorization and every public
  claim permission remain false. The component API accepts an injected
  invoker, so its result alone is not an execution attestation. An official
  runner is not implemented. Any authoritative future use must internally
  construct and own an exact `SandboxedWorkerInvoker` and must expose no
  caller-injection path.
  Two independent read-only source audits reported zero blockers, zero major
  findings, and zero minor findings. Local source evidence passed all 28
  focused evaluator tests, all 975 repository tests with 19
  environment-specific skips, Ruff lint and format checks, Pyright, source
  and wheel builds, Gitleaks, and public-boundary checks. Public CI run
  `30604750422` succeeded in 16m32s: Python 3.11, 3.13, and 3.14 respectively
  passed Quicknet 6/6 in 528.547056ms, 728.88314ms, and 608.578832ms, then all
  975 tests with 22 environment-specific skips in 843.345s, 957.050s, and
  906.624s. Every matrix job passed Ruff, checked all 179 files with Ruff
  format, reported zero Pyright errors, warnings, or information messages, and
  built both the sdist and wheel.
  No C3 controller or freeze builder has been implemented; no freeze has been
  dispatched; and no C3 run, target selection, detector, real-source access or
  result, decipherment evidence, or prize result exists. KP1979 V2 remains
  immutable. At that checkpoint, next was a non-operational C3
  controller/freeze-builder boundary plus Quicknet interruption cleanup; no
  target round had been selected.
- A synthetic-only deterministic KP1979 V3 generator checkpoint at commit
  `88794f9748e909eef66f54c4c56d82fee5e9e521`, with 12 positive, 14 negative,
  and six out-of-contract cases plus eight fixed two-endpoint metamorphic
  relations, yielding exactly 48 worker invocations. Authoritative validation
  requires the supplied suite seed and rejects any controller-side case or
  relation that differs from exact canonical regeneration. Only
  `request_bytes` satisfying the exact five-field answer-free wire contract
  may reach a worker. At that generator-only checkpoint,
  instantiated suite seeds, generated objects, full construction and truth
  metadata, generation commitments, and schedule metadata must not be
  persisted or published before execution or passed to a worker. Independent
  read-only source QA reported zero blockers, zero major findings, and zero
  minor findings. Public CI run `30599459365`
  passed all 947 tests with 22 environment-specific skips on Python 3.11,
  3.13, and 3.14 and built both distributions in every job. This checkpoint
  contained no evaluator, C3 freeze or run, target Quicknet round, detector,
  real-source access or result, decipherment evidence, or prize evidence.
  KP1979 V2 remains immutable.
- A frozen public KP1979 V2 label-lattice qualification protocol, closed
  execution plan, one-shot runner, closed result contract, and
  [single published diagnostic result](benchmark/results/kp1979-label-lattice-v2-result-v1.json).
  The raw control is `not_qualified`: 18 of 19 cases passed, with an abstention
  on `positive_bounded_jitter_with_gaps` yielding zero precision and recall
  against 68 synthetic references. All three metamorphic checks passed. The
  run started 25 child processes for 25 adapter invocations, accepted 21
  responses, properly rejected four out-of-contract inputs, and recorded no
  transport failure. Overall status remains `not_qualified` and advance false
  independently because the detector froze before the control and a
  post-freeze periodic two-tier non-label confound blocks deployment. Git
  proves bytes and ancestry only; blindness, confidentiality, independence,
  cross-access absence, custody, trusted time, and technical single-execution
  enforcement are not claimed. The synthetic run opened no real or
  future-evaluation source, PDF page 78, MTAAC holdout, ORACC prospective
  material, or reserved source. V2 is retired; the next experiment is a
  control-first V3 successor.
- A separately frozen, development-only MTAAC V4 protocol that leaves V2 and
  V3 immutable and reuses only the 271-family development partition. Its
  truth-free target-batch profile is train/validation and clean/mild isolated,
  removes the current family before deriving type statistics, drops the V3
  high-cardinality line template, and exposes only source-neutral categorical
  markers and unit-interval frequency, dispersion, position, context,
  neighbor, and interaction values. One fixed L2-regularized linear-chain CRF
  is fitted with a dependency-free deterministic L-BFGS optimizer; there is
  no candidate grid or inner selection. Local-only, transition-zero,
  logistic-emission, self-inclusive, and single-family variants are
  nonselecting diagnostics. The exact V3 outer assignments and predeclared
  rare-state, paired-delta, profile-increment, and self-information gates
  determine `advance` or `development_killed`. The V2 holdout and reserved
  prospective source remain unavailable, and reports are aggregate only.
- The aggregate MTAAC V4 development execution. Mild macro-F1 improved from
  V3's 0.3243 to 0.3878, all five paired outer-fold deltas were positive, and
  the full profile exceeded the local-only diagnostic by 0.0608. The fixed
  method nevertheless returned `development_killed`: mild `unit` recall
  0.3052 missed its 0.3768 floor and `settlement_name` recall 0.0429 missed
  its 0.15 floor. Every optimizer converged, the closed schema and complete
  metric/gate recomputation passed, no final model was fitted, and the V2
  holdout and prospective validation source remained unused.
- A separately frozen, final MTAAC V5 development protocol. V5 adds no model
  parameters, features, folds, diagnostics, or candidate search; it preserves
  the V4 likelihood and doubles only the fixed within-pair emission contrast
  penalty for `quantity`/`unit` and `person_name`/`settlement_name`. Exact
  recall, precision, clean, paired-fold, one-shot, and stopping gates are
  closed before execution. Its separately published result passed 7 of 15
  gates and returned `mtaac_retired`: mild macro-F1 and `unit` recall
  decreased from V4, the settlement recall gain remained far below its floor,
  and no final model was fitted. MTAAC is now retired.
- A separate, development-only MTAAC V3 plan and implementation boundary that
  leaves V2 immutable, exposes only the fixed 271-family V2 training
  partition, and excludes and does not score the 90-family V2 holdout. It
  predicts five states for every retained token using a fixed source-neutral
  structural feature surface, weighted categorical naive-Bayes emissions,
  first-order transitions, Viterbi decoding, and a nine-candidate
  `gamma × lambda` grid. Selection is family-grouped nested `5 × 4`
  cross-validation on mild data with clean diagnostics and a separate fixed
  four-fold final-development selection. Reports are aggregate only. ORACC
  remains unloaded and is feature-safety-exposed prospective validation, not
  binding confirmation; no V3 result, Indus reading, translation,
  decipherment, or prize result is claimed.
- The aggregate MTAAC V3 development execution. All five outer folds and the
  final four-fold procedure selected `gamma = 0.5, lambda = 0`; mild
  out-of-fold macro-F1 is 0.3243 and worst-state recall is 0.0369. The closed
  result demonstrates that local equality and positional structure are an
  insufficient baseline and does not use the V2 holdout or reserved
  prospective validation source.
- A pre-model-fitting source seal and network-free verifier for the exact CC0
  ORACC ePSD2 Early Dynastic IIIb administrative JSON archive. It applies a
  fixed audit-example exclusion, commits the selected corpus and mechanical
  five-state projection, rejects unsafe archives and ambiguous labels, emits
  only an aggregate source receipt, and disables validation execution until a
  separate post-development protocol is frozen. Gold-conditioned GDL-key
  safety aggregates informed its annotation-stripping sanitizer, so this is a
  feature-safety-exposed prospective validation source rather than untouched
  or binding confirmation evidence. Its separately published aggregate
  source-qualification receipt binds the public source-freeze commit and
  reports no model execution or performance metric.
- An exact-byte-pinned, network-free adapter and pre-result-frozen V2 protocol
  for the CC0 MTAAC known-script control, with whole-document quarantine,
  evaluation-equivalence anti-laundering, gold-independent event/null
  identities, gold/model separation, source-document family splits,
  cumulative degradation, family-weighted categorical baselines, and a fixed
  999-run label-vector permutation reference. It is a method instrument, not
  Indus evidence.
- A closed Penn metadata-only context-anchor registry, exact-CSV
  revalidation CLI, 34-entry real-source derivation check, replica/modern
  negative controls, and a dated Mackay/Penn Chanhu-Daro primary-source
  crosswalk that preserves unresolved field-number and locus conflicts.
- A project-authored CC0 synthetic functional-class identifiability gate with
  family-safe degradation, equal family weighting, conservative
  family-permutation nulls, anchor-free abstention, and explicit
  no-decipherment scope.
- Closed sign-inventory and unsealed visual-transcription review/adjudication
  schemas, exact-byte evidence verification, double-independent-review
  comparison, and one non-overwriting private promotion receipt.
- A fixed Helsinki 1982 pages 20–21 sign-list Batch 0 protocol that preserves
  repeated catalog rank separately from the lower primary source identifier.
  No Batch 0 transcription or adjudication is claimed.
- A closed KP1982 source contract and network-free verifier for the exact
  official PDF plus canonical page-20/page-21 PBM pixels. Two independent
  decoders produced pixel-identical source pages.
- A fixed-seed, deterministic KP1982 layout proposal generator that commits
  all 700 cell and padded-context crops to the verified page pixels and writes
  only a private no-replace `0600` manifest, plus a semantic verifier that
  rebuilds the complete proposal instead of trusting its assurance fields.
  The canonical V1 manifest bytes are pinned against implementation drift.
  Cell crops are locator-only; geometry, occupancy, identifiers, and human
  transcription remain unaccepted.
- A closed KP1982 bootstrap-assignment contract plus deterministic preparation
  and exact-byte verification for all 700 proposal cells. Reviewer assignments
  retain only proposed locator/context rectangles and crop commitments;
  machine occupancy, OCR, identifier, and accepted-observation values are
  structurally excluded. Human double review and adjudication remain pending.
- A closed, non-circular KP1982 bootstrap-review/adjudication contract and
  reviewer-safe CLI verification path that does not receive the layout
  proposal. Exact verification binds the assignment and canonical PBMs,
  rehashes submitted crops, audits exactly two independent records into a
  private no-replace report, and prevents adjudicator invention. No human
  review, independence, rights, decipherment, or prize eligibility is claimed.
- A dated decipherment-efficiency audit that moves the critical path from
  serial full-700 review to parallel stratified calibration,
  source-bound/abstaining concordance proposals, corpus federation, functional
  anchors, and equal-budget hypothesis tournaments. The full Batch 0 contract
  remains available as a high-assurance path and no extraction or reading is
  claimed. The plan separately requires a concordance-row reference and a
  genuinely label-withheld evaluation; sign-list cells alone cannot establish
  end-to-end accuracy.
- A follow-up Helsinki corpus fast-path audit and implementation that moves
  the first corpus lane to the official 1979 identifier-order pages, followed
  by its two sorted internal reprints, the official 1980
  revision/cross-reference/duplicate delta, and only then the 1982 occurrence
  concordance. The exact 1979 PDF and all 179 native page pixels are pinned.
  A streaming pixel-only detector proposes label-lattice slots on every normal
  two-column page while
  abstaining on dense prose, both ten-column sign-list pages, and the
  eight-/six-column auxiliary grids. A predeclared mask, not the detector,
  removes terminal-page prose intersections. It does not segment full rows and
  accepts no label slot, row, identifier, sign, reading, or decipherment value.
- Proposal-free KP1979 label-reference assignments that keep the fixed
  development and future-evaluation six-page partitions separate, disclose no
  detector geometry or expected page class, and bind only the exact source
  bytes, page pixels, and coordinate rules. A closed geometry-only review
  contract and verifier recompute submitted crops while retaining explicit
  nonclaims for human authorship, real independence, evaluation admissibility,
  decipherment, and prize eligibility.
- A separate exposed KP1979 machine-development geometry projection and
  exact-byte verifier. It is restricted to provisional development extraction,
  preserves unresolved observations, records machine authorship and prior
  detector/OCR/page-role/scoring exposure, cannot serve as human reference
  evidence or detector-scoring input, and leaves future-evaluation values
  unopened. Two genuinely separate human passes remain a later
  external-reference promotion gate rather than a prerequisite for provisional
  machine-assisted research. The projection follows continuous target-side ink
  beyond its fixed scan band to a bounded terminus, marks detached exterior
  runs, sign-side continuation, and vertically clipped associations unresolved,
  and requires substantial two-tier row-projection evidence without treating an
  internal horizontal gap alone as a failure.
- The KP1979 label-reference review contract is now v0.2.0 so the new machine
  stage has a distinct reproducible schema version. No v0.1 manual review
  values existed or were migrated.
- A bounded source-independent KP1979 label-position scorer and deterministic
  known-truth synthetic control. The low-level arithmetic is internal; the
  supported evaluator requires a canonical generator-equal synthetic fixture,
  rejects machine-development and external-reference-candidate uses, and fixes
  every external-eligibility and decipherment claim false. The retrospective
  V1 control is retained as `not_qualified` after thin-stroke and periodic
  non-label counterexamples; no real or reserved source is read.
- Private museum bundle format 0.2 with exact official policy/API evidence
  snapshots and reproducible, fail-closed verification.
- Optional external manifest-anchor verification, explicitly separated from
  internal self-consistency.
- Draft 2020-12 catalog-blind museum-review subject and append-only
  review/adjudication contracts, semantic gates, and a synthetic fixture.
- Atomic `prepare-museum-review` generation with opaque IDs, exact evidence
  copies, isolated custody mapping, two-review adjudication policy, and a
  synthetic integration fixture. Executed private packet details are excluded
  from the public changelog.
- Closed `verify-museum-review` rehashing for packet inventories, manifests,
  evidence, blind/custody mappings, permissions, and identity-leak checks.
- A dated 11-institution museum rights/API audit and machine-readable
  candidate ledger.
- A dated primary-source audit separating the authentic Tamil Nadu
  US$1-million announcement from the still-unverified operational submission
  scheme.
- Closed, network-free Penn CSV and raw-byte-bound Smithsonian AWS JSONL
  metadata parsers, schemas, CLI commands, and source-audit documentation.
- Atomic digest-named human-review ledger sealing, complete-chain
  adjudication checks, idempotent retries, and explicit unresolved
  roster/checkpoint/chronology assurance flags.
- A dated global open-source audit with pinned repository revisions, six new
  evidence-ledger entries, current-release deltas, and explicit quarantine
  decisions for unlicensed, leakage-prone, synthetic, or hypothesis-labelled
  material.
- A content-addressed quarantine manifest/schema and machine-enforced gate
  across validation, import, split, audit, baseline, controls, null evaluation,
  treewidth, and corpus-manifest paths.
- Split manifest v0.2 with exact input/partition/audit commitments and an
  unavoidable public-development assurance block; generation now writes
  `development.jsonl` rather than implying a blind `test.jsonl`.
- A closed evaluator configuration and benchmark-definition lock that binds
  exact corpus, schema, registry, split, evaluator, `pyproject.toml`, and
  `uv.lock` bytes while explicitly forbidding blind, final, externally
  anchored, OCI-runtime, or complete evaluator-closure claims.
- A closed submission-commitment schema and deterministic build/verify CLI
  binding a caller-declared digest of a separately verified benchmark
  definition, the complete inventory below a selected root, empty directories,
  executable state, entrypoint, static arguments, and explicit source,
  configuration, model-weight, dependency, and runtime-input roles.
- Closed private-corpus policy and aggregate-readiness schemas plus a
  network-free `audit-private-readiness` command. It uses exact per-file
  coverage, source/quarantine checks, fixed local intended uses, and a
  count-free terminal summary.
- Private policy and readiness contracts v0.2, a closed
  structural-quarantine ledger and atomic review bundle, and
  `prepare-private-review`. Generated entries are exact-byte-bound, deny-all,
  and pending curator review; structural findings copy no source value and
  never override readiness.

### Fixed

- Preserve the aborted MTAAC V1 invocation and its path-free error as an
  immutable erratum, then supersede it with V2. V2 replaces an
  order-dependent binary-float integrity comparison with exact rational
  family-mass and complete-vector checks, validates both 999-run schedules
  before any metric, reuses those exact assignments, and uses `math.fsum`
  bucket accumulation so deterministic replicas cannot change a model,
  baseline, or confusion matrix through addition order. Source, split,
  degradation, seeds, model design, support gates, and thresholds are
  unchanged.

### Security

- Harden KP1979 V3 sandbox cleanup at source commit
  `cd583fb12b12a80d132c80e8a3465e53f5c3151a`. Its timeout,
  negative-status, and other abnormal client-lifecycle
  paths use an explicit bounded sequence: (A) unit-wide kill dispatch,
  (B) client-process-group `SIGKILL`,
  (C) conditional unit-kill retry, (D) bounded `communicate`, and
  (E) bounded `wait` with one retry. Cleanup stages continue after earlier
  ordinary failures or interrupts. Timeout output sizes are read only after
  the main client is reaped and at least one unit-kill helper returns zero;
  helper status zero acknowledges command dispatch and is not proof that the
  cgroup is empty or that isolation, custody, or execution was attested.
  Negative client return codes now take the same cleanup path before output or
  handshake reads.
  A primary non-`Exception` `BaseException` retains exact object identity. If
  the primary is ordinary, the first cleanup non-`Exception` `BaseException`
  is retained by identity while all bounded stages continue. Parent artifact,
  handshake, and output reads add `O_NONBLOCK` where available, bounded owner-safe reads,
  descriptor closure, and mutation checks; exclusive-write and temporary-
  directory cleanup apply the same primary/cleanup exception precedence.
  The public invoker API, result fields, dispositions, and failure codes remain
  unchanged. The started counter increments only after the main client handle
  is returned, never for kill helpers; the verified counter increments only
  after a canonical handshake.
  This is bounded best effort, not guaranteed termination under repeated
  hostile interrupts or privileged interference. A zero unit-kill helper exit
  cannot establish service teardown. The finite attempts and explicit
  `communicate`/`wait` timeouts are not a hard real-time bound on `Popen`
  process creation or kernel/filesystem calls. The tests use controlled
  process doubles plus one inert local sleep-process-group kill/reap regression;
  they invoke no real systemd service or project worker.
  The normal and exact CPython 3.12.11 focused suites each passed 47 tests with
  six environment-specific skips, in 1.644s and 1.645s respectively. The
  evaluator/worker-wire suites passed 51 tests with no skips in 27.230s. Two
  independent code audits of exact diff SHA-256
  `7069fbae6e9749c401f00ef35b5e5cc8c74d0e262f00626c95d4a7192d71115d`
  each reported zero blockers, zero major findings, and zero minor findings.
  An initial full run reached 1,078 tests with 19 skips and recorded
  four Quicknet failure/error outcomes (two failures and two errors). All four
  outcomes were fail-closed mode prechecks because inherited umask left
  vendored Noble files
  at `0664` and directories at `0775` in the isolated worktree. Bytes, hashes,
  and the source diff were unchanged. Worktree-only `chmod go-w` restored
  `0644`/`0755`; this first attempt remains a failed historical validation
  event.
  After normalization, all 23 Quicknet tests passed. The clean full rerun
  passed all 1,078 tests with 19 environment-specific skips in 1213.871s,
  with a 1214.88s external wall duration. Ruff lint passed, Ruff format
  accepted all 181 checked files, and Pyright reported zero errors, warnings,
  or information messages. Distribution checks passed for a 337-member sdist
  and 163-member wheel, including path, private-material, and source-hash
  assertions. Gitleaks scanned 65 commits and approximately 7.15 MB with no
  leaks, and the public-boundary check passed.
  Close the public-CI gate with
  [run 30623782622](/megu0xxx0x/indus-open-benchmark/actions/runs/30623782622),
  event `push`, exact head SHA
  `cd583fb12b12a80d132c80e8a3465e53f5c3151a`, status `completed`, and
  conclusion `success`; all three matrix jobs are green. The overall run was
  `2026-07-31`, `10:30:29Z`–`10:46:17Z` (15m48s). Quicknet asserted
  Node `v24.18.1` on Linux/x64 and reported failed/cancelled/skipped/todo all
  zero in each matrix job. Python 3.11 ran
  `10:30:33Z`–`10:44:34Z` (14m01s): Quicknet 6/6 at
  `duration_ms=615.588048`, then unittest 1078 tests with 22 skipped in
  808.435s. Python 3.13 ran `10:30:32Z`–`10:39:02Z` (8m30s): Quicknet 6/6 at
  `duration_ms=292.030965`, then unittest 1078 tests with 22 skipped in
  483.182s. Python 3.14 ran `10:30:32Z`–`10:46:16Z` (15m44s): Quicknet 6/6 at
  `duration_ms=565.70517`, then unittest 1078 tests with 22 skipped in
  906.229s. Ruff lint, Ruff format with 181 files already formatted, Pyright
  with zero errors, warnings, or information messages, and sdist plus wheel
  builds passed in every job. The public-CI count of 22 skipped tests per job
  is separate from the clean local run's 19 skips and does not replace it.
  The diff fingerprint is not a signature, custody record, or attestation.
  No project or deployment runtime was installed or changed, no real systemd
  unit or project worker ran, no
  control bundle or freeze was built or dispatched, no target was selected or
  fetched, and no protected or real data was opened. No detector, official
  runner, C3 result, decipherment evidence, public claim authorization, or
  prize result exists. KP1979 V2 remains retired and immutable.
- Pin portable Quicknet semantic CI at commit
  `0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec` to exact Node 24.18.1 and
  `actions/setup-node` v7.0.0 full commit SHA
  `820762786026740c76f36085b0efc47a31fe5020`. The workflow explicitly
  requests x64, disables package-manager caching, and asserts exact version,
  Linux platform, and x64 architecture before running the six-test portable
  BLS suite. Its contract test fixes each setup field and assertion exactly
  once, fixes the runtime assertion/command order, and keeps the host test
  outside the portable workflow.
  Earlier public evidence under exact Node 24.18.0 and full-SHA-pinned
  `actions/setup-node` v6.5.0 remains historical and unchanged; it is not
  rewritten as evidence for the new pin.
  This update configures deterministic public-input cryptographic semantic
  checks in ephemeral Linux/x64 CI only. It does not attest a project or
  deployment runtime, launcher, dynamic `libnode`, OpenSSL, glibc, kernel,
  custody, sandbox path, or worker execution. The fixed Node 18.19.1 host
  wrapper is unchanged, end-of-life, and qualification-only.
  A supported host-runtime policy and complete dynamic closure remain
  unresolved.
  Public CI run `30617537380` succeeded in 16m24s at exact source commit
  `0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`:
  - Python 3.11 passed Quicknet 6/6 in 535.647147ms and all 1,047 tests with
    22 environment-specific skips in 856.889s; its job completed in 14m50s;
  - Python 3.13 passed Quicknet 6/6 in 525.265295ms and all 1,047 tests with
    22 environment-specific skips in 944.686s; its job completed in 16m20s;
    and
  - Python 3.14 passed Quicknet 6/6 in 527.783322ms and all 1,047 tests with
    22 environment-specific skips in 895.407s; its job completed in 15m28s.
  Every job used the full-SHA-pinned setup action, provisioned exact Node
  24.18.1 on Linux/x64, passed the exact version/platform/architecture
  assertions, passed Ruff, accepted all 181 checked files as formatted,
  reported zero Pyright errors, warnings, or information messages, and built
  both the sdist and wheel.
  No project or deployment runtime was installed or changed. No freeze,
  target selection or fetch, protected-data access, worker or detector
  execution, decipherment result, or prize result occurred.
- Recognize only Penn's exact generic-object-URL terminal CSV sentinel after
  complete records; continue rejecting every other malformed-width,
  padded, nonterminal, or post-sentinel row.
- Keep detailed transcription agreement reports and promoted artifacts in new
  `0600` files below pre-existing physical owner-only `0700` parents, while
  emitting a fixed count-free terminal summary. Public export and evaluation
  admission are disabled.
- Rebuild the canonical KP1982 layout proposal before preparing or verifying a
  bootstrap assignment, recursively reject machine-answer keys, and keep
  geometry acceptance, human review, reviewer independence/blinding, public
  release, evaluation admission, and decipherment assurances false.
- Strictly decode and schema-check exact inventory, review, and adjudication
  bytes; reject duplicate keys, non-finite values, inconsistent commitments,
  incomplete token coverage, unsafe geometry, and replacement of an existing
  promotion receipt.
- Rebuild provider records from duplicate-key-free raw API bytes during
  verification instead of trusting the staged rights fields.
- Reject redirects, unknown hosts, malformed image signatures, unsafe paths,
  symbolic and hard links, non-regular files, unexpected directories, and
  configured count/depth/byte-limit violations.
- Bind manifest parsing and hashing to one safe read, fingerprint files and
  directories before and after verification, and publish completed bundles
  with atomic no-replace directory renames.
- Reject review output overlapping the source, existing/dangling destinations,
  missing media, evidence copy hash/byte drift, hard/symbolic links, forbidden
  interpretation fields, and catalog identity leakage into reviewer text.
- Reject extended ACLs and unsupported atomic-publication platforms for
  private packets/ledgers; require directory durability operations instead of
  silently accepting unsupported `fsync`.
- Recompute Smithsonian container, line, record, classification, metadata
  rights, and per-media rights from strict raw JSONL bytes, while rejecting
  duplicate keys, credentials, unapproved media endpoints, and resource-limit
  violations.
- Bind Smithsonian acquisition headers into the intake identifier, scan
  rights-like fields across EDAN scopes, reject ambiguous media identifiers,
  and report committed-but-not-durable output states without encouraging an
  unsafe retry.
- Reject duplicate JSON keys, `NaN`, infinities, overflow-to-infinity numbers,
  unknown or spoofed sources, quarantine self-hash drift, remote schema
  references in definition locks, input symlinks/hardlinks, concurrent file
  mutation, coordinated split/member drift, and claim escalation after local
  digest recomputation.
- Traverse submission trees through pinned directory descriptors and
  no-follow/nonblocking `openat`, with two complete inventories, streaming
  hashes, fixed resource limits, a portable ASCII path profile, collision and
  inode checks, special-file/cross-device rejection, no-replace output, and
  code-generated non-blind assurance fields.
- Parse commitment JSON with fixed byte/depth/node limits while rejecting
  invalid UTF-8, duplicate keys, floats, non-finite values, symlinks, and hard
  links.
- Publish with POSIX mode bits `0600`, pinned-parent/inode/requested-path
  checks, descriptor ACL rejection, directory `fsync`, exact-byte postchecks,
  and explicit point-in-time/non-atomic semantics. A post-link failure reports
  the possibly present output instead of implying a safe automatic retry.
- Traverse a physical private corpus twice through pinned, no-follow
  descriptors; reject symlinks, hardlinks, special/cross-device entries,
  non-owner-only modes, extended ACLs, Unicode/casefold collisions, mutations,
  and fixed resource-limit violations. Ephemeral keyed path/content tokens are
  never serialized.
- Bind every reviewed private policy decision to a private SHA-256 commitment
  and independently block pending review or same-path byte replacement. Keep
  paths and digests out of terminal and aggregate outputs.
- Publish policy and structural findings as one descriptor-pinned `0600`
  private JSON file using exact-byte verification, atomic no-replace linking,
  requested-path/inode rechecks, ACL rejection, and explicit uncertain-commit
  states. Existing files, links, directories, and special entries are never
  replaced.
- Parse CSV with strict UTF-8 and CSV syntax, pre-materialization logical-record
  and column limits, bounded streaming rows, one-based logical ordinals, and
  fixed anomaly codes while discarding source rows, headers, cells,
  source/catalog identifiers, and exception text.
- Preflight JSON/JSONL syntax, numeric-token length, node count, and depth
  before object materialization; iterate line boundaries in linear space/time;
  and reject incomplete resource-limited analysis instead of publishing a
  partial private review ledger.

### Scientific limitations

- KP1979 V2 did not qualify or advance. Its raw synthetic control passed 18 of
  19 cases but remained `not_qualified`; separately, the detector-before-
  control freeze and post-freeze periodic two-tier non-label confound force the
  same overall decision. The report is diagnostic only. V2 establishes no
  accepted reference, real accuracy, row or transcription validity, reading
  direction, language, meaning, translation, decipherment, prize eligibility,
  or prize submission.
- The single frozen MTAAC V2 run returned `NO_GO`. Clean passed every gate,
  but mild `settlement_name` recall was 0.193553 against the frozen minimum
  0.35. The unchanged method is blocked from Indus transfer. This is a
  known-script method-control failure, not evidence for or against an Indus
  reading, language, translation, decipherment, or prize claim.
- Transcription bridge v0.1 records are unsealed private drafts. Left-to-right
  indexing describes image coordinates only; reading direction and signs may
  remain unknown. Source-document, crop, and source-image bytes are not
  independently rehashed by promotion, and rights, real-world reviewer
  independence, blind evaluation, translation, and decipherment are not
  established.
- KP1982 bootstrap assignments are preparation artifacts, not completed
  reviews. Proposed rectangles and crop commitments are not accepted geometry;
  no human double review, adjudication, sign inventory, decipherment, or prize
  result is established.
- A local `S` creates no trusted-time, authorship, confidentiality, custody,
  hidden-access, blindness, runtime-execution, result, or decipherment
  evidence. It is deterministic and linkable, and it does not prove complete
  runtime/dependency closure or permission to publish the committed metadata.
- Private readiness is only a point-in-time declaration-compatibility check
  for local non-public work. Its rights-ownership, provenance-authenticity,
  confidentiality, custody, trusted-time, blind/final, decipherment, and prize
  assurances always remain false.

## 0.1.0 — 2026-07-26

### Added

- Six Draft 2020-12 contracts for sources, artifacts, hypotheses, research evidence, museum
  intake, and split manifests.
- Observation/hypothesis separation and namespaced lossless extensions.
- Rights-aware source registry covering mayig, CISI, Mahadevan/RMRL, ICIT, and blocked mixed data.
- Deterministic mayig importer that vendors no upstream corpus files or images.
- Domain and optional full-schema validation.
- Connected-component splits across duplicate families, catalog aliases, image hashes, and exact
  normalized sequences.
- Cross-partition leakage audit.
- Unigram and add-one n-gram held-out and missing-sign baselines.
- Frequency- and sequence-length-preserving shuffled control.
- Repeated matched-shuffle null distributions with empirical one-sided p-values.
- Machine-readable global evidence ledger covering major corpora, claims, critiques, active
  projects, prize status, rights, falsification criteria, and scheduled review.
- Explicit cross-edition artifact/sign crosswalk and recurring research-intelligence protocols.
- Item-reviewed Met and Cleveland Museum open-access pilot sources.
- Atomic, fail-closed museum API intake and bundle re-verification with exact raw-response,
  downloaded-byte, and SHA-256 evidence.
- Deterministic sign-adjacency treewidth audit with line/artifact boundary modes and three null
  families.
- Corpus fingerprints, membership-frozen public-development split manifests,
  CLI, synthetic fixtures, and release documentation. These historical
  manifests were not blind/final benchmark locks.

### Scientific limitations

- No authoritative image-linked open corpus is bundled.
- No phonetic values, language assignment, or translation is claimed.
- The mayig adapter preserves a small, geographically narrow work-in-progress transcription and
  records known anomalous upstream fields without silently correcting them.
