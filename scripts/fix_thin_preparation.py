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
path.write_text(value, encoding="utf-8", newline="\n")
print("thin preparation targets corrected")
