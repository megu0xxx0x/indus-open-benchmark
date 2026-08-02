# Source-reported-link exact-16 installed static resolver V2

Status recorded at 2026-08-02 10:12:22 JST.

This source-free checkpoint implements the installed-package consumer for the
frozen
[V2 static-resource compatibility wrapper](SOURCE_REPORTED_LINK_STATIC_RESOURCE_COMPATIBILITY_PROFILE_V2.md).
It validates one fixed, ordered 16-resource package-local surface and returns
a V2-specific immutable snapshot. It does not modify or promote the historical
exact-14 V1 public API, output, or eligibility state; only the shared private
filesystem traversal is generalized for an internally fixed resource tuple.

No research or protected source was requested or opened. No external response,
receipt, pass, observation, source-link/no-link result, join, transcription,
translation, decipherment evidence, submission, prize eligibility, or prize
result was created.

## Public API and isolation

The sidecar module is `indusbench.source_reported_link_static_v2`. Its public
zero-argument entry point is:

```python
from indusbench.source_reported_link_static_v2 import (
    load_installed_source_link_static_profile_v2,
)

snapshot = load_installed_source_link_static_profile_v2()
```

The caller cannot provide a package root, path, digest, profile, exception,
schema, trust root, or authority value. The public loader accepts only a real
filesystem `Path` returned for the installed `indusbench` package. It has no
repository, current-working-directory, archive, or network fallback.

The V1 API remains `load_installed_source_link_static()`. Its exact-14 table,
six-identity snapshot, two blockers, representation, and
`strict_v1_resolver_eligible=False` result are unchanged. The common
filesystem traversal was generalized internally only so V1 can read exact 14
and V2 can read exact 16 through one identical descriptor-bound mechanism.

## Exact-16 surface

The first 14 resources and their order are exactly the V1 table documented in
the [V1 loader report](SOURCE_REPORTED_LINK_STATIC_LOADER_V1.md). V2 appends
only these two canonical resources:

| Index | Resource | Bytes | SHA-256 |
|---:|---|---:|---|
| 14 | `registry/source-reported-link-protected-ephemeral-custody-contract-v2.json` | 16,981 | `a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c` |
| 15 | `schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json` | 17,694 | `1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671` |

The ordered total is 16 resources and 1,069,631 bytes. Unrelated additional
package files are outside this selected surface; their presence neither
extends nor satisfies it.

All 16 files are opened during one traversal of pinned package, `registry`,
and `schemas` directory descriptors. Each read preserves the V1 regular-file,
single-link, owner, mode, same-device, bounded-size, no-follow, fingerprint,
namespace-revalidation, and close-failure rules. The exact-14 result is not
loaded first and supplemented by a later two-file read.

The inherited strong-loader boundary supports only Linux and macOS POSIX
filesystems with the required descriptor flags. Unsupported platforms fail
closed. Each file and namespace is revalidated around its own read, but the
ordered 16-file traversal is sequential: it is not an atomic or continuing
snapshot across all 16 files and does not defeat replacement by the same UID
or root outside those checks. The detailed inherited filesystem boundary is
documented in the
[V1 loader report](SOURCE_REPORTED_LINK_STATIC_LOADER_V1.md#installed-static-loader).

## Decode, schema, and binding checks

Every resource first requires its compiled path, size, and raw SHA-256. JSON
then requires BOM-free UTF-8, no duplicate keys, no floats or nonfinite
numbers, and the unchanged V1 depth, node, integer, key, and string limits.

The two historical noncanonical resources retain their raw identities. V2
additionally requires raw/canonical inequality and the frozen canonical
re-encoding canary for each:

| Resource | Canonical bytes | Canonical SHA-256 |
|---|---:|---|
| `registry/sources.json` | 43,239 | `da9254e6a8cd4d6cbe7a465119bd1a1be7b6583586b8b1cb0cb8af02e9f83b1b` |
| `schemas/source-registry.schema.json` | 8,295 | `b118345e10446f92446114b3a1773bb0927a6b808e253268088d953776218073` |

The canonical projection is discarded after verification. It is never an
identity, output, writeback, or persisted derivative. Every other selected
resource requires raw bytes to equal its canonical re-encoding.

The resolver then:

- performs the complete V1 nine-schema, five-instance, parent, roster,
  schema-set, digest, and registration cross-binding validation;
- checks the V2 schema as Draft 2020-12 with exactly `$id`, `$schema`, and
  `const`, and validates the wrapper against that exact `const`;
- verifies the exact-16 order and the distinct instance/schema validation
  modes for the historical pair;
- resolves only fixed JSON Pointers within the already-loaded documents;
- verifies all six incorporated V1 raw identities, exact-two binding sources,
  the single-token resolver composition, the four supersession rules, the
  exact-eight future field-name crosswalk, and the additive V1/V2 self-cycle
  exclusion; and
- requires the wrapper's frozen authorization, execution, source-access,
  result, and other nonclaim values to remain inactive.

The wrapper's embedded `resolver_implementation_status=not_implemented` and
`successor_static_profile_conformant=false` are immutable facts about the
earlier wrapper-freeze checkpoint. This later loader does not rewrite them.
Its live result uses the distinct field
`package_local_v2_static_profile_conformant=True`.

## Snapshot meaning

`SourceFreeStaticProfileV2Snapshot` exposes only fixed digests and closed
status values. It uses `compatibility_wrapper_sha256` rather than the future
authority field name `custody_contract_sha256`, so package-local validation is
not mistaken for an activated exact-eight authority binding. The companion
schema digest is likewise named `compatibility_wrapper_schema_sha256` and is
not an authority value.

The snapshot fixes:

- `resource_count=16`;
- `package_local_static_prevalidation_status="validated_package_local_exact16_only"`;
- `package_local_v2_static_profile_conformant=True`;
- both missing runtime binding field names;
- `strict_v1_resolver_eligible=False` and the two unchanged V1 blockers;
- `authority_status="not_authorized"`;
- `runtime_status="not_validated"`;
- `source_access_status="not_performed"`;
- `result_status="not_established"`; and
- `activation_status="blocked_external_prerequisites_absent"`.

It returns no decoded document, canonical projection, source byte, path,
descriptor, manifest, distribution digest, authority proof, or result.

## Installed-distribution verification

The post-build verifier checks the V2 module as one regular wheel member and
checks its bytes against the source tree. It continues to verify the exact 14
V1 resources and the two wrapper resources independently. It then extracts the
wheel under a deterministic safe umask and launches isolated Python from an
empty working directory with a socket audit hook.

One fresh process executes V1 → V2 → V1 and another executes V2 → V1 → V2.
Both require equal fixed-field snapshot projections before and after the other
loader. This proves package-local loader coexistence for that wheel; it does
not establish publisher identity, operating-system network isolation, or
package provenance.

Pre-publication Linux validation completed at 2026-08-02 11:17:04 JST. The
focused V1, V2, frozen-wrapper, and publication set passed 43/43; Ruff,
formatting of all 193 files, and locked Pyright passed with zero findings. The
complete suite passed 1,189 tests with 19 skips in 1,107.947 seconds. Fresh
sdist and wheel builds, the forward/reverse installed-wheel verifier, archive
safety, publication, secret, and Markdown-link checks passed. Three final
independent read-only AI audits reported P0/P1/P2 as 0/0/0 after their
findings were fixed. This is engineering review, not external scientific
review. Public CI evidence is pending publication.

## Remaining blockers

Package-local conformance does not satisfy the complete transitive runtime
manifest, reproducible runtime distribution, bootstrap verifier, fixed trust
root, typed authenticated authority proof, custody/recovery runtime,
acquisition client, deterministic parser, evaluator, or remaining dynamic
schemas. Adding only the two missing runtime binding values remains
insufficient.

That dependency order is local to this deferred source-link lane, not the
project's global next priority. A future schema freeze must also first repair,
through a separate successor rather than a V1/V2 rewrite, the unreachable
pre-source branch in the embedded deletion-record schema. The current
exact-16 resolver neither consumes nor activates that future schema.

No package-local success is package authenticity, rights clearance,
independent custody, runtime eligibility, source-access permission, evidence,
a physical join, a source-link/no-link result, translation, decipherment,
submission, or prize eligibility.
