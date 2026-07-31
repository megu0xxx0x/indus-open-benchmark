# KP1979 V3 non-operational control source bundle

The source-only builder is published at commit
`2e81afef7e188f9dd70059c60b9f1123019b3753`. The code exists, but no real
control bundle, freeze artifact, or artifact digest has been generated or
retained. Test-created subjects were ephemeral verification inputs, not a
freeze, dispatch, execution, or custody event.

This checkpoint is not a decipherment result. It supplies a deterministic
packaging and verification boundary for already-public controller-side source.
It does not create the still-absent operational components needed to run the
control.

## Purpose

The builder closes one source roster so a later, separately authorized process
can package the same bytes under a strict canonical representation. It includes:

- one canonical manifest;
- the project license and the manifest schema;
- the package initializer and the builder itself;
- 12 controller-side modules for the canvas, evaluator, generator, grammar,
  PRF, protocol, Quicknet verifier, two renderers, sandbox, one-shot state, and
  worker wire contract; and
- the exact 20-file vendored Noble/Quicknet verification closure.

There are exactly 36 payload files and 37 regular-file archive members after
adding `MANIFEST.json`. The roster is fixed in source and sorted by ASCII path.
An unlisted source file is never added. The presence of a controller, detector,
detector-freeze, integration, integration-freeze, or runner module causes the
source build to fail closed.

## Closed manifest contract

The compact ASCII JSON manifest ends with one LF, rejects duplicate or unknown
keys, and fixes these meanings:

| Field | Closed value or rule |
| --- | --- |
| `format` | `kp1979-v3-control-bundle-manifest` |
| `version` | `1` |
| `source_commit` | Exactly 40 lowercase hexadecimal characters supplied to the builder |
| `protocol_identity` | `kp1979-v3-closed-answer-free-protocol-v1` |
| `control_identity` | `kp1979-label-lattice-synthetic-control-v3` |
| `target_algorithm_identity` | `two-column-glyph-lattice-v3` |
| `worker_identity` | `kp1979-label-detector-v3-worker-v1` |
| invocation counts | 32 cases, 16 metamorphic endpoints, 48 total |
| `source_only` | `true` |
| `non_operational` | `true` |
| `target_round_selected` | `false` |
| `detector_component` | `absent` |
| `integration_binding` | `absent` |
| `payload` | Exact ordered 36-entry path, byte-size, and SHA-256 roster |

`source_commit` is a manifest label and equality check. The builder does not
query Git, prove that the supplied identifier names the checkout bytes, verify
a signature, establish trusted time, or provide independent custody. Those are
external responsibilities.

## Canonical bytes and bounded verification

The representation is deliberately narrower than general tar or gzip:

- The tar stream is canonical USTAR with ASCII-sorted regular files only,
  mode `0644`, UID/GID zero, empty owner names, mtime zero, canonical octal
  fields and checksums, zero padding, and exactly two terminal zero blocks.
  Links, devices, FIFOs, PAX records, non-ASCII paths, traversal, duplicates,
  reordered members, and trailing bytes are rejected.
- The gzip stream has one fixed header with mtime zero, no filename, and OS
  byte 255. A project-owned stored-DEFLATE encoder avoids zlib-version output
  differences. Concatenated streams, noncanonical block framing, bad CRC or
  size, and trailing bytes are rejected.
- Limits are 512 KiB per source member, 64 KiB for the manifest, 2 MiB for the
  uncompressed tar, and 16 MiB for the complete subject.
- Verification checks the exact roster, closed manifest, every payload size
  and SHA-256, then reconstructs canonical tar and gzip bytes and requires
  byte-for-byte equality.

The verification summary returns only the expected source-commit label,
member and payload counts, uncompressed size, and subject SHA-256. Returning
that object does not attest to execution, isolation, source authenticity,
custody, freshness, single use, or publication.

## Source and output safety boundary

Source reads are descriptor-relative from the builder's fixed checkout root.
The implementation rejects symlinked, group- or other-writable, executable,
empty, oversized, multi-link, nonregular, or ownership-mismatched payloads;
revalidates source ancestry, child directories, leaf namespace entries, and
fingerprints around each read; checks forbidden-module absence before and after
loading the roster; and attempts best-effort descriptor closure on failure.

The CLI accepts one absolute output path with the exact basename
`kp1979-v3-control-bundle.tar.gz`. The final parent must be owner-only mode
`0700`. Output is staged as owner-only mode `0600`, fully written and synced,
hard-linked into the final name without replacement, revalidated by inode and
bytes, reduced to one link, and parent-synced. An existing destination of any
type is not overwritten. On failure, cleanup rechecks that the output name
identifies the builder-owned inode and otherwise preserves an unknown entry.
This is best effort and not atomic against same-UID or root namespace
replacement.

Stable public errors contain a code but no local path or parser detail. The
command-line entry point is silent on both success and ordinary failure.
Unexpected ordinary exceptions collapse to the same failure return.
`BaseException` propagates.

These checks reduce accidental mutation and common namespace races. They are
not an isolation or custody boundary against a concurrent process with the
same UID, root, filesystem-control privileges, or the ability to replace
state between checks. The no-replace protocol also does not prove who created
or retained an output after the builder returns.

## Exact CLI environment gate

The command-line gate accepts only CPython 3.12.11 invoked through the exact
`-s -B -m indusbench.kp1979_v3_control_freeze` form. It requires exactly eight
environment entries:

- `LANG=C.UTF-8`
- `LC_ALL=C.UTF-8`
- `PATH=<the exact CPython directory>:/usr/bin:/bin`
- `PYTHONHASHSEED=0`
- `PYTHONNOUSERSITE=1`
- `SOURCE_COMMIT=<40 lowercase hexadecimal characters>`
- `SOURCE_DATE_EPOCH=0`
- `TZ=UTC`

The exact CPython 3.12.11 runtime is installed in the local qualification
environment. Its installation and the passing runtime test do not mean that a
real control bundle was created.

The public Python build and verification functions are useful for deterministic
byte testing, but calling them does not establish the exact CLI environment or
produce an attestation.

## Verification evidence

Local evidence for commit
`2e81afef7e188f9dd70059c60b9f1123019b3753`:

- the complete 63-test focused control-bundle suite passed under exact
  CPython 3.12.11 in 2.017s;
- all 1,047 repository tests completed in 1002.306s with 19
  environment-specific skips;
- Ruff lint passed, Ruff formatting accepted all 181 checked files, and
  Pyright reported zero errors, warnings, or information messages;
- sdist and wheel builds succeeded;
- Gitleaks and public-boundary checks passed; and
- two independent read-only source audits each reported zero blockers, zero
  major findings, and zero minor findings.

Public CI run `30615528575` succeeded in 16m23s at exact source commit
`2e81afef7e188f9dd70059c60b9f1123019b3753`:

- Python 3.11 passed Quicknet 6/6 in 520.428152ms and all 1,047 tests with 22
  environment-specific skips in 848.443s; its job completed in 14m35s.
- Python 3.13 passed Quicknet 6/6 in 537.327487ms and all 1,047 tests with 22
  environment-specific skips in 943.488s; its job completed in 16m13s.
- Python 3.14 passed Quicknet 6/6 in 410.523122ms and all 1,047 tests with 22
  environment-specific skips in 675.542s; its job completed in 11m48s.

Every matrix job passed Ruff, accepted all 181 checked files as formatted,
reported zero Pyright errors, warnings, or information messages, and built
both the sdist and wheel.

Passing tests and source review support the implementation contract. They are
not independent custody, an execution receipt, a scientific result, or a
security proof against privileged actors.

## Attestation and runtime limitations

Several boundaries remain unresolved:

- The evaluator still accepts a caller-supplied invoker. Its aggregate result
  alone therefore cannot attest that the exact sandbox path ran.
- A future official runner must internally construct and own the exact
  `SandboxedWorkerInvoker`; it must expose no invoker or invoker-factory
  injection surface and must bind process and invocation counters to the
  one-shot state transition.
- Git authenticity, commit-to-checkout equality, trusted time, non-deletion,
  independent custody, and post-build artifact retention remain external.
- The source and output race checks do not defend against same-UID or root
  control and cannot eliminate every check/use window.
- Quicknet cleanup is bounded best effort. A second or repeated hostile
  interrupt during cleanup can still prevent termination or reaping. The
  sandbox subprocess path also requires explicit `BaseException` cleanup
  hardening before an official runner.
- Portable semantic CI is pinned to exact Node 24.18.0. The existing host
  wrapper is pinned to end-of-life Node 18.19.1 for qualification only. A
  supported host-runtime policy remains unresolved.

The control-bundle builder does not solve any of those problems.

## Explicit non-results

At this checkpoint:

- no real control bundle, freeze artifact, or subject digest has been
  generated or retained;
- no freeze has been dispatched;
- no target round has been selected, reserved, fetched, or accessed;
- no suite seed, schedule, generated case, truth, request, worker response, or
  oracle has been instantiated for a real run or persisted;
- no detector component, integration binding, controller, official runner, or
  official execution attestation exists;
- no worker or detector has run;
- no protected or real source has been opened for this control;
- no C3 result, real-source result, decipherment evidence, translation,
  public claim authorization, or prize evidence exists; and
- KP1979 V2 remains retired and immutable.

## Next controlled gates

Before any official execution, the project must separately resolve a supported
host runtime, harden sandbox interruption cleanup, implement an injection-free
official runner, and define external commit/authenticity and custody controls.
Those source tasks do not themselves authorize building or dispatching a
freeze, selecting or fetching a target, executing a worker or detector,
accessing real source material, or making a decipherment or prize claim.
