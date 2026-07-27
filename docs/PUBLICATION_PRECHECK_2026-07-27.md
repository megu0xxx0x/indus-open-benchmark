# Public-source publication boundary

**Scope:** public source repository on the `main` branch

**Decision:** source publication only; package and scientific releases remain
separate decisions

**Repository:** <https://github.com/megu0xxx0x/indus-open-benchmark>

## Approved public surface

The public source may contain:

- MIT-licensed implementation code;
- normative schemas and validators;
- public source/evidence/rights registries;
- synthetic examples and tests;
- scientific protocols, public-source audits, and governance documents; and
- continuous-integration configuration that uses no private data.

## Excluded surface

The public source must not contain:

- raw provider downloads, museum images, or an authoritative Indus corpus;
- ignored data, private review/custody records, or hidden-test material;
- private paths, filenames, identifiers, values, inventories, byte totals,
  timestamps, audit outcomes, or content/manifest digests;
- host, account, network, browser-session, authentication, or key metadata;
- unverified third-party transcriptions or rights-restricted media;
- an unsent institutional message or prize submission;
- a blind/final evaluation result; or
- a language, phonetic, translation, or decipherment claim.

## Required checks

Before publication:

1. inspect the exact Git-tracked inventory and reachable history;
2. confirm the entire `data` path and all local environments, caches, reports,
   build products, and tool state are ignored;
3. build source and wheel archives and inspect their member lists;
4. run lint, formatting, type, unit/integration, schema, and CLI checks;
5. scan the public tree and history for credentials and personal/operational
   metadata;
6. verify local Markdown links;
7. verify the public remote head and CI result; and
8. keep detailed machine/private-data evidence in an owner-only record outside
   Git.

The repository contains no release tag, GitHub Release, package upload, DOI, or
operational prize-submission route unless a later explicit release decision
says otherwise.

## Interpretation

A clean source audit means only that the inspected public source surface
respected this boundary. It does not establish corpus rights, private-data
custody, a historical timestamp, blind evaluation, scientific validity, or
decipherment.
