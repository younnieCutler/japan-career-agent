#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8", newline="\n")


def replace_once(path: str, old: str, new: str) -> None:
    value = text(path)
    if value.count(old) != 1:
        raise SystemExit(f"{path}: expected one replacement for {old[:80]!r}, found {value.count(old)}")
    write(path, value.replace(old, new, 1))


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    value = text(path)
    start_at = value.find(start)
    end_at = value.find(end, start_at + len(start))
    if start_at < 0 or end_at < 0:
        raise SystemExit(f"{path}: section anchors not found: {start!r} -> {end!r}")
    write(path, value[:start_at] + replacement.rstrip() + "\n\n" + value[end_at:])


# 1) One command opens the product. Explicit `ui` remains write-free; only the no-argument
# quickstart prepares the minimum empty local record that the GUI needs to read.
replace_once(
    "skills/career-agent/command_line.py",
    "from vault import CareerVault, today, utc_now",
    "from vault import CareerVault, initialize_vault, today, utc_now",
)
replace_once(
    "skills/career-agent/command_line.py",
    '''        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)\n        try:\n            return serve_gui(''',
    '''        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)\n        if getattr(args, "_quickstart", False) and not ui_vault.initialized():\n            initialize_vault(ui_vault.path)\n        try:\n            return serve_gui(''',
)
replace_once(
    "skills/career-agent/command_line.py",
    '''    parser = build_parser()\n    args = parser.parse_args(list(argv) if argv is not None else None)\n    context: dict[str, Any] = {}''',
    '''    parser = build_parser()\n    raw_argv = list(argv) if argv is not None else sys.argv[1:]\n    quickstart = not raw_argv\n    args = parser.parse_args(raw_argv or ["ui"])\n    if quickstart:\n        args._quickstart = True\n    context: dict[str, Any] = {}''',
)

# 2) Remove implementation vocabulary from the Korean/Japanese product surface. Canonical keys and
# machine values are deliberately untouched.
copy_replacements = {
    '"app.tagline": "경력의 맥락과 근거를 한곳에서 차분히 정리하세요.",':
        '"app.tagline": "경력과 확인 가능한 근거를 한곳에서 정리하세요.",',
    '"diagnosis.empty_body": "경력이 짧다는 뜻이 아니라, Career Vault가 비어 있다는 뜻입니다. 회사나 활동을 하나 추가하는 것부터 시작하세요.",':
        '"diagnosis.empty_body": "경력이 짧다는 뜻이 아니라, 아직 저장된 경력 기록이 없다는 뜻입니다. 회사나 활동을 하나 추가하는 것부터 시작하세요.",',
    '"career.intro": "회사와 활동 맥락 아래에서 프로젝트와 경험을 찾습니다.",':
        '"career.intro": "회사·활동별로 프로젝트와 경험을 모아 봅니다.",',
    '"career.context": "경력 맥락",':
        '"career.context": "회사·활동",',
    '"app.tagline": "キャリアの文脈と根拠を、一か所で落ち着いて整理できます。",':
        '"app.tagline": "経歴と確認できる根拠を一か所で整理できます。",',
    '"diagnosis.empty_body": "経歴が浅いという意味ではなく、Career Vaultが空だという意味です。会社や活動をひとつ追加するところから始めてください。",':
        '"diagnosis.empty_body": "経歴が浅いという意味ではなく、まだ保存された経歴がないという意味です。会社や活動をひとつ追加するところから始めてください。",',
    '"career.title": "キャリア履歴", "career.intro": "会社や活動の文脈から、プロジェクトと経験を探します。",':
        '"career.title": "キャリア履歴", "career.intro": "会社・活動ごとにプロジェクトと経験をまとめます。",',
    '"career.context": "キャリアの文脈",':
        '"career.context": "会社・活動",',
}
for old, new in copy_replacements.items():
    replace_once("skills/career-agent/localization.py", old, new)

# Make raw English implementation vocabulary a permanent KO/JA product-copy regression.
replace_once(
    "skills/career-agent/test_domain_vocabulary.py",
    "from pathlib import Path\n",
    "from pathlib import Path\nfrom unittest.mock import patch\n",
)
replace_once(
    "skills/career-agent/test_domain_vocabulary.py",
    '''sys.path.insert(0, str(RUNTIME))\n\nfrom gui._test_client import client_source  # noqa: E402''',
    '''sys.path.insert(0, str(RUNTIME))\n\nimport command_line  # noqa: E402\nfrom gui._test_client import client_source  # noqa: E402''',
)
replace_once(
    "skills/career-agent/test_domain_vocabulary.py",
    '''        forbidden = (\n            "Unknown", "Conflict", "shinsotsu", "chuto", "needs_confirmation",\n            "profile.", "career-profile.toml", "--proposal-id", "proposal_id",\n            "event_id", "artifact_id", "case_id", "ledger_written", "state_written",\n            "projection_written",\n        )\n        for table in (GUI_TEXT, GUI_PRODUCT_TEXT, UX_TEXT):\n            for language in ("ko", "ja"):\n                for key, value in table[language].items():\n                    with self.subTest(language=language, key=key):\n                        self.assertFalse(any(token in value for token in forbidden), value)''',
    '''        forbidden = (\n            "unknown", "conflict", "shinsotsu", "chuto", "needs_confirmation",\n            "profile.", "career-profile.toml", "--proposal-id", "proposal_id",\n            "event_id", "artifact_id", "case_id", "ledger_written", "state_written",\n            "projection_written", "career vault", "canonical", "context", "evidence",\n            "proposal", "session",\n        )\n        for table in (GUI_TEXT, GUI_PRODUCT_TEXT, UX_TEXT):\n            for language in ("ko", "ja"):\n                for key, value in table[language].items():\n                    with self.subTest(language=language, key=key):\n                        lowered = value.casefold()\n                        self.assertFalse(any(token in lowered for token in forbidden), value)''',
)
entrypoint_tests = '''\n\nclass ThinEntrypointTests(unittest.TestCase):\n    def test_no_argument_launch_defaults_to_gui(self) -> None:\n        captured = {}\n\n        def fake_run(args, context):\n            captured["args"] = args\n            return {"ok": True}\n\n        with patch.object(command_line, "run_command", side_effect=fake_run), patch.object(\n            command_line, "_emit", return_value=0\n        ):\n            self.assertEqual(command_line.main([]), 0)\n        self.assertEqual(captured["args"].command, "ui")\n        self.assertTrue(captured["args"]._quickstart)\n\n    def test_quickstart_prepares_only_an_empty_local_record(self) -> None:\n        with tempfile.TemporaryDirectory() as directory:\n            vault = Path(directory) / "quickstart"\n            args = command_line.build_parser().parse_args(["ui", "--no-browser"])\n            args._quickstart = True\n            with patch.object(command_line, "DEFAULT_VAULT_PATH", vault), patch(\n                "gui.server.serve", return_value={"mode": "ui", "ok": True}\n            ):\n                command_line.run_command(args, {})\n            home = command_line.CareerVault(vault)\n            self.assertTrue(home.initialized())\n            self.assertFalse(home.events.exists())\n            self.assertFalse(home.proposals.exists())\n\n    def test_explicit_ui_keeps_its_write_free_start_contract(self) -> None:\n        with tempfile.TemporaryDirectory() as directory:\n            vault = Path(directory) / "explicit-ui"\n            args = command_line.build_parser().parse_args(["ui", "--no-browser"])\n            with patch.object(command_line, "DEFAULT_VAULT_PATH", vault), patch(\n                "gui.server.serve", return_value={"mode": "ui", "ok": True}\n            ):\n                command_line.run_command(args, {})\n            self.assertFalse(vault.exists())\n'''
replace_once(
    "skills/career-agent/test_domain_vocabulary.py",
    '\n\nif __name__ == "__main__":\n    unittest.main()\n',
    entrypoint_tests + '\n\nif __name__ == "__main__":\n    unittest.main()\n',
)

# 3) The same recorded evidence must make the second and third applications no harder than the
# first: paste a labelled JD, then submit. No checkbox or company setup interaction is allowed.
sequential_test = '''\n\n  it("keeps the second and third applications to one JD paste and one submit each", async () => {\n    const onDone = vi.fn();\n    write\n      .mockResolvedValueOnce({ case_id: "company-1" }).mockResolvedValueOnce({})\n      .mockResolvedValueOnce({ case_id: "company-2" }).mockResolvedValueOnce({})\n      .mockResolvedValueOnce({ case_id: "company-3" }).mockResolvedValueOnce({});\n    render(<AddPosition\n      payload={{\n        companies: [],\n        evidence_options: [\n          { refs: ["e-python"], label: "Python API migration", context: "Recent work", sharing: "available" },\n          { refs: ["e-aws"], label: "AWS operations", context: "Recent work", sharing: "available" },\n          { refs: ["e-k8s"], label: "Kubernetes rollout", context: "Recent work", sharing: "available" },\n        ],\n      }}\n      onDone={onDone}\n    />);\n\n    const add = async (jd, expectedCalls) => {\n      fireEvent.change(screen.getByLabelText("applications.jd"), { target: { value: jd } });\n      fireEvent.click(screen.getByRole("button", { name: "applications.add_position" }));\n      await waitFor(() => expect(write).toHaveBeenCalledTimes(expectedCalls));\n      await waitFor(() => expect(screen.getByLabelText("applications.jd").value).toBe(""));\n    };\n\n    await add("Company: Acme\\nPosition: Platform Engineer\\nPython API", 2);\n    await add("Company: Beta\\nPosition: SRE\\nAWS operations", 4);\n    await add("Company: Gamma\\nPosition: Platform SRE\\nKubernetes rollout", 6);\n\n    expect(write).toHaveBeenNthCalledWith(2, "/api/applications/positions", expect.objectContaining({\n      company_ref: "company-1", label: "Platform Engineer", evidence_refs: ["e-python"],\n    }));\n    expect(write).toHaveBeenNthCalledWith(4, "/api/applications/positions", expect.objectContaining({\n      company_ref: "company-2", label: "SRE", evidence_refs: ["e-aws"],\n    }));\n    expect(write).toHaveBeenNthCalledWith(6, "/api/applications/positions", expect.objectContaining({\n      company_ref: "company-3", label: "Platform SRE", evidence_refs: ["e-k8s"],\n    }));\n    expect(onDone).toHaveBeenCalledTimes(3);\n  });'''
replace_once(
    "frontend/src/screens/Applications.test.jsx",
    '''    expect(onDone).toHaveBeenCalledOnce();\n  });\n});\n\ndescribe("document edit",''',
    '''    expect(onDone).toHaveBeenCalledOnce();\n  });''' + sequential_test + '''\n});\n\ndescribe("document edit",''',
)

# Lead every public README with the one-command GUI route. Advanced CLI details remain below.
replace_section(
    "README.md", "## Quick start", "## Install",
    '''## Quick start\n\nOpen the local GUI without installing the agent globally:\n\n```bash\nnpx japan-career-agent\n```\n\nAlready use uv instead of Node? `uvx japan-career-agent` opens the same GUI.\n\nOn the first zero-argument launch, the tool prepares only the empty local career record the GUI\nneeds. It does not infer, approve, or upload a career fact. Import or paste the history you already\nhave, then confirm only what you want to keep.\n\nThe explicit `setup`, `guided`, `ui`, and other CLI commands remain available for terminal or\nautomation workflows. In a plugin host, use a normal request:\n\n```text\nI want to start preparing for a job change in Japan.\nCompare this JD with my experience and keep unconfirmed points as Unknown.\nHelp me prepare for next week's interview.\nReview this 職務経歴書 without inventing evidence.\n```''',
)
replace_section(
    "README_ko.md", "## Quick Start", "## 설치",
    '''## Quick Start\n\n로컬 GUI를 전역 설치 없이 바로 엽니다.\n\n```bash\nnpx japan-career-agent\n```\n\nNode 대신 uv를 쓰고 있다면 `uvx japan-career-agent`를 실행하면 같은 GUI가 열립니다.\n\n인자 없이 처음 실행할 때는 GUI에 필요한 빈 로컬 경력 기록만 준비합니다. 경력 사실을 추정하거나\n확정하거나 업로드하지 않습니다. 기존 이력서·職務経歴書를 가져오거나 붙여넣고, 남길 내용만 직접\n확정하면 됩니다.\n\n터미널이나 자동화가 필요하면 기존 `setup`, `guided`, `ui`와 나머지 CLI 명령을 그대로 쓸 수 있습니다.\nplugin host에서는 평소 말하듯 요청하면 됩니다.\n\n```text\n일본 이직 준비를 시작하고 싶어.\n이 JD와 내 경력을 비교하고, 확인되지 않은 내용은 Unknown으로 남겨줘.\n다음 주 면접을 준비하고 싶어.\n이 職務経歴書를 검토하되 없는 경력은 만들지 마.\n```''',
)
replace_section(
    "README_ja.md", "## Quick Start", "## インストール",
    '''## Quick Start\n\nローカル GUI をグローバルインストールなしで開きます。\n\n```bash\nnpx japan-career-agent\n```\n\nNode ではなく uv を使っている場合は、`uvx japan-career-agent` で同じ GUI が開きます。\n\n引数なしで初めて起動すると、GUI に必要な空のローカル経歴記録だけを準備します。経歴の事実を\n推測・確定・アップロードすることはありません。手元の履歴書・職務経歴書を読み込むか貼り付け、\n残したい内容だけを自分で確定できます。\n\nターミナルや自動化が必要な場合は、既存の `setup`、`guided`、`ui` とその他の CLI コマンドを\nそのまま使えます。plugin host では普段の言葉で依頼するだけです。\n\n```text\n日本での転職準備を始めたいです。\nこのJDと私の経験を比較し、確認できないことはUnknownのままにしてください。\n来週の面接を準備したいです。\nこの職務経歴書を、ない根拠を足さずにレビューしてください。\n```''',
)

replace_once(
    "README.md",
    '''```bash\nnpx japan-career-agent setup    # via npm\nuvx japan-career-agent setup    # via uv, or: pipx run japan-career-agent setup\n```\n\nRun `setup` bare and it tells you which flags are still missing. The command it prints assumes\n`japan-career-agent` is on your PATH, which `npx` and `uvx` do not leave behind — put the same\nprefix back in front of it yourself.\n''',
    '''```bash\nnpx japan-career-agent          # via npm\nuvx japan-career-agent          # via uv, or: pipx run japan-career-agent\n```\n''',
)
replace_once("README.md", "japan-career-agent setup\ncareer-agent status", "japan-career-agent\ncareer-agent status")
replace_once(
    "README_ko.md",
    '''```bash\nnpx japan-career-agent setup    # npm 경유\nuvx japan-career-agent setup    # uv 경유, 또는: pipx run japan-career-agent setup\n```\n\n`setup`을 그냥 실행하면 어떤 플래그가 빠졌는지 알려줍니다. 다만 화면에 나온 다음 명령은\n`japan-career-agent`가 PATH에 있다고 가정하는데, `npx`나 `uvx`로 실행한 경우는 그게 남지 않습니다.\n출력된 명령 앞에 같은 접두사를 직접 다시 붙이세요.\n''',
    '''```bash\nnpx japan-career-agent          # npm 경유\nuvx japan-career-agent          # uv 경유, 또는: pipx run japan-career-agent\n```\n''',
)
replace_once("README_ko.md", "japan-career-agent setup\ncareer-agent status", "japan-career-agent\ncareer-agent status")
replace_once(
    "README_ja.md",
    '''```bash\nnpx japan-career-agent setup    # npm 経由\nuvx japan-career-agent setup    # uv 経由、または: pipx run japan-career-agent setup\n```\n\n`setup` をそのまま実行すると、どのフラグが足りないかを返します。ただし表示される次のコマンドは\n`japan-career-agent` が PATH にある前提で書かれており、`npx` や `uvx` 経由の実行はそれを残しま\nせん。表示されたコマンドの前に、同じ接頭辞を自分で付け直してください。\n''',
    '''```bash\nnpx japan-career-agent          # npm 経由\nuvx japan-career-agent          # uv 経由、または: pipx run japan-career-agent\n```\n''',
)
replace_once("README_ja.md", "japan-career-agent setup\ncareer-agent status", "japan-career-agent\ncareer-agent status")
replace_once("packaging/npm/README.md", "npx japan-career-agent init", "npx japan-career-agent")
replace_once("packaging/npm/README.md", "uvx japan-career-agent init", "uvx japan-career-agent")

# Release metadata: substantive runtime/UX changes get a normal source version bump.
replace_once("pyproject.toml", 'version = "2.25.0"', 'version = "2.26.0"')
replace_once(
    "CHANGELOG.md",
    "# Changelog\n\n",
    "# Changelog\n\n## [2.26.0] - 2026-09-04\n\n- Make the zero-argument command the thin default: prepare only an empty local record when needed and open the existing GUI. Explicit `ui` stays write-free and the full CLI remains available.\n- Remove raw internal vocabulary from Korean/Japanese GUI copy and lock a three-company application scenario where reusable confirmed evidence keeps every application to JD paste plus submit.\n\n",
)
for path in ("docs/upgrading.md", "docs/upgrading_ko.md", "docs/upgrading_ja.md"):
    replace_once(path, "2.25.0", "2.26.0")

print("thin user path patch applied")
