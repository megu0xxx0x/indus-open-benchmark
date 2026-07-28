from __future__ import annotations

import ast
import hashlib
import json
import tomllib
import unittest
from pathlib import Path

import indusbench.v5dev_cli as v5_cli

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src/indusbench"

_IMMUTABLE_V4_SHA256 = {
    "benchmark/mtaac-v4-development-v1.json": (
        "604725a5929b63f578ade07b65ca784eefefefce9b827e1686d4836f668c123b"
    ),
    "benchmark/results/mtaac-v4-development-v1.json": (
        "4772993941494e19775fe88acec144a008bebd63258afdf2f84f8b9a3f4af897"
    ),
    "schemas/mtaac-v4-development-report.schema.json": (
        "0afeaa3609ef5d09820acbe3a3127697d9c7ff97fde4e99b6ba631a17a8ef2c1"
    ),
    "src/indusbench/v4dev/__init__.py": (
        "2eb143efd692fab35549123c66b4fd27d94553dfd2e129373657bd6833eb38fb"
    ),
    "src/indusbench/v4dev/contracts.py": (
        "90b5b300c636a4628d7c1551eb61589dcae5794e3597bd18495de0dd541077c9"
    ),
    "src/indusbench/v4dev/corpus_statistics.py": (
        "78bb68f064a7c08596287fd8e28d80fb2f93085c5e4a34da419627e7eeb7ecb3"
    ),
    "src/indusbench/v4dev/plan.py": (
        "e1841779bf251f1019ad679a28713e787f8539959515038009f6e476b1eb3a8c"
    ),
    "src/indusbench/v4dev/runner.py": (
        "cd95048b14204da3124340591c83da97f362eee19b22702b412b396687ecaf16"
    ),
    "src/indusbench/v4dev/sequence.py": (
        "cc0836f92025d0ac8a5ccc61c3682eee2ad035aea4917ea5467f6709fee1d251"
    ),
    "src/indusbench/v4dev_cli.py": (
        "0d7bf95074444755706592f0a0c031999d75c72210a79e42898c0b8640b754f1"
    ),
}


class V5ArchitectureTests(unittest.TestCase):
    def test_v4_parent_code_plan_schema_and_result_are_immutable(self) -> None:
        for relative, expected in _IMMUTABLE_V4_SHA256.items():
            with self.subTest(relative=relative):
                self.assertEqual(
                    hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                    expected,
                )

    def test_pyproject_packages_the_exact_v5_command_and_plan(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            pyproject["project"]["scripts"]["indusbench-v5dev-mtaac"],
            "indusbench.v5dev_cli:main",
        )
        force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
        self.assertEqual(
            force_include["benchmark/mtaac-v5-development-v1.json"],
            "indusbench/benchmark/mtaac-v5-development-v1.json",
        )
        self.assertEqual(force_include["schemas"], "indusbench/schemas")

    def test_runtime_fold_support_constants_come_from_the_immutable_v4_result(
        self,
    ) -> None:
        result = json.loads((ROOT / "benchmark/results/mtaac-v4-development-v1.json").read_bytes())
        supports = [fold["support"] for fold in result["outer_development"]["outer_folds"]]
        self.assertEqual(
            tuple(support["train_family_count"] for support in supports),
            v5_cli._EXPECTED_TRAIN_FAMILY_COUNTS,
        )
        self.assertEqual(
            tuple(support["validation_family_count"] for support in supports),
            v5_cli._EXPECTED_VALIDATION_FAMILY_COUNTS,
        )

    def test_v5_static_import_closure_excludes_network_and_reserved_source(self) -> None:
        v5_paths = {
            PACKAGE_ROOT / "v5dev_cli.py",
            *set((PACKAGE_ROOT / "v5dev").glob("*.py")),
        }
        forbidden_prefixes = (
            "ftplib",
            "http",
            "indusbench.oracc",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        )
        for source in v5_paths:
            tree = ast.parse(source.read_bytes(), filename=str(source))
            for node in ast.walk(tree):
                imported: tuple[str, ...] = ()
                if isinstance(node, ast.Import):
                    imported = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = (node.module,)
                for module in imported:
                    self.assertFalse(
                        module.startswith(forbidden_prefixes),
                        (source, module),
                    )
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotEqual(node.func.id, "__import__", source)
                    elif isinstance(node.func, ast.Attribute):
                        self.assertNotEqual(node.func.attr, "import_module", source)

    def test_runner_cannot_fit_a_v4_model_or_diagnostic(self) -> None:
        source = (PACKAGE_ROOT / "v5dev/runner.py").read_text(encoding="utf-8")
        for forbidden in (
            "V4LinearChainCRF",
            "V4LogisticEmissionModel",
            "no_corpus_profile",
            "self_inclusive_target_profile",
            "strict_single_family_profile",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("V5GroupContrastLinearChainCRF.fit", source)


if __name__ == "__main__":
    unittest.main()
