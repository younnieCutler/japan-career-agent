"""Application-owned durable artifact metadata and digest-named bodies."""

from __future__ import annotations

import hashlib
import re
import uuid
import datetime as dt
from pathlib import Path
from typing import Any

from case_store import get_case
from lifecycle import vault_lock
from models import CareerError
from persistence import atomic_write_text, read_json, write_json
from vault import CareerVault, utc_now


ARTIFACT_ID = re.compile(r"^art-[a-f0-9]{16}$")
ARTIFACT_KIND = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
MAX_BODY_BYTES = 4 * 1024 * 1024


def _next_updated_at(previous: str, now: str) -> str:
    try:
        prior = dt.datetime.fromisoformat(previous.replace("Z", "+00:00"))
        current = dt.datetime.fromisoformat(now.replace("Z", "+00:00"))
    except ValueError:
        return now
    if current <= prior:
        return (prior + dt.timedelta(seconds=1)).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return now


def artifacts_root(home: CareerVault) -> Path:
    return home.path / "03-active" / "gui" / "artifacts"


def artifact_path(home: CareerVault, artifact_id: str) -> Path:
    if not isinstance(artifact_id, str) or not ARTIFACT_ID.fullmatch(artifact_id):
        raise CareerError("invalid artifact id", code="INVALID_INPUT")
    return artifacts_root(home) / f"{artifact_id}.json"


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CareerError(f"{field} must be a non-empty string", code="INVALID_INPUT")
    return value.strip()


def _strings(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise CareerError(f"{field} must be a list of strings", code="INVALID_INPUT")
    result: list[str] = []
    for item in value:
        result.append(_text(item, field))
    return result


def _generated_by(value: Any) -> dict[str, str]:
    if value is None:
        return {"entrypoint": "gui", "workflow": "artifact_registration"}
    if not isinstance(value, dict):
        raise CareerError("generated_by must be an object", code="INVALID_INPUT")
    return {
        "entrypoint": _text(value.get("entrypoint"), "generated_by.entrypoint"),
        "workflow": _text(value.get("workflow"), "generated_by.workflow"),
    }


def _validate_artifact(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise CareerError("artifact record must be an object", code="ARTIFACT_INVALID")
    if not isinstance(record.get("artifact_id"), str) or not ARTIFACT_ID.fullmatch(record["artifact_id"]):
        raise CareerError("artifact record has an invalid id", code="ARTIFACT_INVALID")
    if not isinstance(record.get("kind"), str) or not ARTIFACT_KIND.fullmatch(record["kind"]):
        raise CareerError("artifact record has an invalid kind", code="ARTIFACT_INVALID")
    if not isinstance(record.get("case_ref"), str):
        raise CareerError("artifact.case_ref is required", code="ARTIFACT_INVALID")
    if not isinstance(record.get("evidence_refs"), list) or not all(
        isinstance(item, str) and item for item in record["evidence_refs"]
    ):
        raise CareerError("artifact.evidence_refs is invalid", code="ARTIFACT_INVALID")
    if not isinstance(record.get("source_refs"), list) or not all(
        isinstance(item, str) and item for item in record["source_refs"]
    ):
        raise CareerError("artifact.source_refs is invalid", code="ARTIFACT_INVALID")
    if not isinstance(record.get("version"), int) or record["version"] < 1:
        raise CareerError("artifact.version is invalid", code="ARTIFACT_INVALID")
    if record.get("status") not in {"current", "superseded", "deleted"}:
        raise CareerError("artifact.status is invalid", code="ARTIFACT_INVALID")
    if not isinstance(record.get("generated_by"), dict):
        raise CareerError("artifact.generated_by is invalid", code="ARTIFACT_INVALID")
    if not isinstance(record.get("body_ref"), str) or not record["body_ref"].startswith(
        "03-active/gui/artifacts/career-docs/"
    ):
        raise CareerError("artifact.body_ref is invalid", code="ARTIFACT_INVALID")
    return dict(record)


def _read_artifact(home: CareerVault, artifact_id: str) -> dict[str, Any]:
    record = read_json(artifact_path(home, artifact_id), None)
    if record is None:
        raise CareerError(f"artifact not found: {artifact_id}", code="ARTIFACT_NOT_FOUND")
    return _validate_artifact(record)


def get_artifact(home: CareerVault, artifact_id: str) -> dict[str, Any]:
    return _read_artifact(home, artifact_id)


def _read_body_strict(home: CareerVault, artifact_id: str) -> dict[str, Any]:
    """One artifact's stored text, with its digest re-checked against the metadata.

    `body_ref` is a value this process wrote, but it is read back from a file the user or another
    tool can edit, so it is resolved and confined to the artifact tree rather than trusted. The
    digest comparison is not integrity theatre either: a hand-edited body is a document whose text
    no longer matches the artifact record, and the screen should say so instead of showing it as
    the version that was generated.
    """
    record = _read_artifact(home, artifact_id)
    root = (artifacts_root(home) / "career-docs").resolve()
    path = (home.path / str(record.get("body_ref", ""))).resolve()
    if root not in path.parents or not path.is_file():
        raise CareerError("artifact body is missing", code="ARTIFACT_BODY_MISSING")
    body = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {
        "artifact": record,
        "body": body,
        "body_sha256": digest,
        "matches_record": digest == record.get("body_sha256"),
    }


def artifact_body(home: CareerVault, artifact_id: str) -> dict[str, Any] | None:
    """The artifact's text, or None when there is nothing to show.

    Returning None rather than raising keeps the domain error type out of the GUI, which may not
    import it. "Nothing to show" is all the caller needs to choose a 404.
    """
    try:
        return _read_body_strict(home, artifact_id)
    except CareerError:
        return None


def _body_ref(home: CareerVault, case_ref: str, kind: str, body: str) -> tuple[str, str]:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    filename = f"{kind}-{utc_now()[:10].replace('-', '')}-{digest[:16]}.md"
    relative = Path("03-active/gui/artifacts/career-docs") / case_ref / filename
    return relative.as_posix(), digest


def _write_body(home: CareerVault, body_ref: str, body: str) -> None:
    path = home.path / body_ref
    if path.exists():
        if path.read_text(encoding="utf-8") != body:
            raise CareerError("digest-named artifact body collision", code="ARTIFACT_COLLISION")
        return
    atomic_write_text(path, body)


def _all_artifacts(home: CareerVault) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(artifacts_root(home).glob("art-*.json")):
        rows.append(_validate_artifact(read_json(path, None)))
    return rows


def register_artifact(
    home: CareerVault,
    *,
    case_ref: str,
    kind: str,
    body: str,
    evidence_refs: Any = None,
    source_refs: Any = None,
    generated_by: Any = None,
    expected_artifact_id: str | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    case = get_case(home, case_ref)
    if case["status"] != "active":
        raise CareerError("cannot attach an artifact to an inactive case", code="INVALID_RELATIONSHIP")
    if not isinstance(kind, str) or not ARTIFACT_KIND.fullmatch(kind):
        raise CareerError("kind must use lowercase artifact naming", code="INVALID_INPUT")
    if not isinstance(body, str) or not body:
        raise CareerError("artifact body must be a non-empty string", code="INVALID_INPUT")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise CareerError("artifact body is too large", code="INVALID_INPUT")
    refs = _strings(evidence_refs, "evidence_refs")
    sources = _strings(source_refs, "source_refs")
    producer = _generated_by(generated_by)
    body_ref, digest = _body_ref(home, case_ref, kind, body)
    now = utc_now()
    with vault_lock(home):
        if get_case(home, case_ref)["status"] != "active":
            raise CareerError(
                "cannot attach an artifact to an inactive case",
                code="INVALID_RELATIONSHIP",
            )
        previous = [
            item for item in _all_artifacts(home)
            if item["case_ref"] == case_ref and item["kind"] == kind
        ]
        if expected_artifact_id is not None:
            prior = next((item for item in previous if item["artifact_id"] == expected_artifact_id), None)
            # Superseding is linear, so the named version must still be the live one. Demoting a
            # version rewrites its `updated_at`, which already refuses a caller holding the older
            # value -- but re-reading the retired row yields a revision that matches, and that was
            # enough to build a new version on the provenance of one already replaced while
            # retiring the live document in the same call.
            if prior is None or prior["status"] != "current":
                raise CareerError(
                    "this artifact is no longer the current version",
                    code="REVISION_STALE",
                    retryable=True,
                )
            if expected_revision is not None and prior.get("updated_at") != expected_revision:
                raise CareerError("this artifact changed in another entrypoint", code="REVISION_STALE", retryable=True)
        version = max((item["version"] for item in previous), default=0) + 1
        if previous:
            now = _next_updated_at(max(str(item["updated_at"]) for item in previous), now)
        # Write the new version first, demote the old one last. Each file write is atomic on its
        # own, but the transition across several files is not, so the order decides what a kill
        # in the middle leaves behind. Demoting first can leave the kind with no current artifact
        # at all -- the user's document vanishes from the screen while its body is still on disk.
        # This way the worst case is two rows marked current, and `version` says which is newer.
        _write_body(home, body_ref, body)
        record = {
            "artifact_id": f"art-{uuid.uuid4().hex[:16]}",
            "kind": kind,
            "case_ref": case_ref,
            "evidence_refs": refs,
            "source_refs": sources,
            "version": version,
            "status": "current",
            "generated_by": producer,
            "body_ref": body_ref,
            "body_sha256": digest,
            "created_at": now,
            "updated_at": now,
        }
        _validate_artifact(record)
        write_json(artifact_path(home, record["artifact_id"]), record)
        for item in previous:
            if item["status"] == "current":
                item["status"] = "superseded"
                item["updated_at"] = now
                write_json(artifact_path(home, item["artifact_id"]), item)
    return record


def update_artifact(
    home: CareerVault, artifact_id: str, *, body: str, expected_revision: str | None = None,
) -> dict[str, Any]:
    previous = _read_artifact(home, artifact_id)
    return register_artifact(
        home,
        case_ref=previous["case_ref"],
        kind=previous["kind"],
        body=body,
        evidence_refs=previous["evidence_refs"],
        source_refs=previous["source_refs"],
        generated_by=previous["generated_by"],
        # Always named, revision or not: the caller supplied an artifact to rewrite, and whether
        # it is still the current version is checked under the lock rather than here, where the
        # answer could change before the write.
        expected_artifact_id=artifact_id,
        expected_revision=expected_revision,
    )


def list_artifacts(
    home: CareerVault,
    *,
    case_ref: str | None = None,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    if case_ref is not None:
        get_case(home, case_ref)
    rows = [
        item for item in _all_artifacts(home)
        if (case_ref is None or item["case_ref"] == case_ref)
        and (include_deleted or item["status"] != "deleted")
    ]
    return sorted(rows, key=lambda item: (item["case_ref"], item["kind"], item["version"]))


def delete_artifact(home: CareerVault, artifact_id: str) -> dict[str, Any]:
    """Tombstone metadata and leave its body and evidence references intact."""
    with vault_lock(home):
        record = _read_artifact(home, artifact_id)
        record["status"] = "deleted"
        record["updated_at"] = utc_now()
        _validate_artifact(record)
        write_json(artifact_path(home, artifact_id), record)
    return record
