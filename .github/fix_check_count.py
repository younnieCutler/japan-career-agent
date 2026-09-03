from pathlib import Path

path = Path(__file__).resolve().parents[1] / "docs" / "MAINTAINER_RUNBOOK.md"
text = path.read_text(encoding="utf-8")
old = "Expected: `All 96 repository checks passed.`"
new = "Expected: `All 97 repository checks passed.`"
if old not in text:
    raise SystemExit("maintainer check-count anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
