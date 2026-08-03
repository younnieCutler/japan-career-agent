#!/usr/bin/env python3
"""End-to-end check that approve(), status_bar.py, check_action.py and workflow observation reporting agree on
data/pipeline.yml's shape.

Each component's own unit tests build their fixtures by hand, so a root-schema mismatch between
career_agent.py's writer and the other three readers passed every unit test while silently
hiding every company career-agent ever wrote from status_bar, check_action and calibrate. This
test wires the real CLI to the real reader functions instead of a hand-built fixture, so a future
shape mismatch fails here instead of only in a user's actual vault.

Run: python3 scripts/test_pipeline_integration.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "_shared"))

import status_bar  # noqa: E402
import check_action  # noqa: E402
import calibrate  # noqa: E402
import pipeline_store  # noqa: E402


def run_agent(vault: Path, cwd: Path, command: str, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        text=True, encoding="utf-8", capture_output=True, check=False, cwd=str(cwd),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    import json
    return json.loads(result.stdout)


def test_approve_then_status_bar_check_action_calibrate_agree():
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        workdir = Path(tmp) / "work"
        unrelated = Path(tmp) / "unrelated"
        workdir.mkdir()
        unrelated.mkdir()
        run_agent(vault, workdir, "init")

        proposed = run_agent(vault, workdir, "run", "--mode", "chat", "--track", "chuto",
                              "--message", "内定をもらった")
        run_agent(vault, unrelated, "approve", proposed["proposal"]["id"],
                  "--workspace", str(workdir), "--evidence", "内定をもらった", "--company", "GAO")

        path = workdir / "data" / "pipeline.yml"
        assert not (unrelated / "data" / "pipeline.yml").exists()
        pipeline = status_bar.load_yaml(path)

        # status_bar must see the company career-agent just wrote.
        active = status_bar.active_companies(pipeline)
        assert any(c["slug"] == "gao" for c in active), pipeline

        # check_action must be able to find and check an item on the same entry.
        pipeline_store.mutate(path, lambda data: {
            **data,
            "companies": [
                {**c, "action_items": [{"id": "a1", "text": "履歴書を送る", "checked": False}]}
                if c["slug"] == "gao" else c
                for c in data["companies"]
            ],
        })
        loaded = check_action.load(path)
        check_action.check(loaded, "gao", "a1", path)
        reloaded = pipeline_store.load(path)
        gao = next(c for c in reloaded["companies"] if c["slug"] == "gao")
        assert gao["action_items"][0]["checked"] is True, gao

        # calibrate must see the same entry once it's closed with a reached_stage.
        pipeline_store.mutate(path, lambda data: {
            **data,
            "companies": [
                {**c, "closed": True, "reached_stage": 6} if c["slug"] == "gao" else c
                for c in data["companies"]
            ],
        })
        final = pipeline_store.load(path)
        closed = calibrate.closed_companies(final)
        assert any(c["slug"] == "gao" and c["reached_stage"] == 6 for c in closed), closed


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} pipeline integration tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
