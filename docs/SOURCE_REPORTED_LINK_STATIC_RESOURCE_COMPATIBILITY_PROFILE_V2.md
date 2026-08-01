# Source-reported-link static-resource compatibility wrapper V2

Status recorded at 2026-08-02 02:36:40 JST.

This checkpoint freezes and packages a source-free V2 custody/resolver
wrapper and its Draft 2020-12 `const` schema. It does not modify, satisfy, or
make eligible the frozen strict V1 resolver. No installed resolver consumes
the wrapper in this checkpoint.

No research source was requested or opened. No protected source byte,
response, image, transcription, observation, source-link/no-link result,
translation, decipherment result, submission, or prize result was created.

## Why a successor wrapper is required

The frozen V1 source contract and custody contract require every selected JSON
resource to equal its canonical `indusbench.io.encode_json` re-encoding. Two
already-public parents predate that key-order rule while remaining bound by
their historical raw-byte hashes:

| Path | Historical raw bytes / SHA-256 | Canonical re-encoding bytes / SHA-256 |
|---|---|---|
| `registry/sources.json` | 43,235 / `e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584` | 43,239 / `da9254e6a8cd4d6cbe7a465119bd1a1be7b6583586b8b1cb0cb8af02e9f83b1b` |
| `schemas/source-registry.schema.json` | 8,295 / `6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3` | 8,295 / `b118345e10446f92446114b3a1773bb0927a6b808e253268088d953776218073` |

Reformatting those parents in place would invalidate the source contract,
receipt expectations, custody contract, exact `const` schemas, and historical
digests. Re-freezing the complete parent chain solely for key order would
create a wider and riskier transition. The V2 wrapper therefore preserves the
historical raw identities and defines one closed compatibility rule for those
two resources only.

The canonical re-encodings in the table are verification canaries. They are
not replacement identities, new source revisions, retained derivatives, or
bytes that a resolver may write back, persist, or return.

## Frozen V2 artifacts

| Path | Bytes | SHA-256 |
|---|---:|---|
| `registry/source-reported-link-protected-ephemeral-custody-contract-v2.json` | 16,981 | `a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c` |
| `schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json` | 17,694 | `1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671` |

Both files are canonical JSON. The schema has exactly `$id`, `$schema`, and
`const`; the `const` value is the complete V2 wrapper. It has no external
reference. The wrapper intentionally contains no self-hash or schema hash,
which would create a self-reference cycle. A future installed resolver must
compile and validate both raw identities. The transitive runtime-input
manifest must bind both; the authenticated external authority surface must
directly bind the V2 wrapper as `custody_contract_sha256` and bind the
manifest that covers the schema.

The wheel selects the wrapper individually and includes the schema through
the existing complete `schemas` directory rule. The sdist already includes
the complete public `registry` and `schemas` trees. Packaging and schema
validation do not activate the wrapper.

## Normative V1 incorporation

The wrapper incorporates the complete raw bytes and semantics of these
parents by exact size and SHA-256:

| Incorporated artifact | Bytes | SHA-256 |
|---|---:|---|
| V1 custody contract | 426,824 | `917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914` |
| V1 custody `const` schema | 440,116 | `5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b` |
| V1 source contract | 29,059 | `e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f` |
| V1 source-contract `const` schema | 30,752 | `e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78` |
| Historical source registry | 43,235 | `e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584` |
| Historical source-registry schema | 8,295 | `6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3` |

The wrapper's `canonical_json_profile` is exactly equal to V1 and retains
`profile_id=indusbench-io-encode-json-v1` plus the default
`noncanonical_raw_bytes_disposition=hard_reject`. The exception does not
redefine that profile. It has the separate closed compatibility identifier
`source-reported-link-exact-two-static-byte-compatibility-v2`.

All unlisted V1 rules remain incorporated unchanged. The closed supersession
set covers only:

- application of the source-contract global rejection, its
  `canonical_byte_identity_required` execution rule, and the custody-contract
  global rejection to the exact two listed resources; and
- the future authority meaning of `custody_contract_sha256`, which must bind
  the V2 wrapper after every activation prerequisite is met.

The V1 resolver order is not replaced wholesale. The wrapper copies its exact
string, requires exactly one literal `strict_decode_canonical_reencode`
token, replaces only that token with the exact-two branch, and mechanically
fixes the complete composed string. The signed expected digest, roster
recomputation, separately opened manifest-selected distribution, distinct
immutable manifest/distribution handles, and already-loaded custody-byte hash
steps all remain present and ordered.

The V1 self-cycle rule also remains incorporated. An additive ordered
two-member rule excludes both the V1 and V2 custody `const` schemas from the
existing exact-four artifact schema-set digest.

No other static, dynamic, or runtime resource receives a compatibility
exception. A caller cannot select a path, profile, exception, digest, or
schema.

## Frozen verification order

A future V2-aware installed resolver must perform these steps fail-closed:

1. Open only a compiled package-relative resource without following links,
   and require the fixed regular-file boundary.
2. Read bounded raw bytes and require the compiled path, size, and raw
   SHA-256 identity.
3. Strictly decode UTF-8 without BOM; reject duplicate keys, floats,
   nonfinite numbers, and all fixed structure-limit violations.
4. Re-encode with `indusbench.io.encode_json`.
5. For an exact ordered exception, require raw/canonical inequality and the
   fixed canonical size and SHA-256 canary.
6. For every nonexception resource, require exact raw/canonical equality.
7. Never persist, write back, return, or adopt a canonical canary as identity.
8. Validate `sources.json` as an instance of the exact source-registry schema,
   validate that schema itself with Draft 2020-12 `check_schema`, and validate
   all parent, roster, schema-set, and cross-bindings.
9. Validate the V2 wrapper and schema against externally compiled raw
   identities.
10. Remain package-local and block authority, runtime, and source access until
    every external prerequisite is complete.

Those ten stages are the package-local static prevalidation sequence. The
full composed authority/runtime resolver order then preserves every
incorporated V1 step around its exact single-token canonical-byte splice.

The existing general canonical-resource preflight must continue to reject
both historical files with `canonical_bytes_mismatch`. The existing V1
installed loader remains an exact-14 loader and its
`strict_v1_resolver_eligible` value remains permanently `False`.

## Current and future boundary

This checkpoint has no V2-aware production loader. It establishes only a
reviewable, exact-byte successor specification and package presence. In
particular:

- `resolver_implementation_status=not_implemented`;
- `successor_static_profile_conformant=false`;
- authority is `not_authorized`;
- execution is `not_executed`; and
- source access did not occur.

Before any later activation, a separate implementation must validate the
exact 16-resource package-local surface and preserve a V2-specific state name
rather than a generic `eligible=true`. A complete transitive manifest,
distinct reproducible runtime distribution, bootstrap verifier, fixed trust
root, typed signed authority proof, custody/recovery runtime, acquisition
client, parser, evaluator, and remaining closed schemas must also be present
and validated. Adding only the two missing runtime identities is insufficient.

Package-local agreement is not package provenance, authority, source access,
evidence, a physical join, a source-link/no-link result, translation,
decipherment, submission, or prize eligibility.

## Validation and publication evidence

Pre-publication Linux validation passed the related 91-test set, the dedicated
12-test V2 set, Ruff, formatting of 191 files, zero-finding locked Pyright,
both distribution builds, isolated installed-wheel verification, and the
complete 1,175-test suite with 19 skips. Three final independent read-only AI
engineering audits reported P0/P1/P2 as 0/0/0; this is not human or external
scientific review.

Public CI run `30711703762` then succeeded at exact implementation head
`edeb6ebe80215f2bf9fa287ae8f058a3d32f33f5`. Python 3.11, 3.13, and 3.14
each passed exact Node 24.18.1 Quicknet, Ruff, 191-file format, zero-finding
Pyright, all 1,175 tests with 22 skips, both builds, and the isolated
installed-wheel V2 verifier.
