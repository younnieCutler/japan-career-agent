#!/usr/bin/env python3
"""Focused tests for dependency lock parsing and alignment."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import check_dependency_lock as lock


class DependencyLockTests(unittest.TestCase):
    def test_repository_locks_are_aligned(self) -> None:
        errors = lock.validate(
            lock.ROOT / "requirements.lock",
            lock.ROOT / "requirements-dev.lock",
            lock.ROOT / "requirements.txt",
        )
        self.assertEqual(errors, [])

    def test_missing_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "requirements.lock"
            path.write_text("--require-hashes\nPyYAML==6.0.3\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                lock.parse_lock(path)

    def test_pin_outside_requirement_specifier_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            requirements = Path(temporary) / "requirements.txt"
            requirements.write_text("PyYAML>=7,<8\n", encoding="utf-8")
            errors = lock.validate(
                lock.ROOT / "requirements.lock",
                lock.ROOT / "requirements-dev.lock",
                requirements,
            )
            self.assertTrue(any("does not satisfy" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
