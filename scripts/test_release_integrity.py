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

    def _manifest(self, **overrides) -> dict:
        base = {
            "format_version": 1,
            "product": "japan-career-agent",
            "version": "2.1.0",
            "source_commit": "0" * 40,
            "git_status_clean": True,
            "source_tree_sha256": "0" * 64,
            "files": [{"path": "README.md", "size": 0, "sha256": "0" * 64}],
            "artifact": {"name": "a.zip", "size": 0, "sha256": "0" * 64},
            "sbom": {"name": "sbom.cdx.json", "size": 0, "sha256": "0" * 64},
        }
        base.update(overrides)
        return base

    def test_manifest_from_before_the_rename_still_verifies(self) -> None:
        # A 2.0.x bundle is already downloaded and cannot be re-stamped. Rejecting it here would
        # mean this verifier no longer checks the releases people actually hold.
        verify_release._check_manifest(
            self._manifest(product="japan-recruit-ai-agent", version="2.0.0")
        )

    def test_manifest_without_a_wheel_still_verifies(self) -> None:
        verify_release._check_manifest(self._manifest())

    def test_manifest_with_a_wheel_verifies(self) -> None:
        # 2.1.0 records the PyPI wheel beside the archive so the file the registry serves can be
        # checked against the GitHub Release.
        verify_release._check_manifest(
            self._manifest(wheel={"name": "w.whl", "size": 1, "sha256": "0" * 64})
        )

    def test_manifest_rejects_an_unknown_key(self) -> None:
        # `wheel` is tolerated because this contract describes it. Anything else means the manifest
        # was written by something that is not this contract.
        with self.assertRaises(verify_release.ReleaseVerificationError):
            verify_release._check_manifest(self._manifest(surprise={"name": "x"}))

    def test_manifest_rejects_a_malformed_wheel_entry(self) -> None:
        with self.assertRaises(verify_release.ReleaseVerificationError):
            verify_release._check_manifest(self._manifest(wheel={"name": "w.whl"}))

    def test_manifest_rejects_an_unknown_product(self) -> None:
        with self.assertRaises(verify_release.ReleaseVerificationError):
            verify_release._check_manifest(self._manifest(product="something-else"))

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
