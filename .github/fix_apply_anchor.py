from pathlib import Path

path = Path(__file__).with_name("apply_file_import.py")
text = path.read_text(encoding="utf-8")
text = text.replace('"confirmed": ("확정", "確定", "Confirmed")', '"confirmed": ("확정됨", "確定済み", "Confirmed")')
text = text.replace('"superseded": ("이전 기록", "旧記録", "Superseded")', '"superseded": ("새 기록으로 대체됨", "新しい記録に更新済み", "Replaced by a newer record")')
path.write_text(text, encoding="utf-8")
