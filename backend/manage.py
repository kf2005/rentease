"""Management commands.

    python manage.py init-db        # create tables (idempotent)
    python manage.py seed           # add demo users, listings and inquiries
    python manage.py create-admin --email a@b.com --password '...' [--name 'Admin']
"""
import argparse
import getpass
import sys

from app import create_app
from app.auth import hash_password
from app.bootstrap import DEMO_PASSWORD, seed_demo_data
from app.config import Config
from app.db import commit, execute, query


def main():
    parser = argparse.ArgumentParser(description="RentEase management commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Create database tables")
    sub.add_parser("seed", help="Insert demo data")
    admin = sub.add_parser("create-admin", help="Create an admin user")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", help="Prompted if omitted")
    admin.add_argument("--name", default="Site Admin")
    args = parser.parse_args()

    app = create_app(Config(AUTO_MIGRATE=True))
    db = app.extensions["rentease_db"]

    if args.command == "init-db":
        db.migrate()
        print("Database schema is up to date.")
        return

    db.migrate()
    with app.app_context():
        if args.command == "seed":
            if seed_demo_data():
                print(f"Demo data added. All demo accounts use the password: {DEMO_PASSWORD}")
            else:
                print("Demo data already present; nothing to do.")
        elif args.command == "create-admin":
            password = args.password or getpass.getpass("Admin password: ")
            if len(password) < 8:
                sys.exit("Password must be at least 8 characters.")
            email = args.email.strip().lower()
            if query("SELECT id FROM users WHERE email = %s", (email,), one=True):
                sys.exit("A user with that email already exists.")
            execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'admin')",
                (args.name, email, hash_password(password)),
            )
            commit()
            print(f"Admin {email} created.")


if __name__ == "__main__":
    main()
