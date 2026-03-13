# ADR-002: FMC wingpy API Framework — Security & Hardening

**Status:** Active
**Date:** 2026-02-26 (updated 2026-03-13)

## Context

We need a standardized approach for automating Cisco Firepower Management Center (FMC) via its REST API. The `wingpy` library provides a Python SDK that handles authentication, token management, and API calls.

A subsequent security review (2026-03-13) identified hardening areas that all FMC tooling built on this framework must address: TLS certificate validation, API filter injection, input validation, path traversal, and file permissions. These patterns are derived from lessons learned in the `asa2fmc` project.

## Decision

Use `wingpy` as the sole FMC API client library, with environment-variable-based credential management and secure defaults.

---

## 1. Dependencies

| Package | Purpose |
|---------|---------|
| `wingpy` | FMC REST API client (primary dependency) |
| `httpx` | HTTP transport (transitive, installed by wingpy) |
| `loguru` | Structured logging (transitive, installed by wingpy) |

### Installation

```bash
# pip
pip install wingpy

# uv (recommended for speed)
uv pip install wingpy
```

---

## 2. Authentication

wingpy's `CiscoFMC` class handles authentication automatically:

- **Lazy auth** — token is acquired on first API call, not at instantiation
- **30-minute token lifetime** — matches FMC's default session timeout
- **3x automatic refresh** — wingpy retries token refresh up to 3 times before raising `AuthenticationFailure`

```python
from wingpy import CiscoFMC

fmc = CiscoFMC(
    host="10.0.0.1",
    username="api-user",
    password="secret",
    verify="/path/to/fmc-ca-bundle.pem",  # See §3 for TLS options
)
# No API call yet — auth happens on first .get() / .post() / etc.
```

---

## 3. Credential Storage

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `FMC_HOST` | FMC hostname or IP | Yes |
| `FMC_USERNAME` | API user username | Yes |
| `FMC_PASSWORD` | API user password | Yes |
| `FMC_VERIFY_SSL` | Verify TLS certificate (`true`/`false`) | No (default: `false`) |
| `FMC_CA_BUNDLE` | Path to CA bundle or self-signed cert (`.pem`) | No |

### `.env` File

Credentials are stored in a `.env` file that is **always gitignored**. A `.env.example` template is provided:

```
FMC_HOST=
FMC_USERNAME=
FMC_PASSWORD=
FMC_VERIFY_SSL=false
FMC_CA_BUNDLE=
```

### Loading Credentials

```python
import os
from dotenv import load_dotenv
from wingpy import CiscoFMC

load_dotenv()

def _resolve_verify():
    """Resolve TLS verify setting: CA bundle path > bool flag > False (fallback)."""
    ca_bundle = os.getenv("FMC_CA_BUNDLE")
    if ca_bundle:
        return os.path.realpath(os.path.expanduser(ca_bundle))
    return os.getenv("FMC_VERIFY_SSL", "false").lower() == "true"

fmc = CiscoFMC(
    host=os.environ["FMC_HOST"],
    username=os.environ["FMC_USERNAME"],
    password=os.environ["FMC_PASSWORD"],
    verify=_resolve_verify(),
)
```

> **Note:** When `verify=False` is used (no CA bundle configured), a warning should be logged. Operators should export the FMC self-signed certificate and set `FMC_CA_BUNDLE` in production.

---

## 4. API Explorer

Every FMC instance exposes an interactive API explorer:

```
https://<fmc-host>/api/api-explorer
```

Use this to:
- Discover available endpoints and HTTP methods
- View request/response schemas
- Find required and optional parameters
- Test API calls interactively

---

## 5. Minimum API User Permissions

FMC uses role-based access control for API users. Create a **dedicated API user** (do not reuse admin accounts).

| Use Case | FMC Role | Access Level |
|----------|----------|--------------|
| Read-only monitoring, reporting | Security Analyst (Read Only) | GET only |
| Configuration changes, policy deployment | Network Admin | GET, POST, PUT, DELETE |

### Best Practices

- Create a separate user account exclusively for API access
- Use the minimum role required for the task
- Rotate the API user password on a regular schedule
- Audit API activity via FMC's audit log

---

## 6. Code Examples

### Basic Usage

```python
from wingpy import CiscoFMC

fmc = CiscoFMC(host="10.0.0.1", username="api-user", password="secret", verify=False)

# Get a single object by UUID
network = fmc.get("/api/fmc_config/v1/domain/{domainUUID}/object/networks/{objectId}")

# Get all objects (handles pagination automatically)
all_networks = fmc.get_all("/api/fmc_config/v1/domain/{domainUUID}/object/networks")

# Create a new object
payload = {
    "name": "my-network",
    "value": "192.168.1.0/24",
    "type": "Network",
}
result = fmc.post("/api/fmc_config/v1/domain/{domainUUID}/object/networks", json=payload)

# Update an existing object
payload["id"] = result["id"]
payload["name"] = "my-network-updated"
fmc.put(f"/api/fmc_config/v1/domain/{domainUUID}/object/networks/{result['id']}", json=payload)

# Delete an object
fmc.delete(f"/api/fmc_config/v1/domain/{domainUUID}/object/networks/{result['id']}")
```

### Error Handling

```python
from wingpy import CiscoFMC, AuthenticationFailure

fmc = CiscoFMC(host="10.0.0.1", username="api-user", password="secret", verify=False)

try:
    networks = fmc.get_all("/api/fmc_config/v1/domain/{domainUUID}/object/networks")
except AuthenticationFailure:
    print("Authentication failed — check FMC_USERNAME and FMC_PASSWORD")
except Exception as e:
    print(f"API error: {e}")
```

---

## 7. Security Hardening (2026-03-13)

All tooling built on this framework must implement the following hardening patterns. These are derived from the `asa2fmc` security review and apply to any project that interacts with FMC.

### 7.1 TLS Certificate Verification

**Problem:** FMC typically uses self-signed certificates, leading developers to hardcode `verify=False`. This disables all TLS validation and exposes credentials to MITM attacks.

**Required pattern:** Support custom CA bundles via `FMC_CA_BUNDLE` environment variable (see §3). The `verify` parameter should accept:
- `str`: path to a custom CA bundle or self-signed cert file (preferred)
- `True`: use system CA store
- `False`: disable verification — logs a warning, acceptable only in development

**Trade-off:** Default still falls back to `verify=False` when no CA bundle is configured, to preserve backwards compatibility. Operators should export the FMC certificate and configure `FMC_CA_BUNDLE` in production.

### 7.2 UUID Validation for Bulk Operations

**Problem:** When building filter strings for bulk delete/update operations (e.g., `ids:id1,id2,...`), unvalidated IDs can inject additional filter parameters.

**Required pattern:** Validate all object IDs as proper UUIDs before building filter strings:

```python
import uuid

def validate_uuids(ids: list[str]) -> list[str]:
    """Validate and return list of UUID strings. Raises ValueError on invalid ID."""
    validated = []
    for id_str in ids:
        uuid.UUID(id_str)  # Raises ValueError if invalid
        validated.append(id_str)
    return validated
```

### 7.3 Object Name Validation

**Problem:** Object names from user-supplied files passed directly to the FMC API without validation. Names with special characters, excessive length, or control characters can cause unexpected behavior.

**Required pattern:** Validate object names before sending to FMC:
- Non-empty, max 128 characters (FMC limit)
- Allowed characters: `\w`, space, `.`, `:`, `/`, `-`

```python
import re

def validate_object_name(name: str) -> bool:
    """Validate FMC object name. Returns True if valid."""
    if not name or len(name) > 128:
        return False
    return bool(re.match(r'^[\w .:/\-]+$', name))
```

Invalid names should be logged and skipped rather than causing failures.

### 7.4 IP Address & Network Validation

**Problem:** IP addresses, CIDRs, and ranges from user input passed through to FMC without validation.

**Required pattern:** Validate all network values using Python's `ipaddress` module:

```python
import ipaddress

def validate_ip(value: str) -> bool:
    """Validate a single IP address."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

def validate_network(value: str) -> bool:
    """Validate a CIDR network."""
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False
```

### 7.5 Path Canonicalization

**Problem:** User-supplied file paths using `os.path.expanduser()` without `os.path.realpath()` or `Path.resolve()` allow symlink-based path traversal.

**Required pattern:** Always canonicalize user-supplied paths:

```python
from pathlib import Path

def safe_path(raw: str) -> Path:
    """Resolve and canonicalize a user-supplied path."""
    return Path(raw).expanduser().resolve()
```

### 7.6 Log File Permissions

**Problem:** Log files created with default umask (typically 0644) are world-readable. Logs may contain object names, IP addresses, and operational details.

**Required pattern:** Set log files to `0o640` (owner read/write, group read, no world access):

```python
import os

def secure_log_file(path: str):
    """Set restrictive permissions on log file."""
    os.chmod(path, 0o640)
```

### Hardening Properties

| Attack Vector | Without Hardening | With Hardening |
|--------------|-------------------|----------------|
| MITM on FMC connection | Possible (verify=False) | Mitigated with CA bundle |
| Filter injection via bulk operations | Possible with crafted IDs | Blocked by UUID validation |
| Malformed object names to API | Passed through | Validated and rejected |
| Invalid IPs/CIDRs | Passed through | Validated via ipaddress module |
| Symlink path traversal | Possible | Blocked by path canonicalization |
| Log file exposure | World-readable (0644) | Group-readable (0640) |

---

## Consequences

**Positive:**
- All FMC API automation uses a single, consistent pattern
- Credentials never appear in source code or version control
- Token lifecycle is managed automatically by wingpy
- API users follow least-privilege principle
- Defense-in-depth against injection, traversal, and MITM
- Invalid input fails early with clear log messages
- No breaking changes — existing workflows continue to work

**Negative:**
- Object names with unusual characters (outside `[\w .:/\-]`) are rejected
- Adds slight complexity to credential loading (CA bundle resolution)
- `verify=False` remains the fallback default when no CA bundle is configured
