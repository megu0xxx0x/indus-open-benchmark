# KP1979 V3 sandbox cleanup hardening

Status: local pre-publication draft at `2026-07-31T18:53:13+09:00`.

This documentation draft is based on source commit
`cd583fb12b12a80d132c80e8a3465e53f5c3151a`, whose parent is public main
`0f120e813dd449dfdfd499e39fa154a804a6b77a`. The commit changes only the
sandbox source and its tests. Its exact binary diff SHA-256 is
`7069fbae6e9749c401f00ef35b5e5cc8c74d0e262f00626c95d4a7192d71115d`.
That value fingerprints the source-commit diff bytes; it is not a signature,
trusted timestamp, custody record, runtime receipt, or attestation.

This work hardens failure cleanup for the existing
[`SandboxedWorkerInvoker`](../src/indusbench/kp1979_v3_sandbox.py). It does not
create an official runner, run the control, or provide scientific evidence.
The evaluator still accepts a caller-supplied invoker and remains a
non-attestation.

## Post-start cleanup state machine

Once the main sandbox-client `Popen` returns, a timeout, interruption during
client communication or the initial pre-output status access, a missing
initial status, a negative initial status, or another abnormal path before
output or handshake access executes these bounded stages in order:

1. **A — unit kill dispatch.** Start `systemctl --user kill
   --kill-whom=all --signal=SIGKILL` as a separate closed-argument helper in a
   new process group. Wait for it with the fixed unit-kill timeout.
2. **B — client process-group kill.** Independently send `SIGKILL` to the main
   client's process group. `ProcessLookupError` is acceptable; other failures
   or interrupts are remembered without skipping later stages.
3. **C — conditional unit retry.** If A did not return status zero, dispatch
   one more bounded unit kill after the client-group kill.
4. **D — bounded drain.** Call `communicate` on the main client with the fixed
   cleanup timeout.
5. **E — bounded reap.** Call `wait` with the fixed cleanup timeout, then retry
   it once after a failure or interrupt. Treat the main client as reaped only
   when its return code is non-`None`.

Every later stage is attempted after an earlier ordinary error or
`BaseException`. The unit-kill helper also has explicit self-cleanup: its
process group receives up to two kill attempts, followed by bounded
`communicate` and bounded `wait` with one retry. Helper subprocesses never
increment the main-client counter.

A unit-kill helper exit status of zero is only an acknowledgement that the
`systemctl kill` command was dispatched successfully. It does not prove that
the service cgroup is empty, that every descendant stopped, that systemd
finished teardown, or that the official sandbox path ran. It is not custody,
isolation, or execution attestation.

## Result-release gates

A timeout may return the existing public `timeout` result and captured output
byte counts only when both conditions hold:

- the main sandbox client is reaped; and
- at least one A/C unit-kill helper returned status zero.

If either condition is missing, the invocation returns the existing redacted
`setup_failed` surface and reads neither output nor handshake. A negative main
client return code likewise enters the full A–E cleanup before any output or
handshake read. Normal nonnegative completion keeps the established bounded
output and canonical-handshake path.

Those gates limit what the parent reports; they do not turn a dispatch
acknowledgement into proof of cgroup emptiness. They also do not make repeated
hostile interruption safe.

## Exception precedence

The implementation preserves interruption identity across process, descriptor, and
temporary-resource cleanup:

- A primary `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, or other
  non-`Exception` `BaseException` is re-raised as the exact same object after
  bounded cleanup. A later cleanup interrupt does not replace it.
- If the primary fault is an ordinary `Exception`, the first cleanup
  non-`Exception` `BaseException` is retained by identity while every bounded
  cleanup stage continues, then is re-raised.
- Ordinary failures use the existing path-free, detail-free result vocabulary.
  A timeout whose cleanup cannot establish both required release conditions is
  deliberately collapsed to `setup_failed`, rather than reported as a cleanly
  terminated timeout.
- The first cleanup interrupt is retained; later interrupts do not replace it.
  Wait and helper-kill retries remain finite.

These rules prevent a cleanup fault from silently erasing the controlling
interruption. They are still bounded best effort. Repeated hostile interrupts
can defeat all finite attempts or leave a client, helper, or unit in an unknown
state.

Here, bounded means a finite attempt count plus explicit timeouts on
`communicate` and `wait`. It is not a hard real-time wall-clock bound on
`Popen` process creation, kernel scheduling, signal delivery, or filesystem
and other operating-system calls. In particular, the subprocess timeout starts
after process creation, so a stalled creation or kernel/filesystem operation
can exceed the nominal cleanup-timeout sum. The state machine constrains
attempts; it cannot promise a deadline against a stalled kernel or filesystem.

## Parent file and temporary-resource handling

Artifact, handshake, and bounded-output readers now use `O_NOFOLLOW` and
`O_NONBLOCK` where those flags exist. They require owner-safe regular-file
metadata, apply fixed byte limits, compare before/after fingerprints, and
close the descriptor explicitly. On the supported Linux path, `O_NONBLOCK`
prevents the tested FIFO open/read path from blocking before metadata
rejection. It is not a wall-clock bound on arbitrary device or kernel
behavior.

Exclusive writes, file reads, and temporary-directory teardown record primary
and cleanup faults separately. A primary non-`Exception` interruption wins by
identity. An ordinary resource fault yields to a cleanup non-`Exception`
`BaseException`, while ordinary cleanup follows the fixed resource-specific
normalization. These controls reduce descriptor and temporary-path ambiguity
but do not defend against every same-UID or privileged race.

## Stable public contract and counters

The externally supported contract remains unchanged:

- `SandboxedWorkerInvoker` retains its constructor and `__call__` signatures;
- `SandboxInvocationResult` retains its fields;
- existing dispositions and failure codes are reused; and
- ordinary public failures remain redacted.

`started_process_count` increments only after the main sandbox-client `Popen`
returns. Pre-start failures and unit-kill helpers do not increment it. A
post-start ordinary failure is reported with `process_started=true` through
the existing result surface. `verified_invocation_count` increments only after
the exact canonical handshake is parsed; if a later status access fails, that
completed verification is not silently uncounted.

## Validation design

The implementation test matrix covers:

- main-client and unit-kill-helper `Popen` failures;
- ordinary and non-`Exception` failures in unit dispatch, client `killpg`,
  conditional retry, cleanup `communicate`, both bounded waits, and return-code
  access;
- exact primary-versus-cleanup exception identity and first-interrupt
  precedence;
- timeout with and without main-client reaping and a zero-status unit-dispatch
  acknowledgement;
- negative client return codes before output or handshake access;
- artifact, handshake, and bounded-output `fstat`, read, mutation, and close
  failures;
- exclusive-write and temporary-directory cleanup precedence;
- exact started and verified counter boundaries; and
- one inert local Python sleep process group, where a synthetic first
  `killpg` interrupt is followed by the bounded kill/reap path.

Controlled doubles provide the hostile matrix. The single real-process test
is an inert local sleep process only. The tests do not invoke a real systemd
service, project worker, detector, control, target, protected corpus, or real
source.

Current local evidence is bound to source commit
`cd583fb12b12a80d132c80e8a3465e53f5c3151a` and exact diff SHA-256
`7069fbae6e9749c401f00ef35b5e5cc8c74d0e262f00626c95d4a7192d71115d`:

- the normal focused sandbox suite ran 47 tests in 1.644s and passed with six
  environment-specific skips;
- exact CPython 3.12.11 ran the same 47 tests in 1.645s and passed with the
  same six skips;
- the combined evaluator and worker-wire suites ran 51 tests in 27.230s and
  passed with no skips; and
- two independent read-only code audits each reported zero blockers, zero
  major findings, and zero minor findings.

An initial complete-suite attempt ran all 1,078 tests with 19
environment-specific skips and recorded
four Quicknet failure/error outcomes (two failures and two errors). All four
outcomes were fail-closed preflight
rejections: inherited umask had left vendored Noble
regular files at `0664` and directories at `0775` in the isolated worktree.
The source bytes, content hashes, and source diff were unchanged. A
worktree-only `chmod go-w` normalization restored regular files to `0644` and
directories to `0755`; the focused Quicknet suite then passed. This first
attempt remains a failed historical validation event and is not relabeled as
success.

After that worktree-only normalization, final local validation passed:

- all 23 Quicknet tests;
- all 1,078 repository tests with 19 environment-specific skips in 1213.871s,
  with a 1214.88s external wall duration;
- Ruff lint over the complete configured scope and Ruff format over all 181
  checked files;
- Pyright with zero errors, zero warnings, and zero information messages;
- distribution member checks for a 337-member sdist and 163-member wheel,
  including path, private-material, and source-hash assertions;
- Gitleaks across 65 commits and approximately 7.15 MB with no leaks; and
- the public-boundary check.

Public-CI
[run 30623782622](/megu0xxx0x/indus-open-benchmark/actions/runs/30623782622)
used event `push` at exact head SHA
`cd583fb12b12a80d132c80e8a3465e53f5c3151a`, reached status `completed` with
conclusion `success`, and had all three matrix jobs green. The overall run was
`2026-07-31`, `10:30:29Z`–`10:46:17Z` (15m48s). Each Quicknet job
asserted Node `v24.18.1` on Linux/x64 and recorded failed, cancelled, skipped,
and todo counts of zero. Python 3.11 ran
`10:30:33Z`–`10:44:34Z` (14m01s), Quicknet 6/6 at
`duration_ms=615.588048`, and unittest 1078 tests with 22 skipped in 808.435s.
Python 3.13 ran `10:30:32Z`–`10:39:02Z` (8m30s), Quicknet 6/6 at
`duration_ms=292.030965`, and unittest 1078 tests with 22 skipped in 483.182s.
Python 3.14 ran `10:30:32Z`–`10:46:16Z` (15m44s), Quicknet 6/6 at
`duration_ms=565.70517`, and unittest 1078 tests with 22 skipped in 906.229s.
Each job also passed Ruff lint, Ruff format with 181 files already formatted,
Pyright with zero errors, warnings, or information messages, and sdist plus
wheel builds. CI recorded 22 skips per job, not the 19 skips recorded by the
separate clean local full-suite validation above.

## Residual boundaries and non-results

The hardening cannot guarantee termination or reaping under repeated hostile
interrupts, a compromised same-UID actor, root control, kernel failure, or
systemd failure. A zero-status dispatch does not prove an empty cgroup. Public
semantic CI does not prove deployment runtime provenance, and the supported
host-runtime/dynamic-closure gate remains unresolved.

No project or deployment runtime was installed or changed. No real systemd
service, project worker, detector, control bundle, freeze, target, or
scientific run was created or executed. No bundle or freeze was built or
dispatched; no target was selected, reserved, fetched, or accessed; no
protected or real dataset was opened; and no real-run seed, schedule, truth,
request, response, or oracle was instantiated or persisted.

There is no C3 result, real-source result, decipherment evidence, translation,
public-claim authorization, or prize result. KP1979 V2 remains retired and
immutable. After audited source publication, the next separate gates are a
supported host runtime with a closed dynamic dependency policy and an
injection-free official one-shot runner. This document authorizes neither and
does not authorize execution.
