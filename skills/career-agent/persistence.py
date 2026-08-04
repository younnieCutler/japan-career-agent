"""Canonical JSON/TOML/JSONL persistence boundary for the runtime split."""

from runtime import (  # noqa: F401
    append_jsonl,
    atomic_write_text,
    read_json,
    read_jsonl,
    read_toml,
    write_json,
    write_jsonl,
    write_toml,
)
