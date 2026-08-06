"""Run one fresh, read-only Codex Judge session over the frozen v2 corpus."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--judge", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    judge = args.judge.resolve()
    corpus = args.corpus.resolve()
    schema = args.schema.resolve()
    prompt = (
        "You are the candidate LLM Judge v2.\n"
        "Use only the procedure and fixed corpus delimited below. Do not inspect any other file, "
        "including expected.yml, logs, git history, or repository source. Do not use tools, web, "
        "apps, or subagents. Return only the JSON object required by the procedure.\n\n"
        "<JUDGE_PROCEDURE>\n"
        + judge.read_text(encoding="utf-8")
        + "\n</JUDGE_PROCEDURE>\n\n<FIXED_CORPUS>\n"
        + corpus.read_text(encoding="utf-8")
        + "\n</FIXED_CORPUS>\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc)
    codex_binary = shutil.which("codex.cmd") or shutil.which("codex") or "codex.cmd"
    command = [
        codex_binary,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "--model",
        "gpt-5.6-terra",
        "-c",
        "model_reasoning_effort=\"medium\"",
        "-C",
        str(root),
        "--output-schema",
        str(schema),
        "-o",
        str(args.output.resolve()),
        "-",
    ]
    completed = subprocess.run(
        command,
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended = dt.datetime.now(dt.timezone.utc)
    metadata = {
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": command,
        "model": "gpt-5.6-terra",
        "reasoning_effort": "medium",
        "ephemeral": True,
        "sandbox": "read-only",
        "user_config": "ignored",
        "judge_sha256": sha256(judge),
        "corpus_sha256": sha256(corpus),
        "schema_sha256": sha256(schema),
        "returncode": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", errors="replace"),
        "stderr": completed.stderr.decode("utf-8", errors="replace"),
        "output_exists": args.output.exists(),
        "output_sha256": sha256(args.output) if args.output.exists() else None,
    }
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
