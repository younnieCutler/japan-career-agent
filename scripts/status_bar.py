#!/usr/bin/env python3
"""Career status bar — deterministic context injected before every turn.

Reads data/pipeline.yml and data/rules.yml from the working directory and prints a
short key-value block. Run by the UserPromptSubmit hook (hooks/hooks.json); prints
nothing when there is no pipeline, so non-job-search sessions stay clean.

Two rules govern this file, both from the same finding: a model trusts a status bar
almost unconditionally, so an inaccurate one is worse than none at all.

  1. Every value is computed here, in code, from the files on disk. No LLM summarises
     the history into these numbers, and no value is estimated.
  2. Output is key-value lines, never prose. A paragraph has to be re-read and parsed;
     that is the scanning problem the status bar exists to remove.

The bar is a lossy projection: it precomputes only the dimensions listed below. Adding
a question the suite needs answered means adding the field here first — treat it like a
schema change, not a summary.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STAGE_LABELS = {
    0: "自己分析",
    1: "書類準備",
    2: "企業研究",
    3: "応募・書類",
    4: "面接",
    5: "内定",
    6: "退職交渉",
    7: "入社",
}

# Calibration compares predicted tier against the stage actually reached. Below this many
# closed entries the comparison is noise, and reporting it anyway would invite the user to
# explain a pattern that is not there.
CALIBRATION_MIN_SAMPLE = 3

# Number of most recent entries checked for the demo_slot diversity warning.
DIVERSITY_WINDOW = 5

# Update notice. Auto-update is off by default for third-party marketplaces, so an install
# can sit on an old version indefinitely — and from 1.1.0 a stale install has no status bar
# and no execution gate at all, with nothing running that could say so.
#
# The check never blocks a prompt: this process only reads a cache file, and refreshes it by
# detaching a background copy of itself. A cold install therefore shows the notice from the
# following prompt, not this one.
UPDATE_URL = (
    "https://raw.githubusercontent.com/younnieCutler/japan-recruit-ai-agent"
    "/main/.claude-plugin/plugin.json"
)
CHECK_INTERVAL_SECONDS = 24 * 3600
PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def update_check_disabled() -> bool:
    return os.environ.get("JAPAN_RECRUIT_NO_UPDATE_CHECK") == "1"


def cache_file() -> Path:
    """CLAUDE_PLUGIN_DATA survives plugin updates; the cache is useless if it does not."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.japan-recruit-agent")
    return Path(base) / "update-check.json"


def local_version() -> str | None:
    try:
        manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
        return manifest.get("version")
    except Exception:
        return None


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def is_newer(remote: str | None, local: str | None) -> bool:
    if not remote or not local:
        return False
    try:
        return version_tuple(remote) > version_tuple(local)
    except Exception:
        return False


def update_line(local: str | None, cache: dict) -> str | None:
    remote = cache.get("latest")
    if not is_newer(remote, local):
        return None
    return (
        f"update: v{remote} available (installed {local}) — "
        "claude plugin update japan-recruit-ai-agent@japan-recruit-ai-agent, then restart"
    )


def read_cache() -> dict:
    try:
        return json.loads(cache_file().read_text())
    except Exception:
        return {}


def refresh_cache() -> int:
    """Fetch the published version and cache it. Runs detached; prints nothing, ever."""
    import urllib.request

    latest = None
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=10) as response:
            latest = json.loads(response.read().decode("utf-8")).get("version")
    except Exception:
        pass  # offline, rate-limited, repo moved — the notice is not worth an error
    try:
        path = cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"checked_at": time.time()}
        if latest:
            payload["latest"] = latest
        else:
            # Keep the previous answer rather than forgetting it over one failed fetch.
            payload["latest"] = read_cache().get("latest")
        path.write_text(json.dumps(payload))
    except Exception:
        pass
    return 0


def maybe_refresh(cache: dict) -> None:
    if update_check_disabled():
        return
    if time.time() - float(cache.get("checked_at") or 0) < CHECK_INTERVAL_SECONDS:
        return
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--refresh-cache"],
            stdout=subprocess.DEVNULL,  # anything on stdout would land in the model's context
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def stage_label(stage: object) -> str:
    if isinstance(stage, int) and stage in STAGE_LABELS:
        return f"{stage} {STAGE_LABELS[stage]}"
    return str(stage)


def days_until(deadline: str, today: dt.date) -> int | None:
    try:
        return (dt.date.fromisoformat(deadline) - today).days
    except (TypeError, ValueError):
        return None


def active_companies(pipeline: dict) -> list[dict]:
    return [c for c in pipeline.get("companies") or [] if not c.get("closed")]


def closed_companies(pipeline: dict) -> list[dict]:
    return [c for c in pipeline.get("companies") or [] if c.get("closed")]


def unchecked_items(company: dict) -> list[dict]:
    return [i for i in company.get("action_items") or [] if not i.get("checked")]


def pipeline_line(pipeline: dict) -> str:
    active = active_companies(pipeline)
    closed = closed_companies(pipeline)
    if not active:
        return f"pipeline: 0 active / {len(closed)} closed"
    by_stage: dict[str, int] = {}
    for company in active:
        label = stage_label(company.get("stage"))
        by_stage[label] = by_stage.get(label, 0) + 1
    breakdown = ", ".join(f"{label} {n}" for label, n in sorted(by_stage.items()))
    return f"pipeline: {len(active)} active ({breakdown}) / {len(closed)} closed"


def deadline_line(pipeline: dict, today: dt.date) -> str | None:
    """Nearest upcoming deadline only. Listing every date recreates the scanning problem."""
    dated = []
    for company in active_companies(pipeline):
        days = days_until(company.get("deadline"), today)
        if days is not None:
            dated.append((days, company))
    if not dated:
        return None
    days, company = min(dated, key=lambda pair: pair[0])
    name = company.get("name") or company.get("slug") or "?"
    detail = company.get("status") or company.get("next_action") or ""
    when = "TODAY" if days == 0 else (f"D{days:+d}" if days > 0 else f"{-days}d OVERDUE")
    return f"deadline: {name} {company.get('deadline')} ({when}) {detail}".rstrip()


def gate_lines(pipeline: dict) -> list[str]:
    """Unchecked action items, per company, and what they block.

    This is the whole reason the status bar exists. The documented failure mode is a
    checklist that was written and then never opened before the interview it was written
    for; a count the model cannot miss is the countermeasure.
    """
    lines = []
    blocked = []
    for company in active_companies(pipeline):
        pending = unchecked_items(company)
        if not pending:
            continue
        name = company.get("name") or company.get("slug") or "?"
        blocked.append(name)
        preview = "; ".join(i.get("text", "") for i in pending[:3])
        lines.append(f"unchecked_actions[{name}]: {len(pending)} — {preview}")
    if blocked:
        lines.append(
            "gate: interview-prep generation BLOCKED for "
            + ", ".join(blocked)
            + " until the items above are checked"
            " (the user runs: python3 scripts/check_action.py <slug> <id>)"
        )
    return lines


def rules_lines(rules: dict) -> list[str]:
    active = [r for r in rules.get("rules") or [] if r.get("status") == "active"]
    if not active:
        return []
    lines = [f"active_rules: {len(active)}"]
    for rule in active:
        lines.append(f"  - {rule.get('text', '')}")
    return lines


def calibration_line(pipeline: dict) -> str:
    scored = [c for c in closed_companies(pipeline) if c.get("reached_stage") is not None]
    if len(scored) < CALIBRATION_MIN_SAMPLE:
        need = CALIBRATION_MIN_SAMPLE - len(scored)
        return f"calibration: {len(scored)} scored outcomes (need {need} more)"
    return f"calibration: {len(scored)} scored outcomes — `scripts/calibrate.py` available"


def diversity_line(pipeline: dict) -> str | None:
    """Warn when every recent application competes on the same axis.

    Carries no score and changes no ranking. It reports one observable fact: the user has
    only entered 選考 that evaluate verbal explanation, so an artifact they already own has
    had nowhere to be shown.
    """
    companies = (pipeline.get("companies") or [])[-DIVERSITY_WINDOW:]
    known = [c for c in companies if c.get("demo_slot") in {"yes", "company_test", "no"}]
    if len(known) < DIVERSITY_WINDOW:
        return None
    if all(c.get("demo_slot") == "no" for c in known):
        return (
            f"diversity: last {len(known)} applications all demo_slot=no — every 選考 so far "
            "evaluates verbal explanation only"
        )
    return None


def build_status(
    pipeline: dict, rules: dict, today: dt.date, update: str | None = None
) -> str:
    """Assemble the block. Returns "" when there is nothing to report."""
    if not (pipeline.get("companies") or []):
        return ""
    lines = [pipeline_line(pipeline)]
    for line in (deadline_line(pipeline, today),):
        if line:
            lines.append(line)
    lines.extend(gate_lines(pipeline))
    lines.extend(rules_lines(rules))
    lines.append(calibration_line(pipeline))
    diversity = diversity_line(pipeline)
    if diversity:
        lines.append(diversity)
    if update:
        lines.append(update)
    return "<career_status>\n" + "\n".join(lines) + "\n</career_status>"


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        # Surfaced rather than swallowed: a gate that disappears silently is worse than a
        # gate that reports it is down.
        print(
            "<career_status>\nstatus_bar: unavailable — PyYAML not installed "
            "(pip install pyyaml). Execution gate and deadlines are NOT being checked.\n"
            "</career_status>"
        )
        raise SystemExit(0)
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(
            f"<career_status>\nstatus_bar: data/{path.name} is not valid YAML ({exc.__class__.__name__}). "
            "Execution gate and deadlines are NOT being checked until it parses.\n</career_status>"
        )
        raise SystemExit(0)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    argv = list(argv or [])
    if argv and argv[0] == "--refresh-cache":
        return refresh_cache()
    root = Path(argv[0]) if argv else Path.cwd()
    pipeline = load_yaml(root / "data" / "pipeline.yml")
    if not pipeline:
        return 0
    rules = load_yaml(root / "data" / "rules.yml")
    cache = {} if update_check_disabled() else read_cache()
    block = build_status(pipeline, rules, dt.date.today(), update_line(local_version(), cache))
    if block:
        print(block)
    maybe_refresh(cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
