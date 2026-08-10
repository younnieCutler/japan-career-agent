"""Console entry point: put the bundled runtime on `sys.path` and hand over to it.

This module deliberately does nothing else. Argument parsing, routing and every command belong
to `runtime.main`, so an installed wheel and a clone run the same code down to the same line —
a second argument parser here would be a second place for the two to disagree.

The layout inside the wheel mirrors the repository:

    japan_career_agent/_shared/
    japan_career_agent/skills/career-agent/

because `runtime.py` finds its sibling `_shared` tree by walking three parents up from its own
file. Preserving the relative positions is what allows the runtime modules to be shipped
unmodified.
"""

from __future__ import annotations

import sys
from pathlib import Path

MINIMUM_PYTHON = (3, 11)
BUNDLE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = BUNDLE_ROOT / "skills" / "career-agent"


def _python_too_old() -> str | None:
    """Return an actionable message, or None when the interpreter is supported.

    Neither `uvx` nor `npx` provisions a Python for the user, so an unsupported interpreter is a
    normal outcome of a first run. Saying which version is required beats the `SyntaxError` from
    deep inside a runtime module that an unguarded import would produce.
    """
    if sys.version_info >= MINIMUM_PYTHON:
        return None
    required = ".".join(str(part) for part in MINIMUM_PYTHON)
    running = ".".join(str(part) for part in sys.version_info[:3])
    return (
        f"japan-career-agent requires Python {required} or newer, but this interpreter is "
        f"{running} ({sys.executable}).\n"
        f"Install a newer Python, then run the command again — for example with uv:\n"
        f"  uv python install {required}\n"
        f"  uvx --python {required} japan-career-agent doctor"
    )


def main(argv: list[str] | None = None) -> int:
    message = _python_too_old()
    if message is not None:
        print(message, file=sys.stderr)
        return 1

    if not RUNTIME_ROOT.is_dir():
        print(
            f"japan-career-agent is installed but its runtime is missing at {RUNTIME_ROOT}.\n"
            "Reinstall the package; a partial install cannot be repaired from here.",
            file=sys.stderr,
        )
        return 1

    # Front of the path, matching how the runtime resolves its flat imports when the script is
    # run directly from a clone. `runtime` adds the `_shared` tree itself.
    runtime_path = str(RUNTIME_ROOT)
    if runtime_path not in sys.path:
        sys.path.insert(0, runtime_path)

    import runtime

    return runtime.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
