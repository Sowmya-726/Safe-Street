"""Promote an existing registered user to admin. Does not create passwords."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from database.indexes import ensure_indexes  # noqa: E402
from database.json_store import JsonStore  # noqa: E402
from database.users import UserRepository  # noqa: E402
from safe_street.config import Config  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Grant admin role to an existing Safe Street user.")
    parser.add_argument("--email", required=True, help="Email of an already registered account")
    args = parser.parse_args()
    store = JsonStore(Config.DATA_ROOT / "local_store.json")
    users = UserRepository(store)
    ensure_indexes()
    user = users.find_by_email(args.email)
    if not user:
        print("No account found with that email. Register the user first, then run this script.")
        return 1
    updated = users.set_role(user["id"], "admin")
    print(f"Granted admin role to {updated['email']}. Sign in at /admin/login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
