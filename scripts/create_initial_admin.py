import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import or_

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.helpers.auth import hash_password  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


def prompt_if_missing(value: str | None, prompt: str) -> str:
    if value:
        return value

    entered = input(prompt).strip()
    if not entered:
        raise ValueError(f"{prompt.rstrip(': ')} is required.")
    return entered


def prompt_password(value: str | None) -> str:
    if value:
        return value

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    return password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the first verified Admin user directly in the database."
    )
    parser.add_argument("--email", default=os.getenv("INITIAL_ADMIN_EMAIL"))
    parser.add_argument("--name", default=os.getenv("INITIAL_ADMIN_NAME"))
    parser.add_argument("--employee-id", default=os.getenv("INITIAL_ADMIN_EMPLOYEE_ID"))
    parser.add_argument("--password", default=os.getenv("INITIAL_ADMIN_PASSWORD"))
    parser.add_argument(
        "--allow-existing-users",
        action="store_true",
        help="Allow creating an admin even when the users table already has records.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        email = prompt_if_missing(args.email, "Email: ").lower()
        name = prompt_if_missing(args.name, "Name: ")
        employee_id = prompt_if_missing(args.employee_id, "Employee ID: ")
        password = prompt_password(args.password)
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count > 0 and not args.allow_existing_users:
            print(
                "Error: users already exist. Re-run with --allow-existing-users "
                "if you intentionally want to add another admin."
            )
            return 1

        existing_user = (
            db.query(User)
            .filter(or_(User.email == email, User.employee_id == employee_id))
            .first()
        )
        if existing_user is not None:
            if existing_user.email == email:
                print("Error: email already exists.")
            else:
                print("Error: employee ID already exists.")
            return 1

        admin = User(
            email=email,
            name=name,
            employee_id=employee_id,
            password=hash_password(password),
            role=UserRole.Admin,
            active=True,
            is_email_verified=True,
            qc_id=None,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"Created admin user #{admin.id}: {admin.email}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
