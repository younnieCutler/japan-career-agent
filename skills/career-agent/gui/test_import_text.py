#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import unittest
import zipfile
from unittest.mock import patch

from import_text import extract_career_text


def encoded(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def docx_bytes(text: str) -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
    ).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
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

    def test_rejects_unsupported_or_empty_documents(self):
        with self.assertRaises(ValueError):
            extract_career_text("resume.pages", encoded(b"content"))
        with self.assertRaises(ValueError):
            extract_career_text("resume.txt", encoded(b""))


if __name__ == "__main__":
    unittest.main()
