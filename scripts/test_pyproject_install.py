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
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_version import canonical_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "japan_career_agent"
DIST_NAME = "japan-career-agent"
PUBLISH_VISIBILITY_ATTEMPTS = 5
PUBLISH_VISIBILITY_DELAY_SECONDS = 20
CONSOLE_SCRIPTS = ("japan-career-agent", "career-agent")
REQUIRED_MEMBERS = (
    f"{PACKAGE_NAME}/cli.py",
    f"{PACKAGE_NAME}/_shared/pipeline_store.py",
    f"{PACKAGE_NAME}/skills/career-agent/runtime.py",
    f"{PACKAGE_NAME}/skills/career-agent/references/routing.yml",
    f"{PACKAGE_NAME}/skills/career-agent/templates/standard-chuto.html",
    f"{PACKAGE_NAME}/skills/career-agent/gui/server.py",
    f"{PACKAGE_NAME}/skills/career-agent/gui/tanaoroshi.py",
    f"{PACKAGE_NAME}/skills/career-agent/gui/views_read.py",
    f"{PACKAGE_NAME}/skills/career-agent/gui/static/bootstrap.js",
    # The built React bundle. It is committed under `static/app/` rather than a `dist/` the
    # wheel would not ship, so a broken build is caught here rather than by a user with no Node.
    f"{PACKAGE_NAME}/skills/career-agent/gui/static/app/app.js",
    f"{PACKAGE_NAME}/skills/career-agent/gui/static/app/app.css",
    f"{PACKAGE_NAME}/skills/career-agent/sessions.py",
)
# Skill-First Gate C: every domain Skill's SKILL.md must ship, or `skill-open` for it in an
# installed CLI would name a Skill with nothing on disk to point a host at. Kept as a literal
# list, not a glob over the repository, so a Skill directory added without a `pyproject.toml`
# update fails this check instead of shipping silently.
PACKAGED_SKILL_NAMES = (
    "career-agent", "career-document", "career-maintenance", "career-tanaoroshi",
    "company-battlecard", "debloat", "factchk", "hate", "hiring-manager-agent",
    "humanize-japanese-career", "jiko-bunseki", "job-seeker-agent", "kigyou-bunseki",
    "matching-simulator", "mock-interviewer", "readchk", "sip", "tenshoku-strategy",
)
REQUIRED_SKILL_MANIFESTS = tuple(
    f"{PACKAGE_NAME}/skills/{name}/SKILL.md" for name in PACKAGED_SKILL_NAMES
)


def _venv_bin(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _executable(venv: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return _venv_bin(venv) / f"{name}{suffix}"


def _run(command: list[str], *, cwd: Path) -> str:
    # `errors="replace"` is not cosmetic. A tool that writes a byte the declared encoding cannot
    # decode -- `python -m venv` on a Japanese Windows console emits cp932 on stderr -- kills the
    # reader thread inside subprocess, and `run()` then returns `stdout=None` with returncode 0 and
    # no exception. A caller reading that output gets None where it expected text, and a caller
    # merely checking the exit status sees a success that never produced anything.
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
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
    missing_skills = [member for member in REQUIRED_SKILL_MANIFESTS if member not in names]
    if missing_skills:
        raise RuntimeError(f"wheel is missing domain Skill manifests: {missing_skills}")
    # A shipped SKILL.md that references a missing file is a broken prompt a host cannot follow.
    # This walks the repository's own references/ trees rather than trusting a fixed list, so a
    # reference added to a Skill without a packaging change fails this check instead of shipping
    # a SKILL.md whose links 404 inside the installed wheel.
    missing_references = []
    for name in PACKAGED_SKILL_NAMES:
        references_dir = ROOT / "skills" / name / "references"
        if not references_dir.is_dir():
            continue
        for path in references_dir.rglob("*"):
            if path.is_file():
                member = f"{PACKAGE_NAME}/skills/{name}/references/{path.relative_to(references_dir).as_posix()}"
                if member not in names:
                    missing_references.append(member)
    if missing_references:
        raise RuntimeError(f"wheel is missing Skill reference files: {missing_references}")
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
    # Read from pyproject.toml, which owns the release version. The plugin manifest was read here
    # until it became a generated copy of that file; comparing a build against a copy of its own
    # input proves only that `sync_version.py` ran.
    version = canonical_version()
    expected = f"{PACKAGE_NAME}-{version}-"
    if not wheel.name.startswith(expected):
        raise RuntimeError(f"wheel {wheel.name} does not carry release version {version}")
    return version


def check_installed_tree(venv: Path) -> None:
    """Assert the installed package carries what `check_contents` asserts about the wheel.

    The same list, read from site-packages instead of a zip, so it can be pointed at an artifact
    this repository did not build -- the one a user actually downloads. A published release whose
    contents differ from what the checkout builds is invisible to every other check here.
    """
    # Derived here rather than printed by the venv's own interpreter. A child process writes paths
    # in the console encoding, and this repository's own temporary directories contain non-ASCII
    # user names, so the round trip through another encoding can hand back a path that does not
    # exist -- which reads as "every file is missing" rather than as the encoding fault it is.
    # The venv was created from this interpreter, so its layout is this interpreter's scheme.
    site = Path(sysconfig.get_paths(vars={"base": str(venv), "platbase": str(venv)})["purelib"])
    missing = [
        name for name in (*REQUIRED_MEMBERS, *REQUIRED_SKILL_MANIFESTS)
        if not (site / name).is_file()
    ]
    if missing:
        raise RuntimeError(f"the installed distribution is missing {len(missing)} file(s): {missing[:6]}")


def install_and_smoke(requirement: str, root: Path, *, inherit_site_packages: bool = True) -> None:
    venv = root / "venv"
    if inherit_site_packages:
        # The runtime dependencies are already installed in the environment running this check, and
        # inheriting them keeps the smoke offline: a fresh venv would have to reach PyPI.
        _run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], cwd=root)
        install = ["--no-deps", requirement]
    else:
        # Resolving from the index is the point in this mode: it is what a user's `pip install`
        # does, dependency metadata included.
        _run([sys.executable, "-m", "venv", str(venv)], cwd=root)
        install = [requirement]
    _run([str(_executable(venv, "python")), "-m", "pip", "install", "--quiet", *install], cwd=root)

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


def smoke_published(version: str, root: Path) -> None:
    """Run the same smoke against the artifact PyPI is actually serving.

    Everything else in this file proves that *this checkout* builds a working wheel. That says
    nothing about what `uvx japan-career-agent` downloads, and the two had drifted fifteen minor
    versions apart with the published wheel carrying neither the GUI nor most of the Skills. This
    is the check that notices.

    The retry is for index propagation only: a version can be accepted by the upload API a little
    before it is resolvable, so a release workflow running this immediately after publishing would
    otherwise fail on timing rather than on contents.
    """
    requirement = f"{DIST_NAME}=={version}"
    last: Exception | None = None
    for attempt in range(PUBLISH_VISIBILITY_ATTEMPTS):
        try:
            install_and_smoke(requirement, root, inherit_site_packages=False)
            check_installed_tree(root / "venv")
            return
        except RuntimeError as exc:
            if "No matching distribution" not in str(exc) and "no matching distribution" not in str(exc):
                raise
            last = exc
            shutil.rmtree(root / "venv", ignore_errors=True)
            if attempt + 1 < PUBLISH_VISIBILITY_ATTEMPTS:
                time.sleep(PUBLISH_VISIBILITY_DELAY_SECONDS)
    raise RuntimeError(f"{requirement} never became resolvable on the index: {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        type=Path,
        help="write the built wheel to this directory instead of a temporary one",
    )
    parser.add_argument(
        "--pypi",
        metavar="VERSION",
        help="smoke the published distribution at this version instead of a locally built wheel; "
        "requires network access, so the repository check matrix never passes it",
    )
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="japan-career-wheel-smoke-") as temporary:
            root = Path(temporary)
            if args.pypi:
                version = args.pypi
                smoke_published(version, root)
            else:
                wheel = build_wheel(args.keep.resolve() if args.keep else root / "dist")
                check_contents(wheel)
                version = check_version(wheel)
                install_and_smoke(wheel, root)
    except (OSError, RuntimeError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"wheel install smoke: FAIL ({exc})")
        return 1
    source = f"published {DIST_NAME}" if args.pypi else "build"
    print(f"wheel install smoke: PASS (v{version}: {source}, contents, both scripts, setup, routing, templates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
