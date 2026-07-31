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
