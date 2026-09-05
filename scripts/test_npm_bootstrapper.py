#!/usr/bin/env python3
"""Hold the npm package to the self-contained global-install contract."""

from __future__ import annotations

import json
import os
import re
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
RUNTIME = NPM_DIR / "lib" / "runtime.js"
INSTALL_TIME_HOOKS = ("preinstall", "install", "postinstall", "preuninstall", "postuninstall", "prepare")


def _package() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _release_version() -> str:
    return json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


class NpmBootstrapperContractTests(unittest.TestCase):
    def test_only_install_hook_prepares_the_private_runtime(self) -> None:
        scripts = _package().get("scripts", {})
        present = {name: scripts[name] for name in INSTALL_TIME_HOOKS if name in scripts}
        self.assertEqual(present, {"postinstall": "node bin/install-runtime.js"})

    def test_ships_only_bootstrap_code_not_generated_runtime(self) -> None:
        package = _package()
        self.assertEqual(
            sorted(package["files"]),
            [
                "README.md",
                "THIRD_PARTY_NOTICES.md",
                "bin/cli.js",
                "bin/install-runtime.js",
                "lib/runtime.js",
            ],
        )
        self.assertEqual(package["bin"], {"japan-career-agent": "bin/cli.js"})
        self.assertNotIn(".runtime", package["files"])
        self.assertEqual(package.get("dependencies", {}), {})

    def test_version_matches_the_release(self) -> None:
        self.assertEqual(_package()["version"], _release_version())

    def test_identity_matches_the_python_package(self) -> None:
        package = _package()
        self.assertEqual(package["name"], "japan-career-agent")
        self.assertEqual(package["license"], "MIT")

    def test_private_runtime_is_pinned_and_checksum_guarded(self) -> None:
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('const UV_VERSION = "0.12.7";', source)
        self.assertNotIn("/latest/", source)
        self.assertNotIn("pipx", source)
        self.assertNotIn("pip install", source)
        self.assertGreaterEqual(len(set(re.findall(r'[0-9a-f]{64}', source))), 8)
        self.assertIn("checksum mismatch", source)
        self.assertIn("UV_MANAGED_PYTHON", source)
        self.assertIn("UV_TOOL_DIR", source)
        self.assertIn("UV_PYTHON_INSTALL_DIR", source)

    def test_launcher_uses_only_the_private_runtime(self) -> None:
        source = CLI.read_text(encoding="utf-8")
        self.assertIn("ensureRuntime", source)
        self.assertNotIn("pipx", source)
        self.assertNotIn("isAvailable", source)
        self.assertNotIn("RUNNERS", source)

    @unittest.skipIf(shutil.which("npm") is None, "npm is not available")
    @unittest.skipIf(
        sys.platform == "win32",
        "the local no-network fixture uses a POSIX shell stub; Windows is covered by the repository CI contracts",
    )
    def test_global_npm_install_needs_no_preinstalled_python_runner(self) -> None:
        """Install exactly as a user does, with a fake private uv replacing network access.

        The fake uv only implements `uv tool install`; if the npm launcher still probes PATH for uv,
        pipx, or Python this test cannot pass. The generated Python launcher exits 42 so argument and
        exit-code forwarding are observable through npm's global shim.
        """
        with tempfile.TemporaryDirectory(prefix="japan-career-npm-global-") as temporary:
            root = Path(temporary)
            prefix = root / "prefix"
            cache = root / "npm-cache"
            stub = root / "uv"
            recorded = root / "argv.txt"
            stub.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "--version" ]; then echo "uv 0.12.7"; exit 0; fi\n'
                'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
                '  mkdir -p "$UV_TOOL_BIN_DIR"\n'
                '  cat > "$UV_TOOL_BIN_DIR/japan-career-agent" <<\'SH\'\n'
                "#!/bin/sh\n"
                'printf "%s\\n" "$@" > "$JCA_RECORDED"\n'
                "exit 42\n"
                "SH\n"
                '  chmod +x "$UV_TOOL_BIN_DIR/japan-career-agent"\n'
                "  exit 0\n"
                "fi\n"
                "exit 9\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            npm_env = dict(os.environ)
            npm_env["npm_config_cache"] = str(cache)
            npm_env["JAPAN_CAREER_UV_BIN"] = str(stub)
            npm_env["JCA_RECORDED"] = str(recorded)

            subprocess.run(
                [shutil.which("npm"), "pack", "--silent", "--pack-destination", str(root), str(NPM_DIR)],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=npm_env,
                check=True,
            )
            tarballs = sorted(root.glob("*.tgz"))
            self.assertEqual(len(tarballs), 1)
            subprocess.run(
                [
                    shutil.which("npm"),
                    "install",
                    "-g",
                    "--silent",
                    "--no-audit",
                    "--no-fund",
                    "--prefix",
                    str(prefix),
                    str(tarballs[0]),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=npm_env,
                check=True,
            )

            shim = prefix / "bin" / "japan-career-agent"
            self.assertTrue(shim.exists(), "npm did not create the global command")
            markers = list(prefix.rglob("install.json"))
            self.assertEqual(len(markers), 1, "postinstall did not prepare exactly one private runtime")

            result = subprocess.run(
                [str(shim), "doctor", "--format", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=root,
                env=npm_env,
                check=False,
            )
            self.assertEqual(result.returncode, 42, result.stderr)
            forwarded = recorded.read_text(encoding="utf-8")
            self.assertIn("doctor", forwarded)
            self.assertIn("--format", forwarded)
            self.assertIn("json", forwarded)


if __name__ == "__main__":
    unittest.main(verbosity=0)
