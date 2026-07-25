from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src" / "lss_erp_mcp"
BANNED = ("backend", "sqlalchemy", "pg8000")


def test_mcp_source_has_no_backend_or_database_imports() -> None:
    assert SRC.is_dir(), f"MCP source package is missing: {SRC}"

    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(
                    name == prefix or name.startswith(f"{prefix}.")
                    for prefix in BANNED
                ):
                    violations.append(f"{path.relative_to(SRC)}:{node.lineno}:{name}")
    assert violations == []
