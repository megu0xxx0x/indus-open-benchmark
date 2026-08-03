# NMFA source-free deterministic resampling core V1

**Checkpoint:** 2026-08-03

## Outcome

This additive component implements the third executable slice on the path to
the typed NMFA execution bundle `E`: one deterministic counter stream, exact
ordering for rank correlations and paired length deltas, and the fixed
10,000-run four-cell bootstrap.

It consumes separately digest-bound protected selector, score, and target
states. It does not open source X or Y, select or fit a model, authenticate an
external chain head, apply the confirmatory decision gates, execute N1 or N2,
or perform prospective evaluation. Its terminal state is only
`EXACT_PAIRED_BOOTSTRAP_STATE_ONLY`.

This component contains no real source record or target value and produces no
scientific result, numeric sign reading, translation, decipherment,
submission, prize eligibility, or prize result.

## Closed input and stage boundary

The evaluator requires the complete value-free G/F roster, the exact holdout
metric roster, one protected selector assignment, one protected score receipt,
one protected target receipt, and the separately supplied frozen-protocol
chain-head checksum. Every raw object also has a separately supplied expected
raw checksum.

The following alignment is mandatory before a bootstrap run:

- the complete G/F roster equals every selector-assignment row exactly;
- the metric roster equals every and only holdout G/F row, in canonical order;
- selector, roster, score, and target records carry the same claim binding and
  selector-assignment identity;
- score and target rows cover the same complete G/F roster; and
- holdout assignments contain the four closed cells `site`, `period`,
  `medium`, and `object_type`, with at least 20 G in each cell and at least 80
  holdout G overall.

The component reads already-derived score, `L_total`, `L_distinct`, and
canonical-target receipt values. It does not read token identities, raw
transcriptions, source units, unconverted measurements, or the source evidence
from which the predecessor receipts were derived. Receipt and module
separation is not operating-system access control: a future custodial wrapper
must still enforce principals, chronology, one use, and externally pinned
receipt identities.

## Deterministic HMAC counter stream

The counter stream follows [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104)
HMAC-SHA256 with a 32-byte key. For one closed stream label and run index,
block counter zero is the first block. Its message is exactly:

```text
UTF8(label) || NUL || uint64be(run_index) || NUL || uint64be(block_counter)
```

The five closed labels are `bootstrap-v1`, `control-n1-v1`, `null-n2-v1`,
`prospective-bootstrap-v1`, and `prospective-null-n2-v1`. This release uses
only `bootstrap-v1`; fixing the other labels preserves one non-colliding
framing surface for later separately typed components and does not mean those
components execute here.

Each complete 32-byte HMAC block is interpreted as one unsigned 256-bit
big-endian integer. To draw uniformly from `[0, m)`, the sampler accepts only
integers below `2^256 - (2^256 mod m)` and returns the accepted integer modulo
`m`. A rejected block advances the counter and is not a retry or redraw of a
scientific replicate. Bound one returns zero without consuming a block.

The key is raw checksum material supplied by the caller. HMAC makes the
schedule deterministic and reproducible; this component does not establish
that the key was unpredictable, externally retained, available at the claimed
time, used only once, or bound to the complete real claim chain.

## Exact rho and paired-delta order

A defined Spearman state remains exact as

```text
rho = C / sqrt(D)
```

where `C` is the integer covariance numerator and `D` is the positive product
of the two exact variance numerators. Two rhos are ordered by sign and squared
integer cross multiplication. Negative magnitudes reverse the order. Scaled
radicands therefore compare equal without square-free factorization.

For every bootstrap sample, the length reference is exactly

```text
rho_length = max(0, rho_total, rho_distinct)
delta_length = rho_candidate - rho_length
```

The representation-only tie precedence is zero, then `L_total`, then
`L_distinct`; it cannot change the numeric maximum. Delta signs are obtained by
an exact rho comparison. Deltas with the same nonzero sign are ordered through
their squared magnitudes, reversing the magnitude order for negative deltas.
The resulting expression reduces to the exact sign of
`R + P*sqrt(A) + Q*sqrt(B)` and is resolved through at most two exact
squarings with bounded integer and rational arithmetic.

No float, decimal approximation, Q12 display value, iterative precision rule,
or radicand factorization participates in rho selection, delta selection, or
endpoint ordering.

## Paired four-cell bootstrap

The historical holdout bootstrap has exactly 10,000 runs, indexed from zero
through 9,999. Within each run it processes cells in the fixed order `site`,
`period`, `medium`, `object_type`. For a cell containing `n` G, it draws
exactly `n` local indices with replacement from that cell's canonical roster.

One sampled occurrence sequence is reused unchanged for candidate score,
`L_total`, `L_distinct`, and target. This is the required paired resample; none
of the four aligned vectors may receive an independent schedule. Every run is
retained, including a sequence identical to an earlier run.

The protocol substitutions are numeric and closed:

- an undefined candidate correlation in a bootstrap run becomes exact `-1`;
- each undefined length correlation becomes exact zero before the frozen
  maximum is selected; and
- a contract, resource, or arithmetic-limit failure is an error, never a
  numeric substitution.

Only the four closed predecessor statuses
`undefined_insufficient_observations`, `undefined_zero_variance_both`,
`undefined_zero_variance_left`, and `undefined_zero_variance_target` are
undefined metrics. Any other status fails closed instead of becoming a
sentinel.

Runs are never discarded, redrawn, deduplicated, resalted, or replaced after
inspection. Candidate rhos and paired deltas are sorted independently in exact
ascending order. Run index is only the deterministic representation tie
breaker for numerically equal values. Each lower endpoint is the 250th
one-based value, or zero-based index 249.

The schedule commitment is updated incrementally from the fixed cell roster,
key identity, run and cell sizes, and every accepted local index. The complete
schedule and the 10,000-value vectors are neither materialized in the protected
receipt nor exposed by a public summary.

The frozen cross-implementation vector starts from ten canonical synthetic
roster rows and a distinct nonzero key. Tests rederive the roster commitment,
all accepted indices from the HMAC stream, and the final schedule commitment;
field swaps and omitted roster framing are explicit negative cases.

The resampling design follows the paired, stratified use of bootstrap
resampling specified by the parent protocol. The general bootstrap reference
is Bradley Efron's
[“Bootstrap Methods: Another Look at the Jackknife”](https://doi.org/10.1214/aos/1176344552).

## Protected receipt and reexecution

The output is a closed, aggregate-only protected receipt. It binds the exact
predecessor and resampling resources, input raw identities, chain-head key
identity, holdout roster, streamed schedule, and deterministic consumption
counters. It retains the exact rho lower endpoint and exact paired-delta lower
endpoint together with their source run indices and the counts of protocol
substitutions.

It has no G/F item rows, sampled indices, per-run values, X tokens, Y source
values, public-summary method, threshold verdict, `GO`, or decipherment field.
Its Python representation is a constant protected marker. Verification
reexecutes the complete 10,000-run calculation from the exact inputs and
requires canonical receipt-byte equality.

The Python state is factory-issued: ordinary callers cannot construct it from
four self-selected byte and checksum fields. This prevents accidental public
API forgery but is not a secrecy or authenticity boundary against malicious
code in the same Python process. `state.receipt()` is only a convenience for a
state returned directly by the evaluator. A receipt supplied by any external
caller must instead pass `verify_nmfa_bootstrap_receipt`, including full
10,000-run reexecution and byte equality; downstream gates must never treat a
caller-created state object or a recomputed self-digest as authentication.

The installed plan loader and the bootstrap evaluation, verification, and
protected-receipt access paths validate the installed content-addressed bundle
at entry and again before returning. The selector and measurement receipt
decoders also validate their own frozen predecessor bundles. These checks
detect packaged byte drift; they do not attest a mutable host, external
runtime, custodian, or the origin of caller-supplied digests.

## Resource and privacy guards

The fixed limits include:

- 10,000 bootstrap runs and at most 200,000,000 sampled positions;
- at most 20,000 units, at least 80 holdout G, and at least 20 G per cell;
- an index bound `m` accepted through `m <= 2^128`, inclusive;
- at most 16 counter-block attempts per draw and 320,000 generated blocks per
  run;
- exact rho input components of at most 2,048 bits, with a separate
  conservative 262,144-bit ceiling checked for derived integer and rational
  sign-kernel operands; and
- canonical JSON of at most 64 MiB, depth 64, 2,000,000 nodes, and 16,384
  characters per string.

Limits are charged before an otherwise excessive operation can be admitted.
Exhaustion, malformed canonical JSON, wrong order, duplicate or missing rows,
cross-receipt mismatch, invalid counter material, impossible exact states, and
package drift fail closed with fixed path- and value-free errors. They are not
scientific failures and cannot be converted into bootstrap sentinels.

Real X, Y, assignments, and protected receipts remain ineligible for source
control or public commitment under this development component. Aggregate
counts and checksums can still disclose properties of a private inventory, so
receipt publication is not authorized merely because item rows are absent.

## What remains before complete `E`

This component deliberately leaves `N1_N2_RUNNER_UNBOUND` and every
orchestration, prospective, activation, and complete-`E` blocker in place.

N1 first needs a separately typed, target-blind allograph/class universe and
an X-side count surface. That contract must close candidate groups,
alternative-class membership, development occurrence-count and G-prevalence
bins, annotation compatibility, pairwise disjointness, support completeness,
Hall feasibility, exact matching count, lexicographic unranking, and all
99,999 assignments without exposing Y.

N2 first needs a separately typed value-free stratum surface for every primary
holdout G. It must bind the assigned cell, all four canonical context axes, and
the complete ordered documentation and measurement nuisance tuple before Y is
opened. Only then can a later component enforce movable support, whole-G
within-stratum permutations, all 99,999 runs, exact `q0.99`, and the add-one
tail calculation.

After N1 and N2, the project still needs point and cell gates, exact
confirmatory terminal precedence, prospective chronology and relation
reclosure, prospective pre-Y predictions, prospective bootstrap and
permutation, one final audited execution bundle `E`, a successor activation
preflight, and an externally authenticated custodial activation wrapper.

No real metadata, X, or Y may be accessed on the authority of this component.
Even a future successful NMFA result would be only a narrow functional-anchor
candidate. It would not by itself establish phonetic values, language,
translation, full decipherment, eligibility for a prize, or entitlement to an
award.
