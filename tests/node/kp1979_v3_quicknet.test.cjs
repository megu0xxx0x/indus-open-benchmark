"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const path = require("node:path");
const test = require("node:test");

const VERIFIER_PATH = path.resolve(
  __dirname,
  "..",
  "..",
  "src",
  "indusbench",
  "_vendor",
  "noble",
  "quicknet_verify.cjs",
);
const verifier = require(VERIFIER_PATH);

const SIGNATURE =
  "b44679b9a59af2ec876b1a6b1ad52ea9b1615fc3982b19576350f93447cb112" +
  "5e342b73a8dd2bacbe47e4b6b63ed5e39";
const RANDOMNESS = "fe290beca10872ef2fb164d2aa4442de4566183ec51c56ff3cd603d930e54fdd";
const EXPECTED_OUTPUT =
  `{"chain_hash":"${verifier.CHAIN_HASH}","randomness":"${RANDOMNESS}",` +
  `"round":"1000","status":"verified","version":"${verifier.VERSION}"}\n`;

function request(overrides = {}) {
  return {
    beacon_id: verifier.BEACON_ID,
    chain_hash: verifier.CHAIN_HASH,
    dst: verifier.DST,
    genesis_time: verifier.GENESIS_TIME,
    group_hash: verifier.GROUP_HASH,
    period: verifier.PERIOD,
    public_key: verifier.PUBLIC_KEY,
    randomness: RANDOMNESS,
    round: "1000",
    scheme_id: verifier.SCHEME_ID,
    signature: SIGNATURE,
    version: verifier.VERSION,
    ...overrides,
  };
}

function encode(value) {
  return Buffer.from(`${verifier.canonicalJson(value)}\n`, "ascii");
}

function assertRejected(raw) {
  const result = verifier.evaluate(raw);
  assert.equal(result.exitCode, 2);
  assert.equal(
    result.output,
    `{"code":"verification_failed","status":"rejected","version":"${verifier.VERSION}"}\n`,
  );
}

test("official Quicknet round 1000 vector verifies deterministically", () => {
  const raw = encode(request());
  const first = verifier.evaluate(raw);
  const second = verifier.evaluate(raw);
  assert.equal(first.exitCode, 0);
  assert.equal(first.output, EXPECTED_OUTPUT);
  assert.deepEqual(second, first);
});

test("round serialization is fixed unsigned 64-bit big-endian", () => {
  assert.equal(Buffer.from(verifier.roundToBytes(1n)).toString("hex"), "0000000000000001");
  assert.equal(Buffer.from(verifier.roundToBytes(1000n)).toString("hex"), "00000000000003e8");
  assert.equal(
    Buffer.from(verifier.roundToBytes((1n << 64n) - 1n)).toString("hex"),
    "ffffffffffffffff",
  );
});

test("wrong chain identity, key, scheme, DST, and schedule are rejected", () => {
  const mutations = [
    { beacon_id: "other" },
    { chain_hash: `0${verifier.CHAIN_HASH.slice(1)}` },
    { dst: `${verifier.DST.slice(0, -1)}X` },
    { genesis_time: verifier.GENESIS_TIME + 1 },
    { group_hash: `0${verifier.GROUP_HASH.slice(1)}` },
    { period: verifier.PERIOD + 1 },
    { public_key: `0${verifier.PUBLIC_KEY.slice(1)}` },
    { scheme_id: "bls-unchained-on-g1" },
    { version: "other" },
  ];
  for (const mutation of mutations) assertRejected(encode(request(mutation)));
});

test("wrong round, signature, randomness, and infinity signature are rejected", () => {
  assertRejected(encode(request({ round: "1001" })));
  assertRejected(encode(request({ randomness: `0${RANDOMNESS.slice(1)}` })));

  const changedSignature = `a${SIGNATURE.slice(1)}`;
  const changedRandomness = crypto
    .createHash("sha256")
    .update(Buffer.from(changedSignature, "hex"))
    .digest("hex");
  assertRejected(
    encode(request({ signature: changedSignature, randomness: changedRandomness })),
  );

  const infinitySignature = `c0${"00".repeat(47)}`;
  const infinityRandomness = crypto
    .createHash("sha256")
    .update(Buffer.from(infinitySignature, "hex"))
    .digest("hex");
  assertRejected(
    encode(request({ signature: infinitySignature, randomness: infinityRandomness })),
  );

  // x=0, y=2 is on the BLS12-381 G1 curve but outside its prime-order subgroup.
  const nonSubgroupSignature = `80${"00".repeat(47)}`;
  const nonSubgroupRandomness = crypto
    .createHash("sha256")
    .update(Buffer.from(nonSubgroupSignature, "hex"))
    .digest("hex");
  assertRejected(
    encode(
      request({
        signature: nonSubgroupSignature,
        randomness: nonSubgroupRandomness,
      }),
    ),
  );

  const malformedCompression = `00${"00".repeat(47)}`;
  const malformedRandomness = crypto
    .createHash("sha256")
    .update(Buffer.from(malformedCompression, "hex"))
    .digest("hex");
  assertRejected(
    encode(
      request({
        signature: malformedCompression,
        randomness: malformedRandomness,
      }),
    ),
  );
});

test("closed canonical ASCII JSON and round bounds are mandatory", () => {
  const canonical = encode(request());
  assertRejected(Buffer.from("{}\n", "ascii"));
  assertRejected(Buffer.from(` ${canonical.toString("ascii")}`, "ascii"));
  assertRejected(Buffer.from(`${canonical.toString("ascii").trim()}\r\n`, "ascii"));
  assertRejected(Buffer.from(`${canonical.toString("ascii")}\n`, "ascii"));
  assertRejected(Buffer.from(canonical.toString("ascii").replace('"beacon_id"', '"z"'), "ascii"));
  assertRejected(
    Buffer.from(
      canonical
        .toString("ascii")
        .replace(`"beacon_id":"${verifier.BEACON_ID}"`, '"beacon_id":"quicknet","beacon_id":"quicknet"'),
      "ascii",
    ),
  );
  assertRejected(encode({ ...request(), extra: null }));
  assertRejected(encode(request({ round: 1000 })));
  assertRejected(encode(request({ round: "0" })));
  assertRejected(encode(request({ round: "01" })));
  assertRejected(encode(request({ round: "18446744073709551616" })));
  assertRejected(encode(request({ signature: SIGNATURE.toUpperCase() })));
  assertRejected(Buffer.concat([canonical, Buffer.alloc(verifier.MAX_INPUT_BYTES, 0x20)]));
  assertRejected(Buffer.from([0xff, 0x0a]));
});

test("network-capable Node module surfaces are disabled", () => {
  verifier.installNetworkGuard();
  for (const moduleName of [
    "node:dgram",
    "node:dns",
    "node:http",
    "node:http2",
    "node:https",
    "node:net",
    "node:tls",
  ]) {
    assert.throws(() => require(moduleName), /verification_failed/);
  }
  if (Object.prototype.hasOwnProperty.call(globalThis, "fetch")) {
    assert.equal(globalThis.fetch, undefined);
  }
});
