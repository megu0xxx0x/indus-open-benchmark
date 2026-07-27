# Contributing

Contributions are welcome when they make the evidence easier to inspect, reproduce, or falsify.

## Before changing code

```bash
just --list
just test
```

Use Python 3.11+ type hints, keep runtime dependencies minimal, and add focused
tests for each behavior. The normative review commands require the declared
`jsonschema` runtime dependency. The `just` recipes use the locked
dependency set from `uv.lock` in the `uv --extra dev` environment; run
`just check` before proposing a release. This dependency lock is not a
benchmark, custody, or blind-evaluation lock.

## Before adding data

1. Add or update the source in `registry/sources.json`.
2. Verify metadata, image, and code rights separately.
3. Preserve upstream identifiers and exact revision.
4. Record display order independently from inferred reading order.
5. Add uncertainty rather than silently selecting one damaged sign.
6. Link duplicates and impressions to a physical or template family.
7. Keep interpretations in the hypothesis contract.

Do not commit raw or derived external corpora merely to make a test pass. Use small synthetic
fixtures whose origin is unambiguous.

## Scientific claims

A model improvement must report:

- the immutable corpus and split-manifest identifiers;
- duplicate and leakage audit results;
- all exclusions and hyperparameters;
- at least one matched null control;
- calibration and uncertainty, not only top-1 accuracy;
- failures on unseen sites, periods, and object types;
- code, environment, and random seed.

Claims about meaning or language require a frozen hypothesis and independent blind evaluation.
