#!/usr/bin/env node
"use strict";

/**
 * npm-side entry point for japan-career-agent.
 *
 * This package contains an installer and no runtime. The agent is a Python program published to
 * PyPI, and everything below does one thing: run that exact version through a Python tool runner,
 * forwarding arguments and the exit code unchanged. Nothing is reimplemented in Node, so npx and
 * uvx cannot drift apart in behaviour — they end up executing the same wheel.
 *
 * Two deliberate constraints:
 *
 *   - No `postinstall` hook. `npm install` runs nothing from this package; work happens only when
 *     the user actually invokes the command. Install-time code execution is the standard shape of
 *     an npm supply-chain incident, and an installer is exactly the package where it would be
 *     least noticed.
 *   - The version is pinned to this package's own version, never left floating. `npx
 *     japan-career-agent@2.1.0` that quietly installs some other release would make the version
 *     the user asked for meaningless; CI keeps this file's version equal to the release version.
 */

const { spawnSync } = require("node:child_process");
const { version } = require("../package.json");

const PACKAGE = "japan-career-agent";
const SPEC = `${PACKAGE}==${version}`;

// Ordered by how little they disturb the machine: `uv` and `pipx` both run a tool in its own
// isolated environment, so neither writes into whatever Python the user depends on for work.
const RUNNERS = [
  { command: "uv", args: ["tool", "run", "--from", SPEC, PACKAGE] },
  { command: "pipx", args: ["run", "--spec", SPEC, PACKAGE] },
];

function isAvailable(command) {
  const probe = spawnSync(command, ["--version"], { stdio: "ignore", shell: false });
  return probe.error === undefined && probe.status === 0;
}

function missingRunnerMessage() {
  return [
    `${PACKAGE} runs on Python, and neither uv nor pipx was found on PATH.`,
    "",
    "Install one of them, then run this command again:",
    "",
    "  # uv (single binary, recommended)",
    "  curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS and Linux",
    "  powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"   # Windows",
    "",
    "  # pipx",
    "  python3 -m pip install --user pipx",
    "",
    `Or install the agent directly, without npm: uvx ${PACKAGE}`,
    "",
    "Nothing was installed or changed on this machine.",
  ].join("\n");
}

function main() {
  const forwarded = process.argv.slice(2);
  const runner = RUNNERS.find((candidate) => isAvailable(candidate.command));

  if (runner === undefined) {
    // Deliberately not falling back to `pip install` into the user's default interpreter: this
    // command was asked to run a tool, not to modify an environment the user did not name.
    process.stderr.write(`${missingRunnerMessage()}\n`);
    process.exit(1);
  }

  const result = spawnSync(runner.command, [...runner.args, ...forwarded], {
    stdio: "inherit",
    shell: false,
  });

  if (result.error !== undefined) {
    process.stderr.write(`${PACKAGE}: could not start ${runner.command}: ${result.error.message}\n`);
    process.exit(1);
  }
  // A tool killed by a signal has no exit status. Reporting 1 keeps the failure visible instead of
  // letting `npx ... && next-step` continue as though the run had succeeded.
  process.exit(result.status === null ? 1 : result.status);
}

main();
