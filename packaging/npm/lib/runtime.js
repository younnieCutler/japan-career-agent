"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { version } = require("../package.json");

const PACKAGE = "japan-career-agent";
const SPEC = `${PACKAGE}==${version}`;
const UV_VERSION = "0.12.7";
const MAX_ARCHIVE_BYTES = 40 * 1024 * 1024;
const PACKAGE_ROOT = path.resolve(__dirname, "..");
const RUNTIME_ROOT = path.join(PACKAGE_ROOT, ".runtime");
const UV_DIR = path.join(RUNTIME_ROOT, "uv");
const TOOL_DIR = path.join(RUNTIME_ROOT, "tools");
const TOOL_BIN_DIR = path.join(RUNTIME_ROOT, "bin");
const PYTHON_DIR = path.join(RUNTIME_ROOT, "python");
const CACHE_DIR = path.join(RUNTIME_ROOT, "cache");
const MARKER = path.join(RUNTIME_ROOT, "install.json");

const UV_ARCHIVES = Object.freeze({
  "darwin-arm64": {
    asset: "uv-aarch64-apple-darwin.tar.gz",
    sha256: "127ebdda7ad953cdf198e964b570ea5771b85467ea93eb7cb6d6f8e6f55408f3",
  },
  "darwin-x64": {
    asset: "uv-x86_64-apple-darwin.tar.gz",
    sha256: "06b8ae1da8c2661c5434507a66f8c2b0b835933bf955b5958a9ac357a37d1959",
  },
  "win32-arm64": {
    asset: "uv-aarch64-pc-windows-msvc.zip",
    sha256: "1611d0f4be72b0a354ad9a6ae954093dd4c91e93e36b8b490326a05a039ffe14",
  },
  "win32-x64": {
    asset: "uv-x86_64-pc-windows-msvc.zip",
    sha256: "bf1518af459a3915511a11fdc6e2f43ef9a2afa138b9d498eeb9642fe9d85218",
  },
  "linux-arm64-gnu": {
    asset: "uv-aarch64-unknown-linux-gnu.tar.gz",
    sha256: "66393193038dd7eb108abd7a218d9cec04ac70ab98242b0720fa94de19223b7c",
  },
  "linux-x64-gnu": {
    asset: "uv-x86_64-unknown-linux-gnu.tar.gz",
    sha256: "788f18abea7c5f55d6216e4f5613fd89d4d59b631efeec117b2b07fe72f1da21",
  },
  "linux-arm64-musl": {
    asset: "uv-aarch64-unknown-linux-musl.tar.gz",
    sha256: "6dcf60e3c085de88ace3671b949ca99f0652be561ff5627f0d21394140f041db",
  },
  "linux-x64-musl": {
    asset: "uv-x86_64-unknown-linux-musl.tar.gz",
    sha256: "3d64d44ed67da7908dc7f5c4d64ebb44bad326fa17f8a0a52fc9a7793017bbe1",
  },
});

function isMusl() {
  if (process.platform !== "linux") return false;
  try {
    const report = process.report?.getReport?.();
    return !report?.header?.glibcVersionRuntime;
  } catch {
    return false;
  }
}

function platformKey() {
  if (!["x64", "arm64"].includes(process.arch)) {
    throw new Error(`unsupported CPU architecture: ${process.arch}`);
  }
  if (process.platform === "linux") {
    return `linux-${process.arch}-${isMusl() ? "musl" : "gnu"}`;
  }
  if (process.platform === "darwin" || process.platform === "win32") {
    return `${process.platform}-${process.arch}`;
  }
  throw new Error(`unsupported platform: ${process.platform}`);
}

function platformArchive() {
  const key = platformKey();
  const archive = UV_ARCHIVES[key];
  if (!archive) throw new Error(`no pinned uv archive for ${key}`);
  return archive;
}

function allowedDownloadHost(hostname) {
  return hostname === "github.com" ||
    hostname === "release-assets.githubusercontent.com" ||
    hostname === "objects.githubusercontent.com" ||
    hostname.endsWith(".githubusercontent.com");
}

function fetchBuffer(url, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) {
      reject(new Error("too many redirects while downloading uv"));
      return;
    }
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" || !allowedDownloadHost(parsed.hostname)) {
      reject(new Error(`refusing uv download from ${parsed.origin}`));
      return;
    }
    const request = https.get(parsed, {
      headers: { "User-Agent": `${PACKAGE}/${version}` },
    }, (response) => {
      const status = response.statusCode || 0;
      if (status >= 300 && status < 400 && response.headers.location) {
        const next = new URL(response.headers.location, parsed);
        response.resume();
        fetchBuffer(next.toString(), redirects + 1).then(resolve, reject);
        return;
      }
      if (status !== 200) {
        response.resume();
        reject(new Error(`uv download returned HTTP ${status}`));
        return;
      }
      const declared = Number(response.headers["content-length"] || 0);
      if (declared > MAX_ARCHIVE_BYTES) {
        response.resume();
        reject(new Error(`uv archive exceeds ${MAX_ARCHIVE_BYTES} bytes`));
        return;
      }
      const chunks = [];
      let received = 0;
      response.on("data", (chunk) => {
        received += chunk.length;
        if (received > MAX_ARCHIVE_BYTES) {
          request.destroy(new Error(`uv archive exceeds ${MAX_ARCHIVE_BYTES} bytes`));
          return;
        }
        chunks.push(chunk);
      });
      response.on("end", () => resolve(Buffer.concat(chunks)));
    });
    request.on("error", reject);
    request.setTimeout(60_000, () => request.destroy(new Error("uv download timed out")));
  });
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio || "inherit",
    shell: false,
    env: options.env || process.env,
    encoding: options.encoding,
  });
  if (result.error) {
    throw new Error(`could not start ${command}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`);
  }
  return result;
}

function findUv(root) {
  const wanted = process.platform === "win32" ? "uv.exe" : "uv";
  const stack = [root];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const candidate = path.join(current, entry.name);
      if (entry.isDirectory()) stack.push(candidate);
      else if (entry.isFile() && entry.name === wanted) return candidate;
    }
  }
  throw new Error(`pinned uv archive did not contain ${wanted}`);
}

function extractArchive(archivePath, destination, asset) {
  fs.mkdirSync(destination, { recursive: true });
  if (asset.endsWith(".zip")) {
    const script = "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath $env:JCA_ARCHIVE -DestinationPath $env:JCA_DEST -Force";
    const env = { ...process.env, JCA_ARCHIVE: archivePath, JCA_DEST: destination };
    const powershell = process.env.ComSpec ? "powershell.exe" : "powershell";
    run(powershell, ["-NoProfile", "-NonInteractive", "-Command", script], { env });
    return;
  }
  run("tar", ["-xzf", archivePath, "-C", destination]);
}

function privateUvPath() {
  return path.join(UV_DIR, process.platform === "win32" ? "uv.exe" : "uv");
}

async function installUv() {
  const archive = platformArchive();
  const url = `https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${archive.asset}`;
  const bytes = await fetchBuffer(url);
  const digest = crypto.createHash("sha256").update(bytes).digest("hex");
  if (digest !== archive.sha256) {
    throw new Error(`uv checksum mismatch for ${archive.asset}`);
  }

  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "japan-career-uv-"));
  try {
    const archivePath = path.join(temporary, archive.asset);
    const extracted = path.join(temporary, "extracted");
    fs.writeFileSync(archivePath, bytes, { mode: 0o600 });
    extractArchive(archivePath, extracted, archive.asset);
    const source = findUv(extracted);
    fs.mkdirSync(UV_DIR, { recursive: true });
    const target = privateUvPath();
    fs.copyFileSync(source, target);
    if (process.platform !== "win32") fs.chmodSync(target, 0o755);
    return target;
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

function uvVersionMatches(uv) {
  const result = spawnSync(uv, ["--version"], {
    stdio: ["ignore", "pipe", "ignore"],
    shell: false,
    encoding: "utf8",
  });
  return result.error === undefined &&
    result.status === 0 &&
    String(result.stdout || "").trim().startsWith(`uv ${UV_VERSION}`);
}

async function ensureUv() {
  const override = process.env.JAPAN_CAREER_UV_BIN;
  if (override) {
    if (!fs.existsSync(override)) throw new Error("JAPAN_CAREER_UV_BIN does not exist");
    return override;
  }
  const existing = privateUvPath();
  if (fs.existsSync(existing) && uvVersionMatches(existing)) return existing;
  return installUv();
}

function launcherCandidates() {
  const names = process.platform === "win32"
    ? [`${PACKAGE}.exe`, `${PACKAGE}.cmd`, PACKAGE]
    : [PACKAGE];
  return names.map((name) => path.join(TOOL_BIN_DIR, name));
}

function findLauncher() {
  return launcherCandidates().find((candidate) => fs.existsSync(candidate)) || null;
}

function markerIsCurrent() {
  const launcher = findLauncher();
  if (!launcher || !fs.existsSync(MARKER)) return false;
  try {
    const marker = JSON.parse(fs.readFileSync(MARKER, "utf8"));
    return marker.package === PACKAGE &&
      marker.version === version &&
      marker.uv === UV_VERSION;
  } catch {
    return false;
  }
}

function runtimeEnvironment() {
  return {
    ...process.env,
    UV_TOOL_DIR: TOOL_DIR,
    UV_TOOL_BIN_DIR: TOOL_BIN_DIR,
    UV_PYTHON_INSTALL_DIR: PYTHON_DIR,
    UV_CACHE_DIR: CACHE_DIR,
    UV_MANAGED_PYTHON: "1",
    UV_NO_MODIFY_PATH: "1",
    UV_NO_PROGRESS: "1",
    UV_ISOLATED: "1",
  };
}

async function installPythonRuntime() {
  fs.mkdirSync(RUNTIME_ROOT, { recursive: true });
  const uv = await ensureUv();

  fs.rmSync(TOOL_DIR, { recursive: true, force: true });
  fs.rmSync(TOOL_BIN_DIR, { recursive: true, force: true });
  fs.mkdirSync(TOOL_BIN_DIR, { recursive: true });

  run(uv, ["tool", "install", "--force", "--managed-python", "--no-config", "--python", "3.13", SPEC], {
    env: runtimeEnvironment(),
  });
  const launcher = findLauncher();
  if (!launcher) {
    throw new Error("private Python runtime installed without a japan-career-agent launcher");
  }
  fs.writeFileSync(MARKER, `${JSON.stringify({
    package: PACKAGE,
    version,
    uv: UV_VERSION,
  }, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.rmSync(CACHE_DIR, { recursive: true, force: true });
  return launcher;
}

async function ensureRuntime(options = {}) {
  if (!options.force && markerIsCurrent()) return findLauncher();
  return installPythonRuntime();
}

module.exports = {
  PACKAGE,
  RUNTIME_ROOT,
  SPEC,
  UV_ARCHIVES,
  UV_VERSION,
  ensureRuntime,
  platformArchive,
};
