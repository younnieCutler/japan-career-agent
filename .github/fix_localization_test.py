from pathlib import Path

path = Path(__file__).resolve().parents[1] / "skills" / "career-agent" / "test_localization.py"
text = path.read_text(encoding="utf-8")
anchor = "from localization import SUPPORTED_LANGUAGES, UX_TEXT  # noqa: E402\n"
if anchor not in text:
    raise SystemExit("localization test import anchor missing")
text = text.replace(anchor, anchor + "from ux import render_human  # noqa: E402\n", 1)
text = text.replace("ux.render_human(payload)", "render_human(payload)")
path.write_text(text, encoding="utf-8")
