# NMFA value-blind preregistration gate V1

## Status

This release is a source-free, non-operational implementation of a protected
preregistration candidate gate for the
[numeral–metrology functional-anchor protocol](../benchmark/numeral-metrology-functional-anchor-protocol-v1.json).
It has synthetic tests only. It contains no real source record, transcription,
measurement, target value, split, model, prediction, result, or prize entry.

Passing the gate means only
`CANDIDATE_FOR_EXTERNAL_REGISTRATION_REVIEW`. It does not establish external
custody, trusted time, role independence, source rights, scientific validity,
decipherment, or prize eligibility. Source access and experiment execution
remain unauthorized by this public release.

The gate is not a pre-access scanner. A real manifest can exist only after
authorized, role-separated curators have prepared and sealed protected X and Y
archives and frozen the complete population. Authority, rights, custody, and a
claim-slot reservation must therefore be established before that protected
work begins. The required deterministic `PREMETADATA_READY` and
`PREVALUE_READY` evaluators do not yet exist, so no such work is presently
authorized. If an early declaration is inadequate, the report forbids further
acquisition, audit, registration, nonce use, key release, or target reveal; it
cannot undo access that already occurred.

## Scientific purpose

The parent hypothesis asks whether one small, positive additive score over an
Indus transcription predicts one independently measured direct count, mass, or
capacity target across unseen physical-object and archaeological-context
families. The preregistration gate prevents a later analyst from quietly
changing the population, dependence groups, context cells, target family,
split lottery, or control-support requirement after seeing useful values.

The gate evaluates structure and declared governance only. It never reads
plaintext X or numeric Y, chooses a nonce or split, fits a model, scores a
holdout, or evaluates a reading.

## Data roles

The protected manifest represents the parent protocol's roles without putting
their values in public source:

- `F` is one physical original, with every side, alias, edition, and source view
  mapped to it.
- Base `E(F)` is the independently curated per-F eligibility boolean. An
  ineligible F records the sorted, unique, complete set of every applicable
  closed reason, not one convenient primary reason.
- `G` is the transitive target-blind dependence component over all F, including
  ineligible F. Confirmed relations union; possible or unresolved relations
  either union or conservatively exclude the affected components.
- `M_G` preserves every F in G whose base E is true, even if G is later excluded
  as a whole.
- Effective split eligibility is separate from base E. Prior project exposure,
  any unresolved identity/content/context conflict, or an unresolved
  dependence exclusion propagates to the complete G in that precedence order.
- `C` contains canonical site, period, medium, object type, and the frozen
  ordered nuisance tuple. Observed values must be declared canonical group IDs.

Source-record IDs have a functional dependency on F across revisions and
views. Context closures must be reflexive, transitive, and laminar. Ordered
nuisance fields, their complete canonical vocabularies, and their vocabulary
digest are machine checked. An eligible G must have a nonempty M_G and complete
C for every member, including base-E-ineligible members.

## Lifecycle and chronology

The required sequence uses canonical UTC-second declarations and strict
ordering. The gate validates the internal order and digest subjects but does
not prove external time.

1. **Public source-free freeze.** The parent protocol predates the gate plan;
   the exact gate plan predates the evaluator bundle.
2. **Claim reservation.** One externally scoped claim family and claim slot are
   reserved before any claim-instance identifier mapping or source-metadata
   access. The reservation binds the identifier policy before its key is drawn.
3. **Identifier ceremony.** An independent custodian generates one CSPRNG key,
   records its commitment, and forbids rotation or resalting for the instance.
4. **Exact prevalue inventory.** The first clean-role source-metadata access
   occurs after the key ceremony. Before the earliest X or Y access, one
   signed receipt then binds the exact ordered source record/revision/view/
   entry-to-F mapping, exact ordered F roster, actual per-F C tuple, context
   and physical-identity evidence, and per-F prior project exposure. It also
   binds the source-frame, target, rights, custody, identifier, evidence-
   envelope, staged-release, and nonce-event contracts. X- or Y-derived
   eligibility and relation evidence remain later, but no F or C may be added,
   dropped, regrouped, or reassigned after value access.
5. **Independent seals.** X and Y use separate custodians, archives, keys,
   payload contracts, and Merkle roots. Each archive covers the exact ordered F
   roster and contains one randomized per-record XChaCha20-Poly1305 envelope
   for an exact value or an explicit missing/ambiguous status. No plaintext or
   unkeyed dataset digest is admitted.
6. **Population freeze.** X access precedes the X seal, Y access precedes the Y
   seal, and both seals precede the population receipt. Manifest assembly is
   later than that receipt.
7. **External in-custody review.** Before registration, an auditor distinct
   from the originating transcription curator and archive custodian rederives
   the complete F roster, every exact X/status with source record, revision,
   view, side, line, token, and allograph order, the complete transcription-
   derived E-reason contribution, and the complete relation graph. Complete
   relation review covers every F, exact endpoints, kind, status, disposition,
   and evidence envelope. A target auditor distinct from the target curator
   and archive custodian rederives the target contract, complete F roster,
   target contribution to E, and exact Y/status records. External review
   rederives joint base E and component exclusions. Auditor assignments are
   also separate from identifier, source-frame, physical-identity, context,
   relation, split, evaluator, model, and opposing-value roles. Plaintext and
   keys remain in custody.
8. **External registration and split.** A real registry must bind the single
   active chain head. Only then may the first qualifying external nonce event
   occur. Retry, resalting, parallel chains, and post-registration supersession
   are forbidden.

The public gate does not perform steps 2–8 and does not attest that they have
occurred in the real world. Its synthetic receipts test only the closed
contract.

## Split integrity

Two separate commitments prevent randomized evidence or encryption bytes from
becoming lottery salt:

- the full population and structural commitments bind audit-relevant reasons,
  raw relation declarations, evidence envelopes, and X/Y seals;
- the selector inventory binds only exact base-E booleans, F, final G, M_G,
  effective split eligibility, exact C, validated closures, and selection-
  relevant nuisance semantics.

Changing an evidence envelope, ciphertext nonce, Merkle root, attestation ID,
nonselection reason, or redundant edge that leaves final G unchanged cannot
change the selector inventory. Changing E, F-to-G membership, C, a closure, or
effective G eligibility must change it.

The evaluator retains every parent-V1 split-eligible canonical tuple in
lexicographic order. It does not reject or deduplicate parent/child tuples that
happen to produce the same observed G cells, and it does not filter the split
lottery with N2. The future ticket bytes are the canonical JSON array
`[site, period, medium, object_type]`, including its terminal LF. The selected
ticket minimizes:

```text
SHA256(raw_split_nonce || NUL || UTF8(selector_inventory_digest) ||
       NUL || canonical_tuple_bytes)
```

The plan contains fixed vectors for this framing and for target-blind primary-F
ranking. Selection still happens only after an external registration receipt
and nonce; this gate never performs it.

N2 support is a later parent-protocol stop condition, not a split predicate.
For efficient preregistration, this gate applies a conservative rule: every
split-eligible tuple must already meet the frozen N2 support floor of at least
64 movable G and at least 80 percent of its holdout. If even one ticket would
fail, the terminal state is `N2_UNIVERSAL_SUPPORT_BLOCKED`, which is a design-
stage block rather than a scientific refutation.

## Staged release and deferred N1

The sealed values remain compartmented after the candidate gate. N1 support
feasibility and N1 random assignment are deliberately separate stages:

- development X and Y may open only after external registration and a split
  receipt;
- exactly one model, or one preregistered fallback rule, must then freeze;
- before holdout X opens, opaque N1 candidate classes and alternative pools
  freeze and a deterministic, draw-free check must prove the minimum pools and
  existence of complete injective matchings;
- holdout X opens only after those support-feasibility receipts;
- the complete holdout prediction manifest then freezes while Y stays sealed;
- only then does the externally bound pre-Y chain head determine and freeze
  the N1 sampled assignments; and
- holdout Y opens only after both prediction-manifest and sampled-assignment
  receipts exist.

The preregistration manifest contains no actual N1 classes and makes no claim
that N1 support exists. The future sampler has fixed HMAC framing and a test
vector. Its real key is the later externally bound pre-Y frozen-protocol chain
head. That head must bind all earlier/aborted claim slots, signed X/Y audits,
joint E/G review, identifier rederivation, registration, raw split nonce and
extraction receipt, selector roster/ticket receipt, the single model, N1
pools/support, the holdout prediction manifest, the typed evaluator, and the
no-retry rule.

This release implements neither the real split selector nor the scientific
execution stack: model parser/scorer, primary midrank and length metrics,
cell gates, bootstrap confidence intervals, N1 matching/unranking and runs,
N2 permutations and runs, terminal precedence, and prospective evaluation.
One complete typed evaluator bundle, receipt schemas, and fixed vectors are
mandatory before registration or any real run.

## Evaluator and private report

Normative files are:

- [gate plan](../benchmark/nmfa-value-blind-preregistration-gate-plan-v1.json)
- [evaluator bundle](../benchmark/nmfa-value-blind-preregistration-evaluator-bundle-v1.json)
- [manifest schema](../schemas/nmfa-value-blind-preregistration-manifest.schema.json)
- [private report schema](../schemas/nmfa-value-blind-preregistration-report.schema.json)
- [implementation](../src/indusbench/nmfa_preregistration.py)

The supported API loads the installed plan, validates canonical protected
manifest bytes, and evaluates them. It has no public-summary method. Dataclass
representations are deliberately value-free. The module performs no network
request, subprocess call, random draw, or file write.

The report is protected and aggregate-only. Even counts and commitments can
leak a private inventory, so publication is not authorized. The report schema
validates a closed structural shape; it cannot by itself prove cross-field
semantics or authenticity. Verification requires deterministic reexecution
from the exact manifest and evaluator bundle and byte-for-byte equality with
the report.

Computation limits cover canonical tuple attempts, admitted N2 tuple attempts,
charged primary-G assignments, and the deterministic primary-F cache. A limit
produces `COMPUTATION_LIMIT_BLOCKED`, never a partial feasible roster.

## Current evidence and next real step

The synthetic 160-G fixture reaches the candidate state and adversarial tests
exercise exact threshold failures, closure defects, E/G contamination,
source-to-F inconsistencies, randomized-selector invariance, chronology,
receipt kinds, seal/roster mismatches, exposure declarations, computation
limits, private output boundaries, and resource substitution.

This is method sanity only. No verified reusable public source currently joins
complete X, physical identity F, dependence G, canonical C, base E, and direct
numeric Y at the required scale. The next real step is therefore not a model
run. It is to establish documented authority, rights, protected custody,
independent role assignments, a real claim-slot registry route, and in-custody
X/Y audit procedures for one source candidate. Protected source access must
not begin merely because this software exists.

Operational activation is additionally blocked until two separate,
deterministic signed preflight evaluators exist. `PREMETADATA_READY` must check
authority, rights, custody, role assignments, and frozen source/target rules
before claim-instance metadata access. After enumeration,
`PREVALUE_READY` must check the exact prevalue inventory, plan, bundle, archive
contracts, and no-value boundary before either X or Y access. This retrospective
post-seal gate cannot substitute for either checkpoint and does not authorize
access.

The parent protocol is still marked `draft`. V1 binds its exact current bytes;
changing its status or content cannot silently upgrade this gate. A finalized
parent requires a new gate version and a fresh external claim chain. Where the
draft parent says one closed E reason code, this gate applies a stricter typed
refinement: `reason_codes` is the sorted, unique, complete set of all applicable
closed reasons, and E is true only for exactly `[ELIGIBLE]`.
