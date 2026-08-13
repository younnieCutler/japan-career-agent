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

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

CAREER_AGENT_ROOT = Path(__file__).resolve().parent.parent / "skills" / "career-agent"
if str(CAREER_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CAREER_AGENT_ROOT))

from localization import domain_label, normalize_language  # noqa: E402


STATUS_TEXT = {
    "ko": {
        "pipeline": "지원 현황", "active": "진행 중", "closed": "종료", "deadline": "마감",
        "today": "오늘", "overdue": "기한 경과", "unchecked_actions": "미완료 작업",
        "shown": "표시", "total": "전체", "unchecked_action": "미완료 작업", "gate": "실행 조건",
        "blocked": "실행 불가", "active_rules": "적용 중 규칙", "showing": "표시 중",
        "remaining": "나머지", "workflow_observations": "전형 관찰 기록",
        "reached_entries": "도달 단계 기록", "available": "사용 가능", "diversity": "지원 다양성",
        "update": "업데이트", "installed": "설치 버전",
        "gate_sentence": "면접 준비 자료 생성 {blocked}: {companies}. 위 작업을 확인한 뒤 계속할 수 있습니다 (사용자 실행: python3 scripts/check_action.py <slug> <id>)",
        "calibration_sentence": "{count}개 {entries} — `scripts/calibrate.py` {available}",
        "diversity_sentence": "최근 {count}개 지원 모두 작업 결과물이나 실기 과제를 보여줄 기회가 없었습니다 — 지금까지 모든 전형이 말로 설명하는 역량만 평가합니다",
        "update_sentence": "v{remote} {available} ({installed} {local}) — claude plugin update japan-career-agent@japan-career-agent 실행 후 다시 시작",
        "yaml_missing": "상태 표시를 사용할 수 없음 — PyYAML이 설치되지 않아 실행 조건과 마감을 확인하지 못했습니다 (pip install pyyaml).",
        "yaml_invalid": "상태 표시를 사용할 수 없음 — data/{name} 형식이 올바른 YAML이 아니어서 실행 조건과 마감을 확인하지 못했습니다.",
    },
    "ja": {
        "pipeline": "応募状況", "active": "進行中", "closed": "終了", "deadline": "期限",
        "today": "本日", "overdue": "期限超過", "unchecked_actions": "未完了タスク",
        "shown": "表示", "total": "合計", "unchecked_action": "未完了タスク", "gate": "実行条件",
        "blocked": "実行不可", "active_rules": "適用中ルール", "showing": "表示中",
        "remaining": "残り", "workflow_observations": "選考観測", "reached_entries": "到達段階の記録",
        "available": "利用可能", "diversity": "応募の多様性", "update": "更新", "installed": "インストール済み",
        "gate_sentence": "面接準備資料の生成は{blocked}: {companies}。上のタスクを確認すると続行できます（ユーザーが実行: python3 scripts/check_action.py <slug> <id>）",
        "calibration_sentence": "{count}件の{entries} — `scripts/calibrate.py`を{available}",
        "diversity_sentence": "直近{count}件の応募では成果物や実技課題を見せる機会がありませんでした — これまでの選考は説明力のみを評価しています",
        "update_sentence": "v{remote}を{available}（{installed} {local}）— claude plugin update japan-career-agent@japan-career-agentを実行後に再起動",
        "yaml_missing": "ステータス表示を利用できません — PyYAMLが未インストールのため、実行条件と期限を確認できませんでした（pip install pyyaml）。",
        "yaml_invalid": "ステータス表示を利用できません — data/{name}が有効なYAMLではないため、実行条件と期限を確認できませんでした。",
    },
    "en": {
        "pipeline": "pipeline", "active": "active", "closed": "closed", "deadline": "deadline",
        "today": "TODAY", "overdue": "OVERDUE", "unchecked_actions": "unchecked_actions",
        "shown": "shown", "total": "total", "unchecked_action": "unchecked_action", "gate": "gate",
        "blocked": "BLOCKED", "active_rules": "active_rules", "showing": "showing",
        "remaining": "remaining", "workflow_observations": "workflow_observations",
        "reached_entries": "reached-stage entries", "available": "available", "diversity": "diversity",
        "update": "update", "installed": "installed",
        "gate_sentence": "interview-prep generation {blocked} for {companies} until the items above are checked (the user runs: python3 scripts/check_action.py <slug> <id>)",
        "calibration_sentence": "{count} {entries} — `scripts/calibrate.py` {available}",
        "diversity_sentence": "the last {count} applications offered no chance to show work samples or complete a practical task — every 選考 so far evaluates verbal explanation only",
        "update_sentence": "v{remote} {available} ({installed} {local}) — claude plugin update japan-career-agent@japan-career-agent, then restart",
        "yaml_missing": "status_bar: unavailable — PyYAML not installed (pip install pyyaml). Execution gate and deadlines are NOT being checked.",
        "yaml_invalid": "Status is unavailable because data/{name} is not valid YAML. Execution gates and deadlines were not checked.",
    },
}


def status_text(language: str, key: str, **values: Any) -> str:
    return STATUS_TEXT[normalize_language(language)][key].format(**values)


def status_language(explicit: str | None = None) -> str:
    """Use an explicit/env locale, then the configured Vault profile, without loading note bodies."""
    candidate = explicit or os.environ.get("JAPAN_CAREER_LANGUAGE")
    if candidate:
        return normalize_language(candidate)
    vault = os.environ.get("CAREER_VAULT")
    if vault:
        try:
            profile = tomllib.loads(
                (Path(vault).expanduser() / "02-state" / "career-state.toml").read_text(encoding="utf-8")
            )
            if profile.get("language"):
                return normalize_language(profile["language"])
        except (OSError, tomllib.TOMLDecodeError, TypeError):
            pass
    return "ko"

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
    "https://raw.githubusercontent.com/younnieCutler/japan-career-agent"
    "/main/.claude-plugin/plugin.json"
)
CHECK_INTERVAL_SECONDS = 24 * 3600
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
ACTION_CONTEXT_LIMIT = 3
RULE_CONTEXT_LIMIT = 3


def update_check_disabled() -> bool:
    """The 2.0.x name is still honoured: someone who opted out once should stay opted out.

    A renamed variable that silently stops working turns an explicit user decision back on
    without telling anyone, which is the one failure mode an opt-out cannot have.
    """
    return any(
        os.environ.get(name) == "1"
        for name in ("JAPAN_CAREER_NO_UPDATE_CHECK", "JAPAN_RECRUIT_NO_UPDATE_CHECK")
    )


def cache_file() -> Path:
    """CLAUDE_PLUGIN_DATA survives plugin updates; the cache is useless if it does not."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.japan-career-agent")
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


def update_line(local: str | None, cache: dict, *, language: str = "en") -> str | None:
    remote = cache.get("latest")
    if not is_newer(remote, local):
        return None
    return f"{status_text(language, 'update')}: " + status_text(
        language,
        "update_sentence",
        remote=remote,
        available=status_text(language, "available"),
        installed=status_text(language, "installed"),
        local=local,
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
        # ponytail: non-atomic write; a torn file just fails read_cache()'s broad except and
        # re-fetches next cycle. Regenerable cache, not canonical state — no lock/atomic needed.
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


def stage_label(stage: object, *, language: str = "en") -> str:
    if isinstance(stage, int) and not isinstance(stage, bool) and 0 <= stage <= 7:
        return f"{stage} {domain_label(language, 'status_stage', stage)}"
    return domain_label(language, "fact_state", "unknown")


def days_until(deadline: str, today: dt.date) -> int | None:
    try:
        return (dt.date.fromisoformat(deadline) - today).days
    except (TypeError, ValueError):
        return None


def active_companies(pipeline: dict) -> list[dict]:
    return [c for c in _company_entries(pipeline) if not c.get("closed")]


def closed_companies(pipeline: dict) -> list[dict]:
    return [c for c in _company_entries(pipeline) if c.get("closed")]


def unchecked_items(company: dict) -> list[dict]:
    items = company.get("action_items")
    if not isinstance(items, list):
        return []
    return [
        item for item in items
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and isinstance(item.get("checked"), bool)
        and not item["checked"]
    ]


def _company_entries(pipeline: object) -> list[dict]:
    if not isinstance(pipeline, dict):
        return []
    companies = pipeline.get("companies")
    if not isinstance(companies, list):
        return []
    return [company for company in companies if isinstance(company, dict)]


def pipeline_line(
    pipeline: dict, *, active: list[dict] | None = None, closed: list[dict] | None = None,
    language: str = "en",
) -> str:
    active = active if active is not None else active_companies(pipeline)
    closed = closed if closed is not None else closed_companies(pipeline)
    if not active:
        return (
            f"{status_text(language, 'pipeline')}: 0 {status_text(language, 'active')} / "
            f"{len(closed)} {status_text(language, 'closed')}"
        )
    by_stage: dict[str, int] = {}
    for company in active:
        label = stage_label(company.get("stage"), language=language)
        by_stage[label] = by_stage.get(label, 0) + 1
    breakdown = ", ".join(f"{label} {n}" for label, n in sorted(by_stage.items()))
    return (
        f"{status_text(language, 'pipeline')}: {len(active)} {status_text(language, 'active')} "
        f"({breakdown}) / {len(closed)} {status_text(language, 'closed')}"
    )


def _sanitize(text: Any, max_len: int = 200) -> str:
    if not isinstance(text, str):
        return ""
    val = str(text).replace("\r", " ").replace("\n", " ")
    val = val.replace("</career_status>", "[/career_status]").replace("<career_status>", "[career_status]")
    val = val.replace("</untrusted_career_data>", "[/untrusted_career_data]").replace("<untrusted_career_data>", "[untrusted_career_data]")
    val = val.replace("</", "[/").replace("<", "&lt;").replace(">", "&gt;")
    if len(val) <= max_len:
        return val
    cut = val[:max_len]
    # Do not leave a generated HTML entity such as `&lt` or `&gt` half-rendered.
    # If the boundary falls inside an entity, discard that incomplete entity before the ellipsis.
    entity_start = cut.rfind("&")
    if entity_start >= 0 and ";" not in cut[entity_start:]:
        cut = cut[:entity_start]
    return cut + "…"



def deadline_line(
    pipeline: dict, today: dt.date, *, active: list[dict] | None = None,
    language: str = "en",
) -> str | None:
    """Nearest upcoming deadline only. Listing every date recreates the scanning problem."""
    dated = []
    active = active if active is not None else active_companies(pipeline)
    for company in active:
        days = days_until(company.get("deadline"), today)
        if days is not None:
            dated.append((days, company))
    if not dated:
        return None
    days, company = min(dated, key=lambda pair: pair[0])
    name = _sanitize(company.get("name") or company.get("slug") or "?", 60)
    detail = _sanitize(company.get("status") or company.get("next_action") or "", 100)
    when = status_text(language, "today") if days == 0 else (
        f"D{days:+d}" if days > 0 else f"{-days}d {status_text(language, 'overdue')}"
    )
    return f"{status_text(language, 'deadline')}: {name} {company.get('deadline')} ({when}) {detail}".rstrip()


def _pending_action_rows(active: list[dict], today: dt.date) -> list[dict]:
    rows = []
    for company in active:
        for item in unchecked_items(company):
            deadline = item.get("deadline") or company.get("deadline")
            rows.append({
                "company": company,
                "item": item,
                "deadline": deadline,
                "days": days_until(deadline, today),
            })
    return sorted(
        rows,
        key=lambda row: (
            row["days"] is None,
            row["days"] if row["days"] is not None else 0,
            str(row["company"].get("slug") or row["company"].get("name") or ""),
            str(row["item"].get("id") or ""),
        ),
    )


def gate_lines(
    pipeline: dict, today: dt.date, *, active: list[dict] | None = None,
    language: str = "en",
) -> list[str]:
    """Show urgent unchecked actions while retaining every blocker.

    This is the whole reason the status bar exists. The documented failure mode is a
    checklist that was written and then never opened before the interview it was written
    for; the gate and total count cannot be compressed away. Only the most urgent action
    previews are rendered to keep repeated context small.
    """
    active = active if active is not None else active_companies(pipeline)
    rows = _pending_action_rows(active, today)
    if not rows:
        return []
    lines = [
        f"{status_text(language, 'unchecked_actions')}: {min(len(rows), ACTION_CONTEXT_LIMIT)} "
        f"{status_text(language, 'shown')} / {len(rows)} {status_text(language, 'total')}"
    ]
    for row in rows[:ACTION_CONTEXT_LIMIT]:
        company = row["company"]
        item = row["item"]
        name = _sanitize(company.get("name") or company.get("slug") or "?", 60)
        item_id = _sanitize(item.get("id") or "?", 40)
        text = _sanitize(item.get("text", ""), 100)
        lines.append(f"{status_text(language, 'unchecked_action')}[{name}]: {item_id} — {text}")

    blocked = []
    for company in active:
        pending = unchecked_items(company)
        if not pending:
            continue
        name = _sanitize(company.get("name") or company.get("slug") or "?", 60)
        blocked.append(f"{name} ({len(pending)})")
    if blocked:
        lines.append(
            f"{status_text(language, 'gate')}: "
            + status_text(
                language,
                "gate_sentence",
                blocked=status_text(language, "blocked"),
                companies=", ".join(blocked),
            )
        )
    return lines


def _rule_relevance(rule: dict, active_slugs: set[str]) -> int:
    if rule.get("source") == "self_authored":
        return 2
    supported_by = rule.get("supported_by")
    if isinstance(supported_by, list) and any(str(slug) in active_slugs for slug in supported_by):
        return 2
    # Preserve old active rules without routing metadata as a small fallback set; they are
    # not treated as more relevant than explicitly supported rules.
    if not supported_by and not rule.get("source"):
        return 1
    return 0


def rules_lines(
    rules: dict, *, active_slugs: set[str] | None = None, language: str = "en"
) -> list[str]:
    if not isinstance(rules, dict) or not isinstance(rules.get("rules"), list):
        return []
    active_slugs = active_slugs or set()
    active = [
        rule for rule in rules["rules"]
        if isinstance(rule, dict)
        and rule.get("status") == "active"
        and isinstance(rule.get("text"), str)
    ]
    if not active:
        return []
    ranked = sorted(
        enumerate(active),
        key=lambda pair: (-_rule_relevance(pair[1], active_slugs), pair[0]),
    )
    shown = [rule for _, rule in ranked[:RULE_CONTEXT_LIMIT]]
    lines = [
        f"{status_text(language, 'active_rules')}: {len(active)} "
        f"({status_text(language, 'showing')} {len(shown)}; "
        f"{status_text(language, 'remaining')} {len(active) - len(shown)})"
    ]
    for rule in shown:
        lines.append(f"  - {_sanitize(rule.get('text', ''), 150)}")
    return lines


def calibration_line(
    pipeline: dict, *, closed: list[dict] | None = None, language: str = "en"
) -> str | None:
    closed = closed if closed is not None else closed_companies(pipeline)
    scored = [c for c in closed if c.get("reached_stage") is not None]
    if len(scored) < CALIBRATION_MIN_SAMPLE:
        return None
    return f"{status_text(language, 'workflow_observations')}: " + status_text(
        language,
        "calibration_sentence",
        count=len(scored),
        entries=status_text(language, "reached_entries"),
        available=status_text(language, "available"),
    )


def diversity_line(
    pipeline: dict, *, entries: list[dict] | None = None, language: str = "en"
) -> str | None:
    """Warn when every recent application competes on the same axis.

    Carries no score and changes no ranking. It reports one observable fact: the user has
    only entered 選考 that evaluate verbal explanation, so an artifact they already own has
    had nowhere to be shown.
    """
    entries = entries if entries is not None else _company_entries(pipeline)
    companies = entries[-DIVERSITY_WINDOW:]
    known = [c for c in companies if c.get("demo_slot") in {"yes", "company_test", "no"}]
    if len(known) < DIVERSITY_WINDOW:
        return None
    if all(c.get("demo_slot") == "no" for c in known):
        return f"{status_text(language, 'diversity')}: " + status_text(
            language,
            "diversity_sentence",
            count=len(known),
        )
    return None


def build_status(
    pipeline: dict, rules: dict, today: dt.date, update: str | None = None,
    *, language: str = "en",
) -> str:
    """Assemble the block. Returns "" when there is nothing to report."""
    if not isinstance(pipeline, dict) or not isinstance(pipeline.get("companies"), list):
        return ""
    entries = _company_entries(pipeline)
    if not pipeline["companies"] or not entries:
        return ""
    active = [company for company in entries if not company.get("closed")]
    closed = [company for company in entries if company.get("closed")]
    active_slugs = {
        str(company.get("slug")) for company in active if company.get("slug") is not None
    }
    lines = [pipeline_line(pipeline, active=active, closed=closed, language=language)]
    for line in (deadline_line(pipeline, today, active=active, language=language),):
        if line:
            lines.append(line)
    lines.extend(gate_lines(pipeline, today, active=active, language=language))
    lines.extend(rules_lines(rules, active_slugs=active_slugs, language=language))
    calibration = calibration_line(pipeline, closed=closed, language=language)
    if calibration:
        lines.append(calibration)
    diversity = diversity_line(pipeline, entries=entries, language=language)
    if diversity:
        lines.append(diversity)
    if update:
        lines.append(update)
    return (
        "<career_status>\n"
        "<untrusted_career_data>\n"
        + "\n".join(lines)
        + "\n</untrusted_career_data>\n"
        "</career_status>"
    )


def load_yaml(path: Path, *, language: str = "en") -> dict:
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        # Surfaced rather than swallowed: a gate that disappears silently is worse than a
        # gate that reports it is down.
        print(
            "<career_status>\n"
            + status_text(language, "yaml_missing")
            + "\n</career_status>"
        )
        raise SystemExit(0)
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(
            "<career_status>\n"
            + status_text(
                language,
                "yaml_invalid",
                name=path.name,
                error=exc.__class__.__name__,
            )
            + "\n</career_status>"
        )
        raise SystemExit(0)


def workspace_path(explicit: str | Path | None = None) -> Path:
    """Resolve pipeline workspace as explicit path, env var, then CWD (WORK-001).

    Kept as a local, dependency-free copy — deliberately, not by oversight — because this
    module runs on every prompt via the UserPromptSubmit hook and must not gain an import
    that could fail before the pipeline-empty short-circuit at :465. The canonical shared
    implementation is `_shared/pipeline_store.resolve_workspace`; this must stay identical
    to it (see `scripts/test_status_bar.py`'s parity check against that function).
    """
    raw = explicit if explicit is not None else os.environ.get("CAREER_WORKSPACE")
    return Path(raw).expanduser().resolve() if raw else Path.cwd().resolve()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Print the deterministic career status bar")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--workspace", help="workspace containing data/pipeline.yml")
    parser.add_argument("--language", choices=("ko", "ja", "en"))
    parser.add_argument("legacy_root", nargs="?", help=argparse.SUPPRESS)
    args = parser.parse_args(list(argv or []))
    if args.refresh_cache:
        return refresh_cache()
    language = status_language(args.language)
    explicit = args.workspace if args.workspace is not None else args.legacy_root
    root = workspace_path(explicit)
    pipeline = load_yaml(root / "data" / "pipeline.yml", language=language)
    if not pipeline:
        return 0
    rules = load_yaml(root / "data" / "rules.yml", language=language)
    cache = {} if update_check_disabled() else read_cache()
    block = build_status(
        pipeline,
        rules,
        dt.date.today(),
        update_line(local_version(), cache, language=language),
        language=language,
    )
    if block:
        print(block)
    maybe_refresh(cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
