#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import unittest
import zipfile
from unittest.mock import patch

from import_text import (
    MAX_DOCX_XML_BYTES,
    MAX_IMPORT_BYTES,
    MAX_IMPORT_TEXT_CHARS,
    MAX_PDF_PAGES,
    extract_career_text,
)


def encoded(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def docx_bytes(text: str, *, compression: int = zipfile.ZIP_STORED) -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
    ).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


class CareerImportTextTests(unittest.TestCase):
    def test_txt_and_docx_extract_without_changing_content(self):
        self.assertEqual(extract_career_text("resume.txt", encoded("경력 요약".encode())), "경력 요약")
        self.assertEqual(extract_career_text("職務経歴書.docx", encoded(docx_bytes("職務経歴"))), "職務経歴")

    def test_pdf_uses_text_extraction_only(self):
        page = type("Page", (), {"extract_text": lambda self: "Platform migration"})()
        reader = type("Reader", (), {"pages": [page]})()
        with patch("import_text.PdfReader", return_value=reader):
            self.assertEqual(extract_career_text("resume.pdf", encoded(b"pdf")), "Platform migration")

    def test_rejects_unsupported_empty_and_invalid_payloads(self):
        with self.assertRaises(ValueError):
            extract_career_text("resume.pages", encoded(b"content"))
        with self.assertRaises(ValueError):
            extract_career_text("resume.txt", encoded(b""))
        with self.assertRaises(ValueError):
            extract_career_text("resume.txt", "%%%not-base64%%")

    def test_rejects_raw_and_extracted_text_over_limits(self):
        with self.assertRaises(ValueError):
            extract_career_text("resume.txt", encoded(b"x" * (MAX_IMPORT_BYTES + 1)))
        with self.assertRaises(ValueError):
            extract_career_text("resume.txt", encoded(b"x" * (MAX_IMPORT_TEXT_CHARS + 1)))

    def test_rejects_docx_decompression_beyond_bound(self):
        payload = docx_bytes("x" * (MAX_DOCX_XML_BYTES + 1), compression=zipfile.ZIP_DEFLATED)
        self.assertLess(len(payload), MAX_IMPORT_BYTES)
        with self.assertRaises(ValueError):
            extract_career_text("resume.docx", encoded(payload))

    def test_rejects_pdf_page_count_beyond_bound(self):
        page = type("Page", (), {"extract_text": lambda self: "x"})()
        reader = type("Reader", (), {"pages": [page] * (MAX_PDF_PAGES + 1)})()
        with patch("import_text.PdfReader", return_value=reader):
            with self.assertRaises(ValueError):
                extract_career_text("resume.pdf", encoded(b"pdf"))


if __name__ == "__main__":
    unittest.main()
