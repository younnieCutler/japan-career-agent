#!/usr/bin/env python3
"""Deterministic lifecycle tests for the fail-open UserPromptSubmit hook."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"


def _hook_commands() -> tuple[str, str]:
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    hook = data["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    return hook["command"], hook["commandWindows"]


def _run_hook(plugin_root: Path | None, *, script: str | None = None,
              python_available: bool = True, empty_root: bool = False) -> subprocess.CompletedProcess[str]:
    command, command_windows = _hook_commands()
    env = os.environ.copy()
    if empty_root:
        env["CLAUDE_PLUGIN_ROOT"] = ""
    elif plugin_root is None:
        env.pop("CLAUDE_PLUGIN_ROOT", None)
    else:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        if script is not None:
            scripts = plugin_root / "scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / "status_bar.py").write_text(script, encoding="utf-8")

    if not python_available:
        path = Path(tempfile.mkdtemp(prefix="hook-empty-path-"))
        env["PATH"] = str(path)

    if os.name == "nt":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            raise AssertionError("PowerShell is required for the Windows hook contract test")
        argv = [powershell, "-NoProfile", "-NonInteractive", "-Command", command_windows]
    else:
        argv = ["/bin/sh", "-c", command]
    return subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)


def _assert_degraded(result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"hook blocked prompt: {output}"
    assert "<career_status>" in result.stdout
    assert "status_bar: unavailable" in result.stdout
    assert "Execution gates and deadlines were NOT checked." in result.stdout
    assert "can't open file" not in output
    assert "Traceback" not in output


def test_missing_script_fails_open() -> None:
    with tempfile.TemporaryDirectory(prefix="plugins cache ") as tmp:
        stale_root = Path(tmp) / "plugins" / "cache" / "japan-recruit-ai-agent" / "1.6.0"
        _assert_degraded(_run_hook(stale_root))


def test_missing_plugin_root_fails_open() -> None:
    _assert_degraded(_run_hook(None))


def test_empty_plugin_root_fails_open() -> None:
    _assert_degraded(_run_hook(None, empty_root=True))


def test_missing_script_in_existing_root_fails_open() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _assert_degraded(_run_hook(Path(tmp)))


def test_present_script_runs_without_degraded_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_hook(Path(tmp), script="print('status ok')\n")
        assert result.returncode == 0, result.stderr
        assert "status ok" in result.stdout
        assert "status_bar: unavailable" not in result.stdout


def test_python_unavailable_fails_open() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_hook(Path(tmp), script="print('should not run')\n", python_available=False)
        _assert_degraded(result)
        assert "python" in result.stdout.lower()
        assert "should not run" not in result.stdout


def test_runtime_failure_fails_open_without_traceback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_hook(Path(tmp), script="import sys\nprint('partial')\nsys.exit(1)\n")
        _assert_degraded(result)


def test_paths_with_spaces_and_unicode_are_safe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plugin_root = Path(tmp) / "plugin with spaces" / "한글"
        result = _run_hook(plugin_root, script="print('path ok')\n")
        assert result.returncode == 0, result.stderr
        assert "path ok" in result.stdout
        assert "status_bar: unavailable" not in result.stdout


def test_stale_version_delete_and_current_version_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "plugins" / "cache" / "japan-recruit-ai-agent"
        old_root = cache / "1.6.0"
        current_root = cache / "1.6.2"

        assert "old" in _run_hook(old_root, script="print('old')\n").stdout
        shutil.rmtree(old_root)
        _assert_degraded(_run_hook(old_root))
        assert "current" in _run_hook(current_root, script="print('current')\n").stdout


def test_launcher_has_no_cache_repair_or_network_command() -> None:
    command, command_windows = _hook_commands()
    combined = f"{command}\n{command_windows}"
    for forbidden in ("Remove-Item", "Invoke-WebRequest", "curl ", "git ", "rm "):
        assert forbidden not in combined
    assert "Test-Path -LiteralPath" in command_windows
    assert "Get-Command python" in command_windows
    assert "$LASTEXITCODE" in command_windows
    assert 'python3 "${CLAUDE_PLUGIN_ROOT}' not in command
    assert '[ ! -f "$status_bar" ]' in command
    assert "command -v python3" in command


def run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} hook lifecycle tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
