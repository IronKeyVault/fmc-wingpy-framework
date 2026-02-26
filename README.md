# FMC wingpy Framework

Reusable framework for Cisco Firepower Management Center (FMC) API automation using the [wingpy](https://pypi.org/project/wingpy/) library.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in credentials
cp .env.example .env
# Edit .env with your FMC host, username, and password
```

## Documentation

- [ADR-001: ADR Index](docs/ADR/ADR-001-index.md)
- [ADR-002: FMC wingpy API Framework](docs/ADR/ADR-002-fmc-wingpy-api-framework.md)

## API Explorer

Every FMC instance exposes an interactive API explorer at:

```
https://<your-fmc-host>/api/api-explorer
```

Use this to discover available endpoints, required parameters, and response schemas.
