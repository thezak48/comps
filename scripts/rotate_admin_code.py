#!/usr/bin/env python3
"""
Rotate the invitation code that an account uses to sign in.

The invitation code doubles as the account's login credential, and there is no
in-app way to change it. Use this after an install has been running with a code
that shipped as a default, or whenever a credential needs replacing.

Usage:
  python scripts/rotate_admin_code.py
  python scripts/rotate_admin_code.py --username admin
  python scripts/rotate_admin_code.py --username admin --code "<value>"
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# Ensure project root is on sys.path.
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from auth import hash_invitation_code  # noqa: E402
from db import execute, query_one  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate an account's invitation code.")
    parser.add_argument("--username", default="admin", help="Account to rotate.")
    parser.add_argument("--code", default=None, help="New code. Generated if omitted.")
    args = parser.parse_args()

    row = query_one("SELECT id FROM users WHERE username = ?", (args.username,))
    if not row:
        print(f"No user named {args.username!r}.")
        return 1

    new_code = args.code or secrets.token_urlsafe(24)
    execute(
        "UPDATE users SET invitation_code_hash = ? WHERE id = ?",
        (hash_invitation_code(new_code), row[0]),
    )

    print(f"Rotated the invitation code for {args.username!r}.")
    print(f"New code: {new_code}")
    print("Record this value now; it is not stored in recoverable form.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
