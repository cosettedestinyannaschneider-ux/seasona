from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.core.security import hash_password


def main() -> int:
    print("Seasona 管理员密码哈希生成工具")
    print("本脚本只读取 Argon2id 配置并输出哈希，不连接数据库。")

    password = getpass("请输入密码: ")
    confirm = getpass("请再次输入密码: ")
    if password != confirm:
        print("两次输入的密码不一致。", file=sys.stderr)
        return 1
    if len(password) < 8:
        print("密码长度不能少于 8 位。", file=sys.stderr)
        return 1

    settings = get_settings()
    encoded = hash_password(
        password,
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        hash_len=settings.argon2_hash_len,
        salt_len=settings.argon2_salt_len,
    )
    print("\n可写入 user_account.password_hash 的 Argon2id 哈希:")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
