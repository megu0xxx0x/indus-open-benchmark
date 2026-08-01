"""Verify the source-link static loader from an isolated built wheel.

This is a post-build CI check, not a unittest-discovery module. It verifies
wheel/resource parity and then loads only the extracted wheel package from an
empty working directory under isolated Python.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RESOURCES = {
    "registry/chanhu-daro-helsinki-gate-v1.json": (
        6955,
        "43c0fae1a8558fbffeb062725e401e0c3c1de570e5f8f7eef610ca2616cbfb3d",
    ),
    "registry/sources.json": (
        43235,
        "e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584",
    ),
    "registry/source-reported-link-policy-v1.json": (
        7967,
        "c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90",
    ),
    "registry/source-reported-link-source-contract-v1.json": (
        29059,
        "e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f",
    ),
    "registry/source-reported-link-protected-ephemeral-custody-contract-v1.json": (
        426824,
        "917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914",
    ),
    "schemas/context-source-link-gate.schema.json": (
        9216,
        "72109818eb55aca008b0f34b1d6c627efd0e38bdbaff8c500cb3c60dc74e3002",
    ),
    "schemas/source-registry.schema.json": (
        8295,
        "6272a824cd09fb7a3b50225006ffedd4191c707545ad3f98c7d971438906beb3",
    ),
    "schemas/source-reported-link-policy.schema.json": (
        8589,
        "d951541892bb6a5ef092d44e9a5564da2261f960e52e3e84a95ecd5ef8e61aff",
    ),
    "schemas/source-reported-link-source-contract.schema.json": (
        30752,
        "e73a90c12b25c40d134f5ac58d1fceb793f2cd14168e77c7035eef9dd41c3e78",
    ),
    "schemas/source-reported-link-protected-ephemeral-custody-contract.schema.json": (
        440116,
        "5c4b88acb41676b49139242944f28cc3da1202b1e1193edb6e35481aeabaae3b",
    ),
    "schemas/source-reported-link-source-revision-receipt.schema.json": (
        9316,
        "6d0451ed9471315b11689e6cabe8bf7b15e6b5d31f0064d5a364c9ac73789375",
    ),
    "schemas/source-reported-link-receipt-commitment-envelope.schema.json": (
        2546,
        "f4e316c5542c5ea9c57a91fc5006a10550c2dbbd08436e165d997e265570c2d4",
    ),
    "schemas/source-reported-link-source-revision-set.schema.json": (
        6459,
        "15d64ee72ea7a147bcde22a2c28330b67c1eae4d299e272296a53a2ef25d17bb",
    ),
    "schemas/source-reported-link-completeness-attestation.schema.json": (
        5627,
        "a8ae0f32fbda8cd1bb7e29db3d3444ec0659ffa9f9818ea85331288d0f018c02",
    ),
}

_ISOLATED_PROGRAM = r"""
import json
import pathlib
import sys

wheel_root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(wheel_root))

def deny_network(event, args):
    del args
    if event.startswith("socket."):
        raise RuntimeError("network forbidden")

sys.addaudithook(deny_network)

import indusbench
from indusbench.source_reported_link_static import load_installed_source_link_static

package_file = pathlib.Path(indusbench.__file__).resolve()
if not package_file.is_relative_to(wheel_root):
    raise SystemExit("source checkout shadowed the extracted wheel")

snapshot = load_installed_source_link_static()
expected = {
    "artifact_schema_set_sha256": (
        "sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f"
    ),
    "custody_contract_sha256": (
        "sha256:917306d82d7e52551d8a88cc3a82448bbce4b595ed7d08eeaa681ac090222914"
    ),
    "ordered_source_roster_sha256": (
        "sha256:28fe425d8e3d2dcb0b6d6b5c89a3d5d8c3bcea0ab0b6ec86158e185bd0f7a86f"
    ),
    "source_contract_sha256": (
        "sha256:e319e8bdd0021ea58986155788118481c82166a13424ff49d5c949f58876286f"
    ),
    "source_policy_sha256": (
        "sha256:c29c4c2b4beb672e5ce47d6dbc1eb56bbbfe242ef5dd84a09d36a45e672e1d90"
    ),
    "source_registry_sha256": (
        "sha256:e5efa34c8efb4b0b8f0530c9fe4c3e84b8248ecaba0c2cee054825a553133584"
    ),
}
observed = {name: getattr(snapshot, name) for name in expected}
if observed != expected:
    raise SystemExit("static snapshot mismatch")
if snapshot.resource_count != 14:
    raise SystemExit("static resource count mismatch")
if snapshot.missing_binding_fields != (
    "runtime_distribution_sha256",
    "transitive_runtime_input_manifest_sha256",
):
    raise SystemExit("missing-binding boundary mismatch")
if snapshot.strict_v1_resolver_eligible is not False:
    raise SystemExit("strict-v1 eligibility boundary mismatch")
if snapshot.strict_v1_resolver_blockers != (
    "source_registry_noncanonical_raw_bytes",
    "source_registry_schema_noncanonical_raw_bytes",
):
    raise SystemExit("strict-v1 blocker boundary mismatch")
print(json.dumps({"isolated_wheel_static_snapshot": "ok"}, sort_keys=True))
"""


def _fail(message: str) -> None:
    raise SystemExit(f"installed-distribution verification failed: {message}")


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        _fail("unsafe wheel member name")


def verify(wheel: Path) -> None:
    if not wheel.is_file() or wheel.suffix != ".whl":
        _fail("exactly one wheel path is required")

    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            _fail("duplicate wheel member")
        if len(names) != len({name.casefold() for name in names}):
            _fail("case-folding wheel member collision")
        for member in members:
            _validate_member_name(member.filename)
            mode = member.external_attr >> 16
            if member.is_dir():
                if mode and not stat.S_ISDIR(mode):
                    _fail("non-directory wheel member mode")
            elif stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                _fail("non-regular wheel member")

        for relative_path, (expected_size, expected_sha256) in EXPECTED_RESOURCES.items():
            wheel_name = f"indusbench/{relative_path}"
            matching = [member for member in members if member.filename == wheel_name]
            if len(matching) != 1:
                _fail("exact static resource set is incomplete")
            member = matching[0]
            if not stat.S_ISREG(member.external_attr >> 16):
                _fail("static resource is not a regular wheel member")
            if member.file_size != expected_size:
                _fail("wheel resource size mismatch")
            raw = archive.read(member)
            if len(raw) != expected_size:
                _fail("wheel resource short read")
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                _fail("wheel resource digest mismatch")
            if raw != (ROOT / relative_path).read_bytes():
                _fail("wheel and repository resource bytes differ")

        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-wheel-static-") as raw_directory:
                extracted = Path(raw_directory) / "installed"
                empty_cwd = Path(raw_directory) / "empty-cwd"
                extracted.mkdir()
                empty_cwd.mkdir()
                archive.extractall(extracted)
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-s",
                        "-B",
                        "-c",
                        _ISOLATED_PROGRAM,
                        str(extracted),
                    ],
                    cwd=empty_cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
        finally:
            os.umask(previous_umask)
    if completed.returncode != 0:
        _fail("isolated wheel loader rejected the distribution")
    if completed.stdout.strip() != '{"isolated_wheel_static_snapshot": "ok"}':
        _fail("isolated wheel loader emitted unexpected output")
    if completed.stderr:
        _fail("isolated wheel loader emitted stderr")


def main() -> None:
    if len(sys.argv) != 2:
        _fail("exactly one wheel path is required")
    verify(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
