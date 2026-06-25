"""Architecture boundary tests.

These tests parse imports without importing application modules. They are cheap
guardrails for the layered contract documented in ARCHITECTURE.md:

    qt_app -> viewmodels -> services -> domain -> core

Only the Qt application layer may import PySide6.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PACKAGE_ROOT = PROJECT_ROOT / "test_data_analyser"
LAYER_ORDER = {
    "core": 0,
    "domain": 1,
    "services": 2,
    "viewmodels": 3,
    "qt_app": 4,
}


def _python_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def _module_parts(path: Path) -> list[str]:
    relative = path.relative_to(PACKAGE_ROOT).with_suffix("")
    parts = ["test_data_analyser", *relative.parts]
    if parts[-1] == "__init__":
        return parts[:-1]
    return parts


def _module_name(path: Path) -> str:
    return ".".join(_module_parts(path))


def _current_layer(path: Path) -> str | None:
    relative = path.relative_to(PACKAGE_ROOT)
    return relative.parts[0] if relative.parts and relative.parts[0] in LAYER_ORDER else None


def _resolve_import_from(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package_parts = _module_parts(path)
    if path.name != "__init__.py":
        package_parts = package_parts[:-1]
    base_length = max(1, len(package_parts) - node.level + 1)
    parts = package_parts[:base_length]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(_resolve_import_from(path, node))
    return modules


def _package_layer(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "test_data_analyser":
        return None
    return parts[1] if parts[1] in LAYER_ORDER else None


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_pyside6_imports_stay_in_qt_app(self) -> None:
        violations: list[str] = []
        for path in _python_files():
            if _current_layer(path) == "qt_app":
                continue
            for module in _imported_modules(path):
                if module == "PySide6" or module.startswith("PySide6."):
                    violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")

        self.assertEqual(violations, [])

    def test_internal_imports_follow_layer_direction(self) -> None:
        violations: list[str] = []
        for path in _python_files():
            current_layer = _current_layer(path)
            if current_layer is None:
                continue
            current_order = LAYER_ORDER[current_layer]
            for module in _imported_modules(path):
                imported_layer = _package_layer(module)
                if imported_layer is None:
                    continue
                imported_order = LAYER_ORDER[imported_layer]
                if imported_order > current_order:
                    violations.append(
                        f"{_module_name(path)} ({current_layer}) imports {module} ({imported_layer})"
                    )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()