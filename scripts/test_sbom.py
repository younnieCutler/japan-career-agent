#!/usr/bin/env python3
"""Focused tests for deterministic CycloneDX generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_sbom


class SbomTests(unittest.TestCase):
    def test_tracked_sbom_matches_deterministic_generation(self) -> None:
        expected = build_sbom.build_document(
            build_sbom.ROOT / "requirements.lock",
            build_sbom.ROOT / "requirements-dev.lock",
        )
        current = json.loads((build_sbom.ROOT / "sbom.cdx.json").read_text(encoding="utf-8"))
        self.assertEqual(current, expected)
        self.assertEqual(current["bomFormat"], "CycloneDX")
        self.assertEqual(current["specVersion"], "1.5")

    def test_line_endings_do_not_change_semantic_lock_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            documents = []
            for name, newline in (("lf", "\n"), ("crlf", "\r\n")):
                directory = root / name
                directory.mkdir()
                for lock_name in ("requirements.lock", "requirements-dev.lock"):
                    text = (build_sbom.ROOT / lock_name).read_text(encoding="utf-8")
                    (directory / lock_name).write_bytes(text.replace("\n", newline).encode("utf-8"))
                documents.append(
                    build_sbom.build_document(
                        directory / "requirements.lock", directory / "requirements-dev.lock"
                    )
                )
            self.assertEqual(documents[0], documents[1])


if __name__ == "__main__":
    unittest.main()
