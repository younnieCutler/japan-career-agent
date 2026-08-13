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
              python_available: bool = True, empty_root: bool = False,
              language: str = "ko") -> subprocess.CompletedProcess[str]:
    command, command_windows = _hook_commands()
    env = os.environ.copy()
    env["JAPAN_CAREER_LANGUAGE"] = language
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
    assert result.stdout.count("<career_status>") == 1
    assert result.stdout.count("</career_status>") == 1
    assert "<career_status>" in result.stdout
    assert "경력 상태를 표시할 수 없음" in result.stdout
    assert "실행 조건과 마감을 확인하지 못했습니다." in result.stdout
    assert "can't open file" not in output
    assert "Traceback" not in output


def _assert_normal(result: subprocess.CompletedProcess[str], marker: str) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("<career_status>") == 1
    assert result.stdout.count("</career_status>") == 1
    assert marker in result.stdout
    assert "경력 상태를 표시할 수 없음" not in result.stdout


def _normal_script(marker: str) -> str:
    return f"print('<career_status>\\n{marker}\\n</career_status>')\n"


def test_missing_script_fails_open() -> None:
    with tempfile.TemporaryDirectory(prefix="plugins cache ") as tmp:
        stale_root = Path(tmp) / "plugins" / "cache" / "japan-career-agent" / "1.6.0"
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
        _assert_normal(_run_hook(Path(tmp), script=_normal_script("status ok")), "status ok")


def test_python_unavailable_fails_open() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_hook(Path(tmp), script="print('should not run')\n", python_available=False)
        _assert_degraded(result)
        assert "should not run" not in result.stdout


def test_runtime_failure_fails_open_without_traceback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_hook(Path(tmp), script="import sys\nprint('partial')\nsys.exit(1)\n")
        _assert_degraded(result)
        assert "partial" not in result.stdout


def test_degraded_copy_follows_the_requested_language_without_internal_reason() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        japanese = _run_hook(Path(tmp), language="ja")
        english = _run_hook(Path(tmp), language="en")
    assert "ステータス表示を利用できません" in japanese.stdout
    assert "実行条件と期限を確認できませんでした" in japanese.stdout
    assert "Career status unavailable" in english.stdout
    for output in (japanese.stdout, english.stdout):
        assert "plugin script unavailable" not in output
        assert "runtime failure" not in output


def test_paths_with_spaces_and_unicode_are_safe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plugin_root = Path(tmp) / "plugin with spaces" / "한글"
        _assert_normal(_run_hook(plugin_root, script=_normal_script("path ok")), "path ok")


def test_stale_version_delete_and_current_version_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "plugins" / "cache" / "japan-career-agent"
        old_root = cache / "1.6.0"
        current_root = cache / "1.6.2"

        _assert_normal(_run_hook(old_root, script=_normal_script("old")), "old")
        shutil.rmtree(old_root)
        _assert_degraded(_run_hook(old_root))
        _assert_normal(_run_hook(current_root, script=_normal_script("current")), "current")


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
    assert 'status_output="$(python3 "$status_bar" 2>/dev/null)"' in command
    assert "Out-String" in command_windows
    assert "$statusOutput" in command_windows


def run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} hook lifecycle tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
