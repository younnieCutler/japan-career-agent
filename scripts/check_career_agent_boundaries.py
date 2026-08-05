#!/usr/bin/env python3
"""Guard Career Agent ownership and dependency direction during the staged extraction."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAREER_ROOT = ROOT / "skills" / "career-agent"
DOMAIN_MODULES = (
    "models",
    "validation",
    "persistence",
    "vault",
    "routing",
    "proposals",
    "lifecycle",
    "projection",
    "private_store",
    "runtime",
)

# The first extraction PRs intentionally leave the not-yet-moved compatibility files in place.
# This allowlist is reduced in the following PRs and must be empty before the architecture phase
# is declared complete. It is explicit so a new runtime dependency cannot hide in the transition.
TRANSITIONAL_RUNTIME_IMPORTERS = set()

PURE_MODULES = {"models", "validation"}
FORBIDDEN_MODULE_IMPORTS = {
    "os",
    "pathlib",
    "tempfile",
    "tomllib",
    "yaml",
    "pipeline_store",
    "self_analysis_profile",
}
OWNED_SYMBOLS = {
    "CareerError": "models",
    "default_state": "models",
    "normalized_state": "models",
    "validate_career_context": "validation",
    "validate_event": "validation",
    "string_list_from": "validation",
    "atomic_write_text": "persistence",
    "atomic_write_bytes": "persistence",
    "resolve_private_home": "private_store",
    "import_document": "private_store",
    "private_doctor": "private_store",
    "CareerVault": "vault",
    "load_routing": "routing",
    "infer_track": "routing",
    "language_for": "routing",
    "stage_for": "routing",
    "flow_phase_for": "routing",
    "run_chat": "proposals",
    "propose_career_context": "proposals",
    "approve": "lifecycle",
    "restore_state": "lifecycle",
    "upsert_pipeline_entry": "projection",
    "apply_event_to_state": "projection",
}


class BoundaryError(RuntimeError):
    """Raised when a staged ownership or import rule is violated."""


def _module_tree(module: str) -> ast.Module:
    return ast.parse((CAREER_ROOT / f"{module}.py").read_text(encoding="utf-8"))


def _root_module(name: str | None) -> str | None:
    return name.split(".", 1)[0] if name else None


def _imports(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(_root_module(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            root = _root_module(node.module)
            if root:
                modules.add(root)
    return {module for module in modules if module}


def _defined_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    } | {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name)
    }


def _is_thin_facade(tree: ast.Module, symbol: str) -> bool:
    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == symbol),
        None,
    )
    if function is None:
        return False
    body = function.body[1:] if ast.get_docstring(function, clean=False) else function.body
    return len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Call)


def _module_level_calls(tree: ast.Module) -> set[str]:
    calls: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
    return calls


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            cycles.append(visiting[visiting.index(node) :] + [node])
            return
        if node in visited:
            return
        visiting.append(node)
        for child in sorted(graph.get(node, set())):
            visit(child)
        visiting.pop()
        visited.add(node)

    for module in sorted(graph):
        visit(module)
    return cycles


def validate() -> list[str]:
    errors: list[str] = []
    trees = {module: _module_tree(module) for module in DOMAIN_MODULES}
    imports = {module: _imports(tree) for module, tree in trees.items()}

    for module in DOMAIN_MODULES:
        if "career_agent" in imports[module]:
            errors.append(f"{module}.py must not import career_agent.py")
        if "runtime" in imports[module] and module not in TRANSITIONAL_RUNTIME_IMPORTERS and module != "runtime":
            errors.append(f"{module}.py imports runtime.py outside the transitional allowlist")

    for module in PURE_MODULES:
        forbidden = sorted(imports[module] & FORBIDDEN_MODULE_IMPORTS)
        if forbidden:
            errors.append(f"{module}.py is a pure contract module but imports: {', '.join(forbidden)}")
        calls = _module_level_calls(trees[module])
        if calls & {"open", "read_text", "write_text", "safe_load"}:
            errors.append(f"{module}.py has module-level I/O-like calls: {sorted(calls)}")

    for symbol, owner in OWNED_SYMBOLS.items():
        for module, tree in trees.items():
            if module != owner and symbol in _defined_names(tree) and not (
                module == "runtime" and _is_thin_facade(tree, symbol)
            ):
                errors.append(f"{symbol} is defined in {module}.py; owner is {owner}.py")

    graph = {
        module: {child for child in imports[module] if child in DOMAIN_MODULES}
        for module in DOMAIN_MODULES
    }
    for cycle in _find_cycles(graph):
        errors.append(f"circular Career Agent import: {' -> '.join(cycle)}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("career-agent architecture boundary: FAILED", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    remaining = sorted(TRANSITIONAL_RUNTIME_IMPORTERS)
    if remaining:
        print(
            "career-agent architecture boundary: TRANSITIONAL PASS "
            f"(remaining runtime facade importers: {', '.join(remaining)})"
        )
    else:
        print("career-agent architecture boundary: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
