#!/usr/bin/env node
"use strict";

const { ensureRuntime, PACKAGE } = require("../lib/runtime");

async function main() {
  process.stdout.write(`${PACKAGE}: preparing its private runtime...\n`);
  try {
    await ensureRuntime({ force: true });
  } catch (error) {
    process.stderr.write(`${PACKAGE}: install failed: ${error.message}\n`);
    process.exit(1);
  }
  process.stdout.write(`${PACKAGE}: ready. Run "${PACKAGE}".\n`);
}

main();
