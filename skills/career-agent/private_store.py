"""Private career-document store: root resolution, hash-verified import, and registry.

Implements docs/PRIVATE_CAREER_DATA_PRD.md phase 2 (sections 6, 7, 14, 17.1). The store is
deliberately independent of the Career Vault: `CAREER_PRIVATE_HOME` outranks `<CAREER_VAULT>/private`
in the resolution order, and nothing here requires an initialized Vault.

Two invariants drive the whole module:

- The canonical private root MUST NOT resolve inside any Git worktree (section 6.1). Storage that
  lives in a worktree is one `git add -f` away from being tracked, which is the problem the private
  store exists to solve.
- Import copies and verifies; it never moves or deletes the user's original (section 14). "Import
  succeeded" and "your file is gone" are different promises, and only the second is unrecoverable
  when the classification was wrong.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import stat
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SHARED_ROOT = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))
import pipeline_store  # noqa: E402

from models import CareerError  # noqa: E402
from persistence import append_jsonl, atomic_write_bytes, read_jsonl  # noqa: E402

DEFAULT_PRIVATE_DIRNAME = ".career-agent-private"
PRIVATE_ENV = "CAREER_PRIVATE_HOME"

DOCUMENT_TYPES = (
    "resume",
    "shokumukeirekisho",
    "es",
    "certificates",
    "compensation",
    "education",
    "assessments",
    "other",
)
PRIVATE_DIRECTORIES = (
    "inbox",
    *(f"documents/{name}" for name in DOCUMENT_TYPES),
    "timeline",
    "current",
    "quarantine",
)

DOCUMENT_STATUSES = {"current", "superseded"}
READ_CHUNK = 1024 * 1024


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_date(value: str | None, field: str) -> str | None:
    """Reject an impossible calendar date (section 19.2), not just a wrong-looking shape."""
    if value in (None, ""):
        return None
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise CareerError(f"{field} must be a real calendar date (YYYY-MM-DD): {value!r}") from exc


def git_worktree_root(path: Path) -> Path | None:
    """Return the worktree containing ``path``, or None.

    Walks upward so a not-yet-created directory is judged by its parents. A `.git` entry may be a
    directory (ordinary clone) or a file (linked worktree / submodule); both mean "tracked here".
    """
    current = path if path.is_absolute() else path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_private_home(explicit: str | Path | None = None, vault: str | Path | None = None) -> Path:
    """Resolve the canonical private root (section 6.1) and enforce the Git boundary."""
    chosen: Path | None = None
    origin = ""
    if explicit:
        chosen, origin = Path(explicit).expanduser(), "--private-home"
    elif os.environ.get(PRIVATE_ENV):
        chosen, origin = Path(os.environ[PRIVATE_ENV]).expanduser(), PRIVATE_ENV
    elif vault:
        # Only usable when the Vault itself is outside every worktree; otherwise fall through to
        # the user-local default rather than silently choosing a tracked location.
        vault_path = Path(vault).expanduser().resolve()
        if git_worktree_root(vault_path) is None:
            chosen, origin = vault_path / "private", "CAREER_VAULT/private"
    if chosen is None:
        chosen, origin = Path.home() / DEFAULT_PRIVATE_DIRNAME, "user-local default"

    resolved = chosen.expanduser().resolve()
    worktree = git_worktree_root(resolved)
    if worktree is not None:
        raise CareerError(
            f"private root resolves inside a Git worktree and cannot be used: {resolved}\n"
            f"  resolved from: {origin}\n"
            f"  worktree: {worktree}\n"
            f"Set {PRIVATE_ENV} to a location outside every Git repository, "
            f"for example {Path.home() / DEFAULT_PRIVATE_DIRNAME}."
        )
    return resolved


class PrivateHome:
    """Paths inside the private root. Construction never touches the filesystem."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.inbox = self.path / "inbox"
        self.documents = self.path / "documents"
        self.timeline = self.path / "timeline"
        self.current = self.path / "current"
        self.quarantine = self.path / "quarantine"
        self.registry = self.timeline / "documents.jsonl"
        self.facts = self.timeline / "facts.jsonl"
        self.profile = self.current / "personal-profile.json"

    def initialized(self) -> bool:
        return self.registry.exists() or self.documents.is_dir()

    def records(self) -> list[dict[str, Any]]:
        return read_jsonl(self.registry)


@contextmanager
def private_lock(home: PrivateHome) -> Iterator[None]:
    """Serialize import against other processes (section 14: concurrent imports)."""
    home.timeline.mkdir(parents=True, exist_ok=True)
    with pipeline_store.locked(home.timeline / "registry"):
        yield


def initialize_private_home(home: PrivateHome) -> dict[str, Any]:
    created: list[str] = []
    for relative in PRIVATE_DIRECTORIES:
        target = home.path / relative
        if not target.exists():
            target.mkdir(parents=True)
            created.append(relative)
    _restrict_permissions(home.path)
    return {"private_home": str(home.path), "created": created}


def _restrict_permissions(path: Path) -> None:
    """Make the private root user-only where the platform actually supports it.

    On Windows `os.chmod` toggles only the read-only bit and real per-user ACLs need `icacls`, so
    enforcement there is an explicit non-goal (section 6.3). `private-doctor` reports the honest
    state instead of implying a guarantee it did not make.
    """
    if os.name == "nt":
        return
    try:
        path.chmod(stat.S_IRWXU)
    except OSError:
        pass


def permission_state(home: PrivateHome) -> dict[str, Any]:
    if os.name == "nt":
        return {"enforced": False, "detail": "not enforced on this platform"}
    if not home.path.exists():
        return {"enforced": False, "detail": "private root does not exist yet"}
    mode = stat.S_IMODE(home.path.stat().st_mode)
    group_or_other = mode & (stat.S_IRWXG | stat.S_IRWXO)
    return {
        "enforced": group_or_other == 0,
        "detail": "user-only" if group_or_other == 0 else f"group/other bits set: {mode:o}",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_key(document_type: str, company: str | None, purpose: str, language: str) -> dict[str, Any]:
    return {
        "type": document_type,
        "company": company or None,
        "purpose": purpose,
        "language": language,
    }


def _same_key(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(left.get(field) == right.get(field) for field in ("type", "company", "purpose", "language"))


def _validate_source(source: Path) -> Path:
    resolved = source.expanduser().resolve()
    if not resolved.exists():
        raise CareerError(f"source does not exist: {source}")
    if not resolved.is_file():
        raise CareerError(f"source is not a regular file: {source}")
    return resolved


def import_document(
    home: PrivateHome,
    source: str | Path,
    document_type: str,
    *,
    effective_from: str | None = None,
    company: str | None = None,
    purpose: str = "general",
    language: str = "ja",
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Copy-verify-register one document. The source file is preserved (section 14)."""
    if document_type not in DOCUMENT_TYPES:
        raise CareerError(f"unknown document type: {document_type}; expected one of {', '.join(DOCUMENT_TYPES)}")
    effective_from = validate_date(effective_from, "effective_from")
    resolved_source = _validate_source(Path(source))

    initialize_private_home(home)
    key = logical_key(document_type, company, purpose, language)
    checksum = sha256_file(resolved_source)
    size_bytes = resolved_source.stat().st_size
    suffix = resolved_source.suffix.lower()
    # Content-addressed storage: identical bytes are stored once even when several logical keys
    # reference them (section 7.3).
    destination = home.documents / document_type / f"{checksum}{suffix}"

    with private_lock(home):
        records = home.records()
        duplicate = next(
            (row for row in records if row.get("sha256") == checksum and _same_key(row.get("logical_key", {}), key)),
            None,
        )
        if duplicate is not None:
            # Re-observation, not a new version: record that we saw it again without pretending
            # the bytes changed (AC-11).
            observation = {
                "document_id": duplicate["document_id"],
                "event": "reobserved",
                "sha256": checksum,
                "observed_at": observed_at or utc_now(),
            }
            append_jsonl(home.registry, observation)
            return {
                "document_id": duplicate["document_id"],
                "sha256": checksum,
                "storage_path": duplicate["storage_path"],
                "document_type": document_type,
                "status": duplicate.get("status", "current"),
                "duplicate": True,
                "source_preserved": resolved_source.exists(),
                "facts_requiring_confirmation": [],
            }

        _publish_blob(resolved_source, destination, checksum)

        superseded = _current_for_key(records, key)
        record: dict[str, Any] = {
            "document_id": f"doc_{uuid.uuid4().hex[:12]}",
            "document_type": document_type,
            "logical_key": key,
            "storage_path": destination.relative_to(home.path).as_posix(),
            "original_name": resolved_source.name,
            "sha256": checksum,
            "size_bytes": size_bytes,
            "observed_at": observed_at or utc_now(),
            "effective_from": effective_from,
            "effective_to": None,
            "status": "current",
            "supersedes": superseded["document_id"] if superseded else None,
            "superseded_by": None,
            "source_type": "personal_evidence",
            # Importing proves the artifact exists; it never promotes a claim to canonical truth
            # (section 5.4). Fact confirmation is phase 3.
            "verified_by_user": False,
            "reviewed_on": None,
        }
        append_jsonl(home.registry, record)
        if superseded is not None:
            append_jsonl(
                home.registry,
                {
                    "document_id": superseded["document_id"],
                    "event": "superseded",
                    "superseded_by": record["document_id"],
                    "observed_at": record["observed_at"],
                },
            )

    return {
        "document_id": record["document_id"],
        "sha256": checksum,
        "storage_path": record["storage_path"],
        "document_type": document_type,
        "status": "current",
        "supersedes": record["supersedes"],
        "duplicate": False,
        "source_preserved": resolved_source.exists(),
        # Phase 3 promotes claims to canonical facts; phase 2 only records the artifact.
        "facts_requiring_confirmation": [],
    }


def _publish_blob(source: Path, destination: Path, checksum: str) -> None:
    """Steps 5-8 of section 14: copy to temp, fsync, verify the hash, then publish atomically."""
    if destination.exists() and sha256_file(destination) == checksum:
        return  # already stored; retry is idempotent
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != checksum:
        raise CareerError(f"source changed while reading: {source}")
    atomic_write_bytes(destination, payload)
    if sha256_file(destination) != checksum:
        # Verification failed after publication: remove the bad copy and record no success.
        destination.unlink(missing_ok=True)
        raise CareerError(f"destination verification failed for {source}; nothing was imported")


def _current_for_key(records: list[dict[str, Any]], key: dict[str, Any]) -> dict[str, Any] | None:
    superseded = {row.get("document_id") for row in records if row.get("event") == "superseded"}
    for row in reversed(records):
        if row.get("event"):
            continue
        if row.get("document_id") in superseded:
            continue
        if _same_key(row.get("logical_key", {}), key) and row.get("status") == "current":
            return row
    return None


def documents(home: PrivateHome) -> list[dict[str, Any]]:
    """Registry records with supersession events folded in."""
    records = home.records()
    superseded = {row["document_id"]: row for row in records if row.get("event") == "superseded"}
    result = []
    for row in records:
        if row.get("event"):
            continue
        item = dict(row)
        if item["document_id"] in superseded:
            item["status"] = "superseded"
            item["superseded_by"] = superseded[item["document_id"]].get("superseded_by")
        result.append(item)
    return result


def private_doctor(
    explicit: str | Path | None = None, vault: str | Path | None = None,
) -> dict[str, Any]:
    """Read-only diagnosis. Never requires an initialized Career Vault (section 17.1)."""
    report: dict[str, Any] = {"ok": True, "checks": {}}
    try:
        root = resolve_private_home(explicit, vault)
    except CareerError as exc:
        return {
            "ok": False,
            "checks": {"private_root": {"ok": False, "detail": str(exc)}},
            "git_boundary": {"ok": False},
        }

    home = PrivateHome(root)
    report["private_home"] = str(root)
    report["checks"]["private_root"] = {"ok": True, "initialized": home.initialized()}
    report["checks"]["git_boundary"] = {"ok": True, "detail": "outside every Git worktree"}
    report["checks"]["permissions"] = permission_state(home)

    records = documents(home)
    current = [row for row in records if row.get("status") == "current"]
    hashes = [row.get("sha256") for row in records]
    blobs_present = sum(1 for row in records if (home.path / row["storage_path"]).is_file())
    report["documents"] = {
        "current": len(current),
        "historical": len(records) - len(current),
        "duplicates": len(hashes) - len(set(hashes)),
        "missing_blobs": len(records) - blobs_present,
    }
    if report["documents"]["missing_blobs"]:
        report["ok"] = False
    return report
