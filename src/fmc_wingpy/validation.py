#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Input validation helpers — ADR-002 §7.

Provides reusable validators for:
- UUID (bulk operations)
- FMC object names
- IP addresses and CIDR networks
- User-supplied file paths
"""
import ipaddress
import re
import uuid
from pathlib import Path


def validate_uuid(value: str) -> str:
    """Validate and return a UUID string. Raises ValueError if invalid."""
    return str(uuid.UUID(value))


def validate_uuids(ids: list) -> list:
    """Validate a list of UUID strings. Raises ValueError on first invalid ID."""
    return [validate_uuid(id_str) for id_str in ids]


def validate_object_name(name: str) -> bool:
    """Validate an FMC object name.

    Rules (FMC enforced):
    - Non-empty, max 128 characters
    - Allowed characters: word chars, space, . : / -
    """
    if not name or len(name) > 128:
        return False
    return bool(re.match(r'^[\w .:/\-]+$', name))


def validate_ip(value: str) -> bool:
    """Validate a single IP address (v4 or v6)."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_network(value: str) -> bool:
    """Validate a CIDR network (e.g. 192.168.1.0/24)."""
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False


def validate_ip_range(start: str, end: str) -> bool:
    """Validate an IP range (both endpoints must be valid IPs)."""
    return validate_ip(start) and validate_ip(end)


def safe_path(raw: str) -> Path:
    """Resolve and canonicalize a user-supplied path.

    Prevents symlink-based path traversal by resolving to absolute path.
    """
    return Path(raw).expanduser().resolve()
