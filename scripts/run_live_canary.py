#!/usr/bin/env python3
"""Run the optional endpoint health check without sending career data."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CANARY_ID = "CANARY-ENDPOINT-001"
HEALTHCHECK_DESCRIPTOR = {
    "kind": "endpoint_health",
    "product": "japan-recruit-ai-agent",
    "contract_version": 1,
}


def _runtime_identity() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
    }


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return "invalid_configuration"
    return None


def run_canary(
    url: str | None,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: float = 10.0,
) -> dict[str, Any]:
    started = time.perf_counter()
    if not url:
        status = "HOST_UNAVAILABLE"
        failure_class = "missing_configuration"
        response_status = None
    else:
        failure_class = _validate_url(url)
        response_status = None
        if failure_class:
            status = "HOST_UNAVAILABLE"
        else:
            request = urllib.request.Request(
                url,
                method="GET",
                headers={"User-Agent": "japan-recruit-ai-agent-canary/1"},
            )
            try:
                with opener(request, timeout=timeout) as response:
                    response_status = int(response.status)
                    response.read(4096)
                status = "PASS" if 200 <= response_status < 300 else "HOST_UNAVAILABLE"
                failure_class = None if status == "PASS" else f"http_{response_status}"
            except urllib.error.HTTPError as exc:
                response_status = exc.code
                status = "HOST_UNAVAILABLE"
                failure_class = f"http_{exc.code}"
            except (urllib.error.URLError, TimeoutError, OSError):
                status = "HOST_UNAVAILABLE"
                failure_class = "network_unavailable"
    return {
        "scenario_id": CANARY_ID,
        "execution_mode": "endpoint_health",
        "classification": "endpoint_health_pass" if status == "PASS" else "not_executable",
        "status": status,
        "passed": status == "PASS",
        "failure_class": failure_class,
        "response_status": response_status,
        "endpoint_configured": bool(url),
        "input_sha256": _hash_payload(HEALTHCHECK_DESCRIPTOR),
        "output_sha256": _hash_payload({"status": status, "response_status": response_status}),
        "runtime_identity": _runtime_identity(),
        "model_identity": None,
        "duration_ms": max(0, round((time.perf_counter() - started) * 1000)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="approved HTTPS health endpoint; no career data is sent")
    parser.add_argument("--output", default="canary-result.json")
    args = parser.parse_args(argv)
    result = run_canary(args.url)
    output = Path(args.output)
    if not output.is_absolute():
        output = Path.cwd() / output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "failure_class": result["failure_class"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
