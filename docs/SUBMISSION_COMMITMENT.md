# Local submission content commitment

## Current boundary

`submission-commitment.schema.json` schema version 0.1.0 and digest protocol
v0.1 define the local submission commitment `S`. It deterministically binds:

- one caller-declared digest of a separately verified public benchmark
  definition;
- every directory and regular file below one submission root;
- each file's exact bytes and executable-bit state;
- the declared role or roles of every file;
- one entrypoint path, a fixed working directory of `.`, and exact static
  argument strings.

It deliberately contains no creator name, wall-clock time, signature,
custodian, hidden-set detail, or result. Its assurance block always reports:

- `claim_class=submission_content_commitment`;
- `blind_claim_allowed=false`;
- `final_evaluation_eligible=false`;
- `externally_anchored=false`; and
- custody, trusted-time, authorship, access-history, confidentiality,
  runtime-isolation, and execution-result attestation as `false`.

This layer proves only that a particular logical tree, role declaration,
entrypoint declaration, and benchmark target correspond to a digest. It does
not prove that the commitment was made before evaluation. A later independent
receipt must bind both the exact benchmark-definition digest `B` and `S`
before the candidate is run on hidden inputs and before the
hypothesis/submission team receives hidden material or hidden-derived
feedback.

## Deterministic identity

The document excludes self-asserted timestamps and authorship so the same
content and declarations produce the same commitment at different locations
and times.

Each file records:

```json
{
  "path": "src/run.py",
  "type": "file",
  "bytes": 123,
  "content_sha256": "sha256:...",
  "executable": true,
  "roles": ["entrypoint", "source"]
}
```

Directories are also entries, including empty directories. Zero-byte regular
files are valid. Creation order, absolute root path, uid/gid, mtime, xattrs,
and non-executable permission differences are not part of the digest.

The tree digest is:

```text
SHA256(
  "indusbench:submission-tree:v0.1\0"
  || indus-json-c14n-v1(tree without tree_sha256)
)
```

The complete commitment digest is:

```text
SHA256(
  "indusbench:submission-commitment:v0.1\0"
  || indus-json-c14n-v1(commitment without commitment_id
                        and commitment_sha256)
)
```

`indus-json-c14n-v1` is Python/JSON-compatible serialization with
`ensure_ascii=false`, compact separators `(",", ":")`, lexicographically
sorted object keys, preserved array order, and no floats or non-finite values.
It applies no Unicode normalization. Entry and role arrays have separately
enforced canonical orders. Static arguments may contain Unicode but may not be
empty, exceed their byte limits, or contain Unicode-category `C` control,
format, surrogate, private-use, or unassigned characters.

Changing a commitment and recomputing both digests creates a different valid
local commitment. Only a later independently retained receipt can demonstrate
that an earlier digest was the one received before evaluation.

## Disclosure and metadata boundary

`S` is not encryption, hiding, or zero knowledge. The manifest exposes
plaintext paths, roles, byte sizes, executable state, static arguments, the
target digest, and deterministic per-file hashes. Those values permit
cross-submission linkability and dictionary confirmation of low-entropy files.

Never place credentials, API tokens, private keys, confidential arguments,
hidden identifiers or record hashes, a custodian nonce, rights-restricted
metadata, or other secrets in an `S` intended for publication. A commitment
does not grant publication or license rights and does not attest training-data
provenance or absence of test contamination.

Only exact bytes and the executable/non-executable state are committed for
files. Full permission bits, ACLs, xattrs/resource forks, BSD flags, uid/gid,
and filesystem policy are not in the digest. The publisher rejects detectable
extended ACLs on its pinned output descriptor, but this is still not a
confidentiality attestation.

## Complete-tree and role model

There are no ignore patterns. Every directory and file below the
caller-selected root is committed; the root itself is not an inventory entry,
and at least one regular file is required. “Complete tree” is therefore
root-relative. It does not mean that the interpreter, environment variables,
training process, files read outside the root, dynamic dependencies, or
network services are closed.

The closed role vocabulary is:

| Role | Meaning |
|---|---|
| `entrypoint` | The unique declared entrypoint file |
| `source` | Executable or imported implementation source |
| `configuration` | Model or pipeline configuration |
| `model_weight` | Learned parameter or weight bytes |
| `dependency` | Dependency manifest, lock, wheel, or equivalent bound input |
| `runtime_input` | Any otherwise unclassified file still present in the runtime tree |

The entrypoint is automatically also `source`. A file may have several
explicit roles, but `runtime_input` is used alone. Files not named by a role
flag are not ignored; the builder assigns them `runtime_input`. This makes
unclassified material visible while still committing every byte.

Roles are declarations, not proof that a process used a file. A future run
lock must recreate a clean tree, invoke the committed entrypoint, enforce
read-only inputs and network isolation, and bind the resulting output.
`kind=declared_tree_file` identifies the exact file but deliberately does not
choose direct execution versus a particular interpreter. P3 must bind the
exact interpreter/image digest, full argv/environment, external-read policy,
and network policy before execution.

## Safe path profile

Version 0.1 uses a conservative portable ASCII relative-path profile:

- permitted component characters are `A-Z`, `a-z`, `0-9`, `.`, `_`, `+`,
  `@`, and `-`;
- absolute paths, empty components, `.`, `..`, backslashes, drive/UNC forms,
  controls, trailing dot/space, and Windows device names are rejected;
- a component is at most 100 bytes, a path at most 240 bytes, and depth at
  most 32;
- exact and normalized case-fold collision keys are both checked.

Unicode path names are rejected in v0.1. This deliberately fails closed on
NFC/NFD and compatibility-character ambiguity rather than choosing a
filesystem-specific normalization.

## Safe filesystem traversal

The builder and verifier require descriptor-relative primitives. They do not
fall back to a weaker traversal on unsupported platforms.

For each of two complete scans, the implementation:

1. opens and pins the real root with `O_DIRECTORY | O_NOFOLLOW`;
2. enumerates directories through descriptors;
3. opens each child with `openat`, `O_NOFOLLOW`, and `O_NONBLOCK`;
4. rejects symlinks, hardlinks, FIFO/socket/device leaves, duplicate inodes,
   cross-device boundaries, and setuid/setgid/sticky bits;
5. streams SHA-256 without loading model weights into memory;
6. compares device, inode, mode, link count, size, mtime, and ctime before and
   after each read and namespace lookup;
7. rechecks each directory and the root namespace; and
8. requires the two full inventories, fingerprints, counts, and hashes to
   agree.

This catches ordinary replacement and mutation races. It is not an atomic
filesystem snapshot and cannot defeat an indefinitely racing process with the
same user privileges. A custodial runner should receive immutable staged
bytes and reconstruct them into a fresh read-only runtime.

Fixed v0.1 limits are:

| Resource | Limit |
|---|---:|
| Commitment JSON file read by verifier | 16 MiB |
| Commitment JSON depth | 64 |
| Commitment JSON nodes | 100,000 |
| Tree entries | 4,096 |
| Directories | 4,096 |
| One file | 8 GiB |
| Aggregate file bytes | 16 GiB |
| Static arguments | 32 |
| One static argument | 256 UTF-8 bytes |
| All static arguments | 4,096 UTF-8 bytes |

These limits are part of the versioned security profile and are not
user-increaseable CLI flags. The verifier accepts only a nonempty, single-link
regular commitment file and rejects invalid UTF-8, duplicate JSON keys,
floats/non-finite values, excessive depth, and excessive node counts.

## CLI

First verify the target benchmark definition with
`verify-benchmark-lock`; the submission builder validates the supplied
checksum's syntax but does not re-open or re-derive `B`. Then prepare a clean
submission directory and an existing output parent directory. The output
commitment must be outside that tree:

```bash
uv run indusbench build-submission-commitment \
  data/derived/candidate \
  data/derived/candidate-submission.json \
  --benchmark-definition-sha256 sha256:<64-lowercase-hex> \
  --entrypoint src/run.py \
  --source-file src/model.py \
  --config-file config/model.json \
  --model-weight-file weights/model.bin \
  --dependency-file pyproject.toml \
  --dependency-file uv.lock \
  --static-argument=--mode \
  --static-argument predict
```

The command never overwrites an existing file or follows an existing/dangling
output symlink. It pins the output parent by descriptor, checks ancestry by
device/inode rather than path spelling, publishes deterministic JSON with
POSIX mode bits `0600`, rejects a detectable inherited extended ACL, and uses
an atomic no-replace hardlink. It then re-verifies the exact bytes, inode,
link count, requested-parent identity, and submission tree. POSIX mode `0600`
is not encryption or a confidentiality attestation. Unknown durability or any
postcondition failure returns nonzero. A failure after publication may leave
the output present; inspect `written`, `durability_confirmed`, and all
verification fields, and do not automatically delete or retry it. Success is
explicitly
`postcondition=committed_and_verified_at_check`,
`postconditions_atomic=false`, and `future_immutability_attested=false`: the
checks are point-in-time filesystem observations, not one atomic snapshot or a
promise that a same-privilege process cannot mutate bytes immediately
afterward. Publishing that inventory later is a separate, explicit release
decision.

Re-enumerate the full tree:

```bash
uv run indusbench verify-submission-commitment \
  data/derived/candidate-submission.json \
  data/derived/candidate
```

An independently supplied expected digest can be compared:

```bash
uv run indusbench verify-submission-commitment \
  data/derived/candidate-submission.json \
  data/derived/candidate \
  --expected-commitment-sha256 sha256:<64-lowercase-hex>
```

A match sets only `expected_digest_match=true`. It never changes
`externally_anchored`, custody, trusted-time, access-history, blind, or final
fields.

## Interoperability vector

The v0.1 synthetic vector uses benchmark digest `sha256:` followed by 64
`1` characters and this root:

- directory `empty/`;
- executable `run.py` with exact bytes `print('ok')\n`, as
  `entrypoint` + `source`;
- `config.json` with exact bytes `{}\n`, as `configuration`;
- zero-byte `zero.bin`, assigned `runtime_input`;
- static arguments `["--fixed"]`.

Expected digests:

```text
tree_sha256       = sha256:72eca6974faf753e852832d7ec630b3f62ceb70503b74a790c028eeb88bd38b3
commitment_sha256 = sha256:3ee9eed5ec6d8ea2c28dba8cc304772c64e9c929a9a070b57c6b114f3e9a3811
```

The executable state is the only permission-derived bit in the tree digest.
The vector is also enforced by `test_v0_1_digest_golden_vector`.

## What remains

No real hidden data, independent custodian, trusted timestamp, isolated
runtime, or result receipt is created by these commands. The next blind-test
layers remain:

1. an independently operated private hidden companion that reveals no hidden
   identifiers or hashes to the public side;
2. an authenticated, independently retained, time-evidenced receipt binding
   exact `B` and `S` values before the candidate is run on hidden inputs and
   before the hypothesis/submission team receives hidden material or
   hidden-derived feedback; and
3. a run/result protocol binding benchmark definition, `S`, private
   commitment, isolated runtime, and outputs without replay.

Until those layers exist, a valid `S` is local content-integrity evidence
only.
