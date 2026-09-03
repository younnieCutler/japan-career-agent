from pathlib import Path
import json
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def change(path: str, transform):
    p = ROOT / path
    before = p.read_text(encoding="utf-8")
    after = transform(before)
    if after == before:
        raise SystemExit(f"no change made to {path}")
    p.write_text(after, encoding="utf-8")


def once(text: str, old: str, new: str, path: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"expected one anchor in {path}, found {text.count(old)}: {old[:80]!r}")
    return text.replace(old, new, 1)

# Version and direct dependency contracts.
change("pyproject.toml", lambda t: once(
    once(t, 'version = "2.24.0"', 'version = "2.25.0"', "pyproject.toml"),
    '  "jsonschema>=4.23,<5",\n]',
    '  "jsonschema>=4.23,<5",\n  "pypdf>=6.16,<7",\n]',
    "pyproject.toml",
))
change("requirements.txt", lambda t: t.rstrip() + "\npypdf>=6.16,<7\n")

# Hash-pin the current pypdf release without re-resolving unrelated dependencies.
lock = ROOT / "requirements.lock"
lock_text = lock.read_text(encoding="utf-8")
if "pypdf==" not in lock_text:
    with urllib.request.urlopen("https://pypi.org/pypi/pypdf/6.16.2/json", timeout=30) as response:
        metadata = json.load(response)
    hashes = sorted({item["digests"]["sha256"] for item in metadata["urls"]})
    block = "pypdf==6.16.2 \\\n" + " \\\n".join(f"    --hash=sha256:{value}" for value in hashes) + "\n"
    marker = "typing-extensions=="
    index = lock_text.index(marker)
    lock.write_text(lock_text[:index] + block + lock_text[index:], encoding="utf-8")

# Server endpoint with a larger request cap only for local document extraction.
def server_patch(t: str) -> str:
    t = once(t, "import gui.judgments as judgment_api\n", "import gui.judgments as judgment_api\nfrom gui.import_text import extract_career_text\n", "server.py")
    t = once(t, "            payload = self._json_body()\n", "            body_limit = 7 * 1024 * 1024 if path == \"/api/career/import-text\" else 131072\n            payload = self._json_body(limit=body_limit)\n", "server.py")
    t = once(t, '            elif path == "/api/workflows/import-profile":\n', '            elif path == "/api/career/import-text":\n                result = {\n                    "filename": str(payload["filename"]),\n                    "text": extract_career_text(payload["filename"], payload["content_base64"]),\n                }\n            elif path == "/api/workflows/import-profile":\n', "server.py")
    return t
change("skills/career-agent/gui/server.py", server_patch)

# Existing career capture: file select fills the same textarea; approval behavior is unchanged.
def career_patch(t: str) -> str:
    t = once(t, "function ExistingHistoryCapture({ onError }) {\n", '''const fileAsBase64 = (file) => new Promise((resolve, reject) => {\n  const reader = new FileReader();\n  reader.onload = () => {\n    const value = String(reader.result || \"\");\n    resolve(value.includes(\",\") ? value.split(\",\", 2)[1] : value);\n  };\n  reader.onerror = () => reject(reader.error || new Error(\"file read failed\"));\n  reader.readAsDataURL(file);\n});\n\nfunction ExistingHistoryCapture({ onError }) {\n''', "Career.jsx")
    t = once(t, '  const [busy, setBusy] = React.useState(false);\n\n  const submit = async (event) => {\n', '''  const [busy, setBusy] = React.useState(false);\n\n  const importFile = async (event) => {\n    const file = event.target.files?.[0];\n    if (!file) return;\n    setBusy(true);\n    try {\n      const imported = await write(\"/api/career/import-text\", {\n        filename: file.name, content_base64: await fileAsBase64(file),\n      });\n      setBody(String(imported.text || \"\"));\n    } catch (error) { onError(error); }\n    finally { setBusy(false); event.target.value = \"\"; }\n  };\n\n  const submit = async (event) => {\n''', "Career.jsx")
    t = once(t, '      <form className="stack" onSubmit={submit}>\n        <Field label={t("applications.document_body")}>\n', '''      <form className="stack" onSubmit={submit}>\n        <Field label={t(\"career.import_file\")} help={t(\"career.import_file_help\")}>\n          <input\n            type=\"file\"\n            accept=\".txt,.docx,.pdf,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document\"\n            aria-label={t(\"career.import_file\")}\n            onChange={importFile}\n            disabled={busy}\n          />\n        </Field>\n        <Field label={t(\"applications.document_body\")}>\n''', "Career.jsx")
    return t
change("frontend/src/screens/Career.jsx", career_patch)

# GUI strings + namespaced status vocabularies.
def localization_patch(t: str) -> str:
    t = once(t, '"ko": {"common.other": "기타",', '"ko": {"common.other": "기타", "career.import_file": "기존 경력 파일 가져오기", "career.import_file_help": "TXT, DOCX, PDF를 선택하면 내용을 이 화면에 불러옵니다. 확인하기 전에는 경력 정보로 확정되지 않습니다.",', "localization.py")
    t = once(t, '"ja": {"common.other": "その他",', '"ja": {"common.other": "その他", "career.import_file": "既存の経歴ファイルを読み込む", "career.import_file_help": "TXT、DOCX、PDFを選ぶと内容をこの画面に読み込みます。確認するまでは経歴情報として確定されません。",', "localization.py")
    t = once(t, '"en": {"common.other": "Other",', '"en": {"common.other": "Other", "career.import_file": "Import existing career file", "career.import_file_help": "Choose TXT, DOCX, or PDF to load its text here. Nothing becomes confirmed career information until you review it.",', "localization.py")
    marker = '''    "event_status": {\n        "draft": ("초안", "下書き", "Draft"),\n        "confirmed": ("확정", "確定", "Confirmed"),\n        "superseded": ("이전 기록", "旧記録", "Superseded"),\n    },\n'''
    extra = '''    "skill_invocation_status": {\n        "selected": ("선택됨", "選択済み", "Selected"),\n        "started": ("실행 중", "実行中", "Started"),\n        "completed": ("완료", "完了", "Completed"),\n        "blocked": ("진행할 수 없음", "実行できません", "Blocked"),\n        "failed": ("실패", "失敗", "Failed"),\n        "needs_input": ("입력 필요", "入力が必要", "Input needed"),\n        "needs_approval": ("확인 필요", "確認が必要", "Approval needed"),\n        "unsupported": ("지원되지 않음", "未対応", "Unsupported"),\n    },\n    "execution_plan_status": {\n        "running": ("실행 중", "実行中", "Running"),\n        "paused": ("일시 중지", "一時停止", "Paused"),\n        "completed": ("완료", "完了", "Completed"),\n        "blocked": ("진행할 수 없음", "実行できません", "Blocked"),\n        "failed": ("실패", "失敗", "Failed"),\n        "unsupported": ("지원되지 않음", "未対応", "Unsupported"),\n    },\n'''
    return once(t, marker, marker + extra, "localization.py")
change("skills/career-agent/localization.py", localization_patch)

# Translate raw status values only at human rendering boundaries.
def ux_patch(t: str) -> str:
    t = once(t, 'lines.append(text(language, "section.execution_plan", id=plan_id, status=status))', 'lines.append(text(language, "section.execution_plan", id=plan_id, status=domain_label(language, "execution_plan_status", status)))', "ux.py")
    t = once(t, '                        status=invocation.get("status"),\n', '                        status=domain_label(language, "skill_invocation_status", invocation.get("status")),\n', "ux.py")
    t = once(t, '                status=payload.get("status"),\n', '                status=domain_label(language, "skill_invocation_status", payload.get("status")),\n', "ux.py")
    return t
change("skills/career-agent/ux.py", ux_patch)

# Register focused parser test.
change("scripts/run_all_checks.py", lambda t: once(t, '("career-agent GUI cases and artifacts", (PYTHON, "skills/career-agent/gui/test_cases_artifacts.py")),\n', '("career-agent GUI cases and artifacts", (PYTHON, "skills/career-agent/gui/test_cases_artifacts.py")),\n    ("career-agent GUI file import", (PYTHON, "skills/career-agent/gui/test_import_text.py")),\n', "run_all_checks.py"))

# Human status leakage regression tests.
def localization_test_patch(t: str) -> str:
    marker = '\nif __name__ == "__main__":\n'
    block = '''\n\nclass HumanStatusLocalizationRegressionTests(unittest.TestCase):\n    def test_plan_status_is_localized(self):\n        payload = {"mode": "plan-status", "plan_id": "plan-1", "status": "running", "ux": {"language": "ko", "state": "ready"}}\n        ko = ux.render_human(payload)\n        self.assertIn("실행 중", ko)\n        self.assertNotIn("running", ko)\n        payload["ux"]["language"] = "ja"\n        ja = ux.render_human(payload)\n        self.assertIn("実行中", ja)\n        self.assertNotIn("running", ja)\n\n    def test_skill_status_is_localized(self):\n        payload = {"invocation_id": "skillinv-1", "skill": "career-agent", "execution": "deterministic", "status": "unsupported", "ux": {"language": "ko", "state": "blocked"}}\n        ko = ux.render_human(payload)\n        self.assertIn("지원되지 않음", ko)\n        self.assertNotIn("unsupported", ko)\n        payload["ux"]["language"] = "ja"\n        ja = ux.render_human(payload)\n        self.assertIn("未対応", ja)\n        self.assertNotIn("unsupported", ja)\n'''
    return once(t, marker, block + marker, "test_localization.py")
change("skills/career-agent/test_localization.py", localization_test_patch)

# Frontend action-budget regression: selecting a file only fills the existing draft field.
def career_test_patch(t: str) -> str:
    marker = "\n});\n"
    pos = t.rfind(marker)
    if pos < 0:
        raise SystemExit("Career.test.jsx final describe marker missing")
    block = '''\n\n  it("loads a local career file into the existing draft field without approving", async () => {\n    location.search = "?capture=1";\n    read.mockResolvedValue(emptyCareer);\n    write.mockResolvedValueOnce({ text: "Imported career history" });\n    const OriginalFileReader = globalThis.FileReader;\n    globalThis.FileReader = class {\n      readAsDataURL() { this.result = "data:text/plain;base64,SGVsbG8="; this.onload(); }\n    };\n    try {\n      render(<CareerScreen />);\n      const input = await screen.findByLabelText("career.import_file");\n      fireEvent.change(input, { target: { files: [new File(["Hello"], "resume.txt", { type: "text/plain" })] } });\n      await waitFor(() => expect(write).toHaveBeenCalledWith("/api/career/import-text", { filename: "resume.txt", content_base64: "SGVsbG8=" }));\n      expect(screen.getByLabelText("applications.document_body").value).toBe("Imported career history");\n      expect(navigate).not.toHaveBeenCalled();\n    } finally {\n      globalThis.FileReader = OriginalFileReader;\n    }\n  });\n'''
    return t[:pos] + block + t[pos:]
change("frontend/src/screens/Career.test.jsx", career_test_patch)

# Minimal public release metadata; manifests and SBOM are generated by sync_version.py.
changelog = ROOT / "CHANGELOG.md"
t = changelog.read_text(encoding="utf-8")
if "## 2.25.0" not in t:
    first_break = t.find("\n") + 1
    t = t[:first_break] + "\n## 2.25.0\n\n- Add local TXT/DOCX/PDF import to the existing evidence-gated career capture flow.\n- Localize execution-plan and Skill-invocation statuses in Korean and Japanese human output.\n" + t[first_break:]
    changelog.write_text(t, encoding="utf-8")

for name in ("README.md", "README_ko.md", "README_ja.md", "docs/upgrading.md", "docs/upgrading_ko.md", "docs/upgrading_ja.md"):
    p = ROOT / name
    if p.exists():
        value = p.read_text(encoding="utf-8")
        if "2.24.0" in value:
            p.write_text(value.replace("2.24.0", "2.25.0", 1), encoding="utf-8")
