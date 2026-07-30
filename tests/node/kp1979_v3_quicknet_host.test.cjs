"use strict";

const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
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

test("qualified standalone CLI rejects oversized input without waiting for EOF", async () => {
  assert.equal(process.execPath, verifier.NODE_EXECUTABLE);
  assert.equal(process.version, verifier.NODE_VERSION);
  const child = childProcess.spawn(verifier.NODE_EXECUTABLE, [VERIFIER_PATH], {
    env: {
      LANG: "C",
      LC_ALL: "C",
      NODE_NO_WARNINGS: "1",
      NODE_OPTIONS: "",
      NODE_PATH: "",
      PATH: "/usr/bin",
      TZ: "UTC",
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  child.stdin.on("error", () => {});
  child.stdin.write(Buffer.alloc(verifier.MAX_INPUT_BYTES + 1, 0x20));
  const exitCode = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("oversized CLI input was not rejected promptly"));
    }, 2000);
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("exit", (code) => {
      clearTimeout(timer);
      resolve(code);
    });
  });
  assert.equal(exitCode, 2);
  assert.equal(Buffer.concat(stderr).length, 0);
  assert.equal(
    Buffer.concat(stdout).toString("ascii"),
    `{"code":"verification_failed","status":"rejected","version":"${verifier.VERSION}"}\n`,
  );
});
