from __future__ import annotations

import argparse
import getpass

import keyring

from .config import McpSettings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("set", "delete"))
    args = parser.parse_args()
    settings = McpSettings()
    if args.action == "set":
        token = getpass.getpass("ERP API token: ")
        if not token:
            raise SystemExit("Token must not be empty")
        keyring.set_password(
            settings.credential_service,
            settings.credential_name,
            token,
        )
        print("Credential stored.")
    else:
        try:
            keyring.delete_password(
                settings.credential_service,
                settings.credential_name,
            )
        except keyring.errors.PasswordDeleteError:
            pass
        print("Credential removed.")
