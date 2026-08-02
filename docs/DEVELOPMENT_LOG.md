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

## 2026-07-29T04:00:00+09:00 — Final MTAAC V5 code-and-plan freeze

- V5 is the final adaptive MTAAC attempt. It reuses V4's exact development
  partition, folds, observations, features, profile, likelihood, parameter
  layout, class adjustment, family weighting, initialization, and optimizer.
- The only model change is a fixed group-contrast regularizer. For
  `quantity`/`unit` and `person_name`/`settlement_name`, V5 preserves the V4
  mean-direction penalty and doubles the within-pair emission and bias
  contrast penalty. It adds no parameter and exposes no multiplier, grouping,
  diagnostic, or candidate search.
- The exact 15,268-byte
  [plan](../benchmark/mtaac-v5-development-v1.json) has SHA-256
  `3c4a7c733218fcd0c4e6e25fbd59e5b86c1fd589512e9a88bb243b1d036c10f1`.
  It binds the V4 freeze/result and exact fold baselines, 15 mandatory gates,
  the `1e-12` comparison rule, MTAAC retirement, and byte-identical pre-report
  retry conditions.
- The runner fits one V5 primary model per outer fold and no V4 or diagnostic
  model. The closed validator reconstructs every scientific metric from
  confusion, out-of-fold sums, three V4-paired comparisons, support/mass
  invariants, all gates, and the terminal state before no-replace output.
- A valid failure returns `mtaac_retired` and fits no final model. A valid pass
  returns `advance_to_prospective_freeze`, fits only the all-development-family
  V5 model, and still retires MTAAC. Either outcome prohibits another MTAAC
  method attempt.
- Independent adversarial review found no execution blocker. No real V5
  metric exists at this checkpoint; MTAAC, the V2 holdout, and the prospective
  source have not been executed for V5.
- Pre-publication validation passed all 39 focused V5 tests and all 612
  repository tests (599 passed and 13 environment-specific tests skipped),
  Ruff, formatting, Pyright, Draft 2020-12 meta-schema and runtime plan
  validation, 131 local Markdown links, fresh source and wheel builds, isolated
  wheel installation and CLI/resource checks, Gitleaks, Semgrep, Trivy, and a
  dedicated deployment-identifier and private-path scan.

## 2026-07-29T04:23:53+09:00 — Final MTAAC V5 execution completed

- The code-and-plan freeze was first published at implementation commit
  `b0be18d7c317d276dfefd1237c17ec0be6886cd0`.
- The exact command then completed once. Its 59,053-byte aggregate
  [result](../benchmark/results/mtaac-v5-development-v1.json) has SHA-256
  `9b60b9eb6006efc35cdca90e91fdb07c356a09becc2a1d300ef22ec16393e88f`.
  The owner-only output and captured standard output were byte-identical.
- Closed-schema and runtime validation passed before publication. The report
  contains only aggregate development evidence and no deployment identifier,
  private path, item prediction, family membership, or reserved-source result.
- V5 passed 7 of 15 mandatory gates. Mild macro-F1 decreased from 0.3878 to
  0.3846 and improved over V4 in only one of five folds. Mild `unit` recall
  decreased from 0.3052 to 0.2937 and improved in zero folds.
  `settlement_name` recall increased from 0.0429 to 0.0575 and improved in
  three folds, but missed its 0.15 floor.
- The terminal status is `mtaac_retired`. No all-development-family final
  model was fitted. The V2 holdout and prospective source remained unscored,
  and no later MTAAC method attempt is permitted.
- Post-result publication validation passed all 44 focused V5 tests and all
  617 repository tests (604 passed and 13 environment-specific tests skipped),
  Ruff, formatting, Pyright, independent metric/gate recomputation, 135 local
  Markdown links, fresh source and wheel builds, isolated wheel installation
  and resource checks, Gitleaks, Semgrep, Trivy, and dedicated public-boundary
  and deployment-identifier scans.

## 2026-07-30 — KP1979 V2 qualification executed and published

- The
  [public protocol](KP1979_LABEL_LATTICE_V2_QUALIFICATION_PROTOCOL_2026-07-30.md)
  now records the completed execution and links the
  [machine-readable result](../benchmark/results/kp1979-label-lattice-v2-result-v1.json).
- The raw control status is `not_qualified`: 18 of 19 cases passed. The only
  failure was `positive_bounded_jitter_with_gaps`, where the detector abstained
  and obtained zero precision and zero recall against 68 synthetic references.
- All three metamorphic checks passed. The execution started 25 child processes
  for 25 adapter invocations, accepted 21 responses, properly rejected four
  out-of-contract inputs, and recorded no transport failure.
- The detector was frozen before the separately developed control, so the
  required control-before-detector gate fails. Overall status is fixed as
  `not_qualified` and advance is false independently of the raw control
  failure.
- A post-freeze periodic two-tier non-label confound separately blocks
  deployment. It does not alter the frozen detector, control, or raw-control
  gates.
- Git establishes bytes and ancestry only. Confidentiality, blindness,
  independence, organizational independence, cross-access absence, custody,
  trusted time, filesystem or network isolation, and independent public-remote
  attestation remain unverified.
- The run is synthetic only. It does not open real or future-evaluation
  material, PDF page 78, the earlier 57-page proposal assignment, the MTAAC
  holdout, ORACC prospective material, or another reserved source. It supports
  no accuracy, reference, transcription, reading, translation, decipherment,
  prize-eligibility, or submission claim.
- V2 is retired and must not be rerun, retuned, repaired, or used for
  extraction. The next controlled work is to create and publish a control-first
  V3 synthetic control before implementing its new detector identity.

## 2026-07-30 — KP1979 V3 pre-detector control infrastructure

- P0 published the reusable
  [freeze core](../.github/workflows/kp1979-v3-freeze-core.yml) at commit
  `6eebc904a1bee3eaa05be619796cc6336bb2d10e`, with exact workflow SHA-256
  `9bd93bed5359bd8cb396a0f6be063b5bc6f76ad1b84e1d6338e1edc14ae0300a`.
  P1 published the pinned
  [manual caller](../.github/workflows/kp1979-v3-freeze.yml) at commit
  `b530d1a2068135807f96dfe63ddbaf484b1acbb2`, with exact workflow SHA-256
  `aca066fc5df3565af831669b28ab661482dc0a21f319f6759fd912365c3f3442`.
- Python 3.11, 3.13, and 3.14 CI passed 753 tests per P0 job and 758 tests per
  P1 job. No freeze dispatch or V3 attestation has occurred.
- The closed
  [protocol](../src/indusbench/kp1979_v3_protocol.py) fixes
  `kp1979-label-lattice-synthetic-control-v3`,
  `two-column-glyph-lattice-v3`, and
  `kp1979-label-detector-v3-worker-v1`. Its ordered 12-positive,
  14-negative, six-out-of-contract roster plus eight two-endpoint metamorphic
  relations requires 48 fresh worker invocations.
- Audited pre-detector primitives comprise a bounded canvas,
  domain-separated PRF, mutually independent A/B renderers, and the fail-closed
  [systemd/Landlock sandbox](../src/indusbench/kp1979_v3_sandbox.py) with a
  separate bootstrap-owned handshake, seccomp, descriptor closure, and bounded
  resources. This is process isolation rather than a virtual machine; the root
  operating system, user manager, and trusted parent remain trusted.
- No detector, case generator, evaluator, target Quicknet round, C3 artifact
  or result, real-source access, decipherment, or prize claim exists. A C3 pass
  can authorize only owner-only provisional candidates for pages 22 through
  77. Page 78, public release, and every accuracy, identifier, sequence,
  language, meaning, translation, decipherment, prize, and corpus claim remain
  prohibited.
- Next: wire the generators and evaluator to the audited primitives, integrate
  the offline Quicknet verifier and deterministic freeze builder, publish the
  complete C3 source, then choose an exact target round at least eight days
  ahead and attest C3 at least seven days before it. Detector implementation
  begins only after that control freeze and attestation.

## 2026-07-30T16:15:04+09:00 — Quicknet CI and V3 worker-wire checkpoint

- The offline Quicknet dependency was published at commit
  `af9e757087505137a4b9d17d1e7ae4811b63432d`. Public CI run `30519982857`
  passed Python 3.11, 3.13, and 3.14 with 845 tests and 22
  environment-specific skips in each matrix job, and built both source and
  wheel distributions.
- An earlier public run exposed only a test-reporter portability assumption:
  Node 24 used a different TAP informational prefix than the legacy Node 18
  host. The portable BLS semantics step had already passed in every matrix
  job. The follow-up made the TAP reporter explicit; production verifier and
  vendored cryptographic bytes were unchanged.
- The answer-free
  [worker wire](../src/indusbench/kp1979_v3_wire.py) was published at commit
  `f79e437`. Its request has exactly five fields: interface version, raw-P4
  bytes, width, height, and scan bands. It carries no case identity, expected
  answer, truth, seed, relation identity, or generator metadata.
- Responses use the closed `proposed`, `abstained`, and `rejected` states.
  Proposed predictions are unique and sorted, restricted to lanes zero and
  one, page-bounded, and at most 128 pixels high. The future evaluator must
  separately require the intended exact height of 96 pixels; that scientific
  rule is deliberately not weakened into the transport parser.
- All six out-of-contract fixtures are accepted by the outer answer-free
  envelope and reach one sandbox invocation. Worker-owned semantic rejection
  follows the fixed precedence header, dimensions, payload size, then scan
  bands. Deep JSON, oversized integer, and non-finite exponent parser failures
  are reduced to the same path-free, detail-free outer error.
- Commit `cef6299` permanently tests compound semantic precedence and huge
  numeric failures at both request and response boundaries. Independent
  adversarial review after those additions reported zero blocker and zero
  major findings.
- Public CI run `30522383744` passed Python 3.11, 3.13, and 3.14. Every matrix
  job passed all 871 tests with 22 environment-specific skips, passed the six
  mandatory Quicknet BLS tests with zero failures, and built both source and
  wheel distributions.
- No V3 trial-state component, case generator, evaluator, deterministic freeze
  artifact, target Quicknet round, detector, C3 result, real-source access, or
  decipherment or prize evidence is established by this checkpoint.

## 2026-07-30T16:54:12+09:00 — V3 one-shot trial state accepted

- The hardened
  [one-shot state layer](../src/indusbench/kp1979_v3_state.py) was integrated
  at commit `bb01fe6`. It stores only a format version and one closed state
  value. It knows no experiment identity, commitment, request digest, worker
  output, score, seed, oracle, or result payload.
- Non-consuming preflight runs before the attempt marker. Before a worker may
  start, the layer exercises the actual state filesystem's no-replace rename
  behavior in both existing-target and absent-target cases, cleans and syncs
  its probes, writes the `started` record without replacement, and syncs both
  file and directory.
- Once `started` exists, every observed path is terminal. A marker-only crash
  recovers as `consumed_incomplete`; worker or transport failure becomes
  `execution_failed`; a completed scientific evaluation may record only
  `qualified` or `not_qualified`. There is no retry, reset, delete, or force
  API, and terminal publication also uses tested no-replace semantics.
- The state handle pins every ancestor directory descriptor through close,
  rechecks each namespace link, requires safe root/effective-user ownership
  and modes, permits only a root-owned sticky writable boundary, requires the
  final directory to be owner-only mode 0700, and rejects detectable ACL
  attributes. Linux and Darwin are the only admitted platform families;
  unsupported or unverifiable behavior fails before a worker starts.
- Paths, parser details, entropy failures, filesystem details, and worker
  exception text are collapsed to closed error codes. Invalid-surrogate paths,
  ancestor replacement, ACL changes, probe residue, concurrent starts,
  partial writes, and post-rename durability uncertainty have permanent
  adversarial tests.
- Independent review reported zero blocker and zero major findings. Its sole
  minor finding is that the Darwin branch has no permanent repository CI job,
  although its ACL and exclusive-rename paths received an independent live
  check. Focused evidence is 55 passing state tests; the implementation branch
  passed all 886 tests with 19 environment-specific skips. Integrated Ruff,
  formatting, Pyright, source and wheel builds, Gitleaks, and public-boundary
  checks also passed before publication.
- This is owner-controlled local durability, not independent custody. The
  owner, root, or the underlying filesystem can delete, replace, or roll back
  the directory. The records therefore do not prove trusted time,
  non-deletion, tamper resistance, organizational independence, or technical
  single execution against those actors.
- No state record has been created for C3, no worker has been invoked, and no
  generator, evaluator, freeze artifact, target round, detector, real-source
  result, decipherment evidence, or prize evidence is established here.

## 2026-07-31T11:57:56+09:00 — KP1979 V3 deterministic generator published

- Public CI run `30524604595` confirmed the preceding one-shot state
  integration on Python 3.11, 3.13, and 3.14. Each matrix job completed 926
  tests with 22 environment-specific skips and built both source and wheel
  distributions.
- The synthetic-only deterministic
  [generator](../src/indusbench/kp1979_v3_generator.py) was published at
  commit `88794f9748e909eef66f54c4c56d82fee5e9e521`. It implements the closed
  roster of 12 positive, 14 negative, and six out-of-contract cases plus
  eight fixed two-endpoint metamorphic relations, for exactly 48 worker
  invocations.
- Authoritative case and relation validation requires the supplied suite seed
  and exact equality with deterministic canonical regeneration. Structural
  certificate checks alone are not an acceptance boundary.
- The suite seed, generated objects, construction and truth oracles,
  generation commitments, and schedule metadata are controller-only. Once
  instantiated, they must not be persisted or published before execution and
  must never be passed to a worker. Only `request_bytes` under the exact
  five-field answer-free wire contract may cross that boundary.
- Independent read-only QA of the publication candidate reported zero
  blockers, zero major findings, and zero minor findings. The local
  integrated-source profile passed 99 focused generator/state/wire tests and
  all 947 repository tests with 19 environment-specific skips, plus Ruff,
  formatting, Pyright, source and wheel builds, Gitleaks, and public-boundary
  checks.
- Public CI run `30599459365` passed all 947 tests with 22
  environment-specific skips on Python 3.11, 3.13, and 3.14 and built both
  distributions in every matrix job.
- This is a source checkpoint, not a C3 freeze or run. It establishes no
  target Quicknet round, detector, real-source access or result, decipherment
  evidence, or prize evidence. KP1979 V2 remains immutable. At that
  checkpoint, the V3 evaluator was the next implementation task.

## 2026-07-31 — KP1979 V3 streaming evaluator implemented

- At commit `ee847035867fe92dbca8b3e0aa9422dcfd43f138`, the aggregate-only
  [evaluator](../src/indusbench/kp1979_v3_evaluator.py) builds and validates
  one canonical generator object at a time under the same suite seed. It does
  not import or materialize the controller schedule. It passes only
  `request_bytes` to the supplied invoker for 32 case calls followed by 16
  relation-endpoint calls.
- A positive call passes only with `proposed`, exact height 96 for every
  prediction, and complete sorted same-lane one-to-one anchor matching inside
  half-open truth intervals, yielding no false positive or false negative.
  Negative calls require exact `abstained`, each out-of-contract call requires
  its expected `rejected` code, and five invariant relations plus
  vertical-plus-11, lane-swap, and exact gap-deletion are checked.
- A valid scientific failure does not short-circuit: all 48 calls complete and
  the result is `not_qualified`. Any technical fault becomes the same
  `execution_failed` result with no error detail, all five counts absent, and
  no authorization. `BaseException` is intentionally not caught so a future
  one-shot runner can record `consumed_incomplete`.
- The result is a closed ten-field aggregate. Only a complete scientific pass
  carries authorization, limited to owner-only provisional candidates for
  pages 22 through 77. Page 78 authorization and every public claim permission
  are false. No case or relation identity, prediction, truth, worker output,
  request, seed, digest, error detail, or generation commitment is returned.
- The evaluator API accepts an injected invoker, so the component result alone
  is not an execution attestation and does not establish that the official
  sandbox path was used. The official runner has not been implemented. Any
  authoritative future use must internally construct and own an exact
  `SandboxedWorkerInvoker` and must allow no caller-injected invoker.
  Two independent read-only source audits reported zero blockers, zero major
  findings, and zero minor findings.
- Local source evidence passed all 28 focused evaluator tests and all 975
  repository tests with 19 environment-specific skips, plus Ruff, formatting,
  Pyright, source and wheel builds, Gitleaks, and public-boundary checks.
- Public CI run `30604750422` succeeded in 16m32s:
  - Python 3.11 passed Quicknet 6/6 in 528.547056ms and all 975 tests with 22
    environment-specific skips in 843.345s;
  - Python 3.13 passed Quicknet 6/6 in 728.88314ms and all 975 tests with 22
    environment-specific skips in 957.050s; and
  - Python 3.14 passed Quicknet 6/6 in 608.578832ms and all 975 tests with 22
    environment-specific skips in 906.624s.
  Every matrix job passed Ruff, checked all 179 files with Ruff format,
  reported zero Pyright errors, warnings, or information messages, and built
  both the sdist and wheel.
- No C3 controller or freeze builder has been implemented; no freeze has been
  dispatched; and no C3 run, target selection, detector, real-source access or
  result, decipherment evidence, or prize result exists. KP1979 V2 remains
  immutable.
- At that checkpoint, next was the non-operational C3 controller/freeze
  builder plus Quicknet interruption cleanup, without target selection or
  freeze dispatch.

## 2026-07-31 — Quicknet interruption cleanup hardened

- Commit `eda8af5791ed3ad6073d80308fa0696434ab89b6` hardens the bounded
  best-effort cleanup path around the fixed Quicknet verifier subprocess.
- A `BaseException` raised by the initial `communicate` triggers
  process-group termination attempts, bounded `communicate`, bounded `wait`,
  and a bare re-raise preserving the original exception object. Cleanup
  on this path do not replace that primary exception.
- After an ordinary timeout, `OSError`, or `SubprocessError`, the first
  cleanup `BaseException` from process-group kill, `communicate`, or `wait`
  is retained. Every bounded cleanup stage continues, an interrupted first
  kill is retried, an interrupted wait is retried once boundedly, and the
  exact first cleanup exception object is then re-raised. Ordinary public
  Quicknet failures remain path-free and detail-free.
- This is bounded best-effort cleanup, not a guarantee of process termination
  under repeated hostile interrupts. The 27-case ordinary-primary ×
  cleanup-location × `BaseException`-wrapper matrix uses controlled process
  doubles. A separate real-process regression specifically interrupts the
  first kill and verifies the second kill/reap path; it does not imply that
  every matrix combination starts a real process.
- Local evidence passed:
  - all 9 focused interruption tests, including the 27-case matrix;
  - all 23 Quicknet tests;
  - all 984 repository tests with 19 environment-specific skips in 976.360s;
  - Ruff, formatting, Pyright, Gitleaks, and exact two-file source/test scope
    checks; and
  - independent review with zero blockers, zero major findings, and zero
    minor findings.
- Public CI run `30608426512` succeeded in 16m27s:
  - Python 3.11 passed Quicknet 6/6 in 448.623633ms and all 984 tests with 22
    environment-specific skips in 640.818s; its job completed in 11m11s;
  - Python 3.13 passed Quicknet 6/6 in 527.92177ms and all 984 tests with 22
    environment-specific skips in 950.240s; its job completed in 16m17s; and
  - Python 3.14 passed Quicknet 6/6 in 546.222152ms and all 984 tests with 22
    environment-specific skips in 925.641s; its job completed in 16m05s.
  Every matrix job passed Ruff, checked all 179 files as formatted, reported
  zero Pyright errors, warnings, or information messages, and built the sdist
  and wheel.
- Portable semantic CI remains fixed to exact Node 24.18.0. The host wrapper
  remains fixed to end-of-life Node 18.19.1 for qualification only. A
  supported runtime policy remains unresolved before any official runner.
- No official C3 runner, controller, or freeze builder has been implemented.
  No freeze was dispatched, and no target round was selected or
  fetched. No detector, real-source access or result, decipherment evidence,
  or prize result exists. The evaluator's caller-injected invoker boundary
  still means its component result is not an execution attestation. KP1979 V2
  remains retired and immutable.
- Next: implement the non-operational, source-only control-bundle builder and
  supported runtime policy. This does not authorize target selection, freeze
  dispatch, detector execution, real-source access, or a public or prize
  claim.

## 2026-07-31 — KP1979 V3 control source-bundle builder published

- Commit `2e81afef7e188f9dd70059c60b9f1123019b3753` adds the
  deterministic, non-operational
  [control source-bundle builder](KP1979_V3_CONTROL_BUNDLE.md) and its closed
  manifest schema. The code exists, but no real control bundle, freeze
  artifact, or subject digest has been generated or retained.
- The exact roster contains 36 payloads and 37 regular-file members after
  adding `MANIFEST.json`: the license, schema, package initializer, builder,
  12 controller-side modules, and the exact 20-file vendored Noble/Quicknet
  closure.
- The manifest fixes all identities and the 32 case, 16 relation-endpoint, and
  48 total invocation counts. It states that the subject is source-only and
  non-operational, that no target round is selected, and that detector and
  integration components are absent. Each payload entry binds its exact path,
  size, and SHA-256.
- The bounded verifier requires compact sorted-key ASCII JSON with one LF,
  sorted regular-file-only canonical USTAR, and a fixed project-owned
  stored-DEFLATE gzip stream. It rejects noncanonical metadata, framing,
  rosters, hashes, paths, padding, links, special files, concatenation, and
  trailing data, then reconstructs the exact subject bytes.
- Source reads use descriptor-relative, no-follow access with ancestry,
  directory, leaf, fingerprint, and forbidden-module revalidation. Output is
  owner-only, synchronized, no-replace, and verified by namespace, inode, link
  count, mode, size, and bytes. On failure, cleanup rechecks that the output
  name identifies the builder-owned inode and otherwise preserves an unknown
  entry. This is best effort and not atomic against same-UID or root namespace
  replacement.
- The exact CLI gate requires CPython 3.12.11, the exact `-s -B -m` invocation,
  and exactly eight closed environment keys. That runtime is installed in the
  local qualification environment, but it was not used to produce or retain
  a real artifact.
- Local evidence passed:
  - all 63 focused control-bundle tests under exact CPython 3.12.11 in 2.017s;
  - all 1,047 repository tests with 19 environment-specific skips in
    1002.306s;
  - Ruff lint, Ruff format over all 181 checked files, Pyright with zero
    errors, warnings, or information messages, sdist and wheel builds,
    Gitleaks, and public-boundary checks; and
  - two independent audits, each reporting zero blockers, zero major
    findings, and zero minor findings.
- Public CI run `30615528575` succeeded in 16m23s at exact source commit
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
- The supplied `source_commit` is a 40-character label checked for manifest
  equality; the builder does not verify Git, signatures, checkout equality,
  trusted time, or custody. Descriptor and no-replace checks do not establish
  a boundary against same-UID or root actors and cannot remove every race
  window.
- The evaluator's injected-invoker result remains a non-attestation. A future
  official runner must internally own the exact `SandboxedWorkerInvoker`.
  Quicknet cleanup retains a second/repeated-interrupt residual; the sandbox
  needs explicit `BaseException` cleanup hardening; and the supported
  host-runtime policy remains unresolved. Node 18.19.1 is end-of-life and
  qualification-only.
- No freeze was built or dispatched. No target was selected, reserved, fetched,
  or accessed. No real-run suite seed, schedule, generated truth, worker
  response, detector, integration binding, official runner, real-source
  access or result, C3 result, decipherment evidence, translation, public
  claim authorization, or prize evidence exists. KP1979 V2 remains retired
  and immutable.
- Next: resolve the supported host runtime and sandbox interruption cleanup,
  then implement and audit an injection-free official one-shot runner. Those
  tasks authorize no freeze, target, worker, detector, real-source access, or
  public or prize claim.

## 2026-07-31 — Portable Quicknet semantic-CI security pin updated

- Commit `0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec` changes exactly the
  portable CI workflow and its Quicknet contract test. No production Quicknet,
  vendored cryptography, host wrapper, sandbox, generator, evaluator, builder,
  or runtime source changed.
- Portable semantic CI now requests exact Node 24.18.1 on Linux/x64 through
  `actions/setup-node` v7.0.0 full commit SHA
  `820762786026740c76f36085b0efc47a31fe5020`. Package-manager caching is
  disabled. The workflow asserts exact version, `process.platform == "linux"`,
  and `process.arch == "x64"` before the six mandatory semantic tests.
- The source contract requires every setup field and assertion exactly once,
  fixes the runtime assertion/command order, retains the no-skip command, and
  excludes the qualification-host test from the workflow.
- Earlier public runs under exact Node 24.18.0 and full-SHA-pinned
  `actions/setup-node` v6.5.0 remain historical evidence and are not rewritten
  as results for this configuration.
- This step configures deterministic public-input BLS semantic checks in an
  ephemeral Linux/x64 CI job. It is not provenance or attestation for a
  project or deployment runtime, launcher, dynamic `libnode`, OpenSSL, glibc,
  kernel, custody, sandbox path, or worker execution.
- The unchanged Node 18.19.1 host wrapper remains end-of-life and
  qualification-only. A supported host-runtime policy and complete dynamic
  closure remain unresolved.
- Focused Quicknet contract tests, Ruff lint and formatting, Pyright, YAML
  parsing, and diff checks passed locally. Independent read-only review of the
  two-file source change reported zero blockers, zero major findings, and zero
  minor findings.
- Public CI run `30617537380` succeeded in 16m24s at exact source commit
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
- No project or deployment runtime was installed or changed. No freeze was
  built or dispatched; no target was selected, reserved, fetched, or accessed;
  no protected or real data was opened; and no worker or detector ran. This
  checkpoint establishes no C3 result, real-source result, decipherment
  evidence, claim authorization, or prize result.

## 2026-07-31T18:53:13+09:00 — Sandbox cleanup hardening local draft

- Source commit `cd583fb12b12a80d132c80e8a3465e53f5c3151a` changes only
  the sandbox implementation and its test module. Its exact binary diff
  SHA-256 is
  `7069fbae6e9749c401f00ef35b5e5cc8c74d0e262f00626c95d4a7192d71115d`.
  The digest is not a signature, trusted timestamp, custody record, or
  execution attestation.
- After the main sandbox client handle exists, timeout, an interrupt during
  pre-output client communication or status establishment, a negative initial
  client status, a missing initial status, and other abnormal paths before
  output or handshake access enter the same
  bounded state machine: (A) unit-wide kill dispatch, (B) client process-group
  kill, (C) conditional unit-kill retry, (D) bounded `communicate`, and
  (E) bounded `wait` with one retry. Each later stage is attempted after an
  earlier ordinary failure or interrupt.
- A timeout may return the stable public `timeout` result with captured byte
  counts only when the client is reaped and at least one `systemctl kill`
  helper returned zero. Status zero is only dispatch acknowledgement; it does
  not prove that the service cgroup is empty or establish sandbox, custody, or
  execution attestation. Without both conditions the path becomes a redacted
  setup failure and does not read output or handshake files.
- A primary non-`Exception` `BaseException` wins by exact identity over cleanup
  faults. When the primary is ordinary, the first cleanup non-`Exception`
  `BaseException` is retained by identity while all bounded stages continue.
  Ordinary errors are normalized through the existing stable result surface.
- Artifact, handshake, and bounded-output reads use `O_NOFOLLOW` and
  `O_NONBLOCK` where available, owner-safe regular-file metadata checks,
  bounded reads, before/after fingerprint checks, and explicit descriptor
  closure. Exclusive writes and temporary-directory cleanup preserve the
  documented primary/cleanup precedence. These are process-local hardening,
  not a boundary against same-UID or privileged actors.
- The public `SandboxedWorkerInvoker` constructor and `__call__` signatures,
  `SandboxInvocationResult` fields, dispositions, and failure codes are
  unchanged. `started_process_count` advances only after the main sandbox
  client `Popen` returns; kill-helper processes never count.
  `verified_invocation_count` advances only after the canonical handshake is
  parsed, including when a later status access fails.
- Bounded best effort is still not a termination guarantee. Repeated hostile
  interrupts can defeat finite attempts, and privileged interference can leave
  residual process or unit state. A successful kill dispatch is not proof of
  final teardown. Bounded means finite attempts and explicit
  `communicate`/`wait` timeouts, not a hard real-time bound on `Popen` process
  creation, kernel scheduling, signal delivery, or filesystem/system calls.
- Source-commit-bound focused evidence passed:
  - the normal interpreter ran 47 sandbox tests in 1.644s with six
    environment-specific skips;
  - exact CPython 3.12.11 ran the same 47 tests in 1.645s with the same six
    skips; and
  - the combined evaluator and worker-wire suites ran 51 tests in 27.230s
    with no skips.
- Two independent read-only code audits of the exact source commit and diff
  each reported zero blockers, zero major findings, and zero minor findings.
- The first complete-suite attempt ran 1,078 tests with 19
  environment-specific skips and recorded
  four Quicknet failure/error outcomes (two failures and two errors).
  All four outcomes were fail-closed mode prechecks caused by inherited umask
  in the isolated
  worktree: vendored Noble regular files were `0664` and directories were
  `0775`. Source bytes, content hashes, and the source diff were unchanged. A
  worktree-only `chmod go-w` normalization restored `0644` files and `0755`
  directories, after which focused Quicknet passed. This attempt remains a
  failed historical validation event and is not relabeled as success.
- Final local validation after normalization passed:
  - all 23 Quicknet tests;
  - all 1,078 repository tests with 19 environment-specific skips in
    1213.871s, with a 1214.88s external wall duration;
  - Ruff lint over the complete configured scope and Ruff format over all 181
    checked files;
  - Pyright with zero errors, zero warnings, and zero information messages;
  - distribution member checks for a 337-member sdist and 163-member wheel,
    including path, private-material, and source-hash assertions;
  - Gitleaks across 65 commits and approximately 7.15 MB with no leaks; and
  - the public-boundary check.
- Public CI gate closed: event `push`, exact head SHA
  `cd583fb12b12a80d132c80e8a3465e53f5c3151a`, status `completed`, conclusion
  `success`, and all three matrix jobs green in
  [run 30623782622](/megu0xxx0x/indus-open-benchmark/actions/runs/30623782622).
  The overall run window was `2026-07-31`, `10:30:29Z`–`10:46:17Z`
  (15m48s). Each Quicknet job asserted Node `v24.18.1` on Linux/x64 and had
  zero failed, cancelled, skipped, or todo tests. Python 3.11 ran
  `10:30:33Z`–`10:44:34Z` (14m01s), Quicknet 6/6 at
  `duration_ms=615.588048`, and unittest 1078 tests with 22 skipped in
  808.435s. Python 3.13 ran `10:30:32Z`–`10:39:02Z` (8m30s), Quicknet 6/6 at
  `duration_ms=292.030965`, and unittest 1078 tests with 22 skipped in
  483.182s. Python 3.14 ran `10:30:32Z`–`10:46:16Z` (15m44s), Quicknet 6/6 at
  `duration_ms=565.70517`, and unittest 1078 tests with 22 skipped in
  906.229s. Each job also passed Ruff lint, Ruff format with all 181 files
  already formatted, Pyright with zero errors, warnings, or information
  messages, and sdist plus wheel builds. The CI skip count is 22 per job and
  is intentionally recorded separately from the clean local run's 19 skips.
- Controlled tests use subprocess doubles and one inert local Python sleep
  process group. No real systemd service, project worker, detector, freeze,
  target, protected or real corpus, or scientific run was accessed or
  executed. No bundle or freeze was generated or dispatched; no target was
  selected or fetched; and no decipherment evidence, claim authorization, or
  prize result exists. KP1979 V2 remains retired and immutable.
- Next after audited publication: resolve the supported host runtime and
  dynamic closure, then design an injection-free official one-shot runner.
  This draft authorizes none of those actions and no execution.

## Context source-link preselection gate — 2026-07-31

Commit `fd5148431b0fa9136336650208e2d570d0f176d8`, whose parent is
`361b1532d08b642423dd202f2f03c40cd41cdbb2`, adds a static repository-only
preselection registry, an exact Draft 2020-12 schema, and tests. The exact
three-file, mode-`100644`, 979-addition binary diff has SHA-256
`56d8124f05223df5c9e010cfc97de328b5f7b6c3c2bc52f2aa8e8a7d10bd8de9`.

The source-table order is fixed as SF 2000, SF 3495, SF 3493, SF 2428,
SF 3051, and SF 2558. Each row consists of exactly three source-namespaced
identifiers: Mackay field number, Penn official record ID, and Penn accession
number. Every row remains `source_locator_only` and
`not_joined_requires_separate_contract`. The roles are three
`lead_no_listed_material_conflict`, one
`excavation_location_axis_conflict`, and two
`shared_penn_target_identity_collision`. SF 3495 keeps its unresolved
excavation-location axis. SF 3051 and SF 2558 stay separate while both point
to Penn record 329820 / accession L-141-177.

The recorded counts are six source links, five distinct Penn catalog records,
and zero admitted joins. The five-record value is a catalog-record count, not
an artifact or physical-identity assertion; `physical_identity_verified`
remains false. The registry has no positive, probable, exact, joined, or
admitted status, and no sign, glyph, token sequence, transcription, Helsinki
row, reading, direction, language, translation, or decipherment value.

Rights remain layered. Penn bulk metadata is CC BY 4.0, metadata-only, with no
media. The Penn item-page association is outside that bulk source, has no
registered source binding, a null license, unknown rights, and link-only
scope. The Mackay report locator likewise has a null license, unknown rights,
and link-only scope. No image, page, plate, or media bytes are in the gate.

The schema uses six exact `prefixItems` with `items: false`, minimum and
maximum six, and exact constants for the three rights layers and all
nonclaims. The registry and schema are canonical exact bytes. All 355 tested
mutations were rejected. This proves only the static repository contract. No
production builder, API, strict runtime loader, source-access workflow, or
registry runtime package exists. The registry and test are absent from the
wheel; the schema is present. Future operationalization must use strict
`decode_json` and add explicit resource-inclusion tests before any package or
runtime gate can be claimed.

Validation evidence:

- Focused tests passed 9 cases in about 0.03s; related tests passed 19 cases
  with one environment-specific skip in 0.667s; all four publication tests
  passed.
- Ruff lint passed; Ruff format accepted all 182 checked files; Pyright
  reported zero errors, warnings, or information messages.
- The offline isolated build produced a 341-member sdist containing all
  three new source files and a 164-member wheel containing only the new
  schema from that set. A preceding non-isolated build stopped before build
  because the backend was unavailable and produced no artifact.
- Gitleaks scanned 67 commits and approximately 7.22 MB with no leaks.
- The final independent audit reported zero blockers, zero major findings,
  and zero minor findings. An earlier audit had identified a major
  bulk-versus-item source-binding overclaim and a minor object-versus-catalog
  naming problem; both were corrected before the final audit.
- The first complete run reached 1,087 tests with 19 skips but had exactly
  two failures and two errors: Quicknet fail-closed checks rejected vendored
  Noble files/directories at inherited `0664`/`0775` modes. Only the isolated
  worktree modes were normalized to `0644`/`0755`; tracked bytes, hashes, and
  diff did not change. All 23 Quicknet tests then passed in 4.634s. The clean
  second run completed the 1,087-test full suite with `OK (skipped=19)` in
  976.546s.
- Public CI run `30635957691` succeeded for event `push` at exact head SHA
  `fd5148431b0fa9136336650208e2d570d0f176d8`. Every job asserted Node
  `v24.18.1` on Linux/x64. Python 3.11, 3.13, and 3.14 passed Quicknet 6/6 in
  527.702196ms, 655.421586ms, and 503.092653ms, respectively, and completed the
  1,087-test full suite with `OK (skipped=22)` in 810.027s, 946.248s, and
  759.619s, respectively. Each job also passed Ruff (`All checks passed`),
  Ruff format with all 182 files accepted, Pyright with zero errors, warnings,
  or information messages, and both sdist and wheel builds.

No network request to a research or source endpoint, external or protected
source-byte download, image/page/plate retrieval, Helsinki-row access,
institution or source-holder contact, operational source-link gate, or real
source-link attempt occurred. Repository publication and CI are outside that
statement. No source access is authorized by this commit. There is no
admitted row, transcription, sequence, decipherment evidence, or
prize result.

Infrastructure is hard-frozen while the research lane resumes. Host Node 24
activation and an official runner are deferred until a real experiment
exposes a reproducible need. The next research design is a separately frozen
non-sign source-link attempt. It must select rows without sign, glyph, or
sequence similarity, and a no-link outcome is a valid terminal result.

## 2026-08-01T03:23:18+09:00 — Static source-reported-link decision policy published

Commit `c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`, whose parent is
`54fccb7a86a0d45de4e626b57a6332d091c11db2`, freezes a static
repository-only policy, exact Draft 2020-12 schema, and tests. The exact
three-file, mode-`100644`, 898-addition binary diff has SHA-256
`a635c012adefc52e05677aa1b337afe45ba53a25d4589bcb71446c7c2c0e8982`.
The file SHA-256 values are:

- registry:
  `c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90`;
- schema:
  `d951541892bb6a5ef092d44e9a5564da2261f960e52e3e84a95ecd5ef8e61aff`;
  and
- test:
  `8870593c1195aad4138626343d9e051da0815fb6695c8f6515f9e9270b5af045`.

All six parent preselection rows remain in source-table order and receive one
result slot each. The exact terminal-state precedence is `contract_blocked`,
`unresolved`, `source_reported_link`, then `no_link`. Hard rejection precedes
state evaluation and is not a result. Aggregate answers, missing rows, and
post-hoc target substitution are prohibited. `source_reported_link` means
only a dual source report under exact external prerequisites; it is not a
positive/truth state, physical-identity finding, or admitted join.

The mode is two separately sealed coded machine passes. Only `pass_id` and
`seal_sha256` must differ. Human, model, and organizational independence,
blinding, nonexposure, and authorship authenticity remain unverified. A
row-absent `no_link` requires exact complete-roster evidence from both passes;
a bare not-found result remains `unresolved`.

The current prerequisite state is `contract_blocked`. The registered Mackay
locator is unknown-rights and link-only. The Penn item page is unregistered,
null-bound, unknown-rights, and link-only, and does not inherit Penn bulk
metadata's CC BY 4.0 license. A separate source registration and rights
contract must bind exact revisions, rights handling, inspection procedure,
and the complete ordered source roster before any execution decision.

The Schema `const` is semantically exact but treats JSON numbers such as `6`
and `6.0` as equivalent. The policy therefore separately requires canonical
byte identity and hard-rejects noncanonical input. The exact build produced a
345-member sdist, SHA-256
`378f38b04f9e396e96881d4d0a195003080a790256bd34958bb8992114c15033`,
containing all three policy files, and a 165-member wheel, SHA-256
`3f7cb59e4eb7ace577f7dadf2e8e056d644791bf138889e8dbfdaf2e04aba9a5`,
containing only the schema from that set. There is no installed loader or
runtime evaluator and no package/runtime-gate claim.

Before the static design was chosen, a local untracked runtime-evaluator
prototype underwent pre-publication design/security review. It could
misrepresent an incomplete roster as complete, return an aggregate that hid
five rows, trust duck-typed verification values, let raw parser exceptions
escape the closed error boundary, and fail installed-schema lookup. The draft
was never staged, committed, pushed, packaged, or used on source data. It
produced no observation or result and was deleted. The checkpoint was narrowed
to the static policy so these defects could not become a public runtime claim.

Validation evidence:

- all 7 focused policy tests and all 20 combined policy/parent/publication
  tests passed;
- Ruff lint passed, Ruff format accepted all 183 files, and Pyright reported
  zero errors, warnings, or information messages;
- the first full suite ran 1,094 tests in 1034.566s with 19 skips and recorded
  two failures and two errors, solely because Quicknet fail-closed checks
  rejected vendored Noble files/directories inherited at `0664`/`0775` in the
  isolated worktree;
- only those isolated-worktree modes were normalized to `0644`/`0755`, with
  tracked bytes, hashes, and candidate diff unchanged; Quicknet then passed
  23/23 in 4.197s;
- the clean rerun passed 1,094 tests in 1084.894s with `OK (skipped=19)`;
- the final independent audit reported zero blockers, zero major findings,
  and zero minor findings; and
- Gitleaks scanned 69 commits and 7,292,640 bytes with no leaks.

Public CI run `30654728606` succeeded at exact head
`c9035109dc1ee9bc8bf02fdc85b88ce9f716eef9`. Python 3.11, 3.13, and 3.14
passed Quicknet 6/6 in 398.928145ms, 522.070668ms, and 542.131729ms,
respectively, and passed all 1,094 tests with 22 skips in 636.266s, 910.867s,
and 930.525s. Every matrix job asserted Node 24.18.1 on Linux/x64, passed Ruff,
accepted all 183 files as formatted, reported zero Pyright errors, warnings,
or information messages, and built both the sdist and wheel.

During this static-policy checkpoint, no research or protected source endpoint
was requested; no external source byte, image, page, plate, media, Helsinki
row, or protected corpus was opened; and no institution or source holder was
contacted. No evaluator, pass, observation, inspection, roster attestation,
source-reported-link/no-link outcome, join, translation, decipherment evidence,
claim authorization, submission, or prize result exists. Repository
publication and CI are outside that statement and authorize none of those
actions. Next is the separate source registration and rights contract;
execution remains unauthorized.

## 2026-08-01T07:07:54+09:00 — Static source registration and rights contract

Source checkpoint `90f3fd3bea1177034451283795ad13ccb4b31bcf`, based on parent
`45d946a462dd85aa3025ed9ad9c0465541bd85be`, freezes the
[detailed source registration and rights contract](SOURCE_REPORTED_LINK_SOURCE_CONTRACT_V1.md).
The linked documentation records the exact five-file identities and hashes,
request and receipt rules, custody states, package builds, and validation
evidence.

The policy's unregistered/null Penn item-page state remains frozen historical
fact. This later contract records an explicitly nonretroactive
`registered_static_no_revision_receipt` transition for the five exact Penn
URIs. Rights remain unknown and link-only, and bulk CC BY 4.0 is not
inherited. Five future Penn receipt members, six ordered revision resources,
and six ordered result slots remain distinct. Registration is not revision
capture, rights clearance, source access, inspection, or execution.

The exact candidate passed the 30-test focused policy/contract/parent set,
static/build/secret checks, and final zero/zero/zero audit. Two earlier full-
suite attempts were intentionally interrupted for specification hardening,
then `Content-Encoding` nullability correction, not test failures. Final
suite result is `Ran 1106 tests in 1023.743s; OK (skipped=19)`. Public
[CI run 30667904927](/megu0xxx0x/indus-open-benchmark/actions/runs/30667904927)
succeeded at exact head `90f3fd3bea1177034451283795ad13ccb4b31bcf`.
Python 3.11, 3.13, and 3.14 respectively recorded Quicknet/full-suite
durations of 425.727693 ms/642.201s, 522.243511 ms/978.761s, and
512.327502 ms/887.018s. Each matrix passed Quicknet 6/6 and 1106 full tests
with 22 skips, plus Ruff, the 184-file format check, zero-error Pyright,
sdist, and wheel builds.

Contract status is `preregistered_contract_blocked_pending_revision_receipt`;
the policy prerequisite remains `contract_blocked`, authorization
`not_authorized`, and execution `not_executed`. Required schemas, protected
custody/deletion contract, receipt, digests, parser, evaluator, observations,
and results are absent. No source was accessed and no scientific or prize
result exists.

## 2026-08-01T18:17:48+09:00 — Static evidence prerequisites validated and published

Commit `698c029b038b08d8f7e5538e048fdc42eb659160`, based on
`68ae5cff9065477be3a34ccc07b152636f44eb2f`, published the
[static evidence-prerequisite contract](SOURCE_REPORTED_LINK_EVIDENCE_PREREQUISITES_V1.md),
four closed dynamic-payload schemas, the exact-const custody-contract schema,
and prerequisite tests. Commit
`93609e39263fde2617a6ea13b2f4de64947cd17e` then made a test-only locked
Pyright narrowing fix without changing contract/schema bytes or semantics.

The checkpoint freezes the five-member receipt, separate commitment envelope,
six-resource revision set, conditional six-slot completeness payload, and the
protected ephemeral custody/deletion/recovery blueprint. It preserves exact
5/6/6 cardinalities, six row slots, conflict and collision semantics,
one-attempt anti-replay requirements, and the closed source-access status
lattice. Test-local executable models remain explicitly non-security
reference semantics, not a runtime verifier or authority boundary.

Validation evidence:

- the focused policy/source/prerequisite set passed 41/41;
- reference matrices passed five no-ledger branches, 20 other branches, all
  990 Cartesian combinations with zero mismatches, 34 storage cases, and 25
  additional storage assertions;
- Ruff, the 185-file format check, locked Pyright 1.1.409, canonical/schema
  checks, builds, and exact-diff secret/public-boundary checks passed;
- three independent read-only AI audits reported zero P0/P1/P2 findings,
  without claiming human or external review; and
- public GitHub Actions run `30692592441` succeeded at exact head
  `93609e39263fde2617a6ea13b2f4de64947cd17e`. Node 24.18.1 and Python
  3.11/3.13/3.14 each passed Quicknet 6/6, zero-error Pyright, all 1,128
  tests with 22 skips, and both builds. Full-suite times were 832.968s,
  942.715s, and 865.301s.

One retained local-host incident used unsupported Node 18.19.1: 1,128 tests
ran in 912.511s with 19 skips and exactly four Quicknet-only fail-closed
failures/errors. The V8 tests passed, and required-Node public CI established
the environment diagnosis.

The first public run, `30691454425`, passed required-Node Quicknet and lint in
all three jobs, then stopped on seven Pyright narrowing diagnostics in the new
reference-model test. The test-only `93609e3` fix added fail-closed type
narrowing and changed no registry or schema byte.

Documentation-only run `30693842726` later rejected exact head `c8d7231`
in all three Python jobs after the full suite found two publication-boundary
regressions: one literal operational-document digest and three
repository-specific Actions links. The follow-up removes those public
machine-specific literals without changing any frozen contract or schema
byte.

Present status is
`preregistered_static_prerequisite_blocked_not_authorized`,
`not_authorized`, `not_executed`, and
`NONE_no_source_access_executed`. The strict bootstrap/root classifier/
terminalizer/verifier, runtime schemas, acquisition, parser, evaluator,
durable recovery, trust root, runtime manifest/distribution binding, and exact
one-attempt authority proof are not implemented. No source was accessed and
no receipt, pass, observation, result, join, decipherment evidence,
submission, or prize result exists.

Next: implement and freeze that entire runtime boundary without source access,
audit the distinct runtime commit, and only then request a new authenticated
authority proof binding both commits. Generic earlier approval is not that
authority.

## 2026-08-01T19:20:49+09:00 — First source-free static preflight slice

Publication-boundary correction `81269ebf2a3e27e8bb8914733c7e37cc47524ccb`
restored the required publication boundary without changing a frozen
contract or schema byte. GitHub Actions run `30694616450` then succeeded on
Python 3.11, 3.13, and 3.14. Each job passed Quicknet, Ruff, formatting,
zero-error Pyright, all 1,128 tests with 22 skips, and both distribution
builds.

The subsequent source-free implementation candidate adds the
[static loader and canonical-resource preflight](SOURCE_REPORTED_LINK_STATIC_LOADER_V1.md):

- a closed 21-role raw-resource API implementing byte limit, BOM-free strict
  UTF-8, duplicate-key rejection, integer-only JSON, structural bounds, and
  exact `encode_json` byte equality;
- an argument-free installed-package loader for 14 compiled resources using
  descriptor-relative no-follow reads, fixed size/hash checks, ownership/
  mode/link/device checks, before/after fingerprints, bounded reads, and
  fail-closed descriptor cleanup;
- explicit Draft 2020-12 validation of nine schemas with local-only refs,
  `date-time`/`uri` format enforcement, and five registry/contract instance
  validations;
- parent binding, ordered six-task roster, four-schema set, and
  domain-separated digest recomputation;
- a six-identity immutable snapshot that explicitly leaves the runtime
  distribution and transitive runtime-input manifest bindings absent; and
- exact wheel inclusion plus an isolated empty-CWD built-wheel loader check
  with repository fallback excluded, socket audit events trapped, and a
  temporary deterministic `0022` extraction umask restored in `finally`.

Static audit found that the already-frozen `registry/sources.json` and
`schemas/source-registry.schema.json` predate the current canonical key order.
Reformatting them would invalidate existing parent and const-schema
commitments. The implementation therefore has a compiled exact-two
re-encoding exception only after those resources match their frozen raw
size/hash. All other strict JSON, schema, and cross-binding checks remain
mandatory, the normalized bytes are never adopted, and the other 12
resources require canonical equality.

The frozen V1 resolver nevertheless requires canonical equality for every raw
input. The snapshot is therefore fixed as
`strict_v1_resolver_eligible=False`, with both noncanonical parents named as
blockers. The decoder repeats the exact size/hash check itself, so a private
helper cannot activate the exception by key alone. Supplying the two runtime
identities would not resolve this normative incompatibility; a successor
profile or re-frozen parent chain is also required before strict resolution.

Pre-publication focused evidence is 76/76: 22 resource-preflight tests, 13
static-loader tests, seven policy tests, 12 source-contract tests, and 22
evidence-prerequisite tests. Targeted Ruff/format and locked Pyright passed,
as did sdist/wheel builds, exact wheel-member parity, and isolated wheel
execution. Four publication-boundary tests also passed. At
2026-08-01T19:54:34+09:00, three independent read-only AI audits each reported
P0/P1/P2 as 0/0/0.

The local macOS full suite discovered all 1,163 tests and completed in
587.892s with 55 skips. It was not green: five failures and six errors were
confined to unchanged KP1979 V3 control-freeze host tests involving Darwin
directory revalidation and an AF_UNIX path-length limit. No new preflight,
static-loader, package, policy, source-contract, evidence-prerequisite, or
publication-boundary test failed.

At 2026-08-01T20:15:19+09:00, public Linux CI run `30696751707` succeeded at
exact implementation head `8cdaaa29c03d535d9590958194a3de31d0291797`.
All three jobs used exact Node 24.18.1, passed Quicknet, Ruff, formatting of
all 190 files, zero-error Pyright, all 1,163 tests with 22 skips, both
distribution builds, and the isolated installed-wheel verifier. Full-suite
times were 845.198s on Python 3.11, 954.779s on Python 3.13, and 912.584s on
Python 3.14. This closes the public-CI gate for the implementation commit
without changing any authorization, execution, access, or result state.

No research or protected source request was made. No external source byte,
receipt, pass, observation, source-link/no-link result, join, transcription,
translation, decipherment evidence, submission, or prize result exists. The
loader proves only package-local agreement with compiled identities; it does
not authenticate the package, satisfy frozen strict V1, grant authority,
validate a runtime, or permit source access.

## 2026-08-02T02:36:40+09:00 — V2 compatibility wrapper frozen source-free

Three independent read-only AI audits compared two ways to resolve the
frozen-V1 canonical-byte conflict: re-freezing the affected parent chain and
adding a narrow successor wrapper. Re-freezing would require a multi-artifact
digest cascade across the source registry, source contract, four dynamic
schemas, artifact schema-set, custody contract, and exact authority bindings.
The narrower safe checkpoint is a V2 wrapper that incorporates V1 by raw hash
and supersedes only the conflicting static resolver rule.

The new
[V2 compatibility wrapper](SOURCE_REPORTED_LINK_STATIC_RESOURCE_COMPATIBILITY_PROFILE_V2.md)
and Draft 2020-12 `const` schema are canonical, exact-byte public artifacts.
They bind the historical raw and canonical re-encoding identities of exactly
two ordered resources. The canonical bytes are verification canaries only;
they cannot replace the historical identity, be written back, or be selected
or extended by a caller. All unlisted V1 rules and all other resource
canonical checks remain unchanged.

The wrapper is individually selected into the wheel and the schema is
included by the existing schema package rule. The post-build verifier now
checks both resources separately from the historical exact-14 loader surface.
The V1 loader, its six static identities, and its permanent
`strict_v1_resolver_eligible=False` state are unchanged. The wrapper declares
that no V2-aware resolver implementation is present and that packaging does
not activate authority, runtime, or source access.

The first final-candidate audit caught and blocked a same-ID canonical-profile
redefinition and a whole-resolver-order replacement, plus narrower
self-cycle, validation-mode, and documentation ambiguities. All were
corrected before commit. The final three independent read-only AI audits
reported P0/P1/P2 as 0/0/0; this is engineering review, not human or external
scientific review.

At 2026-08-02T03:02:12+09:00, source-link validation passed 91/91 and the V2
wrapper set passed 12/12. Ruff, 191-file formatting, and locked Pyright passed;
the full Linux suite passed 1,175 tests with 19 skips in 1,060.149 seconds.
Fresh sdist/wheel builds and isolated installed-wheel verification passed,
all 223 local Markdown links resolved, and the staged secret scan found zero
new findings. The complete tracked tree and 66-commit history retain four
reviewed scanner findings, all the already-public fixed test vector duplicated
between the frozen V1 custody contract and its `const` schema. Exact Node
24.18.1 CI evidence was pending publication.

Public CI run `30711703762` then succeeded at exact implementation head
`edeb6ebe80215f2bf9fa287ae8f058a3d32f33f5`. Python 3.11, 3.13, and 3.14
passed Quicknet 6/6 in 527.822667 ms, 528.849668 ms, and 441.521465 ms and
passed all 1,175 tests with 22 skips in 866.169s, 948.759s, and 642.752s.
Every job used exact Node 24.18.1 on Linux/x64, passed Ruff, 191-file format,
zero-finding Pyright, both builds, and the isolated installed-wheel V2
verifier.

Next: implement and independently review a dedicated exact-16 V2-aware
installed resolver with a distinct package-local conformance state. Only
after that may work continue on the source-free runtime manifest,
distribution, trust root, custody/recovery machinery, parser/evaluator, and
typed authenticated one-attempt authority boundary.

No research source was requested or opened. No protected byte, receipt,
observation, source-link/no-link result, join, translation, decipherment,
submission, prize eligibility, or prize result exists.

## 2026-08-02T10:12:22+09:00 — V2 exact-16 installed resolver implemented source-free

The new
[V2 exact-16 installed static resolver](SOURCE_REPORTED_LINK_STATIC_RESOLVER_V2.md)
is a sidecar to the unchanged V1 API. The shared private traversal now accepts
an internally compiled resource tuple: V1 supplies its frozen exact 14 and V2
supplies those 14 plus the wrapper and const schema. V2 therefore reads all 16
files in one pinned descriptor traversal rather than combining two separate
package snapshots.

The V2 decoder requires each raw identity before strict JSON. It applies the
frozen raw/canonical inequality and canonical size/hash canary only to the
ordered historical pair, never returns the canonical projection, and requires
canonical bytes for the other 14 resources. The resolver repeats every V1
schema, parent, roster, schema-set, and digest check, then validates the V2
const schema, exact-16 order, validation modes, binding pointers,
incorporation, one-token composition, supersession rules, exact-eight names,
self-cycle exclusion, and frozen nonclaims.

The immutable result is explicitly
`validated_package_local_exact16_only`. V1 remains exact 14 with the same
snapshot, blockers, representation, and `strict_v1_resolver_eligible=False`.
V2 also keeps strict V1 eligibility false and records authority not authorized,
runtime not validated, source access not performed, result not established,
and external activation blocked. The wrapper's historical
`not_implemented`/false fields remain frozen rather than being rewritten.

The build verifier now checks the resolver module in the wheel and executes
V1 → V2 → V1 and V2 → V1 → V2 in fresh isolated processes. Pre-publication
Linux validation completed at 2026-08-02 11:17:04 JST. The focused V1, V2,
wrapper, and publication set passed 43/43 in 4.848 seconds; Ruff, formatting
of all 193 files, and locked Pyright passed with zero findings. The complete
suite passed 1,189 tests with 19 skips in 1,107.947 seconds. Fresh sdist and
wheel builds, both installed-wheel orders, archive safety, publication,
secret, and Markdown-link checks passed. The wheel contains 180 members and
the sdist 371, with no duplicate, case-colliding, unsafe, linked, special, or
forbidden credential-like member. Three independent final read-only AI audits
reported P0/P1/P2 as 0/0/0 after their findings were fixed. This is
engineering review, not external scientific review. Public CI evidence is
recorded below.

The source-link lane's next dependency order would be the missing dynamic
schemas, exact generic preflight closure, runtime manifest/distribution,
bootstrap trust, custody/recovery, acquisition, parser/evaluator, and typed
one-attempt authority. That order is not the project's global next priority.
The adopted efficiency audit rates further generic verifier infrastructure as
low immediate information gain and the roadmap already defers it until a real
experiment exposes a specific need. A read-only inventory also found a future
runtime release blocker: the embedded deletion-record schema requires
`pre_source_empty_workspace_cleanup` in its pre-source branch while omitting
that value from the same property's outer enum. The frozen V1/V2 bytes remain
unchanged, and that schema must not be copied into a new freeze without a
separate source-free successor correction.

The highest-value next source-free slice is therefore a narrow draft
numeral/metrology functional-anchor protocol using the existing hypothesis
schema: fixed independent data roles, holdouts, matched nulls, thresholds,
and kill rules, with no source values or execution. It must remain `draft`
until separately registered; it is not evidence or a preregistration receipt.
No source access is authorized by this checkpoint.

No research or protected source was requested or opened. No protected byte,
receipt, pass, observation, source-link/no-link result, join, transcription,
translation, decipherment evidence, submission, prize eligibility, or prize
result exists.

Public
[CI run 30728985001](/megu0xxx0x/indus-open-benchmark/actions/runs/30728985001)
subsequently succeeded at exact V2 resolver implementation head
`c469668ada6466faf5add471254822e635d987a9`. Python 3.11, 3.13, and 3.14
used exact Node 24.18.1 on Linux/x64 and passed Quicknet 6/6 in
555.070931 ms, 555.662477 ms, and 530.85453 ms. The three complete suites
each passed 1,189 tests with 22 skips in 866.692s, 1,016.315s, and 918.882s.
Every job passed Ruff, accepted all 193 files as formatted, reported zero
Pyright errors/warnings/information messages, built the sdist and wheel, and
passed the isolated installed-wheel forward/reverse V2 verifier.

## 2026-08-02 — Numeral/metrology functional-anchor draft fixed source-free

**Final draft revision/checkpoint:** 2026-08-02 12:48:48 JST

The machine-readable
[numeral/metrology functional-anchor protocol V1](NUMERAL_METROLOGY_FUNCTIONAL_ANCHOR_PROTOCOL_V1.md)
now records the highest-information next experiment under the existing
hypothesis schema. It asks only whether one positive additive score over one
to eight disjoint token/allograph classes can predict exactly one independent
`count`, `mass`, or `capacity` family in one canonical unit.

The final source-free design separates the approved transcription `X`, hidden
target `Y`, value-free target-eligibility commitment `E`, canonical context
and frozen documentation/measurement nuisance tuple `C`, all-side
physical-original unit `F`, transitive leakage/dependence
superfamily `G`, sealed mapping `H`, and controls `N`. All sides of one
original become one ordinal input; casts/impressions remain separate `F` but
join the same `G` where related. Known mold/template, exact-sequence,
production-batch, workshop, locus, and assemblage dependence also closes in
`G`. One `E=true` `F` is selected per `G` without targets or model scores.

The draft requires four disjoint domain cells selected without numeric target
values: site, then period among the remainder, medium among the next
remainder, and object type among the final remainder. Each cell requires at
least 20 independent `G`, their sealed union at least 80, and the
development/validation complement at least 80, so initial eligibility
requires at least 160. Context axes use frozen mutually exclusive vocabularies
and alias/descendant closures. After the complete `E/F/G/M_G/C` inventory digest
is fixed, one externally verifiable unpredictable nonce selects the tuple;
retry and resalting are forbidden.

The provenance policy either restricts every transcription/measurement to one
prespecified regime or requires complete canonical documentation and
measurement nuisance fields. The primary gates are sealed Spearman
`rho >= 0.40`, paired improvement of at least 0.10 over total-token and
distinct-token length proxies, a 10,000-`G` bootstrap rho lower endpoint above
0.20 and paired length-difference lower endpoint above zero, each domain cell
`rho >= 0.20`, and at least four score and target levels. A 99,999-run frequency/prevalence-
matched token-specificity control uses a descriptive tail fraction, not an
inferential p value. A separate 99,999-run no-association null permutes whole
`G` targets only within frozen full-context-plus-nuisance strata, with at
least 80% and 64 holdout `G` movable; both controls must exceed `q0.99` and
their respective 0.01 tail gates.

The prospective source frame, ordering, start, and cutoff are fixed before
opening `H`, together with a design-stage sensitivity/power rationale; 20 new
`G` is only an evaluability floor. Each prospective unit and any associated
information must first become source-bound and available strictly after
immutable model/policy/prediction-algorithm freeze; earlier-available material
is historical. Every qualifying later unit at cutoff is included. With
targets sealed, relations are reclosed across historical and incoming `F`.
Attachment to one
historical `G` is absorbed and excluded; a bridge across two historical `G`
or a historical partition invalidates the benchmark; incoming-only relations
close prospectively. One integer ordinal score is committed per new `G`.
Sample size, complete outputs, score variation, and full-context-plus-nuisance
support must pass before targets are revealed, and no numeric reading or refit
is allowed. A passing label then requires four target levels, `rho >= 0.40`,
length-baseline improvement of at least 0.10, paired bootstrap rho and
length-difference lower gates, and a 99,999-run stratified permutation
`p <= 0.01`. Prospective bootstrap/permutation streams have distinct labels;
the future typed evaluator must freeze exact seed and generator semantics.

Exactly three kill criteria cover generalization, matched-control, and
completed prospective failure. Technical invalidity, confirmatory failure,
prospective insufficiency, prospective failure, and the final narrow label
have phase-safe terminal precedence, so later insufficiency cannot mask a
failed holdout. The earlier
provisional random 50/25/25 split was rejected during design review because
it conflicted with strict domain holdouts; only the disjoint cell design is
retained.

The JSON validates against the existing hypothesis schema, is selected into
the wheel, and has focused semantic tests. It remains `draft` with
false/null registration fields, empty scope IDs, sign mappings, predictions,
evidence, exceptions, and observation references, and zero confidence for
the sole prospective claim, which has exactly three falsification criteria.
The schema does not provide typed metric or evaluator enforcement, so
decision-critical fragments and the complete payload digest are test-locked.
A future
registered executable version still needs typed split/evaluator/result
contracts, exact custody, an external receipt, and separate execution
authority.

No research or protected source was requested or opened. No real source ID or
value, artifact ID, sign, sequence, transcription, measurement, target,
realized split assignment, instantiated prediction, evidence, result,
execution, submission, prize eligibility, or decipherment claim was created.

Public
[CI run 30733414007](/megu0xxx0x/indus-open-benchmark/actions/runs/30733414007)
succeeded for exact implementation commit
`a92593c456e616ad6d81dec2e2a4c0e8b73999b2`. Python 3.11, 3.13, and
3.14 used exact Node 24.18.1 on Linux/x64 and passed Quicknet 6/6 in
525.998623 ms, 520.628547 ms, and 556.612795 ms. Their complete suites each
passed 1,200 tests with 22 skips in 832.204s, 954.108s, and 912.837s. Every
job passed Ruff, accepted all 194 files as formatted, reported zero Pyright
errors/warnings/information messages, built the sdist and wheel, and passed
the installed-distribution verifier, including packaged protocol/schema byte
parity and schema validation.

## 2026-08-02 — NMFA worldwide source audit and candidate gate

The worldwide
[NMFA target-source audit](NMFA_GLOBAL_TARGET_SOURCE_AUDIT_2026-08-02.md)
found no verified reusable public source that currently joins complete
transcription X, physical identity F, dependence G, canonical context C,
complete base E, and one direct numeric Y at the required scale. Public access
was not treated as reuse permission, blocked sources were not scraped, and no
institution was contacted.

The source-free
[NMFA value-blind preregistration gate](NMFA_VALUE_BLIND_PREREGISTRATION_GATE_V1.md)
now packages a closed plan, evaluator bundle, protected-manifest schema,
private-report schema, typed evaluator, adversarial synthetic tests, and an
installed-distribution verifier. It binds the exact ordered source/F/C/prior-
exposure inventory before protected X or Y access; later X/Y seals must cover
that same F roster. Base E remains separate from whole-G exclusion, every
applicable closed reason is retained, N2 is a universal feasibility condition
rather than a split filter, and reports have no public-summary surface.

Independent review closed three design defects before freeze: post-value
roster/C selection, asymmetric X auditing and originator overlap, and a
circular N1 chronology. The corrected N1 order is draw-free support
feasibility before holdout X, prediction freeze after X, sampled-assignment
freeze from the externally bound pre-Y chain, then holdout Y. The immutable
draft parent V1 is not rewritten; the gate explicitly records its stricter
complete-set E-reason refinement.

Focused adversarial tests, canonical and Draft 2020-12 validation, lint,
formatting, type checks, differential tuple/N2 checks, distribution builds,
and isolated installed-wheel verification pass. This is synthetic method
evidence only. A pass is only
`CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW` and establishes no external time,
rights, custody, role independence, scientific result, decipherment, or prize
eligibility.

Operational work remains blocked. The next implementation slice is separate
deterministic signed `PREMETADATA_READY` and `PREVALUE_READY` preflight
evaluators. Before external registration, the project also needs one complete
typed NMFA execution bundle covering split/primary-F selection, model parsing
and scoring, primary/length/cell/bootstrap metrics, N1/N2, terminal precedence,
prospective evaluation, and receipt schemas. Only after those exist may an
authorized rights/custody review of one source candidate be considered; no
protected source access or real run is authorized now.

## 2026-08-03 — NMFA signed activation preflight companion V1

**Checkpoint recorded:** 2026-08-03 00:10 JST

The source-free
[NMFA activation preflight companion V1](NMFA_ACTIVATION_PREFLIGHT_V1.md)
is now implemented and frozen as an additive successor to the immutable draft
parent protocol and V1 candidate gate. It defines closed `PREMETADATA` and
`PREVALUE` requests, a separately supplied trust-profile contract, private
reports, a pure evaluator, an exact installed-resource bundle, synthetic
adversarial tests, and isolated-wheel verification. The parent protocol, gate
plan, gate evaluator bundle, and gate schemas were not edited.

The signing flow uses the canonical request subject with the `signatures`
array omitted. The public message builder accepts only an unsigned request;
the completed request must contain exactly three PREMETADATA signatures or all
six PREVALUE signatures. The evaluator uses exact-version Ed25519 support and
prechecks canonical unpadded base64url, 32-byte public keys, 64-byte
signatures, canonical scalar `S`, and nonidentity prime-subgroup membership of
both public point `A` and signature point `R`. This closes the low-order
identity-forgery class accepted by a library-only verification path. Missing
Ed25519 backend support is normalized to a fixed package failure.

The machine contract deliberately narrows claims that the installed evaluator
cannot establish. It verifies consistency only within the supplied roster,
not completeness against an external source universe. It rederives
metadata-known `Epre` reasons and validates only the declared pre-X relation
edges; complete `R0` and transitive `Rpre` remain future executor/wrapper work.
The access ledger is only an aggregate declared head/counter chain, authority
and rights are signed declarations with opaque evidence commitments, the
metadata channel is a policy requirement rather than verified provider bytes,
and opaque identifier origin is not proven. The expected trust digest is
caller supplied and its origin is explicitly unauthenticated. Prize submission
is outside this preflight and fixed to not applicable.

The chronology now freezes both value barriers in
`PREPARED_LOCKED_NOT_ARMED_NOT_RELEASED`, verifies and consumes the PREVALUE
package through a future permanent registry, and only then permits a joint
compare-and-swap to `ARMED_NOT_RELEASED`. The installed companion performs no
registry mutation or source/value access. It retains exactly five mandatory
blockers: typed execution bundle, external trust, external time, permanent
consumption registry, and activation wrapper. Therefore even a valid synthetic
request remains blocked and cannot authorize metadata, X, Y, execution, or a
ready receipt.

Validation completed on the Linux reference environment: Ruff lint and format
checks passed, Pyright reported zero errors or warnings, 38 focused preflight
and distribution-policy tests passed, all three installed-wheel verifiers
passed, and the complete repository suite passed 1,267 tests with 19
environment-specific skips in 1,159.620 seconds. Independent Ed25519 arithmetic
comparison found no mismatch across randomized addition, scalar,
subgroup-membership, generated-key/signature, and RFC-vector checks. Trivy
reported no high/critical vulnerability, secret, or configuration finding;
Semgrep reported no relevant finding; all changed and new files passed secret
scanning. Four full-tree secret-scan alerts remain known false positives in
unchanged public fixed test vectors.

The next project slice is the complete source-free typed execution bundle
`E`, not source access. It must close nonce and split selection, primary-F
selection, X/Y parsing, the single fixed model and scorer, exact rational and
rank statistics, bootstrap, N1 matching/unranking, N2 permutations, terminal
precedence, prospective evaluation, resource limits, receipt schemas, and
positive/adversarial vectors. After independent audit, freeze a new
operational preflight bundle `P` that binds `E`, then an external activation
wrapper `A`; do not patch the five null bindings in this V1 companion.

No real source identifier, inventory, transcription, target, prediction,
result, operational key/signature, registration, execution, submission,
prize eligibility, reading, translation, or decipherment claim was created.

## 2026-08-03 — NMFA source-free selector core V1

**Checkpoint recorded:** 2026-08-03 02:12 JST

Implemented the first additive execution component for NMFA without changing
the immutable parent protocol, candidate gate, or activation preflight. The
new selector core validates a closed canonical structural inventory, rederives
the exact immutable-gate eligible projection digest against a separately
supplied expected digest, derives a frozen-roster component identity,
normalizes a declared nonce without claiming its provenance, exhausts all
sequentially disjoint domain tuples, enforces universal N2 support, selects the
immutable minimum split ticket, chooses one target-blind primary F per G, and
assigns the complement deterministically to development and validation.

The exact-const plan/schema, evaluator bundle, inventory schema, protected
declared-assignment schema, pure
module, adversarial tests, and installed-wheel verifier are source-free. The
synthetic 160-G fixture agrees exactly with the immutable gate oracle and
produces 80 holdout, 54 development, and 26 validation assignments. The
assignment suppresses protected values in `repr`, records only the nonce
digest, never the raw nonce, and marks digest/claim/identifier/nonce origin,
one-use, realized split, and scientific-result assurances false.

Focused selector tests (22), exact schema validation, Ruff, formatting,
Pyright, and all four isolated-wheel verifiers pass. The reference Linux full
suite passed 1,289 tests with 19 expected skips and no failures or errors.
Changed-file leak scanning, high/critical vulnerability and misconfiguration
scanning, and focused Python security analysis are clean. Publication and
public CI remain pending at this checkpoint.

This is explicitly `development_component_not_complete_E`. The callable
permits repeated declared-nonce analysis and realizes no split. It proves no
external digest or claim-binding origin, nonce provenance/one-use,
relation/source completeness, access authority, execution, scientific result,
reading, decipherment, or prize eligibility. Next implement the separate exact
X/Y/statistics and deterministic bootstrap/N1/N2 components, then
confirmatory/prospective orchestration and a final audited `E` bundle.
