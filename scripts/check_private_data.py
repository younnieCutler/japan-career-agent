#!/usr/bin/env python3
"""Deterministic gate against tracking or committing personal career documents.

Implements docs/PRIVATE_CAREER_DATA_PRD.md §13 (detection) and §15.2/§15.4/§15.5 (Git
protection). Two modes:

    python scripts/check_private_data.py             # every tracked file (AC-19)
    python scripts/check_private_data.py --staged    # the staged set (AC-05, commit hook)

`classify_bytes` is the single detection implementation. `private-doctor` imports it to scan
configured roots for untracked strays (§13.1, AC-03): a second detector that disagrees with the
commit gate would make both of them meaningless.

Detection is standard-library only by decision, not by omission (PRD §4). Adding a PDF/DOCX
parser would cost `requirements.txt` + two hash-pinned lock files + an SBOM regeneration, and
would widen the parsing attack surface against deliberately untrusted input. The signals below
(filename, extension, ZIP container shape, structured field labels) catch the realistic accident
without any of that.

The output is privacy-safe (PRD §16): repository-relative paths and a classification, never a
line of file content.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

# PRIVATE-004: reuse the release bundler's secret patterns rather than maintaining a second,
# divergent detector that can drift from it.
from build_release import SECRET_PATTERNS

ROOT = Path(__file__).resolve().parents[1]

# Read limits (PRD §13.2). A single large file in a scan root must not stall the commit gate.
MAX_FILE_BYTES = 2_000_000
MAX_READ_BYTES = 65_536

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".odt", ".rtf"}

# PRIVATE-002: the synthetic allowlist is rule-based, never a path list, and it requires an
# explicit DECLARATION -- never mere location.
#
# An earlier version exempted anything under examples/, tests/, fixtures/, mock/ or mocks/. That
# turned those directories into detection blind spots: real personal data in `examples/notes.md`
# was invisible to an ordinary `git add`, while byte-identical content one directory up was
# blocked. A location is not a statement about content, and it directly contradicts this phase's
# contract that a generically named personal document is caught.
#
# Declaring a fixture is cheap; silently trusting a directory name is not.
SYNTHETIC_NAME_INFIX = ".example."
SYNTHETIC_CONTENT_MARKERS = (
    "synthetic://",
    "provenance: synthetic",
    "provenance: 'synthetic'",
    'provenance: "synthetic"',
    "実在の人物ではありません",
)

# Document-name tokens. These name documents, never source files, so they are matched on the
# filename alone. The romanized entries are scoped so ordinary source names cannot collide: a
# bare `cv` would match `recv.py` and a bare `resume` would match a future `resume_parser.py`.
FILENAME_PATTERNS = (
    re.compile(r"履歴書|職務経歴書|エントリーシート|給与明細|源泉徴収|在職証明|卒業証明"),
    re.compile(r"payslip", re.IGNORECASE),
    re.compile(r"(?:^|[-_])(?:cv|resume|curriculum-?vitae)(?:[-_.]|$)", re.IGNORECASE),
)

# PRIVATE-003: structured personal-data field labels — a label, a separator, then a value.
# Deliberately NOT topic words. This repository is full of prose *about* resumes (this PRD, the
# job-seeker references, the shared schema keys); matching "resume" or "jlpt_level" in content
# would flag the repository's own documentation, and a gate that fires on its own repository is
# a gate that gets bypassed. A real document carries filled-in identity fields; prose does not.
STRUCTURED_FIELD_PATTERNS = {
    "identity": re.compile(r"(?:氏名|ふりがな|フリガナ|生年月日|現住所)[ 　]*[:：][ 　]*\S"),
    "contact": re.compile(r"(?:電話番号|携帯番号|連絡先)[ 　]*[:：][ 　]*[\d+(]"),
    "payroll": re.compile(r"(?:基本給|支給額|控除額|差引支給額|社会保険料)[ 　]*[:：][ 　]*[\d¥￥]"),
    "employment": re.compile(r"(?:在籍期間|入社年月|退社年月)[ 　]*[:：][ 　]*\d"),
}

OFFICE_ZIP_MEMBERS = ("word/document.xml", "xl/workbook.xml", "ppt/presentation.xml")
ZIP_MAGIC = b"PK\x03\x04"

# Directories skipped by the filesystem stray scan (§13.1) wherever they appear. These are tool
# caches and dependency trees: no one keeps their 履歴書 in `node_modules`, so walking them is
# wasted I/O rather than extra safety.
SKIP_DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".ruff_cache", ".pytest_cache",
})

# Skipped ONLY at the top level of a scan root that is itself a Git worktree, because that is the
# only place these names mean what this repository means by them. `data/` and `career-home/` are
# this repository's ignored runtime state; `dist/`/`build/` are its build outputs. Applying them to
# an arbitrary `--scan-root` would silently blind the scan to `~/Documents/data/履歴書.pdf`, and a
# detector with unexplained blind spots is the failure mode this gate was rewritten to avoid.
REPOSITORY_SKIP_DIRECTORIES = frozenset({"data", "career-home", "dist", "build"})

# ponytail: flat cap instead of a time budget. A doctor run must not walk an entire home directory;
# raise it or add per-root budgets if a legitimate workspace ever exceeds this. Hitting it makes the
# scan result incomplete, never clean -- see `scan_directory`.
MAX_SCAN_FILES = 5000


class Finding:
    """One probable personal document. Carries no file content (PRD §16)."""

    def __init__(self, path: str, classification: str, confidence: str, signal: str):
        self.path = path
        self.classification = classification
        self.confidence = confidence
        self.signal = signal

    def line(self) -> str:
        return f"  {self.path}\n      classification: {self.classification}  signal: {self.signal}"


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=str(ROOT), capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise SystemExit(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout


def _git_bytes(*arguments: str) -> bytes | None:
    """Binary-safe git read. Returns None when the object is absent."""
    result = subprocess.run(
        ["git", *arguments], cwd=str(ROOT), capture_output=True, check=False
    )
    return None if result.returncode else result.stdout


def _paths(staged: bool) -> list[str]:
    if staged:
        output = _git("diff", "--cached", "--name-only", "--diff-filter=ACM", "-z")
    else:
        output = _git("ls-files", "-z")
    return sorted(item for item in output.split("\0") if item)


def is_synthetic(name: str, content: bytes) -> bool:
    if SYNTHETIC_NAME_INFIX in name:
        return True
    text = content[:MAX_READ_BYTES].decode("utf-8", errors="replace")
    return any(marker in text for marker in SYNTHETIC_CONTENT_MARKERS)


def read_path(path: Path) -> bytes:
    """Size-capped binary read. Symlinks are not followed (PRD §28) and an unreadable file is
    classified on metadata alone."""
    if path.is_symlink() or not path.is_file():
        return b""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return b""
        with path.open("rb") as stream:
            return stream.read(MAX_FILE_BYTES)
    except OSError:
        return b""


def _read_index(relative: str) -> bytes:
    """Read the staged blob -- the bytes that will actually be committed.

    PRIVATE-005: reading the worktree file here is a bypass, not a shortcut. `git add` a document,
    then overwrite the worktree copy with something harmless, and a worktree-reading gate inspects
    the harmless version while the personal bytes sit in the index and land in the commit.
    """
    size = _git_bytes("cat-file", "-s", f":{relative}")
    if size is None:
        return b""
    try:
        if int(size.strip()) > MAX_FILE_BYTES:
            return b""
    except ValueError:
        return b""
    return _git_bytes("cat-file", "blob", f":{relative}") or b""


def read_content(relative: str, staged: bool) -> bytes:
    return _read_index(relative) if staged else read_path(ROOT / relative)


def _office_document(content: bytes) -> bool:
    """Detect an Office document by container shape, so a renamed .docx is still caught.

    Reads the whole (size-capped) blob rather than a prefix: a ZIP's central directory lives at
    the end of the archive, so a prefix cannot be inspected.
    """
    if not content.startswith(ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
    return any(member in names for member in OFFICE_ZIP_MEMBERS)


def classify_bytes(label: str, name: str, content: bytes) -> Finding | None:
    """The single detection implementation, over a display label, a filename, and bytes.

    Split out so the filesystem stray scan and the Git gate cannot drift apart: if `private-doctor`
    and the commit hook ever disagreed about the same file, neither verdict would mean anything.
    """
    prefix = content[:MAX_READ_BYTES]

    if is_synthetic(name, content):
        return None

    suffix = Path(name).suffix.lower()

    if suffix in DOCUMENT_EXTENSIONS:
        return Finding(label, "personal document format", "high", f"extension {suffix}")
    if any(pattern.search(name) for pattern in FILENAME_PATTERNS):
        return Finding(label, "career document filename", "high", "filename")
    if _office_document(content):
        return Finding(label, "office document", "high", "zip container shape")

    if b"\0" in prefix:  # binary: never scanned as text
        return None

    text = prefix.decode("utf-8", errors="replace")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return Finding(label, "embedded secret", "high", "secret pattern")

    matched = sorted(key for key, pattern in STRUCTURED_FIELD_PATTERNS.items() if pattern.search(text))
    if len(matched) >= 2:
        return Finding(label, "personal document structure", "high", "+".join(matched))
    if matched:
        return Finding(label, "possible personal data", "ambiguous", matched[0])
    return None


def classify(relative: str, staged: bool = False) -> Finding | None:
    return classify_bytes(relative, relative.split("/")[-1], read_content(relative, staged))


def scan(staged: bool) -> list[Finding]:
    return [
        finding
        for path in _paths(staged)
        if (finding := classify(path, staged=staged)) is not None
    ]


def scan_directory(root: Path, exclude: tuple[Path, ...] = ()) -> tuple[list[Finding], bool]:
    """Classify untracked files under ``root``. Returns (findings, hit_the_file_cap).

    `REPOSITORY_SKIP_DIRECTORIES` applies only when ``root`` is itself a Git worktree, and only to
    its immediate children — an arbitrary scan root gets no repository-shaped assumptions.

    Findings carry absolute paths and a classification only, never file content (PRD §16).
    """
    findings: list[Finding] = []
    root = root.resolve()
    excluded = tuple(item.resolve() for item in exclude)
    top_level_skips = REPOSITORY_SKIP_DIRECTORIES if (root / ".git").exists() else frozenset()
    seen = 0
    for current, directories, names in os.walk(root, followlinks=False):
        here = Path(current)
        if any(here == item or item in here.parents for item in excluded):
            directories[:] = []
            continue
        skip = SKIP_DIRECTORIES | (top_level_skips if here == root else frozenset())
        directories[:] = sorted(name for name in directories if name not in skip)
        for name in sorted(names):
            if seen >= MAX_SCAN_FILES:
                return findings, True
            seen += 1
            path = here / name
            finding = classify_bytes(str(path), name, read_path(path))
            if finding is not None:
                findings.append(finding)
    return findings, False


def _report(findings: list[Finding], staged: bool) -> None:
    high = [item for item in findings if item.confidence == "high"]
    ambiguous = [item for item in findings if item.confidence == "ambiguous"]

    if staged:
        print("BLOCKED: probable personal career document is staged.\n", file=sys.stderr)
    else:
        print("Probable personal career documents are tracked by Git.\n", file=sys.stderr)

    if high:
        print("high confidence:", file=sys.stderr)
        print("\n".join(item.line() for item in high), file=sys.stderr)
    if ambiguous:
        print("\nambiguous (review required, not auto-classified):", file=sys.stderr)
        print("\n".join(item.line() for item in ambiguous), file=sys.stderr)

    if staged:
        print(
            # ASCII only: Windows CI consoles are not guaranteed to be UTF-8, and a gate that
            # crashes while reporting a leak is worse than one that reports it plainly.
            "\nAction: unstage it and import it into CAREER_PRIVATE_HOME instead:\n"
            "  git restore --staged <path>\n"
            "  python skills/career-agent/career_agent.py private-import <path> --type resume\n"
            "If this file is a synthetic fixture, DECLARE it as one (PRD section 13.3): use the\n"
            ".example. infix in the filename, or put a synthetic provenance marker in its content.\n"
            "Directory location never suppresses detection.",
            file=sys.stderr,
        )
        return

    # PRD §15.5: refusing to rewrite history is correct, but refusing to explain leaves the user
    # with a finding and no path forward. Point 4 is the one that changes what they actually do.
    print(
        "\nThis file is already in Git history. Ignore rules do not apply retroactively.\n"
        "  1. `git rm --cached <path>` stops future tracking but does NOT remove it from history.\n"
        "  2. Removing it from history needs a deliberate rewrite and force-push. This tool will\n"
        "     not do that for you.\n"
        "  3. If the commit was pushed — especially to a public remote — treat the contents as\n"
        "     ALREADY DISCLOSED. A later history rewrite does not un-disclose them: clones, forks,\n"
        "     caches, and platform views may retain the content.\n"
        "  4. Act on the content itself: rotate anything credential-like and treat the personal\n"
        "     data as exposed.",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--staged", action="store_true",
        help="check the staged set instead of every tracked file (used by the commit hook)",
    )
    arguments = parser.parse_args(argv)

    findings = scan(arguments.staged)
    if findings:
        _report(findings, arguments.staged)
        return 1
    scope = "staged files" if arguments.staged else "tracked files"
    print(f"private data scan: clean ({scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
