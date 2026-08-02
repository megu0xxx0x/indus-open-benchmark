"""Verify the source-link static loader from an isolated built wheel.

This is a post-build CI check, not a unittest-discovery module. It verifies
wheel/resource parity and then loads only the extracted wheel package from an
empty working directory under isolated Python.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Never

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RESOURCES = {
    "benchmark/numeral-metrology-functional-anchor-protocol-v1.json": (
        25450,
        "b4e175ee3506a8f46883428937236bc5353f26bbe32db64ad98d72eca4692307",
    ),
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
    "schemas/hypothesis.schema.json": (
        15581,
        "47cbe121b6b51af8c1f87e0827705f5db0ade16bb095c8db09cce03e8434bbe7",
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

EXPECTED_V2_WRAPPER_RESOURCES = {
    "registry/source-reported-link-protected-ephemeral-custody-contract-v2.json": (
        16981,
        "a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c",
    ),
    "schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json": (
        17694,
        "1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671",
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
from indusbench.source_reported_link_static_v2 import (
    load_installed_source_link_static_profile_v2,
)

package_file = pathlib.Path(indusbench.__file__).resolve()
if not package_file.is_relative_to(wheel_root):
    raise SystemExit("source checkout shadowed the extracted wheel")

expected_v1 = {
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
expected_v2 = {
    "artifact_schema_set_sha256": (
        "sha256:f4cd8e02a6065ff57170182a0347e2e10bb9f922c5fadf2fbf37694148c5ab9f"
    ),
    "compatibility_profile_id": (
        "source-reported-link-exact-two-static-byte-compatibility-v2"
    ),
    "compatibility_wrapper_sha256": (
        "sha256:a064331361057947e8b4079dcc114e3d7918459a538107039199f7074bc4c86c"
    ),
    "compatibility_wrapper_schema_sha256": (
        "sha256:1523534dabf734c2381d454f4c7a387f271fd4088f81c3d15a4d0e4915fed671"
    ),
    "incorporated_v1_custody_contract_sha256": (
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

def validate_v1(snapshot):
    observed = {name: getattr(snapshot, name) for name in expected_v1}
    if observed != expected_v1:
        raise SystemExit("V1 static snapshot mismatch")
    if snapshot.resource_count != 14:
        raise SystemExit("V1 static resource count mismatch")
    if snapshot.missing_binding_fields != (
        "runtime_distribution_sha256",
        "transitive_runtime_input_manifest_sha256",
    ):
        raise SystemExit("V1 missing-binding boundary mismatch")
    if snapshot.strict_v1_resolver_eligible is not False:
        raise SystemExit("V1 eligibility boundary mismatch")
    if snapshot.strict_v1_resolver_blockers != (
        "source_registry_noncanonical_raw_bytes",
        "source_registry_schema_noncanonical_raw_bytes",
    ):
        raise SystemExit("V1 blocker boundary mismatch")
    return {
        **observed,
        "resource_count": snapshot.resource_count,
        "missing_binding_fields": snapshot.missing_binding_fields,
        "strict_v1_resolver_eligible": snapshot.strict_v1_resolver_eligible,
        "strict_v1_resolver_blockers": snapshot.strict_v1_resolver_blockers,
    }

def validate_v2(snapshot):
    observed = {name: getattr(snapshot, name) for name in expected_v2}
    if observed != expected_v2:
        raise SystemExit("V2 static snapshot mismatch")
    if snapshot.resource_count != 16:
        raise SystemExit("V2 static resource count mismatch")
    if snapshot.missing_binding_fields != (
        "runtime_distribution_sha256",
        "transitive_runtime_input_manifest_sha256",
    ):
        raise SystemExit("V2 missing-binding boundary mismatch")
    if snapshot.package_local_static_prevalidation_status != (
        "validated_package_local_exact16_only"
    ):
        raise SystemExit("V2 package-local status mismatch")
    if snapshot.package_local_v2_static_profile_conformant is not True:
        raise SystemExit("V2 package-local conformance mismatch")
    if snapshot.strict_v1_resolver_eligible is not False:
        raise SystemExit("V2 strict-V1 boundary mismatch")
    if snapshot.strict_v1_resolver_blockers != (
        "source_registry_noncanonical_raw_bytes",
        "source_registry_schema_noncanonical_raw_bytes",
    ):
        raise SystemExit("V2 strict-V1 blocker boundary mismatch")
    if (
        snapshot.authority_status != "not_authorized"
        or snapshot.runtime_status != "not_validated"
        or snapshot.source_access_status != "not_performed"
        or snapshot.result_status != "not_established"
        or snapshot.activation_status != "blocked_external_prerequisites_absent"
    ):
        raise SystemExit("V2 activation nonclaim mismatch")
    for absent in (
        "custody_contract_sha256",
        "eligible",
        "authorized",
        "runtime_distribution_sha256",
        "transitive_runtime_input_manifest_sha256",
        "protected_bytes",
        "decoded_wrapper",
    ):
        if hasattr(snapshot, absent):
            raise SystemExit("V2 forbidden snapshot field")
    return {
        **observed,
        "resource_count": snapshot.resource_count,
        "missing_binding_fields": snapshot.missing_binding_fields,
        "package_local_static_prevalidation_status": (
            snapshot.package_local_static_prevalidation_status
        ),
        "package_local_v2_static_profile_conformant": (
            snapshot.package_local_v2_static_profile_conformant
        ),
        "strict_v1_resolver_eligible": snapshot.strict_v1_resolver_eligible,
        "strict_v1_resolver_blockers": snapshot.strict_v1_resolver_blockers,
        "authority_status": snapshot.authority_status,
        "runtime_status": snapshot.runtime_status,
        "source_access_status": snapshot.source_access_status,
        "result_status": snapshot.result_status,
        "activation_status": snapshot.activation_status,
    }

order = sys.argv[2]
if order == "forward":
    v1_before = validate_v1(load_installed_source_link_static())
    validate_v2(load_installed_source_link_static_profile_v2())
    v1_after = validate_v1(load_installed_source_link_static())
    if v1_before != v1_after:
        raise SystemExit("V1 snapshot mutated by V2 load")
elif order == "reverse":
    v2_before = validate_v2(load_installed_source_link_static_profile_v2())
    validate_v1(load_installed_source_link_static())
    v2_after = validate_v2(load_installed_source_link_static_profile_v2())
    if v2_before != v2_after:
        raise SystemExit("V2 snapshot mutated by V1 load")
else:
    raise SystemExit("invalid isolated verification order")

print(json.dumps({"isolated_wheel_static_snapshots": order}, sort_keys=True))
"""


def _fail(message: str) -> Never:
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


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            _fail("duplicate JSON key")
        value[key] = child
    return value


def _decode_json(raw: bytes, label: str) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _: _fail(f"non-finite {label} JSON number"),
        )
    except (UnicodeError, ValueError, TypeError) as error:
        raise SystemExit(
            f"installed-distribution verification failed: invalid {label} JSON"
        ) from error


def _decode_canonical_json(raw: bytes) -> object:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _: _fail("non-finite wrapper JSON number"),
            parse_float=lambda _: _fail("floating wrapper JSON number"),
        )
        canonical = (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (UnicodeError, ValueError, TypeError) as error:
        raise SystemExit(
            "installed-distribution verification failed: invalid wrapper JSON"
        ) from error
    if canonical != raw:
        _fail("noncanonical wrapper JSON")
    return value


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

        protocol = _decode_json(
            archive.read(
                "indusbench/benchmark/numeral-metrology-functional-anchor-protocol-v1.json"
            ),
            "numeral/metrology protocol",
        )
        hypothesis_schema = _decode_json(
            archive.read("indusbench/schemas/hypothesis.schema.json"),
            "hypothesis schema",
        )
        if not isinstance(hypothesis_schema, dict):
            _fail("hypothesis schema is not an object")
        try:
            Draft202012Validator.check_schema(hypothesis_schema)
            Draft202012Validator(hypothesis_schema).validate(protocol)
        except Exception as error:
            raise SystemExit(
                "installed-distribution verification failed: packaged protocol/schema mismatch"
            ) from error

        decoded_v2_resources = {}
        for relative_path, (
            expected_size,
            expected_sha256,
        ) in EXPECTED_V2_WRAPPER_RESOURCES.items():
            wheel_name = f"indusbench/{relative_path}"
            matching = [member for member in members if member.filename == wheel_name]
            if len(matching) != 1:
                _fail("exact V2 wrapper resource set is incomplete")
            member = matching[0]
            if not stat.S_ISREG(member.external_attr >> 16):
                _fail("V2 wrapper resource is not a regular wheel member")
            if member.file_size != expected_size:
                _fail("V2 wrapper resource size mismatch")
            raw = archive.read(member)
            if len(raw) != expected_size:
                _fail("V2 wrapper resource short read")
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                _fail("V2 wrapper resource digest mismatch")
            if raw != (ROOT / relative_path).read_bytes():
                _fail("wheel and repository V2 wrapper bytes differ")
            decoded_v2_resources[relative_path] = _decode_canonical_json(raw)

        wrapper = decoded_v2_resources[
            "registry/source-reported-link-protected-ephemeral-custody-contract-v2.json"
        ]
        wrapper_schema = decoded_v2_resources[
            "schemas/source-reported-link-protected-ephemeral-custody-contract-v2.schema.json"
        ]
        if not isinstance(wrapper_schema, dict):
            _fail("V2 wrapper schema is not an object")
        if set(wrapper_schema) != {"$id", "$schema", "const"}:
            _fail("V2 wrapper schema surface mismatch")
        if wrapper_schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
            _fail("V2 wrapper schema dialect mismatch")
        if wrapper_schema["const"] != wrapper:
            _fail("V2 wrapper const mismatch")
        Draft202012Validator.check_schema(wrapper_schema)
        Draft202012Validator(wrapper_schema).validate(wrapper)

        v2_module_name = "indusbench/source_reported_link_static_v2.py"
        matching_v2_modules = [member for member in members if member.filename == v2_module_name]
        if len(matching_v2_modules) != 1:
            _fail("V2 resolver module is absent or duplicated")
        v2_module_member = matching_v2_modules[0]
        if not stat.S_ISREG(v2_module_member.external_attr >> 16):
            _fail("V2 resolver module is not a regular wheel member")
        if (
            archive.read(v2_module_member)
            != (ROOT / "src" / "indusbench" / "source_reported_link_static_v2.py").read_bytes()
        ):
            _fail("wheel and repository V2 resolver module bytes differ")

        previous_umask = os.umask(0o022)
        try:
            with tempfile.TemporaryDirectory(prefix="indus-wheel-static-") as raw_directory:
                extracted = Path(raw_directory) / "installed"
                empty_cwd = Path(raw_directory) / "empty-cwd"
                extracted.mkdir()
                empty_cwd.mkdir()
                archive.extractall(extracted)
                completed_runs = []
                for order in ("forward", "reverse"):
                    completed_runs.append(
                        (
                            order,
                            subprocess.run(
                                [
                                    sys.executable,
                                    "-I",
                                    "-s",
                                    "-B",
                                    "-c",
                                    _ISOLATED_PROGRAM,
                                    str(extracted),
                                    order,
                                ],
                                cwd=empty_cwd,
                                check=False,
                                capture_output=True,
                                text=True,
                                timeout=60,
                            ),
                        )
                    )
        finally:
            os.umask(previous_umask)
    for order, completed in completed_runs:
        if completed.returncode != 0:
            _fail("isolated wheel loader rejected the distribution")
        expected_stdout = json.dumps(
            {"isolated_wheel_static_snapshots": order},
            sort_keys=True,
        )
        if completed.stdout.strip() != expected_stdout:
            _fail("isolated wheel loader emitted unexpected output")
        if completed.stderr:
            _fail("isolated wheel loader emitted stderr")


def main() -> None:
    if len(sys.argv) != 2:
        _fail("exactly one wheel path is required")
    verify(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    main()
