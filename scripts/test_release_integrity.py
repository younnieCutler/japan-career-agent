#!/usr/bin/env python3
"""Focused release build and verification tests."""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path

import build_release
import verify_release


class ReleaseIntegrityTests(unittest.TestCase):
    def test_generic_temp_marker_in_scanner_source_is_not_a_leak(self) -> None:
        with mock.patch.object(tempfile, "gettempdir", return_value="/tmp"):
            entries = build_release._source_entries(["scripts/e2e_artifact.py"])
        self.assertEqual(entries[0]["path"], "scripts/e2e_artifact.py")

    def test_clean_bundle_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "release"
            manifest = build_release.build(output)
            verified = verify_release.verify(
                output / "release-manifest.json",
                output / "SHA256SUMS",
                output / manifest["artifact"]["name"],
                output / manifest["sbom"]["name"],
            )
            self.assertEqual(verified["source_commit"], manifest["source_commit"])
            self.assertTrue(verified["git_status_clean"])

    def test_manifest_rejects_absolute_source_paths(self) -> None:
        with self.assertRaises(verify_release.ReleaseVerificationError):
            verify_release._check_manifest(
                {
                    "format_version": 1,
                    "product": "japan-career-agent",
                    "version": "1.7.0",
                    "source_commit": "0" * 40,
                    "git_status_clean": True,
                    "source_tree_sha256": "0" * 64,
                    "files": [{"path": "/home/user/private", "size": 0, "sha256": "0" * 64}],
                    "artifact": {"name": "a.zip", "size": 0, "sha256": "0" * 64},
                    "sbom": {"name": "sbom.cdx.json", "size": 0, "sha256": "0" * 64},
                }
            )


if __name__ == "__main__":
    unittest.main()
