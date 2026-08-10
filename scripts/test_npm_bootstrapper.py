#!/usr/bin/env python3
"""Hold the npm bootstrapper to the two promises that make it safe to publish.

The npm package is an installer, so the interesting failures are not functional. They are: it grew
a hook that runs code at `npm install` time, or its version drifted away from the release, so
`npx japan-career-agent@X` quietly installs something other than X. Both are invisible in a passing
smoke test and both are caught here.

Node is already a repository test dependency (`skills/jiko-bunseki/tests/test_checklist_runtime.js`),
so the script is executed rather than only read.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPM_DIR = ROOT / "packaging" / "npm"
PACKAGE_JSON = NPM_DIR / "package.json"
CLI = NPM_DIR / "bin" / "cli.js"
INSTALL_TIME_HOOKS = ("preinstall", "install", "postinstall", "preuninstall", "postuninstall", "prepare")


def _package() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _release_version() -> str:
    return json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def _isolated_env(path_dir: str, home: str) -> dict[str, str]:
    """A PATH holding only what the test planted, while Node still has what it needs to start.

    `SystemRoot` is not optional on Windows — a process started without it fails before reaching
    any of the behaviour under test, which would look like the bootstrapper failing correctly.
    """
    environment = {"PATH": path_dir, "HOME": home}
    for inherited in ("SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "PATHEXT"):
        value = os.environ.get(inherited)
        if value is not None:
            environment[inherited] = value
    return environment


class NpmBootstrapperContractTests(unittest.TestCase):
    def test_declares_no_install_time_hook(self) -> None:
        scripts = _package().get("scripts", {})
        present = sorted(name for name in INSTALL_TIME_HOOKS if name in scripts)
        self.assertEqual(present, [], f"npm package must not run code at install time: {present}")

    def test_ships_only_the_installer(self) -> None:
        package = _package()
        self.assertEqual(sorted(package["files"]), ["README.md", "bin/cli.js"])
        self.assertEqual(package["bin"], {"japan-career-agent": "bin/cli.js"})

    def test_version_matches_the_release(self) -> None:
        self.assertEqual(_package()["version"], _release_version())

    def test_identity_matches_the_python_package(self) -> None:
        package = _package()
        self.assertEqual(package["name"], "japan-career-agent")
        self.assertEqual(package["license"], "MIT")

    @unittest.skipIf(shutil.which("node") is None, "node is not available")
    def test_fails_with_instructions_when_no_runner_exists(self) -> None:
        """With an empty PATH there is no uv and no pipx, which is a first run on a fresh machine.

        The requirement is that it says what to install and states that nothing was changed — an
        unexplained non-zero exit here is the difference between a user installing uv and a user
        concluding the tool is broken.
        """
        with tempfile.TemporaryDirectory(prefix="japan-career-npm-") as temporary:
            result = subprocess.run(
                [shutil.which("node"), str(CLI), "doctor"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=temporary,
                env=_isolated_env(temporary, temporary),
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        message = result.stderr
        self.assertIn("uv", message)
        self.assertIn("pipx", message)
        self.assertIn("Nothing was installed", message)

    @unittest.skipIf(shutil.which("node") is None, "node is not available")
    @unittest.skipIf(
        sys.platform == "win32",
        # Since the CVE-2024-27980 fix, Node refuses to spawn a .cmd or .bat without `shell: true`,
        # and a stub runner on Windows can only be one of those. The behaviour under test is
        # platform-independent JavaScript, and the real runners there are uv.exe and pipx.exe,
        # which spawn normally — so what is lost is the stub, not the guarantee.
        "a stub runner on Windows would have to be a .cmd, which Node will not spawn without a shell",
    )
    def test_forwards_arguments_and_exit_code_to_the_runner(self) -> None:
        """A stub `uv` on PATH stands in for the real one so the hand-off itself is observable.

        This is the part that cannot be read off the source with confidence: that the arguments the
        user typed arrive after the package spec, and that the runner's exit code is what npx
        reports rather than a zero from the wrapper.
        """
        with tempfile.TemporaryDirectory(prefix="japan-career-npm-stub-") as temporary:
            stub_dir = Path(temporary)
            recorded = stub_dir / "argv.txt"
            stub = stub_dir / "uv"
            stub.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "--version" ]; then echo "uv 0.0.0-stub"; exit 0; fi\n'
                f'printf "%s\\n" "$@" > "{recorded}"\n'
                "exit 42\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            result = subprocess.run(
                [shutil.which("node"), str(CLI), "doctor", "--format", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=temporary,
                env=_isolated_env(str(stub_dir), temporary),
                check=False,
            )
            self.assertEqual(result.returncode, 42, result.stderr)
            forwarded = recorded.read_text(encoding="utf-8")
        self.assertIn(f"japan-career-agent=={_release_version()}", forwarded)
        self.assertIn("doctor", forwarded)
        self.assertIn("--format", forwarded)


if __name__ == "__main__":
    unittest.main(verbosity=0)
