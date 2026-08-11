#!/usr/bin/env python3
"""Assemble, check and render one target's document from already-confirmed evidence.

A generated document is a projection, not a source of truth: nothing in this module appends to
the ledger. `render_document` refuses a draft that has not passed the fidelity gate, because a
rendered file is the artefact a user sends to an employer.
"""

from __future__ import annotations

import hashlib
import json
import sys

from pathlib import Path
from typing import Any

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from document import document_model, fidelity_gate  # noqa: E402
from models import CareerError, UNTRUSTED_DATA_MARKER  # noqa: E402
from persistence import atomic_write_text, read_json, read_jsonl, write_json  # noqa: E402
from projection import pipeline_file  # noqa: E402
from render import (  # noqa: E402
    manifest,
    outdated_reasons,
    render,
    RENDERER_VERSION,
    resolve_template,
)
from vault import CareerVault, utc_now  # noqa: E402


def _canonical_revision(home: CareerVault) -> str:
    """The digest of the confirmed record a document was built from.

    Recorded on every generated file so that "is this still current?" has an answer that does not
    depend on remembering. Generating a document never changes it: this is what makes "a document
    is a projection, not a source" checkable rather than merely stated.
    """
    return hashlib.sha256(home.events.read_bytes()).hexdigest() if home.events.exists() else ""


def _pipeline_company(workspace: str | Path | None, slug: str) -> dict[str, Any]:
    path = pipeline_file(workspace)
    try:
        data = pipeline_store.load(path)
    except ImportError as exc:  # pragma: no cover - pyyaml is a documented requirement
        raise CareerError("pyyaml is required to read the workspace pipeline") from exc
    for entry in data.get("companies") or []:
        if entry.get("slug") == slug:
            return entry
    raise CareerError(
        f"no company '{slug}' in {path}; add it with scripts/pipeline.py upsert first",
        code="COMPANY_NOT_FOUND",
    )


def build_document_model(
    home: CareerVault,
    slug: str,
    *,
    workspace: str | Path | None = None,
    document_type: str = "shokumukeirekisho",
) -> dict[str, Any]:
    """Arrange confirmed evidence for one target. Reads the ledger; writes nothing to it."""
    model = document_model(
        read_jsonl(home.events),
        _pipeline_company(workspace, slug),
        document_type=document_type,
        canonical_revision=_canonical_revision(home),
    )
    model["vault"] = str(home.path)
    model["data_trust"] = UNTRUSTED_DATA_MARKER
    model["instruction_authority"] = "none"
    return model


def _read_document_file(path: str | Path, label: str) -> dict[str, Any]:
    """Read a caller-supplied JSON document, refusing an absent one.

    `read_json` returns a default when the file is missing, which is right for a cache and wrong
    here: a mistyped draft path would become an empty draft, and an empty draft passes every check
    in the gate. A missing input is an error, not an empty one.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise CareerError(f"{label} not found: {resolved}", code="DOCUMENT_INPUT_NOT_FOUND")
    value = read_json(resolved, None)
    if not isinstance(value, dict):
        raise CareerError(f"{label} must be a JSON object: {resolved}", code="DOCUMENT_INPUT_INVALID")
    return value


def check_document(
    model_path: str | Path, draft_path: str | Path, humanized_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the fidelity gate over a written draft, or over its polished replacement."""
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
    template: str,
    out_dir: str | Path,
    humanized_path: str | Path | None = None,
) -> dict[str, Any]:
    """Render a checked document, and refuse to render an unchecked one.

    The gate runs here rather than being trusted to have run earlier, because the failure mode this
    guards against is a document that reaches a recruiter, and "the caller was supposed to check"
    is not a guarantee. On failure nothing is written at all.

    The filename carries a digest of what produced it, so regenerating after new evidence or a
    changed JD writes a new file beside the old one instead of overwriting something the user may
    already have sent.
    """
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
    template_path = resolve_template(Path(__file__).resolve().parent, template)
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
    # The same instant the manifest records, so the filename and `generated_at` cannot disagree.
    generated_at = utc_now()
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
        reasons = outdated_reasons(read_json(existing, {}), model, template)
        if reasons:
            outdated.append({"manifest": str(existing), "reasons": reasons})
    if not unchanged:
        atomic_write_text(document_path, output)
        write_json(manifest_path, record)
    return {
        "mode": "document-render",
        "template": template,
        "output_path": str(document_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        # Regenerating with the same evidence, JD, template and wording produces the same file.
        "unchanged": unchanged,
        # Reported, never acted on. Overwriting a document the user may have already sent is not a
        # decision this runtime makes.
        "outdated_documents": outdated,
        "gate": {"pass": True, "checked_slots": gate["checked_slots"]},
        "print_to_pdf": "open the HTML and print to PDF; the template carries A4 print CSS",
        "ok": True,
    }
