# KP1979 V3 Quicknet verifier

Status: pre-C3 qualification dependency. This document intentionally makes no
claim that C3 is frozen or executed.

## Scope

This component verifies an externally supplied drand Quicknet beacon without
fetching or installing anything at verification time. It is a C3
qualification dependency, not a source of future-round selection, time
attestation, custody evidence, or an unforgeable receipt.

It makes no statement about Indus identifiers, sequences, language, meaning,
translation, decipherment, or eligibility for any prize.

## Fixed public chain identity

The verifier fixes the following public Quicknet values:

| Field | Fixed value |
| --- | --- |
| beacon ID | `quicknet` |
| chain hash | `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971` |
| scheme | `bls-unchained-g1-rfc9380` |
| period | `3` seconds |
| genesis time | `1692803367` |
| group hash | `f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e` |
| hash-to-curve DST | `BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_` |

The 96-byte G2 public key is fixed in
`src/indusbench/kp1979_v3_quicknet.py`. Its value, the fields above, and the
network launch are independently visible in drand's
[Quicknet launch record](https://docs.drand.love/blog/2023/10/16/quicknet-is-live/)
and the live public
[`/info` response](https://api.drand.sh/52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971/info).

The qualification vector is the already-public past round `1000`:

- signature:
  `b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb1125e342b73a8dd2bacbe47e4b6b63ed5e39`
- randomness:
  `fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd`

It is available through drand's
[chain-hash API](https://api.drand.sh/52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971/public/1000)
and [beacon-ID API](https://api.drand.sh/v2/beacons/quicknet/rounds/1000).
The API shape is documented in the official
[HTTP API guide](https://docs.drand.love/developer/http-api/).

## Verification rule

The request is closed, canonical, compact ASCII JSON with exactly one final
line feed. The round is a canonical decimal string in `1..2^64-1`; Python
converts it from an actual `int`, so JavaScript number rounding cannot alter
it.

For a request that matches the fixed chain identity, the implementation:

1. decodes lowercase canonical 48-byte G1 signature and 96-byte G2 public-key
   encodings;
2. rejects infinity, invalid-curve, non-prime-subgroup, and non-canonical
   encodings;
3. requires `randomness = SHA256(signature)`;
4. computes `message = SHA256(uint64be(round))`;
5. hashes that message to G1 with the fixed RFC 9380 DST and verifies the BLS
   pairing against the fixed G2 public key.

The round serialization, unchained digest, G1/G2 placement, and DST are also
fixed by drand's
[protocol specification](https://docs.drand.love/docs/specification/) and its
commit-pinned
[`crypto/schemes.go`](https://github.com/drand/drand/blob/2363f3b9ba5fd6f14e0b84a096b248479790d75d/crypto/schemes.go#L212-L250).
Randomness as the hash of the signature is described in drand's
[cryptography documentation](https://docs.drand.love/docs/cryptography/).

The verifier does not choose a target round, derive a future round, query a
clock, fetch `/latest`, or contact any drand relay. A caller must supply the
round, signature, and randomness obtained through a separately governed
channel.

## Vendored cryptography

The exact minimal CommonJS import closure is checked before loading. It
contains 18 upstream files plus `VENDOR_MANIFEST.json` and
`quicknet_verify.cjs`:

| Package | Version | npm tarball SHA-256 | Git commit |
| --- | --- | --- | --- |
| `@noble/curves` | `1.9.7` | `c4c5545645b8d58a080d2faf84982f6fe5dc3a0516e11de8dc571b38cab565e9` | `a0ac59846ee76c52f7c18886f4963e1211345d48` |
| `@noble/hashes` | `1.8.0` | `e8a765d92c04faaccba8776411c5038cb195f812ee629fce07e1d2e6aec80ea0` | `32f700f38ec49d7e6b2ab687904d6b2d7d60d80a` |

The manifest also records npm SRI, npm SHA-1, signed GitHub tag objects, the
registry signing key ID, per-file SHA-256 values, versions, and MIT licenses.
Those provenance fields are audit-time records. Offline verification pins and
checks the bytes; it does not re-query npm, GitHub, a transparency log, or an
attestation service.

One trailing space in `@noble/hashes@1.8.0` `utils.js` line 133 is preserved
to keep the exact npm source bytes. A regression test fixes that as the only
permitted upstream whitespace exception.

Fresh wheel and sdist builds must contain exactly the same 20-file vendor
inventory. The installed wheel is tested with `verify_vendored_noble()` and
the round-1000 vector; no npm installation is part of build or runtime.

## CI and qualified host

Portable cryptographic semantics are mandatory in the Python CI matrix under
exact Node `24.18.1` on Linux/x64. CI pins
[`actions/setup-node`](https://github.com/actions/setup-node) v7.0.0 by full
commit SHA `820762786026740c76f36085b0efc47a31fe5020`, requests architecture
`x64`, disables package-manager caching, and asserts the exact Node version,
`process.platform == "linux"`, and `process.arch == "x64"` before the portable
suite. It then runs the known vector plus identity, signature, randomness,
canonical-JSON, infinity, malformed-compression, and on-curve non-subgroup
adversarial cases. This suite has no skip path when the CI job is configured
correctly.

Before commit `0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`, published CI
checkpoints used exact Node 24.18.0 with full-SHA-pinned
`actions/setup-node` v6.5.0. Their recorded results remain historical and
unchanged; they do not establish the new Node/action pin. The security update
changes only the workflow and its contract test, not Quicknet verifier or
vendored cryptography bytes.

Public CI run `30617537380` succeeded in 16m24s at exact source commit
`0e30a61c8f2e1ef6ce557c5ebea5b0ee1b7606ec`. Every matrix job used the
full-SHA-pinned setup action, provisioned exact Node 24.18.1 on Linux/x64, and
passed the exact version/platform/architecture assertions. Python 3.11 passed
Quicknet 6/6 in 535.647147ms and all 1,047 tests with 22
environment-specific skips in 856.889s, with a 14m50s job duration. Python
3.13 passed Quicknet 6/6 in 525.265295ms and the same 1,047-test, 22-skip
suite in 944.686s, with a 16m20s job duration. Python 3.14 passed Quicknet 6/6
in 527.783322ms and that suite in 895.407s, with a 15m28s job duration. Every
matrix job passed Ruff, accepted all 181 checked files as formatted, reported
zero Pyright errors, warnings, or information messages, and built both the
sdist and wheel.

The qualification-host Python wrapper in this component is deliberately
narrower:

- `/usr/bin/node` `v18.19.1`, root-owned launcher SHA-256
  `f3f93db342d5ac5bb61656d0599a603a73779e98befd9342171e550002725f4d`;
- `/usr/bin/prlimit` from util-linux `2.39.3`, root-owned launcher SHA-256
  `f27cfd8c1512a4cc6541b59b80cb4cdfd6ef28c34aa21db4299b48264cd0d128`;
- address-space, core, CPU, file-size, and file-descriptor limits applied by
  `prlimit`, without Python `preexec_fn`;
- an empty/minimal fixed environment, no shell, a private working directory,
  bounded input/output, and a wall timeout.

Node 18 is
[end-of-life](https://nodejs.org/en/about/previous-releases). This wrapper is
therefore legacy host-qualified only and is not a portable or
supported-runtime release. Current CI is configured to check the vendored BLS
semantics on exact Node 24.18.1/Linux/x64, but it does not silently
authorize a deployment launcher or attest the provisioned runtime outside
that ephemeral job. A future deployment runner must pin and audit a supported
host runtime, its launcher and dynamic closure, and update the closed host
contract.

## Trust boundary and residual risk

- The setup action pin, version/platform/architecture assertions, and passing
  BLS suite are semantic-CI evidence, not runtime provenance, deployment, or
  execution attestation.
- The Node and `prlimit` hashes cover their launcher files, not the dynamic
  `libnode`, OpenSSL, glibc, kernel, or complete operating-system closure.
  Those root-owned components are an explicit trusted host base.
- The Python wrapper makes no network call and ordinary Node network modules
  and globals are disabled. It does not create a kernel network namespace.
  Compatibility is tested under systemd `PrivateNetwork=yes`; deployments
  requiring enforced denial must supply such an OS sandbox.
- Files must be regular, single-link, non-group/world-writable files owned by
  the invoking UID or root. The same-UID concurrent replacement window between
  checking and use remains outside this threat model.
- The known round is qualification evidence, not a hidden runtime self-test.
  The runtime validates only the caller's supplied beacon.
- Noble, Node/V8, and garbage collection are not asserted to be constant-time.
  This verifier handles public inputs and no secret key.
- `VerifiedQuicknetBeacon` is an in-process convenience value, not an
  unforgeable proof, trusted timestamp, custody record, external attestation,
  or evidence that a beacon is fresh.
- No future target or round is selected, reserved, fetched, or disclosed by
  this component.

No project or deployment runtime was installed or changed by the source
update. It built or dispatched no freeze, accessed no protected or real data,
and ran no worker or detector.

## Local checks

```text
uv run python -m unittest -v tests/test_kp1979_v3_quicknet.py
node --test tests/node/kp1979_v3_quicknet.test.cjs
just check
```

The host-only Node test is intentionally separate at
`tests/node/kp1979_v3_quicknet_host.test.cjs`; it is exercised only when the
current qualification host's Node and `prlimit` prerequisites match exactly.
