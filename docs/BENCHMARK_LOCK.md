# Public-development benchmark definition lock

## Current boundary

`benchmark-lock.schema.json` version 0.1 defines only a local benchmark
**definition** for the fully public train/development workflow. It deliberately
reports:

- `claim_class=development_reproducibility`;
- `blind_claim_allowed=false`;
- `final_evaluation_eligible=false`;
- `external_anchor.status=unanchored_local`;
- dependency-lock-only environment assurance; and
- evaluator dependency closure as not attested.

The lock is not evidence that a submission existed at a particular time, that
an author could not see an evaluation set, that a runtime was isolated, or
that an institution held custody. A cryptographic digest is also different
from a scientific external anchor such as a bilingual text or independently
confirmed name.

## Bound inputs

The builder reads every input as a single-link regular file, rejects symbolic
links, duplicate JSON keys, non-finite numbers, invalid UTF-8, unsafe logical
paths, oversized inputs, and files that change while being read. It binds:

| Layer | Exact-byte commitment | Semantic re-derivation |
|---|---|---|
| Corpus | raw JSONL SHA-256 and bytes | artifact schema, domain rules, quarantine, canonical corpus digest, count |
| Schemas | artifact, source, quarantine, split, evaluator-config, and lock schema bytes | Draft 2020-12 validation; non-local `$ref` rejected |
| Registries | source and quarantine bytes | source schema, quarantine schema, canonical/self digest |
| Split | manifest, train, development, and leakage-audit bytes | split ID/self digest, all members, record union, row equality, leakage audit |
| Evaluator | closed config and each supplied evaluator file | config schema and evaluator inventory digest |
| Environment | `pyproject.toml` and `uv.lock` bytes | disclosed as dependency-lock-only, without an OCI-runtime claim |

The canonical definition digest is:

```text
SHA256(
  "indusbench:benchmark-definition:v0.1\0"
  || indus-json-c14n-v1(definition without its two self fields)
)
```

`indus-json-c14n-v1` uses strict JSON, sorted object keys, compact UTF-8,
preserved array order, no Unicode normalization, and no floats.

## CLI

First create a public development split:

```bash
uv run indusbench split \
  data/derived/corpus.jsonl data/derived/split \
  --development-fraction 0.2 --seed 20260727
```

Then bind the exact evaluator files actually used:

```bash
uv run indusbench lock-benchmark \
  data/derived/corpus.jsonl \
  data/derived/split \
  benchmark/development-evaluator.json \
  data/derived/benchmark-definition.json \
  --evaluator-file src/indusbench/cli.py \
  --evaluator-file src/indusbench/audit.py \
  --evaluator-file src/indusbench/baseline.py \
  --evaluator-file src/indusbench/null_evaluation.py \
  --evaluator-file src/indusbench/treewidth_audit.py \
  --created-by local-development
```

Verification reopens and re-derives every input:

```bash
uv run indusbench verify-benchmark-lock \
  data/derived/benchmark-definition.json \
  data/derived/corpus.jsonl \
  data/derived/split \
  benchmark/development-evaluator.json \
  --evaluator-file src/indusbench/cli.py \
  --evaluator-file src/indusbench/audit.py \
  --evaluator-file src/indusbench/baseline.py \
  --evaluator-file src/indusbench/null_evaluation.py \
  --evaluator-file src/indusbench/treewidth_audit.py
```

`--expected-definition-sha256` compares a digest supplied separately from the
lock file. The result field is `expected_digest_match`; even a match leaves
`externally_anchored=false`, because this version has no signed or timestamped
receipt.

## What remains for a real blind evaluation

The local
[submission content commitment](SUBMISSION_COMMITMENT.md) now implements the
submission-layer commitment `S`. It commits the complete inventory below one
caller-selected root and a caller-declared target definition digest, but still
cannot show when or by whom it was created, received, or used.

A real blind protocol still needs the following layers and external actions:

1. an independent custodian must authenticate and retain a time-evidenced
   receipt binding exact `B` and `S` values before the candidate is run on
   hidden inputs and before the hypothesis/submission team receives hidden
   material or hidden-derived feedback;
2. a custodian-held private split companion with a random nonce, exact hidden
   bytes, and no hidden identifiers or record hashes in the public lock;
3. a signed/timestamped custody and run receipt binding definition,
   submission, isolated evaluator runtime, and outputs; and
4. a result receipt that prevents replay across definitions or submissions.

An OCI image digest, read-only inputs, disabled network, fixed locale/timezone,
thread limits, and an externally controlled custodian are required before
runtime or blind-evaluation assurance can be considered.
