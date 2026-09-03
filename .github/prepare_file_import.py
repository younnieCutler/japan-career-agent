from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing patch anchor in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, count), encoding="utf-8")


def append_before(path, marker, block):
    replace(path, marker, block + marker)

# Runtime dependency + source version.
replace("pyproject.toml", 'version = "2.24.0"', 'version = "2.25.0"')
replace(
    "pyproject.toml",
    '  "PyYAML>=6.0.3,<7",\n]',
    '  "PyYAML>=6.0.3,<7",\n  "pypdf>=6.16,<7",\n]',
)
req = ROOT / "requirements.txt"
req_text = req.read_text(encoding="utf-8")
if "pypdf" not in req_text:
    req.write_text(req_text.rstrip() + "\npypdf>=6.16,<7\n", encoding="utf-8")

# Local GUI import endpoint: larger body limit only for this local-only extraction endpoint.
replace(
    "skills/career-agent/gui/server.py",
    "import gui.judgments as judgment_api\n",
    "import gui.judgments as judgment_api\nfrom gui.import_text import extract_career_text\n",
)
replace(
    "skills/career-agent/gui/server.py",
    "            payload = self._json_body()\n",
    "            body_limit = 7 * 1024 * 1024 if path == \"/api/career/import-text\" else 131072\n            payload = self._json_body(limit=body_limit)\n",
)
replace(
    "skills/career-agent/gui/server.py",
    '            elif path == "/api/workflows/import-profile":\n',
    '            elif path == "/api/career/import-text":\n                result = {\n                    "filename": str(payload["filename"]),\n                    "text": extract_career_text(payload["filename"], payload["content_base64"]),\n                }\n            elif path == "/api/workflows/import-profile":\n',
)

# File chooser feeds extracted text into the already-existing draft workflow. No auto-approval.
replace(
    "frontend/src/screens/Career.jsx",
    'function ExistingHistoryCapture({ onError }) {\n',
    '''const fileAsBase64 = (file) => new Promise((resolve, reject) => {\n  const reader = new FileReader();\n  reader.onload = () => {\n    const value = String(reader.result || \"\");\n    resolve(value.includes(\",\") ? value.split(\",\", 2)[1] : value);\n  };\n  reader.onerror = () => reject(reader.error || new Error(\"file read failed\"));\n  reader.readAsDataURL(file);\n});\n\nfunction ExistingHistoryCapture({ onError }) {\n''',
)
replace(
    "frontend/src/screens/Career.jsx",
    '  const [busy, setBusy] = React.useState(false);\n\n  const submit = async (event) => {\n',
    '''  const [busy, setBusy] = React.useState(false);\n\n  const importFile = async (event) => {\n    const file = event.target.files?.[0];\n    if (!file) return;\n    setBusy(true);\n    try {\n      const imported = await write(\"/api/career/import-text\", {\n        filename: file.name, content_base64: await fileAsBase64(file),\n      });\n      setBody(String(imported.text || \"\"));\n    } catch (error) { onError(error); }\n    finally { setBusy(false); event.target.value = \"\"; }\n  };\n\n  const submit = async (event) => {\n''',
)
replace(
    "frontend/src/screens/Career.jsx",
    '      <form className="stack" onSubmit={submit}>\n        <Field label={t("applications.document_body")}>\n',
    '''      <form className="stack" onSubmit={submit}>\n        <Field label={t(\"career.import_file\")} help={t(\"career.import_file_help\")}>\n          <input\n            type=\"file\"\n            accept=\".txt,.docx,.pdf,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document\"\n            aria-label={t(\"career.import_file\")}\n            onChange={importFile}\n            disabled={busy}\n          />\n        </Field>\n        <Field label={t(\"applications.document_body\")}>\n''',
)

# Localized GUI copy through the existing extras catalog.
loc = ROOT / "skills/career-agent/localization.py"
text = loc.read_text(encoding="utf-8")
text = text.replace(
    '"ko": {"common.other": "기타",',
    '"ko": {"common.other": "기타", "career.import_file": "기존 경력 파일 가져오기", "career.import_file_help": "TXT, DOCX, PDF를 선택하면 내용을 이 화면에 불러옵니다. 확인하기 전에는 경력 정보로 확정되지 않습니다.",',
    1,
).replace(
    '"ja": {"common.other": "その他",',
    '"ja": {"common.other": "その他", "career.import_file": "既存の経歴ファイルを読み込む", "career.import_file_help": "TXT、DOCX、PDFを選ぶと内容をこの画面に読み込みます。確認するまでは経歴情報として確定されません。",',
    1,
).replace(
    '"en": {"common.other": "Other",',
    '"en": {"common.other": "Other", "career.import_file": "Import existing career file", "career.import_file_help": "Choose TXT, DOCX, or PDF to load its text here. Nothing becomes confirmed career information until you review it.",',
    1,
)
# Add namespaced status vocabularies next to event status; canonical JSON stays unchanged.
anchor = '''    "event_status": {\n        "draft": ("초안", "下書き", "Draft"),\n        "confirmed": ("확정", "確定", "Confirmed"),\n        "superseded": ("이전 기록", "旧記録", "Superseded"),\n    },\n'''
block = anchor + '''    "skill_invocation_status": {\n        "selected": ("선택됨", "選択済み", "Selected"),\n        "started": ("실행 중", "実行中", "Started"),\n        "completed": ("완료", "完了", "Completed"),\n        "blocked": ("진행할 수 없음", "実行できません", "Blocked"),\n        "failed": ("실패", "失敗", "Failed"),\n        "needs_input": ("입력 필요", "入力が必要", "Input needed"),\n        "needs_approval": ("확인 필요", "確認が必要", "Approval needed"),\n        "unsupported": ("지원되지 않음", "未対応", "Unsupported"),\n    },\n    "execution_plan_status": {\n        "running": ("실행 중", "実行中", "Running"),\n        "paused": ("일시 중지", "一時停止", "Paused"),\n        "completed": ("완료", "完了", "Completed"),\n        "blocked": ("진행할 수 없음", "実行できません", "Blocked"),\n        "failed": ("실패", "失敗", "Failed"),\n        "unsupported": ("지원되지 않음", "未対応", "Unsupported"),\n    },\n'''
if anchor not in text:
    raise SystemExit("event_status localization anchor missing")
text = text.replace(anchor, block, 1)
loc.write_text(text, encoding="utf-8")

# Human CLI/agent output translates status values at the boundary instead of leaking tokens.
replace(
    "skills/career-agent/ux.py",
    'lines.append(text(language, "section.execution_plan", id=plan_id, status=status))',
    'lines.append(text(language, "section.execution_plan", id=plan_id, status=domain_label(language, "execution_plan_status", status)))',
)
replace(
    "skills/career-agent/ux.py",
    '                        status=invocation.get("status"),\n',
    '                        status=domain_label(language, "skill_invocation_status", invocation.get("status")),\n',
)
replace(
    "skills/career-agent/ux.py",
    '                status=payload.get("status"),\n',
    '                status=domain_label(language, "skill_invocation_status", payload.get("status")),\n',
)

# Register the new focused unit test in the existing verification matrix.
replace(
    "scripts/run_all_checks.py",
    '("career-agent GUI cases and artifacts", (PYTHON, "skills/career-agent/gui/test_cases_artifacts.py")),\n',
    '("career-agent GUI cases and artifacts", (PYTHON, "skills/career-agent/gui/test_cases_artifacts.py")),\n    ("career-agent GUI file import", (PYTHON, "skills/career-agent/gui/test_import_text.py")),\n',
)

# Lock the KO/JA status boundary with direct human-rendering regression tests.
append_before(
    "skills/career-agent/test_localization.py",
    '\nif __name__ == "__main__":\n',
    '''\n\nclass HumanStatusLocalizationRegressionTests(unittest.TestCase):\n    def test_execution_plan_status_is_localized_in_korean_and_japanese(self):\n        payload = {\n            "mode": "plan-status", "plan_id": "plan-1", "status": "running",\n            "ux": {"language": "ko", "state": "ready"},\n        }\n        ko = ux.render_human(payload)\n        self.assertIn("실행 중", ko)\n        self.assertNotIn("running", ko)\n        payload["ux"]["language"] = "ja"\n        ja = ux.render_human(payload)\n        self.assertIn("実行中", ja)\n        self.assertNotIn("running", ja)\n\n    def test_skill_invocation_status_is_localized_in_korean_and_japanese(self):\n        payload = {\n            "invocation_id": "skillinv-1", "skill": "career-agent",\n            "execution": "deterministic", "status": "unsupported",\n            "ux": {"language": "ko", "state": "blocked"},\n        }\n        ko = ux.render_human(payload)\n        self.assertIn("지원되지 않음", ko)\n        self.assertNotIn("unsupported", ko)\n        payload["ux"]["language"] = "ja"\n        ja = ux.render_human(payload)\n        self.assertIn("未対応", ja)\n        self.assertNotIn("unsupported", ja)\n''',
)

# Frontend regression: file selection only fills the existing draft textarea; it does not approve.
append_before(
    "frontend/src/screens/Career.test.jsx",
    '\n});\n',
    '''\n\n  it("loads a local career file into the existing draft field without starting approval", async () => {\n    location.search = "?capture=1";\n    read.mockResolvedValue(emptyCareer);\n    write.mockResolvedValueOnce({ text: "Imported career history" });\n    const OriginalFileReader = globalThis.FileReader;\n    globalThis.FileReader = class {\n      readAsDataURL() { this.result = "data:text/plain;base64,SGVsbG8="; this.onload(); }\n    };\n    try {\n      render(<CareerScreen />);\n      const input = await screen.findByLabelText("career.import_file");\n      fireEvent.change(input, { target: { files: [new File(["Hello"], "resume.txt", { type: "text/plain" })] } });\n      await waitFor(() => expect(write).toHaveBeenCalledWith("/api/career/import-text", {\n        filename: "resume.txt", content_base64: "SGVsbG8=",\n      }));\n      expect(screen.getByLabelText("applications.document_body").value).toBe("Imported career history");\n      expect(navigate).not.toHaveBeenCalled();\n    } finally {\n      globalThis.FileReader = OriginalFileReader;\n    }\n  });\n''',
)

# Minimal release notes/docs. Generated manifests/SBOM are handled by sync_version.py after locks.
changelog = ROOT / "CHANGELOG.md"
current = changelog.read_text(encoding="utf-8")
if "## 2.25.0" not in current:
    header_end = current.find("\n", current.find("# ")) + 1
    entry = "\n## 2.25.0\n\n- Add local TXT/DOCX/PDF career-file import into the existing evidence-gated career capture flow.\n- Localize execution-plan and Skill-invocation status values in Korean and Japanese human output.\n"
    current = current[:header_end] + entry + current[header_end:]
    changelog.write_text(current, encoding="utf-8")

for name in ("README.md", "README_ko.md", "README_ja.md", "docs/upgrading.md", "docs/upgrading_ko.md", "docs/upgrading_ja.md"):
    p = ROOT / name
    if not p.exists():
        continue
    value = p.read_text(encoding="utf-8")
    value = value.replace("2.24.0", "2.25.0", 1)
    p.write_text(value, encoding="utf-8")
