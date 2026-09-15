"""Commandes locales sensibles pour administrer le premier supercompte."""

import argparse
from getpass import getpass

from werkzeug.security import generate_password_hash

if __package__:
    from . import database
else:
    import database


def create_superadmin(username):
    database.initialise_database()
    if any(user["role"] == "superadmin" for user in database.users()):
        raise SystemExit("Un supercompte protégé existe déjà.")
    if database.user_credentials(username):
        raise SystemExit(f"Le compte {username!r} existe déjà.")

    password = getpass("Mot de passe du supercompte : ")
    confirmation = getpass("Confirmer le mot de passe : ")
    if password != confirmation:
        raise SystemExit("Les deux mots de passe ne correspondent pas.")
    if len(password) < 6:
        raise SystemExit("Le mot de passe doit contenir au moins 6 caractères.")

    database.create_user(
        username=username.strip(),
        password_hash=generate_password_hash(password),
        role="superadmin",
        is_protected=True,
    )
    print(f"Supercompte {username!r} créé. Son mot de passe est stocké sous forme de hash.")


def main():
    parser = argparse.ArgumentParser(description="Administration locale du BDE ORT Sup")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-superadmin", help="Créer l’unique supercompte protégé")
    create.add_argument("--username", required=True)
    arguments = parser.parse_args()

    if arguments.command == "create-superadmin":
        create_superadmin(arguments.username)


if __name__ == "__main__":
    main()
