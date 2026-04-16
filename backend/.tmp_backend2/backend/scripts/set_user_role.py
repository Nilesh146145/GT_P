#!/usr/bin/env python3
"""
One-off: set a user's ``role`` in MongoDB (e.g. ``admin`` for billing admin APIs).

Usage (from ``backend/``):

  python3 scripts/set_user_role.py admin you@example.com
  python3 scripts/set_user_role.py enterprise you@example.com

Requires the same ``MONGODB_URL`` / ``DATABASE_NAME`` as the API (see ``.env``).

Warning: ``role`` ``admin`` users do **not** pass ``require_enterprise_org_member``;
use ``PLATFORM_ADMIN_EMAILS`` in ``.env`` if you need the same email for enterprise billing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Allow ``python scripts/set_user_role.py`` from repo ``backend/``
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from pymongo import MongoClient

from app.core.config import settings


def main() -> None:
    p = argparse.ArgumentParser(description="Set user role in MongoDB users collection.")
    p.add_argument(
        "role",
        choices=("admin", "enterprise", "reviewer"),
        help="New role value stored on the user document.",
    )
    p.add_argument("email", help="User email (case-insensitive match).")
    args = p.parse_args()
    email = args.email.strip().lower()
    email_rx = re.escape(email)

    client = MongoClient(settings.MONGODB_URL)
    try:
        col = client[settings.DATABASE_NAME]["users"]
        doc = col.find_one({"email": {"$regex": f"^{email_rx}$", "$options": "i"}})
        if not doc:
            print(f"No user found with email matching: {args.email!r}", file=sys.stderr)
            sys.exit(1)
        prev = doc.get("role")
        res = col.update_one({"_id": doc["_id"]}, {"$set": {"role": args.role}})
        if res.modified_count == 0 and prev == args.role:
            print(f"User {doc.get('email')} already has role {args.role!r}.")
        else:
            print(
                f"Updated user {doc.get('email')} (id={doc['_id']}): "
                f"role {prev!r} -> {args.role!r}."
            )
        if args.role == "admin":
            print(
                "\nNote: Admin users cannot call enterprise-only billing routes "
                "(portfolio, projects, etc.). Use PLATFORM_ADMIN_EMAILS for the same email "
                "as enterprise, or a separate enterprise account.",
                file=sys.stderr,
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
