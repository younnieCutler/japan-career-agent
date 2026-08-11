"""Installable launcher for the Career Agent runtime.

The runtime itself is not a Python package and is not imported from here. It is a directory of
flat modules that this launcher puts on `sys.path`, exactly as running the script from a clone
does. Keeping that arrangement is what lets the wheel ship the same files the plugin ships.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    # Read from the installed distribution rather than repeating the number here. The release
    # version already lives in six files kept in step by a check; a seventh copy that nothing
    # compares would be the one free to be wrong.
    __version__ = version("japan-career-agent")
except PackageNotFoundError:  # running from a source checkout, not an install
    __version__ = "0+unknown"
