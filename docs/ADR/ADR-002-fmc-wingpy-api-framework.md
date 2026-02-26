# ADR-002: FMC wingpy API Framework

**Status:** Active
**Date:** 2026-02-26

## Context

We need a standardized approach for automating Cisco Firepower Management Center (FMC) via its REST API. The `wingpy` library provides a Python SDK that handles authentication, token management, and API calls.

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
    verify=False,  # Set True in production with valid certs
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

### `.env` File

Credentials are stored in a `.env` file that is **always gitignored**. A `.env.example` template is provided:

```
FMC_HOST=
FMC_USERNAME=
FMC_PASSWORD=
FMC_VERIFY_SSL=false
```

### Loading Credentials

```python
import os
from dotenv import load_dotenv
from wingpy import CiscoFMC

load_dotenv()

fmc = CiscoFMC(
    host=os.environ["FMC_HOST"],
    username=os.environ["FMC_USERNAME"],
    password=os.environ["FMC_PASSWORD"],
    verify=os.getenv("FMC_VERIFY_SSL", "false").lower() == "true",
)
```

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

## Consequences

- All FMC API automation uses a single, consistent pattern
- Credentials never appear in source code or version control
- Token lifecycle is managed automatically by wingpy
- API users follow least-privilege principle
