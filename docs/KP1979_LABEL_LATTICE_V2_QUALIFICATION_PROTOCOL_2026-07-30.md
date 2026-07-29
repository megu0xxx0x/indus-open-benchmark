# KP1979 V2 label-lattice qualification protocol

Status: pre-execution protocol — 2026-07-30. No combined V2
control-detector execution or result exists at this checkpoint.

## Decision fixed before execution

The `two-column-label-lattice-v2` detector and the
`kp1979-label-lattice-synthetic-control-v2` control were developed on separate
branches from a common public base. The detector branch (`D`) was frozen before
the control branch (`C`). That order does not satisfy the required
control-before-detector freeze.

This failure is terminal for V2 qualification. Regardless of the raw
synthetic-control status:

- the overall terminal status is `not_qualified`;
- `advance_to_provisional_extraction` is false; and
- V2 authorizes no real-source, provisional-extraction, or future-evaluation
  execution.

The raw control report remains useful diagnostic evidence and will be recorded
separately from the overall decision. A raw `qualified` status, if produced,
cannot override the failed freeze-order gate.

A post-freeze adversarial check also exposed a periodic two-tier non-label
confound that the frozen detector can propose as label structure. It was not
used to alter either frozen parent or to rewrite the control. It is a separate
deployment block, so V2 cannot be promoted as a reference detector even if its
raw control report passes.

## Frozen public boundary

The exact commits, module bytes, worker interface, detector artifact
commitment, lock file, control identity, decision gates, and nonclaims are
bound by the
[machine-readable execution plan](../benchmark/kp1979-label-lattice-synthetic-control-v2-execution-v1.json).
The corresponding
[execution-plan schema](../schemas/kp1979-label-lattice-synthetic-control-v2-execution.schema.json)
and
[result schema](../schemas/kp1979-label-lattice-synthetic-control-v2-result.schema.json)
are closed Draft 2020-12 contracts.

The integration commit must be an exact two-parent merge with `C` first and
`D` second. Before execution, the runner requires a clean worktree, verifies
the parent ancestry and frozen file digests, and requires the same integration
commit to be the public `main` reference it has fetched. The detector artifact
must match its frozen digest and member boundary.

The runner verifies the loaded parent-module paths and bytes after import.
Code execution before those post-import checks is not excluded and is not
reported as excluded.

Git establishes exact bytes and ancestry only. It does not prove trusted freeze
time, confidentiality, blindness, custody, independent authorship,
organizational independence, or absence of cross-access.

## One-shot process protocol

The official run has one valid evaluator call and no detector-control preflight.
It expects 25 adapter invocations: 19 fixed synthetic cases plus two calls for
each of three metamorphic relations.

For every invocation, the runner:

1. starts a fresh child process from the exact frozen detector artifact;
2. gives it a distinct empty working directory, a minimal allowlisted
   environment, fixed resource limits, and bounded standard-output captures;
3. sends only the PBM bytes, width, height, scan bands, and worker-interface
   version, without a case identifier, truth, class, or evaluation order; and
4. validates a closed, canonical response with bounded, sorted, unique
   predictions and declared abstention codes.

The result records the actual successfully started child-process count.
Fresh-process verification passes only when that count, the adapter invocation
count, and the expected count are all 25. A timeout, crash, malformed response,
unexpected output, invalid response to a structurally valid input, or failure
to start a child is converted into a fail-closed algorithm-mismatch result
rather than an accidental rejection pass.

The canonical attempt marker is created before the first adapter call. The
result is written once with atomic no-replace publication. No retry is allowed
after any control invocation. This is a protocol rule and a locally checked
state boundary, not a technical guarantee that the owner cannot delete local
state; `single_execution_technically_enforced` therefore remains false.

Each invocation is process-separated, but the protocol provides no operating
system network namespace or filesystem namespace. Process separation is not
evidence of confidentiality, blindness, independence, or lack of prior access.

## Result interpretation

The result must preserve two different facts:

- `control_report.status` is the raw result of the frozen synthetic control;
  and
- the overall status remains `not_qualified`, with advance false, because the
  freeze-order and post-freeze deployment gates fail.

The report cannot claim accepted reference geometry, evaluation admissibility,
real accuracy, full-row segmentation, row identity, identifier or code
transcription, sign sequences, reading direction, language, meaning,
translation, decipherment, prize eligibility, or prize submission.

The run reads synthetic PBM inputs only. It does not open the real KP1979
source, any future-evaluation value or pixel, PDF page 78, the earlier
57-page proposal assignment, the MTAAC holdout, ORACC prospective material, or
any other reserved source.

The declarations of process separation and mutual nonexposure are retained as
declarations only. Confidentiality, blindness, independence, organizational
independence, filesystem or network isolation, custody, trusted time,
independent public-remote attestation, and absence of cross-access all remain
unverified.

## Controlled next step

After the integration source and this protocol are published, the exact V2
command may run once and its schema-valid diagnostic result may be published
without changing the terminal decision. V2 must then remain immutable and
must not be rerun, retuned, or used for extraction.

Any successor must use a new algorithm and control identity. Its synthetic
control must be frozen and published before detector implementation, and it
must include independent positive renderers plus explicit periodic-rule,
table, box, decoration, and non-label confounds. That successor is a new
experiment, not a repair of V2 and not evidence of decipherment.
