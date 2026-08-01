# Source-reported-link static loader and canonical-resource preflight V1

Status recorded at 2026-08-01 19:20:49 JST.

This checkpoint implements a source-free package-local preflight slice next
to the frozen source-reported-link evidence-prerequisite contract. It is not
yet an implementation of that contract's strict V1 resolver. Here,
“source-free” means that the installed loader does not depend on a repository
checkout and does not access a research source. It does not mean that a Python
wheel contains no `.py` source.

No protected source endpoint, Penn item page, Mackay revision, response body,
image, transcription, or other research-source byte was accessed while
building or testing this slice.

## Implemented boundary

### Canonical raw-resource preflight

`indusbench.source_reported_link_resource.preflight_canonical_resource`
implements only checks 1–5 of the frozen verification order:

1. the exact per-role raw-byte maximum;
2. strict UTF-8 with no BOM;
3. rejection of duplicate object keys at every depth;
4. integer-only JSON with no float, exponent, or nonfinite number; and
5. byte equality with `indusbench.io.encode_json`.

The API accepts exact `bytes` and one member of a closed 21-role enum. A
caller cannot supply a size profile, schema, digest domain, file path, or
hash. Shared limits are:

| Limit | Value |
|---|---:|
| root-relative maximum nesting depth | 32 |
| maximum JSON nodes, including the root and excluding object keys | 4,096 |
| maximum decoded Unicode scalar count per key or string value | 8,192 |
| maximum integer digits, excluding an optional minus sign | 10 |
| authenticated-control staging maximum | 16,384 bytes |

The returned `PreflightedCanonicalResource` is recursively immutable and has
a redacted representation. It is deliberately described as a preflight
result, not a schema-valid artifact, evidence receipt, trusted capability, or
authorization.

The raw-role maxima are fixed at 4,096, 8,192, 16,384, 32,768, or 65,536
bytes according to the frozen custody contract. All 21 role-to-limit
mappings are asserted in tests.

### Installed static loader

`indusbench.source_reported_link_static.load_installed_source_link_static`
accepts no arguments. It resolves only the real filesystem package directory
reported for `indusbench`. Zip import, arbitrary traversables, a source-tree
fallback, and a caller-selected root are unsupported by the public API.

The strong loader mode currently supports Linux and macOS hosts with all of
the following primitives:

- descriptor-relative `open` and no-follow `stat`;
- `O_DIRECTORY`, `O_NOFOLLOW`, `O_CLOEXEC`, and `O_NONBLOCK`;
- stable UID and file metadata available through `fstat`.

An unsupported platform hard-blocks. The package root, `registry`, and
`schemas` directories must be real directories on one device, owned by root
or the current effective UID, readable/searchable by the owner, and not
group/other writable. Every selected file must be a single-link,
non-executable regular file on that device with an allowed owner.

Each file is opened relative to a pinned parent descriptor, read with an
exact upper bound, and compared against namespace and descriptor metadata
before and after the read. Size and SHA-256 are checked before JSON
interpretation. Descriptor-close failure hard-blocks. Public errors contain
only a closed error code; they expose no path, resource value, validator
message, UID, inode, or underlying exception chain.

This protects against several ordinary package-tree substitution and race
classes. It is not a defense against a hostile kernel, root, same-UID process
with broader powers, mount/rollback attack, replacement of the wheel and its
code together, or every ACL/xattr policy. Sequential validation is not an
atomic or continuing snapshot guarantee across all 14 files. The loader does
not authenticate the wheel or its publisher.

## Exact 14 static resources

The loader opens only the following compiled path/size/hash table:

| Package-relative path | Bytes | SHA-256 |
|---|---:|---|
| `registry/chanhu-daro-helsinki-gate-v1.json` | 6,955 | `43c0fae1a8558fbffeb062725e401e0c3c1de570e5f8f7eef610ca2616cbfb3d` |
| `registry/sources.json` | 43,235 | `e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584` |
| `registry/source-reported-link-policy-v1.json` | 7,967 | `c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90` |
| `registry/source-reported-link-source-contract-v1.json` | 29,059 | `e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f` |
| `registry/source-reported-link-protected-ephemeral-custody-contract-v1.json` | 426,824 | `917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914` |
| `schemas/context-source-link-gate.schema.json` | 9,216 | `72109818eb55aca008b0f34b1d6c627efd0e38bdbaff8c500cb3c60dc74e3002` |
| `schemas/source-registry.schema.json` | 8,295 | `6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3` |
| `schemas/source-reported-link-policy.schema.json` | 8,589 | `d951541892bb6a5ef092d44e9a5564da2261f960e52e3e84a95ecd5ef8e61aff` |
| `schemas/source-reported-link-source-contract.schema.json` | 30,752 | `e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78` |
| `schemas/source-reported-link-protected-ephemeral-custody-contract.schema.json` | 440,116 | `5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b` |
| `schemas/source-reported-link-source-revision-receipt.schema.json` | 9,316 | `6d0451ed9471315b11689e6cabe8bf7b15e6b5d31f0064d5a364c9ac73789375` |
| `schemas/source-reported-link-receipt-commitment-envelope.schema.json` | 2,546 | `f4e316c5542c5ea9c57a91fc5006a10550c2dbbd08436e165d997e265570c2d4` |
| `schemas/source-reported-link-source-revision-set.schema.json` | 6,459 | `15d64ee72ea7a147bcde22a2c28330b67c1eae4d299e272296a53a2ef25d17bb` |
| `schemas/source-reported-link-completeness-attestation.schema.json` | 5,627 | `a8ae0f32fbda8cd1bb7e29db3d3444ec0659ffa9f9818ea85331288d0f018c02` |

The table totals 1,034,956 bytes. Extra package files are not selected by this
loader and cannot be substituted for a table member.

## Closed legacy byte-order exception

Twelve of the exact resources re-encode byte-for-byte under
`indusbench.io.encode_json`. Two older V1 resources predate that key-order
profile:

- `registry/sources.json`
- `schemas/source-registry.schema.json`

Changing either file to the current canonical order would change multiple
already-frozen parent commitments and the exact custody `const` schema.
Changing those frozen artifacts is outside this implementation slice.

The loader therefore permits a canonical re-encoding mismatch only for those
two compiled resource keys and only after their exact raw size and SHA-256
have matched. They still receive strict UTF-8, duplicate-key, integer-only,
bounded-structure, schema, and cross-binding checks. Their decoded or
re-encoded form is never written back, adopted as a new identity, or returned
to the caller. This is not a general legacy mode and cannot be selected by a
caller. The decoder itself repeats the exact size/hash condition, so a private
helper call cannot activate the exception with merely the same resource key.

The frozen V1 resolver separately requires canonical byte equality and
hard-rejects noncanonical raw input. The two parent resources therefore leave
this snapshot explicitly ineligible for that resolver even though their
frozen hashes match. Adding the two missing runtime identities would not cure
this incompatibility. A later authority-bearing path must first either freeze
a successor contract/profile that explicitly defines the exact-two rule or
re-freeze the affected parent chain under canonical bytes.

## Schema and cross-binding validation

After raw identity and strict JSON checks, the loader:

- checks all nine schemas with `Draft202012Validator.check_schema`;
- requires the Draft 2020-12 URI and exact schema ID;
- permits only local JSON Pointer `$ref` values;
- permits only `date-time` and `uri` formats;
- exercises valid and invalid format canaries, including a timezone-less
  date-time rejection;
- validates the five registry/contract instances with an explicit
  `FormatChecker`;
- verifies policy-to-preselection, source-contract-to-parent, and
  custody-to-parent size/hash/ID bindings;
- rederives the six ordered tasks from the preselection rows;
- recomputes the domain-separated ordered-roster digest;
- verifies the exact ordered four-schema set and recomputes its
  domain-separated digest; and
- checks the source-registry IDs used by the registration transition.

No URI is dereferenced. JSON Schema validation is not allowed to retrieve an
external reference.

## Exact output and missing boundary

Successful loading returns a `SourceFreeStaticSnapshot` with exactly these six
static identity fields:

| Field | Value |
|---|---|
| `artifact_schema_set_sha256` | `sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f` |
| `custody_contract_sha256` | `sha256:917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914` |
| `ordered_source_roster_sha256` | `sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f` |
| `source_contract_sha256` | `sha256:e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f` |
| `source_policy_sha256` | `sha256:c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90` |
| `source_registry_sha256` | `sha256:e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584` |

The snapshot also records resource count 14 and names the two absent future
bindings:

- `runtime_distribution_sha256`
- `transitive_runtime_input_manifest_sha256`

It has no value-bearing runtime, authority, authorization, source-access, or
result field. It is not the future complete eight-field binding set. It also
fixes:

- `strict_v1_resolver_eligible=False`; and
- blockers
  `source_registry_noncanonical_raw_bytes` and
  `source_registry_schema_noncanonical_raw_bytes`.

Those fields are set internally and cannot be selected through the snapshot
constructor. A future strict resolver must fail closed while the eligibility
flag is false.

## Packaging and validation evidence

The wheel now individually includes the preselection registry, live source
registry, source policy, source contract, and custody contract. It does not
include a caller-selected registry directory wholesale.

The post-build verifier independently checks that every exact resource is a
unique regular wheel member with the expected size, hash, and repository-byte
parity. It rejects duplicate names, case-fold collisions, unsafe member names,
and non-regular exact resources. It then extracts the validated wheel into a
temporary installed layout and invokes isolated Python from an empty working
directory. The subprocess asserts that `indusbench` came from the extracted
wheel, traps socket audit events, and loads the six-identity snapshot.
Extraction temporarily fixes umask `0022` and restores the caller's umask in
a `finally` block, so the strong loader receives deterministic non-writable
package modes even on a build host whose ambient umask is `0002`.

Pre-publication local evidence at the timestamp above:

- 22 canonical-resource preflight tests passed;
- 13 static-loader boundary, exact-14 pin, schema, digest, no-network, and close-failure
  tests passed;
- the combined policy/source-contract/prerequisite/new-runtime set passed
  76/76;
- targeted Ruff and formatting passed;
- targeted Pyright reported zero errors, warnings, or information messages;
  and
- sdist, wheel, exact-member parity, and isolated-wheel loading passed.

Validation update at 2026-08-01 19:54:34 JST:

- three independent read-only AI audits each reported P0/P1/P2 as 0/0/0;
- the local macOS full suite completed all 1,163 discovered tests in 587.892
  seconds with 55 skips, but was not green: five failures and six errors were
  confined to unchanged KP1979 V3 control-freeze host tests involving Darwin
  directory revalidation and an AF_UNIX path-length limit; and
- no new preflight, static-loader, packaging, policy, source-contract,
  evidence-prerequisite, or publication-boundary test failed.

Public Linux CI run `30696751707` then succeeded at exact implementation head
`8cdaaa29c03d535d9590958194a3de31d0291797`:

| Python | Quicknet | Full suite |
|---|---:|---:|
| 3.11 | 537.059591 ms | 1,163 tests, 22 skips, 845.198 s |
| 3.13 | 545.911912 ms | 1,163 tests, 22 skips, 954.779 s |
| 3.14 | 517.956550 ms | 1,163 tests, 22 skips, 912.584 s |

Every job used exact Node 24.18.1 and passed Ruff, formatting of all 190
files, zero-error Pyright, the complete suite, both distribution builds, and
the isolated installed-wheel verifier. This closes the publication gate for
the implementation commit; it does not change any nonclaim below.

## Explicit nonclaims and next blockers

This implementation does not establish any of the following:

- wheel signing, package provenance, publisher authenticity, Git commit
  identity, or dependency-closure authenticity;
- legal rights, source truth, revision capture, trusted time, or external
  custody;
- a complete runtime manifest or runtime distribution binding;
- eligibility for the frozen strict V1 resolver while its canonical-byte
  requirement conflicts with the two frozen parent resources;
- an external trust root, authenticated authority proof, one-attempt grant,
  or source-access authorization;
- the strict cross-artifact runtime verifier, root classifier, terminalizer,
  restart/recovery implementation, acquisition client, deterministic parser,
  evaluator, two-pass execution, or retention supervisor;
- a receipt, pass proof, observation, terminal result, admitted join,
  transcription, translation, decipherment, prize submission, or prize
  result; or
- operating-system network isolation merely because the loader itself made
  no network call.

Current status remains
`preregistered_static_prerequisite_blocked_not_authorized`,
`not_authorized`, `not_executed`, and
`NONE_no_source_access_executed`.

The next implementation checkpoint is the missing source-free runtime
boundary, especially the transitive runtime-input manifest, reproducible
runtime distribution, complete dynamic schemas, independent bootstrap/trust
interface, and strict verifier. In parallel, the exact-two canonical
incompatibility must be resolved by a newly frozen normative profile or a
re-frozen parent chain; simply supplying the two runtime bindings is
insufficient. Only a later exact authenticated authority proof may bind an
eligible static profile and the runtime commit and authorize one acquisition.
Generic instructions to continue are not that future authority.
