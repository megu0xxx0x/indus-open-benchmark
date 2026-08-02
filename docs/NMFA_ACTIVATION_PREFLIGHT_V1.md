# NMFA activation preflight companion V1

**Status date:** 2026-08-02

## Outcome and status

This document specifies a source-free, non-operational activation companion
for the
[NMFA value-blind preregistration gate V1](NMFA_VALUE_BLIND_PREREGISTRATION_GATE_V1.md).
It defines two deterministic checkpoints:

- `PREMETADATA_READY`, before any claim-instance source metadata are accessed;
- `PREVALUE_READY`, after a declared metadata-only inventory is frozen and
  before either transcription `X` or target `Y` is accessed. Completeness
  against an external source universe is not established by this release.

The companion does not modify the exact bytes of the
[draft parent protocol](NUMERAL_METROLOGY_FUNCTIONAL_ANCHOR_PROTOCOL_V1.md),
the gate plan, the gate evaluator bundle, or either V1 gate schema. It is an
additive successor boundary. A later activation wrapper must bind those
immutable resources and this companion by exact raw identities.

The installed V1 companion is deliberately blocked. Its compiled activation
profile does not bind a complete typed execution bundle, an externally
authenticated trust profile, an external time anchor, a permanent one-time consumption
registry, or a final activation wrapper. Those five missing bindings are
mandatory blockers, not warnings. Consequently, a syntactically correct
request and valid synthetic signatures still cannot produce an operational
ready state.

This release contains no real source identifier, inventory, transcription,
measurement, target, archive, operational key/signature, access receipt, prediction,
result, submission, or prize entry. It does not authorize metadata, `X`, or
`Y` access and does not claim a reading, translation, decipherment, scientific
result, or prize eligibility.

## Why a separate companion is required

The existing V1 gate evaluates a retrospective protected manifest assembled
after X and Y have been prepared and sealed. It cannot prove that authority,
rights, clean roles, source rules, or the complete prevalue population were
fixed before access. A declaration inside that later manifest cannot undo an
earlier exposure.

The activation companion therefore precedes the gate and has a different
job. The installed evaluator checks closed signed declarations and exact
package/request relations; a future activation wrapper must authenticate the
external conditions under which later work may begin. It does not evaluate
the NMFA hypothesis and does not inspect real values.

The companion also cannot manufacture its own trust. Operational trust in
candidate-selected or trust-on-first-use keys is forbidden. A request cannot
embed a public key, but the installed API can only match a separately supplied
profile to a caller-expected digest; it cannot authenticate that digest's
origin and therefore remains externally blocked. The evaluator holds no
private key and creates no trusted timestamp. External roles sign its
canonical subjects, an external verifier verifies them, and a separately
administered registry must consume each stage once.

## Immutable-resource and digest DAG

Operational activation uses one acyclic, raw-byte digest graph denoted
`E -> P -> A`:

1. `E` is the exact complete typed NMFA execution bundle. It binds every
   execution plan, closed schema, pure implementation module, fixed vector,
   terminal rule, dependency identity, and distribution resource needed from
   split selection through prospective evaluation.
2. `P` is the exact activation-preflight bundle. It is frozen after `E`, binds
   the raw digest of `E`, and binds the immutable parent protocol, gate plan,
   gate evaluator bundle, preflight plan, schemas, verifier implementation,
   fixed vectors, and a normalized version-pinned dependency contract. Exact
   runtime artifacts and backend provenance remain successor work.
3. `A` is the external activation wrapper. It is frozen after `P` and binds
   the raw digests of both `E` and `P`, the exact external trust-profile
   digest, trusted-time service identity, permanent registry identity,
   permission and custody contracts, role and conflict-domain assignments,
   identifier policy, frozen source/metadata/target/archive rules,
   claim-family scope, and the one allowed claim-slot policy.

Every edge is an exact raw-byte SHA-256 identity. Domain-separated semantic
digests are additional subjects and never replace raw resource identities.
No node contains its own digest. An inventory or bundle that lists its own
members excludes only the top-level self-digest field under its explicitly
versioned rule; no recursive or implicit exclusion is permitted.

The claim-slot reservation binds the final `A` digest. Both preflight stages
bind `E`, `P`, `A`, the immutable V1 resource digests, the claim family,
claim slot, experiment instance, and predecessor chain head. A request cannot
substitute a newer executor, preflight, trust profile, or wrapper after the
reservation.

The source-free installed companion has null operational identities for the
five external blockers. It can test parsing, canonicalization, signatures,
and semantic rejection, but it is not the operational `P` or `A` described
above. Once `E` exists, an operational successor must be frozen in DAG order;
the installed blocked V1 bytes must not be edited in place.

## Canonical input boundary

All machine inputs use the project canonical JSON profile: UTF-8 without BOM,
integer-only JSON, sorted keys, two-space indentation, one terminal LF,
duplicate-key rejection, signed-64-bit integer bounds, closed schemas, and
fixed byte/depth/cardinality limits. Decoding success is not enough; exact
re-encoding must equal the supplied bytes.

Every externally signed object has a closed envelope containing only:

- the Ed25519 algorithm identifier;
- the signer role, actor identifier, and pinned key identifier, but no
  candidate-supplied public key; and
- one canonical, unpadded base64url signature.

The signature message is not free-form. Its fixed domain-separated frame
contains the stage, role, trust profile/domain/revocation snapshot, claim
family, claim slot, instance, sequence, request time, and canonical request-
subject digest. That subject transitively binds the predecessor ledger head
and every other request field. Changing any of them invalidates the signature.

Malformed input produces one fixed contract exception and no partial report.
A canonical, schema-valid request that fails a readiness condition produces a
closed private blocked report. Exceptions and Python representations expose no
private inventory count, identifier, digest, field value, chronology detail,
or signature; the private canonical report bytes retain only the minimum
binding digests and timestamp needed for deterministic reexecution.

## Separately supplied trust profile

The evaluator API receives the trust profile as separate canonical bytes and
an expected trust-profile SHA-256 argument intended for an out-of-band,
read-only configuration boundary. It first verifies raw-byte equality to that digest, the closed
profile shape, declared issuer/domain/time/revocation fields, algorithm, key
identifiers, public-key points, and role set. Only then may it parse a
candidate request. A request cannot embed, replace, extend, or select a trust
root. These checks do not authenticate the issuer, revocation service, or
real-world role controller. The installed API also cannot authenticate the
origin of its expected-digest argument; `EXTERNAL_TRUST_PROFILE_UNBOUND`
therefore remains mandatory until an operational wrapper pins it.

The closed role set is:

- `authority`;
- `governance_reviewer`;
- `metadata_controller`;
- `transcription_controller`;
- `target_controller`;
- `value_barrier_coordinator`.

Each role has one exact Ed25519 public key and a key identifier derived under
the fixed profile rule from the raw public-key bytes. All six role keys must
be distinct. The trust profile also binds controller and conflict-domain
identifiers; the plan and signed role-separation contract bind the conflict
policy. Distinct strings or keys do not prove that the roles belong to
different people or organizations, so this companion explicitly makes no
claim about human, organizational, or financial independence.

The evaluator never receives or generates a private key. The public message
builder accepts a schema-valid request whose `signatures` array is exactly
empty and derives a canonical request subject by omitting that array. Detached
external roles sign their domain-separated messages over that same subject;
the completed request must contain the exact complete role roster. The
evaluator then verifies the envelopes and evaluates the request. It does not
emit a pre-sign semantic decision.

### Ed25519 verification profile

Only Ed25519 is admitted. The verifier requires an exact 32-byte public key
and exact 64-byte signature. Base64url must be canonical and unpadded. Before
library verification, it canonically decompresses both public key `A` and
signature point `R`, rejects the identity, low-order points and torsion-coset
points by requiring nonidentity membership in the prime-order subgroup, and
rejects noncanonical scalar `S`, invalid lengths, and alternate base64url
encodings. The version-pinned cryptographic library then verifies the exact
domain-separated subject. The bundle does not attest the library wheel,
backend binary, or complete runtime environment and claims no formal proof.

No prehash variant, context variant, RSA, ECDSA, shared MAC, key discovery,
certificate fetching, fallback algorithm, or permissive decoder exists. Exact
runtime-artifact provenance remains part of future `E` and operational `P`.

`PREMETADATA` requires signatures from `authority`,
`governance_reviewer`, and `metadata_controller` over the same canonical
request subject. `PREVALUE` requires all six roles: authority,
governance reviewer, metadata controller, target controller, transcription
controller, and value-barrier coordinator. A role swap, missing signer, extra signer,
reused envelope, or signature over a different chain head blocks the stage.

## External time, access ledger, and one-time consumption

A signed timestamp alone is not evidence that source access did not happen.
An operational successor therefore must authenticate all three of the
following externally administered objects:

1. an append-only, signed access ledger whose complete prefix is verified;
2. an external time-anchor receipt over the exact ledger and decision heads;
3. a permanent one-time registry receipt that atomically consumes the exact
   claim slot and stage subject.

The installed request contains only aggregate ledger-head declarations,
counters, a ledger identifier, and adjacent checkpoint relations. It
recomputes those local heads and requires one declared ledger chain, but it
does not receive individual events, a genesis record, an external ledger
signature, or a complete prefix. Consequently it cannot detect an omitted
external event, fork, rollback, or dishonest counter. The report explicitly
sets `access_ledger_prefix_authenticated=false`; full prefix verification is
part of the activation wrapper and typed execution successor.

Before `PREMETADATA`, the signed request declares zero access across metadata,
X, and Y. Before `PREVALUE`, it declares at least one metadata access within
one authorized metadata phase and still declares zero X and Y accesses. The
stage signatures bind these aggregate declarations, but they are not an
authenticated external ledger prefix and do not prove that no other access
occurred.

The permanent registry allows one active chain per claim slot. It uses
compare-and-swap transitions and terminal abort states. At a minimum, it
binds reservation, identifier ceremony, `PREMETADATA` evaluation and
consumption, inventory freeze, `PREVALUE` evaluation and consumption, and
the later value-access transition. Reuse, retry, parallel activation,
rollback, deletion, resalting, and post-consumption supersession are forbidden.

The pure evaluator does not mutate or verify this registry. An operational
ready package is valid only when the evaluator package, all detached signatures, time-anchor
receipt, and registry-consumption receipt agree byte-for-byte on the same
subject. A locally returned decision without registry consumption is not a
ready receipt.

## Permission, authority, rights, and custody contract

The installed request contains typed authority/rights declarations and opaque
evidence commitments, not the evidence envelopes themselves. It binds phase,
actions, purposes, validity interval, revocation-snapshot commitment, seven
layer-specific permission matrices, scope commitments, and evidence-envelope
commitments. The evaluator checks their closed shape and internal declaration
rules; it does not authenticate legal authority, inspect evidence, or prove
that a commitment refers to sufficient evidence.

The closed permission matrix keeps seven layers separate: source-frame
metadata, transcription X, canonical context C, physical identity F,
dependence G, target Y, and derived aggregate output. Each layer has typed
retrieve, retention, analysis, derivation, custodial-transfer, aggregate-
publication dispositions. `prize_submit` is fixed to `NOT_APPLICABLE` because
prize-program acceptance and submission rights are outside this preflight.

Permission at one layer never implies permission at another. Public
availability does not imply reuse permission. Conservatively, the installed
`PREMETADATA` request requires every downstream data-layer permission
declaration already to be `PERMITTED`; it does not implement a later
permission-acquisition procedure. Those declarations still require external
evidence authentication.

Custody binds separate metadata, X, and Y controllers, archives, credentials,
release rules, retention and deletion procedures, incident states, and
recovery behavior. A declaration of separate role identifiers does not prove
physical isolation or independent control. Those remain external assurances
that the public evaluator cannot establish.

## Metadata-only channel

`PREMETADATA_READY` is meaningful only for a byte-level metadata-only channel.
The installed source policy records closed requirements and opaque profile
commitments for transport, parser, projection, cache, logging, proxy capture,
browser use, and mixed-value transport. It does not fetch provider bytes or
prove that those commitments describe the real channel. A future wrapper must
freeze and verify the exact endpoint or offline resource, revision semantics,
response media type, parser, byte allowlist, normalization, and failure
behavior before access.

Field-level filtering after downloading a mixed X/Y response is not
metadata-only access. If the source necessarily co-transports inscription
content, transcription, target values, value-bearing status, images, or other
forbidden fields, an operational wrapper must block the channel. A browser
page, proxy, cache, preview,
debug dump, telemetry sink, or server log that exposes those bytes also
blocks unless it is explicitly inside the same protected, verified channel
and permitted scope. There is no best-effort redaction fallback.

An operational activation wrapper must also freeze the target rule before
metadata access: exactly one direct target family (`count`, `mass`, or
`capacity`), one canonical unit and conversion contract, missing/ambiguous
handling, provenance requirements, and every value-bearing field that later Y
access may expose. The installed companion binds only a target no-access
policy because the final wrapper is intentionally absent.

## `PREMETADATA_READY`

The first checkpoint request binds one closed source-free preparation
declaration. Its request includes:

- declared `E`, `P`, and `A` bindings plus immutable V1 resource identities;
- one declared claim-family/slot reservation subject;
- the claim family, identifier-key commitment, and declared ceremony record;
- trust-profile, time-anchor, registry, and access-ledger commitments;
- authority, permission, custody, role, conflict-domain, and retention
  contracts;
- metadata-channel/parser policy declarations and commitments that an operational
  wrapper must transitively bind to the complete source-frame, context,
  physical-identity, exposure, relation, target, archive, staged-release,
  nonce-event, and no-retry rules; and
- an aggregate signed zero-access declaration for metadata, X, and Y.

The evaluator domain-binds claim family, slot, instance, activation-root
declaration, reservation, identifier-key commitment, and ceremony, and checks
their adjacent local sequence/time relations. It verifies three request
signatures, installed package bindings, the separately supplied trust-profile digest,
and the absence of named inventory/value fields. It does not verify the
external time service, registry state, HMAC derivation, key nonrotation, or
resalting history; those omissions are covered by compiled blockers.

A future registry-consumed `PREMETADATA_READY` receipt would permit only one
declared metadata phase, with every call recorded, through the verified
channel. It does not permit X, Y, archive payload creation, model work,
registration, execution, or public
reporting. Any deviation, extra request, parser fallback, mixed-value response,
or uncertain access event terminally aborts the claim slot.

## Declared prevalue inventory

After the permitted metadata phase and before either value layer opens, the
metadata controller signs one declared ordered inventory. The installed
evaluator checks internal roster consistency, not completeness against an
external source universe. The declaration contains:

- supplied source records, revisions, views, entries, and their single
  opaque physical-original identifier `F`;
- one contiguous, sorted, unique ordered F roster, with every source entry
  mapped to exactly one F and every F covered by at least one source entry;
- typed canonical-context status inputs `C` for each supplied F, opaque
  evidence commitments, and ordered nuisance status inputs;
- metadata-known base-eligibility contributions `Epre` for each F;
- a declared set of pre-X relation edges and deterministic row-level
  status-to-disposition checks;
- declared prior project exposure for each F with policy/proof commitments;
- value-empty archive-preparation state for the exact ordered F roster.

Source-record identity has a functional dependency on F across revisions and
views within the supplied roster. Duplicate record IDs, duplicate F IDs,
noncontiguous order, unmapped entries, uncovered supplied F, or roster
disagreement blocks the checkpoint. Incomplete/conflicting context and other
known deficiencies are frozen as exact `Epre` reason codes rather than
misrepresented as eligibility.

`Epre` contains only reasons already established without X or Y. It is a
contribution set, not final base E. It may record a known disqualifying reason,
but it may not assert `ELIGIBLE`, calculate final E, or infer a transcription-
or target-derived reason. Final E is later formed from the complete union of
the frozen prevalue contribution and separately audited X and Y contributions.
The union is sorted, unique, and complete. An empty final reason union alone
maps to the immutable gate's `[ELIGIBLE]` representation; any reason makes
base E false.

The installed field is deliberately named `declared_pre_x_relation_edges`.
For each supplied edge, confirmed status requires `UNION`; possible or
unresolved status requires `EXCLUDE_BOTH`. An empty declared set is valid and
does not claim a complete `R0`. The evaluator does not establish the external
relation universe, no-evidence rows, or transitive `Rpre` closure. Those are
explicitly deferred to the typed execution bundle and activation wrapper.

Prior exposure is separate from E. The installed evaluator requires one
ordered status and proof binding per F and blocks `UNKNOWN`; it does not claim
to have independently queried or authenticated a complete external ledger.
An operational successor must derive each status from the fixed exposure
policy plus the complete signed ledger, not a curator-selected boolean.
Unknown or incomplete exposure history blocks. A confirmed exposure later
excludes the complete final G component under the immutable gate precedence;
it does not silently remove the F from the inventory. Final whole-G exclusion
uses the fixed order prior exposure, identity/context conflict, unresolved
dependence, then none; a later class cannot mask an earlier one.

The generic archive profile is frozen before metadata access. The prevalue
instance may bind only the exact F roster, archive roles, payload schema,
encryption and staged-release algorithms, and a value-empty prepared state.
It must not contain ciphertext, a Merkle root, a keyed or unkeyed dataset
digest, seal randomness, per-record nonce, target/transcription status, or a
claim that the later payload already exists.

## Forbidden prevalue surface

The PREVALUE boundary uses a closed schema, fixed-shape opaque-identifier
syntax, and cross-field checks so that no named generic free-text or extension
field is available for a value or value-derived choice. This is a typed-
surface claim only: syntax cannot prove that an opaque identifier or digest
was not derived from a value. Named forbidden fields include:

- transcription text, signs, tokens, allographs, normalized sequences, and
  transcription completeness or ambiguity status;
- target numbers, units observed with a value, numeric strings, measurement
  status, target completeness or ambiguity status, and value-derived
  eligibility;
- final E, final G, model features, scores, predictions, ranks, metrics,
  thresholds evaluated on data, selected holdout cells, and N1/N2 outcomes;
- X/Y plaintext, ciphertext, payload lengths, Merkle roots, archive seals,
  encryption randomness, unkeyed dataset digests, or value-bearing error and
  log text; and
- any inventory count, digest, or summary exposed through a public result
  surface. Private declared counts and binding digests are used only for
  internal consistency checks.

An operational successor may permit opaque identifiers only after their
derivation, namespace, and non-value role are externally verified before
access. This installed evaluator checks only `hmac-sha256:<64 lower-hex>`
syntax and explicitly reports origin verification as false. Hashing a value
does not make it value-free. An encrypted, encoded, redacted, rounded,
bucketed, or hashed X/Y
field remains forbidden at PREVALUE.

## Value barriers and `PREVALUE_READY`

X and Y use separate controllers and separate access barriers. Before
PREVALUE evaluation, both controllers sign distinct `PREPARED_LOCKED_NOT_ARMED_NOT_RELEASED`
commitments over the same claim slot, declared inventory head, supplied F
roster identity, archive contract, ledger-head declaration, and zero-value-
access declaration. The installed evaluator checks their layer/role bindings,
distinct CAS-token commitments, local sequence, and prepared state. It does
not perform a compare-and-swap.

The future external protocol is two phase: verify and consume the package
containing the six-signature request and reexecuted evaluator report as
`PREVALUE_READY` in the permanent registry, then atomically CAS both still-
current locked commitments to one joint `ARMED_NOT_RELEASED` state. Neither
controller may arm alone.

Any race, stale head, partial prepare, unilateral unlock, mismatched roster,
timeout with uncertain state, or failed compare-and-swap terminally blocks
the claim. The wrapper must recheck the same heads immediately before registry
consumption and again in the post-consumption arm CAS. Only that external
atomic protocol can close the interval between evaluation and value access.

The installed PREVALUE request binds the declared inventory, deterministic
metadata-known Epre codes, declared pre-X relation edges, prior-exposure
commitments, two value-empty archive preparations, two `PREPARED_LOCKED`
barrier commitments, and the
predecessor PREMETADATA request/report digests. The verifier reexecutes
PREMETADATA and requires byte-for-byte equality with its supplied private
report, then verifies all six PREVALUE signatures. It cannot verify an
external time service, permanent ledger prefix, atomic arm transition, or
one-time registry consumption; the corresponding compiled blockers therefore
remain mandatory. Because installed PREMETADATA can only be blocked, the
public PREVALUE API cannot reach a semantically valid predecessor; the
positive PREVALUE core vector in tests uses an internal synthetic replacement
and is not a reachable ready report. An operational successor must add and
verify the joint authorization plus both controller CAS-arm receipts described
above.

Only after the PREVALUE ready package is consumed may a separate registry
compare-and-swap transition the joint barrier from `LOCKED` to the exact
authorized unopened X/Y state. This transition is outside the pure evaluator,
cannot be performed by one value controller alone, and cannot be retried after
an uncertain or failed state. `PREVALUE_READY` does not itself reveal or read
a value.

## Required chronology

The externally anchored strict order is:

1. immutable source-free parent protocol and V1 candidate gate freeze;
2. complete typed execution bundle `E` freeze;
3. operational preflight bundle `P` freeze;
4. activation wrapper `A` freeze;
5. single claim-slot reservation binding `A` and all earlier resources;
6. one identifier-key ceremony under the reserved policy;
7. three-signature PREMETADATA request and evaluator-package verification;
8. registry consumption that alone establishes `PREMETADATA_READY`;
9. the one permitted claim-instance metadata phase, with every call logged;
10. declared inventory, deterministic `Epre`, declared relation-edge, and
   exposure-commitment freeze;
11. X and Y separately committed to `PREPARED_LOCKED` with zero value access;
12. PREVALUE request-subject freeze, six signatures, and evaluator-package
    verification;
13. registry consumption that alone establishes `PREVALUE_READY`;
14. joint compare-and-swap to `ARMED_NOT_RELEASED`;
15. first separately authorized X or Y access;
16. X/Y archive construction and in-custody audits;
17. post-seal V1 candidate-gate evaluation, joint E/G review, and external
    registration of the single active chain;
18. first qualifying nonce, deterministic split, development release, one
    model freeze, N1 support freeze, holdout prediction freeze, N1 assignment,
    Y reveal, terminal decision, and any later prospective phase under `E`.

Every `<` boundary is strict except the atomic paired barrier operation. A
timestamp ordering assertion without the ledger and registry chain is
insufficient. A later artifact cannot repair a missing or out-of-order earlier
checkpoint.

## Decision and private report

The closed stage terminals are `PREMETADATA_BLOCKED`,
`PREMETADATA_READY`, `PREVALUE_BLOCKED`, and `PREVALUE_READY`. The installed
source-free V1 profile always includes these compiled blockers:

- `TYPED_EXECUTION_BUNDLE_UNBOUND`;
- `EXTERNAL_TRUST_PROFILE_UNBOUND`;
- `EXTERNAL_TIME_ANCHOR_UNBOUND`;
- `CONSUMPTION_REGISTRY_UNBOUND`;
- `ACTIVATION_WRAPPER_UNBOUND`.

Installed semantic reasons cover invalid signatures or role separation,
resource mismatches, claim-chain/scope declarations, rights declarations,
local ledger/chronology faults, predecessor mismatch, supplied-inventory
inconsistency, invalid deterministic `Epre`, malformed declared relation
edges, archive preparation, and value-barrier commitments. Some schema-listed
reason codes are reserved for an operational successor and are not emitted by
this installed evaluator: `TRUST_PROFILE_INVALID`,
`FORBIDDEN_VALUE_SURFACE`, `CUSTODY_NOT_READY`, `SOURCE_RULE_INVALID`, and
`TARGET_RULE_INVALID`. Invalid trust/value-schema inputs instead fail at the
fixed contract-exception boundary. Reasons that are emitted are sorted and
unique by fixed precedence.

The report and its directly readable fields are private-only. There is no
authorized public-summary serializer, and its Python representation is a
constant protected marker. The canonical private bytes do contain
resource/request/trust binding digests, the request timestamp, stage,
terminal, and fixed reason codes, but no request body, signature, key,
identifier, inventory count, source name/path, ledger detail, permission
evidence, or failure-localizing value. Publication of even an aggregate
private report is not authorized.

Schema validation of a report does not prove authenticity or semantics.
Future operational verification requires the exact requests, external trust
profile, time and registry receipts, installed bundles, deterministic
reexecution, signature verification, and byte-for-byte report equality. The
installed evaluator verifies only the packaged and caller-supplied inputs
described above. The report asserts no source
rights, human independence, external custody, trusted execution, scientific
validity, decipherment, or prize status merely because a terminal field says
`READY`.

## Adversarial-test coverage and successor requirements

The installed synthetic suite covers only surfaces implemented by this blocked
evaluator: canonical JSON and closed-schema handling; separately supplied
trust-profile equality and shape; strict Ed25519 point, scalar, and base64url
checks; empty-or-complete signer rosters and replay bindings; local claim and
ledger chronology; supplied-roster, deterministic `Epre`, declared-edge,
archive, barrier, and predecessor consistency; closed typed-value surfaces;
private-report representations; and installed-wheel parity.

A future operational `E`/`A` acceptance suite must additionally test
authenticated provider-byte separation; complete signed-ledger
prefix/fork/rollback handling; trusted-time freshness; registry compare-and-
swap, one-use, abort, and retry semantics; real authority/rights/custody
evidence; external source-universe and `R0` completeness plus `Rpre` closure;
barrier-arm races; and full typed execution/terminal behavior. These are
successor requirements, not claims about this release.

The combined threat matrix includes:

- candidate-supplied trust roots, trust-on-first-use, key substitution,
  evaluator self-signing, role swaps, duplicate keys, conflict-domain overlap,
  missing/extra signers, and revoked or expired profiles;
- malformed, padded, or noncanonical base64url; wrong-length keys or
  signatures; identity, low-order, or torsion-coset `A`/`R`; noncanonical `S`;
  signature malleability; stage, role,
  slot, instance, sequence, predecessor, domain, and subject replay;
- canonical-JSON violations, duplicate keys, floats, oversized/deep input,
  unknown fields, dependency/resource substitution, and installed-distribution
  drift;
- installed aggregate-ledger head/counter/identifier mismatches and adjacent
  chronology defects; plus, for the operational successor, ledger gaps,
  rollback, truncation, forked heads, unsigned access, stale time anchors,
  registry replay, parallel claims, failed consumption, and post-abort reuse;
- metadata responses that co-transport X or Y, cache/log/proxy/browser leaks,
  parser fallback, unapproved revisions, target-rule changes, and permission-
  layer inheritance;
- source-to-F functional-dependency violations, duplicate or missing records,
  F-order changes, incomplete coverage, conflicting C, incomplete nuisance
  vocabularies, unknown exposure, ledger/exposure mismatch, and post-access
  inventory mutation;
- malformed, reordered, duplicate, or invalid declared relation edges; plus,
  for future `E`/`A`, incomplete `R0`, incorrect transitive `Rpre`, premature
  final E/G, relation-policy substitution, and final-G claims before X audit;
- ciphertext, hashes of values, roots, randomness, payload/status/length side
  channels, predictions, scores, selected cells, and any other forbidden
  value surface at either preflight;
- X/Y roster mismatch, unilateral or stale lock, prepared-state race,
  compare-and-swap loss, unlock before registry consumption, barrier rollback,
  and uncertain coordinator failure; and
- PREMETADATA report/request tampering, PREVALUE predecessor substitution,
  deterministic-reexecution mismatch, private-report representation leakage,
  and accidental public-summary creation.

Positive synthetic vectors demonstrate only implementation consistency. They
do not establish that a real authority, source permission, controller,
custodian, time service, registry, or nonexposure history exists.

## Next implementation gate: full typed executor

The highest-priority successor is `E`, not source access. Before an
operational preflight can be frozen, one source-free typed execution bundle
must close all decision-bearing semantics now carried only by prose. At a
minimum it must include:

- stable G identifiers and total order;
- raw nonce normalization, provider/event verification, selector framing,
  split-ticket enumeration, and target-blind primary-F selection;
- exact X atom, side/line/token/allograph ordering, candidate-class and length
  parsers, plus the single positive-additive model interface and scorer;
- exact Y canonical-unit conversion to irreducible rationals;
- doubled-integer midranks, exact covariance/variance, fixed-point Spearman
  rho, integer square-root and round-half-even rules, undefined sentinels, and
  threshold-boundary vectors;
- the 10,000 paired whole-G bootstrap PRF, sampling, recomputation, confidence-
  interval order statistic, and failure semantics;
- N1 bin construction, candidate universe, injective-matching feasibility,
  Hall checks, deterministic unranking, sampled assignments, and all 99,999
  runs;
- N2 full-context stratum encoding, movable support, whole-G permutation,
  shuffle framing, all 99,999 runs, and add-one tail calculation;
- closed terminal precedence for invalid, ineligible, insufficient,
  scientific-failure, and pass states;
- prospective source-frame, sensitivity/power, acquisition start, first-
  availability, historical-bridge, completeness, pre-Y prediction, metric,
  bootstrap, permutation, and terminal contracts;
- resource limits, dependency/runtime identities, closed receipt schemas, and
  fixed positive and adversarial vectors for every stage.

The execution interfaces must enforce information separation. The split
selector sees only the frozen selector inventory and nonce. The model and
scorer see X but not Y. The target parser sees Y but not X or predictions.
Joint metrics run only after immutable prediction and N1-assignment receipts.
The pre-Y chain binds every earlier receipt and abort, and the complete
prospective frame must freeze before acquisition begins.

After `E` is independently audited, freeze an operational successor `P`, then
an external `A`, in that order. Only a new exact authority decision for that
completed chain could permit PREMETADATA evaluation on a real candidate. The
current public companion, generic instructions to continue, a synthetic pass,
or the existing candidate gate cannot supply that authority.

## Scientific and public nonclaims

This specification is fail-closed preparation for one narrow falsification
attempt. It is not a data acquisition, corpus, preregistration receipt,
external audit, blind evaluation, model result, sign reading, language
assignment, translation, decipherment, submission, prize claim, or evidence
that the announced prize has an operational entry route.

Role declarations and valid signatures establish only that pinned keys signed
exact subjects. They do not prove who controlled a key, that two humans or
organizations were independent, that no unlogged access occurred, or that an
external institution accepts the protocol. Those questions remain external
governance and evidence obligations. A failure at either preflight stops the
claim slot; it does not invite a retry, substitute source, alternate target,
or weaker protocol.
