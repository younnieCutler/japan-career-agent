#!/usr/bin/env python3
"""Focused tests for endpoint-health classification."""

from __future__ import annotations

import unittest

import run_live_canary as canary


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self, _: int) -> bytes:
        return b"ok"


class LiveCanaryTests(unittest.TestCase):
    def test_missing_endpoint_is_host_unavailable_not_pass(self) -> None:
        result = canary.run_canary(None)
        self.assertEqual(result["status"], "HOST_UNAVAILABLE")
        self.assertEqual(result["classification"], "not_executable")
        self.assertEqual(result["failure_class"], "missing_configuration")
        self.assertIsNone(result["model_identity"])

    def test_healthy_endpoint_is_pass(self) -> None:
        result = canary.run_canary("https://canary.example.invalid/health", lambda *_args, **_kwargs: FakeResponse(200))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["classification"], "endpoint_health_pass")
        self.assertEqual(result["execution_mode"], "endpoint_health")
        self.assertIsNone(result["failure_class"])

    def test_non_https_endpoint_is_rejected(self) -> None:
        result = canary.run_canary("http://canary.example.invalid/health")
        self.assertEqual(result["status"], "HOST_UNAVAILABLE")
        self.assertEqual(result["failure_class"], "invalid_configuration")

    def test_provider_failure_remains_host_unavailable(self) -> None:
        result = canary.run_canary("https://canary.example.invalid/health", lambda *_args, **_kwargs: FakeResponse(503))
        self.assertEqual(result["status"], "HOST_UNAVAILABLE")
        self.assertEqual(result["failure_class"], "http_503")


if __name__ == "__main__":
    unittest.main()
