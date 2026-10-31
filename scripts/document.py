#!/usr/bin/env python3
"""Deterministic document model, fidelity gate, and HTML rendering CLI.

Reads user-confirmed evidence from `./data/evidence.yml` (or JSON/JSONL) and target company
metadata from `./data/pipeline.yml`. Never modifies evidence or pipeline files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHARED_ROOT = ROOT / "_shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

import pipeline_store  # noqa: E402
from document import (  # noqa: E402
    CareerError,
    confirmed_evidence_events,
    document_model,
    fidelity_gate,
    normalize_evidence_records,
)
from render import (  # noqa: E402
    DEFAULT_TEMPLATE_ROOT,
    RENDERER_VERSION,
    manifest,
    outdated_reasons,
    render,
    resolve_template,
)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_document_file(path: str | Path, label: str) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.is_file():
        raise CareerError(f"{label} not found: {resolved}", code="DOCUMENT_INPUT_NOT_FOUND")
    value = _read_json(resolved, None)
    if not isinstance(value, dict):
        raise CareerError(f"{label} must be a JSON object: {resolved}", code="DOCUMENT_INPUT_INVALID")
    return value


def _load_evidence(path: Path) -> tuple[list[dict[str, Any]] | dict[str, Any], str]:
    if not path.is_file():
        return [], ""
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        return rows, digest
    if path.suffix.lower() == ".json":
        return json.loads(text) or {}, digest
    return yaml.safe_load(text) or {}, digest


def _pipeline_company(workspace: str | Path | None, slug: str) -> dict[str, Any]:
    path = pipeline_store.resolve_pipeline_path(workspace)
    data = pipeline_store.load(path)
    for entry in data.get("companies") or []:
        if entry.get("slug") == slug:
            return entry
    raise CareerError(
        f"no company '{slug}' in {path}; add it with scripts/pipeline.py upsert first",
        code="COMPANY_NOT_FOUND",
    )


def build_document_model(
    slug: str,
    *,
    workspace: str | Path | None = None,
    evidence_path: str | Path | None = None,
    document_type: str = "shokumukeirekisho",
) -> dict[str, Any]:
    ws = pipeline_store.resolve_workspace(workspace)
    ev_file = Path(evidence_path) if evidence_path else (ws / "data" / "evidence.yml")
    records, revision = _load_evidence(ev_file)
    company = dict(_pipeline_company(ws, slug))
    if not company.get("primary_experience_ids") and not company.get("supporting_experience_ids"):
        normalized = normalize_evidence_records(records)
        company["primary_experience_ids"] = [
            str(ev["id"]) for ev in confirmed_evidence_events(normalized) if ev.get("id")
        ]
    model = document_model(
        records,
        company,
        document_type=document_type,
        canonical_revision=revision,
    )
    model["evidence_file"] = str(ev_file)
    model["data_trust"] = "untrusted_career_data"
    model["instruction_authority"] = "none"
    return model


def check_document(
    model_path: str | Path, draft_path: str | Path, humanized_path: str | Path | None = None,
) -> dict[str, Any]:
    model = _read_document_file(model_path, "--model")
    draft = _read_document_file(draft_path, "--draft")
    humanized = _read_document_file(humanized_path, "--humanized") if humanized_path else None
    result = fidelity_gate(model, draft, humanized=humanized)
    result["model"] = str(model_path)
    return result


def render_document(
    model_path: str | Path,
    draft_path: str | Path,
    *,
    template: str = "standard-chuto",
    out_dir: str | Path = "./career-docs",
    humanized_path: str | Path | None = None,
) -> dict[str, Any]:
    model = _read_document_file(model_path, "--model")
    draft = _read_document_file(draft_path, "--draft")
    humanized = _read_document_file(humanized_path, "--humanized") if humanized_path else None
    gate = fidelity_gate(model, draft, humanized=humanized)
    if not gate["pass"]:
        raise CareerError(
            f"fidelity gate failed with {len(gate['violations'])} violation(s); nothing was written",
            code="FIDELITY_GATE_FAILED",
            details={"violations": gate["violations"]},
        )
    source = humanized or draft
    slots = source.get("slots") or {}
    template_path = resolve_template(DEFAULT_TEMPLATE_ROOT, template)
    output = render(model, slots, template_path.read_text(encoding="utf-8"), skills=source.get("skills"))
    target = model.get("target") or {}
    fingerprint = hashlib.sha256(
        "\0".join(
            [
                str(model.get("canonical_revision") or ""),
                str(target.get("jd_digest") or ""),
                template,
                RENDERER_VERSION,
                json.dumps(slots, ensure_ascii=False, sort_keys=True),
                json.dumps(source.get("skills"), ensure_ascii=False, sort_keys=True),
            ]
        ).encode("utf-8")
    ).hexdigest()[:8]
    slug = str(target.get("slug") or "target")
    directory = Path(out_dir) / slug
    directory.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now()
    name = f"{model.get('document_type')}-{generated_at[:10].replace('-', '')}-{fingerprint}"
    document_path = directory / f"{name}.html"
    manifest_path = directory / f"{name}.manifest.json"
    unchanged = document_path.exists() and document_path.read_text(encoding="utf-8") == output
    record = manifest(
        model,
        document_id=f"doc-{fingerprint}",
        template_id=template,
        output_path=str(document_path.resolve()),
        generated_at=generated_at,
    )
    outdated: list[dict[str, Any]] = []
    for existing in sorted(directory.glob("*.manifest.json")):
        if existing == manifest_path:
            continue
        reasons = outdated_reasons(_read_json(existing, {}), model, template)
        if reasons:
            outdated.append({"manifest": str(existing), "reasons": reasons})
    if not unchanged:
        _atomic_write_text(document_path, output)
        _atomic_write_text(manifest_path, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return {
        "mode": "document-render",
        "template": template,
        "output_path": str(document_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "unchanged": unchanged,
        "outdated_documents": outdated,
        "gate": {"pass": True, "checked_slots": gate["checked_slots"]},
        "print_to_pdf": "open the HTML and print to PDF; the template carries A4 print CSS",
        "ok": True,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("model", "document-model"):
        p_model = sub.add_parser(name, help="build a JD-specific document model from confirmed evidence")
        p_model.add_argument("slug", help="target company slug in data/pipeline.yml")
        p_model.add_argument("--workspace", help="workspace directory")
        p_model.add_argument("--evidence", help="path to confirmed evidence file (default: data/evidence.yml)")
        p_model.add_argument("--type", dest="document_type", default="shokumukeirekisho")
        p_model.add_argument("--format", choices=("json", "text"), default="json")

    for name in ("check", "document-check"):
        p_check = sub.add_parser(name, help="run the deterministic fidelity gate on a draft")
        p_check.add_argument("--model", required=True)
        p_check.add_argument("--draft", required=True)
        p_check.add_argument("--humanized")
        p_check.add_argument("--format", choices=("json", "text"), default="json")

    for name in ("render", "document-render"):
        p_render = sub.add_parser(name, help="render a checked document into HTML")
        p_render.add_argument("--model", required=True)
        p_render.add_argument("--draft", required=True)
        p_render.add_argument("--humanized")
        p_render.add_argument("--template", default="standard-chuto")
        p_render.add_argument("--out", default="./career-docs")
        p_render.add_argument("--format", choices=("json", "text"), default="json")

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = _build_parser().parse_args(argv)
    try:
        if args.command in {"model", "document-model"}:
            result = build_document_model(
                args.slug,
                workspace=args.workspace,
                evidence_path=args.evidence,
                document_type=args.document_type,
            )
        elif args.command in {"check", "document-check"}:
            result = check_document(args.model, args.draft, args.humanized)
        else:
            result = render_document(
                args.model,
                args.draft,
                template=args.template,
                out_dir=args.out,
                humanized_path=args.humanized,
            )
    except CareerError as exc:
        payload = {
            "ok": False,
            "error": str(exc),
            "error_code": exc.code or "DOCUMENT_ERROR",
            "retryable": exc.retryable,
            "details": exc.details,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
