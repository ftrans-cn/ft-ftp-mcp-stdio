from __future__ import annotations

import argparse
import getpass

import keyring

from .config import load_config
from .credentials import SERVICE_NAME
from .doctor import run_doctor
from .errors import AppError
from .setup_wizard import run_setup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ft-ftp-mcp-stdio")
    commands = parser.add_subparsers(dest="command", required=True)
    cred = commands.add_parser("cred", help="管理 Windows keyring 中的服务器凭据")
    cred_commands = cred.add_subparsers(dest="cred_command", required=True)
    add = cred_commands.add_parser("add")
    add.add_argument("alias")
    list_command = cred_commands.add_parser("list")
    del list_command
    remove = cred_commands.add_parser("remove")
    remove.add_argument("alias")
    commands.add_parser("setup", help="交互式维护服务器配置")
    doctor = commands.add_parser("doctor", help="只读诊断运行环境和服务器连接")
    doctor.add_argument("--server", dest="server_alias")
    args = parser.parse_args(argv)

    if args.command == "setup":
        return run_setup()
    if args.command == "doctor":
        return run_doctor(args.server_alias)

    try:
        config = load_config()
    except AppError as exc:
        if args.cred_command == "list" and "配置文件不存在" in exc.message:
            print("未找到配置文件；请先创建 ~/.ft-ftp-mcp/config.json，再按服务器别名检查凭据。")
            return 0
        raise
    if args.cred_command != "list" and args.alias not in config.servers:
        raise AppError("not_found", f"服务器 {args.alias} 未在配置中定义")
    if args.cred_command == "add":
        server = config.servers[args.alias]
        prompt = f"Passphrase for {args.alias} (blank for unencrypted key): " if server.key_path else f"Password for {args.alias}: "
        password = getpass.getpass(prompt)
        if password:
            keyring.set_password(SERVICE_NAME, args.alias, password)
            print(f"Credential saved for {args.alias}.")
        elif server.key_path:
            try:
                keyring.delete_password(SERVICE_NAME, args.alias)
            except keyring.errors.PasswordDeleteError:
                pass
            print(f"Server {args.alias} uses an unencrypted private key; no passphrase stored.")
        else:
            raise AppError("credential_missing", "密码不能为空")
    elif args.cred_command == "remove":
        try:
            keyring.delete_password(SERVICE_NAME, args.alias)
        except keyring.errors.PasswordDeleteError as exc:
            raise AppError("not_found", f"未找到服务器 {args.alias} 的凭据") from exc
        print(f"Credential removed for {args.alias}.")
    else:
        for alias in sorted(config.servers):
            present = bool(keyring.get_password(SERVICE_NAME, alias))
            if present:
                status = "configured"
            elif config.servers[alias].key_path:
                status = "not required (unencrypted private key)"
            else:
                status = "missing"
            print(f"{alias}: {status}")
    return 0
