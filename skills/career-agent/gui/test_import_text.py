#!/usr/bin/env python3
from __future__ import annotations

import base64
import http.client
import io
import json
import sys
import threading
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from gui.server import create_server  # noqa: E402
from import_text import (  # noqa: E402
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


@contextmanager
def running_server():
    try:
        server = create_server(port=0, home=object())
    except PermissionError as exc:
        raise unittest.SkipTest(f"loopback bind unavailable in this execution sandbox: {exc}") from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def request(server, method: str, path: str, *, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, dict(response.getheaders()), payload
    connection.close()
    return result


class CareerImportTextTests(unittest.TestCase):
    def test_txt_and_docx_extract_without_changing_content(self):
        self.assertEqual(extract_career_text("resume.txt", encoded("경력 요약".encode())), "경력 요약")
        self.assertEqual(extract_career_text("職務経歴書.docx", encoded(docx_bytes("職務経歴"))), "職務経歴")

    def test_pdf_uses_text_extraction_only(self):
        page = type("Page", (), {"extract_text": lambda self: "Platform migration"})()
        reader = type("Reader", (), {"pages": [page]})()
        with patch("import_text.PdfReader", return_value=reader):
            self.assertEqual(extract_career_text("resume.pdf", encoded(b"pdf")), "Platform migration")

    def test_authenticated_post_route_returns_imported_text(self):
        with running_server() as server:
            status, headers, body = request(
                server,
                "POST",
                "/session",
                headers={"Content-Type": "application/json", "Origin": server.origin},
                body=json.dumps({"token": server.bootstrap_token}),
            )
            self.assertEqual(status, 200)
            cookie = headers["Set-Cookie"].split(";", 1)[0]
            csrf_token = json.loads(body)["csrf_token"]

            status, _, body = request(
                server,
                "POST",
                "/api/career/import-text",
                headers={
                    "Content-Type": "application/json",
                    "Cookie": cookie,
                    "X-CSRF-Token": csrf_token,
                    "Origin": server.origin,
                },
                body=json.dumps({
                    "filename": "resume.txt",
                    "content_base64": encoded("경력 요약".encode()),
                }),
            )
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["text"], "경력 요약")

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
