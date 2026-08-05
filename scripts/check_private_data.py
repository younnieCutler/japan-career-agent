#!/usr/bin/env python3
"""Deterministic gate against tracking or committing personal career documents.

Implements docs/PRIVATE_CAREER_DATA_PRD.md §13 (detection) and §15.2/§15.4/§15.5 (Git
protection). Two modes:

    python scripts/check_private_data.py             # every tracked file (AC-19)
    python scripts/check_private_data.py --staged    # the staged set (AC-05, commit hook)

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

# PRIVATE-002: the synthetic allowlist is rule-based, never a path list. A path list goes stale
# on the first rename, and every stale entry is either a false positive that trains people to
# bypass the gate or a false negative that silently stops protecting a file.
SYNTHETIC_PATH_PARTS = {"examples", "mock", "mocks", "fixtures", "tests"}
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


def _paths(staged: bool) -> list[str]:
    if staged:
        output = _git("diff", "--cached", "--name-only", "--diff-filter=ACM", "-z")
    else:
        output = _git("ls-files", "-z")
    return sorted(item for item in output.split("\0") if item)


def is_synthetic(relative: str, prefix: bytes) -> bool:
    parts = relative.split("/")
    if SYNTHETIC_PATH_PARTS.intersection(parts[:-1]):
        return True
    if SYNTHETIC_NAME_INFIX in parts[-1]:
        return True
    text = prefix.decode("utf-8", errors="replace")
    return any(marker in text for marker in SYNTHETIC_CONTENT_MARKERS)


def _read_prefix(path: Path) -> bytes:
    # Symlinks are not followed (PRD §28); an unreadable file is classified on metadata alone.
    if path.is_symlink() or not path.is_file():
        return b""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return b""
        with path.open("rb") as stream:
            return stream.read(MAX_READ_BYTES)
    except OSError:
        return b""


def _office_document(path: Path, prefix: bytes) -> bool:
    """Detect an Office document by container shape, so a renamed .docx is still caught."""
    if not prefix.startswith(ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
    return any(member in names for member in OFFICE_ZIP_MEMBERS)


def classify(relative: str) -> Finding | None:
    path = ROOT / relative
    prefix = _read_prefix(path)

    if is_synthetic(relative, prefix):
        return None

    name = relative.split("/")[-1]
    suffix = Path(name).suffix.lower()

    if suffix in DOCUMENT_EXTENSIONS:
        return Finding(relative, "personal document format", "high", f"extension {suffix}")
    if any(pattern.search(name) for pattern in FILENAME_PATTERNS):
        return Finding(relative, "career document filename", "high", "filename")
    if _office_document(path, prefix):
        return Finding(relative, "office document", "high", "zip container shape")

    if b"\0" in prefix:  # binary: never scanned as text
        return None

    text = prefix.decode("utf-8", errors="replace")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return Finding(relative, "embedded secret", "high", "secret pattern")

    matched = sorted(key for key, pattern in STRUCTURED_FIELD_PATTERNS.items() if pattern.search(text))
    if len(matched) >= 2:
        return Finding(relative, "personal document structure", "high", "+".join(matched))
    if matched:
        return Finding(relative, "possible personal data", "ambiguous", matched[0])
    return None


def scan(staged: bool) -> list[Finding]:
    return [finding for path in _paths(staged) if (finding := classify(path)) is not None]


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
            "If this file is a synthetic fixture, mark it as one (PRD section 13.3): put it under\n"
            "an examples/ or tests/ directory, use the .example. infix, or declare a synthetic\n"
            "provenance marker in its content.",
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
