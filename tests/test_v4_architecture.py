from __future__ import annotations

import ast
import hashlib
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "indusbench"

_FORBIDDEN_PACKAGE_PREFIXES = (
    "indusbench.cli",
    "indusbench.oracc_ed3b",
    "indusbench.v3dev.plan",
    "indusbench.v3dev.runner",
    "indusbench.v3dev_cli",
)
_FORBIDDEN_NETWORK_ROOTS = frozenset(
    {
        "aiohttp",
        "http",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "urllib3",
    }
)
_ALLOWED_LEGACY_IMPORTS = frozenset(
    {
        "indusbench.mtaac",
        "indusbench.mtaac_control",
        "indusbench.v3dev.contracts",
        "indusbench.v3dev.folds",
        "indusbench.v3dev.metrics",
        "indusbench.v3dev.mtaac_training",
        "indusbench.v3dev.sequence",
    }
)
_IMMUTABLE_SHA256 = {
    "src/indusbench/mtaac.py": ("aa6d698272f82108cbf3dce40df29bee4905809318cc931ba7f9dbfab9590c10"),
    "src/indusbench/mtaac_control.py": (
        "1192e74440a193f784c6c8c5afec267e9bfb125d12241a71cf567c35a24b838a"
    ),
    "benchmark/mtaac-known-script-control-v2.json": (
        "25913e826db786f3867d5aca5391f116d1e3e0aab4c22754be28f87ab2fa3892"
    ),
    "benchmark/results/mtaac-known-script-control-v2.json": (
        "6bc4ed610862d109b596bdd934f36fd19b99e3cbfcced42882546d0c852a7afe"
    ),
    "src/indusbench/v3dev/__init__.py": (
        "5fb1b39b7003e7d784cf886a76f5020d7c661bfedbbf29ad8ea6eef6f49b139f"
    ),
    "src/indusbench/v3dev/contracts.py": (
        "e755e50aaccbe8ce1a961aed247ddf5e1530092b44336c03f38cb4630c1f7ba8"
    ),
    "src/indusbench/v3dev/folds.py": (
        "f075064531ee9fd155dbdb453b95b29e0bf83b45522a798711281a68c6e62b94"
    ),
    "src/indusbench/v3dev/metrics.py": (
        "46d2ad89786140156082771f9d6cf3c97d9ca13c051cc4de95825f45fac36623"
    ),
    "src/indusbench/v3dev/mtaac_training.py": (
        "d5ba5701644208e47daa56d57e286d887ed0da1789b0f91b1f3f4f1688ec6323"
    ),
    "src/indusbench/v3dev/plan.py": (
        "f92cbde4ed6b8c60b05975f3cb1388790039b6968a3c0d569ee766c53415ff91"
    ),
    "src/indusbench/v3dev/runner.py": (
        "913a4fad4552af661ef5852f09e878315d5465a2d87b4f8deaff7feb13d0bbbe"
    ),
    "src/indusbench/v3dev/sequence.py": (
        "5dd663296cc45e068d4d1d7f1b76beed9eb244b1655769269991f01166f40e0d"
    ),
    "src/indusbench/v3dev_cli.py": (
        "78896e060e78df7a9ec28151d1d3aabccacfca60d7d98af8ccadc68cc1e00375"
    ),
    "benchmark/mtaac-v3-development-v1.json": (
        "b2100318fa0e958d741fd25d7b9263ae1574967f4585f4609c118b1bd16880dd"
    ),
    "schemas/mtaac-v3-development-report.schema.json": (
        "c15d1ae1c686fb4827b48610e983340bf44de1a27f4f5474a6ca0d943e11f689"
    ),
    "benchmark/results/mtaac-v3-development-v1.json": (
        "e40d4802906dbe05b19a8625949f8c9154711a28a687c930d3e31cec2bf124d2"
    ),
}


def _module_for_path(path: Path) -> tuple[str, bool]:
    relative = path.relative_to(SOURCE_ROOT)
    parts = list(relative.with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _path_for_module(module: str) -> Path | None:
    if not module.startswith("indusbench"):
        return None
    relative = Path(*module.split("."))
    module_file = SOURCE_ROOT / relative.with_suffix(".py")
    if module_file.is_file():
        return module_file
    package_file = SOURCE_ROOT / relative / "__init__.py"
    return package_file if package_file.is_file() else None


def _resolve_from(module: str, *, is_package: bool, level: int, target: str | None) -> str:
    if level == 0:
        return target or ""
    package_parts = module.split(".") if is_package else module.split(".")[:-1]
    parent_count = level - 1
    if parent_count > len(package_parts):
        return ""
    base_parts = package_parts[: len(package_parts) - parent_count]
    if target:
        base_parts.extend(target.split("."))
    return ".".join(base_parts)


def _imports(path: Path) -> set[str]:
    module, is_package = _module_for_path(path)
    tree = ast.parse(path.read_bytes(), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from(
                module,
                is_package=is_package,
                level=node.level,
                target=node.module,
            )
            if base:
                imported.add(base)
                base_path = _path_for_module(base)
                if base_path is not None and base_path.name == "__init__.py":
                    for alias in node.names:
                        candidate = f"{base}.{alias.name}"
                        if _path_for_module(candidate) is not None:
                            imported.add(candidate)
    return imported


class V4ArchitectureTests(unittest.TestCase):
    def test_static_import_closure_excludes_cli_reserved_source_and_network(self) -> None:
        roots = {
            PACKAGE_ROOT / "v4dev_cli.py",
            *set((PACKAGE_ROOT / "v4dev").glob("*.py")),
        }
        pending = list(roots)
        visited: set[Path] = set()
        all_imports: dict[Path, set[str]] = {}
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            imported = _imports(path)
            all_imports[path] = imported
            for module in imported:
                dependency = _path_for_module(module)
                if dependency is not None and dependency not in visited:
                    pending.append(dependency)

        self.assertIn(PACKAGE_ROOT / "mtaac.py", visited)
        self.assertIn(PACKAGE_ROOT / "mtaac_control.py", visited)
        for path, imported_modules in all_imports.items():
            source = path.read_text(encoding="utf-8").casefold()
            self.assertNotIn("oracc_ed3b", source, path)
            self.assertNotIn("indusbench.cli", source, path)
            for module in imported_modules:
                self.assertFalse(
                    module.startswith(_FORBIDDEN_PACKAGE_PREFIXES),
                    f"{path}: forbidden project import {module}",
                )
                self.assertNotIn(
                    module.split(".", 1)[0],
                    _FORBIDDEN_NETWORK_ROOTS,
                    f"{path}: forbidden network import {module}",
                )

    def test_v4_direct_legacy_imports_are_narrow_and_no_dynamic_import_exists(self) -> None:
        v4_paths = {
            PACKAGE_ROOT / "v4dev_cli.py",
            *set((PACKAGE_ROOT / "v4dev").glob("*.py")),
        }
        for path in v4_paths:
            tree = ast.parse(path.read_bytes(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("indusbench.v3dev") or node.module in {
                        "indusbench.mtaac",
                        "indusbench.mtaac_control",
                    }:
                        self.assertIn(node.module, _ALLOWED_LEGACY_IMPORTS, path)
                    if node.module == "indusbench.v3dev.sequence":
                        self.assertEqual(
                            {"structural_feature_rows"},
                            {alias.name for alias in node.names},
                            path,
                        )
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotEqual("__import__", node.func.id, path)
                    if isinstance(node.func, ast.Attribute):
                        self.assertNotEqual("import_module", node.func.attr, path)

    def test_profile_module_has_no_gold_or_training_contract_dependency(self) -> None:
        path = PACKAGE_ROOT / "v4dev" / "corpus_statistics.py"
        tree = ast.parse(path.read_bytes(), filename=str(path))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(
            {
                "MTAACTrainingDocument",
                "MTAACTrainingLine",
                "MTAACTrainingToken",
                "V3StructuralState",
            }
            & imported_names
        )
        forbidden_attributes = {
            "cluster_identifier",
            "document_key",
            "observed_form_id",
            "state",
            "token_key",
        }
        self.assertFalse(
            {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
            & forbidden_attributes
        )

    def test_prediction_interface_accepts_only_id_free_feature_lines(self) -> None:
        path = PACKAGE_ROOT / "v4dev" / "sequence.py"
        self.assertTrue(path.is_file(), "V4 sequence module must exist before protocol freeze")
        tree = ast.parse(path.read_bytes(), filename=str(path))
        decode_methods = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"decode", "predict"}
        ]
        self.assertTrue(decode_methods)
        for method in decode_methods:
            positional = method.args.posonlyargs + method.args.args
            value_arguments = [argument for argument in positional if argument.arg != "self"]
            self.assertTrue(value_arguments, method.name)
            annotation = value_arguments[0].annotation
            if annotation is None:
                self.fail(f"{method.name} first value argument must be annotated")
            self.assertIn("V4FeatureLine", ast.unparse(annotation), method.name)

    def test_v2_and_v3_immutable_files_match_their_published_hashes(self) -> None:
        for relative_path, expected_sha256 in _IMMUTABLE_SHA256.items():
            with self.subTest(path=relative_path):
                self.assertEqual(
                    expected_sha256,
                    hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest(),
                )

    def test_pyproject_includes_v4_cli_and_frozen_plan(self) -> None:
        value = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            "indusbench.v4dev_cli:main",
            value["project"]["scripts"]["indusbench-v4dev-mtaac"],
        )
        force_include = value["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
        self.assertEqual(
            "indusbench/benchmark/mtaac-v4-development-v1.json",
            force_include["benchmark/mtaac-v4-development-v1.json"],
        )
        self.assertEqual(
            ["src/indusbench"],
            value["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"],
        )


if __name__ == "__main__":
    unittest.main()
