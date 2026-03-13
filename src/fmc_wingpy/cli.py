#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI entry point for fmc-wingpy.

Provides:
- --setup:  Interactive wizard to configure FMC connection and credentials
- --config: Show current configuration and credential storage backend
- --clear:  Clear stored credentials and configuration
"""
import argparse
import ipaddress
import logging
import os
import sys

from fmc_wingpy.config import CredentialManager, ConfigManager
from fmc_wingpy.logging_setup import setup_logging
from fmc_wingpy.terminal import (
    smart_input,
    get_password,
    confirm,
    prompt_with_default,
)
from fmc_wingpy.validation import safe_path

log = logging.getLogger("fmc_wingpy")


def interactive_setup() -> dict:
    """Interactive setup wizard for FMC connection details.

    Prompts for:
    - FMC IP/hostname
    - FMC username
    - FMC password
    - CA bundle path (optional)

    Returns:
        dict with setup values, or None if cancelled.
    """
    print("\n=== FMC wingpy Setup ===\n")

    # --- FMC host ---
    previous_url = ConfigManager.get("fmc_base_url")
    if previous_url:
        host_default = previous_url.replace("https://", "")
    else:
        host_default = ""

    fmc_host = prompt_with_default("FMC IP or hostname", host_default)
    if not fmc_host:
        print("FMC host is required.")
        return None

    # Ensure https:// prefix
    if not fmc_host.startswith("https://"):
        fmc_base_url = f"https://{fmc_host}"
    else:
        fmc_base_url = fmc_host

    # --- FMC username ---
    previous_user = ConfigManager.get("fmc_username", "")
    fmc_username = prompt_with_default("FMC username", previous_user)
    if not fmc_username:
        print("FMC username is required.")
        return None

    # --- FMC password ---
    existing_creds = CredentialManager.get_credentials()
    if existing_creds:
        reuse = confirm("Use stored password?", default=True)
        if reuse:
            fmc_password = existing_creds["fmc_password"]
        else:
            fmc_password = get_password("FMC password: ")
    else:
        fmc_password = get_password("FMC password: ")

    if not fmc_password:
        print("FMC password is required.")
        return None

    # --- CA bundle (optional) ---
    previous_ca = ConfigManager.get("ca_bundle", "")
    ca_bundle_raw = prompt_with_default(
        "CA bundle path (optional, for TLS verification)", previous_ca
    )
    ca_bundle = ""
    if ca_bundle_raw:
        ca_path = safe_path(ca_bundle_raw)
        if ca_path.is_file():
            ca_bundle = str(ca_path)
        else:
            print(f"Warning: CA bundle not found at {ca_path}")
            if not confirm("Continue without CA bundle?", default=True):
                return None

    # --- Summary ---
    print("\n--- Configuration Summary ---")
    print(f"  FMC URL:    {fmc_base_url}")
    print(f"  Username:   {fmc_username}")
    print(f"  Password:   {'***' * 3}")
    if ca_bundle:
        print(f"  CA bundle:  {ca_bundle}")
    else:
        print("  CA bundle:  (none — TLS verification disabled)")
    print(f"  Storage:    {CredentialManager.get_storage_backend()}")
    print()

    if not confirm("Save this configuration?", default=True):
        print("Setup cancelled.")
        return None

    return {
        "fmc_base_url": fmc_base_url,
        "fmc_username": fmc_username,
        "fmc_password": fmc_password,
        "ca_bundle": ca_bundle,
    }


def cmd_setup():
    """Handle --setup: run interactive wizard and store results."""
    result = interactive_setup()
    if not result:
        sys.exit(1)

    CredentialManager.set_credentials(
        result["fmc_base_url"],
        result["fmc_username"],
        result["fmc_password"],
    )
    ConfigManager.set("fmc_base_url", result["fmc_base_url"])
    ConfigManager.set("fmc_username", result["fmc_username"])
    if result["ca_bundle"]:
        ConfigManager.set("ca_bundle", result["ca_bundle"])

    print("\nSetup complete. You can now use:")
    print("  from fmc_wingpy.client import get_fmc_client")
    print("  fmc = get_fmc_client()")


def cmd_show_config():
    """Handle --config: display current configuration."""
    print("\n=== FMC wingpy Configuration ===\n")

    fmc_url = ConfigManager.get("fmc_base_url", "(not set)")
    fmc_user = ConfigManager.get("fmc_username", "(not set)")
    ca_bundle = ConfigManager.get("ca_bundle", "(not set)")
    log_file = ConfigManager.get_log_file()

    print(f"  FMC URL:       {fmc_url}")
    print(f"  Username:      {fmc_user}")
    print(f"  CA bundle:     {ca_bundle}")
    print(f"  Credentials:   {CredentialManager.get_storage_backend()}")
    print(f"  Log file:      {log_file}")
    print()


def cmd_clear():
    """Handle --clear: wipe stored credentials and config."""
    if not confirm("Clear all stored credentials and configuration?", default=False):
        print("Cancelled.")
        return
    CredentialManager.clear_credentials()
    ConfigManager.clear()
    print("Credentials and configuration cleared.")


def main():
    parser = argparse.ArgumentParser(
        prog="fmc-wingpy",
        description="FMC wingpy framework — secure FMC automation",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true", help="Run interactive setup wizard")
    group.add_argument("--config", action="store_true", help="Show current configuration")
    group.add_argument("--clear", action="store_true", help="Clear stored credentials and config")

    args = parser.parse_args()

    setup_logging(console=True)

    if args.setup:
        cmd_setup()
    elif args.config:
        cmd_show_config()
    elif args.clear:
        cmd_clear()


if __name__ == "__main__":
    main()
