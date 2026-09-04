# japan-career-agent (npm)

Self-contained npm installer for [japan-career-agent](https://github.com/younnieCutler/japan-career-agent).

```bash
npm install -g japan-career-agent
japan-career-agent
```

That is the normal installation path. The user does not need to install Python, uv, or pipx.

The underlying product supports Python 3.11 or newer, while the npm path installs and owns its managed interpreter internally. No system Python is required.

## What happens during install

The npm package has no npm runtime dependencies. Its `postinstall` step:

1. selects a pinned uv 0.12.7 archive for the current x64/arm64 macOS, Linux, or Windows platform;
2. downloads it only from uv's official GitHub release and verifies the hard-coded SHA-256 digest;
3. stores uv under this npm package's private `.runtime/` directory;
4. uses that private uv with managed-Python-only settings to install the exact matching
   `japan-career-agent` PyPI release into the same private runtime.

It does not run a downloaded shell installer, use global pip, or modify an existing Python
environment. npm's own global command shim is the only PATH entry created by the normal install.

If npm lifecycle scripts were intentionally disabled, the first `japan-career-agent` invocation
repairs the same private runtime before handing over.

## One-off and direct alternatives

```bash
npx japan-career-agent
uvx japan-career-agent
uv tool install japan-career-agent
pipx install japan-career-agent
```

`npx` uses the same self-contained npm package in its temporary cache. The uv/pipx commands are
advanced direct-Python alternatives, not prerequisites.

Career data stays on the machine. Nothing is uploaded.

MIT licensed.
