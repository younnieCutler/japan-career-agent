"""Extract text from a local career document without changing canonical career state."""

from __future__ import annotations

import base64
import binascii
import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader


MAX_IMPORT_BYTES = 5 * 1024 * 1024
SUPPORTED_SUFFIXES = frozenset({".txt", ".docx", ".pdf"})
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _decode_payload(content_base64: str) -> bytes:
    try:
        raw = base64.b64decode(str(content_base64), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid document payload") from exc
    if not raw:
        raise ValueError("document is empty")
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError("document is too large")
    return raw


def _txt_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("text document must be UTF-8") from exc


def _docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            document = archive.read("word/document.xml")
        root = ET.fromstring(document)
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise ValueError("invalid DOCX document") from exc
    lines: list[str] = []
    for paragraph in root.iter(f"{_WORD_NS}p"):
        value = "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t")).strip()
        if value:
            lines.append(value)
    return "\n".join(lines)


def _pdf_text(raw: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Exception as exc:
        raise ValueError("invalid PDF document") from exc


def extract_career_text(filename: str, content_base64: str) -> str:
    """Return plain text from TXT, DOCX, or text-based PDF bytes."""
    suffix = Path(str(filename)).suffix.casefold()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("unsupported document type")
    raw = _decode_payload(content_base64)
    text = {
        ".txt": _txt_text,
        ".docx": _docx_text,
        ".pdf": _pdf_text,
    }[suffix](raw).strip()
    if not text:
        raise ValueError("document contains no extractable text")
    return text
