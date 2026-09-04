# japan-career-agent (npm)

Installer for [japan-career-agent](https://github.com/younnieCutler/japan-career-agent). This
package contains no runtime: the agent is a Python program, and this command installs and runs the
matching release from PyPI.

```bash
npx japan-career-agent
```

Equivalent, without npm:

```bash
uvx japan-career-agent
```

## What it needs

[uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/), to run the tool in its own
environment rather than in a Python you depend on. If neither is present, the command explains how
to install one and changes nothing.

Python 3.11 or newer is required: `uv` downloads a matching interpreter by itself, `pipx` uses one
that is already installed.

## What it does not do

- No `postinstall` hook. `npm install` runs nothing from this package.
- No download, unpacking or checksum logic of its own; the only artefact fetched is the PyPI wheel,
  verified by the installer that fetches it.
- No version drift: the PyPI version installed always equals this package's version.

Career data stays on the machine. Nothing is uploaded.

MIT licensed.
