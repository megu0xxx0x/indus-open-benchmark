from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "indusbench"

_FORBIDDEN_PACKAGE_PREFIXES = (
    "indusbench.cli",
    "indusbench.oracc_ed3b",
)
_FORBIDDEN_NETWORK_ROOTS = frozenset(
    {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "urllib3",
    }
)


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


class V3ArchitectureTests(unittest.TestCase):
    def test_static_import_closure_excludes_main_cli_oracc_and_network_clients(self) -> None:
        roots = {
            PACKAGE_ROOT / "v3dev_cli.py",
            *set((PACKAGE_ROOT / "v3dev").glob("*.py")),
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


if __name__ == "__main__":
    unittest.main()
