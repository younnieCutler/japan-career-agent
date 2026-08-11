#!/usr/bin/env python3
"""Smoke-test the built wheel the way `uvx` and `pipx` install it.

`scripts/test_release_install.py` covers the plugin bundle; this covers the other distribution
channel. The wheel relocates two trees that are not Python packages, so the failure it guards
against is specific: the runtime resolves `_shared`, `references/routing.yml` and `templates/`
from paths relative to its own file, and a packaging change that moves either tree leaves an
install that imports cleanly and then cannot find its own data.

Everything therefore runs from a directory unrelated to the repository, because a check run
inside the checkout passes even when the wheel ships nothing at all.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "japan_career_agent"
CONSOLE_SCRIPTS = ("japan-career-agent", "career-agent")
REQUIRED_MEMBERS = (
    f"{PACKAGE_NAME}/cli.py",
    f"{PACKAGE_NAME}/_shared/pipeline_store.py",
    f"{PACKAGE_NAME}/skills/career-agent/runtime.py",
    f"{PACKAGE_NAME}/skills/career-agent/references/routing.yml",
    f"{PACKAGE_NAME}/skills/career-agent/templates/standard-chuto.html",
    f"{PACKAGE_NAME}/skills/career-agent/gui/server.py",
    f"{PACKAGE_NAME}/skills/career-agent/gui/views_read.py",
    f"{PACKAGE_NAME}/skills/career-agent/gui/static/bootstrap.js",
    f"{PACKAGE_NAME}/skills/career-agent/gui/static/style.css",
)


def _venv_bin(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _executable(venv: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return _venv_bin(venv) / f"{name}{suffix}"


def _run(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr or result.stdout}")
    return result.stdout


def _run_json(command: list[str], *, cwd: Path) -> dict[str, object]:
    value = json.loads(_run(command, cwd=cwd))
    if not isinstance(value, dict):
        raise RuntimeError(f"{command[0]} did not return an object")
    return value


def build_wheel(output_dir: Path) -> Path:
    """Build without isolation so the hash-pinned backend in requirements-dev.lock is used."""
    try:
        import build  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "the wheel build backend is missing; install it with "
            "`python -m pip install --require-hashes -r requirements-dev.lock`"
        ) from exc
    _run(
        [sys.executable, "-m", "build", "--no-isolation", "--wheel", "--outdir", str(output_dir), str(ROOT)],
        cwd=ROOT,
    )
    wheels = sorted(output_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one wheel, found {[w.name for w in wheels]}")
    return wheels[0]


def check_contents(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = [member for member in REQUIRED_MEMBERS if member not in names]
    if missing:
        raise RuntimeError(f"wheel is missing runtime files: {missing}")
    # Tests and caches are repository artefacts. Shipping them would also mean a stray
    # `__pycache__` from a local run could travel into a published artefact.
    stowaways = sorted(
        name
        for name in names
        if Path(name).name.startswith("test_")
        or {"tests", "__pycache__"} & set(Path(name).parts)
    )
    if stowaways:
        raise RuntimeError(f"wheel ships files that are not part of an install: {stowaways[:5]}")


def check_version(wheel: Path) -> str:
    plugin_version = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    expected = f"{PACKAGE_NAME}-{plugin_version}-"
    if not wheel.name.startswith(expected):
        raise RuntimeError(f"wheel {wheel.name} does not carry plugin version {plugin_version}")
    return plugin_version


def install_and_smoke(wheel: Path, root: Path) -> None:
    venv = root / "venv"
    # The runtime dependencies are already installed in the environment running this check, and
    # inheriting them keeps the smoke offline: a fresh venv would have to reach PyPI.
    _run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], cwd=root)
    _run(
        [str(_executable(venv, "python")), "-m", "pip", "install", "--quiet", "--no-deps", str(wheel)],
        cwd=root,
    )

    workspace = root / "workspace"
    workspace.mkdir()
    vault = root / "vault"

    agent = str(_executable(venv, CONSOLE_SCRIPTS[0]))

    # A setup that still needs input prints the command to run next. From an installed wheel that
    # command must name the installed program: `python skills/career-agent/career_agent.py` is a
    # file the user does not have, so the suggestion would be a dead end.
    incomplete = subprocess.run(
        [agent, "setup", "--vault", str(root / "hint-vault"), "--format", "json"],
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    hint = json.loads(incomplete.stdout).get("next", "")
    if "career_agent.py" in hint or CONSOLE_SCRIPTS[0] not in hint:
        raise RuntimeError(f"installed setup suggests a command that does not exist: {hint!r}")

    setup = _run_json(
        [agent, "setup", "--vault", str(vault), "--track", "chuto", "--target-role", "Data Engineer", "--format", "json"],
        cwd=workspace,
    )
    if setup.get("mode") != "setup" or not (vault / "02-state").is_dir():
        raise RuntimeError("setup did not create a vault from the installed wheel")

    for script in CONSOLE_SCRIPTS:
        executable = _executable(venv, script)
        if not executable.exists():
            raise RuntimeError(f"console script {script} was not installed")
        # Both names are documented: `uvx japan-career-agent` needs the script to match the
        # package name, and `career-agent` is the short form. A silent rename breaks one install
        # instruction while the other keeps working, so both are exercised.
        doctor = _run_json([str(executable), "doctor", "--vault", str(vault), "--format", "json"], cwd=workspace)
        if doctor.get("mode") != "doctor":
            raise RuntimeError(f"{script} doctor did not return doctor mode")

    # Routing is loaded from `references/routing.yml`, resolved relative to the runtime module.
    # A chat turn is the cheapest command that fails outright when that file is not found.
    chat = _run_json(
        [agent, "run", "--mode", "chat", "--vault", str(vault), "--message", "이직 준비를 시작하고 싶어요", "--format", "json"],
        cwd=workspace,
    )
    if chat.get("mode") != "chat":
        raise RuntimeError("chat routing failed from the installed wheel")

    # `status` and `guided` are the two commands a first-run user reaches for next, and both cross
    # more of the runtime than `doctor` does: status projects the workspace, guided assembles a menu
    # from several read paths at once. Running them here is what proves the wheel carries the whole
    # application layer rather than the modules the earlier commands happen to touch.
    status = _run_json([agent, "status", "--vault", str(vault), "--format", "json"], cwd=workspace)
    if status.get("profile", {}).get("track") != "chuto":
        raise RuntimeError("status did not project the profile from the installed wheel")

    guided = _run_json([agent, "guided", "--vault", str(vault), "--format", "json"], cwd=workspace)
    if guided.get("mode") != "guided" or not guided.get("guided", {}).get("available_actions"):
        raise RuntimeError("guided returned no actions from the installed wheel")

    templates = _run(
        [
            str(_executable(venv, "python")),
            "-c",
            "import sys;"
            f"import {PACKAGE_NAME}.cli as cli;"
            "sys.path.insert(0, str(cli.RUNTIME_ROOT));"
            "import render;"
            "print(' '.join(render.available_templates(cli.RUNTIME_ROOT)))",
        ],
        cwd=workspace,
    ).split()
    if "standard-chuto" not in templates or "simple-print" not in templates:
        raise RuntimeError(f"built-in templates are not reachable from the install: {templates}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        type=Path,
        help="write the built wheel to this directory instead of a temporary one",
    )
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="japan-career-wheel-smoke-") as temporary:
            root = Path(temporary)
            wheel = build_wheel(args.keep.resolve() if args.keep else root / "dist")
            check_contents(wheel)
            version = check_version(wheel)
            install_and_smoke(wheel, root)
    except (OSError, RuntimeError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"wheel install smoke: FAIL ({exc})")
        return 1
    print(f"wheel install smoke: PASS (v{version}: build, contents, both scripts, setup, routing, templates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
