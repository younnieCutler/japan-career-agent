#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("apply_thin_user_path.py")
value = path.read_text(encoding="utf-8")
value = value.replace(
    '''replace_once(\n    "skills/career-agent/command_line.py",\n    "from vault import CareerVault, today, utc_now",\n    "from vault import CareerVault, initialize_vault, today, utc_now",\n)\n''',
    "",
)
value = value.replace(
    '''replace_once(\n    "skills/career-agent/command_line.py",\n    ''' + "'''" + '''        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)\\n        try:\\n            return serve_gui(''' + "'''" + ''',\n    ''' + "'''" + '''        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)\\n        if getattr(args, "_quickstart", False) and not ui_vault.initialized():\\n            initialize_vault(ui_vault.path)\\n        try:\\n            return serve_gui(''' + "'''" + ''',\n)''',
    '''replace_once(\n    "skills/career-agent/dispatch.py",\n    ''' + "'''" + '''        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)\\n        try:\\n            return serve_gui(''' + "'''" + ''',\n    ''' + "'''" + '''        ui_vault = CareerVault(Path(args.vault).expanduser()) if args.vault else CareerVault(DEFAULT_VAULT_PATH)\\n        if getattr(args, "_quickstart", False) and not ui_vault.initialized():\\n            initialize_vault(ui_vault.path)\\n        try:\\n            return serve_gui(''' + "'''" + ''',\n)''',
)
value = value.replace(
    'patch.object(command_line, "DEFAULT_VAULT_PATH", vault)',
    'patch("dispatch.DEFAULT_VAULT_PATH", vault)',
)
value = value.replace(
    '"projection_written", "career vault", "canonical", "context", "evidence",',
    '"projection_written", "career vault", "canonical", "evidence",',
)
extra_copy = '''    '"trust.local_detail": "이 화면의 작업은 로컬 Career Vault에 저장됩니다. 명시적으로 확정하기 전에는 신뢰 기록이 바뀌지 않습니다.",':\n        '"trust.local_detail": "이 화면의 작업은 이 기기에만 저장됩니다. 명시적으로 확정하기 전에는 확인된 경력 기록이 바뀌지 않습니다.",',\n    '"state.loading": "Career Vault를 확인하고 있습니다.",':\n        '"state.loading": "저장된 경력 기록을 확인하고 있습니다.",',\n    '"review.intro": "아래 내용 그대로 Career Vault의 신뢰 기록에 추가됩니다.",':\n        '"review.intro": "확정하면 아래 내용이 경력 기록에 추가됩니다.",',\n    '"success.experience_approved_body": "Career Vault의 신뢰 기록에 추가되었으며 지원에서 재사용할 수 있습니다.",':\n        '"success.experience_approved_body": "확인된 경력 기록에 추가되어 지원에서 재사용할 수 있습니다.",',\n    '"error.data_unchanged": "저장된 Career Vault 데이터는 바뀌지 않았습니다.",':\n        '"error.data_unchanged": "저장된 경력 기록은 바뀌지 않았습니다.",',\n    '"trust.local_detail": "この画面の作業はローカルのCareer Vaultに保存されます。明示的に確定するまで信頼済み記録は変わりません。",':\n        '"trust.local_detail": "この画面の作業はこの端末だけに保存されます。明示的に確定するまで確認済みの経歴記録は変わりません。",',\n    '"state.loading": "Career Vaultを確認しています。",':\n        '"state.loading": "保存された経歴記録を確認しています。",',\n    '"review.intro": "以下の内容がそのままCareer Vaultの信頼済み記録に追加されます。",':\n        '"review.intro": "確定すると、以下の内容が経歴記録に追加されます。",',\n    '"success.experience_approved_body": "Career Vaultの信頼済み記録に追加され、応募で再利用できます。",':\n        '"success.experience_approved_body": "確認済みの経歴記録に追加され、応募で再利用できます。",',\n    '"error.data_unchanged": "保存済みCareer Vaultデータは変わっていません。",':\n        '"error.data_unchanged": "保存済みの経歴記録は変わっていません。",',\n'''
value = value.replace(
    '}\nfor old, new in copy_replacements.items():',
    extra_copy + '}\nfor old, new in copy_replacements.items():',
    1,
)
path.write_text(value, encoding="utf-8", newline="\n")
print("thin preparation targets and copy cleanup corrected")
