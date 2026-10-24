"""Create the first coordinator (there is no public way to become one).

    python -m app.scripts.create_coordinator "Ada Lovelace" ada@example.com
The password is read from the prompt, never from the command line.
"""
from __future__ import annotations

import getpass
import sys

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import User, UserRole, UserStatus


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    name, email = argv[1], argv[2].lower()
    password = getpass.getpass("Password (min 10 characters): ")
    if len(password) < 10:
        print("password too short")
        return 1
    with SessionLocal() as db:
        db.add(User(name=name, email=email, hashed_password=hash_password(password),
                    role=UserRole.COORDINATOR, status=UserStatus.ACTIVE))
        db.commit()
    print(f"created coordinator {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
