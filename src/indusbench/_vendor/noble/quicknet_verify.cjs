"use strict";

const Module = require("node:module");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const VERSION = "kp1979-v3-quicknet-offline-verifier-v1";
const NODE_EXECUTABLE = "/usr/bin/node";
const NODE_VERSION = "v18.19.1";
const MAX_INPUT_BYTES = 4096;
const MAX_MANIFEST_BYTES = 16384;
const MAX_UINT64 = (1n << 64n) - 1n;
const VENDOR_MANIFEST_SHA256 =
  "84e999ba41218a6a80b0a880fe714bf158667f670ce394e0f39774a9e7586b4b";

const CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971";
const PUBLIC_KEY =
  "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183" +
  "c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4" +
  "bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a";
const GROUP_HASH = "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e";
const SCHEME_ID = "bls-unchained-g1-rfc9380";
const BEACON_ID = "quicknet";
const DST = "BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_";
const GENESIS_TIME = 1692803367;
const PERIOD = 3;

const REQUEST_KEYS = Object.freeze([
  "beacon_id",
  "chain_hash",
  "dst",
  "genesis_time",
  "group_hash",
  "period",
  "public_key",
  "randomness",
  "round",
  "scheme_id",
  "signature",
  "version",
]);
const EXPECTED_ENVIRONMENT = Object.freeze({
  LANG: "C",
  LC_ALL: "C",
  NODE_NO_WARNINGS: "1",
  NODE_OPTIONS: "",
  NODE_PATH: "",
  PATH: "/usr/bin",
  TZ: "UTC",
});
const DENIED_NETWORK_MODULES = new Set([
  "dgram",
  "dns",
  "dns/promises",
  "http",
  "http2",
  "https",
  "net",
  "tls",
]);

class VerificationError extends Error {
  constructor() {
    super("verification_failed");
    this.name = "VerificationError";
  }
}

function fail() {
  throw new VerificationError();
}

function canonicalJson(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) fail();
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  }
  if (typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype) {
    const keys = Object.keys(value).sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  fail();
}

function bytesToHex(bytes) {
  let output = "";
  for (const value of bytes) output += value.toString(16).padStart(2, "0");
  return output;
}

function hexToBytes(value, length) {
  if (
    typeof value !== "string" ||
    value.length !== length * 2 ||
    !/^[0-9a-f]+$/.test(value)
  ) {
    fail();
  }
  const output = new Uint8Array(length);
  for (let index = 0; index < length; index += 1) {
    output[index] = Number.parseInt(value.slice(index * 2, index * 2 + 2), 16);
  }
  return output;
}

function equalBytes(left, right) {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

function sha256Hex(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function roundToBytes(round) {
  const output = new Uint8Array(8);
  let remaining = round;
  for (let index = output.length - 1; index >= 0; index -= 1) {
    output[index] = Number(remaining & 0xffn);
    remaining >>= 8n;
  }
  if (remaining !== 0n) fail();
  return output;
}

function requireSafePath(target, expectedType) {
  let metadata;
  try {
    metadata = fs.lstatSync(target);
    if (fs.realpathSync(target) !== target) fail();
  } catch {
    fail();
  }
  if (
    metadata.isSymbolicLink() ||
    (expectedType === "file" && (!metadata.isFile() || metadata.nlink !== 1)) ||
    (expectedType === "directory" && !metadata.isDirectory()) ||
    (metadata.uid !== 0 && metadata.uid !== process.getuid()) ||
    (metadata.mode & 0o022) !== 0
  ) {
    fail();
  }
  return metadata;
}

function collectFiles(directory, output) {
  requireSafePath(directory, "directory");
  let names;
  try {
    names = fs.readdirSync(directory).sort();
  } catch {
    fail();
  }
  for (const name of names) {
    const target = path.join(directory, name);
    const metadata = fs.lstatSync(target);
    if (metadata.isDirectory()) collectFiles(target, output);
    else {
      requireSafePath(target, "file");
      output.push(target);
    }
  }
}

let vendorVerified = false;
function verifyVendor() {
  if (vendorVerified) return VENDOR_MANIFEST_SHA256;
  const manifestPath = path.join(__dirname, "VENDOR_MANIFEST.json");
  requireSafePath(__dirname, "directory");
  const manifestMetadata = requireSafePath(manifestPath, "file");
  if (manifestMetadata.size < 1 || manifestMetadata.size > MAX_MANIFEST_BYTES) fail();
  let rawManifest;
  try {
    rawManifest = fs.readFileSync(manifestPath);
  } catch {
    fail();
  }
  if (sha256Hex(rawManifest) !== VENDOR_MANIFEST_SHA256) fail();
  if (
    rawManifest[rawManifest.length - 1] !== 0x0a ||
    rawManifest.subarray(0, -1).includes(0x0a)
  ) {
    fail();
  }
  let manifest;
  try {
    manifest = JSON.parse(rawManifest.toString("ascii"));
  } catch {
    fail();
  }
  if (
    canonicalJson(manifest) !== rawManifest.subarray(0, -1).toString("ascii") ||
    manifest === null ||
    typeof manifest !== "object" ||
    Array.isArray(manifest) ||
    Object.keys(manifest).sort().join(",") !== "format,packages" ||
    manifest.format !== "kp1979-v3-noble-vendor-manifest-v1" ||
    !Array.isArray(manifest.packages) ||
    manifest.packages.length !== 2
  ) {
    fail();
  }

  const nodeModules = path.join(__dirname, "node_modules");
  const namespaceRoot = path.join(nodeModules, "@noble");
  requireSafePath(nodeModules, "directory");
  requireSafePath(namespaceRoot, "directory");
  const declared = [];
  for (const packageRecord of manifest.packages) {
    if (
      packageRecord === null ||
      typeof packageRecord !== "object" ||
      Array.isArray(packageRecord) ||
      !["@noble/curves", "@noble/hashes"].includes(packageRecord.name) ||
      !Array.isArray(packageRecord.files) ||
      packageRecord.files.length === 0
    ) {
      fail();
    }
    const packageRoot = path.join(namespaceRoot, packageRecord.name.slice("@noble/".length));
    requireSafePath(packageRoot, "directory");
    let previous = "";
    for (const fileRecord of packageRecord.files) {
      if (
        fileRecord === null ||
        typeof fileRecord !== "object" ||
        Array.isArray(fileRecord) ||
        Object.keys(fileRecord).sort().join(",") !== "path,sha256" ||
        typeof fileRecord.path !== "string" ||
        typeof fileRecord.sha256 !== "string" ||
        !/^[0-9a-f]{64}$/.test(fileRecord.sha256) ||
        fileRecord.path <= previous ||
        path.isAbsolute(fileRecord.path) ||
        fileRecord.path.split("/").some((part) => part === "" || part === "." || part === "..")
      ) {
        fail();
      }
      const target = path.join(packageRoot, ...fileRecord.path.split("/"));
      if (!target.startsWith(`${packageRoot}${path.sep}`)) fail();
      requireSafePath(path.dirname(target), "directory");
      requireSafePath(target, "file");
      let fileBytes;
      try {
        fileBytes = fs.readFileSync(target);
      } catch {
        fail();
      }
      if (sha256Hex(fileBytes) !== fileRecord.sha256) fail();
      declared.push(target);
      previous = fileRecord.path;
    }
  }
  if (manifest.packages.map((entry) => entry.name).join(",") !== "@noble/curves,@noble/hashes") {
    fail();
  }
  const actual = [];
  collectFiles(nodeModules, actual);
  const actualSorted = actual.sort();
  const declaredSorted = declared.sort();
  if (
    actualSorted.length !== declaredSorted.length ||
    actualSorted.some((entry, index) => entry !== declaredSorted[index])
  ) {
    fail();
  }
  vendorVerified = true;
  return VENDOR_MANIFEST_SHA256;
}

function assertRuntime() {
  if (
    process.execPath !== NODE_EXECUTABLE ||
    process.version !== NODE_VERSION ||
    process.execArgv.length !== 0 ||
    process.argv.length !== 2
  ) {
    fail();
  }
  const actualKeys = Object.keys(process.env).sort();
  const expectedKeys = Object.keys(EXPECTED_ENVIRONMENT).sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some(
      (key, index) =>
        key !== expectedKeys[index] || process.env[key] !== EXPECTED_ENVIRONMENT[key],
    )
  ) {
    fail();
  }
}

let networkGuardInstalled = false;
function installNetworkGuard() {
  if (networkGuardInstalled) return;
  networkGuardInstalled = true;
  const originalLoad = Module._load;
  Module._load = function guardedLoad(request, parent, isMain) {
    const normalized = request.startsWith("node:") ? request.slice(5) : request;
    if (DENIED_NETWORK_MODULES.has(normalized)) fail();
    return originalLoad.call(this, request, parent, isMain);
  };
  for (const globalName of ["EventSource", "WebSocket", "fetch"]) {
    if (Object.prototype.hasOwnProperty.call(globalThis, globalName)) {
      Object.defineProperty(globalThis, globalName, {
        configurable: false,
        enumerable: false,
        value: undefined,
        writable: false,
      });
    }
  }
}

function parseCanonicalRequest(rawInput) {
  if (!(rawInput instanceof Uint8Array) || rawInput.length === 0 || rawInput.length > MAX_INPUT_BYTES) {
    fail();
  }
  for (const byte of rawInput) {
    if (byte > 0x7f) fail();
  }
  const text = Buffer.from(rawInput).toString("ascii");
  if (!text.endsWith("\n") || text.indexOf("\n") !== text.length - 1) fail();
  const body = text.slice(0, -1);
  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    fail();
  }
  if (
    parsed === null ||
    typeof parsed !== "object" ||
    Array.isArray(parsed) ||
    Object.getPrototypeOf(parsed) !== Object.prototype
  ) {
    fail();
  }
  const keys = Object.keys(parsed).sort();
  if (
    keys.length !== REQUEST_KEYS.length ||
    keys.some((key, index) => key !== REQUEST_KEYS[index]) ||
    canonicalJson(parsed) !== body
  ) {
    fail();
  }
  if (
    parsed.version !== VERSION ||
    parsed.beacon_id !== BEACON_ID ||
    parsed.chain_hash !== CHAIN_HASH ||
    parsed.public_key !== PUBLIC_KEY ||
    parsed.group_hash !== GROUP_HASH ||
    parsed.scheme_id !== SCHEME_ID ||
    parsed.dst !== DST ||
    parsed.genesis_time !== GENESIS_TIME ||
    parsed.period !== PERIOD
  ) {
    fail();
  }
  if (typeof parsed.round !== "string" || !/^[1-9][0-9]*$/.test(parsed.round)) fail();
  let round;
  try {
    round = BigInt(parsed.round);
  } catch {
    fail();
  }
  if (round < 1n || round > MAX_UINT64) fail();
  hexToBytes(parsed.signature, 48);
  hexToBytes(parsed.randomness, 32);
  return Object.freeze({ ...parsed, round });
}

let noble;
function loadNoble() {
  if (noble !== undefined) return noble;
  installNetworkGuard();
  verifyVendor();
  const curvesPath = path.join(
    __dirname,
    "node_modules",
    "@noble",
    "curves",
    "bls12-381.js",
  );
  const hashesPath = path.join(
    __dirname,
    "node_modules",
    "@noble",
    "hashes",
    "sha2.js",
  );
  const { bls12_381 } = require(curvesPath);
  const { sha256 } = require(hashesPath);
  if (typeof bls12_381 !== "object" || typeof sha256 !== "function") fail();
  noble = Object.freeze({ bls12_381, sha256 });
  return noble;
}

function verifyParsedRequest(request) {
  const { bls12_381, sha256 } = loadNoble();
  const signatureBytes = hexToBytes(request.signature, 48);
  const publicKeyBytes = hexToBytes(request.public_key, 96);
  const expectedRandomness = hexToBytes(request.randomness, 32);
  if (!equalBytes(sha256(signatureBytes), expectedRandomness)) fail();

  let signaturePoint;
  let publicKeyPoint;
  try {
    signaturePoint = bls12_381.ShortSignature.fromBytes(signatureBytes);
    publicKeyPoint = bls12_381.G2.Point.fromBytes(publicKeyBytes);
    signaturePoint.assertValidity();
    publicKeyPoint.assertValidity();
  } catch {
    fail();
  }
  if (signaturePoint.is0() || publicKeyPoint.is0()) fail();
  if (
    bytesToHex(bls12_381.ShortSignature.toBytes(signaturePoint)) !== request.signature ||
    bytesToHex(publicKeyPoint.toBytes(true)) !== request.public_key
  ) {
    fail();
  }

  const message = sha256(roundToBytes(request.round));
  const messagePoint = bls12_381.shortSignatures.hash(message, DST);
  let valid = false;
  try {
    valid = bls12_381.shortSignatures.verify(signaturePoint, messagePoint, publicKeyPoint);
  } catch {
    fail();
  }
  if (valid !== true) fail();
  return Object.freeze({
    chain_hash: CHAIN_HASH,
    randomness: request.randomness,
    round: request.round.toString(10),
    status: "verified",
    version: VERSION,
  });
}

function evaluate(rawInput) {
  try {
    const request = parseCanonicalRequest(rawInput);
    const response = verifyParsedRequest(request);
    return Object.freeze({
      exitCode: 0,
      output: `${canonicalJson(response)}\n`,
    });
  } catch {
    return Object.freeze({
      exitCode: 2,
      output: `${canonicalJson({
        code: "verification_failed",
        status: "rejected",
        version: VERSION,
      })}\n`,
    });
  }
}

function readBoundedStdin() {
  return new Promise((resolve) => {
    const chunks = [];
    let length = 0;
    let settled = false;
    const finish = (input) => {
      if (settled) return;
      settled = true;
      resolve(input);
    };
    process.stdin.on("data", (chunk) => {
      if (settled) return;
      length += chunk.length;
      if (length > MAX_INPUT_BYTES) {
        chunks.length = 0;
        process.stdin.destroy();
        finish(new Uint8Array());
      } else {
        chunks.push(chunk);
      }
    });
    process.stdin.on("error", () => finish(new Uint8Array()));
    process.stdin.on("end", () => {
      finish(new Uint8Array(Buffer.concat(chunks)));
    });
  });
}

async function main() {
  let result;
  try {
    assertRuntime();
    installNetworkGuard();
    result = evaluate(await readBoundedStdin());
  } catch {
    result = {
      exitCode: 2,
      output: `${canonicalJson({
        code: "verification_failed",
        status: "rejected",
        version: VERSION,
      })}\n`,
    };
  }
  process.stdout.write(result.output);
  process.exitCode = result.exitCode;
}

module.exports = Object.freeze({
  BEACON_ID,
  CHAIN_HASH,
  DST,
  GENESIS_TIME,
  GROUP_HASH,
  MAX_INPUT_BYTES,
  NODE_EXECUTABLE,
  NODE_VERSION,
  PERIOD,
  PUBLIC_KEY,
  REQUEST_KEYS,
  SCHEME_ID,
  VERSION,
  canonicalJson,
  evaluate,
  installNetworkGuard,
  parseCanonicalRequest,
  roundToBytes,
  verifyParsedRequest,
  verifyVendor,
});

if (require.main === module) {
  main();
}
