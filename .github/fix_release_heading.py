from pathlib import Path

path = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
text = path.read_text(encoding="utf-8")
text = text.replace("## 2.25.0\n", "## [2.25.0] - 2026-09-03\n", 1)
path.write_text(text, encoding="utf-8")
