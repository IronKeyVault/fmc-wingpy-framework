#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralised FMC client factory.

Creates a configured CiscoFMC instance from stored credentials managed
by CredentialManager (OS keyring or encrypted local file).

Usage::

    from fmc_wingpy.client import get_fmc_client
    fmc = get_fmc_client()
"""
import logging
import os

from wingpy import CiscoFMC

from fmc_wingpy.config import CredentialManager, ConfigManager

log = logging.getLogger("fmc_wingpy")


def get_fmc_client(verify=None) -> CiscoFMC:
    """Create and return a configured CiscoFMC client from stored credentials.

    Args:
        verify: SSL verification setting.  Accepts:
                - None (default): use CA bundle from config if set, else False
                - True:  use default system CA bundle
                - False: disable verification (insecure, for self-signed certs)
                - str:   path to a custom CA bundle or self-signed cert file

    Returns:
        An authenticated CiscoFMC instance.

    Raises:
        SystemExit: If no credentials have been configured yet.
    """
    creds = CredentialManager.get_credentials()
    if not creds:
        raise SystemExit(
            "No FMC credentials configured. Run: fmc-wingpy --setup"
        )

    if verify is None:
        ca_bundle = ConfigManager.get("ca_bundle")
        if ca_bundle and os.path.isfile(ca_bundle):
            verify = ca_bundle
            log.debug("Using custom CA bundle: %s", ca_bundle)
        else:
            verify = False

    if verify is False:
        log.warning("TLS certificate verification is disabled (verify=False)")

    log.debug(
        "Creating FMC client for %s (user=%s)",
        creds["fmc_base_url"],
        creds["fmc_username"],
    )
    return CiscoFMC(
        base_url=creds["fmc_base_url"],
        username=creds["fmc_username"],
        password=creds["fmc_password"],
        verify=verify,
    )
