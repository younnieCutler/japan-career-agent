"""Deterministic HTML rendering for a document model, with no dependency and no logic in templates.

A template decides where things appear. It never decides what they say — that was settled by the
document model and checked by the fidelity gate before anything reached here. So the substitution
engine below is deliberately incapable of more: named slots, repeated blocks, and nothing else. No
expressions, no conditionals, no includes, no evaluation of any kind.

That is a security property, not an aesthetic one. A template is a file the user brought from
somewhere, and templates carry sample career text, macros, and occasionally text addressed to a
model. None of it can execute here, and every value substituted in is HTML-escaped, so neither the
template nor a JD nor a resume can become markup.

PDF is the browser's print path against the print CSS in the built-in templates. A PDF library
would be a dependency, two hash-pinned lock entries and an SBOM regeneration to reproduce what
Ctrl+P already does correctly.
"""

from __future__ import annotations

import html
import re
from typing import Any

from models import CareerError

RENDERER_VERSION = "1"

TEMPLATE_DIRNAME = "templates"
# `{{#name}} ... {{/name}}` repeats its body once per item. Non-greedy and non-nested on purpose:
# one level of repetition is what a 職務経歴書 needs, and a general nesting engine is a language.
BLOCK = re.compile(r"\{\{#([a-z_]+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
SLOT = re.compile(r"\{\{([a-z_]+)\}\}")
# What a template file may be called. A `.docm` is macro-enabled and is refused by name rather than
# by inspection, because deciding per file whether a macro is harmless is not a decision to make.
SUPPORTED_SUFFIXES = {".html"}
REFUSED_SUFFIXES = {".docm", ".xlsm", ".pptm"}


def _escape(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return html.escape(str(value), quote=True)


def _fill(template: str, scope: dict[str, Any]) -> str:
    """One pass of block expansion followed by slot substitution.

    Blocks are expanded before slots so a repeated body sees its own item's values; slots left
    unresolved become empty rather than raising, because an empty section in a document is a
    section the user has no evidence for, which is a normal and honest outcome.
    """

    def expand(match: re.Match[str]) -> str:
        name, body = match.group(1), match.group(2)
        items = scope.get(name)
        if not isinstance(items, list):
            return ""
        return "".join(_fill(body, {**scope, **item} if isinstance(item, dict) else {name: item})
                       for item in items)

    expanded = BLOCK.sub(expand, template)
    return SLOT.sub(lambda match: _escape(scope.get(match.group(1))), expanded)


def _sections(
    model: dict[str, Any], slots: dict[str, Any], skills: list[str] | None = None,
) -> dict[str, Any]:
    """The model and the written text, flattened into what a template addresses.

    The template never sees an evidence id or a protected claim. It sees a heading and the lines
    under it, which is all a layout has any business knowing.
    """
    by_slot = {entry["slot"]: entry for entry in model.get("entries", [])}
    history = []
    for block in model.get("employment_history", []):
        period = block.get("period") or {}
        entries = []
        for slot in block.get("entries", []):
            text = str(slots.get(slot) or "").strip()
            if not text:
                continue
            entries.append(
                {
                    "heading": by_slot.get(slot, {}).get("heading") or "",
                    "lines": [{"line": line} for line in text.splitlines() if line.strip()],
                }
            )
        if not entries:
            continue
        history.append(
            {
                "company": block.get("label") or "",
                "period": " – ".join(
                    part for part in (period.get("from") or "", period.get("to") or "") if part
                ) or "",
                "experiences": entries,
            }
        )
    target = model.get("target") or {}
    return {
        "document_type": model.get("document_type"),
        "target_company": target.get("company") or "",
        "target_role": target.get("role") or "",
        "career_summary": str(slots.get("section:summary") or "").strip(),
        "self_pr": str(slots.get("section:self_pr") or "").strip(),
        # The model proposes; the draft may have narrowed. It can only ever be a subset -- the
        # gate refuses a label that was not proposed -- so this cannot introduce a skill.
        "skills": [
            {"skill": label}
            for label in (
                skills if skills is not None else [item["label"] for item in model.get("skills", [])]
            )
        ],
        "employment_history": history,
        "unknowns": [{"unknown": item} for item in model.get("unknowns", [])],
    }


def available_templates(root) -> list[str]:
    directory = root / TEMPLATE_DIRNAME
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.iterdir() if path.suffix in SUPPORTED_SUFFIXES)


def resolve_template(root, template_id: str):
    """The template file for an id, refusing anything that could execute or escape the directory."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", template_id or ""):
        raise CareerError(
            "template id must be lowercase letters, digits and dashes", code="TEMPLATE_NOT_FOUND"
        )
    path = (root / TEMPLATE_DIRNAME / f"{template_id}.html").resolve()
    directory = (root / TEMPLATE_DIRNAME).resolve()
    # Redundant while the pattern above admits no separator, and kept anyway: it is the check that
    # still holds if that pattern is ever widened — to allow an uppercase id, say, or a
    # subdirectory. Deleting it would make a one-character change to a regex into a traversal.
    if directory not in path.parents:
        raise CareerError("template path escapes the template directory", code="TEMPLATE_NOT_FOUND")
    if path.suffix in REFUSED_SUFFIXES:
        raise CareerError("macro-enabled templates are not rendered", code="TEMPLATE_UNSUPPORTED")
    if not path.is_file():
        known = ", ".join(available_templates(root)) or "none"
        raise CareerError(
            f"unknown template: {template_id}; built-in templates are: {known}",
            code="TEMPLATE_NOT_FOUND",
        )
    return path


def render(
    model: dict[str, Any],
    slots: dict[str, Any],
    template_text: str,
    *,
    skills: list[str] | None = None,
) -> str:
    """Fill a template with a checked document. Content is decided before this is called."""
    return _fill(template_text, _sections(model, slots, skills))


def manifest(
    model: dict[str, Any],
    *,
    document_id: str,
    template_id: str,
    output_path: str,
    generated_at: str,
) -> dict[str, Any]:
    """What this file was made from, so it can be audited and reproduced.

    `canonical_revision` and `jd_digest` are the two that matter later: when either changes, the
    file on disk is a candidate for regeneration, and saying so is more useful than overwriting it.
    """
    target = model.get("target") or {}
    return {
        "document_id": document_id,
        "document_type": model.get("document_type"),
        "generated_at": generated_at,
        "target_company": target.get("company"),
        "target_role": target.get("role"),
        "jd_source": target.get("jd_source"),
        "jd_digest": target.get("jd_digest"),
        "canonical_revision": model.get("canonical_revision"),
        "primary_evidence_ids": [e["evidence_id"] for e in model.get("entries", []) if e.get("lead")],
        "supporting_evidence_ids": [
            e["evidence_id"] for e in model.get("entries", []) if not e.get("lead")
        ],
        "template_id": template_id,
        "template_version": 1,
        "renderer_version": RENDERER_VERSION,
        "output_path": output_path,
    }


def outdated_reasons(previous: dict[str, Any], model: dict[str, Any], template_id: str) -> list[str]:
    """Why an existing document no longer matches the record, or an empty list.

    Reported, never acted on. Overwriting a file the user may have sent to someone is not a
    decision this runtime gets to make.
    """
    target = model.get("target") or {}
    reasons = []
    if previous.get("canonical_revision") != model.get("canonical_revision"):
        reasons.append("canonical evidence changed since this document was generated")
    if previous.get("jd_digest") != target.get("jd_digest"):
        reasons.append("the target JD changed since this document was generated")
    if previous.get("template_id") != template_id:
        reasons.append("a different template was used")
    if previous.get("renderer_version") != RENDERER_VERSION:
        reasons.append("the renderer changed")
    return reasons
