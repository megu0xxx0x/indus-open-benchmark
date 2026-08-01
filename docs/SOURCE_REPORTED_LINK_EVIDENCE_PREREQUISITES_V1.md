# Static source-reported-link evidence prerequisites

**Evidence record timestamp:** `2026-08-01T18:17:48+09:00`

**Static prerequisite commit:** `698c029b038b08d8f7e5538e048fdc42eb659160`

**Validated head:** `93609e39263fde2617a6ea13b2f4de64947cd17e`

**Parent checkpoint:** `68ae5cff9065477be3a34ccc07b152636f44eb2f`

**Claim status:** static repository-only prerequisite specification;
blocked, not authorized, not executed, and not a source receipt, runtime
attestation, source-link result, join, translation, decipherment, prize
submission, or prize result

## Purpose and present state

This is the non-operational follow-up to the
[static source registration and rights contract](SOURCE_REPORTED_LINK_SOURCE_CONTRACT_V1.md).
It closes the previously missing static shapes for:

- one five-member source-revision receipt;
- its separate, self-cycle-free commitment envelope;
- one six-resource source-revision set;
- the conditional six-slot completeness attestation; and
- protected ephemeral custody, deletion, recovery, review, and retention
  prerequisites.

The follow-up does not retrieve or instantiate any of them. Its exact contract
status is `preregistered_static_prerequisite_blocked_not_authorized`.
Authorization is `not_authorized`, execution is `not_executed`, and the
static source-access status is `NONE_no_source_access_executed`.

The strict runtime verifier, independent bootstrap supervisor and trust root,
root classifier, terminalizer, restart recovery implementation, acquisition
client, deterministic parser, evaluator, dynamic artifact schemas, and
one-time authority record are all absent. Their status is
`NOT_IMPLEMENTED_HARD_BLOCK` or `missing_not_implemented` as applicable.

## Exact published files

Commit `698c029b038b08d8f7e5538e048fdc42eb659160` adds six static contract/schema
files and one test, and updates one parent-contract test. Its parent is
`68ae5cff9065477be3a34ccc07b152636f44eb2f`. The eight-file binary diff has
20,886 additions and four deletions. Its SHA-256 is
`a8bdcda6ec2055d48da8ef5de2a64f32c46a48cc94baddbc4f75ba6b01fc77d3`;
the `--full-index` binary-diff SHA-256 is
`0be85a7c7a2594795a98b58f186c699a6f034b4bee23bd1bf703e42b92f46467`.
Every path has mode `100644`.

| Path | Bytes | SHA-256 at validated head |
|---|---:|---|
| `registry/source-reported-link-protected-ephemeral-custody-contract-v1.json` | 426,824 | `917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914` |
| `schemas/source-reported-link-completeness-attestation.schema.json` | 5,627 | `a8ae0f32fbda8cd1bb7e29db3d3444ec0659ffa9f9818ea85331288d0f018c02` |
| `schemas/source-reported-link-protected-ephemeral-custody-contract.schema.json` | 440,116 | `5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b` |
| `schemas/source-reported-link-receipt-commitment-envelope.schema.json` | 2,546 | `f4e316c5542c5ea9c57a91fc5006a10550c2dbbd08436e165d997e265570c2d4` |
| `schemas/source-reported-link-source-revision-receipt.schema.json` | 9,316 | `6d0451ed9471315b11689e6cabe8bf7b15e6b5d31f0064d5a364c9ac73789375` |
| `schemas/source-reported-link-source-revision-set.schema.json` | 6,459 | `15d64ee72ea7a147bcde22a2c28330b67c1eae4d299e272296a53a2ef25d17bb` |
| `tests/test_source_reported_link_evidence_prerequisites.py` | 313,036 | `137d3151410593b7428867b71ba32824c6ceef366b0e47b27a9d9eec8ba1de69` |
| `tests/test_source_reported_link_source_contract.py` | 37,192 | `0ae77d5bbf9ce7081c3abbd78ca491cbf2072f077caf3cc8c4d354d19697fe04` |

The test hash above includes the test-only Pyright narrowing fix at
`93609e39263fde2617a6ea13b2f4de64947cd17e`. That follow-up changes no
contract or schema byte and no scientific or operational semantics.

## Closed evidence identities

The four dynamic payload schemas form one exact ordered schema set with
digest:

`sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f`

They preserve three different cardinalities:

| Surface | Count | Meaning |
|---|---:|---|
| Receipt members | 5 | One exact Penn response-body identity per registered item URI |
| Revision resources | 6 | The fixed Mackay revision plus five Penn members |
| Inspection/result slots | 6 | One result for every frozen parent link row |

The receipt payload has no self-hash. Its external digest is bound by the
separate commitment envelope. The revision-set digest is a different
domain-separated identity and cannot be replaced by the receipt digest.
The completeness payload is conditionally present only for the closed
row-absent case and must bind the exact six-slot roster, exact parent
identities, and actual zero exception counts.

Every dynamic digest is recomputed from bounded canonical bytes with its
declared domain and NUL framing. A caller-supplied naked digest, path, index,
count, status, or projection is not authoritative.

## Authority and anti-replay boundary

This static contract embeds no authority record. A future authority proof must
be external, typed, authenticated, and scoped to exactly one complete attempt.
It must bind both the published static prerequisite commit and a distinct,
already frozen authorized-runtime commit, its complete transitive runtime
manifest, and its distribution digest.

The contract fixes the authority/review profile identities, Ed25519
algorithms, domains, framings, strict verification rules, and test-only
vectors. The live external trust roots and keys, typed authority schema and
record, bootstrap configuration, and signature-verifier implementation are
absent. Runtime self-issuance, self-bootstrap, schema validity alone, a
process-local HMAC, a generic instruction to continue, or a later result
cannot authorize source access.

A durable one-time reservation, append-only attempt registry, separate
append-only ledger, and grant-keyed exclusive execution lease are required
before any source request. A partial, failed, crashed, or unresolved attempt
consumes its authority. Retrying requires a new separately authenticated grant
and a new derived attempt identity; it cannot reuse the current conversation
or a previous general approval.

## Protected custody and recovery boundary

Content-bearing response, parser, and inspection bytes are restricted to
protected process memory. The workspace is an empty control-isolation
boundary with an exact zero content-leaf maximum. Raw bytes, decoded snippets,
free text, source-derived content, private paths, hostnames, account names,
device/inode identities, operational timestamps, and private audit digests are
forbidden from public or scientific evidence artifacts except for the exact
closed owner-only control exceptions stated in the contract.

The host preflight must reject acquisition unless protected-page swap, core
dumps, source-bearing crash reports, and automatic backup/snapshot inclusion
are disabled. This is a handling prerequisite, not a claim that the kernel,
root, same-UID processes, libraries, TLS stacks, physical media, or external
copies cannot observe or retain bytes.

Cleanup is descriptor-pinned and fail closed. It records logical workspace
absence and durable control evidence but makes no secure-erasure or zeroization
claim. Unknown descriptors, links, mount changes, malformed state, incomplete
ledger relations, guessed deletion targets, or cleanup uncertainty block
scientific retention and publication. Deleted raw ledger generations may not
be reopened or reconstructed from a surviving projection.

The source-access status lattice is exactly:

- `NONE`;
- `POSSIBLE_KNOWN`;
- `POSSIBLE_DISPATCH_UNKNOWN`;
- `POSSIBLE_BODY_UNKNOWN`; and
- `CONFIRMED_COMPLETE`.

It is derived only from validated durable registry/ledger state and the exact
post-acquisition attestation projection. Five apparent counts without that
projection remain `POSSIBLE_KNOWN`, not `CONFIRMED_COMPLETE`. Missing volatile
state never proves `NONE`.

## Reference-model boundary

The prerequisite test contains executable reference models for closed
registry, ledger, branch, status-selector, terminal-copy, and crash-window
relations. These models are test evidence for the static specification only.
They are not a production parser, root classifier, terminalizer, bootstrap
supervisor, signature/MAC trust root, runtime validation boundary, source
client, evaluator, custody attestation, or execution proof.

In particular, a test-local process HMAC detects accidental mutation inside
that test model only. It establishes no authenticity, independence,
authorization, durable custody, or source-access fact. No source or runtime
may call the reference model and relabel its output as validated execution.

## Scientific result and retention boundary

If a later separately authorized runtime reaches two valid pass bundles, it
must preserve all six ordered rows. The only evaluated row states remain
`source_reported_link`, `no_link`, and `unresolved`; malformed or forbidden
input hard-rejects before evaluation. A valid unresolved observation is not
an operational failure, while operational failure can never become
`unresolved` or `no_link`.

Scientific candidates remain memory-only until a separate externally signed
owner-only retention review is durably approved. Review approval is not
predicted by the runtime. Denial, invalid review, candidate loss, cleanup
uncertainty, or retention failure publishes no scientific batch. Public
release would require a later, separately authorized publication protocol;
this contract contains none.

Distinct pass IDs and seals prove only distinct identifiers and digests. They
do not prove human, model, organizational, custody, or source independence,
blinding, authorship authenticity, or nonexposure.

## Packaging and validation evidence

The locked local build at validated head produced:

| Artifact | Members | SHA-256 |
|---|---:|---|
| sdist | 357 | `6b8de3c90d04f4f7ccd92c8e797672f1e4bcbeb8589e53662f4ac39031bfd0f2` |
| wheel | 171 | `1133ab6de865490e62a866e6dcf0fb5198834112db13b5c2f0703c27f165bfc0` |

The sdist includes the static contract registry and all five schemas. The
wheel includes all five schemas but not the contract registry or tests.
Schema packaging therefore creates no installed loader or runtime claim.

Focused validation passed 22 prerequisite tests, 12 parent source-contract
tests, and seven policy tests. The reference-model audit also passed the
five-case no-ledger branch, 20 non-no-ledger branches, all 990 declared
Cartesian branch combinations with zero mismatches, 34 storage-state cases,
and 25 additional storage assertions. Ruff, the 185-file format check, locked
Pyright 1.1.409, canonical/schema checks, distribution builds, and exact-diff
secret/public-boundary checks passed. Three independent read-only AI audits of
the frozen candidate reported zero P0, P1, and P2 findings; this is not human
or external scientific review.

One local full-suite run used the unsupported default Node 18.19.1. It ran
1,128 tests in 912.511 seconds, with 19 skips and exactly two failures plus
two errors, all confined to the fail-closed Quicknet Node-version/vendor
check. The V8 tests passed. This run is retained as an environment incident,
not reported as green.

The first public CI run, `30691454425`, reached all three locked matrix jobs,
passed Node 24 Quicknet and lint, then stopped at the same seven Pyright
narrowing diagnostics in the new reference-model test. The test-only follow-up
at `93609e3` added fail-closed runtime narrowing; it did not change a contract
or schema byte.

Public
[CI run 30692592441](https://github.com/megu0xxx0x/indus-open-benchmark/actions/runs/30692592441)
succeeded at exact head
`93609e39263fde2617a6ea13b2f4de64947cd17e`. Every job asserted Node
24.18.1, passed Quicknet 6/6, Ruff, formatting of all 185 files, zero-error
Pyright, the complete test suite, and both builds:

| Python | Quicknet | Full suite |
|---|---:|---:|
| 3.11 | 509.496182 ms | 1,128 tests, 22 skips, 832.968 s |
| 3.13 | 553.422972 ms | 1,128 tests, 22 skips, 942.715 s |
| 3.14 | 535.736492 ms | 1,128 tests, 22 skips, 865.301 s |

## Non-execution and nonclaims

No research or protected source endpoint was requested while preparing,
testing, publishing, or documenting this checkpoint. No external response
body, image, page, plate, media, Helsinki row, protected corpus, pass input,
observation, or result was opened or created, and no institution or source
holder was contacted. Repository and CI network access are outside that
statement and grant no research-source authority.

There is no source receipt, revision-set instance, completeness attestation,
authority proof, attempt reservation, runtime manifest, acquisition graph,
execution attestation, pass bundle, terminal decision, deletion record,
retention review, source-reported-link/no-link outcome, admitted join,
transcription, translation, language identification, decipherment evidence,
claim authorization, prize submission, prize eligibility, or prize result.

## Next gate for a continuing agent

Work must remain source-free while the following implementation checkpoint is
built and independently validated:

1. freeze the missing dynamic schemas and exact generic resource preflight;
2. implement the independent bootstrap verifier, fixed external trust-root
   interface, strict cross-artifact verifier, root classifier, terminalizer,
   one-time reservation, registry/ledger recovery, and custody supervisor;
3. implement the exact five-request acquisition client, bounded deterministic
   body-to-parser profile, closed parser codebook, two-pass evaluator, deletion
   evidence, review, and retention state machines without executing them;
4. bind the full transitive runtime manifest and reproducible distribution to
   a new runtime commit and audit that frozen implementation; and
5. only then obtain a new exact external authority proof that binds the static
   and runtime commits and permits one complete attempt.

Only a valid authority record after those steps could permit the five-member
acquisition and two coded passes. A valid result would still be a bounded
source-reported context-link finding, not a decipherment. It should feed the
separate hypothesis-tournament and prospective-validation track without
weakening any claim gate.
