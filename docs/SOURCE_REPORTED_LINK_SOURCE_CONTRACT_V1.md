# Static source registration and rights contract

**Evidence record timestamp:** `2026-08-01T07:07:54+09:00`

**Source checkpoint:** `90f3fd3bea1177034451283795ad13ccb4b31bcf`

**Parent checkpoint:** `45d946a462dd85aa3025ed9ad9c0465541bd85be`

**Claim status:** static repository-only preregistration; blocked, not
authorized, not executed, and not an observation, source revision receipt,
runtime evaluator, source-link result, join, translation, decipherment, or
prize result

## Purpose and execution boundary

This contract is the non-operational follow-up to the frozen
[source-reported-link decision policy](SOURCE_REPORTED_LINK_POLICY_V1.md). It
registers the already public Penn item-page URI family as a distinct source
layer, freezes conservative rights handling, and specifies a future bounded
acquisition/receipt interface and the complete ordered inspection roster.

Static registration is not an exact Penn source revision, rights clearance,
permission to retrieve a source, or permission to execute the policy. The
contract status remains
`preregistered_contract_blocked_pending_revision_receipt`; authorization is
`not_authorized`, execution is `not_executed`, and source access under the
contract is false. No observation, pass seal, result, revision receipt,
revision-set digest, completeness-attestation digest, operational parser, or
runtime evaluator exists.

## Exact candidate binding

The source checkpoint above was recorded only after the exact five-file
candidate was committed without byte or mode changes. The committed
checkpoint is based on parent
`45d946a462dd85aa3025ed9ad9c0465541bd85be`; all five paths use mode `100644`.
Its exact binary diff SHA-256 is
`c2d4c4ca55c68460a0e83c5c688578e032e61696107182c789d3a723455a90cc`,
and the same diff with `--full-index` has SHA-256
`ed0c64c871735ce807cf9d8c899b72c8f10d375e77b052b3adcb0baae42c29b6`.
The candidate has 2,410 additions and two deletions.

| Path | Bytes | SHA-256 |
|---|---:|---|
| `registry/source-reported-link-source-contract-v1.json` | 29,059 | `e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f` |
| `registry/sources.json` | 43,235 | `e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584` |
| `schemas/source-reported-link-source-contract.schema.json` | 30,752 | `e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78` |
| `tests/test_source_reported_link_policy.py` | 16,971 | `abeaa9a2ee1dbb06c278389abeef70879b531a3674536ef199615a3fd6358c0d` |
| `tests/test_source_reported_link_source_contract.py` | 36,980 | `2924e9037f5b2bee7ff84e2374630488d689745d2b7fd474d5e764a40ccf1ebe` |

The contract also binds the exact frozen policy, policy schema, parent
preselection registry/schema, post-transition source registry, and source
registry schema by size and SHA-256. A hash is a byte-identity commitment; it
does not prove authenticity, custody, rights, trusted time, or caller honesty.

## Nonretroactive source registration

The frozen policy records the Penn item-page layer as `unregistered` with a
null source-registry binding. That was the exact state at the policy
checkpoint and is not rewritten. This later contract records an explicitly
nonretroactive transition to
`registered_static_no_revision_receipt` and binds the post-transition source
registry entry `penn-museum-object-pages`.

The new source entry names these five exact public URIs in first-parent-
occurrence order:

1. `https://collections.penn.museum/collections/object/83830`;
2. `https://collections.penn.museum/collections/object/83829`;
3. `https://collections.penn.museum/collections/object/149372`;
4. `https://collections.penn.museum/collections/object/238862`; and
5. `https://collections.penn.museum/collections/object/329820`.

Its access time, landing page, and snapshot hash remain null. Its registry
instructions explicitly authorize no access, retrieval, revision capture,
source inspection, subresource request, or media request.

## Rights layers

Rights remain layer-specific and fail closed:

- the Mackay report locator is registered at its existing exact 27,802,606-
  byte revision with SHA-256
  `93a76551ab048c6a455b4239730dce718b96cd5b3747852b025858d86b253ef0`;
  its rights remain unknown and its scope remains link-only;
- Penn bulk metadata remains the separate `penn-museum-collections-data`
  source under CC BY 4.0; and
- the Penn item-page association is registered separately with unknown
  rights, null license/evidence/holder values, link-only scope, and no content
  or media included.

Penn bulk metadata's CC BY 4.0 license is explicitly not inherited by the
item-page layer. False redistribution and derivatives fields are conservative
project handling, not an inferred legal prohibition. No rights clearance or
legal determination is claimed.

## Five receipt members, six revisions, and six link slots

Three cardinalities are deliberately distinct:

| Surface | Count | Meaning |
|---|---:|---|
| Future Penn receipt members | 5 | One member for each exact Penn item URI |
| Ordered source-revision resources | 6 | Existing Mackay report plus five future Penn revisions |
| Ordered inspection/result slots | 6 | One slot for every frozen parent link row |

The five-member receipt cannot substitute for six-slot inspection coverage.
The source revision set is ordered as the Mackay container followed by the
five Penn members above. The inspection slots remain, in order, SF 2000,
SF 3495, SF 3493, SF 2428, SF 3051, and SF 2558. SF 3495 retains its
unresolved excavation-location axis. SF 3051 and SF 2558 remain distinct link
slots in the same collision group even though both reuse Penn resource
329820; that declared reuse is not a duplicate slot.

The exact six-task roster digest is
`sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f`.
Coverage is keyed by the six ordered link IDs, not by the five Penn resources.
Aggregation, omission, row substitution, and post-inspection replacement are
forbidden.

## Frozen future request and response profile

The future request profile is fixed but not authorized:

- exactly one anonymous HTTPS `GET` for each declared Penn URI;
- exact `Accept: text/html` and `Accept-Encoding: identity` end-to-end
  headers, with no additional end-to-end headers;
- TLS certificate and hostname validation required;
- no proxy or environment proxy, cache reuse, authentication, cookies,
  netrc/credential files, client certificate, request body, browser, script,
  subresource, or media retrieval;
- redirects forbidden, maximum hops zero, empty redirect chain, and
  `final_uri` exactly equal to `requested_uri`;
- no query, fragment, userinfo, nondefault port, or source substitution;
- 10-second connect and read-idle limits and a 30-second overall deadline per
  request; and
- a body size from one byte through 10 MiB per member and at most 50 MiB for
  all five members.

An admissible response must be complete, nonempty, HTTP 200, and normalize to
`text/html`. Missing or case-varied identity `Content-Encoding` normalizes to
the non-null literal `identity`; every other content coding is rejected and
decompression is forbidden. Revision bytes are the exact response-body
octets after HTTP transfer decoding and before any charset or text decoding.
Byte size and tagged lowercase SHA-256 are recomputed over that same layer.

Receipt members require 13 fields. Eleven are non-nullable:
`resource_id`, `requested_uri`, `final_uri`, `redirect_chain`,
`retrieved_at`, `http_status`, `content_type`, `content_encoding`,
`response_representation`, `byte_size`, and `sha256`. Only `etag` and
`last_modified` are nullable. Those two fields and `retrieved_at` are
nonidentity metadata and cannot substitute for revision identity, rights, or
trusted time.

Any transport, TLS, hostname, proxy, credential, cache, redirect, HTTP,
content, size, hash, canonicalization, mapping, ordering, or digest failure
hard-rejects the input while the prerequisite state remains
`contract_blocked`. It emits no scientific terminal result, partial receipt,
or partial digest and cannot become `unresolved` or `no_link`. A retry would
require separate authority for the complete five-member ordered attempt.

## Future receipt, revision set, and completeness framing

The future receipt payload must bind its fixed ID/version/status, the exact
contract ID and final contract SHA-256, the exact post-transition source-
registry SHA-256, five members, and the exact ordered resource IDs. Its digest
uses domain
`indusbench:source-reported-link:source-revision-receipt:v1`, a NUL separator,
and the contract's canonical JSON profile. The digest is an external
`revision_receipt_sha256` commitment in a separate envelope; it is not a
self-hash inside the receipt payload.

The six-resource revision set uses the separate domain
`indusbench:source-reported-link:source-revision-set:v1`. Its ordered
projection binds resource ID, requested/final URI where applicable,
representation, byte size, and body SHA-256. Its output
`source_revision_sha256` is the exact value required by the parent policy's
source-revision checks; the receipt digest cannot substitute for it.

A future row-absent completeness attestation must bind the exact final
contract hash, receipt hash, source-revision-set hash, six-link roster count
and digest, all six ordered link IDs, processed count six, and actual zero
values for missing, extra, duplicate, unreadable, error, and ambiguous
counts. The two pass-content digests must match; pass IDs and seals remain
outside that equality digest. A bare zero-candidate report without this
complete attestation remains `unresolved`.

No receipt, receipt digest, revision-set payload or digest, completeness
attestation or digest, pass, seal, observation, or result is instantiated by
this checkpoint. The closed receipt schema and separate commitment-envelope
schema are also absent.

## Custody, canonical bytes, and packaging

Future passes would require the exact source bytes in a protected ephemeral
input boundary, but that retention is not authorized. Persistent and
public/repository retention are forbidden, and the separate custody and
deletion contract is missing.

The exact machine states are
`future_protected_ephemeral_retention_status=required_but_not_authorized`,
`persistent_retention_permitted=false`, and
`public_or_repository_retention_permitted=false`.

The contract fixes the `indusbench-io-encode-json-v1` profile: UTF-8 without a
BOM, lexicographically sorted keys, two-space indentation, no floats or NaN,
and exactly one final LF. Draft 2020-12 `const` fixes the object semantically,
but JSON Schema treats numbers such as `6` and `6.0` as equivalent. Schema
validation therefore cannot replace exact canonical-byte comparison;
noncanonical bytes hard-reject.

The exact candidate build produced a 349-member sdist with SHA-256
`08345cab766f00dc4807ab41407e7c3515ffccb3643906c4ce8fb21b4a1ebb0e`
and a 166-member wheel with SHA-256
`a04a546ed81ac0cea2580dfb92f8b5847f1ff0a1ab34247d801dc68e208f4188`.
The sdist includes the complete five-file set. The wheel includes the modified
source registry and the new schema, but not the contract registry or tests.
There is no installed contract loader, operational parser, or runtime
evaluator, so this is not a package-level execution gate.

## Validation and audit record

The exact final candidate passed the 30-test focused policy/contract/parent
set, Ruff lint, Ruff formatting, canonical/schema checks, and the staged-diff
public-boundary and secret scan. Independent adversarial review of the final
bytes reported zero blockers, zero major findings, and zero minor findings.

Two earlier full-suite attempts were intentionally interrupted after
adversarial review identified specification issues in the then-current
candidates. The first candidate was superseded to close receipt, URI,
revision-set, completeness, and protected-retention ambiguities. The second
was superseded to correct the `Content-Encoding` nullability contract.
Neither interruption was caused by a test failure, and neither attempt is
reported as a completed validation run.

Final full-suite result for the exact committed bytes:
`Ran 1106 tests in 1023.743s; OK (skipped=19)`.

Source commit and public CI evidence:

- source commit: `90f3fd3bea1177034451283795ad13ccb4b31bcf`;
- public CI:
  [run 30667904927](/megu0xxx0x/indus-open-benchmark/actions/runs/30667904927),
  completed successfully;
- exact head `90f3fd3bea1177034451283795ad13ccb4b31bcf`; Python
  3.11, 3.13, and 3.14 respectively recorded Quicknet/full-suite durations
  of 425.727693 ms/642.201s, 522.243511 ms/978.761s, and
  512.327502 ms/887.018s. Each matrix passed Quicknet 6/6 and 1106 full
  tests with 22 skips, plus Ruff, the 184-file format check, zero-error
  Pyright, sdist, and wheel builds.

These values were recorded only after the corresponding event completed
against the exact source checkpoint. Local tests, archives, hashes, and CI do
not establish independent custody, trusted time, caller honesty, source
authenticity, or scientific correctness.

## Non-execution and nonclaims

During this checkpoint, no request was sent to a research or protected source
endpoint; no response body, external source byte, image, page, plate,
subresource, media, Helsinki row, or protected corpus was opened; and no
institution or source holder was contacted. Repository validation and builds
are outside that statement and authorize no source access.

There is no runtime evaluator, parser, receipt, pass, observation, roster
attestation, source-reported-link/no-link result, truth authentication,
context verification, field-number verification, object authenticity,
physical-identity decision, source join, transcription, translation,
decipherment evidence, evaluation admission, claim authorization, prize
submission, or prize result. Distinct machine pass IDs and seals would not
prove human, model, organizational, or source independence, blinding, or
nonexposure.

## Next gate

Safe work remains specification-only until a closed receipt schema, separate
receipt-commitment envelope, protected ephemeral custody/deletion contract,
strict canonical loader, operational parser, runtime evaluator, and a new
explicit authority decision exist. Only then could a separately authorized
five-member acquisition create the exact six-resource revision set needed for
the two coded machine passes. Any invalid or incomplete prerequisite remains
blocked and cannot be relabeled as a source-link or no-link result.

## Later static prerequisite follow-up

The later
[static evidence-prerequisite contract](SOURCE_REPORTED_LINK_EVIDENCE_PREREQUISITES_V1.md)
nonretroactively freezes the receipt, commitment-envelope, revision-set, and
completeness schemas plus a protected custody/deletion/recovery blueprint.
That follow-up preserves every historical absence and nonclaim above. It does
not implement the independent bootstrap trust root, strict runtime verifier,
acquisition client, deterministic parser, evaluator, dynamic authority or
result schemas, durable recovery state machines, or an authority record. No
source access or execution occurred.
