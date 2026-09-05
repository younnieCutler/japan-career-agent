#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PYTHON = process.env.PYTHON || "python";
const TIMEOUT_MS = 15_000;
const sleep = (milliseconds) => new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate.includes("/") && existsSync(candidate)) return candidate;
    const result = spawnSync("which", [candidate], { encoding: "utf8" });
    if (result.status === 0 && result.stdout.trim()) return result.stdout.trim();
  }
  throw new Error(`Chrome/Chromium not found; checked: ${candidates.join(", ")}`);
}

function initializeVault(vault) {
  const code = [
    "from pathlib import Path",
    "import sys",
    'sys.path.insert(0, str(Path.cwd() / "skills" / "career-agent"))',
    "from vault import initialize_vault",
    "initialize_vault(Path(sys.argv[1]))",
  ].join("; ");
  const result = spawnSync(PYTHON, ["-c", code, vault], {
    cwd: ROOT,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, `vault initialization failed:\n${result.stderr || result.stdout}`);
}

async function launchGui(vault) {
  const child = spawn(
    PYTHON,
    [
      "skills/career-agent/career_agent.py",
      "ui",
      "--vault",
      vault,
      "--no-browser",
      "--port",
      "0",
      "--format",
      "json",
    ],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"] },
  );
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });

  const readline = createInterface({ input: child.stdout });
  const line = await new Promise((resolveLine, rejectLine) => {
    const timer = setTimeout(() => {
      rejectLine(new Error(`GUI process did not announce a URL within ${TIMEOUT_MS}ms\n${stderr}`));
    }, TIMEOUT_MS);
    timer.unref();
    readline.once("line", (value) => {
      clearTimeout(timer);
      resolveLine(value.trim());
    });
    child.once("exit", (code, signal) => {
      clearTimeout(timer);
      rejectLine(new Error(`GUI process exited before ready (${code ?? signal})\n${stderr}`));
    });
  });

  const prefix = "Japan Career Agent GUI: ";
  assert.ok(line.startsWith(prefix), `unexpected GUI ready line: ${line}`);
  const url = line.slice(prefix.length);
  const parsed = new URL(url);
  assert.equal(parsed.hostname, "127.0.0.1", `GUI must bind loopback only: ${url}`);
  assert.ok(parsed.hash.includes("t="), `GUI URL is missing bootstrap token: ${url}`);
  return { child, readline, url, stderr: () => stderr };
}

async function waitForDevToolsPort(userDataDir) {
  const marker = join(userDataDir, "DevToolsActivePort");
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (existsSync(marker)) {
      const [port] = readFileSync(marker, "utf8").trim().split(/\r?\n/);
      if (port && Number.isInteger(Number(port))) return Number(port);
    }
    await sleep(50);
  }
  throw new Error("Chrome did not expose a DevTools port");
}

class CdpClient {
  constructor(url) {
    this.url = url;
    this.nextId = 0;
    this.pending = new Map();
    this.exceptions = [];
  }

  async connect() {
    this.socket = new WebSocket(this.url);
    await Promise.race([
      once(this.socket, "open"),
      new Promise((_, reject) => setTimeout(() => reject(new Error("DevTools WebSocket timeout")), TIMEOUT_MS)),
    ]);
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(`${pending.method}: ${message.error.message}`));
        else pending.resolve(message.result);
        return;
      }
      if (message.method === "Runtime.exceptionThrown") {
        const details = message.params?.exceptionDetails || {};
        this.exceptions.push(details.exception?.description || details.text || "Runtime.exceptionThrown");
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.nextId;
    return new Promise((resolveCommand, rejectCommand) => {
      const timer = setTimeout(() => {
        if (this.pending.delete(id)) rejectCommand(new Error(`${method} timed out`));
      }, TIMEOUT_MS);
      timer.unref();
      this.pending.set(id, {
        method,
        resolve: (value) => { clearTimeout(timer); resolveCommand(value); },
        reject: (error) => { clearTimeout(timer); rejectCommand(error); },
      });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    }
    return result.result?.value;
  }

  async waitFor(expression, label) {
    const deadline = Date.now() + TIMEOUT_MS;
    let lastError = null;
    while (Date.now() < deadline) {
      try {
        const value = await this.evaluate(expression);
        if (value) return value;
      } catch (error) {
        // Navigation destroys the old execution context. Retry until the new document is ready.
        lastError = error;
      }
      await sleep(100);
    }
    throw new Error(`timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ""}`);
  }

  close() {
    this.socket?.close();
  }
}

async function launchChrome() {
  const userDataDir = mkdtempSync(join(tmpdir(), "jca-browser-e2e-chrome-"));
  const child = spawn(
    findChrome(),
    [
      "--headless=new",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--no-sandbox",
      "--remote-debugging-port=0",
      `--user-data-dir=${userDataDir}`,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const port = await waitForDevToolsPort(userDataDir);
  const response = await fetch(`http://127.0.0.1:${port}/json/list`);
  assert.equal(response.status, 200, `DevTools target listing failed: ${response.status}`);
  const targets = await response.json();
  const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
  assert.ok(page, `Chrome exposed no debuggable page target: ${JSON.stringify(targets)}`);
  return { child, userDataDir, webSocketDebuggerUrl: page.webSocketDebuggerUrl, stderr: () => stderr };
}

async function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGKILL");
  await Promise.race([once(child, "exit"), sleep(3_000)]);
}

async function main() {
  const workDir = mkdtempSync(join(tmpdir(), "jca-browser-e2e-"));
  const vault = join(workDir, "vault");
  let gui;
  let chrome;
  let cdp;

  try {
    initializeVault(vault);
    gui = await launchGui(vault);
    chrome = await launchChrome();
    cdp = new CdpClient(chrome.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Input.setIgnoreInputEvents", { ignore: false });

    const navigation = await cdp.send("Page.navigate", { url: gui.url });
    assert.ok(!navigation.errorText, `initial GUI navigation failed: ${navigation.errorText}`);

    const boot = await cdp.waitFor(
      `(() => {
        const main = document.querySelector("#main-content");
        if (!document.querySelector(".workspace") || !main || main.innerText.trim().length < 2) return null;
        if (location.hash) return null;
        return { path: location.pathname, text: main.innerText.trim() };
      })()`,
      "React workspace boot with consumed bootstrap token",
    );
    assert.equal(boot.path, "/");

    const careerTarget = await cdp.waitFor(
      `(() => {
        const labels = new Set(["경력", "経歴", "Career"]);
        const element = [...document.querySelectorAll("body *")].find((node) => {
          if (node.children.length || !labels.has(node.textContent.trim())) return false;
          const rect = node.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
      })()`,
      "visible Career navigation item",
    );
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mousePressed", x: careerTarget.x, y: careerTarget.y, button: "left", clickCount: 1,
    });
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mouseReleased", x: careerTarget.x, y: careerTarget.y, button: "left", clickCount: 1,
    });

    const career = await cdp.waitFor(
      `(() => {
        const main = document.querySelector("#main-content");
        if (location.pathname !== "/career" || !document.querySelector(".workspace")) return null;
        if (!main || main.innerText.trim().length < 2) return null;
        return { path: location.pathname, text: main.innerText.trim() };
      })()`,
      "Career route after real pointer click",
    );
    assert.equal(career.path, "/career");
    assert.notEqual(career.text, boot.text, "Career navigation did not replace the Home screen");

    await cdp.send("Page.reload", { ignoreCache: true });
    const reloaded = await cdp.waitFor(
      `(() => {
        const main = document.querySelector("#main-content");
        if (document.readyState !== "complete" || location.pathname !== "/career") return null;
        if (!document.querySelector(".workspace") || !main || main.innerText.trim().length < 2) return null;
        if (location.hash) return null;
        return main.innerText.trim();
      })()`,
      "deep-linked Career route after full browser reload",
    );
    assert.ok(reloaded.length > 1);
    assert.deepEqual(cdp.exceptions, [], `browser runtime exceptions:\n${cdp.exceptions.join("\n")}`);

    console.log("browser E2E: PASS");
    console.log("  - single-use bootstrap token opened a real browser session and disappeared from the URL");
    console.log("  - React workspace rendered against the real local GUI server");
    console.log("  - pointer click navigated Home -> Career through the committed browser bundle");
    console.log("  - full reload preserved the /career deep link and authenticated browser session");
  } catch (error) {
    if (gui?.stderr()) console.error(`GUI stderr:\n${gui.stderr()}`);
    if (chrome?.stderr()) console.error(`Chrome stderr:\n${chrome.stderr()}`);
    throw error;
  } finally {
    cdp?.close();
    gui?.readline.close();
    await stopChild(chrome?.child);
    await stopChild(gui?.child);
    if (chrome?.userDataDir) rmSync(chrome.userDataDir, { recursive: true, force: true, maxRetries: 3 });
    rmSync(workDir, { recursive: true, force: true, maxRetries: 3 });
  }
}

await main();
