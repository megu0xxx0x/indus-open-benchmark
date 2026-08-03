# NMFA source-free exact measurement core V1

**Checkpoint:** 2026-08-03 11:17 JST

## Outcome

The second executable component on the path to the typed NMFA execution
bundle `E` is implemented. It turns already frozen, caller-bound X and Y
records into exact score, canonical-target, and rank-statistic states. It does
not choose a model, open a source, create a split, apply a scientific gate, or
fit a numeric reading from score to target.

This component is deliberately `development_component_not_complete_E`. Its
output is not a reading, translation, decipherment, submission, or prize
result.

## Closed data flow

The core has three code and schema boundaries:

1. The X scorer receives the full value-free `{g_id, primary_f_id}` roster,
   one X batch, its separately expected raw digest, and one separately
   expected model digest. It has no Y, partition, cell, or outcome field.
2. The Y normalizer receives the same full value-free roster, one Y batch,
   its separately expected raw digest, and one separately expected target-
   contract digest. It has no X, model, score, length, partition, or cell
   field.
3. The rank-statistics module receives protected X and Y receipts plus a
   separately declared metric subset roster. The subset contains no
   partition, cell, or outcome label, and the aggregate metric receipt repeats
   no item rows.

The full roster has at least 160 rows. Rows are sorted, and both G identifiers
and primary-F identifiers are individually unique. X, Y, and their receipts
must cover the complete roster exactly. A metric roster may select a nonempty
ordered subset but cannot add an identity outside the full roster.

Every public calculation entry point takes raw canonical bytes and a separate
expected raw digest where an external byte identity exists. A caller-
constructible validated object is never accepted as authority. All receipt
verification entry points recompute their component and require exact
canonical byte equality.

## X model and score

The scorer implements only the parent protocol's positive additive class:

\[
S(x)=\sum_j w_j n_j(x)
\]

It requires one to eight sorted, content-addressed, pairwise-disjoint classes;
integer weights from 1 through 16; and weight gcd equal to one. It permits a
valid zero score and rejects negative weights, interactions, intercepts,
context coefficients, row exceptions, and direction reversal through the
closed model schema.

Each physical original supplies ordered side, line, and token arrays. Indices
are zero-based, contiguous, and equal to array position. Side and line IDs are
globally unique across the complete batch. Each side record denotes one
eligible physical side or inscription surface in frozen source order. Every
token has one closed disposition; only included tokens contribute.

The output preserves three exact nonnegative integers per roster row:

- `score` — the weighted additive score;
- `l_total` — the number of included tokens; and
- `l_distinct` — the number of distinct frozen `length_identity_id` values
  among included tokens.

The score receipt includes no token identity, class identity, class count, or
source-binding value.

## Y canonicalization

The Y normalizer supports exactly one declared family per batch:
`direct_count`, `mass`, or `capacity`. Inputs and positive scale multipliers
are irreducible integer rationals. Conversion performs cross-cancellation and
arbitrary-precision integer multiplication without floating point, offset, or
rounding.

`direct_count` permits zero but must remain an integer. Mass and capacity must
remain strictly positive. The canonical unit must have an explicit identity
conversion of one over one. Input limbs are bounded by the signed 63-bit
positive maximum; reduced output limbs are bounded to 126 bits.

The target receipt exposes only the canonical irreducible rational for each
G/F row. It does not repeat the source unit, source value, source binding, X,
score, or length.

## Exact rank statistics

Ties use one-based doubled average midranks. For a tie block occupying ranks
`a` through `b`, every member receives integer rank `a + b`. Rational target
order uses exact cross multiplication.

For doubled rank vectors `x` and `y`, the core retains:

\[
C=n\sum xy-\sum x\sum y
\]

\[
V_x=n\sum x^2-(\sum x)^2,\qquad
V_y=n\sum y^2-(\sum y)^2
\]

and therefore `rho = C / sqrt(Vx * Vy)`. Insufficient observations, constant
left values, constant target values, and both constant are distinct closed
undefined states.

The canonical receipt keeps exact decimal integer strings for `C`, `Vx`,
`Vy`, and their radicand. A 12-place decimal and scaled integer are produced
with integer square-root comparison and round-half-even. This Q12 projection
is display-only and is not authorized for a future gate, delta, bootstrap
ordering, or control ordering. A public exact helper compares one defined rho
with one nonnegative unit-interval rational threshold after checking the
Cauchy bound. Exact multi-radical delta ordering remains explicitly unbound.

## Information and authority boundary

Module and schema separation prevents accidental field flow, but it is not an
access-control system. Protected states expose canonical receipt bytes to the
authorized caller, and one process could call both X and Y APIs. A later
custodial wrapper must enforce separate processes or principals, opaque
transport, externally pinned receipt identities, trusted chronology, and
permanent one-use state.

Likewise, the core proves that supplied bytes agree with caller-supplied
digests. It does not authenticate the external origin of the roster, claim
binding, X batch, Y batch, model, target contract, metric subset, or upstream
receipt digests. Source completeness, all-side truth, transcription policy,
target provenance, rights, custody, identifier non-grinding, runtime-code
immutability, and external time remain outside this component.

The evaluator bundle rechecks its plan, predecessor plans, schemas, four NMFA
runtime modules, and shared canonical encoder before and after component work.
That detects packaged-byte drift but does not attest a mutable host or prove
that imported code cannot change independently. Operational use therefore
still requires an immutable, externally pinned runtime environment.

Malformed installed-bundle JSON, including an unencodable lone Unicode
surrogate, is normalized to the fixed package-resource error before any bundle
field is trusted.

## Verification

The synthetic full roster has 160 distinct G/F rows. A four-row metric subset
produces scores `[0, 0, 1, 2]`, targets `[0, 1, 1, 2]`, exact covariance 60,
both variances 72, and display rho `0.833333333333`. The suite also covers
zero scores, excluded tokens, G/F duplication, short full rosters, side/line/
token ordering, class overlap and gcd, 63-bit and 126-bit rational boundaries,
count zero, mass zero rejection, undefined states, exact threshold collapse,
round-half-even ties, malformed and noncanonical JSON, lone surrogates, wrong
types and digests, receipt tampering, resource drift, and mid-computation
bundle changes.

The installed-wheel verifier checks all bundle-bound bytes and schemas, direct
dependency metadata, archive paths, and wheel/repository parity. It then runs
the complete synthetic X-to-Y-to-metric chain from an empty directory under
isolated Python, with network and file-write audit events denied, and verifies
all three receipts by exact reexecution.

## What remains before complete `E`

1. Freeze one shared deterministic counter stream, unbiased sampling, and the
   exact comparison/order rules needed by multi-radical deltas.
2. Implement 10,000 paired stratified bootstrap schedules and their exact
   confidence-order statistics.
3. Implement N1 support, Hall certificates, matching unranking, and 99,999
   assignments; then N2 whole-G strata and 99,999 permutations.
4. Implement confirmatory cell/effect/control gates, exact terminal
   precedence, and prospective chronology and receipts.
5. Audit one final content-addressed `E`, then bind it only through a new
   successor preflight and an externally authenticated custodial activation
   wrapper.

Until those layers exist, no real X or Y access and no scientific execution is
authorized by this component.
