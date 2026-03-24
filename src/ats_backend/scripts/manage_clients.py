import sys
import argparse
from ats_backend.core.database import db_manager
from ats_backend.services.client_service import ClientService
from ats_backend.auth.utils import get_password_hash
from ats_backend.auth.models import User

def create_client(name: str, domain: str):
    db_manager.initialize()
    with db_manager.get_session() as db:
        try:
            existing = ClientService.get_client_by_name(db, name)
            if existing:
                print(f"Error: Client '{name}' already exists.")
                return

            client, user, password = ClientService.provision_client_with_admin(db, name=name, email_domain=domain)
            db.commit()
            print("=== Fresh Client Created ===")
            print(f"Client Name: {client.name}")
            print(f"Client ID: {client.id}")
            print(f"Admin Email: {user.email}")
            print(f"Admin Password: {password}")
            print("============================")
        except Exception as e:
            db.rollback()
            print(f"Error: {e}")

def reset_password(email: str, new_password: str):
    db_manager.initialize()
    with db_manager.get_session() as db:
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                print(f"Error: User with email '{email}' not found.")
                return

            user.hashed_password = get_password_hash(new_password)
            db.commit()
            print(f"Success: Password for '{email}' has been reset to '{new_password}'.")
        except Exception as e:
            db.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage ATS Clients and Users")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    parser_create = subparsers.add_parser("create_client", help="Create a fresh client")
    parser_create.add_argument("name", type=str, help="Client name")
    parser_create.add_argument("domain", type=str, help="Email domain")

    parser_reset = subparsers.add_parser("reset_password", help="Reset a user password")
    parser_reset.add_argument("email", type=str, help="User email")
    parser_reset.add_argument("password", type=str, help="New password")

    args = parser_parse_args = parser.parse_args()

    if args.command == "create_client":
        create_client(args.name, args.domain)
    elif args.command == "reset_password":
        reset_password(args.email, args.password)
    else:
        parser.print_help()
