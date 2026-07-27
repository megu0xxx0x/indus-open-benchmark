# Data and Rights Policy

## Principle

Open-source code cannot relicense inscriptions, photographs, catalogue text, book scans, fonts,
or transcriptions obtained from third parties. Every source is reviewed independently.

The repository defaults to **no redistribution** until evidence permits it.

## Required source record

Before an importer or dataset is accepted, `registry/sources.json` must record:

- stable source identifier and canonical URL;
- responsible institution or maintainer;
- exact release, revision, or retrieval date;
- separate licenses for code, metadata/transcription, and images;
- whether bulk retrieval and redistribution are documented;
- provenance limitations and contact route;
- permitted project use: metadata, local research, derived statistics, or redistribution.

Missing license information is treated as `unknown`, not as permission.

## Machine-enforced quarantine

The content-addressed
[`registry/quarantine.json`](registry/quarantine.json) is a fail-closed deny
registry for normal corpus ingestion, training, development/final evaluation,
and redistribution. Unknown source IDs are denied unless they are narrowly
attested internal synthetic fixtures. A matching URL or pinned revision is
also denied even if its `source_id` was relabelled.

`audit --allow-quarantined-for-audit` permits inspection only. Its structured
result retains every quarantine finding and cannot promote the material into
an admissible corpus. A missing, malformed, or self-hash-inconsistent
quarantine registry is an error, not an empty policy.

## Redistribution states

- `allowed`: the included material has explicit compatible rights.
- `metadata_only`: metadata/transcription may be processed, but images or other layers may not.
- `restricted`: permission or an institutional agreement is required.
- `unknown`: rights could not be established; do not redistribute or train release models on it.

An `allowed` artifact with images must name an explicit image license or public-domain statement.

## Repository exclusions

The following are ignored and must not be committed by default:

```text
data/raw/
data/derived/
data/images/
```

Rights-cleared museum downloads still remain private by default. They use the
`museum-intake.schema.json` staging contract, retain exact item-level evidence
and file hashes plus exact policy/API documentation snapshots, and enter a
release only through a separate review. Internal hashes establish bundle
self-consistency; historical authenticity needs a digest anchored outside the
bundle. Legal openness does not automatically resolve physical-side labels,
catalog identity, archaeological context, or cultural-heritage review.

Before normalization, the optional
[`audit-private-readiness`](docs/PRIVATE_CORPUS_READINESS.md) gate can scan a
physical owner-only working tree and compare it with a private exact-path
policy. Its count-free terminal result does not disclose the corpus. An
aggregate report remains private by default. Structural validity, a known
source, or a curator declaration does not itself grant rights; missing,
unknown, ambiguous, conflicting, restricted, purpose-incompatible, or
quarantined evidence fails closed. The tool never repairs permissions,
deletes duplicates, publishes data, or upgrades a local check to custody,
blindness, decipherment, or prize eligibility.

Do not:

- scrape access-controlled or request-only databases;
- copy book or catalogue scans because they are visible online;
- infer a license from a GitHub repository that lacks a `LICENSE` file;
- treat a code license as applying to bundled third-party data;
- use speculative Sanskrit, Tamil, Dravidian, or other translations as target labels;
- publish exact museum image URLs as a substitute for checking item-level terms;
- train a release model on material whose redistribution/training terms are unresolved.

## Observation and hypothesis separation

Artifact records contain observations and documented uncertainty only. Proposed readings,
phonetic values, language assignments, and translations live in hypothesis records with authorship,
date, version, assumptions, coverage, and pre-registered predictions.

Corrections to transcription must preserve the earlier value, source, annotator, and reason.

## Cultural heritage and institutional authority

Legal openness is a minimum, not the whole ethical standard. Contributors must respect the
authority and attribution requirements of source countries, excavating institutions, museums,
communities, and conservation teams. Sensitive locations and unpublished excavation records are
not released without approval.

## Takedown and correction

Report rights problems using the process in `SECURITY.md`, marking the message `DATA RIGHTS`.
Questioned material should be added to the quarantine evidence registry and
kept out of releases, model training, and evaluation while reviewed. Removal
of third-party material does not remove its provenance entry or the public
correction record.
