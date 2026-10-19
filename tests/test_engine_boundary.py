"""Guard the dependency rule: app/engine never imports web or feature code."""

import ast
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1] / "app" / "engine"
FORBIDDEN_ROOTS = {"fastapi", "starlette", "uvicorn", "pydantic", "flask"}
ALLOWED_APP_PREFIX = "app.engine"


def imported_modules(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module


def test_engine_imports_only_stdlib_and_engine():
    violations = []
    for path in sorted(ENGINE_DIR.rglob("*.py")):
        for lineno, module in imported_modules(path):
            root = module.split(".")[0]
            forbidden = root in FORBIDDEN_ROOTS or (
                root == "app" and not module.startswith(ALLOWED_APP_PREFIX)
            )
            if forbidden:
                violations.append(f"{path.name}:{lineno} imports {module}")
    assert not violations, "engine boundary violated:\n" + "\n".join(violations)