# External Preregistration and Receipt Envelope Template

Keep this envelope outside the candidate root and outside submission
commitment `S`. It is populated only after `S` exists. Fields concerning
receipt, time, custody, access, or execution must be completed or attested by
the independent custodian—not self-asserted by the submitter.

This repository provides only a non-operational template. Until a real
custodian, authority, authenticated receipt mechanism, and access procedure
exist, set status to `draft_unattested` and do not claim blindness or final
evaluation.

## Envelope identity

- Protocol/template revision:
- Status: `draft_unattested` / `externally_received` / `incident` / `closed`
- Public-safe envelope ID:
- Submitter/hypothesis ID:

## Frozen hypothesis payload

- Path inside the candidate root:
- Exact byte length:
- SHA-256 of the payload file:
- Hypothesis schema version, ID, and version:
- Change-control review complete:

## Public benchmark definition `B`

- Benchmark-definition ID:
- `definition_sha256`:
- Independent `verify-benchmark-lock` result:
- Verification software revision:
- Verification operator:

## Submission commitment `S`

- `schema_version`:
- `commitment_id`:
- `commitment_sha256`:
- `tree_sha256`:
- Target `benchmark_definition_sha256`:
- Target digest equals independently verified `B`:
- Independent `verify-submission-commitment` result using
  `--expected-commitment-sha256`:
- Entrypoint, working directory, and static argv reviewed:
- Source/configuration/model-weight/dependency roles reviewed:
- Every fallback `runtime_input` reviewed and explained:
- Manifest disclosure/rights/secret review complete:

## Independent receipt and custody

- Custodian organization and authorized operator:
- Organizational separation and conflicts:
- Authority/agreement reference:
- Authenticated receipt ID:
- Receipt bytes SHA-256:
- Detached signature and verification method:
- Independently controlled receive time and time-evidence source:
- Access-log reference:
- Incident status/reference:
- Attestation that exact `B` and `S` were received before hidden execution:
- Attestation that the hypothesis/submission team received no hidden material
  or hidden-derived feedback before receipt:

A signature without independently controlled receipt/time evidence, or a
timestamp without authenticated B/S binding, is insufficient.

## Private companion reference

- Opaque custodian-side reference:
- Private commitment verified by custodian:
- Retention and destruction policy reference:

Do not copy hidden IDs, record hashes, counts, nonce, raw bytes, access-control
details, or other disclosure-sensitive values into a public envelope.

## Reserved P3 run/result fields

- OCI image and interpreter digest:
- Full argv and environment digest:
- Read-only input policy:
- Network policy:
- Clock, locale, timezone, thread, seed, and resource policy:
- Run ID and replay-state decision:
- Run receipt ID/hash/signature:
- Output tree digest:
- Result receipt ID/hash/signature:
- B/S/private/runtime/output cross-reference verified:

These fields do not become true merely because they are filled in. P3 requires
an implemented verifier, isolated execution, authenticated receipts, and
independent operational evidence.
