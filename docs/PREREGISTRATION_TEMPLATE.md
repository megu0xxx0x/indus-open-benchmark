# Frozen Hypothesis Payload Template

Complete this payload before the candidate is run on hidden inputs and before
the hypothesis/submission team receives any hidden material or hidden-derived
feedback. Hypothesis authors normally never receive raw hidden data.

Place the completed payload inside the candidate root before building the
submission commitment `S`. Do **not** write the resulting `S` digest into this
same file: that would create a self-reference. A local hash or `S` does not
prove timing or blindness. The separate
[registration/receipt envelope](PREREGISTRATION_RECEIPT_ENVELOPE_TEMPLATE.md)
must remain outside `S` and requires an independently retained custodian
receipt for exact `B` and `S` values.

For a public machine-readable hypothesis, every
`prediction.target.withheld_target_id` remains `null`. The custodian keeps any
hidden mapping private.

## Identity

- Hypothesis schema version:
- Hypothesis ID and version:
- Title:
- License:
- Authors:
- Affiliations:
- Conflicts of interest:

## Public benchmark and cutoff

- Public benchmark-definition ID:
- Public benchmark `definition_sha256` (`B`):
- Local `verify-benchmark-lock` result and verification date:
- Public corpus manifest ID/SHA-256:
- Public split manifest ID/SHA-256:
- Exact data and knowledge cutoff:
- Public inputs inspected before cutoff:
- Confirmation that no hidden IDs, hashes, counts, nonce, bytes, or
  hidden-derived feedback appear in this payload:

## Frozen implementation plan

- Code revision:
- Dependency-lock files and digests:
- Random seeds:
- Stochastic/nondeterminism policy:
- Planned entrypoint path:
- Planned working directory (`.` for `S` v0.1):
- Planned static argv, in exact order:
- Planned interpreter/runtime/image and version:
- Environment variables and locale/timezone plan:
- External files, devices, network services, or APIs the method would read:
- Training-data sources, revisions, rights, and provenance:
- Contamination search performed:
- Statement of prior hidden-data access or suspected leakage:

The runtime/interpreter plan is prospective metadata only. `S` v0.1 binds the
entrypoint file and static arguments, but P3 must separately bind and enforce
the interpreter/image, full environment, external-read policy, and network
policy.

## Scope

- Claimed level: transcription / structure / phonetic values / language /
  translation
- Artifact, site, period, and object-type coverage:
- Explicit exclusions and reasons:

## Frozen assumptions

- Sign inventory and allograph groups:
- Matrix/impression transformation:
- Reading direction:
- Word or phrase boundaries:
- Writing-system type:
- Candidate language(s), reconstruction date, and lexical sources:
- Permitted null signs, one-to-many mappings, homophony, polyvalence, and
  damaged-sign handling:
- Maximum number and cost of exceptions:

## Predictions

Give every prediction a stable ID and machine-checkable selection rule where
possible:

- prediction ID:
- public selection rule:
- predicted target/type:
- expected direction or value:
- uncertainty/calibration statement:
- negative control:
- `withheld_target_id: null` in public records:

Cover, where relevant:

- missing or next sign;
- unseen sequence probability;
- site, period, object type, motif, quantity, or commodity;
- phonological or morphological alternation;
- confirmed name or place-name correspondence;
- expected result on each negative control.

## Evaluation

- Primary metric and decision threshold:
- Calibration metric:
- Complexity penalty:
- Multiple-testing/multiplicity handling:
- Family, image-hash, and exact-sequence leakage audit:
- Leave-one-site/period/object-type analyses:
- Known-script degraded control:
- Unrelated-language and permuted-semantic controls:
- Timeout and resource-exhaustion rule:
- Missing, malformed, partial, or duplicate output rule:
- Crash and evaluator-error rule:

## Failure conditions

State in advance what result would reject or materially weaken the hypothesis.
A hypothesis without a possible losing result is not eligible for the future
blind benchmark.

## Change control

Any post-freeze change to data, assumptions, mapping, rules, exceptions,
predictions, code, dependencies, weights, configuration, entrypoint, or
arguments creates a new hypothesis version and a new `S`. The external
envelope records the final payload path/hash and B/S identifiers after `S` is
built; this payload never records its own enclosing `S`.
