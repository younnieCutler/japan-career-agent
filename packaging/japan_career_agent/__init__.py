"""Installable launcher for the Career Agent runtime.

The runtime itself is not a Python package and is not imported from here. It is a directory of
flat modules that this launcher puts on `sys.path`, exactly as running the script from a clone
does. Keeping that arrangement is what lets the wheel ship the same files the plugin ships.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "2.1.0"
