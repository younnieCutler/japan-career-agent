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
    "document",
    "personal_timeline",
    "private_store",
    "guided",
    "localization",
    "ux",
    # Application layer: one owner per group of commands, all of them below the CLI and above the
    # domain. They may call each other sideways, but never upwards into the parser or the facade.
    "diagnostics",
    "onboarding",
    "ingest",
    "experiences",
    "documents",
    "views",
    "approvals",
    "guided_flow",
    "sessions",
    "self_analysis",
    "dispatch",
    "command_line",
    "runtime",
    # GUI modules are included in the graph so a new cross-layer import cannot hide in a
    # subpackage the original flat-module checker never visited.
    "gui.server",
    "gui.security",
    "gui.templates",
    "gui.views_read",
    "gui.tanaoroshi",
)

# The first extraction PRs intentionally leave the not-yet-moved compatibility files in place.
# This allowlist is reduced in the following PRs and must be empty before the architecture phase
# is declared complete. It is explicit so a new runtime dependency cannot hide in the transition.
TRANSITIONAL_RUNTIME_IMPORTERS = set()

# `runtime.py` re-exports and delegates; it implements nothing. Checking for definitions rather
# than for size is deliberate: a line-count budget is satisfied by reformatting, while this fails
# the moment a command's behaviour starts living in the facade again.
FACADE_MODULE = "runtime"
# The parser and the dispatcher sit above every owner. An owner reaching back up to either one
# would mean a command could only be understood by reading the CLI, which is what the split was
# for. `runtime` is exempt because re-exporting them is its entire job.
CLI_MODULES = {"command_line", "dispatch"}
APPLICATION_MODULES = {
    "diagnostics", "onboarding", "ingest", "experiences",
    "documents", "views", "approvals", "guided_flow",
    "sessions", "self_analysis",
    "gui.templates", "gui.views_read", "gui.tanaoroshi",
}
GUI_MODULES = {"gui.server", "gui.security", "gui.templates", "gui.views_read", "gui.tanaoroshi"}
# The dispatcher is the sole entrypoint bridge that starts the GUI. GUI modules never import it.
GUI_LAUNCH_IMPORTS = {("dispatch", "gui.server")}
# The only places an owned symbol may be re-declared, and then only as a single delegating call.
# `approvals.approve` injects the pipeline writer and the state projector into `lifecycle.approve`;
# the approval rules stay in `lifecycle`. Listing the pair explicitly keeps this from becoming a
# general "a one-line wrapper may live anywhere" loophole.
THIN_FACADES = {("approvals", "approve")}

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
    "document_model": "document",
    "fidelity_gate": "document",
    "CareerError": "models",
    "default_state": "models",
    "normalized_state": "models",
    "job_search_of": "models",
    "employment_status_of": "models",
    "validate_career_context": "validation",
    "validate_event": "validation",
    "string_list_from": "validation",
    "iso_date": "validation",
    "validate_fact": "validation",
    "validate_work_event": "validation",
    "claim_surface": "validation",
    "derive_intervals": "personal_timeline",
    "project": "personal_timeline",
    "timeline": "personal_timeline",
    "document_states": "personal_timeline",
    "select_personal_context": "personal_timeline",
    "historical_comparison": "personal_timeline",
    "candidate_profile_values": "personal_timeline",
    "atomic_write_text": "persistence",
    "atomic_write_bytes": "persistence",
    "resolve_private_home": "private_store",
    "import_document": "private_store",
    "private_doctor": "private_store",
    "resolve_document": "private_store",
    "stray_documents": "private_store",
    "CareerVault": "vault",
    "load_routing": "routing",
    "infer_track": "routing",
    "language_for": "routing",
    "stage_for": "routing",
    "flow_phase_for": "routing",
    "maintenance_intent": "routing",
    "opportunity_review_intent": "routing",
    "active_search_intent": "routing",
    "transition_intent": "routing",
    "review_closed_intent": "routing",
    "run_chat": "proposals",
    "stated_career_mode": "proposals",
    "propose_career_context": "proposals",
    "propose_fact": "proposals",
    "approve": "lifecycle",
    "review_work_event": "lifecycle",
    "preflight_confirmation": "lifecycle",
    "restore_state": "lifecycle",
    "upsert_pipeline_entry": "projection",
    "apply_event_to_state": "projection",
    "next_career_mode": "projection",
    "clamp_career_mode": "projection",
    "projects_from_events": "projection",
    "project_timeline": "projection",
    "work_event_project_ids": "projection",
    "work_event_date": "projection",
    "make_project_event": "proposals",
    "validate_project": "validation",
    "month_or_day": "validation",
    "doctor": "diagnostics",
    "setup": "onboarding",
    "set_profile_axis": "onboarding",
    "complete_onboarding": "onboarding",
    "run_heartbeat": "ingest",
    "run_discover": "ingest",
    "run_index": "ingest",
    "normalize_posting": "ingest",
    "add_project": "experiences",
    "add_context": "experiences",
    "list_experiences": "experiences",
    "link_work_event": "experiences",
    "work_events": "experiences",
    "run_context": "experiences",
    "build_document_model": "documents",
    "check_document": "documents",
    "render_document": "documents",
    "readiness": "views",
    "evidence_pool": "views",
    "maintenance_check": "views",
    "weekly_review": "views",
    "status": "views",
    "workspace_summary": "views",
    "recover_approval": "approvals",
    "run_guided": "guided_flow",
    "transient_root": "sessions",
    "storage_paths": "sessions",
    "storage_lifetime": "sessions",
    "session_path": "sessions",
    "draft_path": "sessions",
    "register_session_migration": "sessions",
    "create_session": "sessions",
    "load_session": "sessions",
    "missing_fields": "sessions",
    "field_status": "sessions",
    "save_draft": "sessions",
    "resume_session": "sessions",
    "checkpoint_session": "sessions",
    "create_proposal": "sessions",
    "approve_proposal": "sessions",
    "SESSION_SCHEMA_VERSION": "sessions",
    "run_command": "dispatch",
    "run_private_command": "dispatch",
    "build_parser": "command_line",
    "main": "command_line",
}


class BoundaryError(RuntimeError):
    """Raised when a staged ownership or import rule is violated."""


def _module_tree(module: str) -> ast.Module:
    path = CAREER_ROOT.joinpath(*module.split("."))
    source = path.with_suffix(".py") if path.with_suffix(".py").is_file() else path / "__init__.py"
    return ast.parse(source.read_text(encoding="utf-8"))


def _root_module(name: str | None) -> str | None:
    return name.split(".", 1)[0] if name else None


def _import_name(name: str | None) -> str | None:
    if not name:
        return None
    if name.startswith(("gui.", "http.", "urllib.")):
        return name
    return _root_module(name)


def _imports(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(_import_name(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported = _import_name(node.module)
            if imported:
                modules.add(imported)
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
                (module, symbol) in THIN_FACADES and _is_thin_facade(tree, symbol)
            ):
                errors.append(f"{symbol} is defined in {module}.py; owner is {owner}.py")

    facade = trees[FACADE_MODULE]
    defined = [
        node.name
        for node in facade.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if defined:
        errors.append(
            f"{FACADE_MODULE}.py must only re-export, but defines: {', '.join(sorted(defined))}"
        )

    for module in sorted(APPLICATION_MODULES):
        reaching_up = sorted(imports[module] & CLI_MODULES)
        if reaching_up:
            errors.append(f"{module}.py imports the CLI layer: {', '.join(reaching_up)}")

    for module in sorted(GUI_MODULES):
        reaching_up = sorted(imports[module] & CLI_MODULES)
        if reaching_up:
            errors.append(f"{module}.py imports the CLI layer: {', '.join(reaching_up)}")
        forbidden = sorted(
            imported
            for imported in imports[module]
            if imported in {"socket", "subprocess", "http.client"}
            or imported == "urllib"
            or imported.startswith("urllib.")
        )
        if forbidden:
            errors.append(f"{module}.py imports forbidden GUI transport modules: {', '.join(forbidden)}")
        if "webbrowser" in imports[module] and module != "gui.server":
            errors.append(f"webbrowser is only allowed in gui.server.py, found in {module}.py")
        if module != "gui.templates":
            direct_domain = sorted(
                imported
                for imported in imports[module]
                if imported in DOMAIN_MODULES
                and imported not in GUI_MODULES
                and imported not in APPLICATION_MODULES
            )
            if direct_domain:
                errors.append(f"{module}.py imports domain modules directly: {', '.join(direct_domain)}")

    for module in (module for module in DOMAIN_MODULES if module not in GUI_MODULES):
        gui_imports = imports[module] & GUI_MODULES
        disallowed = sorted(
            (module, imported)
            for imported in gui_imports
            if (module, imported) not in GUI_LAUNCH_IMPORTS
        )
        if disallowed:
            errors.append(
                "only dispatch may launch the GUI; disallowed imports: "
                + ", ".join(f"{owner} -> {child}" for owner, child in disallowed)
            )

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
