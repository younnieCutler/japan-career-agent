#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const { ensureRuntime, PACKAGE } = require("../lib/runtime");

async function main() {
  let launcher;
  try {
    launcher = await ensureRuntime();
  } catch (error) {
    process.stderr.write(
      `${PACKAGE}: local runtime setup failed: ${error.message}\n` +
      `Re-run "npm install -g ${PACKAGE}" after checking network access and permissions.\n`
    );
    process.exit(1);
  }

  const result = spawnSync(launcher, process.argv.slice(2), {
    stdio: "inherit",
    shell: false,
  });
  if (result.error) {
    process.stderr.write(`${PACKAGE}: could not start the installed runtime: ${result.error.message}\n`);
    process.exit(1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

main();
